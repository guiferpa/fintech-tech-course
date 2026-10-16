# Module 6, Monday: double entry, account types and balances

[Module 6](../../modules/06-ledgers-and-accounting.md) · [Leia em português](day-1.pt-BR.md)

**Reading time:** about 45 minutes. Use the rest of the 2-hour block on the references at the end, starting with the sections marked as the main source.

This is an original text written for this course. It is based on the references listed at the end, and each section names the source it follows. Where an idea comes from a specific author, the text says so.

## Why this matters for a fintech

Until now your wallet has stored a `balance` column and changed it with `UPDATE`. That works until someone asks a simple question: "why is this balance R$ 37.12 and not R$ 40.00?" A mutable number has no answer. A ledger does, because the balance is the sum of every movement that ever touched the account, and every movement says where the money came from and where it went.

Interviewers at payment companies ask you to model a ledger because it shows whether you think about money as a conserved quantity. This week you replace the balance column with accounts, transactions and postings, and you let the database refuse any write that creates or destroys money.

## 1. Accounts, entries, transactions and the ledger

*Main source: Modern Treasury, "Accounting for Developers, Part I", section "Core Concepts".*

The Modern Treasury series starts with four words. Learn them precisely, because interviewers use them precisely.

- An **account** is a pool of value whose balance you care about. The article puts it in one line: "An **account** is a segregated pool of value." In a wallet, each customer's wallet is an account, and so is the company's cash at the partner bank.
- An **entry** (in this course also called a **posting**, or "lançamento" in Portuguese) is one line that changes one account by one amount in one direction.
- A **transaction** is an atomic group of entries. It touches at least two accounts, and either all its entries are written or none are.
- A **ledger** is the time-ordered log of those transactions. Balances are computed from it.

The article argues for storing immutable transactions and deriving balances, instead of editing balances in place. Its warning is direct: "Mutating balances directly creates a system that is prone to errors". The reason is that an `UPDATE wallets SET balance = balance - 5000` leaves no trace of why the number changed. If a bug runs it twice, nothing in the database tells you.

The second idea is that **every transaction records both sides**. In the article's words, "every transaction should record both where the money came from and what the money was used for." When Ana sends R$ 50 to Bruno, the money comes from Ana's wallet and goes to Bruno's. Writing only Bruno's side would create R$ 50 out of nothing.

## 2. Debit normal and credit normal accounts

*Main source: Modern Treasury, "Accounting for Developers, Part I", sections on debit and credit normal accounts.*

This is where most engineers get lost, because "debit" and "credit" in accounting do not mean "minus" and "plus". The article reframes them in a way that suits programmers.

Every account has a **normal balance**, which is the direction that makes it grow.

- **Debit normal** accounts track **uses** of funds. Assets (cash, money lent to someone) and expenses are debit normal. A debit increases them; a credit decreases them.
- **Credit normal** accounts track **sources** of funds. Liabilities, equity and revenue are credit normal. A credit increases them; a debit decreases them.

The article summarizes it in a table, reproduced here with a wallet example in each row:

| Account type | Debit | Credit | Normal balance | Wallet example |
| --- | --- | --- | --- | --- |
| Asset | + | - | Debit | Cash held at the partner bank |
| Liability | - | + | Credit | Each customer's wallet balance |
| Equity | - | + | Credit | Money the founders put in |
| Revenue | - | + | Credit | Transfer fees charged to customers |
| Expense | + | - | Debit | Card processing fees paid to the acquirer |

So "debit" and "credit" are just the two sides of an entry. Whether a debit makes a number go up depends on the account type. It helps to treat the direction as a flag on the entry and the normal balance as a flag on the account, and to compute the effect from both.

The surprise for most engineers is the second row. **From the company's point of view, a customer's wallet is a liability.** The company holds the money but owes it back to the customer on demand. When a customer deposits R$ 100, the company's cash (an asset) goes up by R$ 100 and what it owes the customer (a liability) also goes up by R$ 100. Both accounts grow, one by a debit and one by a credit. That is double entry working as designed.

