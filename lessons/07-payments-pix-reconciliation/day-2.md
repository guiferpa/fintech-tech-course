# Module 7, Tuesday: Pix, returns and the MED

[Module 7](../../modules/07-payments-pix-reconciliation.md) · [Leia em português](day-2.pt-BR.md)

**Reading time:** about 45 minutes. Use the rest of the 2-hour block on the references at the end, starting with the sections marked as the main source.

This is an original text written for this course. It is based on the references listed at the end, and each section names the source it follows. Where an idea comes from a specific author, the text says so.

## Why this matters for a fintech

In Brazil, Pix is how most wallet money comes in and goes out. It is very different from a card payment. There is no authorization that lasts days, no capture step and no settlement file arriving the next morning: the money moves in seconds, 24 hours a day. That speed removes some problems and creates others. A wrong Pix can't be "voided" before settlement, because settlement already happened. It can only be returned, and fraud is handled by a dedicated mechanism with strict deadlines.

Interviewers at Brazilian fintechs expect you to know the vocabulary: SPI, DICT, Pix key, end_to_end_id, devolução and MED. Today gives you each term, where it comes from, and what it means for your tables. The day ends with the design for tonight's lab, the payment state machine.

## 1. What Pix is, according to its regulation

*Main source: Resolution BCB No. 1 and its annexed Pix Regulation (English version), Articles 3, 33, 34 and 36.*

Pix is the instant payment scheme created and run by the Banco Central do Brasil (BCB). Its regulation defines an instant payment as an electronic transfer in which the payment order and the availability of the funds to the payee happen in real time, and for which the service "is available 24 (twenty-four) hours a day and every day of the year" (Art. 3, XI). For you, that sentence is an architectural requirement: no maintenance windows, no nightly batch that blocks payments, and on-call coverage at 3 a.m. on a Sunday.

Settlement depends on who the parties are:

- **Between different participants**, settlement happens in the **SPI** (Art. 33). The regulation defines the SPI as a centralized, real-time gross settlement infrastructure that moves funds between holders of PI accounts at the BCB (Art. 3, XIX). "Gross" means each payment settles individually, not netted at the end of the day.
- **Between two customers of the same participant**, settlement happens in the participant's own systems (Art. 34). Your wallet paying another of your wallet's users is a ledger transfer, not an SPI message.

Article 36 defines when a Pix counts as **authorized**: the payer's provider, after its security checks, finds enough balance in the payer's account and blocks that amount to start settlement. Notice the parallel with yesterday. The block is a **hold**, just like a card authorization, but it lasts seconds instead of days. In your ledger, an outgoing Pix creates a hold, the confirmation from the SPI turns it into an entry, and a rejection releases it.

Article 38 lists cases in which the payer's provider must reject a Pix. These include exceeding the maximum authorization time, a reasonable suspicion of fraud, and authentication problems. Article 35 says the maximum periods for transactions are set in a separate document, the Manual of Pix Schedules. So "Pix is instant" is a regulated service level, with deadlines your system must meet.

## 2. Participants and the DICT

*Main source: Resolution BCB No. 1, Art. 3 of the Resolution, Articles 23 to 29 and 45 to 52 of the Regulation.*

**Who participates.** Participation is mandatory for BCB-authorized institutions with "more than half a million active customer accounts", counting deposit, savings and prepaid accounts. Smaller institutions and those that only initiate payments may join voluntarily. The Regulation lists modalities in Article 23: transactional account provider, government entity, special settlement agent and initiator.

Not every participant connects to the SPI directly. A **responsible participant** (Articles 26 to 29) can take on other institutions that rely on it. Article 24 adds that payment institutions not authorized by the BCB need a contract with a responsible participant and at least R$1,000,000 in capital. A young wallet company usually lives in this indirect world: it offers Pix to its users through a partner bank that connects to the SPI. That is why your capstone has a "partner bank" and not a direct SPI connection.

**The DICT.** The DICT is the directory of Pix keys run by the BCB. A **Pix key** is information linked to a transactional account. The allowed types are phone number, e-mail, CPF, CNPJ and random key. When a user types a key, the payer's provider queries the DICT to find the account behind it, shows the payee's name, and only then sends the payment.

Some DICT rules have direct engineering consequences:

- Direct SPI participants must access the DICT directly; others go through a direct participant (Art. 48).
- Participants with direct access must keep their internal key database in sync with the DICT, and the synchronization check is available 24 hours a day.
- Participants must detect and handle excessive key queries that don't result in payments. Key lookups leak names, so a scraper querying thousands of keys is an attack. The rate limiters from this week's DSA problems are the tool for it.
- Key registration, removal, portability and ownership claims must be available to end users from 8:00 a.m. to 8:00 p.m. Brasília time, every day.

## 3. The identifiers: end_to_end_id, txid and rtrId

*Main source: Banco Central do Brasil, Pix API specification (bacen/pix-api, openapi.yaml, version 2.10.0).*

Every Pix carries identifiers, and choosing the right one as your primary key for reconciliation is a design decision.

| Identifier | Created by | What the spec says |
| --- | --- | --- |
| `endToEndId` (end_to_end_id, e2eid) | The payer's provider | "Id fim a fim da transação": the EndToEndIdentification carried in the pacs.002, pacs.004 and pacs.008 messages. Exactly 32 alphanumeric characters. |
| `txid` | The payee | A transaction identifier whose stated purpose is to let the payee's provider offer payment reconciliation to the payee. Between 26 and 35 alphanumeric characters, unique per payee CPF/CNPJ in the context of a charge. |
| `rtrId` | The provider that returns funds | The ReturnIdentification carried in the pacs.004 message of a return. Also 32 characters. |
| Return `id` | The payee's system | An id the client generates to represent one return uniquely. |

The pacs codes are ISO 20022 message types used by the SPI: pacs.008 carries a payment, pacs.002 a status report, and pacs.004 a return. In the spec's examples, end-to-end ids start with `E` and return ids with `D`.

What this means for your schema:

- Store the `end_to_end_id` on every Pix entry, with a unique constraint. It is the one id that every party (your partner bank, the SPI, the other provider) shares. A duplicated notification from the partner bank then fails the insert instead of crediting twice.
- When your wallet charges someone with a QR code, generate the `txid` yourself and store it on the expected payment. When the credit arrives, you match by `txid` to know which charge was paid.
- A return gets its own row, linked to the original `end_to_end_id`, with its own `rtrId`.

```sql
CREATE TABLE pix_transfers (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  end_to_end_id   char(32) UNIQUE,          -- known once the payer's provider creates it
  txid            varchar(35),
  direction       text NOT NULL CHECK (direction IN ('IN','OUT')),
  amount_cents    bigint NOT NULL CHECK (amount_cents > 0),
  status          text NOT NULL,
  created_at      timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE pix_returns (
  id                   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  original_e2e_id      char(32) NOT NULL REFERENCES pix_transfers(end_to_end_id),
  return_id            varchar(35) NOT NULL,
  rtr_id               char(32) UNIQUE,
  amount_cents         bigint NOT NULL CHECK (amount_cents > 0),
  status               text NOT NULL,
  UNIQUE (original_e2e_id, return_id)
);
```

## 4. Returns (devoluções)

*Main source: Resolution BCB No. 1, Regulation Articles 40 to 41-A; Pix API specification, endpoint `/pix/{e2eid}/devolucao/{id}`.*

A Pix can't be canceled after it settles. The regulation's answer is the **return** (devolução in Portuguese; the English text calls it a refund). Article 40 says funds already available in the payee's account may be returned, in whole or in part. As a rule, the payee starts the return. Multiple partial returns of the same Pix are allowed, up to the original amount. Article 41-A sets a general deadline: most returns "must be initiated within 90 (ninety) days" of the original transaction.

The Pix API spec shows how a return is requested and tracked:

- `PUT /pix/{e2eid}/devolucao/{id}` asks for a return of the Pix identified by `e2eid`, with an `id` chosen by the client. Using PUT with a client-chosen id makes the request naturally idempotent: sending it twice names the same return.
- The return's status is one of `EM_PROCESSAMENTO` (processing), `DEVOLVIDO` (returned) or `NAO_REALIZADO` (not done).
- The return amount is capped: for a common Pix, it can't exceed the value of the Pix itself.

In the ledger, a return is a **new entry in the opposite direction**, linked to the original. Never update the amount of the original entry. Keep a running total of returned amounts per `end_to_end_id`, and enforce `sum(returns) <= original` in the same transaction that inserts the return, with a row lock on the original transfer so two concurrent partial returns can't both pass the check.

