# Module 5: Messaging and events

**Week 6** · [Back to the syllabus](../README.md) · [Leia em português](05-messaging-and-events.pt-BR.md)

## Goal

Run events through a log safely: partition keys, offsets, retries, DLQ, ordering and signed webhooks.

## Monday to Wednesday: DSA + reading + lab (3 h 30 a day)

| Day | DSA (30 min) | Reading (2 h) | Lab (1 h) |
| --- | --- | --- | --- |
| Mon | [Course Schedule](https://leetcode.com/problems/course-schedule/) (cycle detection in a directed graph (3-color DFS))<br>Same idea as deadlock detection in a wait-for graph. | [Course text: The log, partitions and producers](../lessons/05-messaging-and-events/day-1.md) (written for this course): read this first. It explains the day's concepts and says which sections of the references below to read next.<br>[Jay Kreps, "The Log: What every software engineer should know about real-time data's unifying abstraction"](https://engineering.linkedin.com/distributed-systems/log-what-every-software-engineer-should-know-about-real-time-datas-unifying) (free): queues vs. logs, offsets and consumers.<br>[Gwen Shapira et al., "Kafka: The Definitive Guide", 2nd edition, chapter 3 (Producers)](https://www.confluent.io/resources/kafka-the-definitive-guide-v2/) (free, sign-up required): acks, idempotent producer, partition key and per-key ordering. | Redpanda in Compose; create partitioned topics; produce and consume with kcat. |
| Tue | [Course Schedule II](https://leetcode.com/problems/course-schedule-ii/) (topological sort (Kahn)) | [Course text: Consumers, offsets and exactly-once](../lessons/05-messaging-and-events/day-2.md) (written for this course): read this first. It explains the day's concepts and says which sections of the references below to read next.<br>[Gwen Shapira et al., "Kafka: The Definitive Guide", 2nd edition, chapters 4 (Consumers) and 7 (Reliable Data Delivery)](https://www.confluent.io/resources/kafka-the-definitive-guide-v2/) (free, sign-up required): consumer groups, rebalancing, committing offsets before or after processing.<br>[Confluent blog, "Exactly-Once Semantics Are Possible: Here's How Kafka Does It"](https://www.confluent.io/blog/exactly-once-semantics-are-possible-heres-how-apache-kafka-does-it/) (free): transactions and exactly-once, and where they stop (side effects outside Kafka). | Switch the outbox publisher to Redpanda with account_id as key; simple consumer. |
| Wed | [Accounts Merge](https://leetcode.com/problems/accounts-merge/) (union-find) | [Course text: Retries, DLQ, event sourcing and signed webhooks](../lessons/05-messaging-and-events/day-3.md) (written for this course): read this first. It explains the day's concepts and says which sections of the references below to read next.<br>[Uber Engineering, "Building Reliable Reprocessing and Dead Letter Queues with Apache Kafka"](https://www.uber.com/us/en/blog/reliable-reprocessing/) (free): retries, DLQ, poison messages and backpressure.<br>[Martin Fowler, "Event Sourcing"](https://martinfowler.com/eaaDev/EventSourcing.html) (free): state as a sequence of events; then read his short CQRS note linked from it.<br>[Standard Webhooks specification](https://github.com/standard-webhooks/standard-webhooks) (free): signed webhooks: HMAC, id and timestamp. | Capstone prep: sketch chaos scripts (kill consumer, poison message, out-of-order) and the task list. No TCM code. |

Solve without AI, 30-minute timebox. Method and full list: [DSA track](../DSA.md).

In labs, AI is allowed only to clarify concepts, never to write capstone code.

## Thursday and Friday: capstone (TCM), no AI

Everything is done WITHOUT AI. No ChatGPT, Claude, Copilot or AI autocomplete in the editor. Allowed: official docs, books, your own notes and previous labs. Whatever doesn't fit today becomes cut scope for the next checkpoint; the deadline does not move.

1. (1 h) Consumer with inbox (processed_messages), committing the offset only after writing.
2. (1 h) Retry topic with backoff, DLQ after N attempts and a command to replay the DLQ.
3. (30 min) Version in the event; consumer ignores versions lower than or equal to the current one.
4. (1 h) Webhook sender: HMAC-SHA256, event_id, timestamp and redelivery with backoff.
5. (1 h) Run the 3 chaos scenarios and record results.
6. (30 min) docs/m05.md.

Thursday covers items 1 to 3; Friday covers the rest and ends with 30 minutes of delivery.

## Pass criteria

A consumer killed before committing its offset causes no duplicate effect, a poison message goes to the DLQ without blocking the partition, and out-of-order events never move state backwards.

## Mastery test

Answer out loud, in under 2 minutes, without notes, and record it:

> Your Kafka consumer processed the event, wrote to the database and died before committing the offset. What happens, and why is it not a problem in your design?
