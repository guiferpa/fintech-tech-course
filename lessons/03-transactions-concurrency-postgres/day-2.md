# Module 3, Tuesday: Postgres isolation, locks and retries

[Module 3](../../modules/03-transactions-concurrency-postgres.md) · [Leia em português](day-2.pt-BR.md)

**Reading time:** about 45 minutes. Use the rest of the 2-hour block on the references at the end, starting with section 13.2 of the Postgres docs.

This is an original text written for this course. It is based on the references listed at the end, and each section names the source it follows.

## Why this matters for a fintech

Yesterday gave you the map: which anomaly each isolation level allows. Today is about the tools Postgres gives you to stop them. There are three families: pick a stronger isolation level and retry, lock rows explicitly, or write the check into the `UPDATE` itself. Thursday's capstone builds one transfer with each of them, so today you need to know exactly how each behaves under concurrency, what error it raises, and what your NestJS code must do when that error arrives.

## 1. MVCC: every statement reads a snapshot

*Main source: PostgreSQL documentation, section 13.1 "Introduction".*

Postgres does not protect reads with locks. It keeps several versions of each row and shows every statement a **snapshot**: the database as it was at some moment. The docs call this Multiversion Concurrency Control (MVCC), and they name its main advantage: "reading never blocks writing and writing never blocks reading."

For a wallet, that means a long account statement query never blocks a transfer, and a transfer never blocks the statement. It also means two transactions can look at the "same" balance and see different values, depending on when each snapshot was taken. Every isolation level in Postgres is a rule about **when the snapshot is taken** and **what happens when two transactions write the same row**.

The docs add that explicit table and row locks exist "for applications which don't generally need full transaction isolation and prefer to explicitly manage particular points of conflict", and that advisory locks are available for locks not tied to a single transaction. Sections 5 to 7 cover both.

## 2. Read committed: a new snapshot for each statement

*Main source: PostgreSQL documentation, section 13.2.1 "Read Committed Isolation Level".*

Read committed is the default. In the docs' words, "a `SELECT` query sees a snapshot of the database as of the instant the query begins to run." Two `SELECT`s in the same transaction can see different data if another transaction commits in between.

The important part is what happens when an `UPDATE` finds a row that another transaction is changing:

1. It **waits** for the other transaction to commit or roll back.
2. If the other one commits, it takes the **new version** of the row.
3. It **re-evaluates the `WHERE` clause** against that new version, and applies the change only if the row still matches.

This rule explains two things you need for the capstone.

First, a single-statement debit does not lose updates:

```sql
UPDATE wallets SET balance = balance - 30 WHERE id = $1;
```

The second transaction waits, then subtracts from the balance the first one left. Yesterday's lost update needed the value to travel through application memory (`SELECT`, compute in TypeScript, `UPDATE ... SET balance = 70`). The docs use a bank transfer as their own example of this safe case: since each command affects a predetermined row, seeing the updated version "does not create any troublesome inconsistency."

Second, a **conditional update** is safe against overdraft at the default level:

```sql
UPDATE wallets
   SET balance = balance - $2
 WHERE id = $1 AND balance >= $2;
-- check the affected row count: 0 means insufficient funds (or no such wallet)
```

If two debits race for the last 100, the second waits, re-checks `balance >= $2` against the new balance, and matches zero rows. That is capstone version 3. Your code must read the affected row count (in node-postgres, `result.rowCount`) and turn 0 into a business error.

The docs also warn about the limit of this behavior. Their example is a `DELETE ... WHERE hits = 10` that silently does nothing because a concurrent `UPDATE` moved the value from 9 to 10 to 11 underneath it. Their conclusion: read committed is "unsuitable for commands that involve complex search conditions; however, it is just right for simpler cases." A check on one row's balance is a simple case. A check that sums several rows is not.

## 3. Repeatable read: one snapshot for the whole transaction

*Main source: PostgreSQL documentation, section 13.2.2 "Repeatable Read Isolation Level".*

At repeatable read, the snapshot is taken at the first real statement of the transaction and kept until the end. All your reads agree with each other, which is what a statement or a reconciliation report needs.

When a repeatable read transaction tries to update a row that another transaction changed and committed after the snapshot, Postgres does not re-evaluate. It aborts:

