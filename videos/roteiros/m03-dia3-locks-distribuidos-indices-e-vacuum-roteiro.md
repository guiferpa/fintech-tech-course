# Roteiro · M3 · Dia 3 · Locks distribuídos, índices e vacuum


## Abertura

Esta é a aula em vídeo do módulo três, dia três: locks distribuídos, índices e vacuum.

Cedo ou tarde alguém propõe: trava a carteira no Redis e depois faz a transferência. Parece mais simples que níveis de isolamento. Hoje você vê por que um lock fora do banco nunca pode ser a garantia final para dinheiro. E depois, as mesmas tabelas sob carga real: o índice do extrato, como ler um plano de execução, e por que o vacuum existe.


## Para que serve o lock?

Martin Kleppmann começa perguntando: para que serve esse lock? Ele separa dois casos.

Eficiência: o lock evita que dois workers façam o mesmo trabalho. Se falhar, o custo é pequeno, um relatório gerado duas vezes. Para isso, um único nó Redis basta, sem a complexidade do Redlock.

Corretude: o lock evita que dois processos escrevam juntos e corrompam dados. Se falhar, os dados ficam errados. Duas transferências debitando a mesma carteira. Para esse caso, a resposta dele é que o lock sozinho nunca basta, seja qual for o serviço.


## O lock no Redis

O lock Redis mais comum usa SET com NX, que só grava se a chave não existe, e PX, que expira depois de alguns milissegundos. Para liberar, um script que apaga a chave só se o valor ainda for o seu.

A expiração existe porque um cliente pode cair segurando o lock, e ninguém nunca o liberaria.

O Redlock é a versão com vários nós: pega o lock na maioria de nós independentes.

A principal crítica de Kleppmann é sobre tempo. A segurança depende de atraso de rede, pausas de processo e erro de relógio limitados. Ou seja, um sistema síncrono. E o módulo um mostrou que sistemas reais não são: relógios pulam e processos pausam.


## O cliente pausado

O exemplo central de Kleppmann vale para qualquer serviço de lock. Traduzido para a carteira, são quatro passos.

O worker um pega o lock da carteira quarenta e dois, com lease de dez segundos.

Ele sofre uma pausa longa de garbage collection, ou o container é estrangulado.

O lease expira. O worker dois pega o lock, debita a carteira e termina.

O worker um acorda. Do ponto de vista dele, ainda tem o lock. E grava o saldo que calculou antes da pausa.

O débito do worker dois se perde. E não adianta checar o lease logo antes de escrever: a pausa pode acontecer entre a checagem e a escrita. O veredito de Kleppmann: o padrão ingênuo é fundamentalmente inseguro, seja qual for o serviço de lock.

> **Pausa:** Pergunta: por que verificar o lease logo antes de escrever não torna o lock seguro?

Porque a pausa, ou um pacote atrasado, pode acontecer depois da verificação e antes da escrita. O cliente escreve achando que ainda tem o lock.


## Fencing tokens

A solução de Kleppmann é o fencing token: um número que cresce toda vez que alguém pega o lock. O ponto crucial é quem verifica: o próprio storage. Para a carteira, o storage é o Postgres.

O cliente um recebe o token trinta e três e pausa. O cliente dois recebe trinta e quatro e escreve.

Quando o cliente um finalmente escreve com trinta e três, o banco rejeita, porque já viu o trinta e quatro.

Mas repare: a cláusula WHERE sozinha já impede o saldo negativo.

Essa é a lição para entrevistas. A garantia final para dinheiro fica no banco de dados: num update condicional, num lock de linha, numa transação serializable ou numa constraint. Um lock no Redis na frente pode reduzir contenção, que é eficiência. Nunca é o que mantém o saldo correto.

> **Pausa:** Pergunta: o que é um fencing token, e quem precisa verificá-lo?

Um número que cresce a cada aquisição do lock. Quem verifica é o storage, que rejeita escritas com token menor que o último que viu.


## O índice do extrato

O extrato é a leitura mais frequente: os cinquenta lançamentos mais recentes de uma conta. Sem índice, o Postgres lê todos os lançamentos, filtra, ordena e devolve cinquenta. E a tabela cresce para sempre.

A regra para índices multicoluna: colunas com igualdade primeiro, e depois a coluna de ordenação ou intervalo. Então: account ID, depois created at.

E como só índices B-tree entregam saída ordenada, e podem ser percorridos de trás para frente, o Postgres pega as primeiras cinquenta linhas direto, sem ordenar nada. A próxima página usa o mesmo índice, com created at menor que o cursor. Em produção, acrescente o id como desempate.

Mas use com moderação. Todo índice deixa cada insert no ledger mais lento. Crie os que suas consultas precisam, não todas as combinações.

> **Pausa:** Pergunta: qual índice atende o extrato, e por que essa ordem de colunas?

