# Module 5, Monday: the log, partitions and producers

[Module 5](../../modules/05-messaging-and-events.md) · [Leia em português](day-1.pt-BR.md)

**Reading time:** about 45 minutes. Use the rest of the 2-hour block on the references at the end, starting with the sections marked as the main source.

This is an original text written for this course. It is based on the references listed at the end, and each section names the source it follows. Where an idea comes from a specific author, the text says so.

## Why this matters for a fintech

In Module 4 you wrote events to an outbox table in the same transaction as the money movement. Those events still have to reach other services: the notification service, the fraud checks, the statement builder, the webhook sender. This week they go through a log (Kafka, or Redpanda in the labs).

A log is not a magic pipe. It gives you ordering only inside a partition, it can deliver the same event twice, and the producer decides how durable a write really is. If you pick the wrong partition key, two events for the same account can be processed in the wrong order, and a balance can go backwards. Today is about the guarantees you get on the producing side, and the ones you don't.

## 1. What a log is

*Main source: Jay Kreps, "The Log", Part One.*

Jay Kreps, one of the creators of Kafka at LinkedIn, describes the log as the simplest possible storage abstraction. In his words, "It is an append-only, totally-ordered sequence of records ordered by time." New records go at the end. Old records are never changed in place. Each record gets a sequential number, which Kafka calls the **offset**.

Kreps makes two points that matter for a wallet:

- **The offset is a clock you can trust.** The order of records in the log defines "time" without any physical clock. Module 1 showed that wall clocks disagree across machines. A log replaces "which timestamp is earlier" with "which offset is smaller", and that question has one answer.
- **The log plus a position describes a replica.** If deterministic processes receive the same inputs in the same order, they reach the same state. Kreps calls this the state machine replication principle. A consumer can be described completely by the last offset it has processed.

He also points out that tables and events are dual. A table holds the current state. The log of changes holds how you got there. You can rebuild the table by replaying the log, and you can produce the log by recording every change to the table. Your Postgres write-ahead log (Module 1, Tuesday) is exactly this idea inside a database. Debezium (Module 4) exposes it to the outside world.

For a wallet, think of the log as the ordered history of "things that happened": `TransferCompleted`, `DepositSettled`, `HoldReleased`. The ledger in Postgres stays the source of truth for balances. The log is how the rest of the company learns about those changes, in order.

## 2. Queues versus logs

*Main source: Jay Kreps, "The Log", Part Two, and the Apache Kafka documentation, "Design".*

Kreps says he prefers the word "log" to "messaging system" because pub/sub says little about guarantees. The difference becomes clear when you compare a classic queue with a log.

| | Classic queue (for example RabbitMQ, SQS) | Log (Kafka, Redpanda) |
| --- | --- | --- |
| What happens after a read | The broker deletes the message once it is acknowledged | The record stays; only retention removes it |
| Who tracks progress | The broker, per message | Each consumer group, as one offset per partition |
| Several independent readers | Need one queue per reader (fan-out) | Each group reads the same records at its own pace |
| Replay after a bug fix | Not possible once acked | Rewind the offset and read again |
| Ordering | Usually weak once several consumers compete | Total order inside each partition |

The Kafka design documentation explains why this is cheap: for each partition, a consumer's position is a single integer, the offset of the next record to read. Tracking one number per partition is far cheaper than tracking an acknowledgment state for every message.

Kreps describes the log as a buffer: "The log acts as a very, very large buffer that allows process to be restarted or fail" without slowing down the rest of the pipeline. If your statement builder is down for an hour, the producer keeps writing. When the builder comes back, it continues from its last committed offset and catches up.

Records don't live forever. Kreps describes two policies, both available in Kafka:

- **Time or size retention.** Event data is kept for a window (Kreps mentions a window of a few days), then deleted.
- **Log compaction.** For keyed data, older records for a key are removed once a newer record for the same key exists. The log still holds the latest value of every key, but intermediate states are gone.

A compacted topic is good for "current status of each customer". It is wrong for money movements, where every event matters. Keep transfer events on a topic with time retention, and keep the permanent history in your ledger.

## 3. Topics, partitions and per-key ordering

*Main source: Jay Kreps, "The Log", "Building a Scalable Log", and the Apache Kafka documentation, "Design".*

