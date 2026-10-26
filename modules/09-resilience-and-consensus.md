# Module 9: Resilience, high availability and consensus

**Week 11** · [Back to the syllabus](../README.md) · [Leia em português](09-resilience-and-consensus.pt-BR.md)

## Goal

Keep the system degrading gracefully: timeouts, retries with jitter, circuit breakers, bulkheads, rate limiting, safe migrations, DR, and consensus at a high level.

## Monday to Wednesday: DSA + reading + lab (3 h 30 a day)

| Day | DSA (30 min) | Reading (2 h) | Lab (1 h) |
| --- | --- | --- | --- |
| Mon | [Find Median from Data Stream](https://leetcode.com/problems/find-median-from-data-stream/) (two heaps) | [Course text: Timeouts, retries, circuit breakers and bulkheads](../lessons/09-resilience-and-consensus/day-1.md) (written for this course): read this first. It explains the day's concepts and says which sections of the references below to read next.<br>[Martin Fowler, "Circuit Breaker"](https://martinfowler.com/bliki/CircuitBreaker.html) (free): how a circuit breaker works and its states.<br>[Microsoft Azure Architecture Center, "Bulkhead pattern"](https://learn.microsoft.com/en-us/azure/architecture/patterns/bulkhead) (free): isolating resources so one slow dependency doesn't take everything down.<br>[Amazon Builders' Library, "Timeouts, retries, and backoff with jitter"](https://aws.amazon.com/builders-library/timeouts-retries-and-backoff-with-jitter/) (free): choosing timeouts, retry storms and retry budgets. | k6 + Toxiproxy: provider answering in 30 s; measure with no protection (p99, errors, connections). |
| Tue | [Task Scheduler](https://leetcode.com/problems/task-scheduler/) (greedy + max-heap) | [Course text: Overload, backlogs and consensus](../lessons/09-resilience-and-consensus/day-2.md) (written for this course): read this first. It explains the day's concepts and says which sections of the references below to read next.<br>[Amazon Builders' Library, "Avoiding insurmountable queue backlogs"](https://aws.amazon.com/builders-library/avoiding-insurmountable-queue-backlogs/) (free): backlogs, prioritization and dropping work.<br>[Amazon Builders' Library, "Using load shedding to avoid overload"](https://aws.amazon.com/builders-library/using-load-shedding-to-avoid-overload/) (free): load shedding and rate limiting.<br>[Amazon Builders' Library, "Leader election in distributed systems"](https://aws.amazon.com/builders-library/leader-election-in-distributed-systems/) (free): why systems use a leader, how Amazon elects one with leases, and the stale-leader problem (GC pauses, checking the lease before side effects).<br>[etcd documentation, "FAQ"](https://etcd.io/docs/v3.6/faq/) (free): quorum and failure tolerance per cluster size, why odd member counts, why at most seven members, and how quorum avoids split brain.<br>[etcd documentation, "Failure modes"](https://etcd.io/docs/v3.6/op-guide/failures/) (free): what happens on leader failure, majority failure and network partition: election time, queued writes, and why committed writes are never lost.<br>[etcd documentation, "Tuning"](https://etcd.io/docs/v3.6/tuning/) (free): heartbeat interval and election timeout: defaults (100 ms, 1000 ms) and how to size them from round-trip time.<br>[HashiCorp Consul documentation, "Consensus"](https://developer.hashicorp.com/consul/docs/concept/consensus) (free): a one-page Raft overview from a product that runs it: follower, candidate, leader, when an entry is committed, and the deployment table.<br>[Cockroach Labs documentation, "Replication Layer"](https://docs.cockroachlabs.com/docs/stable/architecture/replication-layer) (free): the Raft section: Raft groups, heartbeats, randomized election timeouts, fault tolerance by replication factor, and snapshots.<br>[Patroni documentation, "Introduction"](https://patroni.readthedocs.io/en/latest/) (free): optional: which consensus stores (etcd, Consul, ZooKeeper, Kubernetes) a real Postgres failover tool relies on.<br>[The Raft Consensus Algorithm, "Raft" site with visualization (links to The Secret Lives of Data walkthrough)](https://raft.github.io/) (free): watch an election and log replication in the interactive visualization; then follow the guided walkthrough at thesecretlivesofdata.com/raft. | Explicit timeouts and a circuit breaker (opossum) on the provider; measure again. |
| Wed | Priority scheduler (design + code: heap ordered by (runAt, priority))<br>No LeetCode link: schedule(task, priority, runAt) and next(now), plus retry with exponential backoff for failed tasks. | [Course text: Disaster recovery, safe migrations and feature flags](../lessons/09-resilience-and-consensus/day-3.md) (written for this course): read this first. It explains the day's concepts and says which sections of the references below to read next.<br>[AWS whitepaper, "Disaster recovery options in the cloud"](https://docs.aws.amazon.com/whitepapers/latest/disaster-recovery-workloads-on-aws/disaster-recovery-options-in-the-cloud.html) (free): RPO, RTO, active-passive vs. active-active. Think about why active-active with balances is hard.<br>[Martin Fowler, "Parallel Change"](https://martinfowler.com/bliki/ParallelChange.html) (free): expand/contract migrations.<br>[Pete Hodgson, "Feature Toggles (aka Feature Flags)" (martinfowler.com)](https://martinfowler.com/articles/feature-toggles.html) (free): feature flags and canary releases. | Capstone prep: backup script and chosen migration scenario; task list. No TCM code. |

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
