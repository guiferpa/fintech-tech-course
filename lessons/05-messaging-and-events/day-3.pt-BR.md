# Módulo 5, quarta-feira: retries, DLQ, event sourcing e webhooks assinados

[Módulo 5](../../modules/05-messaging-and-events.pt-BR.md) · [Read in English](day-3.md)

**Tempo de leitura:** cerca de 45 minutos. Use o resto do bloco de 2 horas nas referências do final, depois esboce os scripts de caos do TCM.

Este é um texto original escrito para este curso. Ele se baseia nas referências listadas no final, e cada seção indica a fonte que segue. Quando uma ideia vem de um autor específico, o texto diz isso.

## Por que isso importa para uma fintech

O consumidor de terça está correto quando tudo acaba funcionando. Consumidores reais encontram eventos que não conseguem processar: uma API de parceiro fora do ar por dez minutos, um payload com uma moeda que o seu código não conhece, um bug introduzido no deploy de ontem. Se o consumidor continua fazendo retry do mesmo registro, a partição inteira para, e toda conta cujo hash cai nela para de receber atualizações.

Hoje você vê três temas que fecham o módulo. Primeiro, como fazer retry sem bloquear (tópicos de retry e uma dead letter queue). Segundo, como impedir que eventos fora de ordem façam o estado andar para trás, e como o event sourcing trata os eventos como o próprio estado. Terceiro, como enviar eventos para o mundo de fora como webhooks em que o receptor pode confiar. O TCM de quinta e sexta implementa tudo isso.

## 1. Por que fazer retry no lugar bloqueia a partição

*Fonte principal: Uber Engineering, "Building Reliable Reprocessing and Dead Letter Queues with Apache Kafka", seções sobre retries simples e seus problemas.*

O artigo da Uber abre com uma frase que vale decorar: "In distributed systems, retries are inevitable." O time o escreveu para seu produto de seguro para motoristas, em que um evento do Kafka dispara uma chamada de pagamento.

O design mais simples faz retry dentro do consumidor: chama o serviço e, se falhar, espera e tenta de novo até dar certo. O artigo lista os problemas:

- **A partição fica bloqueada.** O consumidor nunca commita o offset do registro que falha, então continua relendo o mesmo registro, e os registros mais novos esperam atrás dele. Um registro ruim segura todos os registros saudáveis da sua partição.
- **Os metadados de retry são difíceis de manter.** Saber quantas vezes um registro foi tentado, e quando, é complicado quando o registro nunca sai do lugar.

Na carteira, a partição 3 pode conter 1/6 de todas as contas. Um único evento malformado de uma conta congelaria as notificações de saldo de todas as contas daquela partição. Uma mensagem que falha sempre, não importa quantas vezes você faça retry, é chamada de **mensagem envenenada** (poison message). O artigo da Uber não usa esse termo, mas descreve o caso: erros de bugs ou de dados ruins não se resolvem sozinhos, ao contrário de instabilidades de rede.

## 2. Tópicos de retry e a dead letter queue

*Fonte principal: Uber Engineering, "Building Reliable Reprocessing and Dead Letter Queues with Apache Kafka", seções sobre filas separadas e seus benefícios.*

A resposta da Uber é tirar o registro que falha do fluxo principal. O consumidor tenta um registro um número fixo de vezes. Se ainda falhar, o consumidor o publica em um **tópico de retry**, então commita o offset no tópico principal e segue em frente. A partição fica livre de novo.

Existe uma escada de tópicos de retry, cada um com seus próprios consumidores e um atraso maior que o do anterior. Uma falha em um nível manda o registro para o próximo. Uma falha no último nível o manda para a **dead letter queue (DLQ)**, um tópico onde os registros esperam por uma pessoa ou uma ferramenta. O artigo enfatiza que os atrasos são de melhor esforço: um handler roda pelo menos depois do seu atraso, possivelmente mais tarde. O atraso é imposto segurando o consumo em cada fila de retry até que o registro tenha idade suficiente.

```text
wallet.account-events  --falha x3-->  wallet.account-events.retry-1 (espera ~1 min)
                                          --falha-->  .retry-2 (espera ~10 min)
                                          --falha-->  .dlq  (alerta; replay por comando)
```

Esses nomes de tópico e atrasos são um exemplo para este curso. O artigo não prescreve um esquema de nomes nem atrasos específicos.

