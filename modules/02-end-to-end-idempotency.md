# Module 2: End-to-end idempotency

**Week 2** · [Back to the syllabus](../README.md) · [Leia em português](02-end-to-end-idempotency.pt-BR.md)

## Goal

Close idempotency end to end: API (Idempotency-Key), message consumers (processed messages) and third-party integrations (forwarding the key).

## Monday to Wednesday: reading + lab (3 h a day)

| Day | Reading (2 h) | Lab (1 h) |
| --- | --- | --- |
| Mon | Stripe, "Designing robust and predictable APIs with idempotency". Brandur Leach, "Implementing Stripe-like Idempotency Keys in Postgres", first half (atomic phases, recovery points). | Hands-on practice of what you read. |
| Tue | Brandur Leach, second half. Idempotent message consumers: at-least-once + processed-messages table keyed by message_id in the same transaction as the effect. | Hands-on practice of what you read. |
| Wed | Natural key vs. client key (Pix end_to_end_id), naturally idempotent operations (SET status ... WHERE status = 'PENDING') vs. non-idempotent ones (balance = balance - 100), forwarding the key to the provider. Draw API -> queue -> worker -> provider with every idempotency point. | Capstone prep: list the test cases (same key + same body, same key + different body, request still in flight, 50 concurrent) and create empty migrations. No TCM code. |

In labs, AI is allowed only to clarify concepts, never to write capstone code.

## Thursday and Friday: capstone (TCM), no AI

Everything is done WITHOUT AI. No ChatGPT, Claude, Copilot or AI autocomplete in the editor. Allowed: official docs, books, your own notes and previous labs. Whatever doesn't fit today becomes cut scope for the next checkpoint; the deadline does not move.

1. (45 min) idempotency_keys table (key, user, body hash, status, response code and body, locked_at) and migration.
2. (1 h 30) NestJS interceptor: insert key with ON CONFLICT; completed with same hash returns stored response; in flight returns 409; different hash returns 422.
3. (30 min) Forward the key as a header to the fake partner bank, which also dedupes.
4. (45 min) processed_messages table and a consumer that ignores repeated message_id in the same transaction as the effect.
5. (45 min) Test: 50 concurrent requests with the same key end in exactly 1 transfer.
6. (45 min) docs/m02.md with your decisions.

Thursday covers items 1 to 3; Friday covers the rest and ends with 30 minutes of delivery.

## Pass criteria

A test fires 50 concurrent requests with the same key and the database ends with exactly one transfer.

## Mastery test

Answer out loud, in under 2 minutes, without notes, and record it:

> In an API -> queue -> worker -> provider flow, where do you put idempotency, and why at each point?
