# Module 4, Monday: two-phase commit and why sagas exist

[Module 4](../../modules/04-sagas-outbox.md) · [Leia em português](day-1.pt-BR.md)

**Reading time:** about 45 minutes. Use the rest of the 2-hour block on the references at the end, starting with the sections marked as the main source.

This is an original text written for this course. It is based on the references listed at the end, and each section names the source it follows. Where an idea comes from a specific author, the text says so.

## Why this matters for a fintech

Until now, your wallet kept every balance in one Postgres database. A transfer from Ana to Bruno was one `BEGIN ... COMMIT`, and Postgres made sure both entries were written or neither was. This week you split the wallet into two services, `accounts` and `payments`, each with its own database. The single transaction is gone.

The question every fintech interviewer asks next is: "How do you move money between two services without losing or creating any?" There are two families of answers. One tries to keep a single atomic transaction across machines (two-phase commit). The other accepts a sequence of local transactions and repairs failures with compensations (the saga). This lesson explains both, using the commands Postgres really ships and the patterns AWS, Azure and Cockroach Labs document, and shows why payment systems almost always pick the second.

## 1. The atomic commitment problem

*Main sources: Cockroach Labs blog, "Parallel Commits"; AWS Prescriptive Guidance, "Saga orchestration pattern".*

Start from what you already rely on. The Cockroach Labs article on parallel commits sums up atomicity in a phrase: a transaction is "all or nothing". It either commits, and all of its writes become durable, or it rolls back and leaves nothing behind. The invariant "the sum of all balances is constant" holds only because a transfer never half-happens.

Now let the transaction touch data on two machines. The debit lives in the `accounts` database for Ana, and the credit in another database for Bruno. To keep the invariant, both databases must commit or both must abort, and a crash of either one in the middle must not leave the debit without the credit. That is the **atomic commitment problem**.

The AWS guide on saga orchestration explains why this is hard in a microservices setup: with a database per service, "there is no single controller" that can coordinate the commit the way one database coordinates its own transactions. You need a protocol that coordinates several independent databases. The classic one is two-phase commit.

Keep one point for Module 9: a consensus cluster (Raft, etcd) works while a majority is up, but atomic commit needs every participant, because each holds part of the data. One participant that says no, or never answers, forces an abort.

## 2. How two-phase commit works

*Main sources: AWS Prescriptive Guidance, "Saga orchestration pattern"; PostgreSQL documentation, "Two-Phase Transactions" and "PREPARE TRANSACTION".*

Two-phase commit (2PC) adds one extra role, the **coordinator**. The AWS guide describes the two phases in two sentences. In the prepare phase, the coordinator asks the participants "to promise to either commit or roll back the transaction". In the commit phase, it asks them to commit; if any participant could not agree in the prepare phase, the transaction is rolled back.

With our wallet:

1. The client asks the coordinator to start transfer T1. T1 runs normally on database A (Ana's account) and database B (Bruno's account): reads, writes, row locks.
2. The client asks the coordinator to commit T1.
3. **Phase 1 (prepare).** The coordinator tells A and B to prepare. Each participant checks whether it can commit (constraints pass, data is safely on disk) and replies yes or no.
4. **Phase 2 (decision).** If every participant said yes, the coordinator decides commit. If any said no, or one didn't answer, it decides abort. It records the decision, then sends it to every participant.

The key promise is in phase 1. A participant that votes yes promises it will be able to commit later, even after a crash. Postgres exposes this participant role directly. Its documentation says Postgres supports 2PC through three commands, `PREPARE TRANSACTION`, `COMMIT PREPARED` and `ROLLBACK PREPARED`, and follows the model of the X/Open XA standard:

```sql
-- on the accounts database (participant A)
BEGIN;
UPDATE accounts SET balance = balance - 100 WHERE id = 'ana';
PREPARE TRANSACTION 'transfer-7f3a';  -- vote "yes": state saved on disk, locks kept

-- later, when the coordinator decides (from any session)
COMMIT PREPARED 'transfer-7f3a';      -- or ROLLBACK PREPARED 'transfer-7f3a'
```

