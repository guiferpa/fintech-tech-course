# Module 2, Wednesday: idempotency at every hop

[Module 2](../../modules/02-end-to-end-idempotency.md) · [Leia em português](day-3.pt-BR.md)

**Reading time:** about 45 minutes. Use the rest of the 2-hour block on the Stripe pages at the end, then draw the flow described in section 5.

This is an original text written for this course. It is based on the references listed at the end, and each section names the source it follows.

## Why this matters for a fintech

On Monday and Tuesday you learned the two patterns: idempotency keys at the API, processed messages at the consumer. Real flows chain several hops, and a single hop without protection is enough to send money twice. Today you look at how a real provider documents its idempotency contract, learn to tell which operations are already safe to repeat, and then draw the whole wallet flow, marking every point where a duplicate is stopped. That drawing is the answer to this module's mastery question. The lab then turns it into the test cases for Thursday.

## 1. How a real provider documents the contract

*Main source: Stripe API reference, "Idempotent requests", and Stripe docs, "Advanced error handling".*

Stripe's API reference page on idempotent requests is short, and every sentence on it is a design decision. Reading it as an API designer, rather than as a Stripe user, is the best preparation for writing your own `docs/m02.md`. Here is what it specifies for API v1, with the decision behind each point.

| What Stripe documents | The decision behind it |
| --- | --- |
| The client generates the key; Stripe suggests V4 UUIDs or another random string with enough entropy | The key identifies the operation, and only the client knows when an operation is new |
| Keys can be up to 255 characters | A fixed upper limit you can enforce with a `CHECK` |
| Don't put sensitive data, such as email addresses, in the key | Keys get logged and stored; they should carry no meaning |
| Stripe saves the status code and body of the first request once the endpoint starts executing | A retry gets exactly the first answer, not a fresh computation |
| Retries return the saved response, **including `500` errors** | A replay is a replay, even of a failure |
| Keys can be removed once they are at least 24 hours old; a reused key after that is a new request | Keys give near-term safety, not a permanent archive |
| Incoming parameters are compared to the original, and a mismatch is an error | The same key with a different body is a client bug, not a retry |
| Nothing is saved if validation fails or another request with the same key is executing concurrently | Those requests can simply be retried |
| All `POST` requests accept keys; sending them on `GET` or `DELETE` has no effect | Those verbs are idempotent by definition |

The reference page sums up the purpose in one line: "When creating or updating an object, use an idempotency key."

Stripe's "Advanced error handling" page, linked from the reference, adds the client side of the contract. Four points are worth copying into your notes:

- **A `409` means another request with the same key is still running.** The page tells you to wait and retry with the same key and parameters, and warns that a new key can start a second operation.
- **A `500` is indeterminate.** The operation might have produced side effects. Don't retry with a new key until you know what happened: fetch the object, check the dashboard, or wait for webhooks. This is Module 1's `UNKNOWN` state, written by a payment company.
- **There is a retry window.** Keep retrying with the same key for up to 24 hours. After that, stop and reconcile instead of retrying with either the old key or a new one.
- **Replays are labelled.** A response served from the idempotency layer carries the header `Idempotent-Replayed: true`, and a `Stripe-Should-Retry` header can tell the client whether to retry.

The same page lists two ways to build keys: a random UUID v4, or a key derived from an object the user already has, such as a shopping cart ID. That second option leads straight into the next section. One more detail: Stripe's newer API v2 uses a different replay behavior and a 30-day window, which shows that even the provider's contract is a choice, not a law of nature.

## 2. Natural keys and client keys

*Main source: course synthesis, using the Stripe docs above and Brandur Leach's Rocket Rides design.*

An idempotency key answers one question: "Is this the same operation I've already seen?" There are two ways to get that identity.

A **client key** is an arbitrary random value the client generates for the occasion, like the `Idempotency-Key` header. It carries no business meaning. It only works if the client stores it and reuses it on retries.

A **natural key** is an identifier that already exists in the domain and is unique for each real operation. Examples in a wallet:

- **The Pix end-to-end ID (`end_to_end_id`).** Every Pix payment carries a unique end-to-end identifier that all participants use to refer to that payment. When your wallet receives an incoming Pix notification from the partner bank, that ID is the natural deduplication key. Two notifications with the same `end_to_end_id` are the same payment, so you credit the user once.
- **A boleto or invoice ID** when a user pays a bill.
- **The partner's transfer ID** when the partner sends you a status update about a transfer.
- **A cart or order ID**, the example in Stripe's docs.

Natural keys are attractive because you don't need the client to behave well. The rule is enforced by a `UNIQUE` constraint on a column that has to exist anyway:

```sql
CREATE TABLE incoming_pix (
  id             BIGSERIAL PRIMARY KEY,
  end_to_end_id  TEXT NOT NULL UNIQUE,
  account_id     BIGINT NOT NULL REFERENCES accounts (id),
  amount_cents   BIGINT NOT NULL CHECK (amount_cents > 0),
  received_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

A natural key has two limits. First, it only exists when the domain gives you one: "send R$ 200 to Ana" from a mobile app has no natural ID until your system creates the transfer. That is why the API uses a client key. Second, a natural key identifies the business event, not the HTTP request. It can tell you "already credited", but it doesn't store the response to replay.

A useful rule of thumb: **use a natural key whenever the domain provides one, and a client key where it doesn't.** Many flows use both. The client key protects the API call that creates a transfer. The transfer's own ID then becomes the natural key for every later hop.

## 3. Naturally idempotent operations

*Main source: course synthesis, building on the Stripe blog's "Making liberal use of idempotency" and Richardson's `AccountDebited` example.*

Some writes are safe to repeat without any key, because their result doesn't depend on how many times they run. Others change state by a relative amount, and every repeat does damage.

Compare these two statements:

```sql
-- Naturally idempotent: a conditional state transition.
UPDATE transfers
SET status = 'COMPLETED', completed_at = now()
WHERE id = $1 AND status = 'PENDING';

-- Not idempotent: a relative change.
UPDATE accounts
SET balance_cents = balance_cents - 10000
WHERE id = $1;
```

The first runs once with effect. The second time, the `WHERE` clause matches no row, so nothing changes. The row count (1 the first time, 0 after) also tells the code whether this call did the work, which is useful for deciding whether to emit an event.

The second statement subtracts R$ 100 every time it runs. This is exactly Richardson's `AccountDebited` example: the consumer is correct only if it never sees the same message twice, and at-least-once delivery guarantees it will.

| Operation | Idempotent by nature? | How to make it safe |
| --- | --- | --- |
| `SET status = 'COMPLETED' WHERE status = 'PENDING'` | Yes | Nothing extra; check the row count |
| `SET email = 'ana@example.com'` | Yes | Nothing extra |
| `INSERT ... ON CONFLICT (end_to_end_id) DO NOTHING` | Yes | The unique constraint is the protection |
| `SET balance = balance - 100` | No | Key or processed message in the same transaction |
| `INSERT INTO ledger_entries ...` without a unique reference | No | Add a unique `(transfer_id, leg)` or similar |
| Partner call "send R$ 200" | No | Forward a stable key to the partner |

The design goal follows from the table: **turn relative changes into state transitions or into inserts guarded by a unique key.** A ledger is the classic example. Instead of updating a balance, you insert entries, each with a unique reference to the transfer that caused it. Module 4 builds the ledger on this idea. For now, notice that a unique constraint on the entry's reference makes posting naturally idempotent.

## 4. Forwarding the key to the provider

*Main source: Brandur Leach, "Implementing Stripe-like Idempotency Keys in Postgres", section "Calling Stripe", and the Stripe docs above.*

Your API can be perfectly idempotent and still send money twice if the call to the partner bank is not. The worker times out, retries, and the partner sees two separate requests. The fix is to send an idempotency key to the partner, but which key?

Brandur's Rocket Rides shows the answer: build the forwarded key from **your own durable record**, not from the client's raw value. Rocket Rides uses `rocket-rides-atomic-` plus the internal ID of the idempotency key row. For the wallet, the transfer ID is a natural choice: `wallet-transfer-812`. Three properties make this work:

1. **It exists before the call.** The transfer row is committed in an atomic phase before the worker calls the partner (Monday's rule).
2. **It is the same on every attempt.** Whether the retry comes from the same worker, a different pod, the completer or a reconciliation job, they all read the same transfer row and send the same key.
3. **It is unique across your whole system.** Two users who sent the same client key would still get different forwarded keys.

```typescript
// Worker calling the partner bank; the key comes from the committed transfer row.
const res = await this.partner.post('/payments', payload, {
  headers: { 'Idempotency-Key': `wallet-transfer-${transfer.id}` },
  timeout: 10_000,
});
```

Then read the provider's contract as carefully as you read Stripe's. Ask how long it keeps keys, what it returns for a key in flight, and whether it replays errors. If your retries can last longer than the provider's key window, the key no longer protects you. At that point, follow Stripe's own advice for its clients: stop retrying and **query the status** by your reference instead. If the partner supports no key at all, fall back on Brandur's "Complications" advice from Tuesday: treat ambiguous failures as unknown and reconcile, never as safe to retry.

In Thursday's capstone, the fake partner bank also deduplicates by this header. That lets your test prove the whole chain, not only the API.

## 5. Putting it together: every idempotency point in the flow

*Main source: course synthesis of this week's three readings.*

Here is the flow for "send R$ 200 to another bank", with every hop where a duplicate could appear and what stops it.

```text
 Mobile app
   | POST /transfers, Idempotency-Key: K (generated once, reused on retry)
   v
 [1] API ............. idempotency_keys UNIQUE (user_id, key)
   |                    same key + same body  -> stored response
   |                    same key + other body -> 422
   |                    still in flight       -> 409
   | tx: transfer row + hold + outgoing message, all committed together
   v
 [2] Queue ........... at-least-once: the message may arrive twice
   |                    message_id = transfer id (stable)
   v
 [3] Worker .......... processed_messages UNIQUE (subscriber_id, message_id)
   |                    + conditional update: status 'PENDING' -> 'SENDING'
   | Idempotency-Key: wallet-transfer-<id>
   v
 [4] Partner bank .... dedupes by the forwarded key; timeout -> UNKNOWN, query later
   |
   v
 [5] Partner webhook . dedupe by partner transfer ID (natural key)
                        + conditional update 'SENDING' -> 'COMPLETED'
