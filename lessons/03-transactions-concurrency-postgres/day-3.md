# Module 3, Wednesday: distributed locks, indexes and vacuum

[Module 3](../../modules/03-transactions-concurrency-postgres.md) · [Leia em português](day-3.pt-BR.md)

**Reading time:** about 45 minutes. Use the rest of the 2-hour block on the references at the end, starting with Kleppmann's article.

This is an original text written for this course. It is based on the references listed at the end, and each section names the source it follows. Where an idea comes from a specific author, the text says so.

## Why this matters for a fintech

Sooner or later someone on the team proposes a Redis lock: "lock the wallet in Redis, then do the transfer". It sounds simpler than isolation levels. Today's first reading explains why a lock outside the database can never be the final guarantee for money, and what that guarantee looks like instead.

The rest of the day is about the same Postgres tables under real load. A statement query that reads millions of ledger rows is slow without the right index. A balance row updated thousands of times a day leaves thousands of dead versions behind. Thursday's capstone measures both, so today you learn to read a query plan and to explain why vacuum exists.

## 1. Two reasons to want a lock

*Main source: Martin Kleppmann, "How to do distributed locking", section "What are you using that lock for?".*

Kleppmann starts by asking what the lock is for. He separates two cases:

- **Efficiency.** The lock stops two workers from doing the same work twice. If it fails, you pay a small cost: a report generated twice, a duplicate email. Example: only one instance of the nightly reconciliation job should run.
- **Correctness.** The lock stops two processes from writing at the same time and corrupting data. If it fails, the data is wrong. Example: two transfers debiting the same wallet.

The distinction drives everything else. Kleppmann's advice for the first case: "if you are using locks merely for efficiency purposes, it is unnecessary to incur the cost and complexity of Redlock". A single Redis node is enough. For the second case, his answer is that the lock alone is never enough, whatever service provides it.

## 2. A Redis lock and its timing assumptions

*Main source: Martin Kleppmann, "How to do distributed locking", sections "What are you using that lock for?" and "The synchrony assumptions of Redlock".*

The usual single-node Redis lock uses the `SET` command with two options: `NX` (set only if the key does not exist) and `PX` (expire after a number of milliseconds). Kleppmann describes the pattern as "conditional set-if-not-exists to obtain a lock, atomic delete-if-value-matches to release a lock":

```
SET lock:wallet:42 <random-owner-id> NX PX 10000
```

The expiry exists because a client can crash while holding the lock, and nobody would ever release it. The random value lets the owner release only its own lock, usually with a small Lua script that deletes the key only if the value still matches.

Redlock is the multi-node variant that acquires the same lock on a majority of independent Redis nodes. Kleppmann's main criticism is about time. Its safety depends on bounded network delay, bounded process pauses and bounded clock error, and he argues that "Redlock works correctly only if you assume a synchronous system model". Module 1 showed that real systems are at best partially synchronous: clocks jump when NTP steps them, and processes pause. When those assumptions break, two clients can believe they hold the same lock.

## 3. The paused client and fencing tokens

*Main source: Martin Kleppmann, "How to do distributed locking", sections "Protecting a resource with a lock" and "Making the lock safe with fencing".*

Kleppmann's central example works with any lock service, not just Redis. Translate it to a wallet:

1. Worker 1 acquires the lock on wallet 42, with a 10-second lease.
2. Worker 1 hits a long garbage collection pause (or its container is throttled).
3. The lease expires. Worker 2 acquires the lock, debits the wallet and finishes.
4. Worker 1 wakes up. From its point of view, it still holds the lock. It writes the balance it computed before the pause.

Worker 2's debit is lost, and nothing in the lock service could stop it. Kleppmann is explicit that "You cannot fix this problem by inserting a check on the lock expiry just before writing back to storage." The pause can happen between the check and the write, and network packets can be delayed too. Kleppmann's verdict on the naive pattern: it is "fundamentally unsafe, no matter what lock service you use."

His fix is the **fencing token**: "a number that increases (e.g. incremented by the lock service) every time a client acquires the lock." In his example, client 1 gets token 33 and pauses, client 2 gets token 34 and writes. When client 1 finally writes with token 33, the storage rejects it, because it has already seen 34. The crucial point is who does the check: "this requires the storage server to take an active role in checking tokens".

For a wallet, the "storage server" is Postgres, and it can check much more than a token. Here is one way to apply Kleppmann's idea, with the token stored on the row:

```sql
UPDATE wallets
   SET balance = balance - $2, fence = $3
 WHERE id = $1 AND fence < $3 AND balance >= $2;
-- 0 rows: either a newer lock holder already wrote, or funds are insufficient
```

At that point, notice that the `WHERE` clause alone already prevents the overdraft. That is the lesson to take into interviews: **the final guarantee for money lives in the database**, in a conditional update, a row lock, a serializable transaction or a constraint such as `CHECK (balance >= 0)`. A Redis lock in front can reduce contention or duplicate work, which is an efficiency goal. It cannot be the thing that keeps a balance correct. For locks that protect correctness, Kleppmann recommends a consensus system such as ZooKeeper, with fencing on every access. He also writes: "At the very least, use a database with reasonable transactional guarantees."

