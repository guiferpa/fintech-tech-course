# Module 6: Ledgers and accounting

**Week 7** · [Back to the syllabus](../README.md) · [Leia em português](06-ledgers-and-accounting.pt-BR.md)

## Goal

Model money like an accountant: double entry, balances by state, holds, fees, refunds and invariants enforced by the database.

## Monday to Wednesday: DSA + reading + lab (3 h 30 a day)

| Day | DSA (30 min) | Reading (2 h) | Lab (1 h) |
| --- | --- | --- | --- |
| Mon | [Word Ladder](https://leetcode.com/problems/word-ladder/) (BFS shortest path) | [Course text: Double entry, account types and balances](../lessons/06-ledgers-and-accounting/day-1.md) (written for this course): read this first. It explains the day's concepts and says which sections of the references below to read next.<br>[Modern Treasury, "Accounting for Developers", parts I and II](https://www.moderntreasury.com/journal/accounting-for-developers-part-i) (free): double entry, debits and credits, normal balance of each account type (part II is linked at the end).<br>[Modern Treasury, "Accounting for Developers", part III](https://www.moderntreasury.com/journal/accounting-for-developers-part-iii) (free): a full example of a product's ledger.<br>[Modern Treasury, "How to Scale a Ledger"](https://www.moderntreasury.com/ebooks/how-to-scale-a-ledger) (free): pending, posted and available balances. | Model and migrate: accounts, transactions, postings. |
| Tue | [Word Ladder (optimization)](https://leetcode.com/problems/word-ladder/) (bidirectional BFS + wildcard map)<br>Redo yesterday's solution, now with bidirectional BFS, and compare the runtimes. | [Course text: Holds, account invariants and missing money](../lessons/06-ledgers-and-accounting/day-2.md) (written for this course): read this first. It explains the day's concepts and says which sections of the references below to read next.<br>[TigerBeetle documentation, "Two-Phase Transfers"](https://docs.tigerbeetle.com/coding/two-phase-transfers/) (free): pending transfers that are later posted or voided.<br>[TigerBeetle documentation, "Account" reference](https://docs.tigerbeetle.com/reference/account/) (free): the data model and flags like debits_must_not_exceed_credits.<br>[Stripe blog, "Ledger: Stripe's system for tracking and validating money movement"](https://stripe.dev/blog/ledger-stripe-system-for-tracking-and-validating-money-movement) (free): how a ledger detects money that went missing. | Money type (bigint cents + currency), deterministic split of 100 into 3 and banker's rounding, with unit tests. |
| Wed | [Merge K Sorted Lists](https://leetcode.com/problems/merge-k-sorted-lists/) (min-heap, or divide and conquer)<br>Same shape as merging sorted event streams in reconciliation. | [Course text: Concurrency, immutability and entries on paper](../lessons/06-ledgers-and-accounting/day-3.md) (written for this course): read this first. It explains the day's concepts and says which sections of the references below to read next.<br>[Modern Treasury, "Designing the Ledgers API with Optimistic Locking"](https://www.moderntreasury.com/journal/designing-ledgers-with-optimistic-locking) (free): concurrency on hot accounts.<br>[Modern Treasury, "Enforcing Immutability in your Double-Entry Ledger"](https://www.moderntreasury.com/journal/enforcing-immutability-in-your-double-entry-ledger) (free): append-only entries and corrections by reversal.<br>On paper: entries for deposit, transfer with fee, partial refund, hold and capture. | Capstone prep: install fast-check, sketch operation generators, task list. No TCM code. |

Solve without AI, 30-minute timebox. Method and full list: [DSA track](../DSA.md).

In labs, AI is allowed only to clarify concepts, never to write capstone code.

## Thursday and Friday: capstone (TCM), no AI

Everything is done WITHOUT AI. No ChatGPT, Claude, Copilot or AI autocomplete in the editor. Allowed: official docs, books, your own notes and previous labs. Whatever doesn't fit today becomes cut scope for the next checkpoint; the deadline does not move.

1. (45 min) Zero-sum invariant enforced in the database (deferrable constraint trigger).
2. (1 h) Entries: deposit, transfer with fee, partial refund.
3. (1 h) Holds: create, capture, release; pending, available and held balances.
4. (45 min) Move the transfers from modules 3 and 4 onto the ledger.
5. (1 h) Property-based test: 10,000 random operations never break zero-sum nor make available negative.
6. (30 min) docs/m06.md.

Thursday covers items 1 to 3; Friday covers the rest and ends with 30 minutes of delivery.

## Pass criteria

A property-based test runs 10,000 random operations and never breaks zero-sum nor makes the available balance negative.

## Mastery test

Answer out loud, in under 2 minutes, without notes, and record it:

> Model the tables of a digital wallet ledger and show the entries for: a deposit, a transfer between users with a fee, and a partial refund.
