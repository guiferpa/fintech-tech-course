# Módulo 6, segunda-feira: partidas dobradas, tipos de conta e saldos

[Módulo 6](../../modules/06-ledgers-and-accounting.pt-BR.md) · [Read in English](day-1.md)

**Tempo de leitura:** cerca de 45 minutos. Use o resto do bloco de 2 horas nas referências do final, começando pelas seções marcadas como fonte principal.

Este é um texto original escrito para este curso. Ele se baseia nas referências listadas no final, e cada seção indica a fonte que segue. Quando uma ideia vem de um autor específico, o texto diz isso.

## Por que isso importa para uma fintech

Até agora sua carteira digital guardava uma coluna `balance` e a alterava com `UPDATE`. Isso funciona até alguém fazer uma pergunta simples: "por que este saldo é R$ 37,12 e não R$ 40,00?" Um número mutável não tem resposta. Um ledger tem, porque o saldo é a soma de todos os movimentos que já tocaram a conta, e cada movimento diz de onde o dinheiro veio e para onde foi.

Entrevistadores de empresas de pagamento pedem para você modelar um ledger porque isso mostra se você pensa em dinheiro como uma quantidade que se conserva. Nesta semana você troca a coluna de saldo por contas, transações e postings, e deixa o banco de dados recusar qualquer escrita que crie ou destrua dinheiro.

## 1. Contas, lançamentos, transações e o ledger

*Fonte principal: Modern Treasury, "Accounting for Developers, Part I", seção "Core Concepts".*

A série da Modern Treasury começa com quatro palavras. Aprenda-as com precisão, porque os entrevistadores as usam com precisão.

- Uma **conta** (account) é um reservatório de valor cujo saldo importa para você. O artigo resume em uma linha: "An **account** is a segregated pool of value." Em uma carteira digital, a carteira de cada cliente é uma conta, e o caixa da empresa no banco parceiro também.
- Um **lançamento** (entry; neste curso também chamado de **posting**) é uma linha que altera uma conta, em um valor, em uma direção.
- Uma **transação** é um grupo atômico de lançamentos. Ela toca pelo menos duas contas, e ou todos os seus lançamentos são gravados ou nenhum é.
- Um **ledger** é o registro ordenado no tempo dessas transações. Os saldos são calculados a partir dele.

O artigo defende guardar transações imutáveis e derivar os saldos, em vez de editar saldos no lugar. O alerta é direto: "Mutating balances directly creates a system that is prone to errors". O motivo é que um `UPDATE wallets SET balance = balance - 5000` não deixa rastro de por que o número mudou. Se um bug o executar duas vezes, nada no banco de dados vai contar isso a você.

A segunda ideia é que **toda transação registra os dois lados**. Nas palavras do artigo, "every transaction should record both where the money came from and what the money was used for." Quando Ana envia R$ 50 para Bruno, o dinheiro sai da carteira da Ana e vai para a do Bruno. Gravar só o lado do Bruno criaria R$ 50 do nada.

## 2. Contas de saldo devedor e de saldo credor

*Fonte principal: Modern Treasury, "Accounting for Developers, Part I", seções sobre contas debit normal e credit normal.*

É aqui que a maioria dos engenheiros se perde, porque "débito" e "crédito" na contabilidade não significam "menos" e "mais". O artigo os reformula de um jeito que combina com quem programa.

Toda conta tem um **saldo normal** (normal balance), que é a direção que a faz crescer.

- Contas **debit normal** (natureza devedora) registram **usos** de recursos. Ativos (caixa, dinheiro emprestado a alguém) e despesas são debit normal. Um débito as aumenta; um crédito as diminui.
- Contas **credit normal** (natureza credora) registram **fontes** de recursos. Passivos, patrimônio líquido e receitas são credit normal. Um crédito as aumenta; um débito as diminui.

O artigo resume isso em uma tabela, reproduzida aqui com um exemplo de carteira digital em cada linha:

| Tipo de conta | Débito | Crédito | Saldo normal | Exemplo na carteira |
| --- | --- | --- | --- | --- |
| Ativo | + | - | Devedor | Caixa mantido no banco parceiro |
| Passivo | - | + | Credor | Saldo da carteira de cada cliente |
| Patrimônio líquido | - | + | Credor | Dinheiro que os fundadores aportaram |
| Receita | - | + | Credor | Tarifas de transferência cobradas dos clientes |
| Despesa | + | - | Devedor | Tarifas de processamento de cartão pagas à adquirente |

Então "débito" e "crédito" são apenas os dois lados de um lançamento. Se um débito faz um número subir depende do tipo da conta. Ajuda tratar a direção como uma flag do lançamento e o saldo normal como uma flag da conta, e calcular o efeito a partir das duas.

A surpresa para a maioria dos engenheiros está na segunda linha. **Do ponto de vista da empresa, a carteira de um cliente é um passivo.** A empresa guarda o dinheiro, mas o deve de volta ao cliente quando ele pedir. Quando um cliente deposita R$ 100, o caixa da empresa (um ativo) sobe R$ 100 e o que ela deve ao cliente (um passivo) também sobe R$ 100. As duas contas crescem, uma por um débito e outra por um crédito. São as partidas dobradas funcionando como foram projetadas.

## 3. Provando que o ledger fecha

*Fonte principal: Modern Treasury, "Accounting for Developers, Part I", seção "How to Ensure Your Ledger is Balanced".*

Se toda transação tem débitos e créditos iguais, o ledger inteiro tem uma propriedade que você pode verificar a qualquer momento. O artigo a enuncia assim: a soma dos saldos de todas as contas debit normal é igual à soma dos saldos de todas as contas credit normal. Sua padaria fictícia, a Modern Bagelry, termina com US$ 1,47 milhão de cada lado: caixa e estoque do lado devedor, patrimônio e empréstimos do lado credor. O artigo diz o que uma diferença significaria: "Not matching would mean the system created or lost money out of nothing."

Para um engenheiro, a mesma regra tem uma forma mais simples. Dê um sinal a cada lançamento: débitos positivos, créditos negativos (ou o contrário, desde que você seja consistente). Então:

- **Por transação:** os lançamentos com sinal somam zero.
- **No ledger inteiro:** os lançamentos com sinal somam zero, porque é uma soma de transações que somam zero.

Esse é o **invariante de soma zero** que você vai impor no Postgres na quinta-feira. Ele vale por moeda: R$ 100 debitados e US$ 100 creditados não se anulam. A aula de quarta volta ao tema das moedas.

O invariante não prova que o ledger está certo. Uma transferência lançada para o cliente errado também fecha. O que ele prova é que nenhum bug criou ou destruiu dinheiro. Outras verificações, como a conciliação com o banco parceiro (Módulo 8) e as contas de clearing da aula de amanhã, pegam o resto.

## 4. O plano de contas de uma carteira digital

*Fonte principal: Modern Treasury, "Accounting for Developers, Part II".*

O segundo artigo da série projeta um ledger para uma carteira no estilo do Venmo. Seu **plano de contas** (chart of accounts, a lista de tipos de conta que um produto usa) tem quatro tipos:

| Conta | Tipo | Saldo normal |
| --- | --- | --- |
| Caixa | Ativo | Devedor |
| Carteira do usuário (uma por cliente) | Passivo | Credor |
| Tarifas de processamento de cartão | Despesa | Devedor |
| Receita | Receita | Credor |

Depois ele modela três eventos. Aqui estão eles, traduzidos para reais e para a nossa carteira. A estrutura é do artigo; os números são nossos.

**Transferência de R$ 100 da Ana para o Bruno.**

| Conta | Débito | Crédito |
| --- | --- | --- |
| Carteira: Ana | 100,00 | |
| Carteira: Bruno | | 100,00 |

O passivo com a Ana diminui e o passivo com o Bruno aumenta. O caixa da empresa nem se mexe, porque nenhum dinheiro saiu nem entrou na conta bancária da empresa.

