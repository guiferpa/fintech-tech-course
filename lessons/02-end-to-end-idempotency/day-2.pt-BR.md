# Módulo 2, terça-feira: recuperando requisições interrompidas e consumidores idempotentes

[Módulo 2](../../modules/02-end-to-end-idempotency.pt-BR.md) · [Read in English](day-2.md)

**Tempo de leitura:** cerca de 45 minutos. Use o resto do bloco de 2 horas nas referências do final.

Este é um texto original escrito para este curso. Ele se baseia nas referências listadas no final, e cada seção indica a fonte que segue.

## Por que isso importa para uma fintech

O desenho de ontem cobre uma requisição que falha e volta com a mesma chave. Restam duas lacunas. Primeiro, alguns clientes nunca voltam: o usuário apaga o app, ou o serviço que chama perde seu estado. As transferências deles, pela metade, ainda precisam de um desfecho. Segundo, boa parte do trabalho de uma carteira nem chega por HTTP. Chega como mensagens de um broker, e brokers entregam algumas mensagens mais de uma vez. Hoje fecha as duas lacunas: a segunda metade do artigo de Brandur para a primeira, e o padrão Idempotent Consumer de Chris Richardson para a segunda.

## 1. Pegando a chave: o upsert e o lock

*Fonte principal: Brandur Leach, "Implementing Stripe-like Idempotency Keys in Postgres", seção "Idempotency key upsert".*

Toda requisição com chave começa do mesmo jeito: encontrar a chave ou criá-la, e garantir que nenhuma outra tentativa esteja trabalhando nela no mesmo momento. O Rocket Rides de Brandur trata quatro casos.

| Situação quando a requisição chega | O que o Rocket Rides faz |
| --- | --- |
| A chave não existe | Insere a chave, travada, no recovery point `started` |
| A chave existe, mas os parâmetros são diferentes | Rejeita com `409 Conflict` (params mismatch) |
| A chave existe e está travada por uma tentativa recente | Rejeita com `409 Conflict` (request in progress) |
| A chave existe e o lock expirou | Pega o lock e continua a partir do recovery point |

Uma chave já em `finished` não é travada de novo. A requisição simplesmente devolve o código e o corpo de resposta armazenados.

Dois detalhes tornam isso seguro sob concorrência. O índice único em `(user_id, idempotency_key)` faz com que só um de dois inserts simultâneos tenha sucesso. Brandur também roda a fase numa transação `SERIALIZABLE`, então, se duas transações tentarem travar a mesma chave, o Postgres aborta uma delas.

O lock é um timestamp, `locked_at`, e não um flag. Um processo que cai segurando o lock não consegue liberá-lo, então um lock mais velho que um timeout é tratado como abandonado e pode ser tomado. O código de Brandur se refere a uma constante para esse timeout, mas o artigo não dá um valor. Você vai escolher um no TCM. Ele precisa ser maior que sua requisição legítima mais lenta, incluindo a chamada ao banco parceiro.

O TCM deste curso usa códigos de status um pouco diferentes dos do Rocket Rides: `409` quando a chave ainda está em andamento, e `422 Unprocessable Content` quando a mesma chave chega com um corpo diferente. Separá-los ajuda o cliente: um `409` significa "espere e faça retry", enquanto um `422` significa "seu cliente tem um bug, fazer retry não vai adiantar".

No Postgres, o passo "inserir ou encontrar" pode ser um único comando:

```sql
INSERT INTO idempotency_keys
  (user_id, idempotency_key, request_method, request_path, request_hash)
VALUES ($1, $2, 'POST', '/transfers', $3)
ON CONFLICT (user_id, idempotency_key) DO NOTHING
RETURNING id;
```

Se uma linha volta, esta requisição criou a chave e é dona dela. Se nada volta, a chave já existia, e o código a lê para decidir entre devolver a resposta armazenada, `409` ou `422`. No nível padrão `READ COMMITTED`, um segundo insert da mesma chave espera a primeira transação fazer commit ou rollback antes de concluir que há conflito. É exatamente essa espera que impede 50 requisições concorrentes de criarem 50 chaves.

## 2. Percorrendo a máquina de estados

*Fonte principal: Brandur Leach, "Implementing Stripe-like Idempotency Keys in Postgres", seções "A directed and acyclic state machine", "Calling Stripe" e "Send receipt and finish".*

