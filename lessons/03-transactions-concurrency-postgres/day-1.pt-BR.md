# Módulo 3, segunda-feira: níveis de isolamento e as anomalias que eles permitem

[Módulo 3](../../modules/03-transactions-concurrency-postgres.pt-BR.md) · [Read in English](day-1.md)

**Tempo de leitura:** cerca de 45 minutos. Use o resto do bloco de 2 horas nas referências do final, começando pela tabela do Hermitage.

Este é um texto original escrito para este curso. Ele se baseia nas referências listadas no final, e cada seção indica a fonte que segue. Quando uma ideia vem de um autor específico, o texto diz isso.

## Por que isso importa para uma fintech

Uma carteira digital guarda dinheiro em linhas, e muitas requisições mexem nas mesmas linhas ao mesmo tempo. Um cliente toca duas vezes em "Pagar". Uma transferência Pix chega enquanto uma compra no cartão está sendo autorizada. Um job em lote cobra tarifas mensais enquanto o cliente transfere dinheiro para fora. Cada requisição está correta sozinha. Rodando juntas, o saldo pode terminar errado.

Bancos de dados prometem "transações", mas a promessa é mais fraca do que a maioria dos engenheiros imagina. O Postgres roda em READ COMMITTED por padrão, e esse nível deixa duas transferências corretas produzirem um saldo negativo. Esta semana é sobre saber exatamente qual anomalia cada nível permite e, depois, impedir saldo negativo de mais de um jeito. Hoje é a teoria: o vocabulário e o mapa.

## 1. O que o ACID promete de fato

*Fonte principal: Jepsen, mapa "Consistency Models", e documentação do PostgreSQL, seção 13.2.*

ACID são quatro letras, e cada uma promete uma coisa diferente. Leia pensando em uma transferência da carteira da Ana para a do Bruno: um débito, um crédito, uma transação.

| Letra | O que promete | O que não promete |
| --- | --- | --- |
| **Atomicidade** | Se a transação aborta, nenhuma das suas escritas permanece. O débito nunca fica sem o crédito. | Que a transação vai dar certo, ou que um retry é seguro. |
| **Consistência** | Constraints declaradas (`CHECK`, `UNIQUE`, chaves estrangeiras) valem depois de todo commit. | Regras de negócio que você não declarou, como "o saldo somado de um casal nunca fica abaixo de zero". Essas são trabalho do seu código. |
| **Isolamento** | Transações concorrentes ficam separadas no grau que o nível escolhido define. | Que todo nível se comporte como se as transações rodassem uma de cada vez. Só o serializable faz isso. |
| **Durabilidade** | Uma transação com commit sobrevive a uma queda. | Que uma réplica já a tenha (veja Módulo 1, terça-feira). |

A letra que mais esconde coisas é o **I**. Isolamento não é uma propriedade, e sim uma família delas, chamadas níveis de isolamento ou, no vocabulário mais amplo do Jepsen, modelos de consistência. O Jepsen descreve um modelo de consistência como "a safety property which declares what a system can do." Formalmente, um modelo é o conjunto de históricos (ordenações de leituras e escritas) que um sistema pode produzir. Um modelo mais fraco permite mais históricos, e alguns desses históricos quebram seus invariantes.

Então "roda dentro de uma transação" não responde a "isso pode ficar negativo?". A resposta real sempre cita um nível de isolamento e uma anomalia.

## 2. O mapa dos níveis de isolamento

*Fonte principal: Jepsen, mapa "Consistency Models" e as páginas "Read Committed" e "Snapshot Isolation".*

O mapa do Jepsen desenha os modelos como uma árvore em que uma seta significa "implica". A parte transacional da árvore, simplificada, fica assim:

```
strict serializable
        |
   serializable
     /        \
repeatable   snapshot
  read       isolation
     \        /
monotonic atomic view   (cursor stability também fica aqui)
        |
  read committed
        |
 read uncommitted
```

Dois fatos do mapa importam mais para esta semana:

- **Serializable implica snapshot isolation.** Todo histórico serializable também é um histórico snapshot válido, mas não o contrário.
- **Snapshot isolation e repeatable read são incomparáveis.** O Jepsen aponta que cada um permite um fenômeno que o outro proíbe. Isso importa porque o Postgres usa o nome "repeatable read" para algo que na verdade é snapshot isolation (seção 4).

