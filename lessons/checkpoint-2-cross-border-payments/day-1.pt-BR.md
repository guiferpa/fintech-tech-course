# Checkpoint 2, segunda-feira: pagamentos cross-border

[Checkpoint 2](../../modules/checkpoints.pt-BR.md) · [Read in English](day-1.md)

**Tempo de leitura:** cerca de 45 minutos. Use o resto do bloco de 2 horas nas referências do final, e reserve a noite para o laboratório no papel da seção 8.

Este é um texto original escrito para este curso. Ele se baseia nas referências listadas no final, e cada seção indica a fonte que segue. Quando um número ou uma regra vem de uma empresa ou de um regulador específico, o texto diz isso.

## Por que isso importa para uma fintech

Os módulos 5 a 7 construíram uma carteira digital que move reais dentro do Brasil. Uma pergunta de follow-up comum em entrevista é "e se o usuário quiser mandar US$ 100 para um freelancer nos Estados Unidos?". Essa pergunta toca tudo o que você estudou, mais três problemas novos: um preço que muda a cada segundo, uma cadeia de bancos que você não controla e regras de dois países.

Leia isto como uma revisão com um caso novo: cada seção reaproveita idempotency keys, máquinas de estado, holds, lançamentos por moeda ou reconciliação, o que também prepara o system design gravado de quarta-feira.

## 1. Como o dinheiro realmente atravessa a fronteira

*Fonte principal: blog da Wise, "What is a correspondent bank?" e "How to use Nostro/Vostro account when sending to India".*

O dinheiro não viaja; saldos mudam em livros de dois países. Um banco brasileiro sem conta nos Estados Unidos precisa de um banco que tenha. A Wise resume assim: "Correspondent banks are usually involved when sending payments to foreign countries through SWIFT."

O encanamento é uma conta vista de dois lados. A Wise define uma conta **nostro** como "an account held by a domestic bank at a foreign correspondent bank", e uma conta **vostro** como "an account held by a foreign correspondent bank at a domestic bank". Nostro quer dizer "nossa conta, nos seus livros"; vostro quer dizer "sua conta, nos nossos livros". Os bancos mantêm essas contas para "maintain a pool of funds in each other's currencies".

Então um pagamento do Brasil para os EUA funciona assim. O banco brasileiro debita o cliente em BRL e compra USD. Ele envia uma instrução ao seu correspondente nos EUA (uma mensagem, ainda sem dinheiro). O correspondente debita a nostro em USD do banco brasileiro e paga o banco do beneficiário, direto ou por meio de outro intermediário. O banco do beneficiário credita o freelancer.

Cada salto leva tempo e cobra uma tarifa. A Wise diz que o correspondente "will deduct their service fee from the transferred funds", e que "25 USD - 75 USD are common", embora os custos variem muito. É por isso que o freelancer pode receber menos de US$ 100 (seção 4).

Provedores como a Wise usam contas bancárias locais em cada país: o dinheiro entra localmente e sai localmente (seção 5). Ainda é o raciocínio de nostro/vostro, com pools pré-financiados por moeda.

## 2. As mensagens: SWIFT e ISO 20022 na prática

*Fonte principal: ING Wholesale Banking, "ISO 20022 SWIFT CBPR+ update"; J.P. Morgan, "ISO 20022 FAQs".*

O SWIFT é a rede de mensagens entre bancos. Ele carrega instruções, não dinheiro. Por décadas, a transferência de cliente foi a **MT103**, uma mensagem de texto com campos numerados. Os bancos migraram para o **ISO 20022**, um padrão XML, num programa chamado CBPR+. A página do ING diz: "Since 22 November 2025, MT payment instructions such as MT103, MT200 and MT202(COV) have been replaced". O mapeamento que você precisa saber:

| Mensagem MT antiga | Mensagem ISO 20022 | Finalidade |
| --- | --- | --- |
| MT103 | pacs.008 | Transferência de cliente |
| MT200 / MT202 | pacs.009 | Transferência entre instituições financeiras |
| Devolução MT103/MT202 | pacs.004 | Devolução de recursos |
| (nenhuma) | pacs.002 | Relatório de status do pagamento |
| Extratos MT940 | camt.053 | Extrato da conta bancária |

