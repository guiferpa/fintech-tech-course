# Module 6, Wednesday: concurrency, immutability and entries on paper

[Module 6](../../modules/06-ledgers-and-accounting.md) · [Leia em português](day-3.pt-BR.md)

**Reading time:** about 45 minutes. Use the rest of the 2-hour block on the references at the end and on the paper exercise.

This is an original text written for this course. It is based on the references listed at the end, and each section names the source it follows.

## Why this matters for a fintech

A ledger that is correct for one request at a time is not yet a ledger. In production, two card authorizations for the same wallet arrive in the same millisecond, the fee revenue account receives a posting from every transfer in the company, and an operator wants to "fix" a wrong entry with an `UPDATE`. Each of these can break the guarantees you built on Monday and Tuesday.

Today covers the two properties that keep the ledger trustworthy under real load: **concurrency control** (two writers cannot both spend the same money) and **immutability** (history is never rewritten, only extended). It ends with the paper exercise that prepares you for the capstone and for the mastery test.

## 1. The race on a wallet

*Main source: Modern Treasury, "Designing the Ledgers API with Optimistic Locking", by Andy Qin, 2021.*

Andy Qin's post starts with a peer-to-peer app. Lucy Ledger has a balance of 15000 cents (US$ 150.00) and sends US$ 50 to John Journal. The transaction debits Lucy and credits John. The danger is a second debit that runs at the same time.

The naive code does this:

1. Read Lucy's balance: 15000.
2. Check that 15000 >= 5000.
3. Insert the postings.

If two requests run steps 1 and 2 before either reaches step 3, both see 15000, both pass the check, and both insert. Make the second request US$ 120 instead of US$ 50 and Lucy ends at minus US$ 20. The post describes this as a phantom read: the check was true when it was read and false when the write landed.

In Postgres, the default isolation level is Read Committed, and it does not prevent this pattern. Each statement sees the data committed before it started, so two transactions can both read the old balance. You need a lock or a version check that ties the read to the write.

## 2. Pessimistic and optimistic locking

*Main source: Modern Treasury, "Designing the Ledgers API with Optimistic Locking".*

The post compares the two standard answers, as offered by Rails' ActiveRecord on top of Postgres.

**Pessimistic locking** takes an exclusive lock on the row before reading it. Other writers wait until the lock is released. In Postgres:

```sql
BEGIN;
SELECT id FROM accounts WHERE id = $1 FOR UPDATE;   -- other writers to this account wait here
-- compute available balance, check it, insert postings
COMMIT;
```

**Optimistic locking** adds a `lock_version` column. Every write increments it, and every write states which version it expects. If two clients write at the same time, one commits and the other fails, and the losing client reads again and decides whether to retry. In Postgres:

```sql
UPDATE account_versions
SET lock_version = lock_version + 1
WHERE account_id = $1 AND lock_version = $2;
-- 0 rows updated: someone else wrote first. ROLLBACK and retry from the read.
```

Modern Treasury chose optimistic locking. The deciding reason, in Qin's words: "A huge advantage over pessimistic locking is that reads aren't blocked by writes." Most ledger traffic is reading balances and statements, so blocking reads would be expensive.

The post also has a design detail worth copying. The thing that must be versioned is not the account's own attributes but its **set of entries**. So Modern Treasury put the `lock_version` in a separate "ledger account version" record, one per account, and bumped it whenever a new entry was created for that account. Renaming an account no longer conflicts with posting to it. In the API, the client sends the `lock_version` it read for each account in the transaction. As the post says: "If either "lock_version" differs, we rollback the database transaction and fail the request." Clients that do not send it get no concurrency guarantee; their version is updated later in a background job.

For your wallet, a simple rule works well: **lock only the accounts that need an authorization check, in a fixed order.** Sorting account IDs before locking avoids deadlocks when Ana pays Bruno while Bruno pays Ana.

## 3. Hot accounts and balance conditions

*Main source: Modern Treasury, "How to Scale a Ledger", chapters 4 and 6.*

Optimistic locking has a weakness that the whitepaper names directly. On an account that receives writes all the time, the version changes before most clients can commit: "If the `account_version` is incrementing at a fast enough pace, some Transactions will never be able to commit." These are **hot accounts**. In a wallet, the obvious ones are company accounts touched by every transaction: fee revenue, cash at the partner bank, and the clearing accounts from Tuesday.

The whitepaper offers two ideas to handle them.

**Lock per entry, not per transaction.** It separates two ways of writing to a ledger. **Recording** logs money that already moved somewhere else; it needs high throughput and accepts reads that are a few seconds stale. **Authorizing** decides whether money may move; it needs read-after-write consistency and serializes writes. The key claim is that "the model must be determined at the Entry level." Its card example has two entries in one transaction: the cardholder's entry needs a balance check and strong consistency, while the entry owed to the card processor needs neither. Both still commit atomically. In wallet terms: when Ana pays a R$ 2 fee, her wallet entry needs a lock and a balance check. The credit to fee revenue does not, because revenue can only grow from that entry and nobody authorizes anything against it.

