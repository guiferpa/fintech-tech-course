# Module 1, Wednesday: partitioning, consistency models and trade-offs

[Module 1](../../modules/01-distributed-systems-fundamentals.md) · [Leia em português](day-3.pt-BR.md)

**Reading time:** about 45 minutes. Use the rest of the 2-hour block on the references at the end, then draft the consistency table described at the end.

This is an original text written for this course. It is based on the references listed at the end, and each section names the source it follows.

## Why this matters for a fintech

Two questions decide much of a payment system's architecture. First, how do you split the data when one machine is no longer enough? Second, for each operation, how fresh and how agreed-upon does the data have to be? A balance check before a debit and a monthly spending chart need very different answers. Today gives you the vocabulary to answer both, and you finish by writing those answers down for 8 wallet operations.

## 1. Partitioning: splitting data across machines

*Main source: Amazon DynamoDB Developer Guide, "Best practices for designing and using partition keys effectively".*

Replication (Tuesday) copies the same data to several nodes. **Partitioning**, also called sharding, splits different data across nodes so that each holds only a part. Real systems do both: each partition is replicated.

Every record has a **partition key**, and the system uses it to decide which partition holds the record. There are two classic ways to map keys to partitions.

- **By key range.** Partition 1 holds keys A to F, partition 2 holds G to M, and so on. Range scans are cheap ("all transactions of account 42 in March"), but if the key is a timestamp, all of today's writes land on the same partition.
- **By hash of the key.** The system hashes the key and assigns ranges of hash values to partitions. Load spreads evenly, but you lose cheap range scans across keys; you can only scan efficiently inside one key.

DynamoDB, like many stores, hashes the partition key and can keep records with the same key sorted by a second key (the *sort key*). The DynamoDB guide's main advice is that the partition key should have **many distinct values that are accessed fairly evenly**. Each DynamoDB partition serves at most about 3,000 read units and 1,000 write units per second. When a few keys receive most of the traffic, the partitions holding them become **hot partitions**: they hit that limit and requests are throttled, even though the table as a whole has spare capacity. DynamoDB's adaptive capacity absorbs some imbalance, but the guide still tells you to design for uniform access rather than rely on it.

The guide's remedy for a key that is inherently hot is **write sharding**: add a suffix to the key (for example `merchant#123#7`, a random or calculated number from 0 to N−1) so its writes spread across N partitions, and combine the N parts when you read.

For a wallet, the natural partition key is the **account ID**. Each account's entries live together, so a statement is a single-partition query, and a transfer between two accounts in the same partition can be atomic. The hot spot is the account with enormous traffic, such as a big merchant receiving thousands of payments per second, or the fee account that every transfer credits. Module 6 deals with these hot accounts.

When nodes are added or removed, partitions must move between them. This is **rebalancing**. A common approach is to create many more partitions than nodes up front and move whole partitions around, so a key never has to change partition.

## 2. Linearizability: behaving like a single copy

*Main source: Kleppmann's lecture notes, section 7.2.*

Replication and partitioning give you many copies and many places. A consistency model says what readers are allowed to see despite that.

The strongest common model is **linearizability**. A system is linearizable if it behaves as if there were **a single copy of the data and every operation took effect atomically at some instant between its start and its end**. In practice:

- Once a write has completed, every read that starts afterward sees it (or a later write), no matter which replica it reads from.
- Once any reader has seen a new value, no later reader sees the old one.

Linearizability is what you implicitly assume when you write `if balance >= amount then debit`. If the balance read can be stale, two concurrent debits can both pass the check. Kleppmann's notes show how to get linearizable reads and writes on top of quorums (the ABD algorithm, where a reader writes back the newest value it saw before returning), and section 6 shows how consensus provides it for more complex operations.

The cost is coordination. Every linearizable operation must reach a majority, or a single leader, that knows the latest state. That adds latency, and **if a network partition cuts a node off from the majority, that node cannot serve linearizable operations at all**.

## 3. CAP, stated carefully

*Main source: Kleppmann's lecture notes, section 7.2.*

The CAP theorem is often summarized as "pick two of consistency, availability and partition tolerance", which is misleading. Network partitions aren't something you choose; they happen. The precise statement is: **when there is a network partition, a system must choose between linearizability (C) and availability (A)**, where availability means every node that is up can still answer.

- A **CP** choice: a node that can't reach the majority refuses requests (returns an error or waits) rather than risk answering with stale data.
- An **AP** choice: every node keeps answering with what it has, and the replicas reconcile after the partition heals.

