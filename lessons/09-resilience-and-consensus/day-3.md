# Module 9, Wednesday: disaster recovery, safe migrations and feature flags

[Module 9](../../modules/09-resilience-and-consensus.md) · [Leia em português](day-3.pt-BR.md)

**Reading time:** about 45 minutes. Use the rest of the 2-hour block on the references at the end.

This is an original text written for this course. It is based on the references listed at the end, and each section names the source it follows. Where an idea comes from a specific author, the text says so.

## Why this matters for a fintech

Monday and Tuesday were about surviving bad minutes: a slow partner, a traffic spike, a node that dies. Today is about two other ways a wallet loses money and trust. The first is the bad day: a region goes dark, or someone runs a `DELETE` without a `WHERE`. The second is self-inflicted: a deploy or a schema migration that breaks production. Regulators and partner banks will ask you how long you can be down and how much data you can lose. You need numbers, and you need to have tested them.

Friday's capstone asks for exactly this: a backup and restore by script, a `docs/m09.md` with your RPO and RTO, and a column rename with no downtime. Today's lab is the preparation.

## 1. RPO and RTO

*Main source: AWS whitepaper "Disaster Recovery of Workloads on AWS", page "Disaster recovery options in the cloud".*

Two numbers describe any recovery plan. The whitepaper uses them throughout as the targets each strategy must meet:

- **RPO (recovery point objective):** the most data, measured in time, you accept losing. An RPO of 5 minutes means that after a disaster you may lose up to the last 5 minutes of writes.
- **RTO (recovery time objective):** the most time you accept being down, from the moment of the disaster until the service works again.

They are business decisions, not technical ones, and they differ per kind of data:

| Data | Reasonable target | Why |
| --- | --- | --- |
| Ledger postings and transfers | RPO close to zero, RTO in minutes | A lost posting means a balance that doesn't match the partner bank |
| Idempotency keys | Same as the ledger | Losing them allows a retry to charge twice |
| Push notification history | RPO of hours | Annoying to lose, not dangerous |
| Analytics warehouse | RPO and RTO of a day | It can be rebuilt from the ledger |

An important point from the whitepaper: continuous replication gives a low RPO against losing a site, but it doesn't protect you from **data corruption or malicious deletion**, because the bad change replicates too. For that you need **point-in-time backups**. A wallet needs both: replication for the "region is gone" case, and backups for the "someone deleted the wrong rows" case.

## 2. Four strategies, from cheap to expensive

*Main source: AWS whitepaper, "Disaster recovery options in the cloud".*

The whitepaper groups strategies into four, ordered by cost and complexity. It describes RPO and RTO for each in relative terms; it doesn't give fixed numbers on this page.

| Strategy | What runs in the recovery site | Recovery |
| --- | --- | --- |
| **Backup and restore** | Only the backups | Restore data and redeploy all infrastructure. Slowest, cheapest. |
| **Pilot light** | Data replicated continuously; core services such as databases on; application servers defined but off | Turn on and scale the app servers. Faster. |
| **Warm standby** | A smaller but fully working copy of production | Scale it up. Faster still. |
| **Multi-site active/active** | Full production, serving traffic | No failover step: traffic is routed away from the failed site. |

The first three are **active/passive**: the passive site serves no traffic until a failover. Only active/active serves users from every site.

Details from the whitepaper that matter for your design:

- **Infrastructure as code.** Backup and restore only meets its RTO if you can recreate the environment quickly and without manual mistakes.
- **Be careful with automatic failover.** The whitepaper warns that failing over automatically on health checks can turn a false alarm into a real outage. It recommends that even manual failover be automated, so it is a single, tested action.
- **Test the plan.** A backup you have never restored is a hope, not a backup. Scaling up a warm standby also depends on control-plane operations (like auto scaling) that may be degraded during a regional event, which is why some teams provision full capacity in advance (a "hot standby").

For the capstone, your wallet runs on one machine with Docker Compose, so your strategy is backup and restore. That's fine. What matters is that the RPO and RTO in `docs/m09.md` come from measurement, not guesses.

## 3. Why active-active with balances is hard

*Main source: AWS whitepaper, "Disaster recovery options in the cloud", section on multi-site active/active. The wallet analysis is this course's.*

Active/active sounds ideal: near-zero RTO, no failover. The whitepaper explains that reads are usually served locally, and offers three patterns for writes:

- **Write global:** all writes go to one region; if it fails, another region is promoted.
- **Write local:** each region accepts writes, and concurrent updates are reconciled, for example with **last writer wins** (the whitepaper names this for DynamoDB global tables).
- **Write partitioned:** each record has a home region, chosen by a key such as user ID, so two regions never write the same record.

Now apply these to a balance. Alice has R$ 100. At the same moment, she pays R$ 80 at a store routed to São Paulo and sends R$ 80 by Pix through a request routed to Virginia.

