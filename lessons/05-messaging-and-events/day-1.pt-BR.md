# Módulo 5, segunda-feira: o log, partições e producers

[Módulo 5](../../modules/05-messaging-and-events.pt-BR.md) · [Read in English](day-1.md)

**Tempo de leitura:** cerca de 45 minutos. Use o resto do bloco de 2 horas nas referências do final, começando pelas seções marcadas como fonte principal.

Este é um texto original escrito para este curso. Ele se baseia nas referências listadas no final, e cada seção indica a fonte que segue. Quando uma ideia vem de um autor específico, o texto diz isso.

## Por que isso importa para uma fintech

No Módulo 4 você gravou eventos em uma tabela outbox na mesma transação da movimentação de dinheiro. Esses eventos ainda precisam chegar a outros serviços: o serviço de notificações, as checagens de fraude, o gerador de extrato, o enviador de webhooks. Nesta semana eles passam por um log (Kafka, ou Redpanda nos labs).

Um log não é um cano mágico. Ele só garante ordem dentro de uma partição, pode entregar o mesmo evento duas vezes, e é o producer que decide quão durável uma escrita realmente é. Se você escolher a chave de partição errada, dois eventos da mesma conta podem ser processados na ordem errada, e um saldo pode andar para trás. Hoje o assunto são as garantias que você tem do lado de quem produz, e as que você não tem.

## 1. O que é um log

*Fonte principal: Jay Kreps, "The Log", Parte Um.*

Jay Kreps, um dos criadores do Kafka no LinkedIn, descreve o log como a abstração de armazenamento mais simples possível. Nas palavras dele, "It is an append-only, totally-ordered sequence of records ordered by time." Registros novos vão para o final. Registros antigos nunca são alterados no lugar. Cada registro recebe um número sequencial, que o Kafka chama de **offset**.

Kreps faz dois pontos que importam para uma carteira digital:

- **O offset é um relógio em que você pode confiar.** A ordem dos registros no log define o "tempo" sem nenhum relógio físico. O Módulo 1 mostrou que relógios de parede discordam entre máquinas. Um log troca "qual timestamp é anterior" por "qual offset é menor", e essa pergunta tem uma única resposta.
- **O log mais uma posição descrevem uma réplica.** Se processos determinísticos recebem as mesmas entradas na mesma ordem, chegam ao mesmo estado. Kreps chama isso de princípio da replicação de máquina de estados. Um consumidor pode ser descrito por completo pelo último offset que processou.

Ele também aponta que tabelas e eventos são duais. Uma tabela guarda o estado atual. O log de mudanças guarda como você chegou lá. Você pode reconstruir a tabela reproduzindo o log, e pode produzir o log registrando cada mudança na tabela. O write-ahead log do seu Postgres (Módulo 1, terça-feira) é exatamente essa ideia dentro de um banco de dados. O Debezium (Módulo 4) a expõe para o mundo de fora.

Para uma carteira digital, pense no log como o histórico ordenado das "coisas que aconteceram": `TransferCompleted`, `DepositSettled`, `HoldReleased`. O ledger no Postgres continua sendo a fonte da verdade para os saldos. O log é como o resto da empresa fica sabendo dessas mudanças, em ordem.

## 2. Filas versus logs

*Fonte principal: Jay Kreps, "The Log", Parte Dois, e a documentação do Apache Kafka, "Design".*

Kreps diz que prefere a palavra "log" a "sistema de mensageria" porque pub/sub diz pouco sobre garantias. A diferença fica clara quando você compara uma fila clássica com um log.

| | Fila clássica (por exemplo RabbitMQ, SQS) | Log (Kafka, Redpanda) |
| --- | --- | --- |
| O que acontece depois de uma leitura | O broker apaga a mensagem quando ela é confirmada | O registro fica; só a retenção o remove |
| Quem acompanha o progresso | O broker, por mensagem | Cada consumer group, como um offset por partição |
| Vários leitores independentes | Precisa de uma fila por leitor (fan-out) | Cada grupo lê os mesmos registros no seu ritmo |
| Reprocessar depois de corrigir um bug | Impossível depois do ack | Volte o offset e leia de novo |
| Ordem | Em geral fraca quando vários consumidores competem | Ordem total dentro de cada partição |

