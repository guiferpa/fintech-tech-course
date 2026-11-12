# Roteiro · M9 · Dia 1 · Timeouts, retries, breakers e bulkheads


## Abertura

Esta é a aula em vídeo do módulo nove, dia um: timeouts, retries, circuit breakers e bulkheads.

Sua carteira depende de parceiros que você não controla: banco parceiro, processador de cartão, provedor de Pix, fornecedor de K Y C. Um dia o provedor principal começa a responder em trinta segundos em vez de trezentos milissegundos. Nada está fora do ar. Os health checks estão verdes. E mesmo assim, em poucos minutos, a API inteira para, inclusive a tela de saldo, que nunca chama esse provedor. Esse é o teste de domínio do módulo. As quatro ferramentas de hoje existem para que uma dependência lenta degrade uma funcionalidade, não a empresa inteira.


## Falha em cascata

Toda requisição que espera uma chamada remota segura alguma coisa: um socket, uma vaga no pool de conexões, uma conexão de banco se a transação ainda está aberta. O serviço lento ocupa os recursos, o pool se esgota, e logo as requisições para outros serviços também falham. É a falha em cascata. A lei de Little mostra a velocidade: requisições em andamento são a taxa de chegada vezes o tempo de cada uma. Com cinquenta por segundo:

Trezentos milissegundos: quinze em andamento.

Três segundos: cento e cinquenta.

Trinta segundos: mil e quinhentas. Se cada transferência segura uma de vinte conexões do Postgres enquanto chama o parceiro, o pool se esgota quase na hora. E o saldo, que só precisa de uma query de dois milissegundos, espera por uma conexão. O app inteiro trava.

Duas regras de design saem daí. Nunca segure conexão ou transação aberta durante uma chamada remota: grave a transferência como pendente, faça commit, chame o parceiro, e registre o resultado numa transação nova. E toda espera precisa ter fim, e todo recurso compartilhado precisa de fronteira. Timeouts dão o fim. Bulkheads dão a fronteira.

> **Pausa:** Pergunta: com cinquenta requisições por segundo e latência de três segundos, quantas ficam em andamento?

Cento e cinquenta. Cinquenta vezes três.


## Timeouts

A primeira regra de Marc Brooker, da Amazon: timeout em toda chamada remota.

No node J S, o fetch não tem timeout por padrão. Passe um abort signal com timeout.

A parte difícil é o número. Alto demais segura recursos à toa. Baixo demais falha requisições que dariam certo, e dispara retries. O método: decida que taxa de timeouts falsos aceita, por exemplo zero vírgula um por cento, e pegue o percentil correspondente da latência do serviço, o P 99 ponto 9. Comece por aí e ajuste.

Se o P 99 ponto 9 estiver muito perto do P 50, dê margem, porque uma pequena variação causaria muitos timeouts de uma vez. E saiba o que o timeout inclui. Brooker conta de um timeout de vinte milissegundos que falhava depois de cada deploy, porque também cobria o handshake T L S das conexões novas.

Timeouts são aninhados. Se o app desiste em dez segundos, o orçamento da API é menor, e cada chamada dentro dela menor ainda. Senão um worker continua tentando depois que o cliente foi embora.

E timeout significa não sei. A transferência vai para desconhecido, e a conciliação pergunta ao parceiro depois. Nunca direto para falha.


## Retries

Um retry esconde falhas transitórias. Mas retries são egoístas: pedem ao servidor que gaste mais capacidade com o seu pedido. Quando o servidor falha porque está sobrecarregado, retries acrescentam carga justamente quando ele menos aguenta.

E a amplificação cresce com a profundidade. Cinco camadas, cada uma com três retries, multiplicam a carga no banco lá embaixo por três elevado a cinco: duzentas e quarenta e três vezes. Na carteira: app, gateway, transferências, adaptador de pagamentos, banco parceiro. Um soluço curto vira uma enxurrada.

Regras práticas. Retry em uma camada só, normalmente a dona da operação e da idempotency key, como o adaptador de pagamentos.

Retry só do que pode dar certo depois. Um 5 X X ou erro de conexão, sim. Um 4 X X, como saldo insuficiente, vai falhar igual.

Retry só de operações idempotentes. Um timeout não prova que o efeito não aconteceu. O adaptador envia o I D da transferência como idempotency key, então o retry não move dinheiro duas vezes.

E limite com um orçamento: retries só enquanto forem menos de dez por cento das requisições recentes. É um token bucket local, que o A W S S D K adotou em 2016. No pior caso, a carga fica em uma vírgula uma vez o normal, não duzentas e quarenta e três. É o item um do projeto de quinta.

> **Pausa:** Pergunta: com retry budget de dez por cento, qual a carga máxima quando toda chamada falha?

Uma vírgula uma vez o normal: as requisições originais mais no máximo dez por cento de retries.


## Backoff e jitter

Retry imediato bate de novo num servidor que ainda não se recuperou. O backoff exponencial espera mais a cada tentativa: cem, duzentos, quatrocentos milissegundos. Com um teto, e com número máximo de tentativas, senão os clientes tentam para sempre no ritmo do teto.

Mas se mil requisições falharam no mesmo instante, porque o parceiro reiniciou, todas esperam os mesmos intervalos e voltam juntas, em ondas. O jitter acrescenta aleatoriedade: aqui, um ponto qualquer entre zero e o valor exponencial.

