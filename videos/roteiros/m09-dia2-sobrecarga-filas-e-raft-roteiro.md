# Roteiro · M9 · Dia 2 · Sobrecarga, filas e Raft


## Abertura

Esta é a aula em vídeo do módulo nove, dia dois: sobrecarga, filas acumuladas e Raft.

Ontem, você se protegeu de uma dependência lenta. Hoje a visão se inverte: e quando é você que recebe trabalho demais? Dia de pagamento, Black Friday, ou um parceiro que volta de uma queda e reenvia todos os webhooks de uma vez. Um serviço que tenta aceitar tudo acaba não atendendo ninguém. E a segunda metade responde à pergunta bônus: onde entra o consenso? Se dois nós acreditam que são o líder do seu ledger, você tem duas versões de um saldo. O Raft é o algoritmo que impede isso.


## Throughput e goodput

David Yanacek, da Amazon, separa dois números que parecem iguais num dashboard.

Throughput: todas as requisições por segundo que o servidor recebe.

Goodput: as que ele responde sem erro e rápido o bastante para o cliente usar a resposta. Conforme a carga sobe, a latência cresce devagar, depois dispara. Quando passa do timeout do cliente, o servidor continua ocupado, mas toda resposta chega depois que o cliente desistiu. Throughput alto, goodput zero. Regra prática: mediana igual ao timeout do cliente, metade dá timeout, disponibilidade de cinquenta por cento. E os clientes que deram timeout fazem retry, o que aumenta a carga. É a tempestade de retries de ontem, vista do outro lado.


## Load shedding

A ideia central: quando um servidor se aproxima da sobrecarga, ele começa a rejeitar o excesso, para se concentrar nas requisições que decidiu aceitar.

Rejeitar vinte por cento rapidamente mantém os outros oitenta rápidos. Aceitar todas deixa cem por cento lentas.

Descarte cedo e barato: antes de fazer parse do corpo, abrir transação, ou chamar qualquer coisa. E nada de registrar um stack trace completo para cada rejeição.

Priorize. O health check do load balancer nunca é descartado: senão o servidor é removido, e os outros recebem ainda mais carga. Depois, termine o trabalho já iniciado antes de aceitar novo. Na carteira: confirmar uma transferência já autorizada vem antes de iniciar uma nova, e as duas vêm antes de buscar extratos antigos.

Respeite deadlines. Se o cliente já desistiu, terminar é desperdício. Clientes enviam quanto tempo vão esperar, e cada serviço repassa o restante. Verifique o deadline também ao tirar uma requisição de uma fila interna.

E meça com honestidade. Exclua rejeições rápidas da latência: um serviço descartando sessenta por cento pode mostrar uma mediana enganosamente boa. Num middleware Nest J S, basta um contador de requisições em andamento: acima do máximo, ou com deadline vencido, responda 503 com retry after, cedo e barato.


## Rate limiting

O load shedding protege o servidor como um todo. O rate limiting protege os clientes uns dos outros: um parceiro mandando uma rajada não pode deixar todos os outros lentos.

O algoritmo usual é o token bucket. Cada cliente tem um balde. A cada requisição, recarregue os tokens pelo tempo que passou, até a capacidade. Se houver um token, consome e permite. Senão, rejeita com 429 e retry after. O estado por cliente é só dois números: tokens e o instante da última recarga.

A capacidade é o tamanho da rajada. A taxa de recarga é o limite sustentado.

Numa frota de pods, esse estado mora no Redis, e o ler-modificar-gravar precisa ser atômico, senão dois pods veem o último token ao mesmo tempo. É o item três do projeto de quinta, e você vai projetar o passo atômico.

E na carteira, os limites são por cliente e por operação. Consultas de chave Pix, alvo conhecido de enumeração, têm limite mais apertado que leituras de saldo.

> **Pausa:** Pergunta: por que o token bucket no Redis precisa de um passo atômico?

Porque dois pods podem ler o mesmo último token ao mesmo tempo, e os dois permitem. O ler, recarregar, consumir e gravar precisa acontecer como uma operação só.


## Filas acumuladas

Filas parecem a cura: o produtor grava e segue, e os workers alcançam depois. Mas um sistema com filas é bimodal.

Sem acúmulo, é rápido. Depois de uma queda ou pico, as mensagens chegam mais rápido do que são processadas, e a latência de ponta a ponta não para de crescer. Um serviço síncrono descarta durante a queda e se recupera na hora. Um assíncrono guarda o trabalho todo, e precisa digerir depois.

A conta para decorar: depois de uma queda de uma hora, você precisa de cerca do dobro da capacidade por mais uma hora para alcançar, enquanto trabalho novo continua chegando.

E quando a mensagem antiga é processada, o resultado pode ser inútil. Um push de sua transferência chegou três horas depois é ruído.

Monitore a idade da mensagem mais antiga, não a profundidade da fila. A profundidade não diz se você está dois segundos ou duas horas atrasado.

E a lei de Little mostra a armadilha das threads: cem mensagens por segundo a cem milissegundos pedem uns dez workers. Se o processamento cai para dez segundos, você precisaria de uns mil.


## Estratégias para filas

Estratégias de Yanacek, aplicadas à carteira.

Filas separadas por carga de trabalho, como um bulkhead: uma por banco parceiro, e liquidações separadas de notificações.

Shuffle sharding e fila de transbordo: grandes lojistas, ou o arquivo de pagamentos em lote de um lojista, não atrasam as transferências de varejo.

Desviar mensagens antigas para uma fila de atraso, processada depois que a fila ao vivo alcança.

Descartar mensagens antigas, com T T L, só quando uma sincronização periódica vai corrigir o estado, como eventos de cache de saldo. Nunca lançamentos do ledger.

