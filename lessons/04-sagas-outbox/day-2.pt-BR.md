# Módulo 4, terça-feira: isolamento em sagas, reserva de saldo e transactional outbox

[Módulo 4](../../modules/04-sagas-outbox.pt-BR.md) · [Read in English](day-2.md)

**Tempo de leitura:** cerca de 45 minutos. Use o resto do bloco de 2 horas nas referências do final. O capítulo 4 de "Microservices Patterns" é de um livro pago; se você não tiver o livro, use o tempo nas páginas de outbox e na página de arquitetura do Debezium.

Este é um texto original escrito para este curso. Ele se baseia nas referências listadas no final, e cada seção indica a fonte que segue. Quando uma ideia vem de um autor específico, o texto diz isso.

## Por que isso importa para uma fintech

A segunda-feira terminou com dois problemas que uma saga deixa em aberto. Primeiro, uma saga não tem isolamento: seus passos intermediários já fizeram commit e estão visíveis para todos. Em uma carteira digital, isso significa que outra requisição pode ver dinheiro que está "a caminho" e gastá-lo duas vezes. Segundo, cada passo precisa atualizar seu banco e avisar o próximo participante, e uma queda entre essas duas ações perde a mensagem ou envia uma mensagem sobre uma mudança que nunca fez commit.

Os dois problemas produzem o mesmo sintoma em produção: saldos que não fecham e transferências presas no meio. Hoje você aprende as respostas padrão: contramedidas para o isolamento (com a reserva de saldo como versão de fintech) e o transactional outbox para mensageria confiável.

## 1. Sagas são ACD, não ACID

*Fonte principal: Richardson, "Microservices Patterns", capítulo 4, "Handling the lack of isolation". O livro é pago; esta seção descreve seus conceitos conhecidos, e o tratamento completo está no livro.*

Richardson descreve uma saga como tendo atomicidade (todos os passos rodam, ou compensações os desfazem), consistência (cada serviço mantém seus próprios invariantes) e durabilidade (cada passo faz commit), mas não isolamento. Cada transação local faz commit assim que termina, então outras sagas e requisições comuns veem seus efeitos antes de a saga acabar.

O livro agrupa os problemas resultantes em três anomalias. Aqui estão elas com exemplos da carteira:

| Anomalia | O que acontece | Exemplo na carteira |
| --- | --- | --- |
| Lost update | Uma saga sobrescreve uma mudança de outra sem lê-la | Uma saga de reembolso põe a transferência em `REFUNDED` enquanto a saga original, ainda rodando, a volta para `COMPLETED` |
| Dirty read | Uma saga lê dados que outra saga não terminou, e depois essa saga compensa | Uma checagem de limite vê o saldo da Ana após um crédito que depois é estornado, e aprova um saque que ela não consegue cobrir |
| Fuzzy (nonrepeatable) read | Dois passos da mesma saga leem o mesmo dado e obtêm valores diferentes | O passo 1 lê o uso do limite diário da Ana, outra transferência termina, o passo 3 lê outro número |

O ponto a lembrar: essas anomalias não são bugs do banco. Cada transação local está totalmente isolada pelo Postgres. As anomalias vêm dos intervalos **entre** transações locais, que nenhum banco enxerga.

## 2. Contramedidas e a estrutura de uma saga

*Fonte principal: Richardson, "Microservices Patterns", capítulo 4. Detalhes e código estão no livro.*

Richardson classifica os passos de uma saga em três tipos. Essa classificação decide onde as contramedidas entram:

- **Compensatable transactions** podem ser desfeitas por uma compensação. Debitar a Ana dentro do seu próprio ledger é compensável: um lançamento de estorno desfaz o débito.
- A **pivot transaction** é o ponto de decisão. Se ela fizer commit, a saga vai até o fim. Ela é o último passo compensável ou o primeiro passo que não pode ser desfeito. Em um saque para conta externa, a chamada que manda o banco parceiro enviar o dinheiro é a pivot: depois que ela dá certo, você não consegue pegar o dinheiro de volta.
- **Retriable transactions** vêm depois da pivot. Elas têm garantia de dar certo em algum momento, então são repetidas até darem. Marcar a transferência como `COMPLETED` e creditar o Bruno no seu próprio ledger após um saque confirmado são retriable.