```
ERROR:  could not serialize access due to concurrent update
```

That is the error you saw at the end of yesterday's lab, and it is how repeatable read prevents lost updates. The docs are explicit about the consequence: "Applications using this level must be prepared to retry transactions due to serialization failures." They also note that read-only transactions never get this conflict.

The docs confirm what Hermitage showed: this level "is implemented using a technique known in academic database literature and in some other database products as *Snapshot Isolation*." And they warn about exactly the joint-wallet case: business rules enforced at this level "are not likely to work correctly without careful use of explicit locks to block conflicting transactions." Carla and Diego each update a different row, so neither gets the error, and the combined balance goes negative. That is today's lab.

## 4. Serializable and the 40001 retry loop

*Main sources: PostgreSQL documentation, sections 13.2.3 "Serializable Isolation Level" and 13.5 "Serialization Failure Handling".*

Serializable "works exactly the same as Repeatable Read except that it also monitors for conditions" that could produce a result no serial order would produce. Postgres implements it as Serializable Snapshot Isolation, the SSI from yesterday's reading. To track what each transaction read, it uses **predicate locks**, visible in `pg_locks` with mode `SIReadLock`. These locks never block anyone and can never cause a deadlock. They are bookkeeping, used to detect dangerous read/write patterns.

The docs' own example is two transactions that each sum one class of rows and insert the result into the other class. Both would commit at repeatable read. At serializable, one fails with:

```
ERROR:  could not serialize access due to read/write dependencies among transactions
```

Run the joint-wallet transactions at serializable and one of them fails the same way. Section 13.5 tells you how to handle these errors:

- Every serialization failure has SQLSTATE **`40001`** (`serialization_failure`), whatever the message says. The docs recommend retrying these unconditionally.
- Deadlocks (`40P01`, `deadlock_detected`) may also be worth retrying.
- Unique violations (`23505`) are retryable only in some cases, since they may be a persistent error rather than a transient one.
- Retry **the whole transaction**, "including all logic that decides which SQL to issue and/or which values to use." That is why Postgres has no automatic retry: it cannot re-run your TypeScript.
- A retry can fail again. Under heavy contention it can take many attempts, so bound them.

In a NestJS service with node-postgres, the shape looks like this:

```ts
import { Pool, PoolClient } from 'pg';

const RETRYABLE = new Set(['40001', '40P01']);

export async function inSerializable<T>(
  pool: Pool,
  work: (client: PoolClient) => Promise<T>,
  maxAttempts = 5,
): Promise<T> {
  for (let attempt = 1; ; attempt++) {
    const client = await pool.connect();
    try {
      await client.query('BEGIN ISOLATION LEVEL SERIALIZABLE');
      const result = await work(client); // re-reads balances on every attempt
      await client.query('COMMIT');
      return result;
    } catch (err: any) {
      await client.query('ROLLBACK').catch(() => undefined);
      if (!RETRYABLE.has(err.code) || attempt >= maxAttempts) throw err;
      await new Promise((r) => setTimeout(r, Math.random() * 20 * attempt));
    } finally {
      client.release();
    }
  }
}
```

Note that the error can arrive at an `UPDATE` or at `COMMIT`, so the catch block covers both. The docs also add a subtle rule: data read in a serializable transaction should not be considered valid until that transaction commits. Do not send a push notification with a balance read halfway through.

The docs list performance advice for serializable systems. The items that matter most for a wallet: declare transactions `READ ONLY` when possible, keep the number of active connections under control with a pool, put no more into a transaction than integrity needs, and do not leave sessions "idle in transaction". They also note that a sequential scan always takes a relation-level predicate lock, which can raise the failure rate. Good indexes help serializable, which is one more reason for tomorrow's topic.

## 5. Row locks: SELECT ... FOR UPDATE and friends

*Main sources: PostgreSQL documentation, section 13.3.2 "Row-Level Locks", and the "Locking Clause" of the `SELECT` reference page.*

The other family is pessimistic: lock the rows first, then read and write them. `SELECT ... FOR UPDATE` locks the returned rows so that other transactions trying to update, delete or lock them wait until you finish.

There are four row lock modes. Only two matter often in a wallet:

