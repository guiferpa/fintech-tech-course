# Roteiro · M4 · Dia 2 · Isolamento de sagas e outbox


## Abertura

Esta é a aula em vídeo do módulo quatro, dia dois: isolamento de sagas, reserva de saldo e o transactional outbox.

Ontem a saga deixou dois problemas. Ela não tem isolamento: os passos intermediários já fizeram commit e estão visíveis, e outra requisição pode gastar dinheiro que está a caminho. E cada passo precisa atualizar o banco e avisar o próximo, e uma queda entre as duas coisas perde a mensagem ou anuncia uma mudança que nunca aconteceu. Hoje, as respostas padrão para os dois.


## Sagas são ACD

Richardson descreve a saga como A C D, sem o I. Ela tem atomicidade, porque todos os passos rodam ou são compensados. Consistência em cada serviço. Durabilidade em cada passo. Mas não isolamento. São três anomalias.

Lost update: uma saga sobrescreve a mudança de outra sem lê-la. Uma saga de reembolso marca a transferência como reembolsada, e a saga original, ainda rodando, a volta para concluída.

Dirty read: uma saga lê dados de outra que ainda não terminou, e que depois compensa. A checagem de limite vê um crédito que depois é estornado, e aprova um saque que a Ana não consegue cobrir.

Fuzzy read: dois passos da mesma saga leem o mesmo dado e obtêm valores diferentes.

O ponto a lembrar: não é bug do banco. Cada transação local está totalmente isolada pelo Postgres. As anomalias moram nos intervalos entre as transações, que nenhum banco enxerga.

> **Pausa:** Pergunta: qual letra do ACID falta a uma saga, e por que o Postgres não consegue fornecê-la?

O isolamento. Cada passo faz commit sozinho, e entre um passo e outro não existe transação nenhuma para o Postgres isolar.


## Contramedidas

O livro lista contramedidas. Quatro são as mais úteis para uma carteira.

Semantic lock: um passo marca uma flag que diz este registro está no meio de uma saga, como uma transferência PENDING. O resto do código respeita a flag. É um lock no nível da aplicação, que sobrevive entre transações.

Commutative updates: atualizações cuja ordem não importa. Acrescentar lançamentos ao ledger comuta. Escrever saldo igual a setenta não. Um estorno acrescentado comuta com os lançamentos das outras sagas.

Reordenar os passos: debite o pagador antes de creditar o recebedor. Compensar um débito só devolve à Ana o próprio dinheiro. Compensar um crédito é perigoso, porque o Bruno pode já ter gastado.

E reread value: antes de sobrescrever, releia e confira que nada mudou, com uma coluna version. Para o TCM: debitar primeiro, lançamentos só de acréscimo, e um estado PENDING respeitado por todos.

> **Pausa:** Pergunta: por que debitar antes de creditar é uma contramedida?

Porque, se precisar compensar, devolver um débito é seguro: é o próprio dinheiro da Ana. Já um crédito compensado pode ter sido gasto pelo Bruno.


## Reserva de saldo

Uma carteira tem um problema de isolamento acima de todos: duas transferências simultâneas da Ana não podem gastar os mesmos cem. A resposta de fintech é a reserva de saldo, o hold.

Ele divide o saldo em dois números. O saldo contábil é a soma dos lançamentos efetivados.

O saldo disponível é o contábil menos os holds ativos. É o que dá para gastar agora.

As bandeiras de cartão fazem isso há décadas. A autorização reserva o dinheiro, e a captura o movimenta depois.


## Try, Confirm, Cancel

O hold segue um formato de três passos chamado TCC. Try reserva: cria o hold só se o saldo disponível cobre. Confirm torna definitivo: a captura vira um lançamento de débito. Cancel libera: fecha o hold sem lançar nada. Essa é a compensação, e é trivialmente segura, porque nenhum dinheiro se moveu.

A checagem e o insert do hold acontecem numa única transação local, travando a linha da conta para serializar os holds.

Confirm e Cancel precisam ser idempotentes, porque o orquestrador vai repeti-los.

E holds precisam de expiração. Se o orquestrador morrer de vez, um sweeper libera os vencidos, para que uma saga caída não congele o dinheiro do cliente para sempre.

Compare com o 2PC. Um hold parece um prepare, mas é um registro de negócio com commit, visível e com prazo. Não é um lock de banco aberto pela rede. As outras transferências continuam rodando contra o saldo disponível.

> **Pausa:** Pergunta: por que um hold precisa de expiração?

Porque se a saga morrer de vez, ninguém vai confirmar nem cancelar. Sem prazo, o dinheiro do cliente ficaria reservado para sempre.