O livro então lista contramedidas. As mais úteis para uma carteira são:

- **Semantic lock.** Um passo compensável marca uma flag que diz "este registro está no meio de uma saga", como uma transferência no estado `PENDING` ou um débito marcado como reservado. Outras requisições checam a flag e recusam, esperam ou tratam o registro de outro jeito. A flag é limpa pelo passo retriable ou pela compensação. É um lock no nível da aplicação, então sobrevive entre transações locais.
- **Commutative updates.** Projete atualizações cuja ordem não importa. Acrescentar lançamentos ao ledger (`+100`, `-30`) é comutativo; fazer `balance = 70` não é. Uma compensação que acrescenta um lançamento de estorno comuta com os lançamentos de outras sagas, então nenhuma atualização se perde.
- **Reordenar passos (pessimistic view).** Organize os passos para reduzir o risco de dirty read. Por exemplo, debite o pagador antes de creditar o recebedor, para que ninguém consiga gastar dinheiro que pode ser estornado depois. Um crédito que precisa ser compensado é perigoso porque o Bruno pode já tê-lo gasto; um débito que precisa ser compensado só devolve à Ana o próprio dinheiro dela.
- **Reread value.** Antes de sobrescrever um registro, um passo o relê e confere que ele não mudou desde a última leitura da saga (optimistic locking, muitas vezes com uma coluna `version`). Se mudou, a saga aborta ou recomeça.

O livro descreve outras (version file, by value) e explica como escolher entre elas. Para o TCM, a combinação de que você precisa é: debitar primeiro (reordenação), lançamentos só de acréscimo (commutative updates) e um estado `PENDING` que o resto do código respeita (semantic lock).

## 3. Reserva de saldo e TCC

*Fonte principal: Richardson, "Microservices Patterns", capítulo 4, para a ideia de semantic lock. TCC é um padrão relacionado vindo da prática da indústria, descrito aqui em termos gerais.*

Uma carteira tem um problema de isolamento acima de todos: duas transferências simultâneas da Ana não podem gastar os mesmos 100. A forma de fintech de um semantic lock é a **reserva de saldo**, ou **hold** (também chamada de autorização). As bandeiras de cartão usam isso há décadas: a autorização reserva o dinheiro, e a captura o movimenta depois.

Um hold divide o saldo em dois números:

- **Saldo contábil (ledger balance):** a soma dos lançamentos efetivados.
- **Saldo disponível (available balance):** saldo contábil menos os holds ativos.

O primeiro passo da saga contra `accounts` cria um hold. Ele só dá certo se o saldo disponível for suficiente, e a checagem e o insert acontecem em uma única transação local:

```sql
BEGIN;
SELECT id FROM accounts WHERE id = 'ana' FOR UPDATE;  -- serializa holds por conta
INSERT INTO holds (id, account_id, amount, saga_id, status, expires_at)
SELECT gen_random_uuid(), 'ana', 100, $1, 'ACTIVE', now() + interval '5 minutes'
WHERE (SELECT balance FROM accounts WHERE id = 'ana')
    - (SELECT coalesce(sum(amount), 0) FROM holds
       WHERE account_id = 'ana' AND status = 'ACTIVE') >= 100
ON CONFLICT (saga_id) DO NOTHING;     -- idempotente por saga (índice único em saga_id)
COMMIT;
```

O hold então termina de um de dois jeitos. A **captura** o transforma em um lançamento de débito efetivado e fecha o hold, em uma transação local. A **liberação** fecha o hold sem lançar nada. Essa é a compensação, e ela é trivialmente segura porque nenhum dinheiro se moveu.