One log on one machine doesn't scale. Kafka splits each **topic** into **partitions**, and each partition is its own log. Kreps states the trade-off plainly: "Each partition is a totally ordered log, but there is no global ordering between partitions". Records from one producer to one partition arrive in the order they were sent.

The producer chooses the partition. According to the Kafka design documentation, if a record has a **key**, the key is hashed to pick the partition, so every record with the same key lands in the same partition. That is the only ordering tool you have. Choose the key as "the thing whose events must stay in order".

| Key choice | What stays ordered | Risk |
| --- | --- | --- |
| No key (round robin or sticky) | Nothing across records | Two events for one account can be processed out of order |
| `transfer_id` | Events of one transfer | Events for the same account from different transfers can interleave |
| `account_id` | All events that touch one account | A very active account becomes a hot partition |
| `customer_id` | All events of one customer, across accounts | Coarser, more chance of hot spots |

For the wallet, `account_id` is the usual choice, and it is the one the Tuesday lab uses. A transfer touches two accounts, so you either publish one event per affected account (keyed by each account) or pick the source account as the key and accept that ordering is guaranteed only from that account's point of view. Write down which you choose.

Two warnings about keys:

- **The mapping depends on the partition count.** The hash is taken modulo the number of partitions. If you add partitions later, new records for a key can land in a different partition than old ones, and ordering breaks during the transition. Pick a generous partition count at the start.
- **Parallelism is capped by partitions.** Inside one consumer group, each partition is read by exactly one consumer at a time. Six partitions means at most six busy consumers in that group. Tuesday covers this.

## 4. Producer acknowledgments and durability

*Main source: Apache Kafka documentation, "Design" (replication), and the `KafkaProducer` Javadoc. Chapter 3 of "Kafka: The Definitive Guide" covers the same settings in more depth.*

When a producer sends a record, the partition's leader broker writes it, and follower brokers copy it. The `acks` setting decides when the producer considers the send complete. The `KafkaProducer` Javadoc puts it simply: "The `acks` config controls the criteria under which requests are considered complete."

| `acks` | The producer gets success when | What you can lose |
| --- | --- | --- |
| `0` | It has written to the socket, without waiting for the broker | Anything: the broker may never have received it |
| `1` | The leader has written it to its own log | Records the leader had not yet replicated when it crashed |
| `all` (or `-1`) | All in-sync replicas have it | Nothing, as long as one in-sync replica survives |

The design documentation defines a **committed** record as one that all replicas in the **in-sync replica set (ISR)** have applied. A follower that falls behind is dropped from the ISR. That creates a trap: with `acks=all`, if the ISR shrinks to the leader alone, "all" means one copy. The topic setting `min.insync.replicas` closes it. If the ISR is smaller than this number, the partition rejects writes from `acks=all` producers. The documentation describes this as trading availability for durability.

For payment events, the usual configuration is replication factor 3, `min.insync.replicas=2` and `acks=all`. One broker can fail and writes continue. Two fail and writes stop, which is what you want: an error you can retry beats an event that silently disappears.

According to the Javadoc, since Kafka 3.0 the Java producer defaults to `acks=all` with idempotence enabled. Other clients have their own defaults, so always check and set these explicitly.

## 5. The idempotent producer and its limits

*Main source: Apache Kafka documentation, "Design", and the `KafkaProducer` Javadoc.*

A producer with `acks=all` waits for the broker, and the broker's answer can be lost, exactly the timeout problem from Module 1. The producer retries, and without protection the record is written twice.

The **idempotent producer** fixes this specific case. The design documentation explains the mechanism: "The broker assigns each producer an ID and deduplicates messages using a sequence number." Each batch carries the producer ID and a per-partition sequence number. If the broker sees a sequence number it has already written, it acknowledges without writing again. It also keeps records from one producer in order when retries happen.

Read the limits carefully, because they decide your consumer design:

- **It only covers retries inside one producer session.** The Javadoc says it removes duplicates caused by the producer's own retries, but only within a single session. If your process restarts, the new producer has a new ID.
- **Your own re-sends are not covered.** The Javadoc warns applications to avoid re-sends of their own, because the broker cannot de-duplicate them.

