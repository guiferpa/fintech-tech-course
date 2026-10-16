# Módulo 6, terça-feira: holds, invariantes de conta e dinheiro sumido

[Módulo 6](../../modules/06-ledgers-and-accounting.pt-BR.md) · [Read in English](day-2.md)

**Tempo de leitura:** cerca de 45 minutos. Use o resto do bloco de 2 horas nas referências do final.

Este é um texto original escrito para este curso. Ele se baseia nas referências listadas no final, e cada seção indica a fonte que segue.

## Por que isso importa para uma fintech

O ledger de ontem registra dinheiro que já se moveu. A maioria das operações de uma carteira digital não é assim. Uma compra no cartão primeiro reserva o dinheiro e liquida depois. Uma transferência para um banco parceiro sai da carteira antes de o banco confirmá-la. Um app de corridas reserva R$ 50 e cobra R$ 37. Cada um desses casos precisa de um **hold** (reserva): dinheiro que não está mais disponível, mas ainda não saiu.

Holds trazem duas perguntas que os entrevistadores adoram. Como reservar dinheiro de modo que o passo final nunca deixe a conta negativa? E quando um hold ou uma transferência fica preso no meio do caminho, como você percebe? O TigerBeetle responde à primeira no seu modelo de dados. O Ledger da Stripe responde à segunda com uma regra simples sobre quais saldos deveriam ser zero.

## 1. Um hold é uma transferência em duas fases

*Fonte principal: documentação do TigerBeetle, "Two-Phase Transfers".*

O TigerBeetle é um banco de dados feito só para contabilidade de partidas dobradas. Sua documentação descreve uma **two-phase transfer** (transferência em duas fases): uma transferência que move dinheiro em dois passos em vez de um. O nome vem do protocolo two-phase commit para transações distribuídas.

- **Fase 1, reservar.** Uma transferência criada com a flag `pending` reserva seu valor. Ela soma o valor ao `debits_pending` da conta debitada e ao `credits_pending` da conta creditada. Os saldos posted não mudam.
- **Fase 2, resolver.** Depois, a reserva é resolvida de exatamente uma de três formas: ela é **confirmada** (posted), **anulada** (voided) ou **expira**.

Traga isso para a carteira. Ana paga R$ 100 em um posto de gasolina com cartão. A autorização chega; a carteira cria uma transferência pendente da carteira da Ana para uma conta de liquidação de cartão. O saldo available da Ana cai R$ 100 na hora, mas o saldo posted continua o mesmo. Quando a bandeira envia o valor final, a carteira confirma a transferência. Se a autorização for cancelada, ela a anula. Se nada chegar a tempo, ela expira.

É o mesmo modelo pending/posted/available que você viu ontem em "How to Scale a Ledger". Fornecedor diferente, mesma ideia: valores pendentes ficam em contadores próprios até que algo os resolva.

## 2. Post, post parcial, void e expiração

*Fonte principal: documentação do TigerBeetle, "Two-Phase Transfers".*

A documentação é precisa sobre a segunda fase. Veja o que cada desfecho faz.

| Desfecho | Como é pedido | Efeito |
| --- | --- | --- |
| Post total | Nova transferência com a flag `post_pending_transfer` e `pending_id`, valor igual ao pendente | O valor inteiro passa de pending para posted nas duas contas |
| Post parcial | Igual, com valor menor que o pendente | Só esse valor é confirmado; o resto volta para as contas originais |
| Post acima do valor | Igual, com valor maior que o pendente | Rejeitado com `exceeds_pending_transfer_amount` |
| Void | Nova transferência com a flag `void_pending_transfer` e `pending_id` | A reserva é liberada; os saldos posted não mudam |
| Expiração | A transferência pendente foi criada com um `timeout` que passou | O valor inteiro volta, como num void |

O exemplo numérico da documentação: uma transferência pendente de 123 soma 123 aos contadores pending. Confirmar 100 dela soma 100 a `debits_posted` e `credits_posted`, tira a reserva inteira dos contadores pending, e os outros 23 simplesmente voltam. É exatamente o caso do posto. A autorização foi de R$ 100, o combustível custou R$ 80, e R$ 20 voltam para o saldo available da Ana.

Três regras tornam o modelo seguro, e cada uma corresponde a algo que você construiu em módulos anteriores:

1. **Uma transferência pendente é resolvida uma única vez.** Tentar de novo falha com `pending_transfer_already_posted`, `pending_transfer_already_voided` ou `pending_transfer_expired`. Uma mensagem de "captura" duplicada da bandeira não consegue capturar duas vezes. É idempotência (Módulo 2) embutida no modelo de dados.
2. **Transferências são imutáveis.** Confirmar ou anular nunca edita a transferência pendente. Cria uma nova transferência, com seu próprio `id`, que aponta para a original via `pending_id`. O histórico fica completo.
3. **Timeouts são intervalos em segundos**, não prazos de relógio de parede. O Módulo 1 explicou por quê: relógios em máquinas diferentes discordam, então "expira às 14:00:00" significa coisas diferentes em nós diferentes.

