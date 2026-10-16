# Módulo 9, terça-feira: sobrecarga, filas acumuladas e consenso

[Módulo 9](../../modules/09-resilience-and-consensus.pt-BR.md) · [Read in English](day-2.md)

**Tempo de leitura:** cerca de 45 minutos. Use o resto do bloco de 2 horas nas referências do final. Deixe a [visualização do Raft](https://raft.github.io/) aberta enquanto lê as seções 5 a 7.

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

*Fonte principal: Martin Kleppmann, notas de aula "Distributed Systems" (Universidade de Cambridge), seção 6.1, na forma apresentada nos slides para impressão do curso.*

No Módulo 1 você viu que um único líder dá uma ordem total: todas as escritas passam por um nó, que decide a ordem delas, e as réplicas as aplicam nessa ordem. É assim que um primário do Postgres funciona. Mas o líder é um ponto único de falha. Quando ele morre, alguém precisa escolher um novo.

Kleppmann descreve as duas opções:

- **Failover manual**: um operador escolhe um novo líder e reconfigura todos os nós. Comum em bancos de dados e aceitável para manutenção planejada, mas quedas não planejadas duram o tempo que uma pessoa leva para acordar e agir.
- **Failover automático**: os próprios nós elegem um novo líder. É aqui que entra o consenso.

Tradicionalmente, **consenso** significa vários nós concordando sobre um valor. Kleppmann mostra que concordar sobre "a próxima mensagem a entregar", repetidas vezes, dá a você total order broadcast, e que os dois problemas são formalmente equivalentes. Os algoritmos conhecidos são Paxos (com Multi-Paxos para uma sequência de valores), Raft, Viewstamped Replication e Zab.

Dois limites enquadram o que esses algoritmos conseguem fazer:

- **Resultado FLP.** Os slides afirmam: "There is no deterministic consensus algorithm that is guaranteed to terminate in an asynchronous crash-stop system model." (Não existe algoritmo de consenso determinístico com garantia de terminar em um modelo de sistema assíncrono crash-stop.) Por isso Paxos e Raft assumem um modelo **parcialmente síncrono e crash-recovery** (Módulo 1, seção 4).
- **Relógios só para liveness.** Eles usam timeouts para detectar um líder que falhou e para avançar, mas a **safety** nunca depende de tempo. Um timeout errado pode causar uma eleição desnecessária; não pode causar dois históricos confirmados diferentes.

O perigo a evitar é o **split brain**: dois nós agindo como líder ao mesmo tempo, cada um aceitando escritas. Para um ledger, isso significa dois históricos divergentes de lançamentos e, depois que a partição se resolve, nenhum saldo correto.

## 6. Eleição de líder no Raft

*Fonte principal: Diego Ongaro e John Ousterhout, "In Search of an Understandable Consensus Algorithm" (o paper do Raft), seções 5.1, 5.2 e 5.6. As notas de Kleppmann, seção 6.2, cobrem o mesmo algoritmo.*

Um cluster Raft normalmente tem cinco servidores, o que tolera duas falhas. Cada servidor está em um de três estados:

| Estado | Papel | Passa a ser |
| --- | --- | --- |
| **Follower** | Passivo; responde a requisições de líderes e candidatos | Candidate, se não ouvir nada de um líder durante um election timeout |
| **Candidate** | Pede votos | Leader com maioria dos votos; follower se vir um líder válido ou um term mais novo |
| **Leader** | Atende todas as requisições de clientes, replica o log, envia heartbeats | Follower, se vir um term maior |

O tempo é dividido em **terms** numerados. Cada term começa com uma eleição. Os servidores incluem seu term em toda mensagem; um servidor que vê um term maior atualiza o seu e, se era líder ou candidato, volta a ser follower. O Raft precisa de só dois RPCs: `RequestVote` (enviado por candidatos) e `AppendEntries` (enviado pelo líder para replicar entradas, e vazio como heartbeat).

Uma eleição acontece assim:

1. O election timeout de um follower expira sem nenhum heartbeat.
2. Ele incrementa seu term, vira candidato, vota em si mesmo e envia `RequestVote` a todos.
3. Cada servidor vota em no máximo um candidato por term, por ordem de chegada, e só se o log do candidato estiver pelo menos tão atualizado quanto o seu (seção 5.4).
4. Um candidato com votos da maioria do cluster inteiro vira líder e começa a enviar heartbeats.
5. Se os votos se dividem, o term termina sem líder, e uma nova eleição começa depois de outro timeout.

A garantia central do paper: "Raft ensures that there is at most one leader in a given term." (O Raft garante que existe no máximo um líder em um dado term.) Ela vem das maiorias: dois candidatos não conseguem votos da maioria no mesmo term, porque duas maiorias quaisquer têm pelo menos um servidor em comum, e esse servidor vota uma vez só.

Para que votos divididos sejam raros, o Raft **sorteia os election timeouts**, por exemplo entre 150 e 300 ms, então normalmente um servidor dá timeout primeiro e vence antes que os outros acordem. A seção 5.6 dá o requisito de tempo: o tempo de broadcast muito menor que o election timeout, que por sua vez é muito menor que o tempo médio entre falhas. Os números do paper: tempo de broadcast de 0,5 a 20 ms, election timeout entre 10 e 500 ms, e MTBF de um servidor de vários meses ou mais.

O que o Raft não consegue impedir, como observam os slides de Kleppmann, é que dois líderes de terms *diferentes* existam ao mesmo tempo: um líder antigo isolado por uma partição pode não saber que foi substituído. É por isso que um líder precisa ouvir a maioria antes que uma escrita conte. O líder antigo não alcança a maioria, então nada que ele aceite chega a ser confirmado. Os fencing tokens do Módulo 3 aplicam a mesma ideia (o term maior vence) a locks.

## 7. Replicação de log no Raft

*Fonte principal: Ongaro e Ousterhout, o paper do Raft, seções 5.3 e 5.4.*

Depois de eleito, o líder transforma comandos de clientes em entradas de log:

1. O líder acrescenta o comando ao seu log, marcado com o term e o índice atuais.
2. Ele envia `AppendEntries` a todos os followers em paralelo.
3. Quando a maioria armazenou a entrada, ela está **committed** (confirmada). O líder a aplica à sua máquina de estados e responde ao cliente. Confirmar uma entrada também confirma todas as anteriores.
4. Os followers ficam sabendo do índice de commit pelos `AppendEntries` seguintes e aplicam as entradas em ordem.

Cada `AppendEntries` carrega o índice e o term da entrada imediatamente anterior às novas. Um follower que não tem essa entrada rejeita a requisição, e o líder recua (decrementando seu `nextIndex` para aquele follower) até achar o ponto em que os dois logs concordam. Então ele sobrescreve as entradas conflitantes do follower. Essa verificação de consistência mantém a propriedade de **Log Matching**.

A seção 5.4 acrescenta duas regras de safety. Primeiro, a **restrição de eleição**: um candidato não vence se seu log não estiver pelo menos tão atualizado quanto o de uma maioria (comparando o term da última entrada, depois o tamanho), então um novo líder sempre tem todas as entradas confirmadas. Segundo, um líder nunca decide que uma entrada de um term *anterior* está confirmada só contando réplicas; ele confirma uma entrada do seu próprio term, o que confirma as antigas junto. A Figura 8 do paper mostra o cenário que torna essa regra necessária.

A Figura 3 do paper lista as propriedades que o Raft garante:

| Propriedade | Significado |
| --- | --- |
| Election Safety | No máximo um líder por term |
| Leader Append-Only | Um líder nunca sobrescreve nem apaga suas próprias entradas |
| Log Matching | Mesmo índice e mesmo term significam a mesma entrada e o mesmo histórico antes dela |
| Leader Completeness | Uma entrada confirmada está presente no log de todo líder posterior |
| State Machine Safety | Dois servidores nunca aplicam entradas diferentes no mesmo índice |

Onde isso encontra sua carteira digital? Você não vai implementar Raft. Você vai usá-lo: o etcd é construído sobre Raft, e ferramentas como o Patroni usam um armazenamento como o etcd para decidir qual nó do Postgres é o primário; o modo KRaft do Kafka usa um quorum de controladores baseado em Raft. Quando um entrevistador perguntar como o failover evita dois primários, a resposta é uma votação por maioria com terms, e uma escrita que só conta depois que a maioria a tem. O custo é latência: toda escrita confirmada espera uma ida e volta até a maioria, o que é barato dentro de uma região e caro entre continentes. A discussão de ativo-ativo de amanhã depende disso.

## O que anotar hoje

1. O que uma fila acumulada faz com o tempo de recuperação (o exemplo da queda de uma hora), e quais mensagens da carteira digital você pode atrasar, desviar ou descartar, e quais nunca pode descartar.
2. Load shedding x rate limiting: o que cada um protege, o que você descarta primeiro e o token bucket em cinco linhas.
3. Por que consenso é necessário: failover manual x automático, split brain e o resultado FLP em uma frase.
4. Como o Raft elege um líder: estados, terms, as regras de voto e por que os timeouts sorteados importam.
5. Como o Raft replica e confirma uma entrada de log, e por que um líder antigo isolado não consegue confirmar nada.

## Teste-se

Estas perguntas dão bons flashcards (veja o [guia de flashcards](../../FLASHCARDS.pt-BR.md)).

- Qual a diferença entre throughput e goodput?
- Por que um servidor deve responder ao health check mesmo quando está descartando carga?
- Por que a idade da mensagem mais antiga é um alarme melhor que a profundidade da fila?
- O que um token bucket guarda por cliente, e o que o torna seguro entre muitos pods?
- Por que dois líderes Raft não podem ser eleitos no mesmo term?
- Quando uma entrada de log do Raft está confirmada?
- Por que algoritmos de consenso usam relógios só para liveness, e não para safety?

## Referências

- **Fonte principal:** David Yanacek, ["Avoiding insurmountable queue backlogs"](https://aws.amazon.com/builders-library/avoiding-insurmountable-queue-backlogs/), Amazon Builders' Library, 2019. Leia inteiro, especialmente as estratégias para sistemas multitenant. Gratuito.
- **Fonte principal:** David Yanacek, ["Using load shedding to avoid overload"](https://aws.amazon.com/builders-library/using-load-shedding-to-avoid-overload/), Amazon Builders' Library, 2019. Leia inteiro. Gratuito.
- **Fonte principal:** Martin Kleppmann, [notas de aula "Distributed Systems"](https://www.cl.cam.ac.uk/teaching/2122/ConcDisSys/dist-sys-notes.pdf), Universidade de Cambridge, 2021/22, capítulo 6 (Consensus: 6.1 Introduction e 6.2 Raft). Gratuito, Creative Commons BY-SA. O mesmo material está nos [slides para impressão](https://www.cl.cam.ac.uk/teaching/2122/ConcDisSys/dist-sys-handout.pdf), e os vídeos correspondentes estão linkados na [página de materiais do curso](https://www.cl.cam.ac.uk/teaching/2122/ConcDisSys/materials.html).
- **Fonte principal:** Diego Ongaro e John Ousterhout, ["In Search of an Understandable Consensus Algorithm (Extended Version)"](https://raft.github.io/raft.pdf), o paper do Raft. Leia a seção 5 (5.1 a 5.6) e a Figura 3; a Figura 2 é um resumo de uma página do algoritmo inteiro. Gratuito.
- Site [The Raft Consensus Algorithm](https://raft.github.io/), com uma visualização interativa. Derrube um líder, acompanhe uma eleição e particione o cluster. Gratuito.
