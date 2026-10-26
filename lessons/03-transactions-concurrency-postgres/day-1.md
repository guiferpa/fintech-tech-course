# Module 3, Monday: isolation levels and the anomalies they allow

[Module 3](../../modules/03-transactions-concurrency-postgres.md) · [Leia em português](day-1.pt-BR.md)

**Reading time:** about 45 minutes. Use the rest of the 2-hour block on the references at the end, starting with the Hermitage table and the PostgreSQL wiki examples.

This is an original text written for this course. It is based on the references listed at the end, and each section names the source it follows. Where an idea comes from a specific author, the text says so.

## Why this matters for a fintech

A wallet holds money in rows, and many requests touch the same rows at the same time. A customer double-taps "Pay". A Pix transfer arrives while a card purchase is being authorized. A batch job charges monthly fees while the customer moves money out. Each request is correct on its own. Run them together, and the balance can end up wrong.

Databases promise "transactions", but the promise is weaker than most engineers think. Postgres runs at READ COMMITTED by default, and that level lets two correct transfers produce a negative balance. This week is about knowing exactly which anomaly each level allows, and then preventing negative balances in more than one way. Today is the vocabulary, told through what Postgres really does and through examples you can type into `psql`.

## 1. What ACID actually promises

*Main source: PostgreSQL documentation, "Transaction Isolation" (section 13.2).*

ACID is four letters, and each one promises something different. Read them with a transfer from Ana's wallet to Bruno's in mind: one debit, one credit, one transaction.

| Letter | What it promises | What it does not promise |
| --- | --- | --- |
| **Atomicity** | If the transaction aborts, none of its writes remain. The debit never stays without the credit. | That the transaction will succeed, or that a retry is safe. |
| **Consistency** | Declared constraints (`CHECK`, `UNIQUE`, foreign keys) hold after every commit. | Business rules you did not declare, such as "a couple's combined balance never goes below zero". Those are your code's job. |
| **Isolation** | Concurrent transactions are kept apart to the degree the chosen level says. | That every level behaves as if transactions ran one at a time. Only serializable does. |
| **Durability** | A committed transaction survives a crash. | That a replica has it (see Module 1, Tuesday). |

The letter that hides the most is **I**. Isolation is not one property but a menu of levels, and each level allows a different set of surprises. Only the strongest level, serializable, guarantees that the result matches some order of running the transactions one at a time. Every level below that trades some of that guarantee for fewer aborts and less waiting.

So "it runs in a transaction" is not an answer to "can this go negative?". The real answer always names an isolation level and an anomaly.

## 2. The four levels, as Postgres implements them

*Main source: PostgreSQL documentation, "Transaction Isolation", Table 13.1 and the definitions above it.*

The SQL standard defines four levels by the phenomena each one forbids. The Postgres docs define the phenomena in one sentence each. In wallet terms:

- **Dirty read.** "A transaction reads data written by a concurrent uncommitted transaction." You see a debit that later rolls back.
- **Nonrepeatable read.** A transaction reads a row again and finds it changed by another transaction that committed in between. You read Ana's balance twice in one transaction and get 100, then 70.
- **Phantom read.** A transaction re-runs a query with a search condition and the set of matching rows has changed because another transaction committed. You sum today's Pix transfers twice and a new one appears.
- **Serialization anomaly.** "The result of successfully committing a group of transactions is inconsistent with all possible orderings of running those transactions one at a time." Each transaction looked fine, but together they produced a state no serial order could produce.

Table 13.1 then says which level allows what. Note the two "but not in PG" cells, because they are where Postgres is stricter than the standard:

| Level | Dirty read | Nonrepeatable read | Phantom read | Serialization anomaly |
| --- | --- | --- | --- | --- |
| Read uncommitted | Allowed, but not in PG | Possible | Possible | Possible |
| Read committed | Not possible | Possible | Possible | Possible |
| Repeatable read | Not possible | Not possible | Allowed, but not in PG | Possible |
| Serializable | Not possible | Not possible | Not possible | Not possible |

Three practical facts follow, all from the same page:

- **Read committed is the default.** If you never set a level, every transaction in your NestJS service runs at it.
- **Postgres implements only three levels.** Read uncommitted behaves like read committed, so there are no dirty reads in Postgres.
- **Repeatable read works on a snapshot.** Your transaction sees the data as of its first statement, so nonrepeatable reads and classic phantoms do not happen. It still allows serialization anomalies, which section 3 shows with money.

One more behavior matters for the lab. At repeatable read, if you update a row that another transaction changed and committed after your snapshot was taken, Postgres refuses with `ERROR: could not serialize access due to concurrent update`, and the docs say to retry the whole transaction. This first-committer-wins rule stops the lost update but not write skew.

At serializable, the failure has a different message, `could not serialize access due to read/write dependencies among transactions`, and both messages share SQLSTATE `40001`. The docs recommend a generic way to catch `40001` and retry. Tuesday's lesson builds that retry.

## 3. Lost update, write skew and phantoms, in wallet terms

*Main sources: Justin Jaffray, "What write skew looks like" (Cockroach Labs blog), for write skew; PostgreSQL wiki, "SSI", for the overdraft and intersecting-data examples; PostgreSQL documentation, section 13.2, for the phenomena definitions.*

These three anomalies are the ones that break balances. Learn them as three stories, each with two concurrent transactions T1 and T2.

**Lost update.** Ana's wallet has 100. Two purchases of 30 and 50 run at the same time. Both transactions read the balance into application memory, compute a new value, and write it back.

| Step | T1 (purchase 30) | T2 (purchase 50) |
| --- | --- | --- |
| 1 | `SELECT balance` → 100 | |
| 2 | | `SELECT balance` → 100 |
| 3 | `UPDATE ... SET balance = 70` | |
| 4 | `COMMIT` | |
| 5 | | `UPDATE ... SET balance = 50` (waits, then runs) |
| 6 | | `COMMIT` |

The final balance is 50. The 30 purchase happened, but its debit was overwritten. Both transactions wrote the **same row**, and the second write erased the first. This is the classic read-modify-write bug, and it lives in application code that reads a value, does arithmetic in TypeScript, and writes the result. At repeatable read, step 5 fails with the "concurrent update" error from section 2 instead.

**Write skew.** The PostgreSQL wiki page on SSI has a banking example that fits a wallet almost word for word. Kevin has two accounts, savings and checking, with 500 each. The bank lets a customer withdraw "up to the total of what they have in all accounts" and moves funds between accounts later to close the day positive. Someone submits two withdrawals of 900 at the same time, one from each account. Each transaction checks that the total covers the amount, sees 1,000, decides 900 is fine, and updates only its own account.

| Step | T1 (900 from savings) | T2 (900 from checking) |
| --- | --- | --- |
| 1 | reads savings=500, checking=500; total 1,000, OK | |
| 2 | | reads savings=500, checking=500; total 1,000, OK |
| 3 | `UPDATE` savings → -400 | |
| 4 | | `UPDATE` checking → -400 |
| 5 | `COMMIT` | `COMMIT` |

The total is now -800. Neither transaction broke the rule on its own, and they wrote **different rows**, so first-committer-wins sees no conflict. The wiki says that at repeatable read this "could work", meaning both withdrawals go through. At serializable, Postgres lets the first committer win and fails the other with a serialization error. On retry, the second transaction sees a net of 100, and the application rejects the 900 withdrawal.

Jaffray's article explains the general shape: two concurrent transactions read overlapping data, write to disjoint places, and both commit. In his example, P copies x into y while Q copies y into x, and the values end up swapped, "an outcome not possible in either serial execution."

**Phantom-style write skew.** The dangerous case for a wallet is a check that reads a **set** of rows and then inserts a new one. Say the daily Pix limit is 1,000. T1 sums today's transfers (800), sees room for 200, and inserts a 200 transfer. T2 does the same at the same time with another 200. Both commit, and the day ends at 1,200. No existing row was updated by both. The conflict is about a row that did not exist yet when each one read.

