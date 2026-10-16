# Módulo 1, quarta-feira: particionamento, modelos de consistência e trade-offs

[Módulo 1](../../modules/01-distributed-systems-fundamentals.pt-BR.md) · [Read in English](day-3.md)

**Tempo de leitura:** cerca de 45 minutos. Use o resto do bloco de 2 horas nas referências do final e depois rascunhe a tabela de consistência descrita no final.

Este é um texto original escrito para este curso. Ele se baseia nas referências listadas no final, e cada seção indica a fonte que segue.

## Por que isso importa para uma fintech

Duas perguntas definem boa parte da arquitetura de um sistema de pagamentos. Primeira: como dividir os dados quando uma máquina não dá mais conta? Segunda: para cada operação, quão atualizados e quão acordados entre as réplicas os dados precisam estar? Uma verificação de saldo antes de um débito e um gráfico mensal de gastos precisam de respostas muito diferentes. Hoje você ganha o vocabulário para responder às duas, e termina escrevendo essas respostas para 8 operações da carteira digital.

## 1. Particionamento: dividir os dados entre máquinas

*Fonte principal: Amazon DynamoDB Developer Guide, "Best practices for designing and using partition keys effectively".*

A replicação (terça-feira) copia os mesmos dados para vários nós. O **particionamento**, também chamado de sharding, divide dados diferentes entre os nós, de modo que cada um guarda só uma parte. Sistemas reais fazem as duas coisas: cada partição é replicada.

Todo registro tem uma **chave de partição**, que o sistema usa para decidir qual partição guarda o registro. Há duas formas clássicas de mapear chaves para partições.

- **Por intervalo de chaves.** A partição 1 guarda as chaves de A a F, a partição 2 guarda de G a M, e assim por diante. Varreduras por intervalo são baratas ("todas as transações da conta 42 em março"). Mas se a chave for um timestamp, todas as escritas de hoje caem na mesma partição.
- **Por hash da chave.** O sistema calcula o hash da chave e atribui faixas de valores de hash às partições. A carga se espalha de forma uniforme, mas você perde as varreduras baratas por intervalo entre chaves; só dá para varrer com eficiência dentro de uma chave.

O DynamoDB, como muitos stores, calcula o hash da chave de partição e pode manter registros com a mesma chave ordenados por uma segunda chave (a *sort key*). O principal conselho do guia do DynamoDB é que a chave de partição tenha **muitos valores distintos, acessados de forma razoavelmente uniforme**. Cada partição do DynamoDB atende no máximo cerca de 3.000 unidades de leitura e 1.000 unidades de escrita por segundo. Quando poucas chaves recebem a maior parte do tráfego, as partições que as guardam viram **hot partitions**: batem nesse limite e as requisições sofrem throttling, mesmo com a tabela como um todo tendo capacidade sobrando. A capacidade adaptativa do DynamoDB absorve parte do desequilíbrio, mas o guia ainda manda projetar para acesso uniforme em vez de depender dela.

O remédio do guia para uma chave que é quente por natureza é o **write sharding**: adicione um sufixo à chave (por exemplo `merchant#123#7`, um número aleatório ou calculado de 0 a N−1) para que suas escritas se espalhem por N partições, e combine as N partes na leitura.

Para uma carteira digital, a chave de partição natural é o **ID da conta**. Os lançamentos de cada conta ficam juntos, então um extrato é uma consulta em uma única partição, e uma transferência entre duas contas na mesma partição pode ser atômica. O ponto quente é a conta com tráfego enorme, como um grande lojista recebendo milhares de pagamentos por segundo, ou a conta de tarifas que toda transferência credita. O Módulo 6 trata dessas contas quentes.

Quando nós são adicionados ou removidos, partições precisam migrar entre eles. Isso é o **rebalanceamento**. Uma abordagem comum é criar, desde o início, muito mais partições do que nós e mover partições inteiras, para que uma chave nunca precise trocar de partição.

## 2. Linearizabilidade: comportar-se como uma cópia única

