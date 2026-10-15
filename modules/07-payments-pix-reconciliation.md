# Module 7: Payments, Pix and reconciliation

**Week 8** · [Back to the syllabus](../README.md) · [Leia em português](07-payments-pix-reconciliation.pt-BR.md)

## Goal

Understand the payment lifecycle, Pix in Brazil, reconciliation against settlement files and safe provider fallback.

## Monday to Wednesday: DSA + reading + lab (3 h 30 a day)

| Day | DSA (30 min) | Reading (2 h) | Lab (1 h) |
| --- | --- | --- | --- |
| Mon | Rate limiter: token bucket (design + code: allow(userId, now))<br>No LeetCode link: write a class with allow(userId, now) and unit tests for bursts and refill. | [Stripe, "How card payment processing and settlement works"](https://stripe.com/resources/more/credit-card-payment-authorization-and-transaction-settlement-process) (free): authorization, capture, settlement and the actors (issuer, acquirer, card network, gateway).<br>[Stripe documentation, "The Payment Intents API"](https://docs.stripe.com/payments/payment-intents) (free): a payment modeled as a state machine.<br>[Airbnb Engineering, "Avoiding Double Payments in a Distributed Payments System"](https://medium.com/airbnb-engineering/avoiding-double-payments-in-a-distributed-payments-system-2981f6b070bb) (free): a real payment system design: idempotency, retries and unknown outcomes. | Two fake acquirers that authorize, capture and produce a daily settlement CSV. |
| Tue | Rate limiter: sliding window (sliding window log, then sliding window counter)<br>Same interface as yesterday; compare memory use and accuracy at window boundaries. | [Banco Central do Brasil, Pix page (regulation and manuals)](https://www.bcb.gov.br/estabilidadefinanceira/pix) (free): SPI, DICT, end_to_end_id and returns.<br>[Banco Central do Brasil, Resolution BCB No. 1 (Pix regulation, in English)](https://www.bcb.gov.br/content/estabilidadefinanceira/pix/Pix_Regulation/Resolution_BCB_1.pdf) (free): skim the participants and the 24/7 availability duties.<br>[Banco Central do Brasil, "Guia de implementação do MED" (Portuguese)](https://www.bcb.gov.br/content/estabilidadefinanceira/pix/Guia_MED.pdf) (free): the Special Return Mechanism (MED) flow.<br>[Open Finance Brasil](https://openfinancebrasil.org.br/) (free): Open Finance at a high level. | Payment state machine with a table of valid transitions and tests. |
| Wed | [Trapping Rain Water](https://leetcode.com/problems/trapping-rain-water/) (two pointers, then monotonic stack) | [Modern Treasury documentation, "Reconciliation Overview"](https://docs.moderntreasury.com/reconciliation/docs) (free): matching, tolerances and handling discrepancies.<br>[Airbnb Engineering, "Measuring Transactional Integrity in Airbnb's Distributed Payment Ecosystem"](https://medium.com/airbnb-engineering/measuring-transactional-integrity-in-airbnbs-distributed-payment-ecosystem-a670d6926d22) (free): reconciliation and data checks at scale.<br>Provider orchestration: routing and safe fallback. Draw timeout -> status query -> only then another provider. | Capstone prep: CSV files with planted discrepancies and the task list. No TCM code. |

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
