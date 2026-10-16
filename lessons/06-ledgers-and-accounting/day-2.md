# Module 6, Tuesday: holds, account invariants and missing money

[Module 6](../../modules/06-ledgers-and-accounting.md) · [Leia em português](day-2.pt-BR.md)

**Reading time:** about 45 minutes. Use the rest of the 2-hour block on the references at the end.

This is an original text written for this course. It is based on the references listed at the end, and each section names the source it follows.

## Why this matters for a fintech

Yesterday's ledger records money that already moved. Most wallet operations are not like that. A card purchase reserves money first and settles later. A transfer to a partner bank leaves the wallet before the bank confirms it. A ride-hailing app reserves R$ 50 and charges R$ 37. Each of these needs a **hold**: money that is no longer available but not yet gone.

Holds bring two questions that interviewers love. How do you reserve money so that the final step can never overdraw the account? And when a hold or a transfer gets stuck halfway, how do you notice? TigerBeetle answers the first one in its data model. Stripe's Ledger answers the second one with a simple rule about which balances should be zero.

## 1. A hold is a two-phase transfer

*Main source: TigerBeetle documentation, "Two-Phase Transfers".*

TigerBeetle is a database built only for double-entry accounting. Its documentation describes a **two-phase transfer**: a transfer that moves money in two steps instead of one. The name comes from the two-phase commit protocol for distributed transactions.

- **Phase 1, reserve.** A transfer created with the `pending` flag reserves its amount. It adds the amount to the debit account's `debits_pending` and to the credit account's `credits_pending`. The posted balances do not change.
- **Phase 2, resolve.** Later, the reservation is resolved in exactly one of three ways: it is **posted**, **voided**, or it **expires**.

Map this to the wallet. Ana pays R$ 100 at a gas station by card. The authorization arrives; the wallet creates a pending transfer from Ana's wallet to a card settlement account. Ana's available balance drops by R$ 100 immediately, but her posted balance stays the same. When the network sends the final amount, the wallet posts the transfer. If the authorization is canceled, it voids it. If nothing arrives in time, it expires.

This is the same pending/posted/available model you saw yesterday in "How to Scale a Ledger". Different vendor, same idea: pending amounts sit in their own counters until something resolves them.

## 2. Post, partial post, void and expire

*Main source: TigerBeetle documentation, "Two-Phase Transfers".*

The documentation is precise about the second phase. Here is what each outcome does.

| Outcome | How it is requested | Effect |
| --- | --- | --- |
| Post in full | New transfer with `post_pending_transfer` flag and `pending_id`, amount equal to the pending amount | The full amount moves from pending to posted on both accounts |
| Partial post | Same, with an amount smaller than the pending amount | Only that amount is posted; the rest goes back to the original accounts |
| Over-post | Same, with an amount larger than the pending amount | Rejected with `exceeds_pending_transfer_amount` |
| Void | New transfer with `void_pending_transfer` flag and `pending_id` | The reservation is released; posted balances do not change |
| Expire | The pending transfer was created with a `timeout` that passed | The full amount returns, as if voided |

The documentation's numeric example: a pending transfer of 123 adds 123 to the pending counters. Posting 100 of it adds 100 to `debits_posted` and `credits_posted`, removes the whole reservation from the pending counters, and the other 23 simply returns. That is exactly the gas station case. The authorization was R$ 100, the fuel cost R$ 80, and R$ 20 goes back to Ana's available balance.

Three rules make the model safe, and each one matches something you built in earlier modules:

1. **A pending transfer is resolved only once.** Trying again fails with `pending_transfer_already_posted`, `pending_transfer_already_voided` or `pending_transfer_expired`. A duplicate "capture" message from the card network cannot capture twice. That is idempotency (Module 2) built into the data model.
2. **Transfers are immutable.** Posting or voiding never edits the pending transfer. It creates a new transfer, with its own `id`, that points to the original through `pending_id`. History stays complete.
3. **Timeouts are intervals in seconds**, not wall-clock deadlines. Module 1 explained why: clocks on different machines disagree, so "expire at 14:00:00" means different things on different nodes.

The most important property is about balance limits. The documentation says the second step "will never cause the accounts' configured balance invariants" to break, whether it posts or voids. The reason is that the limit is checked in phase 1, when the money is reserved. Once a reservation exists, posting it (or part of it) can only consume money that was already set aside. Your Thursday capstone depends on this: if `available >= 0` is checked when the hold is created, capture and release never need to check it again.

## 3. The TigerBeetle account model

*Main source: TigerBeetle documentation, "Account" reference.*

The account reference is short, and reading it is a good lesson in how little a ledger account needs. The main fields are:

| Field | Meaning |
| --- | --- |
| `id` | 128-bit identifier chosen by the client, unique in the cluster |
| `debits_pending`, `debits_posted` | Sums of pending and posted debits |
| `credits_pending`, `credits_posted` | Sums of pending and posted credits |
| `user_data_128`, `user_data_64`, `user_data_32` | Optional links to external entities, such as your user ID |
| `ledger` | Partitions the accounts that can transact with each other |
| `code` | A user-defined category of the account |
| `flags` | Extra behavior, such as balance limits |
| `timestamp` | Creation time in nanoseconds, set by the cluster |

