# Roteiro · M2 · Dia 2 · Upsert, completer e consumidor idempotente


## Abertura

Esta é a aula em vídeo do módulo dois, dia dois: o upsert da chave, o completer e o consumidor idempotente.

O desenho de ontem cobre uma requisição que volta com a mesma chave. Restam duas lacunas. Alguns clientes nunca voltam, e as transferências pela metade deles ainda precisam de um desfecho. E boa parte do trabalho nem chega por HTTP: chega como mensagens de um broker, que entrega algumas mais de uma vez. Hoje você fecha as duas.


## Pegando a chave

Toda requisição com chave começa igual: encontrar ou criar a chave, e garantir que nenhuma outra tentativa trabalhe nela ao mesmo tempo. São quatro casos.

A chave não existe: insere, já travada, no recovery point started.

Existe, mas com um corpo diferente: rejeita. No curso, com quatrocentos e vinte e dois, porque o cliente tem um bug e retry não adianta.

Existe e está travada por uma tentativa recente: rejeita com quatrocentos e nove, que significa espere e tente de novo.

Existe e o lock expirou: pega o lock e continua a partir do recovery point.

E uma chave já em finished não é travada. A requisição só devolve a resposta guardada.


## O upsert e o lock

No Postgres, inserir ou encontrar é um comando só, com ON CONFLICT DO NOTHING. Se volta uma linha, esta requisição criou a chave e é dona dela. Se não volta nada, a chave já existia, e o código decide entre resposta guardada, quatrocentos e nove ou quatrocentos e vinte e dois.

E sob concorrência: um segundo insert da mesma chave espera a primeira transação terminar antes de concluir que há conflito. É essa espera que impede cinquenta requisições concorrentes de criarem cinquenta chaves.

O lock é um timestamp, locked at, e não um booleano. Um processo que cai segurando o lock não consegue liberá-lo. Então um lock mais velho que um timeout é considerado abandonado e pode ser tomado.

Esse timeout precisa ser maior que a requisição legítima mais lenta, incluindo a chamada ao banco parceiro.

> **Pausa:** Pergunta: por que locked at é um timestamp e não um booleano?

Porque um processo que morre nunca libera o lock. Com timestamp, um lock velho demais é tratado como abandonado e outro pode assumir.


## A máquina de estados

Quando a requisição é dona da chave, ela roda um loop: lê o recovery point, executa a próxima fase, commita a fase junto com o novo ponto, e repete. É uma máquina de estados que só anda para frente. Estado desconhecido é bug.

Na chamada à Stripe, o Rocket Rides repassa uma idempotency key, mas não a do cliente. Ele monta uma a partir do ID interno da linha da chave, que é único entre todos os usuários. Se o servidor morre esperando a Stripe, o retry envia a mesma chave repassada, e a própria Stripe impede uma segunda cobrança.

Os erros são separados. Cartão recusado é definitivo: guarda um quatrocentos e dois como resposta final, e todo retry recebe o mesmo.

Mas cuidado com o exemplo do artigo, que guarda o erro temporário como final. No seu desenho, um erro temporário deve deixar a chave inacabada, para que um retry ou o completer tentem de novo. Só resposta definitiva vira final.

> **Pausa:** Pergunta: contra o que a chave repassada ao provedor protege?

Contra a segunda cobrança quando o servidor morre esperando o provedor. O retry reenvia a mesma chave derivada do registro interno, e o provedor deduplica.


## Murphy em ação

Brandur percorre as falhas uma a uma e mostra que cada uma termina num estado correto. Na carteira fica assim.

A conexão cai antes da API: o cliente faz retry com a mesma chave. Duas tentativas chegam juntas: o índice único deixa uma vencer, a outra recebe quatrocentos e nove.

O Postgres cai logo depois de criar a chave: o cliente insiste, e quando o banco volta, a requisição continua. O parceiro está fora: a transferência fica em transfer created, e o cliente tenta mais tarde.

A API morre esperando o parceiro: o retry continua e reenvia a mesma chave repassada, e o parceiro deduplica. E um deploy ruim que devolve quinhentos: depois da correção, os retries dão certo. Se o cliente sumiu, quem termina é o completer.


## Processos em background

O desenho depende de três processos em background.

O enqueuer move jobs da tabela de staged jobs para a fila real, só depois do commit. É isso que põe o envio do recibo dentro de uma fase atômica sem a requisição esperar o email.

O completer procura requisições que começaram e nunca terminaram, cujo cliente foi embora. Ele roda o mesmo código a partir do recovery point, com os parâmetros guardados. Na carteira, ele não é opcional: uma transferência presa em transfer created está segurando dinheiro de quem envia. Alguém precisa enviá-la ao parceiro ou liberar o hold.

O reaper apaga chaves antigas. Brandur sugere esperar umas setenta e duas horas, e não vinte e quatro, por um motivo prático: se um deploy ruim quebra requisições na sexta à noite, o time tem até segunda para corrigir e deixar o completer terminar.

