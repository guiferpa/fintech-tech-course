# Module 10, Wednesday: incidents, runbooks, postmortems and the double-charge detector

[Module 10](../../modules/10-observability-and-operations.md) · [Leia em português](day-3.pt-BR.md)

**Reading time:** about 45 minutes. Use the rest of the 2-hour block on the references at the end, then design the double-charge detector on paper as described in sections 6 and 7.

This is an original text written for this course. It is based on the references listed at the end, and each section names the source it follows.

## Why this matters for a fintech

Monday and Tuesday were about knowing something is wrong. Today is about what people do next. An alert at 3 a.m. is only useful if the person who receives it knows what to check, who to call and when to stop. And once the incident is over, the team needs to learn from it without turning it into a hunt for someone to blame.

For a wallet, the incident that matters most this week is the double charge. The module's pass criterion is that an injected double charge fires an alert with nobody watching the dashboard. So today ends with two designs on paper: the detector (query, window, threshold) and the incident you'll inject on Friday to prove it works.

## 1. What an incident is, and how severe it is

*Main source: PagerDuty Incident Response documentation, "What is an Incident?" and "Severity Levels".*

PagerDuty's documentation is a public version of the process the company uses internally for major incidents. It defines an incident as "Any unplanned disruption or degradation of service that is actively affecting customers ability to use PagerDuty." Replace "PagerDuty" with your wallet, and you have a working definition. It also defines a **major incident** as one that needs a coordinated response between multiple teams.

PagerDuty ranks incidents from SEV-1 (most severe) to SEV-5:

| Level | PagerDuty's description, in short | Wallet example |
| --- | --- | --- |
| SEV-1 | Critical; warrants public notice and executive involvement | Customers charged twice at scale |
| SEV-2 | Critical issue affecting many customers | Transfers failing for everyone |
| SEV-3 | Stability or minor customer impact, needs immediate attention | One provider declining more than usual, fallback working |
| SEV-4 | Minor issue, no impact on using the product | One worker pod restarting in a loop |
| SEV-5 | Cosmetic issue or bug | Wrong label in an internal dashboard |

Two pieces of guidance from that page are worth keeping. If you're unsure between two levels, treat it as the higher one. And during an incident is not the time to argue about severity: assume the higher level and review it in the postmortem. PagerDuty also recommends that each organization make its levels specific and metric-driven, usually by the share of customers affected. For a wallet, you can add money: "any confirmed double charge is at least SEV-2" is a clear rule.

The same docs say that anyone can trigger the incident process, and you don't need to set a severity before starting. On the "During an Incident" page, they add: "Never hesitate to page the IC."

## 2. Roles during an incident

*Main source: PagerDuty Incident Response documentation, "Different Roles" and "During an Incident".*

The idea behind incident roles is that the people fixing the problem should not also be coordinating, writing updates and answering executives. PagerDuty separates these jobs:

| Role | What PagerDuty says it does |
| --- | --- |
| **Incident Commander (IC)** | Drives the incident to resolution and is the single source of truth about what's happening. Delegates all repair work. |
| **Deputy** | Supports the IC, keeps track of what's being missed, and acts as a hot standby IC. |
| **Scribe** | Writes the timeline as the incident progresses: actions, findings, status updates. |
| **Subject Matter Expert (SME)** | Owner of a service. Diagnoses and fixes, and reports to the IC. |
| **Customer Liaison** | Writes and posts public updates once the IC approves them. |
| **Internal Liaison** | Pages more people when the IC asks, and keeps internal stakeholders informed. |

The sentence from the roles page to remember is: "Delegate all repair actions, the Incident Commander is NOT a resolver." The IC who starts reading logs stops coordinating, and nobody notices that the Customer Liaison is waiting for approval to post an update.

The SME role has its own rule in "During an Incident": share your suggested fixes with the IC, but "do not follow any actions unless told to do so!" Two engineers running unrelated fixes at the same time make the incident harder to understand. In a wallet, imagine one engineer replaying the dead-letter queue while another is refunding duplicates by hand.

