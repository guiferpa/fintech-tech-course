# Módulo 6, quarta-feira: concorrência, imutabilidade e lançamentos no papel

[Módulo 6](../../modules/06-ledgers-and-accounting.pt-BR.md) · [Read in English](day-3.md)

**Tempo de leitura:** cerca de 45 minutos. Use o resto do bloco de 2 horas nas referências do final e no exercício no papel.

Este é um texto original escrito para este curso. Ele se baseia nas referências listadas no final, e cada seção indica a fonte que segue.

## Por que isso importa para uma fintech

Um ledger que está correto para uma requisição por vez ainda não é um ledger. Em produção, duas autorizações de cartão para a mesma carteira chegam no mesmo milissegundo, a conta de receita de tarifas recebe um posting de cada transferência da empresa, e um operador quer "consertar" um lançamento errado com um `UPDATE`. Cada uma dessas situações pode quebrar as garantias que você construiu na segunda e na terça.

Hoje cobrimos as duas propriedades que mantêm o ledger confiável sob carga real: **controle de concorrência** (dois escritores não podem gastar o mesmo dinheiro) e **imutabilidade** (o histórico nunca é reescrito, só estendido). A aula termina com o exercício no papel que prepara você para o TCM e para o teste de domínio.

## 1. A corrida em uma carteira

*Fonte principal: Modern Treasury, "Designing the Ledgers API with Optimistic Locking", de Andy Qin, 2021.*

O post de Andy Qin começa com um app de pagamentos entre pessoas. Lucy Ledger tem saldo de 15000 centavos (US$ 150,00) e envia US$ 50 para John Journal. A transação debita Lucy e credita John. O perigo é um segundo débito rodando ao mesmo tempo.

O código ingênuo faz isto:

1. Lê o saldo da Lucy: 15000.
2. Verifica que 15000 >= 5000.
3. Insere os postings.

Se duas requisições executarem os passos 1 e 2 antes de qualquer uma chegar ao passo 3, as duas veem 15000, as duas passam na verificação e as duas inserem. Troque a segunda requisição por US$ 120 em vez de US$ 50 e Lucy termina com menos US$ 20. O post descreve isso como uma phantom read: a verificação era verdadeira quando foi lida e falsa quando a escrita aconteceu.

No Postgres, o nível de isolamento padrão é Read Committed, e ele não impede esse padrão. Cada comando enxerga os dados confirmados antes de ele começar, então duas transações podem ler o saldo antigo. Você precisa de um lock ou de uma verificação de versão que amarre a leitura à escrita.

## 2. Lock pessimista e lock otimista

*Fonte principal: Modern Treasury, "Designing the Ledgers API with Optimistic Locking".*

O post compara as duas respostas clássicas, como oferecidas pelo ActiveRecord do Rails sobre o Postgres.

O **lock pessimista** trava a linha com exclusividade antes de lê-la. Os outros escritores esperam até o lock ser liberado. No Postgres:

```sql
BEGIN;
SELECT id FROM accounts WHERE id = $1 FOR UPDATE;   -- outros escritores desta conta esperam aqui
-- calcula o saldo available, verifica, insere os postings
COMMIT;
```

O **lock otimista** adiciona uma coluna `lock_version`. Toda escrita a incrementa, e toda escrita declara qual versão espera. Se dois clientes escreverem ao mesmo tempo, um confirma e o outro falha, e o cliente que perdeu lê de novo e decide se faz retry. No Postgres:

```sql
UPDATE account_versions
SET lock_version = lock_version + 1
WHERE account_id = $1 AND lock_version = $2;
-- 0 linhas atualizadas: alguém escreveu antes. ROLLBACK e retry a partir da leitura.
```

A Modern Treasury escolheu o lock otimista. O motivo decisivo, nas palavras de Qin: "A huge advantage over pessimistic locking is that reads aren't blocked by writes." A maior parte do tráfego de um ledger é leitura de saldos e extratos, então bloquear leituras sairia caro.

O post também tem um detalhe de design que vale copiar. O que precisa de versão não são os atributos da conta, e sim o seu **conjunto de lançamentos**. Por isso a Modern Treasury colocou o `lock_version` em um registro separado de "versão da conta", um por conta, e o incrementa sempre que um novo lançamento é criado para aquela conta. Renomear uma conta deixou de conflitar com lançar nela. Na API, o cliente envia o `lock_version` que leu para cada conta da transação. Como diz o post: "If either "lock_version" differs, we rollback the database transaction and fail the request." Clientes que não o enviam não têm garantia de concorrência; a versão deles é atualizada depois, em um job em background.

