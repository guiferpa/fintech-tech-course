# Módulo 4, segunda-feira: two-phase commit e por que sagas existem

[Módulo 4](../../modules/04-sagas-outbox.pt-BR.md) · [Read in English](day-1.md)

**Tempo de leitura:** cerca de 45 minutos. Use o resto do bloco de 2 horas nas referências do final, começando pelas seções marcadas como fonte principal.

Este é um texto original escrito para este curso. Ele se baseia nas referências listadas no final, e cada seção indica a fonte que segue. Quando uma ideia vem de um autor específico, o texto diz isso.

## Por que isso importa para uma fintech

Até agora, sua carteira digital guardava todos os saldos em um único banco Postgres. Uma transferência da Ana para o Bruno era um único `BEGIN ... COMMIT`, e o Postgres garantia que os dois lançamentos fossem gravados, ou nenhum. Nesta semana você divide a carteira em dois serviços, `accounts` e `payments`, cada um com seu próprio banco. A transação única deixa de existir.

A pergunta que todo entrevistador de fintech faz em seguida é: "Como você move dinheiro entre dois serviços sem perder nem criar dinheiro?" Há duas famílias de respostas. Uma tenta manter uma única transação atômica entre máquinas (two-phase commit). A outra aceita uma sequência de transações locais e conserta as falhas com compensações (a saga). Esta aula explica as duas, usando os comandos que o Postgres realmente oferece e os padrões que AWS, Azure e Cockroach Labs documentam, e mostra por que sistemas de pagamento quase sempre escolhem a segunda.

## 1. O problema do atomic commit

*Fontes principais: blog da Cockroach Labs, "Parallel Commits"; AWS Prescriptive Guidance, "Saga orchestration pattern".*

Comece pelo que você já usa. O artigo da Cockroach Labs sobre parallel commits resume a atomicidade numa expressão: uma transação é "all or nothing". Ou ela faz commit, e todas as suas escritas se tornam duráveis, ou faz rollback e não deixa nada para trás. O invariante "a soma de todos os saldos é constante" só vale porque uma transferência nunca acontece pela metade.

Agora deixe a transação mexer em dados em duas máquinas. O débito fica no banco de `accounts` para a Ana, e o crédito em outro banco para o Bruno. Para manter o invariante, os dois bancos precisam fazer commit ou os dois precisam abortar, e um crash de qualquer um deles no meio não pode deixar o débito sem o crédito. Esse é o **problema do atomic commit**.

O guia da AWS sobre saga orchestration explica por que isso é difícil num cenário de microsserviços: com um banco por serviço, "there is no single controller" capaz de coordenar o commit como um banco coordena as próprias transações. Você precisa de um protocolo que coordene vários bancos independentes. O clássico é o two-phase commit.

Guarde um ponto para o Módulo 9: um cluster de consenso (Raft, etcd) funciona enquanto a maioria está de pé, mas o atomic commit precisa de todos os participantes, porque cada um guarda parte dos dados. Um participante que diz não, ou que nunca responde, força um abort.

## 2. Como o two-phase commit funciona

*Fontes principais: AWS Prescriptive Guidance, "Saga orchestration pattern"; documentação do PostgreSQL, "Two-Phase Transactions" e "PREPARE TRANSACTION".*

O two-phase commit (2PC) acrescenta um papel extra, o **coordenador**. O guia da AWS descreve as duas fases em duas frases. Na fase de prepare, o coordenador pede aos participantes "to promise to either commit or roll back the transaction". Na fase de commit, pede que façam commit; se algum participante não conseguiu concordar na fase de prepare, a transação sofre rollback.

Com a nossa carteira:

1. O cliente pede ao coordenador para iniciar a transferência T1. T1 roda normalmente no banco A (conta da Ana) e no banco B (conta do Bruno): leituras, escritas, locks de linha.
2. O cliente pede ao coordenador para fazer commit de T1.
3. **Fase 1 (prepare).** O coordenador manda A e B se prepararem. Cada participante verifica se consegue fazer commit (constraints passam, dados estão seguros em disco) e responde sim ou não.
4. **Fase 2 (decisão).** Se todos disseram sim, o coordenador decide commit. Se algum disse não, ou não respondeu, decide abort. Ele registra a decisão e depois a envia para todos os participantes.

