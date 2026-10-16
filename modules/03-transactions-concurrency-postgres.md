# Module 3: Transactions, concurrency and Postgres

**Week 3** · [Back to the syllabus](../README.md) · [Leia em português](03-transactions-concurrency-postgres.pt-BR.md)

## Goal

Know which anomaly each isolation level allows, and prevent negative balances under concurrency in more than one way.

## Monday to Wednesday: DSA + reading + lab (3 h 30 a day)

| Day | DSA (30 min) | Reading (2 h) | Lab (1 h) |
| --- | --- | --- | --- |
| Mon | [Subarray Sum Equals K](https://leetcode.com/problems/subarray-sum-equals-k/) (prefix sum + hash map) | [Course text: Isolation levels and the anomalies they allow](../lessons/03-transactions-concurrency-postgres/day-1.md) (written for this course): read this first. It explains the day's concepts and says which sections of the references below to read next.<br>[Jepsen, "Consistency Models" map: "Read Committed" and "Snapshot Isolation"](https://jepsen.io/consistency) (free): what each isolation level allows and forbids, and what ACID really promises for money.<br>[Cockroach Labs blog, "What write skew looks like"](https://www.cockroachlabs.com/blog/what-write-skew-looks-like/) (free): lost update vs. write skew, and phantoms. Then build your own write-skew example with balances.<br>[Martin Kleppmann, "Hermitage: testing transaction isolation levels"](https://github.com/ept/hermitage) (free): the table of anomalies per database; focus on the PostgreSQL rows. | Two psql sessions: reproduce a lost update under READ COMMITTED. Write down the exact command sequence. |
| Tue | [Merge Intervals](https://leetcode.com/problems/merge-intervals/) (intervals: sort by start) | [Course text: Postgres isolation, locks and retries](../lessons/03-transactions-concurrency-postgres/day-2.md) (written for this course): read this first. It explains the day's concepts and says which sections of the references below to read next.<br>[PostgreSQL documentation, "Concurrency Control", sections 13.1 and 13.2](https://www.postgresql.org/docs/current/mvcc.html) (free): isolation levels in Postgres, serialization failure (40001) and retries.<br>[PostgreSQL documentation, "Explicit Locking" (13.3)](https://www.postgresql.org/docs/current/explicit-locking.html) (free): SELECT ... FOR UPDATE, SKIP LOCKED, advisory locks, deadlocks and lock ordering. | Write skew under REPEATABLE READ with a couple's two accounts (rule: sum of balances >= 0). Repeat under SERIALIZABLE and see error 40001. |
| Wed | [Koko Eating Bananas](https://leetcode.com/problems/koko-eating-bananas/) (binary search on the answer) | [Course text: Distributed locks, indexes and vacuum](../lessons/03-transactions-concurrency-postgres/day-3.md) (written for this course): read this first. It explains the day's concepts and says which sections of the references below to read next.<br>[Martin Kleppmann, "How to do distributed locking"](https://martin.kleppmann.com/2016/02/08/how-to-do-distributed-locking.html) (free): Redis SET NX PX, fencing tokens, why the final guarantee lives in the database.<br>[PostgreSQL documentation, "Indexes" (multicolumn and partial)](https://www.postgresql.org/docs/current/indexes.html) (free): which index serves the account statement query.<br>[PostgreSQL documentation, "Using EXPLAIN"](https://www.postgresql.org/docs/current/using-explain.html) (free): reading a query plan before and after an index.<br>[PostgreSQL documentation, "Routine Vacuuming", introduction](https://www.postgresql.org/docs/current/routine-vacuuming.html) (free): MVCC and why vacuum exists. | Capstone prep: seed 1,000 accounts, skeleton of the parallel load script, test list. No TCM code. |

Solve without AI, 30-minute timebox. Method and full list: [DSA track](../DSA.md).

In labs, AI is allowed only to clarify concepts, never to write capstone code.

## Thursday and Friday: capstone (TCM), no AI

Everything is done WITHOUT AI. No ChatGPT, Claude, Copilot or AI autocomplete in the editor. Allowed: official docs, books, your own notes and previous labs. Whatever doesn't fit today becomes cut scope for the next checkpoint; the deadline does not move.

1. (45 min) Transfer v1: SELECT ... FOR UPDATE locking both accounts in id order.
2. (45 min) v2 optimistic: version column and bounded retries.
3. (30 min) v3: conditional UPDATE ... WHERE balance >= :amount, checking affected rows.
4. (1 h) Test with 100 parallel transfers per version: no negative balance, constant total.
5. (45 min) Measure throughput, conflicts and retries; build the comparison table.
6. (30 min) EXPLAIN ANALYZE of the statement query before and after an (account_id, created_at) index.
7. (45 min) docs/m03.md stating which version you'd ship to production and why.

Thursday covers items 1 to 4; Friday covers the rest and ends with 30 minutes of delivery.

## Pass criteria

None of the three versions allows a negative balance, and docs/m03.md says which one you'd ship and why.

## Mastery test

Answer out loud, in under 2 minutes, without notes, and record it:

> Two concurrent transfers leave the same account, with balance for only one. Show three ways to prevent a negative balance and the trade-off of each.
