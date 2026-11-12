# Roteiro · M3 · Dia 1 · Isolamento e anomalias


## Abertura

Esta é a aula em vídeo do módulo três, dia um: níveis de isolamento e anomalias.

Uma carteira guarda dinheiro em linhas, e muitas requisições mexem nas mesmas linhas ao mesmo tempo. Cada requisição está certa sozinha, mas juntas o saldo pode terminar errado. O Postgres roda em READ COMMITTED por padrão, e esse nível deixa duas transferências corretas produzirem um saldo negativo. Hoje você aprende exatamente qual anomalia cada nível permite.


## O que o ACID promete

O ACID são quatro letras, e cada uma promete uma coisa diferente. Pense numa transferência da Ana para o Bruno: um débito, um crédito, uma transação.

Atomicidade: se a transação abortar, nenhuma escrita fica. O débito nunca fica sem o crédito. Mas não promete que vai dar certo.

Consistência: as constraints que você declarou, como CHECK e UNIQUE, valem depois de todo commit. Regras de negócio que você não declarou, como o saldo somado de um casal nunca ficar negativo, são trabalho do seu código.

Isolamento é a letra que mais esconde coisas. Não é uma propriedade, é um cardápio de níveis. E só o serializable garante que o resultado bate com alguma ordem de execução uma de cada vez.

Durabilidade: o commit sobrevive a um crash, mas não promete que a réplica já tem o dado.

Então rodar dentro de uma transação não responde se o saldo pode ficar negativo. A resposta de verdade sempre cita um nível de isolamento e uma anomalia.


## Os fenômenos

O padrão SQL define os níveis pelos fenômenos que cada um proíbe. São quatro.

Dirty read: você lê um dado de uma transação que ainda não fez commit. Vê um débito que depois sofre rollback. No Postgres isso não existe.

Nonrepeatable read: você lê a mesma linha duas vezes e ela mudou, porque outra transação fez commit no meio. Cem, depois setenta.

Phantom read: você repete uma consulta com condição, e o conjunto de linhas mudou. Soma os Pix de hoje e aparece um novo.

E serialization anomaly: cada transação parecia correta, mas juntas produziram um estado que nenhuma ordem serial produziria. É a mais traiçoeira.


## Os níveis no Postgres

Agora a tabela do Postgres. Ele implementa só três níveis de fato.

Read uncommitted se comporta como read committed. Por isso não existe dirty read.

Read committed é o padrão. Se você nunca define um nível, todo o seu serviço roda nele. E ele permite todo o resto.

Repeatable read trabalha sobre um snapshot: a transação enxerga os dados como estavam no primeiro comando. Nonrepeatable e phantom clássicos não acontecem. Mas serialization anomaly ainda pode.

Só serializable proíbe tudo.

Um comportamento para o lab: em repeatable read, se você atualiza uma linha que outra transação alterou depois do seu snapshot, o Postgres recusa com could not serialize access due to concurrent update. É a regra first-committer-wins. Em serializable, a mensagem é outra, mas o SQLSTATE é o mesmo, quatro zero zero zero um. Nos dois, você refaz a transação inteira.


## Lost update

Três anomalias quebram saldos. Aprenda como três histórias. A primeira é o lost update. A carteira da Ana tem cem. Duas compras, de trinta e de cinquenta, rodam juntas.

As duas transações leem o saldo, cem.

T um calcula setenta, grava e faz commit.

T dois calculou cinquenta, grava e faz commit. Saldo final: cinquenta. A compra de trinta aconteceu, mas o débito dela foi sobrescrito.

As duas gravaram a mesma linha, e a segunda apagou a primeira. É o bug clássico do read-modify-write: o código lê um valor, faz a conta em TypeScript e grava. Em repeatable read, o passo cinco falharia com o erro de concurrent update.


## Write skew

A segunda história é o write skew, da wiki do Postgres. O Kevin tem poupança e corrente, quinhentos em cada. O banco deixa sacar até o total das duas contas. Alguém envia dois saques de novecentos ao mesmo tempo, um de cada conta.

Cada transação confere o total, vê mil, e decide que novecentos está ok.

Cada uma atualiza só a própria conta. Menos quatrocentos e menos quatrocentos.

As duas fazem commit. Total: menos oitocentos. Nenhuma quebrou a regra sozinha.

E elas gravaram linhas diferentes, então o first-committer-wins não vê conflito. Em repeatable read, os dois saques passam. Em serializable, o Postgres aborta um deles, e no retry a aplicação recusa o saque.

> **Pausa:** Pergunta: qual a diferença entre lost update e write skew?

No lost update, as duas transações gravam a mesma linha e uma apaga a outra. No write skew, elas leem dados que se sobrepõem e gravam linhas diferentes, quebrando juntas uma regra que cada uma respeitou.


## Write skew com phantom