A promessa principal está na fase 1. Um participante que vota sim promete que vai conseguir fazer commit depois, mesmo após um crash. O Postgres expõe esse papel de participante diretamente. A documentação diz que o Postgres suporta 2PC com três comandos, `PREPARE TRANSACTION`, `COMMIT PREPARED` e `ROLLBACK PREPARED`, e segue o modelo do padrão X/Open XA:

```sql
-- no banco de accounts (participante A)
BEGIN;
UPDATE accounts SET balance = balance - 100 WHERE id = 'ana';
PREPARE TRANSACTION 'transfer-7f3a';  -- voto "sim": estado salvo em disco, locks mantidos

-- depois, quando o coordenador decide (de qualquer sessão)
COMMIT PREPARED 'transfer-7f3a';      -- ou ROLLBACK PREPARED 'transfer-7f3a'
```

A página de `PREPARE TRANSACTION` torna a promessa concreta. Depois do comando, a transação se desliga da sua sessão e o estado dela fica "fully stored on disk", então muito provavelmente ainda poderá receber commit depois de um crash. Sua sessão não vê mais transação corrente, e os efeitos ficam invisíveis até alguém rodar `COMMIT PREPARED`, que pode vir de qualquer sessão: é isso que permite a um coordenador externo terminar o trabalho. O identificador é um literal de string com menos de 200 bytes; derivá-lo do ID da transferência facilita a recuperação. A página "Two-Phase Transactions" acrescenta que os únicos comandos possíveis em seguida são `COMMIT PREPARED` ou `ROLLBACK PREPARED`.

## 3. Por que o 2PC bloqueia e segura locks

*Fontes principais: documentação do PostgreSQL, "PREPARE TRANSACTION" e "Two-Phase Transactions"; Nathan VanBenschoten, "Parallel Commits" (blog da Cockroach Labs).*

Se o coordenador cai e volta, ele lê a decisão registrada e a envia de novo. A janela perigosa fica no meio: o coordenador cai **depois** que os participantes votaram sim e **antes** que eles recebam a decisão.

O artigo da Cockroach Labs aponta esse como o problema mais citado do 2PC: ele é "blocking". Depois que os participantes votam pelo commit, o sistema "enters a fragile state", e se o coordenador caiu, seria impossível para os outros saber o resultado final. Pense no que um participante pode fazer. Se A fizer commit por conta própria, B pode ter votado não, e a atomicidade quebra. Se A abortar por conta própria, o coordenador pode ter decidido commit e avisado B. Então A espera.

O que significa esperar dentro do Postgres? A página de `PREPARE TRANSACTION` é explícita: uma transação preparada "continues to hold whatever locks it held". A linha da conta da Ana fica travada enquanto o coordenador está fora. Toda outra transferência que mexe no saldo da Ana espera. Com um coordenador que leva dez minutos para voltar, suas contas mais ativas congelam por dez minutos.

A mesma página lista os outros custos de deixar transações preparadas por muito tempo: isso atrapalha o `VACUUM` e, em casos extremos, pode forçar o banco a desligar para evitar o wraparound de IDs de transação. Por isso a documentação recomenda manter o recurso desligado, com `max_prepared_transactions` em zero, a menos que você precise dele: isso evita transações preparadas que acabam esquecidas. Você vê as que sobraram com uma consulta simples:

```sql
SELECT gid, prepared, owner, database
FROM pg_prepared_xacts
ORDER BY prepared;  -- as mais antigas primeiro: são as que seguram locks há mais tempo
```

A documentação é igualmente clara sobre quem deve usar o recurso: `PREPARE TRANSACTION` "is not intended for use in applications or interactive sessions". Ele existe para gerenciadores de transação externos. A página "Two-Phase Transactions" acrescenta que o estado preparado deveria ser muito curto, mas problemas de disponibilidade externos podem esticá-lo.

**Como um banco que usa 2PC evita o bloqueio.** No CockroachDB, gravar valores provisórios (write intents) faz o papel da fase de prepare, e marcar um registro de transação como committed é a fase de commit. Esse registro é replicado por consenso como os dados, então a decisão sobrevive a um crash, e qualquer transação que esbarra num intent consulta o registro para saber o resultado. O preço é latência: colocar 2PC sobre consenso "requires two sequential rounds of consensus writes", e o protocolo Parallel Commits reduz isso a uma rodada. A lição: 2PC seguro precisa de um sistema de consenso por baixo, algo que você compra num banco de dados, não algo que você constrói entre dois serviços NestJS.

## 4. Por que o 2PC não serve para uma carteira digital

