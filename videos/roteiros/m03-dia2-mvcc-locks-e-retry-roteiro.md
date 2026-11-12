# Roteiro · M3 · Dia 2 · MVCC, locks e retry


## Abertura

Esta é a aula em vídeo do módulo três, dia dois: MVCC, locks e o retry do quatro zero zero zero um.

Ontem você viu qual anomalia cada nível permite. Hoje, as ferramentas para impedi-las. São três famílias: um nível mais forte com retry, travar linhas explicitamente, ou escrever a verificação dentro do próprio UPDATE. Você precisa saber como cada uma se comporta sob concorrência, qual erro lança, e o que seu código faz com ele.


## MVCC

O Postgres não protege leituras com locks. Ele guarda várias versões de cada linha e mostra a cada comando um snapshot, o banco como estava em algum momento. Isso é o MVCC.

A grande vantagem: ler nunca bloqueia escrever, e escrever nunca bloqueia ler.

Numa carteira, uma consulta longa de extrato nunca bloqueia uma transferência. Mas duas transações podem olhar o mesmo saldo e ver valores diferentes.

E todo nível de isolamento é só uma regra sobre duas coisas: quando o snapshot é tirado, e o que acontece quando duas transações escrevem a mesma linha.


## Read committed

Read committed é o padrão, e cada SELECT vê um snapshot novo, do instante em que começa. A parte importante é o que acontece quando um UPDATE encontra uma linha que outra transação está alterando.

Primeiro, ele espera a outra transação terminar.

Se ela fez commit, ele pega a versão nova da linha.

E reavalia a cláusula WHERE contra essa versão nova, aplicando só se a linha ainda atende.

Por isso, um débito num único comando, saldo igual a saldo menos trinta, não perde atualização. A segunda transação espera e subtrai do saldo que a primeira deixou. O lost update de ontem precisava que o valor passasse pela memória da aplicação.


## O update condicional

Essa regra dá a versão três do TCM: o update condicional. O débito só acontece onde o saldo é maior ou igual ao valor.

Se dois débitos disputam os últimos cem, o segundo espera, reavalia a condição contra o saldo novo, e não atinge nenhuma linha.

Seu código precisa ler o número de linhas afetadas e transformar zero num erro de negócio.

Mas atenção ao limite. A documentação diz que read committed não serve para condições de busca complexas, e é perfeito para casos simples. O saldo de uma linha é simples. Uma verificação que soma várias linhas, não.

> **Pausa:** Pergunta: em read committed, o que um UPDATE faz quando a linha que ele mira acabou de ser alterada por outra transação com commit?

Espera, pega a versão nova da linha, reavalia o WHERE contra ela, e só aplica se a condição ainda for verdadeira.


## Repeatable read

Em repeatable read, o snapshot é tirado no primeiro comando e mantido até o fim. Todas as leituras concordam entre si, que é o que um extrato ou uma conciliação precisam.

Quando a transação tenta atualizar uma linha que outra alterou depois do snapshot, o Postgres não reavalia. Ele aborta com could not serialize access due to concurrent update. É assim que este nível impede lost update.

Consequência: a aplicação precisa estar pronta para refazer transações. Transações somente leitura nunca recebem esse erro.

E é snapshot isolation. Na carteira conjunta, Carla e Diego atualizam cada um uma linha diferente, nenhum recebe erro, e o saldo somado fica negativo. É o lab de hoje.


## Serializable e o retry

Serializable funciona igual ao repeatable read, mas também monitora condições que produziriam um resultado impossível em ordem serial. É o SSI de ontem.

Para rastrear o que cada transação leu, ele usa predicate locks. Eles nunca bloqueiam ninguém e nunca causam deadlock. São só contabilidade.

Toda falha de serialização tem o SQLSTATE quatro zero zero zero um, seja qual for a mensagem. Faça retry sem condição. Deadlock, quatro zero P zero um, também pode valer um retry.

Violação de unicidade só às vezes, porque pode ser um erro persistente.

E o ponto principal: repita a transação inteira, incluindo a lógica que decide qual SQL emitir e com quais valores. Por isso o Postgres não faz retry sozinho: ele não consegue reexecutar o seu TypeScript. Limite o número de tentativas.


## O wrapper de retry

Num serviço NestJS, o wrapper fica assim. Abre a transação serializable, roda o trabalho, que relê os saldos a cada tentativa, e faz commit. Se der quatro zero zero zero um ou deadlock, rollback, uma pequena espera aleatória, e tenta de novo, até o limite.

Repare que o erro pode chegar num UPDATE ou no próprio COMMIT, e o catch cobre os dois.

E uma regra sutil: dados lidos numa transação serializable só valem depois do commit. Não mande uma push notification com um saldo lido no meio do caminho.

> **Pausa:** Pergunta: qual SQLSTATE marca uma falha de serialização, e o que exatamente você repete no retry?

