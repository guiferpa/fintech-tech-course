# Módulo 1, quarta-feira: particionamento, modelos de consistência e trade-offs

[Módulo 1](../../modules/01-distributed-systems-fundamentals.pt-BR.md) · [Read in English](day-3.md)

**Tempo de leitura:** cerca de 45 minutos. Use o resto do bloco de 2 horas nas referências do final e depois rascunhe a tabela de consistência descrita no final.

Este é um texto original escrito para este curso. Ele se baseia nas referências listadas no final, e cada seção indica a fonte que segue.

## Por que isso importa para uma fintech

Duas perguntas decidem boa parte da arquitetura de um sistema de pagamentos. Primeira: como dividir os dados quando uma máquina não basta mais? Segunda: para cada operação, quão atualizados e quão acordados entre as réplicas os dados precisam estar? Uma verificação de saldo antes de um débito e um gráfico mensal de gastos precisam de respostas muito diferentes. Hoje você ganha o vocabulário para responder às duas, usando o jeito como DynamoDB, Azure Cosmos DB, Cassandra e CockroachDB documentam o próprio comportamento, e termina escrevendo essas respostas para 8 operações da carteira digital.

## 1. Particionamento: dividir os dados entre máquinas

*Fonte principal: Amazon DynamoDB Developer Guide, "Best practices for designing and using partition keys effectively" e suas subpáginas.*

A replicação (terça) copia os mesmos dados para vários nós. O **particionamento**, também chamado de sharding, divide dados diferentes entre os nós, de modo que cada um guarda só uma parte. Sistemas reais fazem os dois: cada partição é replicada.

Todo registro tem uma **partition key**, e o sistema a usa para decidir qual partição guarda o registro. Há duas formas clássicas de mapear chaves para partições.

- **Por faixa de chave.** A partição 1 guarda as chaves de A a F, a partição 2 de G a M, e assim por diante. Varreduras por faixa são baratas ("todas as transações da conta 42 em março"), mas se a chave for um timestamp, todas as escritas de hoje caem na mesma partição.
- **Por hash da chave.** O sistema calcula o hash da chave e atribui faixas de valores de hash às partições. A carga se espalha de forma uniforme, mas você perde as varreduras baratas por faixa entre chaves; só consegue varrer com eficiência dentro de uma chave.

O DynamoDB faz hash da partition key e pode manter os registros com a mesma chave ordenados por uma segunda chave (a *sort key*). O guia diz para "design your application for uniform activity across all partition keys" (projetar a aplicação para ter atividade uniforme em todas as partition keys). Ele também dá os números concretos: cada partição entrega no máximo 3.000 unidades de leitura e 1.000 unidades de escrita por segundo, em que uma unidade de escrita é uma escrita por segundo de um item de até 1 KB. Quando poucas chaves recebem a maior parte do tráfego, as partições que as guardam viram **hot partitions** e as requisições a elas sofrem throttling, mesmo que a tabela como um todo tenha capacidade sobrando.

Vale copiar para suas anotações a tabela de chaves boas e ruins do guia:

| Partition key | Uniformidade |
| --- | --- |
| ID do usuário, com muitos usuários | Boa |
| Código de status, com poucos valores possíveis | Ruim |
| Data de criação arredondada para dia, hora ou minuto | Ruim |
| ID do dispositivo, com dispositivos acessados em ritmos parecidos | Boa |
| ID do dispositivo, quando um dispositivo é muito mais popular que os outros | Ruim |

Leia a carteira digital nessa tabela. `status = 'PENDING'` como chave é ruim. `created_date` é ruim: em um dado dia, observa o guia, todos os itens novos vão para essa única chave. O **ID da conta** é bom para a maioria das contas: os lançamentos de cada conta ficam juntos, então um extrato é uma consulta em uma partição só. Mas ele tem o problema da última linha: um grande lojista recebendo milhares de pagamentos por segundo, ou a conta de tarifas que toda transferência credita, é o dispositivo muito mais popular que os outros. O Módulo 6 trata dessas hot accounts.

