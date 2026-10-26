# Módulo 1, terça-feira: replicação e replication lag

[Módulo 1](../../modules/01-distributed-systems-fundamentals.pt-BR.md) · [Read in English](day-2.md)

**Tempo de leitura:** cerca de 45 minutos. Use o resto do bloco de 2 horas nas referências do final.

Este é um texto original escrito para este curso. Ele se baseia nas referências listadas no final, e cada seção indica a fonte que segue.

## Por que isso importa para uma fintech

Quase toda carteira digital em que você vai trabalhar tem um Postgres primário e pelo menos uma réplica. A réplica dá a você uma cópia dos dados se o primário morrer, e um lugar para mandar tráfego de leitura, como extratos e dashboards. Os dois usos têm uma pegadinha. A réplica fica atrás do primário por algum tempo, e um failover pode perder as escritas que a réplica ainda não tinha recebido. O assunto de hoje são essas duas pegadinhas, vistas pela documentação dos bancos de dados que lidam com elas em produção: PostgreSQL, MongoDB, Azure Cosmos DB e Apache Cassandra.

## 1. Líder e seguidores

*Fonte principal: documentação do PostgreSQL, "High Availability, Load Balancing, and Replication".*

A configuração mais comum é a **replicação com líder único**. Um nó, o **primário** (também chamado de líder ou master), aceita todas as escritas. Os outros nós, os **standbys** (seguidores, réplicas), recebem um fluxo de mudanças do primário e as aplicam na mesma ordem. Os clientes podem ler de qualquer nó, mas só escrevem no primário.

O Postgres implementa isso com **streaming replication**. Toda mudança é escrita primeiro no write-ahead log (WAL) do primário. O primário envia os registros do WAL em fluxo para os standbys, e cada standby os reaplica. Um standby que aceita consultas somente leitura enquanto reaplica o WAL é chamado de **hot standby**.

Toda posição no WAL tem um endereço chamado **LSN** (log sequence number), mostrado como algo do tipo `0/3000148`. LSNs só crescem, então são o jeito natural de dizer "até onde" um standby chegou. Como o standby aplica o log do primário em ordem, ele é sempre uma cópia consistente do primário em algum momento do passado. A questão é quão no passado.

## 2. Replicação síncrona e assíncrona

*Fonte principal: documentação do PostgreSQL, "Log-Shipping Standby Servers" (seções sobre streaming replication e replicação síncrona).*

Quando um cliente faz commit de uma transação no primário, em que momento o primário diz "commitado"?

- **Replicação assíncrona** é o padrão do Postgres. O primário confirma assim que o commit está no seu próprio WAL em disco. A documentação diz que o atraso até a mudança ficar visível no standby é "typically under one second assuming the standby is powerful enough to keep up with the load" (normalmente menos de um segundo, desde que o standby consiga acompanhar a carga). Sob carga pesada ou com um problema de rede, pode ser bem mais.
- **Replicação síncrona** faz o commit esperar um standby. Você a habilita definindo `synchronous_standby_names` e escolhe até onde vai a confirmação com `synchronous_commit`.

Vale conhecer com exatidão os três níveis de `synchronous_commit`, porque cada um compra uma garantia diferente:

| Configuração | O commit espera até o standby ter... | O que protege |
| --- | --- | --- |
| `remote_write` | recebido o commit e entregue ao sistema operacional | Sobrevive a um crash do Postgres no standby, mas não a um crash do sistema operacional |
| `on` (padrão quando há um standby síncrono configurado) | gravado o registro de commit em armazenamento durável | O commit existe em dois discos |
| `remote_apply` | reaplicado a transação, que fica visível para consultas | Uma leitura nesse standby logo após o commit enxerga o dado |

Você também pode esperar por vários standbys. `synchronous_standby_names = 'FIRST 1 (s1, s2)'` espera pelo standby disponível de maior prioridade, e `'ANY 2 (s1, s2, s3)'` espera por dois quaisquer dos três, um quorum.

O trade-off:

| | Assíncrona | Síncrona |
| --- | --- | --- |
| Latência do commit | Só o disco do primário | Mais uma ida e volta até o standby |
| Se o standby está fora | As escritas continuam | As escritas esperam até ele voltar ou ser removido |
| Se o primário morre | Commits recentes podem se perder | Os dados commitados existem em um standby |

A documentação é direta sobre a linha do meio: commits que esperam um standby síncrono "may never be completed" (podem nunca terminar) se esse standby cair, e a solução é reduzir o número de standbys exigidos ou desabilitar a configuração e recarregar o arquivo de configuração. Por isso muitos times usam `ANY 1` sobre dois standbys: um commit fica em pelo menos duas máquinas, e uma réplica lenta não consegue parar todas as escritas.