A documentação de design do Kafka explica por que isso é barato: para cada partição, a posição de um consumidor é um único inteiro, o offset do próximo registro a ler. Acompanhar um número por partição custa muito menos do que acompanhar um estado de confirmação para cada mensagem.

Kreps descreve o log como um buffer: "The log acts as a very, very large buffer that allows process to be restarted or fail" sem atrasar o resto do pipeline. Se o seu gerador de extrato ficar fora do ar por uma hora, o producer continua escrevendo. Quando o gerador volta, ele continua a partir do último offset commitado e alcança o atraso.

Registros não vivem para sempre. Kreps descreve duas políticas, as duas disponíveis no Kafka:

- **Retenção por tempo ou tamanho.** Dados de eventos ficam guardados por uma janela (Kreps menciona uma janela de alguns dias), depois são apagados.
- **Log compaction.** Para dados com chave, registros antigos de uma chave são removidos quando existe um registro mais novo para a mesma chave. O log ainda guarda o valor mais recente de cada chave, mas os estados intermediários somem.

Um tópico compactado serve bem para "status atual de cada cliente". Ele é errado para movimentações de dinheiro, em que todo evento importa. Mantenha eventos de transferência em um tópico com retenção por tempo, e mantenha o histórico permanente no seu ledger.

## 3. Tópicos, partições e ordem por chave

*Fonte principal: Jay Kreps, "The Log", "Building a Scalable Log", e a documentação do Apache Kafka, "Design".*

Um log em uma máquina só não escala. O Kafka divide cada **tópico** em **partições**, e cada partição é um log próprio. Kreps descreve o trade-off sem rodeios: "Each partition is a totally ordered log, but there is no global ordering between partitions". Registros de um producer para uma partição chegam na ordem em que foram enviados.

Quem escolhe a partição é o producer. Segundo a documentação de design do Kafka, se um registro tem uma **chave**, a chave passa por um hash para escolher a partição, então todos os registros com a mesma chave caem na mesma partição. Essa é a única ferramenta de ordem que você tem. Escolha como chave "a coisa cujos eventos precisam ficar em ordem".

| Escolha de chave | O que fica em ordem | Risco |
| --- | --- | --- |
| Sem chave (round robin ou sticky) | Nada entre registros | Dois eventos de uma conta podem ser processados fora de ordem |
| `transfer_id` | Os eventos de uma transferência | Eventos da mesma conta vindos de transferências diferentes podem se intercalar |
| `account_id` | Todos os eventos que tocam uma conta | Uma conta muito ativa vira uma partição quente |
| `customer_id` | Todos os eventos de um cliente, em todas as contas | Mais grosso, mais chance de pontos quentes |

Para a carteira, `account_id` é a escolha usual, e é a que o lab de terça usa. Uma transferência toca duas contas, então ou você publica um evento por conta afetada (com a chave de cada conta), ou escolhe a conta de origem como chave e aceita que a ordem só é garantida do ponto de vista dessa conta. Anote qual você escolheu.

Dois alertas sobre chaves:

- **O mapeamento depende do número de partições.** O hash é tomado módulo o número de partições. Se você adicionar partições depois, registros novos de uma chave podem cair em uma partição diferente da dos antigos, e a ordem quebra durante a transição. Escolha um número generoso de partições desde o início.
- **O paralelismo é limitado pelas partições.** Dentro de um consumer group, cada partição é lida por exatamente um consumidor de cada vez. Seis partições significam no máximo seis consumidores ocupados nesse grupo. A aula de terça trata disso.

## 4. Acks do producer e durabilidade

*Fonte principal: documentação do Apache Kafka, "Design" (replicação), e o Javadoc do `KafkaProducer`. O capítulo 3 de "Kafka: The Definitive Guide" cobre as mesmas configurações com mais profundidade.*

Quando um producer envia um registro, o broker líder da partição o grava, e os brokers seguidores o copiam. A configuração `acks` decide quando o producer considera o envio completo. O Javadoc do `KafkaProducer` resume assim: "The `acks` config controls the criteria under which requests are considered complete."

