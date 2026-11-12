# Roteiro · M2 · Dia 3 · Idempotência no fluxo inteiro


## Abertura

Esta é a aula em vídeo do módulo dois, dia três: idempotência no fluxo inteiro.

Você já tem os dois padrões: chaves na API e mensagens processadas no consumidor. Mas fluxos reais encadeiam várias etapas, e basta uma sem proteção para enviar dinheiro duas vezes. Hoje você lê o contrato de um provedor real, aprende a reconhecer operações já seguras, e desenha o fluxo inteiro marcando onde cada duplicata é barrada. Esse desenho é a resposta do teste de domínio.


## O contrato da Stripe

A página da Stripe sobre requisições idempotentes é curta, e cada frase é uma decisão de design. Leia como quem projeta APIs.

O cliente gera a chave, sugerido um UUID versão quatro, com até duzentos e cinquenta e cinco caracteres. Porque só o cliente sabe quando uma operação é nova. E nada sensível na chave, porque chaves vão parar em logs.

A Stripe salva o status e o corpo da primeira requisição, e os retries devolvem essa resposta, inclusive um erro quinhentos. Um replay é um replay, até de uma falha.

As chaves podem ser removidas depois de vinte e quatro horas. E parâmetros diferentes com a mesma chave são erro: bug do cliente, não retry.

Se a validação falha, ou outra requisição com a mesma chave está rodando, nada é salvo, e dá para repetir. E só POST usa chave, porque GET e DELETE já são idempotentes.

> **Pausa:** Pergunta: o que a Stripe devolve quando você faz retry de uma chave cuja primeira tentativa recebeu quinhentos?

O mesmo quinhentos guardado. A resposta salva é devolvida, inclusive erros.


## O lado do cliente

A página de tratamento de erros da Stripe completa o contrato pelo lado do cliente. Quatro pontos para anotar.

Um quatrocentos e nove significa que outra requisição com a mesma chave ainda está rodando. Espere e repita com a mesma chave. Uma chave nova pode iniciar uma segunda operação.

Um quinhentos é indeterminado. A operação pode ter tido efeito. Não tente com chave nova antes de saber o que aconteceu: busque o objeto, confira o dashboard ou espere o webhook. É o estado UNKNOWN do módulo um, escrito por uma empresa de pagamentos.

Existe uma janela: repita com a mesma chave por até vinte e quatro horas. Depois, pare e concilie.

E replays são identificados com um header. Um detalhe: a API v2 da Stripe usa outra janela, de trinta dias. Até o contrato do provedor é uma escolha, não uma lei da natureza.

> **Pausa:** Pergunta: o que a Stripe manda o cliente fazer depois de um quatrocentos e nove?

Esperar e repetir com a mesma chave e os mesmos parâmetros. Nunca gerar uma chave nova.


## Chaves naturais

Uma idempotency key responde a uma pergunta: esta é a mesma operação que eu já vi? Há duas formas de obter essa identidade.

A chave do cliente é um valor aleatório gerado para a ocasião, como o header Idempotency-Key. Não tem significado de negócio, e só funciona se o cliente a guardar e reutilizar.

A chave natural já existe no domínio. O melhor exemplo é o end to end ID do Pix: todo Pix tem um identificador único que todos os participantes usam. Quando o parceiro avisa que chegou um Pix, duas notificações com o mesmo ID são o mesmo pagamento, e você credita uma vez só, com uma constraint UNIQUE na coluna. Não depende do bom comportamento de ninguém.

Mas a chave natural tem limites. Enviar duzentos reais para a Ana a partir do app não tem ID natural até você criar a transferência. Por isso a API usa chave do cliente. A regra prática: chave natural sempre que o domínio der uma, chave do cliente onde não der. E muitas vezes as duas: a chave do cliente cria a transferência, e o ID da transferência vira a chave natural de todo o resto.

> **Pausa:** Pergunta: quando uma chave natural é melhor que a do cliente, e quando você não pode usar uma?

É melhor quando o domínio já fornece um ID único, como o end to end ID do Pix, porque não depende do cliente. Não dá quando a operação ainda não tem ID, como o pedido de enviar dinheiro antes de a transferência existir.


## Idempotente por natureza

Compare dois comandos. O primeiro move a transferência para COMPLETED só se ela estiver PENDING. Na segunda vez, o WHERE não encontra linha nenhuma, e nada muda. O segundo subtrai cem reais do saldo toda vez que roda. É o exemplo do Richardson: só está correto se nunca vir a mesma mensagem duas vezes, e a entrega at-least-once garante que vai ver.

Bônus do primeiro: a contagem de linhas, uma na primeira vez e zero depois, diz ao código se esta chamada fez o trabalho. Útil para decidir se emite um evento.

O objetivo de design sai daí: transforme mudanças relativas em transições de estado, ou em inserts protegidos por chave única.

O ledger é o exemplo clássico. Em vez de atualizar um saldo, você insere lançamentos, cada um com uma referência única à transferência. A gravação fica naturalmente idempotente.

