# Module 8, Monday: hashing, encryption, keys and mTLS

[Module 8](../../modules/08-security-compliance-risk.md) · [Leia em português](day-1.pt-BR.md)

**Reading time:** about 45 minutes. Use the rest of the 2-hour block on the references at the end, starting with the sections marked as the main source.

This is an original text written for this course. It is based on the references listed at the end, and each section names the source it follows. Where an idea comes from a specific author, the text says so.

## Why this matters for a fintech

A wallet stores things that hurt people when they leak: CPF numbers, phone numbers, partner bank credentials, the private keys that sign your webhooks. It also sends money instructions over networks you don't control. An attacker who reads your database dump, or who sits between you and the partner bank, should get nothing useful.

Cryptography is the tool for that, but most real incidents don't come from broken algorithms. They come from the wrong tool for the job (encrypting a password, hashing a CPF you need to read back), from keys stored next to the data they protect, and from keys that nobody knows how to rotate. This lesson is about choosing the right primitive and, above all, about managing keys. Thursday's capstone asks you to rotate a signing key with a live client and zero failures, so the key lifecycle is the part to master.

## 1. Four tools that people confuse

*Main source: OWASP, "Cryptographic Storage Cheat Sheet", sections "Introduction" and "Algorithms". The HMAC and signature rows come from general cryptography practice, not from the cheat sheet, which doesn't cover HMAC.*

Start by asking what the reader of the data needs to do with it. That question picks the primitive.

| Tool | Key? | Reversible? | Answers the question | Wallet example |
| --- | --- | --- | --- | --- |
| Hash (SHA-256) | No | No | "Are these the same bytes as before?" | Fingerprint of an uploaded document |
| Password hash (Argon2id, bcrypt) | No, but salted and slow on purpose | No | "Did the user type the right password?" | Login password, transaction PIN |
| HMAC (HMAC-SHA256) | Shared secret | No | "Did someone who holds the secret produce this, unchanged?" | Webhook signature with a shared secret |
| Digital signature (Ed25519, ECDSA) | Private key signs, public key verifies | No | "Did the holder of the private key produce this, unchanged?" | Webhook signature verifiable from a public endpoint |
| Encryption (AES-256-GCM) | Secret key | Yes | "Can only key holders read this?" | CPF stored in Postgres |

The OWASP sheet is direct about one of these choices: passwords must not be protected with reversible encryption. If an attacker gets your key and your table, every password comes out. Use a password hashing algorithm instead, and the sheet points to its sibling, the Password Storage Cheat Sheet, for the details.

The opposite mistake is hashing a CPF. You need it back to send to the partner bank, and a SHA-256 of an 11-digit number is trivial to brute force anyway. A CPF needs encryption.

HMAC and signatures solve a different problem: integrity and origin, not secrecy. A webhook body is not secret to the receiver. What the receiver needs to know is that you sent it and nobody changed it. With HMAC both sides hold the same secret, so you must hand each client a secret over a secure channel. With a signature, you keep the private key and publish the public key. That is why the capstone asks for a "public endpoint with verification keys": public keys can be published, shared secrets can't.

## 2. Encrypting data at rest, the OWASP way

*Main source: OWASP, "Cryptographic Storage Cheat Sheet", sections "Architectural Design", "Algorithms", "Secure Random Number Generation" and "Defense in Depth".*

**Decide where to encrypt from the threat model.** The sheet lists four layers: application, database, filesystem and hardware. Disk encryption protects against someone walking out with a disk, but it does nothing against a SQL injection, because the database decrypts the pages for anyone who can query it. If the threat is "an attacker reads rows through the application or a leaked backup", you need application-level encryption of the sensitive columns.

**Store less.** The sheet's strongest advice is a single sentence: "The best way to protect sensitive information is to not store it in the first place." It uses card numbers as the example. Tuesday shows how tokenization lets a wallet avoid storing card numbers at all.

**Pick boring, authenticated algorithms.** For symmetric encryption the sheet recommends AES with at least a 128-bit key, ideally 256 bits. It wants authenticated modes whenever they are available, with GCM and CCM as first choices. CTR and CBC are fallbacks that need a separate MAC (Encrypt-then-MAC), and ECB should be avoided. On custom algorithms the advice is three words: "Don't do this."

An authenticated mode detects tampering: if someone changes bytes in an AES-GCM ciphertext, decryption fails. You can also bind **additional authenticated data (AAD)**, such as the customer ID, so a ciphertext copied from one customer's row into another customer's row fails to decrypt.

**Use a cryptographically secure random generator** for keys, IVs and tokens. In Node.js that is `crypto.randomBytes()`, never `Math.random()`. The sheet also warns that you shouldn't rely on UUIDs as secrets unless you know the generator is cryptographically secure.

