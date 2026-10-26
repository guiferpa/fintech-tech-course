# Module 1, Tuesday: replication and replication lag

[Module 1](../../modules/01-distributed-systems-fundamentals.md) · [Leia em português](day-2.pt-BR.md)

**Reading time:** about 45 minutes. Use the rest of the 2-hour block on the references at the end.

This is an original text written for this course. It is based on the references listed at the end, and each section names the source it follows.

## Why this matters for a fintech

Almost every wallet you will work on has a Postgres primary and at least one replica. The replica gives you a copy of the data if the primary dies, and a place to send read traffic like statements and dashboards. Both uses come with a catch. The replica is behind the primary by some amount of time, and a failover can lose the writes the replica hadn't received yet. Today is about those two catches, seen through the documentation of the databases that deal with them in production: PostgreSQL, MongoDB, Azure Cosmos DB and Apache Cassandra.

## 1. Leader and followers

*Main source: PostgreSQL documentation, "High Availability, Load Balancing, and Replication".*

The most common setup is **single-leader replication**. One node, the **primary** (also called leader or master), accepts all writes. The other nodes, the **standbys** (followers, replicas), receive a stream of changes from the primary and apply them in the same order. Clients may read from any node but write only to the primary.

Postgres implements this with **streaming replication**. Every change is first written to the primary's write-ahead log (WAL). The primary streams WAL records to the standbys, and each standby replays them. A standby that accepts read-only queries while it replays is called a **hot standby**.

Every position in the WAL has an address called an **LSN** (log sequence number), shown as something like `0/3000148`. LSNs only grow, so they are the natural way to say "how far" a standby has gotten. Because the standby applies the primary's log in order, it is always a consistent copy of the primary at some past moment. The question is how far in the past.

## 2. Synchronous and asynchronous replication

*Main source: PostgreSQL documentation, "Log-Shipping Standby Servers" (sections on streaming and synchronous replication).*

When a client commits a transaction on the primary, when does the primary say "committed"?

- **Asynchronous replication** is the Postgres default. The primary confirms as soon as the commit is in its own WAL on disk. The documentation says the delay until the change is visible on the standby is "typically under one second assuming the standby is powerful enough to keep up with the load". Under heavy load or a network problem it can be much more.
- **Synchronous replication** makes the commit wait for a standby. You enable it by setting `synchronous_standby_names`, and you choose how far the confirmation goes with `synchronous_commit`.

The three levels of `synchronous_commit` are worth knowing exactly, because each one buys a different guarantee:

| Setting | The commit waits until the standby has... | What it protects |
| --- | --- | --- |
| `remote_write` | received the commit and handed it to its operating system | Survives a Postgres crash on the standby, but not an OS crash |
| `on` (default once a sync standby is configured) | written the commit record to durable storage | The commit exists on two disks |
| `remote_apply` | replayed the transaction, so it is visible to queries | A read on that standby right after the commit sees it |

You can also wait for several standbys. `synchronous_standby_names = 'FIRST 1 (s1, s2)'` waits for the highest-priority standby that is available, and `'ANY 2 (s1, s2, s3)'` waits for any two of the three, a quorum.

The trade-off:

| | Asynchronous | Synchronous |
| --- | --- | --- |
| Commit latency | Primary's disk only | Plus a round trip to the standby |
| If the standby is down | Writes continue | Writes wait until it's back or removed |
| If the primary dies | Recent commits can be lost | Committed data exists on a standby |

The documentation is blunt about the middle row: commits that wait for a synchronous standby "may never be completed" if that standby crashes, and the fix is to reduce the number of required standbys or disable the setting and reload the configuration. That is why many teams use `ANY 1` over two standbys: a commit is on at least two machines, and one slow replica can't stop all writes.

Other databases expose the same choice as a dial. Azure Cosmos DB's documentation publishes the recovery point objective (RPO) for a region-wide outage per consistency level: with several regions and a single write region, the weaker levels can lose "less than 15 minutes" of writes, while strong consistency gives an RPO of 0, because every write is committed in a majority of regions before it is confirmed. It's the same trade as Postgres, sync against async, only between regions instead of machines.

## 3. Failover and the writes you lose

