# Roteiro · Checkpoint 2 · Dia 1 · Pagamentos cross-border


## Abertura

Esta é a aula em vídeo do checkpoint dois: pagamentos cross-border.

Os módulos cinco a sete construíram uma carteira que move reais dentro do Brasil. Uma pergunta comum de entrevista é: e se o usuário quiser mandar cem dólares para um freelancer nos Estados Unidos? Ela toca tudo o que você estudou, mais três problemas novos: um preço que muda a cada segundo, uma cadeia de bancos que você não controla, e regras de dois países. Leia como revisão com um caso novo: idempotency keys, máquinas de estado, holds, lançamentos por moeda e conciliação, tudo volta. E isso prepara o system design de quarta.


## Bancos correspondentes

O dinheiro não viaja. Saldos mudam em livros de dois países. Um banco brasileiro sem conta nos Estados Unidos precisa de um banco que tenha: o correspondente.

O banco brasileiro debita o cliente em reais e compra dólares.

Envia uma instrução ao correspondente nos Estados Unidos. É uma mensagem, ainda sem dinheiro.

O correspondente debita a conta em dólares que o banco brasileiro mantém com ele.

E paga o banco do freelancer, direto ou por outro intermediário, que credita a conta dele.

Essa conta tem dois nomes. Nostro: nossa conta, nos seus livros. Vostro: sua conta, nos nossos livros. Os bancos mantêm assim pools de fundos nas moedas uns dos outros.

Cada salto leva tempo e cobra uma tarifa, descontada do valor. Vinte e cinco a setenta e cinco dólares é comum. Por isso o freelancer pode receber menos de cem.

Provedores como a Wise usam contas locais em cada país: o dinheiro entra localmente e sai localmente. É o mesmo raciocínio, com pools pré-financiados por moeda.


## As mensagens

O SWIFT é a rede de mensagens entre bancos. Carrega instruções, não dinheiro. Desde novembro de 2025, as mensagens M T de texto foram substituídas pelo I S O 20022, em XML. O mapeamento para saber.

A M T 103, transferência de cliente, virou pacs 008.

A M T 202, entre instituições, virou pacs 009.

Devoluções usam a pacs 004.

Relatório de status, pacs 002, que não tinha equivalente.

E extratos M T 940 viram camt 053. Os dois convivem até 2028, então você ainda vai ver M T 940.

O I S O 20022 traz dados que o seu código usa. O U E T R, uma referência única de ponta a ponta: guarde na transferência, como guardou o end to end I D do Pix. Endereços estruturados, com pelo menos cidade e país, a partir de novembro de 2026, então o formulário precisa de campos separados. E códigos de finalidade em alguns corredores. O provedor monta a mensagem, mas o seu modelo guarda o que ela exige.


## Cotação de câmbio

Uma cotação de câmbio é uma promessa com prazo: você converte por esta taxa até este horário. A F X Quotes API da Stripe decompõe o preço.

A taxa de referência, pública.

A taxa base, antes das tarifas.

A tarifa de câmbio.

O prêmio pela duração da trava: o provedor carrega risco de mercado enquanto a taxa está travada.

E a taxa aplicada ao cliente. A distância entre referência e taxa do cliente é o spread.

Dois comportamentos importam. A trava pode acabar antes: se o mercado passar de um limite, a cotação é invalidada. E uma cotação expirada falha de forma explícita, com erro 400 e um webhook. Na Wise, a trava é de trinta minutos. Se o dinheiro chega depois, vale a taxa do momento, e se só parte do dinheiro chega, a taxa não é garantida.


## Consumo único da cotação

A Ana viu quinhentos e cinquenta reais por cem dólares. Cobrar qualquer outro valor é bug. Então a cotação é uma linha gravada, com os dois valores, a taxa, a tarifa, o I D do provedor e a expiração, que uma única transferência consome. O update só marca como usada se ainda estiver aberta e não expirada.

A expiração gravada é a do provedor menos uma margem, para você não usar uma cotação que expira no meio da chamada.

Zero linhas: expirada ou já usada. Peça à Ana que confirme uma taxa nova. Nunca recote em silêncio.

E a criação da cotação aceita idempotency key, para um toque duplo não criar duas travas. A referência que você envia ao provedor é gerada uma vez e gravada antes da chamada, e um retry envia o mesmo valor. O lado do ledger, com quatro contas balanceadas por moeda, está no módulo seis, dia três.

> **Pausa:** Pergunta: a cotação expirou enquanto a Ana confirmava. O que o sistema faz?

O update retorna zero linhas. O sistema mostra uma cotação nova e pede que a Ana confirme. Nunca cobra por uma taxa que ela não viu.


## Tarifas e cut-offs

Um pagamento SWIFT carrega um código de tarifa.

O U R: o remetente paga tudo antecipado, e o beneficiário recebe o valor integral.

S H A: compartilhado. Bancos intermediários podem descontar tarifas do valor, e o beneficiário recebe menos.

Ben: o beneficiário paga, e recebe o valor menos as tarifas. A tela de cotação precisa dizer qual código vale. E a conciliação precisa esperar um valor menor em S H A ou ben, com um código de motivo próprio, não um valor diferente genérico.

E cada moeda tem um horário de corte diário para execução no mesmo dia. Dólar via SWIFT, dezoito e trinta, horário da Europa central. Depois do corte, passa para o dia seguinte, e feriados não processam. Então toda transferência tem uma data de liquidação esperada, que depende da moeda, do trilho, do corte e de dois calendários de feriados. Grave, e deixe a conciliação sinalizar o que passar dela.