**Read committed.** A página do Jepsen resume em uma linha: "transactions are not allowed to observe writes from transactions which do not commit." Ele proíbe dirty writes (P0: sobrescrever a escrita sem commit de outra transação) e dirty reads (P1: ler a escrita sem commit de outra transação). Ele permite fuzzy reads (P2: você lê uma linha, alguém faz commit de uma mudança, você lê de novo e vê outro valor) e phantoms (P3: você consulta um conjunto de linhas, alguém faz commit de uma linha nova que bate com a condição, e o seu conjunto muda). O Jepsen observa que read committed pode ser totalmente disponível, ou seja, todo nó consegue continuar trabalhando durante uma partição de rede.

**Snapshot isolation.** A definição do Jepsen: "In a snapshot isolated system, each transaction appears to operate on an independent, consistent snapshot of the database." Sua transação lê de uma foto congelada tirada quando ela começa. As escritas dela ficam invisíveis até o commit, e aí aparecem todas de uma vez. Snapshot isolation também tem uma regra de **first-committer-wins**: se duas transações concorrentes escrevem o mesmo objeto, a segunda a fazer commit precisa abortar. Essa regra é o que impede lost updates. Snapshot isolation não pode ser totalmente disponível, então, em uma partição, alguns nós precisam parar.

O que snapshot isolation ainda permite é o assunto da seção 3. A página do Jepsen é direta: "The most notable phenomena allowed by snapshot isolation are write skews".

**Serializable.** Todo resultado com commit equivale a rodar as transações uma de cada vez, em alguma ordem. Nada da lista de anomalias pode acontecer.

## 3. Lost update, write skew e phantoms, em termos de carteira

*Fontes principais: Justin Jaffray, "What write skew looks like" (blog da Cockroach Labs), para write skew; documentação do PostgreSQL, seção 13.2, para as definições dos fenômenos.*

Essas três anomalias são as que quebram saldos. Aprenda como três histórias, cada uma com duas transações concorrentes T1 e T2.

**Lost update.** A carteira da Ana tem 100. Duas compras de 30 e 50 rodam ao mesmo tempo. As duas transações leem o saldo para a memória da aplicação, calculam um novo valor e gravam de volta.

| Passo | T1 (compra de 30) | T2 (compra de 50) |
| --- | --- | --- |
| 1 | `SELECT balance` → 100 | |
| 2 | | `SELECT balance` → 100 |
| 3 | `UPDATE ... SET balance = 70` | |
| 4 | `COMMIT` | |
| 5 | | `UPDATE ... SET balance = 50` (espera, depois roda) |
| 6 | | `COMMIT` |

O saldo final é 50. A compra de 30 aconteceu, mas o débito dela foi sobrescrito. As duas transações escreveram na **mesma linha**, e a segunda escrita apagou a primeira. Esse é o bug clássico de read-modify-write, e ele mora no código da aplicação que lê um valor, faz a conta em TypeScript e grava o resultado.

**Write skew.** Carla e Diego têm um plano conjunto: duas carteiras, A e B, com a regra "A + B precisa ficar em zero ou acima". A tem 100 e B tem 0. Carla saca 100 de A enquanto Diego saca 100 de B. Cada transação lê os dois saldos, verifica a regra contra o seu snapshot e escreve só na própria carteira.

| Passo | T1 (Carla, de A) | T2 (Diego, de B) |
| --- | --- | --- |
| 1 | lê A=100, B=0; soma 100 ≥ 100, OK | |
| 2 | | lê A=100, B=0; soma 100 ≥ 100, OK |
| 3 | `UPDATE carteira A` → 0 | |
| 4 | | `UPDATE carteira B` → -100 |
| 5 | `COMMIT` | `COMMIT` |

A soma agora é -100. Nenhuma transação quebrou a regra sozinha, e elas escreveram em **linhas diferentes**, então o first-committer-wins não vê conflito. O artigo de Jaffray explica a forma geral: duas transações concorrentes leem dados que se sobrepõem, escrevem em lugares disjuntos e as duas fazem commit, com um resultado que nenhuma ordem serial produziria. O exemplo dele é abstrato e vale a leitura: a transação P copia o registrador x para y, a transação Q copia y para x, e sob snapshot isolation os dois valores acabam trocados. Nas palavras dele, esse é "an outcome not possible in either serial execution."

