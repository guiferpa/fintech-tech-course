# Module 7, Monday: the card payment lifecycle and double payments

[Module 7](../../modules/07-payments-pix-reconciliation.md) · [Leia em português](day-1.pt-BR.md)

**Reading time:** about 45 minutes. Use the rest of the 2-hour block on the references at the end, starting with the sections marked as the main source.

This is an original text written for this course. It is based on the references listed at the end, and each section names the source it follows. Where an idea comes from a specific author, the text says so.

## Why this matters for a fintech

Until now, the wallet moved money between its own accounts. This week it starts talking to the outside world: card acquirers, Pix and bank settlement files. Outside money has two properties that internal money doesn't. It moves in several steps spread over days, and the other side keeps its own records, which may disagree with yours.

Today covers the first property. You will learn who the actors in a card payment are, what authorization, capture and settlement mean, how Stripe models a payment as a state machine, and how Airbnb stopped charging guests twice. Tonight's lab builds two fake acquirers that you will reconcile against on Thursday.

## 1. Who is involved in a card payment

*Main source: Stripe, "How card payment processing and settlement works", section "Who is involved in the authorization and settlement process?".*

A card payment that looks like one tap to the customer crosses at least five parties. The Stripe article lists them like this:

| Actor | Role | Wallet example |
| --- | --- | --- |
| Cardholder | The person paying; the money comes from their account | A wallet user topping up with a credit card |
| Business (merchant) | The seller; settled funds end up in its bank account | Your wallet company |
| Acquirer | Processes card payments for the business and routes them through the card network to the issuer | The acquirer your wallet signed a contract with |
| Payment processor | Passes transaction details between business, network and issuer | Often the same company as the acquirer |
| Card network | Runs the card rails and routes authorization requests | Visa, Mastercard |
| Issuer | Gives the card and the credit line; approves or declines | The cardholder's bank |

Stripe notes that processors and acquirers were historically separate companies but can be combined, as Stripe itself does. The brief for this module also mentions the **gateway**: the software layer that receives card data from your checkout and sends it to the processor. The Stripe article doesn't define it as a separate actor, so treat "gateway" as a role that many providers bundle with processing.

Two consequences matter for your design. First, your wallet only talks to the acquirer (or the processor in front of it). You never call the issuer or the network directly. Second, every party in the chain keeps its own record of the same payment. That is why reconciliation exists, and why Wednesday is about it.

## 2. Authorization, capture and settlement

*Main source: Stripe, "How card payment processing and settlement works", sections "How does card authorization work?" and "What is capturing and settlement?".*

A card payment happens in three stages, and money only moves in the last one.

**Authorization.** The customer submits the card. The processor sends an approval request through the card network to the issuer. The issuer checks that the card is valid, that details such as the billing address match, and that there is enough balance or credit. The article says the issuer answers with a two-digit code, and the approval usually comes back within a few seconds. Then comes the key point: "If the transaction is approved, the issuer will immediately reduce the balance or available credit". No money has moved yet. The issuer has only reserved it.

**Capture.** The acquirer acts on the authorization and asks for the funds. The business can choose when to capture, because an authorization stays valid for a while. The article says authorizations usually last 5 to 10 days, and sometimes up to 30 days. A hotel or a car rental authorizes at check-in and captures at check-out, possibly for a different amount.

**Settlement.** In Stripe's words, "Settlement is when the funds themselves are moved from the issuing account to the merchant account." The acquirer holds the funds and then pays the business's bank account, which the article says usually takes a few days.

Map those stages onto the ledger from Module 6, because the capstone asks you to do exactly that on Thursday:

| Card stage | What it means | Wallet ledger effect |
| --- | --- | --- |
| Authorization approved | Issuer reserved the money | Create a **hold**; available balance goes down, nothing posted |
| Capture | Merchant claimed the money | Post the **entry**; release or consume the hold |
| Authorization expired or voided | Reservation dropped | Release the hold; no entry |
| Settlement | Money arrived at your bank | Match the settlement line to the entry; move it from "receivable from acquirer" to "cash at bank" |
| Refund | Money goes back | Post a **reverse entry**, never edit the original |

The last row is the rule you'll keep using: the ledger is append-only, so a refund is a new entry that points to the original one.

## 3. A payment as a state machine

*Main source: Stripe documentation, "The Payment Intents API", plus its linked page "How Payment Intents and Setup Intents work".*

Stripe models each attempt to collect money as a **PaymentIntent**, an object whose `status` moves through a fixed set of states. The docs say that each PaymentIntent "typically correlates with a single shopping cart or customer session" in your application. The lifecycle page lists these statuses:

| Status | Meaning (summarized from the Stripe docs) |
| --- | --- |
| `requires_payment_method` | Created, no payment method attached yet. A failed attempt, such as a decline, returns here so the customer can retry. |
| `requires_confirmation` | Payment details are present and ready to confirm. Most integrations skip it. |
| `requires_action` | Extra customer action needed, such as 3D Secure authentication. |
| `processing` | Waiting on an asynchronous method, such as a bank debit, which can take days. |
| `requires_capture` | Authorized but not captured, when you authorize and capture separately. |
| `succeeded` | The flow is complete; the docs say you can fulfill the order. |
| `canceled` | Invalidated; held funds are released. Not reversible. |

Three design ideas from these pages are worth copying into your own wallet.

**The object outlives the attempts.** A PaymentIntent can have more than one Charge, because retries create new attempts. The intent tracks the customer's goal (pay for this cart). The charges track each try. In your schema, that means a `payments` table and a separate `payment_attempts` table, which becomes important on Wednesday when one payment may be tried on two providers.

**Reuse instead of recreate.** Stripe recommends creating the intent as soon as the amount is known, and reusing it if the checkout is interrupted and resumes. The docs also tell you to send an idempotency key, "typically based on the ID that you associate with the cart or customer session". A deterministic key derived from the cart is what stops a double click from creating two payments.

**Not every state can reach every other.** You can cancel before `processing` or `succeeded`, but not after (with exceptions for some bank debit methods). A failed attempt goes back to `requires_payment_method`, never to `succeeded`. These rules are a transition table, and tomorrow's lab is to write one.

Finally, the docs recommend that after the client confirms, your server monitors webhooks to learn whether the payment completed or failed. The provider pushes the final state; you don't assume it from your own call returning.

## 4. The double payment problem at Airbnb

*Main source: Airbnb Engineering, "Avoiding Double Payments in a Distributed Payments System", sections "The problem statement" and "Solution explained".*

Airbnb's payments team moved from a monolith to services and had to keep its money movement correct while each request now crossed many network calls. The post is direct about the priority: "Guaranteeing eventual consistency for our payments system is of the utmost importance." They also needed very low latency, which is why they did not build a separate idempotency service. Instead they built a library, called **Orpheus**, that each payment service embeds.

Orpheus splits every request into three phases:

1. **Pre-RPC.** Write the details of the payment request to the database.
2. **RPC.** Call the external service (an acquirer, say) and receive the answer. This phase may also query the status of an earlier attempt.
3. **Post-RPC.** Save the result to the database: success or failure, and whether a failure can be retried.

Two rules hold the design together. The post states them as "No service interaction over networks in Pre and Post-RPC phases" and "No database interactions in the RPC phases." Each database phase is a single short transaction. This means you never hold a Postgres transaction open while waiting for a slow acquirer, and you never call an acquirer from inside a transaction that might roll back after the money already moved.

Here is the same shape in a NestJS service. The `db` and `acquirer` objects are placeholders for your own repository and HTTP client.

```typescript
async capture(paymentId: string, idemKey: string) {
  // Pre-RPC: one short transaction, no network calls
  const attempt = await this.db.transaction(async (tx) => {
    return tx.attempts.claim(paymentId, idemKey); // row lock + lease
  });
  if (attempt.state === 'COMPLETED') return attempt.response; // replay

  // RPC: network only, no database
  let result: AcquirerResult;
  try {
    result = await this.acquirer.capture(attempt.acquirerRef, { idemKey });
  } catch (err) {
    result = classify(err); // RETRYABLE, NON_RETRYABLE or UNKNOWN
  }

  // Post-RPC: one short transaction, no network calls
  return this.db.transaction(async (tx) => tx.attempts.finish(attempt.id, result));
}
```

## 5. Retries, leases and recorded responses

*Main source: Airbnb Engineering, "Avoiding Double Payments in a Distributed Payments System", sections "Handling exceptions", "Clients play a vital role", "How to choose an idempotency key?", "Each API request has an expiring lease", "Recording the response" and "Avoid replica databases".*

The rest of the post is a list of rules that turn the three phases into a safe system. Each one answers a specific way to charge twice.