Quatro zero zero zero um. Você repete a transação inteira, incluindo as leituras e a lógica que decide o que gravar.


## Locks de linha

A outra família é pessimista: trave as linhas primeiro, depois leia e escreva. SELECT FOR UPDATE trava as linhas retornadas, e quem tentar alterá-las espera você terminar.

São quatro modos. FOR UPDATE, quando você vai alterar a linha. Bloqueia todos os outros.

FOR NO KEY UPDATE é pego automaticamente por um UPDATE comum.

FOR SHARE garante que a linha não muda enquanto você lê. E FOR KEY SHARE é pego por verificações de chave estrangeira.

A versão um do TCM trava as duas carteiras da transferência, em ordem de id, antes de mexer nelas. Rode em read committed, porque em níveis mais altos travar uma linha alterada desde o início da transação lança erro.


## NOWAIT e SKIP LOCKED

Duas opções evitam esperar. NOWAIT reporta erro na hora se a linha já está travada. Útil quando esperar estouraria seu orçamento de latência.

SKIP LOCKED pula as linhas travadas. Isso dá uma visão inconsistente dos dados, então não serve para trabalho geral. Mas encaixa perfeitamente numa tabela que funciona como fila: vários workers do outbox, no módulo quatro, pegam cada um o próximo lote sem pisar no outro. Nunca use para saldos.

> **Pausa:** Pergunta: para que serve SKIP LOCKED, e por que não para saldos?

Para vários consumidores de uma tabela tipo fila pegarem linhas diferentes sem esperar. Não serve para saldos porque pula linhas, e você decidiria com uma visão incompleta.


## Deadlocks

O exemplo de deadlock da documentação é uma transferência. Numa carteira, acontece quando Ana paga Bruno enquanto Bruno paga Ana, e cada transferência trava origem primeiro.

T um trava Ana. T dois trava Bruno.

T um espera Bruno. T dois espera Ana. Cada uma espera a outra para sempre. O Postgres detecta o ciclo e aborta uma delas com quatro zero P zero um, e qual delas é imprevisível.

A cura: todas as transações pegam os locks na mesma ordem. Para transferências, a ordem é o id da carteira. Sempre trave primeiro o menor id, seja ele a origem ou o destino. E pegue logo o lock mais forte que vai precisar. Nunca mantenha uma transação aberta chamando o banco parceiro ou esperando um usuário.

> **Pausa:** Pergunta: como você evita deadlock entre duas transferências opostas?

Travando as carteiras sempre na mesma ordem, menor id primeiro, independente de quem é origem ou destino.


## Advisory locks

Advisory locks travam um número que você escolhe, não uma linha. São advisory porque o sistema não obriga ninguém a usá-los.

Prefira as versões de nível de transação: o lock é solto no fim da transação, inclusive no rollback.

As de nível de sessão ignoram rollback. Atrás de um pool de conexões, um lock esquecido fica preso numa conexão e bloqueia a próxima requisição que a usar.

Um bom uso: garantir que só uma instância do job diário de conciliação rode. Um uso ruim: proteger saldos, porque qualquer caminho de código que esqueça a chamada fica desprotegido.


## Três formas de impedir saldo negativo

Para fechar, as formas de impedir saldo negativo que você constrói na quinta.

Versão um, pessimista: FOR UPDATE nas duas carteiras, em ordem de id. As transferências fazem fila atrás do lock.

Versão dois, otimista: você lê uma coluna version e só atualiza se ela não mudou. Ninguém espera, mas conflitos causam retries. Não é recurso do Postgres, é um padrão.

Versão três, condicional: a verificação dentro do UPDATE, conferindo o número de linhas.

E a quarta: tudo em serializable com o loop de retry. É a única que também protege regras que abrangem várias linhas, como a carteira conjunta. Na sexta você mede o desempenho de cada uma.


## Revisão relâmpago

Hora da revisão relâmpago. São três perguntas, sem olhar.

> **Pausa:** Pergunta um: por que o repeatable read não impede o write skew da carteira conjunta?

Porque Carla e Diego gravam linhas diferentes. Não há conflito de escrita para o Postgres abortar.

> **Pausa:** Pergunta dois: por que o advisory lock de nível de transação é mais seguro atrás de um pool?

Porque ele é solto no fim da transação. O de sessão sobrevive ao rollback e pode ficar preso numa conexão do pool.

> **Pausa:** Pergunta três: no update condicional, o que significa zero linhas afetadas?

Saldo insuficiente, ou carteira inexistente. Seu código transforma isso num erro de negócio.


## O que anotar e próximo passo

Anote com as suas palavras: cada nível com seu snapshot, conflito e erro. Sua política de retry. Quando usar FOR UPDATE, NOWAIT, SKIP LOCKED e advisory locks. O deadlock desenhado em duas colunas. E o resultado do lab.

Agora faça o lab da carteira conjunta: write skew em repeatable read e o erro em serializable. Até a próxima aula.