## 3. Proving that the ledger balances

*Main source: Modern Treasury, "Accounting for Developers, Part I", section "How to Ensure Your Ledger is Balanced".*

If every transaction has equal debits and credits, then the whole ledger has a property you can check at any time. The article states it as: the sum of the balances of all debit normal accounts equals the sum of the balances of all credit normal accounts. Its fictional bagel shop, Modern Bagelry, ends with US$ 1.47M on each side: cash and inventory on the debit side, equity and loans on the credit side. The article says what a mismatch would mean: "Not matching would mean the system created or lost money out of nothing."

For an engineer, the same rule has a simpler form. Give each entry a sign: debits positive, credits negative (or the reverse, as long as you are consistent). Then:

- **Per transaction:** the signed entries sum to zero.
- **For the whole ledger:** the signed entries sum to zero, because it is a sum of zero-sum transactions.

This is the **zero-sum invariant** you will enforce in Postgres on Thursday. It holds per currency: R$ 100 debited and US$ 100 credited do not cancel out. Wednesday's lesson comes back to currencies.

The invariant does not prove the ledger is right. A transfer posted to the wrong customer still balances. What it proves is that money was not created or destroyed by a bug. Other checks, like reconciliation against the partner bank (Module 8) and the clearing accounts from tomorrow's lesson, catch the rest.

## 4. A wallet's chart of accounts

*Main source: Modern Treasury, "Accounting for Developers, Part II".*

The second article in the series designs a ledger for a Venmo-style wallet. Its **chart of accounts** (the list of account types a product uses) has four kinds:

| Account | Type | Normal balance |
| --- | --- | --- |
| Cash | Asset | Debit |
| User wallet (one per customer) | Liability | Credit |
| Card processing fees | Expense | Debit |
| Revenue | Revenue | Credit |

It then models three events. Here they are, translated to reais and to our wallet. The structure is the article's; the numbers are ours.

**Transfer of R$ 100 from Ana to Bruno.**

| Account | Debit | Credit |
| --- | --- | --- |
| Wallet: Ana | 100.00 | |
| Wallet: Bruno | | 100.00 |

Ana's liability goes down and Bruno's goes up. The company's cash does not move at all, because no money left or entered the company's bank account.

**Ana deposits R$ 300 by card, and the company pays a 2% card fee.**

| Account | Debit | Credit |
| --- | --- | --- |
| Cash | 294.00 | |
| Card processing fees | 6.00 | |
| Wallet: Ana | | 300.00 |

