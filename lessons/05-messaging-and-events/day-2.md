# Module 5, Tuesday: consumers, offsets and exactly-once

[Module 5](../../modules/05-messaging-and-events.md) · [Leia em português](day-2.pt-BR.md)

**Reading time:** about 45 minutes. Use the rest of the 2-hour block on the references at the end, starting with the sections marked as the main source.

This is an original text written for this course. It is based on the references listed at the end, and each section names the source it follows. Where an idea comes from a specific author, the text says so.

## Why this matters for a fintech

Monday ended with a conclusion: events can arrive twice. Today you see the other half. Consumers crash, restart and get their partitions moved to another instance, and each of those moments can make an event be processed again or, with the wrong commit strategy, never processed at all.

In a wallet, "processed twice" can mean a customer gets two credit notifications, or worse, a cashback is paid twice. "Never processed" can mean a statement that is missing a transfer. This module's mastery test is exactly this situation: the consumer wrote to the database and died before committing its offset. By the end of today you should be able to answer it.

## 1. Consumer groups and offsets

*Main source: Apache Kafka, `KafkaConsumer` Javadoc, and the Kafka documentation, "Design".*

Consumers that share a `group.id` form a **consumer group**. Kafka splits the topic's partitions among the members, and at any moment each partition belongs to exactly one consumer of the group. Different groups are independent: the notification service and the statement builder each have their own group and their own offsets on the same topic.

A consumer has two numbers per partition, and the Javadoc keeps them apart:

- The **position** is the offset of the next record `poll()` will return. It moves forward as you read.
- The **committed offset** is the position stored durably for the group. After a crash or a rebalance, the new owner of the partition starts from here.

The Javadoc is precise about the value: "The committed offset should always be the offset of the next message that your application will read." If you processed offset 41, you commit 42. Committing 41 means record 41 is read again after a restart. That off-by-one mistake is common in interviews and in code.

Partitions cap parallelism. With 6 partitions and 8 consumers in one group, 2 consumers sit idle. With 6 partitions and 2 consumers, each consumer owns 3 partitions. If you need more throughput later, you need more partitions, and Monday showed that adding partitions moves keys.

## 2. Rebalancing: when partitions change owner

*Main source: Apache Kafka, `KafkaConsumer` Javadoc. Chapter 4 of "Kafka: The Definitive Guide" covers rebalancing and its strategies in depth.*

A **rebalance** reassigns partitions among the members of a group. According to the Javadoc, it happens when a member joins, leaves or fails, when partitions are added to a subscribed topic, or when a subscription by pattern matches a new topic.

Kafka has two ways to decide that a consumer failed:

- **Heartbeats.** The client sends heartbeats in the background. If none arrive within `session.timeout.ms`, the member is considered dead.
- **Poll interval.** If your code doesn't call `poll()` again within `max.poll.interval.ms`, the consumer leaves the group. The Javadoc says it directly: "So to stay in the group, you must continue to call poll."

The second one bites payment code. Suppose each record calls a partner bank that sometimes takes 30 seconds, and you fetch 500 records per poll. You exceed the poll interval, the group rebalances, your partitions go to another instance, and that instance starts from the last committed offset. Records you already processed are processed again. When you finally try to commit, the commit fails because you no longer own the partition. Two fixes: reduce `max.poll.records` so a batch finishes in time, and never put slow external calls in the consumer loop without a timeout.

The Javadoc also describes a `ConsumerRebalanceListener`. It lets you commit progress when partitions are revoked and restore positions when partitions are assigned. Rebalances are normal events in a healthy system (every deploy causes them), so design as if partitions move often.

## 3. Commit before or after processing

*Main source: Apache Kafka documentation, "Design", section on message delivery semantics. Chapters 4 and 7 of "Kafka: The Definitive Guide" discuss the same choice.*

The Kafka design documentation describes the core decision in a few lines. A consumer can save its position before or after processing a record, and a crash in between gives two different results:

| Order of steps | Crash between the steps | Delivery semantics |
| --- | --- | --- |
| Commit offset, then process | The record is skipped; the new owner starts after it | At most once |
| Process, then commit offset | The record is processed again by the new owner | At least once |

The documentation says Kafka guarantees at-least-once delivery by default, and it notes that idempotent processing makes the second option safe. For money, losing an event is never acceptable, so you always pick **process, then commit**, and you make processing idempotent.