Quando uma requisição é dona da chave, ela roda um loop: lê o recovery point, executa a próxima fase, faz commit da fase junto com o novo recovery point, repete. Brandur chama o conjunto de recovery points de máquina de estados dirigida e acíclica. Ela só anda para frente, e qualquer estado desconhecido é tratado como bug.

| Recovery point | Próximo passo | Novo recovery point |
| --- | --- | --- |
| `started` | Criar a corrida e o registro de auditoria (uma transação) | `ride_created` |
| `ride_created` | Cobrar pela Stripe, salvar o ID da cobrança | `charge_created` |
| `charge_created` | Preparar o job de recibo, guardar a resposta | `finished` |
| `finished` | Devolver a resposta armazenada | (fim) |

Dois detalhes da chamada à Stripe importam para o TCM desta semana.

**A chave é repassada, mas não como veio.** O Rocket Rides passa sua própria idempotency key para a Stripe, montada a partir do ID interno da linha da chave (`rocket-rides-atomic-#{key.id}`), e não do valor bruto do cliente. Como o ID da linha é único entre todos os usuários, a chave repassada também é. Se o servidor morre esperando a Stripe, o retry envia a mesma chave repassada, e a camada de idempotência da própria Stripe impede uma segunda cobrança. A tarefa 3 de quinta faz o mesmo com o banco parceiro falso.

**Os erros são separados em definitivos e temporários.** Um erro de cartão da Stripe é definitivo: o Rocket Rides guarda uma resposta `402` e move a chave para `finished`, então todo retry recebe a mesma resposta. Os outros erros da Stripe viram um `503`. Na seção "Murphy in action", o artigo diz que o cliente é orientado a fazer retry quando a Stripe está fora. Leia o código com atenção, porém: o exemplo guarda o `503` como resposta final. Pergunte-se o que você quer no seu desenho. Um erro temporário deve deixar a chave **inacabada**, para que um retry ou o completer possam tentar de novo. Só uma resposta definitiva deve ser guardada como final.

A última fase grava um job `send_ride_receipt` em `staged_jobs`, devolve `201` e define o recovery point como `finished`, tudo numa só transação.

## 3. Murphy em ação: toda falha tem um desfecho

*Fonte principal: Brandur Leach, "Implementing Stripe-like Idempotency Keys in Postgres", seção "Murphy in action".*

Brandur percorre as falhas uma a uma e mostra que cada uma termina num estado correto. Eis a mesma lista, traduzida para uma transferência da carteira.

| Falha | O que acontece |
| --- | --- |
| A conexão cai antes de chegar à API | O cliente faz retry com a mesma chave; a primeira tentativa que chegar faz o trabalho |
| Duas tentativas com a mesma chave chegam juntas | O índice único deixa um insert vencer; o outro recebe `409` |
| O Postgres cai logo depois de a chave ser criada | O cliente continua fazendo retry; quando o Postgres volta, a chave é encontrada e a requisição continua |
| O banco parceiro está fora | A fase do parceiro falha; o cliente é orientado a tentar mais tarde; a transferência fica em `transfer_created` |
| O processo da API morre esperando o parceiro | O retry continua a partir de `transfer_created` e envia a **mesma chave repassada**; o parceiro deduplica |
| Um deploy ruim devolve 500 no meio do fluxo | Depois que a correção sobe, os retries dão certo; se o cliente sumiu, o completer termina a requisição |

A última linha apresenta os processos que mantêm tudo andando quando não há cliente por perto.

## 4. O completer, o enqueuer e o reaper

*Fonte principal: Brandur Leach, "Implementing Stripe-like Idempotency Keys in Postgres", seção "Other processes".*

O desenho de Brandur depende de três processos em background.

- **O enqueuer** move jobs de `staged_jobs` para a fila de jobs de verdade, mas só depois que a transação que os inseriu fez commit. É isso que torna "enviar o recibo" parte de uma fase atômica sem fazer a requisição esperar pelo email.
- **O completer** procura requisições que começaram mas nunca terminaram e cujos clientes parecem ter ido embora. Ele as leva até o fim executando o mesmo caminho de código a partir do recovery point armazenado, usando os parâmetros guardados da requisição e uma forma interna de se autenticar como o usuário original. Brandur ressalta o pouco que ele precisa saber: "It doesn’t even have to have special knowledge about how the stack is implemented." Isso só funciona porque os parâmetros da requisição e o recovery point estão na chave.
- **O reaper** apaga chaves antigas. Brandur primeiro diz que as chaves podem ser recicladas depois de "24 hours or so" e, mais adiante, sugere que o reaper espere cerca de 72 horas. O motivo da janela maior é prático: se um deploy ruim quebrar requisições na sexta à noite, o time tem até segunda para subir uma correção e deixar o completer terminar as requisições presas. Um reaper ideal também sinaliza as requisições que não conseguiu terminar, para que uma pessoa as analise.

