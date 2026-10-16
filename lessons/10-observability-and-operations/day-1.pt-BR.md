# Módulo 10, segunda-feira: sintomas, sinais de ouro, SLOs e alertas por burn rate

[Módulo 10](../../modules/10-observability-and-operations.pt-BR.md) · [Read in English](day-1.md)

**Tempo de leitura:** cerca de 45 minutos. Use o resto do bloco de 2 horas nas referências do final, começando pelo capítulo "Alerting on SLOs".

Este é um texto original escrito para este curso. Ele se baseia nas referências listadas no final, e cada seção indica a fonte que segue. Quando uma ideia ou um número vem de um autor específico, o texto diz isso.

## Por que isso importa para uma fintech

Em uma carteira digital, as piores falhas são silenciosas. Uma API de transferências que devolve HTTP 500 é percebida em minutos. Um worker que cobra alguns clientes duas vezes, ou um provedor que recusa em silêncio 30% dos pagamentos, pode rodar por horas até alguém abrir um chamado no suporte. A essa altura o dinheiro já se moveu, e cada hora soma estornos, chargebacks e mensagens irritadas.

O objetivo deste módulo é saber que o sistema está errado antes do cliente. Hoje você ganha o vocabulário e a matemática: o que observar (sintomas, sinais de ouro), o que significa "bom o suficiente" (SLIs, SLOs, error budget) e quando acordar um humano (alertas por burn rate). Na terça entram traces e métricas de negócio, e na quarta, o que acontece depois que o alerta dispara.

## 1. Vocabulário de monitoramento

*Fonte principal: livro de SRE do Google, capítulo 6, "Definitions" e "Why Monitor?".*

O livro de SRE define **monitoramento** como coletar, processar, agregar e exibir números em tempo real sobre um sistema. Depois divide o monitoramento em dois:

- **Monitoramento white-box** usa dados que o sistema expõe sobre o próprio funcionamento interno: métricas, logs, páginas internas de status. Seu serviço NestJS contando requisições por rota é white-box.
- **Monitoramento black-box** testa o comportamento por fora, do jeito que um usuário veria. Uma sonda que chama `POST /transfers` com uma conta de teste a cada minuto é black-box.

Mais dois termos importam. Um **dashboard** é uma visão resumida das métricas principais de um serviço. Um **alerta** é uma notificação feita para ser lida por um humano. O livro separa os alertas em tickets, alertas por e-mail e pages, e essa divisão é importante: um page interrompe alguém agora, talvez às 3 da manhã, enquanto um ticket pode esperar o horário comercial.

O capítulo também dá motivos para monitorar além de alertar: analisar tendências de longo prazo (com que velocidade a tabela do ledger está crescendo?), comparar antes e depois de uma mudança (o novo índice no Postgres ajudou?), montar dashboards e depurar. Para uma carteira digital você pode somar mais um: provar a um auditor ou ao banco parceiro que você sabe o que seu sistema fez.

## 2. Sintomas x causas

*Fonte principal: livro de SRE do Google, capítulo 6, "Symptoms Versus Causes" e "Black-Box Versus White-Box".*

A ideia central do capítulo cabe em uma frase: "Your monitoring system should address two questions: what's broken, and why?" (seu sistema de monitoramento deve responder a duas perguntas: o que está quebrado, e por quê?). O **sintoma** é o que está quebrado. A **causa** é o porquê. O livro chama isso de uma das distinções mais importantes para escrever um bom monitoramento.

Aqui está a mesma ideia com exemplos de carteira digital:

| Sintoma (o que o usuário sente) | Causa possível (por quê) |
| --- | --- |
| Transferências devolvem HTTP 500 | Pool de conexões do Postgres esgotado |
| Transferências levam 4 segundos | API do banco parceiro lenta, retries se acumulando |
| Mais pagamentos com cartão recusados que o normal | Provedor A rejeitando um certificado novo |
| Um cliente foi cobrado duas vezes | Consumer reprocessou uma mensagem do Kafka sem checar o inbox |
| Saldos parecem desatualizados no app | Réplica de leitura atrasada em relação ao primário |

