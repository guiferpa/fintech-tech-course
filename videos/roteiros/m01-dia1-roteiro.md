# Roteiro · M1 Dia 1 · Falhas, timeouts e tempo

## Abertura

Olá! Esta é a aula em vídeo do módulo um, dia um: falhas, timeouts e tempo. São uns doze minutos.

No final você vai conseguir responder três perguntas. O que um timeout realmente significa. Como fazer retry sem cobrar o cliente duas vezes. E por que você não pode ordenar eventos pelo relógio.

Em alguns momentos o vídeo vai parar e te fazer uma pergunta. Tente responder em voz alta antes da resposta aparecer. É esse esforço de lembrar que faz o conteúdo ficar.


## Por que importa

Um sistema de pagamentos é distribuído desde a primeira linha. Sua API fala com o banco de dados. Um worker chama o banco parceiro. O parceiro chama o Pix.

Cada seta desse desenho é uma chamada de rede. E toda chamada de rede pode falhar de jeitos que uma função local não falha.

Os bugs mais caros em pagamentos vêm de uma confusão só: tratar não recebi resposta como se fosse não aconteceu. Guarde essa frase. A aula inteira gira em torno dela.


## Falha parcial

Em uma máquina só, ou o programa funciona, ou a máquina inteira caiu. As partes compartilham o destino.

Numa rede isso acaba. O servidor pode cair com o cliente rodando. A rede pode perder uma mensagem com as duas máquinas saudáveis. Os sistemas distribuídos falham parcialmente: algumas partes funcionam, outras não, e ninguém tem a visão completa.

Jacob Gabrielson, da AWS, classifica pagamentos como sistema de tempo real rígido: precisa responder rápido a requisições imprevisíveis. Sua carteira está nessa categoria.


## Uma chamada, oito falhas

Pegue uma única requisição com resposta. No caminho feliz, ela passa por oito passos. Enviar, a rede entregar, o servidor validar, o servidor fazer o trabalho. Depois a resposta faz o caminho de volta, também em quatro passos.

Cada passo pode falhar sozinho. Gabrielson chama isso de os oito modos de falha do apocalipse.

Agora leve isso para uma transferência. Se a falha foi nos passos um a três, nenhum dinheiro se moveu.

Se foi nos passos cinco a oito, o parceiro já debitou o cliente, e você nunca ficou sabendo. E aqui está o problema: do seu lado, os dois casos parecem idênticos. Nenhuma resposta utilizável.

> **Pausa:** Pergunta: a resposta se perdeu no passo seis. O dinheiro do cliente saiu?

Saiu, sim. O passo quatro, atualizar o estado do servidor, já aconteceu. Só a notícia que não chegou até você.


## Os três desfechos de um timeout

Em uma máquina só, sacar dinheiro devolve sucesso ou saldo insuficiente. Pela rede, aparece um terceiro resultado: desconhecido. Nas palavras de Gabrielson: pode ou não ter acontecido, e o cliente precisa tratar isso corretamente.

Quando o timeout dispara, existem três situações. Um: a requisição nunca chegou. Nada aconteceu, tentar de novo é seguro.

Dois: chegou e foi processada, mas a resposta se perdeu. O efeito aconteceu. Tentar de novo sem proteção faz duas vezes.

Três: chegou e ainda está sendo processada, talvez presa numa fila. O efeito pode acontecer depois que você desistiu. E do seu lado, você não consegue distinguir nenhum dos três.

> **Pausa:** Pergunta: por que marcar a transferência como falhou, logo no timeout, causa cobrança dupla?

Porque o cliente vê falhou, tenta de novo, e se o primeiro pedido tinha dado certo, ele paga duas vezes.


## Modelar o “não sei”

Então seu modelo de dados precisa ser capaz de dizer não sei. No projeto final do curso, uma transferência cuja chamada ao parceiro dá timeout vai para o estado UNKNOWN. Nunca para FAILED.

No código, são três ramos. Sucesso marca concluída. Uma rejeição explícita do parceiro é resposta definitiva, então marca falhou. Timeout marca desconhecida.

Depois, um job pergunta ao parceiro o que aconteceu, e move a transferência para COMPLETED ou FAILED. Diferente da teoria, pagamentos podem ser corrigidos depois: você consulta o status, e uma cobrança errada pode ser estornada. Sistemas reais são construídos em cima de consulta de status e conciliação.


## Escolher o timeout

Como escolher o número? A Amazon faz assim: primeiro decide quantos timeouts falsos aceita. Timeout falso é desistir de uma chamada que teria dado certo. Por exemplo, um em mil.

Então define o timeout no percentil de latência correspondente. Um em mil é o p99.9. Se o parceiro responde noventa e nove vírgula nove por cento das chamadas em um vírgula oito segundo, um timeout de dois segundos desiste por engano de cerca de uma chamada em mil.

O trade-off corta para os dois lados. Curto demais, você transforma sucessos lentos em desconhecidos e aumenta a carga justamente quando o parceiro está mal. Longo demais, clientes e threads ficam presos esperando uma chamada que não volta.


## Retry com segurança

Agora, retries. A Builders' Library diz que retries são egoístas. Quem tenta de novo ocupa mais da capacidade do servidor para melhorar as próprias chances. Se todo mundo fizer isso durante um incidente, os retries viram o incidente.