Some details are worth noticing:

- **There is no balance field.** The account keeps four counters, and you compute balances from them, exactly like the four sums in yesterday's formulas. The four counters must be zero when the account is created.
- **Amounts are unsigned 128-bit integers.** No decimals and no floating point. Money is a count of the smallest unit.
- **`ledger` separates what must never mix.** The docs describe it as an identifier "that partitions the sets of accounts that can transact with each other". A common use is one ledger per currency, so a transfer between a BRL account and a USD account is impossible by construction.
- **Accounts are immutable after creation, except for the balance counters.** You cannot "edit" an account's type or currency.

The reference also lists the global invariants: the sum of all `debits_pending` equals the sum of all `credits_pending`, and the sum of all `debits_posted` equals the sum of all `credits_posted`. That is yesterday's zero-sum rule, stated separately for each phase.

## 4. Balance limits as flags

*Main source: TigerBeetle documentation, "Account" reference, section "flags".*

Two flags let the database itself refuse an overdraft. The documentation gives the exact checks:

- `debits_must_not_exceed_credits`: a transfer is rejected if `debits_pending + debits_posted + amount > credits_posted`.
- `credits_must_not_exceed_debits`: a transfer is rejected if `credits_pending + credits_posted + amount > debits_posted`.

The two flags cannot both be set on the same account. Which one fits a wallet? A customer wallet is credit normal (a liability, from Monday). Its balance is credits minus debits, and it must not go below zero. So the wallet uses `debits_must_not_exceed_credits`.

Now look closely at the check. On its left side are all debits, pending and posted. On its right side are only posted credits. Rearranged, the rule says `credits_posted - (debits_posted + debits_pending) >= amount`. That is Monday's **available balance** formula from "How to Scale a Ledger", with the pending debits counted and the pending credits ignored. Two independent sources arrive at the same rule. Money that has not arrived yet cannot be spent, and money that is reserved cannot be spent twice.

The two-phase documentation shows the check in action. An account has the flag, `credits_posted = 100` and `debits_posted = 70`. A new pending transfer of 50 would bring debits to 120, which is more than 100, so it fails immediately, at reservation time.

Other flags in the reference are worth knowing by name: `linked` (chain several operations so they all succeed or all fail), `history` (keep the balance after every transfer, needed to query past balances), `imported` (load historical data with its own timestamps) and `closed` (reject new transfers, except voiding pending ones).