Outros bancos de dados expõem a mesma escolha como um botão de ajuste. A documentação do Azure Cosmos DB publica o recovery point objective (RPO) para uma queda de região inteira por nível de consistência: com várias regiões e uma única região de escrita, os níveis mais fracos podem perder "less than 15 minutes" (menos de 15 minutos) de escritas, enquanto a consistência strong dá RPO 0, porque toda escrita é commitada na maioria das regiões antes de ser confirmada. É o mesmo trade do Postgres, síncrono contra assíncrono, só que entre regiões em vez de entre máquinas.

## 3. Failover e as escritas que você perde

*Fonte principal: documentação do PostgreSQL, seção ["Failover"](https://www.postgresql.org/docs/current/warm-standby-failover.html) do capítulo de High Availability.*

Quando o primário morre, um standby precisa ser **promovido** a novo primário, e os clientes precisam ser apontados para ele. A documentação do Postgres é explícita: o Postgres "does not provide the system software required to identify a failure on the primary" (não fornece o software necessário para identificar uma falha no primário); ele só fornece a promoção em si:

```sql
-- No standby que você quer promover
SELECT pg_promote();
```

Uma ferramenta externa (Patroni, um serviço gerenciado como o RDS, ou um operador) precisa detectar a falha e executar isso. Cada passo tem uma armadilha.

- **Detectar a falha** depende de timeouts, então tem todos os problemas de segunda-feira. Um primário que está só lento pode ser declarado morto.
- **Escritas perdidas com replicação assíncrona.** A documentação diz isso diretamente: se o primário cair, "some transactions that were committed may not have been replicated to the standby server, causing data loss" (algumas transações commitadas podem não ter sido replicadas para o standby, causando perda de dados), e a quantidade perdida "is proportional to the replication delay at the time of failover" (é proporcional ao atraso de replicação no momento do failover). Do ponto de vista do cliente, uma transferência que devolveu 201 desapareceu. Se era uma movimentação de dinheiro já enviada ao banco parceiro, seu ledger e o banco agora discordam. A conciliação (Módulo 7) é como você descobre isso.
- **Split brain.** Se o primário antigo não estava morto, só isolado, ou se ele reinicia depois, dois nós podem achar que são o primário e aceitar escritas. A documentação diz que você precisa de um jeito de avisar o primário antigo de que ele não é mais o primário, conhecido como STONITH ("Shoot The Other Node In The Head"), porque senão o resultado é "confusion and ultimately data loss" (confusão e, no fim, perda de dados). A técnica geral se chama fencing.
- **Identificadores reutilizados.** Se o novo primário distribui IDs ou valores de sequence que o antigo já tinha usado, outros sistemas que viram os IDs antigos (um cache, uma mensagem já publicada no Kafka) passam a apontar para dados diferentes.

A documentação do MongoDB mostra o split brain de forma concreta. Em um replica set de cinco membros cortado por uma partição de rede, o primário antigo pode ainda não ter deixado o posto. Escritas com write concern `{ w: 1 }` (confirmadas por um nó) podem dar certo em qualquer um dos dois primários, e as aceitas pelo antigo sofrem **rollback** quando a partição se resolve. Escritas com `{ w: "majority" }` só conseguem terminar no lado que tem a maioria. Para dinheiro, essa diferença é tudo: uma escrita confirmada só por um nó que pode estar do lado perdedor é uma escrita que você pode perder.

A lição para o design é que **um failover é um evento de corretude, não só de disponibilidade**. Anote seu RPO (quantos dados você aceita perder) e saiba qual modo de replicação o entrega. O Módulo 9 volta a RPO e RTO.

## 4. Medir o replication lag

*Fonte principal: documentação do PostgreSQL, "Log-Shipping Standby Servers", seção "Monitoring".*

Você não consegue raciocinar sobre um atraso que não mede. A receita da documentação é comparar posições do WAL: `pg_current_wal_lsn()` no primário contra `pg_last_wal_receive_lsn()` no standby, e acompanhar a view `pg_stat_replication` no primário, que tem uma linha por standby com até onde o WAL já foi enviado para ele. Subtrair dois LSNs dá um número de bytes:

```sql
-- No primário: quantos bytes de WAL ainda não foram enviados a cada standby
SELECT application_name, pg_current_wal_lsn() - sent_lsn AS bytes_behind
  FROM pg_stat_replication;

-- No standby: recebido mas ainda não reaplicado (visível para consultas)
SELECT pg_last_wal_receive_lsn() - pg_last_wal_replay_lsn() AS bytes_not_replayed;
```

A documentação também ensina a ler as diferenças. Uma grande diferença entre o LSN atual do primário e o `sent_lsn` aponta para um primário sob carga pesada. Uma grande diferença entre o `sent_lsn` e o que o standby recebeu aponta para a rede ou para um standby ocupado. Um standby que recebe mais rápido do que reaplica aparece como uma diferença entre o recebido e o reaplicado. No lab desta semana você vai colocar o Toxiproxy entre o primário e a réplica e ver esses números crescerem.

## 5. O replication lag e as anomalias que ele causa

*Fontes principais: manual do MongoDB, "Read Isolation, Consistency, and Recency", e documentação do Azure Cosmos DB, "Consistency levels in Azure Cosmos DB".*

Com replicação assíncrona, leituras em um standby podem mostrar resultados surpreendentes. O manual do MongoDB descreve as leituras em secundários sem rodeios: elas "may return data that lags behind the primary" (podem devolver dados atrasados em relação ao primário), mas como os secundários aplicam as escritas na mesma ordem que o primário, as leituras "may be stale but never out of order" (podem estar desatualizadas, mas nunca fora de ordem). O mesmo vale para um hot standby do Postgres. O manual do MongoDB também dá nome às garantias que você perde, com definições que você pode usar diretamente. Duas importam mais para uma carteira digital.

**Read your writes.** Nas palavras do MongoDB, "read operations reflect the results of write operations that precede them" (as leituras refletem os resultados das escritas que vieram antes delas). A violação: um cliente envia um Pix, a API escreve no primário, o app recarrega o extrato de uma réplica, e o Pix não está lá. O cliente envia de novo.

**Monotonic reads.** As leituras nunca devolvem um estado anterior ao de uma leitura anterior. A violação: uma página carrega o extrato da réplica A (atualizada), o usuário puxa para atualizar, a requisição vai para a réplica B (atrasada), e uma transação desaparece.

Como produtos reais oferecem essas garantias? A consistência **session** do Azure Cosmos DB, que a documentação chama de "the most widely used consistency level" (o nível de consistência mais usado), é um bom modelo para copiar. Depois de cada escrita, o cliente recebe um **session token**, e as leituras seguintes o enviam de volta. A documentação descreve o token como "a minimum version barrier" (uma barreira de versão mínima): uma réplica só responde depois de ter chegado pelo menos até aquele ponto. Os tokens são ligados a uma partição, e um cliente que perdeu o token recebe consistência eventual para aquela partição. As sessões causalmente consistentes do MongoDB fazem o mesmo com um "operation time" que o driver acompanha para você.

Você pode construir a mesma coisa no Postgres com LSNs:

1. Depois que a transferência faz commit no primário, leia `pg_current_wal_lsn()` e devolva ao app (ou guarde na sessão do usuário) como token.
2. Ao servir o extrato desse usuário a partir de uma réplica, verifique `pg_last_wal_replay_lsn() >= token` na réplica.
3. Se a réplica ainda não chegou lá, espere um pouco ou mande a leitura para o primário.

Alternativas mais simples também funcionam: ler do primário tudo o que o usuário pode ter acabado de mudar (o próprio saldo e extrato logo após uma transferência), ou direcionar o usuário ao primário por uma janela curta depois de uma escrita. Para monotonic reads, fixe cada usuário em uma réplica, por exemplo pelo hash do ID do usuário, ou aplique a mesma regra do token usando o maior LSN que o usuário já viu.

**Consistent prefix.** Os leitores veem as escritas na ordem em que aconteceram. A documentação do Cosmos DB dá um exemplo preciso: se uma transação atualiza Doc1 e Doc2, um leitor vê as duas versões antigas ou as duas novas, mas nunca uma mistura. Em uma carteira digital, o débito e o crédito de uma transferência são escritos em uma transação, então nenhum leitor deveria ver só um lado. Um Postgres com líder único dá isso de graça. Isso costuma quebrar quando os dados são particionados entre máquinas que replicam de forma independente, o assunto de quarta-feira.

Essas são *session guarantees*: prometem algo a um cliente. Modelos mais fortes, como a linearizabilidade que você vai ver na quarta, prometem a mesma visão para todos.

## 6. Replicação sem líder e quorums

*Fonte principal: documentação do Apache Cassandra, "Dynamo".*

Alguns bancos de dados, como o Cassandra e outros da família Dynamo, não têm líder. Cada dado é guardado em um número de nós dado pelo **replication factor** (RF). A documentação do Cassandra explica que as escritas "are always sent to all replicas" (são sempre enviadas a todas as réplicas); o que você ajusta é quantas confirmações o coordenador espera, usando um **consistency level** por requisição:

- `ONE`: uma única réplica precisa responder.
- `QUORUM`: a maioria, n/2 + 1 das réplicas.
- `ALL`: todas as réplicas.
- `LOCAL_QUORUM`: a maioria no datacenter do próprio coordenador.

Se o número de réplicas que uma leitura espera (R) mais o número que uma escrita espera (W) for maior que o RF, todo conjunto de leitura se sobrepõe a todo conjunto de escrita em pelo menos um nó. A documentação escreve isso como W + R > RF e diz que isso torna "all acknowledged writes ... visible to subsequent reads" (todas as escritas confirmadas visíveis para as leituras seguintes). Com RF = 3, escritas e leituras `QUORUM` precisam de 2 réplicas cada, então sempre compartilham uma, e cada uma sobrevive a uma réplica fora do ar. Com `LOCAL_QUORUM` em um cluster com vários datacenters, a garantia só vale dentro do mesmo datacenter. Se você não precisa dela, `ONE` dá menor latência e maior disponibilidade.

Réplicas que perderam uma escrita são atualizadas por vários mecanismos:

- **Hinted handoff**: quando uma réplica está fora, o coordenador guarda um hint e reaplica a escrita quando ela volta.
- **Read repair**: uma leitura que percebe que as réplicas discordam corrige a desatualizada.
- **Anti-entropy repair**: as réplicas comparam árvores de hash (Merkle trees) dos seus dados em segundo plano e copiam o que falta. É isso que garante que elas acabem convergindo.

Quorums não são um interruptor mágico de consistência. Quando duas escritas no mesmo valor são concorrentes, o Cassandra as resolve por **last write wins**, usando o timestamp de cada escrita, que vem do cliente ou do relógio do coordenador. A documentação avisa que isso depende de relógios sincronizados, que é a lição de segunda-feira de novo: com relógios desalinhados, a "última" escrita pode ser a mais antiga, e a outra é descartada em silêncio. Tudo bem para uma foto de perfil, inaceitável para um saldo. Esse é um dos motivos pelos quais ledgers normalmente vivem em um banco com líder único e transações, e stores sem líder ficam para dados em que perder uma atualização concorrente é aceitável.

## O que anotar hoje

1. Desenhe o primário e o standby com o fluxo de WAL, e marque onde um commit é confirmado com replicação assíncrona e com cada nível de `synchronous_commit`.
2. Liste as escritas que você poderia perder em um failover e o que seu sistema faz para encontrá-las.
3. Um exemplo de violação de read your writes e um de monotonic reads em um app de carteira digital, e como você evitaria cada um (o token de LSN é uma resposta).

## Teste-se

- O que `synchronous_commit = remote_apply` garante que `on` não garante?
- Por que a replicação assíncrona pode perder um commit que o cliente já viu dar certo, e o que decide quanto se perde?
- O que é split brain, e o que o evita?
- Quais duas funções SQL dizem quão atrasado um standby está?
- Como um session token do Cosmos DB dá read your writes a um usuário, e como você copiaria a ideia no Postgres?
- Com RF = 3, por que leituras e escritas `QUORUM` enxergam a última escrita confirmada?
- Por que last write wins é perigoso para um saldo?

## Referências

- **Fonte principal:** documentação do PostgreSQL, ["High Availability, Load Balancing, and Replication"](https://www.postgresql.org/docs/current/high-availability.html), especialmente as seções sobre streaming replication, replicação síncrona, failover e hot standby. Gratuito.
- Documentação do PostgreSQL, ["Log-Shipping Standby Servers"](https://www.postgresql.org/docs/current/warm-standby.html), subseções "Streaming Replication" (incluindo "Monitoring") e "Synchronous Replication". Gratuito.
- Manual do MongoDB, ["Read Isolation, Consistency, and Recency"](https://www.mongodb.com/docs/manual/core/read-isolation-consistency-recency/), seções sobre consistência causal e leituras desatualizadas em secundários; e ["Causal Consistency and Read and Write Concerns"](https://www.mongodb.com/docs/manual/core/causal-consistency-read-write-concerns/) para os cenários de partição de rede. Gratuito.
- Microsoft, documentação do Azure Cosmos DB, ["Consistency levels in Azure Cosmos DB"](https://learn.microsoft.com/azure/cosmos-db/consistency-levels), seções sobre as consistências session e consistent prefix e a tabela de RPO. Gratuito.
- Documentação do Apache Cassandra, ["Dynamo"](https://cassandra.apache.org/doc/latest/cassandra/architecture/dynamo.html), seções sobre replicação, consistência ajustável e sincronização de réplicas. Gratuito.
