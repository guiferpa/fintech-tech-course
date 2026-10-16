# Módulo 7: Pagamentos, Pix e reconciliação

**Semana 8** · [Voltar para a ementa](../README.pt-BR.md) · [Read in English](07-payments-pix-reconciliation.md)

## Objetivo

Entender o ciclo de vida de pagamento, o Pix, a reconciliação contra arquivos de liquidação e o fallback seguro entre provedores.

## Segunda a quarta: DSA + leitura + laboratório (3 h 30 por dia)

| Dia | DSA (30 min) | Leitura (2 h) | Laboratório (1 h) |
| --- | --- | --- | --- |
| Seg | Rate limiter: token bucket (design + código: allow(userId, now))<br>Sem link do LeetCode: escreva uma classe com allow(userId, now) e testes unitários de rajada e reposição. | [Texto do curso: O ciclo de vida do pagamento com cartão e pagamentos duplicados](../lessons/07-payments-pix-reconciliation/day-1.pt-BR.md) (escrito para este curso): leia este primeiro. Ele explica os conceitos do dia e indica quais seções das referências abaixo ler em seguida.<br>[Stripe, "How card payment processing and settlement works"](https://stripe.com/resources/more/credit-card-payment-authorization-and-transaction-settlement-process) (gratuito): autorização, captura, liquidação e os atores (emissor, adquirente, bandeira, gateway).<br>[Documentação da Stripe, "The Payment Intents API"](https://docs.stripe.com/payments/payment-intents) (gratuito): um pagamento modelado como máquina de estados.<br>[Airbnb Engineering, "Avoiding Double Payments in a Distributed Payments System"](https://medium.com/airbnb-engineering/avoiding-double-payments-in-a-distributed-payments-system-2981f6b070bb) (gratuito): o design de um sistema de pagamento real: idempotência, retries e desfechos desconhecidos. | Dois adquirentes falsos que autorizam, capturam e geram CSV de liquidação diário. |
| Ter | Rate limiter: sliding window (sliding window log, depois sliding window counter)<br>Mesma interface de ontem; compare memória e precisão nas bordas da janela. | [Texto do curso: Pix, devoluções e o MED](../lessons/07-payments-pix-reconciliation/day-2.pt-BR.md) (escrito para este curso): leia este primeiro. Ele explica os conceitos do dia e indica quais seções das referências abaixo ler em seguida.<br>[Banco Central do Brasil, página do Pix (regulamento e manuais)](https://www.bcb.gov.br/estabilidadefinanceira/pix) (gratuito): SPI, DICT, end_to_end_id e devoluções.<br>[Banco Central do Brasil, Resolução BCB nº 1 (regulamento do Pix, versão em inglês)](https://www.bcb.gov.br/content/estabilidadefinanceira/pix/Pix_Regulation/Resolution_BCB_1.pdf) (gratuito): passe pelos participantes e pelas obrigações de disponibilidade 24/7.<br>[Banco Central do Brasil, "Guia de implementação do MED"](https://www.bcb.gov.br/content/estabilidadefinanceira/pix/Guia_MED.pdf) (gratuito): o fluxo do Mecanismo Especial de Devolução (MED).<br>[Open Finance Brasil](https://openfinancebrasil.org.br/) (gratuito): Open Finance em alto nível. | Máquina de estados de pagamento com tabela de transições válidas e testes. |
| Qua | [Trapping Rain Water](https://leetcode.com/problems/trapping-rain-water/) (two pointers, depois pilha monotônica) | [Texto do curso: Reconciliação e fallback seguro entre provedores](../lessons/07-payments-pix-reconciliation/day-3.pt-BR.md) (escrito para este curso): leia este primeiro. Ele explica os conceitos do dia e indica quais seções das referências abaixo ler em seguida.<br>[Documentação da Modern Treasury, "Defining Reconciliation Rules"](https://docs.moderntreasury.com/payments/docs/defining-reconciliation-rules) (gratuito): regras de matching e tolerâncias; a barra lateral leva às outras páginas de reconciliação.<br>[Airbnb Engineering, "Measuring Transactional Integrity in Airbnb's Distributed Payment Ecosystem"](https://medium.com/airbnb-engineering/measuring-transactional-integrity-in-airbnbs-distributed-payment-ecosystem-a670d6926d22) (gratuito): reconciliação e checagens de dados em escala.<br>Orquestração de provedores: roteamento e fallback seguro. Desenhe timeout → consulta de status → só então outro provedor. | Preparação do dia de conclusão: arquivos CSV com divergências plantadas e lista de tarefas. Sem código do TCM. |

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
