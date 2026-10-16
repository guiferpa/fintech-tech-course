# Módulo 2, segunda-feira: idempotency keys e fases atômicas

[Módulo 2](../../modules/02-end-to-end-idempotency.pt-BR.md) · [Read in English](day-1.md)

**Tempo de leitura:** cerca de 45 minutos. Use o resto do bloco de 2 horas nas referências do final, começando pelas seções marcadas como fonte principal.

Este é um texto original escrito para este curso. Ele se baseia nas referências listadas no final, e cada seção indica a fonte que segue. Quando uma ideia vem de um autor específico, o texto diz isso.

## Por que isso importa para uma fintech

O Módulo 1 terminou com uma regra: um timeout significa "não sei". O cliente da API da sua carteira digital vai esbarrar nessa regra todos os dias. Um celular perde sinal no elevador, um load balancer derruba uma conexão, um pod reinicia no meio de uma requisição. A única reação razoável do cliente é tentar de novo.

Fazer retry é fácil. Fazer retry de uma transferência sem enviar o dinheiro duas vezes é a parte difícil. Nesta semana você fecha essa lacuna em cada etapa do fluxo: a API, os consumidores de mensagens e a chamada ao banco parceiro. Hoje cobre a primeira etapa: o que é uma idempotency key, como um cliente deve usá-la e como o servidor deve dividir seu trabalho para que um retry continue de onde a última tentativa parou.

## 1. Três formas de uma requisição falhar

*Fonte principal: blog da Stripe, "Designing robust and predictable APIs with idempotency", seção "Planning for failure".*

Em 2017, Brandur Leach, então no time de API da Stripe, escreveu o post que a maioria dos engenheiros cita quando explica idempotency keys. Ele parte de uma observação simples: uma chamada de rede pode quebrar em três momentos diferentes, e cada um deixa o cliente com uma quantidade diferente de informação.

| Quando quebra | O que aconteceu no servidor | Um retry cego é seguro? |
| --- | --- | --- |
| A conexão nem chega a abrir | Nada | Sim |
| A conexão cai enquanto o servidor trabalha | Parte do trabalho pode estar feita | Não necessariamente |
| O servidor termina, mas a resposta se perde | Todo o trabalho está feito | Não, ele repete o efeito |

O primeiro caso é inofensivo. O terceiro é o perigoso, e é exatamente o "a requisição chegou e foi processada, mas a resposta se perdeu" do Módulo 1. O caso do meio é o mais interessante, porque o servidor pode ficar num estado pela metade. Boa parte da segunda fonte de hoje trata desse caso do meio.

Pense num usuário da carteira que toca em "Enviar R$ 200" para um amigo. Se o cliente recebe um timeout, ele não consegue saber em qual linha da tabela está. Se ele faz retry e o servidor trata o retry como uma requisição nova, o amigo recebe R$ 400 e quem enviou perde R$ 400. Se ele não faz retry, quem enviou talvez nunca saiba se o dinheiro saiu.

## 2. Algumas operações são idempotentes por natureza

*Fonte principal: blog da Stripe, "Designing robust and predictable APIs with idempotency", seção "Making liberal use of idempotency".*

Uma operação é **idempotente** quando executá-la duas vezes tem o mesmo efeito que executá-la uma vez. O cliente pode chamar um endpoint idempotente quantas vezes precisar até ver um sucesso.

O post da Stripe usa um exemplo de DNS: um `PUT` que cria um registro DNS pode ser repetido com segurança, porque a segunda chamada encontra o registro já criado e simplesmente informa sucesso. Ele também lembra que o HTTP define `PUT` e `DELETE` como idempotentes. `GET` não tem efeito colateral nenhum, então também é seguro repetir. `POST` não traz essa promessa.

Muitas operações de uma carteira podem ser escritas de forma idempotente por natureza:

- "Defina o email de notificação do usuário como `ana@example.com`" produz o mesmo estado final, não importa quantas vezes rode.
- "Cancele a transferência 812" pode ser escrita de modo que uma segunda chamada encontre a transferência já cancelada e não faça nada.
- "Marque a transferência 812 como `COMPLETED`" é seguro de repetir se só mover a transferência a partir de `PENDING`.

O problema são as operações cujo objetivo é justamente mudar algo por um valor relativo: "debite R$ 200", "cobre o cartão", "crie uma transferência". Executá-las duas vezes nunca é o mesmo que executá-las uma vez. A quarta-feira volta a essa distinção em detalhe, com SQL.

