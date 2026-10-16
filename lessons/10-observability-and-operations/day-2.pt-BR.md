# Módulo 10, terça-feira: traces, propagação de contexto e métricas de negócio

[Módulo 10](../../modules/10-observability-and-operations.pt-BR.md) · [Read in English](day-2.md)

**Tempo de leitura:** cerca de 45 minutos. Use o resto do bloco de 2 horas nas referências do final.

Este é um texto original escrito para este curso. Ele se baseia nas referências listadas no final, e cada seção indica a fonte que segue.

## Por que isso importa para uma fintech

Uma única transferência na sua carteira digital passa por muitos processos. A API recebe `POST /transfers`, grava a transferência e uma linha de outbox no Postgres, um relay publica no Kafka, um worker consome o evento, chama o banco parceiro e grava os postings no ledger. Quando um cliente diz "minha transferência levou 40 segundos e depois falhou", você precisa seguir aquela requisição por todos esses saltos. É isso que traces fazem, e a parte difícil é o salto pelo Kafka.

Traces explicam uma requisição. Métricas falam sobre todas. Os sinais de ouro de segunda dizem se a API está saudável, mas uma carteira pode devolver 201 para toda requisição e ainda assim estar perdendo dinheiro. Por isso hoje também cobre métricas sobre o negócio em si: taxa de aprovação por provedor, pagamentos parados em `PENDING`, divergências de conciliação. São os números que respondem à pergunta do teste de domínio do módulo.

## 1. Traces e spans

*Fonte principal: documentação do OpenTelemetry, "Traces", seções "Spans", "Span Context", "Attributes", "Span Events" e "Span Status".*

A documentação do OpenTelemetry descreve um **trace** como o caminho de uma requisição pela sua aplicação. Um trace é feito de **spans**. Um span é uma unidade de trabalho: um handler HTTP, uma query SQL, uma chamada ao banco parceiro, o processamento de uma mensagem do Kafka.

Cada span carrega:

- um **nome** (por exemplo `POST /transfers` ou `partner-bank.debit`),
- um **timestamp de início e de fim**,
- um **span context** (veja abaixo),
- um **ID do span pai**, exceto na raiz,
- **attributes**, **events**, **links** e um **status**.

O primeiro span de uma requisição, o que não tem pai, é o **root span**. Todos os outros apontam para o seu pai, então os spans de uma requisição formam uma árvore. O Jaeger desenha essa árvore como uma cascata, e foi isso que você viu no laboratório de segunda.

O **span context** é um objeto imutável com quatro partes: o **trace ID** (compartilhado por todos os spans do trace), o **span ID** (único deste span), as **trace flags** (flags binárias, como se o trace é amostrado) e o **trace state** (pares chave-valor específicos de fornecedor). O span context é a parte que viaja entre serviços. Todo o resto fica onde o span foi criado.

**Attributes** são pares chave-valor que descrevem a operação. As chaves são strings. Os valores são strings, booleanos, números ou arrays desses tipos. A documentação recomenda adicionar attributes ao criar o span, porque os samplers só enxergam os attributes que existem no momento da criação. Ela também aponta as **semantic conventions**, nomes padronizados para attributes comuns como o método HTTP ou o sistema de banco de dados. Use esses nomes quando existirem, e o seu próprio namespace (`wallet.transfer_id`) para dados de domínio.

**Span events** são mensagens de log estruturadas presas a um span em um ponto no tempo. A documentação dá uma regra simples: se o timestamp importa, use um event; se não importa, use um attribute. "Banco parceiro devolveu 503, fazendo retry" é um event. O nome do provedor é um attribute.

**Span status** tem três valores. `Unset` é o padrão e significa que a operação terminou sem erro. `Error` significa que algo falhou. `Ok` significa que um desenvolvedor marcou explicitamente o span como bem-sucedido, e a documentação diz que isso costuma ser desnecessário. Para uma transferência que o banco parceiro recusou por "saldo insuficiente", pense antes de marcar `Error`: o sistema funcionou, e o resultado de negócio foi uma recusa. Coloque o resultado em um attribute e reserve `Error` para falhas de verdade.