*Fonte principal: notas de aula de Kleppmann, seção 7.2.*

Replicação e particionamento dão a você muitas cópias e muitos lugares. Um modelo de consistência diz o que os leitores podem ver apesar disso.

O modelo comum mais forte é a **linearizabilidade**. Um sistema é linearizável se ele se comporta como se houvesse **uma única cópia dos dados e cada operação tivesse efeito atomicamente em algum instante entre seu início e seu fim**. Na prática:

- Depois que uma escrita termina, toda leitura que começa em seguida a vê (ou vê uma escrita posterior), não importa de qual réplica ela leia.
- Depois que algum leitor viu um valor novo, nenhum leitor posterior vê o antigo.

A linearizabilidade é o que você assume implicitamente quando escreve `if balance >= amount then debit`. Se o saldo lido puder estar velho, dois débitos concorrentes podem passar ambos pela verificação. As notas de Kleppmann mostram como obter leituras e escritas linearizáveis em cima de quorums (o algoritmo ABD, em que o leitor escreve de volta o valor mais novo que viu antes de retornar). A seção 6 mostra como o consenso garante isso para operações mais complexas.

O custo é coordenação. Toda operação linearizável precisa alcançar uma maioria, ou um líder único, que conheça o estado mais recente. Isso adiciona latência, e **se uma partição de rede isolar um nó da maioria, esse nó não consegue atender nenhuma operação linearizável**.

## 3. CAP, enunciado com cuidado

*Fonte principal: notas de aula de Kleppmann, seção 7.2.*

O teorema CAP costuma ser resumido como "escolha dois entre consistência, disponibilidade e tolerância a partições", o que é enganoso. Partições de rede não são algo que você escolhe; elas acontecem. O enunciado preciso é: **quando há uma partição de rede, um sistema precisa escolher entre linearizabilidade (C) e disponibilidade (A)**, em que disponibilidade significa que todo nó que está no ar ainda consegue responder.

- Uma escolha **CP**: um nó que não alcança a maioria recusa requisições (retorna um erro ou espera) em vez de arriscar responder com dados velhos.
- Uma escolha **AP**: todo nó continua respondendo com o que tem, e as réplicas se reconciliam depois que a partição se resolve.

O CAP não diz nada sobre o que acontece quando a rede está bem, e isso é a maior parte do tempo. É essa lacuna que o PACELC preenche.

## 4. PACELC: o trade-off que você paga todo dia

*Fonte principal: Daniel Abadi, "Consistency Tradeoffs in Modern Distributed Database System Design", IEEE Computer, 2012.*

O argumento de Abadi é que o CAP recebe atenção demais porque partições são raras, enquanto um trade-off diferente está presente em toda requisição. Ele o formulou como PACELC: **se houver uma Partição (P), escolha entre Disponibilidade (A) e Consistência (C); senão (E, de "Else"), escolha entre Latência (L) e Consistência (C).**

A parte do "senão" existe porque manter réplicas consistentes exige esperar por elas. Uma réplica síncrona (terça-feira) adiciona uma ida e volta a cada commit; ler do líder em vez de uma réplica próxima adiciona distância. Sistemas que replicam dados de qualquer forma escolhem, o tempo todo, entre responder rápido e responder com dados acordados entre as réplicas.

Na classificação de Abadi, sistemas como Dynamo e Cassandra na configuração padrão são **PA/EL** (favorecem disponibilidade durante partições e latência no resto do tempo). Já sistemas totalmente consistentes, como VoltDB, Megastore, BigTable e HBase, são **PC/EC**. Muitos sistemas são configuráveis por operação, e essa é a mentalidade útil para uma fintech: você não escolhe um modelo para a empresa, escolhe um por operação.

## 5. Consistência eventual e sua prima mais forte

*Fonte principal: notas de aula de Kleppmann, seção 7.3.*

Na outra ponta do espectro está a **consistência eventual**: se não chegarem novas escritas, todas as réplicas acabam convergindo para o mesmo valor. Ela não promete nada sobre o que você lê nesse meio-tempo, e não diz nada sobre quanto tempo leva esse "acabam".

