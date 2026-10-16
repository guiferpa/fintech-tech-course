# Module 10, Monday: symptoms, golden signals, SLOs and burn-rate alerts

[Module 10](../../modules/10-observability-and-operations.md) · [Leia em português](day-1.pt-BR.md)

**Reading time:** about 45 minutes. Use the rest of the 2-hour block on the references at the end, starting with the "Alerting on SLOs" chapter.

This is an original text written for this course. It is based on the references listed at the end, and each section names the source it follows. Where an idea or a number comes from a specific author, the text says so.

## Why this matters for a fintech

In a wallet, the worst failures are quiet. A transfer API that returns HTTP 500 gets noticed in minutes. A worker that charges some customers twice, or a provider that silently declines 30% of payments, can run for hours before someone opens a support ticket. By then the money has moved, and every hour adds refunds, chargebacks and angry messages.

This module's goal is to know the system is wrong before a customer does. Today gives you the vocabulary and the math: what to watch (symptoms, golden signals), what "good enough" means (SLIs, SLOs, error budgets), and when to wake a human (burn-rate alerts). Tuesday adds traces and business metrics, and Wednesday covers what happens after the alert fires.

## 1. Monitoring vocabulary

*Main source: Google SRE book, chapter 6, "Definitions" and "Why Monitor?".*

The SRE book defines **monitoring** as collecting, processing, aggregating and displaying real-time numbers about a system. It then splits monitoring in two:

- **White-box monitoring** uses data the system exposes about its own internals: metrics, logs, internal status pages. Your NestJS service counting requests per route is white-box.
- **Black-box monitoring** tests behavior from the outside, the way a user would see it. A probe that calls `POST /transfers` with a test account every minute is black-box.

Two more terms matter. A **dashboard** is a summary view of a service's core metrics. An **alert** is a notification meant to be read by a human. The book sorts alerts into tickets, email alerts and pages, and that split is important: a page interrupts someone right now, possibly at 3 a.m., while a ticket can wait for working hours.

The chapter also gives reasons to monitor beyond alerting: analyzing long-term trends (how fast is the ledger table growing?), comparing before and after a change (did the new Postgres index help?), building dashboards, and debugging. For a wallet you can add one more: proving to an auditor or to the partner bank that you know what your system did.

## 2. Symptoms versus causes

*Main source: Google SRE book, chapter 6, "Symptoms Versus Causes" and "Black-Box Versus White-Box".*

The chapter's central idea fits in one sentence: "Your monitoring system should address two questions: what's broken, and why?" The **symptom** is what's broken. The **cause** is why. The book calls this one of the most important distinctions in writing good monitoring.

Here is the same idea with wallet examples:

| Symptom (what the user feels) | Possible cause (why) |
| --- | --- |
| Transfers return HTTP 500 | Postgres connection pool exhausted |
| Transfers take 4 seconds | Partner bank API slow, retries piling up |
| Card payments declined more than usual | Provider A rejecting a new certificate |
| A customer was charged twice | Consumer reprocessed a Kafka message without checking its inbox |
| Balances look stale in the app | Read replica lagging behind the primary |

Why does the distinction matter? Because the list of possible causes is endless, and the list of symptoms a user can feel is short. If you page on causes ("CPU above 80%"), you get pages for things that hurt nobody and miss failures you didn't think of. If you page on symptoms ("transfers failing"), every page means a real user problem, and the causes become the tools you use to debug.

The book adds a nuance: one person's symptom is another person's cause. Slow database queries are a cause for the transfer API team and a symptom for the database team. So each layer watches its own symptoms.

On black-box versus white-box, the book's position is a mix. Heavy use of white-box monitoring, plus modest but critical use of black-box monitoring. Black-box is symptom-oriented by nature: it only sees problems that are already happening. White-box lets you see problems that are about to happen (a queue that keeps growing) and causes hidden behind retries.

## 3. The four golden signals

*Main source: Google SRE book, chapter 6, "The Four Golden Signals" and "Worrying About Your Tail".*

The book says that if you can measure only four metrics of a user-facing system, measure these:

| Signal | Book's idea | Wallet example |
| --- | --- | --- |
| **Latency** | The time it takes to serve a request | p99 of `POST /transfers` |
| **Traffic** | How much demand is placed on the system | Transfers per second, payments per provider |
| **Errors** | The rate of requests that fail | 5xx responses, plus 200s with the wrong content |
| **Saturation** | How "full" the service is | DB pool in use, Kafka consumer lag, worker queue depth |

Three details from the chapter are worth writing down.

**Separate successful and failed latency.** A request that fails fast with a 500 can pull the average latency down and make things look better. The book also notes that "a slow error is even worse than a fast error!" So record latency with an outcome label and look at both.

**Errors are more than status codes.** The book counts explicit failures (HTTP 500), implicit ones (a 200 with the wrong content) and failures by policy (a request you promised to answer in one second that took longer). In a wallet, a transfer that returns 201 but writes an unbalanced posting is an error, even though no status code says so.

**Saturation comes before failure.** The chapter notes that many systems degrade before they reach 100% utilization, and that latency increases are often a leading indicator of saturation. A Postgres pool at 95% doesn't fail yet, but every new request waits.

The book then warns against averages. Its example: a service handling 1,000 requests per second with an average latency of 100 ms can easily have 1% of requests taking 5 seconds. In a wallet that 1% is 10 customers per second staring at a spinner, and some of them will tap "pay" again. The fix is to record latency as a **histogram**: count requests in latency buckets instead of storing an average. The book's example buckets are 0 to 10 ms, 10 to 30 ms, 30 to 100 ms and so on: boundaries that grow roughly exponentially, by factors of about 3.

The chapter closes with rules for pages that you'll reuse on Wednesday. Every page should be actionable. Every page response should require intelligence (if a script could do it, automate it). Ask, before adding an alert: is it urgent, is it actionable, does it definitely mean users are hurting?

## 4. SLIs, SLOs and SLAs

*Main source: Google SRE book, chapter 4, "Service Level Terminology", "Indicators in Practice" and "Objectives in Practice".*

The book defines three terms that people often mix up:

- **SLI (service level indicator):** a carefully defined number that measures some aspect of the service. For example, the fraction of transfer requests that succeed.
- **SLO (service level objective):** a target for an SLI. For example, "99.9% of transfer requests succeed, measured over 30 days".
- **SLA (service level agreement):** a contract with users that includes consequences for missing the SLOs. The book gives a quick test: ask "what happens if the SLOs aren't met?" If nothing explicit happens, it's an SLO, not an SLA.

In a fintech, SLAs show up in contracts with merchants or with a partner bank. Your team usually owns SLOs, and the SLA should be looser than your internal SLO so you have room to react. The book recommends exactly this safety margin.

**Choosing SLIs.** The book suggests a handful of representative indicators, not every metric you have. It groups systems by what users care about: user-facing serving systems care about availability, latency and throughput; storage systems about latency, availability and durability; big data pipelines about throughput and end-to-end latency. All systems should care about correctness. For a wallet, a reasonable first set is:

| SLI | Good event | Valid event |
| --- | --- | --- |
| Transfer availability | Response not 5xx | Every well-formed `POST /transfers` |
| Transfer latency | Answered in under 300 ms | Every well-formed `POST /transfers` |
| Settlement freshness | Payment leaves `PENDING` within 10 minutes | Every payment created |

Writing an SLI as "good events divided by valid events" makes it easy to compute from counters, and it is the form the workbook uses for alerting.

**Percentiles, not averages.** The book says that most metrics are better thought of as distributions rather than averages. A latency SLO is therefore written as "99% of requests under 300 ms", not "average under 300 ms".

**Choosing targets.** The book's advice, in short:

- Start from what users care about, not from what is easy to measure.
- Don't pick a target only because it's your current performance.
- Keep it simple, and have as few SLOs as possible.
- Avoid absolutes. Nobody can promise 100%.
- Perfection can wait: start loose and tighten later, because relaxing a target users rely on is harder.

The chapter's boxed story about Chubby, Google's lock service, shows why "too reliable" is a risk. Chubby was so dependable that other teams assumed it would never fail. Google's response was to make sure the global Chubby service meets but does not greatly exceed its SLO, even taking it down on purpose in a quarter without real outages. Users start to depend on the reliability you actually deliver, not the one you promised.

