# Módulo 1, terça-feira: replicação e replication lag

[Módulo 1](../../modules/01-distributed-systems-fundamentals.pt-BR.md) · [Read in English](day-2.md)

**Tempo de leitura:** cerca de 45 minutos. Use o resto do bloco de 2 horas nas referências do final.

Este é um texto original escrito para este curso. Ele se baseia nas referências listadas no final, e cada seção indica a fonte que segue.

## Por que isso importa para uma fintech

Quase toda carteira digital em que você vai trabalhar tem um Postgres primário e pelo menos uma réplica. A réplica dá a você uma cópia dos dados se o primário morrer, e um lugar para mandar tráfego de leitura, como extratos e dashboards. Os dois usos têm uma pegadinha. A réplica fica atrás do primário por algum tempo, e um failover pode perder as escritas que a réplica ainda não tinha recebido. O assunto de hoje são essas duas pegadinhas.

## 1. Líder e seguidores

*Fonte principal: documentação do PostgreSQL, "High Availability, Load Balancing, and Replication".*

A configuração mais comum é a **replicação com líder único**. Um nó, o **primário** (também chamado de líder ou master), aceita todas as escritas. Os outros nós, os **standbys** (seguidores, réplicas), recebem um fluxo de mudanças do primário e as aplicam na mesma ordem. Os clientes podem ler de qualquer nó, mas só escrevem no primário.

O Postgres implementa isso com **streaming replication**. Toda mudança é escrita primeiro no write-ahead log (WAL) do primário. O primário envia os registros do WAL em fluxo para os standbys, e cada standby os reaplica. Um standby que aceita consultas somente leitura enquanto reaplica o WAL é chamado de **hot standby**.

Como o standby aplica o log do primário em ordem, ele é sempre uma cópia consistente do primário em algum momento do passado. A questão é quão no passado.

## 2. Replicação síncrona e assíncrona

*Fonte principal: documentação do PostgreSQL, "High Availability, Load Balancing, and Replication", e a configuração `synchronous_commit`.*

Quando um cliente faz commit de uma transação no primário, em que momento o primário diz "commitado"?

- **Replicação assíncrona** (o padrão do Postgres): assim que o primário grava o commit no seu próprio WAL em disco. O standby o recebe alguns milissegundos depois, ou alguns minutos depois se estiver com dificuldade.
- **Replicação síncrona**: só depois que pelo menos um standby confirma que também tem o commit. No Postgres, você lista os standbys em `synchronous_standby_names` e escolhe até onde vai a confirmação com `synchronous_commit` (`remote_write`, `on`, que significa gravado no disco do standby, ou `remote_apply`, que significa já visível para consultas no standby).

O trade-off:

| | Assíncrona | Síncrona |
| --- | --- | --- |
| Latência do commit | Só o disco do primário | Mais uma ida e volta até o standby |
| Se o standby cair | As escritas continuam | As escritas ficam bloqueadas até ele voltar ou ser removido |
| Se o primário morrer | Commits recentes podem ser perdidos | Os dados commitados existem em um standby |

Muitos times usam um standby síncrono e os demais assíncronos, o que às vezes é chamado de *semissíncrono*. Assim, um commit fica em pelo menos duas máquinas, e uma réplica lenta não consegue parar todas as escritas.

## 3. Failover e as escritas que você perde

