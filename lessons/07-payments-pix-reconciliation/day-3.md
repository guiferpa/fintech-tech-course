# Module 7, Wednesday: reconciliation and safe provider fallback

[Module 7](../../modules/07-payments-pix-reconciliation.md) · [Leia em português](day-3.pt-BR.md)

**Reading time:** about 45 minutes. Use the rest of the 2-hour block on the references at the end, then draw the fallback diagram described in section 5.

This is an original text written for this course. It is based on the references listed at the end, and each section names the source it follows. Where an idea comes from a specific author, the text says so.

## Why this matters for a fintech

On Monday you saw that every party in a payment keeps its own record. Your ledger says one thing, the acquirer's settlement file says another, and the partner bank's statement says a third. Usually they agree. When they don't, somebody is losing money: the customer, the merchant or you. **Reconciliation** is the process that compares those records and turns every disagreement into a ticket before it turns into a loss.

The module's mastery test asks what happens when a payment shown as "approved" is missing from the next day's settlement file. Today gives you the full answer: how to match records, how much tolerance to allow, what to do with what doesn't match, and how to switch providers during an outage without charging anyone twice.

## 1. What reconciliation is

*Main source: Modern Treasury documentation, "Reconciling received payments".*

Reconciliation compares two views of the same money: **what you expected to happen** and **what the bank or provider says happened**. Modern Treasury makes the first view an explicit object. An Expected Payment is used to "represent and reconcile a payment that you expect to receive or send (e.g., an invoice)." The second view is the **Transaction**, a line reported by the financial institution. Reconciliation links each Transaction to the Expected Payments it pays.

Two rules from this page shape any reconciliation engine:

- **All conditions must match.** The docs say an Expected Payment reconciles to a Transaction only "if all of the defined conditions are matched." A partial match is not a match.
- **Ambiguity is never resolved automatically.** "When multiple Expected Payments match the details of a transaction, they won't be automatically reconciled." Instead, they are flagged for manual review.

The second rule is the important one. A matcher that guesses between two candidates will sometimes guess wrong, and the error then hides inside a "reconciled" status where nobody looks. A matcher that refuses to guess produces more manual work but never lies.

In your wallet, the expected side is the ledger. Every captured card payment, every outgoing Pix and every refund creates an expectation: "the acquirer will settle this amount for this reference on or around this date". The actual side is the settlement CSV from your fake acquirers.

## 2. Matching rules and tolerances

*Main source: Modern Treasury documentation, "Defining Reconciliation Rules", "Advanced Matching Using Expected Payments" and "Valid conditions for Reconciliation Rules".*

A **reconciliation rule** is matching logic: a list of conditions that must be true for records to reconcile. Each condition is a field, an operator and a value. The value can be a constant (currency equals BRL) or a field on the other side (transaction direction equals expected payment direction). Conditions can be grouped with AND and OR.

**Order matters.** The docs say rules "are evaluated sequentially, starting with the first rule and finishing with the last rule." They advise putting specific rules first, such as those that match on a unique identifier, and broader rules after. In your wallet, the first rule is "same `acquirer_ref` or same `end_to_end_id`". A fallback rule could be "same amount, same day, same customer", but only if it produces exactly one candidate.

**Cardinality.** The docs list three strategies:

| Strategy | Example in a wallet |
| --- | --- |
| One transaction to one expected payment | One settlement line for one captured payment |
| One transaction to many expected payments | The acquirer pays one lump sum for a whole day of captures |
| Many transactions to one expected payment | A payment settled in installments |

The docs give an example of the second strategy, "a $100 Transaction reconciles to a group of three Expected Payments with amounts of $10, $20, $70." Under the third, an Expected Payment becomes reconciled "once the sum of the amounts of its reconciled Transactions equals its amount."

**Tolerances.** Real amounts and dates drift. Modern Treasury offers three kinds of tolerance:

- **Amount range.** An Expected Payment can carry `amount_lower_bound` and `amount_upper_bound`, and a Transaction reconciles when its amount falls within the range. This absorbs fees, taxes or currency swings.
- **Amount variance on grouped matches.** One-to-many rules accept a variance of type `fixed` (in the smallest currency unit, so 500 means $5) or `percentage`.
- **Date window.** The Transaction's `as_of_date` must fall between the Expected Payment's `date_lower_bound` and `date_upper_bound`.

Tolerance is a business decision, not a technical one. If your acquirer deducts a 2.5% fee, compare the net amount from the file against gross minus the expected fee, and keep the tolerance for rounding only (a cent or two). A wide tolerance hides real errors. For dates, a window of one or two business days around the expected settlement date catches holidays and late files without hiding a payment that never arrived.

## 3. Discrepancies and how to report them

*Main source: Modern Treasury documentation, "Exception Handling - Manual Reconciliation", applied to the capstone's discrepancy types.*

Whatever the automatic rules can't match goes to manual reconciliation. Modern Treasury's interface shows unreconciled Transactions next to Expected Payments, displays the difference between the selected items (the docs note that "In most cases, this will be 0"), and lets an operator reconcile them, adjusting amounts where needed. Each manual reconciliation emits a webhook, so other systems learn about it.

Your capstone job won't have a UI, but it needs the same result: every record ends up either matched or in a **discrepancy report** with a clear type. The module lists four planted discrepancies. Here they are with a fifth that the job should detect too:

| Type | What you see | Likely cause | First action |
| --- | --- | --- | --- |
| Missing in file | Ledger has a captured payment; no settlement line | Capture never reached the acquirer, or the file is late | Query the acquirer's status for that reference |
| Missing in ledger | Settlement line with no ledger entry | Your capture timed out, the acquirer processed it, you marked it failed | Query status; post the missing entry or refund |
| Duplicate | Two settlement lines for one reference | Retry without idempotency at the acquirer, or a file loaded twice | Check file ids; if real, refund the extra charge |
| Different amount | Same reference, amounts differ beyond tolerance | Partial capture, wrong fee, currency error | Compare against the authorization and the contract |
| Wrong date | Matched, but outside the date window | Holiday, late batch, time zone bug | Flag; escalate if it repeats |

A full outer join is the natural first pass in Postgres. It finds both kinds of "missing" in one query. Load each CSV into a staging table first, normalized to one format.

```sql
SELECT l.payment_id, s.acquirer_ref,
       l.amount_cents  AS ledger_cents,
       s.net_cents     AS file_cents,
       CASE
         WHEN s.acquirer_ref IS NULL THEN 'MISSING_IN_FILE'
         WHEN l.payment_id  IS NULL THEN 'MISSING_IN_LEDGER'
         WHEN abs(l.expected_net_cents - s.net_cents) > 1 THEN 'AMOUNT_MISMATCH'
         WHEN s.settlement_date NOT BETWEEN l.expected_date - 1 AND l.expected_date + 2
              THEN 'DATE_MISMATCH'
         ELSE 'MATCHED'
       END AS result
FROM ledger_expected l
FULL OUTER JOIN settlement_staging s ON s.acquirer_ref = l.acquirer_ref;
```

Duplicates need a separate check before the join (`GROUP BY acquirer_ref HAVING count(*) > 1`), otherwise the join silently produces two "matched" rows. Two more practical rules: write the report to a table with the run id, so you can see how a discrepancy evolves across days; and never let the reconciliation job change the ledger by itself. It reports, and a separate, audited action fixes.

## 4. Transactional integrity at Airbnb

*Main source: Airbnb Engineering, "Measuring Transactional Integrity in Airbnb's Distributed Payment Ecosystem", sections "What is transactional integrity?", "What is an out-of-sync transaction?" and "Payment reconciliation using traditional tools is not sufficient".*

The Airbnb authors (Ninad Khisti and William Betz) define the goal in one sentence: "When it comes to payments, transactional integrity represents a no-surprise, accurate money movement." Airbnb uses several gateways and dozens of processors, and each extra party adds a place where a transaction can fall **out of sync**: one side believes something different from the other. The post names the causes. A system in the chain doesn't respond, a downstream system mishandles a response, or a batch process with a bank leaves the systems out of sync until the response files arrive.

