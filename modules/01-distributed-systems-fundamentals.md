# Module 1: Distributed systems fundamentals

**Week 1** · [Back to the syllabus](../README.md) · [Leia em português](01-distributed-systems-fundamentals.pt-BR.md)

## Goal

Build the vocabulary everything else depends on: partial failures, delivery semantics, replication, partitioning, consistency models and clocks. Consensus and Raft are left for Module 9.

## Monday to Wednesday: DSA + reading + lab (3 h 30 a day)

| Day | DSA (30 min) | Reading (2 h) | Lab (1 h) |
| --- | --- | --- | --- |
| Mon | [Two Sum](https://leetcode.com/problems/two-sum/) (hash map)<br>[Two Sum II](https://leetcode.com/problems/two-sum-ii-input-array-is-sorted/) (two pointers on a sorted array) | DDIA ch. 8, first half: partial failures, unreliable networks, timeouts. Write down the 3 possible outcomes of a timeout (happened, didn't happen, unknown).<br>DDIA ch. 8, second half: unreliable clocks, process pauses, truth defined by the majority. Write down why you can't order events by wall clock and what a Lamport clock is. | Create the public repo (services/, docs/, chaos/) with the NestJS skeleton and Docker Compose with a Postgres primary + async replica (streaming replication). |
| Tue | [3Sum](https://leetcode.com/problems/3sum/) (sort + two pointers, generalizes to k-sum) | DDIA ch. 5 up to "Problems with Replication Lag": leader/follower, sync vs. async replication, failover and lost writes, read-your-writes, monotonic reads.<br>DDIA ch. 5, rest: multi-leader, leaderless, quorums (R + W > N). | Stale-read experiment (short version): a script writes to the primary and reads from the replica in a loop, measuring lag; put Toxiproxy between them to make lag visible. |
| Wed | [Top K Frequent Elements](https://leetcode.com/problems/top-k-frequent-elements/) (heap, then bucket sort in O(n)) | DDIA ch. 6: partitioning by key range and by hash, hot partitions, rebalancing. Think: what is the partition key of a digital wallet?<br>DDIA ch. 9 up to "Ordering Guarantees": linearizability and CAP. Extra: PACELC (Daniel Abadi, 2012). Draft the table of 8 wallet operations vs. required consistency model. | Capstone prep (no TCM code yet): spin up the fake partner bank (endpoint with configurable delay) behind Toxiproxy and write on paper the task list and test cases for Thu/Fri. |

Solve without AI, 30-minute timebox. Method and full list: [DSA track](../DSA.md).

In labs, AI is allowed only to clarify concepts, never to write capstone code.

## Thursday and Friday: capstone (TCM), no AI

Everything is done WITHOUT AI. No ChatGPT, Claude, Copilot or AI autocomplete in the editor. Allowed: official docs, books, your own notes and previous labs. Whatever doesn't fit today becomes cut scope for the next checkpoint; the deadline does not move.

1. (1 h) payments service: POST /transfers stores the transfer as PENDING and calls the fake partner bank with a 2 s timeout.
2. (1 h) Handle the 3 outcomes: success -> COMPLETED, definitive error -> FAILED, timeout -> UNKNOWN (never FAILED). Job that queries the partner and resolves UNKNOWNs.
3. (1 h) Integration tests with Testcontainers + Toxiproxy covering the 3 outcomes.
4. (1 h) chaos/replica-lag.sh reproducing the stale read automatically.
5. (1 h) docs/m01.md: the experiment, the 3 outcomes of a timeout and the 8-operation consistency table.

Thursday covers items 1 to 3; Friday covers the rest and ends with 30 minutes of delivery.

## Pass criteria

The stale read is reproducible by script, and the consistency table justifies each choice in one line.

## Mastery test

Answer out loud, in under 2 minutes, without notes, and record it:

> Your service calls the partner bank, it times out and the client retries. What may have happened, and how does your system guarantee it didn't charge twice?
