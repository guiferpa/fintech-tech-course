# Module 4, Monday: two-phase commit and why sagas exist

[Module 4](../../modules/04-sagas-outbox.md) · [Leia em português](day-1.pt-BR.md)

**Reading time:** about 45 minutes. Use the rest of the 2-hour block on the references at the end, starting with the sections marked as the main source.

This is an original text written for this course. It is based on the references listed at the end, and each section names the source it follows. Where an idea comes from a specific author, the text says so.

## Why this matters for a fintech

Until now, your wallet kept every balance in one Postgres database. A transfer from Ana to Bruno was one `BEGIN ... COMMIT`, and Postgres made sure both entries were written or neither was. This week you split the wallet into two services, `accounts` and `payments`, each with its own database. The single transaction is gone.

The question every fintech interviewer asks next is: "How do you move money between two services without losing or creating any?" There are two families of answers. One tries to keep a single atomic transaction across machines (two-phase commit). The other accepts a sequence of local transactions and repairs failures with compensations (the saga). This lesson explains both and why payment systems almost always pick the second.

## 1. The atomic commitment problem

*Main source: Kleppmann's lecture notes, section 7.1.*

Start from what you already rely on. In an ACID transaction, atomicity means the transaction either commits, and all of its writes become durable, or aborts, and it leaves no visible side effects. Kleppmann points out that the "C" in ACID (keeping invariants true) depends on atomicity. "The sum of all balances is constant" holds only because a transfer never half-happens.

Now let the transaction touch data on two nodes. The debit lives in the `accounts` database for Ana, and the credit in another database for Bruno. To keep the invariant, Kleppmann's notes state the rule: either all nodes commit, or all abort, and if any node crashes, all must abort. This is the **atomic commitment problem**.

It looks like consensus (Module 9 covers it in depth), but the notes show it is stricter in one important way:

| | Consensus | Atomic commit |
| --- | --- | --- |
| Input | One or more nodes propose a value | Every node votes commit or abort |
| Decision | Any one of the proposed values | Commit only if all vote commit; abort if any votes abort |
| Crashed nodes | Tolerated while a quorum works | A crashed participant forces abort |

Consensus is happy with a majority. Atomic commit needs every participant, because every participant holds part of the data. That difference is why atomic commit is more fragile than a consensus cluster such as Raft, which you will meet in Module 9.

## 2. How two-phase commit works

*Main source: Kleppmann's lecture notes, section 7.1.*

Two-phase commit (2PC) is the classic algorithm for atomic commit. It adds one extra node, the **coordinator**. Using Kleppmann's diagram with our wallet:

1. The client sends `begin T1` to the coordinator. T1 then runs normally on node A (Ana's account) and node B (Bruno's account): reads, writes, row locks.
2. The client sends `commit T1` to the coordinator.
3. **Phase 1 (prepare).** The coordinator sends `prepare` to A and B. Each participant checks whether it can commit (constraints pass, data is safely on disk) and replies `ok` or `not ok`.
4. **Phase 2 (decision).** If every participant said `ok`, the coordinator decides commit. If any said `not ok`, or one didn't answer, it decides abort. It writes the decision to its own disk, then sends it to every participant.

The key promise is in phase 1. When a participant replies `ok`, it promises that it will be able to commit later, no matter what happens, even after a crash. That is why it must persist its prepared writes before voting. Postgres exposes this participant role directly:

```sql
-- on the accounts database (participant A)
BEGIN;
UPDATE accounts SET balance = balance - 100 WHERE id = 'ana';
PREPARE TRANSACTION 'transfer-7f3a';  -- vote "ok": durable, locks kept

-- later, when the coordinator decides
COMMIT PREPARED 'transfer-7f3a';      -- or ROLLBACK PREPARED 'transfer-7f3a'
```

`PREPARE TRANSACTION` is disabled by default (`max_prepared_transactions = 0`), and the Postgres documentation warns that it is meant for external transaction managers, not for application code. The fact that you have to turn it on is a hint about how rarely application teams use it.

## 3. Why 2PC blocks and holds locks

*Main source: Kleppmann's lecture notes, section 7.1.*

The coordinator writes its decision to disk. If it crashes and recovers, it reads the decision and sends it again. If it crashed before deciding, it aborts. So far, so good.

The problem Kleppmann highlights is the window in between: the coordinator crashes **after** sending `prepare` and **before** sending the decision. Each participant has voted `ok`. The notes say that such a participant "cannot commit or abort" on its own after responding `ok`. If A committed on its own, B might have voted `not ok`, and atomicity breaks. If A aborted on its own, the coordinator might have decided commit and told B. So the notes conclude that the algorithm "is blocked until coordinator recovers".