Brandur chama isso de sistema passivamente seguro. O que falhar, ele para num estado estável, e processos ativos o levam à consistência depois. Idealmente, nenhum humano precisa intervir.

> **Pausa:** Pergunta: o que o completer precisa encontrar guardado na chave para terminar uma requisição sem o cliente?

O recovery point e os parâmetros da requisição. Com eles, roda o mesmo caminho de código a partir de onde parou.


## Quando o outro lado não ajuda

O desenho se apoia em duas premissas. A primeira: o serviço externo é idempotente. Se o banco parceiro não aceita chave nem permite consultar a transferência pela sua referência, um retry pode não ser seguro.

A resposta conservadora de Brandur: trate como falha permanente, a menos que o erro diga explicitamente que é seguro tentar de novo. Timeouts e conexões resetadas contam como falha.

Em pagamentos, falha permanente significa mandar para conciliação manual, não dizer ao cliente que falhou.

A segunda premissa: o armazenamento local é transacional. Sem isso, toda escrita vira uma foreign state mutation.

A lição real: pressione todo serviço de que você depende a oferecer idempotência, e mantenha o dinheiro num banco com transações.


## O consumidor idempotente

Agora a segunda lacuna. Depois que uma transferência é aceita, uma mensagem vai para um broker, e um worker a consome para gravar no ledger. A maioria dos brokers garante entrega at-least-once. Se o worker cai depois de fazer o trabalho e antes do ack, o broker entrega de novo. Processe duas vezes e o saldo fica errado.

O padrão Idempotent Consumer, de Chris Richardson, tem três partes. Primeira: toda mensagem carrega um message ID único.

Segunda: o consumidor registra os IDs que já processou, numa tabela com chave subscriber ID e message ID. O subscriber importa porque quem grava no ledger e quem envia a notificação precisam, cada um, de seu próprio registro.

Terceira, a que torna tudo correto: o ID é gravado na mesma transação do efeito.


## A ordem importa

Veja por que a terceira parte é essencial. Se você registra o ID, commita, e cai antes do efeito, o efeito se perde, e a reentrega é pulada para sempre.

Se aplica o efeito, commita, e cai antes de registrar o ID, a reentrega aplica o efeito duas vezes.

Só com os dois na mesma transação, ou os dois ficam, ou nenhum fica.

E confirme ao broker só depois do commit. Um último cuidado: o padrão protege efeitos dentro do seu banco. Se o efeito é chamar o banco parceiro, a tabela não cobre, porque é uma foreign state mutation. Aí você usa o que Brandur mostrou: commitar a intenção e chamar o parceiro com uma chave derivada do seu registro.

> **Pausa:** Pergunta: o que acontece se o consumidor registra o message ID e faz commit antes de aplicar o efeito?

Se ele cair no meio, o ID fica salvo e o efeito não. A reentrega é pulada para sempre, e o lançamento nunca acontece.


## Dois padrões, uma ideia

Os dois padrões parecem diferentes, mas fazem o mesmo movimento: dar à operação uma identidade estável, e deixar uma constraint única, na mesma transação do efeito, decidir se ela já aconteceu.

Na API, quem escolhe o ID é o cliente, e fica na tabela de chaves. No consumidor, quem escolhe é o produtor, e fica na tabela de mensagens processadas. Uma duplicata na API recebe a resposta guardada. No consumidor, é ignorada em silêncio.

Uma duplicata concorrente recebe quatrocentos e nove na API, e no consumidor espera no índice único e pula. E trabalho em vários passos usa recovery points na API, enquanto o consumidor normalmente faz uma transação por mensagem.


## Revisão relâmpago

Hora da revisão relâmpago. São três perguntas, sem olhar.

> **Pausa:** Pergunta um: um erro temporário do provedor deve fazer o que com a chave? E um erro definitivo?

O temporário deixa a chave inacabada, para retry ou completer. O definitivo guarda a resposta como final.

> **Pausa:** Pergunta dois: por que manter as chaves umas setenta e duas horas, e não vinte e quatro?

Para que um deploy ruim de sexta à noite possa ser corrigido na segunda, e o completer ainda encontre as requisições presas.

> **Pausa:** Pergunta três: por que a chave das mensagens processadas inclui o subscriber?

Porque vários consumidores processam a mesma mensagem por motivos diferentes, e cada um precisa do próprio registro.


## O que anotar e próximo passo

Anote com as suas palavras: os quatro casos do upsert e o status de cada um. Por que a chave repassada vem do registro interno. O que fazem o completer, o enqueuer e o reaper. E o consumidor idempotente, com a tabela de mensagens processadas na mesma transação do efeito.

Depois, leia a página do Idempotent Consumer de Chris Richardson e a segunda metade do artigo de Brandur. Até a próxima aula.
