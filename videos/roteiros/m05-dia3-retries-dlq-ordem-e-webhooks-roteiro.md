# Roteiro · M5 · Dia 3 · Retries, DLQ, ordem e webhooks


## Abertura

Esta é a aula em vídeo do módulo cinco, dia três: retries, dead letter queue, ordem e webhooks.

O consumidor de ontem está correto quando tudo acaba funcionando. Mas consumidores reais encontram eventos que não conseguem processar: um parceiro fora do ar por dez minutos, uma moeda desconhecida, um bug do deploy de ontem. Hoje são três temas. Como fazer retry sem bloquear. Como impedir que eventos fora de ordem façam o estado andar para trás, e o que é event sourcing. E como enviar webhooks em que o receptor pode confiar.


## Retry no lugar

O artigo da Uber Engineering sobre reprocessamento abre com uma frase para decorar: in distributed systems, retries are inevitable. Em sistemas distribuídos, retries são inevitáveis.

O design mais simples faz retry dentro do consumidor: chama o serviço, falhou, espera e tenta de novo, até dar certo. O consumidor nunca commita o offset desse registro.

Resultado: a partição fica bloqueada. Os registros mais novos esperam atrás dele. Um registro ruim segura todos os saudáveis da partição.

E os metadados de retry ficam difíceis: quantas vezes o registro foi tentado, e quando, se ele nunca sai do lugar?

Uma mensagem que falha sempre, não importa quantos retries, é uma mensagem envenenada, poison message. Erros de bug ou de dados ruins não se resolvem sozinhos, ao contrário de instabilidades de rede.

Na carteira, a partição três pode ter um sexto de todas as contas. Um único evento malformado congelaria as notificações de saldo de todas elas.


## Tópicos de retry e DLQ

A resposta da Uber é tirar o registro que falha do fluxo principal.

O consumidor tenta um número fixo de vezes. Se ainda falhar, publica o registro num tópico de retry, commita o offset no tópico principal, e segue em frente. A partição fica livre de novo.

Esse tópico de retry tem seus próprios consumidores e um atraso, por exemplo um minuto. Os atrasos são de melhor esforço: o handler roda pelo menos depois do atraso, talvez mais tarde.

Falhou de novo, vai para o próximo nível, com atraso maior, por exemplo dez minutos. Esses nomes e atrasos são um exemplo do curso, não uma regra do artigo.

Falhou no último nível, vai para a dead letter queue, a D L Q: um tópico onde o registro espera por uma pessoa ou uma ferramenta, com um alerta.

Separe os tipos de erro. Erros transitórios, como um timeout ou um 503 do parceiro, passam pela escada.

Erros que não adianta repetir, como uma validação ou um bug, vão direto para a D L Q, porque repetir só desperdiça capacidade.

E o replay: depois de corrigir, os registros da D L Q são republicados no primeiro tópico de retry e voltam ao processamento. A tarefa dois do projeto pede exatamente esse comando.

> **Pausa:** Pergunta: por que um erro de validação deve ir direto para a D L Q, sem passar pela escada?

Porque ele vai falhar sempre. Repetir só gasta capacidade e atrasa a pessoa que precisa corrigir o dado ou o código.


## Os dois preços

O padrão cobra dois preços.

Primeiro, ordem. Um registro que vai para retry é processado depois de registros mais novos da mesma chave. Se o evento sete de acc um falha e o oito dá certo, a conta vê o oito antes do sete. A próxima parte mostra como tornar isso inofensivo.

Segundo, idempotência. Um registro pode ser tentado em vários níveis, então o consumidor precisa ser idempotente. O seu inbox de terça já cobre.

E o outro lado dos retries é backpressure. A escada de atrasos limita a velocidade com que falhas voltam, e um serviço em dificuldade não é martelado. Num consumidor só, o Kafka tem pause e resume por partição. Se o circuit breaker do banco parceiro está aberto, pause as partições em vez de jogar tudo na escada. Como o Kafka é pull, os registros simplesmente se acumulam no log, onde estão seguros.


## Fora de ordem

Retries, reenvios e replays da D L Q significam que um evento antigo pode chegar depois de um novo. E a regra do projeto é: o estado nunca pode andar para trás.

A ferramenta é uma versão por entidade. O serviço de contas emite account status changed com versão um, dois, três. O consumidor só atualiza a sua cópia se a versão que chegou for maior que a que ele tem. Zero linhas atualizadas: evento velho ou duplicado, pule e commite o offset.

A versão é definida pelo producer, na mesma transação que mudou o estado.

Repare no que não se usa: created at, ou o timestamp do Kafka. O módulo um mostrou que relógios de parede não ordenam eventos entre máquinas.

E cuidado: versões servem para visões de estado mais recente. São erradas para eventos que se somam, como créditos. Um crédito atrasado não está velho, ele ainda precisa ser aplicado uma vez. Para esses, use o inbox, e faça a projeção tolerar qualquer ordem, somando lançamentos em vez de sobrescrever o saldo.

> **Pausa:** Pergunta: por que a regra de versão é errada para eventos de crédito?

Porque um crédito atrasado continua válido. Com a regra de versão, ele seria descartado, e o dinheiro sumiria do saldo. Créditos usam o inbox e somam.


## Event sourcing

Até aqui, eventos eram notificações sobre mudanças guardadas em tabelas. Martin Fowler descreve uma ideia mais forte, o event sourcing: toda mudança de estado é guardada como uma sequência de eventos. Os eventos são a verdade, e o estado atual é calculado a partir deles. O valor está no que o log permite.

Reconstrução completa: jogue fora o estado e reproduza todos os eventos desde o zero.

