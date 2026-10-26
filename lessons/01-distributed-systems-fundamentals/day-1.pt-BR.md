# Módulo 1, segunda-feira: falhas, timeouts e tempo

[Módulo 1](../../modules/01-distributed-systems-fundamentals.pt-BR.md) · [Read in English](day-1.md)

**Tempo de leitura:** cerca de 45 minutos. Use o resto do bloco de 2 horas nas referências do final, começando pelas seções marcadas como fonte principal.

Este é um texto original escrito para este curso. Ele se baseia nas referências listadas no final, e cada seção indica a fonte que segue. Quando uma ideia vem de um autor ou de uma empresa específica, o texto diz isso.

## Por que isso importa para uma fintech

Um sistema de pagamentos é um sistema distribuído desde a primeira linha de código. Sua API conversa com um banco de dados, o banco replica para outra máquina, um worker chama um banco parceiro, e o banco parceiro chama a bandeira do cartão ou o Pix. Cada seta desse desenho é uma chamada de rede. E toda chamada de rede pode falhar de jeitos que uma chamada de função em uma única máquina não falha.

Os bugs mais caros em pagamentos vêm de uma confusão: tratar "não recebi resposta" como "não aconteceu". Esta aula explica por que as duas coisas são diferentes e o que fazer a respeito, usando o jeito como Amazon, Google, Cloudflare e Cockroach Labs descrevem o problema no seu próprio material de engenharia.

## 1. O que torna um sistema distribuído

*Fonte principal: AWS Builders' Library, "Challenges with distributed systems" (Jacob Gabrielson).*

Um sistema distribuído é um conjunto de computadores que cooperam por uma rede para fazer um trabalho. Eles não compartilham memória. A única forma de uma máquina saber algo sobre outra é recebendo uma mensagem dela.

Gabrielson, senior principal engineer na AWS, separa os sistemas offline (jobs em lote, que têm os benefícios da distribuição quase sem nenhuma dor), os sistemas soft real-time (que continuam produzindo resultados dentro de uma janela folgada) e os sistemas **hard real-time**, que precisam responder rápido a requisições imprevisíveis. Entre os exemplos desse último tipo ele cita todas as APIs da AWS e **pagamentos**. Sua carteira digital é do tipo hard. A expressão-chave do artigo é que o cliente, o servidor e a rede não "compartilham o destino" ("share fate"). Em uma máquina só, um programa ou funciona ou a máquina inteira está fora do ar. Através de uma rede, o servidor pode cair enquanto o cliente continua rodando, ou a rede pode perder uma mensagem com as duas máquinas saudáveis. Jeff Hodges, no seu ensaio para engenheiros que estão chegando na área, aponta a mesma ideia como o que diferencia os sistemas distribuídos: eles falham com frequência, e falham **parcialmente**. Algumas partes funcionam e outras não, e ninguém tem a visão completa.

## 2. Uma chamada, oito jeitos de falhar

*Fonte principal: AWS Builders' Library, "Challenges with distributed systems".*

O artigo pega uma única requisição e resposta e a quebra nos oito passos que acontecem no caminho feliz:

1. **Post request**: o cliente coloca a mensagem na rede.
2. **Deliver request**: a rede a leva até o servidor.
3. **Validate request**: o servidor verifica se a mensagem faz sentido.
4. **Update server state**: o servidor faz o trabalho.
5. **Post reply**: o servidor envia a resposta.
6. **Deliver reply**: a rede a traz de volta.
7. **Validate reply**: o cliente verifica a resposta.
8. **Update client state**: o cliente registra o resultado.

Cada passo pode falhar sozinho: a rede perde a requisição, o servidor cai logo depois de recebê-la, o servidor rejeita uma mensagem corrompida ou incompatível, a escrita no banco falha, a placa de rede morre enquanto envia a resposta, a resposta se perde, o cliente não consegue interpretá-la, ou o cliente cai antes de salvá-la. Gabrielson chama isso de "eight failure modes of the apocalypse".

Leve isso para uma transferência ao banco parceiro. Se a falha está nos passos 1 a 3, nenhum dinheiro se moveu. Se está nos passos 5 a 8, **o parceiro já debitou o cliente** e você nunca ficou sabendo. Do seu lado, todos parecem iguais: nenhuma resposta utilizável.

O artigo também avisa que bugs distribuídos costumam ficar latentes: um deles pode ficar meses em produção até que a combinação certa de falhas o dispare. Uma das histórias dele é sobre um servidor de catálogo cujo disco encheu. Ele passou a devolver respostas vazias muito rápido, o load balancer entendeu "rápido" como "saudável" e mandou para ele a maior parte do tráfego, e o site caiu. Uma falha em uma máquina se espalhou pela rede.

