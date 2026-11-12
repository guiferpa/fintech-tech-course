# Roteiro · M6 · Dia 1 · Partidas dobradas e saldos


## Abertura

Esta é a aula em vídeo do módulo seis, dia um: partidas dobradas e saldos.

Até agora a sua carteira guardava uma coluna de saldo e a alterava com update. Isso funciona até alguém perguntar: por que este saldo é trinta e sete reais e doze centavos, e não quarenta? Um número mutável não tem resposta. Um ledger tem, porque o saldo é a soma de todos os movimentos que tocaram a conta, e cada movimento diz de onde o dinheiro veio e para onde foi. Entrevistadores de pagamentos pedem para modelar um ledger porque isso mostra se você pensa em dinheiro como uma quantidade que se conserva.


## Quatro palavras

A série Accounting for Developers, da Modern Treasury, começa com quatro palavras. Aprenda com precisão, porque os entrevistadores as usam assim.

Uma conta é um reservatório de valor separado. A carteira de cada cliente é uma conta, e o caixa da empresa no banco parceiro também.

Um lançamento, que neste curso também se chama posting, é uma linha que altera uma conta, num valor, numa direção.

Uma transação é um grupo atômico de lançamentos. Toca pelo menos duas contas, e ou todos os lançamentos são gravados, ou nenhum.

E o ledger é o registro ordenado no tempo dessas transações. Os saldos são calculados a partir dele.


## Não altere saldos

A Modern Treasury defende guardar transações imutáveis e derivar os saldos, em vez de editar saldos no lugar.

Um update que subtrai cinquenta do saldo não deixa rastro de por que o número mudou. Se um bug o executar duas vezes, nada no banco vai contar isso a você.

A segunda ideia: toda transação registra os dois lados, de onde o dinheiro veio e para que foi usado. Quando Ana envia cinquenta reais para Bruno, o dinheiro sai da carteira da Ana e entra na do Bruno. Gravar só o lado do Bruno criaria cinquenta reais do nada.


## Saldo normal

Aqui a maioria dos engenheiros se perde, porque débito e crédito não significam menos e mais. Toda conta tem um saldo normal, a direção que a faz crescer. Contas de natureza devedora registram usos de recursos: um débito as aumenta. Contas de natureza credora registram fontes: um crédito as aumenta.

Ativo é devedor. Um débito aumenta. Exemplo: o caixa no banco parceiro.

Passivo é credor. Um crédito aumenta. Exemplo: o saldo da carteira de cada cliente.

Patrimônio líquido é credor: o dinheiro que os fundadores aportaram.

Receita é credora: as tarifas cobradas dos clientes.

E despesa é devedora: a tarifa paga à adquirente do cartão. Trate a direção como uma flag do lançamento, e o saldo normal como uma flag da conta. O efeito sai das duas.

A surpresa está na segunda linha. Para a empresa, a carteira do cliente é um passivo. A empresa guarda o dinheiro, mas deve de volta quando o cliente pedir. Num depósito de cem reais, o caixa sobe cem, por um débito, e o que a empresa deve ao cliente também sobe cem, por um crédito. As duas contas crescem. São as partidas dobradas funcionando.

> **Pausa:** Pergunta: por que a carteira do cliente é um passivo para a empresa, e o que um crédito faz com ela?

Porque a empresa deve esse dinheiro ao cliente. É uma conta credora, então um crédito aumenta o saldo dela.


## O invariante

Se toda transação tem débitos e créditos iguais, o ledger inteiro tem uma propriedade verificável a qualquer momento: a soma dos saldos das contas devedoras é igual à das credoras. Não bater significaria que o sistema criou ou perdeu dinheiro do nada.

Para um engenheiro, a forma é mais simples. Dê sinal aos lançamentos: débitos positivos, créditos negativos. Em cada transação, a soma é zero. E no ledger inteiro também, porque é uma soma de transações que somam zero. Esse é o invariante de soma zero que você vai impor no Postgres na quinta. Ele vale por moeda: cem reais e cem dólares não se anulam.

E atenção: ele não prova que o ledger está certo. Uma transferência para o cliente errado também fecha. Ele prova que nenhum bug criou ou destruiu dinheiro. A conciliação e as contas de clearing pegam o resto.


## Depósito com tarifa

O segundo artigo da série projeta um ledger de carteira, com quatro tipos de conta: caixa, carteira de cada usuário, tarifas de processamento, e receita. Veja um depósito.

Ana deposita trezentos reais com cartão, e a empresa paga dois por cento de tarifa. O banco recebe duzentos e noventa e quatro: débito no caixa.

Os seis reais que a adquirente ficou são despesa da empresa: débito em tarifas.

E a Ana vê trezentos reais: crédito na carteira dela.

Três lançamentos, e a transação fecha: duzentos e noventa e quatro mais seis, trezentos. Compare com uma transferência de cem reais da Ana para o Bruno: débito na carteira da Ana, crédito na do Bruno. O caixa nem se mexe, porque nenhum dinheiro entrou ou saiu do banco.


## Saque com tarifa

