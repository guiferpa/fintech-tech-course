# Módulo 4: Saga, Outbox e transações distribuídas

**Semana 4** · [Voltar para a ementa](../README.pt-BR.md) · [Read in English](04-sagas-outbox.md)

## Objetivo

Mover dinheiro entre serviços sem 2PC: saga orquestrada com estado persistido, compensações e transactional outbox.

## Segunda a quarta: DSA + leitura + laboratório (3 h 30 por dia)

| Dia | DSA (30 min) | Leitura (2 h) | Laboratório (1 h) |
| --- | --- | --- | --- |
| Seg | [Capacity To Ship Packages Within D Days](https://leetcode.com/problems/capacity-to-ship-packages-within-d-days/) (busca binária na resposta (capacidade, dias, pesos)) | [Texto do curso: Two-phase commit e por que sagas existem](../lessons/04-sagas-outbox/day-1.pt-BR.md) (escrito para este curso): leia este primeiro. Ele explica os conceitos do dia e indica quais seções das referências abaixo ler em seguida.<br>[Chris Richardson, microservices.io, "Pattern: Saga"](https://microservices.io/patterns/data/saga.html) (gratuito): sagas orquestradas x coreografadas e transações de compensação.<br>[Documentação do PostgreSQL, "PREPARE TRANSACTION"](https://www.postgresql.org/docs/current/sql-prepare-transaction.html) (gratuito): o lado participante do 2PC num banco real: o que o prepare faz, e os avisos sobre locks mantidos, VACUUM e transações preparadas esquecidas.<br>[Documentação do PostgreSQL, "Two-Phase Transactions"](https://www.postgresql.org/docs/current/two-phase.html) (gratuito): dois parágrafos: os três comandos do 2PC, o modelo XA e por que o estado preparado deve ser curto.<br>[Blog da Cockroach Labs, "Parallel Commits: An atomic commit protocol for globally distributed transactions"](https://www.cockroachlabs.com/blog/parallel-commits/) (gratuito): por que o 2PC clássico bloqueia e é lento, e como um banco em produção o torna seguro replicando a decisão de commit por consenso.<br>[AWS Prescriptive Guidance, "Saga orchestration pattern"](https://docs.aws.amazon.com/prescriptive-guidance/latest/cloud-design-patterns/saga-orchestration.html) (gratuito): as fases do 2PC, por que um banco por serviço descarta o 2PC, problemas a planejar (idempotência, isolamento, ponto único de falha) e um exemplo com Step Functions e compensações.<br>[Azure Architecture Center, "Saga distributed transactions pattern"](https://learn.microsoft.com/en-us/azure/architecture/patterns/saga) (gratuito): transações compensáveis, pivô e repetíveis, e os trade-offs de coreografia x orquestração. | Separe accounts e payments, cada um com seu banco no Compose, falando por HTTP. |
| Ter | [Clone Graph](https://leetcode.com/problems/clone-graph/) (DFS/BFS em grafo + hash map de cópias) | [Texto do curso: Isolamento em sagas, reserva de saldo e transactional outbox](../lessons/04-sagas-outbox/day-2.pt-BR.md) (escrito para este curso): leia este primeiro. Ele explica os conceitos do dia e indica quais seções das referências abaixo ler em seguida.<br>[Chris Richardson, "Microservices Patterns" (Manning), capítulo 4, "Handling the lack of isolation"](https://www.manning.com/books/microservices-patterns) (livro pago): contramedidas (semantic lock, commutative updates, reordering), pivot transaction, TCC e reserva de saldo. Nenhuma fonte gratuita cobre isso tão bem.<br>[Chris Richardson, microservices.io, "Pattern: Transactional outbox"](https://microservices.io/patterns/data/transactional-outbox.html) (gratuito): o outbox e as duas formas de publicar linkadas na página: Polling publisher e Transaction log tailing.<br>[Documentação do Debezium, "Debezium Architecture"](https://debezium.io/documentation/reference/stable/architecture.html) (gratuito): como o change data capture lê o log do banco. | Outbox experimental: tabela outbox e publicador por polling com SKIP LOCKED enviando para um log (Kafka só no M5). |
| Qua | [Copy List with Random Pointer](https://leetcode.com/problems/copy-list-with-random-pointer/) (hash map, depois intercalação com espaço O(1)) | [Texto do curso: Workflows duráveis e a máquina de estados da saga de transferência](../lessons/04-sagas-outbox/day-3.pt-BR.md) (escrito para este curso): leia este primeiro. Ele explica os conceitos do dia e indica quais seções das referências abaixo ler em seguida.<br>[Documentação do Temporal, "What is Temporal?"](https://docs.temporal.io/temporal) (gratuito): workflows, activities, retries e timers.<br>[AWS Step Functions Developer Guide, "What is Step Functions?"](https://docs.aws.amazon.com/step-functions/latest/dg/welcome.html) (gratuito): outra visão de workflows duráveis; quando valem o custo?<br>No papel: a máquina de estados da saga de transferência entre serviços, com estados, transições, compensações e timeouts por passo. | Preparação do dia de conclusão: esqueleto de chaos/kill-orchestrator.sh, lista de tarefas e casos de falha. Sem código do TCM. |

Resolva sem IA, com limite de 30 minutos. Método e lista completa: [trilha de DSA](../DSA.pt-BR.md).

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
