# Módulo 3, terça-feira: isolamento, locks e retries no Postgres

[Módulo 3](../../modules/03-transactions-concurrency-postgres.pt-BR.md) · [Read in English](day-2.md)

**Tempo de leitura:** cerca de 45 minutos. Use o resto do bloco de 2 horas nas referências do final, começando pela seção 13.2 da documentação do Postgres.

Este é um texto original escrito para este curso. Ele se baseia nas referências listadas no final, e cada seção indica a fonte que segue.

## Por que isso importa para uma fintech

Ontem você recebeu o mapa: qual anomalia cada nível de isolamento permite. Hoje o assunto são as ferramentas que o Postgres oferece para impedi-las. Há três famílias: escolher um nível de isolamento mais forte e fazer retry, travar linhas explicitamente, ou escrever a verificação dentro do próprio `UPDATE`. O TCM de quinta-feira constrói uma transferência com cada uma delas, então hoje você precisa saber exatamente como cada uma se comporta sob concorrência, qual erro ela lança e o que o seu código NestJS deve fazer quando esse erro chega.

## 1. MVCC: todo comando lê um snapshot

*Fonte principal: documentação do PostgreSQL, seção 13.1 "Introduction".*

O Postgres não protege leituras com locks. Ele mantém várias versões de cada linha e mostra a cada comando um **snapshot**: o banco como ele estava em algum momento. A documentação chama isso de Multiversion Concurrency Control (MVCC) e cita sua principal vantagem: "reading never blocks writing and writing never blocks reading."

Para uma carteira, isso significa que uma consulta longa de extrato nunca bloqueia uma transferência, e uma transferência nunca bloqueia o extrato. Também significa que duas transações podem olhar para o "mesmo" saldo e ver valores diferentes, dependendo de quando cada snapshot foi tirado. Todo nível de isolamento no Postgres é uma regra sobre **quando o snapshot é tirado** e **o que acontece quando duas transações escrevem na mesma linha**.

A documentação acrescenta que locks explícitos de tabela e de linha existem "for applications which don't generally need full transaction isolation and prefer to explicitly manage particular points of conflict", e que advisory locks estão disponíveis para locks que não ficam presos a uma única transação. As seções 5 a 7 tratam dos dois.

## 2. Read committed: um snapshot novo a cada comando

*Fonte principal: documentação do PostgreSQL, seção 13.2.1 "Read Committed Isolation Level".*

Read committed é o padrão. Nas palavras da documentação, "a `SELECT` query sees a snapshot of the database as of the instant the query begins to run." Dois `SELECT`s na mesma transação podem ver dados diferentes se outra transação fizer commit entre eles.

A parte importante é o que acontece quando um `UPDATE` encontra uma linha que outra transação está alterando:

1. Ele **espera** a outra transação fazer commit ou rollback.
2. Se a outra fizer commit, ele pega a **versão nova** da linha.
3. Ele **reavalia a cláusula `WHERE`** contra essa versão nova e só aplica a mudança se a linha ainda atender à condição.

Essa regra explica duas coisas de que você precisa no TCM.

Primeiro, um débito em um único comando não perde atualizações:

```sql
UPDATE wallets SET balance = balance - 30 WHERE id = $1;
```

A segunda transação espera e depois subtrai do saldo que a primeira deixou. O lost update de ontem precisava que o valor passasse pela memória da aplicação (`SELECT`, conta em TypeScript, `UPDATE ... SET balance = 70`). A documentação usa uma transferência bancária como exemplo desse caso seguro: como cada comando afeta uma linha predeterminada, ver a versão atualizada "does not create any troublesome inconsistency."

Segundo, um **update condicional** é seguro contra saldo negativo no nível padrão:

```sql
UPDATE wallets
   SET balance = balance - $2
 WHERE id = $1 AND balance >= $2;
-- confira o número de linhas afetadas: 0 significa saldo insuficiente (ou carteira inexistente)
```

