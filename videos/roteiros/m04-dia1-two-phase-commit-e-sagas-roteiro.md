# Roteiro · M4 · Dia 1 · Two-phase commit e sagas


## Abertura

Esta é a aula em vídeo do módulo quatro, dia um: two-phase commit e sagas.

Até agora, uma transferência era um único BEGIN e COMMIT no mesmo Postgres. Nesta semana você divide a carteira em dois serviços, accounts e payments, cada um com seu banco. A transação única deixa de existir. E vem a pergunta que todo entrevistador de fintech faz: como você move dinheiro entre dois serviços sem perder nem criar dinheiro? Há duas famílias de resposta: o two-phase commit e a saga.


## O atomic commit

Dentro de um banco, a transação é tudo ou nada. Agora deixe ela mexer em duas máquinas: o débito da Ana num banco, o crédito do Bruno em outro.

Para manter a soma dos saldos constante, os dois precisam fazer commit, ou os dois abortar. E um crash de qualquer um no meio não pode deixar o débito sem o crédito. Esse é o problema do atomic commit.

Com um banco por serviço, não existe um controlador único que coordene o commit como um banco coordena as próprias transações.

Guarde para o módulo nove: consenso funciona com a maioria de pé. O atomic commit precisa de todos, porque cada participante guarda parte dos dados. Um que diz não, ou não responde, força o abort.


## Two-phase commit

O two-phase commit acrescenta um papel: o coordenador.

A transação roda normalmente nos bancos A e B, com leituras, escritas e locks de linha.

Na fase um, o prepare, o coordenador pede aos participantes que prometam fazer commit ou rollback.

Cada um verifica se consegue, constraints e dados seguros em disco, e vota sim ou não. O voto sim é uma promessa: vou conseguir fazer commit depois, mesmo após um crash.

Na fase dois, se todos disseram sim, o coordenador decide commit. Se algum disse não ou não respondeu, abort.

Ele registra a decisão e depois a envia para todos.


## 2PC no Postgres

O Postgres expõe o papel de participante com três comandos. PREPARE TRANSACTION é o voto sim: o estado vai inteiro para o disco, e os locks continuam. Depois, COMMIT PREPARED ou ROLLBACK PREPARED, de qualquer sessão. É isso que permite a um coordenador externo terminar o trabalho.

Depois do prepare, a transação se desliga da sua sessão, e os efeitos ficam invisíveis até alguém fazer o commit preparado. Derive o identificador do ID da transferência, para facilitar a recuperação.

E a documentação é clara: esse comando não é feito para aplicações ou sessões interativas. Ele existe para gerenciadores de transação externos.


## Por que o 2PC bloqueia

Se o coordenador cai e volta, ele lê a decisão registrada e reenvia. A janela perigosa fica no meio: o coordenador cai depois que todos votaram sim e antes de eles receberem a decisão. O 2PC é bloqueante.

O que o participante pode fazer? Se fizer commit sozinho, B pode ter votado não.

Se abortar sozinho, o coordenador pode ter decidido commit e avisado B.

Então ele espera. E uma transação preparada continua segurando seus locks.

A linha da conta da Ana fica travada enquanto o coordenador está fora. Toda transferência que mexe nela espera. Dez minutos de coordenador fora, dez minutos de conta congelada.

Transações preparadas esquecidas também atrapalham o vacuum. Por isso a documentação recomenda deixar o recurso desligado se você não precisa dele.

E num incidente, esta é a consulta: as transações preparadas, das mais antigas para as mais novas.

> **Pausa:** Pergunta: no 2PC, por que um participante que votou sim não pode decidir sozinho quando o coordenador some?

Porque não sabe a decisão. Se fizer commit, outro pode ter votado não. Se abortar, o coordenador pode ter decidido commit. Só lhe resta esperar, segurando os locks.


## 2PC seguro custa consenso

Como um banco que usa 2PC evita o bloqueio? No CockroachDB, os valores provisórios fazem o papel do prepare, e o registro da transação, com a decisão, é replicado por consenso como os dados. A decisão sobrevive a crash, e qualquer um pode consultá-la.

O preço é latência, e o protocolo Parallel Commits existe para reduzi-la. A lição: 2PC seguro precisa de consenso por baixo. É algo que você compra num banco de dados, não algo que constrói entre dois serviços NestJS.


## 2PC numa carteira? Não.

Richardson resume: two-phase commit não é opção. E para pagamentos há mais motivos, que o entrevistador quer ouvir.

Primeiro, e mais importante: APIs externas não têm fase de prepare. O banco parceiro, o processador de cartão, o Pix são APIs HTTP. Você pode pedir um pagamento, consultar e às vezes estornar. Não pode pedir que preparem e segurem locks até você avisar.

Segundo: locks atravessando a rede. Todo participante segura locks do prepare até a decisão. Contas quentes viram fila.

Terceiro: a disponibilidade se multiplica para baixo. Três serviços a noventa e nove vírgula nove por cento dão uma transação a uns noventa e nove vírgula sete.

Quarto: acoplamento. Um banco de accounts lento deixa payments lento. A posição prática: transação ACID local dentro de cada serviço, e saga entre eles.

> **Pausa:** Pergunta: por que você não pode incluir a API de um banco parceiro numa transação 2PC?

