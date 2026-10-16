# Módulo 4, quarta-feira: workflows duráveis e a máquina de estados da saga de transferência

[Módulo 4](../../modules/04-sagas-outbox.pt-BR.md) · [Read in English](day-3.md)

**Tempo de leitura:** cerca de 45 minutos. Use o resto do bloco de 2 horas nas referências do final e depois desenhe no papel a máquina de estados descrita na seção 6.

Este é um texto original escrito para este curso. Ele se baseia nas referências listadas no final, e cada seção indica a fonte que segue. Quando uma ideia vem de um autor específico, o texto diz isso.

## Por que isso importa para uma fintech

Na quinta-feira você constrói um orquestrador, e na sexta você o derruba 20 vezes em pontos aleatórios. O critério de aprovação é rígido: saldo total inalterado e nenhuma saga presa. Essa é a dificuldade real das sagas. Escrever o caminho feliz leva uma hora. Fazer cada passo sobreviver a uma queda, um retry, um timeout e um reinício é o trabalho de verdade.

Algumas empresas resolvem isso com uma tabela `sagas` caseira e um recovery worker. Outras adotam um motor de workflow durável, como Temporal ou AWS Step Functions, que vende "seu código sobrevive a quedas" como produto. Hoje você vê o que esses motores fazem, para construir as mesmas garantias à mão nesta semana e explicar numa entrevista quando vale pagar por um motor.

## 1. O orquestrador é o ponto mais fraco

*Esta seção aplica as fontes de segunda e terça ao TCM; não há uma referência única.*

Um orquestrador é um loop que lê o estado de uma saga, chama um participante e grava o novo estado. Uma queda pode acontecer em qualquer um destes pontos:

| Ponto da queda | O que sobrevive | O que precisa acontecer no reinício |
| --- | --- | --- |
| Depois de salvar `STARTED`, antes de chamar `accounts` | A linha da saga | Chamar o débito; ele não aconteceu |
| Depois de `accounts` debitar a Ana, antes de salvar `DEBITED` | O débito da Ana, saga ainda `STARTED` | Chamar o débito de novo; `accounts` precisa responder "já feito" |
| Depois de salvar `DEBITED`, antes de chamar o crédito | Débito e estado | Chamar o crédito |
| Durante a chamada de crédito (timeout) | Desconhecido | Fazer retry do crédito com a mesma chave, ou consultar o status |
| Depois que o crédito falhou de vez, durante a compensação | Débito, estado `COMPENSATING` | Repetir o estorno até dar certo |

Duas regras cobrem todas as linhas da tabela. **Cada passo é idempotente**, com chave `saga_id` mais passo, então repetir um passo não causa dano. **Algo retoma as sagas não terminais**, para que uma saga cujo orquestrador morreu não espere para sempre. Um motor de workflow durável é, no fundo, um produto que entrega essas duas regras, mais timers, retries e visibilidade.

## 2. Temporal: durable execution

*Fonte principal: documentação do Temporal, "What is Temporal?", mais as páginas linkadas sobre Workflow Definitions e Activities.*

O Temporal se descreve como um runtime para execuções duráveis de funções. A documentação diz que ele "enables you to develop as if failures don't even exist" (permite desenvolver como se falhas nem existissem). A ideia central é a **Durable Execution**: uma Workflow Execution mantém seu estado e seu progresso através de quedas e indisponibilidades. O Temporal registra cada passo em um **Event History**, e uma Workflow Execution pode continuar a partir do último evento registrado.

A plataforma tem duas partes. O **Temporal Service** (o Temporal Server, escrito em Go, mais um banco de dados, ou o Temporal Cloud como opção hospedada) supervisiona as execuções. Os **Worker Processes**, que você hospeda e opera, rodam seu código usando os SDKs do Temporal. Note o que isso significa na operação: o Temporal não tira o banco de dados do seu desenho; ele move o estado da saga para o banco dele, que você precisa operar ou pagar.

Seu código se divide em dois tipos de função:

- **Workflows** contêm a lógica de orquestração: chamar isto, depois aquilo, compensar em caso de falha. A documentação diz que uma Workflow Execution executa sua Workflow Definition exatamente uma vez e até o fim, qualquer que seja a duração, a carga ou as falhas.
- **Activities** fazem o trabalho real com efeitos colaterais, como chamar `accounts` ou um banco parceiro. A página de Activities recomenda que cada Activity seja idempotente, "so retries can be processed without duplicate side effects" (para que retries sejam processados sem efeitos colaterais duplicados).