**Phantom.** A documentação do Postgres define phantom read como reexecutar uma consulta com uma condição de busca e encontrar um conjunto diferente de linhas porque outra transação fez commit. Em uma carteira, o caso perigoso é uma verificação que lê um **conjunto** de linhas e depois insere uma nova. Digamos que o limite diário de Pix seja 1.000. T1 soma as transferências do dia (800), vê espaço para 200 e insere uma transferência de 200. T2 faz o mesmo ao mesmo tempo com outros 200. As duas fazem commit, e o dia termina em 1.200. Nenhuma linha existente foi atualizada pelas duas. O conflito é sobre uma linha que ainda não existia quando cada uma leu. O Hermitage chama isso de "write skew on predicate read" (G2), em oposição a write skew sobre linhas que já existem (G2-item).

Um jeito rápido de diferenciar:

| Anomalia | As duas transações escrevem... | O que a verificação leu | Bug típico de carteira |
| --- | --- | --- | --- |
| Lost update | a mesma linha | essa mesma linha | ler saldo, subtrair no código, gravar de volta |
| Write skew | linhas diferentes | linhas que a outra escreve | limite compartilhado entre duas carteiras |
| Phantom (G2) | linhas novas | um conjunto definido por uma condição | limite diário somando transferências |

## 4. Por que serializable resolve o write skew

*Fonte principal: Justin Jaffray, "What write skew looks like", seções "Who cares?" e "When is Snapshot not Serializable?".*

O artigo de Jaffray explica a teoria por trás da solução, e vale conhecê-la para entrevistas.

Desenhe cada transação como um nó. Adicione uma aresta quando uma transação depende de outra. Há três tipos de dependência: **wr** (T2 lê o que T1 escreveu), **ww** (T2 sobrescreve o que T1 escreveu) e **rw**, também chamada de antidependência (T1 leu um valor que T2 depois sobrescreveu, então T1 precisa vir antes de T2). Jaffray enuncia o resultado central: "A history is serializable if and only if its serialization graph has no cycles."

Na história da carteira conjunta, T1 leu B e T2 escreveu B, então T1 precisa vir antes de T2. T2 leu A e T1 escreveu A, então T2 precisa vir antes de T1. Isso é um ciclo de duas arestas rw, e não existe ordem serial.

Jaffray também observa que, entre transações snapshot concorrentes, a única dependência possível é rw. Ele cita um teorema de Fekete e colegas: todo ciclo em um histórico snapshot contém duas arestas rw consecutivas. O **Serializable Snapshot Isolation (SSI)** do Postgres usa esse resultado. Ele rastreia dependências rw e, quando vê um padrão perigoso, aborta uma transação. Às vezes ele aborta uma transação que não fazia parte de um ciclo de verdade, e esse é o preço de verificar de forma barata.

A razão prática para preferir serializable é o que Jaffray chama de raciocínio local. Sob serializable, "it's sufficient to verify that every individual transaction maintains this invariant on its own". Sob níveis mais fracos, "one must consider the interactions between every transaction to ensure said invariants are upheld". Para uma carteira com dezenas de operações que mexem em saldo, essa diferença é enorme. Sob serializable, você revisa cada operação uma vez. Sob snapshot isolation, precisa revisar cada par.

## 5. O que o Postgres entrega de fato

*Fonte principal: Martin Kleppmann, repositório Hermitage, linhas do PostgreSQL na tabela de resultados.*

O Hermitage é um conjunto de testes que Kleppmann escreveu para verificar quais anomalias cada banco realmente impede em cada nível de isolamento. O README dele parte de uma observação direta: "Unfortunately, those weaker isolation levels are quite poorly understood." Ele acrescenta que a documentação dos fornecedores sobre eles é "frustratingly vague". Cada teste é uma sequência de comandos SQL digitados em duas ou mais sessões, então você consegue reproduzir qualquer linha com duas janelas de `psql`.

Kleppmann baseia o projeto na definição formal de isolamento fraco de Adya, estendida por Bailis e colegas, e é daí que vêm os códigos de anomalia. Os que importam aqui:

| Código | Nome no Hermitage | Significado na carteira |
| --- | --- | --- |
| G0 | write cycles (dirty writes) | duas transferências intercalam escritas nas mesmas linhas |
| G1a, G1b, G1c | dirty reads | você vê um débito que depois sofre rollback |
| P4 | lost update | seção 3 |
| G-single | read skew | um extrato mostra A depois de uma transferência e B antes dela |
| G2-item | write skew on disjoint read | regra da carteira conjunta |
| G2 | write skew on predicate read | limite diário somando linhas |

As linhas do PostgreSQL, como o Hermitage as reporta:

| Nível que você pede | O que ele é de fato | Impede | Permite |
| --- | --- | --- | --- |
| read committed (padrão) | monotonic atomic view | G0, G1a, G1b, G1c, OTV | PMP, **P4**, G-single, **G2-item**, **G2** |
| repeatable read | snapshot isolation | tudo acima mais PMP, **P4**, G-single | **G2-item**, **G2** |
| serializable | serializable | as dez | nenhuma |

Leia os códigos em negrito como o plano desta semana:

- **No nível padrão, o Postgres permite lost updates.** Esse é o lab de segunda-feira.
- **Repeatable read impede lost updates, mas permite write skew.** Esse é o lab de terça-feira, com a carteira conjunta.
- **Serializable impede os dois**, abortando uma transação com o erro 40001. Na terça você vai ver esse erro e aprender a fazer retry dele.

Um detalhe para guardar: o lost update em read committed precisa do padrão read-modify-write da seção 3. A leitura de amanhã explica por que `UPDATE wallets SET balance = balance - 30` em um único comando não perde a atualização, nem em read committed.

## 6. Preparando o lab de hoje

O lab pede que você reproduza um lost update em duas sessões de `psql` sob READ COMMITTED e anote a sequência exata de comandos. Planeje antes de digitar:

1. Crie uma tabela pequena com uma carteira e um saldo conhecido.
2. Na sessão 1, abra uma transação e leia o saldo com um `SELECT` simples.
3. Na sessão 2, faça o mesmo.
4. Na sessão 1, grave o novo saldo como um literal (o que o seu código calcularia) e faça commit.
5. Na sessão 2, grave o literal que ela calculou e faça commit.
6. Leia o saldo e compare com o que ele deveria ser.

Depois repita os mesmos passos com `BEGIN ISOLATION LEVEL REPEATABLE READ` nas duas sessões. O Hermitage prevê que agora a segunda escrita recebe um erro em vez de apagar a primeira em silêncio. Anote o texto do erro; a leitura de amanhã dá nome a ele.

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
- O que é um phantom, e qual verificação de carteira fica exposta a ele?
- O que torna um histórico serializable, em termos do seu grafo de dependências?

## Referências

- **Fonte principal:** Martin Kleppmann, ["Hermitage: testing transaction isolation levels"](https://github.com/ept/hermitage), repositório no GitHub. Leia a tabela de resultados do README, focando nas linhas do PostgreSQL, e depois abra o arquivo de testes `postgres.md` para ver os comandos exatos, sessão por sessão. Gratuito.
- Jepsen, mapa ["Consistency Models"](https://jepsen.io/consistency), mais as páginas dos modelos ["Read Committed"](https://jepsen.io/consistency/models/read-committed) e ["Snapshot Isolation"](https://jepsen.io/consistency/models/snapshot-isolation). Leia o mapa primeiro e depois as duas páginas, pulando as definições formais na primeira passada. Gratuito.
- Justin Jaffray, ["What write skew looks like"](https://www.cockroachlabs.com/blog/what-write-skew-looks-like/), blog da Cockroach Labs, 2022. Leia tudo; a parte do grafo de dependências é a mais difícil e a mais útil. O artigo foca em write skew; lost updates e phantoms vêm do Hermitage e da documentação do Postgres. Gratuito.
- Documentação do PostgreSQL, ["Transaction Isolation"](https://www.postgresql.org/docs/current/transaction-iso.html) (seção 13.2), Tabela 13.1 e as definições acima dela. Gratuito. Essa é a leitura principal de amanhã; hoje, leia só a tabela.
