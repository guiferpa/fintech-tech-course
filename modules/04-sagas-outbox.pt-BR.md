# Módulo 4: Saga, Outbox e transações distribuídas

**Semana 4** · [Voltar para a ementa](../README.pt-BR.md) · [Read in English](04-sagas-outbox.md)

## Objetivo

Mover dinheiro entre serviços sem 2PC: saga orquestrada com estado persistido, compensações e transactional outbox.

## Segunda a quarta: leitura + laboratório (3 h por dia)

| Dia | Leitura (2 h) | Laboratório (1 h) |
| --- | --- | --- |
| Seg | DDIA cap. 9, "Atomic Commit and Two-Phase Commit": como o 2PC funciona, por que trava recursos e por que APIs externas não o suportam.<br>Microservices Patterns (Richardson), cap. 4: saga orquestrada x coreografada, compensação, pivot transaction e ordem dos passos. | Separe accounts e payments, cada um com seu banco no Compose, falando por HTTP. |
| Ter | Microservices Patterns, cap. 4, falta de isolamento e contramedidas (semantic lock, commutative updates, reordenar passos). TCC (Try-Confirm-Cancel) e a relação com hold de saldo.<br>Microservices Patterns, cap. 3: mensageria transacional, Transactional Outbox, polling x log tailing. microservices.io/patterns/data/transactional-outbox. Introdução do Debezium. | Outbox experimental: tabela outbox e publicador por polling com SKIP LOCKED enviando para um log (Kafka só no M5). |
| Qua | Documentação do Temporal (workflows, activities, retries, timers) e visão geral do AWS Step Functions. Quando um workflow durável vale o custo.<br>No papel: máquina de estados da saga de transferência entre serviços, com estados, transições, compensações e timeout de cada passo. | Preparação do dia de conclusão: esqueleto de chaos/kill-orchestrator.sh, lista de tarefas e casos de falha. Sem código do TCM. |

Nos laboratórios, IA só para tirar dúvida de conceito, nunca para escrever código do TCM.

## Quinta e sexta: trabalho de conclusão (TCM), sem IA

Tudo feito SEM IA. Nada de ChatGPT, Claude, Copilot ou autocomplete com IA no editor. Vale: documentação oficial, livros, suas anotações e os laboratórios das semanas anteriores. O que não couber hoje vira escopo cortado para o próximo checkpoint; o deadline não muda.

1. (45 min) Tabela sagas (id, estado, passo, tentativas, deadline, payload) e máquina de estados no orquestrador (payments).
2. (1 h) Passos: debitar A em accounts, creditar B, concluir. Cada passo idempotente com chave saga_id + passo.
3. (45 min) Compensação: falha no crédito gera estorno do débito como novo lançamento, nunca apaga.
4. (45 min) Worker de retomada: pega sagas não terminais com SKIP LOCKED e continua; timeout por passo.
5. (30 min) Outbox gravado na mesma transação do dado em cada serviço.
6. (45 min) chaos/kill-orchestrator.sh: 20 kills em pontos aleatórios; verificar soma dos saldos e ausência de saga parada.
7. (30 min) docs/m04.md com o diagrama de estados.

A quinta cobre os itens 1 a 3; a sexta cobre o resto e termina com 30 minutos de entrega.

## Critério de aprovação

Matar o orquestrador 20 vezes em pontos aleatórios mantém a soma dos saldos e não deixa nenhuma saga parada.

## Teste de domínio

Responda em voz alta, em até 2 minutos, sem consultar, e grave:

> Desenhe uma transferência entre contas de dois serviços diferentes usando saga. O que acontece se o crédito em B falhar depois do débito em A?