| Mode | Use it when | Blocks |
| --- | --- | --- |
| `FOR UPDATE` | you will change the row, or need nobody else to | every other row lock mode and every `UPDATE`/`DELETE` |
| `FOR NO KEY UPDATE` | taken automatically by a plain `UPDATE` that doesn't change a key | `FOR SHARE`, `FOR NO KEY UPDATE`, `FOR UPDATE` |
| `FOR SHARE` | you need the row not to change while you read | updates and exclusive locks, not other shares |
| `FOR KEY SHARE` | (taken by foreign key checks) | only `FOR UPDATE` and key changes |

Capstone version 1 locks both wallets of a transfer before touching them:

```sql
BEGIN;
SELECT id, balance FROM wallets
 WHERE id IN ($1, $2)
 ORDER BY id
   FOR UPDATE;
-- check the source balance in code, then two UPDATEs and the ledger inserts
COMMIT;
```

Two details from the docs. At repeatable read or serializable, locking a row that another transaction changed since your transaction started raises an error, so this pattern is usually run at read committed. And the `SELECT` reference has a caution: at read committed, `ORDER BY` with a locking clause can return rows out of order, because the sort happens first and the rows are locked as they come out of it. If a sort column changes while you wait for its lock, the result can come back out of order. Wallet ids never change, so `ORDER BY id` keeps the lock order consistent. If you want the order to be obvious to a reviewer, lock the two rows in two separate statements, lowest id first.

The `SELECT` page also documents two options that avoid waiting:

- **`NOWAIT`**: report an error at once if a row is already locked. Useful when waiting would break a latency budget.
- **`SKIP LOCKED`**: skip rows that are locked. The docs say this gives "an inconsistent view of the data", so it is not for general work, but it fits "multiple consumers accessing a queue-like table". That is exactly the outbox worker of Module 4: several workers each grab the next unlocked batch of pending messages without stepping on each other. Never use it for balances.

## 6. Deadlocks and lock ordering

*Main source: PostgreSQL documentation, section 13.3.4 "Deadlocks".*

The docs' deadlock example is a transfer, which shows how natural it is to write one. Transaction 1 credits account 11111. Transaction 2 credits 22222, then tries to debit 11111 and waits for transaction 1. Transaction 1 then tries to debit 22222 and waits for transaction 2. Each waits for the other forever.

In a wallet, this happens whenever Ana pays Bruno while Bruno pays Ana, and each transfer locks "source first, then destination". Postgres detects the cycle and aborts one of the transactions with SQLSTATE `40P01`. Which one is aborted "is difficult to predict and should not be relied upon."

The docs give the cure: "The best defense against deadlocks is generally to avoid them by being certain that all applications using a database acquire locks on multiple objects in a consistent order." For transfers, that order is wallet id: always lock the smaller id first, whichever is the source. The docs add two more rules worth copying into your notes:

- Take the most restrictive lock you will need on a row the first time you lock it. Locking `FOR SHARE` and then upgrading to `FOR UPDATE` invites deadlocks.
- A transaction waiting for a lock waits indefinitely unless a deadlock is detected. Never keep a transaction open while you call the partner bank or wait for a user. Set `lock_timeout` or `statement_timeout` if you need a bound.

## 7. Advisory locks

*Main sources: PostgreSQL documentation, section 13.3.5 "Advisory Locks", and section 9.28.10 "Advisory Lock Functions".*

Advisory locks lock a **number** you choose, not a row. The docs call them advisory "because the system does not enforce their use": every piece of code must agree to take the lock. The functions take a `bigint` key (or two `integer` keys):

| Function | Scope | If the lock is taken |
| --- | --- | --- |
| `pg_advisory_xact_lock(key)` | until the transaction ends | waits |
| `pg_try_advisory_xact_lock(key)` | until the transaction ends | returns `false` |
| `pg_advisory_lock(key)` | until `pg_advisory_unlock` or the session ends | waits |
| `pg_try_advisory_lock(key)` | same as above | returns `false` |

Prefer the transaction-level versions. Session-level locks ignore transaction semantics: a lock taken in a transaction that rolls back is still held afterwards. With a connection pool, a forgotten session lock stays on a pooled connection and blocks whoever needs it next.