## A escrita dupla

Agora o segundo problema. Todo passo faz duas coisas: muda seus dados e avisa alguém. Como fazer as duas de forma atômica?

Se você faz commit e depois publica, e cai no meio, os dados mudaram e ninguém ficou sabendo. A saga trava.

Se publica e depois faz commit, a mensagem sai e a transação faz rollback. Os consumidores agem sobre uma mudança que nunca aconteceu.

E tem um terceiro requisito: as mensagens precisam sair na ordem em que o serviço as produziu.


## Transactional outbox

A solução de Richardson é o transactional outbox. O serviço insere a mensagem numa tabela de outbox, na mesma transação que muda os dados de negócio. Ou o lançamento e a mensagem fazem commit juntos, ou nenhum dos dois.

Um componente separado, o message relay, lê o outbox e publica no broker. Sem 2PC, mensagens só saem se a transação fez commit, e saem na ordem produzida.

A pegadinha: o relay pode publicar uma mensagem mais de uma vez, se cair depois de publicar e antes de marcar como publicada. Por isso os consumidores precisam ser idempotentes. Na carteira, a chave saga ID mais passo é exatamente isso.

> **Pausa:** Pergunta: por que o insert no outbox precisa estar na mesma transação da escrita de negócio?

Para que os dois façam commit juntos ou nenhum. Assim nunca existe dado mudado sem mensagem, nem mensagem sobre algo que não aconteceu.


## Polling publisher

A primeira forma de construir o relay é o polling publisher: um loop que busca linhas não publicadas e publica. Funciona com qualquer banco SQL. Com várias instâncias, FOR UPDATE SKIP LOCKED faz cada uma pegar linhas diferentes. É exatamente o caso de tabela com cara de fila da semana passada.

Três detalhes. Se o processo morrer depois de publicar e antes do commit, as linhas saem de novo. É at-least-once.

Ordem contra paralelismo: com dois relays, o segundo lote pode ser publicado antes do primeiro. Se a ordem importa por conta, use um relay só, ou particione por aggregate ID.

E o outbox cresce para sempre. Limpe as linhas publicadas num job separado, fora do caminho quente. No lab, o relay escreve num log; o Kafka chega no módulo cinco.

> **Pausa:** Pergunta: por que o polling publisher entrega at-least-once, e não exactly-once?

Porque pode publicar e cair antes de marcar como publicada. No reinício, a mesma linha é publicada de novo.


## Log tailing e Debezium

A segunda forma é o transaction log tailing: ler o log de transações do banco e publicar cada mensagem inserida no outbox. Sem queries de polling, sem coluna de publicado. A ferramenta open source mais conhecida é o Debezium, que roda como connector dentro do Kafka Connect e manda cada tabela para um tópico.

O polling funciona com qualquer banco SQL, com latência do intervalo. O log tailing precisa de um log legível, e a latência fica perto do commit.

No polling, a ordem é você que projeta. No log tailing, ela vem do log. Em compensação, a operação é mais pesada: Kafka Connect, slots, configuração.

E nos dois há duplicatas. O consumidor deduplica sempre.

No Postgres, o Debezium usa logical decoding do WAL por um replication slot, a mesma maquinaria da replicação do módulo um. Um slot guarda o WAL até o consumidor confirmar. Um Debezium parado faz o WAL acumular no disco do primário. Monitore. Para o TCM, polling basta. Em entrevistas, cite o log tailing para volume maior.

> **Pausa:** Pergunta: como o Debezium lê mudanças do Postgres?

Por logical decoding do WAL, através de um replication slot.


## Revisão relâmpago

Hora da revisão relâmpago. São três perguntas, sem olhar.

> **Pausa:** Pergunta um: qual a diferença entre saldo contábil e saldo disponível?

O contábil é a soma dos lançamentos efetivados. O disponível é o contábil menos os holds ativos.

> **Pausa:** Pergunta dois: num saque para um banco parceiro, qual passo é a pivot?

A chamada que manda o parceiro enviar o dinheiro. Depois que ela dá certo, não dá para pegar o dinheiro de volta.

> **Pausa:** Pergunta três: dê um exemplo de lost update entre sagas na carteira.

Uma saga de reembolso marca a transferência como reembolsada, e a saga original, ainda rodando, a sobrescreve como concluída.


## O que anotar e próximo passo

Anote com as suas palavras: as três anomalias. Os tipos de passo e a pivot de um saque. As contramedidas. O hold como TCC. A escrita dupla e o outbox. E polling contra log tailing.

No lab, construa o relay com SKIP LOCKED escrevendo num log. Até a próxima aula.