In a small team, one person can hold several roles. PagerDuty mentions the Deputy also acting as Scribe and Internal Liaison in smaller incidents. In your capstone, you're alone, so you'll play all of them. Still, write the timeline as a Scribe would: that timeline becomes the core of your postmortem.

## 3. Alerts that lead somewhere: runbooks

*Main source: PagerDuty Incident Response documentation, "Alerting Principles". The runbook template is this course's.*

PagerDuty's alerting page starts from a strict definition: "An alert is something which requires a human to perform an action." Anything else is a notification and shouldn't wake anyone. That matches Monday's rule from the SRE book that every page should be actionable.

The page sorts alerts by urgency:

- **High:** pages 24/7 and needs immediate action.
- **Medium:** high priority, but sent only during business hours.
- **Low:** someone should act eventually, with no urgency.
- **Notification:** no page at all, only context for later.

It then says what an alert must contain: a clear title, the metric that triggered it, a description of the problem and why it matters, and a resolution path. The resolution path is either the steps to fix it or a link to a **runbook**. PagerDuty's verdict on alerts with neither: "Alerts with neither of these things are useless."

A runbook is the page the on-call person opens when the alert fires. The PagerDuty docs require the link but don't prescribe a format, so here is a structure for this course. It works well for a double charge:

1. **What this alert means.** One paragraph, in plain words. "At least one payment has two capture postings in the ledger."
2. **Impact.** Who is hurt and how. "Customers lose money until refunded. Treat as SEV-2 or higher."
3. **First checks (5 minutes).** Exact queries and dashboard links. Is it one payment or many? One provider or all? Did a deploy happen in the last hour?
4. **Stop the bleeding.** The safest action that stops new damage, for example pausing the payment worker's consumer group, or turning off the provider with a feature flag. Say what it costs.
5. **Fix the damage.** How to list affected payments and how to reverse them through the ledger (reverse entries, never deleting rows).
6. **Escalation.** Who to page, and when. "If more than 10 customers are affected, page the IC."
7. **Close.** How to confirm it's over: the detector at zero for 30 minutes, reconciliation clean.

The same page closes with a rule you will apply on Friday: "An untested alert is equivalent to not having an alert at all." It asks you to test thresholds, to make "No Data" trigger an alert where it makes sense (missing data usually means something broke), and to check that the alert resolves on its own when the metric returns to normal.

## 4. Blameless postmortems

*Main source: Google SRE book, chapter 15, "Postmortem Culture: Learning from Failure".*

The SRE book defines a **postmortem** as a written record of an incident: its impact, the actions taken to mitigate or resolve it, the root causes, and the follow-up actions to prevent it from happening again.

**When to write one.** The book lists common triggers. They include user-visible downtime or degradation beyond a threshold, data loss of any kind, on-call intervention such as a rollback or rerouting traffic, a resolution time above a threshold, and a monitoring failure, which usually means a human found the incident by hand. The book stresses defining these criteria before an incident happens. For a wallet, add a trigger of your own: any incorrect movement of customer money, of any size.

**Blameless.** The book states that blameless postmortems are a tenet of SRE culture, and notes that the idea comes from healthcare and avionics, where mistakes can be fatal. A blameless postmortem assumes everyone acted with good intentions and the information they had at the time. It focuses on the contributing causes, not on who made the mistake. The reasoning is practical: if people get punished for incidents, they stop reporting them, and problems stay hidden until they're bigger. The chapter's shortest version is: "You can't 'fix' people, but you can fix systems and processes to better support people making the right choices when designing and maintaining complex systems."

See the difference in a wallet example:

- Blameful: "Ana deployed a consumer without the inbox check and caused 300 double charges."
- Blameless: "The consumer was deployed without the inbox check. No test covered redelivery, and the review checklist didn't mention idempotency. The detector paged 4 minutes after the first duplicate."

The second version has more information, and every sentence leads to an action item: a redelivery test, a checklist line, a faster detector.

**Review and sharing.** The book says a postmortem is reviewed by senior engineers before it's published. The review criteria include whether key data was collected, whether the impact assessment is complete, whether the root cause analysis went deep enough, whether the action plan and bug priorities are appropriate, and whether the outcome was shared with stakeholders. Its blunt line: "An unreviewed postmortem might as well never have existed."

