# Module 8, Tuesday: API risks, threat modeling, PCI scope and LGPD

[Module 8](../../modules/08-security-compliance-risk.md) · [Leia em português](day-2.pt-BR.md)

**Reading time:** about 45 minutes. Use the rest of the 2-hour block on the references at the end.

This is an original text written for this course. It is based on the references listed at the end, and each section names the source it follows. Where an idea comes from a specific author, the text says so.

## Why this matters for a fintech

Monday was about protecting bytes. Today is about protecting the system and staying on the right side of the rules. Three questions come up in almost every fintech interview and design review:

- What are the ways an attacker can abuse our API, and which ones have we covered?
- Do card numbers ever touch our servers, and if so, how much of our infrastructure is now under PCI DSS?
- A customer asked us to delete their data. What do we delete, and what does the law force us to keep?

You'll answer the first one today in the lab, as a STRIDE threat model. The second and third are design decisions that are expensive to change later, so you make them early.

## 1. The OWASP API Security Top 10

*Main source: OWASP API Security Top 10, 2023 edition.*

OWASP's list is a shared vocabulary for API risks. The 2023 edition has ten entries. The table restates each in one line and gives a wallet example.

| ID | Risk | In a wallet, it looks like |
| --- | --- | --- |
| API1 | Broken Object Level Authorization (BOLA) | `GET /accounts/{id}/statement` returns any account's statement to any logged-in user |
| API2 | Broken Authentication | Tokens that never expire, weak login without rate limits, a JWT accepted with `alg: none` |
| API3 | Broken Object Property Level Authorization | The response includes `internal_risk_score`, or a `PATCH` lets the user set `daily_limit` |
| API4 | Unrestricted Resource Consumption | An attacker triggers thousands of SMS one-time codes, which you pay for per message |
| API5 | Broken Function Level Authorization | A regular user calls `POST /admin/accounts/{id}/unblock` and it works |
| API6 | Unrestricted Access to Sensitive Business Flows | Bots create thousands of accounts to farm a sign-up bonus |
| API7 | Server Side Request Forgery | A "webhook URL" field lets a customer make your server call `http://169.254.169.254/` |
| API8 | Security Misconfiguration | Verbose stack traces in production, permissive CORS, default credentials |
| API9 | Improper Inventory Management | An old `/v1/transfers` without the new limits check is still deployed |
| API10 | Unsafe Consumption of APIs | You trust the partner bank's webhook body without verifying its signature |

Three notes on the list.

**BOLA is first for a reason.** OWASP explains that APIs expose endpoints that take object IDs, and every one of them is a chance to forget the check that the caller may touch that object. A wallet is full of such endpoints: accounts, transfers, statements, cards, beneficiaries. Wednesday covers BOLA in depth.

**API6 is about business logic, not bugs.** OWASP notes this risk doesn't necessarily come from implementation flaws. Your sign-up endpoint can be perfectly coded and still be abused at scale. The defenses are limits, velocity checks and device signals, which is Wednesday's fraud topic.

**API7 matters if you send webhooks.** The capstone lets clients register a webhook URL. If your sender follows any URL a client gives, you have built an SSRF tool. Validate the scheme (HTTPS only), resolve the host and reject private and link-local address ranges, and don't follow redirects blindly.

## 2. Threat modeling with STRIDE

*Main source: OWASP, "Threat Modeling Cheat Sheet". The STRIDE categories were created at Microsoft; the cheat sheet presents them with the security property each one violates.*

Today's lab is a threat model of your wallet. The cheat sheet frames threat modeling around four questions from the Threat Modeling Manifesto: "What are we working on?", "What can go wrong?", "What are we going to do about it?" and "Did we do a good enough job?"

**What are we working on: the data flow diagram.** The cheat sheet says a model should show external entities, processes, data stores and data flows, and should make trust boundaries clear, since boundaries "often represent possible attack points." For the wallet, a first diagram has:

- External entities: the customer's app, the partner bank, webhook clients, back-office staff.
- Processes: API gateway, transfer service, ledger service, webhook sender, limits service.
- Data stores: Postgres (ledger, customers, PII), the message broker, Vault.
- Trust boundaries: internet to gateway, gateway to internal services, your network to the partner bank, your network to client webhook endpoints.

**What can go wrong: STRIDE.** For each element and each flow that crosses a boundary, walk through six categories. The cheat sheet pairs each with the property it violates. The wallet examples and mitigations below are this course's.