O remédio do guia para uma chave que é quente por natureza é o **write sharding**: adicionar um sufixo à chave para que suas escritas se espalhem por muitos valores de chave. O exemplo do guia acrescenta um número aleatório de 1 a 200 a uma data, gerando de `2014-07-09.1` até `2014-07-09.200`. O custo fica nas leituras: para pegar tudo daquele dia você consulta as 200 chaves e junta os resultados. Um sufixo **calculado**, derivado de algo que você conhece, como o ID do pedido, mantém as escritas espalhadas e permite calcular a chave exata para ler um item diretamente. Para uma conta de tarifas, `fees#17` (com 17 derivado do ID da transferência) espalha os créditos por N linhas, e o saldo de tarifas vira a soma das N linhas.

Quando nós entram ou saem, os dados precisam se mover entre eles. Isso é o **rebalanceamento**. A documentação do Cassandra explica por que ele usa consistent hashing: quando o número de nós muda, ele "only has to move a small fraction of the keys" (só precisa mover uma pequena fração das chaves), diferente de um `hash(key) % N` ingênuo, em que quase toda chave muda de lugar. Ele também dá a cada nó físico muitos tokens no anel (virtual nodes), de modo que um nó novo pega pedaços pequenos de todo mundo.

## 2. Linearizabilidade: comportar-se como uma cópia única

*Fontes principais: documentação do Azure Cosmos DB, "Consistency levels in Azure Cosmos DB", e Amazon DynamoDB Developer Guide, "DynamoDB read consistency".*

Replicação e particionamento dão a você muitas cópias e muitos lugares. Um modelo de consistência diz o que os leitores podem ver apesar disso.

O modelo forte mais comum é a **linearizabilidade**: o sistema se comporta como se houvesse uma única cópia dos dados, e cada operação acontece em um instante entre seu início e seu fim. A documentação dos produtos descreve isso em termos práticos:

- O nível **strong** do Cosmos DB "offers a linearizability guarantee" (oferece garantia de linearizabilidade): as leituras "are guaranteed to return the most recent committed version of an item" (garantidamente devolvem a versão commitada mais recente de um item), e um cliente nunca vê uma escrita não commitada ou parcial.
- A **strongly consistent read** do DynamoDB devolve "the most up-to-date data, reflecting the updates from all prior write operations that were successful" (os dados mais atuais, refletindo as atualizações de todas as escritas anteriores bem-sucedidas).
- A Cockroach Labs descreve o contrato do CockroachDB como "the most recent write is always visible to subsequent readers" (a escrita mais recente é sempre visível para os leitores seguintes).

Na prática: depois que uma escrita termina, toda leitura que começa depois a enxerga, seja qual for a réplica que a atende.

A linearizabilidade é o que você assume implicitamente quando escreve `if balance >= amount then debit`. Se a leitura do saldo pode estar desatualizada, dois débitos concorrentes podem passar os dois pela verificação. No DynamoDB isso é uma flag por requisição, e o padrão é a mais fraca:

```bash
# Eventualmente consistente por padrão; --consistent-read pede o último valor commitado
aws dynamodb get-item --table-name accounts \
  --key '{"account_id": {"S": "acc_42"}}' --consistent-read
```

Os detalhes da documentação são onde estão as armadilhas para uma fintech:

- **Leituras fortes custam mais.** O DynamoDB diz que leituras eventualmente consistentes "are half the cost of strongly consistent reads" (custam metade das fortemente consistentes). O Cosmos DB diz que o throughput de leitura com strong e bounded staleness "is half that of the other consistency levels" (é metade do dos outros níveis), porque elas leem de duas réplicas em vez de uma.
- **Nem tudo pode ser lido de forma forte.** No DynamoDB, leituras fortemente consistentes "from a global secondary index or a DynamoDB stream are not supported" (a partir de um global secondary index ou de um DynamoDB stream não são suportadas). Se você consulta idempotency keys por um global secondary index, essa consulta é eventualmente consistente, e dois retries chegando juntos podem os dois ver "chave nova". Mantenha essa verificação na primary key da tabela, ou no Postgres com uma unique constraint.