The `PREPARE TRANSACTION` page makes the promise concrete. After the command, the transaction is detached from your session and its state is "fully stored on disk", so it can very probably still be committed after a crash. Your session sees no current transaction, and the effects stay invisible until someone runs `COMMIT PREPARED`, which can come from any session: that is what lets an external coordinator finish the job. The identifier is a string literal under 200 bytes; deriving it from the transfer ID makes recovery easier. The "Two-Phase Transactions" page adds that the only possible next commands are `COMMIT PREPARED` or `ROLLBACK PREPARED`.

## 3. Why 2PC blocks and holds locks

*Main sources: PostgreSQL documentation, "PREPARE TRANSACTION" and "Two-Phase Transactions"; Nathan VanBenschoten, "Parallel Commits" (Cockroach Labs blog).*

If the coordinator crashes and recovers, it reads its recorded decision and sends it again. The dangerous window is in between: the coordinator crashes **after** the participants voted yes and **before** they hear the decision.

The Cockroach Labs article names this the most cited problem of 2PC: it is "blocking". After the participants vote to commit, the system "enters a fragile state", and if the coordinator crashed, it would be impossible for the others to know the final outcome. Think about what a participant can do. If A commits on its own, B might have voted no, and atomicity breaks. If A aborts on its own, the coordinator might have decided commit and told B. So A waits.

What does waiting mean inside Postgres? The `PREPARE TRANSACTION` page is explicit: a prepared transaction "continues to hold whatever locks it held". Ana's account row stays locked while the coordinator is down. Every other transfer that touches Ana's balance waits. With a coordinator that takes ten minutes to come back, your most active accounts freeze for ten minutes.

The same page lists the other costs of leaving transactions prepared for a long time: it interferes with `VACUUM`, and in extreme cases could force the database to shut down to prevent transaction ID wraparound. That is why the docs recommend keeping the feature disabled, with `max_prepared_transactions` set to zero, unless you need it: it prevents prepared transactions that get forgotten. You can see any leftovers with a simple query:

```sql
SELECT gid, prepared, owner, database
FROM pg_prepared_xacts
ORDER BY prepared;  -- oldest first: these are the ones holding locks longest
```

The docs are just as clear about who should use it: `PREPARE TRANSACTION` "is not intended for use in applications or interactive sessions". It exists for external transaction managers. The "Two-Phase Transactions" page adds that the prepared state is meant to be very short, but external availability problems can stretch it.

**How a database that does use 2PC avoids blocking.** In CockroachDB, writing provisional values (write intents) plays the role of the prepare phase, and marking a transaction record as committed is the commit phase. That record is replicated through consensus like the data, so the decision survives a crash, and any transaction that hits an intent looks up the record to learn the outcome. The price is latency: layering 2PC on consensus "requires two sequential rounds of consensus writes", which the Parallel Commits protocol cuts to one. The lesson: safe 2PC needs a consensus system underneath, something you buy in a database, not something you build between two NestJS services.

## 4. Why 2PC doesn't fit a wallet

*Main sources: Chris Richardson, "Pattern: Saga" (microservices.io), Forces section; AWS Prescriptive Guidance, "Saga orchestration pattern", Applicability.*

Richardson's saga page states the constraint in four words: "2PC is not an option." The AWS guide recommends sagas when the data store does not provide 2PC or implementing it in the application is complex. For a payment system there are more reasons, and an interviewer will want to hear them:

- **External APIs have no prepare phase.** The step that matters most in a fintech is often a call to a partner bank, a card processor or a payment rail. Those are HTTP APIs. You can ask them to make a payment, ask its status, and sometimes refund it. You cannot ask them to "prepare and hold locks until I tell you". 2PC needs every participant to speak the protocol, and they don't.
- **Locks across the network.** As section 3 showed, every participant holds locks from prepare until the decision arrives, which is at least one network round trip and as long as a crashed coordinator takes to recover. Hot accounts (a merchant receiving thousands of payments) turn into a queue.
- **Availability multiplies down.** Atomic commit needs every participant. If each of three services is up 99.9% of the time, a transaction that needs all three is available roughly 99.7% of the time.
- **Coupling.** Services that join a 2PC share fate: a slow `accounts` database slows `payments`. Separate databases per service were chosen precisely to avoid this.

So the practical position is: use a local ACID transaction inside each service, and coordinate across services with a saga.

## 5. Sagas: local transactions plus compensations

*Main sources: Chris Richardson, "Pattern: Saga", Solution section; Azure Architecture Center, "Saga distributed transactions pattern".*