| Threat | Property violated | Wallet example | Typical mitigation |
| --- | --- | --- | --- |
| **S**poofing | Authentication | A forged "payment received" webhook from a fake partner bank | Verify partner signatures, mTLS with the partner |
| **T**ampering | Integrity | Changing the amount of a transfer message on the broker | Signed or authenticated messages, least-privilege broker ACLs |
| **R**epudiation | Accountability | A staff member reverses a transfer and denies it | Append-only audit log with actor, time and reason |
| **I**nformation disclosure | Confidentiality | CPFs and tokens appear in application logs | Log redaction, envelope encryption of PII |
| **D**enial of service | Availability | A flood of transfer requests exhausts the connection pool | Rate limits, timeouts, bulkheads (Module 9) |
| **E**levation of privilege | Authorization | A user edits a JWT claim to `role: admin` | Verify signatures with fixed algorithms, server-side roles |

**What are we going to do about it.** The cheat sheet lists four responses to each threat: mitigate, eliminate, transfer or accept. "Transfer" is very real in payments. Using a processor's hosted card fields transfers most card-data risk to the processor, which is the next section.

For the lab, write each threat as one row: element, STRIDE letter, scenario, response, and a link to the code or task that implements it. That table is the first draft of `docs/m08.md`.

## 3. PCI DSS in one page

*Main source: PCI Security Standards Council, document library, "PCI DSS v4.0.1" and the "PCI DSS Quick Reference Guide". The library page didn't list the Quick Reference Guide when this lesson was written, so the list of requirements below comes from the Wikipedia article on PCI DSS, which quotes the v4.0.1 requirement titles.*

PCI DSS (Payment Card Industry Data Security Standard) applies to anyone who stores, processes or transmits cardholder data. It is set by the PCI Security Standards Council, which the card brands founded. The current version is 4.0.1.

The standard groups twelve requirements under six goals:

| Goal | Requirements |
| --- | --- |
| Build and maintain a secure network and systems | 1. Network security controls. 2. Secure configurations. |
| Protect account data | 3. Protect stored account data. 4. Strong cryptography in transit over open networks. |
| Maintain a vulnerability management program | 5. Protect against malicious software. 6. Develop and maintain secure systems and software. |
| Implement strong access control measures | 7. Restrict access by business need to know. 8. Identify users and authenticate access. 9. Restrict physical access. |
| Regularly monitor and test networks | 10. Log and monitor all access. 11. Test security regularly. |
| Maintain an information security policy | 12. Organizational policies and programs. |

Two terms decide how painful compliance is:

- **Cardholder data environment (CDE)**: the systems that store, process or transmit card data, plus anything connected to them that could affect their security. Every system in scope must meet the requirements.
- **Validation**: smaller merchants fill a Self-Assessment Questionnaire (SAQ), while large ones are assessed by a Qualified Security Assessor (QSA). Which SAQ applies depends on how card data flows through you.

Notice how much of Monday maps directly to requirements 3 and 4: encryption at rest, key management, and strong cryptography in transit.

## 4. Tokenization: the best way to shrink scope

*Main source: Stripe documentation, "Integration security guide". The general idea of tokenization is standard industry practice.*

The cheapest PCI control is to never see the card number (the PAN). **Tokenization** replaces the PAN with a token, a value that is useless outside the provider that issued it. The provider keeps the PAN in its own PCI-certified vault. You store the token and charge with it.

Stripe's guide shows what's at stake. If your business handles card data directly, it says "you might be required to meet more than 300 security controls in PCI DSS," plus dedicated security hardware and software and external auditors. Its low-risk integrations instead collect card data in the provider's fields, so the data goes straight to Stripe without passing through your servers. The guide also says what you may keep: the card brand, the last four digits and the expiry date are not subject to PCI compliance, so you can store them to show "Visa •••• 4242".

For the wallet, the rule is:

```text
Customer device ──card data──▶ processor's hosted fields / SDK ──▶ processor vault
        │                                                            │
        └────────── token + last4 + brand + expiry ◀──────────────────┘
                          │
                          ▼
                 your API and Postgres  (no PAN, no CVV, ever)
```

Consequences to put in your design notes:

- Your servers never receive a PAN or CVV, so they never log one either. Log redaction (Friday's item 4) is a second line of defense, not the first.
- The token is still sensitive. Someone with your processor API key and a token can charge the card. Store the API key in Vault and restrict who can call the charge endpoint.
- Scope doesn't vanish completely. The page that hosts the card fields still matters, which is why the Stripe guide also discusses TLS, third-party JavaScript and Content Security Policy.

## 5. LGPD: deleting data vs. keeping financial records

*Main source: Lei nº 13.709/2018 (LGPD), articles 5, 7, 16 and 18. This is an engineering reading of the law, not legal advice. Confirm decisions with your company's DPO and lawyers.*

The LGPD is Brazil's general data protection law. Article 5 defines personal data as information about an identified or identifiable natural person, which covers CPF, name, phone, address and also the transaction history tied to a customer.

**Article 7: you need a legal basis.** Processing is allowed only under listed hypotheses. Consent (I) is one, and it's the one people remember, but a wallet relies mostly on others:

- II: compliance with a legal or regulatory obligation of the controller.
- V: execution of a contract with the data subject (the account agreement itself).
- VI: regular exercise of rights in judicial, administrative or arbitration proceedings (defending a chargeback or a lawsuit).
- IX: legitimate interests of the controller, unless the subject's rights prevail.
- X: credit protection.

**Article 18: the data subject's rights.** The customer can ask for confirmation that you process their data, access, correction, anonymization or blocking or deletion of unnecessary or excessive data, portability, information about sharing, and revocation of consent. Read item VI carefully: the right is to deletion of data processed **with consent**, "exceto nas hipóteses previstas no art. 16 desta Lei."

**Article 16: when you may keep data.** Personal data must be deleted when processing ends, but keeping it is authorized for, among other purposes, "cumprimento de obrigação legal ou regulatória pelo controlador" (item I), and for the controller's exclusive use if the data is anonymized (item IV).

So a deletion request in a wallet doesn't mean `DELETE FROM customers`. Financial institutions have record-keeping duties. Wednesday's reading, BCB Circular 3.978/2020, requires customer information and transaction records to be kept for at least ten years. The ledger itself is also the source of truth for balances and reconciliation, and Module 6 made it append-only on purpose.

A design that serves both duties:

| Data | On a deletion request |
| --- | --- |
| Marketing preferences, push tokens, analytics profiles (consent-based) | Delete now |
| Data processed under contract that has no legal retention duty | Delete when the account is closed and settled |
| KYC data and transaction records under a legal duty | Block from normal use, keep until the retention date, then delete |
| Ledger entries | Keep; they reference `customer_id`, not the CPF or name |

```sql
ALTER TABLE customer_pii
  ADD COLUMN blocked_at      timestamptz,
  ADD COLUMN retain_until    date;   -- set from the legal basis when the account closes

-- Daily job: purge PII whose retention period has passed
DELETE FROM customer_pii
WHERE blocked_at IS NOT NULL AND retain_until < current_date;
```

Two engineering habits make this workable. First, keep PII in its own table, separate from the ledger, so blocking or deleting it never touches money data. Second, Monday's per-record DEK gives you **crypto-shredding**: destroy a customer's data key and every copy of their encrypted CPF becomes unreadable, including copies in backups you can't edit. Write down the legal basis for each retained field. "We keep it because of law X, until date Y" is the answer an auditor and a customer both deserve.

## Notes to write today

1. The ten OWASP API risks in one line each, with BOLA first and a wallet example for at least five of them.
2. What PCI DSS asks for (six goals, twelve requirements, what a CDE is) and how tokenization shrinks the scope, with the data flow drawn.
3. Deletion requests vs. the duty to keep financial records: which LGPD articles apply (7, 16, 18) and your wallet's table of "delete now / block and keep / keep".
4. Lab: the data flow diagram with trust boundaries, and the STRIDE threat list as the first draft of `docs/m08.md`.

## Check yourself

These make good flashcards (see the [flashcards guide](../../FLASHCARDS.md)).

- What is the difference between BOLA (API1) and Broken Function Level Authorization (API5)?
- Why is SSRF a risk for a service that sends webhooks, and what are two defenses?
- Name the six STRIDE categories and the security property each one violates.
- What is a cardholder data environment, and why does tokenization make it smaller?
- Which card details can a wallet store without being in PCI scope, according to the Stripe guide?
- Under the LGPD, why can a fintech refuse to delete a customer's transaction history after a deletion request?
- What is crypto-shredding, and which Monday design makes it possible?

## References

- **Main source:** OWASP, ["OWASP API Security Top 10 (2023)"](https://owasp.org/API-Security/editions/2023/en/0x11-t10/). Read the summary page, then the full page for API1, API4, API6 and API7. Free.
- PCI Security Standards Council, [document library](https://www.pcisecuritystandards.org/document_library/): "PCI DSS Quick Reference Guide" and "PCI DSS v4.0.1". Read the parts on the twelve requirements and scoping. Free, sign-up required for some documents.
- Lei nº 13.709/2018, [LGPD](https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2018/lei/l13709.htm) (Portuguese). Read articles 5, 7, 16 and 18. Free.
- OWASP Cheat Sheet Series, ["Threat Modeling Cheat Sheet"](https://cheatsheetseries.owasp.org/cheatsheets/Threat_Modeling_Cheat_Sheet.html). The source for section 2 and the method for today's lab. Free.
- Stripe documentation, ["Integration security guide"](https://docs.stripe.com/security/guide). The source for section 4: low-risk integrations and what card data you can store. Free.
- Wikipedia, ["Payment Card Industry Data Security Standard"](https://en.wikipedia.org/wiki/Payment_Card_Industry_Data_Security_Standard). Used for the list of PCI DSS v4.0.1 goals and requirements. Free.
