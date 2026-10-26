# Checkpoint 2, Monday: cross-border payments

[Checkpoint 2](../../modules/checkpoints.md) · [Leia em português](day-1.pt-BR.md)

**Reading time:** about 45 minutes. Use the rest of the 2-hour block on the references at the end, and keep the evening for the paper lab in section 8.

This is an original text written for this course. It is based on the references listed at the end, and each section names the source it follows. Where a number or a rule comes from a specific company or regulator, the text says so.

## Why this matters for a fintech

Modules 5 to 7 built a wallet that moves reais inside Brazil. A common interview follow-up is "and what if the user wants to send US$ 100 to a freelancer in the United States?" That question touches everything you studied, plus three new problems: a price that changes every second, a chain of banks you don't control, and rules from two countries.

Read this as a review with a new case: every section reuses idempotency keys, state machines, holds, per-currency entries or reconciliation, which also prepares Wednesday's recorded system design.

## 1. How money actually crosses a border

*Main source: Wise blog, "What is a correspondent bank?" and "How to use Nostro/Vostro account when sending to India".*

Money does not travel; balances change on books in two countries. A Brazilian bank with no account in the United States needs a bank that has one. Wise puts it simply: "Correspondent banks are usually involved when sending payments to foreign countries through SWIFT."

The plumbing is one account seen from two sides. Wise defines a **nostro** account as "an account held by a domestic bank at a foreign correspondent bank", and a **vostro** account as "an account held by a foreign correspondent bank at a domestic bank". Nostro means "our account, on your books"; vostro means "your account, on our books". Banks keep them to "maintain a pool of funds in each other's currencies".

So a Brazil to US payment goes like this. The Brazilian bank debits the customer in BRL and buys USD. It sends an instruction to its US correspondent (a message, no money yet). The correspondent debits the Brazilian bank's USD nostro and pays the beneficiary bank, directly or through another intermediary. The beneficiary bank credits the freelancer.

Each hop takes time and a fee. Wise says the correspondent "will deduct their service fee from the transferred funds", and that "25 USD - 75 USD are common", although costs vary widely. That is why the freelancer may receive less than US$ 100 (section 4).

Providers such as Wise use local bank accounts in each country instead: money in locally, out locally (section 5). It is still nostro/vostro thinking, with prefunded pools per currency.

## 2. The messages: SWIFT and ISO 20022 in practice

*Main source: ING Wholesale Banking, "ISO 20022 SWIFT CBPR+ update"; J.P. Morgan, "ISO 20022 FAQs".*

SWIFT is the messaging network between banks. It carries instructions, not money. For decades the customer transfer was the **MT103**, a text message with numbered fields. Banks moved to **ISO 20022**, an XML standard, under a programme called CBPR+. ING's page says: "Since 22 November 2025, MT payment instructions such as MT103, MT200 and MT202(COV) have been replaced". The mapping to know:

| Old MT message | ISO 20022 message | Purpose |
| --- | --- | --- |
| MT103 | pacs.008 | Customer credit transfer |
| MT200 / MT202 | pacs.009 | Transfer between financial institutions |
| MT103/MT202 return | pacs.004 | Return of funds |
| (none) | pacs.002 | Payment status report |
| MT940 statements | camt.053 | Bank account statement |

ING adds that MT and CAMT statements coexist until November 2028, so you will still meet MT940 files.

ISO 20022 carries structured data your code can use. J.P. Morgan's FAQ highlights three items:

- **UETR**, a unique end-to-end reference carried by every payment. Store it on your transfer, as you stored the Pix `end_to_end_id` in Module 7.
- **Structured addresses.** From November 2026, J.P. Morgan says, the address "must be provided in a structured or hybrid manner" for CBPR+ payments, with at least town and country. Your recipient form needs separate fields.
- **Purpose codes.** Some corridors require them: J.P. Morgan cites Philippine offshore payments and UK CHAPS property payments (codes such as HLRP and PDEP).

Your provider builds the pacs.008, but your data model must hold everything it needs.

