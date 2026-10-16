# Módulo 7, quarta-feira: reconciliação e fallback seguro entre provedores

[Módulo 7](../../modules/07-payments-pix-reconciliation.pt-BR.md) · [Read in English](day-3.md)

**Tempo de leitura:** cerca de 45 minutos. Use o resto do bloco de 2 horas nas referências do final e depois desenhe o diagrama de fallback descrito na seção 5.

Este é um texto original escrito para este curso. Ele se baseia nas referências listadas no final, e cada seção indica a fonte que segue. Quando uma ideia vem de um autor específico, o texto diz isso.

## Por que isso importa para uma fintech

Na segunda-feira você viu que cada parte de um pagamento mantém seu próprio registro. Seu ledger diz uma coisa, o arquivo de liquidação do adquirente diz outra e o extrato do banco parceiro diz uma terceira. Em geral eles concordam. Quando não concordam, alguém está perdendo dinheiro: o cliente, o lojista ou você. A **reconciliação** é o processo que compara esses registros e transforma cada divergência em um ticket antes que ela vire prejuízo.

O teste de domínio do módulo pergunta o que acontece quando um pagamento mostrado como "aprovado" não aparece no arquivo de liquidação do dia seguinte. Hoje você recebe a resposta completa: como casar registros, quanta tolerância permitir, o que fazer com o que não casa e como trocar de provedor durante uma queda sem cobrar ninguém duas vezes.

## 1. O que é reconciliação

*Fonte principal: documentação da Modern Treasury, "Reconciling received payments".*

A reconciliação compara duas visões do mesmo dinheiro: **o que você esperava que acontecesse** e **o que o banco ou provedor diz que aconteceu**. A Modern Treasury transforma a primeira visão em um objeto explícito. Um Expected Payment serve para "represent and reconcile a payment that you expect to receive or send (e.g., an invoice)." A segunda visão é a **Transaction**, uma linha informada pela instituição financeira. Reconciliar é ligar cada Transaction aos Expected Payments que ela paga.

Duas regras dessa página moldam qualquer motor de reconciliação:

- **Todas as condições precisam bater.** A documentação diz que um Expected Payment só reconcilia com uma Transaction "if all of the defined conditions are matched." Um match parcial não é match.
- **Ambiguidade nunca é resolvida automaticamente.** "When multiple Expected Payments match the details of a transaction, they won't be automatically reconciled." Em vez disso, eles são sinalizados para revisão manual.

A segunda regra é a importante. Um matcher que chuta entre dois candidatos vai às vezes chutar errado, e o erro então se esconde dentro de um status "reconciliado" para o qual ninguém olha. Um matcher que se recusa a chutar gera mais trabalho manual, mas nunca mente.

Na sua carteira, o lado esperado é o ledger. Todo pagamento com cartão capturado, todo Pix de saída e todo estorno cria uma expectativa: "o adquirente vai liquidar este valor para esta referência nesta data ou perto dela". O lado real é o CSV de liquidação dos seus adquirentes falsos.

## 2. Regras de matching e tolerâncias

*Fonte principal: documentação da Modern Treasury, "Defining Reconciliation Rules", "Advanced Matching Using Expected Payments" e "Valid conditions for Reconciliation Rules".*

Uma **regra de reconciliação** é uma lógica de matching: uma lista de condições que precisam ser verdadeiras para os registros reconciliarem. Cada condição é um campo, um operador e um valor. O valor pode ser uma constante (moeda igual a BRL) ou um campo do outro lado (direção da transaction igual à direção do expected payment). As condições podem ser agrupadas com AND e OR.

**A ordem importa.** A documentação diz que as regras "are evaluated sequentially, starting with the first rule and finishing with the last rule." Ela recomenda colocar primeiro as regras específicas, como as que casam por um identificador único, e depois as mais amplas. Na sua carteira, a primeira regra é "mesmo `acquirer_ref` ou mesmo `end_to_end_id`". Uma regra de reserva poderia ser "mesmo valor, mesmo dia, mesmo cliente", mas só se ela produzir exatamente um candidato.