The Postgres docs and the wiki both use the same shape with a table `mytab(class, value)`: one transaction sums class 1 and inserts the result as class 2, the other sums class 2 and inserts the result as class 1. At repeatable read both commit. At serializable one fails. Note the subtlety: Table 13.1 says repeatable read in Postgres has no phantom reads, and that is true: neither transaction ever sees the other's new row. That is exactly the problem, since each one decided on an outdated snapshot. Hermitage calls this "write skew on predicate read" (G2), as opposed to write skew on rows that already exist (G2-item, "write skew on disjoint read").

## 4. Why serializable fixes write skew

*Main sources: Justin Jaffray, "What write skew looks like", sections "Who cares?" and "When is Snapshot not Serializable?"; PostgreSQL wiki, "SSI".*

Jaffray's article explains the theory behind the fix, and it is worth knowing for interviews.

Draw each transaction as a node. Add an edge when one transaction depends on another. There are three kinds of dependency: **wr** (T2 reads what T1 wrote), **ww** (T2 overwrites what T1 wrote) and **rw**, also called an anti-dependency (T1 read a value that T2 then overwrote, so T1 must come before T2). Jaffray states the key result: "A history is serializable if and only if its serialization graph has no cycles."

In Kevin's story, T1 read checking and T2 wrote checking, so T1 must come before T2. T2 read savings and T1 wrote savings, so T2 must come before T1. That is a cycle of two rw edges, and no serial order exists.

Jaffray also notes that between concurrent snapshot transactions, the only possible dependency is rw, and that every cycle in a non-serializable snapshot history contains two consecutive rw edges. Postgres's **Serializable Snapshot Isolation (SSI)** is built on that observation. It tracks rw dependencies, and when it sees a dangerous pattern it aborts one transaction. The wiki's overdraft example describes exactly this: SSI detects a "dangerous structure" and cancels one of the two withdrawals.

The wiki adds two practical warnings that matter for your code:

- **Ignore results from a failed transaction.** The wiki says any query results from a failed serializable transaction "must be ignored; use the results from the retry." If your handler already computed a response from the first attempt, throw it away.
- **Retries must be generic.** In the wiki's three-transaction example (the "Primary Colors" case), the wiki says the fate of the third transaction "is not deterministic": it might commit or it might get a serialization failure. You cannot predict which transaction gets the error, so every transaction that touches balances needs the same retry wrapper.

The practical reason to prefer serializable is what Jaffray calls local reasoning. Under serializable, "it's sufficient to verify that every individual transaction maintains this invariant on its own". Under weaker levels, "one must consider the interactions between every transaction to ensure said invariants are upheld". For a wallet with dozens of operations that touch balances, that difference is huge. Under serializable, you review each operation once. Under snapshot isolation, you have to review every pair.

The wiki's "Deposit Report" example is a back-office version of the same problem: a receipt that slips into a batch already closed and taken to the bank. Reconciliation jobs in Module 7 have that shape.

## 5. What Postgres actually gives you

*Main source: Martin Kleppmann, Hermitage repository, PostgreSQL rows of the results table.*

Hermitage is a set of tests Kleppmann wrote to check which anomalies each database really prevents at each isolation level. His README starts from a blunt observation: "Unfortunately, those weaker isolation levels are quite poorly understood." He adds that vendor documentation about them is "frustratingly vague". Each test is a sequence of SQL statements typed into two or more sessions, so you can reproduce any row yourself with two `psql` windows. That is what makes it practical: it is a test suite, not a theory.

The anomaly codes that matter here, with the names Hermitage gives them:

| Code | Name in Hermitage | Wallet meaning |
| --- | --- | --- |
| G0 | write cycles (dirty writes) | two transfers interleave writes on the same rows |
| G1a, G1b, G1c | aborted reads, intermediate reads, circular information flow | you see a debit that later rolls back, or half of a transaction |
| P4 | lost update | section 3 |
| G-single | read skew | a statement shows A after a transfer and B before it |
| G2-item | write skew on disjoint read | Kevin's two accounts |
| G2 | write skew on predicate read | daily limit by summing rows |

The PostgreSQL rows, as Hermitage reports them:

| Level you ask for | What it really is | Prevents | Allows |
| --- | --- | --- | --- |
| read committed (default) | monotonic atomic view | G0, G1a, G1b, G1c, OTV | PMP, **P4**, G-single, **G2-item**, **G2** |
| repeatable read | snapshot isolation | all of the above plus PMP, **P4**, G-single | **G2-item**, **G2** |
| serializable | serializable | all ten | none |

Read the bold codes as this week's plan:

- **At the default level, Postgres allows lost updates.** That is Monday's lab.
- **Repeatable read stops lost updates but allows write skew.** That is Tuesday's lab, with the joint wallet.
- **Serializable stops both**, by aborting one transaction with error 40001. Tuesday you will see that error and learn to retry it.

One detail to remember: the lost update at read committed needs the read-modify-write pattern from section 3. Tomorrow's reading explains why `UPDATE wallets SET balance = balance - 30` in a single statement does not lose the update, even at read committed.

## 6. Preparing today's lab

The lab asks you to reproduce a lost update in two `psql` sessions under READ COMMITTED and write down the exact command sequence. Plan it before you type:

1. Create a small table with one wallet and a known balance.
2. In session 1, start a transaction and read the balance with a plain `SELECT`.
3. In session 2, do the same.
4. In session 1, write the new balance as a literal (what your code would compute), then commit.
5. In session 2, write its own computed literal and commit.
6. Read the balance and compare it with what it should be.

Then repeat the same steps with `BEGIN ISOLATION LEVEL REPEATABLE READ` in both sessions. Hermitage and the Postgres docs both predict that the second writer now gets `could not serialize access due to concurrent update` instead of silently erasing the first write. Write down the full error text.

If time is left, paste Kevin's overdraft example from the wiki into the same two sessions, at repeatable read and then at serializable.

## Notes to write today

1. A table with the four Postgres isolation levels you can request (read uncommitted, read committed, repeatable read, serializable) and, for each, what it forbids and what it still allows. Add one line on what ACID really promises for a balance, and which business rules stay your job.
2. Lost update vs. write skew vs. phantom, each in one sentence plus a wallet example. Then build your own write-skew example with balances: two rows, a rule that spans both, and the step-by-step interleaving that breaks it.
3. The three PostgreSQL rows of the Hermitage table, copied from the source, with one sentence on what surprised you.
4. From the lab: the exact command sequence that produced a lost update, and the error you saw under repeatable read.

## Check yourself

These make good flashcards (see the [flashcards guide](../../FLASHCARDS.md)).

- What is the default isolation level in Postgres, and does it allow lost updates?
- What is the difference between a lost update and write skew?
- Why does first-committer-wins not stop write skew?
- What does Postgres's "repeatable read" level really implement, according to Hermitage?
- Which ACID letter covers the rule "a couple's combined balance never goes below zero"? Who enforces it?
- Table 13.1 says Postgres's repeatable read has no phantom reads. Why can a daily-limit check still be broken at that level?
- What makes a history serializable, in terms of its dependency graph?
- Which SQLSTATE do both serialization errors share, and what should your code do with it?

## References

- **Main source:** Martin Kleppmann, ["Hermitage: testing transaction isolation levels"](https://github.com/ept/hermitage), GitHub repository. Read the README's results table, focusing on the PostgreSQL rows, then open the `postgres.md` test file to see the exact session-by-session commands. Free.
- **Main source:** PostgreSQL wiki, ["SSI"](https://wiki.postgresql.org/wiki/SSI). Read the Overview, the three "Simple Write Skew" examples (Black and White, Intersecting Data, Overdraft Protection) and "Deposit Report". Each one is a session-by-session script you can paste into `psql`. Free.
- Justin Jaffray, ["What write skew looks like"](https://www.cockroachlabs.com/blog/what-write-skew-looks-like/), Cockroach Labs blog, 2022. Read it all; the dependency-graph part is the hardest and the most useful. The article focuses on write skew; lost updates and phantoms come from Hermitage and the Postgres docs. Free.
- PostgreSQL documentation, ["Transaction Isolation"](https://www.postgresql.org/docs/current/transaction-iso.html) (section 13.2). Today, read the introduction, the phenomena definitions and Table 13.1. Free. This is tomorrow's main reading, so the rest of the page can wait.