O custo da linearizabilidade é coordenação. Toda operação linearizável precisa alcançar uma maioria, ou um líder único, que conhece o estado mais recente. Isso adiciona latência, e um nó isolado da maioria não consegue atender operações linearizáveis. A documentação do Cosmos DB mostra isso: com consistência strong entre regiões, ele pode tirar do quorum uma região que não responde, e essa região fica então "no longer able to serve reads" (sem poder atender leituras) até voltar.

## 3. CAP, enunciado com cuidado

*Fonte principal: blog da Cockroach Labs, "Limits of the CAP theorem" (Ben Darnell).*

O teorema CAP costuma ser resumido como "escolha dois entre consistência, disponibilidade e tolerância a partições", o que engana. Partições de rede não são algo que você escolhe; elas acontecem. Jeff Hodges resume em uma linha: "you can't choose CA" (você não pode escolher CA). O enunciado preciso é o que Darnell dá: na presença de partições, "a system cannot be both consistent and available" (um sistema não pode ser consistente e disponível ao mesmo tempo). Consistência no CAP significa linearizabilidade, e disponibilidade significa que todo nó que está de pé ainda consegue responder.

- Uma escolha **CP**: um nó que não alcança a maioria recusa requisições (devolve erro ou espera) em vez de arriscar responder com dados desatualizados. Darnell descreve o CockroachDB assim: "in the event of partitions, the system will block rather than return inconsistent data" (em caso de partições, o sistema bloqueia em vez de devolver dados inconsistentes). As escritas precisam da maioria das réplicas; um nó isolado que tem um lease continua atendendo leituras só até o lease expirar.
- Uma escolha **AP**: todo nó continua respondendo com o que tem, e as réplicas se reconciliam depois que a partição se resolve.

O exemplo do MongoDB de terça é o CAP em ação: durante uma partição, escritas `{ w: "majority" }` não conseguem terminar no primário antigo isolado (o comportamento CP), enquanto escritas `{ w: 1 }` são aceitas lá e sofrem rollback depois (o comportamento AP, com o seu preço).

Darnell acrescenta dois pontos práticos. A maioria das quedas não é partição; falhas de hardware, bugs de aplicação e erros de operador causam mais indisponibilidade, e o CAP não diz nada sobre eles. E sistemas CP pagam pela consistência mesmo com a rede funcionando, porque "consistent systems must coordinate between different nodes during writes" (sistemas consistentes precisam coordenar nós diferentes durante as escritas). Esse segundo ponto é o assunto do PACELC.

## 4. PACELC: o trade-off que você paga todo dia

*Fonte principal: documentação do Azure Cosmos DB, "Consistency levels in Azure Cosmos DB".*

O PACELC estende o CAP: **se há uma Partição (P), escolha entre Disponibilidade (A) e Consistência (C); senão (Else, E), escolha entre Latência (L) e Consistência (C).** Partições são raras; o trade-off do "senão" está presente em toda requisição.

A documentação do Cosmos DB é útil aqui porque nomeia o PACELC e depois coloca números nele. Ela começa dizendo que bancos replicados precisam equilibrar consistência, disponibilidade, latência e throughput "as defined by the PACELC theorem" (como definido pelo teorema PACELC), e então:

- Na maioria dos níveis, leituras e escritas ficam abaixo de 10 ms no percentil 99 dentro de uma região.
- Com consistência strong entre regiões, a latência de escrita é "two times round-trip time (RTT) between any of the two farthest regions, plus 10 milliseconds at the 99th percentile" (duas vezes o tempo de ida e volta entre as duas regiões mais distantes, mais 10 milissegundos no percentil 99). Se a ida e volta entre suas duas regiões mais distantes é de 120 ms, isso dá cerca de 250 ms para cada escrita.
- Consistência strong entre regiões a mais de 5.000 milhas de distância é bloqueada por padrão por causa dessa latência.
- Contas que aceitam escritas em várias regiões não podem usar consistência strong.