O artigo recomenda separar os tipos de erro. Erros transitórios (timeouts, um 503 de um parceiro) passam pela escada de retry. Erros que não adianta repetir (uma falha de validação, um bug) podem ir direto para a DLQ, porque fazer retry deles só desperdiça capacidade. Para o **replay**, as ferramentas da Uber conseguem listar, apagar e mesclar a DLQ: "Dead letter messages are merged to re-enter processing by being published back into the first retry topic." A tarefa 2 do TCM pede exatamente esse comando.

O padrão cobra dois preços, ambos citados nas "other considerations" do artigo:

- **Ordem.** Um registro que vai para um tópico de retry é processado depois de registros mais novos da mesma chave. Se o evento 7 de `acc-1` falha e o evento 8 dá certo, a conta vê o 8 antes do 7. A seção 3 mostra como tornar isso inofensivo.
- **Idempotência.** Um registro pode ser tentado em vários níveis, e o artigo observa que os consumidores precisam ser idempotentes. O seu inbox de terça já cobre isso.

**Backpressure** é o outro lado dos retries. O artigo não usa a palavra, mas descreve a ideia: a escada de atrasos limita a velocidade com que registros que falharam voltam, então um serviço downstream em dificuldade não é martelado por retries. Em um único consumidor, o Javadoc do `KafkaConsumer` descreve `pause()` e `resume()` para partições, em "Consumption Flow Control". Um consumidor que vê o circuit breaker do banco parceiro aberto (Módulo 9) pode pausar suas partições em vez de jogar todo registro na escada de retry. O modelo pull do Kafka ajuda aqui: um consumidor que para de fazer poll simplesmente deixa os registros se acumularem no log, onde estão seguros.

## 3. Eventos fora de ordem não podem fazer o estado andar para trás

*Fonte principal: a regra do TCM deste curso, construída sobre o ponto de Jay Kreps (segunda-feira) de que a ordem vem de números de sequência, não de relógios.*

Tópicos de retry, reenvios do producer e replays da DLQ significam que um evento mais antigo pode chegar depois de um mais novo. Os critérios de aprovação dizem que eventos fora de ordem nunca podem fazer o estado andar para trás. A ferramenta é uma **versão** (um número de sequência por entidade) definida pelo producer, na mesma transação que mudou o estado.

Digamos que o serviço de contas emita `AccountStatusChanged` com `version` 1, 2, 3. Um consumidor que mantém uma cópia local do status da conta só aplica um evento se ele for mais novo do que o que já tem:

```sql
UPDATE account_status_view
SET status = $2, version = $3, updated_at = now()
WHERE account_id = $1
  AND version < $3;   -- versões iguais ou mais antigas não mudam nada
-- 0 linhas atualizadas: evento velho ou duplicado, pule e commite o offset
```

Essa é a tarefa 3 do TCM. Repare no que ela não usa: `created_at` ou o timestamp do Kafka. O Módulo 1 explicou por que relógios de parede não ordenam eventos entre máquinas.

Versões funcionam para visões de "estado mais recente". Elas são erradas para eventos cujos efeitos se somam, como créditos. Um crédito atrasado não está velho; ele ainda precisa ser aplicado uma vez. Para esses, use o inbox para garantir uma vez, e faça a projeção tolerar qualquer ordem, por exemplo somando lançamentos do ledger em vez de sobrescrever um saldo.

## 4. Event sourcing: eventos como o estado

*Fonte principal: Martin Fowler, "Event Sourcing".*

Até aqui, eventos eram notificações sobre mudanças guardadas em tabelas. Fowler descreve uma ideia mais forte: "Event Sourcing ensures that all changes to application state are stored as a sequence of events." Os eventos são o registro da verdade. O estado atual é algo que você calcula a partir deles.

Fowler explica que guardar só o histórico é um ganho pequeno. O valor vem do que você consegue fazer com o log:

- **Reconstrução completa.** Jogue fora o estado atual e reproduza todos os eventos a partir do zero para reconstruí-lo.
- **Consulta temporal.** Calcule o estado como ele era em qualquer momento passado, reproduzindo os eventos até aquele momento.
- **Replay de eventos.** Se um evento passado estava errado, corrija-o e recalcule as consequências.

Reproduzir tudo é lento, então os sistemas guardam **snapshots** do estado atual e reproduzem só os eventos mais novos. Fowler observa que, como o estado é derivado do log, "you can cache it anywhere you like". Ele também trata da **reversão de eventos**: é mais fácil quando cada evento é uma diferença (por exemplo "débito de 30") e não um novo valor absoluto.

