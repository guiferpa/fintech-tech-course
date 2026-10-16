# Module 8, Wednesday: tokens, authorization, fraud limits and KYC

[Module 8](../../modules/08-security-compliance-risk.md) · [Leia em português](day-3.pt-BR.md)

**Reading time:** about 45 minutes. Use the rest of the 2-hour block on the references at the end.

This is an original text written for this course. It is based on the references listed at the end, and each section names the source it follows. Where an idea comes from a specific author, the text says so.

## Why this matters for a fintech

Every request to move money has to answer three questions before it touches the ledger. Who is calling? Is this caller allowed to act on this specific account? And even if they are, should this particular transfer go through right now? The first is authentication (OAuth tokens and JWTs). The second is per-object authorization, where BOLA lives. The third is risk: limits, velocity checks and the anti-money-laundering duties a Brazilian payment institution has by regulation.

Get the first two wrong and an attacker moves other people's money. Get the third wrong and a legitimate account becomes a mule for stolen funds, or your fraud check goes down and takes every transfer with it. Friday's capstone builds the limits service, so today ends with its design.

## 1. OAuth 2.0 security in 2025: RFC 9700

*Main source: RFC 9700, "Best Current Practice for OAuth 2.0 Security", January 2025, sections 2 and 4.*

RFC 9700 collects a decade of attacks on OAuth deployments and turns them into rules. Its section 2 is a checklist, and section 4 explains each attack in detail. The rules a wallet team should know by heart:

| Rule (section) | What it says | The attack it stops |
| --- | --- | --- |
| Exact redirect URI matching (2.1) | Authorization servers "MUST utilize exact string matching" when comparing redirect URIs, except the port on native-app localhost URIs | Pattern or wildcard matching lets an attacker register a URI that captures codes (4.1) |
| PKCE (2.1.1) | Public clients must use PKCE, servers "MUST support PKCE", and S256 is the recommended method | Authorization code injection (4.5) and PKCE downgrade (4.8) |
| No implicit grant (2.1.2) | Clients "SHOULD NOT use the implicit grant" and should use the authorization code flow | Tokens leaking through URLs, browser history and Referer headers (4.2, 4.3) |
| No password grant (2.4) | The resource owner password credentials grant must not be used | The client sees the user's password, and it doesn't fit multi-factor authentication |
| Sender-constrained tokens (2.2) | Access tokens should be bound to the client with mTLS (RFC 8705) or DPoP (RFC 9449) | A stolen token is useless without the client's private key (4.10) |
| Refresh token protection (2.2.2) | "Refresh tokens for public clients MUST be sender-constrained or use refresh token rotation" | A leaked refresh token keeps working for months |
| Least privilege (2.3) | Tokens should carry minimal privileges and be restricted to an audience (specific resource servers) | A token for the statement service is replayed against the transfer service (4.9, 4.10) |
| Client authentication (2.5) | Prefer asymmetric methods such as mTLS or `private_key_jwt` | Leaked shared client secrets |

The RFC also updates the attacker model (section 3). It no longer assumes only a network attacker. It assumes attackers can run their own authorization server (mix-up attacks, section 4.4), read authorization responses that leak through logs or browser history, and obtain access tokens that leak from resource servers. That broader model is why sender-constrained tokens matter: in a world where tokens leak, a bearer token is a bearer cheque.

Notice the link to Monday. mTLS is not only for service-to-service traffic. RFC 9700 uses it to bind tokens to a client certificate, and partner bank APIs in Brazil, such as those in Open Finance, typically combine OAuth with mTLS for exactly this reason.

## 2. JWT pitfalls

*Main source: OWASP, "JSON Web Token Cheat Sheet".*

Most wallets use JWTs as access tokens. A JWT is easy to issue and easy to verify badly. The cheat sheet's main pitfalls, in the order you'd hit them:

1. **`alg: none`.** Some libraries once accepted unsigned tokens. The rule: make sure `"alg":"none"` is not accepted by your parser.
2. **Algorithm confusion.** A verifier that lets the token's header choose the algorithm can be tricked into treating your RSA or EC public key as an HMAC secret. Since the public key is public, the attacker can forge tokens. The cheat sheet says to hardcode the accepted algorithms and not mix public-key and MAC algorithms.
3. **Trusting keys named in the header.** Headers like `jku`, `x5u` or `jwk` can point to an attacker's key. Take keys from the issuer's configured `jwks_uri`, never from the token.
4. **Issuer and audience confusion.** Always validate `iss` and `aud`. The cheat sheet warns: "never verify against a union of keys from several issuers."
5. **Token type confusion.** A password-reset token or an ID token must not be accepted as an access token. Set and check a specific `typ` per purpose.
6. **No built-in revocation.** A JWT is valid until `exp`. Keep expirations short. If you need revocation, use a denylist keyed on `jti` and `iss`, not on the raw token string, which the cheat sheet says is not safe because alternate encodings can still verify.
7. **Claims are readable.** The payload is encoded, not encrypted. Never put a CPF, balance or card data in claims.
8. **Weak HMAC secrets.** "Do not use a password as MAC secret." The secret needs at least 160 bits of entropy from a secure generator.

In NestJS with the `jsonwebtoken` library, most of this is a matter of passing the right options:

```ts
import { verify } from 'jsonwebtoken';

const claims = verify(token, getPublicKey(kid), {
  algorithms: ['ES256'],              // fixed list, never taken from the header
  issuer: 'https://auth.wallet.example',
  audience: 'transfers-api',
}) as { sub: string; scope: string };
```

Look at `kid` here. The same key ID idea from Monday's webhook signing lets your auth server rotate its signing keys: publish the new public key in the JWKS, start signing with it, and remove the old one after the longest token lifetime has passed.

## 3. BOLA: authorize every object

*Main source: OWASP, "API1:2023 Broken Object Level Authorization".*

Authentication tells you the caller is customer 42. It doesn't tell you whether customer 42 may read account 9137. OWASP rates BOLA as easy to exploit, widespread and easy to detect: an attacker just changes an ID in the path, query, header or body and sees whether the response changes. The impact ranges from data disclosure to full account takeover.

OWASP's examples include a car maker's API that unlocked any vehicle given its VIN, and a document service whose delete mutation took any document ID. Translate those to a wallet:

- `GET /accounts/9137/statement`: anyone's statement.
- `POST /transfers` with `source_account_id: 9137`: spending from someone else's account.
- `DELETE /beneficiaries/555`: removing another customer's saved Pix key.

Two clarifications from the OWASP page are worth memorizing. First, comparing the user ID from the JWT with an ID parameter "covers only a small subset of cases". Real ownership is often indirect: a transfer belongs to an account, which belongs to a customer, or to a company where the user has a role. Second, if the user shouldn't reach the endpoint at all, the problem is function-level authorization (API5), not BOLA.

OWASP's defenses: an authorization mechanism based on user policies and hierarchy, used in every function that takes a client-supplied ID; random, unpredictable IDs such as GUIDs; and tests for the authorization mechanism that block deployment when they fail.

The most robust pattern in a Postgres-backed service is to make ownership part of the query, so a missing check returns nothing instead of someone else's data:

```ts
async getStatement(userId: string, accountId: string) {
  const { rows } = await this.db.query(
    `SELECT e.* FROM ledger_entries e
       JOIN accounts a ON a.id = e.account_id
      WHERE a.id = $1 AND a.owner_id = $2
      ORDER BY e.seq DESC LIMIT 50`,
    [accountId, userId],
  );
  if (rows.length === 0 && !(await this.accountOwnedBy(accountId, userId))) {
    throw new NotFoundException(); // 404, not 403: don't confirm the account exists
  }
  return rows;
}
```

Random UUIDs make guessing harder, but they are not authorization. IDs leak through URLs, logs and shared screenshots. The check must be there anyway, and a test that calls every endpoint with another user's IDs should be in CI.

## 4. Limits and velocity checks

*Main source: Stripe documentation, "Fraud prevention rules" and "Supported attributes" for Radar.*

Even an authenticated, authorized transfer may be fraud: a stolen phone, a socially engineered customer, an account used as a mule. Stripe's Radar is a good model of how rule-based risk checks work in practice.

**Actions.** Radar rules can request 3D Secure, allow, block or send a payment to review. Rules use the syntax `{action} if {attribute} {operator} {value}`, for example `Request 3D Secure if :risk_level: != 'normal' and :amount_in_usd: > 25`.

