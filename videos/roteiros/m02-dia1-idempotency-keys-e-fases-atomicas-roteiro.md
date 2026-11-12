# Roteiro · M2 · Dia 1 · Idempotency keys e fases atômicas


## Abertura

Esta é a aula em vídeo do módulo dois, dia um: idempotency keys e fases atômicas.

O módulo um terminou com uma regra: timeout significa não sei. E a única reação razoável do cliente é tentar de novo. Fazer retry é fácil. Fazer retry de uma transferência sem enviar o dinheiro duas vezes é a parte difícil. Hoje você vai ver como o cliente usa uma idempotency key, e como o servidor divide o trabalho para que um retry continue de onde parou.


## Três formas de falhar

Em dois mil e dezessete, Brandur Leach, do time de API da Stripe, escreveu o post que quase todo mundo cita sobre idempotency keys. Ele parte de uma observação: uma chamada pode quebrar em três momentos, e cada um deixa o cliente com uma informação diferente.

Primeiro: a conexão nem abre. Nada aconteceu, retry é seguro.

Segundo: a conexão cai enquanto o servidor trabalha. Parte do trabalho pode estar feita, e o servidor fica num estado pela metade. É o caso mais interessante.

Terceiro: o servidor termina, mas a resposta se perde. Tudo foi feito, e um retry cego repete o efeito.

Pense num usuário enviando duzentos reais. Se o retry é tratado como requisição nova, o amigo recebe quatrocentos. E se não há retry, quem enviou talvez nunca saiba se o dinheiro saiu.

> **Pausa:** Pergunta: qual dos três momentos faz um retry cego repetir o efeito?

O terceiro: o servidor terminou o trabalho, mas a resposta se perdeu. O retry faz tudo de novo.


## Idempotente por natureza

Uma operação é idempotente quando executar duas vezes tem o mesmo efeito que executar uma vez. O cliente pode chamar quantas vezes precisar até ver sucesso.

O HTTP define PUT e DELETE como idempotentes, e GET não tem efeito colateral. Muitas operações da carteira podem ser escritas assim. Definir o email do usuário dá o mesmo estado final. Cancelar a transferência oitocentos e doze não faz nada se ela já está cancelada. Marcar como COMPLETED é seguro se só move a partir de PENDING.

O problema são as operações relativas: debite duzentos reais, cobre o cartão, crie uma transferência. Executar duas vezes nunca é o mesmo que uma. É para elas que existe a idempotency key.


## A idempotency key

A solução da Stripe: o cliente gera um valor único, a idempotency key, e envia no header Idempotency-Key. Se a requisição falha, faz retry com a mesma chave. O servidor usa a chave para reconhecer o retry.

Se a conexão nem abriu, o servidor vê a chave pela primeira vez e processa normalmente.

Se o servidor falhou no meio, ele retoma ou desfaz com segurança. Como, é o assunto da segunda metade da aula.

Se a resposta se perdeu, o servidor devolve o resultado guardado da primeira tentativa, sem executar de novo.

Visto de fora, o efeito acontece exatamente uma vez, mesmo que a requisição seja enviada muitas vezes.


## O lado do cliente

Do lado do cliente, a regra é: a chave pertence à operação, não à tentativa HTTP. Repare que a chave entra na função como parâmetro. Ela é reutilizada em toda tentativa, com backoff exponencial e jitter entre elas.

Gere a chave uma vez, quando o usuário confirma a transferência, fora do loop. E guarde junto da operação pendente, para que um retry depois de reiniciar o app ainda use a mesma chave e o mesmo corpo.

Um cliente que cria um UUID novo a cada tentativa tem idempotency key só no nome. Cada retry parece novo para o servidor.

E veja a última linha. Depois de desistir, o cliente ainda não sabe se a transferência aconteceu. Ele mostra processando e consulta o status depois. Nunca falhou.

> **Pausa:** Pergunta: por que o jitter importa quando muitos clientes fazem retry ao mesmo tempo?

Sem jitter, clientes que falharam no mesmo instante também tentam no mesmo instante. Essa rajada, o thundering herd, mantém o servidor fora do ar.


## Foreign state mutations

O segundo artigo de Brandur mostra como construir isso com Postgres. A ideia central é a foreign state mutation: uma mudança feita fora do seu banco de dados. Uma cobrança na Stripe, um email, e no nosso caso, uma transferência no banco parceiro. Até chamadas aos seus próprios serviços e publicar no Kafka contam, porque falham independentemente da sua transação.

Divida a transferência. Inserir a chave, criar a transferência com o hold no saldo, gravar a auditoria: tudo local.

Pedir ao banco parceiro que envie o dinheiro: externo.

