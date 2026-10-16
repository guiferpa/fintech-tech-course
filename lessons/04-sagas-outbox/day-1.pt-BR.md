# Módulo 4, segunda-feira: two-phase commit e por que sagas existem

[Módulo 4](../../modules/04-sagas-outbox.pt-BR.md) · [Read in English](day-1.md)

**Tempo de leitura:** cerca de 45 minutos. Use o resto do bloco de 2 horas nas referências do final, começando pelas seções marcadas como fonte principal.

Este é um texto original escrito para este curso. Ele se baseia nas referências listadas no final, e cada seção indica a fonte que segue. Quando uma ideia vem de um autor específico, o texto diz isso.

## Por que isso importa para uma fintech

Até agora, sua carteira digital guardava todos os saldos em um único banco Postgres. Uma transferência da Ana para o Bruno era um único `BEGIN ... COMMIT`, e o Postgres garantia que os dois lançamentos fossem gravados, ou nenhum. Nesta semana você divide a carteira em dois serviços, `accounts` e `payments`, cada um com seu próprio banco. A transação única deixa de existir.

A pergunta que todo entrevistador de fintech faz em seguida é: "Como você move dinheiro entre dois serviços sem perder nem criar dinheiro?" Há duas famílias de respostas. Uma tenta manter uma única transação atômica entre máquinas (two-phase commit). A outra aceita uma sequência de transações locais e corrige falhas com compensações (a saga). Esta aula explica as duas e por que sistemas de pagamento quase sempre escolhem a segunda.

## 1. O problema do atomic commit

*Fonte principal: notas de aula de Kleppmann, seção 7.1.*

Comece pelo que você já usa. Em uma transação ACID, atomicidade significa que a transação ou faz commit, e todas as suas escritas se tornam duráveis, ou aborta, e não deixa nenhum efeito visível. Kleppmann observa que o "C" do ACID (manter invariantes verdadeiros) depende da atomicidade. "A soma de todos os saldos é constante" só vale porque uma transferência nunca acontece pela metade.

Agora deixe a transação tocar dados em dois nós. O débito fica no banco de `accounts` da Ana, e o crédito em outro banco, do Bruno. Para manter o invariante, as notas de Kleppmann enunciam a regra: ou todos os nós fazem commit, ou todos abortam, e se qualquer nó cair, todos precisam abortar. Esse é o **problema do atomic commit** (atomic commitment problem).

Ele parece consenso (o Módulo 9 trata disso a fundo), mas as notas mostram que é mais rígido em um ponto importante:

| | Consenso | Atomic commit |
| --- | --- | --- |
| Entrada | Um ou mais nós propõem um valor | Todo nó vota commit ou abort |
| Decisão | Qualquer um dos valores propostos | Commit só se todos votarem commit; abort se algum votar abort |
| Nós caídos | Tolerados enquanto um quorum funciona | Um participante caído força abort |

O consenso se contenta com uma maioria. O atomic commit precisa de todos os participantes, porque cada participante guarda parte dos dados. Essa diferença explica por que o atomic commit é mais frágil que um cluster de consenso como o Raft, que você vai ver no Módulo 9.

## 2. Como o two-phase commit funciona

*Fonte principal: notas de aula de Kleppmann, seção 7.1.*

O two-phase commit (2PC) é o algoritmo clássico de atomic commit. Ele adiciona um nó extra, o **coordenador**. Usando o diagrama de Kleppmann com a nossa carteira:

1. O cliente envia `begin T1` ao coordenador. T1 então roda normalmente no nó A (conta da Ana) e no nó B (conta do Bruno): leituras, escritas, locks de linha.
2. O cliente envia `commit T1` ao coordenador.
3. **Fase 1 (prepare).** O coordenador envia `prepare` para A e B. Cada participante verifica se consegue fazer commit (constraints passam, dados estão seguros em disco) e responde `ok` ou `not ok`.
4. **Fase 2 (decisão).** Se todos os participantes disseram `ok`, o coordenador decide commit. Se algum disse `not ok`, ou não respondeu, ele decide abort. Ele grava a decisão no próprio disco e depois a envia a todos os participantes.

A promessa central está na fase 1. Quando um participante responde `ok`, ele promete que conseguirá fazer commit depois, aconteça o que acontecer, mesmo após uma queda. Por isso ele precisa persistir as escritas preparadas antes de votar. O Postgres expõe esse papel de participante diretamente:

```sql
-- no banco de accounts (participante A)
BEGIN;
UPDATE accounts SET balance = balance - 100 WHERE id = 'ana';
PREPARE TRANSACTION 'transfer-7f3a';  -- vota "ok": durável, locks mantidos

-- depois, quando o coordenador decidir
COMMIT PREPARED 'transfer-7f3a';      -- ou ROLLBACK PREPARED 'transfer-7f3a'
```

O `PREPARE TRANSACTION` vem desabilitado por padrão (`max_prepared_transactions = 0`), e a documentação do Postgres avisa que ele é feito para gerenciadores de transação externos, não para código de aplicação. O fato de você precisar ligá-lo já indica como times de aplicação raramente o usam.

## 3. Por que o 2PC bloqueia e segura locks

*Fonte principal: notas de aula de Kleppmann, seção 7.1.*

O coordenador grava sua decisão em disco. Se ele cair e se recuperar, lê a decisão e a envia de novo. Se caiu antes de decidir, aborta. Até aqui, tudo bem.

O problema que Kleppmann destaca é a janela no meio: o coordenador cai **depois** de enviar `prepare` e **antes** de enviar a decisão. Cada participante votou `ok`. As notas dizem que um participante nessa situação não pode fazer commit nem abortar por conta própria depois de responder `ok`. Se A fizesse commit sozinho, B poderia ter votado `not ok`, e a atomicidade quebraria. Se A abortasse sozinho, o coordenador poderia ter decidido commit e avisado B. Por isso as notas concluem que o algoritmo fica bloqueado até o coordenador se recuperar.

Pense no que "bloqueado" significa dentro do banco do participante. Uma transação preparada ainda não fez commit, então continua segurando seus locks de linha. A linha da conta da Ana fica travada enquanto o coordenador está fora. Toda outra transferência que mexe no saldo da Ana espera. Com um coordenador que leva dez minutos para voltar, suas contas mais ativas ficam congeladas por dez minutos. No Postgres, uma transação preparada esquecida também continua segurando locks e impede o `VACUUM` de limpar linhas antigas, outro motivo para o recurso vir desligado.

As notas de Kleppmann também mostram um **2PC tolerante a falhas**. Em vez de mandar os votos só ao coordenador, cada participante difunde seu voto a todos os participantes usando total order broadcast (construído sobre consenso). Se um nó suspeita que um participante caiu, ele difunde um voto "not ok" em nome dele. Como todos processam os votos na mesma ordem, todo nó chega à mesma decisão sem esperar por um único coordenador. Isso remove o ponto único de bloqueio, ao custo de uma rodada de consenso por transação. O Spanner do Google, também coberto nas notas, usa 2PC entre shards com participantes replicados por Paxos, que é essa ideia em escala.

## 4. Por que o 2PC não serve para uma carteira digital

*Fonte principal: Richardson, "Pattern: Saga" e "Pattern: Transactional outbox", seções Forces.*

A página de saga de Richardson enuncia a restrição em poucas palavras: "2PC is not an option." A página de outbox dá parte do motivo: o banco ou o message broker podem não suportá-lo, e acoplar um serviço aos dois é indesejável. Para um sistema de pagamentos há mais motivos, e um entrevistador vai querer ouvi-los:

- **APIs externas não têm fase de prepare.** O passo que mais importa em uma fintech costuma ser uma chamada a um banco parceiro, a um processador de cartão ou a um arranjo de pagamento. Isso são APIs HTTP. Você pode pedir que façam um pagamento, consultar o status e às vezes estornar. Você não pode pedir que "preparem e segurem locks até eu avisar". O 2PC exige que todo participante fale o protocolo, e eles não falam.
- **Locks através da rede.** Todo participante segura locks por pelo menos uma ida e volta na rede, e por quanto tempo o participante mais lento ou um coordenador caído levar. Contas quentes (um lojista recebendo milhares de pagamentos) viram uma fila.
- **A disponibilidade se multiplica para baixo.** O atomic commit precisa de todos os participantes. Se cada um de três serviços fica no ar 99,9% do tempo, uma transação que precisa dos três fica disponível cerca de 99,7% do tempo.
- **Acoplamento.** Serviços que entram num 2PC compartilham o destino: um banco de `accounts` lento deixa `payments` lento. Bancos separados por serviço foram escolhidos justamente para evitar isso.

Então a posição prática é: use uma transação ACID local dentro de cada serviço e coordene entre serviços com uma saga.

## 5. Sagas: transações locais mais compensações

*Fonte principal: Richardson, "Pattern: Saga", seção Solution.*

