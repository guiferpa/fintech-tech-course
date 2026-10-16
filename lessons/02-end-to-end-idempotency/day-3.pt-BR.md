# Módulo 2, quarta-feira: idempotência em cada etapa

[Módulo 2](../../modules/02-end-to-end-idempotency.pt-BR.md) · [Read in English](day-3.md)

**Tempo de leitura:** cerca de 45 minutos. Use o resto do bloco de 2 horas nas páginas da Stripe do final e depois desenhe o fluxo descrito na seção 5.

Este é um texto original escrito para este curso. Ele se baseia nas referências listadas no final, e cada seção indica a fonte que segue.

## Por que isso importa para uma fintech

Na segunda e na terça você aprendeu os dois padrões: idempotency keys na API, mensagens processadas no consumidor. Fluxos reais encadeiam várias etapas, e basta uma etapa sem proteção para enviar dinheiro duas vezes. Hoje você vê como um provedor real documenta seu contrato de idempotência, aprende a reconhecer quais operações já são seguras de repetir e depois desenha o fluxo inteiro da carteira, marcando cada ponto em que uma duplicata é barrada. Esse desenho é a resposta à pergunta do teste de domínio deste módulo. O laboratório então o transforma nos casos de teste de quinta.

## 1. Como um provedor real documenta o contrato

*Fonte principal: referência da API da Stripe, "Idempotent requests", e documentação da Stripe, "Advanced error handling".*

A página da referência da API da Stripe sobre requisições idempotentes é curta, e cada frase nela é uma decisão de design. Lê-la como quem projeta APIs, e não como usuário da Stripe, é a melhor preparação para escrever seu próprio `docs/m02.md`. Eis o que ela especifica para a API v1, com a decisão por trás de cada ponto.

| O que a Stripe documenta | A decisão por trás |
| --- | --- |
| O cliente gera a chave; a Stripe sugere UUIDs V4 ou outra string aleatória com entropia suficiente | A chave identifica a operação, e só o cliente sabe quando uma operação é nova |
| As chaves têm até 255 caracteres | Um limite superior fixo que você pode impor com um `CHECK` |
| Não coloque dados sensíveis, como endereços de email, na chave | Chaves vão para logs e ficam guardadas; não devem carregar significado |
| A Stripe salva o código de status e o corpo da primeira requisição quando o endpoint começa a executar | Um retry recebe exatamente a primeira resposta, não um cálculo novo |
| Retries devolvem a resposta salva, **inclusive erros `500`** | Um replay é um replay, mesmo de uma falha |
| As chaves podem ser removidas quando têm pelo menos 24 horas; uma chave reutilizada depois disso é uma requisição nova | Chaves dão segurança de curto prazo, não um arquivo permanente |
| Os parâmetros recebidos são comparados com os originais, e uma divergência é um erro | A mesma chave com outro corpo é bug do cliente, não um retry |
| Nada é salvo se a validação falhar ou se outra requisição com a mesma chave estiver executando ao mesmo tempo | Essas requisições podem simplesmente ser repetidas |
| Todas as requisições `POST` aceitam chaves; enviá-las em `GET` ou `DELETE` não tem efeito | Esses verbos são idempotentes por definição |

A página da referência resume o propósito numa linha: "When creating or updating an object, use an idempotency key."

A página "Advanced error handling" da Stripe, linkada a partir da referência, acrescenta o lado do cliente do contrato. Vale copiar quatro pontos para suas anotações:

- **Um `409` significa que outra requisição com a mesma chave ainda está rodando.** A página manda esperar e fazer retry com a mesma chave e os mesmos parâmetros, e avisa que uma chave nova pode iniciar uma segunda operação.
- **Um `500` é indeterminado.** A operação pode ter produzido efeitos colaterais. Não faça retry com uma chave nova até saber o que aconteceu: busque o objeto, confira o dashboard ou espere os webhooks. Esse é o estado `UNKNOWN` do Módulo 1, escrito por uma empresa de pagamentos.
- **Existe uma janela de retry.** Continue fazendo retry com a mesma chave por até 24 horas. Depois disso, pare e concilie, em vez de fazer retry com a chave antiga ou com uma nova.
- **Replays são identificados.** Uma resposta servida pela camada de idempotência traz o header `Idempotent-Replayed: true`, e um header `Stripe-Should-Retry` pode dizer ao cliente se deve fazer retry.

A mesma página lista duas formas de montar chaves: um UUID v4 aleatório, ou uma chave derivada de um objeto que o usuário já tem, como o ID de um carrinho de compras. Essa segunda opção leva direto à próxima seção. Mais um detalhe: a API v2, mais nova, da Stripe usa outro comportamento de replay e uma janela de 30 dias, o que mostra que até o contrato do provedor é uma escolha, não uma lei da natureza.

