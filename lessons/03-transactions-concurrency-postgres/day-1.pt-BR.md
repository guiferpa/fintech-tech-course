# Módulo 3, segunda-feira: níveis de isolamento e as anomalias que eles permitem

[Módulo 3](../../modules/03-transactions-concurrency-postgres.pt-BR.md) · [Read in English](day-1.md)

**Tempo de leitura:** cerca de 45 minutos. Use o resto do bloco de 2 horas nas referências do final, começando pela tabela do Hermitage e pelos exemplos da wiki do PostgreSQL.

Este é um texto original escrito para este curso. Ele se baseia nas referências listadas no final, e cada seção indica a fonte que segue. Quando uma ideia vem de um autor específico, o texto diz isso.

## Por que isso importa para uma fintech

Uma carteira digital guarda dinheiro em linhas, e muitas requisições mexem nas mesmas linhas ao mesmo tempo. Um cliente toca duas vezes em "Pagar". Uma transferência Pix chega enquanto uma compra no cartão está sendo autorizada. Um job em lote cobra tarifas mensais enquanto o cliente transfere dinheiro para fora. Cada requisição está correta sozinha. Rodando juntas, o saldo pode terminar errado.

Bancos de dados prometem "transações", mas a promessa é mais fraca do que a maioria dos engenheiros imagina. O Postgres roda em READ COMMITTED por padrão, e esse nível deixa duas transferências corretas produzirem um saldo negativo. Esta semana é sobre saber exatamente qual anomalia cada nível permite e, depois, impedir saldos negativos de mais de uma forma. Hoje é o vocabulário, contado pelo que o Postgres faz de verdade e por exemplos que você pode digitar no `psql`.

## 1. O que o ACID promete de fato

*Fonte principal: documentação do PostgreSQL, "Transaction Isolation" (seção 13.2).*

ACID são quatro letras, e cada uma promete uma coisa diferente. Leia-as pensando numa transferência da carteira da Ana para a do Bruno: um débito, um crédito, uma transação.

| Letra | O que promete | O que não promete |
| --- | --- | --- |
| **Atomicidade** | Se a transação abortar, nenhuma das suas escritas permanece. O débito nunca fica sem o crédito. | Que a transação vai dar certo, ou que um retry é seguro. |
| **Consistência** | As constraints declaradas (`CHECK`, `UNIQUE`, foreign keys) valem depois de todo commit. | Regras de negócio que você não declarou, como "o saldo somado de um casal nunca fica abaixo de zero". Essas são trabalho do seu código. |
| **Isolamento** | Transações concorrentes ficam separadas no grau que o nível escolhido define. | Que todo nível se comporte como se as transações rodassem uma de cada vez. Só o serializable faz isso. |
| **Durabilidade** | Uma transação com commit sobrevive a um crash. | Que uma réplica já a tenha (veja o Módulo 1, terça-feira). |

A letra que mais esconde coisas é o **I**. Isolamento não é uma propriedade só, mas um cardápio de níveis, e cada nível permite um conjunto diferente de surpresas. Só o nível mais forte, serializable, garante que o resultado corresponde a alguma ordem de execução das transações uma de cada vez. Todo nível abaixo dele troca parte dessa garantia por menos abortos e menos espera.

Então "roda dentro de uma transação" não responde à pergunta "isso pode ficar negativo?". A resposta de verdade sempre cita um nível de isolamento e uma anomalia.

## 2. Os quatro níveis, como o Postgres os implementa

*Fonte principal: documentação do PostgreSQL, "Transaction Isolation", Tabela 13.1 e as definições acima dela.*

O padrão SQL define quatro níveis pelos fenômenos que cada um proíbe. A documentação do Postgres define cada fenômeno em uma frase. Em termos de carteira:

- **Dirty read.** "A transaction reads data written by a concurrent uncommitted transaction." Você vê um débito que depois sofre rollback.
- **Nonrepeatable read.** Uma transação lê uma linha de novo e a encontra alterada por outra transação que fez commit no meio-tempo. Você lê o saldo da Ana duas vezes na mesma transação e recebe 100, depois 70.
- **Phantom read.** Uma transação executa de novo uma consulta com uma condição de busca e o conjunto de linhas que atendem à condição mudou porque outra transação fez commit. Você soma os Pix de hoje duas vezes e aparece um novo.
- **Serialization anomaly.** "The result of successfully committing a group of transactions is inconsistent with all possible orderings of running those transactions one at a time." Cada transação parecia correta, mas juntas produziram um estado que nenhuma ordem serial produziria.

A Tabela 13.1 então diz o que cada nível permite. Repare nas duas células "but not in PG", porque é nelas que o Postgres é mais rígido que o padrão:

| Nível | Dirty read | Nonrepeatable read | Phantom read | Serialization anomaly |
| --- | --- | --- | --- | --- |
| Read uncommitted | Permitido, mas não no PG | Possível | Possível | Possível |
| Read committed | Não é possível | Possível | Possível | Possível |
| Repeatable read | Não é possível | Não é possível | Permitido, mas não no PG | Possível |
| Serializable | Não é possível | Não é possível | Não é possível | Não é possível |

Três fatos práticos saem dessa mesma página:

- **Read committed é o padrão.** Se você nunca define um nível, toda transação do seu serviço NestJS roda nele.
- **O Postgres implementa só três níveis.** Read uncommitted se comporta como read committed, então não existe dirty read no Postgres.
- **Repeatable read trabalha sobre um snapshot.** Sua transação enxerga os dados como estavam no primeiro comando, então nonrepeatable reads e phantoms clássicos não acontecem. Ele ainda permite serialization anomalies, que a seção 3 mostra com dinheiro.

Mais um comportamento importa para o lab. Em repeatable read, se você atualizar uma linha que outra transação alterou e commitou depois que o seu snapshot foi tirado, o Postgres recusa com `ERROR: could not serialize access due to concurrent update`, e a documentação manda refazer a transação inteira. Essa regra first-committer-wins impede o lost update, mas não o write skew.

Em serializable, a falha tem outra mensagem, `could not serialize access due to read/write dependencies among transactions`, e as duas mensagens compartilham o SQLSTATE `40001`. A documentação recomenda uma forma genérica de capturar o `40001` e fazer retry. A aula de terça constrói esse retry.

## 3. Lost update, write skew e phantoms, em termos de carteira

*Fontes principais: Justin Jaffray, "What write skew looks like" (blog da Cockroach Labs), para write skew; wiki do PostgreSQL, "SSI", para os exemplos de cheque especial e de dados que se cruzam; documentação do PostgreSQL, seção 13.2, para as definições dos fenômenos.*

Essas três anomalias são as que quebram saldos. Aprenda-as como três histórias, cada uma com duas transações concorrentes, T1 e T2.

**Lost update.** A carteira da Ana tem 100. Duas compras, de 30 e de 50, rodam ao mesmo tempo. As duas transações leem o saldo para a memória da aplicação, calculam um novo valor e o gravam de volta.

| Passo | T1 (compra de 30) | T2 (compra de 50) |
| --- | --- | --- |
| 1 | `SELECT balance` → 100 | |
| 2 | | `SELECT balance` → 100 |
| 3 | `UPDATE ... SET balance = 70` | |
| 4 | `COMMIT` | |
| 5 | | `UPDATE ... SET balance = 50` (espera, depois roda) |
| 6 | | `COMMIT` |

O saldo final é 50. A compra de 30 aconteceu, mas o débito dela foi sobrescrito. As duas transações gravaram a **mesma linha**, e a segunda escrita apagou a primeira. Esse é o bug clássico de read-modify-write, e ele mora no código da aplicação que lê um valor, faz a conta em TypeScript e grava o resultado. Em repeatable read, o passo 5 falha com o erro de "concurrent update" da seção 2.

**Write skew.** A página da wiki do PostgreSQL sobre SSI tem um exemplo bancário que serve para uma carteira quase palavra por palavra. O Kevin tem duas contas, poupança e corrente, com 500 cada. O banco deixa o cliente sacar "up to the total of what they have in all accounts" e move dinheiro entre as contas depois, para fechar o dia positivo. Alguém envia dois saques de 900 ao mesmo tempo, um de cada conta. Cada transação confere se o total cobre o valor, vê 1.000, decide que 900 está ok e atualiza só a própria conta.

