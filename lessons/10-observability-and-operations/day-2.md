# Module 10, Tuesday: traces, context propagation and business metrics

[Module 10](../../modules/10-observability-and-operations.md) · [Leia em português](day-2.pt-BR.md)

**Reading time:** about 45 minutes. Use the rest of the 2-hour block on the references at the end.

This is an original text written for this course. It is based on the references listed at the end, and each section names the source it follows.

## Why this matters for a fintech

A single transfer in your wallet touches many processes. The API receives `POST /transfers`, writes the transfer and an outbox row in Postgres, a relay publishes to Kafka, a worker consumes the event, calls the partner bank, and writes ledger postings. When a customer says "my transfer took 40 seconds and then failed", you need to follow that one request across all of those hops. That is what traces do, and the hard part is the Kafka hop.

Traces explain one request. Metrics tell you about all of them. Monday's golden signals tell you whether the API is healthy, but a wallet can return 201 to every request and still be losing money. So today also covers metrics about the business itself: approval rate per provider, payments stuck in `PENDING`, reconciliation discrepancies. These are the numbers that answer the module's mastery question.

## 1. Traces and spans

*Main source: OpenTelemetry documentation, "Traces", sections "Spans", "Span Context", "Attributes", "Span Events" and "Span Status".*

The OpenTelemetry docs describe a **trace** as the path of a request through your application. A trace is made of **spans**. A span is one unit of work: an HTTP handler, a SQL query, a call to the partner bank, the processing of one Kafka message.

Each span carries:

- a **name** (for example `POST /transfers` or `partner-bank.debit`),
- a **start and end timestamp**,
- a **span context** (see below),
- a **parent span ID**, except for the root,
- **attributes**, **events**, **links** and a **status**.

The first span of a request, the one with no parent, is the **root span**. Every other span points to its parent, so the spans of one request form a tree. Jaeger draws that tree as a waterfall, and that is what you saw in Monday's lab.

The **span context** is an immutable object with four parts: the **trace ID** (shared by every span of the trace), the **span ID** (unique to this span), **trace flags** (binary flags, such as whether the trace is sampled) and **trace state** (vendor-specific key-value pairs). The span context is the part that travels between services. Everything else stays where the span was created.

**Attributes** are key-value pairs that describe the operation. Keys are strings. Values are strings, booleans, numbers or arrays of those. The docs recommend adding attributes when you create the span, because samplers can only see attributes that exist at creation time. They also point to **semantic conventions**, standard names for common attributes such as the HTTP method or the database system. Use those names when they exist and your own namespace (`wallet.transfer_id`) for domain data.

**Span events** are structured log messages attached to a span at one point in time. The docs give a simple rule: if the timestamp matters, use an event; if it doesn't, use an attribute. "Partner bank returned 503, retrying" is an event. The provider name is an attribute.

**Span status** has three values. `Unset` is the default and means the operation completed without error. `Error` means something failed. `Ok` means a developer explicitly marked the span as successful, and the docs say this is usually unnecessary. For a transfer that the partner bank declined with "insufficient funds", think before setting `Error`: the system worked, and the business outcome was a decline. Put the outcome in an attribute and reserve `Error` for real failures.

## 2. Span kinds and span links

*Main source: OpenTelemetry documentation, "Traces", sections "Span Kind" and "Span Links".*

Every span has a **kind**, which tells the tracing backend how it relates to other processes:

| Kind | Meaning in the docs | Wallet example |
| --- | --- | --- |
| Server | Incoming synchronous remote call | NestJS handler for `POST /transfers` |
| Client | Outgoing synchronous remote call | HTTP call to the partner bank, SQL query |
| Internal | Work that doesn't cross a process boundary | Computing fees, validating limits |
| Producer | Creates a job that may be processed later | Publishing `TransferRequested` to Kafka |
| Consumer | Processes a job created by a producer | Worker handling `TransferRequested` |

If you don't set a kind, the span is treated as internal. The docs note that a consumer span may start long after the producer span has ended. In a wallet that is normal: the outbox relay may publish a second after the API returned, and the worker may consume minutes later during an incident.