Backpressure: pedir aos produtores que desacelerem, como devolver 429 a um parceiro reenviando webhooks.

Dead-letter para mensagens que falham sempre, com alarme. E heartbeats para jobs longos estenderem a concessão, senão um segundo worker os pega. A regra para dinheiro: você pode reordenar, atrasar ou desviar movimentações de dinheiro. Nunca descartar.

> **Pausa:** Pergunta: que mensagens da carteira você pode descartar quando ficam velhas?

Só as que podem ser recalculadas ou não valem nada atrasadas, como atualizações de cache ou certos pushes. Movimentações de dinheiro nunca.


## Por que consenso

Um único líder dá ordem total: todas as escritas passam por ele, como num primário do Postgres. Mas um único líder é um ponto único de falha. Quando ele morre, alguém escolhe outro. A abordagem usual da Amazon são leases: um store guarda o líder atual, e o líder manda heartbeats para manter o papel. O perigo é o split brain: dois nós agindo como líder, e para um ledger, duas histórias divergentes. Uma pausa de garbage collection pode fazer um líder antigo agir depois de perder o papel. Por isso, cheque o lease logo antes dos efeitos, e deixe o banco rejeitar o segundo líder, com fencing. A defesa do etcd é o quorum: só a maioria funciona.

Um membro: quorum um, não tolera falha.

Três membros: quorum dois, tolera uma falha.

Quatro membros: quorum três, e ainda tolera uma só. Uma máquina a mais para pagar, sem ganho.

Cinco: quorum três, tolera duas.

Sete: quorum quatro, tolera três.

Então use número ímpar, e não cresça demais: no máximo sete, porque toda escrita é replicada para mais máquinas. Quaisquer duas maiorias têm pelo menos um membro em comum, então dois grupos nunca têm quorum ao mesmo tempo. É isso que elimina o split brain.

> **Pausa:** Pergunta: por que um cluster de quatro membros não é melhor que um de três?

Porque o quorum de quatro é três, e ele tolera só uma falha, igual ao de três. Você paga uma máquina a mais sem ganhar tolerância.


## Eleição no Raft

O Raft em poucas frases.

Todo nó começa como follower, recebendo heartbeats do líder.

Se um follower fica sem notícias por algum tempo, vira candidate e pede votos.

Quem recebe um quorum de votos vira leader, aceita novas entradas de log, e as replica.

Dois timers comandam isso. No etcd, o heartbeat é de cem milissegundos, perto do tempo de ida e volta. E o election timeout, de mil milissegundos, pelo menos dez vezes a ida e volta, para absorver a variação da rede.

Se todo follower usasse o mesmo timeout, todos começariam eleições juntos e dividiriam os votos. Então o timeout é sorteado, multiplicado por um fator entre um e dois. Normalmente um acorda primeiro e vence antes dos outros.

Cada eleição inicia um novo term, um número de período de liderança. O etcd mostra o raft term em toda resposta. Uma mensagem de um term mais antigo vem de um líder já substituído.

> **Pausa:** Pergunta: por que o election timeout é sorteado?

Para evitar que vários followers virem candidates ao mesmo tempo e dividam os votos, sem ninguém ganhar.


## Commit e partições

Depois de eleito, o líder transforma cada comando numa entrada de log.

Uma entrada está confirmada quando está gravada de forma durável num quorum. Só então é aplicada à máquina de estados. Agora particione um cluster de cinco em três e dois, com o líder antigo no lado menor.

O lado de três elege um novo líder e vira o cluster disponível.

O lado de dois fica indisponível. O líder antigo não alcança quorum, então não confirma nada. Por isso ele é inofensivo.

Quando a partição se desfaz, a minoria reconhece o novo líder e recupera o estado.

E quanto custa um failover? Cerca de um election timeout, um segundo com os padrões. As escritas enviadas durante a eleição ficam enfileiradas. As enviadas ao líder antigo e ainda não confirmadas podem se perder. As confirmadas, nunca. Timeouts afetam a velocidade de recuperação, nunca se uma escrita confirmada sobrevive. E leituras: linearizable por padrão, serializable mais rápida mas talvez desatualizada. Checagem de saldo antes de débito precisa da primeira.


## Onde você encontra o Raft

Onde isso encontra a sua carteira? Você não vai implementar o Raft. Vai usá-lo.

O etcd roda sobre ele, e o Kubernetes guarda o estado no etcd.

O Patroni, de alta disponibilidade para Postgres, depende de um store como etcd, Consul ou ZooKeeper para decidir qual nó é o primário.

Quando o entrevistador perguntar como o failover evita dois primários: um voto da maioria com terms, e uma escrita que só vale depois que a maioria a tem.

O custo é latência: toda escrita confirmada espera uma ida e volta até um quorum. Barato dentro de uma região, caro entre continentes. A discussão de active-active de amanhã depende disso.


## Revisão relâmpago

Hora da revisão relâmpago. São três perguntas, sem olhar.

> **Pausa:** Pergunta um: como um servidor pode ter throughput alto e goodput zero?

Quando a latência passa do timeout do cliente. O servidor trabalha, mas toda resposta chega depois que o cliente desistiu.

> **Pausa:** Pergunta dois: qual a métrica principal para uma fila?

A idade da mensagem mais antiga, não a profundidade.

> **Pausa:** Pergunta três: num failover do Raft, uma escrita confirmada pode se perder?

Nunca. Só escritas ainda não confirmadas podem se perder.


## O que anotar e próximo passo

Anote com as suas palavras: filas acumuladas e o que pode ser descartado. Load shedding contra rate limiting, e o token bucket. Por que consenso, com a tabela de quorum. A eleição do Raft. E o commit, a partição e o custo do failover.

Depois, no lab, acrescente timeouts e o circuit breaker, e meça de novo. Até a próxima aula.