A minimal AES-256-GCM helper in Node.js looks like this. The 12-byte IV must be unique for every encryption with the same key, which is why it comes from `randomBytes`.

```ts
import { createCipheriv, createDecipheriv, randomBytes } from 'node:crypto';

export function encrypt(plaintext: Buffer, key: Buffer, aad: Buffer) {
  const iv = randomBytes(12);
  const cipher = createCipheriv('aes-256-gcm', key, iv);
  cipher.setAAD(aad);
  const ciphertext = Buffer.concat([cipher.update(plaintext), cipher.final()]);
  return { iv, ciphertext, tag: cipher.getAuthTag() };
}

export function decrypt(c: { iv: Buffer; ciphertext: Buffer; tag: Buffer }, key: Buffer, aad: Buffer) {
  const decipher = createDecipheriv('aes-256-gcm', key, c.iv);
  decipher.setAAD(aad);
  decipher.setAuthTag(c.tag); // final() throws if the tag doesn't match
  return Buffer.concat([decipher.update(c.ciphertext), decipher.final()]);
}
```

The sheet prefers that a library handle IVs for you, so in production use a maintained library or your KMS client. The snippet only shows the moving parts.

**Defense in depth.** The sheet says applications "should be designed to still be secure even if cryptographic controls fail." Encryption doesn't replace authorization checks, and an encrypted ID in a URL is not access control.

## 3. Key management: the part that actually breaks

*Main source: OWASP, "Cryptographic Storage Cheat Sheet", sections "Key Management" and "Key Storage".*

An algorithm is only as strong as the secrecy of its key. The sheet asks for formal, tested processes for the whole key lifecycle: generation, storage, distribution, deployment to servers, rotation and decommissioning.

**Generation.** Keys must come from a cryptographically secure function, never from words, phrases or keyboard patterns. Use independent keys for independent purposes. The key that encrypts CPFs must not also sign webhooks.

**Rotation.** The sheet lists when to rotate:

- When a key is known or suspected to be compromised, including when someone with access leaves the company.
- When its cryptoperiod ends (it cites NIST SP 800-57 for guidance on periods).
- When the amount of data encrypted under the key approaches the mode's safe limit.
- When the algorithm's security changes, for example after a new attack.

After rotating, existing data can be handled in two ways. You can decrypt and re-encrypt everything with the new key, which the sheet says should generally be preferred. Or you can tag each ciphertext with the ID of the key that produced it and keep old keys available for decryption. In practice wallets often do the second immediately and the first as a background job. Either way, the sheet reminds you to keep retired keys for a while so old backups stay readable.

**Storage.** The sheet recommends dedicated mechanisms first: HSMs, key vaults such as AWS KMS or Azure Key Vault, and secrets managers such as HashiCorp Vault. When those aren't available, its basic rules are: don't hard-code keys, don't commit them to version control, restrict permissions on config files that contain them, and avoid environment variables, which can leak through debug pages or `/proc/self/environ`.

**Separation.** "Where possible, encryption keys should be stored in a separate location from encrypted data." If the key sits in the same database as the ciphertext, one SQL injection or one stolen backup gives the attacker both halves.

## 4. Envelope encryption

*Main sources: OWASP, "Cryptographic Storage Cheat Sheet", section "Encrypting Stored Keys"; AWS KMS Developer Guide, "AWS KMS cryptography essentials", section "Envelope encryption".*

Separation creates a practical problem. You can't call a remote key service for every byte of every row, and you can't keep one master key in application memory forever. The answer is a two-level hierarchy.

OWASP names the levels. The **Data Encryption Key (DEK)** encrypts the data. The **Key Encryption Key (KEK)** encrypts the DEK. The encrypted DEK can sit right next to the data, because without the KEK it's useless. The KEK must be stored separately and be at least as strong as the DEK.

AWS defines the same idea: "Envelope encryption is the practice of encrypting plaintext data with a data key, and then encrypting the data key under another key." The top of the hierarchy is the **root key**, which in AWS is a KMS key. The guide lists the benefits:

- The encrypted data key can be stored alongside the encrypted data.
- To encrypt the same data under several keys, you only re-encrypt the small data key, not the data.
- You can combine algorithms: fast symmetric encryption for data, and a different scheme for the key layer.

Here is how the capstone's CPF encryption fits (Thursday, item 3):

1. On customer creation, ask the KMS (or Vault) for a new data key. You get it twice: once in plaintext, once encrypted under the master key.
2. Encrypt the CPF locally with the plaintext DEK using AES-256-GCM, with the customer ID as AAD.
3. Store the ciphertext, IV, tag, encrypted DEK and master key ID. Wipe the plaintext DEK from memory.
4. To read the CPF, send the encrypted DEK to the KMS, get the plaintext DEK back, decrypt locally.