As global tables do DynamoDB mostram a mesma escolha. Por padrão (multi-Region eventual consistency), as mudanças chegam às outras regiões "typically within a second" (normalmente em até um segundo). Com multi-Region strong consistency, uma escrita é replicada para outra região "before the write returns" (antes de a escrita retornar), então leituras fortes em qualquer lugar a enxergam, e toda escrita paga pela viagem.

A mentalidade útil para uma fintech: você não escolhe um modelo para a empresa, escolhe um por operação. Tanto o DynamoDB quanto o Cosmos DB deixam você escolher por requisição, e é assim que você deveria pensar também nas leituras do seu Postgres (primário ou réplica).

## 5. Consistência eventual e o que fica no meio

*Fontes principais: documentação do Azure Cosmos DB, "Consistency levels in Azure Cosmos DB", e documentação do Redis, "Active-Active geo-distributed Redis".*

Na outra ponta está a **consistência eventual**: se as escritas param, as réplicas convergem, mas enquanto isso você pode ler dados desatualizados. A documentação do Cosmos DB vai além e avisa que um cliente "might read values older than those values it read in the past" (pode ler valores mais antigos do que os que já leu antes), e a sugere para coisas como contagens de curtidas e comentários, em que nenhuma ordem é necessária. O guia do DynamoDB diz o mesmo das suas leituras padrão: elas "might not reflect the results of a recently completed write" (podem não refletir o resultado de uma escrita recém-concluída), e uma repetição pouco depois "should eventually" (deve, em algum momento) devolvê-lo.

O Cosmos DB é um bom mapa do espaço intermediário porque oferece cinco níveis com nome, do mais forte ao mais fraco:

| Nível | O que é prometido ao leitor |
| --- | --- |
| Strong | Linearizabilidade |
| Bounded staleness | O atraso fica abaixo de K versões ou T de tempo, o que vier primeiro |
| Session | Read your writes e writes follow reads, dentro de uma sessão (terça) |
| Consistent prefix | As escritas de uma transação aparecem juntas, nunca pela metade |
| Eventual | Convergência, em algum momento; leituras podem até voltar no tempo |

**Bounded staleness** é uma ideia útil para dashboards: "no máximo 5 segundos de atraso" é uma promessa que você pode mostrar aos usuários.

Uma prima mais forte da consistência eventual é a **strong eventual consistency**: réplicas que receberam as mesmas atualizações estão no mesmo estado, seja qual for a ordem em que as atualizações chegaram, sem esperar coordenação. Os bancos Active-Active do Redis funcionam assim. A documentação do Redis diz que eles usam só conflict-free replicated data types (CRDTs), que dão "predictable conflict resolution" (resolução de conflitos previsível) sem trabalho extra da aplicação, e aceitam escritas em todas as regiões com latência local abaixo de um milissegundo. O Cassandra também usa um CRDT: sua regra de last write wins por linha é um. O problema para dinheiro está em como os conflitos são resolvidos: um contador de curtidas pode juntar incrementos concorrentes, mas dois débitos juntados depois do fato podem deixar uma conta negativa, porque a verificação de saldo nunca foi coordenada.

## 6. Escolher um modelo por operação da carteira digital

Junte tudo perguntando, para cada operação: qual o dano de uma leitura desatualizada ou fora de ordem, e qual o custo da coordenação?