## 2. Chaves naturais e chaves do cliente

*Fonte principal: síntese do curso, usando a documentação da Stripe acima e o desenho do Rocket Rides de Brandur Leach.*

Uma idempotency key responde a uma pergunta: "Esta é a mesma operação que eu já vi?" Há duas formas de obter essa identidade.

Uma **chave do cliente** é um valor aleatório arbitrário que o cliente gera para a ocasião, como o header `Idempotency-Key`. Ela não carrega significado de negócio. Só funciona se o cliente a guardar e reutilizar nos retries.

Uma **chave natural** é um identificador que já existe no domínio e é único para cada operação real. Exemplos numa carteira:

- **O end-to-end ID do Pix (`end_to_end_id`).** Todo pagamento Pix carrega um identificador end-to-end único, que todos os participantes usam para se referir àquele pagamento. Quando sua carteira recebe do banco parceiro a notificação de um Pix recebido, esse ID é a chave natural de deduplicação. Duas notificações com o mesmo `end_to_end_id` são o mesmo pagamento, então você credita o usuário uma vez.
- **O ID de um boleto ou fatura** quando o usuário paga uma conta.
- **O ID da transferência no parceiro** quando o parceiro envia uma atualização de status sobre uma transferência.
- **O ID de um carrinho ou pedido**, o exemplo da documentação da Stripe.

Chaves naturais são atraentes porque você não depende do bom comportamento do cliente. A regra é imposta por uma constraint `UNIQUE` numa coluna que precisa existir de qualquer jeito:

```sql
CREATE TABLE incoming_pix (
  id             BIGSERIAL PRIMARY KEY,
  end_to_end_id  TEXT NOT NULL UNIQUE,
  account_id     BIGINT NOT NULL REFERENCES accounts (id),
  amount_cents   BIGINT NOT NULL CHECK (amount_cents > 0),
  received_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

Uma chave natural tem dois limites. Primeiro, ela só existe quando o domínio fornece uma: "enviar R$ 200 para a Ana" a partir do app não tem ID natural até seu sistema criar a transferência. Por isso a API usa uma chave do cliente. Segundo, uma chave natural identifica o evento de negócio, não a requisição HTTP. Ela consegue dizer "já creditado", mas não guarda a resposta para replay.

Uma regra prática útil: **use uma chave natural sempre que o domínio fornecer uma, e uma chave do cliente onde ele não fornecer.** Muitos fluxos usam as duas. A chave do cliente protege a chamada à API que cria a transferência. O próprio ID da transferência então vira a chave natural de todas as etapas seguintes.

## 3. Operações naturalmente idempotentes

*Fonte principal: síntese do curso, a partir da seção "Making liberal use of idempotency" do blog da Stripe e do exemplo `AccountDebited` de Richardson.*

Algumas escritas são seguras de repetir sem chave nenhuma, porque o resultado não depende de quantas vezes rodam. Outras mudam o estado por um valor relativo, e cada repetição causa estrago.

Compare estes dois comandos:

```sql
-- Naturalmente idempotente: uma transição de estado condicional.
UPDATE transfers
SET status = 'COMPLETED', completed_at = now()
WHERE id = $1 AND status = 'PENDING';

