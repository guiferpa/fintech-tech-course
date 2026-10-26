# Módulo 9, terça-feira: sobrecarga, filas acumuladas e consenso

[Módulo 9](../../modules/09-resilience-and-consensus.pt-BR.md) · [Read in English](day-2.md)

**Tempo de leitura:** cerca de 45 minutos. Use o resto do bloco de 2 horas nas referências do final. Deixe a [visualização do Raft](https://raft.github.io/) aberta enquanto lê as seções 6 e 7.

Este é um texto original escrito para este curso. Ele se baseia nas referências listadas no final, e cada seção indica a fonte que segue. Quando uma ideia vem de um autor específico, o texto diz isso.

## Por que isso importa para uma fintech

Ontem o assunto foi proteger seu serviço de uma dependência lenta. Hoje a visão se inverte: o que acontece quando é *você* quem recebe trabalho demais? Dia de pagamento, uma campanha de Black Friday, ou um parceiro que volta depois de uma queda e reenvia todos os webhooks de uma vez. Um serviço que tenta aceitar tudo acaba não atendendo ninguém.

A segunda metade do dia responde à pergunta bônus do teste de domínio: onde entra o consenso? Toda vez que um banco de dados faz failover para um novo primário, ou o Kafka escolhe um novo líder de partição, algum algoritmo decide quem é o líder. Se dois nós acreditam que são o líder do seu ledger, você tem duas versões de um saldo. O Raft é o algoritmo que impede isso, e você depende dele mais do que imagina.

## 1. Throughput não é goodput

*Fonte principal: David Yanacek, Amazon Builders' Library, "Using load shedding to avoid overload", as partes sobre a anatomia da sobrecarga.*

Yanacek separa dois números que parecem iguais em um dashboard:

- **Throughput**: todas as requisições por segundo que o servidor recebe.
- **Goodput**: a parte dessas requisições que o servidor responde sem erro *e* rápido o bastante para o cliente usar a resposta.

Conforme a carga sobe, a latência primeiro cresce devagar, depois dispara a partir de um ponto de inflexão, por causa da disputa por threads, CPU, garbage collection e I/O. Quando a latência do servidor passa do timeout do cliente, o servidor continua ocupado (o throughput está alto), mas toda resposta chega depois que o cliente desistiu (o goodput é zero). Yanacek dá uma regra prática simples: quando a latência mediana é igual ao timeout do cliente, metade das requisições dá timeout, então a disponibilidade é de 50%.

Esse trabalho desperdiçado se retroalimenta. Clientes que deram timeout fazem retry, o que acrescenta carga, o que aumenta a latência, o que causa mais timeouts. A amplificação de 243x por retries de ontem é o mesmo ciclo visto do outro lado.

## 2. Load shedding

*Fonte principal: Yanacek, "Using load shedding to avoid overload", as partes sobre load shedding, priorização e deadlines.*

A ideia central cabe em uma frase do artigo: "When a server approaches overload, it should start rejecting excess requests so that it can focus on the requests it decides to let in." (Quando um servidor se aproxima da sobrecarga, ele deve começar a rejeitar o excesso de requisições para poder se concentrar nas que decidiu aceitar.) Rejeitar 20% das requisições rapidamente mantém os outros 80% rápidos. Aceitar todas deixa 100% lentas.

Pontos práticos do artigo, com exemplos de carteira digital:

- **Descarte cedo e barato.** Rejeitar uma requisição também custa recursos, então rejeite antes de fazer o parse do corpo, abrir uma transação ou chamar qualquer coisa a jusante. Yanacek também alerta para rejeições caras, por exemplo registrar um stack trace completo para cada requisição rejeitada.
- **Priorize.** A prioridade máxima dele é o health check do load balancer: se o servidor está ocupado demais para respondê-lo, o load balancer o remove, e os servidores restantes recebem ainda mais carga. Depois disso, ele sugere terminar o trabalho já iniciado antes de aceitar trabalho novo (por exemplo, favorecer chamadas `end()` em vez de `start()`, ou páginas seguintes em vez de primeiras páginas). Em uma carteira digital: confirmar uma transferência que o cliente já autorizou vem antes de iniciar uma nova, e as duas vêm antes de uma busca por extratos antigos.
- **Respeite deadlines.** Se o cliente já desistiu, terminar o trabalho é desperdício. Clientes podem enviar quanto tempo vão esperar, e cada serviço repassa o tempo restante ao próximo. Verifique o deadline depois de tirar uma requisição de qualquer fila interna, não só na chegada.
- **Meça com honestidade.** Exclua rejeições rápidas das métricas de latência: Yanacek observa que um serviço descartando 60% do tráfego pode mostrar uma mediana enganosamente boa. Registre quem foi rejeitado e em qual operação, e busque zero rejeições quando há capacidade disponível.

Um limitador de concorrência mínimo em um middleware NestJS poderia ser assim:

```typescript
@Injectable()
export class ShedMiddleware implements NestMiddleware {
  private inFlight = 0;
  private readonly max = Number(process.env.MAX_IN_FLIGHT ?? 200);

  use(req: Request, res: Response, next: NextFunction) {
    if (req.path === '/health') return next();      // nunca descarte health checks
    const deadline = Number(req.header('x-deadline-ms')); // epoch ms absoluto, se enviado
    if (this.inFlight >= this.max || (deadline && Date.now() > deadline)) {
      res.status(503).set('Retry-After', '1').end(); // rejeição barata e cedo
      return;
    }
    this.inFlight++;
    res.on('close', () => this.inFlight--);
    next();
  }
}
```

Um deadline absoluto exige relógios razoavelmente sincronizados entre os hosts; Yanacek menciona esse trade-off, e a alternativa de enviar uma duração medida com relógio monotônico (Módulo 1).

## 3. Rate limiting por cliente

*Fonte principal: Yanacek, "Using load shedding to avoid overload", a parte sobre throttling; e o artigo "Avoiding insurmountable queue backlogs" sobre justiça entre clientes.*

O load shedding protege o servidor como um todo. O **rate limiting** (ou throttling) protege os clientes uns dos outros. Em um serviço multitenant, um parceiro de integração mandando uma rajada não pode deixar todos os outros clientes lentos. Os dois artigos da Amazon descrevem limites por cliente com alguma folga para rajadas, e Yanacek acrescenta que requisições acima da cota ainda podem ser aceitas quando sobra capacidade, mas com prioridade menor que as requisições dentro da cota.

O algoritmo usual é o **token bucket**. Cada cliente tem um balde com uma capacidade (o tamanho da rajada) que se recarrega a uma taxa fixa (o limite sustentado). Cada requisição consome um token; sem tokens, a requisição é rejeitada com HTTP 429. O estado por cliente é só dois números: tokens e o instante da última recarga.

```text
on request(client):
  elapsed = now - last_refill
  tokens  = min(capacity, tokens + elapsed * refill_rate)
  last_refill = now
  if tokens >= 1: tokens -= 1; allow
  else: reject 429 with Retry-After
```

Em uma frota de pods de API, esse estado precisa morar em um armazenamento compartilhado, e o ler-modificar-gravar precisa ser atômico, senão dois pods vão ver o último token ao mesmo tempo. Esse é o item 3 do TCM de quinta (token bucket no Redis), e você vai projetar o passo atômico por conta própria. Em uma carteira digital, rate limits costumam ser por cliente *e* por operação: por exemplo, um limite mais apertado em consultas de chave Pix (um alvo conhecido de enumeração) do que em leituras de saldo.

## 4. Filas acumuladas

*Fonte principal: David Yanacek, Amazon Builders' Library, "Avoiding insurmountable queue backlogs".*

Filas parecem a cura para a sobrecarga: o produtor grava uma mensagem e segue em frente, e os workers alcançam depois. Yanacek mostra o custo escondido. Um sistema baseado em filas é **bimodal**. Sem acúmulo, ele é rápido. Depois de uma queda ou de um pico, as mensagens chegam mais rápido do que são processadas, e a latência de ponta a ponta não para de crescer. Um serviço síncrono descarta requisições durante uma queda, mas se recupera na hora. Um serviço assíncrono guarda todo esse trabalho e precisa digeri-lo depois.

Vale decorar a conta dele. Depois de uma queda de uma hora, você precisa de cerca do dobro da capacidade normal por mais uma hora para alcançar, enquanto trabalho novo continua chegando. Se um pico coloca na fila 10 vezes a capacidade do consumidor, drenar leva horas. E quando as mensagens antigas forem processadas, o resultado pode ser inútil: uma notificação push de "sua transferência chegou" três horas atrasada é ruído.

Estratégias que o artigo descreve, e como elas se aplicam a uma carteira digital:

| Estratégia | Ideia | Exemplo na carteira digital |
| --- | --- | --- |
| Filas separadas por carga de trabalho | Isolamento, como um bulkhead | Uma fila por banco parceiro; liquidações separadas de notificações |
| Shuffle sharding | Cada cliente cai, por hash, em poucas filas de um pool | Grandes lojistas não bloqueiam os pequenos |
| Fila de transbordo (spillover) | O tráfego acima da taxa de um cliente vai para uma segunda fila | O arquivo de pagamentos em lote de um lojista não atrasa transferências de varejo |
| Desviar mensagens antigas | Mensagens com mais de X vão para uma fila de atraso, processada depois que a fila ao vivo alcança | Webhooks novos primeiro, antigos depois |
| Descartar mensagens antigas (TTL) | Seguro quando uma sincronização completa periódica vai corrigir o estado de qualquer jeito | Eventos de atualização do cache de saldo, nunca lançamentos do ledger |
| Backpressure | Pedir aos produtores que desacelerem quando o acúmulo cresce | Devolver 429 a um parceiro que reenvia webhooks |
| Dead-letter queue | Mensagens que falham sempre vão para o lado, com alarme | Um lançamento que viola uma constraint |
| Heartbeats | Jobs longos estendem sua concessão para que um segundo worker não os pegue | Um job de PDF de extrato que leva minutos |

A regra para dinheiro: **você pode reordenar, atrasar ou desviar movimentações de dinheiro, mas nunca descartá-las.** Descartar serve só para trabalho que pode ser recalculado ou que não vale nada quando chega atrasado.

Para monitoramento, Yanacek recomenda **a idade da mensagem mais antiga** (ou a idade na primeira tentativa de processamento) como sinal principal, e não a profundidade da fila ou os erros do consumidor. A profundidade não diz se você está dois segundos ou duas horas atrasado. Ele também usa a lei de Little para mostrar a armadilha das threads: 100 mensagens por segundo a 100 ms cada exigem cerca de 10 workers, mas se o processamento cai para 10 s, você precisaria de cerca de 1.000.

## 5. Por que consenso é necessário

*Fontes principais: Marc Brooker, Amazon Builders' Library, "Leader election in distributed systems"; documentação do etcd, "FAQ".*

No Módulo 1 você viu que um único líder dá uma ordem total: todas as escritas passam por um nó, que decide a ordem delas, e as réplicas as aplicam nessa ordem. É assim que um primário do Postgres funciona. O artigo do Brooker lista por que os times gostam de líderes: eles tornam o sistema mais fácil de entender e podem oferecer consistência forte aos clientes. E é igualmente direto sobre o custo: "A single leader is a single point of failure." Quando o primário morre, alguém precisa escolher um novo.

Uma pessoa pode escolher o novo primário, mas aí uma queda não planejada dura até alguém acordar. A alternativa é a eleição automática. O Brooker descreve a abordagem usual da Amazon, os **leases**: "a single database that stores the current leader", e um líder que precisa mandar heartbeats periodicamente para manter o papel. Ele observa que DynamoDB e ZooKeeper oferecem clientes de lock baseados em lease para isso. O store que guarda o lease também precisa sobreviver a falhas, e stores como etcd e Consul conseguem isso com o Raft.

O perigo é o **split brain**: dois nós agindo como líder ao mesmo tempo, cada um aceitando escritas. Para um ledger, isso significa duas histórias divergentes de lançamentos. O Brooker alerta que uma pausa de garbage collection entre verificar um lease e fazer o trabalho pode levar um líder antigo a agir depois de perder o papel; então verifique o lease logo antes de efeitos colaterais e deixe o banco rejeitar um segundo líder (a ideia de fencing do Módulo 3).

O FAQ do etcd explica a defesa: um cluster só funciona enquanto a maioria dos membros (um quorum) consegue conversar entre si, um modelo que "totally avoids any possibility of split brain inconsistency". Quaisquer duas maiorias têm pelo menos um membro em comum, então dois grupos nunca podem ter quorum ao mesmo tempo.

Duas consequências práticas, ambas no FAQ:

| Membros | Quorum | Falhas toleradas |
| --- | --- | --- |
| 1 | 1 | 0 |
| 3 | 2 | 1 |
| 4 | 3 | 1 |
| 5 | 3 | 2 |
| 7 | 4 | 3 |

- **Use um número ímpar de membros.** Um cluster de 4 membros tolera a mesma falha única que um de 3, com uma máquina a mais para pagar. Durante uma partição de rede, um número ímpar garante que sempre existe um lado com maioria.
- **Não cresça demais.** O FAQ diz que um cluster "probably should have no more than seven nodes", porque toda escrita precisa ser replicada para mais máquinas. A documentação do Consul dá o mesmo conselho com outras palavras: 3 ou 5 servidores em produção.

## 6. Eleição de líder no Raft, como o etcd e o CockroachDB rodam

*Fontes principais: documentação do HashiCorp Consul, "Consensus"; documentação da Cockroach Labs, "Replication Layer"; documentação do etcd, "Tuning", "Failure modes" e "etcd API".*

A documentação do Consul descreve o Raft em poucas frases, suficientes para acompanhar uma eleição. Todo nó começa como **follower**. Se um follower não recebe nada de um líder por algum tempo, ele se promove a **candidate** e pede votos aos outros membros. Um candidate que recebe um quorum de votos vira **leader**. O líder aceita novas entradas de log e as replica para os followers.

Dois timers comandam isso, e a página "Tuning" do etcd dá números reais:

- **Heartbeat interval.** Com que frequência o líder avisa os followers de que está vivo. O padrão do etcd é 100 ms, e a página recomenda algo em torno do tempo de ida e volta entre os membros.
- **Election timeout.** Quanto tempo um follower espera sem notícias do líder antes de iniciar uma eleição. O padrão do etcd é 1.000 ms, e a página diz que ele precisa ser pelo menos 10 vezes o tempo de ida e volta para absorver a variação da rede. Um valor maior demora mais para detectar um líder morto; um heartbeat menor manda mensagens desnecessárias.

```sh
etcd --heartbeat-interval=100 --election-timeout=500   # valores em milissegundos
```

Se todo follower usasse exatamente o mesmo timeout, todos iniciariam eleições no mesmo instante e dividiriam os votos. A página "Replication Layer" do CockroachDB mostra a solução padrão: os followers viram candidates "after randomized election timeouts", com o timeout multiplicado por um fator aleatório entre 1 e 2 "to avoid election ties". Normalmente um follower estoura o timeout primeiro e vence antes que os outros acordem. A visualização no site do Raft permite assistir a eleições como essa.

Cada eleição inicia um novo **term**, um número que identifica um período de liderança. O etcd o mostra aos clientes: todo cabeçalho de resposta traz um campo `raft_term`, e a página da API do etcd diz que as aplicações podem usá-lo para saber quando o cluster terminou de eleger um novo líder. Uma mensagem de um term mais antigo é uma mensagem de um líder que já foi substituído.

Quanto um failover custa para a sua aplicação? A página "Failure modes" do etcd responde de forma concreta:

- Quando o líder falha, "it takes about an election timeout to elect a new leader". Com os padrões, cerca de um segundo.
- Requisições de escrita enviadas durante a eleição ficam enfileiradas até existir um novo líder.
- Escritas já enviadas ao líder antigo, mas ainda não confirmadas, podem se perder, mas "no committed writes are ever lost".

Esse é o contrato para lembrar: timeouts afetam a velocidade de recuperação do cluster, nunca se uma escrita confirmada sobrevive. O site do Raft diz o mesmo: quando servidores demais falham, o cluster para de avançar, "but will never return an incorrect result".

## 7. Replicação de log, partições e onde você encontra o Raft

*Fontes principais: documentação do HashiCorp Consul, "Consensus"; documentação do etcd, "Failure modes" e "etcd API"; documentação da Cockroach Labs, "Replication Layer"; documentação do Patroni.*

Depois de eleito, o líder transforma cada comando do cliente numa **entrada de log**. A documentação do Consul dá a regra de commit: "An entry is considered committed when it is durably stored on a quorum of nodes." Só então ela é aplicada à máquina de estados (o key-value store, no caso do etcd). Snapshots compactam o log, e a documentação do CockroachDB acrescenta que um nó atrasado carrega um snapshot e reexecuta o log do Raft para se atualizar.

Agora particione um cluster de 5 membros em um grupo de 3 e um grupo de 2, com o líder antigo no lado menor. A página "Failure modes" do etcd descreve o que acontece:

1. O lado com maioria elege um novo líder e vira o cluster disponível.
2. O lado minoritário fica indisponível. O líder dele deixa o papel.
3. Quando a partição se desfaz, o lado minoritário reconhece o novo líder e recupera seu estado.

O líder antigo não consegue confirmar nada durante a partição, porque não alcança um quorum. O Consul diz o mesmo: se um quorum não está disponível, nenhum log novo pode ser confirmado. É por isso que o líder isolado é inofensivo.

As leituras também têm uma escolha. A página da API do etcd diz que leituras são linearizable por padrão, enquanto uma leitura serializable é atendida localmente por qualquer membro: mais rápida, mas possivelmente desatualizada. Uma checagem de saldo antes de um débito precisa da primeira; um dashboard convive bem com a segunda.

Onde isso encontra a sua carteira digital? Você não vai implementar Raft; você vai usá-lo. O etcd roda sobre ele (e o Kubernetes guarda seu estado no etcd), e o Patroni, uma ferramenta de alta disponibilidade para Postgres, depende de um store como etcd, Consul, ZooKeeper ou Kubernetes para decidir qual nó Postgres é o primário. Quando um entrevistador perguntar como o failover evita dois primários, a resposta é um voto da maioria com terms, e uma escrita que só vale depois que a maioria a tem. O custo é latência: toda escrita confirmada espera uma ida e volta até um quorum, o que é barato dentro de uma região e caro entre continentes. O FAQ do etcd aponta esse trade-off para clusters espalhados entre regiões, e a discussão de active-active de amanhã depende dele.

## O que anotar hoje

1. O que uma fila acumulada faz com o tempo de recuperação (o exemplo da queda de uma hora), e quais mensagens da carteira digital você pode atrasar, desviar ou descartar, e quais nunca pode descartar.
2. Load shedding x rate limiting: o que cada um protege, o que você descarta primeiro e o token bucket em cinco linhas.
3. Por que consenso é necessário: líder único como ponto único de falha, leases, split brain e a tabela de quorum, com o motivo dos tamanhos ímpares.
4. Como funciona uma eleição Raft no etcd: follower, candidate, leader, terms, os dois timers com seus valores padrão e por que os timeouts são sorteados.
5. Quando uma entrada de log é confirmada, o que cada lado de uma partição faz e quanto um failover custa para as suas escritas (enfileiradas, as não confirmadas podem se perder, as confirmadas nunca).

## Teste-se

Estas perguntas dão bons flashcards (veja o [guia de flashcards](../../FLASHCARDS.pt-BR.md)).

- Qual a diferença entre throughput e goodput?
- Por que um servidor deve responder ao health check mesmo quando está descartando carga?
- Por que a idade da mensagem mais antiga é um alarme melhor que a profundidade da fila?
- O que um token bucket guarda por cliente, e o que o torna seguro entre muitos pods?
- Por que um cluster etcd de 4 membros não tolera mais falhas que um de 3?
- Quando uma entrada de log do Raft está confirmada?
- O que acontece com as escritas enviadas ao etcd durante uma eleição de líder?
- Por que as implementações de Raft sorteiam o election timeout?

## Referências

- **Fonte principal:** David Yanacek, ["Avoiding insurmountable queue backlogs"](https://aws.amazon.com/builders-library/avoiding-insurmountable-queue-backlogs/), Amazon Builders' Library, 2019. Leia inteiro, especialmente as estratégias para sistemas multitenant. Gratuito.
- **Fonte principal:** David Yanacek, ["Using load shedding to avoid overload"](https://aws.amazon.com/builders-library/using-load-shedding-to-avoid-overload/), Amazon Builders' Library, 2019. Leia inteiro. Gratuito.
- **Fonte principal:** Marc Brooker, ["Leader election in distributed systems"](https://aws.amazon.com/builders-library/leader-election-in-distributed-systems/), Amazon Builders' Library, 2019. Leia inteiro: por que ter líderes, leases e o problema do líder desatualizado. Gratuito.
- **Fonte principal:** documentação do etcd, ["FAQ"](https://etcd.io/docs/v3.6/faq/) e ["Failure modes"](https://etcd.io/docs/v3.6/op-guide/failures/). No FAQ, leia as perguntas sobre tamanho do cluster, tolerância a falhas, números ímpares e latência de disco. "Failure modes" é curto; leia inteiro. Gratuito.
- Documentação do etcd, ["Tuning"](https://etcd.io/docs/v3.6/tuning/). Leia os parâmetros de tempo: heartbeat interval e election timeout. Gratuito.
- Documentação do HashiCorp Consul, ["Consensus"](https://developer.hashicorp.com/consul/docs/concept/consensus). Uma visão geral do Raft em uma página, escrita por um produto que o roda, com a tabela de implantação. Gratuito.
- Documentação da Cockroach Labs, ["Replication Layer"](https://docs.cockroachlabs.com/docs/stable/architecture/replication-layer). Leia a seção sobre Raft: grupos Raft, election timeouts sorteados e snapshots. Gratuito.
- Documentação do Patroni, ["Introduction"](https://patroni.readthedocs.io/en/latest/). Opcional: passe os olhos na primeira página para ver de quais stores (etcd, Consul, ZooKeeper, Kubernetes) uma ferramenta real de failover de Postgres depende. Gratuito.
- Site [The Raft Consensus Algorithm](https://raft.github.io/), com uma visualização interativa de cinco servidores e seus logs: assista a uma eleição e à replicação de log acontecendo. O site também linka [The Secret Lives of Data](http://thesecretlivesofdata.com/raft/), um passo a passo mais guiado e menos interativo do mesmo algoritmo. Gratuito.