| Passo | T1 (900 da poupança) | T2 (900 da corrente) |
| --- | --- | --- |
| 1 | lê poupança=500, corrente=500; total 1.000, ok | |
| 2 | | lê poupança=500, corrente=500; total 1.000, ok |
| 3 | `UPDATE` poupança → -400 | |
| 4 | | `UPDATE` corrente → -400 |
| 5 | `COMMIT` | `COMMIT` |

O total agora é -800. Nenhuma transação quebrou a regra sozinha, e elas gravaram **linhas diferentes**, então o first-committer-wins não vê conflito. A wiki diz que em repeatable read isso "could work", ou seja, os dois saques passam. Em serializable, o Postgres deixa o primeiro a fazer commit vencer e faz o outro falhar com um erro de serialização. No retry, a segunda transação vê um saldo líquido de 100, e a aplicação recusa o saque de 900.

O artigo do Jaffray explica o formato geral: duas transações concorrentes leem dados que se sobrepõem, gravam em lugares disjuntos e as duas fazem commit. No exemplo dele, P copia x para y enquanto Q copia y para x, e os valores terminam trocados, "an outcome not possible in either serial execution."

**Write skew do tipo phantom.** O caso perigoso numa carteira é uma verificação que lê um **conjunto** de linhas e depois insere uma nova. Digamos que o limite diário de Pix seja 1.000. T1 soma as transferências de hoje (800), vê espaço para 200 e insere uma transferência de 200. T2 faz o mesmo ao mesmo tempo com outros 200. As duas fazem commit, e o dia termina em 1.200. Nenhuma linha existente foi atualizada pelas duas. O conflito é sobre uma linha que ainda não existia quando cada uma leu.

A documentação do Postgres e a wiki usam o mesmo formato com uma tabela `mytab(class, value)`: uma transação soma a classe 1 e insere o resultado como classe 2, a outra soma a classe 2 e insere o resultado como classe 1. Em repeatable read, as duas fazem commit. Em serializable, uma falha. Repare na sutileza: a Tabela 13.1 diz que o repeatable read do Postgres não tem phantom reads, e é verdade: nenhuma das transações chega a ver a linha nova da outra. Esse é justamente o problema, já que cada uma decidiu com base num snapshot desatualizado. O Hermitage chama isso de "write skew on predicate read" (G2), em oposição ao write skew sobre linhas que já existem (G2-item, "write skew on disjoint read").

## 4. Por que serializable resolve o write skew

*Fontes principais: Justin Jaffray, "What write skew looks like", seções "Who cares?" e "When is Snapshot not Serializable?"; wiki do PostgreSQL, "SSI".*

O artigo do Jaffray explica a teoria por trás da solução, e vale a pena conhecê-la para entrevistas.

Desenhe cada transação como um nó. Adicione uma aresta quando uma transação depende de outra. Há três tipos de dependência: **wr** (T2 lê o que T1 gravou), **ww** (T2 sobrescreve o que T1 gravou) e **rw**, também chamada de antidependência (T1 leu um valor que T2 depois sobrescreveu, então T1 precisa vir antes de T2). O Jaffray enuncia o resultado principal: "A history is serializable if and only if its serialization graph has no cycles."

Na história do Kevin, T1 leu a corrente e T2 gravou a corrente, então T1 precisa vir antes de T2. T2 leu a poupança e T1 gravou a poupança, então T2 precisa vir antes de T1. Isso é um ciclo de duas arestas rw, e não existe ordem serial.

O Jaffray também observa que, entre transações snapshot concorrentes, a única dependência possível é rw, e que todo ciclo num histórico snapshot não serializable contém duas arestas rw consecutivas. O **Serializable Snapshot Isolation (SSI)** do Postgres é construído sobre essa observação. Ele rastreia dependências rw e, quando vê um padrão perigoso, aborta uma transação. O exemplo do cheque especial na wiki descreve exatamente isso: o SSI detecta uma "dangerous structure" e cancela um dos dois saques.