## 4. The index that serves the statement query

*Main source: PostgreSQL documentation, chapter 11 "Indexes", sections 11.3 "Multicolumn Indexes", 11.4 "Indexes and ORDER BY" and 11.8 "Partial Indexes".*

The account statement (extrato) is the most frequent read in a wallet:

```sql
SELECT id, amount, direction, created_at
  FROM ledger_entries
 WHERE account_id = $1
 ORDER BY created_at DESC
 LIMIT 50;
```

Without an index, Postgres reads every ledger row, keeps the ones for this account, sorts them and returns 50. The table grows forever, so the query gets slower every day.

The docs give the rule for multicolumn B-tree indexes: "equality constraints on leading columns, plus any inequality constraints on the first column that does not have an equality constraint, will always be used to limit the portion of the index that is scanned." So the column you filter by equality goes first, and the column you sort or range on goes second:

```sql
CREATE INDEX ledger_entries_account_created_idx
    ON ledger_entries (account_id, created_at);
```

Section 11.4 explains why this also removes the sort. Only B-tree indexes produce sorted output, and "if there is an index matching the `ORDER BY`, the first *n* rows can be retrieved directly, without scanning the remainder at all." An index can be scanned backward, so `(account_id, created_at)` serves `ORDER BY created_at DESC` once `account_id` is fixed. The next page of the statement uses the same index, because `created_at < $cursor` is an inequality on the first column without an equality:

```sql
... WHERE account_id = $1 AND created_at < $2 ORDER BY created_at DESC LIMIT 50;
```

Two entries can share a timestamp, so production code often adds `id` as a third column and as a tie-breaker in the cursor. The docs also say "Multicolumn indexes should be used sparingly", and that more than three columns rarely helps. Every index slows down every insert into the ledger, so add the ones your queries need, not every combination.

**Partial indexes** index only the rows that match a predicate. The docs' example is an index over only the unbilled orders, the small fraction of rows that is read the most. The wallet equivalent is the set of transfers a worker polls:

```sql
CREATE INDEX transfers_pending_idx ON transfers (created_at)
    WHERE status IN ('PENDING', 'UNKNOWN');
```

Completed transfers pile up forever, but this index stays small. A **partial unique index** enforces uniqueness only among matching rows. The docs' example allows one "successful" test per subject and target; in a wallet, the same tool can allow at most one active hold per card authorization. The docs also warn against creating many partial indexes, one per category, as a substitute for partitioning: "This is a bad idea!"

## 5. Reading a query plan

*Main source: PostgreSQL documentation, section 14.1 "Using EXPLAIN".*

`EXPLAIN` shows the plan Postgres chose: a tree of nodes, with scan nodes at the bottom reading tables and nodes above them sorting, joining or limiting. Each node shows four estimates in parentheses: start-up cost, total cost, estimated rows and average row width in bytes. Costs are "arbitrary units determined by the planner's cost parameters", traditionally anchored at 1.0 for one sequential page read. They are useful for comparing plans, not as milliseconds. A parent node's cost includes its children.

`EXPLAIN ANALYZE` runs the query and adds the real numbers: actual time in milliseconds, actual rows and `loops`. When a node runs several times, its time and rows are per loop, so multiply by `loops`. `ANALYZE` also turns on `BUFFERS`, which shows how many pages came from cache (`shared hit`) and how many were read. Because it really executes, the docs warn that side effects happen. Wrap data-changing statements:

```sql
BEGIN;
EXPLAIN ANALYZE UPDATE wallets SET balance = balance - 10 WHERE id = 42;
ROLLBACK;
```

For Friday's before-and-after comparison, these are the shapes to look for. Costs and timings are left out on purpose, since yours will differ. When Postgres walks an index in reverse, the node is labeled `Index Scan Backward`.

```
-- before the index
Limit
  -> Sort  (Sort Key: created_at DESC)
       -> Seq Scan on ledger_entries
            Filter: (account_id = 42)
            Rows Removed by Filter: ...

-- after the index
Limit
  -> Index Scan Backward using ledger_entries_account_created_idx on ledger_entries
       Index Cond: (account_id = 42)
```

What to read, in order:

- **The scan node.** `Seq Scan` with a large "Rows Removed by Filter" means Postgres read many rows to keep few. The docs note this line appears only when the filter rejected at least one row.
- **The Sort node.** If it is gone after the index, the index is delivering rows already in order, and `Limit` can stop after 50.
- **Estimated vs. actual rows.** A big gap means the planner's statistics are off. Keeping statistics fresh is one of vacuum's jobs (section 6).
- **Buffers.** Fewer pages touched is the most honest measure of the improvement.

One trap from the docs: under a `Limit`, the child's estimated cost is shown as if it ran to completion, while the actual rows stop early. That is a display convention, not an estimation error.

## 6. MVCC leaves dead rows: why vacuum exists

*Main source: PostgreSQL documentation, section 24.1 "Routine Vacuuming", introduction and subsections 24.1.1 and 24.1.2.*

