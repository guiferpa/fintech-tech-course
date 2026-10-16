# Module 5, Wednesday: retries, DLQ, event sourcing and signed webhooks

[Module 5](../../modules/05-messaging-and-events.md) · [Leia em português](day-3.pt-BR.md)

**Reading time:** about 45 minutes. Use the rest of the 2-hour block on the references at the end, then sketch the chaos scripts for the capstone.

This is an original text written for this course. It is based on the references listed at the end, and each section names the source it follows. Where an idea comes from a specific author, the text says so.

## Why this matters for a fintech

Tuesday's consumer is correct when everything eventually works. Real consumers meet events they can't process: a partner API that is down for ten minutes, a payload with a currency your code doesn't know, a bug introduced in yesterday's deploy. If the consumer keeps retrying the same record, the whole partition stops, and every account that hashes to it stops getting updates.

Today covers three topics that close the module. First, how to retry without blocking (retry topics and a dead letter queue). Second, how to keep out-of-order events from moving state backwards, and how event sourcing treats events as the state itself. Third, how to send events to the outside world as webhooks that the receiver can trust. Thursday and Friday's capstone implements all of it.

## 1. Why retrying in place blocks the partition

*Main source: Uber Engineering, "Building Reliable Reprocessing and Dead Letter Queues with Apache Kafka", sections on simple retries and their problems.*

The Uber article opens with a sentence worth memorizing: "In distributed systems, retries are inevitable." The team built it for its driver insurance product, where a Kafka event triggers a payment call.

The simplest design retries inside the consumer: call the service, and on failure wait and try again until it works. The article lists the problems:

- **The partition is blocked.** The consumer never commits the offset of the failing record, so it keeps re-reading the same record, and newer records wait behind it. One bad record holds back every healthy record in its partition.
- **Retry metadata is hard to keep.** Knowing how many times a record was tried, and when, is awkward when the record never leaves its place.

In the wallet, partition 3 might hold 1/6 of all accounts. A single malformed event for one account would freeze balance notifications for every account on that partition. A message that fails every time, no matter how often you retry it, is called a **poison message**. The Uber article doesn't use that term, but it describes the case: errors from bugs or bad data won't fix themselves, unlike network blips.

## 2. Retry topics and the dead letter queue

*Main source: Uber Engineering, "Building Reliable Reprocessing and Dead Letter Queues with Apache Kafka", sections on separate queues and their benefits.*

Uber's answer is to take the failing record out of the main flow. The consumer tries a record a fixed number of times. If it still fails, the consumer publishes it to a **retry topic**, then commits the offset on the main topic and moves on. The partition is free again.

There is a ladder of retry topics, each with its own consumers and a longer delay than the previous one. A failure on one level sends the record to the next. A failure on the last level sends it to the **dead letter queue (DLQ)**, a topic where records wait for a human or a tool. The article stresses that the delays are best-effort: a handler runs at least after its delay, possibly later. The delay is enforced by holding consumption in each retry queue until a record is old enough.

```text
wallet.account-events  --fail x3-->  wallet.account-events.retry-1 (wait ~1 min)
                                         --fail-->  .retry-2 (wait ~10 min)
                                         --fail-->  .dlq  (alert; replay by command)
```

Those topic names and delays are an example for this course. The article doesn't prescribe a naming scheme or specific delays.

The article recommends separating error types. Transient errors (timeouts, a 503 from a partner) go through the retry ladder. Non-retryable errors (a validation failure, a bug) can go straight to the DLQ, because retrying them only wastes capacity. For **replay**, Uber's tooling can list, purge and merge the DLQ: "Dead letter messages are merged to re-enter processing by being published back into the first retry topic." Capstone task 2 asks for exactly this command.

Two things the pattern costs you, both mentioned in the article's "other considerations":

- **Ordering.** A record that goes to a retry topic is processed after newer records for the same key. If event 7 for `acc-1` fails and event 8 succeeds, the account sees 8 before 7. Section 3 shows how to make that harmless.
- **Idempotency.** A record can be tried on several levels, and the article notes that consumers must be idempotent. Your inbox from Tuesday already covers this.

**Backpressure** is the other side of retries. The article doesn't use the word, but it describes the idea: the delay ladder limits how fast failing records come back, so a struggling downstream service isn't hammered by retries. On a single consumer, the `KafkaConsumer` Javadoc describes `pause()` and `resume()` for partitions, under "Consumption Flow Control". A consumer that sees the partner bank's circuit breaker open (Module 9) can pause its partitions instead of failing every record into the retry ladder. Kafka's pull model helps here: a consumer that stops polling simply lets records accumulate in the log, where they are safe.