**Order and precedence.** Request-3DS rules are evaluated before review, block and allow rules. Review rules come after block rules. Allow rules override everything else, including Stripe's default rules, so the documentation advises using them minimally and adding `and :risk_level: != 'highest'` to them.

**Velocity attributes.** Radar exposes counters over time windows (hourly, daily, weekly, all time), such as `card_count_for_ip_address_hourly`, `declined_charges_per_card_number_daily` or `total_charges_per_email_weekly`. These capture the classic fraud signals: many cards from one IP, many declines on one card, a sudden burst from one customer.

**Operating rules safely.** The documentation's advice translates directly to a wallet:

- When unsure, use review instead of block, look at the false positives, then decide.
- Test a rule against history before enabling it. Radar simulates rules on the last 6 months of charges.
- Roll out gradually with traffic allocation. At 0% a rule runs in shadow mode and only reports what it would have done.
- Keep an audit trail of rule changes, and watch each rule's metrics, because fraud patterns change.

**The wallet's limits service.** For Friday you build a simpler version. A good starting rule set:

| Check | Example rule | Action |
| --- | --- | --- |
| Per-transfer limit | amount > R$ 5,000 | Block, or require step-up authentication |
| Daily cumulative limit | sum today + amount > R$ 10,000 | Block |
| Night limit | 20:00 to 06:00 and amount > R$ 1,000 | Block (Brazilian banks apply night limits to Pix) |
| Velocity | more than 5 transfers in 10 minutes | Review |
| New beneficiary | first transfer to this key and amount > R$ 500 | Hold for review |

A velocity count can be a plain query over an indexed table, which is fine at wallet scale:

```sql
SELECT count(*) AS n, coalesce(sum(amount), 0) AS total
FROM transfers
WHERE source_account_id = $1
  AND created_at > now() - interval '10 minutes'
  AND status <> 'REJECTED';
```

**Timeout and fallback.** The limits service is a dependency on the money path, so Module 1's lesson applies: a timeout means "I don't know". Decide in advance what happens then, write it down and test it:

- **Fail closed** (reject or hold) for high amounts, where the cost of letting fraud through is larger than the cost of a delayed transfer.
- **Fail open with a conservative local limit** for small amounts, so an outage of the risk service doesn't stop every R$ 20 Pix.
- Always record that the decision was a fallback, so the transfer can be re-checked when the service recovers.

```ts
const decision = await withTimeout(this.limits.check(req), 150).catch(() => null);
if (decision === null) {
  return req.amountCents <= FALLBACK_MAX_CENTS
    ? { action: 'ALLOW', reason: 'limits_timeout_fallback' }
    : { action: 'HOLD', reason: 'limits_timeout_fallback' };
}
```

Module 9 adds the circuit breaker around this call.

## 5. KYC and anti-money-laundering: BCB Circular 3.978/2020

*Main source: Banco Central do Brasil, Circular nº 3.978, of January 23, 2020.*

Velocity rules protect your customers from fraudsters. Anti-money-laundering rules protect the financial system from your customers. In Brazil, institutions authorized by the Central Bank, including payment institutions, must follow Circular 3.978/2020 on preventing money laundering and terrorist financing (PLD/FT in Portuguese). You only need to skim its structure today:

| Chapter | Topic | What it means for engineers |
| --- | --- | --- |
| II, III | PLD/FT policy and governance | A board-approved policy and a named director responsible |
| IV | Internal risk assessment | Products, customers and channels are rated by risk; reviewed every two years |
| V | Knowing the customer (KYC) | Identification, qualification and risk classification of each customer |
| VI | Recording operations | Every operation recorded, with origin and destination of funds |
| VII | Monitoring, selection and analysis | Suspicious operations selected within 45 days and analyzed within 45 more, each in a documented dossier |
| VIII | Reporting to Coaf | Suspicious cases reported "até o dia útil seguinte ao da decisão de comunicação" |
| IX | Knowing employees, partners and contractors | Due diligence on your own staff and partners |
| XI | Effectiveness assessment | An annual effectiveness report |
| XII | Final provisions, including retention | Customer information, operation records and dossiers kept "pelo período mínimo de dez anos" |

Three points connect directly to your code:

- **KYC is three steps, not one.** Identification (who is this, with verified data), qualification (where they live, their financial capacity, kept up to date) and classification (which risk category they fall in). A customer's risk class should change your limits.
- **Politically exposed persons (PEPs)** need reinforced procedures, and the status lasts five years after they leave office. That is a field in your customer model with an effect on monitoring.
- **No tipping off.** Article 50 says reports to Coaf are made without informing the people involved. A customer whose transfer is held for AML review should not see "reported to Coaf" in the app.

This is also the legal obligation behind Tuesday's LGPD answer. The ten-year retention in the Circular is exactly the kind of "obrigação legal ou regulatória" that LGPD article 16 allows you to keep data for.

## 6. Capstone prep: the test webhook client and the task list

*Main source: this module's capstone tasks. No AI for any capstone code; today you only plan.*

The pass criterion is concrete: rotating the signing key with an active webhook client causes zero verification failures. You need a client that proves it. Plan a small separate service that:

- Fetches your public verification keys from the public endpoint and caches them with a TTL.
- On an unknown `kid`, refetches the keys once before failing, so a newly published key is picked up quickly.
- Verifies signature and timestamp on every webhook and counts successes and failures, exposing the counters on an endpoint your test can read.
- Runs under constant load (for example, a transfer every 200 ms producing webhooks) while you rotate.

Then write the task list for Thursday and Friday, mapped to the six capstone items:

1. Signing with `kid` and two active keys; the public keys endpoint.
2. Rotation script: publish new, switch signing, wait the overlap, retire old. Test: failure counter stays at zero.
3. CPF envelope encryption: data key per record, master key in Vault Transit or LocalStack KMS.
4. Log redaction for CPF, card data and tokens, with a test that greps the logs.
5. Limits and velocity service with a timeout and the fallback table from section 4.
6. `docs/m08.md`: the STRIDE table from Tuesday, the key inventory (what key, where, who can use it, rotation period), and the LGPD retention table.

## Notes to write today

1. The OAuth attacks RFC 9700 describes (redirect URI manipulation, code injection, token leakage, mix-up, stolen tokens) and the defense for each.
2. Common JWT pitfalls and the verification options that prevent them.
3. Per-resource authorization: why the JWT user ID check isn't enough, and your query pattern for ownership.
4. Limits and velocity checks: your wallet's rule table, rule actions and precedence, and the fallback when the check times out.
5. KYC and AML duties: the structure of Circular 3.978, the three KYC steps, the Coaf deadline and the ten-year retention.
6. Lab: the test webhook client design and the capstone task list.

## Check yourself

These make good flashcards (see the [flashcards guide](../../FLASHCARDS.md)).

- Why does RFC 9700 require exact string matching of redirect URIs?
- What does PKCE prevent, and which method does RFC 9700 recommend?
- What is a sender-constrained token, and what two mechanisms does RFC 9700 name?
- How does an algorithm confusion attack on JWT work, and what single option prevents it?
- Why return 404 instead of 403 when a user requests an account they don't own?
- In Stripe Radar, which rule type overrides all others, and what is shadow mode?
- What should your transfer flow do when the limits service times out?

## References

- **Main source:** IETF, [RFC 9700, "Best Current Practice for OAuth 2.0 Security"](https://www.rfc-editor.org/rfc/rfc9700), January 2025. Read section 2 in full, then sections 4.1, 4.5, 4.8 and 4.10. Free.
- OWASP Cheat Sheet Series, ["JSON Web Token Cheat Sheet"](https://cheatsheetseries.owasp.org/cheatsheets/JSON_Web_Token_Cheat_Sheet.html). Read the whole page. Free.
- OWASP, ["API1:2023 Broken Object Level Authorization"](https://owasp.org/API-Security/editions/2023/en/0xa1-broken-object-level-authorization/). Read the whole page, including the attack scenarios. Free.
- Stripe documentation, ["Fraud prevention rules"](https://docs.stripe.com/radar/rules). Read "Built-in rules", "Create rules" and "Construct transaction rules". Free.
- Stripe documentation, ["Supported attributes"](https://docs.stripe.com/radar/rules/supported-attributes). Skim the velocity counters used in section 4. Free.
- Banco Central do Brasil, [Circular nº 3.978/2020](https://normativos.bcb.gov.br/Lists/Normativos/Attachments/50905/Circ_3978_v3_P.pdf) (Portuguese). Skim the chapter structure, then read chapter V (KYC) and articles 48 to 50 and 67. Free.