-- Não idempotente: uma mudança relativa.
UPDATE accounts
SET balance_cents = balance_cents - 10000
WHERE id = $1;
```

O primeiro tem efeito uma vez. Na segunda vez, a cláusula `WHERE` não encontra nenhuma linha, então nada muda. A contagem de linhas (1 na primeira vez, 0 depois) também diz ao código se esta chamada fez o trabalho, o que é útil para decidir se deve emitir um evento.

O segundo comando subtrai R$ 100 toda vez que roda. É exatamente o exemplo `AccountDebited` de Richardson: o consumidor só está correto se nunca vir a mesma mensagem duas vezes, e a entrega at-least-once garante que vai ver.

| Operação | Idempotente por natureza? | Como torná-la segura |
| --- | --- | --- |
| `SET status = 'COMPLETED' WHERE status = 'PENDING'` | Sim | Nada a mais; confira a contagem de linhas |
| `SET email = 'ana@example.com'` | Sim | Nada a mais |
| `INSERT ... ON CONFLICT (end_to_end_id) DO NOTHING` | Sim | A constraint única é a proteção |
| `SET balance = balance - 100` | Não | Chave ou mensagem processada na mesma transação |
| `INSERT INTO ledger_entries ...` sem referência única | Não | Acrescente um único `(transfer_id, leg)` ou algo parecido |
| Chamada ao parceiro "envie R$ 200" | Não | Repasse uma chave estável ao parceiro |

O objetivo de design sai da tabela: **transforme mudanças relativas em transições de estado ou em inserts protegidos por uma chave única.** Um ledger é o exemplo clássico. Em vez de atualizar um saldo, você insere lançamentos, cada um com uma referência única à transferência que o causou. O Módulo 4 constrói o ledger em cima dessa ideia. Por enquanto, repare que uma constraint única na referência do lançamento torna a gravação naturalmente idempotente.

## 4. Repassando a chave ao provedor

*Fonte principal: Brandur Leach, "Implementing Stripe-like Idempotency Keys in Postgres", seção "Calling Stripe", e a documentação da Stripe acima.*

Sua API pode ser perfeitamente idempotente e ainda assim enviar dinheiro duas vezes se a chamada ao banco parceiro não for. O worker dá timeout, faz retry, e o parceiro vê duas requisições separadas. A correção é enviar uma idempotency key ao parceiro, mas qual chave?

O Rocket Rides de Brandur mostra a resposta: monte a chave repassada a partir do **seu próprio registro durável**, e não do valor bruto do cliente. O Rocket Rides usa `rocket-rides-atomic-` mais o ID interno da linha da idempotency key. Na carteira, o ID da transferência é uma escolha natural: `wallet-transfer-812`. Três propriedades fazem isso funcionar:

1. **Ela existe antes da chamada.** A linha da transferência é commitada numa fase atômica antes de o worker chamar o parceiro (a regra de segunda).
2. **Ela é a mesma em toda tentativa.** Venha o retry do mesmo worker, de outro pod, do completer ou de um job de conciliação, todos leem a mesma linha da transferência e enviam a mesma chave.
3. **Ela é única no sistema inteiro.** Dois usuários que enviaram a mesma chave do cliente ainda recebem chaves repassadas diferentes.

```typescript
// Worker chamando o banco parceiro; a chave vem da linha da transferência já commitada.
const res = await this.partner.post('/payments', payload, {
  headers: { 'Idempotency-Key': `wallet-transfer-${transfer.id}` },
  timeout: 10_000,
});
```

Depois, leia o contrato do provedor com o mesmo cuidado com que leu o da Stripe. Pergunte por quanto tempo ele guarda as chaves, o que devolve para uma chave em andamento e se faz replay de erros. Se seus retries podem durar mais que a janela de chaves do provedor, a chave deixa de proteger você. Nesse ponto, siga o conselho que a própria Stripe dá aos clientes dela: pare de fazer retry e **consulte o status** pela sua referência. Se o parceiro não aceita chave nenhuma, recorra ao conselho de "Complications" de Brandur, visto na terça: trate falhas ambíguas como desconhecidas e concilie, nunca como seguras para retry.

No TCM de quinta, o banco parceiro falso também deduplica por esse header. Isso permite que seu teste prove a cadeia inteira, e não só a API.

## 5. Juntando tudo: cada ponto de idempotência do fluxo

*Fonte principal: síntese do curso a partir das três leituras da semana.*

Eis o fluxo de "enviar R$ 200 para outro banco", com cada etapa em que uma duplicata pode aparecer e o que a barra.

```text
 App
   | POST /transfers, Idempotency-Key: K (gerada uma vez, reutilizada no retry)
   v
 [1] API ............. idempotency_keys UNIQUE (user_id, key)
   |                    mesma chave + mesmo corpo -> resposta armazenada
   |                    mesma chave + outro corpo -> 422
   |                    ainda em andamento        -> 409
   | tx: linha da transferência + hold + mensagem de saída, commitados juntos
   v
 [2] Fila ............ at-least-once: a mensagem pode chegar duas vezes
   |                    message_id = id da transferência (estável)
   v
 [3] Worker .......... processed_messages UNIQUE (subscriber_id, message_id)
   |                    + update condicional: status 'PENDING' -> 'SENDING'
   | Idempotency-Key: wallet-transfer-<id>
   v
 [4] Banco parceiro .. deduplica pela chave repassada; timeout -> UNKNOWN, consultar depois
   |
   v
 [5] Webhook ......... deduplica pelo ID da transferência no parceiro (chave natural)
                        + update condicional 'SENDING' -> 'COMPLETED'
