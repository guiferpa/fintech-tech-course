# Roteiro · M1 · Dia 2 · Replicação e replication lag


## Abertura

Esta é a aula em vídeo do módulo um, dia dois: replicação e replication lag.

No final você vai saber responder três perguntas. Em que momento um commit está realmente seguro. O que você pode perder num failover. E por que um Pix recém enviado pode sumir do extrato do cliente. Lembre de responder em voz alta nas pausas.


## Por que importa

Quase toda carteira digital tem um Postgres primário e pelo menos uma réplica. A réplica serve como cópia se o primário morrer, e como lugar para mandar leituras, como extratos e dashboards.

Os dois usos têm uma pegadinha. Primeira: a réplica fica atrás do primário por algum tempo.

Segunda: um failover pode perder as escritas que a réplica ainda não tinha recebido. A aula de hoje é sobre essas duas pegadinhas.


## Líder e seguidores

O modelo mais comum é a replicação com líder único. Um nó, o primário, aceita todas as escritas. Os standbys recebem um fluxo de mudanças e aplicam na mesma ordem.

No Postgres isso é a streaming replication. Toda mudança é escrita primeiro no write-ahead log, o WAL. O primário envia o WAL em fluxo, e cada standby reaplica.

Um standby que aceita consultas de leitura enquanto reaplica é chamado de hot standby.

Cada posição no WAL tem um endereço, o LSN, log sequence number. Ele só cresce, então é o jeito natural de dizer até onde um standby chegou.

Como o standby aplica o log em ordem, ele é sempre uma cópia consistente do primário em algum momento do passado. A pergunta é: quão no passado.


## Síncrona vs assíncrona

Quando o cliente faz commit, em que momento o primário diz commitado? Na replicação assíncrona, que é o padrão do Postgres, ele confirma assim que o commit está no próprio disco. O atraso até a réplica costuma ser menor que um segundo, mas sob carga pode ser bem mais. E se o primário morrer, commits recentes podem se perder.

Na replicação síncrona, o commit espera um standby. Custa uma ida e volta a mais de latência. E tem um risco: se o standby síncrono cair, os commits podem nunca terminar.

Por isso muitos times usam ANY um sobre dois standbys. Um commit fica em pelo menos duas máquinas, e uma réplica lenta não consegue parar todas as escritas.


## Níveis de synchronous_commit

Vale saber com exatidão os três níveis de synchronous_commit. Com remote_write, o standby recebeu e entregou ao sistema operacional. Sobrevive a um crash do Postgres, mas não do sistema operacional.

Com on, o padrão quando há standby síncrono, o registro de commit está em disco durável. O commit existe em dois discos.

Com remote_apply, o standby já reaplicou a transação. Uma leitura nele logo após o commit enxerga o dado.

> **Pausa:** Pergunta: o que remote_apply garante que on não garante?

Que uma leitura no standby, logo depois do commit, já vê o dado. Com on, o dado está gravado no disco do standby, mas pode ainda não estar visível.

O Azure Cosmos DB expõe a mesma escolha entre regiões. Níveis mais fracos podem perder menos de quinze minutos de escritas numa queda regional. A consistência strong dá RPO zero.


## Failover

Quando o primário morre, um standby é promovido e os clientes passam a apontar para ele. O Postgres só faz a promoção, com pg_promote. Detectar a falha é trabalho de uma ferramenta externa, como Patroni ou o RDS. E cada passo tem uma armadilha.

Primeira: detectar a falha depende de timeouts. Um primário que está só lento pode ser declarado morto. É a aula de ontem de novo.

Segunda: com replicação assíncrona, commits confirmados podem não ter chegado ao standby. A quantidade perdida é proporcional ao atraso no momento do failover. Para o cliente, uma transferência que devolveu sucesso simplesmente desapareceu. Se o dinheiro já tinha ido ao banco parceiro, seu ledger e o banco agora discordam. É a conciliação, no módulo sete, que encontra isso.

Terceira: split brain. Se o primário antigo só estava isolado, dois nós podem aceitar escritas. A documentação manda ter um jeito de derrubar o antigo, chamado STONITH, shoot the other node in the head. A técnica geral se chama fencing.

Quarta: o novo primário pode reutilizar IDs que o antigo já distribuiu, e um cache ou uma mensagem no Kafka passa a apontar para outro dado.

> **Pausa:** Pergunta: por que a replicação assíncrona pode perder um commit que o cliente já viu dar certo, e o que decide quanto se perde?

Porque o primário confirma antes do standby receber. Se ele morre nesse intervalo, o commit some. O quanto se perde depende do atraso de replicação no momento do failover. A lição: failover é um evento de corretude, não só de disponibilidade.


## Split brain no MongoDB

O MongoDB mostra o split brain de forma concreta. Num replica set de cinco membros cortado por uma partição, o primário antigo ainda pode não ter deixado o posto. Uma escrita com write concern w um pode dar certo nele, e sofre rollback quando a rede volta.

Uma escrita com w majority só termina no lado que tem a maioria. Para dinheiro, essa diferença é tudo: uma escrita confirmada só por um nó que pode estar do lado perdedor é uma escrita que você pode perder.


