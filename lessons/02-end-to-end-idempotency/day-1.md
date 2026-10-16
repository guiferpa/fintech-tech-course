# Module 2, Monday: idempotency keys and atomic phases

[Module 2](../../modules/02-end-to-end-idempotency.md) · [Leia em português](day-1.pt-BR.md)

**Reading time:** about 45 minutes. Use the rest of the 2-hour block on the references at the end, starting with the sections marked as the main source.

This is an original text written for this course. It is based on the references listed at the end, and each section names the source it follows. Where an idea comes from a specific author, the text says so.

## Why this matters for a fintech

Module 1 ended with a rule: a timeout means "I don't know". The client of your wallet API will hit that rule every day. A phone loses signal in an elevator, a load balancer drops a connection, a pod restarts in the middle of a request. The client's only reasonable move is to try again.

Retrying is easy. Retrying a transfer without sending the money twice is the hard part. This week you close that gap at every hop of the flow: the API, the message consumers and the call to the partner bank. Today covers the first hop: what an idempotency key is, how a client should use it, and how the server should split its work so that a retry can pick up where the last attempt stopped.

## 1. Three ways a request can fail

*Main source: Stripe blog, "Designing robust and predictable APIs with idempotency", section "Planning for failure".*

In 2017, Brandur Leach, then on Stripe's API team, wrote the blog post that most engineers point to when they explain idempotency keys. It starts from a simple observation: a network call can break at three different moments, and each one leaves the client with a different amount of knowledge.

| When it breaks | What happened on the server | Is a blind retry safe? |
| --- | --- | --- |
| The connection never opens | Nothing | Yes |
| The connection breaks while the server is working | Some of the work may be done | Not obviously |
| The server finishes, but the response is lost | All of the work is done | No, it repeats the effect |

The first case is harmless. The third is the dangerous one, and it is exactly Module 1's "the request arrived and was processed, but the response was lost". The middle case is the most interesting, because the server may be left in a half-finished state. Most of today's second source is about that middle case.

Take a wallet user who taps "Send R$ 200" to a friend. If the client sees a timeout, it cannot tell which row of the table it is in. If it retries and the server treats the retry as a new request, the friend receives R$ 400 and the sender loses R$ 400. If it doesn't retry, the sender may never know whether the money left.

## 2. Some operations are idempotent by nature

*Main source: Stripe blog, "Designing robust and predictable APIs with idempotency", section "Making liberal use of idempotency".*

An operation is **idempotent** when doing it twice has the same effect as doing it once. The client can call an idempotent endpoint as many times as it needs until it sees a success.

The Stripe post uses a DNS example: a `PUT` that creates a DNS record can be repeated safely, because the second call finds the record already there and simply reports success. It also reminds the reader that HTTP defines `PUT` and `DELETE` as idempotent. `GET` has no side effects at all, so it is safe to repeat too. `POST` carries no such promise.

Many wallet operations can be written so that they are idempotent by nature:

- "Set the user's notification email to `ana@example.com`" gives the same final state no matter how many times it runs.
- "Cancel transfer 812" can be written so that a second call finds the transfer already cancelled and does nothing.
- "Mark transfer 812 as `COMPLETED`" is safe to repeat if it only moves the transfer from `PENDING`.

The trouble is the operations whose whole point is to change something by a relative amount: "debit R$ 200", "charge the card", "create a transfer". Running these twice is never the same as running them once. Wednesday comes back to this distinction in detail, with SQL.

## 3. Idempotency keys: making a non-idempotent call safe to retry

*Main source: Stripe blog, "Designing robust and predictable APIs with idempotency", sections "Guaranteeing exactly once semantics" and "Being a good distributed citizen".*

For operations that must not happen twice, the Stripe post describes the mechanism that Stripe's API uses: the client generates a unique value, the **idempotency key**, and sends it with the request in the `Idempotency-Key` HTTP header. If the request fails, the client retries with **the same key**. The server uses the key to recognize the retry and to decide what to do, depending on where the first attempt broke:

- **The connection never opened.** The server sees the key for the first time and processes the request normally.
- **The server failed midway.** The server resumes the work or safely rolls it back. How it does that depends on the implementation, which is what Brandur's second article explains.
- **The response was lost.** The server returns the stored result of the first attempt and does not run the operation again.

From the outside, the client gets "exactly once" behavior for the effect, even though the request itself may be sent many times. In the post's own summary: "Use idempotency and idempotency keys to allow clients to pass a unique value and retry requests as needed."

### What this means for the client

The key belongs to the **operation**, not to the HTTP attempt. That has practical consequences for your wallet's mobile app or for any service that calls your API:

1. Generate the key once, when the user confirms the transfer, not inside the retry loop.
2. Store it with the pending operation (on the device or in the calling service's database) so a retry after an app restart still uses it.
3. Send the same key and the same body on every attempt.
4. Only generate a new key when the user starts a genuinely new operation.

A client that creates a fresh UUID per HTTP attempt has idempotency keys in name only. Every retry looks new to the server.

### Retrying politely

The post's last technical section is about how often to retry. If thousands of clients retry immediately after a server hiccup, they keep the server down. It recommends **exponential backoff**: wait longer after each failure (for example 1 s, 2 s, 4 s, 8 s). It also recommends adding random **jitter** to each wait. Without jitter, clients that failed at the same moment retry at the same moment too, and the post calls that burst a "thundering herd".

```typescript
// Client side: one key per operation, reused on every attempt.
async function sendTransfer(body: TransferBody, key: string) {
  for (let attempt = 0; attempt < 5; attempt++) {
    try {
      return await http.post('/transfers', body, {
        headers: { 'Idempotency-Key': key },
        timeout: 5_000,
      });
    } catch (err) {
      if (!isRetryable(err)) throw err;
      const base = 2 ** attempt * 1_000;
      await sleep(base / 2 + Math.random() * (base / 2)); // backoff with jitter
    }
  }
  throw new Error('Gave up: outcome unknown, check status later');
}
```

Notice the final error message. After the last attempt the client still doesn't know whether the transfer happened. It should show "processing" and query the status later, never "failed".

The post closes with three principles, which make a good summary of this section: handle failures **consistently** (clients retry), **safely** (idempotency keys) and **responsibly** (exponential backoff with jitter).

## 4. Foreign state mutations: the part a transaction can't undo

*Main source: Brandur Leach, "Implementing Stripe-like Idempotency Keys in Postgres", sections "Rocket Rides" and "Foreign state mutations".*

The Stripe post tells you what the server must do. Brandur's longer article, on his own site, shows how to build it with Postgres. He defines the term like this: "An idempotency key is a unique value that’s generated by a client and sent to an API along with a request." The server stores the key, tracks the request's progress against it and, once the request finishes, stores the result so that a repeat with the same key gets the same answer.

His running example is Rocket Rides, a demo ride-sharing app from Stripe. Creating a ride runs seven steps: insert the idempotency key, create a ride, create an audit record, charge the user through Stripe, save the charge ID on the ride, email a receipt, and store the final response on the key. He then lists what goes wrong in production: the database refuses an insert or loses the connection, the call to Stripe times out, the email provider fails, or the client simply disconnects halfway.

The central idea of the article is the **foreign state mutation**: a change made in a system outside your own database. A Stripe charge is one. So is an email, a DNS record or, in our case, a transfer sent to the partner bank. Brandur also counts calls to your own internal services and publishing to Kafka as foreign, because they can fail independently of your transaction.

Why does the distinction matter? Inside Postgres, a failed transaction rolls back and leaves no trace. Outside it, there is no rollback. As Brandur puts it, "once we make our first foreign state mutation, we’re committed one way or another." He notes that two-phase commit could in theory roll back across systems, but it is complex enough that real software rarely uses it.

Map this onto a wallet transfer out to another bank:

| Step | Local or foreign? |
| --- | --- |
| Insert the idempotency key | Local |
| Create the `transfers` row and place a hold on the sender's balance | Local |
| Write an audit record | Local |
| Ask the partner bank to send the money | **Foreign** |
| Save the partner's transfer ID | Local |
| Send a push notification | Foreign, but can be deferred |
| Store the response on the key | Local |

## 5. Atomic phases

*Main source: Brandur Leach, "Implementing Stripe-like Idempotency Keys in Postgres", section "Atomic phases".*

Brandur's answer is to group the local steps into **atomic phases**. An atomic phase is a set of local changes committed together in one database transaction, sitting between two foreign state mutations. Postgres guarantees that either all of them happen or none do.

The key rule is short: "Atomic phases should be safely committed before initiating any foreign state mutation." Before you call the partner bank, the `transfers` row, the hold and the audit record must already be committed. If the call then fails, crashes or times out, your database still records that the attempt was made. A retry, or a background process, can find it and continue. If you called the partner bank first and crashed before committing, you would have sent money with no local record of why.

Each foreign call gets its own phase boundary, and all the local work between two foreign calls goes into a single phase. For the wallet transfer, that gives:

1. **Phase 1 (transaction):** insert or lock the idempotency key.
2. **Phase 2 (transaction):** create the transfer, place the hold, write the audit record.
3. **Foreign call:** ask the partner bank to send the money.
4. **Phase 3 (transaction):** save the partner's ID and update the transfer.
5. **Phase 4 (transaction):** schedule the notification and store the final response on the key.

Brandur adds one more technique. Work that doesn't have to happen inside the request, like the receipt email, should become a background job. He writes the job into a `staged_jobs` table **in the same transaction** as the phase, so it only becomes visible to workers after the commit. A separate process moves committed jobs to the real queue. The payment call, however, can't be deferred in Rocket Rides, because the request must tell the user whether the charge succeeded. Later modules come back to this "write the message in the same transaction" idea, because it is the core of the outbox pattern.

## 6. Recovery points

*Main source: Brandur Leach, "Implementing Stripe-like Idempotency Keys in Postgres", sections "Recovery points" and "The idempotency key relation".*

If a request dies between phases, the retry needs to know where to restart. Brandur stores that on the key itself, in a column called `recovery_point`. He describes a recovery point as "a name of a check point that we get to after having successfully executed any atomic phase." Rocket Rides uses four: `started`, `ride_created`, `charge_created` and `finished`.

The important detail is that the recovery point is updated **inside the same transaction as the phase it marks**. The phase's data and the checkpoint commit together or not at all, so the checkpoint can never claim work that isn't there.

The recovery points form a path that only moves forward. A retry reads the current point and jumps to the next phase. A request at `finished` doesn't run anything again: the server just returns the stored response.

Here is a sketch of what that table could look like for the wallet. It follows the shape of Brandur's `idempotency_keys` table, adapted to this course's names:

```sql
CREATE TABLE idempotency_keys (
  id               BIGSERIAL PRIMARY KEY,
  user_id          BIGINT      NOT NULL REFERENCES users (id),
  idempotency_key  TEXT        NOT NULL CHECK (char_length(idempotency_key) <= 255),
  request_method   TEXT        NOT NULL,
  request_path     TEXT        NOT NULL,
  request_hash     TEXT        NOT NULL,          -- hash of the request body
  recovery_point   TEXT        NOT NULL DEFAULT 'started',
  locked_at        TIMESTAMPTZ DEFAULT now(),     -- NULL when no one is working on it
  response_code    INT,
  response_body    JSONB,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  last_run_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (user_id, idempotency_key)
);
```

A few choices are worth noticing, and you will defend them in `docs/m02.md` on Friday:

- The uniqueness is on `(user_id, idempotency_key)`, as in Brandur's schema. Two users who happen to send the same key never collide, and one user can't replay another user's response.
- Brandur stores the full request parameters as JSONB so a retry with different parameters can be rejected and an unfinished request can be completed later. This course's capstone stores a hash of the body for the comparison; if you want a background completer, you also need the parameters themselves.
- `locked_at` marks that some process is working on the key right now. Tuesday covers how it prevents two attempts from running at once.
- Brandur says keys are short-lived: "Keys are not meant to be used as a permanent request archive but rather as a mechanism for ensuring near-term correctness." A cleanup job deletes old rows.

With a wallet transfer, the recovery points would be `started`, `transfer_created`, `partner_called` and `finished`. Writing the transfer out as phases, foreign calls and recovery points is today's main exercise.

## Notes to write today

1. The three moments a request can fail (before the connection, midway, after the work with the response lost), and what the server must do with a retried key in each.
2. How a good client uses an idempotency key: when it creates the key, where it keeps it, and what it sends on each retry. Add one line on backoff with jitter.
3. Brandur's definitions, in your own words: foreign state mutation, atomic phase, recovery point.
4. The wallet "send money to another bank" flow split into atomic phases and foreign calls, with a recovery point after each phase.

## Check yourself

These make good flashcards (see the [flashcards guide](../../FLASHCARDS.md)).

- Why must a client reuse the same idempotency key on every retry of one operation?
- Which of the three failure moments makes a blind retry repeat the effect?
- Why does jitter matter when many clients retry at once?
- What is a foreign state mutation, and why can't a database transaction undo it?
- What must be committed before the call to the partner bank, and why?
- Why is the recovery point updated in the same transaction as its phase?
- Why is the unique constraint on `(user_id, idempotency_key)` rather than on the key alone?

## References

- **Main source (sections 1 to 3):** Brandur Leach, ["Designing robust and predictable APIs with idempotency"](https://stripe.com/blog/idempotency), Stripe blog, 2017. Read all of it; it is short. Free.
- **Main source (sections 4 to 6):** Brandur Leach, ["Implementing Stripe-like Idempotency Keys in Postgres"](https://brandur.org/idempotency-keys), first half: from the start through "Atomic phases" and the schema in "The idempotency key relation". Free. Tuesday covers the second half.
