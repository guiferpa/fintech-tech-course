# Module 1, Tuesday: replication and replication lag

[Module 1](../../modules/01-distributed-systems-fundamentals.md) · [Leia em português](day-2.pt-BR.md)

**Reading time:** about 45 minutes. Use the rest of the 2-hour block on the references at the end.

This is an original text written for this course. It is based on the references listed at the end, and each section names the source it follows.

## Why this matters for a fintech

Almost every wallet you will work on has a Postgres primary and at least one replica. The replica gives you a copy of the data if the primary dies, and a place to send read traffic like statements and dashboards. Both uses come with a catch. The replica is behind the primary by some amount of time, and a failover can lose the writes the replica hadn't received yet. Today is about those two catches.

## 1. Leader and followers

*Main source: PostgreSQL documentation, "High Availability, Load Balancing, and Replication".*

The most common setup is **single-leader replication**. One node, the **primary** (also called leader or master), accepts all writes. The other nodes, the **standbys** (followers, replicas), receive a stream of changes from the primary and apply them in the same order. Clients may read from any node but write only to the primary.

Postgres implements this with **streaming replication**. Every change is first written to the primary's write-ahead log (WAL). The primary streams WAL records to the standbys, and each standby replays them. A standby that accepts read-only queries while it replays is called a **hot standby**.

Because the standby applies the primary's log in order, it is always a consistent copy of the primary at some past moment. The question is how far in the past.

## 2. Synchronous and asynchronous replication

*Main source: PostgreSQL documentation, "High Availability, Load Balancing, and Replication", and the `synchronous_commit` setting.*

When a client commits a transaction on the primary, when does the primary say "committed"?