**Auto-commit is the hidden version of the first row.** With `enable.auto.commit=true`, the client commits offsets periodically in the background. The Javadoc warns that if you don't finish processing everything a poll returned before the next poll or close, the committed offset can pass what you actually processed, and those records are lost. In NestJS microservices or KafkaJS, auto-commit is often on by default. Turn it off for anything that moves money, and commit explicitly after your database transaction commits.

## 4. Making at-least-once safe: the inbox

*Main source: Apache Kafka, `KafkaConsumer` Javadoc ("Storing Offsets Outside Kafka"), applied to this course's capstone.*

At-least-once means duplicates. You handle them at the consumer with an **inbox** (also called a processed-messages table). The event's effect and the record that it was processed are written in the **same database transaction**:

```sql
CREATE TABLE processed_messages (
  consumer_name text        NOT NULL,
  event_id      uuid        NOT NULL,
  processed_at  timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (consumer_name, event_id)
);

BEGIN;
INSERT INTO processed_messages (consumer_name, event_id)
VALUES ('cashback', $1)
ON CONFLICT DO NOTHING;
-- if 0 rows were inserted: duplicate, COMMIT and skip the effect
INSERT INTO cashback_credits (account_id, transfer_id, amount_cents)
VALUES ($2, $3, $4);
COMMIT;
-- only now: commit the Kafka offset (processed offset + 1)
```

Walk through the mastery test with this design. The consumer reads the event, the transaction commits, and the process dies before committing the offset. A rebalance gives the partition to another instance, which starts from the old committed offset and reads the same event. Its `INSERT INTO processed_messages` hits the primary key and inserts zero rows, so it skips the effect, commits the transaction, and commits the offset. The event was delivered twice and applied once. That is what "effectively once" means in practice.

The Javadoc describes a stronger variant: store the offsets themselves in your database, in the same transaction as the results. On startup, or when partitions are assigned, you `seek()` to the stored offset instead of using Kafka's committed offset. It removes the duplicate read entirely, at the cost of more code (rebalance listener, seeking). The inbox is simpler and also protects against duplicates that come from the producer side, like Monday's outbox re-send, which offset tricks can't catch. For the capstone, use the inbox.

A KafkaJS consumer loop with manual commits looks like this:

```ts
await consumer.run({
  autoCommit: false,
  eachMessage: async ({ topic, partition, message }) => {
    const eventId = message.headers?.event_id?.toString();
    await this.cashback.applyOnce(eventId, JSON.parse(message.value!.toString()));
    await consumer.commitOffsets([
      { topic, partition, offset: (BigInt(message.offset) + 1n).toString() },
    ]);
  },
});
```

## 5. Reliable delivery end to end

*Main source: Apache Kafka documentation, "Design" (replication). Chapter 7 of "Kafka: The Definitive Guide", "Reliable Data Delivery", is the full treatment; read it today.*

Chapter 7 of the book looks at reliability as a property of the whole chain, not of the broker alone. Its central idea is that the broker, the producer and the consumer must each be configured correctly, and one weak link breaks the guarantee. The details and the reasoning behind each setting are in the book. As a checklist for the wallet:

| Link | Setting or practice | Why |
| --- | --- | --- |
| Topic | Replication factor 3, `min.insync.replicas=2` | Survive one broker failure without losing committed records |
| Broker | Unclean leader election disabled (`unclean.leader.election.enable=false`) | Never promote a replica that is missing committed records |
| Producer | `acks=all`, idempotence on, handle send errors | A send is only "done" when it is committed |
| Outbox | Mark published only after the ack | Crash means re-send, never loss |
| Consumer | Auto-commit off, commit after the DB transaction | Crash means re-process, never skip |
| Consumer | Inbox with `event_id` | Re-process has no second effect |

Notice the pattern: every link is allowed to duplicate, and no link is allowed to lose. Deduplication happens once, at the place where the effect happens.

## 6. Kafka's exactly-once and where it stops

*Main source: Confluent blog, "Exactly-Once Semantics Are Possible: Here's How Kafka Does It".*