Hodges recomenda o clássico problema dos "dois generais" como forma de sentir isso: duas partes em um canal que perde mensagens nunca podem ter certeza, as duas, de que estão de acordo, não importa quantas confirmações troquem.

## 3. Os três desfechos de um timeout

*Fonte principal: AWS Builders' Library, "Challenges with distributed systems".*

O exemplo bancário de Gabrielson resume a aula em poucas linhas. Em uma máquina só, `account.withdraw(amount)` devolve `SUCCESS` ou `INSUFFICIENT_FUNDS`. Através de uma rede, existe um terceiro resultado, `UNKNOWN`, e o código dele literalmente responde a isso com `WHAT_THE_FARG?`. Nas palavras dele, um timeout significa que o resultado "is UNKNOWN. It may or may not have happened" (é desconhecido, pode ou não ter acontecido), e "the client must handle UNKNOWN correctly" (o cliente precisa tratar o UNKNOWN corretamente).

Quando o timeout dispara na sua chamada ao banco parceiro, há três situações possíveis, e você não consegue distingui-las do seu lado:

1. **A requisição nunca chegou.** Nada aconteceu. Tentar de novo é seguro.
2. **A requisição chegou e foi processada, mas a resposta se perdeu ou atrasou.** O efeito aconteceu. Tentar de novo sem proteção faz duas vezes.
3. **A requisição chegou e ainda está sendo processada**, ou está presa em uma fila. O efeito pode acontecer depois que você desistiu.

Então um timeout dá a você um terceiro estado além de sucesso e falha. No capstone deste curso, uma transferência cuja chamada ao banco parceiro dá timeout vai para `UNKNOWN`, nunca para `FAILED`. Um job então pergunta ao parceiro o que aconteceu e a move para `COMPLETED` ou `FAILED` conforme a resposta:

```ts
switch (result.kind) {
  case 'success':  return markCompleted(transfer);
  case 'rejected': return markFailed(transfer, result.reason); // resposta definitiva
  case 'timeout':  return markUnknown(transfer);              // perguntar ao parceiro depois
}
```

Marcar como `FAILED` na hora é o bug clássico: o cliente vê "falhou", tenta de novo e é cobrado duas vezes.

Diferente dos dois generais, pagamentos podem ser corrigidos depois: você pode **perguntar o status ao parceiro mais tarde**, e uma cobrança feita por engano pode ser estornada. Sistemas de pagamento reais são construídos em torno de consultas de status e conciliação, não da esperança de que toda chamada retorne. A regra de hoje: **um timeout significa "não sei", e seu modelo de dados precisa ser capaz de dizer "não sei".**

## 4. Escolher timeouts e fazer retry com segurança

*Fonte principal: AWS Builders' Library, "Timeouts, retries, and backoff with jitter".*

Um artigo companheiro na mesma biblioteca explica como a Amazon escolhe os números de fato. O time primeiro decide qual taxa de **timeouts falsos** aceita (dar timeout em uma chamada que teria dado certo), por exemplo 0,1%, e então define o timeout no percentil de latência correspondente do serviço que chama, nesse caso o p99.9. Se o banco parceiro responde 99,9% das chamadas em até 1,8 segundo, um timeout de 2 segundos desiste por engano de cerca de uma chamada em mil.

O trade-off corta para os dois lados:

- Curto demais, e você transforma sucessos lentos em `UNKNOWN`s, faz retry deles e aumenta a carga justamente quando o parceiro está com dificuldade.
- Longo demais, e clientes e threads ficam esperando uma chamada que nunca vai voltar.

Os pontos do artigo sobre retries se aplicam direto a pagamentos:

- **Retries são "egoístas" ("selfish").** Um cliente que faz retry ocupa mais da capacidade do servidor para melhorar as próprias chances. Se todo cliente fizer isso durante um incidente, os retries viram o incidente.
- **Retries precisam de idempotência.** Fazer retry de uma chamada com efeitos colaterais só é seguro se a API for idempotente. O Amazon EC2 faz isso com um client token enviado em cada requisição, de modo que a mesma requisição enviada duas vezes é executada uma vez. As idempotency keys da Stripe, que você vai estudar no Módulo 2, são a mesma ideia.
- **Faça backoff exponencial e adicione jitter.** Espere mais depois de cada tentativa, limite a espera e adicione uma quantidade aleatória para que milhares de clientes não tentem de novo no mesmo instante.
- **Faça retry em uma camada só.** Se a aplicação, o cliente HTTP e o load balancer fazem até três tentativas cada um, um clique do usuário pode virar 27 chamadas. Escolha um único lugar na stack.