Richardson defines it in one sentence: "A saga is a reliably coordinated sequence of local transactions." Each step is a normal transaction in one service's database. When a step fails a business rule, the saga runs **compensating transactions** that semantically undo the steps already completed.

The Azure Architecture Center page adds a vocabulary that fits money flows well. It splits a saga's steps into three kinds:

- **Compensable** steps can be undone by another transaction with the opposite effect.
- The **pivot** step is "the point of no return". Once it succeeds, compensation no longer applies, and every remaining step must complete.
- **Retryable** steps come after the pivot. They are idempotent, so they can be retried until the saga reaches its final state.

For the transfer from Ana to Bruno, in two services:

| Step | Service | Local transaction | Compensation | Kind |
| --- | --- | --- | --- | --- |
| 1 | payments | Create transfer `PENDING` | Mark transfer `FAILED` | compensable |
| 2 | accounts | Debit Ana 100 (new ledger entry) | Credit Ana 100 (reversal entry) | compensable |
| 3 | accounts | Credit Bruno 100 (new ledger entry) | (none: last step that can fail) | pivot |
| 4 | payments | Mark transfer `COMPLETED` | (none) | retryable |

Three things in that table matter for the capstone:

- **A compensation is a new transaction, not a rollback.** The debit of step 2 already committed, and other sagas may already have read Ana's new balance. You can't erase it. You write a reversal entry that credits Ana back. A ledger never deletes or updates past entries, so the reversal is the only honest record of what happened.
- **A compensation must not fail for business reasons.** You can always give Ana her money back. If a compensation can fail for technical reasons, it must be retried until it succeeds, so it has to be idempotent.
- **Order matters.** Put the step most likely to fail early, and put steps that can't be undone (a call to a partner bank) as late as possible, at or after the pivot. Tuesday's lesson comes back to this ordering.

Richardson lists the benefit simply: data consistency across services "without using distributed transactions". He is just as direct about the costs: there is no automatic rollback, so developers must design compensations, and there is no isolation between concurrent sagas.

## 6. Choreography versus orchestration

*Main sources: Chris Richardson, "Pattern: Saga", examples for both styles; Azure Architecture Center, "Saga distributed transactions pattern"; AWS Prescriptive Guidance, "Saga orchestration pattern", example.*

There are two ways to coordinate the steps.

**Choreography.** No one is in charge. Each service does its local transaction and publishes an event, and other services react to events. In Richardson's example, the Order Service creates a `PENDING` order and emits an event, the Customer Service reserves credit and emits the outcome, and the Order Service approves or rejects the order. In the wallet: `payments` emits `TransferRequested`, `accounts` debits and emits `AccountDebited`, then credits and emits `AccountCredited`, and `payments` marks the transfer complete.

**Orchestration.** One component, the orchestrator, tells participants what to do with commands and reacts to their replies. The AWS guide has a concrete version: an AWS Step Functions workflow that runs Place Order, Update Inventory and Make Payment, and on failure runs Revert Payment, Revert Inventory and Remove Order. In the wallet, the orchestrator lives in `payments`: it calls `accounts` to debit Ana, then to credit Bruno, and finally completes the transfer.

The Azure page lists the trade-offs, and they line up with what you will feel in the capstone:

| | Choreography | Orchestration |
| --- | --- | --- |
| Good for | Simple flows with few services | Complex flows, or when you add services |
| Coordination | No extra service, no single point of failure | The orchestrator is a point of failure |
| Main risk | Cyclic dependencies; hard to track who reacts to what | Coordination logic to design and maintain |
| Testing | All services must run to simulate a transaction | Flow lives in one place |

For money, most teams choose orchestration: the state of each transfer is in one row you can query, alert on and resume. Richardson's book example also uses orchestration. The AWS guide notes that Step Functions reduces the single-point-of-failure risk with built-in fault tolerance; in the capstone you get a similar effect by persisting the orchestrator's state in Postgres.

Here is what the orchestrator's persisted state might look like:

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

The orchestrator must write its state **before** acting on it. If it crashes after calling `accounts` but before saving `DEBITED`, a recovery worker will call `accounts` again on restart. That is safe only if the debit is idempotent, keyed by `saga_id` plus step (Module 2 again). The AWS guide agrees: participants must be idempotent to survive crashes and orchestrator failures.

## 7. What a saga leaves you to solve

