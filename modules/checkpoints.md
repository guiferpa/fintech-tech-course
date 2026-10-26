# Checkpoints

[Back to the syllabus](../README.md) · [Leia em português](checkpoints.pt-BR.md)

Checkpoint weeks are for a timed mock interview, a review of what was weak, and time to catch up on cut scope. Checkpoint 2 also brings one new topic on Monday: cross-border payments.

| Day | Checkpoint 1 (week 5, modules 1 to 4) | Checkpoint 2 (week 9, modules 5 to 7) |
| --- | --- | --- |
| Mon | Review all flashcards; reread code and notes; list cut scope | **Cross-border payments**: course text, readings and a paper lab (see below) |
| Tue | Catch up on cut scope, without AI | Review all flashcards and list cut scope (1 h), then catch up on it without AI (2 h) |
| Wed | 45-min system design, recorded: **digital wallet** | 45-min system design, recorded: **payment gateway or Pix system** |
| Thu | 5 random mastery tests + 30-min code review | Same, for modules 5 to 7 |
| Fri | 3 answers in English, 1 STAR story, 1 question outside your experience | Same, plus update your CV and LinkedIn |

**Pass if** every recording covers failures and idempotency without being asked. Whatever was missing becomes a flashcard.

## Checkpoint 2, Monday: cross-border payments

Reading (2 h):

- [Course text: Cross-border payments](../lessons/checkpoint-2-cross-border-payments/day-1.md) *(written for this course)*: read this first. It explains the day's concepts and says which sections of the references below to read next.
- [Wise, "What is a correspondent bank?"](https://wise.com/us/blog/what-is-a-correspondent-bank) *(free)*: how correspondent banks, nostro and vostro accounts move SWIFT payments, and why each hop deducts fees. Note the two account definitions.
- [ING Wholesale Banking, "ISO 20022 SWIFT CBPR+ update"](https://www.ingwb.com/en/service/payments-and-collections/iso20022-swift-cbpr-update) *(free)*: the MT to ISO 20022 mapping (MT103 to pacs.008, returns as pacs.004) and the migration dates. Note which message replaces which.
- [Stripe documentation, "Enable currency conversion using the FX Quotes API"](https://docs.stripe.com/payments/custom/localize-prices/fx-quotes-api) *(free)*: a real FX quote: reference rate, fee, lock premium, lock duration, early expiry and the error for an expired quote. Note how to lock the rate the customer saw.
- [Wise Platform documentation, "Transfer statuses"](https://docs.wise.com/guides/product/send-money/tracking/transfer-statuses) *(free)*: the states of a real cross-border transfer, from waiting for funds to paid out or bounced back. Map them onto your own state machine.
- [Banco Central do Brasil, "Cartilha de Câmbio 2026"](https://www.bcb.gov.br/content/estabilidadefinanceira/politica_cambial/Cartilha_cambio_2026.pdf) *(free)*: official BCB guide (in Portuguese): who may operate câmbio, international transfers through eFX providers, and the VET. Note what the VET includes.

Lab (1 h): on paper, design a cross-border transfer from a BRL wallet to a USD account: quote, lock, debit, convert, pay out, reconcile. Draw the state machine, the quote row and the ledger entries per currency, and mark where idempotency and reconciliation keys live.

## DSA (Monday to Wednesday, first 30 min)

| Day | Checkpoint 1 (week 5) | Checkpoint 2 (week 9) |
| --- | --- | --- |
| Mon | Re-solve 2 problems you marked "redo" in weeks 1 to 4, from scratch, no hints. | Re-solve 2 problems you marked "redo" in weeks 6 to 8, from scratch, no hints. |
| Tue | Mock coding interview (30 min, recorded): pick a random problem from weeks 1 to 4 and solve it explaining out loud, as in an interview. | Mock coding interview (30 min, recorded): pick a random problem from weeks 6 to 8 and solve it explaining out loud, as in an interview. |
| Wed | Complexity review: write the time and space complexity of every problem so far from memory, check, and turn mistakes into flashcards. | Complexity review: write the time and space complexity of every problem so far from memory, check, and turn mistakes into flashcards. |

Solve without AI, 30-minute timebox. Method and full list: [DSA track](../DSA.md).

## Code review checklist

Read it out loud before every review:

1. Money stored as float?
2. Non-idempotent operation with retries?
3. Read and write without a transaction or lock?
4. External call inside a database transaction?
5. Swallowed error, or unknown status treated as failure?
6. Secret or personal data in logs?
7. Missing timeout?
8. (From module 5) Consumer without dedupe?
9. (From module 6) Ledger entry that doesn't sum to zero?
