# Módulo 5, terça-feira: consumidores, offsets e exactly-once

[Módulo 5](../../modules/05-messaging-and-events.pt-BR.md) · [Read in English](day-2.md)

**Tempo de leitura:** cerca de 45 minutos. Use o resto do bloco de 2 horas nas referências do final, começando pelas seções marcadas como fonte principal.

Este é um texto original escrito para este curso. Ele se baseia nas referências listadas no final, e cada seção indica a fonte que segue. Quando uma ideia vem de um autor específico, o texto diz isso.

## Por que isso importa para uma fintech

A segunda-feira terminou com uma conclusão: eventos podem chegar duas vezes. Hoje você vê a outra metade. Consumidores caem, reiniciam e têm suas partições movidas para outra instância, e cada um desses momentos pode fazer um evento ser processado de novo ou, com a estratégia de commit errada, nunca ser processado.

Em uma carteira digital, "processado duas vezes" pode significar um cliente recebendo duas notificações de crédito, ou pior, um cashback pago duas vezes. "Nunca processado" pode significar um extrato sem uma transferência. O teste de domínio deste módulo é exatamente essa situação: o consumidor gravou no banco e morreu antes de commitar o offset. Ao final de hoje você deve conseguir respondê-lo.

## 1. Consumer groups e offsets

*Fonte principal: Apache Kafka, Javadoc do `KafkaConsumer`, e a documentação do Kafka, "Design".*

Consumidores que compartilham um `group.id` formam um **consumer group**. O Kafka divide as partições do tópico entre os membros, e a cada momento cada partição pertence a exatamente um consumidor do grupo. Grupos diferentes são independentes: o serviço de notificações e o gerador de extrato têm cada um seu grupo e seus offsets no mesmo tópico.

Um consumidor tem dois números por partição, e o Javadoc os separa bem:

- A **posição** é o offset do próximo registro que o `poll()` vai devolver. Ela avança conforme você lê.
- O **offset commitado** é a posição guardada de forma durável para o grupo. Depois de uma queda ou de um rebalanceamento, o novo dono da partição começa daqui.

O Javadoc é preciso sobre o valor: "The committed offset should always be the offset of the next message that your application will read." Se você processou o offset 41, commita 42. Commitar 41 significa que o registro 41 é lido de novo depois de um reinício. Esse erro de um a menos é comum em entrevistas e em código.

As partições limitam o paralelismo. Com 6 partições e 8 consumidores em um grupo, 2 consumidores ficam ociosos. Com 6 partições e 2 consumidores, cada consumidor fica com 3 partições. Se você precisar de mais vazão depois, precisa de mais partições, e a segunda-feira mostrou que adicionar partições move as chaves.

## 2. Rebalanceamento: quando as partições trocam de dono

*Fonte principal: Apache Kafka, Javadoc do `KafkaConsumer`. O capítulo 4 de "Kafka: The Definitive Guide" cobre o rebalanceamento e suas estratégias em profundidade.*

Um **rebalanceamento** redistribui as partições entre os membros de um grupo. Segundo o Javadoc, ele acontece quando um membro entra, sai ou falha, quando partições são adicionadas a um tópico assinado, ou quando uma assinatura por padrão encontra um tópico novo.

O Kafka tem duas formas de decidir que um consumidor falhou:

- **Heartbeats.** O cliente envia heartbeats em segundo plano. Se nenhum chegar dentro de `session.timeout.ms`, o membro é considerado morto.
- **Intervalo de poll.** Se o seu código não chamar `poll()` de novo dentro de `max.poll.interval.ms`, o consumidor sai do grupo. O Javadoc diz isso diretamente: "So to stay in the group, you must continue to call poll."

