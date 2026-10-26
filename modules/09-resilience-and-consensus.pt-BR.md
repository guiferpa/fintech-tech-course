# Módulo 9: Resiliência, alta disponibilidade e consenso

**Semana 11** · [Voltar para a ementa](../README.pt-BR.md) · [Read in English](09-resilience-and-consensus.md)

## Objetivo

Fazer o sistema degradar de forma controlada: timeouts, retry com jitter, circuit breaker, bulkhead, rate limiting, migrações seguras, DR e consenso em alto nível.

## Segunda a quarta: DSA + leitura + laboratório (3 h 30 por dia)

| Dia | DSA (30 min) | Leitura (2 h) | Laboratório (1 h) |
| --- | --- | --- | --- |
| Seg | [Find Median from Data Stream](https://leetcode.com/problems/find-median-from-data-stream/) (dois heaps) | [Texto do curso: Timeouts, retries, circuit breakers e bulkheads](../lessons/09-resilience-and-consensus/day-1.pt-BR.md) (escrito para este curso): leia este primeiro. Ele explica os conceitos do dia e indica quais seções das referências abaixo ler em seguida.<br>[Martin Fowler, "Circuit Breaker"](https://martinfowler.com/bliki/CircuitBreaker.html) (gratuito): como um circuit breaker funciona e seus estados.<br>[Microsoft Azure Architecture Center, "Bulkhead pattern"](https://learn.microsoft.com/en-us/azure/architecture/patterns/bulkhead) (gratuito): isolar recursos para uma dependência lenta não derrubar tudo.<br>[Amazon Builders' Library, "Timeouts, retries, and backoff with jitter"](https://aws.amazon.com/builders-library/timeouts-retries-and-backoff-with-jitter/) (gratuito): como escolher timeouts, tempestades de retry e orçamento de retries. | k6 + Toxiproxy: cenário com provedor respondendo em 30 s; medir sem proteção (p99, erros, conexões). |
| Ter | [Task Scheduler](https://leetcode.com/problems/task-scheduler/) (guloso + max-heap) | [Texto do curso: Sobrecarga, filas acumuladas e consenso](../lessons/09-resilience-and-consensus/day-2.pt-BR.md) (escrito para este curso): leia este primeiro. Ele explica os conceitos do dia e indica quais seções das referências abaixo ler em seguida.<br>[Amazon Builders' Library, "Avoiding insurmountable queue backlogs"](https://aws.amazon.com/builders-library/avoiding-insurmountable-queue-backlogs/) (gratuito): filas acumuladas, priorização e descarte de trabalho.<br>[Amazon Builders' Library, "Using load shedding to avoid overload"](https://aws.amazon.com/builders-library/using-load-shedding-to-avoid-overload/) (gratuito): load shedding e rate limiting.<br>[Amazon Builders' Library, "Leader election in distributed systems"](https://aws.amazon.com/builders-library/leader-election-in-distributed-systems/) (gratuito): por que sistemas usam um líder, como a Amazon elege um com leases, e o problema do líder desatualizado (pausas de GC, verificar o lease antes de efeitos colaterais).<br>[Documentação do etcd, "FAQ"](https://etcd.io/docs/v3.6/faq/) (gratuito): quorum e tolerância a falhas por tamanho de cluster, por que números ímpares de membros, por que no máximo sete membros e como o quorum evita split brain.<br>[Documentação do etcd, "Failure modes"](https://etcd.io/docs/v3.6/op-guide/failures/) (gratuito): o que acontece em falha do líder, falha da maioria e partição de rede: tempo de eleição, escritas enfileiradas e por que escritas confirmadas nunca se perdem.<br>[Documentação do etcd, "Tuning"](https://etcd.io/docs/v3.6/tuning/) (gratuito): heartbeat interval e election timeout: padrões (100 ms, 1000 ms) e como dimensioná-los a partir do tempo de ida e volta.<br>[Documentação do HashiCorp Consul, "Consensus"](https://developer.hashicorp.com/consul/docs/concept/consensus) (gratuito): uma visão geral do Raft em uma página, de um produto que o roda: follower, candidate, leader, quando uma entrada é confirmada e a tabela de implantação.<br>[Documentação da Cockroach Labs, "Replication Layer"](https://docs.cockroachlabs.com/docs/stable/architecture/replication-layer) (gratuito): a seção sobre Raft: grupos Raft, heartbeats, election timeouts sorteados, tolerância a falhas pelo fator de replicação e snapshots.<br>[Documentação do Patroni, "Introduction"](https://patroni.readthedocs.io/en/latest/) (gratuito): opcional: de quais stores de consenso (etcd, Consul, ZooKeeper, Kubernetes) uma ferramenta real de failover de Postgres depende.<br>[The Raft Consensus Algorithm, site "Raft" com visualização (linka o passo a passo The Secret Lives of Data)](https://raft.github.io/) (gratuito): assista a uma eleição e à replicação de log na visualização interativa; depois siga o passo a passo guiado em thesecretlivesofdata.com/raft. | Timeouts explícitos e circuit breaker (opossum) no provedor; medir de novo. |
| Qua | Priority scheduler (design + código: heap ordenado por (runAt, prioridade))<br>Sem link do LeetCode: schedule(task, priority, runAt) e next(now), mais retry com backoff exponencial para tarefas que falham. | [Texto do curso: Disaster recovery, migrações seguras e feature flags](../lessons/09-resilience-and-consensus/day-3.pt-BR.md) (escrito para este curso): leia este primeiro. Ele explica os conceitos do dia e indica quais seções das referências abaixo ler em seguida.<br>[Whitepaper da AWS, "Disaster recovery options in the cloud"](https://docs.aws.amazon.com/whitepapers/latest/disaster-recovery-workloads-on-aws/disaster-recovery-options-in-the-cloud.html) (gratuito): RPO, RTO, ativo-passivo x ativo-ativo. Pense por que ativo-ativo com saldos é difícil.<br>[Martin Fowler, "Parallel Change"](https://martinfowler.com/bliki/ParallelChange.html) (gratuito): migrações expand/contract.<br>[Pete Hodgson, "Feature Toggles (aka Feature Flags)" (martinfowler.com)](https://martinfowler.com/articles/feature-toggles.html) (gratuito): feature flags e canary releases. | Preparação do dia de conclusão: script de backup e cenário de migração escolhido; lista de tarefas. Sem código do TCM. |

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