Consulta temporal: calcule o estado como ele era em qualquer momento passado.

Replay: se um evento passado estava errado, corrija e recalcule as consequências.

Reproduzir tudo é lento, então se guardam snapshots, e só os eventos mais novos são reproduzidos.

A parte difícil é o mundo de fora. O replay não pode enviar mensagens reais de novo, então sistemas externos ficam atrás de gateways que não fazem nada durante o replay. E consultas externas, como uma taxa de câmbio, precisam ser registradas no evento, para o replay usar a taxa daquela época.

Fowler aponta que contabilidade se encaixa naturalmente. O seu ledger, uma lista de lançamentos só de acréscimo de onde os saldos são derivados, já é event sourcing na prática. No projeto, você precisa dos hábitos: eventos imutáveis, versões, e replays sem efeitos colaterais.

> **Pausa:** Pergunta: por que um replay precisa de gateways para sistemas externos?

Para não repetir efeitos reais. Sem eles, reproduzir eventos reenviaria transferências Pix, webhooks e e-mails.


## CQRS

C Q R S quer dizer command query responsibility segregation. A ideia, que Fowler credita a Greg Young, é usar um modelo para mudar dados e outro para lê-los. O modelo de leitura costuma ser construído a partir dos eventos do lado de escrita.

Na carteira, o lado de escrita é o ledger, com transações estritas. É dele que vem a checagem de saldo antes de um débito.

O lado de leitura pode ser o extrato, atualizado por um consumidor dos eventos de conta. Ele é eventualmente consistente: uma transferência pode levar um instante para aparecer.

E Fowler é direto: seja muito cauteloso com C Q R S. A maioria dos sistemas cabe num crud simples. Na entrevista, diga que o extrato é um modelo de leitura no estilo C Q R S, e que a checagem de saldo nunca pode ler dele.


## Webhooks assinados

Webhooks são eventos entregues por HTTP a outra empresa: um lojista sabendo que um pagamento liquidou, ou a sua carteira sabendo que um Pix chegou. O receptor precisa verificar que a requisição é genuína, recente e não duplicada. A especificação aberta Standard Webhooks define um formato comum.

Toda requisição leva três headers. O webhook I D é o identificador único da mensagem, igual em todos os retries. É a idempotency key: se o receptor já processou aquele I D, confirma e não faz nada.

O webhook timestamp é o tempo Unix do envio. Ele permite rejeitar requisições antigas, o que bloqueia ataques de replay. Alguns minutos de tolerância é o comum.

E o webhook signature tem uma ou mais assinaturas, no formato v1 vírgula base64.

O conteúdo assinado é o I D, ponto, o timestamp, ponto, o body. Quem envia calcula o H mac sha 256 dessa string com um segredo compartilhado. O segredo é aleatório, de vinte e quatro a sessenta e quatro bytes, com prefixo W H sec. Assim, o body fica protegido contra alterações.


## Verificando no NestJS

No Nest J S, com o crypto do Node. Primeiro, rejeite timestamps fora de cinco minutos. Depois, calcule o H mac esperado sobre I D, timestamp e body, e compare com cada assinatura recebida. Três detalhes importam.

Assine e verifique os bytes do body cru, não um objeto JSON serializado de novo. Senão as assinaturas não batem.

Compare com uma função de tempo constante, o timing safe equal. Senão um atacante descobre a assinatura byte a byte pelo tempo de resposta.

E aceite várias assinaturas, porque durante a rotação de chaves quem envia assina com o segredo antigo e com o novo.

> **Pausa:** Pergunta: por que comparar a assinatura em tempo constante?

Porque uma comparação comum para no primeiro byte diferente. Medindo o tempo de resposta, o atacante acerta a assinatura byte a byte.


## Entregando webhooks

Do lado de quem envia, que é a tarefa quatro do projeto, a especificação recomenda.

Qualquer 2xx é sucesso. 3xx é falha, e não siga redirecionamentos.

Em 410, gone, desative o endpoint.

Em 429, 502 ou 504, desacelere, e respeite o header retry after.

Faça retry com backoff exponencial e jitter ao longo de vários dias. O exemplo da especificação espalha as tentativas por uns três dias. E use um timeout de quinze a trinta segundos.

O seu enviador de webhooks é só mais um consumidor do log. Lê o evento, envia com webhook I D igual ao event I D, e na falha passa pela mesma escada de retry e D L Q.


## Revisão relâmpago

Hora da revisão relâmpago. São três perguntas, sem olhar.

> **Pausa:** Pergunta um: por que fazer retry no lugar, dentro do consumidor, é perigoso?

Porque bloqueia a partição. Todos os registros saudáveis esperam atrás do que falha, e uma mensagem envenenada congela a partição para sempre.

> **Pausa:** Pergunta dois: como impedir que um evento velho faça o estado andar para trás?

Com uma versão por entidade: o update só acontece se a versão nova for maior que a guardada. Zero linhas, pule e commite.

> **Pausa:** Pergunta três: qual é o conteúdo assinado num webhook do Standard Webhooks?

O I D, o timestamp e o body, separados por pontos, com H mac sha 256.


## O que anotar e próximo passo

Anote com as suas palavras: o desenho da escada de retry e da D L Q, e como funciona o replay. Mensagem envenenada e backpressure. A regra de versão e por que ela não serve para créditos. Event sourcing, snapshots e gateways, e uma linha sobre C Q R S. E os três headers dos webhooks assinados.

Depois, prepare o projeto com os scripts de caos do lab: matar o consumidor antes do commit, publicar uma mensagem envenenada, e publicar eventos fora de ordem. Para cada um, escreva o resultado esperado. Até a próxima aula.