The most useful part of the post explains why classic reconciliation was not enough for them. Traditional tools give "only an overall picture", without results for each stage of the process. They also reconcile only "when money exchanges hands", skip transactions already matched, and match on identifying attributes instead of comparing everything. Airbnb's pipeline does the opposite:

- **Compare every transaction**, including the ones that move no money, such as voids.
- **Compare every attribute**: amount, currency, status, payment method and timing, not just the id.
- **Compare every stage**: internal stores against gateway data against processor reports.
- **Measure from day zero**, the day the new gateway started taking real traffic.

The mechanics are batch: processors send daily reports, which land in S3; database snapshots go to HDFS at regular intervals; Hive compares the schemas; and anomalies are grouped by type. Dashboards in Superset, backed by Druid, show an integrity score per category (payments, refunds, payouts and returns). Alerts go out by email or Slack after each pipeline run, including when a processor's report is missing or late.

The results the post reports should sound familiar after Monday. The analysis helped them tune "socket timeouts, error handling, and retry mechanisms", and cut down high-volume support tickets. Its future plans include stronger idempotency, because safe retries need a guarantee that money moves once.

For your wallet, two ideas transfer directly. First, a missing or late settlement file is itself a discrepancy and should page someone. Second, compare status and timing, not just amount: a payment `CAPTURED` in your ledger and `VOIDED` at the acquirer has matching ids and amounts, and is still wrong.

## 5. Provider orchestration: routing and safe fallback

*Main source: no single reference. This section combines the unknown-outcome rule from Module 1, the lease and status-query rules from Monday's Airbnb post, and the attempt model from Stripe's Payment Intents.*

A wallet with two acquirers wants to use the second when the first fails. Routing (choosing a provider per payment) is simple: by cost, by card brand, by health, or by a percentage split. **Fallback** (trying another provider for the same payment) is where double charges come from.

The trap is the timeout. Your call to acquirer A times out. If you immediately send the same payment to acquirer B, and A had actually approved it, the customer is charged twice. Remember Module 1: a timeout means "I don't know". The rule this module asks you to draw is:

**timeout → status query → only then another provider.**

```text
call A (idem key k-A) ──► success ─────────────► done (A)
        │
        ├─► definite decline (4XX, non-retryable) ─► stop or try B (new attempt)
        │
        └─► timeout / 5XX ──► attempt = UNKNOWN
                               │
                               ▼
                    query A status by k-A (with backoff, past A's lease)
                               │
              ┌────────────────┼──────────────────┐
              ▼                ▼                  ▼
         found: approved   found: failed      still unknown
         → done (A)        → try B            → keep waiting; or cancel/void
                                                 at A and confirm; never try B
```

The rules that make this safe:

- **One payment, many attempts.** Each provider call is a row in `payment_attempts` with its own idempotency key. Retries to the same provider reuse the key; a fallback to B creates a new attempt with a new key.
- **At most one live attempt.** A partial unique index stops a second attempt while one is pending or unknown:

```sql
CREATE UNIQUE INDEX one_live_attempt_per_payment
  ON payment_attempts (payment_id)
  WHERE state IN ('PENDING', 'UNKNOWN', 'COMPLETED');
```

  With this index, the database itself refuses to start attempt B while attempt A is `UNKNOWN` or `COMPLETED`. Only a failed attempt frees the slot.
- **Decide on facts.** Move an attempt to `FAILED_FINAL` only when the provider says so: a definite decline, a status query saying "failed", or a confirmed void. "Not found" right after a timeout is not proof, because the request may still be in flight. Wait until the provider's lease or processing window has passed, and query again.
- **Late success is still success.** If A's approval arrives (by webhook or query) after you gave up, record it and void or refund it at once. Reconciliation would catch it anyway, as a "missing in ledger" line.
- **Trip the breaker per provider.** When A's error rate climbs, route new payments to B. Only new payments: those already sent to A stay with A until resolved. Module 9 covers circuit breakers in depth.

