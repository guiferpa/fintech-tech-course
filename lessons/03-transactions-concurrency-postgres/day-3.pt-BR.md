# Módulo 3, quarta-feira: locks distribuídos, índices e vacuum

[Módulo 3](../../modules/03-transactions-concurrency-postgres.pt-BR.md) · [Read in English](day-3.md)

**Tempo de leitura:** cerca de 45 minutos. Use o resto do bloco de 2 horas nas referências do final, começando pelo artigo de Kleppmann.

Este é um texto original escrito para este curso. Ele se baseia nas referências listadas no final, e cada seção indica a fonte que segue. Quando uma ideia vem de um autor específico, o texto diz isso.

## Por que isso importa para uma fintech

Cedo ou tarde alguém do time propõe um lock no Redis: "trava a carteira no Redis e depois faz a transferência". Parece mais simples que níveis de isolamento. A primeira leitura de hoje explica por que um lock fora do banco de dados nunca pode ser a garantia final para dinheiro, e como essa garantia deve ser.

O resto do dia trata das mesmas tabelas do Postgres sob carga real. Uma consulta de extrato que lê milhões de lançamentos fica lenta sem o índice certo. Uma linha de saldo atualizada milhares de vezes por dia deixa milhares de versões mortas para trás. O TCM de quinta-feira mede as duas coisas, então hoje você aprende a ler um plano de execução e a explicar por que o vacuum existe.

## 1. Dois motivos para querer um lock

*Fonte principal: Martin Kleppmann, "How to do distributed locking", seção "What are you using that lock for?".*

Kleppmann começa perguntando para que serve o lock. Ele separa dois casos:

- **Eficiência.** O lock impede que dois workers façam o mesmo trabalho duas vezes. Se ele falhar, você paga um custo pequeno: um relatório gerado duas vezes, um e-mail duplicado. Exemplo: só uma instância do job noturno de conciliação deve rodar.
- **Corretude.** O lock impede que dois processos escrevam ao mesmo tempo e corrompam dados. Se ele falhar, os dados ficam errados. Exemplo: duas transferências debitando a mesma carteira.

Essa distinção guia todo o resto. O conselho de Kleppmann para o primeiro caso: "if you are using locks merely for efficiency purposes, it is unnecessary to incur the cost and complexity of Redlock". Um único nó Redis basta. Para o segundo caso, a resposta dele é que o lock sozinho nunca basta, seja qual for o serviço que o fornece.

## 2. Um lock no Redis e suas premissas de tempo

*Fonte principal: Martin Kleppmann, "How to do distributed locking", seções "What are you using that lock for?" e "The synchrony assumptions of Redlock".*

O lock Redis de nó único mais comum usa o comando `SET` com duas opções: `NX` (só grava se a chave não existir) e `PX` (expira depois de um número de milissegundos). Kleppmann descreve o padrão como "conditional set-if-not-exists to obtain a lock, atomic delete-if-value-matches to release a lock":

```
SET lock:wallet:42 <random-owner-id> NX PX 10000
```

A expiração existe porque um cliente pode cair segurando o lock, e ninguém nunca o liberaria. O valor aleatório permite que o dono libere só o próprio lock, normalmente com um pequeno script Lua que apaga a chave apenas se o valor ainda bater.

O Redlock é a variante com vários nós, que pega o mesmo lock numa maioria de nós Redis independentes. A principal crítica de Kleppmann é sobre tempo. A segurança dele depende de atraso de rede limitado, pausas de processo limitadas e erro de relógio limitado, e ele argumenta que "Redlock works correctly only if you assume a synchronous system model". O Módulo 1 mostrou que sistemas reais são, no máximo, parcialmente síncronos: relógios pulam quando o NTP os ajusta em degrau, e processos pausam. Quando essas premissas quebram, dois clientes podem acreditar que têm o mesmo lock.

## 3. O cliente pausado e os fencing tokens

*Fonte principal: Martin Kleppmann, "How to do distributed locking", seções "Protecting a resource with a lock" e "Making the lock safe with fencing".*

O exemplo central de Kleppmann vale para qualquer serviço de lock, não só o Redis. Traduzido para uma carteira:

1. O worker 1 pega o lock da carteira 42, com um lease de 10 segundos.
2. O worker 1 sofre uma pausa longa de garbage collection (ou o container dele é estrangulado).
3. O lease expira. O worker 2 pega o lock, debita a carteira e termina.
4. O worker 1 acorda. Do ponto de vista dele, ainda tem o lock. Ele grava o saldo que calculou antes da pausa.

O débito do worker 2 se perde, e nada no serviço de lock poderia impedir isso. Kleppmann é explícito: "You cannot fix this problem by inserting a check on the lock expiry just before writing back to storage." A pausa pode acontecer entre a verificação e a escrita, e pacotes de rede também podem atrasar. O veredito de Kleppmann sobre o padrão ingênuo: ele é "fundamentally unsafe, no matter what lock service you use."

