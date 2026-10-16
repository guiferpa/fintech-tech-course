# Module 3, Monday: isolation levels and the anomalies they allow

[Module 3](../../modules/03-transactions-concurrency-postgres.md) · [Leia em português](day-1.pt-BR.md)

**Reading time:** about 45 minutes. Use the rest of the 2-hour block on the references at the end, starting with the Hermitage table.

This is an original text written for this course. It is based on the references listed at the end, and each section names the source it follows. Where an idea comes from a specific author, the text says so.

## Why this matters for a fintech

A wallet holds money in rows, and many requests touch the same rows at the same time. A customer double-taps "Pay". A Pix transfer arrives while a card purchase is being authorized. A batch job charges monthly fees while the customer moves money out. Each request is correct on its own. Run them together, and the balance can end up wrong.

Databases promise "transactions", but the promise is weaker than most engineers think. Postgres runs at READ COMMITTED by default, and that level lets two correct transfers produce a negative balance. This week is about knowing exactly which anomaly each level allows, and then preventing negative balances in more than one way. Today is the theory: the vocabulary and the map.

## 1. What ACID actually promises

*Main source: Jepsen, "Consistency Models" map, and PostgreSQL documentation, section 13.2.*

ACID is four letters, and each one promises something different. Read them with a transfer from Ana's wallet to Bruno's in mind: one debit, one credit, one transaction.

| Letter | What it promises | What it does not promise |
| --- | --- | --- |
| **Atomicity** | If the transaction aborts, none of its writes remain. The debit never stays without the credit. | That the transaction will succeed, or that a retry is safe. |
| **Consistency** | Declared constraints (`CHECK`, `UNIQUE`, foreign keys) hold after every commit. | Business rules you did not declare, such as "a couple's combined balance never goes below zero". Those are your code's job. |
| **Isolation** | Concurrent transactions are kept apart to the degree the chosen level says. | That every level behaves as if transactions ran one at a time. Only serializable does. |
| **Durability** | A committed transaction survives a crash. | That a replica has it (see Module 1, Tuesday). |

The letter that hides the most is **I**. Isolation is not one property but a family of them, called isolation levels or, in Jepsen's broader vocabulary, consistency models. Jepsen describes a consistency model as "a safety property which declares what a system can do." Formally, a model is the set of histories (orderings of reads and writes) a system is allowed to produce. A weaker model allows more histories, and some of those histories break your invariants.

So "it runs in a transaction" is not an answer to "can this go negative?". The real answer always names an isolation level and an anomaly.

## 2. The map of isolation levels

*Main source: Jepsen, "Consistency Models" map and the pages "Read Committed" and "Snapshot Isolation".*

Jepsen's map draws models as a tree where an arrow means "implies". The transactional part of the tree, simplified, looks like this:

```
strict serializable
        |
   serializable
     /        \
repeatable   snapshot
  read       isolation
     \        /
monotonic atomic view   (cursor stability also sits here)
        |
  read committed
        |
 read uncommitted
```

Two facts from the map matter most for this week:

- **Serializable implies snapshot isolation.** Every serializable history is also a valid snapshot history, but not the other way around.
- **Snapshot isolation and repeatable read are incomparable.** Jepsen points out that each allows a phenomenon the other prohibits. This matters because Postgres uses the name "repeatable read" for what is really snapshot isolation (section 4).