O segundo pega código de pagamento. Suponha que cada registro chame um banco parceiro que às vezes leva 30 segundos, e que você busque 500 registros por poll. Você estoura o intervalo, o grupo rebalanceia, suas partições vão para outra instância, e essa instância começa do último offset commitado. Registros que você já processou são processados de novo. Quando você finalmente tenta commitar, o commit falha porque você não é mais dono da partição. Duas correções: reduza `max.poll.records` para que um lote termine a tempo, e nunca coloque chamadas externas lentas no loop do consumidor sem um timeout.

O Javadoc também descreve um `ConsumerRebalanceListener`. Ele permite commitar o progresso quando partições são revogadas e restaurar posições quando partições são atribuídas. Rebalanceamentos são eventos normais em um sistema saudável (todo deploy causa um), então projete como se as partições mudassem de dono com frequência.

## 3. Commit antes ou depois de processar

*Fonte principal: documentação do Apache Kafka, "Design", seção sobre semântica de entrega de mensagens. Os capítulos 4 e 7 de "Kafka: The Definitive Guide" discutem a mesma escolha.*

A documentação de design do Kafka descreve a decisão central em poucas linhas. Um consumidor pode salvar sua posição antes ou depois de processar um registro, e uma queda no meio dá dois resultados diferentes:

| Ordem dos passos | Queda entre os passos | Semântica de entrega |
| --- | --- | --- |
| Commit do offset, depois processa | O registro é pulado; o novo dono começa depois dele | At most once |
| Processa, depois commit do offset | O registro é processado de novo pelo novo dono | At least once |

A documentação diz que o Kafka garante entrega at-least-once por padrão, e observa que processamento idempotente torna a segunda opção segura. Com dinheiro, perder um evento nunca é aceitável, então você sempre escolhe **processar, depois commitar**, e torna o processamento idempotente.

**O auto-commit é a versão escondida da primeira linha.** Com `enable.auto.commit=true`, o cliente commita offsets periodicamente em segundo plano. O Javadoc avisa que, se você não terminar de processar tudo que um poll devolveu antes do próximo poll ou do close, o offset commitado pode passar do que você realmente processou, e esses registros se perdem. Em microservices do NestJS ou no KafkaJS, o auto-commit costuma vir ligado por padrão. Desligue-o em tudo que movimenta dinheiro, e commite explicitamente depois que a transação do banco fizer commit.

## 4. Tornando o at-least-once seguro: o inbox

*Fonte principal: Apache Kafka, Javadoc do `KafkaConsumer` ("Storing Offsets Outside Kafka"), aplicado ao TCM deste curso.*

At-least-once significa duplicatas. Você lida com elas no consumidor com um **inbox** (também chamado de tabela de mensagens processadas). O efeito do evento e o registro de que ele foi processado são gravados na **mesma transação do banco**:

```sql
CREATE TABLE processed_messages (
  consumer_name text        NOT NULL,
  event_id      uuid        NOT NULL,
  processed_at  timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (consumer_name, event_id)
);

BEGIN;
INSERT INTO processed_messages (consumer_name, event_id)
VALUES ('cashback', $1)
ON CONFLICT DO NOTHING;
-- se 0 linhas foram inseridas: duplicata, faça COMMIT e pule o efeito
INSERT INTO cashback_credits (account_id, transfer_id, amount_cents)
VALUES ($2, $3, $4);
COMMIT;
-- só agora: commit do offset no Kafka (offset processado + 1)
```

Percorra o teste de domínio com esse design. O consumidor lê o evento, a transação faz commit, e o processo morre antes de commitar o offset. Um rebalanceamento entrega a partição a outra instância, que começa do offset commitado antigo e lê o mesmo evento. O `INSERT INTO processed_messages` dela bate na chave primária e insere zero linhas, então ela pula o efeito, faz commit da transação e commita o offset. O evento foi entregue duas vezes e aplicado uma. É isso que "efetivamente uma vez" significa na prática.

