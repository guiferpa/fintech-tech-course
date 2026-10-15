# Module 8: Security, compliance and risk

**Week 10** · [Back to the syllabus](../README.md) · [Leia em português](08-security-compliance-risk.pt-BR.md)

## Goal

Apply security where money flows: key management and rotation, envelope encryption, PCI/LGPD scope, and limits/fraud checks.

## Monday to Wednesday: DSA + reading + lab (3 h 30 a day)

| Day | DSA (30 min) | Reading (2 h) | Lab (1 h) |
| --- | --- | --- | --- |
| Mon | [LRU Cache](https://leetcode.com/problems/lru-cache/) (hash map + doubly linked list) | [OWASP, "Cryptographic Storage Cheat Sheet"](https://cheatsheetseries.owasp.org/cheatsheets/Cryptographic_Storage_Cheat_Sheet.html) (free): hashing vs. encryption vs. HMAC, and key management basics.<br>[Cloudflare Learning, "What is mutual TLS (mTLS)?"](https://www.cloudflare.com/learning/access-management/what-is-mutual-tls/) (free): TLS and mTLS between services and with partners.<br>[AWS KMS Developer Guide, "AWS KMS cryptography essentials"](https://docs.aws.amazon.com/kms/latest/developerguide/kms-cryptography.html) (free): KMS vs. HSM, envelope encryption and key rotation. | Vault in dev mode (or LocalStack KMS) in Compose; encrypt and decrypt from the CLI. |
| Tue | [LFU Cache (1/2)](https://leetcode.com/problems/lfu-cache/) (hash map + frequency buckets)<br>Design the structures and get get/put working. | [OWASP API Security Top 10 (2023)](https://owasp.org/API-Security/editions/2023/en/0x11-t10/) (free): the 10 risks, with BOLA first.<br>[PCI Security Standards Council, document library: "PCI DSS Quick Reference Guide"](https://www.pcisecuritystandards.org/document_library/) (free, sign-up required): what PCI DSS asks for and how tokenization shrinks the scope.<br>[LGPD, Lei nº 13.709/2018, articles 7, 16 and 18 (Portuguese)](https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2018/lei/l13709.htm) (free): deletion requests vs. the duty to keep financial records. | STRIDE threat model: data flow diagram and list of threats (draft of docs/m08.md). |
| Wed | [LFU Cache (2/2)](https://leetcode.com/problems/lfu-cache/) (hash map + frequency buckets)<br>Finish, then test eviction ties (same frequency, least recently used goes first). | [RFC 9700, "Best Current Practice for OAuth 2.0 Security"](https://www.rfc-editor.org/rfc/rfc9700) (free): the attacks it describes and the recommended defenses.<br>[OWASP, "JSON Web Token Cheat Sheet"](https://cheatsheetseries.owasp.org/cheatsheets/JSON_Web_Token_Cheat_Sheet.html) (free): common JWT pitfalls.<br>[OWASP, "API1:2023 Broken Object Level Authorization"](https://owasp.org/API-Security/editions/2023/en/0xa1-broken-object-level-authorization/) (free): per-resource authorization.<br>[Stripe documentation, "Fraud prevention rules"](https://docs.stripe.com/radar/rules) (free): limits and velocity checks in practice.<br>[Banco Central do Brasil, Circular nº 3.978/2020 (Portuguese)](https://normativos.bcb.gov.br/Lists/Normativos/Attachments/50905/Circ_3978_v3_P.pdf) (free): KYC and anti-money-laundering duties; skim the structure. | Capstone prep: test webhook client and task list. No TCM code. |

Solve without AI, 30-minute timebox. Method and full list: [DSA track](../DSA.md).

In labs, AI is allowed only to clarify concepts, never to write capstone code.

## Thursday and Friday: capstone (TCM), no AI

Everything is done WITHOUT AI. No ChatGPT, Claude, Copilot or AI autocomplete in the editor. Allowed: official docs, books, your own notes and previous labs. Whatever doesn't fit today becomes cut scope for the next checkpoint; the deadline does not move.

1. (1 h) Webhook signing with kid and two active keys; public endpoint with verification keys.
2. (1 h) Rotation: new key, overlap, retire the old one; test with an active client and no failed verification.
3. (1 h) Envelope encryption of the CPF: data key per record, master key in Vault/KMS.
4. (30 min) Redact CPF, card data and tokens from logs.
5. (1 h) Limits and velocity check service with timeout and a defined fallback.
6. (30 min) Final docs/m08.md.

Thursday covers items 1 to 3; Friday covers the rest and ends with 30 minutes of delivery.

## Pass criteria

Rotating the signing key with an active webhook client causes zero verification failures.

## Mastery test

Answer out loud, in under 2 minutes, without notes, and record it:

> Where do the keys that sign the webhooks you send live, and how do you rotate them without breaking clients?
