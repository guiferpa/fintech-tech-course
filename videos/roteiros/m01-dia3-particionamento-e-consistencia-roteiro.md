# Roteiro · M1 · Dia 3 · Particionamento e consistência


## Abertura

Esta é a aula em vídeo do módulo um, dia três: particionamento, modelos de consistência e trade-offs.

Duas perguntas decidem boa parte da arquitetura de pagamentos. Como dividir os dados quando uma máquina não basta? E, para cada operação, quão atualizados os dados precisam estar? Uma verificação de saldo e um gráfico mensal de gastos precisam de respostas bem diferentes. No final, você vai montar essa resposta para oito operações da carteira.


## Particionamento

Ontem vimos replicação: copiar os mesmos dados para vários nós. Particionamento, ou sharding, é diferente: divide dados diferentes entre os nós. Todo registro tem uma partition key, que decide onde ele mora.

Uma forma é por faixa de chave. A partição um guarda de A a F, a dois de G a M. Varrer uma faixa é barato, como todas as transações da conta quarenta e dois em março. Mas se a chave for um timestamp, todas as escritas de hoje caem na mesma partição.

A outra é por hash da chave. A carga se espalha de forma uniforme, mas você perde a varredura barata entre chaves. Só consegue varrer bem dentro de uma mesma chave. O DynamoDB faz hash da partition key, e mantém os itens da mesma chave ordenados por uma sort key.

Sistemas reais fazem os dois: cada partição é replicada.


## Hot partitions

O guia do DynamoDB diz: projete para ter atividade uniforme em todas as partition keys. Cada partição entrega no máximo três mil leituras e mil escritas por segundo. Quando poucas chaves recebem a maior parte do tráfego, elas viram hot partitions e sofrem throttling, mesmo que a tabela como um todo tenha capacidade sobrando.

Veja a tabela de chaves. ID do usuário, com muitos usuários: boa.

Código de status, com poucos valores, como PENDING: ruim.

Data de criação: ruim. Num dado dia, todos os itens novos vão para uma única chave.

ID da conta é bom para a maioria das contas. Os lançamentos ficam juntos, e o extrato é uma consulta numa partição só.

Mas tem o problema da última linha: um grande lojista recebendo milhares de pagamentos por segundo, ou a conta de tarifas que toda transferência credita. São as hot accounts, que o módulo seis trata.

> **Pausa:** Pergunta: por que uma data é uma partition key ruim?

Porque num dado dia todas as escritas novas caem na mesma chave, e portanto na mesma partição, que sofre throttling.


## Write sharding

O remédio para uma chave quente por natureza é o write sharding: adicionar um sufixo à chave. Em vez de uma linha de tarifas, você tem N linhas, e o saldo é a soma delas.

Com sufixo aleatório, as escritas se espalham, mas para ler tudo daquele dia você consulta as N chaves e junta.

Com sufixo calculado, derivado de algo que você conhece, como o ID da transferência, você espalha as escritas e ainda consegue calcular a chave exata de um item.

E quando nós entram ou saem, os dados se movem. O Cassandra usa consistent hashing, que move só uma pequena fração das chaves. Com um hash módulo N ingênuo, quase toda chave mudaria de lugar.


## Linearizabilidade

Linearizabilidade é o modelo forte mais comum. O sistema se comporta como se houvesse uma única cópia dos dados. Depois que uma escrita termina, toda leitura que começa depois a enxerga, seja qual for a réplica.

É o que você assume implicitamente quando escreve: se saldo maior ou igual ao valor, debita. Se a leitura do saldo pode estar desatualizada, dois débitos concorrentes passam os dois pela verificação.

No DynamoDB, a leitura padrão é a mais fraca. Para a forte, você pede consistent read, e ela custa o dobro. No Cosmos DB, o throughput de leitura com strong é a metade, porque lê de duas réplicas.

E nem tudo aceita leitura forte. Um global secondary index do DynamoDB não aceita. Se você verifica idempotency keys por um índice desses, dois retries chegando juntos podem os dois ver chave nova. Mantenha essa verificação na primary key, ou numa unique constraint do Postgres.

O custo é coordenação. Toda operação linearizável precisa alcançar uma maioria ou um líder. Isso adiciona latência, e um nó isolado da maioria não consegue responder.

> **Pausa:** Pergunta: defina linearizabilidade sem usar a palavra consistente.

O sistema se comporta como uma única cópia: depois que uma escrita termina, toda leitura que começa depois enxerga essa escrita.


## CAP com cuidado

O CAP costuma ser resumido como escolha dois entre três, o que engana. Partições não são opcionais; elas acontecem. O enunciado preciso: na presença de uma partição, um sistema não consegue ser consistente e disponível ao mesmo tempo. Consistência aqui é linearizabilidade.