Richardson a define em uma frase: "A saga is a reliably coordinated sequence of local transactions." (uma saga é uma sequência de transações locais coordenada de forma confiável). Cada passo é uma transação normal no banco de um serviço. Quando um passo falha em uma regra de negócio, a saga executa **transações de compensação** que desfazem semanticamente os passos já concluídos.

Para a transferência da Ana para o Bruno, em dois serviços:

| Passo | Serviço | Transação local | Compensação |
| --- | --- | --- | --- |
| 1 | payments | Criar transferência `PENDING` | Marcar transferência `FAILED` |
| 2 | accounts | Debitar 100 da Ana (novo lançamento) | Creditar 100 à Ana (lançamento de estorno) |
| 3 | accounts | Creditar 100 ao Bruno (novo lançamento) | (nenhuma: último passo que pode falhar) |
| 4 | payments | Marcar transferência `COMPLETED` | (nenhuma) |

Três coisas nessa tabela importam para o TCM:

- **Uma compensação é uma transação nova, não um rollback.** O débito do passo 2 já fez commit, e outras sagas podem já ter lido o novo saldo da Ana. Você não pode apagá-lo. Você grava um lançamento de estorno que devolve o dinheiro à Ana. Um ledger nunca apaga nem altera lançamentos passados, então o estorno é o único registro honesto do que aconteceu.
- **Uma compensação não pode falhar por motivo de negócio.** Você sempre consegue devolver o dinheiro da Ana. Se uma compensação pode falhar, ela precisa ser repetida até dar certo, então precisa ser idempotente.
- **A ordem importa.** Coloque cedo o passo com mais chance de falhar, e deixe o mais tarde possível os passos que não podem ser desfeitos (uma chamada ao banco parceiro). A aula de terça dá nome a essa ordenação: a pivot transaction.

Richardson resume o benefício de forma simples: consistência entre serviços sem transações distribuídas. E é igualmente direto sobre o custo: não há rollback automático, e os desenvolvedores precisam projetar as compensações.

## 6. Coreografia versus orquestração

*Fonte principal: Richardson, "Pattern: Saga", exemplos dos dois estilos.*

Richardson descreve duas formas de coordenar os passos.

**Coreografia.** Ninguém está no comando. Cada serviço faz sua transação local e publica um evento, e outros serviços reagem aos eventos. No exemplo de Richardson, o Order Service cria um pedido `PENDING` e emite um evento, o Customer Service reserva crédito e emite o resultado, e o Order Service aprova ou rejeita o pedido. Na carteira: `payments` emite `TransferRequested`, `accounts` debita e emite `AccountDebited`, depois credita e emite `AccountCredited`, e `payments` marca a transferência como concluída.

**Orquestração.** Um componente, o orquestrador, diz aos participantes o que fazer por meio de comandos e reage às respostas. No exemplo de Richardson, um orquestrador da saga Create Order envia o comando `Reserve Credit` ao Customer Service e aprova ou rejeita o pedido conforme a resposta. Na carteira, o orquestrador fica em `payments`: ele chama `accounts` para debitar a Ana, depois para creditar o Bruno, e por fim conclui a transferência.

| | Coreografia | Orquestração |
| --- | --- | --- |
| Onde o fluxo vive | Espalhado pelos handlers de eventos | Em um lugar, o orquestrador |
| Adicionar um passo | Mexe em vários serviços | Muda o orquestrador |
| Ver o estado de uma saga | Reconstruir a partir dos eventos | Ler uma linha |
| Risco | Dependências cíclicas, difícil de depurar | Orquestrador concentra lógica demais |
| Combina com | Poucos passos, poucos times | Fluxos de dinheiro com compensações e timeouts |

Para dinheiro, a maioria dos times escolhe orquestração. O estado de cada transferência está em uma linha que você pode consultar, monitorar e retomar. Richardson observa que a aplicação de exemplo do livro dele também usa orquestração. O TCM faz o mesmo: uma tabela `sagas` em `payments`, com a máquina de estados no orquestrador.

Veja como fica o estado persistido do orquestrador no Postgres:

```sql
CREATE TABLE sagas (
  id         uuid PRIMARY KEY,
  state      text NOT NULL,       -- STARTED, DEBITED, CREDITED, COMPENSATING, COMPLETED, FAILED
  step       int  NOT NULL DEFAULT 0,
  attempts   int  NOT NULL DEFAULT 0,
  deadline   timestamptz NOT NULL, -- quando o passo atual estoura o timeout
  payload    jsonb NOT NULL,       -- from, to, amount, currency
  updated_at timestamptz NOT NULL DEFAULT now()
);
```

Trate isso como um rascunho para raciocinar, não como a resposta do TCM: na quinta-feira você projeta sua própria tabela e seus nomes de estado sem ajuda.