| `acks` | O producer recebe sucesso quando | O que você pode perder |
| --- | --- | --- |
| `0` | Escreveu no socket, sem esperar o broker | Qualquer coisa: o broker pode nunca ter recebido |
| `1` | O líder gravou no próprio log | Registros que o líder ainda não tinha replicado quando caiu |
| `all` (ou `-1`) | Todas as réplicas em sincronia têm o registro | Nada, desde que uma réplica em sincronia sobreviva |

A documentação de design define um registro **committed** como aquele que todas as réplicas do **conjunto de réplicas em sincronia (ISR)** aplicaram. Um seguidor que fica para trás sai do ISR. Isso cria uma armadilha: com `acks=all`, se o ISR encolher até sobrar só o líder, "todas" significa uma cópia. A configuração de tópico `min.insync.replicas` fecha essa brecha. Se o ISR for menor que esse número, a partição rejeita escritas de producers com `acks=all`. A documentação descreve isso como trocar disponibilidade por durabilidade.

Para eventos de pagamento, a configuração usual é fator de replicação 3, `min.insync.replicas=2` e `acks=all`. Um broker pode falhar e as escritas continuam. Se dois falharem, as escritas param, e é isso que você quer: um erro que você pode tentar de novo é melhor que um evento que some em silêncio.

Segundo o Javadoc, desde o Kafka 3.0 o producer Java usa por padrão `acks=all` com idempotência ligada. Outros clientes têm seus próprios padrões, então sempre confira e defina esses valores explicitamente.

## 5. O producer idempotente e seus limites

*Fonte principal: documentação do Apache Kafka, "Design", e o Javadoc do `KafkaProducer`.*

Um producer com `acks=all` espera o broker, e a resposta do broker pode se perder, exatamente o problema de timeout do Módulo 1. O producer faz retry, e sem proteção o registro é gravado duas vezes.

O **producer idempotente** resolve esse caso específico. A documentação de design explica o mecanismo: "The broker assigns each producer an ID and deduplicates messages using a sequence number." Cada lote carrega o ID do producer e um número de sequência por partição. Se o broker vê um número de sequência que já gravou, ele confirma sem gravar de novo. Ele também mantém em ordem os registros de um producer quando há retries.

Leia os limites com atenção, porque eles decidem o design do seu consumidor:

- **Só cobre retries dentro de uma sessão do producer.** O Javadoc diz que ele remove duplicatas causadas pelos retries do próprio producer, mas só dentro de uma única sessão. Se o seu processo reinicia, o novo producer tem um novo ID.
- **Reenvios feitos pela sua aplicação não são cobertos.** O Javadoc avisa que as aplicações devem evitar reenvios próprios, porque o broker não consegue deduplicá-los.

Agora aplique isso ao publicador do outbox do Módulo 4. Ele lê uma linha, envia, espera o ack e então marca a linha como publicada. Se ele cair depois do envio e antes do update, a próxima execução envia a linha de novo com um producer novo. O broker vê dois registros diferentes. Então **o outbox dá publicação at-least-once, e os consumidores precisam deduplicar pelo ID do evento.** É por isso que todo evento precisa de um `event_id` estável (o ID da linha do outbox serve bem), e por isso o consumidor de quinta tem uma tabela de inbox.

Um esboço de producer em TypeScript com KafkaJS (qualquer cliente tem configurações equivalentes):

```ts
const producer = kafka.producer({ idempotent: true, maxInFlightRequests: 1 });
await producer.connect();

// Uma linha do outbox vira um registro, com account_id como chave.
await producer.send({
  topic: 'wallet.account-events',
  acks: -1, // todas as réplicas em sincronia
  messages: [{
    key: row.accountId,
    value: JSON.stringify(row.payload),
    headers: { event_id: row.id, event_type: row.type, version: String(row.version) },
  }],
});

await db.query(
  'UPDATE outbox SET published_at = now() WHERE id = $1',
  [row.id],
); // uma queda antes desta linha faz a linha ser enviada de novo
```

