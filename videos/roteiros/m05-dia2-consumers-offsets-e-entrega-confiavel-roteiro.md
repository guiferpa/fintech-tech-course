# Roteiro · M5 · Dia 2 · Consumers, offsets e entrega confiável


## Abertura

Esta é a aula em vídeo do módulo cinco, dia dois: consumers, offsets e entrega confiável.

Ontem você concluiu que eventos podem chegar duas vezes. Hoje é a outra metade. Consumidores caem, reiniciam e perdem suas partições para outra instância. Cada um desses momentos pode fazer um evento ser processado de novo, ou, com a estratégia de commit errada, nunca ser processado. Numa carteira, isso é cashback pago duas vezes, ou um extrato sem uma transferência. O teste de domínio do módulo é exatamente este: o consumidor gravou no banco e morreu antes de commitar o offset. No fim da aula, você vai saber responder.


## Consumer groups e offsets

Consumidores que compartilham um group I D formam um consumer group. O Kafka divide as partições entre os membros, e cada partição pertence a exatamente um consumidor do grupo.

Grupos diferentes são independentes. O serviço de notificações e o gerador de extrato leem o mesmo tópico, cada um com seus offsets.

Cada consumidor tem dois números por partição. A posição é o offset do próximo registro que o poll vai devolver. Ela avança conforme você lê.

O offset commitado é a posição guardada de forma durável para o grupo. Depois de uma queda ou de um rebalanceamento, o novo dono começa daqui.

E o valor é preciso: o offset commitado é o da próxima mensagem que você vai ler. Processou o quarenta e um, commite o quarenta e dois. Commitar o quarenta e um faz ele ser lido de novo depois de um reinício. É um erro de um a menos muito comum.

E as partições limitam o paralelismo. Com seis partições e oito consumidores, dois ficam parados.

> **Pausa:** Pergunta: qual a diferença entre a posição do consumidor e o offset commitado?

A posição é o próximo registro que o poll devolve, e vive na memória. O offset commitado é guardado de forma durável, e é dali que o próximo dono da partição recomeça.


## Rebalanceamento

Um rebalanceamento redistribui as partições do grupo. Ele acontece quando um membro entra, sai ou falha, ou quando partições são adicionadas. O Kafka decide que um consumidor falhou de duas formas: heartbeats em segundo plano, com o session timeout, e o intervalo entre polls, o max poll interval. Para continuar no grupo, você precisa continuar chamando poll.

O segundo pega código de pagamento. Suponha que você busque quinhentos registros por poll, e cada um chame um banco parceiro.

Às vezes o parceiro leva trinta segundos.

Você estoura o intervalo de poll, e o consumidor sai do grupo.

O grupo rebalanceia, e suas partições vão para outra instância.

Essa instância começa do último offset commitado, e reprocessa registros que você já tinha processado. Quando você finalmente tenta commitar, falha, porque não é mais dono da partição.

Duas correções. Reduza o max poll records, para um lote terminar a tempo.

E nunca coloque uma chamada externa lenta no loop do consumidor sem timeout.

E lembre: rebalanceamentos são normais. Todo deploy causa um. Projete como se as partições trocassem de dono o tempo todo.

> **Pausa:** Pergunta: cite dois eventos que disparam um rebalanceamento.

Um membro entrar, sair ou falhar, inclusive por estourar o intervalo de poll. E partições serem adicionadas a um tópico assinado.


## Commit antes ou depois

Agora a decisão central. O consumidor pode salvar sua posição antes ou depois de processar um registro. Uma queda no meio dá dois resultados diferentes.

Commit primeiro, depois processa: se cair no meio, o novo dono começa depois do registro, e ele é pulado. Isso é at-most-once.

Processa primeiro, depois commit: se cair no meio, o novo dono lê o registro de novo. Isso é at-least-once.

Com dinheiro, perder um evento nunca é aceitável. Então você sempre processa e depois commita, e torna o processamento idempotente. E atenção ao auto-commit. Ele commita offsets em segundo plano, e o offset pode passar do que você realmente processou. É a primeira linha da tabela, escondida. No Kafka J S e no Nest J S ele costuma vir ligado. Desligue, e commite depois que a transação do banco fizer commit.

> **Pausa:** Pergunta: por que o auto-commit pode perder registros?

Porque ele commita periodicamente, sem saber o que você terminou. Se você cair antes de processar o que o poll devolveu, o offset já passou desses registros, e eles são pulados.


## O inbox

At-least-once significa duplicatas. Você lida com elas no consumidor, com um inbox: uma tabela de mensagens processadas, com chave primária no nome do consumidor e no event I D.

A regra é: o efeito do evento e o registro de que ele foi processado vão na mesma transação do banco. Primeiro você insere no inbox, com on conflict do nothing. Se zero linhas entraram, é duplicata: commit e pule o efeito. Senão, grave o crédito de cashback, e faça commit. Só depois disso, commite o offset no Kafka, o processado mais um.

Por que na mesma transação? Porque ou os dois ficam, ou nenhum fica. Se fossem separados, uma queda entre eles deixaria o crédito sem registro, ou o registro sem crédito.