**Span links** connect a span to one or more other spans without making them parent and child. The docs give the example of an asynchronous operation started by an earlier trace, where you don't know when it will run. Links matter for messaging because a span has exactly one parent. If your worker processes a batch of 50 Kafka messages in one span, it can't have 50 parents, but it can have 50 links. The OpenTelemetry messaging conventions, covered in section 4, build on this.

## 3. Context propagation

*Main source: OpenTelemetry documentation, "Context propagation", sections "Context", "Propagation" and "Example".*

A trace across two services only works if the second service knows which trace it belongs to. The docs call the information that makes this possible **context**: the trace ID and span ID that let the receiver create a span in the same trace. **Propagation** is moving that context between services and processes, by serializing it on the sending side and deserializing it on the receiving side.

The component that does this is a **propagator**. The default in OpenTelemetry uses the **W3C TraceContext** specification, which defines the `traceparent` header. Its format is `version-traceid-parentid-traceflags`, and the docs show this example:

```
traceparent: 00-a0892f3577b34da6a3ce929d0e0e4736-f03067aa0ba902b7-01
```

Read it as: version `00`, a 32-hex-character trace ID, the 16-hex-character ID of the span that sent the call, and flags `01` (sampled). The receiver extracts it, creates its own span with the same trace ID, and sets that span's parent to the sender's span ID.

In the docs' vocabulary, the sender **injects** context into a **carrier** and the receiver **extracts** it. For HTTP, the carrier is the request headers, and the auto-instrumentation libraries for HTTP and NestJS do it for you. That's why Monday's lab gave you a trace with no extra code.

The docs' example also shows that propagation helps the other signals. SDKs can add the trace ID and span ID to log records, so you can jump from a trace to its logs. This is the **correlation id** that capstone item 1 asks for: use the trace ID itself, so logs and traces share one key.

Two security notes from the same page apply to a fintech. Treat incoming context from untrusted sources with care, because forged headers can distort your traces. Think twice before sending context to external services, because it can expose internal details. And **baggage**, a separate mechanism that carries arbitrary key-value pairs across services, must never carry credentials, API keys or personal data. In a wallet, don't put a CPF or account number in baggage.

## 4. Propagating through Kafka

*Main source: OpenTelemetry documentation, "Context propagation", section "Custom Context Propagation"; OpenTelemetry semantic conventions, "Messaging spans", section "Context propagation".*

The "Context propagation" page explains the general rule for protocols the libraries don't cover: inject into whatever carrier the protocol offers, and extract on the other side. For Kafka, the carrier is the **message headers**. The page doesn't cover messaging in detail. The messaging semantic conventions do, and their key sentence is: "A producer SHOULD attach a message creation context to each message." The **creation context** is the span context of the moment the message was created. The consumer's processing span should then **link** to it. Using it as the parent is allowed only in single-message cases, and the convention asks you to document that choice.

In your capstone, there is an extra hop: the API writes an outbox row, and a relay publishes it later. If the relay injects its own context, the trace starts at the relay and you lose the link to the HTTP request. So capture the context when the API writes the outbox row, and store it in a column:

```typescript
import { context, propagation } from '@opentelemetry/api';

// Inside the same transaction that creates the transfer
const carrier: Record<string, string> = {};
propagation.inject(context.active(), carrier); // fills carrier.traceparent
await tx.query(
  `INSERT INTO outbox (id, topic, payload, trace_headers)
   VALUES ($1, $2, $3, $4)`,
  [eventId, 'transfers', payload, carrier],
);
```

The relay copies `trace_headers` into the Kafka message headers unchanged. The worker extracts them and starts a consumer span:

```typescript
import { context, propagation, trace, SpanKind, SpanStatusCode } from '@opentelemetry/api';

const tracer = trace.getTracer('wallet-worker');

async function handle(message: KafkaMessage) {
  // KafkaJS delivers header values as Buffers; the propagator expects strings
  const carrier: Record<string, string> = {};
  for (const [key, value] of Object.entries(message.headers ?? {})) {
    if (value) carrier[key] = value.toString();
  }
  const parentCtx = propagation.extract(context.active(), carrier);

  await tracer.startActiveSpan(
    'process transfers',
    { kind: SpanKind.CONSUMER, attributes: { 'messaging.system': 'kafka' } },
    parentCtx,
    async (span) => {
      try {
        await processTransfer(message); // inbox check, partner call, postings
      } catch (err) {
        span.setStatus({ code: SpanStatusCode.ERROR });
        throw err;
      } finally {
        span.end();
      }
    },
  );
}
```