Now apply that to the outbox publisher from Module 4. It reads a row, sends it, waits for the ack, then marks the row as published. If it crashes after the send and before the update, the next run sends the row again with a fresh producer. The broker sees two different records. So **the outbox gives you at-least-once publishing, and consumers must deduplicate by event ID.** That is why every event needs a stable `event_id` (the outbox row ID is a good one), and why Thursday's consumer has an inbox table.

A producer sketch in TypeScript with KafkaJS (any client has equivalent settings):

```ts
const producer = kafka.producer({ idempotent: true, maxInFlightRequests: 1 });
await producer.connect();

// One outbox row becomes one record, keyed by account_id.
await producer.send({
  topic: 'wallet.account-events',
  acks: -1, // all in-sync replicas
  messages: [{
    key: row.accountId,
    value: JSON.stringify(row.payload),
    headers: { event_id: row.id, event_type: row.type, version: String(row.version) },
  }],
});

await db.query(
  'UPDATE outbox SET published_at = now() WHERE id = $1',
  [row.id],
); // a crash before this line means the row is sent again
```

The `version` header is not a Kafka feature. It is the per-account sequence your consumer will use on Thursday to ignore stale events.

## 6. What to try in today's lab

*Main source: sections 2 to 4 of this lesson, applied to the lab.*

The lab runs Redpanda in Docker Compose. Redpanda speaks the Kafka protocol, so the same clients and the same concepts apply. Use it to see the guarantees with your own eyes:

```bash
# A topic with 6 partitions
rpk topic create wallet.account-events -p 6

# Produce keyed records: "key:value" per line
kcat -b localhost:9092 -t wallet.account-events -P -K:
acc-1:{"type":"Deposit","amount":100}
acc-2:{"type":"Deposit","amount":50}
acc-1:{"type":"Withdrawal","amount":30}

# Consume and print partition, offset and key
kcat -b localhost:9092 -t wallet.account-events -C -e \
  -f 'p=%p o=%o k=%k %s\n'
```

Check three things. Every `acc-1` record shows the same partition. Offsets grow by one inside a partition and are independent across partitions. Reading the topic a second time returns the same records again, because reading doesn't delete anything. That last point is the "log, not queue" idea in one command.

## Notes to write today

1. Queues versus logs: a table with what happens after a read, who tracks progress, replay and ordering. Add one sentence on what an offset is and why a consumer can be described by one number per partition.
2. Your partition key for wallet events, why you chose it, and what ordering you get and don't get with it (per key, never global).
3. `acks=0`, `1` and `all`, what each can lose, and the role of `min.insync.replicas`.
4. What the idempotent producer prevents and what it doesn't (restarts, your own re-sends), and the conclusion for your consumers.

## Check yourself

These make good flashcards (see the [flashcards guide](../../FLASHCARDS.md)).

- What does Kreps mean when he says the log defines time without a clock?
- After a consumer reads a record from a log, is the record deleted? What removes it?
- Which records does Kafka keep in order, and which does it not?
- Why can adding partitions to a topic break per-key ordering?
- With `acks=all`, how can a write still end up with only one copy, and which setting prevents it?
- Your outbox publisher crashed after sending and before marking the row as published. Does the idempotent producer prevent the duplicate? Why not?

## References

- **Main source:** Jay Kreps, ["The Log: What every software engineer should know about real-time data's unifying abstraction"](https://engineering.linkedin.com/distributed-systems/log-what-every-software-engineer-should-know-about-real-time-datas-unifying), LinkedIn Engineering, 2013. Read Part One fully and, in Part Two, "Log-structured data flow" and "Building a Scalable Log"; skim Part Three's "Log Compaction". Free.
- Gwen Shapira, Todd Palino, Rajini Sivaram and Krit Petty, ["Kafka: The Definitive Guide", 2nd edition](https://www.confluent.io/resources/kafka-the-definitive-guide-v2/), O'Reilly, chapter 3 (Producers): configuration of `acks`, retries and idempotence, and how keys map to partitions. Free, sign-up required. Read it for the full details behind this lesson.
- Apache Kafka documentation, ["Design"](https://kafka.apache.org/41/design/design/): read the parts on the producer, replication (ISR, `min.insync.replicas`) and message delivery semantics. Free.
- Apache Kafka, [`KafkaProducer` Javadoc](https://kafka.apache.org/39/javadoc/org/apache/kafka/clients/producer/KafkaProducer.html): the class description explains `acks`, idempotence and transactions. Free.