As notas de Kleppmann descrevem uma variante mais útil, a **consistência eventual forte**: duas réplicas quaisquer que receberam o mesmo conjunto de atualizações estão no mesmo estado, independentemente da ordem em que as receberam, e não é preciso esperar a convergência para ler. Tipos de dados projetados para que atualizações concorrentes se combinem de forma determinística (CRDTs, como contadores que só somam) conseguem isso sem coordenação.

Entre a linearizabilidade e a consistência eventual ficam as garantias de sessão de terça-feira (read your writes, monotonic reads) e a consistência causal. Esta preserva a ordem de causa e efeito (o happens-before de segunda-feira), mas permite que escritas concorrentes sejam vistas em ordens diferentes.

## 6. Escolher um modelo por operação da carteira digital

Junte tudo perguntando, para cada operação: qual é o dano de uma leitura velha ou fora de ordem, e qual é o custo da coordenação?

| Operação | Modelo necessário | Por quê |
| --- | --- | --- |
| Débito com verificação de saldo | Linearizável (líder único, dentro de uma transação) | Um saldo velho permite saldo negativo ou gasto duplo |
| Verificação da chave de idempotência | Linearizável na chave | Duas réplicas dizendo "chave nova" significa cobrança em dobro |
| Extrato logo após a transferência do próprio usuário | Read your writes | O usuário precisa ver o que acabou de fazer |
| Extrato durante a rolagem | Monotonic reads | Lançamentos não podem sumir ao recarregar |
| Gráfico mensal de gastos | Eventual | Segundos de atraso não prejudicam ninguém |
| Saldo exibido na tela inicial | Read your writes, com horário de "última atualização" | Rápido, mas precisa refletir as ações do próprio usuário |
| Contador de velocidade para fraude | Eventual ou eventual forte, com margem de segurança | Bloquear todo pagamento esperando coordenação custa mais do que uma contagem um pouco velha |
| Taxa de câmbio usada para precificar uma transferência | Leitura linearizável de uma taxa versionada, gravada no lançamento | O cliente precisa ser cobrado pela taxa que foi cotada para ele |

Sua tabela pode ser diferente, e tudo bem, desde que cada linha tenha uma justificativa de uma linha. Esse é o entregável do `docs/m01.md` desta semana.

## O que anotar hoje

1. A chave de partição de uma carteira digital, e quais contas ficam quentes.
2. A diferença entre linearizabilidade e consistência eventual, em uma frase para cada uma.
3. O CAP enunciado corretamente, e o que o PACELC acrescenta.
4. Um primeiro rascunho da tabela das 8 operações.

## Teste-se

- Por que um timestamp é uma má chave de partição em um store particionado por intervalo?
- O que é write sharding, e quanto ele custa nas leituras?
- Defina linearizabilidade sem usar a palavra "consistente".
- Durante uma partição de rede, o que um nó CP faz com uma requisição? E um nó AP?
- O que o "ELC" do PACELC descreve?
- O que a consistência eventual forte acrescenta à consistência eventual?

## Referências

- **Fonte principal para particionamento:** Amazon DynamoDB Developer Guide, ["Best practices for designing and using partition keys effectively"](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/bp-partition-key-design.html), e sua subpágina ["Using write sharding to distribute workloads evenly"](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/bp-partition-key-sharding.html). Gratuito.
- **Fonte principal para consistência:** Martin Kleppmann, [notas de aula "Distributed Systems"](https://www.cl.cam.ac.uk/teaching/2122/ConcDisSys/dist-sys-notes.pdf), Universidade de Cambridge, seções 7.2 (Linearizability) e 7.3 (Eventual consistency). Gratuito, Creative Commons BY-SA.
- Daniel Abadi, ["Consistency Tradeoffs in Modern Distributed Database System Design"](https://www.cs.umd.edu/~abadi/papers/abadi-pacelc.pdf), IEEE Computer, 2012. PDF gratuito no site do autor.