In Postgres you do not get these flags for free, but you can copy the rule. Before inserting a pending debit on a wallet, inside the same database transaction and with the account protected from concurrent writers (Wednesday's topic), check:

```sql
SELECT
  COALESCE(SUM(p.amount) FILTER (WHERE p.direction = 'credit' AND t.status = 'posted'), 0)
  - COALESCE(SUM(p.amount) FILTER (WHERE p.direction = 'debit' AND t.status IN ('pending', 'posted')), 0)
    AS available
FROM postings p
JOIN ledger_transactions t ON t.id = p.transaction_id
WHERE p.account_id = $1;
-- reject the hold if available < requested amount
```

This is the property your Friday property-based test will hammer: no sequence of 10,000 operations may make `available` negative.

## 5. How a ledger notices missing money

*Main source: Stripe blog, "Ledger: Stripe's system for tracking and validating money movement", by Ilya Ganelin, 2024.*

Stripe's post describes Ledger, its internal system of record for money movement. The scale numbers are striking: about five billion events per day, and over 99.9999% of money movement explainable. But the most useful idea for you is a simple one.

Ledger models every system that touches money as accounts and events that move balances between them. Ganelin uses a water analogy: "At steady state, terminal (nonclearing) reservoirs are full, and intermediate (clearing) pipes are empty." And then: "If there is water stuck in the pipes, then you have a problem."

Translate it to the wallet. Some accounts are **terminal**: a customer's wallet, the company's revenue. Their balances are supposed to be nonzero. Other accounts are **clearing** accounts: they exist only to hold money while a flow is in progress. When the flow finishes, they must go back to zero.

A transfer from Ana's wallet to an external bank via the partner bank shows the pattern:

| Step | Debit | Credit |
| --- | --- | --- |
| 1. Wallet sends the transfer to the partner bank | Wallet: Ana, R$ 200 | Clearing: outbound transfers, R$ 200 |
| 2. Partner bank confirms settlement | Clearing: outbound transfers, R$ 200 | Cash: partner bank, R$ 200 |

After step 2, the clearing account is back to zero for this transfer. Now suppose step 2 never happens because the confirmation webhook was lost, or because it was posted against the wrong transfer. The R$ 200 sits in the clearing account. Nothing is "missing" from the sum, since the ledger still balances, but water is stuck in the pipe. A daily query for clearing accounts with a nonzero balance older than the expected settlement time finds it. Stripe's post gives a real case of this shape: a release event carrying the wrong business ID left funds in an account where they should have cleared.

Ganelin describes three data quality questions that Stripe measures for every slice of money movement:

- **Clearing:** did the flow complete, leaving clearing accounts at zero?
- **Timeliness:** did the data arrive on time?
- **Completeness:** does every event in the source system have a matching ledger event?

The post also stresses that Ledger is immutable: "Transactions previously published into Ledger cannot be deleted or modified." Corrections are new operations that revert and reprocess, not edits. Wednesday's lesson turns that into rules for your Postgres tables.

For the capstone, the lesson is cheap to apply. Give every multi-step flow (holds, outbound transfers, card deposits) a clearing or holding account, and make "this account is zero once everything settles" a check you can run. Module 8 builds full reconciliation on top of it.

## 6. Money in code: integers, currency and rounding

Today's lab builds a `Money` type: a `bigint` amount in minor units plus a currency, a deterministic split, and banker's rounding, with unit tests. The sources above all point the same way: TigerBeetle stores amounts as unsigned integers, and Monday's schema uses `bigint` centavos. Here is what the lab needs to get right.

**Amount and currency travel together.** A `Money` value is the pair (amount in minor units, ISO 4217 currency code). Adding R$ 1.00 to US$ 1.00 must throw, not return 2. Comparing them must throw too. In TypeScript, use `bigint` (or an integer that is checked to stay within `Number.MAX_SAFE_INTEGER`), and never parse amounts with `parseFloat`.

```typescript
export class Money {
  private constructor(readonly amount: bigint, readonly currency: string) {}

  static of(amount: bigint, currency: string): Money {
    return new Money(amount, currency);
  }

  add(other: Money): Money {
    if (other.currency !== this.currency) {
      throw new Error(`currency mismatch: ${this.currency} vs ${other.currency}`);
    }
    return new Money(this.amount + other.amount, this.currency);
  }
}
```

**A split must not lose or invent a cent.** Splitting R$ 1.00 (100 centavos) into 3 parts cannot give 33.33 each. With integers, 100 / 3 is 33 with a remainder of 1. The deterministic rule is: give everyone the quotient, then hand out the remainder one cent at a time, in a fixed order. The result is 34, 33, 33, and the parts always sum to the original. "Fixed order" matters: the same input must always give the same output, so a retry or a replay produces identical postings. A good unit test is a property: for any amount and any number of parts, the parts sum to the amount and differ by at most one cent.

**Rounding must be a decision, not an accident.** Fees often produce fractions of a cent. A 1.5% fee on R$ 10.10 is 15.15 centavos. You must choose a rounding rule and write it down. **Banker's rounding** (round half to even) rounds exact halves to the nearest even number: 2.5 becomes 2, 3.5 becomes 4, while 2.6 becomes 3 as usual. Its purpose is to avoid the upward bias of always rounding halves up, which adds up over millions of fees. Test the halves explicitly, and include negative values if your type allows them.

Whatever rule you pick, the ledger stays balanced only if the rounded fee is used on both sides of the entry. Compute the fee once, as an integer, and use that same value for the debit and the credit.

## Notes to write today

1. The lifecycle of a two-phase transfer: reserve, then post, partial post, void or expire. Write what happens to pending and posted counters in each case, using the 123 and 100 example.
2. Why the balance limit is checked in phase 1, and why that makes phase 2 safe.
3. The TigerBeetle account fields, and the exact check of `debits_must_not_exceed_credits`. Show that it is the available balance rule from Monday.
4. Clearing versus terminal accounts in Stripe's Ledger, and how a nonzero clearing balance reveals money that went missing or got stuck. Draw one wallet flow with a clearing account.
5. Your `Money` rules: integer minor units, currency always attached, deterministic split, and which rounding mode you use for fees.

## Check yourself

These make good flashcards (see the [flashcards guide](../../FLASHCARDS.md)).

- What does a pending transfer change in TigerBeetle, and what does it leave alone?
- A hold of R$ 100 is captured for R$ 80. What happens to the other R$ 20?
- Why can a pending transfer not be posted twice, and how does that help when the card network repeats a message?
- Which flag fits a customer wallet, `debits_must_not_exceed_credits` or `credits_must_not_exceed_debits`, and why?
- In Stripe's water analogy, what are the pipes, and what does water stuck in them mean?
- How do you split R$ 1.00 into three parts deterministically?
- What is banker's rounding, and what problem does it avoid?

## References

- **Main source for holds:** TigerBeetle documentation, ["Two-Phase Transfers"](https://docs.tigerbeetle.com/coding/two-phase-transfers/), the whole page, including the examples at the end. Free.
- **Main source for the account model:** TigerBeetle documentation, ["Account" reference](https://docs.tigerbeetle.com/reference/account/), especially the fields, the flags `debits_must_not_exceed_credits` and `credits_must_not_exceed_debits`, and the invariants. Free.
- **Main source for missing money:** Ilya Ganelin, ["Ledger: Stripe's system for tracking and validating money movement"](https://stripe.dev/blog/ledger-stripe-system-for-tracking-and-validating-money-movement), Stripe blog, February 2024. Read the sections on the water analogy and on data quality metrics. Free.
