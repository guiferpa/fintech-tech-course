# Module 2, Tuesday: recovering interrupted requests and idempotent consumers

[Module 2](../../modules/02-end-to-end-idempotency.md) · [Leia em português](day-2.pt-BR.md)

**Reading time:** about 45 minutes. Use the rest of the 2-hour block on the references at the end.

This is an original text written for this course. It is based on the references listed at the end, and each section names the source it follows.

## Why this matters for a fintech

Yesterday's design covers a request that fails and comes back with the same key. Two gaps remain. First, some clients never come back: the user deletes the app, or the calling service loses its state. Their half-finished transfers still need an ending. Second, much of a wallet's work doesn't arrive over HTTP at all. It arrives as messages from a broker, and brokers deliver some messages more than once. Today closes both gaps: the second half of Brandur's article for the first, and Chris Richardson's Idempotent Consumer pattern for the second.

## 1. Taking the key: the upsert and the lock

*Main source: Brandur Leach, "Implementing Stripe-like Idempotency Keys in Postgres", section "Idempotency key upsert".*

Every request with a key starts the same way: find the key or create it, and make sure no other attempt is working on it at the same moment. Brandur's Rocket Rides handles four cases.

| Situation when the request arrives | What Rocket Rides does |
| --- | --- |
| The key doesn't exist | Insert it, locked, at recovery point `started` |
| The key exists, but the parameters differ | Reject with `409 Conflict` (params mismatch) |
| The key exists and is locked by a recent attempt | Reject with `409 Conflict` (request in progress) |
| The key exists and its lock has expired | Take the lock and continue from the recovery point |

A key already at `finished` is not locked again. The request simply returns the stored response code and body.

Two details make this safe under concurrency. The unique index on `(user_id, idempotency_key)` means only one of two simultaneous inserts can succeed. Brandur also runs the phase in a `SERIALIZABLE` transaction, so if two transactions try to lock the same key, Postgres aborts one of them.

The lock is a timestamp, `locked_at`, rather than a flag. A process that crashes while holding it can't release it, so a lock older than a timeout is treated as abandoned and can be taken over. Brandur's code refers to a constant for that timeout but the article doesn't give a value. You will choose one for the capstone. It must be longer than your slowest legitimate request, including the call to the partner bank.

This course's capstone uses slightly different status codes from Rocket Rides: `409` when the key is still in flight, and `422 Unprocessable Content` when the same key arrives with a different body. Separating them helps the client: a `409` means "wait and retry", while a `422` means "your client has a bug, retrying won't help".

In Postgres, the "insert or find" step can be a single statement:

```sql
INSERT INTO idempotency_keys
  (user_id, idempotency_key, request_method, request_path, request_hash)
VALUES ($1, $2, 'POST', '/transfers', $3)
ON CONFLICT (user_id, idempotency_key) DO NOTHING
RETURNING id;
```

If a row comes back, this request created the key and owns it. If nothing comes back, the key already existed, and the code reads it to decide between returning the stored response, `409` or `422`. Under the default `READ COMMITTED` level, a second insert of the same key waits for the first transaction to commit or roll back before deciding there is a conflict. That waiting is exactly what keeps 50 concurrent requests from creating 50 keys.

## 2. Walking the state machine

*Main source: Brandur Leach, "Implementing Stripe-like Idempotency Keys in Postgres", sections "A directed and acyclic state machine", "Calling Stripe" and "Send receipt and finish".*

Once a request owns the key, it runs a loop: read the recovery point, run the phase that comes next, commit the phase together with the new recovery point, repeat. Brandur calls the set of recovery points a directed acyclic state machine. It only moves forward, and any unknown state is treated as a bug.

| Recovery point | Next step | New recovery point |
| --- | --- | --- |
| `started` | Create the ride and the audit record (one transaction) | `ride_created` |
| `ride_created` | Charge through Stripe, save the charge ID | `charge_created` |
| `charge_created` | Stage the receipt job, store the response | `finished` |
| `finished` | Return the stored response | (stop) |

Two details from the Stripe call matter for this week's capstone.

**The key is forwarded, but not as-is.** Rocket Rides passes its own idempotency key to Stripe, built from the internal row ID of the key (`rocket-rides-atomic-#{key.id}`) rather than the client's raw value. Because the row ID is unique across all users, the forwarded key is too. If the server dies while waiting for Stripe, the retry sends the same forwarded key, and Stripe's own idempotency layer stops a second charge. Your Thursday task 3 does the same with the fake partner bank.