A divisão existe por causa do **replay**. Quando um worker cai, outro worker reconstrói o estado do workflow rodando o código do workflow de novo e comparando o que ele faz com o Event History. A página de Workflow Definition diz que "Workflow code must be deterministic to support replay" (o código do workflow precisa ser determinístico para suportar replay). Por isso o código do workflow não pode chamar APIs, ler o relógio ou gerar números aleatórios diretamente. Isso vai para Activities, que rodam fora do caminho de replay, ou para funções do SDK cujos resultados ficam guardados no histórico. Uma saga de transferência no Temporal parece TypeScript comum:

```typescript
// Código de workflow: só orquestração determinística (estilo do SDK TypeScript do Temporal).
// debit, credit e reverseDebit são Activities obtidas com proxyActivities().
export async function transferSaga(t: Transfer): Promise<void> {
  await debit(t.from, t.amount, `${t.id}:debit`);        // chamada de Activity
  try {
    await credit(t.to, t.amount, `${t.id}:credit`);      // chamada de Activity
  } catch (err) {
    await reverseDebit(t.from, t.amount, `${t.id}:reversal`); // compensação
    throw err;
  }
}
```

Se o worker morrer depois de `debit` retornar, um novo worker faz o replay do histórico, vê que `debit` já terminou, não o chama de novo e continua em `credit`. Seu recovery worker faz o mesmo trabalho à mão: lê o estado da saga na tabela `sagas` e continua a partir dali.

## 3. Retries, timeouts e timers no Temporal

*Fonte principal: documentação do Temporal, "Retry Policies", "Detecting Activity failures" e "Workflow Definition".*

Vale conhecer os defaults do Temporal, porque eles mostram o que um motor maduro considera seguro.

**Retries.** Activities fazem retry por padrão. A página de Retry Policies dá os defaults: intervalo inicial de 1 segundo, coeficiente de backoff 2,0, intervalo máximo de 100 vezes o intervalo inicial, tentativas ilimitadas e nenhum erro não retentável. Workflows são diferentes: a página diz que "Workflow Executions do not retry by default" (Workflow Executions não fazem retry por padrão). A lição para o seu desenho é a mesma divisão: repita o passo individual indefinidamente com backoff (ele é idempotente), mas não recomece a saga inteira.

Retries ilimitados são errados para falhas de negócio. Se `accounts` responde "a conta do Bruno está encerrada", repetir por uma semana não vai ajudar. Você marca esse erro como não retentável, para que o workflow veja a falha e compense.

**Timeouts.** O Temporal tem quatro timeouts de Activity:

| Timeout | Limita | Equivalente no TCM |
| --- | --- | --- |
| Schedule-To-Start | Tempo que uma tarefa espera na fila por um worker | Raramente necessário; a documentação sugere monitorar a métrica de latência em vez disso |
| Start-To-Close | Uma tentativa | Timeout HTTP de cada chamada a `accounts` |
| Schedule-To-Close | Todas as tentativas somadas | O `deadline` por passo na sua linha de `sagas` |
| Heartbeat | Intervalo entre relatos de progresso de uma Activity longa | Desnecessário para chamadas HTTP curtas |

A documentação explica por que o Start-To-Close importa: o servidor não detecta que um worker caiu, então é esse timeout que força um retry depois de uma queda. É obrigatório definir o Start-To-Close ou o Schedule-To-Close. Seu recovery worker se apoia na mesma ideia: uma saga cujo `deadline` passou é considerada abandonada e é retomada.

**Timers.** Um workflow pode dormir de forma durável. A página de Workflow Definition mostra que iniciar um timer emite um comando `StartTimer` e suspende a execução até ele disparar, então "espere 24 horas e depois consulte o banco parceiro" sobrevive a reinícios. Na sua tabela, um timer é só o `deadline` mais um worker que busca linhas vencidas.

## 4. AWS Step Functions: máquinas de estado como serviço

*Fonte principal: AWS Step Functions Developer Guide, "What is Step Functions?".*

O Step Functions ataca o mesmo problema de outro jeito. Em vez de código que passa por replay, você declara uma **máquina de estados** (o guia a chama de workflow) de passos orientados a eventos. Cada passo é um **state**. Um **Task state** é uma unidade de trabalho feita por outro serviço, como chamar uma função Lambda ou outra API da AWS. Cada instância em execução é uma **execution**. O trabalho também pode ser feito por **Activities**, workers que rodam fora do Step Functions.