O Javadoc descreve uma variante mais forte: guardar os próprios offsets no seu banco, na mesma transação dos resultados. Na inicialização, ou quando partições são atribuídas, você faz `seek()` para o offset guardado em vez de usar o offset commitado no Kafka. Isso elimina a leitura duplicada, ao custo de mais código (rebalance listener, seek). O inbox é mais simples e também protege contra duplicatas que vêm do lado do producer, como o reenvio do outbox da segunda-feira, que truques com offset não pegam. No TCM, use o inbox.

Um loop de consumidor no KafkaJS com commits manuais fica assim:

```ts
await consumer.run({
  autoCommit: false,
  eachMessage: async ({ topic, partition, message }) => {
    const eventId = message.headers?.event_id?.toString();
    await this.cashback.applyOnce(eventId, JSON.parse(message.value!.toString()));
    await consumer.commitOffsets([
      { topic, partition, offset: (BigInt(message.offset) + 1n).toString() },
    ]);
  },
});
```

## 5. Entrega confiável de ponta a ponta

*Fonte principal: documentação do Apache Kafka, "Design" (replicação). O capítulo 7 de "Kafka: The Definitive Guide", "Reliable Data Delivery", é o tratamento completo; leia-o hoje.*

O capítulo 7 do livro olha a confiabilidade como uma propriedade da cadeia inteira, não só do broker. A ideia central é que o broker, o producer e o consumidor precisam cada um estar configurado corretamente, e um elo fraco quebra a garantia. Os detalhes e o raciocínio por trás de cada configuração estão no livro. Como checklist para a carteira:

| Elo | Configuração ou prática | Por quê |
| --- | --- | --- |
| Tópico | Fator de replicação 3, `min.insync.replicas=2` | Sobreviver à falha de um broker sem perder registros committed |
| Broker | Eleição de líder unclean desligada (`unclean.leader.election.enable=false`) | Nunca promover uma réplica sem registros committed |
| Producer | `acks=all`, idempotência ligada, tratar erros de envio | Um envio só está "feito" quando está committed |
| Outbox | Marcar como publicado só depois do ack | Queda significa reenvio, nunca perda |
| Consumidor | Auto-commit desligado, commit depois da transação do banco | Queda significa reprocessar, nunca pular |
| Consumidor | Inbox com `event_id` | Reprocessar não gera um segundo efeito |

Repare no padrão: todo elo pode duplicar, e nenhum elo pode perder. A deduplicação acontece uma vez, no lugar onde o efeito acontece.

## 6. O exactly-once do Kafka e onde ele acaba

*Fonte principal: blog da Confluent, "Exactly-Once Semantics Are Possible: Here's How Kafka Does It".*

O artigo da Confluent, escrito quando o Kafka 0.11 trouxe a semântica exactly-once, abre com esta frase: "Exactly-once semantics is the most desirable guarantee, but also a poorly understood one." Ele define as três garantias do lado do producer. At-least-once faz retry e pode duplicar. At-most-once não faz retry e pode perder. Exactly-once entrega cada mensagem uma vez ao consumidor final mesmo quando o producer faz retry.

O Kafka constrói isso com três peças:

1. **Producer idempotente** (`enable.idempotence=true`): números de sequência permitem ao broker descartar duplicatas de retries, como você viu na segunda-feira.
2. **Transações** (`transactional.id`): um producer pode gravar em várias partições de forma atômica, e pode commitar os offsets do consumidor na mesma transação. Consumidores configuram `isolation.level=read_committed` para ver só registros de transações confirmadas. O Javadoc lista as chamadas: `initTransactions()`, `beginTransaction()`, os envios, `sendOffsetsToTransaction()` e então `commitTransaction()`. Um `transactional.id` estável também permite ao broker isolar (fencing) uma instância "zumbi" que ainda acha que é dona do trabalho.
3. **Kafka Streams** com `processing.guarantee=exactly_once`, que embrulha estado, saída e offsets nessas transações.

O artigo relata um custo pequeno: com mensagens de 1 KB e transações de 100 ms, a vazão do producer caiu cerca de 3% em comparação com `acks=all` e uma requisição em voo.