Ana sees R$ 300 in her wallet. The bank receives R$ 294 because the acquirer kept R$ 6. The R$ 6 is an expense of the company. The transaction has three entries and still balances: 294 + 6 = 300. (The article's requirements list mentions a 3% fee while its example uses US$ 6 on US$ 300. What matters is the shape of the entry.)

**Bruno withdraws R$ 500 to his bank account and pays a 0.5% fee.**

| Account | Debit | Credit |
| --- | --- | --- |
| Wallet: Bruno | 502.50 | |
| Cash | | 500.00 |
| Revenue | | 2.50 |

The fee is revenue for the company, so it is a credit to a credit normal account. Notice the pattern: a fee is one more entry in the same transaction, never a second transaction written later. If the fee were written separately, a crash between the two writes would leave the ledger in a state that never happened in the real world.

The article closes the wallet example with a rule it calls essential: enforce double entry on every transaction, "at least one debit + one credit". And it gives the conclusion you should be able to say in an interview: "As debits equal credits, money in equals money out."

## 5. A full product ledger: the lending marketplace

*Main source: Modern Treasury, "Accounting for Developers, Part III".*

Part III, by Lucas Rocha, builds a whole product: a fictional peer-to-peer lending marketplace. An investor, Lucy, deposits US$ 10,000 at 4.8% a year. A borrower, Desi, takes US$ 5,000 at 12% a year. The marketplace keeps the difference between the interest it charges and the interest it pays as revenue.

Its chart of accounts is worth studying because it mixes company accounts and per-user accounts, with both normal balances on the user side:

| Account | Normal balance | Why |
| --- | --- | --- |
| Cash | Debit | Asset: money at the bank |
| Revenue (interest) | Credit | Source: the spread |
| Investor principal and investor interest (per investor) | Credit | Liability: owed to the investor |
| Borrower principal and borrower interest (per borrower) | Debit | Asset: owed by the borrower |

The most instructive entry is the monthly interest accrual. No money moves between banks. The ledger just records that obligations grew: Desi's borrower interest account is debited US$ 50 (she owes more), Lucy's investor interest account is credited US$ 40 (she is owed more), and revenue is credited US$ 10. Fifty in debits, fifty in credits. A ledger records **obligations**, not only bank movements.

The repayment then splits one incoming payment into two credits (principal and interest), and the payout at maturity debits two of Lucy's accounts against one credit to cash. Multi-entry transactions are normal, not an edge case.

One sentence from the article deserves a place in your notes: "The ledger's functionality and underlying data models should not be tightly coupled to business logic." For the wallet, this means the ledger module knows about accounts, transactions and postings. It does not know what a "Pix transfer" or a "refund" is. The transfer service translates business events into balanced postings and asks the ledger to write them.

## 6. Pending, posted and available balances

*Main source: Modern Treasury, "How to Scale a Ledger", chapters 1 and 2.*

So far each account has one balance. Real money is slower than that. A card purchase is authorized now and settles tonight. A Pix sent to a partner bank is accepted now and confirmed seconds later. The whitepaper "How to Scale a Ledger" handles this with three balances per account:

- **Posted balance:** money that has fully settled.
- **Pending balance:** posted money plus money that is expected to settle, in both directions.
- **Available balance:** what the customer can spend now. It counts outgoing pending money but ignores incoming money that has not settled.

The whitepaper computes all three from four sums kept per account: `posted_debits`, `posted_credits`, `pending_debits` and `pending_credits`, where the pending sums include the posted ones. For a credit normal account, like a customer wallet:

| Balance | Formula (credit normal) |
| --- | --- |
| Posted | posted_credits - posted_debits |
| Pending | pending_credits - pending_debits |
| Available | posted_credits - pending_debits |

For a debit normal account, swap debits and credits in each formula. The available formula is the important one. It is deliberately pessimistic: it subtracts every debit that might happen and adds only credits that already happened. That is the number you check before letting money out.

Here is Ana's wallet through a day, using those formulas:

| Event | Posted | Pending | Available |
| --- | --- | --- | --- |
| Start: R$ 1,000 settled | 1,000 | 1,000 | 1,000 |
| Card purchase of R$ 200 authorized (pending debit) | 1,000 | 800 | 800 |
| Incoming transfer of R$ 300, not yet settled (pending credit) | 1,000 | 1,100 | 800 |
| Card purchase settles | 800 | 1,100 | 800 |
| Incoming transfer settles | 1,100 | 1,100 | 1,100 |

Notice that settling never changes the pending balance. Pending already counted the movement; settling only moves it into posted.

The whitepaper walks through a credit card in the same way: a US$ 1,000 plane ticket "starts out pending", lowering pending and available but not posted, and moves to posted when it settles that night. A US$ 250 hotel hold lowers pending and available until it is removed.

Two more rules from the whitepaper matter for Thursday. First: "Account balances are never directly modified." Balances are derived from entries, even if you cache them. Second, entries belong to transactions with a state (pending, posted or archived), and clients create transactions, never loose entries. Tomorrow's lesson shows the same model in TigerBeetle under the name "two-phase transfers".

## 7. From the model to tables

Today's lab is to model and migrate accounts, transactions and postings. Here is a starting point in Postgres. It follows the vocabulary above. It is a sketch, so adapt names to your project.

```sql
CREATE TYPE normal_balance AS ENUM ('debit', 'credit');
CREATE TYPE entry_direction AS ENUM ('debit', 'credit');
CREATE TYPE ledger_tx_status AS ENUM ('pending', 'posted', 'archived');

CREATE TABLE accounts (
  id             uuid PRIMARY KEY,
  code           text NOT NULL UNIQUE,          -- 'cash:partner_bank', 'wallet:<user_id>'
  normal_balance normal_balance NOT NULL,
  currency       char(3) NOT NULL,              -- 'BRL'
  created_at     timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE ledger_transactions (
  id              uuid PRIMARY KEY,
  idempotency_key text NOT NULL UNIQUE,
  status          ledger_tx_status NOT NULL,
  description     text NOT NULL,
  effective_at    timestamptz NOT NULL,
  created_at      timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE postings (
  id             bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  transaction_id uuid NOT NULL REFERENCES ledger_transactions(id),
  account_id     uuid NOT NULL REFERENCES accounts(id),
  direction      entry_direction NOT NULL,
  amount         bigint NOT NULL CHECK (amount > 0),   -- minor units (centavos)
  currency       char(3) NOT NULL
);
```

Some choices to notice and be ready to defend:

- **Amounts are `bigint` in minor units** with a positive `CHECK`. The direction column carries the sign. Never use floating point for money.
- **The idempotency key lives on the transaction**, so a retried request from Module 2 cannot write the same money twice.
- **`effective_at` is separate from `created_at`.** The whitepaper uses `effective_at` for when the movement happened in the real world and lets the ledger set its own creation time.
- **There is no `balance` column.** A balance is a query:

```sql
SELECT
  SUM(CASE WHEN p.direction = 'credit' THEN p.amount ELSE -p.amount END) AS posted_balance
FROM postings p
JOIN ledger_transactions t ON t.id = p.transaction_id
WHERE p.account_id = $1 AND t.status = 'posted';
```

That query is correct for a credit normal account and slow for an account with millions of postings. Caching is fine later, as long as the cache is derived from postings and checked against them. The zero-sum rule is not in this schema yet. That is Thursday's first capstone task.

## Notes to write today

1. Double entry in one sentence, and why mutating a balance column is dangerous.
2. The five account types, the normal balance of each, and what a debit and a credit do to each. Include why a customer wallet is a liability for the company.
3. The entries for a wallet deposit with a card fee and a withdrawal with a fee, in the debit/credit table format.
4. One thing the lending ledger in Part III taught you that the wallet example did not (hint: accruals, multi-entry transactions, or decoupling from business logic).
5. The definitions of posted, pending and available balance, and the available formula for a credit normal account.

## Check yourself

These make good flashcards (see the [flashcards guide](../../FLASHCARDS.md)).

- What is the normal balance of a liability account, and does a debit increase or decrease it?
- Why is a customer's wallet balance a liability on the company's books?
- What does "the ledger balances" mean, and what kind of bug does it rule out? What kind does it not rule out?
- A deposit of R$ 300 by card costs a R$ 6 fee paid by the company. Which accounts are debited and credited?
- Why must a fee be an entry in the same transaction as the transfer, not a separate transaction?
- Write the available balance of a credit normal account in terms of posted and pending debits and credits.
- Why does the available balance ignore pending credits but count pending debits?

## References

- **Main source:** Modern Treasury, ["Accounting for Developers, Part I"](https://www.moderntreasury.com/journal/accounting-for-developers-part-i), all sections, and ["Accounting for Developers, Part II"](https://www.moderntreasury.com/journal/accounting-for-developers-part-ii) (linked at the end of part I), the wallet example. Free.
- Modern Treasury, ["Accounting for Developers, Part III"](https://www.moderntreasury.com/journal/accounting-for-developers-part-iii), by Lucas Rocha, the lending marketplace: read the chart of accounts and the five transaction types. Free.
- Modern Treasury, ["How to Scale a Ledger"](https://www.moderntreasury.com/ebooks/how-to-scale-a-ledger), chapters 1 and 2 today (balances, entries, transactions, the credit card example). Chapters 4 to 6 are for Wednesday. Free. It is a vendor whitepaper that also promotes Modern Treasury's product; the concepts are general.