Porque ela não fala o protocolo. Não existe fase de prepare numa API HTTP de pagamento: ela não promete, nem segura locks esperando sua decisão.


## Sagas

Richardson define em uma frase: uma saga é uma sequência confiavelmente coordenada de transações locais. Cada passo é uma transação normal no banco de um serviço. Quando um passo falha numa regra de negócio, a saga executa compensações que desfazem semanticamente os passos já feitos. O Azure acrescenta três tipos de passo.

Passos compensáveis podem ser desfeitos por uma transação com efeito oposto. Criar a transferência, compensado marcando como falha. Debitar a Ana, compensado com um lançamento de estorno.

O passo pivô é o ponto sem volta. Depois que ele dá certo, a compensação não se aplica mais. Aqui, creditar o Bruno.

E os passos repetíveis vêm depois do pivô. São idempotentes e são repetidos até a saga terminar. Marcar a transferência como concluída.


## Regras da compensação

Três regras importam para o capstone. Primeira: compensação é uma nova transação, não um rollback. O débito da Ana já fez commit, e outras sagas podem ter lido o saldo novo. Você não pode apagá-lo.

Você grava um lançamento de estorno. Um ledger nunca apaga nem altera o passado, então o estorno é o único registro honesto.

Segunda: compensação não pode falhar por regra de negócio. Você sempre pode devolver o dinheiro da Ana. Se pode falhar tecnicamente, é repetida até dar certo, então precisa ser idempotente.

Terceira: a ordem importa. O passo com mais chance de falhar vem cedo, e o que não dá para desfazer, como a chamada ao banco parceiro, fica o mais tarde possível, no pivô ou depois.

> **Pausa:** Pergunta: o que é a transação pivô, e onde a chamada ao banco parceiro deve ficar em relação a ela?

É o ponto sem volta: depois dela, só se segue em frente. A chamada ao parceiro, que não dá para desfazer, fica no pivô ou depois dele.


## Coreografia vs orquestração

Há dois jeitos de coordenar os passos.

Na coreografia, ninguém está no comando. Cada serviço faz sua transação e publica um evento, e os outros reagem. Payments emite transfer requested, accounts debita e emite account debited, e assim por diante. Não tem ponto único de falha, mas surgem dependências cíclicas, e fica difícil rastrear quem reage a quê.

Na orquestração, um componente manda comandos aos participantes e reage às respostas. Na carteira, o orquestrador mora em payments. O estado de cada transferência fica numa linha que você consulta, monitora e retoma.

Para dinheiro, a maioria dos times escolhe orquestração.

> **Pausa:** Pergunta: cite uma vantagem da orquestração sobre a coreografia numa transferência de dinheiro.

O estado de cada transferência fica num lugar só, numa linha que você consulta, monitora com alertas e retoma depois de uma falha.


## O estado do orquestrador

O estado do orquestrador fica no Postgres, mais ou menos assim: o estado, o passo, as tentativas, e um prazo para o passo atual. É um esboço para raciocinar. Na quinta você projeta o seu.

A regra: grave o estado antes de agir com base nele. Se o orquestrador cair depois de chamar accounts e antes de salvar debitado, o worker de recuperação vai chamar accounts de novo.

Isso só é seguro se o débito for idempotente, com chave saga ID mais passo. O módulo dois de novo.


## O que a saga deixa para você

Richardson lista os problemas que você herda, e cada um é uma parte desta semana.

Sem isolamento. Entre o débito e o crédito, o débito da Ana já está visível. Outra saga pode ler esse estado intermediário. Terça você vê semantic lock.

Gravar no banco e publicar um evento de forma atômica. O passo pode cair no meio. Terça você vê o transactional outbox.

O cliente precisa do resultado, e a saga demora mais que uma requisição. Na carteira, a resposta comum é duzentos e dois accepted com o ID da transferência, e uma rota para consultar.

E crashes no meio. O orquestrador pode morrer a qualquer momento, então o estado precisa ser durável e algo precisa retomar. Quarta, os motores de workflow durável resolvem isso como produto. No lab de hoje, rode os dois serviços no Docker Compose, mate um container no meio de uma transferência, e olhe o estado pela metade nos dois bancos.


## Revisão relâmpago

Hora da revisão relâmpago. São três perguntas, sem olhar.

> **Pausa:** Pergunta um: o que o PREPARE TRANSACTION faz com a sessão, os locks e o vacuum?

Desliga a transação da sessão, mantém os locks, e atrapalha o vacuum enquanto ela estiver preparada.

> **Pausa:** Pergunta dois: por que uma compensação é uma nova transação, e não um rollback?

Porque o passo já fez commit e outras transações podem ter visto o resultado. Só um lançamento de estorno registra honestamente o que aconteceu.

> **Pausa:** Pergunta três: por que o atomic commit precisa de todos os participantes, se o consenso só precisa da maioria?

Porque cada participante guarda uma parte diferente dos dados. Não dá para fazer commit sem uma delas.


## O que anotar e próximo passo

Anote com as suas palavras: o 2PC em cinco linhas e seus comandos no Postgres. Por que o participante segura locks. Três motivos para não usar 2PC com o parceiro. Coreografia contra orquestração. E a tabela de compensação com o pivô marcado.

Agora suba os dois serviços, mate um container no meio de uma transferência e observe o estrago. Até a próxima aula.