A solução dele é o **fencing token**: "a number that increases (e.g. incremented by the lock service) every time a client acquires the lock." No exemplo dele, o cliente 1 recebe o token 33 e pausa, o cliente 2 recebe o token 34 e escreve. Quando o cliente 1 finalmente escreve com o token 33, o storage rejeita, porque já viu o 34. O ponto crucial é quem faz a verificação: "this requires the storage server to take an active role in checking tokens".

Para uma carteira, o "storage server" é o Postgres, e ele consegue verificar muito mais que um token. Este é um jeito de aplicar a ideia de Kleppmann, com o token guardado na linha:

```sql
UPDATE wallets
   SET balance = balance - $2, fence = $3
 WHERE id = $1 AND fence < $3 AND balance >= $2;
-- 0 linhas: ou um dono mais novo do lock já escreveu, ou o saldo é insuficiente
```

Neste ponto, repare que a cláusula `WHERE` sozinha já impede o saldo negativo. Essa é a lição para levar às entrevistas: **a garantia final para dinheiro fica no banco de dados**, num update condicional, num lock de linha, numa transação serializable ou numa constraint como `CHECK (balance >= 0)`. Um lock no Redis na frente pode reduzir contenção ou trabalho duplicado, que é um objetivo de eficiência. Ele não pode ser o que mantém um saldo correto. Para locks que protegem corretude, Kleppmann recomenda um sistema de consenso como o ZooKeeper, com fencing em todo acesso. Ele também escreve: "At the very least, use a database with reasonable transactional guarantees."

## 4. O índice que atende a consulta de extrato

*Fonte principal: documentação do PostgreSQL, capítulo 11 "Indexes", seções 11.3 "Multicolumn Indexes", 11.4 "Indexes and ORDER BY" e 11.8 "Partial Indexes".*

O extrato é a leitura mais frequente de uma carteira:

```sql
SELECT id, amount, direction, created_at
  FROM ledger_entries
 WHERE account_id = $1
 ORDER BY created_at DESC
 LIMIT 50;
```

Sem índice, o Postgres lê todos os lançamentos, fica com os desta conta, ordena e devolve 50. A tabela cresce para sempre, então a consulta fica mais lenta a cada dia.

A documentação dá a regra para índices B-tree multicoluna: "equality constraints on leading columns, plus any inequality constraints on the first column that does not have an equality constraint, will always be used to limit the portion of the index that is scanned." Então a coluna filtrada por igualdade vem primeiro, e a coluna usada para ordenar ou filtrar por intervalo vem em segundo:

```sql
CREATE INDEX ledger_entries_account_created_idx
    ON ledger_entries (account_id, created_at);
```

A seção 11.4 explica por que isso também elimina a ordenação. Só índices B-tree produzem saída ordenada, e "if there is an index matching the `ORDER BY`, the first *n* rows can be retrieved directly, without scanning the remainder at all." Um índice pode ser percorrido de trás para frente, então `(account_id, created_at)` atende `ORDER BY created_at DESC` quando `account_id` está fixo. A próxima página do extrato usa o mesmo índice, porque `created_at < $cursor` é uma desigualdade na primeira coluna sem igualdade:

```sql
... WHERE account_id = $1 AND created_at < $2 ORDER BY created_at DESC LIMIT 50;
```

Dois lançamentos podem ter o mesmo timestamp, então código de produção costuma adicionar `id` como terceira coluna e como desempate no cursor. A documentação também diz "Multicolumn indexes should be used sparingly", e que mais de três colunas raramente ajudam. Todo índice deixa mais lento cada insert no ledger, então crie os que suas consultas precisam, não todas as combinações.

**Índices parciais** indexam só as linhas que atendem a um predicado. O exemplo da documentação é um índice só sobre os pedidos não faturados, a pequena fração das linhas que é a mais lida. O equivalente na carteira é o conjunto de transferências que um worker consulta periodicamente:

```sql
CREATE INDEX transfers_pending_idx ON transfers (created_at)
    WHERE status IN ('PENDING', 'UNKNOWN');
```

Transferências concluídas se acumulam para sempre, mas esse índice continua pequeno. Um **índice único parcial** garante unicidade só entre as linhas que atendem ao predicado. O exemplo da documentação permite um único teste "bem-sucedido" por par de sujeito e alvo; numa carteira, a mesma ferramenta pode permitir no máximo um hold ativo por autorização de cartão. A documentação também avisa contra criar muitos índices parciais, um por categoria, como substituto de particionamento: "This is a bad idea!"

## 5. Lendo um plano de execução

*Fonte principal: documentação do PostgreSQL, seção 14.1 "Using EXPLAIN".*

