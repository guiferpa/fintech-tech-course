# Módulo 1, segunda-feira: falhas, timeouts e tempo

[Módulo 1](../../modules/01-distributed-systems-fundamentals.pt-BR.md) · [Read in English](day-1.md)

**Tempo de leitura:** cerca de 45 minutos. Use o resto do bloco de 2 horas nas referências do final, começando pelas seções marcadas como fonte principal.

Este é um texto original escrito para este curso. Ele se baseia nas referências listadas no final, e cada seção indica a fonte que segue. Quando uma ideia vem de um autor específico, o texto diz isso.

## Por que isso importa para uma fintech

Um sistema de pagamentos é um sistema distribuído desde a primeira linha de código. Sua API conversa com um banco de dados, o banco replica para outra máquina, um worker chama um banco parceiro, e o banco parceiro chama a bandeira do cartão ou o Pix. Cada seta desse desenho é uma chamada de rede. E toda chamada de rede pode falhar de jeitos que uma chamada de função em uma única máquina não falha.

Os bugs mais caros em pagamentos vêm de uma confusão: tratar "não recebi resposta" como "não aconteceu". Esta aula explica por que as duas coisas são diferentes e o que fazer a respeito.

## 1. O que torna um sistema distribuído

*Fonte principal: notas de aula de Kleppmann, seção 1.1.*

Um sistema distribuído é um conjunto de computadores (nós) que cooperam por uma rede para fazer um trabalho. Os nós não compartilham memória. A única forma de um nó saber algo sobre outro é receber uma mensagem dele.

Esse único fato cria os três problemas aos quais este módulo sempre volta:

- **Mensagens podem se perder ou atrasar**, e quem enviou não consegue saber qual dos dois aconteceu.
- **Nós podem cair ou pausar**, e os outros não conseguem distinguir um nó caído de um nó lento.
- **Cada nó tem seu próprio relógio**, e os relógios discordam.

Um nome útil para os dois primeiros é **falha parcial**. Em uma máquina, um programa ou funciona ou a máquina inteira está fora do ar. Em um sistema distribuído, algumas partes funcionam enquanto outras não, e ninguém tem a visão completa. As falhas também são não determinísticas: a mesma requisição pode dar certo nove vezes e travar na décima.

## 2. O problema dos dois generais

*Fonte principal: notas de aula de Kleppmann, seção 2.1.*

Dois exércitos acampam em lados opostos de uma cidade. Se os dois atacarem ao mesmo tempo, vencem; se só um atacar, perde. Os generais só se comunicam enviando mensageiros pela cidade, e um mensageiro pode ser capturado.

O general 1 envia "atacar ao amanhecer". Se nenhuma resposta voltar, o general 1 não tem como saber se a mensagem se perdeu ou se a resposta se perdeu. Então o general 2 precisa responder. Mas aí o general 2 não sabe se a resposta chegou, então o general 1 precisa confirmar a resposta, e assim por diante. **Nenhum número finito de mensagens deixa os dois lados com certeza.** A certeza exigiria conhecimento comum, e mensagens por um canal não confiável não conseguem criá-lo.

As notas de Kleppmann aplicam isso diretamente a pagamentos. Uma loja online pede a um serviço de pagamento que cobre um cartão, e a conexão cai antes de a resposta chegar. A loja não sabe se o cartão foi cobrado. A diferença em relação aos generais é que pagamentos podem ser corrigidos depois: a loja pode **consultar o status no serviço de pagamento mais tarde**, e uma cobrança feita por engano pode ser estornada. É por isso que sistemas de pagamento reais são projetados em torno de consultas de status e conciliação, e não da esperança de que toda chamada retorne.

## 3. Os três desfechos de um timeout

Quando você chama um serviço remoto e o timeout estoura, há três situações possíveis, e do seu lado você não consegue distingui-las:

1. **A requisição nunca chegou.** Nada aconteceu. Fazer retry é seguro.
2. **A requisição chegou e foi processada, mas a resposta se perdeu ou atrasou.** O efeito aconteceu. Um retry sem proteção faz tudo duas vezes.
3. **A requisição chegou e ainda está sendo processada**, ou está presa em uma fila. O efeito pode acontecer depois que você desistir.

Então um timeout dá a você um terceiro estado além de sucesso e falha: **desconhecido**. No TCM deste curso, uma transferência cuja chamada ao banco parceiro dá timeout vai para `UNKNOWN`, nunca para `FAILED`. Um job então pergunta ao parceiro o que aconteceu e a move para `COMPLETED` ou `FAILED` de acordo com a resposta. Marcar como `FAILED` na hora é o bug clássico: o cliente vê "falhou", tenta de novo e é cobrado duas vezes.

O que torna um retry seguro é a idempotência, tema do Módulo 2. Por enquanto, a regra é: **um timeout significa "não sei", e seu modelo de dados precisa ser capaz de dizer "não sei".**

## 4. Modelos de sistema: o que assumimos sobre a rede, os nós e o tempo

*Fonte principal: notas de aula de Kleppmann, seção 2.3.*

Para raciocinar sobre qualquer algoritmo, primeiro você declara o que pode dar errado. As notas de Kleppmann descrevem um modelo de sistema em três partes.

**Rede.**

- *Links confiáveis*: uma mensagem chega se e somente se foi enviada (ela pode chegar fora de ordem).
- *Links com perda justa (fair-loss)*: mensagens podem ser perdidas, duplicadas ou reordenadas, mas se você continuar tentando, alguma acaba passando.
- *Links arbitrários*: um atacante pode ler, alterar, descartar, forjar ou repetir mensagens.

Você consegue construir um link confiável a partir de um link com perda justa usando **retries mais deduplicação**, e o TLS transforma um link arbitrário em algo próximo de um link com perda justa. Nada, porém, impede um atacante ou um cabo rompido de bloquear o tráfego por muito tempo. Um período longo de perda ou atraso entre grupos de nós é uma **partição de rede**.

**Nós.**

- *Crash-stop*: um nó que cai nunca mais volta.
- *Crash-recovery*: um nó pode cair e reiniciar; ele perde o que estava em memória e mantém o que estava em disco.
- *Bizantino*: um nó pode fazer qualquer coisa, inclusive mentir.

Seus serviços rodam no modelo crash-recovery: um container morre e reinicia, e tudo o que não foi commitado no Postgres se perde. Falhas bizantinas importam entre organizações que não confiam umas nas outras. Esse é um dos motivos pelos quais mensagens de pagamento entre bancos são assinadas.

**Tempo.**

- *Síncrono*: o atraso das mensagens e a velocidade de processamento têm limites superiores conhecidos.
- *Parcialmente síncrono*: o sistema se comporta de forma síncrona na maior parte do tempo, mas pode deixar de fazê-lo por períodos desconhecidos.
- *Assíncrono*: nenhum limite.

Sistemas reais são, no máximo, parcialmente síncronos. Mensagens esperam em filas, redes se reconfiguram, o sistema operacional tira seu processo da CPU, e o garbage collector pode pausar um processo Node.js ou JVM por centenas de milissegundos. Kleppmann observa que **um nó pausado parece exatamente um nó caído** para todos os outros. Quando ele acorda, pode agir com base em informações que já não são verdadeiras. O Módulo 3 volta a isso com fencing tokens.

## 5. Detecção de falhas, disponibilidade e SLOs

*Fonte principal: notas de aula de Kleppmann, seção 2.4.*

Como você não consegue enxergar outro nó diretamente, você **detecta falhas com timeouts**: se um nó não responde dentro de certo tempo, você suspeita que ele caiu. Em um sistema parcialmente síncrono, esse detector às vezes vai errar e marcar um nó lento como morto. Kleppmann chama o melhor que se pode fazer de *eventually perfect failure detector*: ele pode errar, mas em algum momento passa a suspeitar exatamente dos nós que caíram.

