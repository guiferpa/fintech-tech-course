# Roteiro · M6 · Dia 3 · Concorrência, imutabilidade e moedas


## Abertura

Esta é a aula em vídeo do módulo seis, dia três: concorrência, imutabilidade e moedas.

Um ledger correto para uma requisição por vez ainda não é um ledger. Em produção, duas autorizações para a mesma carteira chegam no mesmo milissegundo. A conta de receita de tarifas recebe um posting de cada transferência. E um operador quer consertar um lançamento com um update. Hoje são as duas propriedades que mantêm o ledger confiável sob carga: controle de concorrência, e imutabilidade. E no fim, o exercício no papel que prepara o projeto.


## A corrida

O post de Andy Qin, da Modern Treasury, começa com um app de pagamentos. Lucy tem cento e cinquenta dólares e envia cinquenta. O código ingênuo lê o saldo, verifica, e insere os postings.

Agora duas requisições ao mesmo tempo. As duas leem o saldo: quinze mil centavos.

A primeira verifica se cabe cinquenta, a segunda se cabe cento e vinte. As duas passam.

As duas inserem.

E Lucy termina com vinte dólares negativos. A verificação era verdadeira quando foi lida, e falsa quando a escrita aconteceu.

No Postgres, o nível padrão, Read Committed, não impede esse padrão. Você precisa de um lock ou de uma verificação de versão que amarre a leitura à escrita.


## Pessimista vs otimista

O post compara as duas respostas clássicas.

O lock pessimista trava a linha da conta antes de ler, com select for update. Os outros escritores da conta esperam ali até o commit.

O lock otimista usa uma coluna lock version. Toda escrita a incrementa, e declara qual versão espera. Se dois escreverem juntos, um confirma, e o outro atualiza zero linhas, faz rollback, lê de novo e decide se tenta de novo. A Modern Treasury escolheu o otimista, porque leituras não são bloqueadas por escritas, e a maior parte do tráfego de um ledger é leitura de saldos e extratos.

Um detalhe para copiar: o que precisa de versão é o conjunto de lançamentos da conta, não os atributos dela. Então a versão fica num registro separado, e renomear a conta não conflita com lançar nela. E para a sua carteira: trave só as contas que precisam de verificação, em ordem fixa de I D. Assim, Ana pagando Bruno enquanto Bruno paga Ana não vira deadlock.

> **Pausa:** Pergunta: por que travar as contas sempre na mesma ordem?

Para evitar deadlock. Se uma transação trava Ana e depois Bruno, e outra trava Bruno e depois Ana, cada uma espera a outra para sempre.


## Contas quentes

O lock otimista tem uma fraqueza. Numa carteira, algumas contas são tocadas por toda transação: receita de tarifas, caixa no banco parceiro, contas de clearing. São as contas quentes.

Nelas, a versão muda antes que a maioria consiga confirmar, e algumas transações nunca conseguem.

O whitepaper How to Scale a Ledger dá dois remédios. Primeiro: o modelo é decidido por lançamento, não por transação. Registrar dinheiro que já se moveu aceita leituras um pouco defasadas. Autorizar precisa de consistência forte. Quando Ana paga uma tarifa, o lançamento na carteira dela precisa de lock e verificação. O crédito na receita de tarifas não, porque só faz a receita crescer, e ninguém autoriza nada contra ela. Mesmo assim, os dois confirmam atomicamente.

Segundo: condições de saldo em vez de versão. O cliente diz: confirme só se este saldo continuar maior ou igual a zero. Escritas sem relação deixam de falhar. Só falha a que realmente quebraria a condição.

No exemplo do whitepaper, duas transações de duzentos e cinquenta e setecentos e cinquenta contra mil dólares precisam de seis chamadas com versão, e duas com condição de saldo.


## Condição de saldo no Postgres

No Postgres, com uma linha de saldo em cache por conta, a condição de saldo vira um único update: some o valor aos débitos pendentes, só se o available continuar cabendo. Zero linhas: saldo insuficiente, rejeite o hold.

O update trava a linha até o commit, então verificar e alterar é atômico.

Mas o cache precisa ser derivado dos postings, e atualizado na mesma transação.

E conferido contra a soma dos postings. Se desviar, pare de confiar no cache daquela conta.


## Imutabilidade

Agora imutabilidade. Jason Jong, da Modern Treasury, diz: se o dado foi mutado, ele foi destruído de forma irreversível. O exemplo: um lojista reclama de dez dólares de diferença num repasse de dez mil. Se os pedidos foram editados no lugar, rastrear pode levar dias. Se cada mudança foi uma transação nova, é uma consulta.

O post separa dois tipos de objeto. Objetos de negócio, como um pedido, podem ser mutáveis. São o que o produto mostra.

