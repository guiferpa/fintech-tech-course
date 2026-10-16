# Module 9, Monday: timeouts, retries, circuit breakers and bulkheads

[Module 9](../../modules/09-resilience-and-consensus.md) · [Leia em português](day-1.pt-BR.md)

**Reading time:** about 45 minutes. Use the rest of the 2-hour block on the references at the end, starting with the sections marked as the main source.

This is an original text written for this course. It is based on the references listed at the end, and each section names the source it follows. Where an idea comes from a specific author, the text says so.

## Why this matters for a fintech

Your wallet depends on partners you don't control: a partner bank for transfers, a card processor, a Pix provider, a KYC vendor. One day the main provider starts answering in 30 seconds instead of 300 milliseconds. Nothing is "down". Every health check is green. And yet, within a few minutes, your whole API stops answering, including endpoints that never call that provider, like the balance screen.

This is the scenario of this module's mastery test, and today's lab reproduces it with k6 and Toxiproxy. The four tools of today (timeouts, retries with backoff and jitter, circuit breakers and bulkheads) exist so that one slow dependency degrades one feature, not the whole company.

## 1. How a slow dependency takes everything down

*Main source: Microsoft Azure Architecture Center, "Bulkhead pattern", section "Context and problem".*

Every request that waits on a remote call holds something while it waits: a socket, a slot in an HTTP connection pool, a database connection if the transaction is still open, memory for the request object. The Azure article describes the chain: a service becomes unresponsive, the consumer's resources stay busy, the connection pool runs out, and soon requests to *other* services fail too. That chain is a **cascading failure**.

A quick calculation shows how fast it happens. Little's law says that the average number of requests in flight equals the arrival rate times the average time each one spends in the system (L = λ × W). Suppose your transfer endpoint receives 50 requests per second:

| Provider latency | Requests in flight (50 req/s) |
| --- | --- |
| 300 ms | 15 |
| 3 s | 150 |
| 30 s | 1,500 |

If each in-flight transfer holds one of 20 Postgres connections while it calls the partner bank, the pool is exhausted almost immediately at 30 s. Now the balance endpoint, which only needs a 2 ms query, waits for a connection too. Customers see the whole app freeze.

Two design rules follow, and the rest of the lesson builds on them:

- **Never hold a database connection or transaction open while calling a remote service.** Write the transfer as `PENDING`, commit, call the partner, then record the result in a new transaction.
- **Every wait must have an end, and every shared resource must have a boundary.** Timeouts give the end. Bulkheads give the boundary.

## 2. Timeouts: choosing the number

*Main source: Marc Brooker, Amazon Builders' Library, "Timeouts, retries, and backoff with jitter", the part on timeouts.*

Brooker's first rule is simple: put a timeout on every remote call, including calls between processes on the same machine. The hard part is choosing the value. Too high, and you hold resources for nothing. Too low, and you fail requests that would have succeeded, which triggers retries and more load.

The method he describes for Amazon services:

1. Decide what rate of **false timeouts** you accept, for example 0.1% of calls.
2. Look at the latency distribution of the downstream service and take the matching percentile, here p99.9.
3. Use that as the starting value, and adjust.

He lists cases that need adjustment. Clients on the internet need extra room for bad networks. When p99.9 is very close to p50, add padding, because a small shift would cause many timeouts at once. He also tells a story of a 20 ms timeout that failed requests after every deployment, because it also covered the TLS handshake of new connections. The lesson: know what your timeout actually includes (DNS, connect, TLS, request, response body).

In Node.js, `fetch` has no timeout by default. Pass a signal:

```typescript
// Partner bank p99.9 measured at ~1.2 s, so 2 s gives margin.
const res = await fetch(`${PARTNER_URL}/transfers`, {
  method: 'POST',
  headers: { 'Idempotency-Key': transfer.id, 'Content-Type': 'application/json' },
  body: JSON.stringify(payload),
  signal: AbortSignal.timeout(2_000),
});
```

Two more rules connect today with earlier modules:

- **Timeouts must nest.** If the mobile app gives up after 10 s, your API's total budget must be smaller, and each call inside it smaller still. A worker that keeps retrying after the client left does wasted work (Tuesday's load shedding article calls this out).
- **A timeout means "I don't know".** As in Module 1, a transfer whose partner call times out goes to `UNKNOWN`, and a reconciliation job asks the partner for the status later. It never goes straight to `FAILED`.

## 3. Retries are selfish

*Main source: Brooker, "Timeouts, retries, and backoff with jitter", the parts on retries and idempotency.*

A retry hides transient failures: a dropped packet, a server restart, a brief lock. But Brooker points out that retries are selfish. A retrying client asks the server to spend more of its capacity on that client's request. When failures are rare, that's fine. When the server is failing *because* it's overloaded, retries add load exactly when it can least afford it, and they slow down recovery.

The amplification gets worse with depth. Brooker's example: a stack of five layers where each layer retries three times can multiply the load on the database at the bottom by 3^5 = 243. In a wallet, the chain might be mobile app → API gateway → transfer service → payment adapter → partner bank. If each one retries on its own, a short partner hiccup becomes a flood.

