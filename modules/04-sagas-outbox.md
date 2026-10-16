# Module 4: Sagas, Outbox and distributed transactions

**Week 4** · [Back to the syllabus](../README.md) · [Leia em português](04-sagas-outbox.pt-BR.md)

## Goal

Move money across services without 2PC: orchestrated sagas with persisted state, compensations and the transactional outbox.

## Monday to Wednesday: DSA + reading + lab (3 h 30 a day)

| Day | DSA (30 min) | Reading (2 h) | Lab (1 h) |
| --- | --- | --- | --- |
| Mon | [Capacity To Ship Packages Within D Days](https://leetcode.com/problems/capacity-to-ship-packages-within-d-days/) (binary search on the answer (capacity, days, weights)) | [Course text: Two-phase commit and why sagas exist](../lessons/04-sagas-outbox/day-1.md) (written for this course): read this first. It explains the day's concepts and says which sections of the references below to read next.<br>[Martin Kleppmann, "Distributed Systems" lecture notes (University of Cambridge), section 7.1 (Two-phase commit)](https://www.cl.cam.ac.uk/teaching/2122/ConcDisSys/dist-sys-notes.pdf) (free): how 2PC works, why it holds locks and why external APIs don't support it.<br>[Chris Richardson, microservices.io, "Pattern: Saga"](https://microservices.io/patterns/data/saga.html) (free): orchestrated vs. choreographed sagas and compensating transactions. | Split accounts and payments, each with its own database in Compose, talking over HTTP. |
| Tue | [Clone Graph](https://leetcode.com/problems/clone-graph/) (graph DFS/BFS + hash map of copies) | [Course text: Saga isolation, balance holds and the transactional outbox](../lessons/04-sagas-outbox/day-2.md) (written for this course): read this first. It explains the day's concepts and says which sections of the references below to read next.<br>[Chris Richardson, "Microservices Patterns" (Manning), chapter 4, "Handling the lack of isolation"](https://www.manning.com/books/microservices-patterns) (paid book): countermeasures (semantic lock, commutative updates, reordering), pivot transaction, TCC and balance holds. No free source covers these as well.<br>[Chris Richardson, microservices.io, "Pattern: Transactional outbox"](https://microservices.io/patterns/data/transactional-outbox.html) (free): the outbox, plus the two publishing options linked from it: Polling publisher and Transaction log tailing.<br>[Debezium documentation, "Debezium Architecture"](https://debezium.io/documentation/reference/stable/architecture.html) (free): how change data capture reads the database log. | Experimental outbox: outbox table and a polling publisher with SKIP LOCKED writing to a log (Kafka comes in M5). |
| Wed | [Copy List with Random Pointer](https://leetcode.com/problems/copy-list-with-random-pointer/) (hash map, then O(1) space interleaving) | [Course text: Durable workflows and the transfer saga state machine](../lessons/04-sagas-outbox/day-3.md) (written for this course): read this first. It explains the day's concepts and says which sections of the references below to read next.<br>[Temporal documentation, "What is Temporal?"](https://docs.temporal.io/temporal) (free): workflows, activities, retries and timers.<br>[AWS Step Functions Developer Guide, "What is Step Functions?"](https://docs.aws.amazon.com/step-functions/latest/dg/welcome.html) (free): another take on durable workflows; when are they worth the cost?<br>On paper: the state machine of a cross-service transfer saga, with states, transitions, compensations and per-step timeouts. | Capstone prep: skeleton of chaos/kill-orchestrator.sh, task list and failure cases. No TCM code. |

Solve without AI, 30-minute timebox. Method and full list: [DSA track](../DSA.md).

In labs, AI is allowed only to clarify concepts, never to write capstone code.

## Thursday and Friday: capstone (TCM), no AI

Everything is done WITHOUT AI. No ChatGPT, Claude, Copilot or AI autocomplete in the editor. Allowed: official docs, books, your own notes and previous labs. Whatever doesn't fit today becomes cut scope for the next checkpoint; the deadline does not move.

1. (45 min) sagas table (id, state, step, attempts, deadline, payload) and the state machine in the orchestrator (payments).
2. (1 h) Steps: debit A in accounts, credit B, complete. Each step idempotent with saga_id + step as key.
3. (45 min) Compensation: a failed credit creates a reversal of the debit as a new entry, never a delete.
4. (45 min) Recovery worker: picks non-terminal sagas with SKIP LOCKED and resumes; per-step timeout.
5. (30 min) Outbox written in the same transaction as the data in each service.
6. (45 min) chaos/kill-orchestrator.sh: 20 kills at random points; check total balance and no stuck saga.
7. (30 min) docs/m04.md with the state diagram.

Thursday covers items 1 to 3; Friday covers the rest and ends with 30 minutes of delivery.

## Pass criteria

Killing the orchestrator 20 times at random points leaves the total balance unchanged and no saga stuck.

## Mastery test

Answer out loud, in under 2 minutes, without notes, and record it:

> Design a transfer between accounts in two different services using a saga. What happens if the credit to B fails after the debit from A?