Esse formato de três passos tem nome: **TCC (Try, Confirm, Cancel)**. Try reserva o recurso (o hold), Confirm o torna definitivo (a captura), Cancel o libera. Todo participante precisa oferecer as três operações, e Confirm e Cancel precisam ser idempotentes, porque o orquestrador vai repeti-las. Holds também precisam de expiração. Se o orquestrador morrer de vez, um sweeper libera os holds que passaram de `expires_at`, para que uma saga caída não congele o dinheiro de um cliente para sempre.

Compare com o 2PC de segunda. Um hold parece um "prepare", mas é um registro de negócio com commit feito, visível e com expiração, não um lock de banco mantido aberto através da rede. Outras transferências continuam rodando contra o saldo disponível.

## 4. O problema da escrita dupla e o transactional outbox

*Fonte principal: Richardson, microservices.io, "Pattern: Transactional outbox".*

Todo passo de saga faz duas coisas: muda seus próprios dados e avisa alguém. O orquestrador salva `DEBITED` e precisa enviar o comando de crédito. O `accounts` grava um lançamento e precisa publicar `AccountDebited`. A página de outbox de Richardson enuncia o problema como uma pergunta: como atualizar o banco e enviar mensagens a um broker de forma atômica?

Veja as duas ordens ingênuas:

- **Commit, depois publicar.** O serviço cai depois do `COMMIT` e antes de publicar. Os dados mudaram, e ninguém fica sabendo. A saga trava.
- **Publicar, depois commit.** A mensagem sai, e então a transação faz rollback (uma constraint falha, ou o processo morre). Consumidores agem sobre uma mudança que nunca aconteceu.

As forces de Richardson acrescentam um terceiro requisito: as mensagens precisam sair na ordem em que o serviço as produziu, mesmo com várias instâncias atualizando o mesmo agregado.

A solução dele: o serviço insere cada mensagem em uma **tabela de outbox** na **mesma transação local** que muda os dados de negócio. Um componente separado, o **message relay**, lê o outbox e publica no broker. Ou o lançamento e a mensagem fazem commit juntos, ou nenhum dos dois.

```sql
CREATE TABLE outbox (
  id           bigserial PRIMARY KEY,
  aggregate_id text  NOT NULL,          -- ex.: id da conta, usado para ordenar
  type         text  NOT NULL,          -- 'AccountDebited'
  payload      jsonb NOT NULL,
  created_at   timestamptz NOT NULL DEFAULT now(),
  published_at timestamptz
);

BEGIN;
INSERT INTO ledger_entries (account_id, amount, saga_id, step) VALUES ('ana', -100, $1, 2);
INSERT INTO outbox (aggregate_id, type, payload)
VALUES ('ana', 'AccountDebited', jsonb_build_object('sagaId', $1, 'amount', 100));
COMMIT;
```

Richardson lista os benefícios: sem 2PC, mensagens só saem se a transação fizer commit, e saem na ordem em que a aplicação as produziu. Ele também aponta a pegadinha: o relay pode publicar uma mensagem mais de uma vez, por exemplo se cair depois de publicar e antes de marcá-la como publicada. Por isso os consumidores precisam ser idempotentes, normalmente registrando os IDs das mensagens já processadas. Ele acrescenta que isso costuma ser tranquilo, já que consumidores precisam de idempotência de qualquer jeito. Na sua carteira, a idempotency key do Módulo 2 (`saga_id` mais passo) é exatamente isso.

## 5. Polling publisher com SKIP LOCKED

*Fonte principal: Richardson, microservices.io, "Pattern: Polling publisher". Documentação do PostgreSQL, "SELECT", The Locking Clause.*