Tuesday's reading said every statement sees a snapshot. The cost of snapshots is storage. The docs put it plainly: "In PostgreSQL, an `UPDATE` or `DELETE` of a row does not immediately remove the old version of the row." The old version must stay as long as some transaction might still see it. Once no transaction can, it becomes a dead row version, and its space has to be reclaimed. That is `VACUUM`.

A wallet is close to the worst case for this. A popular merchant's balance row may be updated thousands of times a day, and each update leaves one more dead version behind. The docs list four reasons every table needs vacuuming:

1. To recover or reuse the space of updated or deleted rows.
2. To update the statistics the query planner uses.
3. To update the visibility map, which speeds up index-only scans.
4. To protect against transaction ID wraparound.

The fourth is the dangerous one. Transaction IDs are a 32-bit counter. If a table goes too long without vacuum, the counter wraps and old transactions suddenly look like they are in the future. The docs summarize the result as "catastrophic data loss", and they require every table to be vacuumed at least once every two billion transactions.

In practice, the **autovacuum** daemon runs vacuum for you, scheduled by update activity. Standard `VACUUM` runs alongside normal traffic and makes space reusable inside the table; `VACUUM FULL` returns space to the operating system but is much slower, and the docs advise avoiding it. Your job as an application engineer is mostly not to get in the way. Since a dead version cannot be removed while a transaction might still see it, a session left "idle in transaction" for hours holds cleanup back for the whole database. This is the same advice as Tuesday's, now with a second reason: short transactions reduce lock waits and let vacuum do its job.

## 7. Preparing the capstone

Today's lab is preparation only: no TCM code. Three things to have ready for Thursday morning:

**Seed data.** A thousand wallets with known balances, created by a script you can re-run. `generate_series` is the usual tool. A generic example on a throwaway table:

```sql
INSERT INTO demo_accounts (id, balance)
SELECT g, 1000 FROM generate_series(1, 1000) AS g;
```

Write down the expected total before any test runs. "The total never changes" is one of your assertions.

**Load script skeleton.** A script that fires N transfers in parallel (Thursday: 100), each with random source and destination, over a pool of several connections. Plan what it records per run: successes, business rejections (insufficient funds), conflicts, retries and total time. A single connection serializes everything and hides every bug, so the pool size matters.

**Test list.** Write the tests as sentences before you write any code. A starting list:

- After 100 parallel transfers, no wallet has a negative balance.
- After 100 parallel transfers, the sum of all balances equals the seeded total.
- Two opposite transfers between the same wallets, run together many times, never deadlock in v1.
- A wallet with balance for only one of two concurrent debits ends with exactly one debit applied.
- v2 gives up after its retry limit and reports a conflict, never a silent success.
- The statement query uses the index (check with `EXPLAIN`).

## Notes to write today

1. Kleppmann's two reasons for a lock (efficiency and correctness), the paused-client scenario in four steps, and how a fencing token stops it. End with one sentence: why the final guarantee for a balance lives in the database.
2. The index that serves the statement query, the docs' rule that justifies the column order, and how the same index serves the next page. Add one partial index your wallet could use.
3. How to read a plan: the four estimate fields, what `ANALYZE` and `BUFFERS` add, and what you expect to change in the statement plan after the index.
4. MVCC and vacuum: why updates leave dead versions, the four reasons vacuum runs, and what long transactions do to it.
5. Your capstone prep: seed command, load script outline and test list.

## Check yourself

These make good flashcards (see the [flashcards guide](../../FLASHCARDS.md)).

- What is the difference between a lock for efficiency and a lock for correctness?
- Why can't checking the lease just before writing make a lease-based lock safe?
- What is a fencing token, and who must check it?
- Which index serves `WHERE account_id = $1 ORDER BY created_at DESC LIMIT 50`, and why that column order?
- What does `EXPLAIN ANALYZE` do that `EXPLAIN` does not, and what is the risk?
- Why does an `UPDATE` in Postgres leave a dead row behind?
- What is transaction ID wraparound, and what prevents it?

## References

- **Main source:** Martin Kleppmann, ["How to do distributed locking"](https://martin.kleppmann.com/2016/02/08/how-to-do-distributed-locking.html), 2016. Read it all. Free.
- PostgreSQL documentation, ["Indexes"](https://www.postgresql.org/docs/current/indexes.html) (chapter 11). Read [11.3 "Multicolumn Indexes"](https://www.postgresql.org/docs/current/indexes-multicolumn.html), [11.4 "Indexes and ORDER BY"](https://www.postgresql.org/docs/current/indexes-ordering.html) and [11.8 "Partial Indexes"](https://www.postgresql.org/docs/current/indexes-partial.html). Free.
- PostgreSQL documentation, ["Using EXPLAIN"](https://www.postgresql.org/docs/current/using-explain.html) (section 14.1). Read 14.1.1 and 14.1.2 (EXPLAIN basics and EXPLAIN ANALYZE). Free.
- PostgreSQL documentation, ["Routine Vacuuming"](https://www.postgresql.org/docs/current/routine-vacuuming.html) (section 24.1). Read the introduction, 24.1.1 and 24.1.2; skim 24.1.5 on wraparound. Free.
