# Módulo 7, segunda-feira: o ciclo de vida do pagamento com cartão e pagamentos duplicados

[Módulo 7](../../modules/07-payments-pix-reconciliation.pt-BR.md) · [Read in English](day-1.md)

**Tempo de leitura:** cerca de 45 minutos. Use o resto do bloco de 2 horas nas referências do final, começando pelas seções marcadas como fonte principal.

Este é um texto original escrito para este curso. Ele se baseia nas referências listadas no final, e cada seção indica a fonte que segue. Quando uma ideia vem de um autor específico, o texto diz isso.

## Por que isso importa para uma fintech

Até agora, a carteira digital movia dinheiro entre as próprias contas. Nesta semana ela começa a conversar com o mundo externo: adquirentes de cartão, o Pix e arquivos de liquidação de bancos. O dinheiro externo tem duas propriedades que o interno não tem. Ele se move em várias etapas espalhadas por dias, e o outro lado mantém os próprios registros, que podem discordar dos seus.

Hoje o assunto é a primeira propriedade. Você vai ver quem são os atores de um pagamento com cartão, o que significam autorização, captura e liquidação, como a Stripe modela um pagamento como máquina de estados e como o Airbnb parou de cobrar hóspedes duas vezes. O laboratório de hoje constrói dois adquirentes falsos, contra os quais você vai reconciliar na quinta-feira.

## 1. Quem participa de um pagamento com cartão

*Fonte principal: Stripe, "How card payment processing and settlement works", seção "Who is involved in the authorization and settlement process?".*

Um pagamento com cartão que parece um único toque para o cliente passa por pelo menos cinco partes. O artigo da Stripe lista assim:

| Ator | Papel | Exemplo na carteira |
| --- | --- | --- |
| Portador do cartão | Quem paga; o dinheiro sai da conta dele | Um usuário da carteira fazendo recarga com cartão de crédito |
| Empresa (lojista) | Quem vende; o dinheiro liquidado termina na conta bancária dela | Sua empresa de carteira digital |
| Adquirente | Processa os pagamentos com cartão da empresa e os encaminha pela bandeira até o emissor | O adquirente com quem sua carteira assinou contrato |
| Processador de pagamento | Repassa os dados da transação entre empresa, bandeira e emissor | Muitas vezes a mesma empresa que o adquirente |
| Bandeira | Opera os trilhos do cartão e encaminha os pedidos de autorização | Visa, Mastercard |
| Emissor | Fornece o cartão e o limite de crédito; aprova ou recusa | O banco do portador |

A Stripe observa que processadores e adquirentes eram historicamente empresas separadas, mas podem ser combinados, como a própria Stripe faz. O roteiro deste módulo também cita o **gateway**: a camada de software que recebe os dados do cartão no seu checkout e os envia ao processador. O artigo da Stripe não o define como um ator separado, então trate "gateway" como um papel que muitos provedores oferecem junto com o processamento.

Duas consequências importam para o seu design. Primeiro, sua carteira só conversa com o adquirente (ou com o processador na frente dele). Você nunca chama o emissor ou a bandeira diretamente. Segundo, cada parte da cadeia mantém seu próprio registro do mesmo pagamento. É por isso que a reconciliação existe, e é por isso que a quarta-feira é sobre ela.

## 2. Autorização, captura e liquidação

*Fonte principal: Stripe, "How card payment processing and settlement works", seções "How does card authorization work?" e "What is capturing and settlement?".*

Um pagamento com cartão acontece em três etapas, e o dinheiro só se move na última.

**Autorização.** O cliente informa o cartão. O processador envia um pedido de aprovação pela bandeira até o emissor. O emissor confere se o cartão é válido, se dados como o endereço de cobrança batem e se há saldo ou limite suficiente. O artigo diz que o emissor responde com um código de dois dígitos, e a aprovação costuma voltar em poucos segundos. Aí vem o ponto central: "If the transaction is approved, the issuer will immediately reduce the balance or available credit". Nenhum dinheiro se moveu ainda. O emissor apenas o reservou.

**Captura.** O adquirente age sobre a autorização e pede os fundos. A empresa pode escolher quando capturar, porque uma autorização continua válida por um tempo. O artigo diz que autorizações costumam durar de 5 a 10 dias, e às vezes até 30 dias. Um hotel ou uma locadora de carros autoriza no check-in e captura no check-out, possivelmente com outro valor.

**Liquidação.** Nas palavras da Stripe, "Settlement is when the funds themselves are moved from the issuing account to the merchant account." O adquirente segura os fundos e depois paga a conta bancária da empresa, o que, segundo o artigo, costuma levar alguns dias.

Mapeie essas etapas no ledger do Módulo 6, porque o TCM pede exatamente isso na quinta-feira:

| Etapa do cartão | O que significa | Efeito no ledger da carteira |
| --- | --- | --- |
| Autorização aprovada | O emissor reservou o dinheiro | Criar um **hold**; o saldo disponível cai, nada é lançado |
| Captura | O lojista reivindicou o dinheiro | Fazer o **lançamento**; liberar ou consumir o hold |
| Autorização expirada ou cancelada | A reserva caiu | Liberar o hold; nenhum lançamento |
| Liquidação | O dinheiro chegou ao seu banco | Casar a linha de liquidação com o lançamento; mover de "a receber do adquirente" para "caixa no banco" |
| Estorno | O dinheiro volta | Fazer um **lançamento inverso**, nunca editar o original |

A última linha é a regra que você vai continuar usando: o ledger é append-only, então um estorno é um novo lançamento que aponta para o original.

## 3. Um pagamento como máquina de estados

*Fonte principal: documentação da Stripe, "The Payment Intents API", mais a página vinculada "How Payment Intents and Setup Intents work".*

A Stripe modela cada tentativa de cobrar dinheiro como um **PaymentIntent**, um objeto cujo `status` passa por um conjunto fixo de estados. A documentação diz que cada PaymentIntent "typically correlates with a single shopping cart or customer session" na sua aplicação. A página do ciclo de vida lista estes status:

| Status | Significado (resumido da documentação da Stripe) |
| --- | --- |
| `requires_payment_method` | Criado, ainda sem meio de pagamento. Uma tentativa que falha, como uma recusa, volta para cá para o cliente tentar de novo. |
| `requires_confirmation` | Os dados de pagamento estão presentes e prontos para confirmar. A maioria das integrações pula este estado. |
| `requires_action` | É preciso uma ação extra do cliente, como a autenticação 3D Secure. |
| `processing` | Aguardando um meio assíncrono, como um débito bancário, que pode levar dias. |
| `requires_capture` | Autorizado, mas não capturado, quando você autoriza e captura separadamente. |
| `succeeded` | O fluxo terminou; a documentação diz que você pode entregar o pedido. |
| `canceled` | Invalidado; os fundos retidos são liberados. Não tem volta. |

Três ideias de design dessas páginas valem a pena copiar para a sua carteira.

**O objeto sobrevive às tentativas.** Um PaymentIntent pode ter mais de uma Charge, porque retries criam novas tentativas. O intent acompanha o objetivo do cliente (pagar este carrinho). As charges acompanham cada tentativa. No seu schema, isso significa uma tabela `payments` e uma tabela separada `payment_attempts`, o que vai importar na quarta-feira, quando um pagamento puder ser tentado em dois provedores.

**Reutilize em vez de recriar.** A Stripe recomenda criar o intent assim que o valor for conhecido e reutilizá-lo se o checkout for interrompido e retomado. A documentação também manda enviar uma idempotency key, "typically based on the ID that you associate with the cart or customer session". Uma chave determinística derivada do carrinho é o que impede um clique duplo de criar dois pagamentos.

**Nem todo estado alcança todos os outros.** Você pode cancelar antes de `processing` ou `succeeded`, mas não depois (com exceções para alguns débitos bancários). Uma tentativa que falha volta para `requires_payment_method`, nunca para `succeeded`. Essas regras formam uma tabela de transições, e o laboratório de amanhã é escrever uma.

Por fim, a documentação recomenda que, depois que o cliente confirma, seu servidor acompanhe webhooks para saber se o pagamento terminou ou falhou. O provedor empurra o estado final; você não o deduz pelo simples retorno da sua chamada.

## 4. O problema do pagamento duplicado no Airbnb

*Fonte principal: Airbnb Engineering, "Avoiding Double Payments in a Distributed Payments System", seções "The problem statement" e "Solution explained".*

O time de pagamentos do Airbnb migrou de um monólito para serviços e precisou manter a movimentação de dinheiro correta enquanto cada requisição passava a atravessar muitas chamadas de rede. O post é direto sobre a prioridade: "Guaranteeing eventual consistency for our payments system is of the utmost importance." Eles também precisavam de latência muito baixa, por isso não construíram um serviço de idempotência separado. Em vez disso, construíram uma biblioteca, chamada **Orpheus**, que cada serviço de pagamento embute.

O Orpheus divide cada requisição em três fases:

1. **Pre-RPC.** Gravar no banco os detalhes do pedido de pagamento.
2. **RPC.** Chamar o serviço externo (um adquirente, por exemplo) e receber a resposta. Esta fase também pode consultar o status de uma tentativa anterior.
3. **Post-RPC.** Gravar o resultado no banco: sucesso ou falha, e se a falha pode ter retry.