## 2. Span kinds e span links

*Fonte principal: documentação do OpenTelemetry, "Traces", seções "Span Kind" e "Span Links".*

Todo span tem um **kind**, que diz ao backend de tracing como ele se relaciona com outros processos:

| Kind | Significado na documentação | Exemplo na carteira digital |
| --- | --- | --- |
| Server | Chamada remota síncrona recebida | Handler NestJS de `POST /transfers` |
| Client | Chamada remota síncrona enviada | Chamada HTTP ao banco parceiro, query SQL |
| Internal | Trabalho que não cruza a fronteira do processo | Calcular tarifas, validar limites |
| Producer | Cria um job que pode ser processado depois | Publicar `TransferRequested` no Kafka |
| Consumer | Processa um job criado por um producer | Worker tratando `TransferRequested` |

Se você não definir um kind, o span é tratado como internal. A documentação observa que um span consumer pode começar muito depois de o span producer ter terminado. Em uma carteira isso é normal: o relay do outbox pode publicar um segundo depois de a API ter respondido, e o worker pode consumir minutos depois durante um incidente.

**Span links** ligam um span a um ou mais outros spans sem torná-los pai e filho. A documentação dá o exemplo de uma operação assíncrona disparada por um trace anterior, sem que se saiba quando ela vai rodar. Links importam em mensageria porque um span tem exatamente um pai. Se o seu worker processa um lote de 50 mensagens do Kafka em um span, ele não pode ter 50 pais, mas pode ter 50 links. As convenções de mensageria do OpenTelemetry, vistas na seção 4, se apoiam nisso.

## 3. Propagação de contexto

*Fonte principal: documentação do OpenTelemetry, "Context propagation", seções "Context", "Propagation" e "Example".*

Um trace entre dois serviços só funciona se o segundo serviço souber a qual trace pertence. A documentação chama de **contexto** a informação que torna isso possível: o trace ID e o span ID que permitem ao receptor criar um span no mesmo trace. **Propagação** é levar esse contexto entre serviços e processos, serializando-o no lado que envia e desserializando-o no lado que recebe.

O componente que faz isso é um **propagator**. O padrão no OpenTelemetry usa a especificação **W3C TraceContext**, que define o header `traceparent`. O formato dele é `version-traceid-parentid-traceflags`, e a documentação mostra este exemplo:

```
traceparent: 00-a0892f3577b34da6a3ce929d0e0e4736-f03067aa0ba902b7-01
```

Leia assim: versão `00`, um trace ID de 32 caracteres hexadecimais, o ID de 16 caracteres hexadecimais do span que enviou a chamada, e as flags `01` (amostrado). O receptor extrai o header, cria seu próprio span com o mesmo trace ID e define como pai desse span o span ID de quem enviou.

No vocabulário da documentação, quem envia **injeta** (inject) o contexto em um **carrier** e quem recebe o **extrai** (extract). Em HTTP, o carrier são os headers da requisição, e as bibliotecas de auto-instrumentação para HTTP e NestJS fazem isso por você. Por isso o laboratório de segunda deu a você um trace sem código extra.

O exemplo da documentação também mostra que a propagação ajuda os outros sinais. Os SDKs podem adicionar o trace ID e o span ID aos registros de log, para você pular de um trace para os seus logs. Esse é o **correlation id** que o item 1 do TCM pede: use o próprio trace ID, para que logs e traces compartilhem uma chave.

Duas observações de segurança da mesma página valem para uma fintech. Trate com cuidado o contexto recebido de fontes não confiáveis, porque headers forjados podem distorcer seus traces. Pense duas vezes antes de enviar contexto para serviços externos, porque ele pode expor detalhes internos. E o **baggage**, um mecanismo separado que carrega pares chave-valor arbitrários entre serviços, nunca deve levar credenciais, chaves de API ou dados pessoais. Em uma carteira digital, não coloque CPF ou número de conta no baggage.

## 4. Propagando pelo Kafka

*Fonte principal: documentação do OpenTelemetry, "Context propagation", seção "Custom Context Propagation"; semantic conventions do OpenTelemetry, "Messaging spans", seção "Context propagation".*