## 5. The Special Return Mechanism (MED)

*Main source: Banco Central do Brasil, "Guia de implementação dos procedimentos de devolução no Pix, com ênfase no Mecanismo Especial de Devolução", version 4.3, sections 2, 4.2 and 4.3; Resolution BCB No. 1, Articles 39-B and 41-B.*

Ordinary returns depend on the payee's good will. Fraud victims can't count on that. The **MED** (Mecanismo Especial de Devolução) lets providers block and return funds without asking the receiving customer each time. The Regulation (Art. 41-B) covers suspected fraud and operational failures. The guide describes several cases, each with its own deadlines and message codes.

The fraud flow, which the guide calls funds recovery (Recuperação de Valores), works roughly like this:

1. The victim complains to the **payer's provider**, which opens a funds recovery in the DICT. The guide says it should not judge the merit before opening it, and the transaction must be at most 80 days old.
2. The DICT sends **infraction notifications** to the provider that received the original Pix and to the providers of later transfers, because fraudsters move money on quickly.
3. The **payee's provider** blocks the requested amount immediately (or the whole balance, if smaller), tells its customer, and analyzes the case within 7 calendar days. It closes the notification as "agreed" or "disagreed".
4. If fraud is confirmed, the payer's provider has 72 hours to start the return. The payee's provider then debits its customer and sends a pacs.004 with reason code FR01, which the guide says should happen within 6 hours in 99% of cases.

Separately, Article 39-B creates the **precautionary block** (bloqueio cautelar). The payee's provider must block incoming funds when it suspects fraud, and the block "must be effected simultaneously with the credit". It must notify the customer immediately, and the block lasts at most 72 hours. Article 39-B also says this block applies only to accounts of natural persons. The Regulation adds that only one refund request can be opened for each Pix.

| MED case (guide section) | Who acts | Main deadline in the guide |
| --- | --- | --- |
| Operational failure of the payer's provider (4.1) | Payee's provider returns | 48 hours from the request |
| Well-founded suspicion of fraud (4.2) | Payee's provider blocks and analyzes | 7 calendar days to analyze; 6 hours to return after confirmation |
| Precautionary block (4.3) | Payee's provider | Up to 72 hours to analyze |
| Fraud funds with no notification or block (4.4) | Payee's provider | Up to 90 days from the transaction |

The engineering lessons for a wallet that receives Pix:

- "Blocked" is a balance category. Your Module 6 ledger already has holds; a MED block is a hold your customer didn't create and can't release.
- Deadlines are in hours. Build a job that lists every open infraction notification with its due time, and alert well before it.
- The debit for a MED return can happen days after the credit, when the customer may have spent the money. Decide in advance what happens when the balance is lower than the requested amount; the guide's rule is to block whatever balance exists.

## 6. Open Finance at a high level

*Main source: Open Finance Brasil, home page.*

Open Finance is a BCB initiative to increase competition and improve financial products for consumers. The site defines it simply: "Open Finance significa sistema financeiro aberto." With the customer's consent, one authorized institution can see data held by another, such as balances, cards, statements and investments. The site also says the sharing enables new ways to make payments, transfers and Pix. Three points from the site are worth remembering. The customer chooses what to share, with whom and for how long, and can cancel at any time. There is no central system storing the data. It is free for consumers.

For this course, Open Finance matters in two ways. First, the Regulation defines a **payment transaction initiation service** as one in which a payment is "instructed by an institution that does not hold the account". Through Open Finance, another app could start a Pix from your user's wallet. Second, consent is a first-class object: it has a scope, an expiry and a revocation, and every access must be checked against it.

## 7. Tonight's lab: a payment state machine with a transitions table

*Main source: Stripe's PaymentIntent lifecycle (Monday) and Articles 36 to 41 of the Pix Regulation, applied to the wallet.*

The lab is a payment state machine with a table of valid transitions and tests. Put the rules in data, not in scattered `if` statements. Then one table answers "is this move allowed?" for card and Pix alike.