Numa carteira, o completer não é opcional. Uma transferência presa em `transfer_created` segura dinheiro na conta de quem envia. Alguém precisa ou enviá-la ao parceiro ou liberar o hold. No TCM, basta você saber onde o completer se encaixaria; o status `UNKNOWN` do Módulo 1 e o job de conciliação são primos próximos da mesma ideia.

Brandur termina o artigo com a ideia de um sistema **passivamente seguro** (passively safe): o que quer que falhe, o sistema para num estado estável, e processos ativos como o completer o levam à consistência completa depois. Nas palavras dele: "Ideally, human operators never have to intervene to fix things (or at least as infrequently as possible)."

## 5. Quando o outro lado não ajuda

*Fonte principal: Brandur Leach, "Implementing Stripe-like Idempotency Keys in Postgres", seção "Complications".*

O desenho inteiro se apoia em duas premissas. Brandur diz o que fazer quando elas não valem.

**O serviço externo não é idempotente.** Se o banco parceiro não aceita idempotency key e não oferece forma de consultar uma transferência pela sua referência, uma chamada que falhou pode não ser segura de repetir. A resposta conservadora de Brandur é marcar a operação como falha permanente, a menos que o erro diga explicitamente que o retry é seguro. Erros ambíguos, como timeouts e conexões resetadas, contam como falha. Em pagamentos, "falha permanente" costuma significar "mandar para conciliação manual", e não "dizer ao cliente que falhou". A lição real dele é pressionar todo serviço do qual você depende a oferecer idempotência.

**O armazenamento local não é transacional.** Sem transações ACID, você não consegue agrupar mudanças locais em fases atômicas, então toda escrita se comporta como uma foreign state mutation. Esse é um dos motivos pelos quais este curso mantém o dinheiro no Postgres.

Brandur também observa que a mesma ideia funciona em formulários web comuns: um campo oculto com uma chave gerada quando o formulário é renderizado impede que um clique duplo cobre duas vezes.

## 6. O consumidor idempotente

*Fonte principal: Chris Richardson, microservices.io, "Pattern: Idempotent Consumer".*

Agora a segunda lacuna. Sua carteira não recebe só requisições HTTP. Depois que uma transferência é aceita, uma mensagem como `TransferRequested` vai para um broker, e um worker a consome para gravar lançamentos no ledger ou chamar o banco parceiro.

O padrão de Richardson parte de um fato sobre brokers: a maioria garante entrega **at-least-once**. Um consumidor pode cair depois de fazer o trabalho e antes de confirmar (ack) a mensagem, e o broker então a entrega de novo. A página formula o problema diretamente: "How does a message consumer handle duplicate messages correctly?" O exemplo dela é um serviço de contas que consome um evento `AccountDebited` e subtrai o valor do saldo. Processe duas vezes e o saldo fica errado.

A solução tem três partes:

1. Toda mensagem carrega um **message ID** único.
2. O consumidor registra os IDs das mensagens que já processou, numa tabela separada `PROCESSED_MESSAGES` ou nas próprias linhas de negócio que cria.
3. O ID é registrado **na mesma transação do banco** que o efeito.

A chave da tabela é `(subscriber_id, message_id)`. Quando chega uma duplicata, inserir o ID dela viola a chave, a transação sofre rollback e o consumidor ignora a mensagem. O subscriber ID importa porque vários consumidores podem processar a mesma mensagem por motivos diferentes: quem grava no ledger e quem envia a notificação precisam, cada um, de seu próprio registro.

O ponto 3 é o que torna o padrão correto. Veja as duas ordens erradas:

| Ordem | Uma queda entre os dois passos leva a |
| --- | --- |
| Registrar o ID, commit, depois aplicar o efeito | O ID fica salvo, o efeito se perde; a reentrega é pulada para sempre |
| Aplicar o efeito, commit, depois registrar o ID | O efeito fica salvo, o ID não; a reentrega aplica o efeito duas vezes |
| Os dois numa transação | Ou os dois são salvos ou nenhum; a reentrega faz a coisa certa |

