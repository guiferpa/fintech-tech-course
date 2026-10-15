# Módulo 7: Pagamentos, Pix e reconciliação

**Semana 8** · [Voltar para a ementa](../README.pt-BR.md) · [Read in English](07-payments-pix-reconciliation.md)

## Objetivo

Entender o ciclo de vida de pagamento, o Pix, a reconciliação contra arquivos de liquidação e o fallback seguro entre provedores.

## Segunda a quarta: DSA + leitura + laboratório (3 h 30 por dia)

| Dia | DSA (30 min) | Leitura (2 h) | Laboratório (1 h) |
| --- | --- | --- | --- |
| Seg | Rate limiter: token bucket (design + código: allow(userId, now))<br>Sem link do LeetCode: escreva uma classe com allow(userId, now) e testes unitários de rajada e reposição. | Ciclo de vida de pagamento com cartão (autorização, captura, liquidação, estorno, chargeback) e atores (emissor, adquirente, bandeira, subadquirente, gateway, PSP). Documentação da Stripe sobre PaymentIntents.<br>System Design Interview vol. 2, capítulo de sistema de pagamento. | Dois adquirentes falsos que autorizam, capturam e geram CSV de liquidação diário. |
| Ter | Rate limiter: sliding window (sliding window log, depois sliding window counter)<br>Mesma interface de ontem; compare memória e precisão nas bordas da janela. | Regulamento do Pix (Bacen): SPI, DICT, end_to_end_id, devoluções.<br>Carnaval: se for viajar, junte com a sessão de amanhã. MED (Mecanismo Especial de Devolução), Pix 24/7 e o que isso exige de disponibilidade. Open Finance em alto nível. | Máquina de estados de pagamento com tabela de transições válidas e testes. |
| Qua | [Trapping Rain Water](https://leetcode.com/problems/trapping-rain-water/) (two pointers, depois pilha monotônica) | Carnaval: se for viajar, junte com a sessão de ontem. Reconciliação: matching, tolerâncias, tratamento de divergência (artigos da Modern Treasury sobre reconciliação).<br>Orquestração de provedores: roteamento e fallback seguro. Desenhe o fluxo timeout → consulta de status → só então outro provedor. | Preparação do dia de conclusão: arquivos CSV com divergências plantadas e lista de tarefas. Sem código do TCM. |

Resolva sem IA, com limite de 30 minutos. Método e lista completa: [trilha de DSA](../DSA.pt-BR.md).

Nos laboratórios, IA só para tirar dúvida de conceito, nunca para escrever código do TCM.

## Quinta e sexta: trabalho de conclusão (TCM), sem IA

Tudo feito SEM IA. Nada de ChatGPT, Claude, Copilot ou autocomplete com IA no editor. Vale: documentação oficial, livros, suas anotações e os laboratórios das semanas anteriores. O que não couber hoje vira escopo cortado para o próximo checkpoint; o deadline não muda.

1. (1 h) Integrar a máquina de estados ao ledger: autorização vira hold, captura vira lançamento, estorno vira lançamento inverso.
2. (1 h 15) Job de reconciliação ledger x CSV: matching por id, tolerância e relatório de divergências.
3. (30 min) Rodar contra as divergências plantadas: faltando, duplicado, valor diferente, data trocada.
4. (1 h) Orquestrador de provedores com fallback seguro.
5. (45 min) Testes: 100% das divergências detectadas; nunca cobra nos dois provedores.
6. (30 min) docs/m07.md.

A quinta cobre os itens 1 a 3; a sexta cobre o resto e termina com 30 minutos de entrega.

## Critério de aprovação

100% das divergências plantadas são detectadas, e o fallback nunca cobra nos dois provedores.

## Teste de domínio

Responda em voz alta, em até 2 minutos, sem consultar, e grave:

> Um pagamento ficou 'aprovado' para o cliente, mas não aparece no arquivo de liquidação do adquirente no dia seguinte. Como seu sistema detecta e o que faz?
