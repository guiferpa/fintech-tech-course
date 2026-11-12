# Roteiro · M6 · Dia 2 · Holds, contas de clearing e Money


## Abertura

Esta é a aula em vídeo do módulo seis, dia dois: holds, contas de clearing, e o tipo Money.

O ledger de ontem registra dinheiro que já se moveu. Mas a maioria das operações não é assim. Uma compra no cartão reserva o dinheiro e liquida depois. Um app de corridas reserva cinquenta reais e cobra trinta e sete. Cada caso precisa de um hold, uma reserva: dinheiro que não está mais disponível, mas ainda não saiu. E aí vêm duas perguntas que entrevistadores adoram: como reservar de modo que o passo final nunca deixe a conta negativa? E quando algo fica preso no meio, como você percebe? O TigerBeetle responde a primeira. O Ledger da Stripe, a segunda.


## Hold em duas fases

O TigerBeetle é um banco de dados feito só para contabilidade de partidas dobradas. Ele descreve a two-phase transfer, a transferência em duas fases. O nome vem do two-phase commit.

Na fase um, uma transferência criada com a flag pending reserva o valor.

Ela soma o valor ao debits pending da conta debitada, e ao credits pending da creditada. Os saldos posted não mudam.

Na fase dois, a reserva é resolvida de exatamente uma de três formas: confirmada, que é o post, anulada, que é o void, ou expira.

Na carteira: Ana paga cem reais num posto com cartão. A autorização chega, e a carteira cria uma transferência pendente para uma conta de liquidação de cartão. O available da Ana cai cem na hora, mas o posted continua igual.

Quando a bandeira manda o valor final, a carteira confirma. Se a autorização for cancelada, anula. Se nada chegar a tempo, expira.

É o mesmo modelo de pending, posted e available de ontem. Fornecedor diferente, mesma ideia.


## Os desfechos

A documentação é precisa sobre a fase dois.

Post total: uma nova transferência com a flag post pending transfer e o pending I D, com o valor igual. Tudo passa de pending para posted.

Post parcial: o mesmo, com valor menor. Só esse valor é confirmado, e o resto volta para as contas.

Post acima do valor reservado é rejeitado.

Void: uma transferência com void pending transfer. A reserva é liberada, e o posted não muda.

Expiração: a pendente tinha um timeout que passou. Tudo volta, como num void.

O exemplo da documentação: uma pendente de cento e vinte e três. Confirmar cem soma cem aos posted, tira a reserva inteira dos pending, e os outros vinte e três voltam. É o posto: autorizou cem, o combustível custou oitenta, e vinte voltam ao available da Ana.


## Por que é seguro

Três regras tornam o modelo seguro, e cada uma corresponde a algo de módulos anteriores.

Uma pendente é resolvida uma única vez. Tentar de novo falha com pending transfer already posted. Uma captura duplicada da bandeira não captura duas vezes. É idempotência no modelo de dados.

Transferências são imutáveis. Confirmar ou anular nunca edita a pendente. Cria uma transferência nova, que aponta para a original pelo pending I D. O histórico fica completo.

Timeouts são intervalos em segundos, não horários de parede, porque relógios em máquinas diferentes discordam.

E a propriedade mais importante: o limite de saldo é verificado na fase um, quando o dinheiro é reservado. Depois, confirmar, toda ou em parte, só consome o que já estava separado. O projeto de quinta depende disso: se o available maior ou igual a zero é verificado na criação do hold, a captura e a liberação nunca precisam verificar de novo.

> **Pausa:** Pergunta: por que a captura de um hold nunca deixa a conta negativa?

Porque o limite foi verificado ao reservar. A captura só consome dinheiro já separado, e nunca mais do que o reservado.


## A conta do TigerBeetle

A referência de conta do TigerBeetle é uma boa lição sobre o pouco que uma conta precisa.

Não existe campo de saldo. A conta guarda quatro contadores: débitos e créditos, pendentes e confirmados. Os saldos são calculados deles, como as fórmulas de ontem.

Os valores são inteiros sem sinal de cento e vinte e oito bits. Sem decimais, sem ponto flutuante.

O campo ledger separa os conjuntos de contas que podem transacionar entre si. Um uso comum é um ledger por moeda, e aí uma transferência entre uma conta em real e outra em dólar é impossível por construção.

Contas são imutáveis depois de criadas, exceto os contadores. Você não edita a moeda de uma conta.

E os invariantes globais: a soma dos débitos pendentes é igual à dos créditos pendentes, e o mesmo para os confirmados. É a regra de soma zero, para cada fase.


## Limites de saldo

Duas flags deixam o próprio banco recusar um saldo negativo. A carteira do cliente é credora, e o saldo dela não pode ficar abaixo de zero.

Então ela usa debits must not exceed credits. A transferência é rejeitada se débitos pendentes, mais débitos confirmados, mais o valor, passarem dos créditos confirmados.

