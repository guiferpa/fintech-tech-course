# Module 1, Monday: failures, timeouts and time

[Module 1](../../modules/01-distributed-systems-fundamentals.md) · [Leia em português](day-1.pt-BR.md)

**Reading time:** about 45 minutes. Use the rest of the 2-hour block on the references at the end, starting with the sections marked as the main source.

This is an original text written for this course. It is based on the references listed at the end, and each section names the source it follows. Where an idea comes from a specific author or company, the text says so.

## Why this matters for a fintech

A payment system is a distributed system from the first line of code. Your API talks to a database, the database replicates to another machine, a worker calls a partner bank, and the partner bank calls the card network or Pix. Every arrow in that drawing is a network call, and every network call can fail in ways a function call on one machine cannot.

The most expensive bugs in payments come from one confusion: treating "I didn't get an answer" as "it didn't happen". This lesson is about why those two are different and what to do about it, using how Amazon, Google, Cloudflare and Cockroach Labs describe the problem in their own engineering material.

## 1. What makes a system distributed

*Main source: AWS Builders' Library, "Challenges with distributed systems" (Jacob Gabrielson).*

A distributed system is a set of computers that cooperate over a network to do one job. They share no memory. The only way one machine learns anything about another is by receiving a message from it.

Gabrielson, a senior principal engineer at AWS, separates offline systems (batch jobs, which get the benefits of distribution with almost none of the pain), soft real-time systems (which keep producing results within a generous window) and **hard real-time** systems, which must answer unpredictable requests quickly. His examples of the last kind include every AWS API and **payments**. Your wallet is the hard kind. The key phrase in the article is that the client, the server and the network do not "share fate". On one machine, a program either works or the whole machine is down. Across a network, the server can crash while the client keeps running, or the network can drop a message while both machines are healthy. Jeff Hodges, in his essay for engineers new to the field, puts the same idea as the thing that sets distributed systems apart: they fail often, and they fail **partially**. Some parts work while others don't, and nobody has the full picture.

## 2. One call, eight ways to fail

*Main source: AWS Builders' Library, "Challenges with distributed systems".*

The article takes a single request and reply and breaks it into the eight steps that happen on the happy path:

1. **Post request**: the client puts the message on the network.
2. **Deliver request**: the network carries it to the server.
3. **Validate request**: the server checks that the message makes sense.
4. **Update server state**: the server does the work.
5. **Post reply**: the server sends the answer.
6. **Deliver reply**: the network carries it back.
7. **Validate reply**: the client checks the answer.
8. **Update client state**: the client records the result.

Each step can fail on its own: the network drops the request, the server crashes right after receiving it, the server rejects a corrupted or incompatible message, the database write fails, the network card dies while sending the reply, the reply is lost, the client can't parse it, or the client crashes before saving it. Gabrielson calls these the "eight failure modes of the apocalypse".

Map them onto a transfer to the partner bank. If the failure is in steps 1 to 3, no money moved. If it is in steps 5 to 8, **the partner already debited the customer** and you never learned it. From your side, all of them look the same: no usable answer.

The article also warns that distributed bugs are often latent: one can sit in production for months until the right mix of failures triggers it. One of his stories is about a catalog server whose disk filled up. It started returning empty responses very quickly, the load balancer took "fast" as "healthy" and sent it most of the traffic, and the website went down. A failure on one machine spread through the network.

Hodges recommends the classic "two generals" puzzle as a way to feel this: two parties on a channel that loses messages can never both be certain they agree, however many confirmations they exchange.

## 3. The three outcomes of a timeout

*Main source: AWS Builders' Library, "Challenges with distributed systems".*

Gabrielson's banking example is the whole lesson in a few lines. On one machine, `account.withdraw(amount)` returns either `SUCCESS` or `INSUFFICIENT_FUNDS`. Across a network, there is a third result, `UNKNOWN`, and his code literally answers it with `WHAT_THE_FARG?`. In his words, a timeout means the result "is UNKNOWN. It may or may not have happened", and "the client must handle UNKNOWN correctly".

When the timeout fires on your call to the partner bank, there are three possible situations, and you can't tell them apart from your side:

1. **The request never arrived.** Nothing happened. Retrying is safe.
2. **The request arrived and was processed, but the response was lost or late.** The effect happened. Retrying without protection does it twice.
3. **The request arrived and is still being processed**, or is stuck in a queue. The effect may happen after you give up.

