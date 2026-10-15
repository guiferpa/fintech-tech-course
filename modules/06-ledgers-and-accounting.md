# Module 6: Ledgers and accounting

**Week 7** · [Back to the syllabus](../README.md) · [Leia em português](06-ledgers-and-accounting.pt-BR.md)

## Goal

Model money like an accountant: double entry, balances by state, holds, fees, refunds and invariants enforced by the database.

## Monday to Wednesday: reading + lab (3 h a day)

| Day | Reading (2 h) | Lab (1 h) |
| --- | --- | --- |
| Mon | Modern Treasury, "Accounting for Developers" parts 1 and 2: double entry, debits and credits, normal balance of each account type.<br>Modern Treasury, "Accounting for Developers" part 3 and the ledger series: pending, posted and available balances. | Model and migrate: accounts, transactions, postings. |
| Tue | TigerBeetle docs: data model (accounts, transfers), two-phase pending transfers, flags like debits_must_not_exceed_credits.<br>Stripe, "Ledger: Stripe's system for tracking and validating money movement". | Money type (bigint cents + currency), deterministic split of 100 into 3 and banker's rounding, with unit tests. |
| Wed | Hot accounts (sub-accounts, batching), append-only auditability, currency and FX rate on the entry.<br>On paper: entries for deposit, transfer with fee, partial refund, hold and capture. | Capstone prep: install fast-check, sketch operation generators, task list. No TCM code. |

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
