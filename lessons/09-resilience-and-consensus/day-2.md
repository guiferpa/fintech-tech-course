# Module 9, Tuesday: overload, backlogs and consensus

[Module 9](../../modules/09-resilience-and-consensus.md) · [Leia em português](day-2.pt-BR.md)

**Reading time:** about 45 minutes. Use the rest of the 2-hour block on the references at the end. Keep the [Raft visualization](https://raft.github.io/) open while you read sections 6 and 7.

This is an original text written for this course. It is based on the references listed at the end, and each section names the source it follows. Where an idea comes from a specific author, the text says so.

## Why this matters for a fintech

Yesterday was about protecting your service from a slow dependency. Today flips the view: what happens when *you* are the one receiving too much work? Payday, a Black Friday campaign, or a partner that comes back after an outage and replays every webhook at once. A service that tries to accept everything ends up serving nobody.

The second half of the day answers the bonus question of the mastery test: where does consensus come in? Every time a database fails over to a new primary, or Kafka picks a new partition leader, some algorithm decides who the leader is. If two nodes both believe they are the leader of your ledger, you get two versions of a balance. Raft is the algorithm that prevents that, and you rely on it more often than you think.

## 1. Throughput is not goodput

*Main source: David Yanacek, Amazon Builders' Library, "Using load shedding to avoid overload", the parts on the anatomy of overload.*

Yanacek separates two numbers that look the same on a dashboard:

- **Throughput**: all requests per second the server receives.
- **Goodput**: the part of those requests the server answers without error *and* fast enough for the client to use the answer.

As load rises, latency first grows slowly, then sharply past an inflection point, because of contention for threads, CPU, garbage collection and I/O. Once server latency passes the client's timeout, the server is still busy (throughput is high) but every answer arrives after the client gave up (goodput is zero). Yanacek gives a simple rule of thumb: when median latency equals the client timeout, half the requests time out, so availability is 50%.

That wasted work feeds itself. Clients that timed out retry, which adds load, which raises latency, which causes more timeouts. Yesterday's 243x retry amplification is the same loop seen from the other side.

## 2. Load shedding

*Main source: Yanacek, "Using load shedding to avoid overload", the parts on load shedding, prioritization and deadlines.*

The core idea fits in one sentence from the article: "When a server approaches overload, it should start rejecting excess requests so that it can focus on the requests it decides to let in." Rejecting 20% of requests quickly keeps the other 80% fast. Accepting all of them makes 100% slow.

Practical points from the article, with wallet examples:

- **Shed early and cheaply.** Rejecting a request also costs resources, so reject before parsing the body, opening a transaction or calling anything downstream. Yanacek also warns about expensive rejections, for example logging a full stack trace for every rejected request.
- **Prioritize.** His top priority is the load balancer's health check: if the server is too busy to answer it, the load balancer removes it, and the remaining servers get even more load. After that, he suggests finishing work already started before accepting new work (for example, favoring `end()` over `start()` calls, or later pages over first pages). In a wallet: confirming a transfer the customer already authorized ranks above starting a new one, and both rank above a search for old statements.
- **Respect deadlines.** If the client already gave up, finishing the work is waste. Clients can send how long they will wait, and each service passes the remaining time to the next one. Check the deadline after taking a request off any internal queue, not only on arrival.
- **Measure honestly.** Exclude fast rejections from latency metrics: Yanacek notes that a service shedding 60% of traffic can show a deceptively good median. Record who was rejected and for which operation, and aim for zero rejections when capacity is available.

A minimal concurrency limiter in a NestJS middleware might look like this:

```typescript
@Injectable()
export class ShedMiddleware implements NestMiddleware {
  private inFlight = 0;
  private readonly max = Number(process.env.MAX_IN_FLIGHT ?? 200);

  use(req: Request, res: Response, next: NextFunction) {
    if (req.path === '/health') return next();      // never shed health checks
    const deadline = Number(req.header('x-deadline-ms')); // absolute epoch ms, if sent
    if (this.inFlight >= this.max || (deadline && Date.now() > deadline)) {
      res.status(503).set('Retry-After', '1').end(); // cheap, early rejection
      return;
    }
    this.inFlight++;
    res.on('close', () => this.inFlight--);
    next();
  }
}
```

An absolute deadline needs reasonably synchronized clocks across hosts; Yanacek mentions this trade-off, and the alternative of sending a duration measured with a monotonic clock (Module 1).

## 3. Rate limiting per client

*Main source: Yanacek, "Using load shedding to avoid overload", the part on throttling; and the "Avoiding insurmountable queue backlogs" article on fairness.*

Load shedding protects the server as a whole. **Rate limiting** (or throttling) protects clients from each other. In a multitenant service, one integration partner sending a burst must not slow down every other customer. Both Amazon articles describe per-customer limits with some burst allowance, and Yanacek adds that requests above the quota can still be accepted when there is spare capacity, but at a lower priority than requests within quota.

The usual algorithm is the **token bucket**. Each client has a bucket with a capacity (the burst size) that refills at a fixed rate (the sustained limit). Each request takes one token; with no tokens left, the request is rejected with HTTP 429. The state per client is just two numbers: tokens and the time of the last refill.

```text
on request(client):
  elapsed = now - last_refill
  tokens  = min(capacity, tokens + elapsed * refill_rate)
  last_refill = now
  if tokens >= 1: tokens -= 1; allow
  else: reject 429 with Retry-After
```

In a fleet of API pods, that state has to live in a shared store, and the read-modify-write must be atomic, or two pods will both see the last token. That is Thursday's capstone item 3 (token bucket in Redis), and you'll design the atomic step yourself. Rate limits in a wallet are often per customer *and* per operation: for example, a tighter limit on Pix key lookups (a known enumeration target) than on balance reads.

## 4. Queue backlogs

*Main source: David Yanacek, Amazon Builders' Library, "Avoiding insurmountable queue backlogs".*

Queues look like the cure for overload: the producer writes a message and moves on, and workers catch up later. Yanacek shows the hidden cost. A queue-based system is **bimodal**. With no backlog it is fast. After an outage or a spike, messages arrive faster than they are processed, and end-to-end latency keeps growing. A synchronous service drops requests during an outage but recovers instantly. An asynchronous service keeps all that work and must chew through it afterwards.

His arithmetic is worth memorizing. After a one-hour outage, you need about double your normal capacity for another hour to catch up, while new work keeps arriving. If a spike puts 10 times the consumer's capacity into the queue, draining it takes hours. And by the time old messages are processed, the result may be useless: a "your transfer arrived" push notification three hours late is noise.

Strategies the article describes, and how they map to a wallet:

| Strategy | Idea | Wallet example |
| --- | --- | --- |
| Separate queues per workload | Isolation, like a bulkhead | One queue per partner bank; settlements separate from notifications |
| Shuffle sharding | Each customer hashes to a few queues out of a pool | Large merchants can't block small ones |
| Spillover queue | Traffic above a customer's rate goes to a second queue | A merchant's bulk payout file doesn't delay retail transfers |
| Sideline old messages | Messages older than X go to a backlog queue, processed after the live queue catches up | Fresh webhooks first, old ones later |
| Drop old messages (TTL) | Safe when a periodic full sync will fix the state anyway | Balance cache refresh events, never ledger postings |
| Backpressure | Tell producers to slow down when the backlog grows | Return 429 to a partner replaying webhooks |
| Dead-letter queue | Messages that keep failing go aside, with an alarm | A posting that violates a constraint |
| Heartbeats | Long jobs extend their lease so no second worker picks them up | A statement PDF job that takes minutes |

The rule for money: **you may reorder, delay or sideline money movements, but never drop them.** Dropping is only for work that is recomputable or worthless when late.

For monitoring, Yanacek recommends **the age of the oldest message** (or the age at first processing attempt) as the main signal, rather than queue depth or consumer errors. Depth doesn't tell you whether you are two seconds or two hours behind. He also uses Little's law to show the threads trap: 100 messages per second at 100 ms each needs about 10 workers, but if processing slows to 10 s, you would need about 1,000.

## 5. Why consensus is needed

*Main sources: Marc Brooker, Amazon Builders' Library, "Leader election in distributed systems"; etcd documentation, "FAQ".*

In Module 1 you saw that a single leader gives you a total order: all writes go through one node, which decides their order, and replicas apply them in that order. That's how a Postgres primary works. Brooker's article lists why teams like leaders: they make systems easier to reason about and can give clients strong consistency. It is just as direct about the cost: "A single leader is a single point of failure." When the primary dies, someone must pick a new one.

A human can pick the new primary, but then an unplanned outage lasts until someone wakes up. The alternative is automatic election. Brooker describes the usual Amazon approach, **leases**: "a single database that stores the current leader", and a leader that must heartbeat periodically to keep the role. He notes that DynamoDB and ZooKeeper offer lease-based locking clients for this. The store holding the lease must itself survive failures, and stores like etcd and Consul get that from Raft.

The danger is **split brain**: two nodes acting as leader at once, each accepting writes. For a ledger, that means two divergent histories of postings. Brooker warns that a garbage collection pause between checking a lease and doing the work can make an old leader act after losing the role, so check the lease right before side effects and let the database reject a second leader (Module 3's fencing idea).

The etcd FAQ explains the defense: a cluster works only while a majority of members (a quorum) can talk to each other, a model that "totally avoids any possibility of split brain inconsistency". Any two majorities share at least one member, so two groups can never both have a quorum.

Two practical consequences, both in the FAQ:

| Members | Quorum | Failures tolerated |
| --- | --- | --- |
| 1 | 1 | 0 |
| 3 | 2 | 1 |
| 4 | 3 | 1 |
| 5 | 3 | 2 |
| 7 | 4 | 3 |

- **Use an odd number of members.** A 4-member cluster tolerates the same single failure as a 3-member one, with one more machine to pay for. During a network partition, an odd number guarantees there is always a majority side.
- **Do not grow too big.** The FAQ says a cluster "probably should have no more than seven nodes", because every write must be replicated to more machines. Consul's documentation gives the same advice in its own words: 3 or 5 servers for production.

## 6. Raft leader election, as etcd and CockroachDB run it

*Main sources: HashiCorp Consul documentation, "Consensus"; Cockroach Labs documentation, "Replication Layer"; etcd documentation, "Tuning", "Failure modes" and "etcd API".*

The Consul documentation describes Raft in a few sentences that are enough to follow an election. Every node starts as a **follower**. If a follower receives nothing from a leader for some time, it promotes itself to **candidate** and asks the other members for votes. A candidate that gets a quorum of votes becomes the **leader**. The leader accepts new log entries and replicates them to the followers.

Two timers drive this, and etcd's "Tuning" page gives real numbers:

- **Heartbeat interval.** How often the leader tells followers it is alive. The etcd default is 100 ms, and the page recommends setting it around the round-trip time between members.
- **Election timeout.** How long a follower waits without hearing from the leader before it starts an election. The etcd default is 1,000 ms, and the page says it must be at least 10 times the round-trip time to absorb network variance. A higher value takes longer to detect a dead leader; a lower heartbeat sends unnecessary messages.

```sh
etcd --heartbeat-interval=100 --election-timeout=500   # values in milliseconds
```

If every follower used exactly the same timeout, they would all start elections at the same moment and split the vote. CockroachDB's "Replication Layer" page shows the standard fix: followers become candidates "after randomized election timeouts", with the timeout multiplied by a random factor between 1 and 2 "to avoid election ties". Usually one follower times out first and wins before the others wake up. The visualization on the Raft website lets you watch elections like this one.

Each election starts a new **term**, a number that identifies one period of leadership. etcd shows it to clients: every response header carries a `raft_term` field, and the etcd API page says applications can use it to tell when the cluster has finished electing a new leader. A message from an older term is a message from a leader that has already been replaced.

What does a failover cost your application? etcd's "Failure modes" page answers concretely:

- When the leader fails, "it takes about an election timeout to elect a new leader". With the defaults, that is about a second.
- Write requests sent during the election are queued until a new leader exists.
- Writes already sent to the old leader but not yet committed may be lost, but "no committed writes are ever lost".

That is the contract to remember: timeouts affect how fast the cluster recovers, never whether a committed write survives. The Raft website says the same: when too many servers fail, the cluster stops making progress, "but will never return an incorrect result".

## 7. Log replication, partitions and where you meet Raft

*Main sources: HashiCorp Consul documentation, "Consensus"; etcd documentation, "Failure modes" and "etcd API"; Cockroach Labs documentation, "Replication Layer"; Patroni documentation.*

Once elected, the leader turns each client command into a **log entry**. Consul's documentation gives the commit rule: "An entry is considered committed when it is durably stored on a quorum of nodes." Only then is it applied to the state machine (the key-value store, in etcd's case). Snapshots compact the log, and CockroachDB's documentation adds that a lagging node loads a snapshot and replays the Raft log to catch up.

Now partition a 5-member cluster into a group of 3 and a group of 2, with the old leader on the small side. etcd's "Failure modes" page describes what happens:

1. The majority side elects a new leader and becomes the available cluster.
2. The minority side is unavailable. Its leader steps down.
3. When the partition heals, the minority side recognizes the new leader and recovers its state.

The old leader cannot commit anything during the partition, because it cannot reach a quorum. Consul says the same: if a quorum is unavailable, no new logs can be committed. That is why the cut-off leader is harmless.

Reads have a choice too. The etcd API page says reads are linearizable by default, while a serializable read is served locally by any member: faster, but possibly stale. A balance check before a debit needs the first; a dashboard can live with the second.

Where does this meet your wallet? You will not implement Raft; you use it. etcd runs on it (and Kubernetes stores its state in etcd), and Patroni, a high-availability tool for Postgres, relies on a store such as etcd, Consul, ZooKeeper or Kubernetes to decide which Postgres node is primary. When an interviewer asks how failover avoids two primaries, the answer is a majority vote with terms, and a write that only counts after a majority has it. The cost is latency: every committed write waits for a quorum round trip, which is cheap inside one region and expensive across continents. The etcd FAQ notes this trade-off for clusters spread across regions, and tomorrow's active-active discussion depends on it.

## Notes to write today

1. What a queue backlog does to recovery time (the one-hour outage example), and which wallet messages you may delay, sideline or drop, and which you must never drop.
2. Load shedding vs. rate limiting: what each protects, what you shed first, and the token bucket in five lines.
3. Why consensus is needed: single leader as single point of failure, leases, split brain, and the quorum table with why clusters use odd sizes.
4. How a Raft election works in etcd: follower, candidate, leader, terms, the two timers with their default values, and why timeouts are randomized.
5. When a log entry is committed, what each side of a partition does, and what a failover costs your writes (queued, uncommitted ones may be lost, committed ones never).

## Check yourself

These make good flashcards (see the [flashcards guide](../../FLASHCARDS.md)).

- What is the difference between throughput and goodput?
- Why should a server answer its health check even when it is shedding load?
- Why is the age of the oldest message a better alarm than queue depth?
- What does a token bucket store per client, and what makes it safe across many pods?
- Why does a 4-member etcd cluster tolerate no more failures than a 3-member one?
- When is a Raft log entry committed?
- What happens to writes sent to etcd during a leader election?
- Why do Raft implementations randomize the election timeout?

## References

- **Main source:** David Yanacek, ["Avoiding insurmountable queue backlogs"](https://aws.amazon.com/builders-library/avoiding-insurmountable-queue-backlogs/), Amazon Builders' Library, 2019. Read it all, especially the strategies for multitenant systems. Free.
- **Main source:** David Yanacek, ["Using load shedding to avoid overload"](https://aws.amazon.com/builders-library/using-load-shedding-to-avoid-overload/), Amazon Builders' Library, 2019. Read it all. Free.
- **Main source:** Marc Brooker, ["Leader election in distributed systems"](https://aws.amazon.com/builders-library/leader-election-in-distributed-systems/), Amazon Builders' Library, 2019. Read it all: why leaders, leases, and the stale-leader problem. Free.
- **Main source:** etcd documentation, ["FAQ"](https://etcd.io/docs/v3.6/faq/) and ["Failure modes"](https://etcd.io/docs/v3.6/op-guide/failures/). In the FAQ, read the questions on cluster size, failure tolerance, odd numbers and disk latency. "Failure modes" is short; read it all. Free.
- etcd documentation, ["Tuning"](https://etcd.io/docs/v3.6/tuning/). Read the time parameters: heartbeat interval and election timeout. Free.
- HashiCorp Consul documentation, ["Consensus"](https://developer.hashicorp.com/consul/docs/concept/consensus). A one-page Raft overview from a product that runs it, with the deployment table. Free.
- Cockroach Labs documentation, ["Replication Layer"](https://docs.cockroachlabs.com/docs/stable/architecture/replication-layer). Read the Raft section: Raft groups, randomized election timeouts, and snapshots. Free.
- Patroni documentation, ["Introduction"](https://patroni.readthedocs.io/en/latest/). Optional: skim the first page to see which stores (etcd, Consul, ZooKeeper, Kubernetes) a real Postgres failover tool relies on. Free.
- [The Raft Consensus Algorithm](https://raft.github.io/) site, with an interactive visualization of five servers and their logs: watch an election and log replication happen. The site also links to [The Secret Lives of Data](http://thesecretlivesofdata.com/raft/), a more guided, less interactive walkthrough of the same algorithm. Free.