Na escolha CP, um nó que não alcança a maioria recusa ou espera, em vez de responder com dado desatualizado. O CockroachDB bloqueia em vez de devolver dado inconsistente.

Na escolha AP, todo nó continua respondendo, e as réplicas se reconciliam depois. O MongoDB de ontem mostra os dois: w majority é o comportamento CP, w um é o AP, com rollback depois.

Ben Darnell lembra dois pontos. A maioria das quedas não é partição, é hardware, bug e erro de operador. E sistemas CP pagam pela consistência mesmo com a rede funcionando. Isso é o PACELC.

> **Pausa:** Pergunta: durante uma partição, o que um nó CP faz com uma requisição? E um nó AP?

O nó CP recusa ou espera, porque não alcança a maioria. O nó AP responde com o que tem e reconcilia depois.


## PACELC

O PACELC estende o CAP. Se há partição, escolha entre disponibilidade e consistência. Senão, escolha entre latência e consistência. Partições são raras. O trade-off do senão está em toda requisição.

O Cosmos DB põe números nisso. Na maioria dos níveis, numa região, leituras e escritas ficam abaixo de dez milissegundos no p99.

Com strong entre regiões, cada escrita custa duas vezes a ida e volta entre as regiões mais distantes, mais dez milissegundos. Com cento e vinte de ida e volta, são uns duzentos e cinquenta milissegundos por escrita.

As global tables do DynamoDB mostram a mesma escolha. No modo eventual, as mudanças chegam às outras regiões em cerca de um segundo. No modo strong, a escrita é replicada antes de retornar, e paga a viagem.

A mentalidade certa: você não escolhe um modelo para a empresa. Escolhe um por operação.


## O espectro de consistência

O Cosmos DB é um bom mapa do espectro, com cinco níveis. Strong é linearizabilidade.

Bounded staleness promete atraso abaixo de K versões ou T segundos. Ótimo para dashboards: no máximo cinco segundos de atraso é algo que você pode mostrar ao usuário.

Session dá read your writes dentro da sessão, como vimos ontem.

Consistent prefix garante que as escritas de uma transação aparecem juntas.

E eventual só promete convergir em algum momento. Um cliente pode até ler valores mais antigos do que já leu. Serve para contador de curtidas.

Existe ainda a strong eventual consistency, dos CRDTs, usada pelo Redis Active-Active: réplicas com as mesmas atualizações chegam ao mesmo estado, sem coordenar. Para um contador, ótimo. Para dinheiro, não: dois débitos juntados depois do fato podem deixar a conta negativa, porque a verificação de saldo nunca foi coordenada.


## Um modelo por operação

Junte tudo perguntando, para cada operação: qual o dano de ler um dado desatualizado, e qual o custo de coordenar?

Débito com verificação de saldo precisa ser linearizável, dentro de uma transação, senão a conta fica negativa. Verificar a idempotency key também, na chave, nunca numa réplica de índice, senão vem cobrança dupla.

O extrato logo após a transferência do próprio usuário precisa de read your writes. O extrato enquanto ele rola a tela precisa de monotonic reads.

O gráfico mensal aceita eventual ou bounded staleness. O saldo da tela inicial, read your writes, com um horário de atualizado em.

O contador de velocidade para fraude aceita eventual com margem de segurança, porque coordenar todo pagamento custa mais. E a taxa de câmbio deve ser lida de forma linearizável, numa versão gravada no lançamento, para cobrar exatamente a taxa cotada. Esta tabela é o entregável desta semana: cada linha com uma justificativa de uma linha.


## Revisão relâmpago

Hora da revisão relâmpago. São três perguntas, sem olhar.

> **Pausa:** Pergunta um: por que verificar idempotência por um global secondary index do DynamoDB não é seguro?

Porque o índice só tem leitura eventual. Dois retries chegando juntos podem os dois ver chave nova.

> **Pausa:** Pergunta dois: o que o E L C do PACELC descreve?

Que mesmo sem partição você troca latência por consistência, em toda requisição.

> **Pausa:** Pergunta três: o que um sufixo calculado melhora no write sharding?

Ele espalha as escritas e ainda permite calcular a chave exata para ler um item, sem consultar todas.


## O que anotar e próximo passo

Anote com as suas palavras: a partition key da carteira e quais contas ficam quentes. Linearizável e eventual numa frase cada, e o custo da forte. O CAP enunciado do jeito certo, e o que o PACELC acrescenta. E um primeiro rascunho da tabela de oito operações.

Depois, rascunhe essa tabela no docs barra m zero um ponto md, e transforme o Teste-se em flashcards. Até a próxima aula.