A página "Context propagation" explica a regra geral para protocolos que as bibliotecas não cobrem: injete no carrier que o protocolo oferecer e extraia do outro lado. No Kafka, o carrier são os **headers da mensagem**. A página não trata de mensageria em detalhe. As semantic conventions de mensageria tratam, e a frase-chave delas é: "A producer SHOULD attach a message creation context to each message." (um producer DEVERIA anexar um contexto de criação a cada mensagem). O **creation context** é o span context do momento em que a mensagem foi criada. O span de processamento do consumer deve então fazer **link** para ele. Usá-lo como pai só é permitido em casos de uma única mensagem, e a convenção pede que você documente essa escolha.

No seu TCM há um salto a mais: a API grava uma linha de outbox, e um relay a publica depois. Se o relay injetar o próprio contexto, o trace começa no relay e você perde a ligação com a requisição HTTP. Então capture o contexto quando a API grava a linha de outbox e guarde-o em uma coluna:

```typescript
import { context, propagation } from '@opentelemetry/api';

// Dentro da mesma transação que cria a transferência
const carrier: Record<string, string> = {};
propagation.inject(context.active(), carrier); // preenche carrier.traceparent
await tx.query(
  `INSERT INTO outbox (id, topic, payload, trace_headers)
   VALUES ($1, $2, $3, $4)`,
  [eventId, 'transfers', payload, carrier],
);
```

O relay copia `trace_headers` para os headers da mensagem do Kafka sem alterar nada. O worker os extrai e inicia um span consumer:

```typescript
import { context, propagation, trace, SpanKind, SpanStatusCode } from '@opentelemetry/api';

const tracer = trace.getTracer('wallet-worker');

async function handle(message: KafkaMessage) {
  // O KafkaJS entrega os valores dos headers como Buffers; o propagator espera strings
  const carrier: Record<string, string> = {};
  for (const [key, value] of Object.entries(message.headers ?? {})) {
    if (value) carrier[key] = value.toString();
  }
  const parentCtx = propagation.extract(context.active(), carrier);

  await tracer.startActiveSpan(
    'process transfers',
    { kind: SpanKind.CONSUMER, attributes: { 'messaging.system': 'kafka' } },
    parentCtx,
    async (span) => {
      try {
        await processTransfer(message); // checagem do inbox, chamada ao parceiro, postings
      } catch (err) {
        span.setStatus({ code: SpanStatusCode.ERROR });
        throw err;
      } finally {
        span.end();
      }
    },
  );
}
```

Esta versão usa o contexto extraído como pai, que é o caso de uma única mensagem. Para seguir o padrão das convenções, inicie o span a partir do contexto atual e passe `links: [{ context: trace.getSpanContext(parentCtx)! }]` nas opções. De qualquer jeito, o Jaeger agora consegue mostrar a requisição na API e o processamento no worker como uma história só. Anote qual opção você escolheu e por quê: é uma boa linha para o `docs/m10.md`.

O nome do span segue o padrão das convenções, nome da operação mais destino, como `process transfers`. `messaging.system` e `messaging.destination.name` estão entre os nomes de attributes padronizados que elas definem.

## 5. O que o Prometheus manda instrumentar

*Fonte principal: documentação do Prometheus, "Instrumentation", seções "How to instrument", "The three types of services" e "Subsystems".*

A página do Prometheus começa com uma resposta direta sobre o que medir: "The short answer is to instrument everything." (a resposta curta é instrumentar tudo). Depois ela separa os serviços em três tipos, e o seu TCM tem os três:

| Tipo | Métricas-chave na documentação | Na carteira digital |
| --- | --- | --- |
| Online-serving | Queries executadas, erros, latência; requisições em andamento também ajudam | API de transferências |
| Offline processing | Itens chegando, em andamento, último momento de processamento, itens enviados | Worker do Kafka, relay do outbox |
| Batch job | A última vez que deu certo; duração de cada etapa e da execução | Conciliação noturna |

