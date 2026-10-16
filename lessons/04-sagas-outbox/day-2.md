# Module 4, Tuesday: saga isolation, balance holds and the transactional outbox

[Module 4](../../modules/04-sagas-outbox.md) · [Leia em português](day-2.pt-BR.md)

**Reading time:** about 45 minutes. Use the rest of the 2-hour block on the references at the end. Chapter 4 of "Microservices Patterns" is a paid book; if you don't have it, spend the time on the outbox pages and the Debezium architecture page.

This is an original text written for this course. It is based on the references listed at the end, and each section names the source it follows. Where an idea comes from a specific author, the text says so.

## Why this matters for a fintech

Monday ended with two problems a saga leaves open. First, a saga has no isolation: its intermediate steps are committed and visible to everyone. In a wallet, that means another request can see money that is "on its way" and spend it twice. Second, each step must update its database and tell the next participant, and a crash between those two actions loses the message or sends one for a change that never committed.

Both problems produce the same symptom in production: balances that don't add up and transfers stuck halfway. Today you learn the standard answers: countermeasures for isolation (with balance holds as the fintech version), and the transactional outbox for reliable messaging.

## 1. Sagas are ACD, not ACID

*Main source: Richardson, "Microservices Patterns", chapter 4, "Handling the lack of isolation". The book is paid; this section describes its well-known concepts, and the full treatment is in the book.*

Richardson describes a saga as having atomicity (all steps run, or compensations undo them), consistency (each service keeps its own invariants) and durability (each step commits), but not isolation. Each local transaction commits as soon as it finishes, so other sagas and plain requests see its effects before the saga is done.

The book groups the resulting problems into three anomalies. Here they are with wallet examples:

| Anomaly | What happens | Wallet example |
| --- | --- | --- |
| Lost update | One saga overwrites a change made by another without reading it | A refund saga sets a transfer to `REFUNDED` while the original saga, still running, sets it back to `COMPLETED` |
| Dirty read | A saga reads data another saga hasn't finished, then that saga compensates | A limit check sees Ana's balance after a credit that is later reversed, and approves a withdrawal she can't cover |
| Fuzzy (nonrepeatable) read | Two steps of one saga read the same data and get different values | Step 1 reads Ana's daily limit usage, another transfer completes, step 3 reads a different number |

The point to remember: these anomalies are not database bugs. Each local transaction is fully isolated by Postgres. The anomalies come from the gaps **between** local transactions, which no database can see.

## 2. Countermeasures, and the structure of a saga

*Main source: Richardson, "Microservices Patterns", chapter 4. Details and code are in the book.*

Richardson classifies saga steps into three kinds. This classification decides where countermeasures go:

- **Compensatable transactions** can be undone by a compensation. Debiting Ana inside your own ledger is compensatable: a reversal entry undoes it.
- The **pivot transaction** is the go/no-go point. If it commits, the saga will run to completion. It is either the last compensatable step or the first step that can't be undone. In a payout, the call that tells the partner bank to send the money is the pivot: after it succeeds, you can't take the money back.
- **Retriable transactions** come after the pivot. They are guaranteed to succeed eventually, so they are retried until they do. Marking the transfer `COMPLETED` and crediting Bruno inside your own ledger after a confirmed payout are retriable.

The book then lists countermeasures. The ones most useful for a wallet are:

- **Semantic lock.** A compensatable step sets a flag that says "this record is in the middle of a saga", such as a transfer in state `PENDING` or a debit marked as held. Other requests check the flag and either refuse, wait or treat the record differently. The flag is cleared by the retriable step or by the compensation. It is an application-level lock, so it survives across local transactions.
- **Commutative updates.** Design updates so their order doesn't matter. Appending ledger entries (`+100`, `-30`) is commutative; setting `balance = 70` is not. A compensation that appends a reversal entry commutes with other sagas' entries, so no update is lost.
- **Reordering steps (pessimistic view).** Arrange the steps to reduce the risk of a dirty read. For example, debit the payer before crediting the payee, so that no one can ever spend money that might be reversed later. A credit that must be compensated is dangerous because Bruno may already have spent it; a debit that must be compensated only gives Ana her own money back.
- **Reread value.** Before overwriting a record, a step rereads it and checks it hasn't changed since the saga last read it (optimistic locking, often with a `version` column). If it changed, the saga aborts or restarts.

The book describes more (version file, by value), and explains how to choose among them. For the capstone, the combination you need is: debit first (reordering), append-only entries (commutative updates) and a `PENDING` state that other code respects (semantic lock).

## 3. Balance holds and TCC

*Main source: Richardson, "Microservices Patterns", chapter 4, for the semantic lock idea. TCC is a related pattern from industry practice, described here in general terms.*

A wallet has one isolation problem above all others: two transfers from Ana at the same time must not both spend the same 100. The fintech form of a semantic lock is the **balance hold** (also called an authorization or reservation). Card networks have used it for decades: the authorization holds the money, and the capture moves it later.

A hold splits the balance into two numbers:

- **Ledger balance:** the sum of posted entries.
- **Available balance:** ledger balance minus active holds.

