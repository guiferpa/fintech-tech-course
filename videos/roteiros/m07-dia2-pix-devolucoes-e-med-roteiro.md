# Roteiro · M7 · Dia 2 · Pix, devoluções e MED


## Abertura

Esta é a aula em vídeo do módulo sete, dia dois: Pix, devoluções e o MED.

No Brasil, o Pix é o principal caminho de entrada e saída de dinheiro de uma carteira. E ele é muito diferente do cartão. Não há autorização de dias, nem captura, nem arquivo de liquidação na manhã seguinte. O dinheiro se move em segundos, vinte e quatro horas por dia. Um Pix errado não pode ser cancelado antes da liquidação, porque ela já aconteceu. Só pode ser devolvido. Entrevistadores esperam o vocabulário: SPI, DICT, chave Pix, end to end I D, devolução e MED.


## O que é o Pix

O Pix é o arranjo de pagamentos instantâneos criado e operado pelo Banco Central, com regras na Resolução BCB número um.

O serviço fica disponível vinte e quatro horas, todos os dias do ano. Para você, isso é requisito de arquitetura: sem janela de manutenção, sem batch noturno que bloqueie pagamentos, e com plantão às três da manhã de domingo.

Entre participantes diferentes, a liquidação acontece no SPI, uma infraestrutura centralizada de liquidação bruta em tempo real. Bruta quer dizer que cada pagamento liquida sozinho, sem compensação no fim do dia.

Entre dois clientes do mesmo participante, a liquidação é interna. Sua carteira pagando outro usuário dela é uma transferência no ledger, não uma mensagem ao SPI.

Um Pix é autorizado quando o prestador do pagador encontra saldo e bloqueia o valor para liquidar. É um hold, como no cartão, mas de segundos. No ledger: o Pix de saída cria um hold, a confirmação do SPI vira lançamento, e uma rejeição libera.

E os prazos máximos ficam no Manual de Tempos do Pix. Instantâneo é um nível de serviço regulado, com prazos que seu sistema precisa cumprir.


## Participantes e DICT

Quem participa? É obrigatório para instituições autorizadas com mais de meio milhão de contas ativas. As menores podem aderir voluntariamente.

Nem todo participante se conecta direto ao SPI. Um participante responsável pode assumir outras instituições. Uma carteira jovem costuma viver nesse mundo indireto, com Pix por meio de um banco parceiro. É por isso que o seu projeto tem um banco parceiro, e não uma conexão direta.

O DICT é o diretório de chaves Pix operado pelo Banco Central. Uma chave é um celular, e-mail, CPF, CNPJ ou uma chave aleatória, vinculada a uma conta.

Quando o usuário digita uma chave, o prestador consulta o DICT, mostra o nome do recebedor, e só então envia.

E como a consulta revela nomes, um scraper consultando milhares de chaves é um ataque. Participantes devem detectar consultas excessivas sem pagamento. É para isso que servem os rate limiters desta semana.


## Os identificadores

Todo Pix carrega identificadores, e escolher o certo como chave da conciliação é decisão de design.

O end to end I D é criado pelo prestador do pagador e transita em todas as mensagens do SPI. Tem exatamente trinta e dois caracteres. É o único I D que todas as partes compartilham: seu banco parceiro, o SPI, e o outro prestador.

O T X I D é criado pelo recebedor, para conciliar cobranças. Quando sua carteira cobra alguém com um Q R code, gere o T X I D e guarde no pagamento esperado. Quando o crédito chegar, case por ele.

O R T R I D identifica uma devolução. A devolução ganha sua própria linha, ligada ao end to end I D original. Essas mensagens são do padrão I S O 20022: a pacs 008 carrega um pagamento, a pacs 002 um status, e a pacs 004 uma devolução.

No schema: guarde o end to end I D em todo lançamento Pix, com restrição de unicidade. Uma notificação duplicada do banco parceiro falha no insert, em vez de creditar duas vezes.

> **Pausa:** Pergunta: chegou um crédito Pix de uma cobrança que você gerou. Por qual identificador você descobre qual cobrança foi paga?

Pelo T X I D, que você mesmo gerou ao criar a cobrança. E o end to end I D garante que o mesmo crédito não entre duas vezes.


## Devoluções

Um Pix não pode ser cancelado depois que liquida. A resposta do regulamento é a devolução.

Em regra, quem inicia é o recebedor. Pode devolver tudo, ou fazer várias devoluções parciais, até o valor original.

E o prazo geral é iniciar em até noventa dias da transação.

Na API Pix, a devolução é um PUT no caminho do pix, com o E 2 E I D e um I D escolhido por você. PUT com I D do cliente é naturalmente idempotente: enviar duas vezes nomeia a mesma devolução.

O status é em processamento, devolvido, ou não realizado.

No ledger, a devolução é um novo lançamento na direção oposta, ligado ao original. Nunca atualize o valor original.

E garanta que a soma das devoluções não passe do original, na mesma transação que insere a devolução, com lock na linha da transferência original. Senão duas devoluções parciais concorrentes passam ambas pela verificação.

