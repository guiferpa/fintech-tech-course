# Módulo 3: Transações, concorrência e Postgres

**Semana 3** · [Voltar para a ementa](../README.pt-BR.md) · [Read in English](03-transactions-concurrency-postgres.md)

## Objetivo

Saber qual anomalia cada nível de isolamento permite e impedir saldo negativo sob concorrência de mais de uma forma.

## Segunda a quarta: DSA + leitura + laboratório (3 h 30 por dia)

| Dia | DSA (30 min) | Leitura (2 h) | Laboratório (1 h) |
| --- | --- | --- | --- |
| Seg | [Subarray Sum Equals K](https://leetcode.com/problems/subarray-sum-equals-k/) (prefix sum + hash map) | [Texto do curso: Níveis de isolamento e as anomalias que eles permitem](../lessons/03-transactions-concurrency-postgres/day-1.pt-BR.md) (escrito para este curso): leia este primeiro. Ele explica os conceitos do dia e indica quais seções das referências abaixo ler em seguida.<br>[Jepsen, mapa "Consistency Models": "Read Committed" e "Snapshot Isolation"](https://jepsen.io/consistency) (gratuito): o que cada nível de isolamento permite e proíbe, e o que o ACID promete de fato para dinheiro.<br>[Blog da Cockroach Labs, "What write skew looks like"](https://www.cockroachlabs.com/blog/what-write-skew-looks-like/) (gratuito): lost update x write skew, e phantoms. Depois monte seu próprio exemplo de write skew com saldos.<br>[Martin Kleppmann, "Hermitage: testing transaction isolation levels"](https://github.com/ept/hermitage) (gratuito): a tabela de anomalias por banco; foque nas linhas do PostgreSQL. | Duas sessões psql: reproduza lost update em READ COMMITTED. Anote a sequência exata de comandos. |
| Ter | [Merge Intervals](https://leetcode.com/problems/merge-intervals/) (intervalos: ordenar pelo início) | [Texto do curso: Isolamento, locks e retries no Postgres](../lessons/03-transactions-concurrency-postgres/day-2.pt-BR.md) (escrito para este curso): leia este primeiro. Ele explica os conceitos do dia e indica quais seções das referências abaixo ler em seguida.<br>[Documentação do PostgreSQL, "Concurrency Control", seções 13.1 e 13.2](https://www.postgresql.org/docs/current/mvcc.html) (gratuito): níveis de isolamento no Postgres, serialization failure (40001) e retries.<br>[Documentação do PostgreSQL, "Explicit Locking" (13.3)](https://www.postgresql.org/docs/current/explicit-locking.html) (gratuito): SELECT ... FOR UPDATE, SKIP LOCKED, advisory locks, deadlocks e ordem de aquisição. | Write skew em REPEATABLE READ com as contas de um casal (regra: soma dos saldos ≥ 0). Repita em SERIALIZABLE e observe o erro 40001. Anote tudo. |
| Qua | [Koko Eating Bananas](https://leetcode.com/problems/koko-eating-bananas/) (busca binária na resposta) | [Texto do curso: Locks distribuídos, índices e vacuum](../lessons/03-transactions-concurrency-postgres/day-3.pt-BR.md) (escrito para este curso): leia este primeiro. Ele explica os conceitos do dia e indica quais seções das referências abaixo ler em seguida.<br>[Martin Kleppmann, "How to do distributed locking"](https://martin.kleppmann.com/2016/02/08/how-to-do-distributed-locking.html) (gratuito): Redis SET NX PX, fencing tokens, por que a garantia final fica no banco.<br>[Documentação do PostgreSQL, "Indexes" (multicoluna e parcial)](https://www.postgresql.org/docs/current/indexes.html) (gratuito): qual índice atende a consulta de extrato.<br>[Documentação do PostgreSQL, "Using EXPLAIN"](https://www.postgresql.org/docs/current/using-explain.html) (gratuito): ler um plano de execução antes e depois de um índice.<br>[Documentação do PostgreSQL, "Routine Vacuuming", introdução](https://www.postgresql.org/docs/current/routine-vacuuming.html) (gratuito): MVCC e por que o vacuum existe. | Preparação do dia de conclusão: seed de 1.000 contas, esqueleto do script de carga paralela e lista de testes. Sem código do TCM. |

Resolva sem IA, com limite de 30 minutos. Método e lista completa: [trilha de DSA](../DSA.pt-BR.md).

Nos laboratórios, IA só para tirar dúvida de conceito, nunca para escrever código do TCM.

## Quinta e sexta: trabalho de conclusão (TCM), sem IA

Tudo feito SEM IA. Nada de ChatGPT, Claude, Copilot ou autocomplete com IA no editor. Vale: documentação oficial, livros, suas anotações e os laboratórios das semanas anteriores. O que não couber hoje vira escopo cortado para o próximo checkpoint; o deadline não muda.

1. (45 min) Transferência v1: SELECT ... FOR UPDATE travando as duas contas em ordem de id.
2. (45 min) v2 otimista: coluna version e retry limitado.
3. (30 min) v3: UPDATE condicional WHERE balance >= :valor, conferindo as linhas afetadas.
4. (1 h) Teste com 100 transferências paralelas em cada versão: nenhum saldo negativo e soma total constante.
5. (45 min) Medir vazão, conflitos e retries; montar a tabela comparativa.
6. (30 min) EXPLAIN ANALYZE do extrato antes e depois do índice (account_id, created_at).
7. (45 min) docs/m03.md dizendo qual versão você usaria em produção e por quê.

A quinta cobre os itens 1 a 4; a sexta cobre o resto e termina com 30 minutos de entrega.

## Critério de aprovação

Nenhuma das três versões deixa saldo negativo, e o docs/m03.md diz qual você usaria em produção e por quê.

## Teste de domínio

Responda em voz alta, em até 2 minutos, sem consultar, e grave:

> Duas transferências simultâneas saem da mesma conta com saldo para só uma. Mostre três formas de impedir saldo negativo e o trade-off de cada.