*Main sources: Chris Richardson, "Pattern: Saga", Resulting context; AWS Prescriptive Guidance, "Saga orchestration pattern", Issues and considerations.*

Richardson's "Resulting context" lists the problems you inherit, and each maps to a later part of this week.

- **No isolation.** Between step 2 and step 3, Ana's debit is committed and visible, but the transfer isn't finished. Another saga can read that intermediate state. Richardson says concurrent sagas can cause data anomalies; the AWS guide recommends semantic locking. That is Tuesday's first topic.
- **Update the database and send a message atomically.** A step that writes to its database and then publishes an event can crash in between. Richardson points to the Transactional Outbox as the fix. That is Tuesday's second topic.
- **The client needs the outcome.** A saga takes longer than one HTTP request. Richardson lists three options: the service answers once the saga completes, the service answers right away with an ID and the client polls, or the service pushes an event such as a webhook when the saga completes. For a wallet, the usual answer is `202 Accepted` with a transfer ID, plus `GET /transfers/:id`.
- **Crashes in the middle.** The orchestrator itself can die at any point. Its state must be durable, and something must resume unfinished sagas. That is the recovery worker of the capstone, and Wednesday's durable workflow engines solve the same problem as a product.

**Today's lab** sets the stage. Run `accounts` and `payments` in Docker Compose, each with its own Postgres, talking over HTTP. Then kill one container in the middle of a transfer and look at both databases. You will see the half-done state that the rest of this week teaches you to handle.

## Notes to write today

1. How 2PC works, in five lines: begin, prepare, vote, decision recorded, decision sent. Add the three Postgres commands that implement the participant side.
2. Why a participant that voted yes keeps its locks, and what that does to a hot account when the coordinator is down. Include the `pg_prepared_xacts` query you would run during an incident.
3. Three reasons 2PC doesn't work across a wallet and a partner bank (start with: external APIs have no prepare phase).
4. Choreography versus orchestration: one sentence each, plus why you'd pick orchestration for a transfer.
5. The compensation table for the Ana-to-Bruno transfer, with the compensable, pivot and retryable steps marked, and why the compensation of a debit is a reversal entry and never a delete.

## Check yourself

These make good flashcards (see the [flashcards guide](../../FLASHCARDS.md)).

- What is the atomic commitment problem, and why does it need every participant while consensus only needs a majority?
- In 2PC, why can't a participant that voted yes decide on its own when the coordinator disappears?
- What does `PREPARE TRANSACTION` do to the session, to the locks and to `VACUUM`?
- Why can't you include a partner bank's HTTP API in a 2PC transaction?
- What is a saga, in Richardson's one-sentence definition?
- What is a pivot transaction, and where should the call to a partner bank go relative to it?
- Why is a compensation a new transaction and not a rollback?
- Name one advantage of orchestration over choreography for a money transfer.

## References

- **Main source:** Chris Richardson, microservices.io, ["Pattern: Saga"](https://microservices.io/patterns/data/saga.html). Read the whole page, including both examples and "Resulting context". Free.
- **Main source:** PostgreSQL documentation, ["PREPARE TRANSACTION"](https://www.postgresql.org/docs/current/sql-prepare-transaction.html). Read the Description, Notes and the Caution box: it is the participant side of 2PC, with the real warnings about locks and `VACUUM`. Free.
- PostgreSQL documentation, ["Two-Phase Transactions"](https://www.postgresql.org/docs/current/two-phase.html). Two paragraphs: the three commands, the XA model, and why the prepared state should be short. Free.
- Nathan VanBenschoten, ["Parallel Commits: An atomic commit protocol for globally distributed transactions"](https://www.cockroachlabs.com/blog/parallel-commits/), Cockroach Labs blog, 2019. Read the parts on atomic commit, two-phase commit and blocking; skim the protocol details. Free.
- AWS Prescriptive Guidance, ["Saga orchestration pattern"](https://docs.aws.amazon.com/prescriptive-guidance/latest/cloud-design-patterns/saga-orchestration.html). Read the 2PC description, "Applicability", "Issues and considerations" and the Step Functions example. Free.
- Azure Architecture Center, ["Saga distributed transactions pattern"](https://learn.microsoft.com/en-us/azure/architecture/patterns/saga). Read the transaction types (compensable, pivot, retryable) and the choreography and orchestration trade-offs. Free.