> **Pausa:** Pergunta: por que o lock na transferência original ao registrar uma devolução parcial?

Porque duas devoluções concorrentes poderiam ler a mesma soma antiga, passar as duas na verificação, e devolver mais que o valor original.


## O MED

Devoluções comuns dependem da boa vontade do recebedor. Vítimas de fraude não podem contar com isso. O MED, Mecanismo Especial de Devolução, permite que os prestadores bloqueiem e devolvam recursos sem autorização do recebedor a cada vez. Veja o fluxo de fraude.

A vítima reclama com o PSP do pagador, que abre uma recuperação de valores no DICT, sem analisar o mérito antes. A transação pode ter no máximo oitenta dias.

O DICT envia notificações de infração ao PSP que recebeu o Pix, e aos PSPs das transferências seguintes, porque fraudadores movem o dinheiro rápido.

O PSP do recebedor bloqueia na hora o valor, ou todo o saldo se for menor, avisa o cliente, e analisa em até sete dias corridos.

Se a fraude for confirmada, o PSP do pagador tem setenta e duas horas para iniciar a devolução.

O PSP do recebedor debita o cliente e envia a pacs 004 com o motivo F R zero um, em até seis horas em noventa e nove por cento dos casos.

Separado disso, existe o bloqueio cautelar. Com suspeita de fraude, o PSP do recebedor bloqueia os recursos simultaneamente ao crédito, avisa o cliente na hora, e o bloqueio dura no máximo setenta e duas horas. Vale só para contas de pessoas naturais.

> **Pausa:** Pergunta: recite os prazos do MED: oitenta dias, sete dias, setenta e duas horas, seis horas. O que é cada um?

Oitenta dias: idade máxima da transação para abrir. Sete dias: análise do PSP do recebedor. Setenta e duas horas: para o PSP do pagador iniciar a devolução, e também o limite do bloqueio cautelar. Seis horas: para o recebedor devolver depois da confirmação.


## Lições de engenharia

Três lições de engenharia para uma carteira que recebe Pix.

Bloqueado é uma categoria de saldo. Seu ledger já tem holds. Um bloqueio do MED é um hold que o cliente não criou e não pode liberar.

Os prazos são em horas. Construa um job que liste toda notificação de infração aberta com seu horário limite, e alerte bem antes.

E o débito de uma devolução do MED pode vir dias depois do crédito, quando o cliente já gastou. Decida de antemão o que acontece. A regra do guia é bloquear o saldo que existir.


## Open Finance

O Open Finance é uma iniciativa do Banco Central para aumentar a concorrência. Open Finance significa sistema financeiro aberto.

Com o consentimento do cliente, uma instituição autorizada vê dados mantidos por outra: saldos, cartões, extratos e investimentos.

O cliente escolhe o que compartilhar, com quem e por quanto tempo, e pode cancelar a qualquer momento. Não existe um sistema central guardando os dados, e é gratuito para o consumidor.

Para o curso, importa de duas formas. A iniciação de pagamento: outro aplicativo pode iniciar um Pix a partir da carteira do seu usuário.

E o consentimento vira objeto de primeira classe, com escopo, validade e revogação. Todo acesso é conferido contra ele.


## O lab de hoje

O lab é uma máquina de estados de pagamento com tabela de transições. Coloque as regras em dados, não em ifs espalhados. Criado vai para autorizado, recusado ou desconhecido. Desconhecido se resolve por consulta de status. Autorizado vai para capturado ou anulado. E os estados terminais, recusado, anulado e devolvido, não têm saída.

No Pix, autorizado é o hold de poucos segundos, e a confirmação do SPI é a captura. Uma devolução leva para devolvido parcial ou devolvido.

Aplique a mesma regra no Postgres, para um bug num serviço não conseguir pulá-la. Um update condicional, que só muda o status se o par existir na tabela de transições. Zero linhas: movimento inválido, ou outro worker mudou antes.

Testes: toda transição listada funciona, todo par não listado falha, terminais não têm saída, e duas atualizações concorrentes a partir do mesmo estado terminam com exatamente um vencedor.


## Revisão relâmpago

Hora da revisão relâmpago. São três perguntas, sem olhar.

> **Pausa:** Pergunta um: um Pix entre dois clientes da sua carteira passa pelo SPI?

Não. Ele liquida nos sistemas do próprio participante. É uma transferência no seu ledger.

> **Pausa:** Pergunta dois: qual identificador recebe restrição de unicidade em todo lançamento Pix, e por quê?

O end to end I D, porque é o único que todas as partes compartilham, e barra créditos duplicados.

> **Pausa:** Pergunta três: como desfazer um Pix já liquidado?

Com uma devolução, iniciada em geral em até noventa dias, registrada como novo lançamento oposto ligado ao original.


## O que anotar e próximo passo

Anote com as suas palavras: o vocabulário do Pix e a coluna que guarda cada identificador. Onde a sua carteira se encaixa entre os participantes, e o que a disponibilidade vinte e quatro por sete impõe. O fluxo do MED com os prazos. E o Open Finance em três frases.

Depois, no lab, construa a máquina de estados com a tabela de transições e os testes. Até a próxima aula.