Duas regras sustentam o design. O post as enuncia como "No service interaction over networks in Pre and Post-RPC phases" e "No database interactions in the RPC phases." Cada fase de banco é uma única transação curta. Isso significa que você nunca segura uma transação do Postgres aberta enquanto espera um adquirente lento, e nunca chama um adquirente de dentro de uma transação que pode sofrer rollback depois que o dinheiro já se moveu.

Aqui está o mesmo formato em um serviço NestJS. Os objetos `db` e `acquirer` representam seu próprio repositório e cliente HTTP.

```typescript
async capture(paymentId: string, idemKey: string) {
  // Pre-RPC: uma transação curta, sem chamadas de rede
  const attempt = await this.db.transaction(async (tx) => {
    return tx.attempts.claim(paymentId, idemKey); // lock de linha + lease
  });
  if (attempt.state === 'COMPLETED') return attempt.response; // replay

  // RPC: só rede, sem banco
  let result: AcquirerResult;
  try {
    result = await this.acquirer.capture(attempt.acquirerRef, { idemKey });
  } catch (err) {
    result = classify(err); // RETRYABLE, NON_RETRYABLE ou UNKNOWN
  }

  // Post-RPC: uma transação curta, sem chamadas de rede
  return this.db.transaction(async (tx) => tx.attempts.finish(attempt.id, result));
}
```

## 5. Retries, leases e respostas gravadas

*Fonte principal: Airbnb Engineering, "Avoiding Double Payments in a Distributed Payments System", seções "Handling exceptions", "Clients play a vital role", "How to choose an idempotency key?", "Each API request has an expiring lease", "Recording the response" e "Avoid replica databases".*

O resto do post é uma lista de regras que transformam as três fases em um sistema seguro. Cada uma responde a um jeito específico de cobrar duas vezes.

**Classifique todo erro.** O Orpheus exige que cada erro seja marcado como **retryable** ou **non-retryable**. Erros retryable são falhas de infraestrutura ou de rede, em geral status 5XX, que se espera serem passageiras. Erros non-retryable são falhas de validação ou estados inválidos (o exemplo do post é estornar um estorno), em geral status 4XX. O post avisa que erros nas duas direções machucam. Um erro retryable marcado como non-retryable deixa o pagamento travado. Um erro non-retryable marcado como retryable pode causar um pagamento duplicado.

Há um terceiro caso que o post trata sem dar nome: a chamada deu timeout e você não sabe o que aconteceu. O Módulo 1 chamou isso de desfecho **desconhecido** (unknown). Ele não pertence a nenhuma das duas classes. Você não pode fazer retry às cegas, e não pode marcar como falha. Você resolve perguntando o status ao provedor, que é exatamente o que a fase RPC tem permissão de fazer.

**O cliente mantém a mesma chave.** Os clientes devem gerar uma chave única por requisição nova, reutilizá-la em todo retry, gravá-la antes de chamar e nunca mudar o payload entre retries. Devem fazer retry com backoff e jitter. O post distingue chaves **por requisição**, como um UUID aleatório por requisição, de chaves **por entidade**, que são determinísticas e ligadas a uma entidade de negócio, como "o estorno do pagamento 123". Chaves por entidade são o que você quer para operações que devem acontecer no máximo uma vez por entidade.

**Uma requisição por vez, com lease.** Cada requisição pega um lock de linha na sua idempotency key antes de seguir. O lock funciona como um lease que expira. Se um servidor morre no meio da requisição, um retry só pode prosseguir depois que o lease vence, e o post sugere que o lease dure mais que o timeout do RPC. Caso contrário, um retry poderia começar enquanto a primeira chamada ainda está em andamento no adquirente.

**Grave a resposta.** Quando uma requisição chega a um estado final determinístico, o Orpheus grava a resposta. Um retry então recebe a resposta original sem chamar o adquirente de novo. O custo é uma tabela que cresce junto com o volume, então planeje uma política de retenção.

**Leia do primário, não de uma réplica.** Os dados de idempotência são sempre lidos e gravados no banco primário (o post diz master). Uma réplica poderia estar atrasada, não enxergar um sucesso já gravado e deixar um retry cobrar de novo. O post apresenta isso como um trade-off: "In a system of distributed databases, there is a tradeoff between consistency and latency." Para dados de idempotência, eles escolheram consistência.

O post afirma que o Orpheus os ajudou a chegar a cinco noves de consistência nos pagamentos, e admite que a consistência eventual "does not come without introducing some complexity."

Uma tabela mínima no Postgres que suporta essas regras, partindo da sua tabela `idempotency_keys` do Módulo 2:

```sql
CREATE TABLE payment_attempts (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  payment_id    uuid NOT NULL REFERENCES payments(id),
  provider      text NOT NULL,
  idem_key      text NOT NULL,
  state         text NOT NULL CHECK (state IN
                  ('PENDING','COMPLETED','FAILED_RETRYABLE','FAILED_FINAL','UNKNOWN')),
  lease_until   timestamptz,
  provider_ref  text,
  response      jsonb,
  UNIQUE (provider, idem_key)
);
```

A constraint de unicidade é a última linha de defesa. Mesmo que dois workers disputem, só pode existir uma linha por provedor e chave.

## 6. Preparando o laboratório de hoje: dois adquirentes falsos

*Fonte principal: o laboratório de segunda-feira na página do módulo, aplicando as seções 2 a 5.*

O laboratório pede dois adquirentes falsos que autorizam, capturam e geram um CSV de liquidação diário. Mantenha-os simples, mas honestos quanto aos comportamentos que você vai precisar testar depois:

- **Autorizar** devolve um `acquirer_ref` e uma aprovação ou recusa. Faça-o aceitar uma idempotency key e devolver a mesma resposta para a mesma chave.
- **Capturar** recebe o `acquirer_ref` e um valor até o valor autorizado.
- **Consultar status** por `acquirer_ref` ou pela sua idempotency key. O fallback seguro de quarta-feira depende de essa chamada existir.
- **Injeção de falhas.** Deixe uma flag fazer uma chamada dar timeout depois que o adquirente já a registrou. É esse o caso que produz pagamentos duplicados, então você precisa conseguir reproduzi-lo de propósito.
- **CSV de liquidação.** Uma vez por dia simulado, escreva uma linha por item capturado ou estornado.

Um layout de CSV razoável, com valores em centavos inteiros para evitar erros de ponto flutuante:

```text
settlement_date,acquirer_ref,payment_id,type,gross_cents,fee_cents,net_cents,currency
2026-10-19,acq_a_0001,pay_7f3c,CAPTURE,10000,250,9750,BRL
2026-10-19,acq_a_0002,pay_91de,REFUND,-3000,0,-3000,BRL
```

Faça os dois adquirentes diferirem um pouco (taxas diferentes, ordem de colunas ou formato de data diferentes). Provedores reais nunca concordam num formato, e o job de reconciliação de quinta-feira deve normalizar cada arquivo antes de casar os registros.

## O que anotar hoje

1. Os atores de um pagamento com cartão (portador, lojista, adquirente, processador ou gateway, bandeira, emissor) e a diferença entre autorização, captura e liquidação. Acrescente o efeito no ledger que cada etapa causa na sua carteira.
2. Sua própria máquina de estados de pagamento, inspirada nos status do PaymentIntent: liste os estados e, para cada um, os estados para os quais ele pode ir. Inclua `UNKNOWN` para uma chamada que deu timeout.
3. As regras do Orpheus para evitar pagamentos duplicados: as três fases, as duas regras de "não", erros retryable x non-retryable, leases, respostas gravadas e leitura do primário. Para cada regra, escreva qual pagamento duplicado ela evita.

## Teste-se

Estas perguntas dão bons flashcards (veja o [guia de flashcards](../../FLASHCARDS.pt-BR.md)).

- Depois que uma autorização de cartão é aprovada, algum dinheiro se moveu? O que o emissor fez?
- Por que uma empresa capturaria dias depois de autorizar, e com outro valor?
- Por que um pagamento deve ter várias tentativas no seu modelo de dados?
- Quais são as três fases do Orpheus, e que tipo de trabalho é proibido em cada uma?
- O que dá errado se um erro non-retryable for marcado como retryable? E o contrário?
- Por que o lease de uma idempotency key precisa durar mais que o timeout do RPC?
- Por que o Airbnb lê dados de idempotência do primário e nunca de uma réplica?

## Referências

- **Fonte principal:** Stripe, ["How card payment processing and settlement works"](https://stripe.com/resources/more/credit-card-payment-authorization-and-transaction-settlement-process). Leia inteiro, principalmente os atores e as etapas da autorização. Gratuito.
- **Fonte principal:** documentação da Stripe, ["The Payment Intents API"](https://docs.stripe.com/payments/payment-intents), junto com ["How Payment Intents and Setup Intents work"](https://docs.stripe.com/payments/paymentintents/lifecycle) para a tabela de status. Pule os exemplos de código do lado do cliente. Gratuito.
- **Fonte principal:** Airbnb Engineering, ["Avoiding Double Payments in a Distributed Payments System"](https://medium.com/airbnb-engineering/avoiding-double-payments-in-a-distributed-payments-system-2981f6b070bb). Leia do começo ao fim; é a leitura mais importante do dia. Gratuito.