Por que a distinção importa? Porque a lista de causas possíveis não tem fim, e a lista de sintomas que um usuário consegue sentir é curta. Se você dispara pages por causas ("CPU acima de 80%"), recebe pages por coisas que não machucam ninguém e perde falhas em que você não pensou. Se você dispara pages por sintomas ("transferências falhando"), cada page significa um problema real de usuário, e as causas viram as ferramentas que você usa para depurar.

O livro acrescenta uma nuance: o sintoma de uma pessoa é a causa de outra. Queries lentas no banco são causa para o time da API de transferências e sintoma para o time de banco de dados. Então cada camada observa os próprios sintomas.

Sobre black-box x white-box, a posição do livro é uma mistura: uso intenso de monitoramento white-box, mais um uso modesto, mas crítico, de black-box. O black-box é orientado a sintomas por natureza: só enxerga problemas que já estão acontecendo. O white-box deixa você ver problemas prestes a acontecer (uma fila que não para de crescer) e causas escondidas atrás de retries.

## 3. Os quatro sinais de ouro

*Fonte principal: livro de SRE do Google, capítulo 6, "The Four Golden Signals" e "Worrying About Your Tail".*

O livro diz que, se você só puder medir quatro métricas de um sistema voltado ao usuário, meça estas:

| Sinal | Ideia do livro | Exemplo na carteira digital |
| --- | --- | --- |
| **Latência** | O tempo para atender uma requisição | p99 de `POST /transfers` |
| **Tráfego** | Quanta demanda o sistema recebe | Transferências por segundo, pagamentos por provedor |
| **Erros** | A taxa de requisições que falham | Respostas 5xx, mais 200s com conteúdo errado |
| **Saturação** | O quão "cheio" o serviço está | Pool do banco em uso, consumer lag do Kafka, profundidade da fila do worker |

Três detalhes do capítulo merecem anotação.

**Separe a latência de sucessos e de falhas.** Uma requisição que falha rápido com 500 pode puxar a latência média para baixo e fazer tudo parecer melhor. O livro também observa que "a slow error is even worse than a fast error!" (um erro lento é ainda pior que um erro rápido). Então registre a latência com um label de resultado e olhe para os dois.

**Erros são mais do que status codes.** O livro conta falhas explícitas (HTTP 500), implícitas (um 200 com o conteúdo errado) e por política (uma requisição que você prometeu responder em um segundo e que levou mais). Em uma carteira digital, uma transferência que devolve 201 mas grava um posting desbalanceado é um erro, mesmo que nenhum status code diga isso.

**A saturação vem antes da falha.** O capítulo observa que muitos sistemas degradam antes de chegar a 100% de utilização, e que aumentos de latência costumam ser um indicador antecipado de saturação. Um pool do Postgres a 95% ainda não falha, mas toda requisição nova espera.

Depois o livro alerta contra médias. O exemplo dele: um serviço com 1.000 requisições por segundo e latência média de 100 ms pode facilmente ter 1% das requisições levando 5 segundos. Em uma carteira digital, esse 1% são 10 clientes por segundo olhando para um spinner, e alguns vão tocar em "pagar" de novo. A solução é registrar a latência como **histograma**: contar requisições em faixas de latência em vez de guardar uma média. As faixas do exemplo do livro são de 0 a 10 ms, de 10 a 30 ms, de 30 a 100 ms e assim por diante: limites que crescem de forma aproximadamente exponencial, em fatores de cerca de 3.

O capítulo termina com regras para pages que você vai reutilizar na quarta. Todo page deve ser acionável. Toda resposta a um page deve exigir inteligência (se um script resolve, automatize). Antes de criar um alerta, pergunte: é urgente, é acionável, significa com certeza que usuários estão sendo prejudicados?

## 4. SLIs, SLOs e SLAs

*Fonte principal: livro de SRE do Google, capítulo 4, "Service Level Terminology", "Indicators in Practice" e "Objectives in Practice".*

O livro define três termos que as pessoas costumam confundir:

- **SLI (service level indicator):** um número cuidadosamente definido que mede algum aspecto do serviço. Por exemplo, a fração de requisições de transferência que dão certo.
- **SLO (service level objective):** uma meta para um SLI. Por exemplo, "99,9% das requisições de transferência dão certo, medido em 30 dias".
- **SLA (service level agreement):** um contrato com os usuários que inclui consequências por não cumprir os SLOs. O livro dá um teste rápido: pergunte "o que acontece se os SLOs não forem cumpridos?". Se nada explícito acontece, é um SLO, não um SLA.