Agora o limite, que é a parte que interessa aos entrevistadores. O artigo afirma: "Exactly-once processing is an end-to-end guarantee". Ele também diz que a garantia do Streams cobre só o processamento interno do Kafka Streams, não efeitos colaterais como chamadas a serviços ou stores remotos. Em outras palavras, transações do Kafka tornam atômico **ler do Kafka, escrever no Kafka**. Elas não fazem nada por:

- Um `INSERT` no seu ledger no Postgres.
- Uma chamada ao banco parceiro ou ao Pix.
- Um webhook para um lojista.
- Um e-mail ou notificação push.

Se o seu consumidor grava no Postgres e depois a transação do Kafka aborta, a gravação no Postgres fica. Para qualquer efeito fora do Kafka você volta ao at-least-once mais idempotência: o inbox, idempotency keys nas chamadas a parceiros (Módulo 2) e `event_id` nos webhooks (amanhã). Na entrevista, diga assim: "O Kafka dá exactly-once dentro do Kafka; fora dele, eu construo efetivamente-uma-vez com entrega at-least-once e consumidores idempotentes."

## O que anotar hoje

1. Consumer groups: uma partição por consumidor por grupo, o que dispara um rebalanceamento, e por que `max.poll.interval.ms` importa quando um handler chama um parceiro lento.
2. Commit antes versus depois de processar: a tabela de duas linhas (queda no meio, resultado, semântica), e por que o auto-commit é a versão perigosa.
3. Sua resposta para o teste de domínio, usando o inbox: o que acontece passo a passo quando o consumidor morre depois de gravar no banco e antes de commitar.
4. Transações do Kafka e exactly-once: as três peças, e a lista de efeitos colaterais na carteira que elas não cobrem.

## Teste-se

Estas perguntas dão bons flashcards (veja o [guia de flashcards](../../FLASHCARDS.pt-BR.md)).

- Você processou o registro no offset 41. Qual offset você commita, e por quê?
- Qual a diferença entre a posição de um consumidor e o seu offset commitado?
- Cite dois eventos que disparam um rebalanceamento.
- Commitar primeiro, depois processar: que garantia isso dá, e o que uma queda faz?
- Por que o auto-commit pode perder registros?
- Por que a inserção no inbox e o efeito de negócio precisam estar na mesma transação do banco?
- As transações do Kafka estão ligadas. O consumidor insere no Postgres e depois a transação aborta. O que acontece com a linha?

## Referências

- **Fonte principal:** Apache Kafka, [Javadoc do `KafkaConsumer`](https://kafka.apache.org/39/javadoc/org/apache/kafka/clients/consumer/KafkaConsumer.html): a descrição da classe, especialmente "Offsets and Consumer Position", "Consumer Groups and Topic Subscriptions", "Detecting Consumer Failures", "Manual Offset Control" e "Storing Offsets Outside Kafka". Gratuito.
- **Fonte principal:** blog da Confluent, ["Exactly-Once Semantics Are Possible: Here's How Kafka Does It"](https://www.confluent.io/blog/exactly-once-semantics-are-possible-heres-how-apache-kafka-does-it/), 2017. Leia inteiro; as seções sobre semântica de stream processing e as observações finais mostram onde a garantia acaba. Gratuito.
- Gwen Shapira, Todd Palino, Rajini Sivaram e Krit Petty, ["Kafka: The Definitive Guide", 2ª edição](https://www.confluent.io/resources/kafka-the-definitive-guide-v2/), O'Reilly, capítulos 4 (Consumers: grupos, rebalanceamento, commits) e 7 (Reliable Data Delivery). Gratuito, com cadastro. Leia para ver os detalhes completos por trás desta aula.
- Documentação do Apache Kafka, ["Design"](https://kafka.apache.org/41/design/design/), a seção sobre semântica de entrega de mensagens. Gratuito.
