# Module 3: Transactions, concurrency and Postgres

**Week 3** · [Back to the syllabus](../README.md) · [Leia em português](03-transactions-concurrency-postgres.pt-BR.md)

## Goal

Know which anomaly each isolation level allows, and prevent negative balances under concurrency in more than one way.

## Monday to Wednesday: DSA + reading + lab (3 h 30 a day)

| Day | DSA (30 min) | Reading (2 h) | Lab (1 h) |
| --- | --- | --- | --- |
| Mon | [Subarray Sum Equals K](https://leetcode.com/problems/subarray-sum-equals-k/) (prefix sum + hash map) | DDIA ch. 7 up to "Weak Isolation Levels": ACID and what each letter protects for money; read committed; snapshot isolation.<br>DDIA ch. 7: lost update, write skew, phantoms. Build a write-skew example with balances. | Two psql sessions: reproduce a lost update under READ COMMITTED. Write down the exact command sequence. |
| Tue | [Merge Intervals](https://leetcode.com/problems/merge-intervals/) (intervals: sort by start) | Postgres docs, "Concurrency Control" 13.1 and 13.2: isolation levels in Postgres, serialization failure (40001) and retries.<br>Postgres 13.3, "Explicit Locking": SELECT ... FOR UPDATE, SKIP LOCKED, advisory locks, deadlocks and lock ordering. | Write skew under REPEATABLE READ with a couple's two accounts (rule: sum of balances >= 0). Repeat under SERIALIZABLE and see error 40001. |
| Wed | [Koko Eating Bananas](https://leetcode.com/problems/koko-eating-bananas/) (binary search on the answer) | Kleppmann, "How to do distributed locking": Redis SET NX PX, fencing tokens, why the final guarantee lives in the database.<br>Postgres: "Indexes" (multicolumn and partial), "Using EXPLAIN", and the intro of "Routine Vacuuming" (MVCC and vacuum). | Capstone prep: seed 1,000 accounts, skeleton of the parallel load script, test list. No TCM code. |

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