Uma versão com sabor de Postgres usa `ON CONFLICT DO NOTHING` em vez de capturar a violação de unicidade. A lógica é a mesma de Richardson: nenhuma linha nova significa que a mensagem já foi processada.

```typescript
// Consumidor de TransferRequested, usando node-postgres.
async handle(msg: TransferRequested): Promise<void> {
  const client = await this.pool.connect();
  try {
    await client.query('BEGIN');
    const res = await client.query(
      `INSERT INTO processed_messages (subscriber_id, message_id)
       VALUES ($1, $2)
       ON CONFLICT (subscriber_id, message_id) DO NOTHING`,
      ['ledger-poster', msg.messageId],
    );
    if (res.rowCount === 1) {
      await this.postEntries(client, msg); // o efeito, na mesma transação
    }
    await client.query('COMMIT');
  } catch (err) {
    await client.query('ROLLBACK');
    throw err; // o broker vai reentregar
  } finally {
    client.release();
  }
}
```

Confirme a mensagem ao broker só depois do `COMMIT`. Se o processo morrer antes da confirmação, a mensagem volta, o insert encontra a linha existente e nada é aplicado duas vezes.

O padrão protege efeitos **dentro do seu banco**. Se o efeito do consumidor for uma chamada ao banco parceiro, a tabela de mensagens processadas não cobre esse efeito, porque a chamada é uma foreign state mutation. Para essa etapa você precisa do que Brandur mostrou: commitar a intenção primeiro e depois chamar o parceiro com uma chave derivada do seu próprio registro. A quarta junta todos esses pontos num só desenho.

## 7. Dois padrões, uma ideia

*Fonte principal: o artigo de Brandur Leach e o padrão de Richardson, comparados lado a lado.*

O padrão da API e o padrão do consumidor parecem diferentes, mas compartilham um movimento: **dar à operação uma identidade estável e deixar que uma constraint única, na mesma transação do efeito, decida se ela já aconteceu.**

| | API com idempotency keys | Consumidor idempotente |
| --- | --- | --- |
| Quem escolhe o ID | O cliente (`Idempotency-Key`) | O produtor (`message_id`) |
| Onde fica guardado | `idempotency_keys`, único em `(user_id, key)` | `processed_messages`, único em `(subscriber_id, message_id)` |
| O que uma duplicata recebe | A resposta armazenada | É ignorada em silêncio |
| Duplicata concorrente | `409` enquanto em andamento | Espera no índice único, depois pula |
| Trabalho em vários passos | Recovery points | Normalmente uma transação por mensagem |

## O que anotar hoje

1. Os quatro casos do upsert da chave (nova, parâmetros diferentes, em andamento, lock expirado) e o código de status que seu TCM devolve em cada um.
2. Por que a chave repassada ao provedor é derivada do seu registro interno, e contra o que ela protege.
3. O que o completer, o enqueuer e o reaper fazem, numa linha cada.
4. O consumidor idempotente: entrega at-least-once, uma tabela `processed_messages` com chave `(subscriber_id, message_id)`, e por que ela precisa ser gravada na mesma transação do efeito.

## Teste-se

Estas perguntas dão bons flashcards (veja o [guia de flashcards](../../FLASHCARDS.pt-BR.md)).

- Por que `locked_at` é um timestamp e não um booleano?
- O que um erro temporário do provedor deve fazer com o estado da chave, e o que um erro definitivo deve fazer?
- O que o completer precisa encontrar guardado na chave para terminar uma requisição sem o cliente?
- Por que Brandur sugere manter as chaves por cerca de 72 horas, e não 24?
- O que acontece se um consumidor registra o message ID e faz commit antes de aplicar o efeito?
- Por que a chave das mensagens processadas é `(subscriber_id, message_id)` e não só `message_id`?
- Por que uma tabela de mensagens processadas não consegue proteger uma chamada ao banco parceiro?

## Referências

- **Fonte principal (seções 1 a 5):** Brandur Leach, ["Implementing Stripe-like Idempotency Keys in Postgres"](https://brandur.org/idempotency-keys), segunda metade: de "Idempotency key upsert" até o fim, incluindo "Other processes", "Murphy in action", "Complications" e "Cultivating passive safety". Gratuito.
- **Fonte principal (seções 6 e 7):** Chris Richardson, ["Pattern: Idempotent Consumer"](https://microservices.io/patterns/communication-style/idempotent-consumer.html), microservices.io. Curto; leia inteiro. Gratuito.
