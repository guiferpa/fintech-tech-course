# Module 4: Sagas, Outbox and distributed transactions

**Week 4** · [Back to the syllabus](../README.md) · [Leia em português](04-sagas-outbox.pt-BR.md)

## Goal

Move money across services without 2PC: orchestrated sagas with persisted state, compensations and the transactional outbox.

## Monday to Wednesday: DSA + reading + lab (3 h 30 a day)

| Day | DSA (30 min) | Reading (2 h) | Lab (1 h) |
| --- | --- | --- | --- |
| Mon | [Capacity To Ship Packages Within D Days](https://leetcode.com/problems/capacity-to-ship-packages-within-d-days/) (binary search on the answer (capacity, days, weights)) | DDIA ch. 9, "Atomic Commit and Two-Phase Commit": how 2PC works, why it holds locks and why external APIs don't support it.<br>Microservices Patterns (Richardson), ch. 4: orchestrated vs. choreographed sagas, compensation, pivot transaction, step ordering. | Split accounts and payments, each with its own database in Compose, talking over HTTP. |
| Tue | [Clone Graph](https://leetcode.com/problems/clone-graph/) (graph DFS/BFS + hash map of copies) | Microservices Patterns, ch. 4: lack of isolation and countermeasures (semantic lock, commutative updates, reordering). TCC (Try-Confirm-Cancel) and balance holds.<br>Microservices Patterns, ch. 3: transactional messaging, Transactional Outbox, polling vs. log tailing. microservices.io outbox page. Debezium intro. | Experimental outbox: outbox table and a polling publisher with SKIP LOCKED writing to a log (Kafka comes in M5). |
| Wed | [Copy List with Random Pointer](https://leetcode.com/problems/copy-list-with-random-pointer/) (hash map, then O(1) space interleaving) | Temporal docs (workflows, activities, retries, timers) and AWS Step Functions overview. When durable workflows are worth the cost.<br>On paper: the state machine of a cross-service transfer saga, with states, transitions, compensations and per-step timeouts. | Capstone prep: skeleton of chaos/kill-orchestrator.sh, task list and failure cases. No TCM code. |

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