Dois detalhes se aplicam direto. Para serviços online, a página sugere contar uma requisição quando ela termina, para que a contagem bata com as estatísticas de erro e latência. Para pipelines, ela sugere um **heartbeat**: um item fictício com um timestamp que atravessa o sistema inteiro, para medir quanto tempo os itens levam para passar. Para o relay do outbox e o worker, um evento de heartbeat a cada minuto diz se o pipeline travou mesmo quando nenhum cliente está transferindo.

Para **falhas**, a página manda incrementar um contador a cada falha e também contar o total de tentativas, para que você calcule a taxa de falha. Essa razão tem exatamente o formato de que os alertas de SLO de segunda precisam.

## 6. Métricas de negócio como sinal principal

*Fonte principal: documentação do Prometheus, "Instrumentation", seções "Counter vs. gauge, summary vs. histogram", "Timestamps, not time since" e "Avoid missing metrics". O enfoque de negócio é deste curso.*

A página do Prometheus fala de métricas técnicas. Em uma fintech, as métricas que pegam os incidentes caros são sobre o negócio. Elas são sintomas no sentido de segunda: descrevem o que o cliente e a empresa sentem. O item 2 do TCM pede três.

**Taxa de aprovação por provedor.** Conte toda tentativa de autorização com dois labels: `provider` e `outcome` (`approved`, `declined`, `error`). A taxa de aprovação é uma razão entre taxas:

```promql
sum by (provider) (rate(payment_authorizations_total{outcome="approved"}[15m]))
/
sum by (provider) (rate(payment_authorizations_total[15m]))
```

Uma queda em um provedor enquanto o outro fica estável aponta para aquele provedor. Uma queda nos dois aponta para você.

**Pagamentos PENDING antigos.** Essa métrica pode subir e descer, então é um gauge. A regra prática do Prometheus: "if the value can go down, it is a gauge" (se o valor pode descer, é um gauge). A página também aconselha exportar o timestamp de quando algo aconteceu, e não o tempo desde que aconteceu, porque assim `time() - metric` dá a idade sem nenhuma lógica de atualização. Então um job periódico pode exportar o horário de criação do pagamento pendente mais antigo:

```sql
SELECT EXTRACT(EPOCH FROM min(created_at)) AS oldest_pending_ts
FROM payments
WHERE status = 'PENDING';
```

```promql
time() - wallet_oldest_pending_payment_timestamp_seconds > 900
```

Esse alerta dispara quando algum pagamento está pendente há mais de 15 minutos. Um segundo gauge com a quantidade de pagamentos pendentes há mais de 15 minutos diz se é um pagamento travado ou mil.

**Divergências de conciliação.** O job do Módulo 7 compara seu ledger com o arquivo do provedor e reporta itens faltando, duplicados, com valor diferente e com data errada. Exporte um gauge por tipo a partir da última execução, mais o timestamp da última execução bem-sucedida (a métrica de batch job da seção 5). Uma contagem de divergências acima de zero precisa de um humano. Um timestamp de último sucesso com mais de um dia significa que o próprio job quebrou, e aí zero divergências não prova nada.

No código, com a biblioteca `prom-client`:

```typescript
import { Counter, Gauge } from 'prom-client';

export const authorizations = new Counter({
  name: 'payment_authorizations_total',
  help: 'Authorization attempts by provider and outcome',
  labelNames: ['provider', 'outcome'] as const,
});

export const reconDiscrepancies = new Gauge({
  name: 'reconciliation_discrepancies',
  help: 'Discrepancies found in the last reconciliation run',
  labelNames: ['type'] as const,
});

// Inicializa com 0 as séries conhecidas, para que existam antes do primeiro evento
for (const provider of ['provider_a', 'provider_b']) {
  for (const outcome of ['approved', 'declined', 'error']) {
    authorizations.inc({ provider, outcome }, 0);
  }
}
```

O último laço segue o conselho "Avoid missing metrics" da página: exporte um valor padrão como 0 para as séries que você sabe que vão existir. Sem isso, a série "error" de um provedor não existe até o primeiro erro, e uma razão ou um alerta sobre ela não devolve nada.