## 3. FX quotes: rate, spread and expiry

*Main source: Stripe documentation, "Enable currency conversion using the FX Quotes API"; Wise Platform API reference, "Quote" and "Types of quotes"; Wise Help Centre, "What's a guaranteed rate?".*

An FX quote is a promise with a deadline: you can convert at this rate until this time. Stripe's FX Quotes API (a preview product) returns an `fx_quote` with a `lock_duration` (`five_minutes`, `hour`, `day` or `none`), a `lock_expires_at` and a `lock_status`. Its example response breaks the price down:

| Field | Example | Meaning |
| --- | --- | --- |
| `reference_rate` | 1.0827 (`ecb`) | Public reference rate |
| `base_rate` | 1.08295 | Stripe's rate before fees |
| `fx_fee_rate` | 0.02 | The FX fee |
| `duration_premium` | 0.0007 | The price of the lock |
| `exchange_rate` | 1.06053 | What is applied |

That is **spread**: the gap between a reference rate and the customer's rate, made of fees and a premium for the market risk the provider carries during the lock. Stripe prices BRL in its Group 2: 0.12% for five minutes, 0.15% for one hour, 0.30% for 24 hours. In Brazil, payments can lock for five minutes or one hour; transfer locks are not supported.

Two behaviors matter. A lock can end early: "If an exchange rate exceeds the rate threshold for payments or transfers, the extended rate quote is invalidated and the `lock_status` changes to `expired`." And an expired quote fails loudly: attaching it to a PaymentIntent or Transfer returns a `400` (for example `payment_intent_fx_quote_invalid`), and Stripe sends an `fx_quote.expired` webhook.

Wise uses the same ideas: `rate`, `rateType` (`FIXED` or `FLOATING`), `expirationTime`, `rateExpirationTime`, and statuses `PENDING`, `ACCEPTED`, `FUNDED`, `EXPIRED`. Unauthenticated quotes "are for illustrative purposes only"; authenticated ones return an ID for creating a transfer, and "The rate is locked for 30 minutes to give a user time to submit the transfer." The help page adds two edge cases. If money arrives after the lock, Wise uses "the live mid-market rate at the time we receive your funds". And: "We cannot guarantee the rate if we only receive part of your money."

Ana saw R$ 550.00 for US$ 100.00; charging anything else is a bug. So the quote is a stored row that one transfer consumes, before it expires:

```sql
CREATE TABLE fx_quotes (
  id                uuid PRIMARY KEY,
  wallet_id         uuid NOT NULL,
  source_amount     bigint NOT NULL,        -- BRL, minor units
  target_amount     bigint NOT NULL,        -- USD, minor units
  rate              numeric(20,10) NOT NULL,
  fee_amount        bigint NOT NULL,
  provider_quote_id text NOT NULL,
  expires_at        timestamptz NOT NULL,   -- provider expiry minus a margin
  status            text NOT NULL CHECK (status IN ('open','used','expired')),
  transfer_id       uuid UNIQUE             -- one transfer per quote
);

UPDATE fx_quotes SET status = 'used', transfer_id = $2
 WHERE id = $1 AND status = 'open' AND expires_at > now()
RETURNING *;
```

Zero rows means expired or used: ask Ana to confirm a new rate, never re-quote silently. `POST /quotes` takes an idempotency key, so a double tap does not create two locks. And the client reference you send to the provider is generated once and stored before the call. Wise's `customerTransactionId` is a "Unique identifier randomly generated per transfer request by the calling client"; a retry sends the same value.