The saga's first step against `accounts` places a hold. It succeeds only if the available balance is enough, and the check and the insert happen in one local transaction:

```sql
BEGIN;
SELECT id FROM accounts WHERE id = 'ana' FOR UPDATE;  -- serialize holds per account
INSERT INTO holds (id, account_id, amount, saga_id, status, expires_at)
SELECT gen_random_uuid(), 'ana', 100, $1, 'ACTIVE', now() + interval '5 minutes'
WHERE (SELECT balance FROM accounts WHERE id = 'ana')
    - (SELECT coalesce(sum(amount), 0) FROM holds
       WHERE account_id = 'ana' AND status = 'ACTIVE') >= 100
ON CONFLICT (saga_id) DO NOTHING;     -- idempotent per saga (unique index on saga_id)
COMMIT;
```

The hold then ends in one of two ways. **Capture** turns it into a posted debit entry and closes the hold, in one local transaction. **Release** closes the hold without posting anything. That is the compensation, and it is trivially safe because no money moved.

This three-step shape has a name: **TCC (Try, Confirm, Cancel)**. Try reserves the resource (the hold), Confirm makes it final (the capture), Cancel releases it. Every participant must offer all three operations, and Confirm and Cancel must be idempotent because the orchestrator will retry them. Holds also need an expiry. If the orchestrator dies for good, a sweeper releases holds past `expires_at`, so a crashed saga can't freeze a customer's money forever.

Compare this with 2PC from Monday. A hold looks like "prepare", but it is a committed, visible business record with an expiry, not a database lock held open across the network. Other transfers keep running against the available balance.

## 4. The dual-write problem and the transactional outbox

*Main source: Richardson, microservices.io, "Pattern: Transactional outbox".*

Every saga step does two things: change its own data and tell someone. The orchestrator saves `DEBITED` and must send the credit command. `accounts` posts an entry and must publish `AccountDebited`. Richardson's outbox page states the problem as a question: how do you atomically update the database and send messages to a broker?

Look at the two naive orders:

- **Commit, then publish.** The service crashes after `COMMIT` and before publishing. The data changed, and nobody hears about it. The saga is stuck.
- **Publish, then commit.** The message goes out, then the transaction rolls back (a constraint fails, or the process dies). Consumers act on a change that never happened.

Richardson's forces add a third requirement: messages must be sent in the order the service produced them, even with several instances updating the same aggregate.

His solution: the service inserts each message into an **outbox table** in the **same local transaction** that changes the business data. A separate **message relay** reads the outbox and publishes to the broker. Either both the entry and the message commit, or neither does.

```sql
CREATE TABLE outbox (
  id           bigserial PRIMARY KEY,
  aggregate_id text  NOT NULL,          -- e.g. account id, used for ordering
  type         text  NOT NULL,          -- 'AccountDebited'
  payload      jsonb NOT NULL,
  created_at   timestamptz NOT NULL DEFAULT now(),
  published_at timestamptz
);

BEGIN;
INSERT INTO ledger_entries (account_id, amount, saga_id, step) VALUES ('ana', -100, $1, 2);
INSERT INTO outbox (aggregate_id, type, payload)
VALUES ('ana', 'AccountDebited', jsonb_build_object('sagaId', $1, 'amount', 100));
COMMIT;
```

Richardson lists the benefits: no 2PC, messages are sent only if the transaction commits, and they go out in the order the application produced them. He also states the catch: the relay can publish a message more than once, for example if it crashes after publishing and before marking it as published. Consumers must therefore be idempotent, typically by recording the IDs of messages they already processed. He adds that this is usually fine, since consumers need idempotency anyway. In your wallet, the idempotency key from Module 2 (`saga_id` plus step) is exactly that.

## 5. Polling publisher with SKIP LOCKED

*Main source: Richardson, microservices.io, "Pattern: Polling publisher". PostgreSQL documentation, "SELECT", The Locking Clause.*

The outbox page links two ways to build the relay. The first is the **polling publisher**: a loop that queries the outbox for unpublished rows and publishes them. Richardson's listed benefit is that it works with any SQL database. His drawbacks: publishing in the right order is tricky, and not all NoSQL databases support it.

With several relay instances, you need them not to grab the same rows. Postgres has `FOR UPDATE SKIP LOCKED` for this. The Postgres documentation says skipping locked rows "provides an inconsistent view of the data", so it is not for general work, but it can be used to avoid lock contention when multiple consumers read a queue-like table. An outbox is exactly that.

```typescript
// One batch of the relay. Runs in a loop with a short sleep when the batch is empty.
async function relayBatch(ds: DataSource, publish: (m: OutboxRow) => Promise<void>) {
  await ds.transaction(async (tx) => {
    const rows: OutboxRow[] = await tx.query(
      `SELECT id, aggregate_id, type, payload FROM outbox
        WHERE published_at IS NULL
        ORDER BY id
        LIMIT 100
        FOR UPDATE SKIP LOCKED`,
    );
    for (const row of rows) {
      await publish(row); // may succeed and then the tx may fail: at-least-once
    }
    if (rows.length > 0) {
      await tx.query(`UPDATE outbox SET published_at = now() WHERE id = ANY($1)`, [
        rows.map((r) => r.id),
      ]);
    }
  });
}
```