Reorganize: créditos confirmados, menos todos os débitos, precisa ser maior ou igual ao valor. É a fórmula do available de ontem. Duas fontes independentes chegam à mesma regra. Dinheiro que não chegou não pode ser gasto, e dinheiro reservado não pode ser gasto duas vezes.

O exemplo: créditos confirmados cem, débitos setenta. Um hold novo de cinquenta levaria os débitos a cento e vinte. Falha na hora, na reserva.

No Postgres você copia a regra: antes de inserir um débito pendente, calcule o available na mesma transação, com a conta protegida contra escritas concorrentes, e rejeite se não couber. O teste de propriedades de sexta vai martelar isso: dez mil operações, e o available nunca negativo.

> **Pausa:** Pergunta: por que créditos pendentes não entram na verificação?

Porque ainda podem não chegar. Contar com eles deixaria o cliente gastar um dinheiro que talvez nunca liquide.


## Água presa no cano

Agora a segunda pergunta. O Ledger da Stripe processa uns cinco bilhões de eventos por dia. A ideia mais útil é uma analogia com água: em regime estável, os reservatórios terminais estão cheios, e os canos intermediários, as contas de clearing, estão vazios. Se tem água presa no cano, você tem um problema.

Veja uma transferência da Ana para um banco externo. Passo um: a carteira envia ao banco parceiro. Débito na carteira da Ana, crédito na clearing de saída.

Passo dois: o banco parceiro confirma. Débito na clearing, crédito no caixa. A clearing volta a zero.

Agora suponha que o passo dois nunca aconteça, porque o webhook se perdeu, ou foi lançado na transferência errada. Os duzentos ficam parados na clearing. Nada falta na soma, o ledger continua fechando. Mas tem água no cano. Uma consulta diária por contas de clearing com saldo diferente de zero, mais antigo que o prazo de liquidação, encontra o problema.

> **Pausa:** Pergunta: se o ledger continua fechando, como você descobre que uma transferência ficou presa?

Pela conta de clearing: ela deveria voltar a zero. Saldo diferente de zero além do prazo esperado é dinheiro preso.


## Qualidade de dados

Ilya Ganelin, da Stripe, descreve três perguntas medidas para cada fatia da movimentação de dinheiro.

Clearing: o fluxo terminou, deixando as contas de clearing em zero?

Pontualidade: os dados chegaram a tempo?

Completude: todo evento do sistema de origem tem um correspondente no ledger? E o Ledger é imutável: correções são novas operações que revertem e reprocessam, nunca edições. Para o projeto, dê a cada fluxo de vários passos uma conta de clearing ou de reserva, e transforme essa conta é zero quando tudo liquida numa verificação que você roda.


## O tipo Money

O lab de hoje constrói um tipo Money.

Ele é um par: valor em big int, na menor unidade, e o código da moeda.

Somar um real com um dólar lança erro, não devolve dois. E nunca faça parse de valores com parse float.

Uma divisão não pode perder nem inventar um centavo. Dividir cem centavos em três dá trinta e três, com resto um. Dê o quociente a todos, e distribua o resto um centavo por vez, numa ordem fixa: trinta e quatro, trinta e três, trinta e três. A ordem fixa garante que um retry ou replay produza postings idênticos.

Um bom teste é uma propriedade: para qualquer valor e qualquer número de partes, as partes somam o total e diferem em no máximo um centavo.

E arredondar é uma decisão. Uma tarifa de um e meio por cento sobre dez reais e dez dá quinze vírgula quinze centavos. O arredondamento bancário leva metades exatas para o par: dois e meio vira dois, três e meio vira quatro. Ele evita o viés para cima que se acumula em milhões de tarifas.

Qualquer que seja a regra, calcule a tarifa uma vez, como inteiro, e use o mesmo valor no débito e no crédito. Senão o ledger não fecha.

> **Pausa:** Pergunta: divida dez centavos em três partes.

Quatro, três e três. O quociente é três, e o resto, um, vai para a primeira parte.


## Revisão relâmpago

Hora da revisão relâmpago. São três perguntas, sem olhar.

> **Pausa:** Pergunta um: um hold de cento e vinte e três é confirmado com cem. O que acontece com os vinte e três?

Voltam para as contas. A reserva inteira sai dos contadores pending, e só cem entram nos posted.

> **Pausa:** Pergunta dois: em que fase o limite de saldo é verificado, e por quê?

Na fase um, na reserva. Depois disso, a captura só consome o que já estava separado.

> **Pausa:** Pergunta três: como o Ledger da Stripe enxerga dinheiro preso?

Como uma conta de clearing com saldo diferente de zero, além do prazo esperado de liquidação.


## O que anotar e próximo passo

Anote com as suas palavras: o ciclo de vida do hold, com o exemplo de cento e vinte e três e cem. Por que verificar o limite na fase um torna a fase dois segura. A flag do TigerBeetle e a regra do available. Contas de clearing contra terminais, com um desenho. E as suas regras de Money.

Depois, no lab, construa o tipo Money com testes unitários. Até a próxima aula.
