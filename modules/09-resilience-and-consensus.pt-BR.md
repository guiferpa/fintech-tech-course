# Módulo 9: Resiliência, alta disponibilidade e consenso

**Semana 11** · [Voltar para a ementa](../README.pt-BR.md) · [Read in English](09-resilience-and-consensus.md)

## Objetivo

Fazer o sistema degradar de forma controlada: timeouts, retry com jitter, circuit breaker, bulkhead, rate limiting, migrações seguras, DR e consenso em alto nível.

## Segunda a quarta: DSA + leitura + laboratório (3 h 30 por dia)

| Dia | DSA (30 min) | Leitura (2 h) | Laboratório (1 h) |
| --- | --- | --- | --- |
| Seg | [Find Median from Data Stream](https://leetcode.com/problems/find-median-from-data-stream/) (dois heaps) | Release It! (Nygard), padrões de estabilidade: timeouts, circuit breaker, bulkhead.<br>Amazon Builders' Library, "Timeouts, retries, and backoff with jitter". Retry storms e orçamento de retry. | k6 + Toxiproxy: cenário com provedor respondendo em 30 s; medir sem proteção (p99, erros, conexões). |
| Ter | [Task Scheduler](https://leetcode.com/problems/task-scheduler/) (guloso + max-heap) | Amazon Builders' Library, "Avoiding insurmountable queue backlogs". Load shedding e rate limiting por token bucket.<br>DDIA cap. 9, consenso; artigo do Raft (seção 5) com a visualização de raft.github.io. | Timeouts explícitos e circuit breaker (opossum) no provedor; medir de novo. |
| Qua | Priority scheduler (design + código: heap ordenado por (runAt, prioridade))<br>Sem link do LeetCode: schedule(task, priority, runAt) e next(now), mais retry com backoff exponencial para tarefas que falham. | Multi-AZ e multi-região, ativo-passivo x ativo-ativo e por que ativo-ativo com saldo é difícil. RPO, RTO e disaster recovery.<br>Deploy seguro: canary, feature flags e migração expand/contract (Martin Fowler, "Parallel Change"). | Preparação do dia de conclusão: script de backup e cenário de migração escolhido; lista de tarefas. Sem código do TCM. |

Resolva sem IA, com limite de 30 minutos. Método e lista completa: [trilha de DSA](../DSA.pt-BR.md).

Nos laboratórios, IA só para tirar dúvida de conceito, nunca para escrever código do TCM.

## Quinta e sexta: trabalho de conclusão (TCM), sem IA

Tudo feito SEM IA. Nada de ChatGPT, Claude, Copilot ou autocomplete com IA no editor. Vale: documentação oficial, livros, suas anotações e os laboratórios das semanas anteriores. O que não couber hoje vira escopo cortado para o próximo checkpoint; o deadline não muda.

1. (45 min) Retry com jitter e orçamento de retry.
2. (45 min) Bulkhead: pools separados por provedor.
3. (45 min) Rate limit por token bucket no Redis.
4. (1 h) Rodar k6 antes e depois e gerar os gráficos de p99 e taxa de erro.
5. (1 h) Migração expand/contract real: renomear uma coluna sem downtime.
6. (45 min) Backup e restore por script; docs/m09.md com RPO e RTO.

A quinta cobre os itens 1 a 3; a sexta cobre o resto e termina com 30 minutos de entrega.

## Critério de aprovação

Os gráficos de p99 e taxa de erro antes e depois mostram degradação controlada, e o restore funciona a partir do script.

## Teste de domínio

Responda em voz alta, em até 2 minutos, sem consultar, e grave:

> O provedor principal começou a responder em 30 s em vez de 300 ms. Descreva o que acontece no seu sistema sem proteção e com cada padrão ligado. Extra: por que ativo-ativo com saldo é difícil, e onde o Raft entra?