Three details to understand before the lab:

- **At-least-once.** If the process dies after `publish` and before `COMMIT`, the rows stay unpublished and go out again. That is the duplicate Richardson warns about.
- **Ordering versus parallelism.** With two relays and `SKIP LOCKED`, relay 1 may take rows 1 to 100 and relay 2 rows 101 to 200, and relay 2 may publish first. If order matters per account, use one relay, or partition the work by `aggregate_id` so all rows for one account go through one relay.
- **Cleanup.** The outbox grows forever unless you delete or archive published rows. Do it in a separate job, not in the hot path.

In today's lab, the relay writes to a log (a file or a `published_messages` table) instead of Kafka, which arrives in Module 5. The shape of the code doesn't change.

## 6. Transaction log tailing and Debezium

*Main source: Richardson, microservices.io, "Pattern: Transaction log tailing". Debezium documentation, "Debezium Architecture".*

The second relay option is **transaction log tailing**. Richardson's solution is to tail the database transaction log and publish each message inserted into the outbox. Every database already writes every committed change to a log: the binlog in MySQL, the write-ahead log (WAL) in Postgres, streams in DynamoDB, all named on his page. Reading that log means no polling queries and no `published_at` column to update.

Richardson's listed benefits are no 2PC and accuracy (the log contains exactly what committed, in commit order). His drawbacks: it is relatively obscure, it needs database-specific solutions, and it is tricky to avoid duplicate publishing.

**Debezium** is the best-known open-source tool for this, and its architecture page explains how it is deployed. Debezium is a change data capture (CDC) tool: it captures row-level changes in a database and publishes them as change events. The most common deployment runs Debezium **source connectors** inside **Kafka Connect**, a separate service next to the Kafka brokers. The page says that by default, changes from one table go to a Kafka topic named after that table. Topic routing can change that mapping. Two other deployments exist: **Debezium Server**, a standalone application that sends events to other systems such as Amazon Kinesis or Google Cloud Pub/Sub, and the **Debezium Engine**, a Java library embedded in your own application.

How it reads the log depends on the database. The architecture page says the MySQL connector reads the binlog, and the PostgreSQL connector reads from a logical replication stream. In Postgres terms, that is logical decoding of the WAL through a replication slot, the same machinery you met with replication in Module 1. A replication slot keeps WAL until the consumer confirms it, so a stopped Debezium makes WAL pile up on the primary disk. Monitor it.

| | Polling publisher | Log tailing (Debezium) |
| --- | --- | --- |
| Works with | Any SQL database | Databases with a readable change log |
| Extra load | Queries every few hundred ms | Reads the log stream |
| Latency | Poll interval | Close to commit time |
| Ordering | You must design it | Commit order from the log |
| Operations | A loop in your service | Kafka Connect, slots, connector config |
| Duplicates | Yes, consumers dedupe | Yes, consumers dedupe |

For the capstone, the polling publisher is enough and far simpler. Mention log tailing in interviews as the option you would choose at higher volume or when you can't add polling load to the primary.

## Notes to write today

1. The three saga anomalies (lost update, dirty read, fuzzy read) with one wallet example each.
2. Compensatable, pivot and retriable steps. Name the pivot in a payout to a partner bank.
3. Semantic lock, commutative updates and reordering: one sentence each and where each appears in the transfer saga.
4. How a balance hold works as TCC (try, confirm, cancel), and why it needs an expiry.
5. The two failure orders of the dual write (commit then publish, publish then commit), and how the outbox fixes both.
6. Polling publisher versus transaction log tailing: one advantage and one drawback each, and why the consumer must be idempotent in both.

## Check yourself

These make good flashcards (see the [flashcards guide](../../FLASHCARDS.md)).

- Which letter of ACID does a saga lack, and why can't Postgres provide it across services?
- What is the pivot transaction of a saga?
- Why is debiting before crediting a countermeasure?
- What is the difference between ledger balance and available balance?
- Why must the outbox insert be in the same transaction as the business write?
- Why does a polling publisher deliver at least once rather than exactly once?
- How does Debezium read changes from Postgres?

## References

- **Main source:** Chris Richardson, ["Microservices Patterns"](https://www.manning.com/books/microservices-patterns), Manning, chapter 4 ("Managing transactions with sagas"), especially "Handling the lack of isolation". Paid book. No free source covers the countermeasures as well.
- **Main source:** Chris Richardson, microservices.io, ["Pattern: Transactional outbox"](https://microservices.io/patterns/data/transactional-outbox.html), plus the two relay options linked from it: ["Pattern: Polling publisher"](https://microservices.io/patterns/data/polling-publisher.html) and ["Pattern: Transaction log tailing"](https://microservices.io/patterns/data/transaction-log-tailing.html). Free.
- Debezium documentation, ["Debezium Architecture"](https://debezium.io/documentation/reference/stable/architecture.html). Read the whole page. Free.
- PostgreSQL documentation, ["SELECT"](https://www.postgresql.org/docs/current/sql-select.html), section "The Locking Clause" (`SKIP LOCKED`). Free.