`EXPLAIN` mostra o plano que o Postgres escolheu: uma árvore de nós, com nós de scan embaixo lendo tabelas e nós acima deles ordenando, fazendo join ou limitando. Cada nó mostra quatro estimativas entre parênteses: custo inicial, custo total, linhas estimadas e largura média da linha em bytes. Os custos são "arbitrary units determined by the planner's cost parameters", tradicionalmente ancorados em 1.0 para a leitura sequencial de uma página. Eles servem para comparar planos, não como milissegundos. O custo de um nó pai inclui o dos filhos.

`EXPLAIN ANALYZE` executa a consulta e acrescenta os números reais: tempo real em milissegundos, linhas reais e `loops`. Quando um nó roda várias vezes, o tempo e as linhas dele são por loop, então multiplique por `loops`. O `ANALYZE` também liga o `BUFFERS`, que mostra quantas páginas vieram do cache (`shared hit`) e quantas foram lidas. Como ele executa de verdade, a documentação avisa que os efeitos colaterais acontecem. Envolva comandos que alteram dados:

```sql
BEGIN;
EXPLAIN ANALYZE UPDATE wallets SET balance = balance - 10 WHERE id = 42;
ROLLBACK;
```

Para a comparação de antes e depois na sexta-feira, estes são os formatos a procurar. Custos e tempos foram omitidos de propósito, porque os seus serão diferentes. Quando o Postgres percorre um índice ao contrário, o nó aparece como `Index Scan Backward`.

```
-- antes do índice
Limit
  -> Sort  (Sort Key: created_at DESC)
       -> Seq Scan on ledger_entries
            Filter: (account_id = 42)
            Rows Removed by Filter: ...

-- depois do índice
Limit
  -> Index Scan Backward using ledger_entries_account_created_idx on ledger_entries
       Index Cond: (account_id = 42)
```

O que ler, nesta ordem:

- **O nó de scan.** `Seq Scan` com um "Rows Removed by Filter" grande significa que o Postgres leu muitas linhas para ficar com poucas. A documentação observa que essa linha só aparece quando o filtro rejeitou pelo menos uma linha.
- **O nó Sort.** Se ele sumiu depois do índice, o índice está entregando as linhas já em ordem, e o `Limit` pode parar depois de 50.
- **Linhas estimadas x reais.** Uma diferença grande significa que as estatísticas do planner estão desatualizadas. Manter as estatísticas atualizadas é uma das tarefas do vacuum (seção 6).
- **Buffers.** Menos páginas tocadas é a medida mais honesta da melhora.

Uma armadilha da documentação: sob um `Limit`, o custo estimado do filho aparece como se ele rodasse até o fim, enquanto as linhas reais param cedo. Isso é uma convenção de exibição, não um erro de estimativa.

## 6. O MVCC deixa linhas mortas: por que o vacuum existe

*Fonte principal: documentação do PostgreSQL, seção 24.1 "Routine Vacuuming", introdução e subseções 24.1.1 e 24.1.2.*

A leitura de terça disse que todo comando vê um snapshot. O custo dos snapshots é armazenamento. A documentação diz sem rodeios: "In PostgreSQL, an `UPDATE` or `DELETE` of a row does not immediately remove the old version of the row." A versão antiga precisa ficar enquanto alguma transação ainda puder vê-la. Quando nenhuma puder mais, ela vira uma versão morta da linha, e o espaço dela precisa ser recuperado. Isso é o `VACUUM`.

Uma carteira está perto do pior caso para isso. A linha de saldo de um lojista popular pode ser atualizada milhares de vezes por dia, e cada update deixa mais uma versão morta para trás. A documentação lista quatro motivos pelos quais toda tabela precisa de vacuum:

1. Recuperar ou reutilizar o espaço de linhas atualizadas ou apagadas.
2. Atualizar as estatísticas que o planner usa.
3. Atualizar o visibility map, que acelera index-only scans.
4. Proteger contra o transaction ID wraparound.

O quarto é o perigoso. IDs de transação são um contador de 32 bits. Se uma tabela passa tempo demais sem vacuum, o contador dá a volta e transações antigas de repente parecem estar no futuro. A documentação resume o resultado como "catastrophic data loss" e exige que toda tabela passe por vacuum pelo menos uma vez a cada dois bilhões de transações.

Na prática, o daemon de **autovacuum** roda o vacuum por você, agendado conforme a atividade de updates. O `VACUUM` padrão roda junto com o tráfego normal e torna o espaço reutilizável dentro da tabela; o `VACUUM FULL` devolve espaço ao sistema operacional, mas é muito mais lento, e a documentação aconselha evitá-lo. Seu trabalho como engenheiro de aplicação é, em geral, não atrapalhar. Como uma versão morta não pode ser removida enquanto alguma transação ainda puder vê-la, uma sessão deixada "idle in transaction" por horas segura a limpeza do banco inteiro. É o mesmo conselho de terça, agora com um segundo motivo: transações curtas reduzem esperas por lock e deixam o vacuum fazer o trabalho dele.

