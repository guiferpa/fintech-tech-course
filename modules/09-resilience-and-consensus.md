# Module 9: Resilience, high availability and consensus

**Week 11** · [Back to the syllabus](../README.md) · [Leia em português](09-resilience-and-consensus.pt-BR.md)

## Goal

Keep the system degrading gracefully: timeouts, retries with jitter, circuit breakers, bulkheads, rate limiting, safe migrations, DR, and consensus at a high level.

## Monday to Wednesday: DSA + reading + lab (3 h 30 a day)

| Day | DSA (30 min) | Reading (2 h) | Lab (1 h) |
| --- | --- | --- | --- |
| Mon | [Find Median from Data Stream](https://leetcode.com/problems/find-median-from-data-stream/) (two heaps) | [Martin Fowler, "Circuit Breaker"](https://martinfowler.com/bliki/CircuitBreaker.html) (free): how a circuit breaker works and its states.<br>[Microsoft Azure Architecture Center, "Bulkhead pattern"](https://learn.microsoft.com/en-us/azure/architecture/patterns/bulkhead) (free): isolating resources so one slow dependency doesn't take everything down.<br>[Amazon Builders' Library, "Timeouts, retries, and backoff with jitter"](https://aws.amazon.com/builders-library/timeouts-retries-and-backoff-with-jitter/) (free): choosing timeouts, retry storms and retry budgets. | k6 + Toxiproxy: provider answering in 30 s; measure with no protection (p99, errors, connections). |
| Tue | [Task Scheduler](https://leetcode.com/problems/task-scheduler/) (greedy + max-heap) | [Amazon Builders' Library, "Avoiding insurmountable queue backlogs"](https://aws.amazon.com/builders-library/avoiding-insurmountable-queue-backlogs/) (free): backlogs, prioritization and dropping work.<br>[Amazon Builders' Library, "Using load shedding to avoid overload"](https://aws.amazon.com/builders-library/using-load-shedding-to-avoid-overload/) (free): load shedding and rate limiting.<br>[Martin Kleppmann, "Distributed Systems" lecture notes (University of Cambridge), chapter 6 (Consensus)](https://www.cl.cam.ac.uk/teaching/2122/ConcDisSys/dist-sys-notes.pdf) (free): why consensus is needed and how Raft elects a leader.<br>[Diego Ongaro and John Ousterhout, "In Search of an Understandable Consensus Algorithm" (the Raft paper), section 5](https://raft.github.io/raft.pdf) (free): leader election and log replication; use the visualization at raft.github.io alongside. | Explicit timeouts and a circuit breaker (opossum) on the provider; measure again. |
| Wed | Priority scheduler (design + code: heap ordered by (runAt, priority))<br>No LeetCode link: schedule(task, priority, runAt) and next(now), plus retry with exponential backoff for failed tasks. | [AWS whitepaper, "Disaster recovery options in the cloud"](https://docs.aws.amazon.com/whitepapers/latest/disaster-recovery-workloads-on-aws/disaster-recovery-options-in-the-cloud.html) (free): RPO, RTO, active-passive vs. active-active. Think about why active-active with balances is hard.<br>[Martin Fowler, "Parallel Change"](https://martinfowler.com/bliki/ParallelChange.html) (free): expand/contract migrations.<br>[Pete Hodgson, "Feature Toggles (aka Feature Flags)" (martinfowler.com)](https://martinfowler.com/articles/feature-toggles.html) (free): feature flags and canary releases. | Capstone prep: backup script and chosen migration scenario; task list. No TCM code. |

Solve without AI, 30-minute timebox. Method and full list: [DSA track](../DSA.md).

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