```sql
CREATE TABLE customer_pii (
  customer_id     uuid PRIMARY KEY REFERENCES customers(id),
  cpf_ciphertext  bytea NOT NULL,
  cpf_iv          bytea NOT NULL,
  cpf_tag         bytea NOT NULL,
  dek_encrypted   bytea NOT NULL,  -- useless without the KEK
  kek_id          text  NOT NULL,  -- which master key (and version) wrapped the DEK
  created_at      timestamptz NOT NULL DEFAULT now()
);
```

A DEK per record costs one KMS call per write and per uncached read. In return, rotating the master key only re-wraps small DEKs, and destroying one record's DEK makes that record unreadable everywhere, including backups. Tuesday's LGPD section uses that property.

## 5. KMS, HSM and rotation in practice

*Main sources: AWS KMS Developer Guide, "AWS KMS cryptography essentials" and "Rotate AWS KMS keys"; HashiCorp Vault documentation, "Transit secrets engine".*

A **hardware security module (HSM)** is a tamper-resistant device that generates keys and uses them internally, so the key never appears in your server's memory. A **KMS** is a managed service in front of HSMs, with an API, access policies and audit logs.

The AWS guide states the core guarantee plainly: KMS keys "never leave the AWS KMS FIPS 140-3 Security Level 3 validated hardware security modules unencrypted." To use a key you must call KMS. Other facts from the guide worth noting:

- All symmetric encryption inside the HSMs uses AES-GCM with 256-bit keys.
- For every encryption under a KMS key, KMS derives a per-call key with a KDF in counter mode using HMAC with SHA-256.
- `GenerateDataKey` returns a data key in plaintext plus an encrypted copy, which is exactly what envelope encryption needs.

The rotation page adds the part you need for interviews. For symmetric KMS keys with KMS-generated material, automatic rotation is available, with a default period of 365 days. KMS keeps all previous key material, so old ciphertexts still decrypt: on decrypt, "AWS KMS automatically chooses the correct version." The key ID never changes, so applications need no change. Rotation does not re-encrypt your data or your data keys. Asymmetric keys and HMAC keys can't be rotated automatically. For those you rotate manually: create a new key and point your application or an alias at it.

That last point matters for webhook signing. A signing key is asymmetric, so "rotation" means a new key with a new ID, published alongside the old one for a while.

**Vault Transit, for the lab.** In the lab you'll run Vault in dev mode, whose Transit engine encrypts and decrypts data for you without exposing the key. The commands from the Vault docs:

```bash
vault secrets enable transit
vault write -f transit/keys/wallet-pii
vault write transit/encrypt/wallet-pii plaintext=$(echo "123.456.789-09" | base64)
# -> ciphertext: vault:v1:...
vault write -f transit/keys/wallet-pii/rotate
vault write transit/rewrap/wallet-pii ciphertext=vault:v1:...
# -> ciphertext: vault:v2:...
```

The `v1` in the ciphertext is the key version, the same "tag each ciphertext with its key ID" idea from OWASP. `rewrap` re-encrypts with the newest version without ever returning the plaintext to you. Vault also has a `min_decryption_version` setting: versions below it are archived, which is how you finally retire an old version once everything is rewrapped.

## 6. TLS and mutual TLS

*Main source: Cloudflare Learning, "What is mutual TLS (mTLS)?"*

So far we protected data at rest. In transit, the tool is TLS. Cloudflare describes TLS as a protocol that authenticates the server and encrypts traffic so outside parties can't read it. The server proves its identity with a certificate, which holds its public key, the issuing certificate authority (CA) and an expiry date, and it proves it owns the matching private key during the handshake.

In ordinary TLS only the server is authenticated. Your wallet's mobile app knows it's talking to your API, but your API learns nothing about the client from TLS itself. That's fine for the public web, where users authenticate with passwords and tokens.

**Mutual TLS** makes both sides present a certificate. The Cloudflare article lists the steps: the client connects, the server presents its certificate, the client verifies it, then the client presents its own certificate, the server verifies it, the server grants access, and encrypted traffic begins.

Where mTLS fits in a fintech:

- **Between your services.** In a zero trust network, the ledger service shouldn't accept a posting request just because it came from inside the VPC. With mTLS it accepts only callers holding a certificate issued for, say, the transfer service.
- **With partners.** Partner banks and payment schemes commonly require mTLS on their APIs, and the Pix ecosystem in Brazil uses client certificates too. Your client certificate's private key becomes one more key to store in a vault and rotate before it expires.

In mTLS, Cloudflare says, "The organization implementing mTLS acts as its own certificate authority." It issues a root certificate, and every authorized client and server certificate must chain to it. The article lists attacks this makes harder: on-path attacks, spoofing, credential stuffing, brute force, phishing and malicious API requests. On on-path attackers it is specific: they "cannot authenticate to either the client or the server."