**Cardinalidade.** A documentação lista três estratégias:

| Estratégia | Exemplo numa carteira |
| --- | --- |
| Uma transaction para um expected payment | Uma linha de liquidação para um pagamento capturado |
| Uma transaction para vários expected payments | O adquirente paga um valor único por um dia inteiro de capturas |
| Várias transactions para um expected payment | Um pagamento liquidado em parcelas |

A documentação dá um exemplo da segunda estratégia: "a $100 Transaction reconciles to a group of three Expected Payments with amounts of $10, $20, $70." Na terceira, um Expected Payment fica reconciliado "once the sum of the amounts of its reconciled Transactions equals its amount."

**Tolerâncias.** Valores e datas reais variam. A Modern Treasury oferece três tipos de tolerância:

- **Faixa de valor.** Um Expected Payment pode ter `amount_lower_bound` e `amount_upper_bound`, e uma Transaction reconcilia quando seu valor cai dentro da faixa. Isso absorve taxas, impostos ou variação cambial.
- **Variação de valor em matches agrupados.** Regras de um para vários aceitam uma variação do tipo `fixed` (na menor unidade da moeda, então 500 significa US$5) ou `percentage`.
- **Janela de data.** O `as_of_date` da Transaction precisa cair entre o `date_lower_bound` e o `date_upper_bound` do Expected Payment.

Tolerância é uma decisão de negócio, não técnica. Se o seu adquirente desconta uma taxa de 2,5%, compare o valor líquido do arquivo com o bruto menos a taxa esperada, e deixe a tolerância só para arredondamento (um ou dois centavos). Uma tolerância larga esconde erros reais. Para datas, uma janela de um ou dois dias úteis em torno da data esperada de liquidação pega feriados e arquivos atrasados sem esconder um pagamento que nunca chegou.

## 3. Divergências e como reportá-las

*Fonte principal: documentação da Modern Treasury, "Exception Handling - Manual Reconciliation", aplicada aos tipos de divergência do TCM.*

O que as regras automáticas não conseguem casar vai para a reconciliação manual. A interface da Modern Treasury mostra as Transactions não reconciliadas ao lado dos Expected Payments, exibe a diferença entre os itens selecionados (a documentação observa que "In most cases, this will be 0") e deixa um operador reconciliá-los, ajustando valores quando necessário. Cada reconciliação manual dispara um webhook, para que outros sistemas fiquem sabendo.

O job do seu TCM não terá interface, mas precisa do mesmo resultado: todo registro termina casado ou em um **relatório de divergências** com um tipo claro. O módulo lista quatro divergências plantadas. Aqui estão elas, mais uma quinta que o job também deve detectar:

| Tipo | O que você vê | Causa provável | Primeira ação |
| --- | --- | --- | --- |
| Faltando no arquivo | O ledger tem um pagamento capturado; não há linha de liquidação | A captura nunca chegou ao adquirente, ou o arquivo está atrasado | Consultar o status no adquirente para aquela referência |
| Faltando no ledger | Linha de liquidação sem lançamento no ledger | Sua captura deu timeout, o adquirente processou, você marcou como falha | Consultar o status; fazer o lançamento que falta ou estornar |
| Duplicado | Duas linhas de liquidação para uma referência | Retry sem idempotência no adquirente, ou arquivo carregado duas vezes | Conferir os ids dos arquivos; se for real, estornar a cobrança extra |
| Valor diferente | Mesma referência, valores diferentes além da tolerância | Captura parcial, taxa errada, erro de moeda | Comparar com a autorização e com o contrato |
| Data trocada | Casado, mas fora da janela de data | Feriado, batch atrasado, bug de fuso horário | Sinalizar; escalar se repetir |

Um full outer join é a primeira passada natural no Postgres. Ele encontra os dois tipos de "faltando" em uma única consulta. Carregue antes cada CSV em uma tabela de staging, normalizada para um formato só.