The practical rules from the article:

- **Retry at one layer only.** Usually the layer that owns the operation and its idempotency key, for example the payment adapter.
- **Retry only what can succeed later.** A 5xx or a connection error may succeed later. A 4xx (bad request, insufficient funds at the partner) will fail the same way, so don't retry it unchanged.
- **Retry only idempotent operations.** A timeout does not prove that the side effect didn't happen. Brooker cites EC2's `RunInstances`, which accepts a client token for this reason. Your adapter sends the transfer ID as an idempotency key (Module 2), so a retry can't move money twice.
- **Limit retries with a budget.** Instead of a circuit breaker, Brooker describes a local **token bucket for retries**: retries flow freely while tokens remain, then are limited to a fixed rate. He says the AWS SDK added this behavior in 2016. A simple version: allow retries only while they are under 10% of recent requests.

A retry budget is item 1 of Thursday's capstone. It caps the worst case: if every call fails, total load is at most 1.1 times normal, not 3 or 243 times.

## 4. Backoff and jitter

*Main source: Brooker, "Timeouts, retries, and backoff with jitter", the parts on backoff and jitter.*

Retrying immediately hits a struggling server again before it has had time to recover. **Exponential backoff** waits longer after each failed attempt (100 ms, 200 ms, 400 ms, ...). Because the wait grows fast, implementations **cap** it. Brooker notes that a cap alone isn't enough: clients then retry forever at the capped rate. Amazon's usual answer is to also limit the number of attempts.

Backoff has a second problem. If a thousand requests failed at the same moment (the partner restarted), they all back off by the same amounts and come back at the same moments, in synchronized waves. **Jitter** adds randomness to each wait so the retries spread out. The article points to a separate AWS post for variants. A common one picks a random wait between zero and the capped exponential value:

```typescript
function backoffMs(attempt: number, baseMs = 100, capMs = 5_000): number {
  const exp = Math.min(capMs, baseMs * 2 ** attempt);
  return Math.random() * exp; // jitter: anywhere in [0, exp)
}
```

Brooker extends jitter beyond retries. Any timer that many hosts share creates spikes: think of a reconciliation job that every worker starts at 00:00, or a statement cache that every pod refreshes at the top of the minute. He describes Amazon adding jitter to such scheduled work and preferring a consistent offset per host (for example, derived from the host name) over a new random value each run, because a fixed pattern is easier to debug.

## 5. Circuit breaker

*Main source: Martin Fowler, "Circuit Breaker" (2014). Fowler credits Michael Nygard's book "Release It!" with popularizing the pattern.*

Timeouts limit how long each call waits, but with a dead provider every call still waits the full timeout. With a 2 s timeout and 50 requests per second, you still have 100 requests stuck at any moment, and each one ends in an error. A **circuit breaker** stops making calls that will almost certainly fail.

Fowler describes it as a wrapper around the protected call that counts failures. In his words, "Once the failures reach a certain threshold, the circuit breaker trips", and further calls return an error immediately, without reaching the supplier. After a while, the breaker lets a trial call through to see if the supplier recovered.

| State | What happens to a call | Moves to |
| --- | --- | --- |
| **Closed** | Goes to the supplier; failures are counted | Open, when failures pass the threshold |
| **Open** | Fails immediately, supplier not called | Half-open, after the reset timeout |
| **Half-open** | One trial call goes through | Closed if it succeeds, open again if it fails |

Details from Fowler's article that matter in practice:

- His simple example trips after 5 failures. He notes that a more realistic breaker might trip on an **error rate** (for example 50%), and might use different thresholds for different errors, such as a higher threshold for timeouts than for connection failures.
- **Not every error is a failure.** A partner answering "insufficient funds" or "invalid account" is a normal business result and must not trip the breaker.
- **Decide the fallback.** Fowler's example of a fallback is queuing a credit card authorization to process later. In a wallet: accept the transfer as `PENDING`, put it on a queue, and tell the customer it is processing.
- **Make it visible.** Log every state change, expose the state for monitoring, and let operators trip or reset a breaker by hand.

Brooker's article adds a caution: breakers introduce modal behavior that is hard to test, and they can slow recovery, which is why Amazon often prefers retry token buckets. The two are not exclusive. In the lab you'll use opossum, a Node.js library:

```typescript
import CircuitBreaker from 'opossum';

const breaker = new CircuitBreaker(callPartnerBank, {
  timeout: 2_000,               // a call slower than this counts as a failure
  errorThresholdPercentage: 50, // open when half of recent calls fail
  resetTimeout: 30_000,         // wait 30 s before a half-open trial
});
breaker.fallback((transfer) => enqueueForLater(transfer)); // returns PENDING
breaker.on('open', () => logger.warn('partner-bank breaker OPEN'));

const result = await breaker.fire(transfer);
```

## 6. Bulkheads

*Main source: Microsoft Azure Architecture Center, "Bulkhead pattern", sections "Solution" and "Problems and considerations".*