## 5. Detecção de falhas, disponibilidade e SLOs

*Fontes principais: documentação do Apache Cassandra, "Dynamo" (seção de detecção de falhas), e Google, "Site Reliability Engineering", capítulo 4 "Service Level Objectives".*

Como você não consegue ver outra máquina diretamente, você **detecta falhas com timeouts e heartbeats**. Um exemplo real é o Apache Cassandra. Cada nó troca informações de heartbeat por gossip e roda uma variante do phi accrual failure detector, que julga cada par pelo jeito como os heartbeats dele estão chegando. Quando um par parece morto, ele é "condenado" ("convicted") e as leituras deixam de ir para ele, enquanto as escritas destinadas a ele são guardadas como hints para reaplicar depois. A documentação destaca que "UP and DOWN state are local node decisions" (os estados UP e DOWN são decisões locais de cada nó). Dois nós podem discordar sobre um terceiro estar vivo, e nenhum está errado pelo que consegue ver. Um nó lento e um nó morto parecem iguais de fora; um detector de falhas só pode suspeitar.

A história do servidor de catálogo da seção 2 mostra a armadilha oposta: uma verificação que mede só "responde rápido" pode considerar um nó quebrado o mais saudável de todos.

**Disponibilidade** é a fração do tempo em que um serviço funciona corretamente. Os "noves" dão uma noção disso:

| Disponibilidade | Indisponibilidade por ano |
| --- | --- |
| 99% | cerca de 3,7 dias |
| 99,9% | cerca de 8,8 horas |
| 99,99% | cerca de 53 minutos |
| 99,999% | cerca de 5,3 minutos |

O livro de SRE do Google define o vocabulário que você vai usar no Módulo 10:

- Um **service level indicator (SLI)** é uma medida cuidadosamente definida, como a fração de requisições de transferência que dão certo, ou a latência delas.
- Um **service level objective (SLO)** é uma meta para um SLI, como "99,9% das requisições `POST /transfers` respondem com sucesso em até 300 ms ao longo de 30 dias".
- Um **service level agreement (SLA)** é um contrato com consequências por não cumprir o SLO. O teste do livro: se nada acontece quando você não cumpre, é um SLO, não um SLA.

O livro também argumenta que 100% é a meta errada. O exemplo é o Chubby, o serviço de locks do Google, que era tão confiável que outros times passaram a depender dele como se ele nunca pudesse falhar; por isso, quando um trimestre passa sem uma queda real, o time de SRE provoca uma queda controlada para expor cedo essas dependências escondidas. Para uma carteira digital, a lição é que seu banco parceiro vai ficar fora do ar em algum momento, e seu design precisa assumir isso.

## 6. Relógios em que você não pode confiar

*Fontes principais: blog da Cloudflare, "How and why the leap second affected Cloudflare DNS" (John Graham-Cumming), a documentação do chrony e Cockroach Labs, "Clock Management in CockroachDB".*

Todo servidor tem seu próprio relógio, e todo relógio deriva. O daemon de tempo chrony, que a Cockroach Labs recomenda para o seu banco, informa a taxa de deriva como uma frequência em partes por milhão: 1 ppm significa que o relógio ganha um microssegundo a cada segundo. Os servidores corrigem o relógio com servidores de tempo via NTP, e na nuvem você normalmente sincroniza com o serviço do provedor; a AWS, por exemplo, mantém o Amazon Time Sync Service, apoiado em relógios de referência conectados a satélites e atômicos em cada região.

O jeito como a correção é aplicada importa:

- **Slewing**: o modo normal do chrony é corrigir uma diferença aos poucos, fazendo o relógio andar um pouco mais rápido ou mais devagar até alcançar a hora certa.
- **Stepping**: pular o relógio de uma vez para a hora certa. A própria documentação do chrony avisa que "certain software will be seriously affected by such jumps" (certos softwares serão seriamente afetados por esses saltos), e por isso ele faz slewing por padrão.

Os leap seconds são o caso famoso. Em 1º de janeiro de 2017, à meia-noite UTC, um leap second atingiu o software de DNS da Cloudflare, escrito em Go. O código media quanto tempo um servidor DNS upstream levava para responder subtraindo um horário de início de `time.Now()`. Durante o leap second, o relógio voltou, a duração medida saiu negativa, uma média suavizada dessas durações ficou negativa, e esse valor foi passado para o `rand.Int63n()` do Go, que entra em panic com argumento negativo. No pico, cerca de 0,2% das consultas DNS da Cloudflare falharam, por várias horas. Graham-Cumming aponta como causa raiz "the belief that time cannot go backwards" (a crença de que o tempo não pode andar para trás). Hoje, AWS e Google espalham ("smear") os leap seconds ao longo de um período maior em vez de inseri-los de uma vez, um ponto que o artigo da Cockroach Labs também menciona.