E jitter vale além de retries. Um job de conciliação que todo worker inicia à meia-noite, ou um cache que todo pod atualiza na virada do minuto, cria picos. A Amazon prefere um deslocamento fixo por host, derivado do nome dele, porque um padrão fixo é mais fácil de depurar.


## Circuit breaker

Timeouts limitam a espera, mas com um provedor morto toda chamada ainda espera o timeout inteiro, e termina em erro. Com dois segundos e cinquenta por segundo, ainda são cem requisições presas. Um circuit breaker para de fazer chamadas que quase certamente vão falhar. Ele tem três estados.

Fechado: as chamadas vão ao fornecedor, e as falhas são contadas.

Quando as falhas passam do limite, ele desarma e fica aberto. As chamadas falham na hora, sem chegar ao fornecedor.

Depois do reset timeout, fica meio-aberto, e deixa passar uma chamada de teste. Se der certo, fecha. Se falhar, abre de novo.

Na prática, ele desarma por taxa de erro, por exemplo cinquenta por cento das chamadas recentes.

Mas nem todo erro é falha. Saldo insuficiente ou conta inválida é um resultado de negócio normal, e não pode desarmar o breaker.

Decida o fallback. Na carteira: aceite a transferência como pendente, ponha numa fila, e diga ao cliente que está em processamento.

E torne visível: log de toda mudança de estado, o estado no monitoramento, e operadores podendo abrir ou fechar manualmente. No lab, você usa a biblioteca opossum. Brooker alerta que breakers criam um comportamento modal difícil de testar, e por isso a Amazon muitas vezes prefere o retry budget. Os dois não se excluem.

> **Pausa:** Pergunta: o banco parceiro responde saldo insuficiente em várias chamadas seguidas. O breaker deve abrir?

Não. É um resultado de negócio, não uma falha do fornecedor. Só erros de infraestrutura, como timeouts e 5 X X, contam.


## Bulkheads

O nome vem dos navios: se o casco é danificado, só a seção atingida se enche de água, e o navio não afunda. Um bulkhead divide os recursos em pools, para que uma falha num pool não esgote os outros.

O tipo principal particiona os recursos do consumidor: um pool de conexões separado para cada dependência. Se uma trava, só o pool dela enche.

Na carteira: um agente HTTP com limite próprio de conexões para cada parceiro. Banco parceiro trinta, fornecedor de K Y C dez. Um K Y C lento não bloqueia transferências. E o bulkhead rejeita quando está cheio, não enfileira.

Um pool do Postgres separado, ou uma réplica de leitura, para os relatórios do back-office. Uma exportação pesada não tira conexões do caminho de pagamento.

E filas de workers separadas por parceiro, para o acúmulo numa não atrasar as outras.

O preço: um bulkhead reserva capacidade que fica ociosa nos dias bons. Escolha as partições pelos requisitos de negócio, monitore cada uma separadamente, e combine com retries, breakers e throttling.


## O provedor de 30 segundos

Agora o teste de domínio, camada por camada. O banco parceiro vai de trezentos milissegundos para trinta segundos.

Sem proteção: mil e quinhentas requisições em andamento, pools esgotados, todos os endpoints lentos, e erros em tudo.

Com timeouts de dois segundos: cada transferência falha em dois segundos e vai para desconhecido. Cerca de cem em andamento. Os outros endpoints se recuperam em grande parte, mas cada transferência ainda custa dois segundos e um erro.

Acrescente retries sem orçamento, e cada falha é tentada mais três vezes. A carga se multiplica. Piora, não melhora.

Com backoff, jitter e retry budget, os retries se espalham e ficam limitados a cerca de dez por cento a mais. Soluços somem, e uma queda real não é amplificada.

Com o circuit breaker, depois de cinquenta por cento de erro, as chamadas falham rápido para o fallback de pendente com fila. A latência cai para milissegundos, e os testes meio-abertos detectam a recuperação.

E com o bulkhead, mesmo antes do breaker abrir, o banco parceiro usa no máximo trinta vagas. Saldo, extrato e K Y C mantêm os seus recursos. No lab de hoje, você mede a primeira linha: P 99, taxa de erro e conexões abertas, com k 6 e Toxiproxy.

> **Pausa:** Pergunta: por que acrescentar retries sem orçamento piora a situação?

Porque o parceiro já está sobrecarregado, e cada falha vira mais três chamadas. A carga se multiplica justamente quando ele precisa de folga.


## Revisão relâmpago

Hora da revisão relâmpago. São três perguntas, sem olhar.

> **Pausa:** Pergunta um: como escolher o valor de um timeout?

Decida a taxa aceitável de timeouts falsos, pegue o percentil correspondente da latência, como o P 99 ponto 9, e acrescente margem.

> **Pausa:** Pergunta dois: quais os três estados de um circuit breaker, e o que move entre eles?

Fechado, que conta falhas e abre ao passar do limite. Aberto, que falha na hora e, depois do reset timeout, fica meio-aberto. E meio-aberto, que deixa uma chamada de teste: sucesso fecha, falha abre de novo.

> **Pausa:** Pergunta três: o que um bulkhead isola na carteira?

Os recursos de cada dependência, como pools de conexão por parceiro. Um fornecedor lento só esgota o próprio pool.


## O que anotar e próximo passo

Anote com as suas palavras: os estados do breaker e os erros que não contam. Os pools da sua carteira. Como escolher um timeout. E a tempestade de retries, com o orçamento que a evita.

Depois, no lab, reproduza o provedor de trinta segundos com k 6 e Toxiproxy, sem proteção, e meça. Até a próxima aula.