So a timeout gives you a third state besides success and failure. In this course's capstone, a transfer whose call to the partner bank times out goes to `UNKNOWN`, never to `FAILED`. A job then asks the partner what happened and moves it to `COMPLETED` or `FAILED` based on the answer:

```ts
switch (result.kind) {
  case 'success':  return markCompleted(transfer);
  case 'rejected': return markFailed(transfer, result.reason); // definitive answer
  case 'timeout':  return markUnknown(transfer);              // ask the partner later
}
```

Marking it `FAILED` right away is the classic bug: the customer sees "failed", tries again, and is charged twice.

Unlike the two generals, payments can be fixed after the fact: you can **ask the partner for the status later**, and a mistaken charge can be refunded. Real payment systems are built around status queries and reconciliation, not the hope that every call returns. The rule for today: **a timeout means "I don't know", and your data model must be able to say "I don't know".**

## 4. Choosing timeouts and retrying safely

*Main source: AWS Builders' Library, "Timeouts, retries, and backoff with jitter".*

A companion article in the same library explains how Amazon actually picks numbers. A team first decides what rate of **false timeouts** it accepts (timing out a call that would have succeeded), for example 0.1%, and then sets the timeout to the matching latency percentile of the service it calls, in that case the p99.9. If the partner bank answers 99.9% of calls within 1.8 seconds, a 2-second timeout wrongly gives up on about one call in a thousand.

The trade-off cuts both ways:

- Too short, and you turn slow successes into `UNKNOWN`s, retry them, and add load exactly when the partner is struggling.
- Too long, and customers and threads wait on a call that is never coming back.

The article's points about retries apply directly to payments:

- **Retries are "selfish".** A client that retries takes more of the server's capacity to improve its own odds. If every client does it during an incident, the retries become the incident.
- **Retries need idempotency.** Retrying a call with side effects is only safe if the API is idempotent. Amazon EC2 does this with a client token sent on each request, so the same request sent twice is executed once. Stripe's idempotency keys, which you'll study in Module 2, are the same idea.
- **Back off exponentially and add jitter.** Wait longer after each attempt, cap the wait, and add a random amount so thousands of clients don't retry at the same instant.
- **Retry at one layer.** If the app, the HTTP client and the load balancer each make up to three attempts, one user click can become 27 calls. Pick a single place in the stack.

## 5. Detecting failures, availability and SLOs

*Main sources: Apache Cassandra documentation, "Dynamo" (failure detection section), and Google, "Site Reliability Engineering", chapter 4 "Service Level Objectives".*

Since you can't see another machine directly, you **detect failure with timeouts and heartbeats**. A real example is Apache Cassandra. Every node exchanges heartbeat information through gossip and runs a variant of the phi accrual failure detector, which judges each peer by how its heartbeats are arriving. When a peer looks dead, it is "convicted" and reads stop going to it, while writes meant for it are stored as hints to replay later. The documentation stresses that "UP and DOWN state are local node decisions". Two nodes can disagree about whether a third is alive, and neither is wrong from what it can see. A slow node and a dead node look the same from outside; a failure detector can only suspect.

The catalog server story from section 2 shows the opposite trap: a check that measures only "answers fast" can call a broken node the healthiest one.

**Availability** is the fraction of time a service works correctly. The "nines" give a feel for it:

| Availability | Downtime per year |
| --- | --- |
| 99% | about 3.7 days |
| 99.9% | about 8.8 hours |
| 99.99% | about 53 minutes |
| 99.999% | about 5.3 minutes |

Google's SRE book defines the vocabulary you'll use in Module 10:

- A **service level indicator (SLI)** is a carefully defined measurement, such as the fraction of transfer requests that succeed, or their latency.
- A **service level objective (SLO)** is a target for an SLI, such as "99.9% of `POST /transfers` requests answer successfully within 300 ms over 30 days".
- A **service level agreement (SLA)** is a contract with consequences for missing the SLO. The book's test: if nothing happens when you miss it, it's an SLO, not an SLA.

The book also argues that 100% is the wrong target. Its example is Chubby, Google's lock service, which was so reliable that other teams depended on it as if it could never fail, so when a quarter goes by without a real outage, the SRE team causes a controlled one to expose those hidden dependencies early. For a wallet, the lesson is that your partner bank will be down at some point, and your design has to assume it.

## 6. Clocks you can't trust

