# Module 1, Wednesday: partitioning, consistency models and trade-offs

[Module 1](../../modules/01-distributed-systems-fundamentals.md) · [Leia em português](day-3.pt-BR.md)

**Reading time:** about 45 minutes. Use the rest of the 2-hour block on the references at the end, then draft the consistency table described at the end.

This is an original text written for this course. It is based on the references listed at the end, and each section names the source it follows.

## Why this matters for a fintech

Two questions decide much of a payment system's architecture. First, how do you split the data when one machine is no longer enough? Second, for each operation, how fresh and how agreed-upon does the data have to be? A balance check before a debit and a monthly spending chart need very different answers. Today gives you the vocabulary to answer both, using the way DynamoDB, Azure Cosmos DB, Cassandra and CockroachDB document their own behavior, and you finish by writing those answers down for 8 wallet operations.

## 1. Partitioning: splitting data across machines

*Main source: Amazon DynamoDB Developer Guide, "Best practices for designing and using partition keys effectively" and its subpages.*

Replication (Tuesday) copies the same data to several nodes. **Partitioning**, also called sharding, splits different data across nodes so that each holds only a part. Real systems do both: each partition is replicated.

Every record has a **partition key**, and the system uses it to decide which partition holds the record. There are two classic ways to map keys to partitions.

- **By key range.** Partition 1 holds keys A to F, partition 2 holds G to M, and so on. Range scans are cheap ("all transactions of account 42 in March"), but if the key is a timestamp, all of today's writes land on the same partition.
- **By hash of the key.** The system hashes the key and assigns ranges of hash values to partitions. Load spreads evenly, but you lose cheap range scans across keys; you can only scan efficiently inside one key.

DynamoDB hashes the partition key and can keep records with the same key sorted by a second key (the *sort key*). Its guide tells you to "design your application for uniform activity across all partition keys". It also gives the hard numbers: each partition delivers at most 3,000 read units and 1,000 write units per second, where a write unit is one write per second of an item up to 1 KB. When a few keys receive most of the traffic, the partitions holding them become **hot partitions** and requests to them are throttled, even if the table as a whole has spare capacity.

The guide's table of good and bad keys is worth copying into your notes:

| Partition key | Uniformity |
| --- | --- |
| User ID, with many users | Good |
| Status code, with only a few possible values | Bad |
| Creation date rounded to the day, hour or minute | Bad |
| Device ID, with devices accessed at similar rates | Good |
| Device ID, when one device is far more popular than the rest | Bad |

Read the wallet into that table. `status = 'PENDING'` as a key is bad. `created_date` is bad: on a given day, the guide notes, all new items go to that single key. **Account ID** is good for most accounts: each account's entries live together, so a statement is a single-partition query. But it has the last row's problem: a big merchant receiving thousands of payments per second, or the fee account that every transfer credits, is the one device far more popular than the rest. Module 6 deals with these hot accounts.

The guide's remedy for a key that is inherently hot is **write sharding**: add a suffix to the key so its writes spread over many key values. Its example appends a random number from 1 to 200 to a date, producing `2014-07-09.1` through `2014-07-09.200`. The cost is on reads: to get everything for that day you query all 200 keys and merge. A **calculated** suffix, derived from something you know such as the order ID, keeps writes spread and lets you compute the exact key to read one item directly. For a fee account, `fees#17` (with 17 derived from the transfer ID) spreads credits across N rows, and the fee balance becomes the sum of the N rows.

When nodes are added or removed, data must move between them. This is **rebalancing**. Cassandra's documentation explains why it uses consistent hashing: when the number of nodes changes, it "only has to move a small fraction of the keys", unlike a naive `hash(key) % N`, where almost every key moves. It also gives each physical node many tokens on the ring (virtual nodes), so a new node takes small pieces from everyone.

## 2. Linearizability: behaving like a single copy

*Main sources: Azure Cosmos DB documentation, "Consistency levels in Azure Cosmos DB", and Amazon DynamoDB Developer Guide, "DynamoDB read consistency".*

Replication and partitioning give you many copies and many places. A consistency model says what readers are allowed to see despite that.

The strongest common model is **linearizability**: the system behaves as if there were a single copy of the data, and every operation takes effect at one instant between its start and its end. Product documentation describes it in practical terms:

- Cosmos DB's **strong** level "offers a linearizability guarantee": reads "are guaranteed to return the most recent committed version of an item", and a client never sees an uncommitted or partial write.
- DynamoDB's **strongly consistent read** returns "the most up-to-date data, reflecting the updates from all prior write operations that were successful".
- Cockroach Labs describes CockroachDB's contract as "the most recent write is always visible to subsequent readers".

In practice: once a write completes, every read that starts afterward sees it, whichever replica serves it.

Linearizability is what you implicitly assume when you write `if balance >= amount then debit`. If the balance read can be stale, two concurrent debits can both pass the check. In DynamoDB it is a per-request flag, and the default is the weaker one:

```bash
# Eventually consistent by default; --consistent-read asks for the latest committed value
aws dynamodb get-item --table-name accounts \
  --key '{"account_id": {"S": "acc_42"}}' --consistent-read
```

The details in the docs are where the fintech traps are:

- **Strong reads cost more.** DynamoDB says eventually consistent reads "are half the cost of strongly consistent reads". Cosmos DB says read throughput for strong and bounded staleness "is half that of the other consistency levels", because they read from two replicas instead of one.
- **Not everything can be read strongly.** In DynamoDB, strongly consistent reads "from a global secondary index or a DynamoDB stream are not supported". If you look up idempotency keys through a global secondary index, that lookup is eventually consistent, and two retries arriving together can both see "new key". Keep that check on the table's primary key, or in Postgres with a unique constraint.

The cost of linearizability is coordination. Every linearizable operation must reach a majority, or a single leader, that knows the latest state. That adds latency, and a node cut off from the majority cannot serve linearizable operations. Cosmos DB's documentation shows this: with strong consistency across regions, it can drop an unresponsive region from the quorum, and that region is then "no longer able to serve reads" until it rejoins.

## 3. CAP, stated carefully

*Main source: Cockroach Labs blog, "Limits of the CAP theorem" (Ben Darnell).*

The CAP theorem is often summarized as "pick two of consistency, availability and partition tolerance", which is misleading. Network partitions aren't something you choose; they happen. Jeff Hodges puts it in one line: "you can't choose CA". The precise statement is the one Darnell gives: in the presence of partitions, "a system cannot be both consistent and available". Consistency in CAP means linearizability, and availability means every node that is up can still answer.

- A **CP** choice: a node that can't reach the majority refuses requests (returns an error or waits) rather than risk answering with stale data. Darnell describes CockroachDB this way: "in the event of partitions, the system will block rather than return inconsistent data". Writes need a majority of replicas; a cut-off node holding a lease keeps serving reads only until its lease expires.
- An **AP** choice: every node keeps answering with what it has, and the replicas reconcile after the partition heals.

Tuesday's MongoDB example is CAP in action: during a partition, `{ w: "majority" }` writes cannot complete on the isolated old primary (the CP behavior), while `{ w: 1 }` writes are accepted there and rolled back later (the AP behavior, with its price).

Darnell adds two practical points. Most outages are not partitions at all; hardware failures, application bugs and operator error cause more downtime, and CAP says nothing about them. And CP systems pay for consistency even when the network is fine, because "consistent systems must coordinate between different nodes during writes". That second point is what PACELC is about.

## 4. PACELC: the trade-off you pay every day

*Main source: Azure Cosmos DB documentation, "Consistency levels in Azure Cosmos DB".*

PACELC extends CAP: **if there is a Partition (P), choose between Availability (A) and Consistency (C); Else (E), choose between Latency (L) and Consistency (C).** Partitions are rare; the "else" trade-off is present on every request.

The Cosmos DB documentation is useful here because it names PACELC and then puts numbers on it. It opens by saying replicated databases must balance consistency, availability, latency and throughput "as defined by the PACELC theorem", and then:

- For most levels, reads and writes are under 10 ms at the 99th percentile within a region.
- With strong consistency across regions, write latency is "two times round-trip time (RTT) between any of the two farthest regions, plus 10 milliseconds at the 99th percentile". If the round trip between your two farthest regions is 120 ms, that's about 250 ms for every write.
- Strong consistency between regions more than 5,000 miles apart is blocked by default because of that latency.
- Accounts that accept writes in several regions cannot use strong consistency at all.

DynamoDB global tables show the same choice. By default (multi-Region eventual consistency) changes reach other regions "typically within a second". With multi-Region strong consistency, a write is replicated to another region "before the write returns", so strong reads anywhere see it, and every write pays for the trip.

The useful mindset for a fintech: you don't pick one model for the company, you pick one per operation. Both DynamoDB and Cosmos DB let you choose per request, and that's how you should think about your Postgres reads too (primary or replica).

## 5. Eventual consistency and what lies between

*Main sources: Azure Cosmos DB documentation, "Consistency levels in Azure Cosmos DB", and Redis documentation, "Active-Active geo-distributed Redis".*

At the other end is **eventual consistency**: if writes stop, replicas converge, but in the meantime you may read stale data. Cosmos DB's documentation goes further and warns that a client "might read values older than those values it read in the past", and suggests it for things like counts of likes and comments, where no ordering is needed. DynamoDB's guide says the same of its default reads: they "might not reflect the results of a recently completed write", and a repeat after a short time "should eventually" return it.

Cosmos DB is a good map of the space in between because it offers five named levels, strongest to weakest:

| Level | What a reader is promised |
| --- | --- |
| Strong | Linearizability |
| Bounded staleness | Lag stays under K versions or T time, whichever is reached first |
| Session | Read your writes and writes follow reads, within a session (Tuesday) |
| Consistent prefix | Writes of one transaction appear together, never partially |
| Eventual | Convergence, eventually; reads can even go backward |

**Bounded staleness** is a useful idea for dashboards: "at most 5 seconds old" is a promise you can show users.

A stronger cousin of eventual consistency is **strong eventual consistency**: replicas that received the same updates are in the same state, whatever order the updates arrived in, without waiting for coordination. Redis's Active-Active databases work this way. The Redis documentation says they use only conflict-free replicated data types (CRDTs), which give "predictable conflict resolution" with no extra work from the application, and they accept writes in every region with sub-millisecond local latency. Cassandra uses a CRDT too: its last-write-wins rule per row is one. The catch for money is in how conflicts are resolved: a counter of likes can merge concurrent increments, but two debits merged after the fact can take an account below zero, because the balance check was never coordinated.

## 6. Choosing a model per wallet operation

Put it together by asking, for each operation: what's the harm of a stale or out-of-order read, and what's the cost of coordination?

| Operation | Model it needs | Why |
| --- | --- | --- |
| Debit with balance check | Linearizable (single leader, inside a transaction) | A stale balance allows overdraft or double spending |
| Idempotency key check | Linearizable on the key (primary key or unique constraint, never a secondary index replica) | Two replicas both saying "new key" means a double charge |
| Statement right after the user's own transfer | Read your writes (session token, LSN check or primary) | The user must see what they just did |
| Statement while scrolling | Monotonic reads | Entries must not disappear on refresh |
| Monthly spending chart | Eventual, or bounded staleness | Seconds of lag hurt no one |
| Balance shown on the home screen | Read your writes, with a "last updated" time | Fast, but must reflect the user's own actions |
| Fraud velocity counter | Eventual or strong eventual, with a safety margin | Blocking every payment on coordination costs more than a slightly stale count |
| Exchange rate used to price a transfer | Linearizable read of a versioned rate, stored on the entry | The customer must be charged the rate they were quoted |

Your own table may differ, and that's fine as long as every row has a one-line justification. That's the deliverable for this week's `docs/m01.md`.

## Notes to write today

1. The partition key of a digital wallet, and which accounts become hot.
2. The difference between linearizability and eventual consistency, in one sentence each, and what DynamoDB and Cosmos DB charge for the stronger one.
3. CAP stated correctly, and what PACELC adds, with the Cosmos DB latency numbers as an example.
4. A first draft of the 8-operation table.

## Check yourself

- Why does a date make a bad partition key, according to the DynamoDB guide?
- What is write sharding, and what does it cost on reads? What does a calculated suffix improve?
- Define linearizability without using the word "consistent".
- Why is an idempotency check through a DynamoDB global secondary index unsafe?
- During a network partition, what does a CP node do with a request? And an AP node?
- What does the "ELC" in PACELC describe, and what does it cost in Cosmos DB with strong consistency across regions?
- What does strong eventual consistency add to eventual consistency, and why doesn't it make a balance check safe?

## References

- **Main source for partitioning:** Amazon DynamoDB Developer Guide, ["Best practices for designing and using partition keys effectively"](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/bp-partition-key-design.html), and its subpages ["Designing partition keys to distribute your workload in DynamoDB"](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/bp-partition-key-uniform-load.html) and ["Using write sharding to distribute workloads evenly"](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/bp-partition-key-sharding.html). Free.
- **Main source for consistency:** Microsoft, Azure Cosmos DB documentation, ["Consistency levels in Azure Cosmos DB"](https://learn.microsoft.com/azure/cosmos-db/consistency-levels). Free. The five levels, PACELC, latency, throughput and RPO.
- Amazon DynamoDB Developer Guide, ["DynamoDB read consistency"](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/HowItWorks.ReadConsistency.html). Free. Eventually vs. strongly consistent reads, and what can't be read strongly.
- Ben Darnell, Cockroach Labs blog, ["Limits of the CAP theorem"](https://www.cockroachlabs.com/blog/limits-of-the-cap-theorem/). Free. CAP stated correctly, from the makers of a CP database.
- Apache Cassandra documentation, ["Dynamo"](https://cassandra.apache.org/doc/latest/cassandra/architecture/dynamo.html), sections on consistent hashing and virtual nodes. Free.
- Redis documentation, ["Active-Active geo-distributed Redis"](https://redis.io/docs/latest/operate/rs/databases/active-active/). Free. Strong eventual consistency with CRDTs in a real product.
- Jeff Hodges, ["Notes on Distributed Systems for Young Bloods"](https://www.somethingsimilar.com/2013/01/14/notes-on-distributed-systems-for-young-bloods/), 2013, section "Use the CAP theorem to critique systems". Free.
