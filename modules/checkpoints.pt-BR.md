# Checkpoints

[Voltar para a ementa](../README.pt-BR.md) · [Read in English](checkpoints.md)

As semanas de checkpoint são para um simulado de entrevista cronometrado, revisão do que ficou fraco e reposição de escopo cortado. O Checkpoint 2 também traz um tema novo na segunda: pagamentos cross-border.

| Dia | Checkpoint 1 (semana 5, módulos 1 a 4) | Checkpoint 2 (semana 9, módulos 5 a 7) |
| --- | --- | --- |
| Seg | Revisar todos os flashcards; reler código e notas; listar escopo cortado | **Pagamentos cross-border**: texto do curso, leituras e um lab no papel (veja abaixo) |
| Ter | Repor escopo cortado, sem IA | Revisar todos os flashcards e listar o escopo cortado (1 h), depois repor sem IA (2 h) |
| Qua | System design de 45 min, gravado: **carteira digital** | System design de 45 min, gravado: **gateway de pagamento ou sistema de Pix** |
| Qui | 5 testes de domínio sorteados + code review de 30 min | Igual, para os módulos 5 a 7 |
| Sex | 3 respostas em inglês, 1 história STAR, 1 pergunta fora da sua experiência | Igual, e atualizar CV e LinkedIn |

**Aprovado se** cada gravação cobre falhas e idempotência sem você ser perguntado. O que faltou vira flashcard.

## Checkpoint 2, segunda-feira: pagamentos cross-border

Leitura (2 h):

- [Texto do curso: Pagamentos cross-border](../lessons/checkpoint-2-cross-border-payments/day-1.pt-BR.md) *(escrito para este curso)*: leia este primeiro. Ele explica os conceitos do dia e indica quais seções das referências abaixo ler em seguida.
- [Wise, "What is a correspondent bank?"](https://wise.com/us/blog/what-is-a-correspondent-bank) *(gratuito)*: como bancos correspondentes e contas nostro e vostro movem pagamentos SWIFT, e por que cada salto desconta tarifas. Anote as duas definições de conta.
- [ING Wholesale Banking, "ISO 20022 SWIFT CBPR+ update"](https://www.ingwb.com/en/service/payments-and-collections/iso20022-swift-cbpr-update) *(gratuito)*: o mapeamento de MT para ISO 20022 (MT103 para pacs.008, devoluções como pacs.004) e as datas da migração. Anote qual mensagem substitui qual.
- [Documentação da Stripe, "Enable currency conversion using the FX Quotes API"](https://docs.stripe.com/payments/custom/localize-prices/fx-quotes-api) *(gratuito)*: uma cotação de câmbio real: taxa de referência, tarifa, prêmio da trava, duração da trava, expiração antecipada e o erro de cotação expirada. Anote como travar a taxa que o cliente viu.
- [Documentação da Wise Platform, "Transfer statuses"](https://docs.wise.com/guides/product/send-money/tracking/transfer-statuses) *(gratuito)*: os estados de uma transferência cross-border real, de aguardando recursos até paga ou devolvida. Mapeie-os na sua própria máquina de estados.
- [Banco Central do Brasil, "Cartilha de Câmbio 2026"](https://www.bcb.gov.br/content/estabilidadefinanceira/politica_cambial/Cartilha_cambio_2026.pdf) *(gratuito)*: guia oficial do BCB: quem pode operar câmbio, transferências internacionais por prestadores de eFX e o VET. Anote o que o VET inclui.

Lab (1 h): no papel, desenhe uma transferência cross-border de uma carteira em BRL para uma conta em USD: cotação, trava, débito, conversão, pagamento e reconciliação. Desenhe a máquina de estados, a linha da cotação e os lançamentos por moeda, e marque onde ficam a idempotência e as chaves de reconciliação.

## DSA (segunda a quarta, primeiros 30 min)

| Dia | Checkpoint 1 (semana 5) | Checkpoint 2 (semana 9) |
| --- | --- | --- |
| Seg | Refaça do zero 2 problemas que você marcou como "refazer" nas semanas 1 a 4, sem dicas. | Refaça do zero 2 problemas que você marcou como "refazer" nas semanas 6 a 8, sem dicas. |
| Ter | Simulado de entrevista de coding (30 min, gravado): sorteie um problema das semanas 1 a 4 e resolva explicando em voz alta, como numa entrevista. | Simulado de entrevista de coding (30 min, gravado): sorteie um problema das semanas 6 a 8 e resolva explicando em voz alta, como numa entrevista. |
| Qua | Revisão de complexidade: escreva de memória a complexidade de tempo e espaço de cada problema até aqui, confira e transforme os erros em flashcards. | Revisão de complexidade: escreva de memória a complexidade de tempo e espaço de cada problema até aqui, confira e transforme os erros em flashcards. |

Resolva sem IA, com limite de 30 minutos. Método e lista completa: [trilha de DSA](../DSA.pt-BR.md).

## Checklist de code review

Leia em voz alta antes de cada revisão:

1. Dinheiro em float?
2. Operação não idempotente com retry?
3. Leitura e escrita sem transação ou lock?
4. Chamada externa dentro de transação de banco?
5. Erro engolido, ou status desconhecido tratado como falha?
6. Segredo ou dado pessoal em log?
7. Falta de timeout?
8. (A partir do módulo 5) Consumidor sem dedupe?
9. (A partir do módulo 6) Lançamento que não fecha em zero?