Escolher o timeout é um trade-off que você vai encontrar de novo no Módulo 9:

- Curto demais, e você declara mortos nós saudáveis porém lentos, dispara failovers desnecessários e adiciona carga no pior momento.
- Longo demais, e os clientes esperam enquanto um nó morto continua recebendo tráfego.

**Disponibilidade** é a fração do tempo em que um serviço funciona corretamente. Os "noves" dão uma noção disso:

| Disponibilidade | Tempo fora do ar por ano |
| --- | --- |
| 99% | cerca de 3,7 dias |
| 99,9% | cerca de 8,8 horas |
| 99,99% | cerca de 53 minutos |
| 99,999% | cerca de 5,3 minutos |

Um **service level objective (SLO)** é uma meta mensurável, como "99,9% das requisições de transferência respondem em até 300 ms". Um **service level agreement (SLA)** é um contrato que inclui um SLO e uma penalidade caso ele não seja cumprido. Uma **falha de componente (fault)** é um componente dando errado; uma **falha do sistema (failure)** é o sistema inteiro parando. Tolerância a falhas significa sobreviver a um número limitado de falhas de componente, principalmente eliminando **pontos únicos de falha**. O Módulo 10 transforma SLOs em alertas.

## 6. Relógios em que você não pode confiar

*Fonte principal: notas de aula de Kleppmann, seções 3.1 e 3.2.*

Todo servidor tem um relógio de quartzo, e o quartzo deriva com a temperatura e a idade, normalmente até cerca de 50 partes por milhão. Isso dá uns 4 segundos por dia se nada corrigir. Servidores corrigem seus relógios com **NTP**, que consulta servidores de horário e estima o desvio.

O NTP estima o desvio a partir de quatro timestamps: o cliente envia em t1, o servidor recebe em t2 e responde em t3, e o cliente recebe em t4. O atraso de ida e volta é (t4 − t1) − (t3 − t2), e o desvio estimado é ((t2 − t1) + (t3 − t4)) / 2. A estimativa assume que o atraso de rede é igual nos dois sentidos, o que muitas vezes é falso. Por isso, mesmo um servidor bem sincronizado costuma estar errado em alguns milissegundos, e em muito mais quando a rede está congestionada.

Quando o NTP corrige um relógio, ele o ajusta gradualmente (**slew**, rodando um pouco mais rápido ou mais devagar até alcançar) para desvios pequenos, ou dá um salto (**step**, para frente ou para trás) para desvios maiores. Desvios muito grandes exigem um operador. Leap seconds pioram tudo: alguns dias têm 86.401 segundos, e em 2012 um leap second causou um bug no kernel Linux que derrubou muitos sites grandes.

É por isso que existem dois tipos de relógio na sua linguagem de programação:

- Um **relógio de hora do dia** (`Date.now()` no Node.js, `CLOCK_REALTIME` no Linux) informa a data e a hora. Ele pode pular para trás ou para frente quando o NTP dá um step. Use-o para timestamps que pessoas leem, nunca para medir quanto tempo algo levou.
- Um **relógio monotônico** (`performance.now()` ou `process.hrtime.bigint()` no Node.js, `CLOCK_MONOTONIC` no Linux) só anda para frente. Seu valor absoluto não significa nada e não pode ser comparado entre máquinas. Mas a diferença entre duas leituras na mesma máquina é uma duração confiável. Use-o para timeouts e latência.

Para uma fintech, as regras práticas são:

- Nunca decida qual de dois eventos em máquinas diferentes veio primeiro comparando seus timestamps de relógio de parede.
- Nunca deixe "a última escrita vence pelo timestamp" decidir um saldo.
- Sempre meça timeouts com um relógio monotônico.

## 7. Happens-before e Lamport clocks

*Fonte principal: notas de aula de Kleppmann, seções 3.3 e 4.1. As ideias vêm do artigo de Leslie Lamport de 1978, "Time, Clocks, and the Ordering of Events in a Distributed System".*