O ING acrescenta que os extratos MT e CAMT convivem até novembro de 2028, então você ainda vai encontrar arquivos MT940.

O ISO 20022 carrega dados estruturados que o seu código pode usar. O FAQ do J.P. Morgan destaca três itens:

- **UETR**, uma referência única de ponta a ponta que acompanha cada pagamento. Guarde-a na sua transferência, como você guardou o `end_to_end_id` do Pix no Módulo 7.
- **Endereços estruturados.** A partir de novembro de 2026, diz o J.P. Morgan, o endereço "must be provided in a structured or hybrid manner" em pagamentos CBPR+, com pelo menos cidade e país. O seu formulário de destinatário precisa de campos separados.
- **Códigos de finalidade.** Alguns corredores exigem: o J.P. Morgan cita pagamentos offshore para as Filipinas e pagamentos imobiliários via CHAPS no Reino Unido (códigos como HLRP e PDEP).

O seu provedor monta o pacs.008, mas o seu modelo de dados precisa guardar tudo o que ele exige.

## 3. Cotações de câmbio: taxa, spread e expiração

*Fonte principal: documentação da Stripe, "Enable currency conversion using the FX Quotes API"; referência da API Wise Platform, "Quote" e "Types of quotes"; Central de Ajuda da Wise, "What's a guaranteed rate?".*

Uma cotação de câmbio é uma promessa com prazo: você pode converter por esta taxa até este horário. A FX Quotes API da Stripe (um produto em preview) devolve um `fx_quote` com `lock_duration` (`five_minutes`, `hour`, `day` ou `none`), um `lock_expires_at` e um `lock_status`. A resposta de exemplo decompõe o preço:

| Campo | Exemplo | Significado |
| --- | --- | --- |
| `reference_rate` | 1.0827 (`ecb`) | Taxa de referência pública |
| `base_rate` | 1.08295 | Taxa da Stripe antes das tarifas |
| `fx_fee_rate` | 0.02 | A tarifa de câmbio |
| `duration_premium` | 0.0007 | O preço da trava |
| `exchange_rate` | 1.06053 | A taxa aplicada |

Isso é **spread**: a distância entre uma taxa de referência e a taxa do cliente, composta de tarifas e de um prêmio pelo risco de mercado que o provedor carrega durante a trava. A Stripe coloca o BRL no seu Grupo 2: 0,12% para cinco minutos, 0,15% para uma hora, 0,30% para 24 horas. No Brasil, pagamentos podem travar por cinco minutos ou uma hora; travas para transfers não são suportadas.

Dois comportamentos importam. Uma trava pode acabar antes: "If an exchange rate exceeds the rate threshold for payments or transfers, the extended rate quote is invalidated and the `lock_status` changes to `expired`." E uma cotação expirada falha de forma explícita: anexá-la a um PaymentIntent ou Transfer devolve `400` (por exemplo `payment_intent_fx_quote_invalid`), e a Stripe envia um webhook `fx_quote.expired`.

A Wise usa as mesmas ideias: `rate`, `rateType` (`FIXED` ou `FLOATING`), `expirationTime`, `rateExpirationTime` e os status `PENDING`, `ACCEPTED`, `FUNDED`, `EXPIRED`. Cotações não autenticadas "are for illustrative purposes only"; as autenticadas devolvem um ID para criar a transferência, e "The rate is locked for 30 minutes to give a user time to submit the transfer." A página de ajuda acrescenta dois casos de borda. Se o dinheiro chega depois da trava, a Wise usa "the live mid-market rate at the time we receive your funds". E: "We cannot guarantee the rate if we only receive part of your money."

A Ana viu R$ 550,00 por US$ 100,00; cobrar qualquer outro valor é bug. Então a cotação é uma linha gravada que uma única transferência consome, antes de expirar:

```sql
CREATE TABLE fx_quotes (
  id                uuid PRIMARY KEY,
  wallet_id         uuid NOT NULL,
  source_amount     bigint NOT NULL,        -- BRL, em centavos
  target_amount     bigint NOT NULL,        -- USD, em centavos
  rate              numeric(20,10) NOT NULL,
  fee_amount        bigint NOT NULL,
  provider_quote_id text NOT NULL,
  expires_at        timestamptz NOT NULL,   -- expiração do provedor menos uma margem
  status            text NOT NULL CHECK (status IN ('open','used','expired')),
  transfer_id       uuid UNIQUE             -- uma transferência por cotação
);

UPDATE fx_quotes SET status = 'used', transfer_id = $2
 WHERE id = $1 AND status = 'open' AND expires_at > now()
RETURNING *;
```

Zero linhas significa expirada ou já usada: peça à Ana que confirme uma taxa nova, nunca recote em silêncio. `POST /quotes` aceita uma idempotency key, para que um toque duplo não crie duas travas. E a referência de cliente que você envia ao provedor é gerada uma vez e gravada antes da chamada. O `customerTransactionId` da Wise é um "Unique identifier randomly generated per transfer request by the calling client"; um retry envia o mesmo valor.

O lado do ledger da conversão (quatro contas, balanceadas por moeda, com a taxa cotada gravada na transação) está no [Módulo 6, quarta-feira, seção 6](../06-ledgers-and-accounting/day-3.pt-BR.md#6-moeda-em-todo-lançamento). Releia lá em vez de repetir aqui.

## 4. Tarifas e cut-offs: por que o valor e a data mudam

*Fonte principal: Nium Developer Hub, "FAQ"; Revolut Business Help, "SWIFT transfer options and fees"; Banking Circle, "Currencies & Cut-Off Times"; documentação da Adyen, "Send funds to third parties".*

Um pagamento SWIFT carrega um código de tarifa. O FAQ da Nium descreve três:

| Código | Quem paga | O beneficiário recebe |
| --- | --- | --- |
| OUR | O remetente, antecipado | O valor integral |
| SHA | Compartilhado | Possivelmente menos, após descontos |
| BEN | O beneficiário | O valor menos as tarifas |

A Revolut explica a armadilha do SHA: bancos intermediários "may also charge fees, which are generally deducted from the amount being transferred". A tela de cotação precisa dizer qual código se aplica. A reconciliação precisa esperar um valor recebido menor em SHA ou BEN, com um código de motivo próprio, e não um "valor diferente" genérico do Módulo 7.

Cada moeda tem um **cut-off** diário para execução no mesmo dia. A tabela do Banking Circle (CET/CEST) mostra SEPA em lote (EUR) às 14:00, EUR SWIFT às 16:00, GBP CHAPS às 17:45, USD SWIFT às 18:30, e SEPA Instant e UK Faster Payments 24/7. JPY via SWIFT vai aos correspondentes com data-valor D+1. Os recursos só saem depois que a operação de câmbio liquida, e "payments will not be processed on public holidays." A Adyen diz o mesmo: depois do cut-off, as solicitações passam para o dia seguinte (por exemplo, USD Regular às 01:45 ET).

Então cada transferência tem uma **data de liquidação esperada** (moeda, trilho, cut-off, dois calendários de feriados). Grave-a e deixe a reconciliação sinalizar as transferências que passarem dela.

## 5. Pagando em trilhos locais por meio de um provedor

*Fonte principal: documentação da Stripe, "Global Payouts" e "Payout methods and amounts"; documentação da Adyen, "Send funds to third parties"; documentação da Wise Platform, "Transfer statuses".*

A maioria das fintechs chama um provedor que paga no trilho doméstico do destinatário. O Stripe Global Payouts alcança "more than 160 countries" e é voltado a empresas que já têm uma Money Transmitter License. Para um remetente nos EUA, a tabela lista ACH (normalmente até 1 dia útil), UK FPS (tempo real), SEPA (normalmente 1 dia útil) e, nos demais países, um trilho `local` ou um wire, normalmente de 1 a 7 dias. Vale copiar um exemplo: as duas moedas precisam passar pelos seus mínimos. Enviar 3 USD para a África do Sul falha, porque isso dá 55,63 ZAR e o mínimo em ZAR é 100. Valide os dois lados antes de travar uma cotação.

A Adyen separa **local payouts** (o sistema de compensação do país do beneficiário) de **cross-border payouts**, em que "the only priority supported for cross-border payouts is crossBorder" e a chegada não é garantida.

Os status de transferência da Wise se encaixam quase um a um na máquina de estados de hoje à noite:

| Status na Wise | Significado |
| --- | --- |
| `incoming_payment_waiting` | Criada, aguardando os recursos |
| `processing` | Recursos recebidos; checagens de AML, compliance e fraude |
| `funds_converted` | Checagens feitas, convertido para a moeda de destino |
| `outgoing_payment_sent` | Pago; final "assuming funds will not be returned" |
| `bounced_back` | Devolvido, ainda não reembolsado |
| `funds_refunded` / `cancelled` | Reembolsado após o financiamento / nunca financiado |

"Enviado" não é "recebido": `outgoing_payment_sent` pode virar `bounced_back` dias depois, quando o banco do beneficiário rejeita uma conta. O seu estado `PAID_OUT` não é terminal para a reconciliação.

## 6. Compliance: triagem de sanções e códigos de finalidade

*Fonte principal: Tesouro dos EUA, OFAC, "Sanctions List Search Tool" e FAQs 91 e 247 a 251; Banco Central do Brasil, Resolução BCB nº 277, arts. 4º a 6º.*

Antes de o dinheiro sair, remetente e beneficiário passam por triagem. A lista mais conhecida é a SDN List da OFAC. O FAQ 91 diz que bens de pessoas da SDN sob jurisdição dos EUA ficam bloqueados e que pessoas dos EUA são, em geral, proibidas de negociar com elas. Entidades detidas em "50 percent or more by one or more blocked persons" ficam bloqueadas mesmo sem estar na lista.

A triagem é matching aproximado, com falsos positivos. A ferramenta de busca da OFAC "employs fuzzy logic on its name search field" (FAQ 249: Jaro-Winkler e Soundex). O FAQ 250 diz que a OFAC não recomenda um limiar: os usuários "must make their own match threshold determinations". Na carteira digital, um possível match é um estado, `COMPLIANCE_REVIEW`. O hold mantém os recursos reservados até um analista liberar ou bloquear. Nunca faça retry ou estorno automático de um hit.

**Códigos de finalidade** dizem por que o dinheiro se move. No Brasil, a Resolução BCB nº 277, art. 4º, atribui ao cliente a responsabilidade pela classificação da finalidade, e a instituição precisa apresentar os códigos de forma compreensível. O Anexo V lista códigos como 34124 (transferência entre conta no país e conta no exterior de mesma titularidade) e 34155 (transferências unilaterais). O art. 6º diz que uma devolução usa o código da operação original. Então o código de finalidade é um campo obrigatório, escolhido pelo cliente e copiado para qualquer devolução.

## 7. O lado brasileiro: câmbio, VET e eFX

*Fonte principal: Banco Central do Brasil, "Cartilha de Câmbio 2026"; Resolução BCB nº 277/2022 e Resolução BCB nº 561/2026.*

No Brasil, converter reais em moeda estrangeira é uma operação de câmbio, feita por uma instituição autorizada pelo BCB. A cartilha de 2026 do BCB inclui entre elas bancos, corretoras e instituições de pagamento, e diz que o cliente "deve ser identificado". Para uma remessa ao exterior, ela pede os dados do beneficiário, incluindo "motivo da remessa, banco, agência e número da conta".

A cartilha define o **VET (Valor Efetivo Total)** como "o total de reais entregues ou recebidos por unidade de moeda estrangeira", incluindo a taxa, o IOF e as tarifas. A Resolução BCB nº 277, art. 18, exige informá-lo antes de operações à vista de até US$ 100.000, e a cartilha diz que ele deve constar no contrato de câmbio ou no recibo. Na sua tela de cotação, isso é um número só: R$ por US$, com tudo incluído.

**eFX** é o prestador de serviço de pagamento ou transferência internacional. A cartilha diz que esses prestadores costumam operar por meio de parcerias no exterior e de canais digitais. A Resolução BCB nº 561, de 30 de abril de 2026, com vigência a partir de 1º de outubro de 2026, reescreveu as regras:

- Limites de US$ 10.000 valem para compras por solução de pagamento digital sem integração a plataforma de comércio eletrônico e para transferências ligadas a investimentos.
- O pagamento à contraparte no exterior usa apenas os meios listados, "sendo vedado o uso de ativos virtuais".
- "É vedada a compensação pelo prestador de eFX entre os reais recebidos do usuário e os reais entregues ao usuário."
- Sem conta de reservas ou de liquidação no BCB, a conta do prestador deve ficar em instituição autorizada a operar em câmbio, com o eFX como propósito único.
- Prestadores ainda não autorizados devem pedir autorização como instituição de pagamento até 31 de maio de 2027.

Por causa da vedação à compensação, os reais que entram e saem de cada usuário precisam ser rastreáveis separadamente, e é isso que um ledger por transação oferece.

Pix cross-border: a única declaração oficial verificada aqui é a nota da cartilha de que, em alguns destinos, "turistas brasileiros já conseguem utilizar o Pix para realizar pagamentos em determinados estabelecimentos". Trate qualquer coisa além disso como não verificada até ler numa página do BCB.

## 8. O laboratório de hoje: uma transferência cross-border no papel

Sem código. A Ana envia US$ 100,00 da carteira em BRL para a conta bancária de um freelancer nos EUA, por meio de um provedor de payouts.

1. **Máquina de estados.** Comece com `QUOTED`, `QUOTE_EXPIRED`, `FUNDS_HELD`, `COMPLIANCE_REVIEW`, `BLOCKED`, `DEBITED`, `CONVERTED`, `PAYOUT_SUBMITTED`, `UNKNOWN`, `PAID_OUT`, `RETURNED`, `REFUNDED`, `RECONCILED`. Para cada transição, escreva o gatilho (chamada de API, webhook, timeout, arquivo) e a idempotency key. Para `UNKNOWN`, aplique a regra do Módulo 7: consulte o status primeiro.
2. **Cotação.** Preencha a linha da cotação com números reais: expiração do provedor, sua margem, o VET, o código de tarifa e o código de finalidade.
3. **Ledger por moeda.** Escreva os lançamentos de hold, débito e tarifa, conversão, envio do payout, liquidação do payout e um bounce com reembolso. Cada um balanceia em BRL e em USD separadamente. Contas sugeridas: Carteira: Ana (BRL), Receita de tarifas (BRL), Pool de câmbio (BRL), Pool de câmbio (USD), A pagar ao provedor (USD), Caixa no provedor (USD). Decida quem absorve a diferença cambial quando um bounce volta depois que a taxa mudou.
4. **Reconciliação.** Liste os arquivos (relatório de transferências do provedor, extrato de saldo do provedor, confirmações de câmbio) e a chave de matching de cada um: o seu ID, o ID do provedor, o UETR. Acrescente uma regra para descontos SHA e uma para a data de liquidação esperada.

## O que anotar hoje

1. Nostro, vostro e os saltos de um pagamento do Brasil para os EUA.
2. De MT para ISO 20022 (pacs.008, pacs.009, pacs.004, pacs.002, camt.053), mais UETR, endereço estruturado e finalidade no seu modelo.
3. Regras de cotação: referência, base, tarifa e prêmio; trava e invalidação antecipada; o SQL de consumo único; a resposta para cotação expirada.
4. OUR, SHA e BEN e o efeito de cada um na reconciliação. Cut-offs, data-valor e data de liquidação esperada.
5. Regras brasileiras: quem opera câmbio, VET, códigos de finalidade e os pontos de eFX da Resolução BCB nº 561.
6. O resultado do laboratório: máquina de estados, linha da cotação e lançamentos por moeda.

## Teste-se

Estas perguntas dão bons flashcards (veja o [guia de flashcards](../../FLASHCARDS.pt-BR.md)).

- Qual a diferença entre uma conta nostro e uma conta vostro, e por que é a mesma conta?
- Qual mensagem ISO 20022 substituiu a MT103, e qual carrega uma devolução?
- Na cotação da Stripe, o que preenche a distância entre `reference_rate` e `exchange_rate`?
- Como garantir que uma cotação seja usada por no máximo uma transferência, e só antes de expirar?
- Com SHA, por que o freelancer pode receber menos de US$ 100, e como a reconciliação deve classificar isso?
- Por que `outgoing_payment_sent` não é final para o seu job de reconciliação?
- O que é o VET, o que ele inclui e quando precisa ser informado?

## Referências

- **Fonte principal:** Wise, ["What is a correspondent bank?"](https://wise.com/us/blog/what-is-a-correspondent-bank) e ["How to use Nostro/Vostro account when sending to India"](https://wise.com/in/blog/nostro-and-vostro-account). Gratuito.
- **Fonte principal:** ING Wholesale Banking, ["ISO 20022 SWIFT CBPR+ update"](https://www.ingwb.com/en/service/payments-and-collections/iso20022-swift-cbpr-update) (datas e mapeamento), e J.P. Morgan, ["ISO 20022 FAQs"](https://www.jpmorgan.com/insights/payments/fx-cross-border/iso-20022-faqs) (UETR, endereços, códigos de finalidade). Gratuito.
- **Fonte principal:** documentação da Stripe, ["Enable currency conversion using the FX Quotes API"](https://docs.stripe.com/payments/custom/localize-prices/fx-quotes-api). Gratuito.
- Wise, ["Quote"](https://docs.wise.com/api-reference/quote), ["Types of quotes"](https://docs.wise.com/api-reference/quote/types-of-quotes), ["What's a guaranteed rate?"](https://www.wise.com/help/articles/2448203/whats-a-guaranteed-rate) e ["Transfer statuses"](https://docs.wise.com/guides/product/send-money/tracking/transfer-statuses). Gratuito.
- Nium, ["FAQ"](https://mpdocs.nium.com/payout-payin/faq-s), e Revolut Business, ["SWIFT transfer options and fees"](https://help.revolut.com/business/help/receiving-payments/sending-money-to-an-external-bank-account/question-fees-swift-transfers), para OUR, SHA e BEN. Gratuito.
- Banking Circle, ["Currencies & Cut-Off Times"](https://www.bankingcircle.com/currencies-and-cut-off-times), e Adyen, ["Send funds to third parties"](https://docs.adyen.com/marketplaces/custom-payouts). Gratuito.
- Documentação da Stripe, ["Global Payouts"](https://docs.stripe.com/global-payouts) e ["Payout methods and amounts"](https://docs.stripe.com/global-payouts/payout-methods). Gratuito.
- OFAC, ["Sanctions List Search Tool"](https://ofac.treasury.gov/sanctions-list-search-tool), [FAQ 91](https://ofac.treasury.gov/faqs/91) e os [FAQs do Sanctions List Search](https://ofac.treasury.gov/faqs/topic/1636/print) (247 a 251). Gratuito.
- **Fonte principal:** Banco Central do Brasil, ["Cartilha de Câmbio 2026"](https://www.bcb.gov.br/content/estabilidadefinanceira/politica_cambial/Cartilha_cambio_2026.pdf); [Resolução BCB nº 277](https://www.bcb.gov.br/estabilidadefinanceira/exibenormativo?tipo=Resolu%C3%A7%C3%A3o%20BCB&numero=277) (arts. 4º a 6º e 18) e [Resolução BCB nº 561](https://www.bcb.gov.br/estabilidadefinanceira/exibenormativo?tipo=Resolu%C3%A7%C3%A3o%20BCB&numero=561). Gratuito.