- With **write local**, each region checks its local copy, sees R$ 100, and approves. After replication, she has spent R$ 160 out of R$ 100. Last writer wins makes it worse: one of the two postings is silently overwritten, and the ledger no longer matches the money that left.
- A balance check is an invariant across all writes to the account ("never below zero"). Enforcing it needs one authority per account at any moment: a single leader, or consensus between regions. Consensus across continents (Tuesday's Raft) means every debit waits for a majority round trip of tens to hundreds of milliseconds.
- **Write partitioned** is the practical answer: each account has a home region where all its debits happen. But a transfer between an account homed in São Paulo and one homed in Virginia is now a cross-region operation, which brings back sagas, outboxes and reconciliation from earlier modules.

So the honest interview answer is: active/active is fine for reads and for data without cross-record invariants. For balances, you either route each account to one writer (partitioning), or you pay consensus latency on every write. That's why many payment systems choose active/passive for the ledger, with a low RPO from synchronous or near-synchronous replication, and accept an RTO of minutes.

## 4. Backup and restore with Postgres

*Main source: PostgreSQL documentation, chapter "Backup and Restore".*

The PostgreSQL documentation describes three approaches: SQL dump, file system level backup, and continuous archiving. Two of them matter here:

- **Logical backups** with `pg_dump`: a snapshot of the data and schema at one moment, restorable with `pg_restore`. Simple and portable. Your RPO is the time since the last dump.
- **Physical backups with WAL archiving**: a base backup plus a continuous archive of the write-ahead log. You can replay the log to any point in time, for example to one second before the bad `DELETE`. This is point-in-time recovery (PITR), and managed Postgres services usually offer it as a feature.

For the capstone, a logical backup is enough. The shape of the script:

```bash
#!/usr/bin/env bash
set -euo pipefail
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
pg_dump --format=custom --file="backups/wallet-$STAMP.dump" "$DATABASE_URL"

# Restore into a fresh database and time it: this is your measured RTO.
time pg_restore --clean --if-exists --no-owner -d "$RESTORE_URL" "backups/wallet-$STAMP.dump"
```

A restore is only "done" when you have verified it. For a ledger, the minimum checks are row counts per table and the invariant that every transfer's postings sum to zero:

```sql
-- Must return no rows after a restore.
SELECT transfer_id, SUM(amount_cents) AS imbalance
FROM ledger_entries
GROUP BY transfer_id
HAVING SUM(amount_cents) <> 0;
```

Write down three numbers in `docs/m09.md`: how often the backup runs (your RPO), how long the restore plus checks took (your RTO), and the size of the dump.

## 5. Parallel change: migrations with no downtime

*Main source: Danilo Sato, "Parallel Change", martinfowler.com bliki, 2014.*

During a rolling deploy, old and new versions of your code run at the same time, against the same database. So a schema change that the old code can't handle breaks production for the length of the deploy. Renaming a column in one migration is the classic example: the moment `ALTER TABLE ... RENAME COLUMN` commits, every old pod's queries fail.

Sato describes **parallel change**, also called **expand and contract**, as a way to make a backward-incompatible change in three safe steps. He notes it was first documented as a refactoring strategy by Joshua Kerievsky in 2006, and that most database refactorings follow it.

1. **Expand:** add the new version next to the old one. Old clients keep working.
2. **Migrate:** move clients to the new version, step by step. During this phase both versions must work.
3. **Contract:** when nobody uses the old version any more, remove it.

Sato also warns that skipping the contract phase leaves the code worse than before, with two versions of everything. Put the contract step in the backlog the day you expand.

Here is Friday's capstone scenario sketched: rename `transfers.ext_ref` to `transfers.partner_reference`.

| Step | Database | Application |
| --- | --- | --- |
| 1. Expand | Add the nullable `partner_reference` column; add a trigger that copies writes from either column to the other | Deploy nothing new yet |
| 2. Backfill | Copy old rows in small batches | No change |
| 3. Migrate reads and writes | Constraints on the new column | Deploy code that reads and writes `partner_reference` only |
| 4. Contract | Drop the trigger, then drop `ext_ref` | Only after every old pod is gone |

The SQL for the expand and backfill steps looks like this:

```sql
-- Expand: adding a nullable column with no default is a quick catalog change.
ALTER TABLE transfers ADD COLUMN partner_reference text;

-- Backfill in batches to avoid long locks and huge transactions.
UPDATE transfers SET partner_reference = ext_ref
WHERE id IN (
  SELECT id FROM transfers
  WHERE partner_reference IS NULL AND ext_ref IS NOT NULL
  LIMIT 5000
);
-- repeat until 0 rows updated
```

Each step is its own deploy, and each one can be rolled back on its own. That is the whole point: there is never a moment where the running code and the schema disagree. You'll design the trigger and the constraint steps yourself on Friday.

## 6. Feature toggles and canary releases

*Main source: Pete Hodgson, "Feature Toggles (aka Feature Flags)", martinfowler.com, 2016 (revised 2017).*

Parallel change separates schema changes from code changes. **Feature toggles** separate deploying code from releasing behavior. The code for a new partner bank route can be in production for a week, switched off, and turned on for 1% of customers when you're ready.

Hodgson names the parts: a **toggle point** is the place in the code that chooses between two paths; a **toggle router** decides which path is active, using the **toggle configuration** and sometimes a **context** such as the user ID. He then classifies toggles by how long they live and how dynamic their decision is:

| Category | Purpose | Lifetime | Decision | Wallet example |
| --- | --- | --- | --- | --- |
| **Release** | Ship unfinished code dark | Days to weeks | Static per release | New statement screen |
| **Experiment** | A/B testing | Long enough for statistics | Per request, stable per user | Two onboarding flows |
| **Ops** | Control operational behavior | Mostly short; some permanent | Changed quickly at runtime | Turn off PDF statements during peak load |
| **Permissioning** | Features for specific users | Can last years | Per request | Higher limits for verified business accounts |

Two ideas from the article tie this module together:

- **Kill switches.** Hodgson describes long-lived ops toggles that act like a manually operated circuit breaker: during an incident, an operator turns off a non-essential feature to save capacity. That's Tuesday's load shedding, done by a human.
- **Canary releasing.** Turn a feature on for a small random cohort (his example selects 1% of users by a modulo of the user ID), compare business metrics with everyone else, and widen only if the numbers look good. Hodgson distinguishes this from exposing a feature to internal users first, which targets a chosen group rather than a random sample.

A toggle router with a stable percentage rollout might look like this:

```typescript
import { createHash } from 'node:crypto';

function inRollout(flag: string, userId: string, percent: number): boolean {
  // Hash flag + user so each flag gets an independent, stable 1% of users.
  const h = createHash('sha256').update(`${flag}:${userId}`).digest();
  return h.readUInt32BE(0) % 100 < percent;
}

// Toggle point, kept in one place (Hodgson: decouple decision points from decision logic).
const route = inRollout('partner-bank-v2', user.id, config.partnerV2Percent)
  ? partnerBankV2
  : partnerBankV1;
```

Hodgson also stresses that toggles have a **carrying cost**: extra code paths, extra tests, extra confusion. He recommends treating them as inventory to keep small: add a removal task when you create a release toggle, set expiry dates, and even add tests that fail after a toggle's expiry. He cites Knight Capital's costly incident as a warning about old toggles left in code. In a wallet, a forgotten toggle that routes some customers to a decommissioned partner is a reconciliation incident waiting to happen.

## 7. Putting it together for Friday

*This section connects the three sources to the capstone tasks.*

The module's Friday items 4 to 6 use everything from today:

- **k6 before and after (item 4).** Your "after" run is only meaningful if the protections from Monday and Tuesday can be switched on and off. Ops toggles for the breaker and the rate limiter make the comparison clean.
- **Expand/contract rename (item 5).** Run k6 during the migration. If error rate stays flat through every step, you have proved "no downtime".
- **Backup and restore (item 6).** Measure the restore, run the ledger checks, and record RPO and RTO in `docs/m09.md`, with one paragraph on what it would take to get a lower RPO (WAL archiving, a replica) and why you did not choose active/active for balances.

Today's lab: write the backup script, choose the migration scenario, and list the steps for Thursday and Friday as tasks. No capstone code yet.

## Notes to write today

1. RPO and RTO in one sentence each, the four DR strategies in one line each, and the difference between active-passive and active-active.
2. Why active-active with balances is hard: the two-region double spend, why last writer wins loses postings, and what write partitioning costs.
3. The three steps of expand/contract, applied to your column rename, with what is deployed at each step.
4. The four kinds of feature toggle, what a kill switch is, and how a canary release works.

## Check yourself

These make good flashcards (see the [flashcards guide](../../FLASHCARDS.md)).

- What is the difference between RPO and RTO?
- Why doesn't continuous replication protect you from a bad `DELETE`?
- What runs in the recovery site in a pilot light strategy?
- Why can't two regions both accept debits for the same account with only local checks?
- Why does renaming a column in one migration break a rolling deploy?
- How does a canary release differ from exposing a feature to internal users?
- What is the carrying cost of a feature toggle?

## References

- **Main source:** AWS whitepaper "Disaster Recovery of Workloads on AWS", page ["Disaster recovery options in the cloud"](https://docs.aws.amazon.com/whitepapers/latest/disaster-recovery-workloads-on-aws/disaster-recovery-options-in-the-cloud.html). Read all four strategies, and the part on reads and writes in active/active. Free.
- **Main source:** Danilo Sato, ["Parallel Change"](https://martinfowler.com/bliki/ParallelChange.html), martinfowler.com bliki, 2014. Short; read it all. Free.
- **Main source:** Pete Hodgson, ["Feature Toggles (aka Feature Flags)"](https://martinfowler.com/articles/feature-toggles.html), martinfowler.com, 2016, revised 2017. Read the categories of toggles, canary releasing, and the advice on managing the carrying cost of toggles. Free.
- PostgreSQL documentation, ["Backup and Restore"](https://www.postgresql.org/docs/current/backup.html). Read the chapter introduction, "SQL Dump" and the overview of "Continuous Archiving and Point-in-Time Recovery (PITR)". Free.