Think about what "blocked" means inside the participant's database. A prepared transaction has not committed, so it still holds its row locks. Ana's account row stays locked while the coordinator is down. Every other transfer that touches Ana's balance waits. With a coordinator that takes ten minutes to come back, your most active accounts freeze for ten minutes. In Postgres, a forgotten prepared transaction also keeps holding locks and stops `VACUUM` from cleaning old rows, which is another reason the feature is off by default.

Kleppmann's notes also show a **fault-tolerant 2PC**. Instead of sending votes only to the coordinator, each participant broadcasts its vote to all participants using total order broadcast (built on consensus). If a node suspects a participant crashed, it broadcasts a "not ok" vote on its behalf. Because everyone processes the votes in the same order, every node reaches the same decision without waiting for one coordinator. This removes the single point of blocking, at the cost of a consensus round for every transaction. Google's Spanner, also covered in the notes, uses 2PC across shards with Paxos-replicated participants, which is this idea at scale.

## 4. Why 2PC doesn't fit a wallet

*Main source: Richardson, "Pattern: Saga" and "Pattern: Transactional outbox", Forces sections.*

Richardson's saga page states the constraint in four words: "2PC is not an option." His outbox page gives part of the reason: the database or the message broker may not support it, and coupling a service to both is undesirable. For a payment system there are more reasons, and an interviewer will want to hear them:

- **External APIs have no prepare phase.** The step that matters most in a fintech is often a call to a partner bank, a card processor or a payment rail. Those are HTTP APIs. You can ask them to make a payment, ask its status, and sometimes refund it. You cannot ask them to "prepare and hold locks until I tell you". 2PC needs every participant to speak the protocol, and they don't.
- **Locks across the network.** Every participant holds locks for at least one network round trip, and for as long as the slowest participant or a crashed coordinator takes. Hot accounts (a merchant receiving thousands of payments) turn into a queue.
- **Availability multiplies down.** Atomic commit needs every participant. If each of three services is up 99.9% of the time, a transaction that needs all three is available roughly 99.7% of the time.
- **Coupling.** Services that join a 2PC share fate: a slow `accounts` database slows `payments`. Separate databases per service were chosen precisely to avoid this.

So the practical position is: use a local ACID transaction inside each service, and coordinate across services with a saga.

## 5. Sagas: local transactions plus compensations

*Main source: Richardson, "Pattern: Saga", Solution section.*

Richardson defines it in one sentence: "A saga is a reliably coordinated sequence of local transactions." Each step is a normal transaction in one service's database. When a step fails a business rule, the saga runs **compensating transactions** that semantically undo the steps already completed.

For the transfer from Ana to Bruno, in two services:

| Step | Service | Local transaction | Compensation |
| --- | --- | --- | --- |
| 1 | payments | Create transfer `PENDING` | Mark transfer `FAILED` |
| 2 | accounts | Debit Ana 100 (new ledger entry) | Credit Ana 100 (reversal entry) |
| 3 | accounts | Credit Bruno 100 (new ledger entry) | (none: last step that can fail) |
| 4 | payments | Mark transfer `COMPLETED` | (none) |

Three things in that table matter for the capstone:

- **A compensation is a new transaction, not a rollback.** The debit of step 2 already committed, and other sagas may already have read Ana's new balance. You can't erase it. You write a reversal entry that credits Ana back. A ledger never deletes or updates past entries, so the reversal is the only honest record of what happened.
- **A compensation must not fail for business reasons.** You can always give Ana her money back. If a compensation can fail, it must be retried until it succeeds, so it has to be idempotent.
- **Order matters.** Put the step most likely to fail early, and put steps that can't be undone (a call to a partner bank) as late as possible. Tuesday's lesson names this ordering: the pivot transaction.

Richardson lists the benefit simply: consistency across services without distributed transactions. He is just as direct about the cost: there is no automatic rollback, and developers must design compensations.

## 6. Choreography versus orchestration

*Main source: Richardson, "Pattern: Saga", examples for both styles.*

Richardson describes two ways to coordinate the steps.

**Choreography.** No one is in charge. Each service does its local transaction and publishes an event, and other services react to events. In Richardson's example, the Order Service creates a `PENDING` order and emits an event, the Customer Service reserves credit and emits the outcome, and the Order Service approves or rejects the order. In the wallet: `payments` emits `TransferRequested`, `accounts` debits and emits `AccountDebited`, then credits and emits `AccountCredited`, and `payments` marks the transfer complete.

**Orchestration.** One component, the orchestrator, tells participants what to do with commands and reacts to their replies. In Richardson's example, a Create Order saga orchestrator sends a `Reserve Credit` command to the Customer Service and approves or rejects the order based on the reply. In the wallet, the orchestrator lives in `payments`: it calls `accounts` to debit Ana, then to credit Bruno, and finally completes the transfer.