Em uma fintech, SLAs aparecem em contratos com lojistas ou com um banco parceiro. Seu time normalmente é dono dos SLOs, e o SLA deve ser mais folgado que o SLO interno para sobrar espaço para reagir. O livro recomenda exatamente essa margem de segurança.

**Escolhendo SLIs.** O livro sugere um punhado de indicadores representativos, não todas as métricas que você tem. Ele agrupa sistemas pelo que importa aos usuários: sistemas que servem usuários se importam com disponibilidade, latência e throughput; sistemas de armazenamento, com latência, disponibilidade e durabilidade; pipelines de big data, com throughput e latência ponta a ponta. Todo sistema deveria se importar com corretude. Para uma carteira digital, um primeiro conjunto razoável é:

| SLI | Evento bom | Evento válido |
| --- | --- | --- |
| Disponibilidade de transferências | Resposta que não é 5xx | Todo `POST /transfers` bem formado |
| Latência de transferências | Respondida em menos de 300 ms | Todo `POST /transfers` bem formado |
| Atualidade da liquidação | Pagamento sai de `PENDING` em até 10 minutos | Todo pagamento criado |

Escrever um SLI como "eventos bons divididos por eventos válidos" facilita calculá-lo a partir de contadores, e é a forma que o workbook usa para alertas.

**Percentis, não médias.** O livro diz que a maioria das métricas é mais bem pensada como distribuição do que como média. Por isso um SLO de latência se escreve "99% das requisições abaixo de 300 ms", e não "média abaixo de 300 ms".

**Escolhendo metas.** O conselho do livro, em resumo:

- Comece pelo que importa aos usuários, não pelo que é fácil de medir.
- Não escolha uma meta só porque ela é o seu desempenho atual.
- Mantenha simples, e tenha o menor número possível de SLOs.
- Evite absolutos. Ninguém consegue prometer 100%.
- A perfeição pode esperar: comece folgado e aperte depois, porque afrouxar uma meta da qual os usuários já dependem é mais difícil.

A história em destaque no capítulo sobre o Chubby, o serviço de locks do Google, mostra por que ser "confiável demais" é um risco. O Chubby era tão confiável que outros times passaram a supor que ele nunca falharia. A resposta do Google foi garantir que o Chubby global cumpra, mas não supere muito, o seu SLO, chegando a derrubá-lo de propósito em um trimestre sem quedas reais. Os usuários passam a depender da confiabilidade que você de fato entrega, não da que você prometeu.

## 5. Error budget

*Fonte principal: livro de SRE do Google, capítulo 4, "Defining Objectives"; Google SRE Workbook, "Alerting on SLOs".*

Se o SLO é 99,9% de sucesso, então 0,1% de falha é permitido. Essa margem é o **error budget**. O livro de SRE o apresenta como uma taxa em que os SLOs podem ser descumpridos, acompanhada diariamente ou semanalmente, e chama 100% de cumprimento de "unrealistic and undesirable" (irreal e indesejável). O workbook coloca em termos de contagem: o error budget dá o número de eventos ruins permitidos.

Um exemplo concreto. Sua carteira processa 2 milhões de transferências em 30 dias, com um SLO de disponibilidade de 99,9%. O error budget é 0,1% de 2.000.000, ou seja, 2.000 transferências com falha a cada 30 dias. Cada transferência com falha gasta uma unidade desse budget.

O budget transforma confiabilidade em regra de decisão. Se a maior parte do budget sobrou perto do fim do mês, o time pode publicar mudanças mais arriscadas. Se um deploy ruim queimou 80% dele em uma tarde, os releases desaceleram e o trabalho de confiabilidade sobe na prioridade. O livro descreve esse ciclo de controle na seção "Control Measures": medir o SLI, comparar com o SLO, decidir se é preciso agir, agir.

Há uma pegadinha de fintech. Nem toda falha é igual. Uma transferência que devolve 503 e recebe retry seguro com idempotency key custa alguns segundos ao cliente. Uma cobrança dupla custa dinheiro de verdade e confiança. Error budgets servem bem para disponibilidade e latência. Uma cobrança dupla não cabe neles: você nunca "orça" para ela. Na quarta você vai construir um detector separado para ela, com um limiar perto de zero.