Se dois débitos disputam os últimos 100, o segundo espera, reavalia `balance >= $2` contra o saldo novo e não atinge nenhuma linha. Essa é a versão 3 do TCM. Seu código precisa ler o número de linhas afetadas (no node-postgres, `result.rowCount`) e transformar 0 em um erro de negócio.

A documentação também avisa sobre o limite desse comportamento. O exemplo dela é um `DELETE ... WHERE hits = 10` que, em silêncio, não faz nada porque um `UPDATE` concorrente mudou o valor de 9 para 10 e de 10 para 11 por baixo dele. A conclusão: read committed é "unsuitable for commands that involve complex search conditions; however, it is just right for simpler cases." Uma verificação sobre o saldo de uma linha é um caso simples. Uma verificação que soma várias linhas não é.

## 3. Repeatable read: um snapshot para a transação inteira

*Fonte principal: documentação do PostgreSQL, seção 13.2.2 "Repeatable Read Isolation Level".*

Em repeatable read, o snapshot é tirado no primeiro comando de verdade da transação e mantido até o fim. Todas as suas leituras concordam entre si, que é o que um extrato ou um relatório de conciliação precisa.

Quando uma transação repeatable read tenta atualizar uma linha que outra transação alterou e com commit depois do snapshot, o Postgres não reavalia. Ele aborta:

```
ERROR:  could not serialize access due to concurrent update
```

Esse é o erro que você viu no fim do lab de ontem, e é assim que repeatable read impede lost updates. A documentação é explícita sobre a consequência: "Applications using this level must be prepared to retry transactions due to serialization failures." Ela também observa que transações somente leitura nunca recebem esse conflito.

A documentação confirma o que o Hermitage mostrou: esse nível "is implemented using a technique known in academic database literature and in some other database products as *Snapshot Isolation*." E avisa exatamente sobre o caso da carteira conjunta: regras de negócio garantidas nesse nível "are not likely to work correctly without careful use of explicit locks to block conflicting transactions." Carla e Diego atualizam cada um uma linha diferente, então nenhum dos dois recebe o erro, e o saldo somado fica negativo. Esse é o lab de hoje.

## 4. Serializable e o loop de retry do 40001

*Fontes principais: documentação do PostgreSQL, seções 13.2.3 "Serializable Isolation Level" e 13.5 "Serialization Failure Handling".*

Serializable "works exactly the same as Repeatable Read except that it also monitors for conditions" que poderiam produzir um resultado que nenhuma ordem serial produziria. O Postgres implementa isso como Serializable Snapshot Isolation, o SSI da leitura de ontem. Para rastrear o que cada transação leu, ele usa **predicate locks**, visíveis em `pg_locks` com modo `SIReadLock`. Esses locks nunca bloqueiam ninguém e nunca podem causar deadlock. Eles são contabilidade, usada para detectar padrões perigosos de leitura e escrita.

O exemplo da própria documentação são duas transações em que cada uma soma uma classe de linhas e insere o resultado na outra classe. As duas fariam commit em repeatable read. Em serializable, uma falha com:

```
ERROR:  could not serialize access due to read/write dependencies among transactions
```

Rode as transações da carteira conjunta em serializable e uma delas falha do mesmo jeito. A seção 13.5 explica como tratar esses erros:

- Toda serialization failure tem SQLSTATE **`40001`** (`serialization_failure`), seja qual for a mensagem. A documentação recomenda fazer retry desses erros sem condição.
- Deadlocks (`40P01`, `deadlock_detected`) também podem valer um retry.
- Violações de unicidade (`23505`) só merecem retry em alguns casos, porque podem ser um erro persistente e não um erro transitório.
- Faça retry **da transação inteira**, "including all logic that decides which SQL to issue and/or which values to use." É por isso que o Postgres não tem retry automático: ele não consegue reexecutar o seu TypeScript.
- Um retry pode falhar de novo. Sob muita contenção, pode levar muitas tentativas, então limite o número delas.

Em um serviço NestJS com node-postgres, a forma é esta:

```ts
import { Pool, PoolClient } from 'pg';

const RETRYABLE = new Set(['40001', '40P01']);

export async function inSerializable<T>(
  pool: Pool,
  work: (client: PoolClient) => Promise<T>,
  maxAttempts = 5,
): Promise<T> {
  for (let attempt = 1; ; attempt++) {
    const client = await pool.connect();
    try {
      await client.query('BEGIN ISOLATION LEVEL SERIALIZABLE');
      const result = await work(client); // relê os saldos a cada tentativa
      await client.query('COMMIT');
      return result;
    } catch (err: any) {
      await client.query('ROLLBACK').catch(() => undefined);
      if (!RETRYABLE.has(err.code) || attempt >= maxAttempts) throw err;
      await new Promise((r) => setTimeout(r, Math.random() * 20 * attempt));
    } finally {
      client.release();
    }
  }
}
```

Repare que o erro pode chegar em um `UPDATE` ou no `COMMIT`, então o bloco catch cobre os dois. A documentação também traz uma regra sutil: dados lidos em uma transação serializable não devem ser considerados válidos até essa transação fazer commit. Não mande uma push notification com um saldo lido no meio do caminho.

A documentação lista conselhos de desempenho para sistemas serializable. Os itens que mais importam para uma carteira: declare transações como `READ ONLY` quando possível, controle o número de conexões ativas com um pool, não coloque numa transação mais do que a integridade exige e não deixe sessões "idle in transaction". Ela também observa que um sequential scan sempre pega um predicate lock no nível da relação, o que pode aumentar a taxa de falhas. Bons índices ajudam o serializable, mais um motivo para o assunto de amanhã.

## 5. Locks de linha: SELECT ... FOR UPDATE e companhia

*Fontes principais: documentação do PostgreSQL, seção 13.3.2 "Row-Level Locks", e a "Locking Clause" da página de referência do `SELECT`.*

A outra família é pessimista: trave as linhas primeiro, depois leia e escreva. `SELECT ... FOR UPDATE` trava as linhas retornadas para que outras transações que tentem atualizá-las, apagá-las ou travá-las esperem até você terminar.

Existem quatro modos de lock de linha. Só dois aparecem com frequência em uma carteira:

| Modo | Use quando | Bloqueia |
| --- | --- | --- |
| `FOR UPDATE` | você vai alterar a linha, ou precisa que ninguém mais altere | todos os outros modos de lock de linha e todo `UPDATE`/`DELETE` |
| `FOR NO KEY UPDATE` | pego automaticamente por um `UPDATE` comum que não muda uma chave | `FOR SHARE`, `FOR NO KEY UPDATE`, `FOR UPDATE` |
| `FOR SHARE` | você precisa que a linha não mude enquanto lê | updates e locks exclusivos, não outros shares |
| `FOR KEY SHARE` | (pego por verificações de chave estrangeira) | só `FOR UPDATE` e mudanças de chave |

A versão 1 do TCM trava as duas carteiras de uma transferência antes de mexer nelas:

```sql
BEGIN;
SELECT id, balance FROM wallets
 WHERE id IN ($1, $2)
 ORDER BY id
   FOR UPDATE;
-- verifique o saldo de origem no código, depois os dois UPDATEs e os inserts no ledger
COMMIT;
```

Dois detalhes da documentação. Em repeatable read ou serializable, travar uma linha que outra transação alterou desde o início da sua transação lança um erro, então esse padrão costuma rodar em read committed. E a referência do `SELECT` tem uma ressalva: em read committed, `ORDER BY` com uma cláusula de lock pode retornar linhas fora de ordem, porque a ordenação acontece primeiro e as linhas são travadas conforme saem dela. Se uma coluna de ordenação mudar enquanto você espera o lock, o resultado pode voltar fora de ordem. IDs de carteira nunca mudam, então `ORDER BY id` mantém a ordem dos locks consistente. Se quiser que a ordem fique óbvia para quem revisa, trave as duas linhas em dois comandos separados, menor id primeiro.

A página do `SELECT` também documenta duas opções que evitam esperar:

- **`NOWAIT`**: reporta um erro na hora se uma linha já estiver travada. Útil quando esperar estouraria um orçamento de latência.
- **`SKIP LOCKED`**: pula as linhas travadas. A documentação diz que isso dá "an inconsistent view of the data", então não serve para trabalho geral, mas encaixa em "multiple consumers accessing a queue-like table". É exatamente o worker do outbox do Módulo 4: vários workers pegam, cada um, o próximo lote de mensagens pendentes não travadas sem pisar um no outro. Nunca use para saldos.

## 6. Deadlocks e ordem de aquisição

*Fonte principal: documentação do PostgreSQL, seção 13.3.4 "Deadlocks".*

O exemplo de deadlock da documentação é uma transferência, o que mostra como é natural escrever um. A transação 1 credita a conta 11111. A transação 2 credita a 22222, depois tenta debitar a 11111 e espera a transação 1. A transação 1 então tenta debitar a 22222 e espera a transação 2. Cada uma espera a outra para sempre.

Em uma carteira, isso acontece sempre que Ana paga Bruno enquanto Bruno paga Ana, e cada transferência trava "origem primeiro, depois destino". O Postgres detecta o ciclo e aborta uma das transações com SQLSTATE `40P01`. Qual delas é abortada "is difficult to predict and should not be relied upon."

A documentação dá a cura: "The best defense against deadlocks is generally to avoid them by being certain that all applications using a database acquire locks on multiple objects in a consistent order." Para transferências, essa ordem é o id da carteira: sempre trave primeiro o menor id, seja ele a origem ou o destino. A documentação acrescenta mais duas regras que valem ir para as suas anotações:

- Pegue o lock mais restritivo de que vai precisar na primeira vez que travar uma linha. Travar com `FOR SHARE` e depois subir para `FOR UPDATE` convida deadlocks.
- Uma transação esperando um lock espera indefinidamente, a menos que um deadlock seja detectado. Nunca mantenha uma transação aberta enquanto chama o banco parceiro ou espera um usuário. Configure `lock_timeout` ou `statement_timeout` se precisar de um limite.

## 7. Advisory locks

*Fontes principais: documentação do PostgreSQL, seção 13.3.5 "Advisory Locks", e seção 9.28.10 "Advisory Lock Functions".*

Advisory locks travam um **número** que você escolhe, não uma linha. A documentação os chama de advisory "because the system does not enforce their use": todo trecho de código precisa concordar em pegar o lock. As funções recebem uma chave `bigint` (ou duas chaves `integer`):

| Função | Escopo | Se o lock já estiver pego |
| --- | --- | --- |
| `pg_advisory_xact_lock(key)` | até o fim da transação | espera |
| `pg_try_advisory_xact_lock(key)` | até o fim da transação | retorna `false` |
| `pg_advisory_lock(key)` | até `pg_advisory_unlock` ou o fim da sessão | espera |
| `pg_try_advisory_lock(key)` | igual ao anterior | retorna `false` |

Prefira as versões de nível de transação. Locks de nível de sessão ignoram a semântica de transação: um lock pego em uma transação que sofre rollback continua pego depois. Com um pool de conexões, um lock de sessão esquecido fica preso numa conexão do pool e bloqueia quem precisar dele em seguida.

Um bom uso numa carteira: garantir que só uma instância do job diário de conciliação rode, com `SELECT pg_try_advisory_lock(42)` na inicialização. Um uso ruim: proteger saldos, já que qualquer caminho de código que esqueça a chamada fica desprotegido. A documentação também avisa contra chamar a função de lock em uma consulta com `LIMIT`, porque o limite pode ser aplicado depois que alguns locks já foram pegos.

## 8. As três formas de impedir saldo negativo

Esta tabela prepara a quinta-feira. Preencha os números medidos na sexta.

| Versão | Mecanismo | Sob contenção | Falha que seu código trata |
| --- | --- | --- | --- |
| v1 pessimista | `SELECT ... FOR UPDATE` nas duas carteiras, em ordem de id | transferências fazem fila atrás do lock | deadlock (`40P01`) se a ordem estiver errada; esperas por lock |
| v2 otimista | ler `version`, depois `UPDATE ... WHERE id = $1 AND version = $2`, retries limitados | ninguém espera, mas conflitos causam retries | 0 linhas atualizadas significa que outro ganhou: retry ou desistir |
| v3 condicional | `UPDATE ... WHERE balance >= $amount`, conferir número de linhas | cada update espera pouco pela linha | 0 linhas significa saldo insuficiente |