*Main sources: Cloudflare blog, "How and why the leap second affected Cloudflare DNS" (John Graham-Cumming), the chrony documentation, and Cockroach Labs, "Clock Management in CockroachDB".*

Every server has its own clock, and every clock drifts. The chrony time daemon, which Cockroach Labs recommends for its database, reports the drift rate as a frequency in parts per million: 1 ppm means the clock gains a microsecond every second. Servers correct their clocks against time servers with NTP, and in the cloud you usually sync to the provider's service; AWS, for example, runs the Amazon Time Sync Service, backed by satellite-connected and atomic reference clocks in each region.

How the correction is applied matters:

- **Slewing**: chrony's normal mode is to fix an offset gradually, by running the clock slightly faster or slower until it catches up.
- **Stepping**: jumping the clock to the right time at once. chrony's own documentation warns that "certain software will be seriously affected by such jumps", which is why it slews by default.

Leap seconds are the famous case. On 1 January 2017, at midnight UTC, a leap second hit Cloudflare's DNS software, written in Go. The code measured how long an upstream DNS server took to answer by subtracting a start time from `time.Now()`. During the leap second, the clock went back, the measured duration came out negative, a smoothed average of those durations went negative, and that value was passed to Go's `rand.Int63n()`, which panics on a negative argument. At peak, about 0.2% of Cloudflare's DNS queries failed, for several hours. Graham-Cumming names the root cause as "the belief that time cannot go backwards". Today, AWS and Google smear leap seconds over a longer period instead of inserting them at once, a point the Cockroach Labs article also makes.

Clocks also stop. The Cockroach Labs article explains that a cloud VM paused for live migration resumes with its clock behind by the length of the pause, and that CockroachDB shuts down a node whose clock drifts too far from the others rather than risk inconsistent reads.

This is why there are two kinds of clock in your programming language:

- A **time-of-day clock** (`Date.now()` in Node.js) tells you the date and time. It can jump when the clock is stepped or a leap second is applied. Use it for timestamps people read, never to measure how long something took.
- A **monotonic clock** (`process.hrtime.bigint()` or `performance.now()` in Node.js) only moves forward. The Node.js documentation says `process.hrtime` times are "relative to an arbitrary time in the past" and "not related to the time of day and therefore not subject to clock drift". The absolute value means nothing and can't be compared across machines, but the difference between two readings on one machine is a reliable duration. Use it for timeouts and latency.

```ts
const start = process.hrtime.bigint();
await partnerBank.createTransfer(req);
const elapsedMs = Number(process.hrtime.bigint() - start) / 1e6; // never negative
```

## 7. Ordering events without wall clocks

*Main sources: Cockroach Labs, "Living without atomic clocks" (Spencer Kimball and Irfan Sharif), the PostgreSQL documentation, "Sequence Manipulation Functions", and Cybertec, "Gaps in sequences in PostgreSQL" (Laurenz Albe).*

If clocks drift, jump and stop, comparing timestamps from two machines can put events in the wrong order. The Cockroach Labs article gives a concrete case it calls **causal reverse**. Node N1 has an accurate clock and node N2's clock is 100 ms behind. Transaction T1 commits on N1 at timestamp 150 ms. About 50 ms later, someone who saw T1 finish starts T2 on N2, and N2 stamps it 100 ms. Anyone ordering by timestamp now sees T2 before T1, even though T2 started after T1 finished. The article puts typical NTP synchronization at somewhere between 100 and 250 ms, and describes how databases go to great lengths to avoid this (Spanner waits out a 7 ms clock uncertainty on every commit). Your application code should not try to compete with them.

Translate that into wallet rules:

- Never decide which of two events on different machines came first by comparing their wall-clock timestamps.
- Never let "last write wins by timestamp" decide a balance.
- Always measure timeouts with a monotonic clock.

So where does order come from? From **a single authority** that every writer must go through. For a ledger, that authority is the database that holds the account.

A Postgres `bigserial` id looks like an order, but the PostgreSQL documentation explains why it isn't a reliable one. A value taken with `nextval` "is not reclaimed for re-use if the calling transaction later aborts", so sequences have gaps, and they "cannot be used to obtain 'gapless' sequences". Albe's Cybertec article shows more ways to get gaps: cached values lost when a session ends, and jumps after a crash. And because a value is taken when `nextval` runs, not when the transaction commits, a transaction holding id 11 can commit before the one holding id 10. A sequence gives you unique ids, not commit order.