*Main source: PostgreSQL documentation, ["Failover"](https://www.postgresql.org/docs/current/warm-standby-failover.html) section of the High Availability chapter.*

When the primary dies, a standby must be **promoted** to become the new primary, and clients must be pointed at it. The Postgres documentation is explicit that Postgres "does not provide the system software required to identify a failure on the primary"; it only provides the promotion itself:

```sql
-- On the standby you want to promote
SELECT pg_promote();
```

An external tool (Patroni, a managed service like RDS, or an operator) has to detect the failure and run that. Each step has a trap.

- **Detecting the failure** relies on timeouts, so it has all of Monday's problems. A primary that's only slow can be declared dead.
- **Lost writes with asynchronous replication.** The documentation says it directly: if the primary crashes, "some transactions that were committed may not have been replicated to the standby server, causing data loss", and the amount lost "is proportional to the replication delay at the time of failover". From the client's point of view, a transfer that returned 201 has disappeared. If it was a money movement already sent to the partner bank, your ledger and the bank now disagree. Reconciliation (Module 7) is how you catch it.
- **Split brain.** If the old primary wasn't dead, only cut off, or if it restarts later, two nodes may both believe they are the primary and accept writes. The documentation says you need a way to tell the old primary it no longer is one, known as STONITH ("Shoot The Other Node In The Head"), because otherwise the result is "confusion and ultimately data loss". The general technique is called fencing.
- **Reused identifiers.** If the new primary hands out IDs or sequence values the old one had already used, other systems that saw the old IDs (a cache, a message already published to Kafka) now point to different data.

MongoDB's documentation shows split brain concretely. In a five-member replica set cut by a network partition, the old primary may not have stepped down yet. Writes with write concern `{ w: 1 }` (confirmed by one node) can succeed on either primary, and those accepted by the old one are **rolled back** when the partition heals. Writes with `{ w: "majority" }` can only complete on the side that has a majority. For money, that difference is the whole point: a write confirmed only by a node that may be on the losing side is a write you may lose.

The lesson for design is that **a failover is a correctness event, not just an availability event**. Write down your RPO (how much data you accept losing) and know which replication mode delivers it. Module 9 comes back to RPO and RTO.

## 4. Measuring replication lag

*Main source: PostgreSQL documentation, "Log-Shipping Standby Servers", section "Monitoring".*

You can't reason about lag you don't measure. The documentation's recipe is to compare WAL positions: `pg_current_wal_lsn()` on the primary against `pg_last_wal_receive_lsn()` on the standby, and to watch the `pg_stat_replication` view on the primary, which has one row per standby with how far it has been sent WAL. Subtracting two LSNs gives a number of bytes:

```sql
-- On the primary: how many bytes of WAL each standby has not yet been sent
SELECT application_name, pg_current_wal_lsn() - sent_lsn AS bytes_behind
  FROM pg_stat_replication;

-- On the standby: received but not yet replayed (visible to queries)
SELECT pg_last_wal_receive_lsn() - pg_last_wal_replay_lsn() AS bytes_not_replayed;
```

The documentation also tells you how to read the gaps. A large difference between the primary's current LSN and `sent_lsn` points to a primary under heavy load. A large difference between `sent_lsn` and what the standby received points to the network or a busy standby. A standby that receives faster than it replays shows up as a gap between received and replayed. In this week's lab you'll put Toxiproxy between primary and replica and watch these numbers grow.

## 5. Replication lag and the anomalies it causes

*Main sources: MongoDB manual, "Read Isolation, Consistency, and Recency", and Azure Cosmos DB documentation, "Consistency levels in Azure Cosmos DB".*

With asynchronous replication, reads from a standby can show surprising results. MongoDB's manual describes reads from secondaries plainly: they "may return data that lags behind the primary", but since secondaries apply writes in the same order as the primary, reads "may be stale but never out of order". The same is true of a Postgres hot standby. MongoDB's manual also names the guarantees you lose, with definitions you can use directly. Two matter most for a wallet.

**Read your writes.** In MongoDB's words, "read operations reflect the results of write operations that precede them". The violation: a customer sends a Pix, the API writes to the primary, the app reloads the statement from a replica, and the Pix isn't there. The customer sends it again.

**Monotonic reads.** Reads never return an earlier state than a previous read. The violation: a page loads the statement from replica A (up to date), the user pulls to refresh, the request goes to replica B (lagging), and a transaction disappears.

How do real products provide these? Azure Cosmos DB's **session** consistency, which its documentation calls "the most widely used consistency level", is a good model to copy. After every write, the client receives a **session token**, and later reads send it back. The documentation describes the token as "a minimum version barrier": a replica only answers once it has caught up to at least that point. Tokens are tied to a partition, and a client that has lost its token gets eventual consistency for that partition. MongoDB's causally consistent sessions do the same with an "operation time" the driver tracks for you.

You can build the same thing on Postgres with LSNs:

1. After the transfer commits on the primary, read `pg_current_wal_lsn()` and return it to the app (or keep it in the user's session) as the token.
2. When serving that user's statement from a replica, check `pg_last_wal_replay_lsn() >= token` on the replica.
3. If the replica isn't there yet, wait briefly or send the read to the primary.

Simpler alternatives also work: read from the primary anything the user may have just changed (their own balance and statement right after a transfer), or route a user to the primary for a short window after they write. For monotonic reads, pin each user to one replica, for example by hashing the user ID, or apply the same token rule using the highest LSN the user has seen.

**Consistent prefix.** Readers see writes in the order they happened. Cosmos DB's documentation gives a precise example: if one transaction updates Doc1 and Doc2, a reader sees both old versions or both new versions, but never a mix. In a wallet, the debit and the credit of one transfer are written in one transaction, so no reader should ever see only one side. A single-leader Postgres gives you this for free. It mostly breaks when data is partitioned across machines that replicate independently, which is Wednesday's topic.

These are *session guarantees*: they promise something to one client. Stronger models, such as the linearizability you'll meet on Wednesday, promise the same view to everyone.

## 6. Leaderless replication and quorums

*Main source: Apache Cassandra documentation, "Dynamo".*

Some databases, such as Cassandra and others in the Dynamo family, have no leader. Each piece of data is stored on a number of nodes given by the **replication factor** (RF). Cassandra's documentation explains that writes "are always sent to all replicas"; what you tune is how many acknowledgments the coordinator waits for, using a **consistency level** per request:

- `ONE`: a single replica must respond.
- `QUORUM`: a majority, n/2 + 1 of the replicas.
- `ALL`: every replica.
- `LOCAL_QUORUM`: a majority in the coordinator's own datacenter.

If the number of replicas a read waits for (R) plus the number a write waits for (W) is greater than RF, every read set overlaps every write set in at least one node. The documentation puts it as W + R > RF and says this makes "all acknowledged writes ... visible to subsequent reads". With RF = 3, `QUORUM` writes and reads each need 2 replicas, so they always share one, and each survives one replica being down. With `LOCAL_QUORUM` in a multi-datacenter cluster, the guarantee only holds within the same datacenter. If you don't need it, `ONE` gives lower latency and higher availability.

Replicas that missed a write are brought up to date by several mechanisms:

- **Hinted handoff**: when a replica is down, the coordinator stores a hint and replays the write when the replica returns.
- **Read repair**: a read that notices replicas disagree fixes the stale one.
- **Anti-entropy repair**: replicas compare hash trees (Merkle trees) of their data in the background and copy what's missing. This is what guarantees they eventually converge.

Quorums are not a magic consistency switch. When two writes to the same value are concurrent, Cassandra resolves them by **last write wins**, using each write's timestamp, which comes from the client or the coordinator's clock. The documentation warns that this depends on synchronized clocks, which is Monday's lesson again: with skewed clocks, the "last" write may be the older one, and the other is silently dropped. Fine for a profile picture, unacceptable for a balance. That is one reason ledgers usually live in a single-leader database with transactions, and leaderless stores are kept for data where losing a concurrent update is acceptable.

## Notes to write today

1. Draw the primary and standby with the WAL stream, and mark where a commit is acknowledged with asynchronous replication and with each `synchronous_commit` level.
2. List the writes you could lose in a failover, and what your system does to find them.
3. One example each of a read-your-writes violation and a monotonic-reads violation in a wallet app, and how you'd prevent each (the LSN token is one answer).

## Check yourself

- What does `synchronous_commit = remote_apply` guarantee that `on` does not?
- Why can asynchronous replication lose a commit the client already saw succeed, and what decides how much is lost?
- What is split brain, and what prevents it?
- Which two SQL functions tell you how far behind a standby is?
- How does a Cosmos DB session token give a user read-your-writes, and how would you copy the idea on Postgres?
- With RF = 3, why do `QUORUM` reads and writes see the latest acknowledged write?
- Why is last write wins dangerous for a balance?

## References

- **Main source:** PostgreSQL documentation, ["High Availability, Load Balancing, and Replication"](https://www.postgresql.org/docs/current/high-availability.html), especially the sections on streaming replication, synchronous replication, failover and hot standby. Free.
- PostgreSQL documentation, ["Log-Shipping Standby Servers"](https://www.postgresql.org/docs/current/warm-standby.html), subsections "Streaming Replication" (including "Monitoring") and "Synchronous Replication". Free.
- MongoDB manual, ["Read Isolation, Consistency, and Recency"](https://www.mongodb.com/docs/manual/core/read-isolation-consistency-recency/), sections on causal consistency and stale secondary reads; and ["Causal Consistency and Read and Write Concerns"](https://www.mongodb.com/docs/manual/core/causal-consistency-read-write-concerns/) for the network partition scenarios. Free.
- Microsoft, Azure Cosmos DB documentation, ["Consistency levels in Azure Cosmos DB"](https://learn.microsoft.com/azure/cosmos-db/consistency-levels), sections on session and consistent prefix consistency and the RPO table. Free.
- Apache Cassandra documentation, ["Dynamo"](https://cassandra.apache.org/doc/latest/cassandra/architecture/dynamo.html), sections on replication, tunable consistency and replica synchronization. Free.