**Errors are sorted into final and temporary.** A card error from Stripe is final: Rocket Rides stores a `402` response and moves the key to `finished`, so every retry gets the same answer. Other Stripe errors map to a `503`. In the "Murphy in action" section, the article says the client is told to retry when Stripe is down. Read the code closely, though: the sample stores the `503` as a finished response. Ask yourself which you want in your design. A temporary error should leave the key **unfinished**, so a retry or the completer can try again. Only a definite answer should be stored as final.

The last phase writes a `send_ride_receipt` job to `staged_jobs`, returns `201` and sets the recovery point to `finished`, all in one transaction.

## 3. Murphy in action: every failure has an ending

*Main source: Brandur Leach, "Implementing Stripe-like Idempotency Keys in Postgres", section "Murphy in action".*

Brandur walks through the failures one by one and shows that each ends in a correct state. Here is the same list, translated to a wallet transfer.

| Failure | What happens |
| --- | --- |
| The connection breaks before reaching the API | The client retries with the same key; the first attempt to arrive does the work |
| Two attempts with the same key arrive together | The unique index lets one insert win; the other gets `409` |
| Postgres goes down right after the key is created | The client keeps retrying; when Postgres returns, the key is found and the request resumes |
| The partner bank is down | The partner phase fails; the client is told to retry later; the transfer stays at `transfer_created` |
| The API process dies while waiting for the partner | The retry resumes from `transfer_created` and sends the **same forwarded key**; the partner deduplicates |
| A bad deploy returns 500s in the middle of the flow | After the fix ships, retries succeed; if the client has gone away, the completer finishes the request |

The last row introduces the processes that keep things moving when no client is around.

## 4. The completer, the enqueuer and the reaper

*Main source: Brandur Leach, "Implementing Stripe-like Idempotency Keys in Postgres", section "Other processes".*

Brandur's design relies on three background processes.

- **The enqueuer** moves jobs from `staged_jobs` to the real job queue, but only after the transaction that inserted them has committed. This is what makes "send the receipt" part of an atomic phase without making the request wait for the email.
- **The completer** looks for requests that started but never finished and whose clients seem to have gone away. It pushes them to completion by running the same code path from the stored recovery point, using the stored request parameters and an internal way to authenticate as the original user. Brandur stresses how little it needs to know: "It doesn’t even have to have special knowledge about how the stack is implemented." That only works because the request parameters and the recovery point are on the key.
- **The reaper** deletes old keys. Brandur first says keys can be recycled after "24 hours or so", and later suggests the reaper wait about 72 hours. His reason for the longer window is practical: if a bad deploy breaks requests on Friday night, the team has until Monday to ship a fix and let the completer finish the stuck requests. An ideal reaper also flags requests it couldn't finish so that a human can look at them.

In a wallet, the completer is not optional. A transfer stuck at `transfer_created` holds money on the sender's account. Somebody has to either send it to the partner or release the hold. For the capstone you only need to know where the completer would plug in; Module 1's `UNKNOWN` status and the reconciliation job are close cousins of the same idea.

Brandur ends the article with the idea of a **passively safe** system: whatever fails, the system lands in a stable state, and active processes like the completer drive it to full consistency later. In his words: "Ideally, human operators never have to intervene to fix things (or at least as infrequently as possible)."

## 5. When the other side can't help you

*Main source: Brandur Leach, "Implementing Stripe-like Idempotency Keys in Postgres", section "Complications".*

The whole design leans on two assumptions. Brandur names what to do when they break.

**The foreign service isn't idempotent.** If the partner bank accepts no idempotency key and offers no way to look up a transfer by your reference, a failed call may not be safe to retry. Brandur's conservative answer is to mark the operation as permanently failed, unless the error explicitly says that retrying is safe. Ambiguous errors such as timeouts and connection resets count as failures. In payments, "permanently failed" usually means "send to manual reconciliation", not "tell the customer it failed". His real lesson is to push every service you depend on to support idempotency.

**The local store isn't transactional.** Without ACID transactions, you can't group local changes into atomic phases, so every write behaves like a foreign state mutation. This is one reason this course keeps the money in Postgres.

Brandur also points out that the same idea works for plain web forms: a hidden field with a key generated when the form is rendered stops a double click from charging twice.

## 6. The idempotent consumer

*Main source: Chris Richardson, microservices.io, "Pattern: Idempotent Consumer".*

Now the second gap. Your wallet doesn't only receive HTTP requests. After a transfer is accepted, a message like `TransferRequested` goes to a broker, and a worker consumes it to post ledger entries or call the partner bank.

Richardson's pattern starts from a fact about brokers: most of them guarantee **at-least-once** delivery. A consumer may crash after doing the work but before acknowledging the message, and the broker will then deliver it again. The page asks the problem directly: "How does a message consumer handle duplicate messages correctly?" Its example is an account service that consumes an `AccountDebited` event and subtracts the amount from the balance. Process it twice and the balance is wrong.