CAP says nothing about what happens when the network is fine, and that's most of the time. That gap is what PACELC fills.

## 4. PACELC: the trade-off you pay every day

*Main source: Daniel Abadi, "Consistency Tradeoffs in Modern Distributed Database System Design", IEEE Computer, 2012.*

Abadi's argument is that CAP gets too much attention because partitions are rare, while a different trade-off is present on every request. He phrased it as PACELC: **if there is a Partition (P), choose between Availability (A) and Consistency (C); Else (E), choose between Latency (L) and Consistency (C).**

The "else" part exists because keeping replicas consistent requires waiting for them. A synchronous replica (Tuesday) adds a round trip to every commit; reading from the leader instead of a nearby replica adds distance. Systems that replicate data in any form choose, constantly, between answering fast and answering with agreed-upon data.

In Abadi's classification, systems like Dynamo and Cassandra in their default configuration are **PA/EL** (they favor availability during partitions and latency otherwise), while fully consistent systems such as VoltDB, Megastore, BigTable and HBase are **PC/EC**. Many systems are configurable per operation, and that is the useful mindset for a fintech: you don't pick one model for the company, you pick one per operation.

## 5. Eventual consistency and its stronger cousin

*Main source: Kleppmann's lecture notes, section 7.3.*

At the other end of the spectrum is **eventual consistency**: if no new writes arrive, all replicas eventually converge to the same value. It promises nothing about what you read in the meantime, and it says nothing about how long "eventually" is.

Kleppmann's notes describe a more useful variant, **strong eventual consistency**: any two replicas that have received the same set of updates are in the same state, regardless of the order they received them, and there's no need to wait for convergence before reading. Data types designed so that concurrent updates merge deterministically (CRDTs, such as counters that only add) achieve this without coordination.

Between linearizability and eventual consistency sit the session guarantees from Tuesday (read your writes, monotonic reads) and causal consistency, which keeps cause-and-effect order (Monday's happens-before) but allows concurrent writes to be seen in different orders.

## 6. Choosing a model per wallet operation

Put it together by asking, for each operation: what's the harm of a stale or out-of-order read, and what's the cost of coordination?

| Operation | Model it needs | Why |
| --- | --- | --- |
| Debit with balance check | Linearizable (single leader, inside a transaction) | A stale balance allows overdraft or double spending |
| Idempotency key check | Linearizable on the key | Two replicas both saying "new key" means a double charge |
| Statement right after the user's own transfer | Read your writes | The user must see what they just did |
| Statement while scrolling | Monotonic reads | Entries must not disappear on refresh |
| Monthly spending chart | Eventual | Seconds of lag hurt no one |
| Balance shown on the home screen | Read your writes, with a "last updated" time | Fast, but must reflect the user's own actions |
| Fraud velocity counter | Eventual or strong eventual, with a safety margin | Blocking every payment on coordination costs more than a slightly stale count |
| Exchange rate used to price a transfer | Linearizable read of a versioned rate, stored on the entry | The customer must be charged the rate they were quoted |

Your own table may differ, and that's fine as long as every row has a one-line justification. That's the deliverable for this week's `docs/m01.md`.

## Notes to write today

1. The partition key of a digital wallet, and which accounts become hot.
2. The difference between linearizability and eventual consistency, in one sentence each.
3. CAP stated correctly, and what PACELC adds.
4. A first draft of the 8-operation table.

## Check yourself

- Why does a timestamp make a bad partition key in a range-partitioned store?
- What is write sharding, and what does it cost on reads?
- Define linearizability without using the word "consistent".
- During a network partition, what does a CP node do with a request? And an AP node?
- What does the "ELC" in PACELC describe?
- What does strong eventual consistency add to eventual consistency?

## References

- **Main source for partitioning:** Amazon DynamoDB Developer Guide, ["Best practices for designing and using partition keys effectively"](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/bp-partition-key-design.html), and its subpage ["Using write sharding to distribute workloads evenly"](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/bp-partition-key-sharding.html). Free.
- **Main source for consistency:** Martin Kleppmann, ["Distributed Systems" lecture notes](https://www.cl.cam.ac.uk/teaching/2122/ConcDisSys/dist-sys-notes.pdf), University of Cambridge, sections 7.2 (Linearizability) and 7.3 (Eventual consistency). Free, Creative Commons BY-SA.
- Daniel Abadi, ["Consistency Tradeoffs in Modern Distributed Database System Design"](https://www.cs.umd.edu/~abadi/papers/abadi-pacelc.pdf), IEEE Computer, 2012. Free PDF on the author's site.