*Fontes principais: Chris Richardson, "Pattern: Saga" (microservices.io), seção Forces; AWS Prescriptive Guidance, "Saga orchestration pattern", Applicability.*

A página de saga do Richardson diz a restrição em poucas palavras: "2PC is not an option." O guia da AWS recomenda sagas quando o banco não oferece 2PC ou quando implementá-lo na aplicação é complexo. Para um sistema de pagamentos há mais motivos, e um entrevistador vai querer ouvi-los:

- **APIs externas não têm fase de prepare.** O passo mais importante numa fintech muitas vezes é uma chamada a um banco parceiro, a um processador de cartão ou a um arranjo de pagamento. São APIs HTTP. Você pode pedir que façam um pagamento, consultar o status e às vezes estornar. Não pode pedir que "preparem e segurem locks até eu avisar". O 2PC exige que todo participante fale o protocolo, e eles não falam.
- **Locks atravessando a rede.** Como a seção 3 mostrou, todo participante segura locks do prepare até a decisão chegar, o que leva pelo menos uma ida e volta de rede, e tanto tempo quanto um coordenador caído levar para voltar. Contas quentes (um lojista recebendo milhares de pagamentos) viram uma fila.
- **A disponibilidade se multiplica para baixo.** O atomic commit precisa de todos os participantes. Se cada um de três serviços fica no ar 99,9% do tempo, uma transação que precisa dos três fica disponível cerca de 99,7% do tempo.
- **Acoplamento.** Serviços que entram num 2PC compartilham o destino: um banco de `accounts` lento deixa `payments` lento. Bancos separados por serviço foram escolhidos justamente para evitar isso.

Então a posição prática é: use uma transação ACID local dentro de cada serviço e coordene entre serviços com uma saga.

## 5. Sagas: transações locais mais compensações

*Fontes principais: Chris Richardson, "Pattern: Saga", seção Solution; Azure Architecture Center, "Saga distributed transactions pattern".*

O Richardson define em uma frase: "A saga is a reliably coordinated sequence of local transactions." Cada passo é uma transação normal no banco de um serviço. Quando um passo falha numa regra de negócio, a saga executa **transações de compensação** que desfazem semanticamente os passos já concluídos.

A página do Azure Architecture Center acrescenta um vocabulário que combina bem com fluxos de dinheiro. Ela divide os passos de uma saga em três tipos:

- Passos **compensáveis** podem ser desfeitos por outra transação com o efeito oposto.
- O passo **pivô** é "the point of no return". Depois que ele dá certo, a compensação não se aplica mais, e todos os passos restantes precisam ser concluídos.
- Passos **repetíveis** (retryable) vêm depois do pivô. São idempotentes, então podem ser repetidos até a saga chegar ao estado final.

Para a transferência da Ana para o Bruno, em dois serviços:

| Passo | Serviço | Transação local | Compensação | Tipo |
| --- | --- | --- | --- | --- |
| 1 | payments | Criar transferência `PENDING` | Marcar transferência `FAILED` | compensável |
| 2 | accounts | Debitar 100 da Ana (novo lançamento no ledger) | Creditar 100 para a Ana (lançamento de estorno) | compensável |
| 3 | accounts | Creditar 100 para o Bruno (novo lançamento no ledger) | (nenhuma: último passo que pode falhar) | pivô |
| 4 | payments | Marcar transferência `COMPLETED` | (nenhuma) | repetível |

Três coisas nessa tabela importam para o capstone:

- **Uma compensação é uma nova transação, não um rollback.** O débito do passo 2 já fez commit, e outras sagas podem já ter lido o novo saldo da Ana. Você não pode apagá-lo. Você grava um lançamento de estorno que devolve o dinheiro à Ana. Um ledger nunca apaga nem altera lançamentos passados, então o estorno é o único registro honesto do que aconteceu.
- **Uma compensação não pode falhar por motivo de negócio.** Você sempre pode devolver o dinheiro da Ana. Se uma compensação pode falhar por motivo técnico, ela precisa ser repetida até dar certo, então tem que ser idempotente.
- **A ordem importa.** Coloque cedo o passo com mais chance de falhar, e deixe os passos que não podem ser desfeitos (uma chamada a um banco parceiro) o mais tarde possível, no pivô ou depois dele. A aula de terça volta a essa ordenação.

O Richardson lista o benefício de forma simples: consistência de dados entre serviços "without using distributed transactions". Ele é igualmente direto sobre os custos: não há rollback automático, então os desenvolvedores precisam projetar compensações, e não há isolamento entre sagas concorrentes.