**Balance conditions instead of version checks.** Instead of "fail if the version changed", the client says "commit only if this balance stays at or above zero after the write". The whitepaper calls this balance locking, with fields such as `BalanceCondition` and a `gte: 0` example. Unrelated concurrent writes no longer cause failures; only a write that would actually break the condition does. The whitepaper counts the difference in one example: two transactions of US$ 250 and US$ 750 against a US$ 1,000 balance take six ledger calls with version locking and two with balance locking.

Postgres can express a balance condition as one atomic statement, if you keep a cached balance row per account:

```sql
UPDATE account_balances
SET pending_debits = pending_debits + $2
WHERE account_id = $1
  AND posted_credits - pending_debits >= $2;   -- available >= amount, for a credit normal wallet
-- 0 rows updated: insufficient available balance, reject the hold
```

The `UPDATE` takes a row lock until commit, so the check and the change are atomic. The cache must be derived from postings, updated in the same database transaction, and checked for drift against the postings. The whitepaper recommends exactly that: monitor cached balances against the sum of entries and stop trusting the cache for accounts that drift.

## 4. Why a ledger must be immutable

*Main source: Modern Treasury, "Enforcing Immutability in your Double-Entry Ledger", by Jason Jong, 2021.*

Jason Jong's post lists three principles Modern Treasury never breaks: double entry, auditability and immutability. The argument for the third is about explaining the past. In his words, "if the data has been mutated, then the data is irreversibly destroyed."

His example is a marketplace that collects payments right away and pays merchants weekly. A merchant complains about a US$ 10 discrepancy in a US$ 10,000 payout. If orders were edited in place after the payout, there is no record of which change caused the difference, and Jong says tracing it "could take days". If every change was a new ledger transaction, the answer is a query.

The post separates two kinds of objects:

- **Business objects**, like an order or a transfer request, can be mutable. They are what the product shows.
- **Ledger transactions** are the accounting source of truth. They are created, never edited, once posted.

The pending state is the one exception, and it is deliberate. A ledger transaction can change while it is pending and becomes "immutable once posted." A payment that fails at the bank before posting can be moved to an **archived** state instead of being reversed. Jong also notes that pending "may not make sense for all products". Use it where real-world money has a pending phase, like holds and outbound transfers.

"How to Scale a Ledger" adds one more detail to the same idea. Pending entries are not edited either: they are marked discarded with a `discarded_at` timestamp and replaced by new entries. The whitepaper's summary: "Only pending Entries can be replaced; posted and archived Entries are permanent."

## 5. Corrections by reversal, and enforcing append-only in Postgres

*Main source: Modern Treasury, "Enforcing Immutability in your Double-Entry Ledger".*

If entries are never edited, how do you fix a mistake? Jong gives two options for an amount that changes after posting:

1. **Full reversal:** post a new transaction with the opposite entries, then post another with the correct amount.
2. **Difference entry:** post one new transaction for the difference between the old and new amounts.

Say a transfer fee was charged as R$ 5.00 but should have been R$ 3.00. A full reversal posts "credit Ana R$ 5, debit fee revenue R$ 5" and then "debit Ana R$ 3, credit fee revenue R$ 3". A difference entry posts only "credit Ana R$ 2, debit fee revenue R$ 2". Either way, the statement shows what happened and when. A full reversal is clearer for auditors; a difference entry produces fewer rows. Pick one and use it everywhere. Partial refunds work the same way: they are new transactions that move money back, linked to the original, never edits of it.

Do not rely on code reviews to keep the table append-only. Make the database refuse:

```sql
CREATE FUNCTION reject_posting_change() RETURNS trigger AS $$
BEGIN
  RAISE EXCEPTION 'postings are append-only (tried % on id %)', TG_OP, OLD.id;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER postings_append_only
BEFORE UPDATE OR DELETE ON postings
FOR EACH ROW EXECUTE FUNCTION reject_posting_change();
```

Also revoke `UPDATE` and `DELETE` on `postings` from the application's database role, so a trigger is not your only line of defense. On `ledger_transactions`, allow only the status changes `pending` to `posted` and `pending` to `archived`, each one at most once, which matches TigerBeetle's "resolved only once" rule from Tuesday.

For holds, one clean design combines both sources. A hold is a pending transaction. A capture archives the hold and creates a new posted transaction for the captured amount, with a column pointing back to the hold, like TigerBeetle's `pending_id`. A release only archives it. Both happen inside one database transaction, so the reservation and the capture are never both active.

## 6. Currency on every entry

*Main source: Modern Treasury, "How to Scale a Ledger", chapter 5.*

Monday's zero-sum rule hides a trap: you cannot sum reais and dollars. The whitepaper states the correct check: "The correct validation is to group Entries by currency and validate that credits and debits for each currency match." Each account has one currency, and each entry carries its currency, so the check can run without joins.

