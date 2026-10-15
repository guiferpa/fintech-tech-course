# Módulo 10: Observabilidade e operação

**Semana 12** · [Voltar para a ementa](../README.pt-BR.md) · [Read in English](10-observability-and-operations.md)

## Objetivo

Saber que o sistema está errado antes do cliente: traces atravessando filas, métricas de negócio, SLO com alerta de burn rate, runbooks e postmortems.

## Segunda a quarta: DSA + leitura + laboratório (3 h 30 por dia)

| Dia | DSA (30 min) | Leitura (2 h) | Laboratório (1 h) |
| --- | --- | --- | --- |
| Seg | [Longest Increasing Subsequence](https://leetcode.com/problems/longest-increasing-subsequence/) (DP O(n²), depois patience sorting em O(n log n)) | [Google, "Site Reliability Engineering", capítulo 6 "Monitoring Distributed Systems"](https://sre.google/sre-book/monitoring-distributed-systems/) (gratuito): sintomas x causas e os quatro sinais de ouro.<br>[Google, "Site Reliability Engineering", capítulo 4 "Service Level Objectives"](https://sre.google/sre-book/service-level-objectives/) (gratuito): SLIs, SLOs e error budget.<br>[Google, "The Site Reliability Workbook", "Alerting on SLOs"](https://sre.google/workbook/alerting-on-slos/) (gratuito): alertas por burn rate. | SDK do OpenTelemetry no NestJS + Jaeger no Compose; trace de uma requisição HTTP. |
| Ter | [Serialize and Deserialize Binary Tree](https://leetcode.com/problems/serialize-and-deserialize-binary-tree/) (DFS em pré-ordem com marcadores de nulo) | [Documentação do OpenTelemetry, "Traces"](https://opentelemetry.io/docs/concepts/signals/traces/) (gratuito): traces e spans.<br>[Documentação do OpenTelemetry, "Context propagation"](https://opentelemetry.io/docs/concepts/context-propagation/) (gratuito): propagação de contexto, inclusive por mensageria.<br>[Documentação do Prometheus, boas práticas de "Instrumentation"](https://prometheus.io/docs/practices/instrumentation/) (gratuito): métricas de negócio como sinal principal, labels e custo de cardinalidade. | Prometheus + Grafana no Compose; métricas técnicas básicas. |
| Qua | [Word Break](https://leetcode.com/problems/word-break/) (DP, depois trie para acelerar os prefixos) | [Google, "Site Reliability Engineering", capítulo 15 "Postmortem Culture: Learning from Failure"](https://sre.google/sre-book/postmortem-culture/) (gratuito): postmortems sem culpados.<br>[Documentação de Incident Response da PagerDuty](https://response.pagerduty.com/) (gratuito): papéis num incidente e como escrever um runbook.<br>No papel: o detector de cobrança dupla (query, janela, limiar) e o incidente que você vai injetar. | Preparação do dia de conclusão: Alertmanager no Compose e lista de tarefas. Sem código do TCM. |

Resolva sem IA, com limite de 30 minutos. Método e lista completa: [trilha de DSA](../DSA.pt-BR.md).

Nos laboratórios, IA só para tirar dúvida de conceito, nunca para escrever código do TCM.

## Quinta e sexta: trabalho de conclusão (TCM), sem IA

Tudo feito SEM IA. Nada de ChatGPT, Claude, Copilot ou autocomplete com IA no editor. Vale: documentação oficial, livros, suas anotações e os laboratórios das semanas anteriores. O que não couber hoje vira escopo cortado para o próximo checkpoint; o deadline não muda.

1. (1 h) Propagar o trace pelo Kafka (headers) até o worker; correlation id nos logs.
2. (1 h) Métricas de negócio: aprovação por provedor, PENDING antigos, divergência de reconciliação.
3. (45 min) SLO com alerta de burn rate.
4. (45 min) Detector de cobrança duplicada com alerta.
5. (30 min) Injetar uma cobrança duplicada e confirmar o alerta.
6. (1 h) Runbook e postmortem; docs/m10.md.

A quinta cobre os itens 1 a 3; a sexta cobre o resto e termina com 30 minutos de entrega.

## Critério de aprovação

Uma cobrança duplicada injetada dispara o alerta sem ninguém olhando o dashboard.

## Teste de domínio

Responda em voz alta, em até 2 minutos, sem consultar, e grave:

> Como você saberia, sem nenhum cliente reclamar, que 2% dos pagamentos estão sendo cobrados duas vezes?