A página de outbox linka duas formas de construir o relay. A primeira é o **polling publisher**: um loop que consulta o outbox em busca de linhas não publicadas e as publica. O benefício listado por Richardson é que funciona com qualquer banco SQL. As desvantagens: publicar na ordem certa é complicado, e nem todo banco NoSQL suporta o padrão.

Com várias instâncias do relay, você precisa que elas não peguem as mesmas linhas. O Postgres tem `FOR UPDATE SKIP LOCKED` para isso. A documentação do Postgres diz que pular linhas travadas "provides an inconsistent view of the data" (dá uma visão inconsistente dos dados), então não serve para uso geral, mas pode ser usado para evitar disputa de locks quando vários consumidores leem uma tabela com cara de fila. Um outbox é exatamente isso.

```typescript
// Um lote do relay. Roda em loop, com uma pequena pausa quando o lote vem vazio.
async function relayBatch(ds: DataSource, publish: (m: OutboxRow) => Promise<void>) {
  await ds.transaction(async (tx) => {
    const rows: OutboxRow[] = await tx.query(
      `SELECT id, aggregate_id, type, payload FROM outbox
        WHERE published_at IS NULL
        ORDER BY id
        LIMIT 100
        FOR UPDATE SKIP LOCKED`,
    );
    for (const row of rows) {
      await publish(row); // pode dar certo e depois a tx falhar: at-least-once
    }
    if (rows.length > 0) {
      await tx.query(`UPDATE outbox SET published_at = now() WHERE id = ANY($1)`, [
        rows.map((r) => r.id),
      ]);
    }
  });
}
```

Três detalhes para entender antes do lab:

- **At-least-once.** Se o processo morrer depois do `publish` e antes do `COMMIT`, as linhas continuam não publicadas e saem de novo. É a duplicata sobre a qual Richardson avisa.
- **Ordem versus paralelismo.** Com dois relays e `SKIP LOCKED`, o relay 1 pode pegar as linhas 1 a 100 e o relay 2 as linhas 101 a 200, e o relay 2 pode publicar primeiro. Se a ordem importa por conta, use um único relay, ou particione o trabalho por `aggregate_id` para que todas as linhas de uma conta passem pelo mesmo relay.
- **Limpeza.** O outbox cresce para sempre, a menos que você apague ou arquive as linhas publicadas. Faça isso em um job separado, fora do caminho quente.

No lab de hoje, o relay escreve em um log (um arquivo ou uma tabela `published_messages`) em vez do Kafka, que chega no Módulo 5. O formato do código não muda.

## 6. Transaction log tailing e Debezium

*Fonte principal: Richardson, microservices.io, "Pattern: Transaction log tailing". Documentação do Debezium, "Debezium Architecture".*

A segunda opção de relay é o **transaction log tailing**. A solução de Richardson é acompanhar o log de transações do banco e publicar cada mensagem inserida no outbox. Todo banco já grava cada mudança com commit em um log: o binlog no MySQL, o write-ahead log (WAL) no Postgres, os streams no DynamoDB, todos citados na página dele. Ler esse log significa nada de queries de polling e nenhuma coluna `published_at` para atualizar.

Os benefícios listados por Richardson são: sem 2PC e precisão (o log contém exatamente o que fez commit, na ordem do commit). As desvantagens: é relativamente pouco conhecido, exige soluções específicas de cada banco, e é difícil evitar publicação duplicada.

O **Debezium** é a ferramenta open source mais conhecida para isso, e sua página de arquitetura explica como ele é implantado. O Debezium é uma ferramenta de change data capture (CDC): ele captura mudanças de linha em um banco e as publica como eventos de mudança. A implantação mais comum roda **source connectors** do Debezium dentro do **Kafka Connect**, um serviço separado ao lado dos brokers Kafka. A página diz que, por padrão, as mudanças de uma tabela vão para um tópico Kafka com o nome dessa tabela. O roteamento de tópicos pode mudar esse mapeamento. Existem outras duas implantações: o **Debezium Server**, uma aplicação independente que envia eventos para outros sistemas, como Amazon Kinesis ou Google Cloud Pub/Sub, e o **Debezium Engine**, uma biblioteca Java embutida na sua própria aplicação.