```typescript
type PaymentState =
  | 'CREATED' | 'AUTHORIZED' | 'CAPTURED' | 'SETTLED'
  | 'DECLINED' | 'VOIDED' | 'UNKNOWN' | 'REFUNDED_PARTIAL' | 'REFUNDED';

const transitions: Record<PaymentState, PaymentState[]> = {
  CREATED:          ['AUTHORIZED', 'DECLINED', 'UNKNOWN'],
  UNKNOWN:          ['AUTHORIZED', 'DECLINED', 'CAPTURED'], // resolved by a status query
  AUTHORIZED:       ['CAPTURED', 'VOIDED'],
  CAPTURED:         ['SETTLED', 'REFUNDED_PARTIAL', 'REFUNDED'],
  SETTLED:          ['REFUNDED_PARTIAL', 'REFUNDED'],
  REFUNDED_PARTIAL: ['REFUNDED_PARTIAL', 'REFUNDED'],
  DECLINED: [], VOIDED: [], REFUNDED: [],
};

export function assertTransition(from: PaymentState, to: PaymentState) {
  if (!transitions[from].includes(to)) {
    throw new Error(`Invalid transition ${from} -> ${to}`);
  }
}
```

For Pix, `AUTHORIZED` is the seconds-long hold and capture happens with the SPI confirmation. A return moves a captured or settled payment to `REFUNDED_PARTIAL` or `REFUNDED`.

Enforce the same rule in Postgres, so a bug in one service can't skip it. Store the allowed pairs in a table and check every update against it with a conditional `UPDATE`:

```sql
UPDATE payments p
   SET status = $2, updated_at = now()
 WHERE p.id = $1
   AND EXISTS (SELECT 1 FROM payment_transitions t
                WHERE t.from_status = p.status AND t.to_status = $2)
RETURNING p.status;
```

Zero rows returned means the move was invalid or another worker changed the row first. Tests to write: every listed transition succeeds; every unlisted pair fails; terminal states have no exits; two concurrent updates from the same state end with exactly one winner.

## Notes to write today

1. SPI, DICT, Pix key, end_to_end_id, txid and returns: one line each, in your own words, with the table column that stores each identifier.
2. Pix participants (mandatory threshold, modalities, responsible participant) and the 24/7 duty. Write where your wallet fits and which design rules the 24/7 duty forces on you.
3. The MED flow for fraud: who opens it, who blocks, who analyzes, who returns, and the deadlines (80 days, 7 days, 72 hours, 6 hours). Add the precautionary block (72 hours).
4. Open Finance in three sentences: what it is, how consent works, and what payment initiation means.

## Check yourself

These make good flashcards (see the [flashcards guide](../../FLASHCARDS.md)).

- Where does a Pix between two customers of the same institution settle? And between different institutions?
- According to the regulation, when is a Pix considered authorized?
- What is the end_to_end_id, who creates it, and how long is it?
- What is the difference between the end_to_end_id and the txid?
- Can a Pix be canceled after settlement? What happens instead, and within what general deadline?
- In the MED fraud flow, how long does the payee's provider have to analyze, and how long can a precautionary block last?
- Why should the DICT key lookup endpoint be rate limited?

## References

- **Main source:** Banco Central do Brasil, [Resolution BCB No. 1 with the Pix Regulation (English version)](https://www.bcb.gov.br/content/estabilidadefinanceira/pix/Pix_Regulation/Resolution_BCB_1.pdf). Skim Art. 3 of the Resolution (participation), and in the Regulation Art. 3 (definitions), Art. 23 to 29 (participation), Art. 33 to 41-C (settlement, authorization, returns, MED) and Chapter XIII (DICT). Free.
- **Main source:** Banco Central do Brasil, ["Guia de implementação dos procedimentos de devolução no Pix, com ênfase no Mecanismo Especial de Devolução"](https://www.bcb.gov.br/content/estabilidadefinanceira/pix/Guia_MED.pdf), in Portuguese. Read sections 2, 4.1, 4.2 and 4.3. Free.
- Banco Central do Brasil, [Pix page (regulation and manuals)](https://www.bcb.gov.br/estabilidadefinanceira/pix). The hub that links the regulation, the SPI and DICT manuals and statistics. Free. Open it in a browser (it needs JavaScript).
- Banco Central do Brasil, [Pix API specification (bacen/pix-api on GitHub)](https://github.com/bacen/pix-api). The OpenAPI file defines `endToEndId`, `txid`, `rtrId` and the return endpoints used in sections 3 and 4. Free.
- Open Finance Brasil, [home page](https://openfinancebrasil.org.br/), in Portuguese. Read the "what is it" and consent parts. Free.