The solution has three parts:

1. Every message carries a unique **message ID**.
2. The consumer records the IDs of the messages it has processed, either in a separate `PROCESSED_MESSAGES` table or in the business rows it creates.
3. The ID is recorded **in the same database transaction** as the effect.

The table's key is `(subscriber_id, message_id)`. When a duplicate arrives, inserting its ID violates the key, the transaction rolls back, and the consumer ignores the message. The subscriber ID matters because several consumers may process the same message for different reasons: the ledger poster and the notification sender each need their own record.

Point 3 is what makes the pattern correct. Look at the two wrong orders:

| Order | Crash between the two steps leads to |
| --- | --- |
| Record the ID, commit, then apply the effect | The ID is saved, the effect is lost; the redelivery is skipped forever |
| Apply the effect, commit, then record the ID | The effect is saved, the ID is not; the redelivery applies it twice |
| Both in one transaction | Either both are saved or neither is; the redelivery does the right thing |

A Postgres-flavored version uses `ON CONFLICT DO NOTHING` instead of catching a unique violation. The logic is the same as Richardson's: no new row means the message was already processed.

```typescript
// Consumer of TransferRequested, using node-postgres.
async handle(msg: TransferRequested): Promise<void> {
  const client = await this.pool.connect();
  try {
    await client.query('BEGIN');
    const res = await client.query(
      `INSERT INTO processed_messages (subscriber_id, message_id)
       VALUES ($1, $2)
       ON CONFLICT (subscriber_id, message_id) DO NOTHING`,
      ['ledger-poster', msg.messageId],
    );
    if (res.rowCount === 1) {
      await this.postEntries(client, msg); // the effect, same transaction
    }
    await client.query('COMMIT');
  } catch (err) {
    await client.query('ROLLBACK');
    throw err; // the broker will redeliver
  } finally {
    client.release();
  }
}
```

Acknowledge the message to the broker only after `COMMIT`. If the process dies before the acknowledgement, the message comes back, the insert finds the existing row, and nothing is applied twice.

The pattern protects effects **inside your database**. If the consumer's effect is a call to the partner bank, the processed-messages table can't cover it, because the call is a foreign state mutation. For that hop you need what Brandur showed: commit the intent first, then call the partner with a key derived from your own record. Wednesday puts all of these points on one drawing.

## 7. Two patterns, one idea

*Main source: Brandur Leach's article and Richardson's pattern, compared side by side.*

The API pattern and the consumer pattern look different but share one move: **give the operation a stable identity, and let a unique constraint in the same transaction as the effect decide whether it has already happened.**

| | API with idempotency keys | Idempotent consumer |
| --- | --- | --- |
| Who chooses the ID | The client (`Idempotency-Key`) | The producer (`message_id`) |
| Where it is stored | `idempotency_keys`, unique on `(user_id, key)` | `processed_messages`, unique on `(subscriber_id, message_id)` |
| What a duplicate gets | The stored response | Silently ignored |
| Concurrent duplicate | `409` while in flight | Waits on the unique index, then skips |
| Multi-step work | Recovery points | Usually one transaction per message |

## Notes to write today

1. The four cases of the key upsert (new, different parameters, in flight, lock expired) and the status code your capstone returns for each.
2. Why the forwarded key to the provider is derived from your internal record, and what it protects against.
3. What the completer, the enqueuer and the reaper each do, in one line each.
4. The idempotent consumer: at-least-once delivery, a `processed_messages` table keyed by `(subscriber_id, message_id)`, and why it must be written in the same transaction as the effect.

## Check yourself

These make good flashcards (see the [flashcards guide](../../FLASHCARDS.md)).

- Why is `locked_at` a timestamp and not a boolean?
- What should a temporary error from the provider do to the key's state, and what should a definite one do?
- What does the completer need stored on the key to finish a request without the client?
- Why does Brandur suggest keeping keys for about 72 hours rather than 24?
- What happens if a consumer records the message ID and commits before applying the effect?
- Why is the processed-messages key `(subscriber_id, message_id)` and not just `message_id`?
- Why can't a processed-messages table protect a call to the partner bank?

## References

- **Main source (sections 1 to 5):** Brandur Leach, ["Implementing Stripe-like Idempotency Keys in Postgres"](https://brandur.org/idempotency-keys), second half: from "Idempotency key upsert" to the end, including "Other processes", "Murphy in action", "Complications" and "Cultivating passive safety". Free.
- **Main source (sections 6 and 7):** Chris Richardson, ["Pattern: Idempotent Consumer"](https://microservices.io/patterns/communication-style/idempotent-consumer.html), microservices.io. Short; read all of it. Free.