Cloudflare explains that mTLS isn't used across the whole internet because managing a certificate on every end-user device is impractical. On Wednesday you'll see the OAuth security BCP also uses mTLS to bind tokens to a client.

## 7. Webhook signing keys: preview of Thursday

*Main sources: the sections above, applied to the capstone tasks. This section is the course's design, not a quote from any one reference.*

In Module 5 your webhook sender signed with HMAC-SHA256, an event ID and a timestamp, following the Standard Webhooks specification. That covered integrity and replay. It did not cover the key's lifecycle: one secret, no key ID, no plan to change it.

The capstone's mastery question is: where do the keys that sign your webhooks live, and how do you rotate them without breaking clients? Everything today points to one answer.

**Where they live.** The private signing key lives in Vault or KMS, never in the repo or an environment variable, following OWASP's storage rules. Ideally the signing operation happens inside the key service, so the private key never reaches your app.

**How clients verify.** Each webhook carries a header with the signature, a timestamp and a `kid` (key ID). Signing the timestamp together with the body lets the receiver reject old replays. The receiver fetches your public keys from a public endpoint, picks the one matching `kid`, and verifies.

```ts
import { sign, verify } from 'node:crypto';

// Ed25519: algorithm argument is null
const message = Buffer.from(`${timestamp}.${rawBody}`);
const signature = sign(null, message, privateKey);            // sender
const ok = verify(null, message, publicKeysByKid[kid], signature); // receiver
```

**How you rotate without failures.** Rotation is three phases, and the order matters:

| Phase | Published keys | Signing key | Why |
| --- | --- | --- | --- |
| 1. Publish | old + new | old | Clients that cache keys learn the new one before they ever see it |
| 2. Switch | old + new | new | In-flight and retried webhooks signed with old still verify |
| 3. Retire | new | new | Only after the overlap is longer than the client cache TTL plus your retry window |

If you switch the signing key before clients have the new public key, some verifications fail. If you remove the old key while retries signed with it are still queued, those fail too. The overlap is what makes "zero verification failures" possible.

With HMAC the same three phases apply, but each client must receive the new secret over a secure channel. That extra distribution step is the main reason to prefer asymmetric signatures for webhooks.

## Notes to write today

1. Hashing vs. encryption vs. HMAC (and signatures): what each answers, whether it uses a key, whether it's reversible, and one wallet example of each.
2. Key management basics: how keys are generated, where they're stored, why keys and data are separated, and the four reasons to rotate.
3. TLS vs. mTLS: who authenticates whom, and two places in the wallet where you'd use mTLS.
4. KMS vs. HSM, envelope encryption (DEK and KEK, drawn as a diagram for the CPF), and what automatic rotation does and does not do in AWS KMS.

## Check yourself

These make good flashcards (see the [flashcards guide](../../FLASHCARDS.md)).

- Why must a password never be stored with reversible encryption, and why can't a CPF be stored as a hash?
- What does an authenticated mode such as AES-GCM give you that CBC alone doesn't?
- In envelope encryption, what does the DEK encrypt, what does the KEK encrypt, and which one can be stored next to the data?
- When AWS KMS rotates a symmetric key automatically, does your old ciphertext need to be re-encrypted? Why not?
- What does mTLS add to ordinary TLS, and who acts as the certificate authority?
- Why does a webhook signing key rotation need an overlap period, and what decides how long it is?
- Why is an asymmetric signature a better fit than HMAC for a public verification-key endpoint?

## References

- **Main source:** OWASP Cheat Sheet Series, ["Cryptographic Storage Cheat Sheet"](https://cheatsheetseries.owasp.org/cheatsheets/Cryptographic_Storage_Cheat_Sheet.html). Read "Architectural Design", "Algorithms" (cipher modes and secure random), "Key Management" and "Key Storage" in full. Free.
- Cloudflare Learning, ["What is mutual TLS (mTLS)?"](https://www.cloudflare.com/learning/access-management/what-is-mutual-tls/). Read the whole page; it is short. Free.
- AWS KMS Developer Guide, ["AWS KMS cryptography essentials"](https://docs.aws.amazon.com/kms/latest/developerguide/kms-cryptography.html). Read "Envelope encryption", the HSM and key derivation parts, and skim the operations table. Free.
- AWS KMS Developer Guide, ["Rotate AWS KMS keys"](https://docs.aws.amazon.com/kms/latest/developerguide/rotate-keys.html). The source for the rotation facts in section 5. Free.
- HashiCorp Vault documentation, ["Transit secrets engine"](https://developer.hashicorp.com/vault/docs/secrets/transit). Keep it open during the lab for the encrypt, decrypt, rotate and rewrap commands. Free.