This version uses the extracted context as the parent, which is the single-message case. To follow the conventions' default instead, start the span from the current context and pass `links: [{ context: trace.getSpanContext(parentCtx)! }]` in the options. Either way, Jaeger can now show the API request and the worker's processing as one story. Write down which option you chose and why: that's a good line for `docs/m10.md`.

The span name follows the conventions' pattern of operation name plus destination, such as `process transfers`. `messaging.system` and `messaging.destination.name` are among the standard attribute names they define.

## 5. What Prometheus says to instrument

*Main source: Prometheus documentation, "Instrumentation", sections "How to instrument", "The three types of services" and "Subsystems".*

The Prometheus page opens with a direct answer to what you should measure: "The short answer is to instrument everything." It then sorts services into three types, and your capstone has all three:

| Type | Key metrics in the docs | In the wallet |
| --- | --- | --- |
| Online-serving | Queries performed, errors, latency; in-progress requests also useful | Transfer API |
| Offline processing | Items coming in, in progress, last processing time, items sent out | Kafka worker, outbox relay |
| Batch job | The last time it succeeded; duration of each stage and of the run | Nightly reconciliation |

Two details apply directly. For online services, the page suggests counting a request when it ends, so the count lines up with error and latency stats. For pipelines, it suggests a **heartbeat**: a dummy item with a timestamp that passes through the whole system, so you can measure how long items take to get through. For the outbox relay and worker, a heartbeat event every minute tells you if the pipeline is stuck even when no customer is transferring.

For **failures**, the page says to increment a counter on each failure and to also count total attempts, so you can compute the failure ratio. That ratio is exactly the shape Monday's SLO alerts need.

## 6. Business metrics as the main signal

*Main source: Prometheus documentation, "Instrumentation", sections "Counter vs. gauge, summary vs. histogram", "Timestamps, not time since" and "Avoid missing metrics". The business framing is this course's.*

The Prometheus page talks about technical metrics. In a fintech, the metrics that catch the expensive incidents are about the business. They are symptoms in Monday's sense: they describe what the customer and the company feel. Capstone item 2 asks for three.

**Approval rate per provider.** Count every authorization attempt with two labels: `provider` and `outcome` (`approved`, `declined`, `error`). The approval rate is a ratio of rates:

```promql
sum by (provider) (rate(payment_authorizations_total{outcome="approved"}[15m]))
/
sum by (provider) (rate(payment_authorizations_total[15m]))
```

A drop for one provider while the other stays flat points to that provider. A drop for both points to you.

**Old PENDING payments.** This metric can go up and down, so it is a gauge. The Prometheus rule of thumb: "if the value can go down, it is a gauge." The page also advises exporting the timestamp when something happened, not the time since it happened, because then `time() - metric` gives the age without any update logic. So a periodic job can export the creation time of the oldest pending payment:

```sql
SELECT EXTRACT(EPOCH FROM min(created_at)) AS oldest_pending_ts
FROM payments
WHERE status = 'PENDING';
```

```promql
time() - wallet_oldest_pending_payment_timestamp_seconds > 900
```

That alert fires when any payment has been pending for more than 15 minutes. A second gauge with the count of payments pending longer than 15 minutes tells you whether it's one stuck payment or a thousand.

**Reconciliation discrepancies.** Module 7's job compares your ledger with the provider's file and reports missing, duplicate, different-amount and wrong-date items. Export a gauge per type from the last run, plus the timestamp of the last successful run (the batch-job metric from section 5). A discrepancy count above zero needs a human. A last-success timestamp older than a day means the job itself is broken, and then zero discrepancies proves nothing.

In code, with the `prom-client` library:

```typescript
import { Counter, Gauge } from 'prom-client';

export const authorizations = new Counter({
  name: 'payment_authorizations_total',
  help: 'Authorization attempts by provider and outcome',
  labelNames: ['provider', 'outcome'] as const,
});

export const reconDiscrepancies = new Gauge({
  name: 'reconciliation_discrepancies',
  help: 'Discrepancies found in the last reconciliation run',
  labelNames: ['type'] as const,
});

// Initialize known series to 0 so they exist before the first event
for (const provider of ['provider_a', 'provider_b']) {
  for (const outcome of ['approved', 'declined', 'error']) {
    authorizations.inc({ provider, outcome }, 0);
  }
}
```

The last loop follows the page's "Avoid missing metrics" advice: export a default value such as 0 for series you know will exist. Without it, the "error" series for a provider doesn't exist until the first error, and a ratio or an alert over it returns nothing.

## 7. Labels and the cost of cardinality

*Main source: Prometheus documentation, "Instrumentation", sections "Use labels" and "Do not overuse labels".*

Labels are what make one metric useful in many ways. The page's advice is to use one metric with a label when you'd add or average the values together, for example a single `http_responses_total` with a `code` label instead of one metric per status code. That's why `outcome` and `provider` are labels and not part of the metric name.

But every unique combination of label values is a separate time series, stored and queried on its own. The page warns about this cost with concrete guidance:

- As a general guideline, keep the cardinality of a metric below 10.
- Metrics above that should be a handful across the whole system.
- If a metric has a cardinality over 100, or could grow that large, look for alternatives, such as moving the analysis out of Prometheus.
- When unsure, start with no labels and add them as real needs appear.

The page's example: a filesystem metric on 10,000 nodes is about 100,000 series, which is fine. Adding per-user quotas for 10,000 users pushes it to tens of millions.

For a wallet, the rule is simple. Labels like `provider` (2 or 3 values), `outcome` (3 values) and `route` (a few dozen) are fine. Labels like `customer_id`, `transfer_id`, `idempotency_key` or `amount` are never fine: their number of values grows with your business. When you need to find a specific transfer, that's the job of traces and logs, which are indexed by trace ID. Metrics answer "how many and how fast". Traces and logs answer "which one".

## Notes to write today

1. Draw the trace of one transfer from `POST /transfers` to the ledger postings: each span with its name and kind, and where the context crosses the outbox and Kafka.
2. Write your propagation decision for the worker: parent or link, which headers you store in the outbox, and how the trace ID gets into every log line.
3. List your business metrics: name, type (counter, gauge or histogram), labels with their possible values, and the PromQL you'd alert on. Mark any label whose cardinality can grow with the business, and remove it.

## Check yourself

These make good flashcards (see the [flashcards guide](../../FLASHCARDS.md)).

- What four fields does a span context hold, and which part travels between services?
- When do you use a span event instead of a span attribute?
- What is the difference between a producer span and a consumer span, and why can the consumer start after the producer ended?
- Why do the messaging conventions prefer span links over parent-child for consumers?
- Read this header: `00-a0892f3577b34da6a3ce929d0e0e4736-f03067aa0ba902b7-01`. What is each part?
- Why export the timestamp of the oldest pending payment instead of its age?
- Why is `customer_id` a bad Prometheus label, and where do you look up one customer's transfer instead?

## References

- **Main source:** OpenTelemetry documentation, ["Traces"](https://opentelemetry.io/docs/concepts/signals/traces/). Read all of "Spans", including span context, attributes, events, links, status and kind. Free.
- **Main source:** OpenTelemetry documentation, ["Context propagation"](https://opentelemetry.io/docs/concepts/context-propagation/). Read "Context", "Propagation", the example and "Security best practices". Free.
- **Main source:** Prometheus documentation, ["Instrumentation"](https://prometheus.io/docs/practices/instrumentation/). Read it all, focusing on "The three types of services" and "Things to watch out for". Free.
- OpenTelemetry semantic conventions, ["Messaging spans"](https://opentelemetry.io/docs/specs/semconv/messaging/messaging-spans/). Read the "Context propagation" part and the span kind table. Free. Added because the "Context propagation" page doesn't cover messaging in detail.