**Ana deposita R$ 300 com cartão, e a empresa paga uma tarifa de 2% do cartão.**

| Conta | Débito | Crédito |
| --- | --- | --- |
| Caixa | 294,00 | |
| Tarifas de processamento de cartão | 6,00 | |
| Carteira: Ana | | 300,00 |

Ana vê R$ 300 na carteira. O banco recebe R$ 294, porque a adquirente ficou com R$ 6. Esses R$ 6 são uma despesa da empresa. A transação tem três lançamentos e ainda assim fecha: 294 + 6 = 300. (A lista de requisitos do artigo menciona uma tarifa de 3%, enquanto o exemplo usa US$ 6 sobre US$ 300. O que importa é o formato do lançamento.)

**Bruno saca R$ 500 para sua conta bancária e paga uma tarifa de 0,5%.**

| Conta | Débito | Crédito |
| --- | --- | --- |
| Carteira: Bruno | 502,50 | |
| Caixa | | 500,00 |
| Receita | | 2,50 |

A tarifa é receita da empresa, então é um crédito em uma conta credit normal. Repare no padrão: uma tarifa é mais um lançamento na mesma transação, nunca uma segunda transação gravada depois. Se a tarifa fosse gravada separadamente, uma queda entre as duas escritas deixaria o ledger em um estado que nunca existiu no mundo real.

O artigo fecha o exemplo da carteira com uma regra que considera essencial: impor partidas dobradas em toda transação, "at least one debit + one credit". E dá a conclusão que você deve saber dizer em uma entrevista: "As debits equal credits, money in equals money out."

## 5. O ledger completo de um produto: o marketplace de empréstimos

*Fonte principal: Modern Treasury, "Accounting for Developers, Part III".*

A parte III, de Lucas Rocha, constrói um produto inteiro: um marketplace fictício de empréstimos entre pessoas. Uma investidora, Lucy, deposita US$ 10.000 a 4,8% ao ano. Uma tomadora, Desi, pega US$ 5.000 a 12% ao ano. O marketplace fica com a diferença entre os juros que cobra e os juros que paga, como receita.

Vale estudar o plano de contas, porque ele mistura contas da empresa e contas por usuário, com os dois saldos normais do lado dos usuários:

| Conta | Saldo normal | Por quê |
| --- | --- | --- |
| Caixa | Devedor | Ativo: dinheiro no banco |
| Receita (juros) | Credor | Fonte: o spread |
| Principal e juros do investidor (por investidor) | Credor | Passivo: devido ao investidor |
| Principal e juros do tomador (por tomador) | Devedor | Ativo: devido pelo tomador |

O lançamento mais instrutivo é a apropriação mensal de juros. Nenhum dinheiro se move entre bancos. O ledger só registra que as obrigações cresceram: a conta de juros da tomadora Desi é debitada em US$ 50 (ela deve mais), a conta de juros da investidora Lucy é creditada em US$ 40 (ela tem mais a receber), e a receita é creditada em US$ 10. Cinquenta em débitos, cinquenta em créditos. Um ledger registra **obrigações**, não só movimentos bancários.

O pagamento da parcela divide um único recebimento em dois créditos (principal e juros), e o resgate no vencimento debita duas contas da Lucy contra um crédito no caixa. Transações com vários lançamentos são normais, não um caso de borda.

Uma frase do artigo merece um lugar nas suas anotações: "The ledger's functionality and underlying data models should not be tightly coupled to business logic." Para a carteira, isso significa que o módulo de ledger conhece contas, transações e postings. Ele não sabe o que é uma "transferência Pix" ou um "estorno". O serviço de transferências traduz eventos de negócio em postings balanceados e pede ao ledger que os grave.

## 6. Saldos pending, posted e available

*Fonte principal: Modern Treasury, "How to Scale a Ledger", capítulos 1 e 2.*