The ledger side of the conversion (four accounts, balanced per currency, quoted rate stored on the transaction) is in [Module 6, Wednesday, section 6](../06-ledgers-and-accounting/day-3.md#6-currency-on-every-entry). Reread it instead of repeating it here.

## 4. Fees and cut-offs: why the amount and the date move

*Main source: Nium Developer Hub, "FAQ"; Revolut Business Help, "SWIFT transfer options and fees"; Banking Circle, "Currencies & Cut-Off Times"; Adyen documentation, "Send funds to third parties".*

A SWIFT payment carries a charge code. Nium's FAQ describes three:

| Code | Who pays | Beneficiary receives |
| --- | --- | --- |
| OUR | The sender, up front | The full amount |
| SHA | Shared | Possibly less, after deductions |
| BEN | The beneficiary | The amount minus fees |

Revolut explains the SHA trap: intermediate banks "may also charge fees, which are generally deducted from the amount being transferred". The quote screen must say which code applies. Reconciliation must expect a smaller received amount on SHA or BEN, with its own reason code, not a generic "different amount" from Module 7.

Each currency has a daily **cut-off** for same-day execution. Banking Circle's table (CET/CEST) shows EUR SEPA batch at 14:00, EUR SWIFT at 16:00, GBP CHAPS at 17:45, USD SWIFT at 18:30, and SEPA Instant and UK Faster Payments at 24/7. JPY over SWIFT goes to correspondents with value date D+1. Funds leave only after the FX trade settles, and "payments will not be processed on public holidays." Adyen says the same: after the cut-off, requests move to the next day (for example, USD Regular at 01:45 ET).

So each transfer has an **expected settlement date** (currency, rail, cut-off, two holiday calendars). Store it and let reconciliation flag transfers that pass it.

## 5. Paying out on local rails through a provider

*Main source: Stripe documentation, "Global Payouts" and "Payout methods and amounts"; Adyen documentation, "Send funds to third parties"; Wise Platform documentation, "Transfer statuses".*

Most fintechs call a provider that pays out on the recipient's domestic rail. Stripe Global Payouts reaches "more than 160 countries" and targets businesses that already hold a Money Transmitter License. From a US sender, its table lists ACH (typically up to 1 business day), UK FPS (real-time), SEPA (typically 1 business day), and a `local` rail or a wire elsewhere, typically 1 to 7 days. One example is worth copying: both currencies must pass their minimums. Sending 3 USD to South Africa fails, because it is 55.63 ZAR and the ZAR minimum is 100. Validate both sides before locking a quote.

Adyen separates **local payouts** (the beneficiary country's clearing system) from **cross-border payouts**, where "the only priority supported for cross-border payouts is crossBorder" and arrival is not guaranteed.

Wise's transfer states map almost one to one onto tonight's state machine:

| Wise status | Meaning |
| --- | --- |
| `incoming_payment_waiting` | Created, waiting for funds |
| `processing` | Funds received; AML, compliance and fraud checks |
| `funds_converted` | Checks done, converted to target currency |
| `outgoing_payment_sent` | Paid out; final "assuming funds will not be returned" |
| `bounced_back` | Returned, not yet refunded |
| `funds_refunded` / `cancelled` | Refunded after funding / never funded |

"Sent" is not "received": `outgoing_payment_sent` can become `bounced_back` days later, when the beneficiary bank rejects an account. Your `PAID_OUT` state is not terminal for reconciliation.

## 6. Compliance: sanctions screening and purpose codes

*Main source: U.S. Treasury OFAC, "Sanctions List Search Tool" and FAQs 91 and 247 to 251; Banco Central do Brasil, Resolução BCB nº 277, Art. 4 to 6.*

Before money leaves, sender and beneficiary are screened. The best known list is OFAC's SDN List. FAQ 91 says SDN property under US jurisdiction is blocked and US persons are generally prohibited from dealing with them. Entities owned "50 percent or more by one or more blocked persons" are blocked even if unlisted.

Screening is fuzzy matching, with false positives. OFAC's search tool "employs fuzzy logic on its name search field" (FAQ 249: Jaro-Winkler and Soundex). FAQ 250 says OFAC recommends no threshold: users "must make their own match threshold determinations". In the wallet, a potential match is a state, `COMPLIANCE_REVIEW`. The hold keeps the funds reserved until an analyst clears or blocks it. Never auto-retry or auto-refund a hit.

**Purpose codes** say why money moves. In Brazil, Resolução BCB nº 277, Art. 4, makes the purpose classification the client's responsibility, and the institution must present the codes understandably. Anexo V lists codes such as 34124 (transfer between accounts in Brazil and abroad with the same owner) and 34155 (unilateral transfers). Art. 6 says a return uses the original operation's code. So the purpose code is a required field, chosen by the customer and copied onto any return.

## 7. The Brazilian side: câmbio, VET and eFX

*Main source: Banco Central do Brasil, "Cartilha de Câmbio 2026"; Resolução BCB nº 277/2022 and Resolução BCB nº 561/2026.*

In Brazil, converting reais to foreign currency is a câmbio operation, done by a BCB-authorized institution. The BCB's 2026 guide lists banks, corretoras and payment institutions among them, and says the client "deve ser identificado". For an outgoing transfer it asks for the "motivo da remessa, banco, agência e número da conta" of the beneficiary.

The guide defines **VET (Valor Efetivo Total)** as "o total de reais entregues ou recebidos por unidade de moeda estrangeira", including the rate, the IOF tax and fees. Resolução BCB nº 277, Art. 18, requires informing it before spot operations up to US$ 100,000, and the guide says it must appear on the contract or receipt. On your quote screen, that is one number: R$ per US$, everything included.

**eFX** is the international payment or transfer service provider. The guide says these providers usually work through partners abroad and digital channels. Resolução BCB nº 561, of 30 April 2026, effective 1 October 2026, rewrote its rules:

- US$ 10,000 limits apply to purchases through a digital payment solution not integrated with an e-commerce platform, and to investment-related transfers.
- Payment to the foreign counterparty uses only listed methods, "sendo vedado o uso de ativos virtuais".
- "É vedada a compensação pelo prestador de eFX entre os reais recebidos do usuário e os reais entregues ao usuário."
- Without a BCB reserve or settlement account, the provider's account must be at a câmbio-authorized institution, used only for eFX.
- Providers not yet authorized must request authorization as a payment institution by 31 May 2027.

Because of the no-netting rule, each user's reais in and out must be traceable separately, which a per-transaction ledger gives you.

Cross-border Pix: the only official statement verified here is the guide's note that "turistas brasileiros já conseguem utilizar o Pix para realizar pagamentos em determinados estabelecimentos" in some destinations. Treat anything more as unverified until you read it on a BCB page.

## 8. Tonight's lab: a cross-border transfer on paper

No code. Ana sends US$ 100.00 from her BRL wallet to a freelancer's US bank account through a payout provider.

1. **State machine.** Start from `QUOTED`, `QUOTE_EXPIRED`, `FUNDS_HELD`, `COMPLIANCE_REVIEW`, `BLOCKED`, `DEBITED`, `CONVERTED`, `PAYOUT_SUBMITTED`, `UNKNOWN`, `PAID_OUT`, `RETURNED`, `REFUNDED`, `RECONCILED`. For each transition, write the trigger (API call, webhook, timeout, file) and the idempotency key. For `UNKNOWN`, apply Module 7's rule: query status first.
2. **Quote.** Fill the quote row with real numbers: provider expiry, your margin, the VET, the charge code and the purpose code.
3. **Ledger per currency.** Write postings for hold, debit and fee, conversion, payout submission, payout settlement, and a bounce with refund. Each balances in BRL and in USD separately. Suggested accounts: Wallet: Ana (BRL), Fee revenue (BRL), FX pool (BRL), FX pool (USD), Payable to provider (USD), Cash at provider (USD). Decide who absorbs the FX difference when a bounce comes back after the rate moved.
4. **Reconciliation.** List the files (provider transfer report, provider balance statement, câmbio confirmations) and the match key for each: your ID, the provider's ID, the UETR. Add a rule for SHA deductions and one for the expected settlement date.

## Notes to write today

1. Nostro, vostro and the hops of a Brazil to US payment.
2. MT to ISO 20022 (pacs.008, pacs.009, pacs.004, pacs.002, camt.053), plus UETR, structured address and purpose in your model.
3. Quote rules: reference, base, fee and premium; lock and early invalidation; consume-once SQL; the expired-quote answer.
4. OUR, SHA and BEN and their effect on reconciliation. Cut-offs, value dates and the expected settlement date.
5. Brazilian rules: who operates câmbio, VET, purpose codes, and the Resolução BCB nº 561 eFX points.
6. Your lab output: state machine, quote row and per-currency entries.

## Check yourself

These make good flashcards (see the [flashcards guide](../../FLASHCARDS.md)).

- What is the difference between a nostro and a vostro account, and why is it the same account?
- Which ISO 20022 message replaced the MT103, and which one carries a return?
- In Stripe's FX quote, what fills the gap between `reference_rate` and `exchange_rate`?
- How do you guarantee a quote is used by at most one transfer, and only before it expires?
- With SHA, why might the freelancer receive less than US$ 100, and how should reconciliation classify it?
- Why is `outgoing_payment_sent` not final for your reconciliation job?
- What is the VET, what does it include, and when must it be shown?

## References

- **Main source:** Wise, ["What is a correspondent bank?"](https://wise.com/us/blog/what-is-a-correspondent-bank) and ["How to use Nostro/Vostro account when sending to India"](https://wise.com/in/blog/nostro-and-vostro-account). Free.
- **Main source:** ING Wholesale Banking, ["ISO 20022 SWIFT CBPR+ update"](https://www.ingwb.com/en/service/payments-and-collections/iso20022-swift-cbpr-update) (dates and mapping), and J.P. Morgan, ["ISO 20022 FAQs"](https://www.jpmorgan.com/insights/payments/fx-cross-border/iso-20022-faqs) (UETR, addresses, purpose codes). Free.
- **Main source:** Stripe documentation, ["Enable currency conversion using the FX Quotes API"](https://docs.stripe.com/payments/custom/localize-prices/fx-quotes-api). Free.
- Wise, ["Quote"](https://docs.wise.com/api-reference/quote), ["Types of quotes"](https://docs.wise.com/api-reference/quote/types-of-quotes), ["What's a guaranteed rate?"](https://www.wise.com/help/articles/2448203/whats-a-guaranteed-rate) and ["Transfer statuses"](https://docs.wise.com/guides/product/send-money/tracking/transfer-statuses). Free.
- Nium, ["FAQ"](https://mpdocs.nium.com/payout-payin/faq-s), and Revolut Business, ["SWIFT transfer options and fees"](https://help.revolut.com/business/help/receiving-payments/sending-money-to-an-external-bank-account/question-fees-swift-transfers), for OUR, SHA and BEN. Free.
- Banking Circle, ["Currencies & Cut-Off Times"](https://www.bankingcircle.com/currencies-and-cut-off-times), and Adyen, ["Send funds to third parties"](https://docs.adyen.com/marketplaces/custom-payouts). Free.
- Stripe documentation, ["Global Payouts"](https://docs.stripe.com/global-payouts) and ["Payout methods and amounts"](https://docs.stripe.com/global-payouts/payout-methods). Free.
- OFAC, ["Sanctions List Search Tool"](https://ofac.treasury.gov/sanctions-list-search-tool), [FAQ 91](https://ofac.treasury.gov/faqs/91) and the [Sanctions List Search FAQs](https://ofac.treasury.gov/faqs/topic/1636/print) (247 to 251). Free.
- **Main source:** Banco Central do Brasil, ["Cartilha de Câmbio 2026"](https://www.bcb.gov.br/content/estabilidadefinanceira/politica_cambial/Cartilha_cambio_2026.pdf); [Resolução BCB nº 277](https://www.bcb.gov.br/estabilidadefinanceira/exibenormativo?tipo=Resolu%C3%A7%C3%A3o%20BCB&numero=277) (Art. 4 to 6, Art. 18) and [Resolução BCB nº 561](https://www.bcb.gov.br/estabilidadefinanceira/exibenormativo?tipo=Resolu%C3%A7%C3%A3o%20BCB&numero=561). In Portuguese. Free.