## Medir o lag

Você não consegue raciocinar sobre um atraso que não mede. A receita é comparar LSNs. Subtrair dois LSNs dá um número de bytes. No primário, a view pg_stat_replication mostra até onde o WAL foi enviado a cada standby. No standby, você compara o recebido com o reaplicado.

As diferenças contam onde está o problema. Distância grande entre o LSN atual e o enviado: o primário está sob carga pesada.

Entre o enviado e o recebido: a rede ou um standby ocupado.

Entre o recebido e o reaplicado: o standby recebe mais rápido do que consegue aplicar. No lab desta semana, você vai colocar o Toxiproxy no meio e ver esses números crescerem.


## Anomalias do lag

Com replicação assíncrona, ler da réplica pode dar resultados estranhos. O manual do MongoDB resume: as leituras podem estar desatualizadas, mas nunca fora de ordem. E ele dá nome às garantias que você perde.

Read your writes: suas leituras refletem as escritas que você fez antes. A violação: o cliente envia um Pix, o app recarrega o extrato de uma réplica, e o Pix não está lá. O cliente envia de novo.

Monotonic reads: uma leitura nunca volta para um estado anterior. A violação: o extrato veio de uma réplica atualizada, o usuário puxa para atualizar, cai numa réplica atrasada, e uma transação desaparece.

Consistent prefix: os leitores veem as escritas na ordem em que aconteceram. Débito e crédito na mesma transação aparecem juntos ou nenhum aparece. Um Postgres com líder único dá isso de graça. Isso quebra quando os dados são particionados, o assunto de amanhã.


## Read your writes com LSN

Como produtos reais resolvem isso? A consistência session do Cosmos DB é o modelo para copiar. Depois de cada escrita, o cliente recebe um session token, e manda de volta nas leituras. É uma barreira de versão mínima: a réplica só responde depois de chegar àquele ponto.

No Postgres, você constrói o mesmo com LSNs. Depois do commit da transferência, leia o LSN atual do primário e devolva ao app como token.

Ao servir o extrato a partir de uma réplica, verifique se o LSN reaplicado na réplica já é maior ou igual ao token.

Se ainda não chegou, espere um pouco ou leia do primário. A alternativa simples também vale: logo após uma transferência, leia saldo e extrato do primário.

Para monotonic reads, fixe cada usuário numa réplica, por exemplo pelo hash do ID, ou aplique a mesma regra do token com o maior LSN que ele já viu.

> **Pausa:** Pergunta: o cliente acabou de fazer um Pix e o extrato vem de uma réplica. Como você garante que o Pix aparece?

Com read your writes: devolva o LSN do commit como token e só sirva da réplica quando ela tiver reaplicado até ele. Senão, leia do primário.


## Sem líder e quorums

Bancos da família Dynamo, como o Cassandra, não têm líder. Cada dado fica em RF nós, o replication factor. As escritas vão para todas as réplicas, e você escolhe quantas confirmações esperar.

Os níveis mais comuns são ONE, QUORUM, que é a maioria, ALL, e LOCAL_QUORUM, a maioria dentro do datacenter.

A regra de ouro: se as réplicas que a leitura espera mais as que a escrita espera passam do RF, os conjuntos sempre se cruzam. Com RF três, QUORUM em leitura e escrita é dois mais dois. Toda leitura encontra a última escrita confirmada, e cada lado tolera uma réplica fora.

Réplicas atrasadas são corrigidas por hinted handoff, por read repair, e por anti-entropy, que compara árvores de hash em segundo plano.

Mas quorum não é mágica. Escritas concorrentes no mesmo valor são resolvidas por last write wins, usando timestamps. Com relógios desalinhados, a última escrita pode ser a mais antiga, e a outra some em silêncio.

> **Pausa:** Pergunta: por que last write wins é perigoso para um saldo?

Porque depende de relógios sincronizados. Uma atualização concorrente é descartada em silêncio, e dinheiro some. Por isso ledgers vivem em bancos com líder único e transações.


## Revisão relâmpago

Hora da revisão relâmpago. São três perguntas, sem olhar.

> **Pausa:** Pergunta um: o que decide quanto se perde num failover com replicação assíncrona?

O replication lag no momento do failover.

> **Pausa:** Pergunta dois: o que evita split brain?

Fencing. Garantir que o primário antigo não aceite mais escritas, e confirmar escritas com a maioria.

> **Pausa:** Pergunta três: quais funções dizem quão atrasado está um standby?

pg_last_wal_receive_lsn e pg_last_wal_replay_lsn, comparadas por subtração. No primário, a view pg_stat_replication.


## O que anotar e próximo passo

Antes de fechar, anote três coisas com as suas palavras. Desenhe o primário, o standby e o fluxo de WAL, e marque onde o commit é confirmado em cada modo. Liste as escritas que um failover pode perder e como seu sistema as encontra. E dê um exemplo de read your writes e um de monotonic reads na carteira, com a correção.

Depois, transforme as perguntas do Teste-se em flashcards. A fonte principal de hoje é a documentação de alta disponibilidade do PostgreSQL. Até a próxima aula.