```sql
SELECT l.payment_id, s.acquirer_ref,
       l.amount_cents  AS ledger_cents,
       s.net_cents     AS file_cents,
       CASE
         WHEN s.acquirer_ref IS NULL THEN 'MISSING_IN_FILE'
         WHEN l.payment_id  IS NULL THEN 'MISSING_IN_LEDGER'
         WHEN abs(l.expected_net_cents - s.net_cents) > 1 THEN 'AMOUNT_MISMATCH'
         WHEN s.settlement_date NOT BETWEEN l.expected_date - 1 AND l.expected_date + 2
              THEN 'DATE_MISMATCH'
         ELSE 'MATCHED'
       END AS result
FROM ledger_expected l
FULL OUTER JOIN settlement_staging s ON s.acquirer_ref = l.acquirer_ref;
```

Duplicados precisam de uma verificação separada antes do join (`GROUP BY acquirer_ref HAVING count(*) > 1`); caso contrário, o join produz em silêncio duas linhas "casadas". Mais duas regras práticas: grave o relatório em uma tabela com o id da execução, para ver como uma divergência evolui ao longo dos dias; e nunca deixe o job de reconciliação alterar o ledger sozinho. Ele reporta, e uma ação separada e auditada corrige.

## 4. Integridade transacional no Airbnb

*Fonte principal: Airbnb Engineering, "Measuring Transactional Integrity in Airbnb's Distributed Payment Ecosystem", seções "What is transactional integrity?", "What is an out-of-sync transaction?" e "Payment reconciliation using traditional tools is not sufficient".*

Os autores do Airbnb (Ninad Khisti e William Betz) definem o objetivo em uma frase: "When it comes to payments, transactional integrity represents a no-surprise, accurate money movement." O Airbnb usa vários gateways e dezenas de processadores, e cada parte extra adiciona um ponto onde uma transação pode ficar **fora de sincronia** (out of sync): um lado acredita em algo diferente do outro. O post cita as causas. Um sistema da cadeia não responde, um sistema seguinte trata mal uma resposta, ou um processo em batch com um banco deixa os sistemas fora de sincronia até os arquivos de resposta chegarem.

A parte mais útil do post explica por que a reconciliação clássica não bastava para eles. Ferramentas tradicionais dão "only an overall picture", sem resultados para cada etapa do processo. Elas também só reconciliam "when money exchanges hands", pulam transações já casadas e casam por atributos de identificação em vez de comparar tudo. O pipeline do Airbnb faz o contrário:

- **Compara toda transação**, inclusive as que não movem dinheiro, como cancelamentos (voids).
- **Compara todo atributo**: valor, moeda, status, meio de pagamento e tempo, não só o id.
- **Compara toda etapa**: bases internas contra dados do gateway contra relatórios do processador.
- **Mede desde o dia zero**, o dia em que o novo gateway começou a receber tráfego real.

A mecânica é em batch: os processadores enviam relatórios diários, que chegam ao S3; snapshots do banco vão para o HDFS em intervalos regulares; o Hive compara os schemas; e as anomalias são agrupadas por tipo. Dashboards no Superset, apoiados no Druid, mostram uma nota de integridade por categoria (pagamentos, estornos, repasses e devoluções). Alertas saem por e-mail ou Slack depois de cada execução do pipeline, inclusive quando o relatório de um processador está faltando ou atrasado.

Os resultados que o post relata devem soar familiares depois de segunda-feira. A análise os ajudou a ajustar "socket timeouts, error handling, and retry mechanisms" e reduziu tickets de suporte de alto volume. Os planos futuros incluem idempotência mais forte, porque retries seguros exigem a garantia de que o dinheiro se move uma única vez.

Para a sua carteira, duas ideias se transferem diretamente. Primeiro, um arquivo de liquidação faltando ou atrasado é em si uma divergência e deve acionar alguém. Segundo, compare status e tempo, não só valor: um pagamento `CAPTURED` no seu ledger e `VOIDED` no adquirente tem ids e valores iguais, e mesmo assim está errado.

## 5. Orquestração de provedores: roteamento e fallback seguro