A propriedade mais importante é sobre limites de saldo. A documentação diz que o segundo passo "will never cause the accounts' configured balance invariants" a quebrar, seja ele um post ou um void. O motivo é que o limite é verificado na fase 1, quando o dinheiro é reservado. Uma vez que a reserva existe, confirmá-la (toda ou em parte) só consome dinheiro que já estava separado. O TCM de quinta depende disso: se `available >= 0` é verificado na criação do hold, a captura e a liberação nunca precisam verificar de novo.

## 3. O modelo de conta do TigerBeetle

*Fonte principal: documentação do TigerBeetle, referência "Account".*

A referência de conta é curta, e lê-la é uma boa lição sobre o pouco que uma conta de ledger precisa. Os campos principais são:

| Campo | Significado |
| --- | --- |
| `id` | Identificador de 128 bits escolhido pelo cliente, único no cluster |
| `debits_pending`, `debits_posted` | Somas dos débitos pendentes e confirmados |
| `credits_pending`, `credits_posted` | Somas dos créditos pendentes e confirmados |
| `user_data_128`, `user_data_64`, `user_data_32` | Vínculos opcionais com entidades externas, como o ID do seu usuário |
| `ledger` | Particiona os conjuntos de contas que podem transacionar entre si |
| `code` | Uma categoria da conta definida pelo usuário |
| `flags` | Comportamentos extras, como limites de saldo |
| `timestamp` | Momento de criação em nanossegundos, definido pelo cluster |

Alguns detalhes merecem atenção:

- **Não existe campo de saldo.** A conta guarda quatro contadores, e você calcula os saldos a partir deles, exatamente como as quatro somas das fórmulas de ontem. Os quatro contadores precisam ser zero quando a conta é criada.
- **Os valores são inteiros sem sinal de 128 bits.** Sem casas decimais e sem ponto flutuante. Dinheiro é uma contagem da menor unidade.
- **`ledger` separa o que nunca deve se misturar.** A documentação o descreve como um identificador "that partitions the sets of accounts that can transact with each other". Um uso comum é um ledger por moeda, de modo que uma transferência entre uma conta em BRL e uma em USD é impossível por construção.
- **Contas são imutáveis depois de criadas, exceto os contadores de saldo.** Você não pode "editar" o tipo ou a moeda de uma conta.

A referência também lista os invariantes globais: a soma de todos os `debits_pending` é igual à soma de todos os `credits_pending`, e a soma de todos os `debits_posted` é igual à soma de todos os `credits_posted`. É a regra de soma zero de ontem, enunciada separadamente para cada fase.

## 4. Limites de saldo como flags

*Fonte principal: documentação do TigerBeetle, referência "Account", seção "flags".*

Duas flags permitem que o próprio banco de dados recuse um saldo negativo. A documentação dá as verificações exatas:

- `debits_must_not_exceed_credits`: uma transferência é rejeitada se `debits_pending + debits_posted + amount > credits_posted`.
- `credits_must_not_exceed_debits`: uma transferência é rejeitada se `credits_pending + credits_posted + amount > debits_posted`.

As duas flags não podem estar ligadas na mesma conta. Qual serve para uma carteira? A carteira de um cliente é credit normal (um passivo, como vimos na segunda). Seu saldo é créditos menos débitos, e não pode ficar abaixo de zero. Então a carteira usa `debits_must_not_exceed_credits`.

Agora olhe com cuidado para a verificação. Do lado esquerdo estão todos os débitos, pendentes e confirmados. Do lado direito estão só os créditos confirmados. Reorganizada, a regra diz `credits_posted - (debits_posted + debits_pending) >= amount`. É a fórmula do **saldo available** de segunda, de "How to Scale a Ledger", com os débitos pendentes contados e os créditos pendentes ignorados. Duas fontes independentes chegam à mesma regra. Dinheiro que ainda não chegou não pode ser gasto, e dinheiro reservado não pode ser gasto duas vezes.

A documentação de two-phase mostra a verificação em ação. Uma conta tem a flag, `credits_posted = 100` e `debits_posted = 70`. Uma nova transferência pendente de 50 levaria os débitos a 120, mais que 100, então ela falha na hora, no momento da reserva.

Outras flags da referência valem ser conhecidas pelo nome: `linked` (encadeia várias operações para que todas tenham sucesso ou todas falhem), `history` (guarda o saldo depois de cada transferência, necessário para consultar saldos passados), `imported` (carrega dados históricos com seus próprios timestamps) e `closed` (rejeita novas transferências, exceto anular as pendentes).