## 3. Idempotency keys: tornando seguro o retry de uma chamada não idempotente

*Fonte principal: blog da Stripe, "Designing robust and predictable APIs with idempotency", seções "Guaranteeing exactly once semantics" e "Being a good distributed citizen".*

Para operações que não podem acontecer duas vezes, o post da Stripe descreve o mecanismo que a API da Stripe usa: o cliente gera um valor único, a **idempotency key**, e o envia com a requisição no header HTTP `Idempotency-Key`. Se a requisição falha, o cliente faz retry com **a mesma chave**. O servidor usa a chave para reconhecer o retry e decidir o que fazer, conforme o ponto em que a primeira tentativa quebrou:

- **A conexão nem abriu.** O servidor vê a chave pela primeira vez e processa a requisição normalmente.
- **O servidor falhou no meio.** O servidor retoma o trabalho ou o desfaz com segurança. Como ele faz isso depende da implementação, que é o que o segundo artigo de Brandur explica.
- **A resposta se perdeu.** O servidor devolve o resultado armazenado da primeira tentativa e não executa a operação de novo.

Visto de fora, o cliente obtém comportamento "exactly once" para o efeito, mesmo que a requisição em si seja enviada muitas vezes. No resumo do próprio post: "Use idempotency and idempotency keys to allow clients to pass a unique value and retry requests as needed."

### O que isso significa para o cliente

A chave pertence à **operação**, não à tentativa HTTP. Isso tem consequências práticas para o app da sua carteira ou para qualquer serviço que chame sua API:

1. Gere a chave uma vez, quando o usuário confirma a transferência, e não dentro do loop de retry.
2. Guarde a chave junto com a operação pendente (no dispositivo ou no banco do serviço que chama), para que um retry depois de reiniciar o app ainda a use.
3. Envie a mesma chave e o mesmo corpo em toda tentativa.
4. Só gere uma chave nova quando o usuário começar uma operação realmente nova.

Um cliente que cria um UUID novo a cada tentativa HTTP tem idempotency keys só no nome. Cada retry parece novo para o servidor.

### Fazendo retry com educação

A última seção técnica do post trata da frequência dos retries. Se milhares de clientes fazem retry imediatamente depois de um soluço no servidor, eles mantêm o servidor fora do ar. O post recomenda **exponential backoff**: esperar mais depois de cada falha (por exemplo 1 s, 2 s, 4 s, 8 s). Também recomenda somar um **jitter** aleatório a cada espera. Sem jitter, clientes que falharam no mesmo instante também fazem retry no mesmo instante, e o post chama essa rajada de "thundering herd".

```typescript
// Lado do cliente: uma chave por operação, reutilizada em toda tentativa.
async function sendTransfer(body: TransferBody, key: string) {
  for (let attempt = 0; attempt < 5; attempt++) {
    try {
      return await http.post('/transfers', body, {
        headers: { 'Idempotency-Key': key },
        timeout: 5_000,
      });
    } catch (err) {
      if (!isRetryable(err)) throw err;
      const base = 2 ** attempt * 1_000;
      await sleep(base / 2 + Math.random() * (base / 2)); // backoff com jitter
    }
  }
  throw new Error('Gave up: outcome unknown, check status later');
}
```

Repare na mensagem de erro final. Depois da última tentativa, o cliente ainda não sabe se a transferência aconteceu. Ele deve mostrar "processando" e consultar o status depois, nunca "falhou".

O post fecha com três princípios, que resumem bem esta seção: tratar falhas de forma **consistente** (clientes fazem retry), **segura** (idempotency keys) e **responsável** (exponential backoff com jitter).

## 4. Foreign state mutations: a parte que uma transação não desfaz

*Fonte principal: Brandur Leach, "Implementing Stripe-like Idempotency Keys in Postgres", seções "Rocket Rides" e "Foreign state mutations".*

O post da Stripe diz o que o servidor precisa fazer. O artigo mais longo de Brandur, no site dele, mostra como construir isso com Postgres. Ele define o termo assim: "An idempotency key is a unique value that’s generated by a client and sent to an API along with a request." O servidor guarda a chave, acompanha o progresso da requisição nela e, quando a requisição termina, guarda o resultado, para que uma repetição com a mesma chave receba a mesma resposta.