Para a sua carteira, uma regra simples funciona bem: **trave só as contas que precisam de verificação de autorização, em uma ordem fixa.** Ordenar os IDs das contas antes de travar evita deadlocks quando Ana paga Bruno enquanto Bruno paga Ana.

## 3. Contas quentes e condições de saldo

*Fonte principal: Modern Treasury, "How to Scale a Ledger", capítulos 4 e 6.*

O lock otimista tem uma fraqueza que o whitepaper nomeia diretamente. Em uma conta que recebe escritas o tempo todo, a versão muda antes que a maioria dos clientes consiga confirmar: "If the `account_version` is incrementing at a fast enough pace, some Transactions will never be able to commit." Essas são as **contas quentes** (hot accounts). Em uma carteira digital, as óbvias são as contas da empresa tocadas por toda transação: receita de tarifas, caixa no banco parceiro e as contas de clearing de terça.

O whitepaper oferece duas ideias para lidar com elas.

**Travar por lançamento, não por transação.** Ele separa duas formas de escrever em um ledger. **Registrar** (recording) anota dinheiro que já se moveu em outro lugar; precisa de alta vazão e aceita leituras alguns segundos defasadas. **Autorizar** (authorizing) decide se o dinheiro pode se mover; precisa de consistência read-after-write e serializa as escritas. A afirmação central é que "the model must be determined at the Entry level." O exemplo do cartão tem dois lançamentos em uma transação: o lançamento do portador precisa de verificação de saldo e consistência forte, enquanto o lançamento devido ao processador do cartão não precisa de nenhuma das duas. Mesmo assim, os dois são confirmados atomicamente. Na carteira: quando Ana paga uma tarifa de R$ 2, o lançamento na carteira dela precisa de lock e verificação de saldo. O crédito na receita de tarifas não precisa, porque esse lançamento só faz a receita crescer e ninguém autoriza nada contra ela.

**Condições de saldo em vez de verificação de versão.** Em vez de "falhe se a versão mudou", o cliente diz "confirme só se este saldo continuar maior ou igual a zero depois da escrita". O whitepaper chama isso de balance locking, com campos como `BalanceCondition` e um exemplo `gte: 0`. Escritas concorrentes sem relação deixam de causar falhas; só falha uma escrita que realmente quebraria a condição. O whitepaper mede a diferença em um exemplo: duas transações de US$ 250 e US$ 750 contra um saldo de US$ 1.000 exigem seis chamadas ao ledger com version locking e duas com balance locking.

O Postgres consegue expressar uma condição de saldo como um único comando atômico, se você mantiver uma linha de saldo em cache por conta:

```sql
UPDATE account_balances
SET pending_debits = pending_debits + $2
WHERE account_id = $1
  AND posted_credits - pending_debits >= $2;   -- available >= valor, para uma carteira credit normal
-- 0 linhas atualizadas: saldo available insuficiente, rejeite o hold
```

O `UPDATE` trava a linha até o commit, então a verificação e a alteração são atômicas. O cache precisa ser derivado dos postings, atualizado na mesma transação de banco e conferido contra os postings para detectar desvio (drift). O whitepaper recomenda exatamente isso: monitorar os saldos em cache contra a soma dos lançamentos e parar de confiar no cache das contas que desviarem.

## 4. Por que um ledger precisa ser imutável

*Fonte principal: Modern Treasury, "Enforcing Immutability in your Double-Entry Ledger", de Jason Jong, 2021.*

O post de Jason Jong lista três princípios que a Modern Treasury nunca quebra: partidas dobradas, auditabilidade e imutabilidade. O argumento a favor do terceiro é sobre explicar o passado. Nas palavras dele, "if the data has been mutated, then the data is irreversibly destroyed."

O exemplo dele é um marketplace que recebe os pagamentos na hora e repassa aos lojistas toda semana. Um lojista reclama de uma diferença de US$ 10 em um repasse de US$ 10.000. Se os pedidos foram editados no lugar depois do repasse, não há registro de qual alteração causou a diferença, e Jong diz que rastreá-la "could take days". Se cada alteração foi uma nova transação no ledger, a resposta é uma consulta.

O post separa dois tipos de objeto:

- **Objetos de negócio**, como um pedido ou uma solicitação de transferência, podem ser mutáveis. São o que o produto mostra.
- **Transações do ledger** são a fonte da verdade contábil. Depois de confirmadas (posted), são criadas, nunca editadas.

O estado pending é a única exceção, e é proposital. Uma transação do ledger pode mudar enquanto está pendente e se torna "immutable once posted." Um pagamento que falha no banco antes de ser confirmado pode ir para o estado **archived** em vez de ser estornado. Jong também observa que pending "may not make sense for all products". Use-o onde o dinheiro real tem uma fase pendente, como holds e transferências de saída.

