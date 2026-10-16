# Módulo 6: Ledger e contabilidade

**Semana 7** · [Voltar para a ementa](../README.pt-BR.md) · [Read in English](06-ledgers-and-accounting.md)

## Objetivo

Modelar dinheiro como um contador: dupla entrada, saldos por estado, holds, taxas, estornos e invariantes garantidas pelo banco.

## Segunda a quarta: DSA + leitura + laboratório (3 h 30 por dia)

| Dia | DSA (30 min) | Leitura (2 h) | Laboratório (1 h) |
| --- | --- | --- | --- |
| Seg | [Word Ladder](https://leetcode.com/problems/word-ladder/) (BFS para menor caminho) | [Texto do curso: Partidas dobradas, tipos de conta e saldos](../lessons/06-ledgers-and-accounting/day-1.pt-BR.md) (escrito para este curso): leia este primeiro. Ele explica os conceitos do dia e indica quais seções das referências abaixo ler em seguida.<br>[Modern Treasury, "Accounting for Developers", partes I e II](https://www.moderntreasury.com/journal/accounting-for-developers-part-i) (gratuito): partidas dobradas, débito e crédito, saldo normal de cada tipo de conta (a parte II está linkada no fim).<br>[Modern Treasury, "Accounting for Developers", parte III](https://www.moderntreasury.com/journal/accounting-for-developers-part-iii) (gratuito): um exemplo completo de ledger de um produto.<br>[Modern Treasury, "How to Scale a Ledger"](https://www.moderntreasury.com/ebooks/how-to-scale-a-ledger) (gratuito): saldos pending, posted e available. | Modelagem e migrations: accounts, transactions, postings. |
| Ter | [Word Ladder (optimization)](https://leetcode.com/problems/word-ladder/) (BFS bidirecional + mapa de curingas)<br>Refaça a solução de ontem, agora com BFS bidirecional, e compare os tempos. | [Texto do curso: Holds, invariantes de conta e dinheiro sumido](../lessons/06-ledgers-and-accounting/day-2.pt-BR.md) (escrito para este curso): leia este primeiro. Ele explica os conceitos do dia e indica quais seções das referências abaixo ler em seguida.<br>[Documentação do TigerBeetle, "Two-Phase Transfers"](https://docs.tigerbeetle.com/coding/two-phase-transfers/) (gratuito): transferências pendentes que depois são confirmadas ou anuladas.<br>[Documentação do TigerBeetle, referência "Account"](https://docs.tigerbeetle.com/reference/account/) (gratuito): o modelo de dados e flags como debits_must_not_exceed_credits.<br>[Blog da Stripe, "Ledger: Stripe's system for tracking and validating money movement"](https://stripe.dev/blog/ledger-stripe-system-for-tracking-and-validating-money-movement) (gratuito): como um ledger detecta dinheiro que sumiu. | Tipo Money (bigint de centavos + moeda), split determinístico de 100 em 3 e banker's rounding, com testes unitários. |
| Qua | [Merge K Sorted Lists](https://leetcode.com/problems/merge-k-sorted-lists/) (min-heap, ou dividir e conquistar)<br>Mesmo formato de juntar streams ordenados de eventos numa reconciliação. | [Texto do curso: Concorrência, imutabilidade e lançamentos no papel](../lessons/06-ledgers-and-accounting/day-3.pt-BR.md) (escrito para este curso): leia este primeiro. Ele explica os conceitos do dia e indica quais seções das referências abaixo ler em seguida.<br>[Modern Treasury, "Designing the Ledgers API with Optimistic Locking"](https://www.moderntreasury.com/journal/designing-ledgers-with-optimistic-locking) (gratuito): concorrência em contas quentes.<br>[Modern Treasury, "Enforcing Immutability in your Double-Entry Ledger"](https://www.moderntreasury.com/journal/enforcing-immutability-in-your-double-entry-ledger) (gratuito): lançamentos append-only e correção por estorno.<br>No papel: lançamentos de depósito, transferência com tarifa, estorno parcial, reserva e captura. | Preparação do dia de conclusão: fast-check instalado, geradores de operação esboçados, lista de tarefas. Sem código do TCM. |

Resolva sem IA, com limite de 30 minutos. Método e lista completa: [trilha de DSA](../DSA.pt-BR.md).

Nos laboratórios, IA só para tirar dúvida de conceito, nunca para escrever código do TCM.

## Quinta e sexta: trabalho de conclusão (TCM), sem IA

Tudo feito SEM IA. Nada de ChatGPT, Claude, Copilot ou autocomplete com IA no editor. Vale: documentação oficial, livros, suas anotações e os laboratórios das semanas anteriores. O que não couber hoje vira escopo cortado para o próximo checkpoint; o deadline não muda.

1. (45 min) Invariante soma zero garantida no banco (constraint trigger deferrable).
2. (1 h) Lançamentos: depósito, transferência com taxa, estorno parcial.
3. (1 h) Holds: criar, capturar e liberar; saldos pending, available e held.
4. (45 min) Migrar as transferências dos módulos 3 e 4 para o ledger.
5. (1 h) Teste baseado em propriedades: 10 mil operações aleatórias sem quebrar a soma zero nem deixar available negativo.
6. (30 min) docs/m06.md.

A quinta cobre os itens 1 a 3; a sexta cobre o resto e termina com 30 minutos de entrega.

## Critério de aprovação

Um teste baseado em propriedades roda 10 mil operações aleatórias e nunca quebra a soma zero nem deixa o saldo disponível negativo.

## Teste de domínio

Responda em voz alta, em até 2 minutos, sem consultar, e grave:

> Modele as tabelas de um ledger de carteira digital e mostre os lançamentos de: depósito, transferência entre usuários com taxa, e estorno parcial.