A parte difícil do artigo é o mundo de fora. Reproduzir eventos não pode enviar mensagens reais de novo, então Fowler recomenda embrulhar sistemas externos em **gateways** que não fazem nada durante o replay. Consultas externas também são um problema: se processar um evento consultou um parceiro sobre uma taxa de câmbio, o replay precisa usar a taxa daquela época, então você registra a resposta. Em uma carteira, isso significa: nunca deixe um replay reenviar uma transferência Pix ou um webhook, e guarde a taxa de câmbio no evento.

Fowler aponta que a contabilidade se encaixa naturalmente, já que lançamentos do ledger já são um log de mudanças em uma conta. O seu ledger do Módulo 6, uma lista append-only de lançamentos da qual os saldos são derivados, é event sourcing na prática, mesmo que você nunca o chame assim. No TCM você não precisa de um serviço completo com event sourcing. Você precisa dos hábitos: eventos imutáveis, versões e replays sem efeitos colaterais.

## 5. CQRS em uma página

*Fonte principal: Martin Fowler, "CQRS" (bliki).*

A nota curta de Fowler sobre CQRS começa assim: "CQRS stands for Command Query Responsibility Segregation." A ideia, que ele credita a Greg Young, é usar um modelo para mudar dados e um modelo diferente para lê-los. Os modelos de leitura costumam ser construídos a partir dos eventos que o lado de escrita emite, então CQRS e event sourcing são usados juntos com frequência.

Em uma carteira, o lado de escrita é o ledger com transações estritas. O lado de leitura pode ser uma tabela de extrato ou um índice de busca, atualizado por um consumidor de `wallet.account-events`. O lado de leitura é eventualmente consistente: uma transferência pode levar um instante para aparecer no extrato.

Fowler é direto sobre o risco: "Despite these benefits, you should be very cautious about using CQRS." Ele diz que a maioria dos sistemas se encaixa em um modelo CRUD simples, e que o CQRS só cabe em partes específicas de um sistema. Na entrevista, mencione que o extrato é um modelo de leitura no estilo CQRS, e que a checagem de saldo antes de um débito nunca pode ler dele.

## 6. Webhooks assinados: a especificação Standard Webhooks

*Fonte principal: especificação Standard Webhooks, seções "Verifying webhook authenticity" e "Operational considerations".*

Webhooks são eventos entregues por HTTP a outra empresa: um lojista sabendo que um pagamento foi liquidado, ou a sua carteira sabendo por um banco parceiro que um Pix chegou. O receptor precisa conseguir verificar que a requisição é genuína, recente e não duplicada. A especificação Standard Webhooks é uma especificação aberta que define um formato comum para isso.

**Headers.** Toda requisição leva três:

| Header | Conteúdo |
| --- | --- |
| `webhook-id` | ID único da mensagem; continua o mesmo em todo retry |
| `webhook-timestamp` | Tempo Unix em segundos de quando a mensagem foi enviada |
| `webhook-signature` | Uma ou mais assinaturas separadas por espaços, cada uma no formato `v1,<base64>` |

**Assinatura.** A especificação diz: "The content to be signed is therefore: `msg_id.timestamp.payload`." Quem envia calcula o HMAC-SHA256 dessa string com um segredo compartilhado, codifica em base64 e coloca o prefixo `v1,`. Os segredos são aleatórios, de 24 a 64 bytes, codificados em base64 e com o prefixo `whsec_`. A especificação também define assinaturas `v1a` com ed25519 para chaves assimétricas.

Cada parte do conteúdo assinado tem uma função:

- O **body** fica protegido contra alterações.
- O **timestamp** permite ao receptor rejeitar requisições antigas, o que bloqueia ataques de replay. A especificação diz para checar se ele está dentro de uma tolerância, sem fixar um valor; alguns minutos é o comum.
- O **id** é a idempotency key. Um receptor que já processou aquele `webhook-id` confirma e não faz nada.

Verificação no NestJS, usando o `crypto` do Node:

```ts
import { createHmac, timingSafeEqual } from 'node:crypto';

function verify(rawBody: string, h: Record<string, string>, secret: string): boolean {
  const ts = Number(h['webhook-timestamp']);
  if (Math.abs(Date.now() / 1000 - ts) > 300) return false; // tolerância de 5 minutos

  const key = Buffer.from(secret.replace(/^whsec_/, ''), 'base64');
  const expected = createHmac('sha256', key)
    .update(`${h['webhook-id']}.${ts}.${rawBody}`)
    .digest();

  return h['webhook-signature'].split(' ').some((sig) => {
    const [version, value] = sig.split(',');
    const given = Buffer.from(value ?? '', 'base64');
    return version === 'v1' && given.length === expected.length
      && timingSafeEqual(given, expected);
  });
}
```