Como ele lê o log depende do banco. A página de arquitetura diz que o connector de MySQL lê o binlog, e o connector de PostgreSQL lê de um stream de replicação lógica. Em termos de Postgres, isso é logical decoding do WAL por meio de um replication slot, a mesma maquinaria que você viu com replicação no Módulo 1. Um replication slot guarda o WAL até o consumidor confirmar a leitura, então um Debezium parado faz o WAL se acumular no disco do primário. Monitore isso.

| | Polling publisher | Log tailing (Debezium) |
| --- | --- | --- |
| Funciona com | Qualquer banco SQL | Bancos com log de mudanças legível |
| Carga extra | Queries a cada poucas centenas de ms | Leitura do stream do log |
| Latência | Intervalo do polling | Próxima ao momento do commit |
| Ordem | Você precisa projetar | Ordem de commit vinda do log |
| Operação | Um loop no seu serviço | Kafka Connect, slots, configuração do connector |
| Duplicatas | Sim, consumidores deduplicam | Sim, consumidores deduplicam |

Para o TCM, o polling publisher basta e é muito mais simples. Em entrevistas, cite o log tailing como a opção que você escolheria com volume maior ou quando não pode adicionar carga de polling ao primário.

## O que anotar hoje

1. As três anomalias de saga (lost update, dirty read, fuzzy read) com um exemplo da carteira para cada.
2. Passos compensatable, pivot e retriable. Diga qual é a pivot em um saque para um banco parceiro.
3. Semantic lock, commutative updates e reordenação: uma frase para cada e onde cada um aparece na saga de transferência.
4. Como uma reserva de saldo funciona como TCC (try, confirm, cancel), e por que ela precisa de expiração.
5. As duas ordens de falha da escrita dupla (commit e depois publicar, publicar e depois commit), e como o outbox resolve as duas.
6. Polling publisher versus transaction log tailing: uma vantagem e uma desvantagem de cada, e por que o consumidor precisa ser idempotente nos dois.

## Teste-se

Estas perguntas dão bons flashcards (veja o [guia de flashcards](../../FLASHCARDS.pt-BR.md)).

- Qual letra do ACID falta a uma saga, e por que o Postgres não consegue fornecê-la entre serviços?
- O que é a pivot transaction de uma saga?
- Por que debitar antes de creditar é uma contramedida?
- Qual é a diferença entre saldo contábil e saldo disponível?
- Por que o insert no outbox precisa estar na mesma transação que a escrita de negócio?
- Por que um polling publisher entrega at-least-once e não exactly-once?
- Como o Debezium lê mudanças do Postgres?

## Referências

- **Fonte principal:** Chris Richardson, ["Microservices Patterns"](https://www.manning.com/books/microservices-patterns), Manning, capítulo 4 ("Managing transactions with sagas"), especialmente "Handling the lack of isolation". Livro pago. Nenhuma fonte gratuita cobre as contramedidas tão bem.
- **Fonte principal:** Chris Richardson, microservices.io, ["Pattern: Transactional outbox"](https://microservices.io/patterns/data/transactional-outbox.html), mais as duas opções de relay linkadas nela: ["Pattern: Polling publisher"](https://microservices.io/patterns/data/polling-publisher.html) e ["Pattern: Transaction log tailing"](https://microservices.io/patterns/data/transaction-log-tailing.html). Gratuito.
- Documentação do Debezium, ["Debezium Architecture"](https://debezium.io/documentation/reference/stable/architecture.html). Leia a página inteira. Gratuito.
- Documentação do PostgreSQL, ["SELECT"](https://www.postgresql.org/docs/current/sql-select.html), seção "The Locking Clause" (`SKIP LOCKED`). Gratuito.