A wiki acrescenta dois avisos práticos que importam para o seu código:

- **Ignore resultados de uma transação que falhou.** A wiki diz que resultados de consultas de uma transação serializable que falhou "must be ignored; use the results from the retry." Se o seu handler já montou uma resposta a partir da primeira tentativa, descarte-a.
- **O retry precisa ser genérico.** No exemplo com três transações da wiki (o caso "Primary Colors"), a wiki diz que o destino da terceira transação "is not deterministic": ela pode fazer commit ou pode receber uma falha de serialização. Você não consegue prever qual transação vai receber o erro, então toda transação que mexe em saldo precisa do mesmo wrapper de retry.

O motivo prático para preferir serializable é o que o Jaffray chama de raciocínio local. Em serializable, "it's sufficient to verify that every individual transaction maintains this invariant on its own". Em níveis mais fracos, "one must consider the interactions between every transaction to ensure said invariants are upheld". Numa carteira com dezenas de operações que mexem em saldo, essa diferença é enorme. Em serializable, você revisa cada operação uma vez. Em snapshot isolation, você precisa revisar cada par.

O exemplo "Deposit Report" da wiki é uma versão de back-office do mesmo problema: um recibo que entra num lote já fechado e levado ao banco. Os jobs de conciliação do Módulo 7 têm esse formato.

## 5. O que o Postgres entrega de fato

*Fonte principal: Martin Kleppmann, repositório Hermitage, linhas do PostgreSQL na tabela de resultados.*

O Hermitage é um conjunto de testes que o Kleppmann escreveu para verificar quais anomalias cada banco de dados realmente impede em cada nível de isolamento. O README dele parte de uma observação direta: "Unfortunately, those weaker isolation levels are quite poorly understood." Ele acrescenta que a documentação dos fornecedores sobre esses níveis é "frustratingly vague". Cada teste é uma sequência de comandos SQL digitados em duas ou mais sessões, então você pode reproduzir qualquer linha com duas janelas de `psql`. É isso que o torna prático: é uma suíte de testes, não uma teoria.

Os códigos de anomalia que importam aqui, com os nomes que o Hermitage dá a eles:

| Código | Nome no Hermitage | Significado na carteira |
| --- | --- | --- |
| G0 | write cycles (dirty writes) | duas transferências intercalam escritas nas mesmas linhas |
| G1a, G1b, G1c | aborted reads, intermediate reads, circular information flow | você vê um débito que depois sofre rollback, ou metade de uma transação |
| P4 | lost update | seção 3 |
| G-single | read skew | um comando mostra A depois de uma transferência e B antes dela |
| G2-item | write skew on disjoint read | as duas contas do Kevin |
| G2 | write skew on predicate read | limite diário somando linhas |

As linhas do PostgreSQL, como o Hermitage as reporta:

| Nível que você pede | O que ele é de verdade | Impede | Permite |
| --- | --- | --- | --- |
| read committed (padrão) | monotonic atomic view | G0, G1a, G1b, G1c, OTV | PMP, **P4**, G-single, **G2-item**, **G2** |
| repeatable read | snapshot isolation | tudo acima mais PMP, **P4**, G-single | **G2-item**, **G2** |
| serializable | serializable | os dez | nenhum |

Leia os códigos em negrito como o plano da semana:

- **No nível padrão, o Postgres permite lost updates.** Esse é o lab de segunda-feira.
- **Repeatable read impede lost updates, mas permite write skew.** Esse é o lab de terça-feira, com a carteira conjunta.
- **Serializable impede os dois**, abortando uma transação com o erro 40001. Na terça você vai ver esse erro e aprender a fazer retry dele.

Um detalhe para lembrar: o lost update em read committed precisa do padrão read-modify-write da seção 3. A leitura de amanhã explica por que `UPDATE wallets SET balance = balance - 30` num único comando não perde a atualização, mesmo em read committed.

## 6. Preparando o lab de hoje

O lab pede que você reproduza um lost update em duas sessões de `psql` em READ COMMITTED e anote a sequência exata de comandos. Planeje antes de digitar:

1. Crie uma tabela pequena com uma carteira e um saldo conhecido.
2. Na sessão 1, inicie uma transação e leia o saldo com um `SELECT` simples.
3. Na sessão 2, faça o mesmo.
4. Na sessão 1, grave o novo saldo como um literal (o que o seu código calcularia) e faça commit.
5. Na sessão 2, grave o literal que ela calculou e faça commit.
6. Leia o saldo e compare com o que ele deveria ser.

Depois repita os mesmos passos com `BEGIN ISOLATION LEVEL REPEATABLE READ` nas duas sessões. O Hermitage e a documentação do Postgres preveem que agora a segunda escrita recebe `could not serialize access due to concurrent update` em vez de apagar a primeira em silêncio. Anote o texto completo do erro.

Se sobrar tempo, cole o exemplo do cheque especial do Kevin, da wiki, nas mesmas duas sessões, em repeatable read e depois em serializable.

## O que anotar hoje

1. Uma tabela com os quatro níveis de isolamento que você pode pedir ao Postgres (read uncommitted, read committed, repeatable read, serializable) e, para cada um, o que ele proíbe e o que ainda permite. Acrescente uma linha sobre o que o ACID promete de fato para um saldo, e quais regras de negócio continuam sendo trabalho seu.
2. Lost update x write skew x phantom, cada um em uma frase mais um exemplo de carteira. Depois monte seu próprio exemplo de write skew com saldos: duas linhas, uma regra que abrange as duas e a intercalação passo a passo que a quebra.
3. As três linhas do PostgreSQL na tabela do Hermitage, copiadas da fonte, com uma frase sobre o que surpreendeu você.
4. Do lab: a sequência exata de comandos que produziu o lost update e o erro que você viu em repeatable read.

## Teste-se

Estas perguntas dão bons flashcards (veja o [guia de flashcards](../../FLASHCARDS.pt-BR.md)).

- Qual é o nível de isolamento padrão no Postgres, e ele permite lost updates?
- Qual é a diferença entre um lost update e um write skew?
- Por que o first-committer-wins não impede write skew?
- O que o nível "repeatable read" do Postgres implementa de fato, segundo o Hermitage?
- Qual letra do ACID cobre a regra "o saldo somado de um casal nunca fica abaixo de zero"? Quem garante essa regra?
- A Tabela 13.1 diz que o repeatable read do Postgres não tem phantom reads. Por que uma verificação de limite diário ainda pode ser quebrada nesse nível?
- O que torna um histórico serializable, em termos do seu grafo de dependências?
- Qual SQLSTATE as duas mensagens de erro de serialização compartilham, e o que o seu código deve fazer com ele?

## Referências

- **Fonte principal:** Martin Kleppmann, ["Hermitage: testing transaction isolation levels"](https://github.com/ept/hermitage), repositório no GitHub. Leia a tabela de resultados do README, focando nas linhas do PostgreSQL, e depois abra o arquivo de testes `postgres.md` para ver os comandos exatos, sessão por sessão. Gratuito.
- **Fonte principal:** wiki do PostgreSQL, ["SSI"](https://wiki.postgresql.org/wiki/SSI). Leia o Overview, os três exemplos de "Simple Write Skew" (Black and White, Intersecting Data, Overdraft Protection) e "Deposit Report". Cada um é um roteiro sessão por sessão que você pode colar no `psql`. Gratuito.
- Justin Jaffray, ["What write skew looks like"](https://www.cockroachlabs.com/blog/what-write-skew-looks-like/), blog da Cockroach Labs, 2022. Leia tudo; a parte do grafo de dependências é a mais difícil e a mais útil. O artigo foca em write skew; lost updates e phantoms vêm do Hermitage e da documentação do Postgres. Gratuito.
- Documentação do PostgreSQL, ["Transaction Isolation"](https://www.postgresql.org/docs/current/transaction-iso.html) (seção 13.2). Hoje, leia a introdução, as definições dos fenômenos e a Tabela 13.1. Gratuito. Essa é a leitura principal de amanhã, então o resto da página pode esperar.