## 5. Error budgets

*Main source: Google SRE book, chapter 4, "Defining Objectives"; Google SRE Workbook, "Alerting on SLOs".*

If the SLO is 99.9% success, then 0.1% failure is allowed. That allowance is the **error budget**. The SRE book introduces it as a rate at which the SLOs can be missed, tracked daily or weekly, and calls 100% compliance "unrealistic and undesirable". The workbook puts it in counting terms: the error budget gives the number of allowed bad events.

A concrete example. Your wallet processes 2 million transfers in 30 days, with a 99.9% availability SLO. The error budget is 0.1% of 2,000,000, which is 2,000 failed transfers per 30 days. Every failed transfer spends one unit of that budget.

The budget turns reliability into a decision rule. If most of the budget is left near the end of the month, the team can ship riskier changes. If a bad deploy burned 80% of it in one afternoon, releases slow down and reliability work moves up. The book describes this control loop in its "Control Measures" section: measure the SLI, compare it with the SLO, decide whether action is needed, act.

There is a fintech catch. Not every failure is equal. A failed transfer that returns 503 and is retried safely with an idempotency key costs the customer a few seconds. A double charge costs real money and trust. Error budgets fit availability and latency well. A double charge doesn't fit them: you never "budget" for it. On Wednesday you'll build a separate detector for it, with a threshold close to zero.

## 6. Burn rate, and why simple alerts fail

*Main source: Google SRE Workbook, "Alerting on SLOs", sections "Alerting Considerations" and "Ways to Alert on Significant Events", approaches 1 to 4.*

The workbook judges any alerting rule on four properties:

- **Precision:** the share of alerts that correspond to a significant event. Low precision means noise.
- **Recall:** the share of significant events that produce an alert. Low recall means missed incidents.
- **Detection time:** how long the alert takes to fire.
- **Reset time:** how long it keeps firing after the problem is fixed.

The key concept is **burn rate**. The workbook defines it as "how fast, relative to the SLO, the service consumes the error budget." A burn rate of 1 spends the budget exactly over the SLO window. The workbook's table for a 99.9% SLO over 30 days:

| Burn rate | Error rate | Budget exhausted in |
| --- | --- | --- |
| 1 | 0.1% | 30 days |
| 2 | 0.2% | 15 days |
| 10 | 1% | 3 days |
| 1,000 | 100% | 43 minutes |

The workbook then walks through simple rules that look reasonable and fail:

1. **Alert when the error rate over 10 minutes is at or above the SLO threshold.** Detection is fast, but precision is terrible. A 0.1% error rate for 10 minutes spends only 0.02% of the monthly budget, yet it pages. The workbook counts up to 144 alerts a day while still meeting the SLO.
2. **Use a much longer window, such as 36 hours.** Precision improves, but reset time is awful: after a 100% outage, the alert keeps firing for 36 hours.
3. **Add a duration (`for: 1h`).** Now a total outage pages only after an hour, and a flapping error rate that dips below the threshold keeps resetting the timer and may never page. The workbook doesn't recommend durations in SLO alerts.
4. **Alert on burn rate over one window,** for example a burn rate of 36 over 1 hour (5% of the budget). Better, but a burn rate of 35 never alerts, even though it would spend the whole budget in under a day.

## 7. Multiwindow, multi-burn-rate alerts

*Main source: Google SRE Workbook, "Alerting on SLOs", approaches 5 and 6 and "Low-Traffic Services and Error Budget Alerting".*

The workbook's recommended answer combines two ideas.

**Several burn rates.** A fast, severe burn pages quickly. A slow burn opens a ticket. The amount of budget consumed when an alert fires is burn rate × window ÷ SLO period. With a 30-day period (720 hours), the workbook's starting points for a 99.9% SLO are:

| Severity | Long window | Short window | Burn rate | Budget consumed |
| --- | --- | --- | --- | --- |
| Page | 1 hour | 5 minutes | 14.4 | 2% |
| Page | 6 hours | 30 minutes | 6 | 5% |
| Ticket | 3 days | 6 hours | 1 | 10% |

Check the first row: 14.4 × 1 h ÷ 720 h = 2%. At that rate the whole budget lasts 50 hours, so someone should look now.