## 3. Out-of-order events must not move state backwards

*Main source: this course's capstone rule, built on Jay Kreps's point (Monday) that order comes from sequence numbers, not clocks.*

Retry topics, producer re-sends and DLQ replays all mean that an older event can arrive after a newer one. The pass criteria say out-of-order events must never move state backwards. The tool is a **version** (a per-entity sequence number) set by the producer, in the same transaction that changed the state.

Say the accounts service emits `AccountStatusChanged` with `version` 1, 2, 3. A consumer that keeps a local copy of account status applies an event only if it is newer than what it has:

```sql
UPDATE account_status_view
SET status = $2, version = $3, updated_at = now()
WHERE account_id = $1
  AND version < $3;   -- equal or older versions change nothing
-- 0 rows updated: stale or duplicate event, skip it and commit the offset
```

This is capstone task 3. Note what it does not use: `created_at` or the Kafka timestamp. Module 1 explained why wall clocks can't order events across machines.

Versions work for "latest state" views. They are wrong for events whose effects add up, like credits. A late credit is not stale; it still has to be applied once. For those, use the inbox to guarantee once, and make the projection tolerate any order, for example by summing ledger entries instead of overwriting a balance.

## 4. Event sourcing: events as the state

*Main source: Martin Fowler, "Event Sourcing".*

So far, events have been notifications about changes stored in tables. Fowler describes a stronger idea: "Event Sourcing ensures that all changes to application state are stored as a sequence of events." The events are the record of truth. Current state is something you compute from them.

Fowler explains that keeping the history alone is a small gain. The value comes from what you can do with the log:

- **Complete rebuild.** Throw away the current state and replay all events from empty to rebuild it.
- **Temporal query.** Compute the state as it was at any past moment, by replaying events up to that moment.
- **Event replay.** If a past event was wrong, correct it and recompute the consequences.

Replaying everything is slow, so systems keep **snapshots** of current state and replay only newer events. Fowler notes that since the state is derived from the log, "you can cache it anywhere you like". He also covers **reversing events**: easiest when each event is a difference (for example "debit 30") rather than a new absolute value.

The hard part in his article is the outside world. Replaying events must not send real messages again, so Fowler recommends wrapping external systems in **gateways** that do nothing during replay. External queries are also a problem: if processing an event asked a partner for an FX rate, a replay must use the rate from that time, so you log the response. In a wallet, that means: never let a replay re-send a Pix transfer or a webhook, and store the FX rate on the event.

Fowler points out that accounting is a natural fit, since ledger entries are already a log of changes to an account. Your Module 6 ledger, an append-only list of entries where balances are derived, is event sourcing in practice even if you never call it that. For the capstone you don't need a full event-sourced service. You need the habits: immutable events, versions, and replays without side effects.

## 5. CQRS in one page

*Main source: Martin Fowler, "CQRS" (bliki).*

Fowler's short note on CQRS starts: "CQRS stands for Command Query Responsibility Segregation." The idea, which he credits to Greg Young, is to use one model to change data and a different model to read it. The read models are often built from the events that the write side emits, so CQRS and event sourcing are frequently used together.

In a wallet, the write side is the ledger with strict transactions. The read side could be a statement table or a search index, updated by a consumer of `wallet.account-events`. The read side is eventually consistent: a transfer may take a moment to show up in the statement.

Fowler is blunt about the risk: "Despite these benefits, you should be very cautious about using CQRS." He says most systems fit a simple CRUD model, and CQRS belongs only in specific parts of a system. In an interview, mention that the statement is a CQRS-style read model, and that the balance check before a debit must never read from it.

## 6. Signed webhooks: the Standard Webhooks specification

*Main source: Standard Webhooks specification, sections "Verifying webhook authenticity" and "Operational considerations".*

Webhooks are events delivered over HTTP to another company: a merchant learning that a payment settled, or your wallet learning from a partner bank that a Pix arrived. The receiver must be able to check that the request is genuine, recent, and not a duplicate. The Standard Webhooks specification is an open specification that defines a common format for this.

**Headers.** Every request carries three:

| Header | Content |
| --- | --- |
| `webhook-id` | Unique ID of the message; stays the same on every retry |
| `webhook-timestamp` | Unix time in seconds when the message was sent |
| `webhook-signature` | One or more signatures separated by spaces, each like `v1,<base64>` |

**Signature.** The spec says: "The content to be signed is therefore: `msg_id.timestamp.payload`." The sender computes HMAC-SHA256 over that string with a shared secret, encodes it in base64 and prefixes it with `v1,`. Secrets are random, 24 to 64 bytes, base64-encoded and prefixed with `whsec_`. The spec also defines `v1a` signatures with ed25519 for asymmetric keys.