Transações do ledger são a verdade contábil. A exceção proposital é o estado pending: enquanto pendente, pode mudar, ou ir para archived se falhar antes de confirmar. Depois de posted, nunca mais muda. Lançamentos pendentes também não são editados: são descartados e substituídos por novos.


## Correção por estorno

Se nunca se edita, como corrigir? Uma tarifa foi cobrada como cinco reais, mas deveria ser três.

Estorno total: lance os lançamentos opostos, creditando a Ana e debitando a receita em cinco. Depois lance o valor correto, de três.

Lançamento da diferença: uma transação só, creditando a Ana e debitando a receita em dois.

De qualquer forma, o extrato mostra o que aconteceu e quando. O estorno total é mais claro para auditores, a diferença gera menos linhas. Escolha um e use em todo lugar. E estornos parciais também são transações novas, vinculadas à original.


## Append-only no banco

Não dependa de code review para manter a tabela append-only. Faça o banco recusar: um trigger antes de update ou delete em postings que lança uma exceção.

E revogue update e delete do role da aplicação, para o trigger não ser a única defesa.

Nas transações, permita só pending para posted, ou pending para archived, cada uma no máximo uma vez. É a regra do TigerBeetle de resolver uma vez só.

Para holds: o hold é uma transação pendente. A captura arquiva o hold e cria uma transação posted nova, apontando de volta para ele. A liberação só arquiva. Tudo numa transação de banco, para a reserva e a captura nunca ficarem ativas juntas.

> **Pausa:** Pergunta: um operador quer corrigir um posting com um update. O que acontece, e o que ele deveria fazer?

O trigger rejeita o update. Ele deve lançar uma transação nova de estorno, total ou da diferença, vinculada à original.


## Moeda em todo lançamento

A regra de soma zero esconde uma armadilha: você não soma reais com dólares. A verificação certa agrupa os lançamentos por moeda. Cada lançamento carrega a sua moeda. Então uma conversão precisa de quatro contas, não duas.

Ana converte quinhentos e cinquenta reais em cem dólares. Débito na carteira em reais da Ana.

Crédito no pool de câmbio em reais. Real fecha com real.

Débito no pool de câmbio em dólares.

Crédito na carteira em dólares da Ana. Dólar fecha com dólar.

Fechar entre moedas com uma taxa é rejeitado: taxas mudam, não há uma taxa única aceita por todos, e duas contas não refletem como uma conversão funciona. A taxa é um fato cotado ao cliente. Guarde a taxa, a origem e o horário na transação, e nunca recalcule.

> **Pausa:** Pergunta: por que uma conversão precisa de quatro contas?

Porque cada moeda precisa fechar sozinha. Dois lançamentos em reais e dois em dólares, com um pool de câmbio em cada moeda.


## Exercício no papel

O projeto começa amanhã, sem I A. Antes, faça este exercício no papel, a lápis.

O primeiro está resolvido. Ana deposita quinhentos por Pix: débito no caixa, crédito na carteira da Ana.

Dois: Ana envia duzentos para Bruno, com tarifa de dois. Decida se Bruno recebe duzentos ou cento e noventa e oito, e anote.

Três: Bruno estorna cinquenta. Decida se a tarifa volta, e registre como uma nova transação vinculada.

Quatro: o cartão da Ana é autorizado em cem num posto. Escreva como transação pendente, e calcule posted, pending e available.

Cinco: o valor final é oitenta. Mostre o que acontece com o hold, e recalcule os saldos.

Confira cada resposta contra quatro regras. Débitos iguais a créditos, por moeda. Nenhum lançamento posted alterado. O available da Ana nunca abaixo de zero. E depois da captura, nada sobra no hold. Essas quatro regras são as propriedades do teste de sexta. Pause o vídeo agora e faça os quatro no papel.


## Revisão relâmpago

Hora da revisão relâmpago. São três perguntas, sem olhar.

> **Pausa:** Pergunta um: cite uma vantagem do lock pessimista e uma do otimista.

O pessimista é simples e não exige retry. O otimista não bloqueia leituras.

> **Pausa:** Pergunta dois: o que é uma conta quente, e quais os dois remédios?

Uma conta tocada por quase toda transação, como receita de tarifas. Os remédios: decidir o modelo por lançamento, e usar condições de saldo no lugar de versão.

> **Pausa:** Pergunta três: como corrigir um lançamento posted errado?

Com uma transação nova: estorno total e relançamento, ou o lançamento da diferença. Nunca com update.


## O que anotar e próximo passo

Anote com as suas palavras: a corrida e os dois locks. Contas quentes e os remédios. As regras de imutabilidade. O fechamento por moeda. E o exercício no papel, com os saldos da Ana.

Depois, no lab, instale o fast-check e esboce geradores para as operações: depósito, transferência, estorno, hold, captura e liberação. Até a próxima aula.
