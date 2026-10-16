# Module 1, Monday: failures, timeouts and time

[Module 1](../../modules/01-distributed-systems-fundamentals.md) · [Leia em português](day-1.pt-BR.md)

**Reading time:** about 45 minutes. Use the rest of the 2-hour block on the references at the end, starting with the sections marked as the main source.

This is an original text written for this course. It is based on the references listed at the end, and each section names the source it follows. Where an idea comes from a specific author, the text says so.

## Why this matters for a fintech

A payment system is a distributed system from the first line of code. Your API talks to a database, the database replicates to another machine, a worker calls a partner bank, and the partner bank calls the card network or Pix. Every arrow in that drawing is a network call, and every network call can fail in ways a function call on one machine cannot.

The most expensive bugs in payments come from one confusion: treating "I didn't get an answer" as "it didn't happen". This lesson is about why those two are different and what to do about it.

## 1. What makes a system distributed

*Main source: Kleppmann's lecture notes, section 1.1.*

A distributed system is a set of computers (nodes) that cooperate over a network to do one job. The nodes share no memory. The only way one node learns anything about another is by receiving a message from it.

That single fact creates the three problems this module keeps coming back to:

- **Messages can be lost or delayed**, and the sender cannot tell which.
- **Nodes can crash or pause**, and the others cannot tell a crashed node from a slow one.
- **Each node has its own clock**, and the clocks disagree.

A useful name for the first two is **partial failure**. On one machine, a program either works or the whole machine is down. In a distributed system, some parts work while others don't, and nobody has the full picture. The failures are also nondeterministic: the same request can succeed nine times and hang on the tenth.

## 2. The two generals problem

*Main source: Kleppmann's lecture notes, section 2.1.*

Two armies camp on opposite sides of a city. If both attack at the same time, they win; if only one attacks, it loses. The generals can only communicate by sending messengers through the city, and a messenger may be captured.

General 1 sends "attack at dawn". If no reply comes back, general 1 cannot know whether the message was lost or the reply was lost. So general 2 must reply, but then general 2 doesn't know whether the reply arrived, so general 1 must confirm the reply, and so on. **No finite number of messages makes both sides certain.** Certainty would require common knowledge, and messages over an unreliable channel cannot create it.

Kleppmann's notes apply this directly to payments. An online shop asks a payment service to charge a card, and the connection breaks before the answer arrives. The shop doesn't know whether the card was charged. The difference from the generals is that payments can be fixed after the fact: the shop can **ask the payment service for the status later**, and a charge made by mistake can be refunded. That is why real payment systems are designed around status queries and reconciliation rather than around the hope that every call returns.

## 3. The three outcomes of a timeout

When you call a remote service and the timeout fires, there are three possible situations, and you can't tell them apart from your side:

1. **The request never arrived.** Nothing happened. Retrying is safe.
2. **The request arrived and was processed, but the response was lost or late.** The effect happened. Retrying without protection does it twice.
3. **The request arrived and is still being processed**, or is stuck in a queue. The effect may happen after you give up.

So a timeout gives you a third state besides success and failure: **unknown**. In this course's capstone, a transfer whose call to the partner bank times out goes to `UNKNOWN`, never to `FAILED`. A job then asks the partner what happened and moves it to `COMPLETED` or `FAILED` based on the answer. Marking it `FAILED` right away is the classic bug: the customer sees "failed", tries again, and is charged twice.

What makes a retry safe is idempotency, the topic of Module 2. For now, the rule is: **a timeout means "I don't know", and your data model must be able to say "I don't know".**

## 4. System models: what we assume about the network, nodes and time

*Main source: Kleppmann's lecture notes, section 2.3.*

To reason about any algorithm, you first state what can go wrong. Kleppmann's notes describe a system model in three parts.

**Network.**

- *Reliable links*: a message arrives if and only if it was sent (it may arrive out of order).
- *Fair-loss links*: messages can be lost, duplicated or reordered, but if you keep retrying, one eventually gets through.
- *Arbitrary links*: an attacker can read, change, drop, forge or replay messages.