*Fonte principal: documentação do PostgreSQL, seção ["Failover"](https://www.postgresql.org/docs/current/warm-standby-failover.html) do capítulo de High Availability.*

Quando o primário morre, um standby precisa ser **promovido** a novo primário, e os clientes precisam ser apontados para ele. A documentação do Postgres é explícita: o Postgres "não fornece o software de sistema necessário para identificar uma falha no primário". Ele só fornece o comando de promoção (`pg_promote()`). Uma ferramenta externa (Patroni, um serviço gerenciado como o RDS, ou um operador) precisa detectar a falha e promover um standby. Cada etapa tem uma armadilha.

- **Detectar a falha** depende de timeouts, então tem todos os problemas de segunda-feira. Um primário que está só lento pode ser declarado morto.
- **Escritas perdidas com replicação assíncrona.** Commits que o primário antigo confirmou, mas ainda não tinha enviado, não estão no novo primário. Do ponto de vista do cliente, uma transferência que retornou 201 desapareceu. Se essas escritas eram movimentações de dinheiro, seu ledger e o banco parceiro agora discordam. A conciliação (Módulo 7) é como você detecta isso.
- **Split brain.** Se o primário antigo não estava morto, só isolado, ou se ele reiniciar depois, dois nós podem acreditar que são o primário e aceitar escritas. A documentação diz que você precisa de um mecanismo para avisar o primário antigo de que ele não é mais o primário, conhecido como STONITH ("shoot the other node in the head"). Caso contrário, o resultado é "confusão e, no fim, perda de dados". A técnica geral se chama fencing.
- **Identificadores reutilizados.** Se o novo primário distribui IDs ou valores de sequência que o antigo já tinha usado, outros sistemas que viram os IDs antigos (um cache, uma mensagem já publicada no Kafka) agora apontam para dados diferentes.

A lição para o design é que **um failover é um evento de corretude, não só um evento de disponibilidade**. Anote seu RPO (quantos dados você aceita perder) e saiba qual modo de replicação o entrega. O Módulo 9 volta a falar de RPO e RTO.

## 4. Replication lag e as anomalias que ele causa

*Fonte principal: Jepsen, modelos de consistência "Read Your Writes" e "Monotonic Reads".*

Com replicação assíncrona, um standby costuma estar milissegundos atrás, mas sob carga ou durante um problema de rede pode ficar segundos ou minutos atrás. Leituras feitas nele podem então mostrar resultados surpreendentes. As páginas de modelos de consistência do Jepsen definem as garantias que você perde.

**Read your writes.** Um cliente que escreveu algo precisa ver essa escrita nas leituras seguintes. A violação: um cliente envia um Pix, a API escreve no primário, o app recarrega o extrato a partir de uma réplica, e o Pix não está lá. O cliente envia de novo.

Formas de garantir isso:

- Leia do primário tudo o que o usuário pode ter acabado de alterar, como o próprio saldo e o extrato logo depois de uma transferência.
- Guarde o horário ou a posição no WAL (LSN) da última escrita do usuário, e só leia de uma réplica que já reaplicou além dela. O Postgres expõe `pg_last_wal_replay_lsn()` nos standbys.
- Direcione o usuário para o primário por uma janela curta depois que ele escreve.

**Monotonic reads.** As leituras de um cliente nunca voltam no tempo: depois que você viu um estado, as leituras seguintes mostram esse estado ou um mais novo. A violação: uma página carrega o extrato da réplica A (atualizada), depois recarrega da réplica B (atrasada), e uma transação desaparece. Fixar cada usuário em uma réplica, por exemplo usando o hash do ID do usuário, garante monotonic reads enquanto essa réplica estiver no ar.

**Consistent prefix.** Os leitores veem as escritas na ordem em que aconteceram. Se um estorno aparece antes do pagamento que ele estorna, o leitor viu um prefixo inconsistente. Isso acontece principalmente quando os dados estão particionados, que é o tema de quarta-feira.

O Jepsen organiza esses modelos em uma hierarquia. Read your writes e monotonic reads são *garantias de sessão*: só prometem algo para um cliente. Modelos mais fortes, como a linearizabilidade, que você vai ver na quarta-feira, prometem a mesma visão para todos.

## 5. Replicação sem líder e quorums

*Fonte principal: notas de aula de Kleppmann, seção 5.2.*

Alguns bancos de dados, como o Cassandra e a família Dynamo, não têm líder. O cliente (ou um nó coordenador) envia cada escrita para todas as N réplicas e cada leitura para várias réplicas.

- Uma escrita conta como bem-sucedida quando **W** réplicas a confirmam.
- Uma leitura consulta réplicas e espera **R** delas responderem.
- Se **R + W > N**, todo quorum de leitura se sobrepõe a todo quorum de escrita em pelo menos um nó, então pelo menos uma das R respostas tem a escrita mais recente. Cada valor carrega uma versão ou um timestamp para que o leitor escolha o mais novo.

Com N = 3, uma escolha comum é W = 2 e R = 2. Assim, cada escrita e cada leitura sobrevivem a uma réplica fora do ar.

Dois mecanismos atualizam réplicas defasadas:

- **Read repair**: quando uma leitura vê um valor antigo em uma réplica, o leitor escreve o valor mais novo de volta nela.
- **Anti-entropy**: um processo em segundo plano compara réplicas e copia os dados que faltam.

Quorums não são um botão mágico de consistência. Escritas concorrentes ainda precisam de uma regra para escolher um vencedor, e "a última escrita vence" por timestamp descarta uma delas em silêncio (de novo o problema dos relógios de segunda-feira). As notas de Kleppmann também mostram (seção 7.2) que R + W > N sozinho não torna as leituras linearizáveis; é preciso fazer o read repair antes de a leitura retornar. Esse é um dos motivos pelos quais ledgers costumam ficar em um banco com líder único e transações, enquanto stores sem líder ficam reservados para dados em que perder uma atualização concorrente é aceitável.

## O que anotar hoje

1. Desenhe o primário e o standby com o fluxo do WAL, e marque onde um commit é confirmado no modo assíncrono e no síncrono.
2. Liste as escritas que você poderia perder em um failover, e o que seu sistema faz para encontrá-las.
3. Um exemplo de violação de read your writes e um de violação de monotonic reads em um app de carteira digital, e como você evitaria cada uma.

## Teste-se

- O que `synchronous_commit = remote_apply` garante que `on` não garante?
- Por que a replicação assíncrona pode perder um commit que o cliente já viu dar certo?
- O que é split brain, e o que o evita?
- Como dar read your writes a um usuário e ainda assim ler de réplicas?
- Por que R + W > N faz uma leitura ver a escrita mais recente?

## Referências

- **Fonte principal:** documentação do PostgreSQL, ["High Availability, Load Balancing, and Replication"](https://www.postgresql.org/docs/current/high-availability.html), especialmente as seções sobre streaming replication, replicação síncrona, failover e hot standby. Gratuito.
- Jepsen, modelos de consistência: ["Read Your Writes"](https://jepsen.io/consistency/models/read-your-writes) e ["Monotonic Reads"](https://jepsen.io/consistency/models/monotonic-reads), além do [mapa de modelos de consistência](https://jepsen.io/consistency). Gratuito.
- Martin Kleppmann, [notas de aula "Distributed Systems"](https://www.cl.cam.ac.uk/teaching/2122/ConcDisSys/dist-sys-notes.pdf), Universidade de Cambridge, seção 5.2 (Quorums). Gratuito, Creative Commons BY-SA.
