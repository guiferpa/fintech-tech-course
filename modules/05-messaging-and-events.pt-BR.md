# Módulo 5: Mensageria e eventos

**Semana 6** · [Voltar para a ementa](../README.pt-BR.md) · [Read in English](05-messaging-and-events.md)

## Objetivo

Passar eventos por um log com segurança: chave de partição, offsets, retries, DLQ, ordem e webhooks assinados.

## Segunda a quarta: DSA + leitura + laboratório (3 h 30 por dia)

| Dia | DSA (30 min) | Leitura (2 h) | Laboratório (1 h) |
| --- | --- | --- | --- |
| Seg | [Course Schedule](https://leetcode.com/problems/course-schedule/) (detecção de ciclo em grafo dirigido (DFS com 3 cores))<br>Mesma ideia da detecção de deadlock num wait-for graph. | [Texto do curso: O log, partições e producers](../lessons/05-messaging-and-events/day-1.pt-BR.md) (escrito para este curso): leia este primeiro. Ele explica os conceitos do dia e indica quais seções das referências abaixo ler em seguida.<br>[Jay Kreps, "The Log: What every software engineer should know about real-time data's unifying abstraction"](https://engineering.linkedin.com/distributed-systems/log-what-every-software-engineer-should-know-about-real-time-datas-unifying) (gratuito): filas x logs, offsets e consumidores.<br>[Gwen Shapira et al., "Kafka: The Definitive Guide", 2ª edição, capítulo 3 (Producers)](https://www.confluent.io/resources/kafka-the-definitive-guide-v2/) (gratuito, com cadastro): acks, producer idempotente, chave de partição e ordem por chave. | Redpanda no Compose; criar tópicos com partições; produzir e consumir com kcat. |
| Ter | [Course Schedule II](https://leetcode.com/problems/course-schedule-ii/) (ordenação topológica (Kahn)) | [Texto do curso: Consumidores, offsets e exactly-once](../lessons/05-messaging-and-events/day-2.pt-BR.md) (escrito para este curso): leia este primeiro. Ele explica os conceitos do dia e indica quais seções das referências abaixo ler em seguida.<br>[Gwen Shapira et al., "Kafka: The Definitive Guide", 2ª edição, capítulos 4 (Consumers) e 7 (Reliable Data Delivery)](https://www.confluent.io/resources/kafka-the-definitive-guide-v2/) (gratuito, com cadastro): consumer groups, rebalanceamento, commit de offset antes ou depois de processar.<br>[Blog da Confluent, "Exactly-Once Semantics Are Possible: Here's How Kafka Does It"](https://www.confluent.io/blog/exactly-once-semantics-are-possible-heres-how-apache-kafka-does-it/) (gratuito): transações e exactly-once, e onde isso acaba (efeitos fora do Kafka). | Trocar o publicador do outbox para publicar no Redpanda com chave account_id; consumidor simples. |
| Qua | [Accounts Merge](https://leetcode.com/problems/accounts-merge/) (union-find) | [Texto do curso: Retries, DLQ, event sourcing e webhooks assinados](../lessons/05-messaging-and-events/day-3.pt-BR.md) (escrito para este curso): leia este primeiro. Ele explica os conceitos do dia e indica quais seções das referências abaixo ler em seguida.<br>[Uber Engineering, "Building Reliable Reprocessing and Dead Letter Queues with Apache Kafka"](https://www.uber.com/us/en/blog/reliable-reprocessing/) (gratuito): retries, DLQ, mensagens envenenadas e backpressure.<br>[Martin Fowler, "Event Sourcing"](https://martinfowler.com/eaaDev/EventSourcing.html) (gratuito): estado como sequência de eventos; depois leia a nota curta sobre CQRS linkada no texto.<br>[Especificação Standard Webhooks](https://github.com/standard-webhooks/standard-webhooks) (gratuito): webhooks assinados: HMAC, id e timestamp. | Preparação do dia de conclusão: scripts de chaos esboçados (matar consumidor, mensagem venenosa, fora de ordem) e lista de tarefas. Sem código do TCM. |

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