O guia descreve dois tipos de workflow, e a diferença é a coisa mais importante da página:

| | Standard | Express |
| --- | --- | --- |
| Semântica | Cada passo roda exatamente uma vez | Cada passo roda pelo menos uma vez, possivelmente mais |
| Duração máxima | Até um ano | Até cinco minutos |
| Preço | Por transição de estado | Por número e duração das execuções |
| Histórico | Guardado no Step Functions, depuração visual | Enviado ao CloudWatch |
| Combina com | Fluxos longos e auditáveis | Processamento de eventos em alto volume |

Para uma transferência de dinheiro, o Standard é o encaixe natural: é auditável e pode esperar um banco parceiro por dias. Mesmo assim, "exatamente uma vez" descreve as transições de passo do motor. Se uma Task chama sua API de `accounts` e a resposta se perde, sua API pode ter feito o trabalho mesmo assim. Idempotency keys continuam sendo sua responsabilidade.

O guia também mostra padrões que correspondem a sagas. **Retry e Catch** permitem repetir uma tarefa que falhou ou capturar a falha e rodar passos alternativos, que é onde entra uma compensação. Um state **Choice** ramifica com base nos dados (o exemplo do guia: aprovar automaticamente um aumento de limite abaixo de um valor, senão mandar para um gerente). **Esperar um callback com task token** pausa a execução até um sistema externo ou uma pessoa devolver o token, útil quando um banco parceiro confirma um saque por webhook.

## 5. Quando um motor vale o custo?

*Esta seção compara os dois motores acima com a abordagem caseira do TCM.*

| | Caseiro (tabela `sagas` + worker) | Temporal | Step Functions |
| --- | --- | --- | --- |
| Onde o estado vive | No seu Postgres | No banco do Temporal | Na AWS |
| Fluxo escrito como | Máquina de estados no código | Código comum, com replay | Máquina de estados declarativa |
| Retries, timers | Você constrói | Embutidos | Embutidos |
| Visibilidade | Suas queries e dashboards | UI do Event History | Histórico de execuções, console visual |
| Custo | Seu tempo de engenharia | Um cluster para operar, ou o Temporal Cloud | Por transição (Standard) |
| Lock-in | Nenhum | SDK e modelo do Temporal | AWS |
| Curva de aprendizado | Baixa no início, cresce a cada caso de borda | Regras de determinismo, versionamento | Definições específicas da AWS |

Uma resposta razoável em entrevista: poucas sagas curtas, de um único time, com Postgres já em uso, funcionam bem com uma tabela e um recovery worker. Muitos fluxos longos (onboarding com KYC, saques que esperam dias por um parceiro, disputas e chargebacks com passos humanos), envolvendo vários times, justificam um motor. O motor não elimina a necessidade de participantes idempotentes, compensações ou conciliação. Ele elimina o encanamento: estado persistido, retries, timers e o loop de retomada.

Construir tudo à mão nesta semana continua sendo a escolha certa. Você não consegue julgar o valor de um motor antes de sentir o que ele substitui.

## 6. No papel: a máquina de estados da saga de transferência

*Esta seção transforma a tarefa de papel de hoje em um checklist. Ela aplica as fontes acima; o desenho é seu.*

Desenhe a máquina de estados da saga de transferência entre serviços antes de escrever qualquer código na quinta. Ela deve responder cinco perguntas.

**Estados.** Liste todos os estados e marque quais são terminais. Um conjunto inicial para discutir: `STARTED`, `DEBITED`, `CREDITED`, `COMPLETED`, `COMPENSATING`, `COMPENSATED` (ou `FAILED`). Pergunte-se se você precisa de um estado `UNKNOWN` para uma chamada que deu timeout, como no Módulo 1.

**Transições.** Para cada estado, qual evento o move e para onde? Por exemplo, "débito confirmado" leva `STARTED` a `DEBITED`; "crédito recusado" leva `DEBITED` a `COMPENSATING`. Marque quais transições são retries do mesmo passo e quais fazem a saga avançar.

**Compensações.** Para cada estado alcançado depois de um passo compensável, o que o desfaz? A compensação do débito é um lançamento de estorno, nunca um delete. Marque a pivot: depois de qual transição a saga está comprometida a terminar? Em uma transferência interna, o crédito ao Bruno é o último passo que pode falhar; depois que ele dá certo, só restam passos retriable.

