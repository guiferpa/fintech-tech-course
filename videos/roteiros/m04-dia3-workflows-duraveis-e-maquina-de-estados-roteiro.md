# Roteiro · M4 · Dia 3 · Workflows duráveis


## Abertura

Esta é a aula em vídeo do módulo quatro, dia três: workflows duráveis e a máquina de estados da saga.

Na quinta você constrói um orquestrador, e na sexta derruba ele vinte vezes em pontos aleatórios. O critério: saldo total inalterado e nenhuma saga presa. Escrever o caminho feliz leva uma hora. Fazer cada passo sobreviver a queda, retry, timeout e reinício é o trabalho de verdade. Hoje você vê o que motores como Temporal e Step Functions fazem, para construir as mesmas garantias à mão e saber quando vale pagar por um.


## O ponto mais fraco

O orquestrador é um loop: lê o estado, chama um participante, grava o novo estado. Uma queda pode acontecer em qualquer ponto.

Depois de salvar started e antes de chamar accounts: no reinício, chama o débito. Depois que accounts debitou e antes de salvar debited: chama o débito de novo, e accounts precisa responder já feito.

Depois de salvar debited: chama o crédito. Durante o crédito, com timeout: o resultado é desconhecido, então retry com a mesma chave, ou consulta o status.

E se o crédito falhou de vez, durante a compensação: repete o estorno até dar certo.

Duas regras cobrem todas as linhas. Cada passo é idempotente, com chave saga ID mais passo. E algo retoma as sagas não terminais. Um motor de workflow durável é, no fundo, um produto que entrega essas duas regras, mais timers, retries e visibilidade.


## Temporal

O Temporal se descreve como um runtime para execução durável. A promessa: desenvolva como se falhas nem existissem.

Cada passo fica registrado num Event History, e uma execução continua a partir do último evento registrado, através de quedas.

Há duas partes. O Temporal Service, que é o servidor mais um banco de dados, ou o Temporal Cloud. E os Worker Processes, que você hospeda e que rodam seu código pelo SDK.

Repare no que isso significa na operação: o Temporal não tira o banco de dados do seu desenho. Ele move o estado da saga para o banco dele, que você precisa operar ou pagar.


## Workflows e Activities

Seu código se divide em dois tipos. O workflow contém a orquestração: debite, depois credite, e compense se falhar. Parece TypeScript comum.

As Activities fazem o trabalho real com efeito colateral, como chamar accounts. Devem ser idempotentes, para retries sem efeito duplicado.

A divisão existe por causa do replay. Quando um worker cai, outro reconstrói o estado rodando o código do workflow de novo e comparando com o histórico. Por isso o workflow precisa ser determinístico: não pode chamar API, ler o relógio ou gerar aleatório diretamente.

Se o worker morre depois do débito, o novo worker faz o replay, vê que o débito já terminou, não o chama de novo, e continua no crédito. Seu recovery worker faz o mesmo à mão, lendo a tabela de sagas.

> **Pausa:** Pergunta: por que o código de workflow do Temporal não pode chamar uma API HTTP diretamente?

Porque o workflow é reexecutado no replay. Uma chamada direta seria repetida a cada replay e poderia dar resultado diferente. Efeitos vão para Activities, cujo resultado fica guardado no histórico.


## Retries e timeouts

Os defaults do Temporal mostram o que um motor maduro considera seguro. São quatro timeouts de Activity.

Schedule-To-Start limita a espera na fila. Raramente necessário.

Start-To-Close limita uma tentativa. É o que força o retry depois da queda de um worker, porque o servidor não detecta a queda. No TCM, é o timeout HTTP.

Schedule-To-Close limita todas as tentativas somadas. É o deadline por passo na sua tabela de sagas.

Heartbeat é para Activities longas. Desnecessário para chamadas curtas.

E os retries: Activities fazem retry por padrão, começando em um segundo, dobrando, sem limite de tentativas. Workflows não fazem retry. A lição: repita o passo individual indefinidamente, ele é idempotente, mas não recomece a saga inteira. E erros de negócio, como conta encerrada, são não retentáveis: repetir por uma semana não ajuda. O workflow vê a falha e compensa.

> **Pausa:** Pergunta: qual timeout do Temporal faz o retry acontecer depois da queda de um worker?

O Start-To-Close. O servidor não percebe que o worker caiu; quando o tempo da tentativa estoura, ele agenda outra.


## Step Functions

O Step Functions ataca o mesmo problema de outro jeito. Em vez de código com replay, você declara uma máquina de estados. Cada passo é um state, e um Task state chama outro serviço, como uma Lambda.

No tipo Standard, cada passo roda exatamente uma vez, a execução dura até um ano, e você paga por transição. É auditável. Para dinheiro, é o encaixe natural: pode esperar um parceiro por dias.

No Express, cada passo roda pelo menos uma vez, até cinco minutos, e o preço é por execução. Serve para eventos em alto volume.