The name comes from ships. The Azure article explains: "If the hull of a ship is compromised, only the damaged section fills with water, which prevents the ship from sinking." A bulkhead in software splits resources into pools so a failure in one pool can't drain the others.

The article describes two kinds:

- **Partition consumer resources.** A service that calls several dependencies gets a separate connection pool for each. If one dependency hangs, only its pool fills up.
- **Partition service instances.** Group instances by consumer or priority, so one heavy client can't starve the others.

In a wallet, examples are:

- One HTTP agent with its own connection limit per partner (partner bank, card processor, KYC). A slow KYC vendor can't block transfers.
- A separate Postgres pool (or a separate read replica) for back-office reports, so a heavy export can't take connections from the payment path.
- Separate worker queues per partner, so a backlog for one doesn't delay the others (Tuesday's queue article returns to this).

A minimal concurrency bulkhead in TypeScript:

```typescript
class Bulkhead {
  private inFlight = 0;
  constructor(private readonly max: number) {}

  async run<T>(fn: () => Promise<T>): Promise<T> {
    if (this.inFlight >= this.max) throw new BulkheadFullError(); // reject, don't queue
    this.inFlight++;
    try { return await fn(); } finally { this.inFlight--; }
  }
}

const partnerBank = new Bulkhead(30);
const kycVendor = new Bulkhead(10);
```

The article's considerations: choose partitions around business and technical requirements (bounded contexts are a good guide), weigh the isolation against cost and complexity, monitor each partition separately, and combine bulkheads with retries, circuit breakers and throttling. It also lists when the pattern may not fit: when less efficient use of resources is unacceptable, or when the added complexity isn't needed. A bulkhead reserves capacity that sits idle on good days. That's the price.

## 7. Putting it together: the 30-second provider

*This section combines the three sources above.*

Here is the mastery test scenario, layer by layer. The partner bank goes from 300 ms to 30 s.

| Protection | What happens |
| --- | --- |
| None | In-flight requests pile up (1,500 at 50 req/s). Connection pools run out. Every endpoint slows down, p99 jumps to the client timeout, error rate climbs everywhere. |
| Timeouts (2 s) | Each transfer fails after 2 s and goes to `UNKNOWN`. In-flight drops to about 100. Other endpoints mostly recover, but every transfer still costs 2 s and an error. |
| + Retries without budget | Each failed call is tried again 3 times. Load on the partner and on your pool multiplies. Things get worse, not better. |
| + Backoff, jitter and retry budget | Retries are spread out and capped at about 10% extra load. Transient blips are hidden; a real outage isn't amplified. |
| + Circuit breaker | After the error rate passes 50%, calls fail fast and fall back to `PENDING` plus a queue. Latency for the customer drops to milliseconds. Half-open trials detect recovery. |
| + Bulkhead | Even before the breaker opens, the partner bank can use at most 30 concurrent slots. Balance, statements and KYC keep their own resources. |

In today's lab you measure the first row: p99, error rate and open connections with no protection. Tomorrow you add timeouts and the breaker and measure again. On Thursday the capstone adds the retry budget, bulkheads per provider and rate limiting, and on Friday you plot before and after.

## Notes to write today

1. The three states of a circuit breaker, what moves it between them, and which partner errors must not count as failures.
2. What a bulkhead isolates in your wallet: list the pools you would create (per partner, back-office, workers) and their sizes.
3. How you choose a timeout (false timeout rate and percentile), and why timeouts must nest from the client inward.
4. What a retry storm is (the 3^5 = 243 example), and how retrying at one layer plus a retry budget prevents it.

## Check yourself

These make good flashcards (see the [flashcards guide](../../FLASHCARDS.md)).

- Why can a slow dependency take down endpoints that never call it?
- How does Brooker suggest choosing a timeout value?
- Why does Brooker call retries selfish?
- What problem does jitter solve that backoff alone does not?
- What happens in each of the three circuit breaker states?
- Why must "insufficient funds" from a partner not trip the breaker?
- What does a bulkhead cost on a good day?

## References

- **Main source:** Martin Fowler, ["Circuit Breaker"](https://martinfowler.com/bliki/CircuitBreaker.html), martinfowler.com, 2014. Read the whole entry, including the parts on thresholds, fallbacks and monitoring. Free.
- **Main source:** Microsoft Azure Architecture Center, ["Bulkhead pattern"](https://learn.microsoft.com/en-us/azure/architecture/patterns/bulkhead). Read "Context and problem", "Solution", "Problems and considerations" and "When to use this pattern". Free.
- **Main source:** Marc Brooker, ["Timeouts, retries, and backoff with jitter"](https://aws.amazon.com/builders-library/timeouts-retries-and-backoff-with-jitter/), Amazon Builders' Library, 2019. Read it all; it is the most important text of the day. Free.
- Michael Nygard, "Release It! Design and Deploy Production-Ready Software", Pragmatic Bookshelf. The book Fowler credits with popularizing the circuit breaker; it also describes bulkheads. Paid book, optional.