O orquestrador precisa gravar seu estado **antes** de agir com base nele. Se ele cair depois de chamar `accounts` mas antes de salvar `DEBITED`, um recovery worker vai chamar `accounts` de novo no reinício. Isso só é seguro se o débito for idempotente, com chave `saga_id` mais passo (Módulo 2 de novo).

## 7. O que uma saga deixa para você resolver

*Fonte principal: Richardson, "Pattern: Saga", Resulting context.*

O "Resulting context" de Richardson lista os problemas que você herda. Cada um corresponde a uma parte posterior desta semana.

- **Sem isolamento.** Entre o passo 2 e o passo 3, o débito da Ana já fez commit e está visível, mas a transferência não terminou. Outra saga pode ler esse estado intermediário. Richardson diz que sagas concorrentes podem causar anomalias de dados e precisam de contramedidas. Esse é o primeiro tema de terça.
- **Atualizar o banco e enviar uma mensagem de forma atômica.** Um passo que grava no banco e depois publica um evento pode cair no meio. Richardson aponta o Transactional Outbox (ou Event Sourcing) como solução. Esse é o segundo tema de terça.
- **O cliente precisa saber o resultado.** Uma saga demora mais que uma requisição HTTP. Richardson lista três opções: a API espera a conclusão, o cliente faz polling em um endpoint de status, ou o serviço envia uma notificação, como um webhook. Para uma carteira, a resposta usual é `202 Accepted` com um ID de transferência, mais `GET /transfers/:id`.
- **Quedas no meio.** O próprio orquestrador pode morrer em qualquer ponto. Seu estado precisa ser durável, e algo precisa retomar as sagas não concluídas. Esse é o recovery worker do TCM, e os motores de workflow durável de quarta resolvem o mesmo problema como produto.

**O lab de hoje** prepara o terreno. Rode `accounts` e `payments` no Docker Compose, cada um com seu próprio Postgres, conversando por HTTP. Depois derrube um container no meio de uma transferência e olhe os dois bancos. Você vai ver o estado pela metade que o resto da semana ensina a tratar.

## O que anotar hoje

1. Como o 2PC funciona, em cinco linhas: begin, prepare, voto, decisão gravada em disco, decisão enviada.
2. Por que um participante que votou `ok` mantém seus locks, e o que isso faz com uma conta quente quando o coordenador está fora.
3. Três motivos pelos quais o 2PC não funciona entre uma carteira e um banco parceiro (comece por: APIs externas não têm fase de prepare).
4. Coreografia versus orquestração: uma frase para cada, mais por que você escolheria orquestração para uma transferência.
5. A tabela de compensações da transferência da Ana para o Bruno, e por que a compensação de um débito é um lançamento de estorno e nunca um delete.

## Teste-se

Estas perguntas dão bons flashcards (veja o [guia de flashcards](../../FLASHCARDS.pt-BR.md)).

- O que é o problema do atomic commit, e como ele difere do consenso?
- No 2PC, por que um participante que votou `ok` não pode decidir sozinho quando o coordenador some?
- Por que você não pode incluir a API HTTP de um banco parceiro em uma transação 2PC?
- O que é uma saga, na definição de uma frase de Richardson?
- Por que uma compensação é uma transação nova e não um rollback?
- Cite uma vantagem da orquestração sobre a coreografia para uma transferência de dinheiro.
- Quais três problemas uma saga deixa para você resolver?

## Referências

- **Fonte principal:** Martin Kleppmann, [notas de aula "Distributed Systems"](https://www.cl.cam.ac.uk/teaching/2122/ConcDisSys/dist-sys-notes.pdf), Universidade de Cambridge, 2021/22, seção 7.1 (Two-phase commit). Gratuito, Creative Commons BY-SA. Os mesmos slides estão no [handout para impressão](https://www.cl.cam.ac.uk/teaching/2122/ConcDisSys/dist-sys-handout.pdf), e as videoaulas estão linkadas na [página de materiais do curso](https://www.cl.cam.ac.uk/teaching/2122/ConcDisSys/materials.html).
- **Fonte principal:** Chris Richardson, microservices.io, ["Pattern: Saga"](https://microservices.io/patterns/data/saga.html). Leia a página inteira, incluindo os dois exemplos e o "Resulting context". Gratuito.
- Documentação do PostgreSQL, ["PREPARE TRANSACTION"](https://www.postgresql.org/docs/current/sql-prepare-transaction.html). Opcional: mostra o lado participante do 2PC no Postgres e seus avisos. Gratuito.