E o inbox também protege contra duplicatas do lado do producer, como o reenvio do outbox de ontem, que nenhum truque com offset pega. Existe uma variante que guarda os offsets no próprio banco e faz seek ao receber partições. Ela evita a leitura duplicada, mas exige mais código. No projeto, use o inbox.


## O teste de domínio

Agora responda o teste de domínio, passo a passo.

O consumidor A lê o evento, e a transação do banco faz commit: inbox e crédito gravados.

A morre antes de commitar o offset.

Um rebalanceamento entrega a partição ao consumidor B, que começa do offset commitado antigo.

B lê o mesmo evento. O insert no inbox bate na chave primária e insere zero linhas.

Então B pula o efeito, faz commit da transação, e commita o offset. O evento foi entregue duas vezes e aplicado uma. É isso que efetivamente uma vez significa na prática.

> **Pausa:** Pergunta: por que a inserção no inbox e o efeito de negócio precisam estar na mesma transação?

Porque, separados, uma queda entre os dois deixa um sem o outro. Ou o efeito acontece sem registro, e se repete, ou o registro fica sem efeito, e o evento se perde.


## O loop no KafkaJS

No Kafka J S, o loop fica assim.

Primeiro, o loop.

Com auto commit falso, porque no Kafka J S ele vem ligado.

Para cada mensagem, você lê o event I D do header e chama apply once, que é a transação com o inbox.

Só depois, commit offsets, com o offset da mensagem mais um.


## Entrega confiável

Confiabilidade é uma propriedade da cadeia inteira, não só do broker. Um elo fraco quebra a garantia. Aqui está o checklist da carteira.

No tópico: fator de replicação três e min in sync replicas dois, para sobreviver a um broker caído.

No broker: unclean leader election desligada, para nunca promover uma réplica que não tem os registros committed.

No producer: acks all e idempotência ligada. O envio só está feito quando está committed.

No outbox: marque como publicado só depois do ack. Uma queda vira reenvio, nunca perda.

No consumidor: auto-commit desligado, e commit depois da transação do banco. Uma queda vira reprocessamento, nunca pulo.

E o inbox com event I D, para o reprocessamento não gerar um segundo efeito.

Repare no padrão: todo elo pode duplicar, e nenhum elo pode perder. A deduplicação acontece uma vez, no lugar onde o efeito acontece.


## Exactly-once do Kafka

Por fim, o exactly-once do Kafka. A Confluent abre o artigo dizendo que é a garantia mais desejada, e uma das mais mal entendidas.

São três peças. O producer idempotente, que descarta duplicatas de retry pelo número de sequência.

Transações, com um transactional I D. O producer grava em várias partições de forma atômica, e commita os offsets do consumidor na mesma transação, com send offsets to transaction. Um transactional I D estável também permite isolar uma instância zumbi.

Consumidores com read committed só veem registros de transações confirmadas.

E o Kafka Streams embrulha estado, saída e offsets nessas transações. O custo relatado é pequeno, cerca de três por cento de vazão.

Agora o limite, que é o que interessa ao entrevistador. As transações tornam atômico ler do Kafka e escrever no Kafka. Elas não fazem nada por um insert no seu ledger no Postgres.

Nem por uma chamada ao banco parceiro ou ao Pix.

Nem por um webhook para um lojista, ou um e-mail, ou uma notificação push.

Se o consumidor grava no Postgres e a transação do Kafka aborta, a linha no Postgres fica. Fora do Kafka, você volta ao at-least-once com idempotência: inbox, idempotency keys nos parceiros, e event I D nos webhooks. Na entrevista, diga: o Kafka dá exactly-once dentro do Kafka. Fora dele, eu construo efetivamente uma vez com entrega at-least-once e consumidores idempotentes.

> **Pausa:** Pergunta: as transações do Kafka estão ligadas. O consumidor insere no Postgres, e a transação aborta. O que acontece com a linha?

Ela fica. A transação do Kafka não alcança o Postgres. Por isso o inbox continua necessário.


## Revisão relâmpago

Hora da revisão relâmpago. São três perguntas, sem olhar.

> **Pausa:** Pergunta um: você processou o registro no offset quarenta e um. Qual offset commita?

Quarenta e dois, o offset da próxima mensagem que você vai ler.

> **Pausa:** Pergunta dois: commitar primeiro e processar depois dá que garantia, e o que uma queda faz?

At-most-once. Uma queda no meio faz o registro ser pulado.

> **Pausa:** Pergunta três: por que o max poll interval importa quando o handler chama um parceiro lento?

Porque o lote demora mais que o intervalo, o consumidor sai do grupo, a partição vai para outro, e os registros são reprocessados.


## O que anotar e próximo passo

Anote com as suas palavras: consumer groups e o que dispara um rebalanceamento. A tabela de commit antes ou depois, e o perigo do auto-commit. Sua resposta ao teste de domínio com o inbox. E as três peças do exactly-once, com a lista do que elas não cobrem.

Depois, leia o capítulo sete de Kafka: The Definitive Guide, sobre entrega confiável. Até a próxima aula.