Mas atenção: exatamente uma vez descreve as transições do motor. Se uma Task chama sua API e a resposta se perde, sua API pode ter feito o trabalho. Idempotency keys continuam sendo sua responsabilidade. E há padrões úteis: Retry e Catch para compensar, Choice para ramificar, e callback com task token para esperar o webhook de um parceiro.

> **Pausa:** Pergunta: o exactly once do Step Functions dispensa idempotency keys na sua API?

Não. Ele vale para as transições do motor. Se a resposta da sua API se perde, o motor repete a chamada, e sua API precisa reconhecer a repetição.


## Quando vale um motor

Compare as três abordagens.

No caseiro, o estado fica no seu Postgres e o fluxo é uma máquina de estados no código. No Temporal, no banco dele, com código comum e replay. No Step Functions, na AWS, com uma máquina declarativa.

Retries e timers você constrói no caseiro, e vêm embutidos nos motores. O custo do caseiro é seu tempo de engenharia; o dos motores, um cluster para operar ou a conta da AWS.

E lock-in: nenhum no caseiro, o SDK no Temporal, a AWS no Step Functions.

Uma boa resposta de entrevista: poucas sagas curtas, de um time, com Postgres já em uso, vão bem com tabela e recovery worker. Muitos fluxos longos, como onboarding com KYC, saques que esperam dias, disputas com passos humanos, envolvendo vários times, justificam um motor. E o motor não elimina idempotência, compensações nem conciliação. Elimina o encanamento. Construir à mão nesta semana é a escolha certa: você só julga o valor de um motor depois de sentir o que ele substitui.

> **Pausa:** Pergunta: cite duas situações em que um motor de workflow durável vale o custo.

Saques que esperam dias pela confirmação de um parceiro, e disputas ou chargebacks com passos humanos. Em geral, muitos fluxos longos e vários times.


## A máquina de estados no papel

O trabalho de hoje é desenhar a máquina de estados da saga de transferência, respondendo cinco perguntas.

Estados: liste todos e marque os terminais. E pergunte se você precisa de um estado UNKNOWN para uma chamada que deu timeout.

Transições: qual evento move cada estado, e para onde. Marque quais são retries do mesmo passo e quais fazem a saga avançar.

Compensações: o que desfaz cada passo compensável. Lançamento de estorno, nunca delete. E marque a pivot: o crédito ao Bruno é o último passo que pode falhar.

Timeouts: todo estado não terminal ganha um deadline e uma ação quando vence. Retry com a mesma chave, consulta, ou compensação. E decida quais erros não são retentáveis.

Recuperação: um worker seleciona sagas não terminais com deadline vencido usando FOR UPDATE SKIP LOCKED, para que dois workers nunca retomem a mesma, e executa o passo do estado atual.

E um teste para o seu desenho: escolha qualquer seta, imagine o processo morrendo no meio, e siga o que o recovery worker faz. Se alguma saga nunca chega a um estado terminal, ou um saldo muda duas vezes, corrija antes de codar.

> **Pausa:** Pergunta: como um recovery worker evita que duas instâncias retomem a mesma saga?

Selecionando as sagas vencidas com FOR UPDATE SKIP LOCKED. Cada instância trava linhas diferentes e pula as que outra já pegou.


## O teste de caos

O lab é um plano, não código. O esqueleto do script de caos: registre o saldo total. Inicie um fluxo constante de transferências, incluindo algumas feitas para falhar no crédito. Vinte vezes, espere um intervalo aleatório e derrube o orquestrador à força, com docker kill, não parada graciosa, e suba de novo. Pare e espere o recovery worker esvaziar. Confira que o total é o inicial e nenhuma saga ficou presa. E saia com erro se algo falhar, para rodar em CI. Depois liste os casos de falha esperados, cada um com o estado, o que o worker faz, e qual chave protege a repetição.


## Revisão relâmpago

Hora da revisão relâmpago. São três perguntas, sem olhar.

> **Pausa:** Pergunta um: o que acontece com um workflow do Temporal quando o worker cai depois que uma Activity terminou?

Outro worker faz o replay do histórico, vê que a Activity já terminou, não a chama de novo, e continua no próximo passo.

> **Pausa:** Pergunta dois: quem chama accounts, o workflow ou uma Activity?

Uma Activity, que deve ser idempotente. O workflow só orquestra, de forma determinística.

> **Pausa:** Pergunta três: quais duas regras cobrem todas as quedas do orquestrador?

Cada passo é idempotente, e algum processo retoma as sagas não terminais.


## O que anotar e próximo passo

Anote com as suas palavras: o que é durable execution. Workflows contra Activities. Os retries e timeouts do Temporal no seu TCM. Standard contra Express. Quando um motor vale. E, no papel, a máquina de estados da saga.

Esse desenho é a base de quinta. Até a próxima aula.