Até aqui cada conta tem um saldo só. O dinheiro real é mais lento que isso. Uma compra no cartão é autorizada agora e liquida à noite. Um Pix enviado a um banco parceiro é aceito agora e confirmado segundos depois. O whitepaper "How to Scale a Ledger" trata disso com três saldos por conta:

- **Saldo posted:** dinheiro totalmente liquidado.
- **Saldo pending:** o dinheiro posted mais o dinheiro que deve liquidar, nas duas direções.
- **Saldo available:** o que o cliente pode gastar agora. Ele conta o dinheiro pendente que vai sair, mas ignora o dinheiro que vai entrar e ainda não liquidou.

O whitepaper calcula os três a partir de quatro somas mantidas por conta: `posted_debits`, `posted_credits`, `pending_debits` e `pending_credits`, em que as somas pending incluem as posted. Para uma conta credit normal, como a carteira de um cliente:

| Saldo | Fórmula (credit normal) |
| --- | --- |
| Posted | posted_credits - posted_debits |
| Pending | pending_credits - pending_debits |
| Available | posted_credits - pending_debits |

Para uma conta debit normal, troque débitos e créditos em cada fórmula. A fórmula do available é a mais importante. Ela é pessimista de propósito: subtrai todo débito que pode acontecer e soma só os créditos que já aconteceram. É esse o número que você verifica antes de deixar dinheiro sair.

Aqui está a carteira da Ana ao longo de um dia, usando essas fórmulas:

| Evento | Posted | Pending | Available |
| --- | --- | --- | --- |
| Início: R$ 1.000 liquidados | 1.000 | 1.000 | 1.000 |
| Compra de R$ 200 no cartão autorizada (débito pendente) | 1.000 | 800 | 800 |
| Transferência recebida de R$ 300, ainda não liquidada (crédito pendente) | 1.000 | 1.100 | 800 |
| A compra no cartão liquida | 800 | 1.100 | 800 |
| A transferência recebida liquida | 1.100 | 1.100 | 1.100 |

Repare que liquidar nunca muda o saldo pending. O pending já contava o movimento; liquidar só o move para o posted.

O whitepaper percorre um cartão de crédito do mesmo jeito: uma passagem aérea de US$ 1.000 "starts out pending", reduzindo pending e available mas não o posted, e passa a posted quando liquida naquela noite. Uma reserva (hold) de US$ 250 de um hotel reduz pending e available até ser removida.

Duas regras do whitepaper importam para quinta-feira. Primeira: "Account balances are never directly modified." Os saldos são derivados dos lançamentos, mesmo que você os guarde em cache. Segunda: os lançamentos pertencem a transações com um estado (pending, posted ou archived), e os clientes criam transações, nunca lançamentos soltos. A aula de amanhã mostra o mesmo modelo no TigerBeetle com o nome de "two-phase transfers".

## 7. Do modelo às tabelas

O lab de hoje é modelar e migrar contas, transações e postings. Aqui está um ponto de partida em Postgres. Ele segue o vocabulário acima. É um esboço, então adapte os nomes ao seu projeto.

```sql
CREATE TYPE normal_balance AS ENUM ('debit', 'credit');
CREATE TYPE entry_direction AS ENUM ('debit', 'credit');
CREATE TYPE ledger_tx_status AS ENUM ('pending', 'posted', 'archived');

CREATE TABLE accounts (
  id             uuid PRIMARY KEY,
  code           text NOT NULL UNIQUE,          -- 'cash:partner_bank', 'wallet:<user_id>'
  normal_balance normal_balance NOT NULL,
  currency       char(3) NOT NULL,              -- 'BRL'
  created_at     timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE ledger_transactions (
  id              uuid PRIMARY KEY,
  idempotency_key text NOT NULL UNIQUE,
  status          ledger_tx_status NOT NULL,
  description     text NOT NULL,
  effective_at    timestamptz NOT NULL,
  created_at      timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE postings (
  id             bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  transaction_id uuid NOT NULL REFERENCES ledger_transactions(id),
  account_id     uuid NOT NULL REFERENCES accounts(id),
  direction      entry_direction NOT NULL,
  amount         bigint NOT NULL CHECK (amount > 0),   -- unidades mínimas (centavos)
  currency       char(3) NOT NULL
);
```