## 7. Preparando o TCM

O lab de hoje é só preparação: nada de código do TCM. Três coisas para ter prontas na quinta de manhã:

**Dados de seed.** Mil carteiras com saldos conhecidos, criadas por um script que você pode rodar de novo. `generate_series` é a ferramenta de sempre. Um exemplo genérico numa tabela descartável:

```sql
INSERT INTO demo_accounts (id, balance)
SELECT g, 1000 FROM generate_series(1, 1000) AS g;
```

Anote o total esperado antes de rodar qualquer teste. "O total nunca muda" é uma das suas asserções.

**Esqueleto do script de carga.** Um script que dispara N transferências em paralelo (na quinta, 100), cada uma com origem e destino aleatórios, sobre um pool de várias conexões. Planeje o que ele registra a cada execução: sucessos, rejeições de negócio (saldo insuficiente), conflitos, retries e tempo total. Uma única conexão serializa tudo e esconde todos os bugs, então o tamanho do pool importa.

**Lista de testes.** Escreva os testes como frases antes de escrever qualquer código. Uma lista inicial:

- Depois de 100 transferências paralelas, nenhuma carteira tem saldo negativo.
- Depois de 100 transferências paralelas, a soma de todos os saldos é igual ao total do seed.
- Duas transferências opostas entre as mesmas carteiras, rodando juntas muitas vezes, nunca dão deadlock na v1.
- Uma carteira com saldo para só um de dois débitos concorrentes termina com exatamente um débito aplicado.
- A v2 desiste depois do limite de retries e reporta um conflito, nunca um sucesso silencioso.
- A consulta de extrato usa o índice (confira com `EXPLAIN`).

## O que anotar hoje

1. Os dois motivos de Kleppmann para um lock (eficiência e corretude), o cenário do cliente pausado em quatro passos e como um fencing token o impede. Termine com uma frase: por que a garantia final de um saldo fica no banco de dados.
2. O índice que atende a consulta de extrato, a regra da documentação que justifica a ordem das colunas e como o mesmo índice atende a próxima página. Acrescente um índice parcial que sua carteira poderia usar.
3. Como ler um plano: os quatro campos de estimativa, o que `ANALYZE` e `BUFFERS` acrescentam e o que você espera que mude no plano do extrato depois do índice.
4. MVCC e vacuum: por que updates deixam versões mortas, os quatro motivos pelos quais o vacuum roda e o que transações longas fazem com ele.
5. Sua preparação para o TCM: comando de seed, esboço do script de carga e lista de testes.

## Teste-se

Estas perguntas dão bons flashcards (veja o [guia de flashcards](../../FLASHCARDS.pt-BR.md)).

- Qual é a diferença entre um lock para eficiência e um lock para corretude?
- Por que verificar o lease logo antes de escrever não torna seguro um lock baseado em lease?
- O que é um fencing token, e quem precisa verificá-lo?
- Qual índice atende `WHERE account_id = $1 ORDER BY created_at DESC LIMIT 50`, e por que essa ordem de colunas?
- O que `EXPLAIN ANALYZE` faz que `EXPLAIN` não faz, e qual é o risco?
- Por que um `UPDATE` no Postgres deixa uma linha morta para trás?
- O que é o transaction ID wraparound, e o que o impede?

## Referências

- **Fonte principal:** Martin Kleppmann, ["How to do distributed locking"](https://martin.kleppmann.com/2016/02/08/how-to-do-distributed-locking.html), 2016. Leia inteiro. Gratuito.
- Documentação do PostgreSQL, ["Indexes"](https://www.postgresql.org/docs/current/indexes.html) (capítulo 11). Leia [11.3 "Multicolumn Indexes"](https://www.postgresql.org/docs/current/indexes-multicolumn.html), [11.4 "Indexes and ORDER BY"](https://www.postgresql.org/docs/current/indexes-ordering.html) e [11.8 "Partial Indexes"](https://www.postgresql.org/docs/current/indexes-partial.html). Gratuito.
- Documentação do PostgreSQL, ["Using EXPLAIN"](https://www.postgresql.org/docs/current/using-explain.html) (seção 14.1). Leia 14.1.1 e 14.1.2 (fundamentos do EXPLAIN e EXPLAIN ANALYZE). Gratuito.
- Documentação do PostgreSQL, ["Routine Vacuuming"](https://www.postgresql.org/docs/current/routine-vacuuming.html) (seção 24.1). Leia a introdução, 24.1.1 e 24.1.2; passe os olhos na 24.1.5, sobre wraparound. Gratuito.