O exemplo que atravessa o artigo é o Rocket Rides, um app de demonstração de caronas da Stripe. Criar uma corrida executa sete passos: inserir a idempotency key, criar a corrida, criar um registro de auditoria, cobrar o usuário pela Stripe, salvar o ID da cobrança na corrida, enviar um recibo por email e guardar a resposta final na chave. Ele então lista o que dá errado em produção: o banco recusa um insert ou perde a conexão, a chamada à Stripe dá timeout, o provedor de email falha, ou o cliente simplesmente desconecta no meio.

A ideia central do artigo é a **foreign state mutation**: uma mudança feita num sistema fora do seu próprio banco de dados. Uma cobrança na Stripe é uma. Um email também, um registro DNS também e, no nosso caso, uma transferência enviada ao banco parceiro. Brandur também conta como externas as chamadas aos seus próprios serviços internos e a publicação no Kafka, porque elas podem falhar independentemente da sua transação.

Por que a distinção importa? Dentro do Postgres, uma transação que falha sofre rollback e não deixa rastro. Fora dele, não existe rollback. Nas palavras de Brandur, "once we make our first foreign state mutation, we’re committed one way or another." Ele observa que o two-phase commit poderia, em teoria, desfazer mudanças em vários sistemas, mas é complexo o bastante para que software real raramente o use.

Aplique isso a uma transferência da carteira para outro banco:

| Passo | Local ou externo? |
| --- | --- |
| Inserir a idempotency key | Local |
| Criar a linha em `transfers` e colocar um hold no saldo de quem envia | Local |
| Gravar um registro de auditoria | Local |
| Pedir ao banco parceiro que envie o dinheiro | **Externo** |
| Salvar o ID da transferência no parceiro | Local |
| Enviar uma notificação push | Externo, mas pode ser adiado |
| Guardar a resposta na chave | Local |

## 5. Fases atômicas

*Fonte principal: Brandur Leach, "Implementing Stripe-like Idempotency Keys in Postgres", seção "Atomic phases".*

A resposta de Brandur é agrupar os passos locais em **fases atômicas**. Uma fase atômica é um conjunto de mudanças locais commitadas juntas numa transação do banco, situada entre duas foreign state mutations. O Postgres garante que ou todas acontecem ou nenhuma acontece.

A regra principal é curta: "Atomic phases should be safely committed before initiating any foreign state mutation." Antes de chamar o banco parceiro, a linha em `transfers`, o hold e o registro de auditoria já precisam estar commitados. Se a chamada então falhar, cair ou der timeout, seu banco ainda registra que a tentativa foi feita. Um retry, ou um processo em background, consegue encontrá-la e continuar. Se você chamasse o banco parceiro primeiro e caísse antes do commit, teria enviado dinheiro sem nenhum registro local do motivo.

Cada chamada externa ganha sua própria fronteira de fase, e todo o trabalho local entre duas chamadas externas entra numa única fase. Para a transferência da carteira, isso dá:

1. **Fase 1 (transação):** inserir ou travar a idempotency key.
2. **Fase 2 (transação):** criar a transferência, colocar o hold, gravar a auditoria.
3. **Chamada externa:** pedir ao banco parceiro que envie o dinheiro.
4. **Fase 3 (transação):** salvar o ID do parceiro e atualizar a transferência.
5. **Fase 4 (transação):** agendar a notificação e guardar a resposta final na chave.

Brandur acrescenta mais uma técnica. Trabalho que não precisa acontecer dentro da requisição, como o email de recibo, deve virar um job em background. Ele grava o job numa tabela `staged_jobs` **na mesma transação** da fase, de modo que ele só fica visível para os workers depois do commit. Um processo separado move os jobs commitados para a fila de verdade. A chamada de pagamento, porém, não pode ser adiada no Rocket Rides, porque a requisição precisa dizer ao usuário se a cobrança deu certo. Módulos posteriores voltam a essa ideia de "gravar a mensagem na mesma transação", porque ela é o núcleo do padrão outbox.

## 6. Recovery points

*Fonte principal: Brandur Leach, "Implementing Stripe-like Idempotency Keys in Postgres", seções "Recovery points" e "The idempotency key relation".*

Se uma requisição morre entre fases, o retry precisa saber onde recomeçar. Brandur guarda isso na própria chave, numa coluna chamada `recovery_point`. Ele descreve um recovery point como "a name of a check point that we get to after having successfully executed any atomic phase." O Rocket Rides usa quatro: `started`, `ride_created`, `charge_created` e `finished`.

