# Module 9: Resilience, high availability and consensus

**Week 11** · [Back to the syllabus](../README.md) · [Leia em português](09-resilience-and-consensus.pt-BR.md)

## Goal

Keep the system degrading gracefully: timeouts, retries with jitter, circuit breakers, bulkheads, rate limiting, safe migrations, DR, and consensus at a high level.

## Monday to Wednesday: reading + lab (3 h a day)

| Day | Reading (2 h) | Lab (1 h) |
| --- | --- | --- |
| Mon | Release It! (Nygard), stability patterns: timeouts, circuit breaker, bulkhead.<br>Amazon Builders' Library, "Timeouts, retries, and backoff with jitter". Retry storms and retry budgets. | k6 + Toxiproxy: provider answering in 30 s; measure with no protection (p99, errors, connections). |
| Tue | Amazon Builders' Library, "Avoiding insurmountable queue backlogs". Load shedding and token-bucket rate limiting.<br>DDIA ch. 9, consensus; the Raft paper (section 5) with the visualization at raft.github.io. | Explicit timeouts and a circuit breaker (opossum) on the provider; measure again. |
| Wed | Multi-AZ and multi-region, active-passive vs. active-active and why active-active with balances is hard. RPO, RTO and disaster recovery.<br>Safe deploys: canary, feature flags and expand/contract migrations (Martin Fowler, "Parallel Change"). | Capstone prep: backup script and chosen migration scenario; task list. No TCM code. |

In labs, AI is allowed only to clarify concepts, never to write capstone code.

## Thursday and Friday: capstone (TCM), no AI

Everything is done WITHOUT AI. No ChatGPT, Claude, Copilot or AI autocomplete in the editor. Allowed: official docs, books, your own notes and previous labs. Whatever doesn't fit today becomes cut scope for the next checkpoint; the deadline does not move.

1. (45 min) Retry with jitter and a retry budget.
2. (45 min) Bulkhead: separate pools per provider.
3. (45 min) Token-bucket rate limit in Redis.
4. (1 h) Run k6 before and after and plot p99 and error rate.
5. (1 h) A real expand/contract migration: rename a column with no downtime.
6. (45 min) Backup and restore by script; docs/m09.md with RPO and RTO.

Thursday covers items 1 to 3; Friday covers the rest and ends with 30 minutes of delivery.

## Pass criteria

Before/after charts of p99 and error rate show controlled degradation, and the restore works from the script.

## Mastery test

Answer out loud, in under 2 minutes, without notes, and record it:

> The main provider started answering in 30 s instead of 300 ms. Describe what happens in your system with no protection and with each pattern on. Bonus: why is active-active with balances hard, and where does Raft come in?