A terceira história é a mais perigosa numa carteira: uma verificação que lê um conjunto de linhas e depois insere uma nova. O limite diário de Pix é mil. T um soma as transferências de hoje, oitocentos, vê espaço para duzentos e insere duzentos. T dois faz o mesmo ao mesmo tempo. O dia termina em mil e duzentos.

Nenhuma linha existente foi atualizada pelas duas. O conflito é sobre uma linha que ainda não existia.

E repare a sutileza. A tabela diz que o repeatable read do Postgres não tem phantom. É verdade: nenhuma das duas vê a linha nova da outra. Esse é justamente o problema: cada uma decidiu num snapshot desatualizado.

O Hermitage chama de G dois item o write skew sobre linhas existentes, como o Kevin, e de G dois o write skew sobre um predicado, como o limite diário.

> **Pausa:** Pergunta: se o repeatable read não tem phantom reads, por que o limite diário ainda pode ser quebrado?

Porque cada transação soma sobre o próprio snapshot e não vê a inserção da outra. As duas decidem com dados velhos, e as duas inserem.


## Por que serializable resolve

Por que serializable resolve? Desenhe cada transação como um nó e ligue as dependências. Há três tipos: W R, quando uma lê o que a outra gravou. W W, quando sobrescreve. E R W, quando uma leu um valor que a outra depois sobrescreveu.

O resultado principal: um histórico é serializable se e somente se o grafo não tem ciclos.

No caso do Kevin, T um leu a corrente que T dois gravou, então T um vem antes. E T dois leu a poupança que T um gravou, então T dois vem antes. Ciclo. Nenhuma ordem serial existe.

O Serializable Snapshot Isolation do Postgres é construído sobre isso. Ele rastreia arestas R W e, ao ver uma estrutura perigosa, aborta uma transação.

Dois avisos práticos. Ignore os resultados da tentativa que falhou; use os do retry. E você não consegue prever qual transação vai receber o erro, então toda transação que mexe em saldo precisa do mesmo wrapper de retry.

O motivo para preferir serializable é o raciocínio local. Basta verificar que cada transação mantém a regra sozinha. Em níveis mais fracos, você precisa revisar cada par de operações. Com dezenas de operações, a diferença é enorme.

> **Pausa:** Pergunta: o que torna um histórico serializable, em termos do grafo de dependências?

Não ter ciclos. Se o grafo tem ciclo, nenhuma ordem serial explica o resultado.


## O que o Postgres entrega

O Hermitage, de Martin Kleppmann, é uma suíte de testes que verifica quais anomalias cada banco impede de verdade. Cada teste é uma sequência de comandos em duas sessões de psql, então você pode reproduzir qualquer linha.

No Postgres, read committed é na verdade monotonic atomic view. Ele permite lost update, read skew e write skew.

Repeatable read é snapshot isolation. Impede lost update, mas permite write skew.

E serializable impede tudo, abortando uma transação com o erro quatro zero zero zero um.

Esse é o plano da semana. Hoje, o lost update em read committed. Amanhã, o write skew e como fazer retry do erro de serialização.

> **Pausa:** Pergunta: o que o repeatable read do Postgres implementa de fato, segundo o Hermitage?

Snapshot isolation. Impede lost update, mas ainda permite write skew.


## O lab de hoje

O lab de hoje é reproduzir um lost update com duas sessões de psql em read committed. Crie uma carteira com saldo conhecido. Nas duas sessões, inicie a transação e leia o saldo. Na primeira, grave o novo saldo como um literal, do jeito que seu código calcularia, e faça commit. Na segunda, grave o literal dela e faça commit. Confira o saldo errado. Depois repita em repeatable read e anote o texto completo do erro. Um detalhe: um UPDATE que faz a conta no próprio comando, saldo igual a saldo menos trinta, não perde a atualização. Amanhã você vê por quê.


## Revisão relâmpago

Hora da revisão relâmpago. São três perguntas, sem olhar.

> **Pausa:** Pergunta um: o nível padrão do Postgres permite lost update?

Permite. Read committed deixa o read-modify-write da aplicação perder uma atualização.

> **Pausa:** Pergunta dois: por que o first-committer-wins não impede write skew?

Porque as transações gravam linhas diferentes. Não existe conflito de escrita para ele detectar.

> **Pausa:** Pergunta três: qual letra do ACID garante que o saldo somado do casal nunca fica negativo?

Nenhuma sozinha. É uma regra de negócio que você não declarou. Quem garante é o seu código, ou o serializable, que faz cada transação poder ser verificada sozinha.


## O que anotar e próximo passo

Anote com as suas palavras: a tabela dos quatro níveis. Lost update, write skew e phantom, com um exemplo de carteira cada. As linhas do Postgres no Hermitage. E, do lab, a sequência de comandos e o erro que você viu.

Agora abra duas janelas de psql e faça o lab. Até a próxima aula.
