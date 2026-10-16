# Course texts

[Back to the syllabus](../README.md) · [Leia em português](README.pt-BR.md)

Each Monday-to-Wednesday reading block starts with a text written for this course. The texts explain the day's concepts with examples from a digital wallet, and end with the notes to write, questions for your flashcards and the references.

Every text is based on the references listed at its end, and each section names the source it follows. The references stay in the reading list so you can go deeper, and so the course still holds up if a link goes offline.

| Module | Monday | Tuesday | Wednesday |
| --- | --- | --- | --- |
| 1. Distributed systems fundamentals | [Failures, timeouts and time](01-distributed-systems-fundamentals/day-1.md) | [Replication and replication lag](01-distributed-systems-fundamentals/day-2.md) | [Partitioning, consistency models and trade-offs](01-distributed-systems-fundamentals/day-3.md) |
| 2. End-to-end idempotency | [Idempotency keys and atomic phases](02-end-to-end-idempotency/day-1.md) | [Recovering interrupted requests and idempotent consumers](02-end-to-end-idempotency/day-2.md) | [Idempotency at every hop](02-end-to-end-idempotency/day-3.md) |
| 3. Transactions, concurrency and Postgres | [Isolation levels and the anomalies they allow](03-transactions-concurrency-postgres/day-1.md) | [Postgres isolation, locks and retries](03-transactions-concurrency-postgres/day-2.md) | [Distributed locks, indexes and vacuum](03-transactions-concurrency-postgres/day-3.md) |
| 4. Sagas, Outbox and distributed transactions | [Two-phase commit and why sagas exist](04-sagas-outbox/day-1.md) | [Saga isolation, balance holds and the transactional outbox](04-sagas-outbox/day-2.md) | [Durable workflows and the transfer saga state machine](04-sagas-outbox/day-3.md) |
| 5. Messaging and events | [The log, partitions and producers](05-messaging-and-events/day-1.md) | [Consumers, offsets and exactly-once](05-messaging-and-events/day-2.md) | [Retries, DLQ, event sourcing and signed webhooks](05-messaging-and-events/day-3.md) |
| 6. Ledgers and accounting | [Double entry, account types and balances](06-ledgers-and-accounting/day-1.md) | [Holds, account invariants and missing money](06-ledgers-and-accounting/day-2.md) | [Concurrency, immutability and entries on paper](06-ledgers-and-accounting/day-3.md) |
| 7. Payments, Pix and reconciliation | [The card payment lifecycle and double payments](07-payments-pix-reconciliation/day-1.md) | [Pix, returns and the MED](07-payments-pix-reconciliation/day-2.md) | [Reconciliation and safe provider fallback](07-payments-pix-reconciliation/day-3.md) |
| 8. Security, compliance and risk | [Hashing, encryption, keys and mTLS](08-security-compliance-risk/day-1.md) | [API risks, threat modeling, PCI scope and LGPD](08-security-compliance-risk/day-2.md) | [Tokens, authorization, fraud limits and KYC](08-security-compliance-risk/day-3.md) |
| 9. Resilience, high availability and consensus | [Timeouts, retries, circuit breakers and bulkheads](09-resilience-and-consensus/day-1.md) | [Overload, backlogs and consensus](09-resilience-and-consensus/day-2.md) | [Disaster recovery, safe migrations and feature flags](09-resilience-and-consensus/day-3.md) |
| 10. Observability and operations | [Symptoms, golden signals, SLOs and burn-rate alerts](10-observability-and-operations/day-1.md) | [Traces, context propagation and business metrics](10-observability-and-operations/day-2.md) | [Incidents, runbooks, postmortems and the double-charge detector](10-observability-and-operations/day-3.md) |