## 6. Coreografia versus orquestração

*Fontes principais: Chris Richardson, "Pattern: Saga", exemplos dos dois estilos; Azure Architecture Center, "Saga distributed transactions pattern"; AWS Prescriptive Guidance, "Saga orchestration pattern", exemplo.*

Há duas formas de coordenar os passos.

**Coreografia.** Ninguém está no comando. Cada serviço faz sua transação local e publica um evento, e os outros serviços reagem aos eventos. No exemplo do Richardson, o Order Service cria um pedido `PENDING` e emite um evento, o Customer Service reserva crédito e emite o resultado, e o Order Service aprova ou rejeita o pedido. Na carteira: `payments` emite `TransferRequested`, `accounts` debita e emite `AccountDebited`, depois credita e emite `AccountCredited`, e `payments` marca a transferência como concluída.

**Orquestração.** Um componente, o orquestrador, diz aos participantes o que fazer com comandos e reage às respostas deles. O guia da AWS tem uma versão concreta: um workflow do AWS Step Functions que executa Place Order, Update Inventory e Make Payment e, em caso de falha, executa Revert Payment, Revert Inventory e Remove Order. Na carteira, o orquestrador mora em `payments`: chama `accounts` para debitar a Ana, depois para creditar o Bruno e, por fim, conclui a transferência.

A página do Azure lista os trade-offs, e eles batem com o que você vai sentir no capstone:

| | Coreografia | Orquestração |
| --- | --- | --- |
| Bom para | Fluxos simples com poucos serviços | Fluxos complexos, ou quando você adiciona serviços |
| Coordenação | Nenhum serviço extra, nenhum ponto único de falha | O orquestrador é um ponto de falha |
| Risco principal | Dependências cíclicas; difícil rastrear quem reage a quê | Lógica de coordenação para projetar e manter |
| Testes | Todos os serviços precisam rodar para simular uma transação | O fluxo fica num lugar só |

Para dinheiro, a maioria dos times escolhe orquestração: o estado de cada transferência fica numa linha que você pode consultar, monitorar com alertas e retomar. O exemplo do livro do Richardson também usa orquestração. O guia da AWS observa que o Step Functions reduz o risco de ponto único de falha com tolerância a falhas embutida; no capstone você obtém um efeito parecido persistindo o estado do orquestrador no Postgres.

Veja como poderia ficar o estado persistido do orquestrador:

```sql
CREATE TABLE sagas (
  id         uuid PRIMARY KEY,
  state      text NOT NULL,       -- STARTED, DEBITED, CREDITED, COMPENSATING, COMPLETED, FAILED
  step       int  NOT NULL DEFAULT 0,
  attempts   int  NOT NULL DEFAULT 0,
  deadline   timestamptz NOT NULL, -- quando o passo atual estoura o timeout
  payload    jsonb NOT NULL,       -- origem, destino, valor, moeda
  updated_at timestamptz NOT NULL DEFAULT now()
);
```

Trate isso como um esboço para raciocinar, não como a resposta do capstone: na quinta você projeta sua própria tabela e seus nomes de estado sem ajuda.

O orquestrador precisa gravar o estado **antes** de agir com base nele. Se ele cair depois de chamar `accounts`, mas antes de salvar `DEBITED`, um worker de recuperação vai chamar `accounts` de novo ao reiniciar. Isso só é seguro se o débito for idempotente, com chave `saga_id` mais passo (Módulo 2 de novo). O guia da AWS concorda: os participantes precisam ser idempotentes para sobreviver a crashes e a falhas do orquestrador.

## 7. O que uma saga deixa para você resolver

*Fontes principais: Chris Richardson, "Pattern: Saga", Resulting context; AWS Prescriptive Guidance, "Saga orchestration pattern", Issues and considerations.*

O "Resulting context" do Richardson lista os problemas que você herda, e cada um corresponde a uma parte posterior desta semana.