Algumas escolhas para notar e estar pronto para defender:

- **Os valores são `bigint` em unidades mínimas**, com um `CHECK` positivo. A coluna de direção carrega o sinal. Nunca use ponto flutuante para dinheiro.
- **A idempotency key fica na transação**, para que uma requisição repetida pelo retry do Módulo 2 não grave o mesmo dinheiro duas vezes.
- **`effective_at` é separado de `created_at`.** O whitepaper usa `effective_at` para quando o movimento aconteceu no mundo real e deixa o ledger definir sua própria data de criação.
- **Não existe coluna `balance`.** Um saldo é uma consulta:

```sql
SELECT
  SUM(CASE WHEN p.direction = 'credit' THEN p.amount ELSE -p.amount END) AS posted_balance
FROM postings p
JOIN ledger_transactions t ON t.id = p.transaction_id
WHERE p.account_id = $1 AND t.status = 'posted';
```

Essa consulta está correta para uma conta credit normal e é lenta para uma conta com milhões de postings. Usar cache depois tudo bem, desde que o cache seja derivado dos postings e conferido contra eles. A regra de soma zero ainda não está neste schema. Essa é a primeira tarefa do TCM na quinta-feira.

## O que anotar hoje

1. Partidas dobradas em uma frase, e por que alterar uma coluna de saldo é perigoso.
2. Os cinco tipos de conta, o saldo normal de cada um, e o que um débito e um crédito fazem com cada um. Inclua por que a carteira de um cliente é um passivo para a empresa.
3. Os lançamentos de um depósito na carteira com tarifa de cartão e de um saque com tarifa, no formato de tabela débito/crédito.
4. Uma coisa que o ledger de empréstimos da parte III ensinou e que o exemplo da carteira não ensinou (dica: apropriações, transações com vários lançamentos, ou desacoplamento da lógica de negócio).
5. As definições dos saldos posted, pending e available, e a fórmula do available para uma conta credit normal.

## Teste-se

Estas perguntas dão bons flashcards (veja o [guia de flashcards](../../FLASHCARDS.pt-BR.md)).

- Qual é o saldo normal de uma conta de passivo, e um débito a aumenta ou diminui?
- Por que o saldo da carteira de um cliente é um passivo nos livros da empresa?
- O que significa "o ledger fecha", e que tipo de bug isso descarta? Que tipo não descarta?
- Um depósito de R$ 300 com cartão custa uma tarifa de R$ 6 paga pela empresa. Quais contas são debitadas e creditadas?
- Por que uma tarifa precisa ser um lançamento na mesma transação da transferência, e não uma transação separada?
- Escreva o saldo available de uma conta credit normal em termos de débitos e créditos posted e pending.
- Por que o saldo available ignora créditos pendentes mas conta débitos pendentes?

## Referências

- **Fonte principal:** Modern Treasury, ["Accounting for Developers, Part I"](https://www.moderntreasury.com/journal/accounting-for-developers-part-i), todas as seções, e ["Accounting for Developers, Part II"](https://www.moderntreasury.com/journal/accounting-for-developers-part-ii) (linkada no fim da parte I), o exemplo da carteira. Gratuito.
- Modern Treasury, ["Accounting for Developers, Part III"](https://www.moderntreasury.com/journal/accounting-for-developers-part-iii), de Lucas Rocha, o marketplace de empréstimos: leia o plano de contas e os cinco tipos de transação. Gratuito.
- Modern Treasury, ["How to Scale a Ledger"](https://www.moderntreasury.com/ebooks/how-to-scale-a-ledger), capítulos 1 e 2 hoje (saldos, lançamentos, transações, o exemplo do cartão de crédito). Os capítulos 4 a 6 ficam para quarta-feira. Gratuito. É um whitepaper de fornecedor que também promove o produto da Modern Treasury; os conceitos são gerais.