## Trilhos locais

A maioria das fintechs chama um provedor que paga no trilho doméstico do destinatário, como A C H nos Estados Unidos ou sepa na Europa. Um detalhe: as duas moedas precisam passar pelos mínimos. Três dólares para a África do Sul falham, porque dão cinquenta e cinco rands, e o mínimo é cem. Valide os dois lados antes de travar a cotação. Os status da Wise se encaixam quase um a um na sua máquina de estados.

Incoming payment waiting: criada, esperando os recursos.

Processing: recursos recebidos, com checagens de lavagem de dinheiro, compliance e fraude.

Funds converted: convertido para a moeda de destino.

Outgoing payment sent: pago, final, desde que os recursos não voltem.

E bounced back: devolvido, dias depois, quando o banco do beneficiário rejeita a conta.

Então enviado não é recebido. O seu estado paid out não é terminal para a conciliação.


## Compliance

Antes de o dinheiro sair, remetente e beneficiário passam por triagem.

A lista mais conhecida é a S D N, da O F A C, dos Estados Unidos. Bens dessas pessoas ficam bloqueados. E empresas com cinquenta por cento ou mais de donos bloqueados também, mesmo fora da lista.

A triagem é aproximada, com algoritmos como Jaro-Winkler e Soundex, e gera falsos positivos. A O F A C não recomenda limiar: você decide.

Na carteira, um possível match é um estado, compliance review. O hold mantém os recursos reservados até um analista liberar ou bloquear.

E nunca faça retry ou estorno automático de um hit.

Códigos de finalidade dizem por que o dinheiro se move. No Brasil, a Resolução BCB duzentos e setenta e sete atribui ao cliente a classificação. Uma devolução usa o código da operação original. Então é um campo obrigatório, escolhido pelo cliente, e copiado para qualquer devolução.

> **Pausa:** Pergunta: a triagem deu possível match no beneficiário. O que acontece com o dinheiro da Ana?

Fica reservado pelo hold, no estado compliance review, até um analista decidir. Nada de retry nem de estorno automático.


## O lado brasileiro

No lado brasileiro.

Converter reais em moeda estrangeira é uma operação de câmbio, feita por instituição autorizada pelo Banco Central. O cliente precisa ser identificado, e a remessa pede motivo, banco e conta do beneficiário.

O VET, valor efetivo total, é o total de reais por unidade de moeda estrangeira, com taxa, IOF e tarifas. Precisa ser informado antes da operação. Na sua tela de cotação, é um número só.

E E F X é o prestador de pagamento internacional. A Resolução BCB quinhentos e sessenta e um, de 2026, reescreveu as regras: limites de dez mil dólares em alguns casos, e vedado o uso de ativos virtuais para pagar a contraparte.

E é vedada a compensação entre os reais recebidos do usuário e os entregues a ele. Os reais de cada usuário precisam ser rastreáveis separadamente, e é isso que um ledger por transação oferece.

Sobre Pix cross-border, a única declaração oficial verificada é que turistas brasileiros já pagam com Pix em alguns estabelecimentos no exterior. Trate o resto como não verificado.


## O lab no papel

O lab de hoje é no papel, sem código. A Ana envia cem dólares da carteira em reais para a conta de um freelancer nos Estados Unidos, por um provedor de payouts.

Desenhe a máquina de estados: cotado, cotação expirada, fundos reservados, revisão de compliance, bloqueado, debitado, convertido, payout enviado, desconhecido, pago, devolvido, reembolsado, conciliado.

Para cada transição, escreva o gatilho, seja chamada, webhook, timeout ou arquivo, e a idempotency key. Para desconhecido, a regra do módulo sete: consulte o status primeiro.

Preencha a linha da cotação com números reais: expiração, margem, VET, código de tarifa e de finalidade.

Escreva os lançamentos de hold, débito e tarifa, conversão, envio, liquidação, e um bounce com reembolso. Cada um balanceia em reais e em dólares separadamente. E decida quem absorve a diferença cambial quando o bounce volta depois que a taxa mudou.

E a conciliação: os arquivos, a chave de cada um, seu I D, o do provedor, o U E T R, uma regra para descontos S H A, e uma para a data esperada. Pause o vídeo e faça agora.


## Revisão relâmpago

Hora da revisão relâmpago. São três perguntas, sem olhar.

> **Pausa:** Pergunta um: o que é uma conta nostro?

A conta que o seu banco mantém num correspondente estrangeiro, na moeda dele. Nossa conta, nos seus livros.

> **Pausa:** Pergunta dois: com código de tarifa S H A, quanto o freelancer recebe, e o que a conciliação faz?

Possivelmente menos que cem, porque intermediários descontam tarifas. A conciliação espera isso, com um código de motivo próprio.

> **Pausa:** Pergunta três: o que é o VET?

O valor efetivo total: reais por unidade de moeda estrangeira, incluindo taxa, IOF e tarifas, informado antes da operação.


## O que anotar e próximo passo

Anote com as suas palavras: nostro, vostro e os saltos. As mensagens I S O 20022 e o U E T R. As regras de cotação. Os códigos de tarifa e os horários de corte. E as regras brasileiras: VET, finalidade e E F X.

Depois, faça o lab no papel: máquina de estados, cotação, e lançamentos por moeda. Até a próxima aula.