Se relógios físicos não conseguem ordenar eventos, o que consegue? A resposta de Lamport é a relação **happens-before**, escrita a → b. Ela vale quando:

1. a e b acontecem no mesmo nó e a acontece primeiro, ou
2. a é o envio de uma mensagem e b é o recebimento dessa mesma mensagem, ou
3. existe algum c com a → c e c → b (transitividade).

Se nem a → b nem b → a, os eventos são **concorrentes** (a ∥ b). Concorrente não quer dizer "no mesmo instante". Quer dizer que nenhuma cadeia de mensagens os conecta, então nenhum poderia ter influenciado o outro. Happens-before é exatamente a noção de **causalidade**: a só pode ter causado b se a → b.

Um **Lamport clock** dá a cada evento um número que respeita a causalidade:

- Cada nó mantém um contador `t`, começando em 0.
- Antes de cada evento local ou envio de mensagem, o nó faz `t = t + 1`, e a mensagem carrega o `t` atual.
- Ao receber uma mensagem que carrega `t'`, o nó define `t = max(t, t') + 1`.

A garantia dele vale em um só sentido: **se a → b, então L(a) < L(b)**. O inverso não é verdade: L(a) < L(b) não significa que a aconteceu antes de b, porque eventos concorrentes podem receber qualquer ordem. Para obter uma ordem total com a qual todos os nós concordem, desempate pelo ID do nó: compare pares (timestamp, ID do nó). **Vector clocks**, também na seção 4.1 das notas, mantêm um contador por nó e conseguem dizer quando dois eventos são concorrentes, ao custo de mais espaço.

Você não vai implementar Lamport clocks no TCM. O que você vai usar é a ideia por trás deles: **a ordem vem da causalidade e de uma autoridade única, não de relógios de parede.** Em um ledger, a ordem dos lançamentos de uma conta vem da ordem de commit do banco de dados ou de um número de sequência por conta, nunca de `created_at`.

## O que anotar hoje

1. Os 3 desfechos possíveis de um timeout (não chegou, aconteceu mas a resposta se perdeu, ainda em andamento) e o que seu sistema faz em cada um.
2. Por que você não pode ordenar eventos pelo relógio de parede, com um exemplo concreto de um fluxo de pagamento.
3. O que um Lamport clock garante e o que ele não garante.

## Teste-se

Estas perguntas dão bons flashcards (veja o [guia de flashcards](../../FLASHCARDS.pt-BR.md)).

- Qual é a diferença entre uma falha de componente (fault) e uma falha do sistema (failure)?
- Por que um timeout não consegue distinguir um nó caído de um nó lento?
- O que um nó crash-recovery perde quando reinicia, e o que ele mantém?
- Qual relógio você usa para medir um timeout, e por quê?
- Se L(a) < L(b), a acontece antes de b?
- Por que o problema dos dois generais não torna os pagamentos online impossíveis?

## Referências

- **Fonte principal:** Martin Kleppmann, [notas de aula "Distributed Systems"](https://www.cl.cam.ac.uk/teaching/2122/ConcDisSys/dist-sys-notes.pdf), Universidade de Cambridge, 2021/22, seções 1.1, 2.1 a 2.4, 3 e 4.1. Gratuito, publicado sob licença Creative Commons BY-SA. As videoaulas correspondentes são gratuitas e estão linkadas na [página de materiais do curso](https://www.cl.cam.ac.uk/teaching/2122/ConcDisSys/materials.html).
- Leslie Lamport, ["Time, Clocks, and the Ordering of Events in a Distributed System"](https://lamport.azurewebsites.net/pubs/time-clocks.pdf), Communications of the ACM, 1978. O artigo original por trás da seção 7.
- Jeff Hodges, ["Notes on Distributed Systems for Young Bloods"](https://www.somethingsimilar.com/2013/01/14/notes-on-distributed-systems-for-young-bloods/), 2013. Um ensaio curto e prático; leia se sobrar tempo.