**Read committed.** Jepsen's page says it in one line: "transactions are not allowed to observe writes from transactions which do not commit." It forbids dirty writes (P0: overwriting someone's uncommitted write) and dirty reads (P1: reading someone's uncommitted write). It allows fuzzy reads (P2: you read a row, someone commits a change, you read it again and see a different value) and phantoms (P3: you query a set of rows, someone commits a new row that matches, and your set changes). Jepsen notes that read committed can be totally available, which means every node can keep working during a network partition.

**Snapshot isolation.** Jepsen's definition: "In a snapshot isolated system, each transaction appears to operate on an independent, consistent snapshot of the database." Your transaction reads from a frozen picture taken when it starts. Its writes stay invisible until commit, and then all appear at once. Snapshot isolation also has a **first-committer-wins** rule: if two concurrent transactions write the same object, the second one to commit must abort. That rule is what prevents lost updates. Snapshot isolation cannot be totally available, so on a partition some nodes must stop.

What snapshot isolation still allows is the subject of section 3. Jepsen's page is direct: "The most notable phenomena allowed by snapshot isolation are write skews".

**Serializable.** Every committed result is equivalent to running the transactions one at a time, in some order. Nothing on the anomaly list can happen.

## 3. Lost update, write skew and phantoms, in wallet terms

*Main sources: Justin Jaffray, "What write skew looks like" (Cockroach Labs blog), for write skew; PostgreSQL documentation, section 13.2, for the phenomena definitions.*

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

The final balance is 50. The 30 purchase happened, but its debit was overwritten. Both transactions wrote the **same row**, and the second write erased the first. This is the classic read-modify-write bug, and it lives in application code that reads a value, does arithmetic in TypeScript, and writes the result.

**Write skew.** Carla and Diego have a joint plan: two wallets, A and B, with the rule "A + B must stay at or above zero". A has 100 and B has 0. Carla withdraws 100 from A while Diego withdraws 100 from B. Each transaction reads both balances, checks the rule against its snapshot, and writes only its own wallet.

| Step | T1 (Carla, from A) | T2 (Diego, from B) |
| --- | --- | --- |
| 1 | reads A=100, B=0; sum 100 ≥ 100, OK | |
| 2 | | reads A=100, B=0; sum 100 ≥ 100, OK |
| 3 | `UPDATE wallet A` → 0 | |
| 4 | | `UPDATE wallet B` → -100 |
| 5 | `COMMIT` | `COMMIT` |

The sum is now -100. Neither transaction broke the rule on its own, and they wrote **different rows**, so first-committer-wins sees no conflict. Jaffray's article explains the general shape: two concurrent transactions read overlapping data, write to disjoint places, and both commit with a result that no serial order could produce. His own example is abstract and worth reading: transaction P copies register x into y, transaction Q copies y into x, and under snapshot isolation the two values end up swapped. As he puts it, that is "an outcome not possible in either serial execution."

**Phantom.** The Postgres docs define a phantom read as re-running a query with a search condition and finding a different set of rows because another transaction committed. In a wallet, the dangerous case is a check that reads a **set** of rows and then inserts a new one. Say the daily Pix limit is 1,000. T1 sums today's transfers (800), sees room for 200, and inserts a 200 transfer. T2 does the same at the same time with another 200. Both commit, and the day ends at 1,200. No existing row was updated by both. The conflict is about a row that did not exist yet when each one read. Hermitage calls this "write skew on predicate read" (G2), as opposed to write skew on rows that already exist (G2-item).

A quick way to tell them apart:

| Anomaly | Both transactions write... | What the check read | Typical wallet bug |
| --- | --- | --- | --- |
| Lost update | the same row | that same row | read balance, subtract in code, write back |
| Write skew | different rows | rows the other one writes | shared limit across two wallets |
| Phantom (G2) | new rows | a set defined by a condition | daily limit by summing transfers |

## 4. Why serializable fixes write skew

*Main source: Justin Jaffray, "What write skew looks like", sections "Who cares?" and "When is Snapshot not Serializable?".*

Jaffray's article explains the theory behind the fix, and it is worth knowing for interviews.

Draw each transaction as a node. Add an edge when one transaction depends on another. There are three kinds of dependency: **wr** (T2 reads what T1 wrote), **ww** (T2 overwrites what T1 wrote) and **rw**, also called an anti-dependency (T1 read a value that T2 then overwrote, so T1 must come before T2). Jaffray states the key result: "A history is serializable if and only if its serialization graph has no cycles."

In the joint-wallet story, T1 read B and T2 wrote B, so T1 must come before T2. T2 read A and T1 wrote A, so T2 must come before T1. That is a cycle of two rw edges, and no serial order exists.

Jaffray also notes that between concurrent snapshot transactions, the only possible dependency is rw. He cites a theorem by Fekete and colleagues: every cycle in a snapshot history contains two consecutive rw edges. Postgres's **Serializable Snapshot Isolation (SSI)** uses that result. It tracks rw dependencies, and when it sees a dangerous pattern it aborts one transaction. It sometimes aborts a transaction that was not really part of a cycle, which is the price of checking cheaply.

The practical reason to prefer serializable is what Jaffray calls local reasoning. Under serializable, "it's sufficient to verify that every individual transaction maintains this invariant on its own". Under weaker levels, "one must consider the interactions between every transaction to ensure said invariants are upheld". For a wallet with dozens of operations that touch balances, that difference is huge. Under serializable, you review each operation once. Under snapshot isolation, you have to review every pair.

## 5. What Postgres actually gives you

*Main source: Martin Kleppmann, Hermitage repository, PostgreSQL rows of the results table.*

Hermitage is a set of tests Kleppmann wrote to check which anomalies each database really prevents at each isolation level. His README starts from a blunt observation: "Unfortunately, those weaker isolation levels are quite poorly understood." He adds that vendor documentation about them is "frustratingly vague". Each test is a sequence of SQL statements typed into two or more sessions, so you can reproduce any row yourself with two `psql` windows.

Kleppmann bases the project on Adya's formal definition of weak isolation, as extended by Bailis and colleagues, and that is where the anomaly codes come from. The ones that matter here:

| Code | Name in Hermitage | Wallet meaning |
| --- | --- | --- |
| G0 | write cycles (dirty writes) | two transfers interleave writes on the same rows |
| G1a, G1b, G1c | dirty reads | you see a debit that later rolls back |
| P4 | lost update | section 3 |
| G-single | read skew | a statement shows A after a transfer and B before it |
| G2-item | write skew on disjoint read | joint-wallet rule |
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

Then repeat the same steps with `BEGIN ISOLATION LEVEL REPEATABLE READ` in both sessions. Hermitage predicts that the second writer now gets an error instead of silently erasing the first write. Write down the error text; tomorrow's reading names it.

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
- What is a phantom, and what wallet check is exposed to one?
- What makes a history serializable, in terms of its dependency graph?

## References

- **Main source:** Martin Kleppmann, ["Hermitage: testing transaction isolation levels"](https://github.com/ept/hermitage), GitHub repository. Read the README's results table, focusing on the PostgreSQL rows, then open the `postgres.md` test file to see the exact session-by-session commands. Free.
- Jepsen, ["Consistency Models"](https://jepsen.io/consistency) map, plus the model pages ["Read Committed"](https://jepsen.io/consistency/models/read-committed) and ["Snapshot Isolation"](https://jepsen.io/consistency/models/snapshot-isolation). Read the map first, then both pages, skipping the formal definitions on a first pass. Free.
- Justin Jaffray, ["What write skew looks like"](https://www.cockroachlabs.com/blog/what-write-skew-looks-like/), Cockroach Labs blog, 2022. Read it all; the dependency-graph part is the hardest and the most useful. The article focuses on write skew; lost updates and phantoms come from Hermitage and the Postgres docs. Free.
- PostgreSQL documentation, ["Transaction Isolation"](https://www.postgresql.org/docs/current/transaction-iso.html) (section 13.2), Table 13.1 and the definitions above it. Free. This is tomorrow's main reading; today, read only the table.
