# Module 1: Distributed systems fundamentals

**Week 1** · [Back to the syllabus](../README.md) · [Leia em português](01-distributed-systems-fundamentals.pt-BR.md)

## Goal

Build the vocabulary everything else depends on: partial failures, delivery semantics, replication, partitioning, consistency models and clocks. Consensus and Raft are left for Module 9.

## Monday to Wednesday: DSA + reading + lab (3 h 30 a day)

| Day | DSA (30 min) | Reading (2 h) | Lab (1 h) |
| --- | --- | --- | --- |
| Mon | [Two Sum](https://leetcode.com/problems/two-sum/) (hash map)<br>[Two Sum II](https://leetcode.com/problems/two-sum-ii-input-array-is-sorted/) (two pointers on a sorted array) | [Martin Kleppmann, "Distributed Systems" lecture notes (University of Cambridge), sections 1.1 and 2.1 to 2.4](https://www.cl.cam.ac.uk/teaching/2122/ConcDisSys/dist-sys-notes.pdf) (free): partial failures, unreliable networks, timeouts and failure detection. Write down the 3 possible outcomes of a timeout (happened, didn't happen, unknown).<br>[Martin Kleppmann, "Distributed Systems" lecture notes (University of Cambridge), chapter 3 and section 4.1](https://www.cl.cam.ac.uk/teaching/2122/ConcDisSys/dist-sys-notes.pdf) (free): physical clocks, clock synchronisation, happens-before and Lamport clocks. Write down why you can't order events by wall clock and what a Lamport clock is.<br>[Jeff Hodges, "Notes on Distributed Systems for Young Bloods"](https://www.somethingsimilar.com/2013/01/14/notes-on-distributed-systems-for-young-bloods/) (free): short practical essay; read it if time is left. | Create the public repo (services/, docs/, chaos/) with the NestJS skeleton and Docker Compose with a Postgres primary + async replica (streaming replication). |
| Tue | [3Sum](https://leetcode.com/problems/3sum/) (sort + two pointers, generalizes to k-sum) | [PostgreSQL documentation, "High Availability, Load Balancing, and Replication"](https://www.postgresql.org/docs/current/high-availability.html) (free): leader/follower, synchronous vs. asynchronous replication, failover and the writes you lose on failover.<br>[Jepsen, consistency models: "Read Your Writes" and "Monotonic Reads"](https://jepsen.io/consistency/models/read-your-writes) (free): what each guarantee means and how a lagging replica breaks it (Monotonic Reads is linked from the same page).<br>[Martin Kleppmann, "Distributed Systems" lecture notes (University of Cambridge), section 5.2 (Quorums)](https://www.cl.cam.ac.uk/teaching/2122/ConcDisSys/dist-sys-notes.pdf) (free): leaderless replication and quorums (R + W > N). | Stale-read experiment (short version): a script writes to the primary and reads from the replica in a loop, measuring lag; put Toxiproxy between them to make lag visible. |
| Wed | [Top K Frequent Elements](https://leetcode.com/problems/top-k-frequent-elements/) (heap, then bucket sort in O(n)) | [Amazon DynamoDB Developer Guide, "Best practices for designing and using partition keys effectively"](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/bp-partition-key-design.html) (free): partitioning by key, hot partitions and write sharding. Think: what is the partition key of a digital wallet?<br>[Martin Kleppmann, "Distributed Systems" lecture notes (University of Cambridge), sections 7.2 and 7.3](https://www.cl.cam.ac.uk/teaching/2122/ConcDisSys/dist-sys-notes.pdf) (free): linearizability, eventual consistency and the CAP trade-off.<br>[Daniel Abadi, "Consistency Tradeoffs in Modern Distributed Database System Design" (2012)](https://www.cs.umd.edu/~abadi/papers/abadi-pacelc.pdf) (free): PACELC. Then draft the table of 8 wallet operations vs. the consistency each one needs. | Capstone prep (no TCM code yet): spin up the fake partner bank (endpoint with configurable delay) behind Toxiproxy and write on paper the task list and test cases for Thu/Fri. |

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