Each part of the signed content has a job:

- The **body** is protected against changes.
- The **timestamp** lets the receiver reject old requests, which blocks replay attacks. The spec says to check that it is within a tolerance, without fixing a value; a few minutes is common.
- The **id** is the idempotency key. A receiver that already processed that `webhook-id` acknowledges and does nothing.

Verification in NestJS, using Node's `crypto`:

```ts
import { createHmac, timingSafeEqual } from 'node:crypto';

function verify(rawBody: string, h: Record<string, string>, secret: string): boolean {
  const ts = Number(h['webhook-timestamp']);
  if (Math.abs(Date.now() / 1000 - ts) > 300) return false; // 5-minute tolerance

  const key = Buffer.from(secret.replace(/^whsec_/, ''), 'base64');
  const expected = createHmac('sha256', key)
    .update(`${h['webhook-id']}.${ts}.${rawBody}`)
    .digest();

  return h['webhook-signature'].split(' ').some((sig) => {
    const [version, value] = sig.split(',');
    const given = Buffer.from(value ?? '', 'base64');
    return version === 'v1' && given.length === expected.length
      && timingSafeEqual(given, expected);
  });
}
```

Three details matter. Sign and verify the **raw body** bytes, not a re-serialized JSON object, or the signatures won't match. Compare with a **constant-time** function, as the spec requires, so an attacker can't learn the signature byte by byte from response times. Accept **several signatures**, because during key rotation the sender signs with both the old and the new secret, and the spec says consumers "can try to verify each signature until one matches."

**Delivery.** For the sender side (capstone task 4), the spec recommends:

- Treat any `2xx` as success. Treat `3xx` as failure and don't follow redirects.
- On `410 Gone`, disable the endpoint. On `429`, `502` or `504`, slow down, and honor `retry-after`.
- Retry with exponential backoff and random jitter over several days. The spec's example schedule spreads attempts over roughly three days.
- Use a request timeout; the spec says "somewhere between 15 and 30s."

Your webhook sender is one more consumer of the log: read the event, send it with `webhook-id = event_id`, and on failure push it through the same retry and DLQ machinery as section 2.

## Notes to write today

1. Retries without blocking: draw the main topic, the retry topics with their delays, and the DLQ. Mark which errors skip straight to the DLQ, and how a DLQ replay works.
2. Poison message and backpressure: what each is, and what your consumer does about each.
3. The version rule: the SQL that ignores stale events, and why it suits "latest state" views but not credits.
4. Event sourcing in your own words: the three capabilities Fowler lists, snapshots, and why replays need gateways. Add one line on CQRS and where the wallet uses a read model.
5. Signed webhooks: the three headers, the signed string, and what the id, the timestamp and constant-time comparison each protect against.
6. Capstone prep from the lab: one line per chaos script (kill the consumer before the commit, publish a poison message, publish events out of order) with the expected result.

## Check yourself

These make good flashcards (see the [flashcards guide](../../FLASHCARDS.md)).

- Why does retrying a failing record inside the consumer block other accounts?
- What happens to a record after the last retry topic, and how do you replay it?
- Which kinds of errors should skip the retry ladder?
- Why does a retry topic break per-key ordering, and how do versions make that harmless?
- Fowler lists three things the event log makes possible. Name them.
- What does a webhook receiver do with `webhook-id`, and why does the timestamp limit replay attacks?
- Why must the HMAC be computed over the raw body?

## References

- **Main source:** Uber Engineering, ["Building Reliable Reprocessing and Dead Letter Queues with Apache Kafka"](https://www.uber.com/us/en/blog/reliable-reprocessing/), 2018. Read it all. Free.
- **Main source:** Martin Fowler, ["Event Sourcing"](https://martinfowler.com/eaaDev/EventSourcing.html), 2005. Read up to "External Interaction" and skim "Code Changes". Free.
- Martin Fowler, ["CQRS"](https://martinfowler.com/bliki/CQRS.html), bliki, 2011. A short note. Free.
- **Main source:** Standard Webhooks, [specification repository](https://github.com/standard-webhooks/standard-webhooks); read the [specification document](https://github.com/standard-webhooks/standard-webhooks/blob/main/spec/standard-webhooks.md), especially "Verifying webhook authenticity" and "Operational considerations". Free.
- Apache Kafka, [`KafkaConsumer` Javadoc](https://kafka.apache.org/39/javadoc/org/apache/kafka/clients/consumer/KafkaConsumer.html), the "Consumption Flow Control" section on `pause()` and `resume()`. Free.
