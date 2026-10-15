# Module 5: Messaging and events

**Week 6** · [Back to the syllabus](../README.md) · [Leia em português](05-messaging-and-events.pt-BR.md)

## Goal

Run events through a log safely: partition keys, offsets, retries, DLQ, ordering and signed webhooks.

## Monday to Wednesday: reading + lab (3 h a day)

| Day | Reading (2 h) | Lab (1 h) |
| --- | --- | --- |
| Mon | DDIA ch. 11, first part: queues vs. logs, brokers, offsets, consumers.<br>Kafka: The Definitive Guide, producers chapter: acks, idempotent producer, partition key and per-key ordering. | Redpanda in Compose; create partitioned topics; produce and consume with kcat. |
| Tue | Kafka: The Definitive Guide, consumers chapter: consumer groups, rebalancing, committing offsets before or after processing.<br>Kafka: The Definitive Guide, reliable delivery chapter; Confluent docs on transactions and exactly-once. | Switch the outbox publisher to Redpanda with account_id as key; simple consumer. |
| Wed | Retries, DLQ, poison messages and backpressure. Uber Engineering, "Building Reliable Reprocessing and Dead Letter Queues with Apache Kafka".<br>Event sourcing and CQRS (DDIA ch. 11, "Event Sourcing"; microservices.io). Webhooks: the Standard Webhooks spec (HMAC, id, timestamp). | Capstone prep: sketch chaos scripts (kill consumer, poison message, out-of-order) and the task list. No TCM code. |

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