- **Asynchronous replication** (the Postgres default): as soon as the primary has written the commit to its own WAL on disk. The standby receives it a few milliseconds later, or a few minutes later if it's struggling.
- **Synchronous replication**: only after at least one standby confirms it has the commit too. In Postgres, you list standbys in `synchronous_standby_names` and choose how far the confirmation goes with `synchronous_commit` (`remote_write`, `on` meaning flushed to the standby's disk, or `remote_apply` meaning already visible to queries on the standby).

The trade-off:

| | Asynchronous | Synchronous |
| --- | --- | --- |
| Commit latency | Primary's disk only | Plus a round trip to the standby |
| If the standby is down | Writes continue | Writes block until it's back or removed |
| If the primary dies | Recent commits can be lost | Committed data exists on a standby |

Many teams use one synchronous standby and the rest asynchronous, which is sometimes called *semi-synchronous*. A commit is then on at least two machines, and one slow replica can't stop all writes.

## 3. Failover and the writes you lose

*Main source: PostgreSQL documentation, ["Failover"](https://www.postgresql.org/docs/current/warm-standby-failover.html) section of the High Availability chapter.*

When the primary dies, a standby must be **promoted** to become the new primary, and clients must be pointed at it. The Postgres documentation is explicit that Postgres "does not provide the system software required to identify a failure on the primary"; it only provides the promotion command (`pg_promote()`). An external tool (Patroni, a managed service like RDS, or an operator) has to detect the failure and promote a standby. Each step has a trap.

- **Detecting the failure** relies on timeouts, so it has all of Monday's problems. A primary that's only slow can be declared dead.
- **Lost writes with asynchronous replication.** Commits the old primary acknowledged but hadn't streamed yet are not on the new primary. From the client's point of view, a transfer that returned 201 has disappeared. If those writes were money movements, your ledger and the partner bank now disagree. Reconciliation (Module 7) is how you catch it.
- **Split brain.** If the old primary wasn't dead, only cut off, or if it restarts later, two nodes may both believe they are the primary and accept writes. The documentation says you must have a mechanism to tell the old primary it no longer is one, known as STONITH ("shoot the other node in the head"), because otherwise the result is "confusion and ultimately data loss". The general technique is called fencing.
- **Reused identifiers.** If the new primary hands out IDs or sequence values the old one had already used, other systems that saw the old IDs (a cache, a message already published to Kafka) now point to different data.

The lesson for design is that **a failover is a correctness event, not just an availability event**. Write down your RPO (how much data you accept losing) and know which replication mode delivers it. Module 9 comes back to RPO and RTO.

## 4. Replication lag and the anomalies it causes

*Main source: Jepsen, consistency models "Read Your Writes" and "Monotonic Reads".*

With asynchronous replication, a standby is usually milliseconds behind, but under load or during a network problem it can be seconds or minutes behind. Reads from it can then show surprising results. Jepsen's consistency model pages define the guarantees you lose.

**Read your writes.** A client that wrote something must see that write in its later reads. The violation: a customer sends a Pix, the API writes to the primary, the app reloads the statement from a replica, and the Pix isn't there. The customer sends it again.

Ways to provide it:

- Read from the primary anything the user may have just changed, such as their own balance and statement right after a transfer.
- Remember the time or WAL position (LSN) of the user's last write, and only read from a replica that has replayed past it. Postgres exposes `pg_last_wal_replay_lsn()` on standbys.
- Route a user to the primary for a short window after they write.

**Monotonic reads.** A client's reads never go back in time: once you've seen a state, later reads show that state or a newer one. The violation: a page loads the statement from replica A (up to date), then refreshes from replica B (lagging), and a transaction disappears. Pinning each user to one replica, for example by hashing the user ID, provides monotonic reads as long as that replica stays up.

**Consistent prefix.** Readers see writes in the order they happened. If a refund shows up before the payment it refunds, the reader saw an inconsistent prefix. This mostly happens when data is partitioned, which is Wednesday's topic.

Jepsen arranges these models in a hierarchy. Read your writes and monotonic reads are *session guarantees*: they only promise something to one client. Stronger models such as linearizability, which you'll meet on Wednesday, promise the same view to everyone.

## 5. Leaderless replication and quorums

*Main source: Kleppmann's lecture notes, section 5.2.*

Some databases, such as Cassandra and the Dynamo family, have no leader. The client (or a coordinator node) sends each write to all N replicas and each read to several replicas.

- A write counts as successful once **W** replicas confirm it.
- A read asks replicas and waits for **R** of them to answer.
- If **R + W > N**, every read quorum overlaps every write quorum in at least one node, so at least one of the R answers has the latest write. Each value carries a version or timestamp so the reader can pick the newest.

With N = 3, a common choice is W = 2 and R = 2. Each write and each read then survives one replica being down.

Two mechanisms bring stale replicas up to date:

- **Read repair**: when a read sees an old value on one replica, the reader writes the newest value back to it.
- **Anti-entropy**: a background process compares replicas and copies missing data.

Quorums are not a magic consistency switch. Concurrent writes still need a rule to pick a winner, and "last write wins" by timestamp silently drops one of them (Monday's clocks problem again). Kleppmann's notes also show (section 7.2) that R + W > N alone doesn't make reads linearizable; it takes read repair done before the read returns. That is one reason ledgers usually live in a single-leader database with transactions, and leaderless stores are kept for data where losing a concurrent update is acceptable.

## Notes to write today

1. Draw the primary and standby with the WAL stream, and mark where a commit is acknowledged in asynchronous and in synchronous mode.
2. List the writes you could lose in a failover, and what your system does to find them.
3. One example each of a read-your-writes violation and a monotonic-reads violation in a wallet app, and how you'd prevent each.

## Check yourself

- What does `synchronous_commit = remote_apply` guarantee that `on` does not?
- Why can asynchronous replication lose a commit the client already saw succeed?
- What is split brain, and what prevents it?
- How do you give a user read-your-writes while still reading from replicas?
- Why does R + W > N make a read see the latest write?

## References

- **Main source:** PostgreSQL documentation, ["High Availability, Load Balancing, and Replication"](https://www.postgresql.org/docs/current/high-availability.html), especially the sections on streaming replication, synchronous replication, failover and hot standby. Free.
- Jepsen, consistency models: ["Read Your Writes"](https://jepsen.io/consistency/models/read-your-writes) and ["Monotonic Reads"](https://jepsen.io/consistency/models/monotonic-reads), plus the [map of consistency models](https://jepsen.io/consistency). Free.
- Martin Kleppmann, ["Distributed Systems" lecture notes](https://www.cl.cam.ac.uk/teaching/2122/ConcDisSys/dist-sys-notes.pdf), University of Cambridge, section 5.2 (Quorums). Free, Creative Commons BY-SA.