When you need a strict order per account, make the account row itself the authority. Albe's article builds a gapless counter from a single row updated in the transaction, and warns of the cost: it serializes every transaction that uses it. Per account, that cost is exactly what you want:

```sql
BEGIN;
-- Locks this account's row until COMMIT; concurrent writers to the same account wait.
UPDATE accounts SET last_seq = last_seq + 1
 WHERE id = $1
RETURNING last_seq;                       -- e.g. 42

INSERT INTO ledger_entries (account_id, seq, amount_cents, created_at)
VALUES ($1, 42, -5000, now());            -- created_at is for humans, seq is the order
COMMIT;
```

Entries of one account now have a gapless, strictly increasing `seq` decided by one authority, and `UNIQUE (account_id, seq)` makes any violation fail loudly. Transfers between different accounts don't block each other. In the capstone, the order of entries for an account comes from this kind of per-account sequence or from the database's commit order, never from `created_at`.

## Notes to write today

1. The 3 possible outcomes of a timeout (didn't arrive, happened but the answer was lost, still in progress), and what your system does in each.
2. How you will pick the timeout for the partner bank call, and where in your stack retries happen.
3. Why you can't order events by wall clock, with one concrete example from a payment flow, and how your ledger orders the entries of one account instead.

## Check yourself

These make good flashcards (see the [flashcards guide](../../FLASHCARDS.md)).

- Name three of the eight steps of a request and reply, and what a failure in each means for a transfer.
- Why can't a timeout tell a crashed server from a slow one?
- How does Amazon choose a timeout value, according to the Builders' Library?
- Why are retries "selfish", and what makes a retry of a payment safe?
- What is the difference between an SLO and an SLA?
- Which clock do you use to measure a timeout, and what went wrong at Cloudflare when the other one was used?
- Why is a Postgres sequence value not the commit order?

## References

- **Main source:** Jacob Gabrielson, AWS Builders' Library, ["Challenges with distributed systems"](https://aws.amazon.com/builders-library/challenges-with-distributed-systems/). Free. Read all of it; note the eight failure modes and the UNKNOWN outcome.
- Marc Brooker, AWS Builders' Library, ["Timeouts, retries, and backoff with jitter"](https://aws.amazon.com/builders-library/timeouts-retries-and-backoff-with-jitter/). Free. How Amazon picks timeouts and makes retries safe.
- Google, "Site Reliability Engineering", [chapter 4, "Service Level Objectives"](https://sre.google/sre-book/service-level-objectives/). Free. SLIs, SLOs, SLAs and the Chubby story.
- John Graham-Cumming, Cloudflare blog, ["How and why the leap second affected Cloudflare DNS"](https://blog.cloudflare.com/how-and-why-the-leap-second-affected-cloudflare-dns/), 2017. Free. A real outage caused by a clock going backward.
- Spencer Kimball and Irfan Sharif, Cockroach Labs blog, ["Living without atomic clocks"](https://www.cockroachlabs.com/blog/living-without-atomic-clocks/). Free. Clock skew, causal reverse and how a database copes.
- Apache Cassandra documentation, ["Dynamo"](https://cassandra.apache.org/doc/latest/cassandra/architecture/dynamo.html), section "Failure Detection". Free. How a real database decides a peer is down.
- Cockroach Labs blog, ["Clock Management in CockroachDB: Good Timekeeping is Key"](https://www.cockroachlabs.com/blog/clock-management-cockroachdb/) (Alex Entin). Free. Slewing, leap second smearing, VM pauses and the maximum clock offset.
- chrony documentation, ["chronyc"](https://chrony-project.org/doc/3.4/chronyc.html), entries `makestep` and `tracking`. Free. Slewing vs. stepping, and drift in ppm.
- PostgreSQL documentation, ["Sequence Manipulation Functions"](https://www.postgresql.org/docs/current/functions-sequence.html). Free. Read the caution box about gaps.
- Cybertec, ["Gaps in sequences in PostgreSQL"](https://www.cybertec-postgresql.com/en/gaps-in-sequences-postgresql/) (Laurenz Albe). Free. Why sequences have gaps and how to build a gapless counter.
- Jeff Hodges, ["Notes on Distributed Systems for Young Bloods"](https://www.somethingsimilar.com/2013/01/14/notes-on-distributed-systems-for-young-bloods/), 2013. A short practical essay; read it if time is left.