A coluna de versão otimista é um padrão geral, não um recurso do Postgres: você adiciona um inteiro `version`, incrementa a cada escrita e trata "0 linhas atualizadas" como conflito. Uma quarta opção, rodar tudo em serializable com o loop de retry da seção 4, é a única que também protege regras que abrangem várias linhas, como a carteira conjunta.

## O que anotar hoje

1. Os quatro níveis de isolamento como o Postgres os implementa: quando o snapshot é tirado, o que acontece num conflito de escrita e qual erro aparece. Inclua o SQLSTATE `40001`, os dois textos de erro e a regra "faça retry da transação inteira, com limite".
2. Sua política de retry: quais SQLSTATEs você trata com retry, quantas tentativas, qual backoff, e por que a lógica que lê os saldos precisa rodar de novo.
3. Quando usar `SELECT ... FOR UPDATE`, `NOWAIT`, `SKIP LOCKED` e advisory locks, com um exemplo de carteira para cada.
4. O deadlock entre duas transferências opostas, desenhado em duas colunas, e a regra de ordem de aquisição que o impede.
5. Do lab: o write skew da carteira conjunta em repeatable read (saldos finais) e o erro exato em serializable.

## Teste-se

Estas perguntas dão bons flashcards (veja o [guia de flashcards](../../FLASHCARDS.pt-BR.md)).

- Em read committed, por que `UPDATE ... SET balance = balance - 30` não perde uma atualização?
- O que um `UPDATE` em read committed faz quando a linha que ele mira foi alterada por uma transação que acabou de fazer commit?
- Qual SQLSTATE marca uma serialization failure, e o que exatamente você precisa repetir no retry?
- Por que repeatable read no Postgres não impede o write skew da carteira conjunta?
- Para que serve `SKIP LOCKED`, e por que não para saldos?
- Como você evita deadlocks entre duas transferências opostas?
- Por que advisory locks de nível de transação são mais seguros que os de nível de sessão atrás de um pool de conexões?

## Referências

- **Fonte principal:** documentação do PostgreSQL, ["Concurrency Control"](https://www.postgresql.org/docs/current/mvcc.html), seções [13.1 "Introduction"](https://www.postgresql.org/docs/current/mvcc-intro.html) e [13.2 "Transaction Isolation"](https://www.postgresql.org/docs/current/transaction-iso.html). Leia a 13.2 inteira, incluindo os conselhos de desempenho para serializable. Gratuito.
- Documentação do PostgreSQL, ["Explicit Locking"](https://www.postgresql.org/docs/current/explicit-locking.html) (seção 13.3). Leia 13.3.2 (locks de linha), 13.3.4 (deadlocks) e 13.3.5 (advisory locks); passe os olhos na tabela de locks de tabela. Gratuito.
- Documentação do PostgreSQL, ["Serialization Failure Handling"](https://www.postgresql.org/docs/current/mvcc-serialization-failure-handling.html) (seção 13.5). Curta; leia inteira. Gratuito.
- Documentação do PostgreSQL, [referência do `SELECT`, "The Locking Clause"](https://www.postgresql.org/docs/current/sql-select.html), para `NOWAIT`, `SKIP LOCKED` e a ressalva sobre `ORDER BY`. Gratuito.
- Documentação do PostgreSQL, ["Advisory Lock Functions"](https://www.postgresql.org/docs/current/functions-admin.html#FUNCTIONS-ADVISORY-LOCKS) (seção 9.28.10). Gratuito.
- Documentação do PostgreSQL, ["Data Consistency Checks at the Application Level"](https://www.postgresql.org/docs/current/applevel-consistency.html) (seção 13.4), se sobrar tempo: quando confiar no serializable e quando em locks explícitos. Gratuito.