Salvar o ID do parceiro e guardar a resposta: local. A notificação push é externa, mas pode ser adiada.

Por que importa? Dentro do Postgres, uma transação que falha some sem deixar rastro. Fora dele, não existe rollback. Nas palavras de Brandur: depois da primeira foreign state mutation, você está comprometido, de um jeito ou de outro.


## Fases atômicas

A resposta de Brandur é agrupar os passos locais em fases atômicas. Uma fase atômica é um conjunto de mudanças locais commitadas juntas numa transação, entre duas chamadas externas. A regra: toda fase atômica é commitada antes de iniciar qualquer chamada externa.

Para a transferência: fase um, inserir ou travar a chave.

Fase dois: criar a transferência, o hold e a auditoria, numa transação.

Só então a chamada ao banco parceiro. Se ela falhar, cair ou der timeout, seu banco ainda registra que a tentativa foi feita, e um retry consegue continuar.

Fase três: salvar o ID do parceiro. Fase quatro: agendar a notificação e guardar a resposta final.

Inverta a ordem e veja o desastre: chamar o parceiro primeiro e cair antes do commit significa dinheiro enviado sem nenhum registro local do motivo.

> **Pausa:** Pergunta: o que precisa estar commitado antes da chamada ao banco parceiro, e por quê?

A transferência, o hold e a auditoria. Assim, se a chamada falhar, existe registro local da tentativa, e um retry ou um job consegue continuar.


## Trabalho adiado

Mais uma técnica. Trabalho que não precisa acontecer dentro da requisição, como o email de recibo, vira um job em background.

Brandur grava o job numa tabela de staged jobs, na mesma transação da fase.

Assim o job só fica visível para os workers depois do commit. Um processo separado move os jobs commitados para a fila de verdade.

Já a chamada de pagamento não pode ser adiada, porque a requisição precisa dizer ao usuário se deu certo.

Guarde essa ideia de gravar a mensagem na mesma transação. Ela é o núcleo do padrão outbox, que volta no módulo quatro.


## Recovery points

Se uma requisição morre entre fases, o retry precisa saber onde recomeçar. Brandur guarda isso na própria chave, numa coluna recovery point. Na carteira: started, transfer created, partner called e finished.

O detalhe crucial: o recovery point é atualizado dentro da mesma transação da fase que ele marca. Os dados e o checkpoint são commitados juntos ou não são. O checkpoint nunca afirma um trabalho que não existe.

Um retry lê o ponto atual e pula para a próxima fase.

E uma requisição em finished não executa nada de novo. O servidor só devolve a resposta guardada.

> **Pausa:** Pergunta: por que o recovery point é atualizado na mesma transação da sua fase?

Para que dado e checkpoint sejam commitados juntos. Se fossem separados, o checkpoint poderia dizer que uma fase terminou sem que o dado exista, ou o contrário.


## A tabela de chaves

Eis um esboço da tabela. Repare em quatro colunas. O hash do corpo, para rejeitar um retry com parâmetros diferentes. O recovery point. O locked at, que indica que alguém está trabalhando na chave agora, assunto de amanhã. E a resposta guardada.

A unicidade é no par usuário e chave. Dois usuários que mandem a mesma chave nunca colidem, e um usuário nunca recebe a resposta de outro.

E as chaves têm vida curta. Nas palavras de Brandur, elas garantem correção no curto prazo, não são um arquivo permanente. Um job de limpeza apaga as antigas.


## Revisão relâmpago

Hora da revisão relâmpago. São três perguntas, sem olhar.

> **Pausa:** Pergunta um: por que o cliente precisa reutilizar a mesma chave em todo retry?

Porque a chave identifica a operação. Com chave nova, o servidor trata o retry como uma operação nova, e o dinheiro sai duas vezes.

> **Pausa:** Pergunta dois: o que é uma foreign state mutation?

Uma mudança fora do seu banco de dados, como a chamada ao parceiro, um email ou uma mensagem no Kafka. Nenhuma transação consegue desfazê-la.

> **Pausa:** Pergunta três: por que a constraint única é em usuário e chave, e não só na chave?

Para que dois usuários com a mesma chave não colidam, e ninguém receba a resposta guardada de outra pessoa.


## O que anotar e próximo passo

Anote com as suas palavras: os três momentos de falha e o que o servidor faz em cada um. Como o cliente cria, guarda e reenvia a chave. As definições de foreign state mutation, fase atômica e recovery point. E o fluxo de enviar dinheiro para outro banco dividido em fases, com um recovery point depois de cada uma.

Depois, leia o artigo de Brandur sobre idempotency keys no Postgres, que é a fonte principal de hoje. Até a próxima aula.