Account ID e created at, nessa ordem. Igualdade na primeira coluna, e a segunda já entrega as linhas ordenadas, então o LIMIT para cedo.


## Índices parciais

Índices parciais indexam só as linhas que atendem a um predicado. Na carteira: as transferências que um worker consulta periodicamente, as pendentes e desconhecidas.

As concluídas se acumulam para sempre, mas esse índice continua pequeno.

E um índice único parcial garante unicidade só entre essas linhas. Por exemplo, no máximo um hold ativo por autorização de cartão.

A documentação avisa: criar um índice parcial por categoria como substituto de particionamento é má ideia.


## Lendo um plano

EXPLAIN mostra o plano: uma árvore de nós, com scans embaixo e ordenações e limites acima. Cada nó traz custo inicial, custo total, linhas estimadas e largura. Os custos são unidades arbitrárias, servem para comparar planos, não são milissegundos.

Antes do índice, você vê um Seq Scan com muitas linhas removidas pelo filtro, e um nó Sort em cima. O Postgres leu muito para ficar com pouco.

Depois do índice, aparece um Index Scan Backward, e o Sort some. O índice entrega as linhas já em ordem, e o Limit para em cinquenta.

Leia nesta ordem: o nó de scan, o Sort, linhas estimadas contra reais, onde uma diferença grande indica estatísticas velhas, e os buffers, a medida mais honesta. EXPLAIN ANALYZE executa a consulta de verdade e mostra tempos reais. Os efeitos colaterais acontecem, então envolva escritas em BEGIN e ROLLBACK.

> **Pausa:** Pergunta: o que EXPLAIN ANALYZE faz que EXPLAIN não faz, e qual o risco?

Executa a consulta e mostra tempos e linhas reais. O risco é que os efeitos colaterais acontecem; por isso, escritas vão dentro de uma transação com rollback.


## Por que o vacuum existe

Terça você viu que todo comando lê um snapshot. O custo é armazenamento. No Postgres, um UPDATE ou DELETE não remove a versão antiga da linha na hora. Ela fica enquanto alguma transação puder vê-la. Depois vira uma versão morta.

Uma carteira está perto do pior caso. A linha de saldo de um lojista popular é atualizada milhares de vezes por dia, e cada update deixa uma versão morta.

O vacuum recupera esse espaço. E também atualiza as estatísticas do planner e o visibility map, que acelera index-only scans.

O quarto motivo é o perigoso. IDs de transação são um contador de trinta e dois bits. Se uma tabela fica tempo demais sem vacuum, o contador dá a volta, e transações antigas parecem estar no futuro. A documentação chama de perda de dados catastrófica. O autovacuum cuida disso por você.

Seu trabalho é não atrapalhar. Uma sessão deixada idle in transaction por horas impede a limpeza do banco inteiro. Transações curtas reduzem espera por lock e deixam o vacuum trabalhar.

> **Pausa:** Pergunta: por que um UPDATE no Postgres deixa uma linha morta para trás?

Por causa do MVCC: a versão antiga precisa existir enquanto alguma transação puder vê-la no seu snapshot. Depois, só o vacuum a remove.


## Preparando o TCM

O lab de hoje é só preparação. Três coisas para ter prontas na quinta.

Dados de seed: mil carteiras com saldos conhecidos, por um script que você pode rodar de novo. Anote o total esperado: o total nunca muda é uma das suas asserções.

O esqueleto do script de carga: cem transferências em paralelo sobre um pool de várias conexões. Uma única conexão serializa tudo e esconde todos os bugs.

E a lista de testes, escritos como frases antes do código. Nenhuma carteira negativa. A soma de todos os saldos igual ao seed. Transferências opostas sem deadlock na versão um. E o extrato usando o índice.


## Revisão relâmpago

Hora da revisão relâmpago. São três perguntas, sem olhar.

> **Pausa:** Pergunta um: qual a diferença entre um lock para eficiência e um para corretude?

No de eficiência, falhar custa pouco, como um trabalho duplicado. No de corretude, falhar corrompe dados, e o lock sozinho nunca basta.

> **Pausa:** Pergunta dois: o que é o transaction ID wraparound, e o que o impede?

O contador de IDs de transação, de trinta e dois bits, dá a volta, e transações antigas parecem futuras. O vacuum, rodando a tempo, impede.

> **Pausa:** Pergunta três: onde fica a garantia final de que um saldo está correto?

No banco de dados: num update condicional, num lock de linha, numa transação serializable ou numa constraint.


## O que anotar e próximo passo

Anote com as suas palavras: os dois motivos para um lock, o cliente pausado e o fencing token. O índice do extrato e a regra das colunas. Como ler um plano. O vacuum e seus motivos. E a preparação do TCM.

A fonte principal é o artigo de Kleppmann sobre locks distribuídos. Vale ler inteiro. Até a próxima aula.
