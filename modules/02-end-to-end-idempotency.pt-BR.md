# Módulo 2: Idempotência ponta a ponta

**Semana 2** · [Voltar para a ementa](../README.pt-BR.md) · [Read in English](02-end-to-end-idempotency.md)

## Objetivo

Fechar idempotência ponta a ponta: na API (Idempotency-Key), no consumidor de mensagens (mensagens processadas) e na integração com terceiros (repassar a chave).

## Segunda a quarta: DSA + leitura + laboratório (3 h 30 por dia)

| Dia | DSA (30 min) | Leitura (2 h) | Laboratório (1 h) |
| --- | --- | --- | --- |
| Seg | [Kth Largest Element in a Stream](https://leetcode.com/problems/kth-largest-element-in-a-stream/) (min-heap de tamanho k) | [Texto do curso: Idempotency keys e fases atômicas](../lessons/02-end-to-end-idempotency/day-1.pt-BR.md) (escrito para este curso): leia este primeiro. Ele explica os conceitos do dia e indica quais seções das referências abaixo ler em seguida.<br>[Blog da Stripe, "Designing robust and predictable APIs with idempotency"](https://stripe.com/blog/idempotency) (gratuito): por que retries precisam de chave de idempotência e como os clientes devem usá-las.<br>[Brandur Leach, "Implementing Stripe-like Idempotency Keys in Postgres", primeira metade](https://brandur.org/idempotency-keys) (gratuito): fases atômicas e recovery points. | Prática do que você leu. |
| Ter | [Maximum Subarray](https://leetcode.com/problems/maximum-subarray/) (Kadane)<br>[Maximum Product Subarray](https://leetcode.com/problems/maximum-product-subarray/) (variação de Kadane (guarda mínimo e máximo)) | [Texto do curso: Recuperando requisições interrompidas e consumidores idempotentes](../lessons/02-end-to-end-idempotency/day-2.pt-BR.md) (escrito para este curso): leia este primeiro. Ele explica os conceitos do dia e indica quais seções das referências abaixo ler em seguida.<br>[Brandur Leach, "Implementing Stripe-like Idempotency Keys in Postgres", segunda metade](https://brandur.org/idempotency-keys) (gratuito): recuperação de requisições interrompidas e o processo completer.<br>[Chris Richardson, microservices.io, "Pattern: Idempotent Consumer"](https://microservices.io/patterns/communication-style/idempotent-consumer.html) (gratuito): entrega at-least-once + tabela de mensagens processadas por message_id, gravada na mesma transação do efeito. | Prática do que você leu. |
| Qua | [Longest Substring Without Repeating Characters](https://leetcode.com/problems/longest-substring-without-repeating-characters/) (sliding window) | [Texto do curso: Idempotência em cada etapa](../lessons/02-end-to-end-idempotency/day-3.pt-BR.md) (escrito para este curso): leia este primeiro. Ele explica os conceitos do dia e indica quais seções das referências abaixo ler em seguida.<br>[Referência da API da Stripe, "Idempotent requests"](https://docs.stripe.com/api/idempotent_requests) (gratuito): como um provedor real documenta chaves, expiração e erros.<br>Chave natural x chave do cliente (end_to_end_id do Pix), operações naturalmente idempotentes (SET status ... WHERE status = 'PENDING') x não idempotentes (balance = balance - 100), repassar a chave ao provedor. Desenhe no papel o fluxo API → fila → worker → provedor com os pontos de idempotência. | Preparação do dia de conclusão: liste os casos de teste (mesma chave e mesmo corpo, mesma chave e corpo diferente, requisição ainda em andamento, 50 simultâneas) e crie as migrations vazias. Sem código do TCM. |

Resolva sem IA, com limite de 30 minutos. Método e lista completa: [trilha de DSA](../DSA.pt-BR.md).

Nos laboratórios, IA só para tirar dúvida de conceito, nunca para escrever código do TCM.

## Quinta e sexta: trabalho de conclusão (TCM), sem IA

Tudo feito SEM IA. Nada de ChatGPT, Claude, Copilot ou autocomplete com IA no editor. Vale: documentação oficial, livros, suas anotações e os laboratórios das semanas anteriores. O que não couber hoje vira escopo cortado para o próximo checkpoint; o deadline não muda.

1. (45 min) Tabela idempotency_keys (chave, usuário, hash do corpo, status, código e corpo da resposta, locked_at) e migration.
2. (1 h 30) Interceptor no NestJS: insere a chave com ON CONFLICT; concluída com mesmo hash devolve a resposta salva; em andamento devolve 409; hash diferente devolve 422.
3. (30 min) Repassar a chave em header ao banco parceiro falso, que também deduplica.
4. (45 min) Tabela processed_messages e consumidor que ignora message_id repetido, na mesma transação do efeito.
5. (45 min) Teste: 50 requisições simultâneas com a mesma chave terminam em exatamente 1 transferência.
6. (45 min) docs/m02.md com as decisões.

A quinta cobre os itens 1 a 3; a sexta cobre o resto e termina com 30 minutos de entrega.

## Critério de aprovação

Um teste dispara 50 requisições simultâneas com a mesma chave e o banco termina com exatamente uma transferência.

## Teste de domínio

Responda em voz alta, em até 2 minutos, sem consultar, e grave:

> Onde, num fluxo API → fila → worker → provedor, você coloca idempotência, e por que em cada ponto?