Relógios também param. O artigo da Cockroach Labs explica que uma VM na nuvem pausada para live migration volta com o relógio atrasado pelo tempo da pausa, e que o CockroachDB desliga um nó cujo relógio se afasta demais dos outros em vez de arriscar leituras inconsistentes.

Por isso existem dois tipos de relógio na sua linguagem de programação:

- Um **relógio de hora do dia** (`Date.now()` no Node.js) diz a data e a hora. Ele pode pular quando o relógio sofre stepping ou quando um leap second é aplicado. Use-o para timestamps que pessoas leem, nunca para medir quanto tempo algo levou.
- Um **relógio monotônico** (`process.hrtime.bigint()` ou `performance.now()` no Node.js) só anda para a frente. A documentação do Node.js diz que os tempos de `process.hrtime` são "relative to an arbitrary time in the past" (relativos a um momento arbitrário no passado) e "not related to the time of day and therefore not subject to clock drift" (não relacionados à hora do dia e portanto não sujeitos à deriva do relógio). O valor absoluto não significa nada e não pode ser comparado entre máquinas, mas a diferença entre duas leituras na mesma máquina é uma duração confiável. Use-o para timeouts e latência.

```ts
const start = process.hrtime.bigint();
await partnerBank.createTransfer(req);
const elapsedMs = Number(process.hrtime.bigint() - start) / 1e6; // nunca negativo
```

## 7. Ordenar eventos sem relógio de parede

*Fontes principais: Cockroach Labs, "Living without atomic clocks" (Spencer Kimball e Irfan Sharif), a documentação do PostgreSQL, "Sequence Manipulation Functions", e Cybertec, "Gaps in sequences in PostgreSQL" (Laurenz Albe).*

Se os relógios derivam, pulam e param, comparar timestamps de duas máquinas pode colocar eventos na ordem errada. O artigo da Cockroach Labs dá um caso concreto que chama de **causal reverse**. O nó N1 tem um relógio preciso e o relógio do nó N2 está 100 ms atrasado. A transação T1 faz commit em N1 com timestamp 150 ms. Uns 50 ms depois, alguém que viu T1 terminar inicia T2 em N2, e N2 a carimba com 100 ms. Quem ordenar por timestamp agora vê T2 antes de T1, embora T2 tenha começado depois que T1 terminou. O artigo coloca a sincronização típica por NTP em algo entre 100 e 250 ms, e descreve o quanto os bancos de dados se esforçam para evitar isso (o Spanner espera uma incerteza de relógio de 7 ms em todo commit). O código da sua aplicação não deve tentar competir com eles.

Traduzindo isso em regras para a carteira:

- Nunca decida qual de dois eventos em máquinas diferentes veio primeiro comparando seus timestamps de relógio de parede.
- Nunca deixe "last write wins por timestamp" decidir um saldo.
- Sempre meça timeouts com um relógio monotônico.

Então de onde vem a ordem? De **uma autoridade única** pela qual todo escritor precisa passar. Para um ledger, essa autoridade é o banco de dados que guarda a conta.

Um id `bigserial` do Postgres parece uma ordem, mas a documentação do PostgreSQL explica por que ele não é confiável para isso. Um valor obtido com `nextval` "is not reclaimed for re-use if the calling transaction later aborts" (não é reaproveitado se a transação que o pediu for abortada), então sequences têm buracos, e elas "cannot be used to obtain 'gapless' sequences" (não servem para obter sequências sem buracos). O artigo de Albe na Cybertec mostra outras origens de buracos: valores em cache perdidos quando uma sessão termina, e saltos depois de um crash. E como o valor é obtido quando `nextval` roda, e não quando a transação faz commit, uma transação com o id 11 pode fazer commit antes da que tem o id 10. Uma sequence dá ids únicos, não a ordem de commit.

Quando você precisa de uma ordem estrita por conta, faça da própria linha da conta a autoridade. O artigo de Albe constrói um contador sem buracos a partir de uma única linha atualizada dentro da transação, e avisa o custo: ele serializa todas as transações que o usam. Por conta, esse custo é exatamente o que você quer:

```sql
BEGIN;
-- Trava a linha desta conta até o COMMIT; escritores concorrentes na mesma conta esperam.
UPDATE accounts SET last_seq = last_seq + 1
 WHERE id = $1
RETURNING last_seq;                       -- por exemplo, 42

INSERT INTO ledger_entries (account_id, seq, amount_cents, created_at)
VALUES ($1, 42, -5000, now());            -- created_at é para humanos, seq é a ordem
COMMIT;
```