Três detalhes importam. Assine e verifique os bytes do **body cru**, não um objeto JSON serializado de novo, senão as assinaturas não batem. Compare com uma função de **tempo constante**, como a especificação exige, para que um atacante não descubra a assinatura byte a byte pelos tempos de resposta. Aceite **várias assinaturas**, porque durante a rotação de chaves quem envia assina com o segredo antigo e com o novo, e a especificação diz que os consumidores "can try to verify each signature until one matches."

**Entrega.** Para o lado de quem envia (tarefa 4 do TCM), a especificação recomenda:

- Tratar qualquer `2xx` como sucesso. Tratar `3xx` como falha e não seguir redirecionamentos.
- Em `410 Gone`, desativar o endpoint. Em `429`, `502` ou `504`, desacelerar, e respeitar o `retry-after`.
- Fazer retry com backoff exponencial e jitter aleatório ao longo de vários dias. A agenda de exemplo da especificação espalha as tentativas por cerca de três dias.
- Usar um timeout de requisição; a especificação diz "somewhere between 15 and 30s."

O seu enviador de webhooks é só mais um consumidor do log: lê o evento, envia com `webhook-id = event_id` e, em caso de falha, passa pela mesma máquina de retry e DLQ da seção 2.

## O que anotar hoje

1. Retries sem bloquear: desenhe o tópico principal, os tópicos de retry com seus atrasos e a DLQ. Marque quais erros vão direto para a DLQ, e como funciona um replay da DLQ.
2. Mensagem envenenada e backpressure: o que é cada um, e o que o seu consumidor faz a respeito de cada um.
3. A regra de versão: o SQL que ignora eventos velhos, e por que ele serve para visões de "estado mais recente" mas não para créditos.
4. Event sourcing com suas palavras: as três capacidades que Fowler lista, snapshots, e por que replays precisam de gateways. Acrescente uma linha sobre CQRS e onde a carteira usa um modelo de leitura.
5. Webhooks assinados: os três headers, a string assinada, e contra o que protegem o id, o timestamp e a comparação em tempo constante.
6. Preparação do TCM vinda do lab: uma linha por script de caos (matar o consumidor antes do commit, publicar uma mensagem envenenada, publicar eventos fora de ordem) com o resultado esperado.

## Teste-se

Estas perguntas dão bons flashcards (veja o [guia de flashcards](../../FLASHCARDS.pt-BR.md)).

- Por que fazer retry de um registro que falha dentro do consumidor bloqueia outras contas?
- O que acontece com um registro depois do último tópico de retry, e como você faz o replay dele?
- Que tipos de erro deveriam pular a escada de retry?
- Por que um tópico de retry quebra a ordem por chave, e como as versões tornam isso inofensivo?
- Fowler lista três coisas que o log de eventos torna possíveis. Cite-as.
- O que um receptor de webhook faz com o `webhook-id`, e por que o timestamp limita ataques de replay?
- Por que o HMAC precisa ser calculado sobre o body cru?

## Referências

- **Fonte principal:** Uber Engineering, ["Building Reliable Reprocessing and Dead Letter Queues with Apache Kafka"](https://www.uber.com/us/en/blog/reliable-reprocessing/), 2018. Leia inteiro. Gratuito.
- **Fonte principal:** Martin Fowler, ["Event Sourcing"](https://martinfowler.com/eaaDev/EventSourcing.html), 2005. Leia até "External Interaction" e passe por "Code Changes". Gratuito.
- Martin Fowler, ["CQRS"](https://martinfowler.com/bliki/CQRS.html), bliki, 2011. Uma nota curta. Gratuito.
- **Fonte principal:** Standard Webhooks, [repositório da especificação](https://github.com/standard-webhooks/standard-webhooks); leia o [documento da especificação](https://github.com/standard-webhooks/standard-webhooks/blob/main/spec/standard-webhooks.md), especialmente "Verifying webhook authenticity" e "Operational considerations". Gratuito.
- Apache Kafka, [Javadoc do `KafkaConsumer`](https://kafka.apache.org/39/javadoc/org/apache/kafka/clients/consumer/KafkaConsumer.html), a seção "Consumption Flow Control" sobre `pause()` e `resume()`. Gratuito.