You can build a reliable link from a fair-loss link with **retries plus deduplication**, and TLS turns an arbitrary link into roughly a fair-loss one. Nothing, however, stops an attacker or a broken cable from blocking traffic for a long time. A long period of loss or delay between groups of nodes is a **network partition**.

**Nodes.**

- *Crash-stop*: a node that crashes never comes back.
- *Crash-recovery*: a node can crash and restart; it loses what was in memory and keeps what was on disk.
- *Byzantine*: a node can do anything, including lying.

Your services run in the crash-recovery model: a container dies and restarts, and whatever wasn't committed to Postgres is gone. Byzantine faults matter between organizations that don't trust each other, which is one reason payment messages between banks are signed.

**Timing.**

- *Synchronous*: message delay and processing speed have known upper bounds.
- *Partially synchronous*: the system behaves synchronously most of the time but can stop doing so for unknown periods.
- *Asynchronous*: no bounds at all.

Real systems are at best partially synchronous. Messages wait in queues, networks reconfigure, the operating system deschedules your process, and garbage collection can pause a Node.js or JVM process for hundreds of milliseconds. Kleppmann points out that **a paused node looks exactly like a crashed node** to everyone else, and when it wakes up it may act on information that is no longer true. Module 3 comes back to this with fencing tokens.

## 5. Detecting failures, availability and SLOs

*Main source: Kleppmann's lecture notes, section 2.4.*

Since you can't see another node directly, you **detect failure with timeouts**: if a node doesn't answer within some time, you suspect it crashed. In a partially synchronous system this detector will sometimes be wrong, labelling a slow node as dead. Kleppmann calls the best you can do an *eventually perfect failure detector*: it may make mistakes, but eventually it suspects exactly the nodes that crashed.

Choosing the timeout is a trade-off you will meet again in Module 9:

- Too short, and you declare healthy-but-slow nodes dead, trigger failovers you didn't need and add load at the worst moment.
- Too long, and customers wait while a dead node keeps receiving traffic.

**Availability** is the fraction of time a service works correctly. The "nines" give a feel for it:

| Availability | Downtime per year |
| --- | --- |
| 99% | about 3.7 days |
| 99.9% | about 8.8 hours |
| 99.99% | about 53 minutes |
| 99.999% | about 5.3 minutes |

A **service level objective (SLO)** is a measurable target such as "99.9% of transfer requests answer within 300 ms". A **service level agreement (SLA)** is a contract that includes an SLO and a penalty for missing it. A **fault** is one component going wrong; a **failure** is the whole system stopping. Fault tolerance means surviving a bounded number of faults, mainly by removing **single points of failure**. Module 10 turns SLOs into alerts.

## 6. Clocks you can't trust

*Main source: Kleppmann's lecture notes, sections 3.1 and 3.2.*

Every server has a quartz clock, and quartz drifts with temperature and age, typically up to about 50 parts per million. That is around 4 seconds a day if nothing corrects it. Servers correct their clocks with **NTP**, which asks time servers and estimates the offset.

NTP estimates the offset from four timestamps: the client sends at t1, the server receives at t2 and replies at t3, and the client receives at t4. The round-trip delay is (t4 − t1) − (t3 − t2), and the estimated offset is ((t2 − t1) + (t3 − t4)) / 2. The estimate assumes the network delay is the same in both directions, which is often false, so even a well-synchronized server is typically off by a few milliseconds, and much more when the network is congested.

When NTP corrects a clock, it either **slews** it (runs it slightly faster or slower until it catches up) for small offsets, or **steps** it (jumps it forward or backward) for larger ones. Very large offsets need an operator. Leap seconds make it worse: some days have 86,401 seconds, and in 2012 a leap second caused a Linux kernel bug that took down many large websites.

This is why there are two kinds of clock in your programming language:

- A **time-of-day clock** (`Date.now()` in Node.js, `CLOCK_REALTIME` on Linux) tells you the date and time. It can jump backward or forward when NTP steps it. Use it for timestamps people read, never to measure how long something took.
- A **monotonic clock** (`performance.now()` or `process.hrtime.bigint()` in Node.js, `CLOCK_MONOTONIC` on Linux) only moves forward. Its absolute value means nothing and can't be compared across machines, but the difference between two readings on the same machine is a reliable duration. Use it for timeouts and latency.

For a fintech, the practical rules are:

- Never decide which of two events on different machines came first by comparing their wall-clock timestamps.
- Never let "last write wins by timestamp" decide a balance.
- Always measure timeouts with a monotonic clock.

## 7. Happens-before and Lamport clocks

*Main source: Kleppmann's lecture notes, sections 3.3 and 4.1. The ideas are from Leslie Lamport's 1978 paper "Time, Clocks, and the Ordering of Events in a Distributed System".*

If physical clocks can't order events, what can? Lamport's answer is the **happens-before** relation, written a → b. It holds when:

1. a and b happen on the same node and a happens first, or
2. a is sending a message and b is receiving that same message, or
3. there is some c with a → c and c → b (transitivity).

If neither a → b nor b → a, the events are **concurrent** (a ∥ b). Concurrent doesn't mean "at the same instant". It means no chain of messages connects them, so neither could have influenced the other. Happens-before is exactly the notion of **causality**: only if a → b could a have caused b.

A **Lamport clock** gives every event a number that respects causality:

- Each node keeps a counter `t`, starting at 0.
- Before each local event or message send, the node does `t = t + 1`, and a message carries the current `t`.
- On receiving a message carrying `t'`, the node sets `t = max(t, t') + 1`.

Its guarantee is one-way: **if a → b, then L(a) < L(b)**. The reverse is not true: L(a) < L(b) doesn't mean a happened before b, because concurrent events can get any order. To get a total order that every node agrees on, break ties with the node ID: compare (timestamp, node ID) pairs. **Vector clocks**, also in section 4.1 of the notes, keep one counter per node and can tell you when two events are concurrent, at the cost of more space.

You won't implement Lamport clocks in the capstone. What you'll use is the idea behind them: **order comes from causality and from one authority, not from wall clocks.** In a ledger, the order of entries for an account comes from the database's commit order or from a per-account sequence number, never from `created_at`.

## Notes to write today

1. The 3 possible outcomes of a timeout (didn't arrive, happened but the answer was lost, still in progress), and what your system does in each.
2. Why you can't order events by wall clock, with one concrete example from a payment flow.
3. What a Lamport clock guarantees and what it doesn't.

## Check yourself

These make good flashcards (see the [flashcards guide](../../FLASHCARDS.md)).

- What is the difference between a fault and a failure?
- Why can't a timeout tell a crashed node from a slow one?
- What does a crash-recovery node lose when it restarts, and what does it keep?
- Which clock do you use to measure a timeout, and why?
- If L(a) < L(b), does a happen before b?
- Why does the two generals problem not make online payments impossible?

## References

- **Main source:** Martin Kleppmann, ["Distributed Systems" lecture notes](https://www.cl.cam.ac.uk/teaching/2122/ConcDisSys/dist-sys-notes.pdf), University of Cambridge, 2021/22, sections 1.1, 2.1 to 2.4, 3 and 4.1. Free, published under a Creative Commons BY-SA license. The matching video lectures are free and linked from the [course materials page](https://www.cl.cam.ac.uk/teaching/2122/ConcDisSys/materials.html).
- Leslie Lamport, ["Time, Clocks, and the Ordering of Events in a Distributed System"](https://lamport.azurewebsites.net/pubs/time-clocks.pdf), Communications of the ACM, 1978. The original paper behind section 7.
- Jeff Hodges, ["Notes on Distributed Systems for Young Bloods"](https://www.somethingsimilar.com/2013/01/14/notes-on-distributed-systems-for-young-bloods/), 2013. A short practical essay; read it if time is left.