> **Pausa:** Pergunta: por que o UPDATE com WHERE status igual a PENDING é seguro de repetir?

Porque na segunda execução a transferência já não está PENDING. O WHERE não encontra linha, e nada muda.


## Repassando a chave

Sua API pode ser perfeitamente idempotente e ainda assim enviar dinheiro duas vezes, se a chamada ao parceiro não for. O worker dá timeout, repete, e o parceiro vê duas requisições. A correção é enviar uma chave ao parceiro, montada a partir do seu próprio registro durável. Na carteira, o ID da transferência: wallet transfer oitocentos e doze.

Três propriedades fazem isso funcionar. Ela existe antes da chamada, porque a transferência foi commitada antes.

Ela é a mesma em toda tentativa. Venha o retry do mesmo worker, de outro pod, do completer ou da conciliação, todos leem a mesma linha.

E ela é única no sistema inteiro.

Depois, leia o contrato do parceiro com o mesmo cuidado. Por quanto tempo ele guarda as chaves? Faz replay de erros?

Se seus retries podem passar da janela dele, a chave deixa de proteger. Aí, pare de repetir e consulte o status pela sua referência. E se o parceiro não aceita chave nenhuma, trate falhas ambíguas como desconhecidas e concilie, nunca como seguras para retry.

> **Pausa:** Pergunta: por que a chave repassada deve vir do ID da transferência, e não da chave do cliente?

Porque o ID da transferência existe antes da chamada, é o mesmo para qualquer processo que repita, e é único no sistema. A chave do cliente só é única por usuário.


## O fluxo inteiro

Agora o fluxo inteiro. Ponto um, a API. Retries do cliente depois de um timeout são barrados pela chave do cliente, com resposta guardada e lock. Na mesma transação, a transferência, o hold e a mensagem de saída são commitados juntos.

Ponto dois, a fila. A mensagem pode chegar duas vezes, porque a API publicou duas vezes ou o broker reentregou. O message ID precisa ser estável: o ID da transferência, fixo antes de a mensagem sair.

Ponto três, o worker. Reentrega depois de uma queda antes do ack. Barrada pela tabela de mensagens processadas na mesma transação do efeito, mais uma transição de PENDING para SENDING.

Ponto quatro, o banco parceiro. O worker repete uma chamada que deu timeout. Barrada pela chave repassada, derivada do ID da transferência. Timeout vira UNKNOWN e consulta depois.

Ponto cinco, o webhook. O parceiro reenvia a notificação. Barrada pela chave natural, o ID dele, e pela transição de SENDING para COMPLETED.

> **Pausa:** Pergunta: no fluxo API, fila, worker, parceiro, qual etapa a tabela de mensagens processadas protege?

O worker: a reentrega da mensagem pelo broker. Ela não protege a chamada ao parceiro, que precisa da chave repassada.


## A frase do teste de domínio

Uma frase resume o desenho inteiro. Toda etapa é at least once. Então todo receptor precisa deduplicar, e todo ID precisa estar fixo antes de cruzar uma fronteira.

Guarde essa frase. É o que o teste de domínio deste módulo quer ouvir, com o motivo de cada ponto.


## Testes de quinta

O laboratório de hoje é listar os casos de teste e criar as migrations vazias. São quatro casos.

Mesma chave e mesmo corpo: a segunda resposta é igual à primeira, e existe uma transferência só. Mesma chave com corpo diferente: quatrocentos e vinte e dois, e a transferência continua com o primeiro valor.

Requisição ainda em andamento, com o parceiro lento: uma recebe o resultado, a outra quatrocentos e nove. E cinquenta requisições simultâneas com a mesma chave: exatamente uma transferência, um hold e uma chamada ao parceiro.

Vale acrescentar: a mesma chave vinda de dois usuários dá duas transferências, uma mensagem duplicada no worker dá uma gravação, e um timeout repetido no parceiro dá um pagamento só.


## Revisão relâmpago

Hora da revisão relâmpago. São três perguntas, sem olhar.

> **Pausa:** Pergunta um: o que fazer quando uma operação continua desconhecida depois da janela de chaves do provedor?

Parar de repetir, consultar o status pela sua referência e conciliar.

> **Pausa:** Pergunta dois: qual a chave natural de um Pix recebido?

O end to end ID, com uma constraint UNIQUE na tabela de Pix recebidos.

> **Pausa:** Pergunta três: como tornar seguro um débito relativo no saldo?

Protegendo com chave ou mensagem processada na mesma transação, ou trocando por um lançamento com referência única.


## O que anotar e próximo passo

Anote com as suas palavras: o contrato da Stripe. Chave natural contra chave do cliente. Um comando naturalmente idempotente e um não, e como tornar o segundo seguro. E, no papel, o fluxo da API até o parceiro com cada ponto de idempotência e o motivo.

Guarde essa folha para o teste de domínio. Depois, leia as páginas da Stripe sobre requisições idempotentes e tratamento de erros. Até a próxima aula.
