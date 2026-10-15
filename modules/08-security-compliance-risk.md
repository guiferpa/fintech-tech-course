# Module 8: Security, compliance and risk

**Week 10** · [Back to the syllabus](../README.md) · [Leia em português](08-security-compliance-risk.pt-BR.md)

## Goal

Apply security where money flows: key management and rotation, envelope encryption, PCI/LGPD scope, and limits/fraud checks.

## Monday to Wednesday: reading + lab (3 h a day)

| Day | Reading (2 h) | Lab (1 h) |
| --- | --- | --- |
| Mon | Hashing vs. encryption vs. HMAC; TLS and mTLS between services and with partners.<br>KMS and HSM, envelope encryption (AWS KMS docs), key rotation. | Vault in dev mode (or LocalStack KMS) in Compose; encrypt and decrypt from the CLI. |
| Tue | OWASP API Security Top 10 (2023).<br>PCI DSS Quick Reference Guide and tokenization; LGPD articles 7, 16 and 18 (deletion vs. duty to keep financial records). | STRIDE threat model: data flow diagram and list of threats (draft of docs/m08.md). |
| Wed | RFC 9700 (OAuth 2.0 Security BCP), JWT pitfalls, per-resource authorization (BOLA).<br>Fraud and limits (velocity checks), KYC/AML and Brazilian Central Bank regulation at a high level. | Capstone prep: test webhook client and task list. No TCM code. |

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
