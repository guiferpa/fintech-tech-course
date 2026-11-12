# Roteiro · M7 · Dia 1 · Cartões, estados e pagamento duplicado


## Abertura

Esta é a aula em vídeo do módulo sete, dia um: cartões, máquina de estados e pagamento duplicado.

Até agora a carteira movia dinheiro entre as próprias contas. Nesta semana ela conversa com o mundo de fora: adquirentes, o Pix, e arquivos de liquidação. O dinheiro externo tem duas propriedades novas. Ele se move em várias etapas espalhadas por dias. E o outro lado mantém registros próprios, que podem discordar dos seus. Hoje o assunto é a primeira: os atores do cartão, as três etapas, a máquina de estados da Stripe, e como o Airbnb parou de cobrar hóspedes duas vezes.


## Os atores

Um pagamento que parece um toque para o cliente passa por pelo menos cinco partes.

O portador do cartão é quem paga. Na carteira, o usuário fazendo recarga com cartão de crédito.

O lojista é quem vende, e recebe o dinheiro liquidado. Aqui, é a sua empresa de carteira.

O adquirente processa os pagamentos do lojista e os encaminha. Muitas vezes é a mesma empresa que o processador. E o gateway é a camada de software que recebe os dados do cartão no checkout, um papel que muitos provedores oferecem junto.

A bandeira, como Visa ou Mastercard, opera os trilhos e encaminha os pedidos.

E o emissor, o banco do portador, fornece o cartão e o limite, e aprova ou recusa.

Duas consequências. Sua carteira só conversa com o adquirente. Você nunca chama o emissor ou a bandeira.

E cada parte da cadeia mantém o próprio registro do mesmo pagamento. É por isso que a conciliação existe.


## Três etapas

Um pagamento com cartão tem três etapas, e o dinheiro só se move na última. Veja cada uma, e o efeito no ledger do módulo seis.

Autorização: o emissor confere o cartão e o limite, e responde em segundos. Se aprova, reduz o limite disponível na hora. Mas nenhum dinheiro se moveu. Ele só reservou. No ledger, você cria um hold.

Captura: o adquirente pede os fundos. A autorização dura em geral de cinco a dez dias, então o lojista escolhe quando capturar. Um hotel autoriza no check-in e captura no check-out, talvez com outro valor. No ledger, você faz o lançamento e consome o hold.

Se a autorização expira ou é cancelada, você libera o hold, sem lançamento.

Liquidação: o dinheiro sai do emissor e chega à conta do lojista, em alguns dias. No ledger, você casa a linha de liquidação com o lançamento, e move de a receber do adquirente para caixa no banco.

E um estorno é um lançamento inverso, que aponta para o original. Nunca uma edição. O ledger é append-only.

Guarde: o dinheiro só se move na liquidação.

> **Pausa:** Pergunta: depois de uma autorização aprovada, quanto dinheiro se moveu, e o que o seu ledger faz?

Nenhum dinheiro se moveu. O emissor só reservou. O ledger cria um hold, que reduz o available, sem lançamento.


## Máquina de estados

A Stripe modela cada tentativa de cobrar como um payment intent, um objeto com status que passa por estados fixos. Em geral, um por carrinho ou sessão do cliente.

Requires payment method: criado, sem meio de pagamento. Uma recusa volta para cá, para o cliente tentar de novo.

Requires action: o cliente precisa agir, como na autenticação 3 D secure. Existe também requires confirmation, que a maioria das integrações pula.

Processing: aguardando um meio assíncrono, como um débito bancário, que pode levar dias.

Requires capture: autorizado, mas não capturado, quando você separa autorização e captura.

Succeeded: o fluxo terminou, e você pode entregar o pedido.

Canceled: invalidado, e os fundos retidos são liberados. Não tem volta.


## Três ideias para copiar

Três ideias para copiar.

Primeira: o objeto sobrevive às tentativas. Um payment intent pode ter várias charges, porque retries criam tentativas novas. O intent acompanha o objetivo do cliente, pagar este carrinho. No seu schema, uma tabela payments e outra, payment attempts. Isso vai importar quando um pagamento puder ser tentado em dois provedores.

Segunda: reutilize em vez de recriar. Crie o intent quando o valor for conhecido, e reutilize se o checkout for retomado, com uma idempotency key derivada do carrinho. É isso que impede um clique duplo de criar dois pagamentos.

Terceira: nem todo estado alcança todos os outros. Você cancela antes de processing ou succeeded, não depois. Uma falha volta para requires payment method, nunca para succeeded. Isso é uma tabela de transições, e o lab de amanhã é escrever uma. E, depois da confirmação, acompanhe webhooks: o provedor empurra o estado final, você não o deduz do retorno da chamada.

> **Pausa:** Pergunta: por que separar a tabela de pagamentos da tabela de tentativas?

Porque um pagamento é o objetivo do cliente, e pode ter várias tentativas, com retries ou em provedores diferentes. Cada tentativa tem seu estado e sua referência no provedor.


## Orpheus: três fases