A conversion therefore needs four accounts, not two. The whitepaper's example is a customer buying ETH with USD: the customer's USD and ETH accounts, and the platform's USD and ETH accounts. In the wallet, Ana converting R$ 550 into US$ 100 looks like this:

| Account | Debit | Credit |
| --- | --- | --- |
| Wallet: Ana (BRL) | R$ 550.00 | |
| FX pool (BRL) | | R$ 550.00 |
| FX pool (USD) | US$ 100.00 | |
| Wallet: Ana (USD) | | US$ 100.00 |

BRL balances with BRL, and USD balances with USD. The whitepaper rejects the alternative of balancing across currencies with an exchange rate, for three reasons: rates change over time, so past balances become hard to verify; there is no single agreed rate; and two accounts do not reflect how a conversion works.

So where does the rate go? It is not part of the balancing rule, but it is a fact the customer was quoted. A sensible design for the capstone stores the quoted rate, its source and its timestamp on the conversion transaction, next to both amounts, and never recomputes it later. Module 1's consistency table already said the same thing: the customer must be charged the rate they were quoted.

## 7. On paper: five entries before any code

The capstone starts tomorrow, without AI. Do this exercise on paper first, with a pencil. Use these accounts:

| Account | Type | Normal balance |
| --- | --- | --- |
| Cash: partner bank | Asset | Debit |
| Wallet: Ana, Wallet: Bruno | Liability | Credit |
| Fee revenue | Revenue | Credit |
| Holds: card settlement | Liability (clearing) | Credit |

Here is the first one, worked out.

**1. Deposit.** Ana deposits R$ 500 by Pix through the partner bank.

| Account | Debit | Credit |
| --- | --- | --- |
| Cash: partner bank | 500.00 | |
| Wallet: Ana | | 500.00 |

Now draw the other four yourself:

2. **Transfer with fee.** Ana sends R$ 200 to Bruno and pays a R$ 2 fee. Decide whether Bruno receives R$ 200 or R$ 198, and write it down.
3. **Partial refund.** Bruno refunds R$ 50 of that transfer to Ana. Decide whether the fee is refunded, and record the refund as a new transaction linked to the original.
4. **Hold.** Ana's card is authorized for R$ 100 at a gas station. Write it as a pending transaction, and compute Ana's posted, pending and available balances after it.
5. **Capture.** The final amount is R$ 80. Show what happens to the hold and what new posted entries appear. Recompute the three balances.

Check every answer against four rules:

- Debits equal credits in each transaction, per currency.
- No posted entry is ever changed. Corrections and refunds are new transactions.
- Ana's available balance never goes below zero at any step.
- After the capture, nothing is left in the hold for this purchase, as in Stripe's empty pipes.

These four rules are also the properties for Friday's property-based test. Today's lab is to install fast-check and sketch generators for the operations above (deposit, transfer with fee, refund, hold, capture, release). fast-check can generate random arrays of such operations, and its `fc.commands` feature supports model-based testing. Write the task list for Thursday and Friday too, but no capstone code.

## Notes to write today

1. The race in Qin's example, and how pessimistic locking and optimistic locking each prevent it. One advantage of each.
2. What a hot account is, why version locking struggles with it, and the two remedies from "How to Scale a Ledger" (lock per entry, balance conditions).
3. The immutability rules: posted entries never change, pending can be archived or replaced, corrections by full reversal or difference entry.
4. Why entries balance per currency, the four-account conversion, and where the quoted FX rate is stored.
5. The paper exercise: entries for deposit, transfer with fee, partial refund, hold and capture, with Ana's balances after each step.

## Check yourself

These make good flashcards (see the [flashcards guide](../../FLASHCARDS.md)).

- Why does Postgres's default isolation level not stop two concurrent debits from overdrawing a wallet?
- What happens to the losing writer in optimistic locking?
- Why is a fee revenue account "hot", and why does it not need a lock?
- What is a balance condition, and how is it different from a version check?
- How do you correct a fee that was posted with the wrong amount?
- Why can't you balance a BRL entry against a USD entry using an exchange rate?
- After a hold of R$ 100 is captured for R$ 80, what are the available and posted balances of a wallet that started with R$ 500?

## References

- **Main source for concurrency:** Andy Qin, ["Designing the Ledgers API with Optimistic Locking"](https://www.moderntreasury.com/journal/designing-ledgers-with-optimistic-locking), Modern Treasury, August 2021. The whole post is short. Free.
- **Main source for immutability:** Jason Jong, ["Enforcing Immutability in your Double-Entry Ledger"](https://www.moderntreasury.com/journal/enforcing-immutability-in-your-double-entry-ledger), Modern Treasury, December 2021. The whole post. Free. It does not cover currencies; that part of today's lesson comes from the next reference.
- Modern Treasury, ["How to Scale a Ledger"](https://www.moderntreasury.com/ebooks/how-to-scale-a-ledger), chapters 4 (recording versus authorizing, version and balance locking), 5 (immutability, currency-level balancing, the card example) and 6 (idempotency, balance caching and drift). Free.