O detalhe importante é que o recovery point é atualizado **dentro da mesma transação da fase que ele marca**. Os dados da fase e o checkpoint são commitados juntos ou não são, então o checkpoint nunca pode afirmar um trabalho que não existe.

Os recovery points formam um caminho que só anda para frente. Um retry lê o ponto atual e pula para a próxima fase. Uma requisição em `finished` não executa nada de novo: o servidor só devolve a resposta armazenada.

Eis um esboço de como essa tabela poderia ficar na carteira. Ele segue o formato da tabela `idempotency_keys` de Brandur, adaptado aos nomes deste curso:

```sql
CREATE TABLE idempotency_keys (
  id               BIGSERIAL PRIMARY KEY,
  user_id          BIGINT      NOT NULL REFERENCES users (id),
  idempotency_key  TEXT        NOT NULL CHECK (char_length(idempotency_key) <= 255),
  request_method   TEXT        NOT NULL,
  request_path     TEXT        NOT NULL,
  request_hash     TEXT        NOT NULL,          -- hash do corpo da requisição
  recovery_point   TEXT        NOT NULL DEFAULT 'started',
  locked_at        TIMESTAMPTZ DEFAULT now(),     -- NULL quando ninguém está trabalhando nela
  response_code    INT,
  response_body    JSONB,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  last_run_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (user_id, idempotency_key)
);
```

Vale reparar em algumas escolhas, que você vai defender no `docs/m02.md` na sexta:

- A unicidade é em `(user_id, idempotency_key)`, como no schema de Brandur. Dois usuários que por acaso mandem a mesma chave nunca colidem, e um usuário não consegue receber a resposta de outro.
- Brandur guarda os parâmetros completos da requisição em JSONB, para poder rejeitar um retry com parâmetros diferentes e completar depois uma requisição inacabada. O TCM deste curso guarda um hash do corpo para a comparação; se você quiser um completer em background, também precisa dos próprios parâmetros.
- `locked_at` indica que algum processo está trabalhando na chave agora. A terça mostra como isso impede que duas tentativas rodem ao mesmo tempo.
- Brandur diz que as chaves têm vida curta: "Keys are not meant to be used as a permanent request archive but rather as a mechanism for ensuring near-term correctness." Um job de limpeza apaga as linhas antigas.

Numa transferência da carteira, os recovery points seriam `started`, `transfer_created`, `partner_called` e `finished`. Escrever a transferência como fases, chamadas externas e recovery points é o principal exercício de hoje.

## O que anotar hoje

1. Os três momentos em que uma requisição pode falhar (antes da conexão, no meio, depois do trabalho com a resposta perdida) e o que o servidor precisa fazer com uma chave repetida em cada um.
2. Como um bom cliente usa uma idempotency key: quando cria a chave, onde a guarda e o que envia em cada retry. Acrescente uma linha sobre backoff com jitter.
3. As definições de Brandur, com suas palavras: foreign state mutation, fase atômica, recovery point.
4. O fluxo "enviar dinheiro para outro banco" da carteira dividido em fases atômicas e chamadas externas, com um recovery point depois de cada fase.

## Teste-se

Estas perguntas dão bons flashcards (veja o [guia de flashcards](../../FLASHCARDS.pt-BR.md)).

- Por que um cliente precisa reutilizar a mesma idempotency key em todo retry de uma operação?
- Qual dos três momentos de falha faz um retry cego repetir o efeito?
- Por que o jitter importa quando muitos clientes fazem retry ao mesmo tempo?
- O que é uma foreign state mutation, e por que uma transação do banco não consegue desfazê-la?
- O que precisa estar commitado antes da chamada ao banco parceiro, e por quê?
- Por que o recovery point é atualizado na mesma transação da sua fase?
- Por que a constraint única é em `(user_id, idempotency_key)` e não só na chave?

## Referências

- **Fonte principal (seções 1 a 3):** Brandur Leach, ["Designing robust and predictable APIs with idempotency"](https://stripe.com/blog/idempotency), blog da Stripe, 2017. Leia inteiro; é curto. Gratuito.
- **Fonte principal (seções 4 a 6):** Brandur Leach, ["Implementing Stripe-like Idempotency Keys in Postgres"](https://brandur.org/idempotency-keys), primeira metade: do início até "Atomic phases" e o schema em "The idempotency key relation". Gratuito. A terça cobre a segunda metade.
