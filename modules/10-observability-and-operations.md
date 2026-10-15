# Module 10: Observability and operations

**Week 12** · [Back to the syllabus](../README.md) · [Leia em português](10-observability-and-operations.pt-BR.md)

## Goal

Know the system is wrong before a customer does: traces across async boundaries, business metrics, SLOs with burn-rate alerts, runbooks and postmortems.

## Monday to Wednesday: DSA + reading + lab (3 h 30 a day)

| Day | DSA (30 min) | Reading (2 h) | Lab (1 h) |
| --- | --- | --- | --- |
| Mon | [Longest Increasing Subsequence](https://leetcode.com/problems/longest-increasing-subsequence/) (O(n²) DP, then patience sorting in O(n log n)) | Site Reliability Engineering, ch. 6: monitoring, symptoms vs. causes, the four golden signals.<br>Site Reliability Engineering, ch. 4 (SLOs) and SRE Workbook, "Alerting on SLOs" (burn rate). | OpenTelemetry SDK in NestJS + Jaeger in Compose; trace one HTTP request. |
| Tue | [Serialize and Deserialize Binary Tree](https://leetcode.com/problems/serialize-and-deserialize-binary-tree/) (preorder DFS with null markers) | OpenTelemetry: traces, spans and context propagation, including through messaging.<br>Business metrics as the main signal; cardinality and cost. | Prometheus + Grafana in Compose; basic technical metrics. |
| Wed | [Word Break](https://leetcode.com/problems/word-break/) (DP, then trie to speed up prefix checks) | Site Reliability Engineering, ch. 15 (blameless postmortems); how to write a runbook.<br>On paper: the double-charge detector (query, window, threshold) and the incident you'll inject. | Capstone prep: Alertmanager in Compose and task list. No TCM code. |

Solve without AI, 30-minute timebox. Method and full list: [DSA track](../DSA.md).

In labs, AI is allowed only to clarify concepts, never to write capstone code.

## Thursday and Friday: capstone (TCM), no AI

Everything is done WITHOUT AI. No ChatGPT, Claude, Copilot or AI autocomplete in the editor. Allowed: official docs, books, your own notes and previous labs. Whatever doesn't fit today becomes cut scope for the next checkpoint; the deadline does not move.

1. (1 h) Propagate the trace through Kafka (headers) to the worker; correlation id in logs.
2. (1 h) Business metrics: approval rate per provider, old PENDING payments, reconciliation discrepancies.
3. (45 min) An SLO with a burn-rate alert.
4. (45 min) Double-charge detector with an alert.
5. (30 min) Inject a double charge and confirm the alert fires.
6. (1 h) Runbook and postmortem; docs/m10.md.

Thursday covers items 1 to 3; Friday covers the rest and ends with 30 minutes of delivery.

## Pass criteria

An injected double charge fires the alert with nobody watching the dashboard.

## Mastery test

Answer out loud, in under 2 minutes, without notes, and record it:

> Without any customer complaining, how would you know that 2% of payments are being charged twice?