**A short window to confirm.** The long window alone keeps the alert firing long after recovery. The workbook adds a short window and fires only when both windows are above the threshold. Its guideline is "to make the short window 1/12 the duration of the long window." When errors stop, the short window drops below the threshold within minutes and the alert resets.

In Prometheus, this becomes recording rules for the error ratio over each window, plus alerts that combine them with `and`. A version for the transfer API, assuming a counter `transfer_requests_total` with an `outcome` label:

```yaml
groups:
  - name: transfers-slo
    rules:
      - record: transfers:error_ratio:rate5m
        expr: |
          sum(rate(transfer_requests_total{outcome="error"}[5m]))
          /
          sum(rate(transfer_requests_total[5m]))
      - record: transfers:error_ratio:rate1h
        expr: |
          sum(rate(transfer_requests_total{outcome="error"}[1h]))
          /
          sum(rate(transfer_requests_total[1h]))
      # ...same for 30m and 6h
      - alert: TransfersErrorBudgetFastBurn
        expr: |
          transfers:error_ratio:rate1h > (14.4 * 0.001)
          and
          transfers:error_ratio:rate5m > (14.4 * 0.001)
        labels:
          severity: page
        annotations:
          summary: "Transfers burning error budget 14.4x faster than allowed"
          runbook: "docs/runbooks/transfers-error-budget.md"
```

The workbook's own examples use the same structure with a generic `slo_errors` and `slo_requests` pair. It also shows the ticket rules with a 24-hour and 2-hour pair at 3x, next to the 3-day pair at 1x. The cost of this approach, as the workbook admits, is many parameters to manage.

**Low traffic.** The workbook warns that this math breaks with few requests. With 10 requests per hour, one failure is a 10% error rate for that hour, a burn rate of 1,000. Its options include synthetic traffic, grouping related services into one SLO, retries with backoff on the client side, and lowering the SLO or lengthening the window. Your local capstone has very low traffic. When you test the alert on Thursday, generate load with a script so the numbers mean something.

**From here to the lab.** Today's lab installs the OpenTelemetry SDK in NestJS and sends traces to Jaeger, which gives you the per-request view. The SLO alert itself is capstone item 3 on Thursday, after Tuesday's lab gives you Prometheus. Pick your SLI and its good and valid events today, so Thursday is only wiring.

## Notes to write today

1. A table of 5 wallet symptoms with 2 possible causes each, and the four golden signals for the transfer API (which metric, which unit, which label).
2. One SLI and one SLO for your capstone: the good event, the valid event, the target, the window, and the error budget in number of requests for a realistic monthly volume.
3. The burn-rate table for your SLO (2% in 1 hour, 5% in 6 hours, 10% in 3 days), with the arithmetic, and one sentence on why the short window exists.

## Check yourself

These make good flashcards (see the [flashcards guide](../../FLASHCARDS.md)).

- Why should pages be based on symptoms and not on causes?
- Name the four golden signals and one wallet metric for each.
- What is the difference between an SLO and an SLA, according to the "what happens if" test?
- Your SLO is 99.9% over 30 days and you serve 2 million requests. What is the error budget?
- What is a burn rate of 14.4, and how much budget does it spend in 1 hour?
- Why does adding `for: 1h` to an error-rate alert hurt recall and detection time?
- Why does the multiwindow approach use a short window of 1/12 of the long one?

## References

- **Main source:** Google, ["Site Reliability Engineering"](https://sre.google/sre-book/monitoring-distributed-systems/), chapter 6 "Monitoring Distributed Systems", by Rob Ewaschuk. Read it all, focusing on "Symptoms Versus Causes", "The Four Golden Signals" and "Worrying About Your Tail". Free.
- Google, ["Site Reliability Engineering"](https://sre.google/sre-book/service-level-objectives/), chapter 4 "Service Level Objectives". Read "Service Level Terminology", "Indicators in Practice" and "Objectives in Practice". Free.
- **Main source:** Google, ["The Site Reliability Workbook"](https://sre.google/workbook/alerting-on-slos/), chapter "Alerting on SLOs". Read the six approaches, the burn-rate tables and "Low-Traffic Services and Error Budget Alerting". Free.