"How to Scale a Ledger" acrescenta mais um detalhe à mesma ideia. Lançamentos pendentes também não são editados: são marcados como descartados com um timestamp `discarded_at` e substituídos por novos lançamentos. O resumo do whitepaper: "Only pending Entries can be replaced; posted and archived Entries are permanent."

## 5. Correção por estorno, e append-only imposto no Postgres

*Fonte principal: Modern Treasury, "Enforcing Immutability in your Double-Entry Ledger".*

Se os lançamentos nunca são editados, como corrigir um erro? Jong dá duas opções para um valor que muda depois de confirmado:

1. **Estorno total:** lance uma nova transação com os lançamentos opostos, depois lance outra com o valor correto.
2. **Lançamento da diferença:** lance uma única transação nova com a diferença entre o valor antigo e o novo.

Digamos que uma tarifa de transferência foi cobrada como R$ 5,00, mas deveria ser R$ 3,00. Um estorno total lança "credita Ana R$ 5, debita receita de tarifas R$ 5" e depois "debita Ana R$ 3, credita receita de tarifas R$ 3". Um lançamento da diferença lança só "credita Ana R$ 2, debita receita de tarifas R$ 2". De qualquer forma, o extrato mostra o que aconteceu e quando. O estorno total é mais claro para auditores; o lançamento da diferença produz menos linhas. Escolha um e use em todo lugar. Estornos parciais funcionam do mesmo jeito: são novas transações que devolvem dinheiro, vinculadas à original, nunca edições dela.

Não dependa de code review para manter a tabela append-only. Faça o banco de dados recusar:

```sql
CREATE FUNCTION reject_posting_change() RETURNS trigger AS $$
BEGIN
  RAISE EXCEPTION 'postings are append-only (tried % on id %)', TG_OP, OLD.id;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER postings_append_only
BEFORE UPDATE OR DELETE ON postings
FOR EACH ROW EXECUTE FUNCTION reject_posting_change();
```

Revogue também `UPDATE` e `DELETE` em `postings` do role de banco da aplicação, para que um trigger não seja sua única linha de defesa. Em `ledger_transactions`, permita só as mudanças de status `pending` para `posted` e `pending` para `archived`, cada uma no máximo uma vez, o que corresponde à regra "resolvida uma única vez" do TigerBeetle, vista na terça.

Para holds, um design limpo combina as duas fontes. Um hold é uma transação pendente. Uma captura arquiva o hold e cria uma nova transação posted com o valor capturado, com uma coluna apontando de volta para o hold, como o `pending_id` do TigerBeetle. Uma liberação só o arquiva. As duas coisas acontecem dentro de uma única transação de banco, então a reserva e a captura nunca ficam ativas ao mesmo tempo.

## 6. Moeda em todo lançamento

*Fonte principal: Modern Treasury, "How to Scale a Ledger", capítulo 5.*

A regra de soma zero de segunda esconde uma armadilha: você não pode somar reais e dólares. O whitepaper enuncia a verificação correta: "The correct validation is to group Entries by currency and validate that credits and debits for each currency match." Cada conta tem uma moeda, e cada lançamento carrega sua moeda, para que a verificação rode sem joins.

Uma conversão, portanto, precisa de quatro contas, não duas. O exemplo do whitepaper é um cliente comprando ETH com USD: as contas em USD e em ETH do cliente, e as contas em USD e em ETH da plataforma. Na carteira, Ana convertendo R$ 550 em US$ 100 fica assim:

| Conta | Débito | Crédito |
| --- | --- | --- |
| Carteira: Ana (BRL) | R$ 550,00 | |
| Pool de câmbio (BRL) | | R$ 550,00 |
| Pool de câmbio (USD) | US$ 100,00 | |
| Carteira: Ana (USD) | | US$ 100,00 |

BRL fecha com BRL, e USD fecha com USD. O whitepaper rejeita a alternativa de fechar entre moedas usando uma taxa de câmbio, por três motivos: as taxas mudam com o tempo, então saldos passados ficam difíceis de verificar; não existe uma taxa única aceita por todos; e duas contas não refletem como uma conversão funciona de verdade.

Então onde fica a taxa? Ela não faz parte da regra de fechamento, mas é um fato que foi cotado ao cliente. Um design sensato para o TCM guarda a taxa cotada, sua origem e seu timestamp na transação de conversão, ao lado dos dois valores, e nunca a recalcula depois. A tabela de consistência do Módulo 1 já dizia a mesma coisa: o cliente precisa pagar a taxa que lhe foi cotada.

## 7. No papel: cinco lançamentos antes de qualquer código

O TCM começa amanhã, sem IA. Faça este exercício primeiro no papel, a lápis. Use estas contas:

| Conta | Tipo | Saldo normal |
| --- | --- | --- |
| Caixa: banco parceiro | Ativo | Devedor |
| Carteira: Ana, Carteira: Bruno | Passivo | Credor |
| Receita de tarifas | Receita | Credor |
| Holds: liquidação de cartão | Passivo (clearing) | Credor |

Aqui está o primeiro, resolvido.

**1. Depósito.** Ana deposita R$ 500 por Pix via banco parceiro.

| Conta | Débito | Crédito |
| --- | --- | --- |
| Caixa: banco parceiro | 500,00 | |
| Carteira: Ana | | 500,00 |

Agora desenhe os outros quatro você mesmo:

2. **Transferência com tarifa.** Ana envia R$ 200 para Bruno e paga uma tarifa de R$ 2. Decida se Bruno recebe R$ 200 ou R$ 198, e anote a decisão.
3. **Estorno parcial.** Bruno estorna R$ 50 dessa transferência para Ana. Decida se a tarifa é devolvida, e registre o estorno como uma nova transação vinculada à original.
4. **Hold.** O cartão da Ana é autorizado em R$ 100 em um posto de gasolina. Escreva como uma transação pendente, e calcule os saldos posted, pending e available da Ana depois dela.
5. **Captura.** O valor final é R$ 80. Mostre o que acontece com o hold e quais novos lançamentos posted aparecem. Recalcule os três saldos.

Confira cada resposta contra quatro regras:

- Débitos são iguais a créditos em cada transação, por moeda.
- Nenhum lançamento posted é alterado. Correções e estornos são novas transações.
- O saldo available da Ana nunca fica abaixo de zero em nenhum passo.
- Depois da captura, nada sobra no hold dessa compra, como nos canos vazios da Stripe.

Essas quatro regras também são as propriedades do teste baseado em propriedades de sexta. O lab de hoje é instalar o fast-check e esboçar geradores para as operações acima (depósito, transferência com tarifa, estorno, hold, captura, liberação). O fast-check consegue gerar arrays aleatórios dessas operações, e o recurso `fc.commands` dele suporta testes baseados em modelo. Escreva também a lista de tarefas de quinta e sexta, mas nenhum código do TCM.

## O que anotar hoje

1. A corrida do exemplo de Qin, e como o lock pessimista e o lock otimista a impedem. Uma vantagem de cada um.
2. O que é uma conta quente, por que o version locking sofre com ela, e os dois remédios de "How to Scale a Ledger" (travar por lançamento, condições de saldo).
3. As regras de imutabilidade: lançamentos posted nunca mudam, pendentes podem ser arquivados ou substituídos, correções por estorno total ou lançamento da diferença.
4. Por que os lançamentos fecham por moeda, a conversão com quatro contas, e onde fica a taxa de câmbio cotada.
5. O exercício no papel: lançamentos de depósito, transferência com tarifa, estorno parcial, hold e captura, com os saldos da Ana depois de cada passo.

## Teste-se

Estas perguntas dão bons flashcards (veja o [guia de flashcards](../../FLASHCARDS.pt-BR.md)).

- Por que o nível de isolamento padrão do Postgres não impede que dois débitos concorrentes deixem uma carteira negativa?
- O que acontece com o escritor que perde no lock otimista?
- Por que uma conta de receita de tarifas é "quente", e por que ela não precisa de lock?
- O que é uma condição de saldo, e como ela difere de uma verificação de versão?
- Como corrigir uma tarifa que foi lançada com o valor errado?
- Por que não dá para fechar um lançamento em BRL contra um em USD usando uma taxa de câmbio?
- Depois que um hold de R$ 100 é capturado por R$ 80, quais são os saldos available e posted de uma carteira que começou com R$ 500?

## Referências

- **Fonte principal sobre concorrência:** Andy Qin, ["Designing the Ledgers API with Optimistic Locking"](https://www.moderntreasury.com/journal/designing-ledgers-with-optimistic-locking), Modern Treasury, agosto de 2021. O post inteiro é curto. Gratuito.
- **Fonte principal sobre imutabilidade:** Jason Jong, ["Enforcing Immutability in your Double-Entry Ledger"](https://www.moderntreasury.com/journal/enforcing-immutability-in-your-double-entry-ledger), Modern Treasury, dezembro de 2021. O post inteiro. Gratuito. Ele não trata de moedas; essa parte da aula vem da próxima referência.
- Modern Treasury, ["How to Scale a Ledger"](https://www.moderntreasury.com/ebooks/how-to-scale-a-ledger), capítulos 4 (registrar versus autorizar, version locking e balance locking), 5 (imutabilidade, fechamento por moeda, o exemplo do cartão) e 6 (idempotência, cache de saldo e drift). Gratuito.
