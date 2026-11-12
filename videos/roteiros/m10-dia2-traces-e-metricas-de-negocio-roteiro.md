# Roteiro · M10 · Dia 2 · Traces e métricas de negócio


## Abertura

Esta é a aula em vídeo do módulo dez, dia dois: traces, propagação de contexto e métricas de negócio.

Uma transferência passa por muitos processos. A API grava a transferência e o outbox no Postgres. Um relay publica no Kafka. Um worker consome, chama o banco parceiro, e grava os postings. Quando o cliente diz minha transferência levou quarenta segundos e falhou, você precisa seguir aquela requisição por todos os saltos. É isso que traces fazem, e a parte difícil é o Kafka. E traces explicam uma requisição. Métricas falam de todas. Uma carteira pode devolver 201 em tudo e ainda estar perdendo dinheiro. Por isso, métricas do negócio.


## Traces e spans

No OpenTelemetry, um trace é o caminho de uma requisição. Ele é feito de spans.

Um span é uma unidade de trabalho: um handler HTTP, uma query, uma chamada ao parceiro, o processamento de uma mensagem. Cada um tem nome, início, fim, o I D do pai, attributes, events e status. O primeiro, sem pai, é o root span. Os spans de uma requisição formam uma árvore, que o Jaeger desenha como cascata.

O span context é imutável, com quatro partes: o trace I D, compartilhado por todos os spans, o span I D, as flags, como se é amostrado, e o state. É a parte que viaja entre serviços. O resto fica onde o span foi criado.

Attributes descrevem a operação, como o nome do provedor. Adicione na criação, porque os samplers só veem o que existe nesse momento. Events são logs estruturados num ponto no tempo: banco parceiro devolveu 503, fazendo retry. A regra: se o timestamp importa, event. Se não, attribute.

Use as semantic conventions, nomes padronizados como o método HTTP. E o seu namespace para domínio, como wallet transfer I D.

O status tem três valores: unset, o padrão, error, e ok, quase sempre desnecessário. Uma transferência recusada por saldo insuficiente: o sistema funcionou, e o resultado foi recusa. Ponha num attribute, e reserve error para falhas de verdade.


## Span kinds e links

Todo span tem um kind, que diz como ele se relaciona com outros processos.

Server: chamada síncrona recebida, como o handler de transferência.

Client: chamada síncrona enviada, como o HTTP ao parceiro ou uma query.

Internal: trabalho dentro do processo, como calcular tarifas. É o padrão se você não definir.

Producer: cria um job para depois, como publicar transfer requested no Kafka.

Consumer: processa esse job. E ele pode começar muito depois de o producer terminar, minutos durante um incidente.

E span links ligam um span a outros, sem ser pai e filho. Importa em mensageria: um span tem exatamente um pai. Se o worker processa um lote de cinquenta mensagens num span, ele não pode ter cinquenta pais, mas pode ter cinquenta links.


## Propagação

Um trace entre dois serviços só funciona se o segundo souber a qual trace pertence. Propagação é levar o contexto. O padrão é o W 3 C trace context, com o header traceparent: versão, o trace I D de trinta e dois caracteres hexadecimais, o I D do span que enviou, e as flags, zero um, amostrado. O receptor cria o seu span com o mesmo trace I D, e com o span de quem enviou como pai.

Quem envia injeta o contexto num carrier, e quem recebe extrai. Em HTTP, o carrier são os headers, e a auto-instrumentação faz isso por você. Por isso o lab de segunda deu um trace sem código.

Os SDKs também põem o trace I D e o span I D nos logs. Esse é o correlation I D que o projeto pede: use o próprio trace I D, e logs e traces compartilham uma chave.

E cuidado. Contexto vindo de fontes não confiáveis pode distorcer seus traces. Contexto enviado para fora pode expor detalhes internos. E o baggage, que carrega pares arbitrários entre serviços, nunca leva credenciais ou dados pessoais. Nada de CPF ou número de conta.


## Pelo outbox e o Kafka

No Kafka, o carrier são os headers da mensagem. Mas o seu projeto tem um salto a mais: o outbox.

Dentro da mesma transação que cria a transferência, a API injeta o contexto ativo num objeto, e grava numa coluna trace headers do outbox.

A linha do outbox guarda o traceparent junto do evento.

O relay copia esses headers para a mensagem do Kafka, sem alterar nada.

O worker converte os headers de buffer para string, extrai o contexto, e inicia um span consumer, marcando error se o processamento falhar.

Por que na API? Se o relay injetar o próprio contexto, o trace começa no relay, e você perde a ligação com a requisição HTTP.

As convenções de mensageria dizem: o producer anexa o contexto de criação a cada mensagem.

