# Módulo 5: Mensageria e eventos

**Semana 6** · [Voltar para a ementa](../README.pt-BR.md) · [Read in English](05-messaging-and-events.md)

## Objetivo

Passar eventos por um log com segurança: chave de partição, offsets, retries, DLQ, ordem e webhooks assinados.

## Segunda a quarta: DSA + leitura + laboratório (3 h 30 por dia)

| Dia | DSA (30 min) | Leitura (2 h) | Laboratório (1 h) |
| --- | --- | --- | --- |
| Seg | [Course Schedule](https://leetcode.com/problems/course-schedule/) (detecção de ciclo em grafo dirigido (DFS com 3 cores))<br>Mesma ideia da detecção de deadlock num wait-for graph. | DDIA cap. 11, primeira parte: filas x logs, brokers, offsets, consumidores.<br>Kafka: The Definitive Guide, capítulo de producers: acks, producer idempotente, chave de partição e ordenação por chave. | Redpanda no Compose; criar tópicos com partições; produzir e consumir com kcat. |
| Ter | [Course Schedule II](https://leetcode.com/problems/course-schedule-ii/) (ordenação topológica (Kahn)) | Kafka: The Definitive Guide, capítulo de consumers: consumer groups, rebalance, commit de offset antes ou depois de processar.<br>Kafka: The Definitive Guide, capítulo de entrega confiável; documentação da Confluent sobre transações e exactly-once. | Trocar o publicador do outbox para publicar no Redpanda com chave account_id; consumidor simples. |
| Qua | [Accounts Merge](https://leetcode.com/problems/accounts-merge/) (union-find) | Retries, DLQ, mensagem venenosa e backpressure. Artigo da Uber, "Building Reliable Reprocessing and Dead Letter Queues with Apache Kafka".<br>Event sourcing e CQRS (DDIA cap. 11, "Event Sourcing"; microservices.io). Webhooks: especificação Standard Webhooks (HMAC, id, timestamp). | Preparação do dia de conclusão: scripts de chaos esboçados (matar consumidor, mensagem venenosa, fora de ordem) e lista de tarefas. Sem código do TCM. |

Resolva sem IA, com limite de 30 minutos. Método e lista completa: [trilha de DSA](../DSA.pt-BR.md).

Nos laboratórios, IA só para tirar dúvida de conceito, nunca para escrever código do TCM.

## Quinta e sexta: trabalho de conclusão (TCM), sem IA

Tudo feito SEM IA. Nada de ChatGPT, Claude, Copilot ou autocomplete com IA no editor. Vale: documentação oficial, livros, suas anotações e os laboratórios das semanas anteriores. O que não couber hoje vira escopo cortado para o próximo checkpoint; o deadline não muda.

1. (1 h) Consumidor com inbox (processed_messages), commit de offset só depois de gravar.
2. (1 h) Tópico de retry com backoff, DLQ após N tentativas e comando para reprocessar a DLQ.
3. (30 min) Versão no evento; consumidor ignora versão menor ou igual à atual.
4. (1 h) Emissor de webhook: HMAC-SHA256, event_id, timestamp e reenvio com backoff.
5. (1 h) Rodar os 3 cenários de chaos e registrar resultados.
6. (30 min) docs/m05.md.

A quinta cobre os itens 1 a 3; a sexta cobre o resto e termina com 30 minutos de entrega.

## Critério de aprovação

Um consumidor morto antes do commit do offset não gera efeito duplicado, uma mensagem venenosa vai para a DLQ sem travar a partição, e eventos fora de ordem nunca regridem o estado.

## Teste de domínio

Responda em voz alta, em até 2 minutos, sem consultar, e grave:

> Seu consumidor Kafka processou o evento, gravou no banco e morreu antes de commitar o offset. O que acontece e por que isso não gera problema no seu desenho?