The Confluent article, written when Kafka 0.11 added exactly-once semantics, opens with this line: "Exactly-once semantics is the most desirable guarantee, but also a poorly understood one." It defines the three guarantees from the producer's side. At-least-once retries and can duplicate. At-most-once doesn't retry and can lose. Exactly-once delivers each message once to the end consumer even when the producer retries.

Kafka builds it from three pieces:

1. **Idempotent producer** (`enable.idempotence=true`): sequence numbers let the broker drop duplicates from retries, as you saw on Monday.
2. **Transactions** (`transactional.id`): a producer can write to several partitions atomically, and it can commit the consumer's offsets in the same transaction. Consumers set `isolation.level=read_committed` to see only records from committed transactions. The Javadoc lists the calls: `initTransactions()`, `beginTransaction()`, the sends, `sendOffsetsToTransaction()`, then `commitTransaction()`. A stable `transactional.id` also lets the broker fence a "zombie" instance that still thinks it owns the work.
3. **Kafka Streams** with `processing.guarantee=exactly_once`, which wraps state, output and offsets in those transactions.

The article reports the cost as small: with 1 KB messages and transactions of 100 ms, producer throughput dropped about 3% compared with `acks=all` and one in-flight request.

Now the limit, which is the part interviewers care about. The article states: "Exactly-once processing is an end-to-end guarantee". It also says the Streams guarantee covers only Kafka Streams' internal processing, not side effects such as calls to remote services or stores. In other words, Kafka transactions make **read from Kafka, write to Kafka** atomic. They do nothing for:

- An `INSERT` into your Postgres ledger.
- A call to the partner bank or to Pix.
- A webhook to a merchant.
- An email or push notification.

If your consumer writes to Postgres and then the Kafka transaction aborts, the Postgres write stays. For any effect outside Kafka you are back to at-least-once plus idempotency: the inbox, idempotency keys on partner calls (Module 2), and `event_id` on webhooks (tomorrow). In an interview, say it this way: "Kafka gives exactly-once inside Kafka; outside it, I build effectively-once with at-least-once delivery and idempotent consumers."

## Notes to write today

1. Consumer groups: one partition per consumer per group, what triggers a rebalance, and why `max.poll.interval.ms` matters when a handler calls a slow partner.
2. Commit before versus after processing: the two-row table (crash in between, result, semantics), and why auto-commit is the dangerous version.
3. Your answer to the mastery test, using the inbox: what happens step by step when the consumer dies after writing to the database and before committing.
4. Kafka transactions and exactly-once: the three pieces, and the list of side effects in the wallet that they do not cover.

## Check yourself

These make good flashcards (see the [flashcards guide](../../FLASHCARDS.md)).

- You processed the record at offset 41. Which offset do you commit, and why?
- What is the difference between a consumer's position and its committed offset?
- Name two events that trigger a rebalance.
- Commit first, then process: which guarantee does that give, and what does a crash do?
- Why can auto-commit lose records?
- Why must the inbox insert and the business effect be in the same database transaction?
- Kafka transactions are enabled. The consumer inserts into Postgres and then the transaction aborts. What happens to the row?

## References

- **Main source:** Apache Kafka, [`KafkaConsumer` Javadoc](https://kafka.apache.org/39/javadoc/org/apache/kafka/clients/consumer/KafkaConsumer.html): the class description, especially "Offsets and Consumer Position", "Consumer Groups and Topic Subscriptions", "Detecting Consumer Failures", "Manual Offset Control" and "Storing Offsets Outside Kafka". Free.
- **Main source:** Confluent blog, ["Exactly-Once Semantics Are Possible: Here's How Kafka Does It"](https://www.confluent.io/blog/exactly-once-semantics-are-possible-heres-how-apache-kafka-does-it/), 2017. Read it all; the sections on stream processing semantics and the closing remarks show where the guarantee stops. Free.
- Gwen Shapira, Todd Palino, Rajini Sivaram and Krit Petty, ["Kafka: The Definitive Guide", 2nd edition](https://www.confluent.io/resources/kafka-the-definitive-guide-v2/), O'Reilly, chapters 4 (Consumers: groups, rebalancing, commits) and 7 (Reliable Data Delivery). Free, sign-up required. Read it for the full details behind this lesson.
- Apache Kafka documentation, ["Design"](https://kafka.apache.org/41/design/design/), the section on message delivery semantics. Free.
