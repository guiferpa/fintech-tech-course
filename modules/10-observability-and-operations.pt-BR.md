# Módulo 10: Observabilidade e operação

**Semana 12** · [Voltar para a ementa](../README.pt-BR.md) · [Read in English](10-observability-and-operations.md)

## Objetivo

Saber que o sistema está errado antes do cliente: traces atravessando filas, métricas de negócio, SLO com alerta de burn rate, runbooks e postmortems.

## Segunda a quarta: leitura + laboratório (3 h por dia)

| Dia | Leitura (2 h) | Laboratório (1 h) |
| --- | --- | --- |
| Seg | Site Reliability Engineering, cap. 6: monitoramento, sintoma x causa, four golden signals.<br>Site Reliability Engineering, cap. 4 (SLOs) e SRE Workbook, "Alerting on SLOs" (burn rate). | SDK do OpenTelemetry no NestJS + Jaeger no Compose; trace de uma requisição HTTP. |
| Ter | OpenTelemetry: traces, spans e propagação de contexto, inclusive em mensageria.<br>Métricas de negócio como sinal principal; cardinalidade e custo. | Prometheus + Grafana no Compose; métricas técnicas básicas. |
| Qua | Site Reliability Engineering, cap. 15 (postmortem sem culpa); como escrever um runbook.<br>No papel: detector de cobrança duplicada (consulta, janela, limiar) e o incidente que você vai injetar. | Preparação do dia de conclusão: Alertmanager no Compose e lista de tarefas. Sem código do TCM. |

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