A good wallet use: make sure only one instance of the daily reconciliation job runs, with `SELECT pg_try_advisory_lock(42)` at startup. A poor use: protecting balances, since any code path that forgets the call is unprotected. The docs also warn against calling the lock function in a query with `LIMIT`, because the limit may be applied after some locks were taken.

## 8. The three ways to stop a negative balance

This table prepares Thursday. Fill in the measured numbers on Friday.

| Version | Mechanism | Under contention | Failure your code handles |
| --- | --- | --- | --- |
| v1 pessimistic | `SELECT ... FOR UPDATE` on both wallets, in id order | transfers queue up behind the lock | deadlock (`40P01`) if ordering is wrong; lock waits |
| v2 optimistic | read `version`, then `UPDATE ... WHERE id = $1 AND version = $2`, bounded retries | no waiting, but conflicts cause retries | 0 rows updated means someone else won: retry or give up |
| v3 conditional | `UPDATE ... WHERE balance >= $amount`, check row count | each update waits briefly on the row | 0 rows means insufficient funds |

The optimistic version column is a general pattern, not a Postgres feature: you add an integer `version`, increment it on every write, and treat "0 rows updated" as a conflict. A fourth option, running everything at serializable with the retry loop from section 4, is the only one that also protects rules spanning several rows, such as the joint wallet.

## Notes to write today

1. The four isolation levels as Postgres implements them: when the snapshot is taken, what happens on a write conflict, and which error appears. Include SQLSTATE `40001`, the two error texts, and the rule "retry the whole transaction, bounded".
2. Your retry policy: which SQLSTATEs you retry, how many attempts, what backoff, and why the logic that reads balances must run again.
3. When to use `SELECT ... FOR UPDATE`, `NOWAIT`, `SKIP LOCKED` and advisory locks, one wallet example each.
4. The deadlock between two opposite transfers, drawn as two columns, and the lock ordering rule that prevents it.
5. From the lab: the joint-wallet write skew under repeatable read (final balances) and the exact error under serializable.

## Check yourself

These make good flashcards (see the [flashcards guide](../../FLASHCARDS.md)).

- At read committed, why does `UPDATE ... SET balance = balance - 30` not lose an update?
- What does an `UPDATE` at read committed do when the row it targets was changed by a transaction that just committed?
- Which SQLSTATE marks a serialization failure, and what exactly must you retry?
- Why does repeatable read in Postgres not stop the joint-wallet write skew?
- What is `SKIP LOCKED` good for, and why not for balances?
- How do you prevent deadlocks between two opposite transfers?
- Why are transaction-level advisory locks safer than session-level ones behind a connection pool?

## References

- **Main source:** PostgreSQL documentation, ["Concurrency Control"](https://www.postgresql.org/docs/current/mvcc.html), sections [13.1 "Introduction"](https://www.postgresql.org/docs/current/mvcc-intro.html) and [13.2 "Transaction Isolation"](https://www.postgresql.org/docs/current/transaction-iso.html). Read 13.2 in full, including the serializable performance advice. Free.
- PostgreSQL documentation, ["Explicit Locking"](https://www.postgresql.org/docs/current/explicit-locking.html) (section 13.3). Read 13.3.2 (row-level locks), 13.3.4 (deadlocks) and 13.3.5 (advisory locks); skim the table-level lock table. Free.
- PostgreSQL documentation, ["Serialization Failure Handling"](https://www.postgresql.org/docs/current/mvcc-serialization-failure-handling.html) (section 13.5). Short; read it all. Free.
- PostgreSQL documentation, [`SELECT` reference, "The Locking Clause"](https://www.postgresql.org/docs/current/sql-select.html), for `NOWAIT`, `SKIP LOCKED` and the `ORDER BY` caution. Free.
- PostgreSQL documentation, ["Advisory Lock Functions"](https://www.postgresql.org/docs/current/functions-admin.html#FUNCTIONS-ADVISORY-LOCKS) (section 9.28.10). Free.
- PostgreSQL documentation, ["Data Consistency Checks at the Application Level"](https://www.postgresql.org/docs/current/applevel-consistency.html) (section 13.4), if time is left: when to rely on serializable and when on explicit locks. Free.