- **Sem isolamento.** Entre o passo 2 e o passo 3, o débito da Ana já fez commit e está visível, mas a transferência não terminou. Outra saga pode ler esse estado intermediário. O Richardson diz que sagas concorrentes podem causar anomalias de dados; o guia da AWS recomenda semantic locking. Esse é o primeiro tema de terça.
- **Atualizar o banco e enviar uma mensagem de forma atômica.** Um passo que grava no banco e depois publica um evento pode cair no meio. O Richardson aponta o Transactional Outbox como solução. Esse é o segundo tema de terça.
- **O cliente precisa do resultado.** Uma saga demora mais que uma requisição HTTP. O Richardson lista três opções: o serviço responde quando a saga termina, o serviço responde na hora com um ID e o cliente faz polling, ou o serviço envia um evento, como um webhook, quando a saga termina. Para uma carteira, a resposta comum é `202 Accepted` com um ID de transferência, mais `GET /transfers/:id`.
- **Crashes no meio.** O próprio orquestrador pode morrer a qualquer momento. O estado dele precisa ser durável, e algo precisa retomar as sagas inacabadas. Esse é o worker de recuperação do capstone, e os motores de workflow durável de quarta resolvem o mesmo problema como produto.

**O lab de hoje** prepara o terreno. Rode `accounts` e `payments` no Docker Compose, cada um com seu próprio Postgres, conversando por HTTP. Depois mate um container no meio de uma transferência e olhe os dois bancos. Você vai ver o estado pela metade que o resto da semana ensina a tratar.

## O que anotar hoje

1. Como o 2PC funciona, em cinco linhas: begin, prepare, voto, decisão registrada, decisão enviada. Acrescente os três comandos do Postgres que implementam o lado participante.
2. Por que um participante que votou sim mantém seus locks, e o que isso faz com uma conta quente quando o coordenador está fora. Inclua a consulta a `pg_prepared_xacts` que você rodaria durante um incidente.
3. Três motivos pelos quais o 2PC não funciona entre uma carteira e um banco parceiro (comece por: APIs externas não têm fase de prepare).
4. Coreografia versus orquestração: uma frase para cada, mais por que você escolheria orquestração para uma transferência.
5. A tabela de compensação da transferência Ana para Bruno, com os passos compensáveis, o pivô e os repetíveis marcados, e por que a compensação de um débito é um lançamento de estorno e nunca um delete.

## Teste-se

Estas perguntas dão bons flashcards (veja o [guia de flashcards](../../FLASHCARDS.pt-BR.md)).

- O que é o problema do atomic commit, e por que ele precisa de todos os participantes enquanto o consenso só precisa da maioria?
- No 2PC, por que um participante que votou sim não pode decidir sozinho quando o coordenador some?
- O que o `PREPARE TRANSACTION` faz com a sessão, com os locks e com o `VACUUM`?
- Por que você não pode incluir a API HTTP de um banco parceiro numa transação 2PC?
- O que é uma saga, na definição de uma frase do Richardson?
- O que é uma transação pivô, e onde a chamada a um banco parceiro deve ficar em relação a ela?
- Por que uma compensação é uma nova transação e não um rollback?
- Cite uma vantagem da orquestração sobre a coreografia para uma transferência de dinheiro.

## Referências

- **Fonte principal:** Chris Richardson, microservices.io, ["Pattern: Saga"](https://microservices.io/patterns/data/saga.html). Leia a página inteira, incluindo os dois exemplos e o "Resulting context". Gratuito.
- **Fonte principal:** Documentação do PostgreSQL, ["PREPARE TRANSACTION"](https://www.postgresql.org/docs/current/sql-prepare-transaction.html). Leia a Description, as Notes e o quadro Caution: é o lado participante do 2PC, com os avisos reais sobre locks e `VACUUM`. Gratuito.
- Documentação do PostgreSQL, ["Two-Phase Transactions"](https://www.postgresql.org/docs/current/two-phase.html). Dois parágrafos: os três comandos, o modelo XA e por que o estado preparado deve ser curto. Gratuito.
- Nathan VanBenschoten, ["Parallel Commits: An atomic commit protocol for globally distributed transactions"](https://www.cockroachlabs.com/blog/parallel-commits/), blog da Cockroach Labs, 2019. Leia as partes sobre atomic commit, two-phase commit e bloqueio; passe os olhos nos detalhes do protocolo. Gratuito.
- AWS Prescriptive Guidance, ["Saga orchestration pattern"](https://docs.aws.amazon.com/prescriptive-guidance/latest/cloud-design-patterns/saga-orchestration.html). Leia a descrição do 2PC, "Applicability", "Issues and considerations" e o exemplo com Step Functions. Gratuito.
- Azure Architecture Center, ["Saga distributed transactions pattern"](https://learn.microsoft.com/en-us/azure/architecture/patterns/saga). Leia os tipos de transação (compensável, pivô, repetível) e os trade-offs de coreografia e orquestração. Gratuito.