*Fonte principal: nenhuma referência única. Esta seção combina a regra do desfecho desconhecido do Módulo 1, as regras de lease e de consulta de status do post do Airbnb de segunda-feira e o modelo de tentativas do Payment Intents da Stripe.*

Uma carteira com dois adquirentes quer usar o segundo quando o primeiro falha. Roteamento (escolher um provedor por pagamento) é simples: por custo, por bandeira, por saúde do provedor ou por divisão percentual. **Fallback** (tentar outro provedor para o mesmo pagamento) é de onde vêm as cobranças duplicadas.

A armadilha é o timeout. Sua chamada ao adquirente A dá timeout. Se você envia na hora o mesmo pagamento ao adquirente B, e A na verdade tinha aprovado, o cliente é cobrado duas vezes. Lembre do Módulo 1: um timeout significa "não sei". A regra que este módulo pede para você desenhar é:

**timeout → consulta de status → só então outro provedor.**

```text
chama A (idem key k-A) ──► sucesso ──────────────► fim (A)
        │
        ├─► recusa definitiva (4XX, non-retryable) ─► parar ou tentar B (nova tentativa)
        │
        └─► timeout / 5XX ──► tentativa = UNKNOWN
                               │
                               ▼
                consulta status em A por k-A (com backoff, após o lease de A)
                               │
              ┌────────────────┼──────────────────┐
              ▼                ▼                  ▼
      achou: aprovado    achou: falhou     continua desconhecido
      → fim (A)          → tentar B        → seguir esperando; ou cancelar
                                              em A e confirmar; nunca tentar B
```

As regras que tornam isso seguro:

- **Um pagamento, várias tentativas.** Cada chamada a um provedor é uma linha em `payment_attempts` com sua própria idempotency key. Retries para o mesmo provedor reutilizam a chave; um fallback para B cria uma nova tentativa com uma nova chave.
- **No máximo uma tentativa viva.** Um índice único parcial impede uma segunda tentativa enquanto houver uma pendente ou desconhecida:

```sql
CREATE UNIQUE INDEX one_live_attempt_per_payment
  ON payment_attempts (payment_id)
  WHERE state IN ('PENDING', 'UNKNOWN', 'COMPLETED');
```

  Com esse índice, o próprio banco se recusa a iniciar a tentativa B enquanto a tentativa A estiver `UNKNOWN` ou `COMPLETED`. Só uma tentativa que falhou libera a vaga.
- **Decida com base em fatos.** Mova uma tentativa para `FAILED_FINAL` só quando o provedor disser isso: uma recusa definitiva, uma consulta de status dizendo "falhou" ou um cancelamento confirmado. "Não encontrado" logo depois de um timeout não é prova, porque a requisição ainda pode estar em trânsito. Espere passar o lease ou a janela de processamento do provedor e consulte de novo.
- **Sucesso atrasado continua sendo sucesso.** Se a aprovação de A chegar (por webhook ou consulta) depois que você desistiu, registre-a e cancele ou estorne na hora. A reconciliação pegaria isso de qualquer forma, como uma linha "faltando no ledger".
- **Abra o circuit breaker por provedor.** Quando a taxa de erro de A subir, roteie os pagamentos novos para B. Só os novos: os que já foram enviados a A ficam com A até serem resolvidos. O Módulo 9 trata de circuit breakers em profundidade.

O critério de aprovação do TCM é "o fallback nunca cobra nos dois provedores". O índice acima e a consulta de status são como você prova isso. Seu teste deve injetar um timeout em A depois que A registra a cobrança, e então verificar que B nunca foi chamado.

## 6. Preparando o TCM

*Fonte principal: o laboratório de quarta-feira na página do módulo e as tarefas de quinta e sexta.*

O laboratório de hoje produz insumos, não código: arquivos CSV com divergências plantadas e uma lista de tarefas para quinta e sexta. Plante de propósito e anote o resultado esperado de cada uma, para que o teste de sexta possa verificar "100% detectadas".