O time de pagamentos do Airbnb migrou de um monólito para serviços, e cada requisição passou a atravessar muitas chamadas de rede. Para não cobrar duas vezes, sem perder latência, eles construíram uma biblioteca embutida em cada serviço, o Orpheus. Ela divide cada requisição em três fases.

Pre R P C: grava no banco os detalhes do pedido.

R P C: chama o serviço externo, e recebe a resposta. Pode também consultar o status de uma tentativa anterior.

Post R P C: grava o resultado no banco: sucesso ou falha, e se a falha admite retry.

Duas regras sustentam o design. Nenhuma chamada de rede nas fases de banco.

E nenhuma interação com o banco na fase de rede. Cada fase de banco é uma transação curta.

Assim, você nunca segura uma transação do Postgres aberta esperando um adquirente lento. E nunca chama o adquirente de dentro de uma transação que pode sofrer rollback depois que o dinheiro já se moveu.

> **Pausa:** Pergunta: o que dá errado se você chamar o adquirente dentro da transação do banco?

A transação pode sofrer rollback depois que o adquirente já cobrou. O dinheiro se moveu, e o seu banco não tem registro. Além disso, a transação fica aberta, segurando locks, durante a chamada lenta.


## Classifique todo erro

O resto do post é uma lista de regras. A primeira: classifique todo erro.

Retryable: falhas de rede ou infraestrutura, em geral 5 X X, que devem passar.

Non-retryable: validação, ou estado inválido, como estornar um estorno. Em geral 4 X X.

E há um terceiro caso que o post trata sem nome: o timeout, em que você não sabe o que aconteceu. É o desfecho desconhecido do módulo um. Você não faz retry às cegas, e não marca como falha. Você pergunta o status ao provedor, que é exatamente o que a fase R P C pode fazer.

Errar a classe machuca nas duas direções. Um erro retryable marcado como final deixa o pagamento travado. Um final marcado como retryable pode causar pagamento duplicado.


## Mais quatro regras

Mais quatro regras.

O cliente mantém a mesma chave em todo retry, grava a chave antes de chamar, e nunca muda o payload. Chaves por requisição são aleatórias. Chaves por entidade são determinísticas, como o estorno do pagamento cento e vinte e três, e servem para operações que devem acontecer no máximo uma vez por entidade.

Uma requisição por vez: cada uma pega um lock de linha na chave, que funciona como um lease que expira. O lease precisa durar mais que o timeout da chamada. Senão um retry começa enquanto a primeira chamada ainda está em andamento no adquirente.

Grave a resposta. Quando a requisição chega a um estado final, a resposta fica gravada, e o retry recebe a original sem chamar o adquirente. Planeje a retenção dessa tabela.

E leia do primário. Uma réplica atrasada pode não enxergar um sucesso já gravado, e deixar um retry cobrar de novo. Para idempotência, consistência vence latência.

Na tabela de tentativas, a restrição unique de provedor e chave é a última linha de defesa. Mesmo que dois workers disputem, só existe uma linha. Com isso, o Airbnb chegou a cinco noves de consistência nos pagamentos.

> **Pausa:** Pergunta: por que o lease precisa durar mais que o timeout da chamada ao adquirente?

Porque, se o lease vencer antes, um retry começa enquanto a primeira chamada ainda pode ser processada pelo adquirente. Aí as duas cobram.


## O lab de hoje

O lab de hoje constrói dois adquirentes falsos. Simples, mas honestos.

Autorizar devolve um acquirer ref e uma aprovação ou recusa. Aceita uma idempotency key, e devolve a mesma resposta para a mesma chave.

Capturar recebe o acquirer ref e um valor até o autorizado.

Consultar status, pela referência ou pela chave. O fallback seguro de quarta depende disso.

Injeção de falha: uma flag que faz a chamada dar timeout depois que o adquirente já registrou. É o caso que produz pagamentos duplicados, então você precisa reproduzi-lo de propósito.

E um C S V de liquidação diário, em centavos inteiros. Faça os dois adquirentes diferirem em taxas, ordem de colunas ou formato de data. Provedores reais nunca concordam num formato, e a conciliação de quinta precisa normalizar.


## Revisão relâmpago

Hora da revisão relâmpago. São três perguntas, sem olhar.

> **Pausa:** Pergunta um: em qual das três etapas do cartão o dinheiro realmente se move?

Na liquidação. A autorização só reserva, e a captura reivindica.

> **Pausa:** Pergunta dois: quais são as duas regras de não do Orpheus?

Nenhuma chamada de rede nas fases de banco, e nenhum acesso ao banco na fase de rede.

> **Pausa:** Pergunta três: a chamada de captura deu timeout. O que você faz?

Marca como desconhecido e consulta o status no provedor com a mesma chave. Nem retry às cegas, nem falha.


## O que anotar e próximo passo

Anote com as suas palavras: os atores e as três etapas do cartão, com o efeito no ledger. Sua máquina de estados de pagamento, incluindo unknown para timeout. E as regras do Orpheus, com o pagamento duplicado que cada uma evita.

Depois, no lab, construa os dois adquirentes falsos. Até a próxima aula.