**Classify every error.** Orpheus requires each error to be marked **retryable** or **non-retryable**. Retryable errors are infrastructure or network failures, generally 5XX statuses, expected to be transient. Non-retryable errors are validation failures or invalid states (the post's example is refunding a refund), generally 4XX statuses. The post warns that mistakes in both directions hurt. A retryable error marked non-retryable leaves the payment stuck. A non-retryable error marked retryable can cause a double payment.

There is a third case the post handles without naming: the call timed out and you don't know what happened. Module 1 called this the **unknown** outcome. It is neither of the two classes. You can't retry blindly, and you can't mark it failed. You resolve it by asking the provider for the status, which is exactly what the RPC phase is allowed to do.

**The client keeps the same key.** Clients must generate a unique key per new request, reuse it on every retry, store it before calling, and never change the payload between retries. They should retry with backoff and jitter. The post distinguishes **request-level** keys, such as a random UUID per request, from **entity-level** keys, which are deterministic and tied to a business entity, such as "the refund of payment 123". Entity-level keys are what you want for operations that must happen at most once per entity.

**One request at a time, with a lease.** Each request takes a row-level lock on its idempotency key before going on. The lock works as a lease that expires. If a server dies mid-request, a retry may proceed only after the lease runs out, and the post suggests making the lease longer than the RPC timeout. Otherwise a retry could start while the first call is still in flight at the acquirer.

**Record the response.** Once a request reaches a deterministic end state, Orpheus stores the response. A retry then gets the original answer without calling the acquirer again. The cost is a table that grows with throughput, so plan a retention policy.

**Read from the primary, not a replica.** Idempotency data is always read from and written to the primary (the post says master) database. A replica could lag, miss a recorded success, and let a retry charge again. The post frames it as a trade-off: "In a system of distributed databases, there is a tradeoff between consistency and latency." For idempotency data, they chose consistency.

The post claims Orpheus helped them achieve five nines in consistency for payments, and admits that eventual consistency "does not come without introducing some complexity."

A minimal Postgres table that supports these rules, building on your Module 2 `idempotency_keys` table:

```sql
CREATE TABLE payment_attempts (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  payment_id    uuid NOT NULL REFERENCES payments(id),
  provider      text NOT NULL,
  idem_key      text NOT NULL,
  state         text NOT NULL CHECK (state IN
                  ('PENDING','COMPLETED','FAILED_RETRYABLE','FAILED_FINAL','UNKNOWN')),
  lease_until   timestamptz,
  provider_ref  text,
  response      jsonb,
  UNIQUE (provider, idem_key)
);
```

The unique constraint is the last line of defense. Even if two workers race, only one row per provider and key can exist.

## 6. Preparing tonight's lab: two fake acquirers

*Main source: the module page's Monday lab, applying sections 2 to 5.*

The lab asks for two fake acquirers that authorize, capture and produce a daily settlement CSV. Keep them simple, but make them honest about the behaviors you'll need to test later:

- **Authorize** returns an `acquirer_ref` and an approval or decline. Make it accept an idempotency key and return the same answer for the same key.
- **Capture** takes the `acquirer_ref` and an amount up to the authorized amount.
- **Get status** by `acquirer_ref` or by your idempotency key. Wednesday's safe fallback depends on this call existing.
- **Failure injection.** Let a flag make a call time out after the acquirer has already recorded it. This is the case that produces double payments, so you need to be able to reproduce it on purpose.
- **Settlement CSV.** Once per simulated day, write one line per captured or refunded item.

A reasonable CSV layout, with amounts in integer cents to avoid floating point errors:

```text
settlement_date,acquirer_ref,payment_id,type,gross_cents,fee_cents,net_cents,currency
2026-10-19,acq_a_0001,pay_7f3c,CAPTURE,10000,250,9750,BRL
2026-10-19,acq_a_0002,pay_91de,REFUND,-3000,0,-3000,BRL
```

Make the two acquirers differ slightly (different fees, different column order or date format). Real providers never agree on a format, and Thursday's reconciliation job should normalize each file before matching.

## Notes to write today

1. The actors in a card payment (cardholder, merchant, acquirer, processor or gateway, card network, issuer) and the difference between authorization, capture and settlement. Add which ledger effect each stage causes in your wallet.
2. Your own payment state machine, inspired by the PaymentIntent statuses: list the states and, for each, the states it may move to. Include `UNKNOWN` for a timed-out call.
3. The Orpheus rules for avoiding double payments: the three phases, the two "no" rules, retryable vs. non-retryable errors, leases, recorded responses and reading from the primary. For each rule, write the double payment it prevents.

## Check yourself

These make good flashcards (see the [flashcards guide](../../FLASHCARDS.md)).

- After a card authorization is approved, has any money moved? What has the issuer done?
- Why might a business capture days after authorizing, and for a different amount?
- Why should one payment have several attempts in your data model?
- What are Orpheus's three phases, and which kind of work is forbidden in each?
- What goes wrong if a non-retryable error is labeled retryable? And the reverse?
- Why must the lease on an idempotency key be longer than the RPC timeout?
- Why does Airbnb read idempotency data from the primary and never from a replica?

## References

- **Main source:** Stripe, ["How card payment processing and settlement works"](https://stripe.com/resources/more/credit-card-payment-authorization-and-transaction-settlement-process). Read all of it, especially the actors and the authorization steps. Free.
- **Main source:** Stripe documentation, ["The Payment Intents API"](https://docs.stripe.com/payments/payment-intents), together with ["How Payment Intents and Setup Intents work"](https://docs.stripe.com/payments/paymentintents/lifecycle) for the status table. Skip the client-side code samples. Free.
- **Main source:** Airbnb Engineering, ["Avoiding Double Payments in a Distributed Payments System"](https://medium.com/airbnb-engineering/avoiding-double-payments-in-a-distributed-payments-system-2981f6b070bb). Read it end to end; it is the most important reading of the day. Free.