**Timeouts por passo.** Dê a todo estado não terminal um deadline e uma ação para quando ele vencer: retry com a mesma idempotency key, consultar o status no participante ou começar a compensar. Decida quantas tentativas um passo recebe antes de desistir e quais erros não são retentáveis (conta encerrada, moeda divergente).

**Recuperação.** Escreva em uma frase como um orquestrador reiniciado encontra seu trabalho. A resposta do TCM é um worker que seleciona sagas não terminais com deadline vencido usando `FOR UPDATE SKIP LOCKED` (o padrão de terça), para que dois workers nunca retomem a mesma saga, e então executa o passo correspondente ao estado atual da saga.

Um teste para o seu desenho: escolha qualquer seta, imagine que o processo morre no meio dela e siga o que o recovery worker faz. Se alguma seta leva a uma saga que nunca chega a um estado terminal, ou a um saldo que muda duas vezes, corrija o desenho antes de escrever o código.

## 7. Preparando o teste de caos

*Esta seção prepara o lab de hoje. Ela aplica o critério de aprovação do módulo.*

O lab de hoje é um plano, não código do TCM. Escreva o esqueleto de `chaos/kill-orchestrator.sh` como comentários e uma lista de tarefas:

1. Registrar o saldo total de todas as contas antes do teste.
2. Iniciar um fluxo constante de transferências, incluindo algumas feitas para falhar no crédito (uma conta encerrada, por exemplo).
3. Vinte vezes: esperar um intervalo aleatório, derrubar o container do orquestrador à força (`docker kill`, não uma parada graciosa) e subi-lo de novo.
4. Parar de enviar transferências e esperar o recovery worker esvaziar a fila.
5. Conferir que o saldo total é igual ao total inicial.
6. Conferir que nenhuma saga está em estado não terminal depois do seu deadline mais uma margem.
7. Sair com código diferente de zero se alguma checagem falhar, para o script poder rodar em CI.

Depois liste os casos de falha que você espera que o teste encontre, uma linha cada, usando a tabela de quedas da seção 1. Cada caso deve dizer em que estado a saga estava, o que o recovery worker vai fazer e qual idempotency key protege a repetição. Essa lista vira o plano de testes de sexta.

## O que anotar hoje

1. O que durable execution significa no Temporal: Event History, replay, e por que o código do workflow precisa ser determinístico.
2. Workflows versus Activities: qual dos dois chama `accounts`, e por que Activities devem ser idempotentes.
3. A retry policy padrão das Activities do Temporal e os quatro timeouts de Activity, mapeados para o seu TCM.
4. Step Functions Standard versus Express: semântica, duração máxima e base de preço.
5. Quando um motor de workflow vale o custo, e o que ele não resolve por você.
6. No papel: a máquina de estados da saga de transferência, com estados, transições, compensações e um timeout para cada estado não terminal.

## Teste-se

Estas perguntas dão bons flashcards (veja o [guia de flashcards](../../FLASHCARDS.pt-BR.md)).

- Por que o código de workflow do Temporal não pode chamar uma API HTTP diretamente?
- O que acontece com um workflow do Temporal quando o worker cai depois que uma Activity terminou?
- Qual timeout do Temporal faz um retry acontecer depois da queda de um worker, e por quê?
- Que semântica de execução os workflows Standard e Express do Step Functions oferecem?
- O "exactly once" do Step Functions dispensa idempotency keys na sua API? Por quê?
- Cite duas situações em que um motor de workflow durável vale o custo.
- Como um recovery worker evita que duas instâncias retomem a mesma saga?

## Referências

- **Fonte principal:** documentação do Temporal, ["What is Temporal?"](https://docs.temporal.io/temporal). Gratuito. Depois siga os links para ["Workflow Definition"](https://docs.temporal.io/workflow-definition) (determinismo e timers) e ["Activities"](https://docs.temporal.io/activities). Para retries e timeouts, leia ["Retry Policies"](https://docs.temporal.io/encyclopedia/retry-policies) e ["Detecting Activity failures"](https://docs.temporal.io/encyclopedia/detecting-activity-failures). Tudo gratuito.
- **Fonte principal:** AWS Step Functions Developer Guide, ["What is Step Functions?"](https://docs.aws.amazon.com/step-functions/latest/dg/welcome.html). Leia a página inteira, especialmente a comparação entre Standard e Express e os casos de uso. Gratuito.
- No papel: a máquina de estados da saga de transferência entre serviços, com estados, transições, compensações e timeouts por passo (seção 6).