No Postgres você não ganha essas flags de graça, mas pode copiar a regra. Antes de inserir um débito pendente em uma carteira, dentro da mesma transação de banco e com a conta protegida contra escritas concorrentes (tema de quarta), verifique:

```sql
SELECT
  COALESCE(SUM(p.amount) FILTER (WHERE p.direction = 'credit' AND t.status = 'posted'), 0)
  - COALESCE(SUM(p.amount) FILTER (WHERE p.direction = 'debit' AND t.status IN ('pending', 'posted')), 0)
    AS available
FROM postings p
JOIN ledger_transactions t ON t.id = p.transaction_id
WHERE p.account_id = $1;
-- rejeite o hold se available < valor pedido
```

Essa é a propriedade que o seu teste baseado em propriedades de sexta vai martelar: nenhuma sequência de 10.000 operações pode deixar o `available` negativo.

## 5. Como um ledger percebe dinheiro sumido

*Fonte principal: blog da Stripe, "Ledger: Stripe's system for tracking and validating money movement", de Ilya Ganelin, 2024.*

O post da Stripe descreve o Ledger, seu sistema interno de registro da movimentação de dinheiro. Os números de escala impressionam: cerca de cinco bilhões de eventos por dia, e mais de 99,9999% da movimentação de dinheiro explicável. Mas a ideia mais útil para você é simples.

O Ledger modela cada sistema que toca dinheiro como contas e eventos que movem saldos entre elas. Ganelin usa uma analogia com água: "At steady state, terminal (nonclearing) reservoirs are full, and intermediate (clearing) pipes are empty." E depois: "If there is water stuck in the pipes, then you have a problem."

Traga isso para a carteira. Algumas contas são **terminais**: a carteira de um cliente, a receita da empresa. É esperado que seus saldos sejam diferentes de zero. Outras são **contas de clearing** (contas transitórias): existem só para segurar o dinheiro enquanto um fluxo está em andamento. Quando o fluxo termina, elas precisam voltar a zero.

Uma transferência da carteira da Ana para um banco externo, via banco parceiro, mostra o padrão:

| Passo | Débito | Crédito |
| --- | --- | --- |
| 1. A carteira envia a transferência ao banco parceiro | Carteira: Ana, R$ 200 | Clearing: transferências de saída, R$ 200 |
| 2. O banco parceiro confirma a liquidação | Clearing: transferências de saída, R$ 200 | Caixa: banco parceiro, R$ 200 |

Depois do passo 2, a conta de clearing volta a zero para essa transferência. Agora suponha que o passo 2 nunca aconteça, porque o webhook de confirmação se perdeu, ou porque foi lançado contra a transferência errada. Os R$ 200 ficam parados na conta de clearing. Nada "falta" na soma, já que o ledger continua fechando, mas há água presa no cano. Uma consulta diária por contas de clearing com saldo diferente de zero, mais antigo que o prazo esperado de liquidação, encontra o problema. O post da Stripe dá um caso real com esse formato: um evento de liberação com o ID de empresa errado deixou fundos em uma conta onde eles deveriam ter zerado.

Ganelin descreve três perguntas de qualidade de dados que a Stripe mede para cada fatia da movimentação de dinheiro:

- **Clearing:** o fluxo terminou, deixando as contas de clearing em zero?
- **Pontualidade (timeliness):** os dados chegaram a tempo?
- **Completude (completeness):** todo evento do sistema de origem tem um evento correspondente no ledger?

O post também reforça que o Ledger é imutável: "Transactions previously published into Ledger cannot be deleted or modified." Correções são novas operações que revertem e reprocessam, não edições. A aula de quarta transforma isso em regras para as suas tabelas no Postgres.

Para o TCM, a lição é barata de aplicar. Dê a cada fluxo de vários passos (holds, transferências de saída, depósitos com cartão) uma conta de clearing ou de reserva, e transforme "esta conta é zero quando tudo liquida" em uma verificação que você consegue rodar. O Módulo 8 constrói a conciliação completa em cima disso.

## 6. Dinheiro no código: inteiros, moeda e arredondamento

O lab de hoje constrói um tipo `Money`: um valor `bigint` em unidades mínimas mais uma moeda, uma divisão determinística e o arredondamento bancário, com testes unitários. As fontes acima apontam todas na mesma direção: o TigerBeetle guarda valores como inteiros sem sinal, e o schema de segunda usa centavos em `bigint`. Veja o que o lab precisa acertar.

**Valor e moeda andam juntos.** Um valor `Money` é o par (valor em unidades mínimas, código de moeda ISO 4217). Somar R$ 1,00 com US$ 1,00 precisa lançar um erro, não devolver 2. Comparar os dois também. Em TypeScript, use `bigint` (ou um inteiro verificado para ficar dentro de `Number.MAX_SAFE_INTEGER`), e nunca faça parse de valores com `parseFloat`.