Os lançamentos de uma conta agora têm um `seq` sem buracos e estritamente crescente, decidido por uma única autoridade, e `UNIQUE (account_id, seq)` faz qualquer violação falhar de forma barulhenta. Transferências entre contas diferentes não bloqueiam umas às outras. No capstone, a ordem dos lançamentos de uma conta vem desse tipo de sequência por conta ou da ordem de commit do banco, nunca do `created_at`.

## O que anotar hoje

1. Os 3 desfechos possíveis de um timeout (não chegou, aconteceu mas a resposta se perdeu, ainda em andamento) e o que seu sistema faz em cada um.
2. Como você vai escolher o timeout da chamada ao banco parceiro, e em que ponto da sua stack os retries acontecem.
3. Por que você não pode ordenar eventos pelo relógio de parede, com um exemplo concreto de um fluxo de pagamento, e como seu ledger ordena os lançamentos de uma conta em vez disso.

## Teste-se

Estas perguntas dão bons flashcards (veja o [guia de flashcards](../../FLASHCARDS.pt-BR.md)).

- Cite três dos oito passos de uma requisição e resposta, e o que uma falha em cada um significa para uma transferência.
- Por que um timeout não consegue distinguir um servidor que caiu de um servidor lento?
- Como a Amazon escolhe o valor de um timeout, segundo a Builders' Library?
- Por que retries são "egoístas", e o que torna seguro o retry de um pagamento?
- Qual é a diferença entre um SLO e um SLA?
- Que relógio você usa para medir um timeout, e o que deu errado na Cloudflare quando o outro foi usado?
- Por que o valor de uma sequence do Postgres não é a ordem de commit?

## Referências

- **Fonte principal:** Jacob Gabrielson, AWS Builders' Library, ["Challenges with distributed systems"](https://aws.amazon.com/builders-library/challenges-with-distributed-systems/). Gratuito. Leia inteiro; anote os oito modos de falha e o desfecho UNKNOWN.
- Marc Brooker, AWS Builders' Library, ["Timeouts, retries, and backoff with jitter"](https://aws.amazon.com/builders-library/timeouts-retries-and-backoff-with-jitter/). Gratuito. Como a Amazon escolhe timeouts e torna os retries seguros.
- Google, "Site Reliability Engineering", [capítulo 4, "Service Level Objectives"](https://sre.google/sre-book/service-level-objectives/). Gratuito. SLIs, SLOs, SLAs e a história do Chubby.
- John Graham-Cumming, blog da Cloudflare, ["How and why the leap second affected Cloudflare DNS"](https://blog.cloudflare.com/how-and-why-the-leap-second-affected-cloudflare-dns/), 2017. Gratuito. Uma queda real causada por um relógio que andou para trás.
- Spencer Kimball e Irfan Sharif, blog da Cockroach Labs, ["Living without atomic clocks"](https://www.cockroachlabs.com/blog/living-without-atomic-clocks/). Gratuito. Diferença entre relógios, causal reverse e como um banco de dados lida com isso.
- Documentação do Apache Cassandra, ["Dynamo"](https://cassandra.apache.org/doc/latest/cassandra/architecture/dynamo.html), seção "Failure Detection". Gratuito. Como um banco de dados real decide que um par caiu.
- Blog da Cockroach Labs, ["Clock Management in CockroachDB: Good Timekeeping is Key"](https://www.cockroachlabs.com/blog/clock-management-cockroachdb/) (Alex Entin). Gratuito. Slewing, smearing de leap seconds, pausas de VM e o offset máximo de relógio.
- Documentação do chrony, ["chronyc"](https://chrony-project.org/doc/3.4/chronyc.html), entradas `makestep` e `tracking`. Gratuito. Slewing vs. stepping, e deriva em ppm.
- Documentação do PostgreSQL, ["Sequence Manipulation Functions"](https://www.postgresql.org/docs/current/functions-sequence.html). Gratuito. Leia o quadro de cuidado sobre buracos.
- Cybertec, ["Gaps in sequences in PostgreSQL"](https://www.cybertec-postgresql.com/en/gaps-in-sequences-postgresql/) (Laurenz Albe). Gratuito. Por que sequences têm buracos e como construir um contador sem buracos.
- Jeff Hodges, ["Notes on Distributed Systems for Young Bloods"](https://www.somethingsimilar.com/2013/01/14/notes-on-distributed-systems-for-young-bloods/), 2013. Um ensaio prático e curto; leia se sobrar tempo.