```

E os motivos, um por ponto, que é o que o teste de domínio pede que você diga em voz alta:

| Ponto | O que pode duplicar | O que barra | Por que aqui |
| --- | --- | --- | --- |
| 1. API | Retries do cliente depois de um timeout | Chave do cliente, resposta armazenada, lock | Só o cliente sabe quais tentativas são a mesma operação |
| 2. Fila | A API publicando duas vezes, ou o broker reentregando | Um message ID estável, tirado da transferência | O ID precisa estar fixo antes de a mensagem sair |
| 3. Worker | Reentrega depois de uma queda antes do ack | Mensagens processadas na mesma transação do efeito, mais transições de estado | Brokers prometem at least once, não exactly once |
| 4. Parceiro | O worker repetindo uma chamada que deu timeout | Chave repassada derivada do ID da transferência | A chamada é uma foreign state mutation; sua transação não a desfaz |
| 5. Webhook | O parceiro reenviando a notificação | Chave natural e update condicional | Notificações também são at least once |

Uma frase resume o desenho inteiro: **toda etapa é at least once, então todo receptor precisa deduplicar, e todo ID precisa estar fixo antes de cruzar uma fronteira.**

## 6. Preparando os testes de quinta

*Fonte principal: as tarefas do TCM deste módulo.*

O laboratório de hoje é listar os casos de teste e criar as migrations vazias, sem escrever código do TCM. Eis os quatro casos da página do módulo, com o que cada um deve provar.

| Teste | Preparação | Esperado |
| --- | --- | --- |
| Mesma chave, mesmo corpo | Envie uma transferência, espere o `201`, envie de novo | A segunda resposta é igual à primeira (status e corpo); uma transferência no banco |
| Mesma chave, corpo diferente | Envie uma transferência, depois a mesma chave com outro valor | `422`; continua uma transferência, com o primeiro valor |
| Requisição ainda em andamento | Deixe o parceiro lento, envie a mesma chave duas vezes sem esperar | Uma recebe o resultado, a outra recebe `409`; uma transferência |
| 50 simultâneas | Dispare 50 requisições com a mesma chave ao mesmo tempo | Exatamente uma transferência, um hold, uma chamada ao parceiro; as demais recebem `409` ou a resposta armazenada |

Vale acrescentar alguns casos à lista, mesmo que você não codifique todos na quinta: a mesma chave vinda de dois usuários diferentes (duas transferências), um worker que recebe a mesma mensagem duas vezes (uma gravação no ledger) e uma chamada ao parceiro que dá timeout e é repetida (um pagamento no parceiro).

Para as migrations, crie arquivos vazios para `idempotency_keys` e `processed_messages`. Escreva as colunas como comentários, decida as constraints únicas e anote o timeout de lock que vai usar. O código fica para quinta.

## O que anotar hoje

1. Da referência da Stripe: tamanho da chave, expiração, o que é devolvido em replay (inclusive `500`), o que acontece com parâmetros divergentes e com uma requisição concorrente.
2. Chave natural x chave do cliente, com o `end_to_end_id` do Pix como exemplo de chave natural e o header `Idempotency-Key` como exemplo de chave do cliente.
3. Dois comandos SQL lado a lado: um naturalmente idempotente (`SET status ... WHERE status = 'PENDING'`) e um não idempotente (`balance = balance - 100`), e como você tornaria o segundo seguro.
4. Como você repassa a chave ao provedor, e o que faz quando a janela de chaves dele já passou.
5. No papel: API → fila → worker → provedor, com cada ponto de idempotência e o motivo de cada um. Guarde essa folha para o teste de domínio.

## Teste-se

Estas perguntas dão bons flashcards (veja o [guia de flashcards](../../FLASHCARDS.pt-BR.md)).

- O que a Stripe devolve quando você faz retry de uma chave cuja primeira tentativa recebeu `500`?
- O que a Stripe manda um cliente fazer depois de um `409` numa requisição idempotente?
- Quando uma chave natural é melhor que uma chave do cliente, e quando você não pode usar uma?
- Por que `UPDATE ... SET status = 'COMPLETED' WHERE status = 'PENDING'` é seguro de repetir?
- Por que a chave repassada ao parceiro deve vir do ID da sua transferência, e não da chave do cliente?
- No fluxo API → fila → worker → provedor, qual etapa uma tabela de mensagens processadas protege?
- O que você deve fazer quando uma operação continua desconhecida depois da janela de chaves do provedor?

## Referências

- **Fonte principal (seção 1):** referência da API da Stripe, ["Idempotent requests"](https://docs.stripe.com/api/idempotent_requests). Curta; leia inteira. Gratuito.
- Documentação da Stripe, ["Advanced error handling"](https://docs.stripe.com/error-low-level), seções "Content errors", "Server errors" e "Idempotency". O lado do cliente do mesmo contrato. Gratuito.
- **Fonte principal (seção 4):** Brandur Leach, ["Implementing Stripe-like Idempotency Keys in Postgres"](https://brandur.org/idempotency-keys), seções "Calling Stripe" e "Complications". Gratuito. Você leu o artigo na segunda e na terça; releia essas duas partes.
- Chris Richardson, ["Pattern: Idempotent Consumer"](https://microservices.io/patterns/communication-style/idempotent-consumer.html), microservices.io, para o ponto 3 do desenho. Gratuito.
- No papel (sem referência): chave natural x chave do cliente, operações naturalmente idempotentes x não idempotentes, repasse da chave e o desenho do fluxo completo. As seções 2 a 6 deste texto são seu guia.