O header `version` não é um recurso do Kafka. É a sequência por conta que o seu consumidor vai usar na quinta para ignorar eventos velhos.

## 6. O que testar no lab de hoje

*Fonte principal: as seções 2 a 4 desta aula, aplicadas ao lab.*

O lab roda o Redpanda no Docker Compose. O Redpanda fala o protocolo do Kafka, então os mesmos clientes e os mesmos conceitos valem. Use-o para ver as garantias com seus próprios olhos:

```bash
# Um tópico com 6 partições
rpk topic create wallet.account-events -p 6

# Produza registros com chave: "chave:valor" por linha
kcat -b localhost:9092 -t wallet.account-events -P -K:
acc-1:{"type":"Deposit","amount":100}
acc-2:{"type":"Deposit","amount":50}
acc-1:{"type":"Withdrawal","amount":30}

# Consuma e imprima partição, offset e chave
kcat -b localhost:9092 -t wallet.account-events -C -e \
  -f 'p=%p o=%o k=%k %s\n'
```

Confira três coisas. Todo registro de `acc-1` mostra a mesma partição. Os offsets crescem de um em um dentro de uma partição e são independentes entre partições. Ler o tópico uma segunda vez devolve os mesmos registros, porque ler não apaga nada. Esse último ponto é a ideia de "log, não fila" em um comando.

## O que anotar hoje

1. Filas versus logs: uma tabela com o que acontece depois de uma leitura, quem acompanha o progresso, reprocessamento e ordem. Acrescente uma frase sobre o que é um offset e por que um consumidor pode ser descrito por um número por partição.
2. Sua chave de partição para os eventos da carteira, por que você a escolheu, e que ordem você tem e não tem com ela (por chave, nunca global).
3. `acks=0`, `1` e `all`, o que cada um pode perder, e o papel do `min.insync.replicas`.
4. O que o producer idempotente evita e o que não evita (reinícios, seus próprios reenvios), e a conclusão para os seus consumidores.

## Teste-se

Estas perguntas dão bons flashcards (veja o [guia de flashcards](../../FLASHCARDS.pt-BR.md)).

- O que Kreps quer dizer quando afirma que o log define o tempo sem um relógio?
- Depois que um consumidor lê um registro de um log, o registro é apagado? O que o remove?
- Quais registros o Kafka mantém em ordem, e quais não?
- Por que adicionar partições a um tópico pode quebrar a ordem por chave?
- Com `acks=all`, como uma escrita ainda pode acabar com uma só cópia, e qual configuração evita isso?
- Seu publicador do outbox caiu depois de enviar e antes de marcar a linha como publicada. O producer idempotente evita a duplicata? Por que não?

## Referências

- **Fonte principal:** Jay Kreps, ["The Log: What every software engineer should know about real-time data's unifying abstraction"](https://engineering.linkedin.com/distributed-systems/log-what-every-software-engineer-should-know-about-real-time-datas-unifying), LinkedIn Engineering, 2013. Leia a Parte Um inteira e, na Parte Dois, "Log-structured data flow" e "Building a Scalable Log"; passe pela seção "Log Compaction" da Parte Três. Gratuito.
- Gwen Shapira, Todd Palino, Rajini Sivaram e Krit Petty, ["Kafka: The Definitive Guide", 2ª edição](https://www.confluent.io/resources/kafka-the-definitive-guide-v2/), O'Reilly, capítulo 3 (Producers): configuração de `acks`, retries e idempotência, e como as chaves são mapeadas para partições. Gratuito, com cadastro. Leia para ver os detalhes completos por trás desta aula.
- Documentação do Apache Kafka, ["Design"](https://kafka.apache.org/41/design/design/): leia as partes sobre o producer, a replicação (ISR, `min.insync.replicas`) e a semântica de entrega de mensagens. Gratuito.
- Apache Kafka, [Javadoc do `KafkaProducer`](https://kafka.apache.org/39/javadoc/org/apache/kafka/clients/producer/KafkaProducer.html): a descrição da classe explica `acks`, idempotência e transações. Gratuito.
