# Módulo 3: Transações, concorrência e Postgres

**Semana 3** · [Voltar para a ementa](../README.pt-BR.md) · [Read in English](03-transactions-concurrency-postgres.md)

## Objetivo

Saber qual anomalia cada nível de isolamento permite e impedir saldo negativo sob concorrência de mais de uma forma.

## Segunda a quarta: leitura + laboratório (3 h por dia)

| Dia | Leitura (2 h) | Laboratório (1 h) |
| --- | --- | --- |
| Seg | DDIA cap. 7 até "Weak Isolation Levels": ACID e o que cada letra protege em dinheiro; read committed; snapshot isolation.<br>DDIA cap. 7: lost update, write skew e phantoms. Monte um exemplo de write skew com saldo. | Duas sessões psql: reproduza lost update em READ COMMITTED. Anote a sequência exata de comandos. |
| Ter | Documentação do Postgres, "Concurrency Control" 13.1 e 13.2: níveis de isolamento no Postgres, erro de serialização (40001) e retry.<br>Postgres 13.3, "Explicit Locking": SELECT ... FOR UPDATE, SKIP LOCKED, advisory locks, deadlocks e ordem de aquisição. | Write skew em REPEATABLE READ com as contas de um casal (regra: soma dos saldos ≥ 0). Repita em SERIALIZABLE e observe o erro 40001. Anote tudo. |
| Qua | Kleppmann, "How to do distributed locking": Redis SET NX PX, fencing tokens, por que a garantia final fica no banco.<br>Postgres: "Indexes" (multicoluna e parcial), "Using EXPLAIN" e a introdução de "Routine Vacuuming" (MVCC e vacuum). | Preparação do dia de conclusão: seed de 1.000 contas, esqueleto do script de carga paralela e lista de testes. Sem código do TCM. |

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