```

And the reasons, one per point, which is what the mastery test asks you to say out loud:

| Point | What can duplicate | What stops it | Why here |
| --- | --- | --- | --- |
| 1. API | Client retries after a timeout | Client key, stored response, lock | Only the client knows which attempts are the same operation |
| 2. Queue | The API publishing twice, or the broker redelivering | A stable message ID taken from the transfer | The ID must be fixed before the message leaves |
| 3. Worker | Redelivery after a crash before the ack | Processed messages in the same transaction as the effect, plus state transitions | Brokers promise at least once, not exactly once |
| 4. Partner | The worker retrying a call that timed out | Forwarded key derived from the transfer ID | The call is a foreign state mutation; your transaction can't undo it |
| 5. Webhook | The partner resending the notification | Natural key and conditional update | Notifications are at least once too |

One sentence holds the whole drawing: **every hop is at least once, so every receiver must deduplicate, and every ID must be fixed before it crosses a boundary.**

## 6. Preparing Thursday's tests

*Main source: this module's capstone tasks.*

Today's lab is to list the test cases and create the empty migrations, without writing capstone code. Here are the four cases from the module page, with what each one should prove.

| Test | Setup | Expected |
| --- | --- | --- |
| Same key, same body | Send a transfer, wait for `201`, send it again | Second response equals the first (status and body); one transfer in the database |
| Same key, different body | Send a transfer, then the same key with another amount | `422`; still one transfer, with the first amount |
| Request still in flight | Make the partner slow, send the same key twice without waiting | One gets the result, the other gets `409`; one transfer |
| 50 concurrent | Fire 50 requests with the same key at once | Exactly one transfer, one hold, one partner call; the rest get `409` or the stored response |

A few cases are worth adding to the list even if you don't code them all on Thursday: the same key from two different users (two transfers), a worker that receives the same message twice (one ledger posting), and a partner call that times out and is retried (one payment at the partner).

For the migrations, create empty files for `idempotency_keys` and `processed_messages`. Write the columns as comments, decide the unique constraints, and note the lock timeout you'll use. The code waits for Thursday.

## Notes to write today

1. From the Stripe reference: key length, expiry, what is replayed (including `500`), what happens on a parameter mismatch and on a concurrent request.
2. Natural key vs. client key, with the Pix `end_to_end_id` as the natural key example and the `Idempotency-Key` header as the client key example.
3. Two SQL statements side by side: a naturally idempotent one (`SET status ... WHERE status = 'PENDING'`) and a non-idempotent one (`balance = balance - 100`), and how you'd make the second safe.
4. How you forward the key to the provider, and what you do when its key window has passed.
5. On paper: API -> queue -> worker -> provider, with every idempotency point and the reason for each. Keep this page for the mastery test.

## Check yourself

These make good flashcards (see the [flashcards guide](../../FLASHCARDS.md)).

- What does Stripe return when you retry a key whose first attempt got a `500`?
- What does Stripe tell a client to do after a `409` on an idempotent request?
- When is a natural key better than a client key, and when can't you use one?
- Why is `UPDATE ... SET status = 'COMPLETED' WHERE status = 'PENDING'` safe to repeat?
- Why should the key forwarded to the partner come from your transfer ID rather than the client's key?
- In the API -> queue -> worker -> provider flow, which hop does a processed-messages table protect?
- What should you do when an operation is still unknown after the provider's key window?

## References

- **Main source (section 1):** Stripe API reference, ["Idempotent requests"](https://docs.stripe.com/api/idempotent_requests). Short; read all of it. Free.
- Stripe documentation, ["Advanced error handling"](https://docs.stripe.com/error-low-level), sections "Content errors", "Server errors" and "Idempotency". The client side of the same contract. Free.
- **Main source (section 4):** Brandur Leach, ["Implementing Stripe-like Idempotency Keys in Postgres"](https://brandur.org/idempotency-keys), sections "Calling Stripe" and "Complications". Free. You read it on Monday and Tuesday; reread these two parts.
- Chris Richardson, ["Pattern: Idempotent Consumer"](https://microservices.io/patterns/communication-style/idempotent-consumer.html), microservices.io, for point 3 of the drawing. Free.
- On paper (no reference): natural key vs. client key, naturally idempotent vs. non-idempotent operations, forwarding the key, and the full flow drawing. Sections 2 to 6 of this text are your guide.