**Building the culture.** The chapter describes activities such as a postmortem of the month shared in a newsletter, postmortem reading clubs, and the "Wheel of Misfortune", where a past postmortem is reenacted with engineers playing the roles. In interviews, being able to describe a blameless postmortem you wrote is a strong signal of seniority.

## 5. The postmortem process in practice

*Main source: PagerDuty Incident Response documentation, "Postmortem Process".*

PagerDuty's process adds concrete steps that fit well with the SRE book's culture:

- A postmortem is required for every major incident (SEV-2 and SEV-1).
- The IC assigns an **owner** at the end of the incident. The owner writes the document and runs the investigation.
- The meeting happens within 3 calendar days for SEV-1 and within 5 business days for SEV-2.
- The owner starts with the **timeline**, and every item in it has a source: a metric, a graph or a log search.
- The analysis covers the cause, the underlying cause and the customers affected, and includes the queries and commands used.
- Follow-up tickets are limited to high-priority items, and the team accepts trade-offs where the return doesn't justify the effort.

For capstone item 6, a short postmortem in `docs/m10.md` can follow this outline: summary, impact (customers, amount, duration), timeline with sources, how it was detected, root cause and contributing factors, what went well, what went badly, action items with an owner each. The most important timeline entries for this module are "first duplicate written" and "alert fired": the gap between them is your detection time.

## 6. Designing the double-charge detector

*This section is this course's design for the capstone. It applies Monday's rules (alert on symptoms, every page actionable) and Tuesday's metric advice.*

First, define precisely what a double charge is in your wallet. There are two kinds, and they need different detectors.

**Hard duplicate.** One payment has more than one capture posting in the ledger. This is always a bug: the idempotency key or the inbox failed. Nothing legitimate produces it, so the threshold is zero.

```sql
-- Hard duplicates: payments captured more than once in the last 15 minutes
SELECT payment_id, count(*) AS captures
FROM ledger_entries
WHERE kind = 'CAPTURE'
  AND created_at > now() - interval '15 minutes'
GROUP BY payment_id
HAVING count(*) > 1;
```

**Soft duplicate.** Two different payments with the same customer, merchant and amount, a short time apart. This is the case where the customer tapped "pay" twice and two idempotency keys were created, or a client retried without reusing the key. Some of these are legitimate (two coffees), so the signal is a ratio, not a single row.

```sql
-- Soft duplicates: same customer, merchant and amount within 2 minutes
SELECT count(*) AS suspicious
FROM (
  SELECT created_at,
         lag(created_at) OVER (
           PARTITION BY customer_id, merchant_id, amount_cents
           ORDER BY created_at
         ) AS prev_at
  FROM payments
  WHERE status = 'CAPTURED'
    AND created_at > now() - interval '15 minutes'
) p
WHERE created_at - prev_at < interval '2 minutes';
```

Adapt the table and column names to your schema. Both queries need an index that starts with `created_at`, or they will scan the table every minute.

Now the three decisions the module asks for:

| | Hard duplicate | Soft duplicate |
| --- | --- | --- |
| **Query** | Captures per `payment_id` | Same customer, merchant, amount within 2 minutes |
| **Window** | Last 15 minutes, run every minute | Last 15 minutes, run every minute |
| **Threshold** | More than 0 rows: page | Ratio of suspicious to total captures above your normal baseline: ticket, or page if far above |
| **Severity** | SEV-2 or higher | SEV-3 until confirmed |

Why 15 minutes? It must be longer than the job interval plus the delay of the slowest path (a Kafka redelivery after a consumer restart can take minutes), and short enough that the alert fires before the morning. Write your own reasoning down. The numbers above are a starting point, not a rule from the references.

To get the result into Prometheus, a small job runs both queries every minute and sets two gauges, for example `wallet_hard_duplicate_captures` and `wallet_soft_duplicate_ratio`. It also sets a gauge with the Unix timestamp of its last successful run, following Tuesday's batch-job advice. Then three alert rules:

```yaml
- alert: DoubleChargeDetected
  expr: wallet_hard_duplicate_captures > 0
  labels:
    severity: page
  annotations:
    summary: "{{ $value }} payments captured more than once in 15 minutes"
    runbook: "docs/runbooks/double-charge.md"
- alert: DoubleChargeDetectorStale
  expr: time() - wallet_duplicate_detector_last_success_timestamp_seconds > 300
  labels:
    severity: page
- alert: DoubleChargeDetectorMissing
  expr: absent(wallet_hard_duplicate_captures)
  labels:
    severity: page
```

The last two follow PagerDuty's "No Data" advice. A detector that stopped running reports nothing, and "nothing" looks exactly like "no double charges". Without these rules, a crashed job gives you a green dashboard during the worst incident of the year.

This is also the answer to the mastery question. If 2% of payments were charged twice, the hard-duplicate gauge would be far above zero within one job interval, and the page would fire with nobody looking. Reconciliation against the provider's file (Module 7) is the second line of defense: it catches duplicates that happened outside your ledger, but only once a day.

## 7. Planning the incident you'll inject

*This section is this course's plan for capstone items 4 and 5, following PagerDuty's rule that an untested alert is no alert.*

On Friday you'll break your own system on purpose and check that the alert fires. Plan it on paper today, the way a game day is planned.

1. **The fault.** Choose a realistic way to create a hard duplicate. Good options: a flag that skips the inbox check in the consumer, then republishing an already processed Kafka message; or calling the capture step twice for the same payment in a test script. Don't edit rows by hand in the database: you want the real code path to write the duplicate.
2. **The expected detection.** Write down when the alert should fire. If the job runs every minute and Prometheus evaluates rules every 15 seconds, the page should arrive in about 2 minutes. Alertmanager's grouping settings, which you'll configure in today's lab, add delay too, so include them.
3. **The evidence.** List what you'll capture: the time of the injection, the time the alert fired, the Alertmanager notification, the trace of the duplicated processing in Jaeger, and the detector's query output.
4. **The recovery.** Turn the fault off, reverse the duplicate through the ledger, and confirm the alert resolves on its own.
5. **The write-up.** Use the evidence to write the postmortem in `docs/m10.md`, with your detection time as a number.

Today's lab installs Alertmanager in Compose and produces the task list for Thursday and Friday. No capstone code today. Make sure Alertmanager can deliver to somewhere you'll actually see (a webhook receiver or a local log is enough), since the pass criterion is that nobody is watching the dashboard.

## Notes to write today

1. The six PagerDuty incident roles in one line each, and which of them you'll play in your capstone incident.
2. The postmortem outline you'll use in `docs/m10.md`, with the SRE book's triggers and review criteria, and one blameful sentence rewritten as blameless.
3. The double-charge detector on paper: the hard and soft queries, the window, the threshold and severity for each, the gauges and alert rules, and the rules for a missing or stale detector.
4. The incident you'll inject: the fault, how you'll trigger it, the expected detection time, the evidence to collect, and the recovery steps.

## Check yourself

These make good flashcards (see the [flashcards guide](../../FLASHCARDS.md)).

- What is PagerDuty's rule when you're unsure between two severity levels?
- Why is the Incident Commander "NOT a resolver"?
- What must every alert contain, according to PagerDuty's alerting principles?
- Name three postmortem triggers from the SRE book.
- What makes a postmortem blameless, and why does blame make systems less reliable?
- What is the difference between a hard and a soft double charge, and why does each need a different threshold?
- Why do you need an alert for a missing or stale detector?

## References

- **Main source:** Google, ["Site Reliability Engineering"](https://sre.google/sre-book/postmortem-culture/), chapter 15 "Postmortem Culture: Learning from Failure". Read it all. Free.
- **Main source:** PagerDuty, ["Incident Response documentation"](https://response.pagerduty.com/). Read "What is an Incident?", "Severity Levels", "Different Roles" and "During an Incident" under "Before" and "During", plus ["Alerting Principles"](https://response.pagerduty.com/oncall/alerting_principles/) and the ["Postmortem Process"](https://response.pagerduty.com/after/post_mortem_process/). Free.