## 6. Burn rate, e por que alertas simples falham

*Fonte principal: Google SRE Workbook, "Alerting on SLOs", seções "Alerting Considerations" e "Ways to Alert on Significant Events", abordagens 1 a 4.*

O workbook julga qualquer regra de alerta por quatro propriedades:

- **Precisão (precision):** a parcela dos alertas que corresponde a um evento significativo. Precisão baixa significa ruído.
- **Revocação (recall):** a parcela dos eventos significativos que gera um alerta. Recall baixo significa incidentes perdidos.
- **Tempo de detecção:** quanto tempo o alerta leva para disparar.
- **Tempo de reset:** quanto tempo ele continua disparando depois que o problema foi corrigido.

O conceito-chave é **burn rate**. O workbook o define como "how fast, relative to the SLO, the service consumes the error budget" (a velocidade, em relação ao SLO, com que o serviço consome o error budget). Um burn rate de 1 gasta o budget exatamente ao longo da janela do SLO. A tabela do workbook para um SLO de 99,9% em 30 dias:

| Burn rate | Taxa de erro | Budget esgotado em |
| --- | --- | --- |
| 1 | 0,1% | 30 dias |
| 2 | 0,2% | 15 dias |
| 10 | 1% | 3 dias |
| 1.000 | 100% | 43 minutos |

Depois o workbook percorre regras simples que parecem razoáveis e falham:

1. **Alertar quando a taxa de erro em 10 minutos for igual ou maior que o limite do SLO.** A detecção é rápida, mas a precisão é péssima. Uma taxa de erro de 0,1% por 10 minutos gasta só 0,02% do budget mensal, e mesmo assim dispara um page. O workbook conta até 144 alertas por dia com o SLO ainda sendo cumprido.
2. **Usar uma janela bem mais longa, como 36 horas.** A precisão melhora, mas o tempo de reset é terrível: depois de uma queda de 100%, o alerta continua disparando por 36 horas.
3. **Adicionar uma duração (`for: 1h`).** Agora uma queda total só gera page depois de uma hora, e uma taxa de erro oscilante que cai abaixo do limite fica zerando o timer e pode nunca gerar page. O workbook não recomenda durações em alertas de SLO.
4. **Alertar por burn rate em uma janela,** por exemplo burn rate de 36 em 1 hora (5% do budget). Melhor, mas um burn rate de 35 nunca alerta, mesmo gastando o budget inteiro em menos de um dia.

## 7. Alertas multijanela e multi-burn-rate

*Fonte principal: Google SRE Workbook, "Alerting on SLOs", abordagens 5 e 6 e "Low-Traffic Services and Error Budget Alerting".*

A resposta recomendada pelo workbook combina duas ideias.

**Vários burn rates.** Uma queima rápida e grave gera page logo. Uma queima lenta abre um ticket. O budget consumido quando um alerta dispara é burn rate × janela ÷ período do SLO. Com um período de 30 dias (720 horas), os pontos de partida do workbook para um SLO de 99,9% são:

| Severidade | Janela longa | Janela curta | Burn rate | Budget consumido |
| --- | --- | --- | --- | --- |
| Page | 1 hora | 5 minutos | 14,4 | 2% |
| Page | 6 horas | 30 minutos | 6 | 5% |
| Ticket | 3 dias | 6 horas | 1 | 10% |

Confira a primeira linha: 14,4 × 1 h ÷ 720 h = 2%. Nesse ritmo o budget inteiro dura 50 horas, então alguém precisa olhar agora.

**Uma janela curta para confirmar.** Só com a janela longa, o alerta continua disparando muito depois da recuperação. O workbook acrescenta uma janela curta e só dispara quando as duas janelas estão acima do limite. A orientação dele é "to make the short window 1/12 the duration of the long window" (fazer a janela curta ter 1/12 da duração da janela longa). Quando os erros param, a janela curta cai abaixo do limite em minutos e o alerta reseta.

No Prometheus, isso vira recording rules para a taxa de erro em cada janela, mais alertas que as combinam com `and`. Uma versão para a API de transferências, supondo um contador `transfer_requests_total` com um label `outcome`:

```yaml
groups:
  - name: transfers-slo
    rules:
      - record: transfers:error_ratio:rate5m
        expr: |
          sum(rate(transfer_requests_total{outcome="error"}[5m]))
          /
          sum(rate(transfer_requests_total[5m]))
      - record: transfers:error_ratio:rate1h
        expr: |
          sum(rate(transfer_requests_total{outcome="error"}[1h]))
          /
          sum(rate(transfer_requests_total[1h]))
      # ...o mesmo para 30m e 6h
      - alert: TransfersErrorBudgetFastBurn
        expr: |
          transfers:error_ratio:rate1h > (14.4 * 0.001)
          and
          transfers:error_ratio:rate5m > (14.4 * 0.001)
        labels:
          severity: page
        annotations:
          summary: "Transfers burning error budget 14.4x faster than allowed"
          runbook: "docs/runbooks/transfers-error-budget.md"
```

Os exemplos do próprio workbook usam a mesma estrutura com um par genérico `slo_errors` e `slo_requests`. Ele também mostra as regras de ticket com um par de 24 horas e 2 horas a 3x, ao lado do par de 3 dias a 1x. O custo dessa abordagem, como o workbook admite, é ter muitos parâmetros para gerenciar.

**Pouco tráfego.** O workbook avisa que essa matemática quebra com poucas requisições. Com 10 requisições por hora, uma falha é uma taxa de erro de 10% naquela hora, um burn rate de 1.000. As opções dele incluem tráfego sintético, agrupar serviços relacionados em um só SLO, retries com backoff no lado do cliente, e baixar o SLO ou alongar a janela. Seu TCM local tem pouquíssimo tráfego. Quando testar o alerta na quinta, gere carga com um script para que os números façam sentido.

**Daqui para o laboratório.** O laboratório de hoje instala o SDK do OpenTelemetry no NestJS e envia traces para o Jaeger, o que dá a visão por requisição. O alerta de SLO em si é o item 3 do TCM na quinta, depois que o laboratório de terça der a você o Prometheus. Escolha hoje seu SLI e seus eventos bons e válidos, para que na quinta reste só ligar os fios.

## O que anotar hoje

1. Uma tabela com 5 sintomas da carteira digital e 2 causas possíveis para cada, e os quatro sinais de ouro da API de transferências (qual métrica, qual unidade, qual label).
2. Um SLI e um SLO para o seu TCM: o evento bom, o evento válido, a meta, a janela e o error budget em número de requisições para um volume mensal realista.
3. A tabela de burn rate do seu SLO (2% em 1 hora, 5% em 6 horas, 10% em 3 dias), com as contas, e uma frase sobre por que a janela curta existe.

## Teste-se

Estas perguntas dão bons flashcards (veja o [guia de flashcards](../../FLASHCARDS.pt-BR.md)).

- Por que pages devem se basear em sintomas e não em causas?
- Cite os quatro sinais de ouro e uma métrica da carteira digital para cada.
- Qual é a diferença entre um SLO e um SLA, segundo o teste do "o que acontece se"?
- Seu SLO é 99,9% em 30 dias e você atende 2 milhões de requisições. Qual é o error budget?
- O que é um burn rate de 14,4, e quanto budget ele gasta em 1 hora?
- Por que adicionar `for: 1h` a um alerta de taxa de erro piora o recall e o tempo de detecção?
- Por que a abordagem multijanela usa uma janela curta de 1/12 da longa?

## Referências

- **Fonte principal:** Google, ["Site Reliability Engineering"](https://sre.google/sre-book/monitoring-distributed-systems/), capítulo 6 "Monitoring Distributed Systems", de Rob Ewaschuk. Leia inteiro, com foco em "Symptoms Versus Causes", "The Four Golden Signals" e "Worrying About Your Tail". Gratuito.
- Google, ["Site Reliability Engineering"](https://sre.google/sre-book/service-level-objectives/), capítulo 4 "Service Level Objectives". Leia "Service Level Terminology", "Indicators in Practice" e "Objectives in Practice". Gratuito.
- **Fonte principal:** Google, ["The Site Reliability Workbook"](https://sre.google/workbook/alerting-on-slos/), capítulo "Alerting on SLOs". Leia as seis abordagens, as tabelas de burn rate e "Low-Traffic Services and Error Budget Alerting". Gratuito.