| Operação | Modelo que ela precisa | Por quê |
| --- | --- | --- |
| Débito com verificação de saldo | Linearizável (líder único, dentro de uma transação) | Um saldo desatualizado permite saldo negativo ou gasto duplo |
| Verificação de idempotency key | Linearizável na chave (primary key ou unique constraint, nunca uma réplica de índice secundário) | Duas réplicas dizendo "chave nova" significa cobrança dupla |
| Extrato logo após a transferência do próprio usuário | Read your writes (session token, verificação de LSN ou primário) | O usuário precisa ver o que acabou de fazer |
| Extrato enquanto rola a tela | Monotonic reads | Lançamentos não podem sumir ao atualizar |
| Gráfico mensal de gastos | Eventual, ou bounded staleness | Segundos de atraso não prejudicam ninguém |
| Saldo mostrado na tela inicial | Read your writes, com um horário de "atualizado em" | Rápido, mas precisa refletir as ações do próprio usuário |
| Contador de velocidade para fraude | Eventual ou strong eventual, com margem de segurança | Bloquear todo pagamento por coordenação custa mais que uma contagem levemente desatualizada |
| Taxa de câmbio usada para precificar uma transferência | Leitura linearizável de uma taxa versionada, gravada no lançamento | O cliente precisa ser cobrado pela taxa que lhe foi cotada |

Sua tabela pode ser diferente, e tudo bem, desde que cada linha tenha uma justificativa de uma linha. Esse é o entregável do `docs/m01.md` desta semana.

## O que anotar hoje

1. A partition key de uma carteira digital, e quais contas ficam quentes.
2. A diferença entre linearizabilidade e consistência eventual, em uma frase cada, e quanto o DynamoDB e o Cosmos DB cobram pela mais forte.
3. O CAP enunciado corretamente, e o que o PACELC acrescenta, com os números de latência do Cosmos DB como exemplo.
4. Um primeiro rascunho da tabela de 8 operações.

## Teste-se

- Por que uma data é uma partition key ruim, segundo o guia do DynamoDB?
- O que é write sharding, e quanto custa nas leituras? O que um sufixo calculado melhora?
- Defina linearizabilidade sem usar a palavra "consistente".
- Por que uma verificação de idempotência por um global secondary index do DynamoDB não é segura?
- Durante uma partição de rede, o que um nó CP faz com uma requisição? E um nó AP?
- O que o "ELC" do PACELC descreve, e quanto ele custa no Cosmos DB com consistência strong entre regiões?
- O que a strong eventual consistency acrescenta à consistência eventual, e por que ela não torna segura uma verificação de saldo?

## Referências

- **Fonte principal para particionamento:** Amazon DynamoDB Developer Guide, ["Best practices for designing and using partition keys effectively"](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/bp-partition-key-design.html), e suas subpáginas ["Designing partition keys to distribute your workload in DynamoDB"](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/bp-partition-key-uniform-load.html) e ["Using write sharding to distribute workloads evenly"](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/bp-partition-key-sharding.html). Gratuito.
- **Fonte principal para consistência:** Microsoft, documentação do Azure Cosmos DB, ["Consistency levels in Azure Cosmos DB"](https://learn.microsoft.com/azure/cosmos-db/consistency-levels). Gratuito. Os cinco níveis, PACELC, latência, throughput e RPO.
- Amazon DynamoDB Developer Guide, ["DynamoDB read consistency"](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/HowItWorks.ReadConsistency.html). Gratuito. Leituras eventualmente consistentes vs. fortemente consistentes, e o que não pode ser lido de forma forte.
- Ben Darnell, blog da Cockroach Labs, ["Limits of the CAP theorem"](https://www.cockroachlabs.com/blog/limits-of-the-cap-theorem/). Gratuito. O CAP enunciado corretamente, pelos criadores de um banco CP.
- Documentação do Apache Cassandra, ["Dynamo"](https://cassandra.apache.org/doc/latest/cassandra/architecture/dynamo.html), seções sobre consistent hashing e virtual nodes. Gratuito.
- Documentação do Redis, ["Active-Active geo-distributed Redis"](https://redis.io/docs/latest/operate/rs/databases/active-active/). Gratuito. Strong eventual consistency com CRDTs em um produto real.
- Jeff Hodges, ["Notes on Distributed Systems for Young Bloods"](https://www.somethingsimilar.com/2013/01/14/notes-on-distributed-systems-for-young-bloods/), 2013, seção "Use the CAP theorem to critique systems". Gratuito.