Segundo: retry de algo com efeito colateral só é seguro se a API for idempotente. O EC2 usa um client token em cada requisição: a mesma requisição enviada duas vezes executa uma vez. As chaves de idempotência da Stripe, do módulo dois, são a mesma ideia.

Terceiro: backoff exponencial com jitter. Espere mais a cada tentativa, ponha um limite, e some um valor aleatório, para que milhares de clientes não voltem no mesmo instante.

Quarto: faça retry em uma camada só.

> **Pausa:** Pergunta: a aplicação, o cliente HTTP e o load balancer fazem até três tentativas cada um. Um clique do usuário vira quantas chamadas?

Vinte e sete. Três vezes três vezes três. Escolha um único lugar na stack para fazer retry.


## Detecção de falhas e SLOs

Você não enxerga outra máquina. Só detecta falhas com timeouts e heartbeats. No Cassandra, cada nó decide sozinho se um par está vivo ou morto, e dois nós podem discordar sem que nenhum esteja errado. De fora, um nó lento e um nó morto parecem iguais. Um detector de falhas só pode suspeitar.

E cuidado com a armadilha oposta. Na Amazon, um servidor de catálogo com disco cheio passou a devolver respostas vazias muito rápido. O load balancer entendeu rápido como saudável, mandou quase todo o tráfego para ele, e o site caiu.

Para falar de disponibilidade, use os noves. Noventa e nove vírgula nove por cento são umas oito horas fora do ar por ano. Quatro noves, uns cinquenta e três minutos.

E o vocabulário do Google. SLI é a medida, por exemplo a fração de transferências bem-sucedidas. SLO é a meta para essa medida. SLA é um contrato com consequência. Se nada acontece quando você não cumpre, é SLO, não SLA. E cem por cento é a meta errada: seu parceiro vai cair em algum momento, e o design precisa assumir isso.


## Relógios em que você não pode confiar

Agora o tempo. Todo servidor tem seu próprio relógio, e todo relógio deriva. Eles se corrigem via NTP. A correção normal é o slewing: andar um pouco mais rápido ou mais devagar até alcançar. A outra é o stepping: pular de uma vez. E alguns programas quebram feio com esse pulo.

O caso famoso é da Cloudflare, no primeiro dia de dois mil e dezessete. Um leap second fez o relógio voltar. O código em Go media duração subtraindo o horário de início do horário atual. A duração saiu negativa. A média das durações ficou negativa. Esse valor foi passado para uma função de número aleatório que entra em pânico com argumento negativo. Resultado: horas de falhas no DNS.

A causa raiz, nas palavras deles: a crença de que o tempo não pode andar para trás. Por isso existem dois relógios. O de hora do dia, Date.now, diz a data, mas pode pular. Use para timestamps que pessoas leem. O monotônico, hrtime, só anda para frente. O valor absoluto não significa nada, mas a diferença entre duas leituras é uma duração confiável.

> **Pausa:** Pergunta: qual relógio você usa para medir um timeout?

O monotônico. Sempre. Hora do dia é para humanos lerem.


## Ordenar eventos sem relógio de parede

Se relógios derivam e pulam, comparar timestamps de duas máquinas pode inverter a ordem. A Cockroach Labs chama isso de causal reverse. O nó um tem o relógio certo. O nó dois está cem milissegundos atrasado.

A transação um faz commit no nó um, com timestamp cento e cinquenta. Cinquenta milissegundos depois, alguém que viu ela terminar inicia a transação dois no nó dois, que carimba cem. Ordenando por timestamp, a dois parece ter vindo antes da um. Mas ela começou depois.

Então de onde vem a ordem? De uma autoridade única. Mas cuidado: um id sequence do Postgres não serve. Ele tem buracos, e o valor é pego quando nextval roda, não no commit. O id onze pode fazer commit antes do dez.

A solução é fazer da própria linha da conta a autoridade. Dentro da transação, você incrementa um contador na linha da conta, o que trava a linha até o commit, e usa esse número no lançamento. A ordem por conta fica estrita e sem buracos. O created_at é para humanos. O seq é a ordem.


## Revisão relâmpago

Revisão relâmpago. Três perguntas, sem olhar.

> **Pausa:** Um: quais são os três desfechos possíveis de um timeout?

Não chegou. Aconteceu mas a resposta se perdeu. Ou ainda está em andamento. Por isso o estado é UNKNOWN, e um job consulta o parceiro.

> **Pausa:** Dois: o que torna seguro fazer retry de um pagamento?

Idempotência. Uma chave enviada em cada requisição, para que duas tentativas executem uma vez só. Mais backoff com jitter, em uma camada só.

> **Pausa:** Três: por que não ordenar os lançamentos de uma conta pelo created_at?

Porque relógios derivam e pulam. A ordem vem de uma autoridade única: um seq por conta, incrementado dentro da transação.


## O que anotar e próximo passo

Antes de fechar, anote três coisas com as suas palavras. Os três desfechos de um timeout e o que seu sistema faz em cada um. Como você escolheria o timeout do banco parceiro, e em que camada ficam os retries. E um exemplo concreto de pagamento em que ordenar pelo relógio daria errado.

Depois, transforme as perguntas do Teste-se em flashcards no Anki. E se tiver tempo, leia o artigo do Gabrielson, Challenges with distributed systems, que é a fonte principal de hoje. Até a próxima aula.