Agora um saque. Bruno saca quinhentos reais para a conta bancária dele, com tarifa de meio por cento.

A carteira do Bruno é debitada em quinhentos e dois e cinquenta: o passivo com ele diminui.

O caixa é creditado em quinhentos: o dinheiro sai do banco.

E a receita é creditada em dois e cinquenta, a tarifa.

Repare: a tarifa é mais um lançamento na mesma transação, nunca uma segunda transação gravada depois. Se fosse separada, uma queda entre as duas escritas deixaria o ledger num estado que nunca existiu. E a regra do artigo para entrevistas: débitos iguais a créditos, dinheiro que entra igual a dinheiro que sai.

> **Pausa:** Pergunta: monte de cabeça os lançamentos do saque do Bruno.

Débito de quinhentos e dois e cinquenta na carteira do Bruno. Crédito de quinhentos no caixa, e de dois e cinquenta na receita.


## O marketplace de empréstimos

A parte três constrói um marketplace de empréstimos. Lucy, a investidora, deposita a quatro vírgula oito por cento ao ano. Desi, a tomadora, pega emprestado a doze por cento. O marketplace fica com a diferença, como receita.

O lançamento mais instrutivo é a apropriação mensal de juros. A conta de juros da Desi é debitada em cinquenta: ela deve mais. A da Lucy é creditada em quarenta: ela tem mais a receber. E a receita é creditada em dez.

Nenhum dinheiro se moveu entre bancos. Um ledger registra obrigações, não só movimentos bancários.

E o pagamento da parcela divide um recebimento em principal e juros. Transações com vários lançamentos são normais, não caso de borda.

Uma frase para as suas anotações: o ledger não deve ser acoplado à lógica de negócio. O módulo de ledger conhece contas, transações e postings. Ele não sabe o que é um Pix ou um estorno. O serviço de transferências traduz eventos de negócio em postings balanceados.


## Três saldos

Dinheiro real é lento. Uma compra no cartão é autorizada agora e liquida à noite. Por isso cada conta tem três saldos. Posted: o que está totalmente liquidado. Pending: o posted mais o que deve liquidar, nas duas direções. E available: o que o cliente pode gastar agora.

Acompanhe a Ana. Ela começa com mil reais liquidados. Os três saldos são mil.

Uma compra de duzentos é autorizada. O posted fica em mil, mas pending e available caem para oitocentos.

Chega uma transferência de trezentos, ainda não liquidada. O pending sobe para mil e cem. O available continua oitocentos, porque ignora dinheiro que vai entrar e ainda não chegou.

A compra liquida. O posted cai para oitocentos. O pending não muda: ele já contava esse movimento.

A transferência liquida, e tudo fica em mil e cem. Liquidar nunca muda o pending, só move para o posted.

A fórmula do available, para uma conta credora, é posted credits menos pending debits. Ela é pessimista de propósito: subtrai todo débito que pode acontecer, e soma só os créditos que já aconteceram. É o número que você verifica antes de deixar dinheiro sair. E duas regras: saldos nunca são modificados diretamente, e clientes criam transações, nunca lançamentos soltos.

> **Pausa:** Pergunta: por que o available ignora a transferência de trezentos que ainda não liquidou?

Porque ela ainda pode não chegar. Se a Ana gastasse esse dinheiro e a transferência falhasse, o saldo ficaria negativo.


## Do modelo às tabelas

O lab de hoje é modelar e migrar isso. Três tabelas: contas, com o saldo normal e a moeda. Transações do ledger, com status. E postings, cada um com transação, conta, direção, valor e moeda.

Escolhas para defender. Valores em big int, em centavos, sempre positivos. A coluna de direção carrega o sinal. Nunca ponto flutuante para dinheiro.

A idempotency key fica na transação, para que um retry do módulo dois não grave o mesmo dinheiro duas vezes.

Effective at, quando o movimento aconteceu no mundo real, é separado de created at, quando o ledger gravou.

E não existe coluna de saldo. O saldo é uma consulta que soma os postings. Ela é lenta com milhões de linhas. Cache depois tudo bem, desde que derivado dos postings e conferido contra eles. A regra de soma zero ainda não está aqui. É a primeira tarefa de quinta.


## Revisão relâmpago

Hora da revisão relâmpago. São três perguntas, sem olhar.

> **Pausa:** Pergunta um: partidas dobradas em uma frase.

Toda transação registra de onde o dinheiro veio e para onde foi, e os débitos são iguais aos créditos.

> **Pausa:** Pergunta dois: um débito numa conta de despesa aumenta ou diminui o saldo?

Aumenta. Despesa é de natureza devedora.

> **Pausa:** Pergunta três: qual a fórmula do saldo available numa conta credora, como a carteira do cliente?

Posted credits menos pending debits.


## O que anotar e próximo passo

Anote com as suas palavras: partidas dobradas e o perigo da coluna de saldo. Os cinco tipos de conta e por que a carteira é um passivo. O depósito e o saque com tarifa, em tabela. E os três saldos, com a fórmula do available.

Depois, no lab, modele e migre contas, transações e postings. Até a próxima aula.