```typescript
export class Money {
  private constructor(readonly amount: bigint, readonly currency: string) {}

  static of(amount: bigint, currency: string): Money {
    return new Money(amount, currency);
  }

  add(other: Money): Money {
    if (other.currency !== this.currency) {
      throw new Error(`currency mismatch: ${this.currency} vs ${other.currency}`);
    }
    return new Money(this.amount + other.amount, this.currency);
  }
}
```

**Uma divisão não pode perder nem inventar um centavo.** Dividir R$ 1,00 (100 centavos) em 3 partes não pode dar 33,33 para cada uma. Com inteiros, 100 / 3 é 33 com resto 1. A regra determinística é: dê o quociente a todos e depois distribua o resto um centavo por vez, em uma ordem fixa. O resultado é 34, 33, 33, e as partes sempre somam o original. A "ordem fixa" importa: a mesma entrada precisa sempre dar a mesma saída, para que um retry ou um replay produza postings idênticos. Um bom teste unitário é uma propriedade: para qualquer valor e qualquer número de partes, as partes somam o valor e diferem em no máximo um centavo.

**Arredondar precisa ser uma decisão, não um acidente.** Tarifas costumam produzir frações de centavo. Uma tarifa de 1,5% sobre R$ 10,10 dá 15,15 centavos. Você precisa escolher uma regra de arredondamento e documentá-la. O **arredondamento bancário** (banker's rounding, metade para o par) arredonda metades exatas para o número par mais próximo: 2,5 vira 2, 3,5 vira 4, enquanto 2,6 vira 3 como sempre. O objetivo é evitar o viés para cima de sempre arredondar metades para cima, que se acumula ao longo de milhões de tarifas. Teste as metades explicitamente, e inclua valores negativos se o seu tipo os permitir.

Qualquer que seja a regra escolhida, o ledger só continua fechando se a tarifa arredondada for usada nos dois lados do lançamento. Calcule a tarifa uma vez, como inteiro, e use esse mesmo valor no débito e no crédito.

## O que anotar hoje

1. O ciclo de vida de uma transferência em duas fases: reservar, depois post, post parcial, void ou expiração. Escreva o que acontece com os contadores pending e posted em cada caso, usando o exemplo de 123 e 100.
2. Por que o limite de saldo é verificado na fase 1, e por que isso torna a fase 2 segura.
3. Os campos de conta do TigerBeetle, e a verificação exata de `debits_must_not_exceed_credits`. Mostre que é a regra do saldo available de segunda.
4. Contas de clearing versus contas terminais no Ledger da Stripe, e como um saldo de clearing diferente de zero revela dinheiro que sumiu ou ficou preso. Desenhe um fluxo da carteira com uma conta de clearing.
5. Suas regras de `Money`: unidades mínimas inteiras, moeda sempre junto, divisão determinística, e qual modo de arredondamento você usa para tarifas.

## Teste-se

Estas perguntas dão bons flashcards (veja o [guia de flashcards](../../FLASHCARDS.pt-BR.md)).

- O que uma transferência pendente muda no TigerBeetle, e o que ela não toca?
- Um hold de R$ 100 é capturado por R$ 80. O que acontece com os outros R$ 20?
- Por que uma transferência pendente não pode ser confirmada duas vezes, e como isso ajuda quando a bandeira repete uma mensagem?
- Qual flag serve para a carteira de um cliente, `debits_must_not_exceed_credits` ou `credits_must_not_exceed_debits`, e por quê?
- Na analogia da água da Stripe, o que são os canos, e o que significa água presa neles?
- Como dividir R$ 1,00 em três partes de forma determinística?
- O que é o arredondamento bancário, e que problema ele evita?

## Referências

- **Fonte principal sobre holds:** documentação do TigerBeetle, ["Two-Phase Transfers"](https://docs.tigerbeetle.com/coding/two-phase-transfers/), a página inteira, incluindo os exemplos do final. Gratuito.
- **Fonte principal sobre o modelo de conta:** documentação do TigerBeetle, [referência "Account"](https://docs.tigerbeetle.com/reference/account/), especialmente os campos, as flags `debits_must_not_exceed_credits` e `credits_must_not_exceed_debits`, e os invariantes. Gratuito.
- **Fonte principal sobre dinheiro sumido:** Ilya Ganelin, ["Ledger: Stripe's system for tracking and validating money movement"](https://stripe.dev/blog/ledger-stripe-system-for-tracking-and-validating-money-movement), blog da Stripe, fevereiro de 2024. Leia as seções sobre a analogia da água e sobre as métricas de qualidade de dados. Gratuito.