- Dois dias de arquivos de liquidação por adquirente, com um caso de cada tipo de divergência da seção 3.
- Um caso "aprovado mas não liquidado", que é o cenário do teste de domínio.
- Um caso em que o adquirente A cobrou durante um timeout, para exercitar o fallback.
- Um `expected_results.csv` listando cada linha plantada e o tipo de divergência que o job deve reportar.

Depois, ensaie a resposta do teste de domínio. Uma boa resposta de dois minutos cobre: o pagamento é um lançamento no ledger com uma data esperada de liquidação; o job diário casa pela referência do adquirente e o reporta como "faltando no arquivo"; a primeira ação é uma consulta de status ao adquirente, não uma correção automática; dependendo da resposta, você espera um arquivo atrasado, captura de novo ou faz o lançamento inverso e avisa o cliente; e um arquivo faltando, ou um número crescente desses casos, dispara um alerta.

## O que anotar hoje

1. Reconciliação: registros esperados x reais, regras de matching avaliadas em ordem do específico para o amplo, as três cardinalidades e por que matches ambíguos nunca são reconciliados automaticamente.
2. Tolerâncias: faixa de valor, variação (fixa x percentual) e janela de data. Escreva os valores que você vai usar no TCM e por quê.
3. Os tipos de divergência (faltando no arquivo, faltando no ledger, duplicado, valor diferente, data trocada), com a causa provável e a primeira ação de cada um.
4. A visão do Airbnb sobre integridade transacional: transações fora de sincronia, e por que eles comparam toda transação, todo atributo e toda etapa.
5. No papel: seu diagrama de fallback, timeout → consulta de status → só então outro provedor. Marque onde a idempotency key muda e qual constraint do banco impede uma cobrança dupla.

## Teste-se

Estas perguntas dão bons flashcards (veja o [guia de flashcards](../../FLASHCARDS.pt-BR.md)).

- Por que um motor de reconciliação deve se recusar a casar automaticamente quando dois candidatos servem?
- Por que a ordem das regras importa, e quais regras vêm primeiro?
- Qual é o risco de uma tolerância de valor larga?
- Qual join do SQL encontra "faltando no arquivo" e "faltando no ledger" em uma única passada?
- O que o Airbnb disse que as ferramentas tradicionais de reconciliação deixam escapar?
- Depois de um timeout no provedor A, o que precisa acontecer antes de você tentar o provedor B?
- Por que um "não encontrado" na consulta de status logo depois de um timeout não basta para fazer fallback?

## Referências

- **Fonte principal:** documentação da Modern Treasury, ["Reconciliation Overview"](https://docs.moderntreasury.com/reconciliation/docs). O link hoje abre a visão geral de pagamentos; siga o menu lateral até ["Reconciling received payments"](https://docs.moderntreasury.com/payments/docs/managing-externally-originated-payments), ["Defining Reconciliation Rules"](https://docs.moderntreasury.com/payments/docs/defining-reconciliation-rules), ["Advanced Matching Using Expected Payments"](https://docs.moderntreasury.com/payments/docs/advanced-matching-using-expected-payments), ["Valid conditions for Reconciliation Rules"](https://docs.moderntreasury.com/payments/docs/valid-conditions-for-reconciliation-rules) e ["Exception Handling - Manual Reconciliation"](https://docs.moderntreasury.com/payments/docs/exception-handling-manual-reconciliation). Gratuito.
- **Fonte principal:** Airbnb Engineering, ["Measuring Transactional Integrity in Airbnb's Distributed Payment Ecosystem"](https://medium.com/airbnb-engineering/measuring-transactional-integrity-in-airbnbs-distributed-payment-ecosystem-a670d6926d22), de Ninad Khisti e William Betz. Leia inteiro. Gratuito.
- Orquestração de provedores: roteamento e fallback seguro. Uma tarefa, não uma leitura: desenhe no papel o diagrama da seção 5. Como apoio, releia o post do Airbnb de segunda-feira, ["Avoiding Double Payments in a Distributed Payments System"](https://medium.com/airbnb-engineering/avoiding-double-payments-in-a-distributed-payments-system-2981f6b070bb), nas seções sobre leases e erros retryable. Gratuito.
