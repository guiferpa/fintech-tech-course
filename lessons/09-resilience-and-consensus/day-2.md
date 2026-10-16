# Module 9, Tuesday: overload, backlogs and consensus

[Module 9](../../modules/09-resilience-and-consensus.md) · [Leia em português](day-2.pt-BR.md)

**Reading time:** about 45 minutes. Use the rest of the 2-hour block on the references at the end. Keep the [Raft visualization](https://raft.github.io/) open while you read sections 5 to 7.

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

*Main source: Martin Kleppmann, "Distributed Systems" lecture notes (University of Cambridge), section 6.1, as presented in the course's printable slides.*

In Module 1 you saw that a single leader gives you a total order: all writes go through one node, which decides their order, and replicas apply them in that order. That's how a Postgres primary works. But the leader is a single point of failure. When it dies, someone must pick a new one.

Kleppmann describes the two options:

- **Manual failover**: an operator picks a new leader and reconfigures every node. Common in databases and fine for planned maintenance, but unplanned outages last as long as it takes a human to wake up and act.
- **Automatic failover**: the nodes elect a new leader themselves. This is where consensus comes in.

Traditionally, **consensus** means several nodes agreeing on one value. Kleppmann shows that agreeing on "the next message to deliver", over and over, gives you total order broadcast, and that the two problems are formally equivalent. The well-known algorithms are Paxos (with Multi-Paxos for a sequence of values), Raft, Viewstamped Replication and Zab.

Two limits frame what these algorithms can do:

- **FLP result.** The slides state: "There is no deterministic consensus algorithm that is guaranteed to terminate in an asynchronous crash-stop system model." So Paxos and Raft assume a **partially synchronous, crash-recovery** model (Module 1, section 4).
- **Clocks for liveness only.** They use timeouts to detect a failed leader and make progress, but their **safety** never depends on timing. A wrong timeout can cause an unnecessary election; it can't cause two different committed histories.

The danger to avoid is **split brain**: two nodes acting as leader at the same time, each accepting writes. For a ledger, that means two divergent histories of postings and, after the partition heals, no correct balance.

## 6. Raft leader election

*Main source: Diego Ongaro and John Ousterhout, "In Search of an Understandable Consensus Algorithm" (the Raft paper), sections 5.1, 5.2 and 5.6. Kleppmann's notes, section 6.2, cover the same algorithm.*

A Raft cluster typically has five servers, which tolerates two failures. Each server is in one of three states:

| State | Role | Becomes |
| --- | --- | --- |
| **Follower** | Passive; answers requests from leaders and candidates | Candidate, if it hears nothing from a leader for an election timeout |
| **Candidate** | Asks for votes | Leader with a majority of votes; follower if it sees a valid leader or a newer term |
| **Leader** | Handles all client requests, replicates the log, sends heartbeats | Follower, if it sees a higher term |

Time is divided into numbered **terms**. Each term starts with an election. Servers include their term in every message; a server that sees a higher term updates its own and, if it was a leader or candidate, steps down to follower. Raft needs only two RPCs: `RequestVote` (sent by candidates) and `AppendEntries` (sent by the leader to replicate entries, and empty as a heartbeat).

An election goes like this:

1. A follower's election timeout expires without a heartbeat.
2. It increments its term, becomes a candidate, votes for itself and sends `RequestVote` to everyone.
3. Each server votes for at most one candidate per term, first come, first served, and only if the candidate's log is at least as up to date as its own (section 5.4).
4. A candidate with votes from a majority of the full cluster becomes leader and starts sending heartbeats.
5. If the vote splits, the term ends with no leader, and a new election starts after another timeout.

The paper's key guarantee: "Raft ensures that there is at most one leader in a given term." It follows from majorities: two candidates can't both get votes from a majority in the same term, because any two majorities share at least one server, and that server votes only once.

To make split votes rare, Raft **randomizes election timeouts**, for example between 150 and 300 ms, so usually one server times out first and wins before the others wake up. Section 5.6 gives the timing requirement: broadcast time much smaller than the election timeout, which is much smaller than the mean time between failures. The paper's numbers: broadcast time of 0.5 to 20 ms, election timeout somewhere between 10 and 500 ms, and server MTBF of several months or more.

What Raft can't prevent, as Kleppmann's slides note, is two leaders from *different* terms existing at once: an old leader cut off by a partition may not know it has been replaced. That's why a leader must hear from a majority before a write counts. The old leader can't reach a majority, so nothing it accepts is ever committed. Module 3's fencing tokens apply the same idea (a higher term wins) to locks.

## 7. Raft log replication

*Main source: Ongaro and Ousterhout, the Raft paper, sections 5.3 and 5.4.*

Once elected, the leader turns client commands into log entries:

1. The leader appends the command to its log, tagged with the current term and index.
2. It sends `AppendEntries` to all followers in parallel.
3. When a majority has stored the entry, it is **committed**. The leader applies it to its state machine and answers the client. Committing an entry also commits every entry before it.
4. Followers learn the commit index from later `AppendEntries` and apply the entries in order.

Each `AppendEntries` carries the index and term of the entry just before the new ones. A follower that doesn't have that entry rejects the request, and the leader steps back (decrementing its `nextIndex` for that follower) until it finds the point where both logs agree. Then it overwrites the follower's conflicting entries. This consistency check keeps the **Log Matching** property.

Section 5.4 adds two safety rules. First, the **election restriction**: a candidate can't win unless its log is at least as up to date as a majority (compared by the term of the last entry, then by length), so a new leader always holds every committed entry. Second, a leader never decides that an entry from an *earlier* term is committed just by counting replicas; it commits an entry from its own term, which commits the older ones with it. The paper's Figure 8 shows the scenario that makes this rule necessary.

Figure 3 of the paper lists the properties Raft guarantees:

| Property | Meaning |
| --- | --- |
| Election Safety | At most one leader per term |
| Leader Append-Only | A leader never overwrites or deletes its own entries |
| Log Matching | Same index and term means the same entry and the same history before it |
| Leader Completeness | A committed entry is present in every later leader's log |
| State Machine Safety | No two servers apply different entries at the same index |

Where does this meet your wallet? You will not implement Raft. You use it: etcd is built on Raft, and tools like Patroni use a store such as etcd to decide which Postgres node is primary; Kafka's KRaft mode uses a Raft-based controller quorum. When an interviewer asks how failover avoids two primaries, the answer is a majority vote with terms, and a write that only counts after a majority has it. The cost is latency: every committed write waits for a majority round trip, which is cheap inside one region and expensive across continents. Tomorrow's active-active discussion depends on that.

## Notes to write today

1. What a queue backlog does to recovery time (the one-hour outage example), and which wallet messages you may delay, sideline or drop, and which you must never drop.
2. Load shedding vs. rate limiting: what each protects, what you shed first, and the token bucket in five lines.
3. Why consensus is needed: manual vs. automatic failover, split brain, and the FLP result in one sentence.
4. How Raft elects a leader: states, terms, the voting rules, and why randomized timeouts matter.
5. How Raft replicates and commits a log entry, and why a cut-off old leader can't commit anything.

## Check yourself

These make good flashcards (see the [flashcards guide](../../FLASHCARDS.md)).

- What is the difference between throughput and goodput?
- Why should a server answer its health check even when it is shedding load?
- Why is the age of the oldest message a better alarm than queue depth?
- What does a token bucket store per client, and what makes it safe across many pods?
- Why can't two Raft leaders be elected in the same term?
- When is a Raft log entry committed?
- Why do consensus algorithms use clocks only for liveness, not safety?

## References

- **Main source:** David Yanacek, ["Avoiding insurmountable queue backlogs"](https://aws.amazon.com/builders-library/avoiding-insurmountable-queue-backlogs/), Amazon Builders' Library, 2019. Read it all, especially the strategies for multitenant systems. Free.
- **Main source:** David Yanacek, ["Using load shedding to avoid overload"](https://aws.amazon.com/builders-library/using-load-shedding-to-avoid-overload/), Amazon Builders' Library, 2019. Read it all. Free.
- **Main source:** Martin Kleppmann, ["Distributed Systems" lecture notes](https://www.cl.cam.ac.uk/teaching/2122/ConcDisSys/dist-sys-notes.pdf), University of Cambridge, 2021/22, chapter 6 (Consensus: 6.1 Introduction and 6.2 Raft). Free, Creative Commons BY-SA. The same material is in the [printable slides](https://www.cl.cam.ac.uk/teaching/2122/ConcDisSys/dist-sys-handout.pdf), and the matching videos are linked from the [course materials page](https://www.cl.cam.ac.uk/teaching/2122/ConcDisSys/materials.html).
- **Main source:** Diego Ongaro and John Ousterhout, ["In Search of an Understandable Consensus Algorithm (Extended Version)"](https://raft.github.io/raft.pdf), the Raft paper. Read section 5 (5.1 to 5.6) and Figure 3; Figure 2 is a one-page summary of the whole algorithm. Free.
- [The Raft Consensus Algorithm](https://raft.github.io/) site, with an interactive visualization. Stop a leader, watch an election, and partition the cluster. Free.