E o span do consumer faz link para ele. Usar como pai só é permitido no caso de mensagem única, e você documenta a escolha. De qualquer jeito, o Jaeger mostra a API e o worker como uma história só. Anote no documento qual opção escolheu e por quê.

> **Pausa:** Pergunta: por que guardar o traceparent numa coluna do outbox?

Porque o relay publica depois, em outro processo. Sem a coluna, o contexto da requisição HTTP se perde, e o trace começaria no relay.


## O que o Prometheus manda medir

A documentação do Prometheus dá a resposta curta: instrumente tudo. E separa três tipos de serviço. O seu projeto tem os três.

Online-serving, como a API: queries, erros, latência, e requisições em andamento. Conte a requisição quando termina, para bater com erros e latência.

Offline processing, como o worker e o relay: itens chegando, em andamento, e o último momento de processamento.

Batch job, como a conciliação noturna: a última vez que deu certo, e a duração de cada etapa.

Para pipelines, um heartbeat: um item fictício com timestamp que atravessa tudo a cada minuto. Ele diz se o pipeline travou mesmo quando nenhum cliente está transferindo. E para falhas: conte cada falha e o total de tentativas, para calcular a taxa. É exatamente o formato que o alerta de S L O precisa.


## Métricas de negócio

Em fintech, as métricas que pegam os incidentes caros são sobre o negócio. São sintomas: descrevem o que o cliente e a empresa sentem. O projeto pede três.

Taxa de aprovação por provedor. Conte toda autorização com dois labels: provedor e resultado, aprovado, recusado ou erro. A taxa é uma razão entre taxas. Se cai em um provedor e o outro fica estável, é o provedor. Se cai nos dois, é você.

Pagamentos pendentes antigos. Pode subir e descer, então é gauge: se o valor pode descer, é gauge. E exporte o timestamp do pendente mais antigo, não a idade. Assim, time menos a métrica dá a idade, e o alerta dispara acima de novecentos segundos, quinze minutos. Um segundo gauge com a quantidade diz se é um travado ou mil.

Divergências de conciliação: um gauge por tipo, da última execução, mais o timestamp do último sucesso. Divergência acima de zero precisa de humano. E se o último sucesso tem mais de um dia, o próprio job quebrou, e zero divergências não prova nada. No código, inicialize com zero as séries conhecidas, como o erro de cada provedor. Senão a série não existe até o primeiro erro, e o alerta não devolve nada.

> **Pausa:** Pergunta: por que exportar o timestamp do pendente mais antigo, e não a idade dele?

Porque o timestamp não precisa de atualização contínua. A idade sai na consulta, como time menos a métrica, sempre correta.


## Cardinalidade

Labels tornam uma métrica útil: um único contador de respostas com o label code, em vez de uma métrica por status. Mas cada combinação de valores é uma série temporal separada, guardada e consultada sozinha. A regra: cardinalidade abaixo de dez, poucas métricas acima disso, e acima de cem, procure alternativa. Na dúvida, comece sem labels.

Na carteira, são aceitáveis: provedor, com dois ou três valores, resultado, com três, e rota, com algumas dezenas.

E nunca: customer I D, transfer I D, idempotency key, ou o valor. A quantidade cresce com o negócio, e as séries explodem.

Para achar uma transferência específica, use traces e logs, indexados pelo trace I D. Métricas respondem quantos e quão rápido. Traces e logs respondem qual.

> **Pausa:** Pergunta: por que não pôr o customer I D como label numa métrica?

Porque cada cliente vira uma série temporal separada, e o número cresce com o negócio. Para achar um cliente específico, use traces e logs.


## Revisão relâmpago

Hora da revisão relâmpago. São três perguntas, sem olhar.

> **Pausa:** Pergunta um: o que viaja entre serviços para manter um trace?

O span context: trace I D, span I D, flags e state, no header traceparent.

> **Pausa:** Pergunta dois: uma transferência recusada por saldo insuficiente deve ter status error?

Não. O sistema funcionou. O resultado de negócio vai num attribute, e error fica para falhas reais.

> **Pausa:** Pergunta três: por que inicializar com zero as séries conhecidas?

Porque, sem isso, a série de erro de um provedor só existe depois do primeiro erro, e razões e alertas sobre ela não devolvem nada.


## O que anotar e próximo passo

Anote com as suas palavras: o trace de uma transferência, com cada span e kind, e onde o contexto atravessa o outbox e o Kafka. A sua decisão de propagação no worker. E as suas métricas de negócio, com nome, tipo, labels e a consulta de alerta.

Depois, no lab, suba o Prometheus. Até a próxima aula.