The capstone's pass criterion is "the fallback never charges on both providers". The index above and the status query are how you prove it. Your test should inject a timeout at A after A records the charge, then assert that B was never called.

## 6. Preparing the capstone

*Main source: the module page's Wednesday lab and the Thursday and Friday tasks.*

Tonight's lab produces inputs, not code: CSV files with planted discrepancies and a task list for Thursday and Friday. Make the plants deliberate and write down the expected result for each, so Friday's test can assert "100% detected".

- Two days of settlement files per acquirer, one with each discrepancy type from section 3.
- One "approved but not settled" case, which is the mastery test scenario.
- One case where acquirer A charged during a timeout, to exercise the fallback.
- An `expected_results.csv` listing each planted row and the discrepancy type the job must report.

Then rehearse the mastery answer. A good two-minute answer covers: the payment is a ledger entry with an expected settlement date; the daily job matches by acquirer reference and reports it as "missing in file"; the first action is a status query to the acquirer, not an automatic fix; depending on the answer, you wait for a late file, recapture, or reverse the entry and notify the customer; and a missing file or a growing count of such cases raises an alert.

## Notes to write today

1. Reconciliation: expected vs. actual records, matching rules evaluated in order from specific to broad, the three cardinalities, and why ambiguous matches are never reconciled automatically.
2. Tolerances: amount range, variance (fixed vs. percentage) and date window. Write the values you will use in the capstone and why.
3. The discrepancy types (missing in file, missing in ledger, duplicate, different amount, wrong date), with the likely cause and first action for each.
4. Airbnb's view of transactional integrity: out-of-sync transactions, and why they compare every transaction, attribute and stage.
5. On paper: your fallback diagram, timeout → status query → only then another provider. Mark where the idempotency key changes and which database constraint stops a double charge.

## Check yourself

These make good flashcards (see the [flashcards guide](../../FLASHCARDS.md)).

- Why should a reconciliation engine refuse to auto-match when two candidates fit?
- Why does rule order matter, and which rules go first?
- What is the risk of a wide amount tolerance?
- Which SQL join finds both "missing in file" and "missing in ledger" in one pass?
- What did Airbnb say traditional reconciliation tools miss?
- After a timeout at provider A, what must happen before you try provider B?
- Why is "not found" from a status query right after a timeout not enough to fall back?

## References

- **Main source:** Modern Treasury documentation, ["Reconciliation Overview"](https://docs.moderntreasury.com/reconciliation/docs). The link currently opens the payments overview; follow the sidebar to ["Reconciling received payments"](https://docs.moderntreasury.com/payments/docs/managing-externally-originated-payments), ["Defining Reconciliation Rules"](https://docs.moderntreasury.com/payments/docs/defining-reconciliation-rules), ["Advanced Matching Using Expected Payments"](https://docs.moderntreasury.com/payments/docs/advanced-matching-using-expected-payments), ["Valid conditions for Reconciliation Rules"](https://docs.moderntreasury.com/payments/docs/valid-conditions-for-reconciliation-rules) and ["Exception Handling - Manual Reconciliation"](https://docs.moderntreasury.com/payments/docs/exception-handling-manual-reconciliation). Free.
- **Main source:** Airbnb Engineering, ["Measuring Transactional Integrity in Airbnb's Distributed Payment Ecosystem"](https://medium.com/airbnb-engineering/measuring-transactional-integrity-in-airbnbs-distributed-payment-ecosystem-a670d6926d22), by Ninad Khisti and William Betz. Read it all. Free.
- Provider orchestration: routing and safe fallback. A task, not a reading: draw the diagram from section 5 on paper. Reread Monday's Airbnb post ["Avoiding Double Payments in a Distributed Payments System"](https://medium.com/airbnb-engineering/avoiding-double-payments-in-a-distributed-payments-system-2981f6b070bb), sections on leases and retryable errors, as support. Free.
