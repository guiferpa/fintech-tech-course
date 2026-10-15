# Module 7: Payments, Pix and reconciliation

**Week 8** · [Back to the syllabus](../README.md) · [Leia em português](07-payments-pix-reconciliation.pt-BR.md)

## Goal

Understand the payment lifecycle, Pix in Brazil, reconciliation against settlement files and safe provider fallback.

## Monday to Wednesday: DSA + reading + lab (3 h 30 a day)

| Day | DSA (30 min) | Reading (2 h) | Lab (1 h) |
| --- | --- | --- | --- |
| Mon | Rate limiter: token bucket (design + code: allow(userId, now))<br>No LeetCode link: write a class with allow(userId, now) and unit tests for bursts and refill. | Card payment lifecycle (authorization, capture, settlement, refund, chargeback) and actors (issuer, acquirer, card network, sub-acquirer, gateway, PSP). Stripe docs on PaymentIntents.<br>System Design Interview vol. 2, payment system chapter. | Two fake acquirers that authorize, capture and produce a daily settlement CSV. |
| Tue | Rate limiter: sliding window (sliding window log, then sliding window counter)<br>Same interface as yesterday; compare memory use and accuracy at window boundaries. | Pix regulation (Banco Central do Brasil): SPI, DICT, end_to_end_id, returns.<br>MED (Special Return Mechanism), Pix 24/7 and what it demands from availability. Open Finance at a high level. | Payment state machine with a table of valid transitions and tests. |
| Wed | [Trapping Rain Water](https://leetcode.com/problems/trapping-rain-water/) (two pointers, then monotonic stack) | Reconciliation: matching, tolerances, handling discrepancies (Modern Treasury articles on reconciliation).<br>Provider orchestration: routing and safe fallback. Draw timeout -> status query -> only then another provider. | Capstone prep: CSV files with planted discrepancies and the task list. No TCM code. |

Solve without AI, 30-minute timebox. Method and full list: [DSA track](../DSA.md).

In labs, AI is allowed only to clarify concepts, never to write capstone code.

## Thursday and Friday: capstone (TCM), no AI

Everything is done WITHOUT AI. No ChatGPT, Claude, Copilot or AI autocomplete in the editor. Allowed: official docs, books, your own notes and previous labs. Whatever doesn't fit today becomes cut scope for the next checkpoint; the deadline does not move.

1. (1 h) Wire the state machine to the ledger: authorization = hold, capture = entry, refund = reverse entry.
2. (1 h 15) Reconciliation job ledger vs. CSV: match by id, tolerance and discrepancy report.
3. (30 min) Run against the planted discrepancies: missing, duplicate, different amount, wrong date.
4. (1 h) Provider orchestrator with safe fallback.
5. (45 min) Tests: 100% of discrepancies detected; never charges on both providers.
6. (30 min) docs/m07.md.

Thursday covers items 1 to 3; Friday covers the rest and ends with 30 minutes of delivery.

## Pass criteria

100% of planted discrepancies are detected, and the fallback never charges on both providers.

## Mastery test

Answer out loud, in under 2 minutes, without notes, and record it:

> A payment showed as 'approved' to the customer but is missing from the acquirer's settlement file the next day. How does your system detect it and what does it do?