| | Choreography | Orchestration |
| --- | --- | --- |
| Where the flow lives | Spread across event handlers | In one place, the orchestrator |
| Adding a step | Touch several services | Change the orchestrator |
| Seeing a saga's state | Rebuild it from events | Read one row |
| Risk | Cyclic dependencies, hard to debug | Orchestrator holds too much logic |
| Fits | Few steps, few teams | Money flows with compensations and timeouts |

For money, most teams choose orchestration. The state of each transfer is in one row you can query, alert on and resume. Richardson notes that his book's example application also uses orchestration. The capstone does the same: a `sagas` table in `payments`, with the state machine in the orchestrator.

Here is what the orchestrator's persisted state looks like in Postgres:

```sql
CREATE TABLE sagas (
  id         uuid PRIMARY KEY,
  state      text NOT NULL,       -- STARTED, DEBITED, CREDITED, COMPENSATING, COMPLETED, FAILED
  step       int  NOT NULL DEFAULT 0,
  attempts   int  NOT NULL DEFAULT 0,
  deadline   timestamptz NOT NULL, -- when the current step times out
  payload    jsonb NOT NULL,       -- from, to, amount, currency
  updated_at timestamptz NOT NULL DEFAULT now()
);
```

Treat this as a sketch to reason with, not as the capstone answer: on Thursday you design your own table and state names without help.

The orchestrator must write its state **before** acting on it. If it crashes after calling `accounts` but before saving `DEBITED`, a recovery worker will call `accounts` again on restart. That is safe only if the debit is idempotent, keyed by `saga_id` plus step (Module 2 again).

## 7. What a saga leaves you to solve

*Main source: Richardson, "Pattern: Saga", Resulting context.*

Richardson's "Resulting context" lists the problems you inherit. Each one maps to a later part of this week.

- **No isolation.** Between step 2 and step 3, Ana's debit is committed and visible, but the transfer isn't finished. Another saga can read that intermediate state. Richardson says concurrent sagas can cause data anomalies and need countermeasures. That is Tuesday's first topic.
- **Update the database and send a message atomically.** A step that writes to its database and then publishes an event can crash in between. Richardson points to the Transactional Outbox (or Event Sourcing) as the fix. That is Tuesday's second topic.
- **The client needs the outcome.** A saga takes longer than one HTTP request. Richardson lists three options: the API waits for completion, the client polls a status endpoint, or the service pushes a notification such as a webhook. For a wallet, the usual answer is `202 Accepted` with a transfer ID, plus `GET /transfers/:id`.
- **Crashes in the middle.** The orchestrator itself can die at any point. Its state must be durable, and something must resume unfinished sagas. That is the recovery worker of the capstone, and Wednesday's durable workflow engines solve the same problem as a product.

**Today's lab** sets the stage. Run `accounts` and `payments` in Docker Compose, each with its own Postgres, talking over HTTP. Then kill one container in the middle of a transfer and look at both databases. You will see the half-done state that the rest of this week teaches you to handle.

## Notes to write today

1. How 2PC works, in five lines: begin, prepare, vote, decision written to disk, decision sent.
2. Why a participant that voted `ok` keeps its locks, and what that does to a hot account when the coordinator is down.
3. Three reasons 2PC doesn't work across a wallet and a partner bank (start with: external APIs have no prepare phase).
4. Choreography versus orchestration: one sentence each, plus why you'd pick orchestration for a transfer.
5. The compensation table for the Ana-to-Bruno transfer, and why the compensation of a debit is a reversal entry and never a delete.

## Check yourself

These make good flashcards (see the [flashcards guide](../../FLASHCARDS.md)).

- What is the atomic commitment problem, and how does it differ from consensus?
- In 2PC, why can't a participant that voted `ok` decide on its own when the coordinator disappears?
- Why can't you include a partner bank's HTTP API in a 2PC transaction?
- What is a saga, in Richardson's one-sentence definition?
- Why is a compensation a new transaction and not a rollback?
- Name one advantage of orchestration over choreography for a money transfer.
- Which three problems does a saga leave you to solve?

## References

- **Main source:** Martin Kleppmann, ["Distributed Systems" lecture notes](https://www.cl.cam.ac.uk/teaching/2122/ConcDisSys/dist-sys-notes.pdf), University of Cambridge, 2021/22, section 7.1 (Two-phase commit). Free, Creative Commons BY-SA. The same slides are in the [printable handout](https://www.cl.cam.ac.uk/teaching/2122/ConcDisSys/dist-sys-handout.pdf), and the lecture videos are linked from the [course materials page](https://www.cl.cam.ac.uk/teaching/2122/ConcDisSys/materials.html).
- **Main source:** Chris Richardson, microservices.io, ["Pattern: Saga"](https://microservices.io/patterns/data/saga.html). Read the whole page, including both examples and "Resulting context". Free.
- PostgreSQL documentation, ["PREPARE TRANSACTION"](https://www.postgresql.org/docs/current/sql-prepare-transaction.html). Optional: shows the participant side of 2PC in Postgres and its warnings. Free.