## 7. Labels e o custo da cardinalidade

*Fonte principal: documentação do Prometheus, "Instrumentation", seções "Use labels" e "Do not overuse labels".*

Labels são o que torna uma métrica útil de muitas formas. O conselho da página é usar uma métrica com um label quando você somaria ou tiraria a média dos valores, por exemplo um único `http_responses_total` com um label `code` em vez de uma métrica por status code. Por isso `outcome` e `provider` são labels e não parte do nome da métrica.

Mas cada combinação única de valores de labels é uma série temporal separada, guardada e consultada por conta própria. A página alerta para esse custo com orientações concretas:

- Como regra geral, mantenha a cardinalidade de uma métrica abaixo de 10.
- Métricas acima disso devem ser só um punhado no sistema inteiro.
- Se uma métrica tem cardinalidade acima de 100, ou pode crescer até isso, procure alternativas, como levar a análise para fora do Prometheus.
- Na dúvida, comece sem labels e adicione conforme surgirem necessidades reais.

O exemplo da página: uma métrica de sistema de arquivos em 10.000 nós dá cerca de 100.000 séries, o que é aceitável. Acrescentar cotas por usuário para 10.000 usuários leva isso a dezenas de milhões.

Para uma carteira digital, a regra é simples. Labels como `provider` (2 ou 3 valores), `outcome` (3 valores) e `route` (algumas dezenas) são aceitáveis. Labels como `customer_id`, `transfer_id`, `idempotency_key` ou `amount` nunca são: a quantidade de valores cresce com o seu negócio. Quando você precisa achar uma transferência específica, esse é o trabalho de traces e logs, que são indexados por trace ID. Métricas respondem "quantos e quão rápido". Traces e logs respondem "qual".

## O que anotar hoje

1. Desenhe o trace de uma transferência, de `POST /transfers` até os postings no ledger: cada span com nome e kind, e onde o contexto atravessa o outbox e o Kafka.
2. Escreva sua decisão de propagação para o worker: pai ou link, quais headers você guarda no outbox e como o trace ID chega a cada linha de log.
3. Liste suas métricas de negócio: nome, tipo (counter, gauge ou histogram), labels com os valores possíveis e a PromQL em que você alertaria. Marque qualquer label cuja cardinalidade possa crescer com o negócio, e remova-o.

## Teste-se

Estas perguntas dão bons flashcards (veja o [guia de flashcards](../../FLASHCARDS.pt-BR.md)).

- Quais quatro campos um span context guarda, e qual parte viaja entre serviços?
- Quando usar um span event em vez de um span attribute?
- Qual é a diferença entre um span producer e um span consumer, e por que o consumer pode começar depois que o producer terminou?
- Por que as convenções de mensageria preferem span links a pai e filho para consumers?
- Leia este header: `00-a0892f3577b34da6a3ce929d0e0e4736-f03067aa0ba902b7-01`. O que é cada parte?
- Por que exportar o timestamp do pagamento pendente mais antigo em vez da idade dele?
- Por que `customer_id` é um label ruim no Prometheus, e onde você procura a transferência de um cliente em vez disso?

## Referências

- **Fonte principal:** documentação do OpenTelemetry, ["Traces"](https://opentelemetry.io/docs/concepts/signals/traces/). Leia toda a parte "Spans", incluindo span context, attributes, events, links, status e kind. Gratuito.
- **Fonte principal:** documentação do OpenTelemetry, ["Context propagation"](https://opentelemetry.io/docs/concepts/context-propagation/). Leia "Context", "Propagation", o exemplo e "Security best practices". Gratuito.
- **Fonte principal:** documentação do Prometheus, ["Instrumentation"](https://prometheus.io/docs/practices/instrumentation/). Leia inteira, com foco em "The three types of services" e "Things to watch out for". Gratuito.
- Semantic conventions do OpenTelemetry, ["Messaging spans"](https://opentelemetry.io/docs/specs/semconv/messaging/messaging-spans/). Leia a parte "Context propagation" e a tabela de span kinds. Gratuito. Incluída porque a página "Context propagation" não trata de mensageria em detalhe.
