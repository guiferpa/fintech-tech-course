# Módulo 10, quarta-feira: incidentes, runbooks, postmortems e o detector de cobrança dupla

[Módulo 10](../../modules/10-observability-and-operations.pt-BR.md) · [Read in English](day-3.md)

**Tempo de leitura:** cerca de 45 minutos. Use o resto do bloco de 2 horas nas referências do final e depois desenhe no papel o detector de cobrança dupla, como descrito nas seções 6 e 7.

Este é um texto original escrito para este curso. Ele se baseia nas referências listadas no final, e cada seção indica a fonte que segue.

## Por que isso importa para uma fintech

Segunda e terça foram sobre saber que algo está errado. Hoje é sobre o que as pessoas fazem em seguida. Um alerta às 3 da manhã só é útil se quem o recebe sabe o que checar, quem chamar e quando parar. E, quando o incidente acaba, o time precisa aprender com ele sem transformá-lo em uma caça ao culpado.

Para uma carteira digital, o incidente que mais importa nesta semana é a cobrança dupla. O critério de aprovação do módulo é que uma cobrança dupla injetada dispare um alerta sem ninguém olhando o dashboard. Por isso hoje termina com dois desenhos no papel: o detector (query, janela, limiar) e o incidente que você vai injetar na sexta para provar que ele funciona.

## 1. O que é um incidente, e quão grave ele é

*Fonte principal: documentação de Incident Response da PagerDuty, "What is an Incident?" e "Severity Levels".*

A documentação da PagerDuty é uma versão pública do processo que a empresa usa internamente para incidentes graves. Ela define um incidente como "Any unplanned disruption or degradation of service that is actively affecting customers ability to use PagerDuty." (qualquer interrupção ou degradação não planejada do serviço que esteja afetando ativamente a capacidade dos clientes de usar a PagerDuty). Troque "PagerDuty" pela sua carteira digital e você tem uma definição que funciona. Ela também define um **incidente grave** (major incident) como aquele que exige uma resposta coordenada entre vários times.

A PagerDuty classifica incidentes de SEV-1 (o mais grave) a SEV-5:

| Nível | Descrição da PagerDuty, em resumo | Exemplo na carteira digital |
| --- | --- | --- |
| SEV-1 | Crítico; justifica aviso público e envolvimento da diretoria | Clientes cobrados duas vezes em escala |
| SEV-2 | Problema crítico afetando muitos clientes | Transferências falhando para todo mundo |
| SEV-3 | Problema de estabilidade ou impacto pequeno no cliente, exige atenção imediata | Um provedor recusando mais que o normal, com fallback funcionando |
| SEV-4 | Problema menor, sem impacto no uso do produto | Um pod do worker reiniciando em loop |
| SEV-5 | Problema cosmético ou bug | Rótulo errado em um dashboard interno |

Duas orientações dessa página merecem ser guardadas. Se estiver em dúvida entre dois níveis, trate como o mais alto. E durante um incidente não é hora de discutir severidade: assuma o nível mais alto e revise no postmortem. A PagerDuty também recomenda que cada organização torne seus níveis específicos e guiados por métricas, normalmente pela parcela de clientes afetados. Para uma carteira digital, você pode somar dinheiro: "qualquer cobrança dupla confirmada é no mínimo SEV-2" é uma regra clara.

A mesma documentação diz que qualquer pessoa pode acionar o processo de incidente, e que não é preciso definir uma severidade antes de começar. Na página "During an Incident", ela acrescenta: "Never hesitate to page the IC." (nunca hesite em acionar o IC).

## 2. Papéis durante um incidente

*Fonte principal: documentação de Incident Response da PagerDuty, "Different Roles" e "During an Incident".*

A ideia por trás dos papéis num incidente é que quem está consertando o problema não deveria também estar coordenando, escrevendo atualizações e respondendo à diretoria. A PagerDuty separa essas funções:

| Papel | O que a PagerDuty diz que ele faz |
| --- | --- |
| **Incident Commander (IC)** | Conduz o incidente até a resolução e é a fonte única da verdade sobre o que está acontecendo. Delega todo o trabalho de reparo. |
| **Deputy** | Apoia o IC, acompanha o que está sendo esquecido e atua como IC reserva pronto para assumir (hot standby). |
| **Scribe** | Escreve a linha do tempo conforme o incidente avança: ações, descobertas, atualizações de status. |
| **Subject Matter Expert (SME)** | Dono de um serviço. Diagnostica e corrige, e reporta ao IC. |
| **Customer Liaison** | Escreve e publica atualizações públicas depois que o IC as aprova. |
| **Internal Liaison** | Aciona mais pessoas quando o IC pede e mantém os stakeholders internos informados. |

A frase da página de papéis para lembrar é: "Delegate all repair actions, the Incident Commander is NOT a resolver." (delegue todas as ações de reparo, o Incident Commander NÃO é quem resolve). O IC que começa a ler logs para de coordenar, e ninguém percebe que o Customer Liaison está esperando aprovação para publicar uma atualização.

O papel de SME tem sua própria regra em "During an Incident": compartilhe suas sugestões de correção com o IC, mas "do not follow any actions unless told to do so!" (não execute nenhuma ação a menos que mandem). Dois engenheiros aplicando correções sem relação ao mesmo tempo deixam o incidente mais difícil de entender. Em uma carteira digital, imagine um engenheiro reprocessando a dead-letter queue enquanto outro estorna duplicatas à mão.

Em um time pequeno, uma pessoa pode acumular vários papéis. A PagerDuty menciona o Deputy atuando também como Scribe e Internal Liaison em incidentes menores. No seu TCM você está sozinho, então vai fazer todos. Mesmo assim, escreva a linha do tempo como um Scribe faria: essa linha do tempo vira o núcleo do seu postmortem.

## 3. Alertas que levam a algum lugar: runbooks

*Fonte principal: documentação de Incident Response da PagerDuty, "Alerting Principles". O modelo de runbook é deste curso.*

A página de alertas da PagerDuty parte de uma definição rigorosa: "An alert is something which requires a human to perform an action." (um alerta é algo que exige que um humano execute uma ação). Todo o resto é notificação e não deveria acordar ninguém. Isso bate com a regra de segunda, do livro de SRE, de que todo page deve ser acionável.

A página classifica alertas por urgência:

- **Alta:** gera page 24/7 e exige ação imediata.
- **Média:** prioridade alta, mas enviado só em horário comercial.
- **Baixa:** alguém deve agir em algum momento, sem urgência.
- **Notificação:** nenhum page, só contexto para depois.

Depois ela diz o que um alerta precisa conter: um título claro, a métrica que o disparou, uma descrição do problema e de por que ele importa, e um caminho de resolução. O caminho de resolução é ou os passos para corrigir, ou um link para um **runbook**. O veredito da PagerDuty sobre alertas sem nenhum dos dois: "Alerts with neither of these things are useless." (alertas sem nenhuma dessas coisas são inúteis).

Um runbook é a página que a pessoa de plantão abre quando o alerta dispara. A documentação da PagerDuty exige o link mas não define um formato, então aqui vai uma estrutura para este curso. Ela funciona bem para uma cobrança dupla:

1. **O que este alerta significa.** Um parágrafo, em palavras simples. "Pelo menos um pagamento tem dois postings de captura no ledger."
2. **Impacto.** Quem é prejudicado e como. "Clientes perdem dinheiro até serem estornados. Trate como SEV-2 ou mais alto."
3. **Primeiras checagens (5 minutos).** Queries exatas e links de dashboards. É um pagamento ou muitos? Um provedor ou todos? Houve deploy na última hora?
4. **Estancar o sangramento.** A ação mais segura que impede novos danos, por exemplo pausar o consumer group do worker de pagamentos, ou desligar o provedor com uma feature flag. Diga quanto isso custa.
5. **Corrigir o dano.** Como listar os pagamentos afetados e como revertê-los pelo ledger (lançamentos de estorno, nunca apagando linhas).
6. **Escalonamento.** Quem acionar, e quando. "Se mais de 10 clientes forem afetados, acione o IC."
7. **Encerramento.** Como confirmar que acabou: detector em zero por 30 minutos, conciliação limpa.

A mesma página termina com uma regra que você vai aplicar na sexta: "An untested alert is equivalent to not having an alert at all." (um alerta não testado equivale a não ter alerta nenhum). Ela pede que você teste os limiares, que faça "No Data" disparar um alerta quando fizer sentido (falta de dados geralmente significa que algo quebrou) e que verifique se o alerta se resolve sozinho quando a métrica volta ao normal.

## 4. Postmortems sem culpados

*Fonte principal: livro de SRE do Google, capítulo 15, "Postmortem Culture: Learning from Failure".*

O livro de SRE define um **postmortem** como um registro escrito de um incidente: seu impacto, as ações tomadas para mitigá-lo ou resolvê-lo, as causas raiz e as ações de acompanhamento para evitar que ele se repita.

**Quando escrever um.** O livro lista gatilhos comuns. Entre eles: indisponibilidade ou degradação visível ao usuário acima de um limite, perda de dados de qualquer tipo, intervenção do plantão como um rollback ou um redirecionamento de tráfego, tempo de resolução acima de um limite, e uma falha de monitoramento, o que normalmente significa que um humano descobriu o incidente à mão. O livro reforça que esses critérios devem ser definidos antes de um incidente acontecer. Para uma carteira digital, acrescente um gatilho seu: qualquer movimentação incorreta de dinheiro de cliente, de qualquer tamanho.

**Sem culpados (blameless).** O livro afirma que postmortems sem culpados são um princípio da cultura de SRE, e observa que a ideia vem da saúde e da aviação, onde erros podem ser fatais. Um postmortem sem culpados supõe que todos agiram com boas intenções e com a informação que tinham no momento. Ele foca nas causas que contribuíram, não em quem errou. O raciocínio é prático: se as pessoas são punidas por incidentes, elas param de reportá-los, e os problemas ficam escondidos até ficarem maiores. A versão mais curta do capítulo é: "You can't 'fix' people, but you can fix systems and processes to better support people making the right choices when designing and maintaining complex systems." (você não consegue "consertar" pessoas, mas consegue consertar sistemas e processos para apoiar melhor as pessoas a fazerem as escolhas certas ao projetar e manter sistemas complexos).

Veja a diferença em um exemplo da carteira digital:

- Com culpado: "A Ana fez deploy de um consumer sem a checagem do inbox e causou 300 cobranças duplas."
- Sem culpado: "O consumer foi para produção sem a checagem do inbox. Nenhum teste cobria reentrega, e o checklist de revisão não mencionava idempotência. O detector gerou page 4 minutos depois da primeira duplicata."

A segunda versão tem mais informação, e cada frase leva a uma ação: um teste de reentrega, uma linha no checklist, um detector mais rápido.

**Revisão e compartilhamento.** O livro diz que um postmortem é revisado por engenheiros seniores antes de ser publicado. Os critérios de revisão incluem se os dados principais foram coletados, se a avaliação de impacto está completa, se a análise de causa raiz foi fundo o bastante, se o plano de ação e as prioridades dos bugs são adequados, e se o resultado foi compartilhado com os stakeholders. A frase direta dele: "An unreviewed postmortem might as well never have existed." (um postmortem não revisado é como se nunca tivesse existido).

**Construindo a cultura.** O capítulo descreve atividades como o postmortem do mês compartilhado em uma newsletter, clubes de leitura de postmortems e a "Wheel of Misfortune", em que um postmortem antigo é reencenado com engenheiros fazendo os papéis. Em entrevistas, conseguir descrever um postmortem sem culpados que você escreveu é um sinal forte de senioridade.

## 5. O processo de postmortem na prática

*Fonte principal: documentação de Incident Response da PagerDuty, "Postmortem Process".*

O processo da PagerDuty acrescenta passos concretos que combinam bem com a cultura do livro de SRE:

- Um postmortem é obrigatório para todo incidente grave (SEV-2 e SEV-1).
- O IC designa um **dono** no fim do incidente. O dono escreve o documento e conduz a investigação.
- A reunião acontece em até 3 dias corridos para SEV-1 e em até 5 dias úteis para SEV-2.
- O dono começa pela **linha do tempo**, e cada item dela tem uma fonte: uma métrica, um gráfico ou uma busca de logs.
- A análise cobre a causa, a causa subjacente e os clientes afetados, e inclui as queries e comandos usados.
- Os tickets de acompanhamento se limitam a itens de alta prioridade, e o time aceita trade-offs quando o retorno não justifica o esforço.

Para o item 6 do TCM, um postmortem curto em `docs/m10.md` pode seguir este roteiro: resumo, impacto (clientes, valor, duração), linha do tempo com fontes, como foi detectado, causa raiz e fatores que contribuíram, o que deu certo, o que deu errado, ações com um dono cada. As entradas mais importantes da linha do tempo neste módulo são "primeira duplicata gravada" e "alerta disparou": a diferença entre elas é o seu tempo de detecção.

## 6. Desenhando o detector de cobrança dupla

*Esta seção é o desenho deste curso para o TCM. Ela aplica as regras de segunda (alertar por sintomas, todo page acionável) e os conselhos de métricas de terça.*

Primeiro, defina com precisão o que é uma cobrança dupla na sua carteira. Há dois tipos, e eles precisam de detectores diferentes.

**Duplicata dura (hard).** Um pagamento tem mais de um posting de captura no ledger. Isso é sempre um bug: a idempotency key ou o inbox falhou. Nada legítimo produz isso, então o limiar é zero.

```sql
-- Duplicatas duras: pagamentos capturados mais de uma vez nos últimos 15 minutos
SELECT payment_id, count(*) AS captures
FROM ledger_entries
WHERE kind = 'CAPTURE'
  AND created_at > now() - interval '15 minutes'
GROUP BY payment_id
HAVING count(*) > 1;
```

**Duplicata leve (soft).** Dois pagamentos diferentes com o mesmo cliente, lojista e valor, com pouco tempo entre eles. É o caso em que o cliente tocou em "pagar" duas vezes e duas idempotency keys foram criadas, ou um cliente fez retry sem reutilizar a chave. Algumas são legítimas (dois cafés), então o sinal é uma razão, não uma linha isolada.

```sql
-- Duplicatas leves: mesmo cliente, lojista e valor em até 2 minutos
SELECT count(*) AS suspicious
FROM (
  SELECT created_at,
         lag(created_at) OVER (
           PARTITION BY customer_id, merchant_id, amount_cents
           ORDER BY created_at
         ) AS prev_at
  FROM payments
  WHERE status = 'CAPTURED'
    AND created_at > now() - interval '15 minutes'
) p
WHERE created_at - prev_at < interval '2 minutes';
```

Adapte os nomes de tabelas e colunas ao seu schema. As duas queries precisam de um índice que comece por `created_at`, ou vão varrer a tabela a cada minuto.

Agora as três decisões que o módulo pede:

| | Duplicata dura | Duplicata leve |
| --- | --- | --- |
| **Query** | Capturas por `payment_id` | Mesmo cliente, lojista e valor em até 2 minutos |
| **Janela** | Últimos 15 minutos, rodando a cada minuto | Últimos 15 minutos, rodando a cada minuto |
| **Limiar** | Mais de 0 linhas: page | Razão entre suspeitas e total de capturas acima da sua linha de base normal: ticket, ou page se muito acima |
| **Severidade** | SEV-2 ou mais alto | SEV-3 até confirmar |

Por que 15 minutos? A janela precisa ser maior que o intervalo do job somado ao atraso do caminho mais lento (uma reentrega do Kafka depois de um restart do consumer pode levar minutos), e curta o bastante para o alerta disparar antes de amanhecer. Anote o seu próprio raciocínio. Os números acima são um ponto de partida, não uma regra das referências.

Para levar o resultado ao Prometheus, um job pequeno roda as duas queries a cada minuto e preenche dois gauges, por exemplo `wallet_hard_duplicate_captures` e `wallet_soft_duplicate_ratio`. Ele também preenche um gauge com o timestamp Unix da sua última execução bem-sucedida, seguindo o conselho de batch job de terça. Depois, três regras de alerta:

```yaml
- alert: DoubleChargeDetected
  expr: wallet_hard_duplicate_captures > 0
  labels:
    severity: page
  annotations:
    summary: "{{ $value }} payments captured more than once in 15 minutes"
    runbook: "docs/runbooks/double-charge.md"
- alert: DoubleChargeDetectorStale
  expr: time() - wallet_duplicate_detector_last_success_timestamp_seconds > 300
  labels:
    severity: page
- alert: DoubleChargeDetectorMissing
  expr: absent(wallet_hard_duplicate_captures)
  labels:
    severity: page
```

As duas últimas seguem o conselho de "No Data" da PagerDuty. Um detector que parou de rodar não reporta nada, e "nada" parece exatamente "nenhuma cobrança dupla". Sem essas regras, um job caído dá a você um dashboard verde durante o pior incidente do ano.

Essa também é a resposta à pergunta do teste de domínio. Se 2% dos pagamentos fossem cobrados duas vezes, o gauge de duplicatas duras ficaria muito acima de zero em um intervalo do job, e o page dispararia sem ninguém olhando. A conciliação contra o arquivo do provedor (Módulo 7) é a segunda linha de defesa: ela pega duplicatas que aconteceram fora do seu ledger, mas só uma vez por dia.

## 7. Planejando o incidente que você vai injetar

*Esta seção é o plano deste curso para os itens 4 e 5 do TCM, seguindo a regra da PagerDuty de que um alerta não testado não é alerta.*

Na sexta você vai quebrar o próprio sistema de propósito e verificar que o alerta dispara. Planeje no papel hoje, como se planeja um game day.

1. **A falha.** Escolha um jeito realista de criar uma duplicata dura. Boas opções: uma flag que pula a checagem do inbox no consumer, seguida da republicação de uma mensagem do Kafka já processada; ou chamar o passo de captura duas vezes para o mesmo pagamento em um script de teste. Não edite linhas à mão no banco: você quer que o caminho real do código grave a duplicata.
2. **A detecção esperada.** Anote quando o alerta deveria disparar. Se o job roda a cada minuto e o Prometheus avalia as regras a cada 15 segundos, o page deveria chegar em cerca de 2 minutos. As configurações de agrupamento do Alertmanager, que você vai configurar no laboratório de hoje, também somam atraso, então inclua-as.
3. **As evidências.** Liste o que você vai registrar: o horário da injeção, o horário em que o alerta disparou, a notificação do Alertmanager, o trace do processamento duplicado no Jaeger e a saída da query do detector.
4. **A recuperação.** Desligue a falha, reverta a duplicata pelo ledger e confirme que o alerta se resolve sozinho.
5. **O relato.** Use as evidências para escrever o postmortem em `docs/m10.md`, com o seu tempo de detecção como um número.

O laboratório de hoje instala o Alertmanager no Compose e produz a lista de tarefas de quinta e sexta. Nada de código do TCM hoje. Garanta que o Alertmanager consiga entregar em algum lugar que você vai mesmo ver (um receptor de webhook ou um log local bastam), já que o critério de aprovação é que ninguém esteja olhando o dashboard.

## O que anotar hoje

1. Os seis papéis num incidente da PagerDuty em uma linha cada, e quais deles você vai fazer no incidente do seu TCM.
2. O roteiro de postmortem que você vai usar no `docs/m10.md`, com os gatilhos e os critérios de revisão do livro de SRE, e uma frase com culpado reescrita sem culpado.
3. O detector de cobrança dupla no papel: as queries dura e leve, a janela, o limiar e a severidade de cada uma, os gauges e as regras de alerta, e as regras para detector ausente ou parado.
4. O incidente que você vai injetar: a falha, como vai dispará-la, o tempo de detecção esperado, as evidências a coletar e os passos de recuperação.

## Teste-se

Estas perguntas dão bons flashcards (veja o [guia de flashcards](../../FLASHCARDS.pt-BR.md)).

- Qual é a regra da PagerDuty quando você está em dúvida entre dois níveis de severidade?
- Por que o Incident Commander "NÃO é quem resolve"?
- O que todo alerta precisa conter, segundo os princípios de alerta da PagerDuty?
- Cite três gatilhos de postmortem do livro de SRE.
- O que torna um postmortem sem culpados, e por que a culpa deixa os sistemas menos confiáveis?
- Qual é a diferença entre uma cobrança dupla dura e uma leve, e por que cada uma precisa de um limiar diferente?
- Por que você precisa de um alerta para um detector ausente ou parado?

## Referências

- **Fonte principal:** Google, ["Site Reliability Engineering"](https://sre.google/sre-book/postmortem-culture/), capítulo 15 "Postmortem Culture: Learning from Failure". Leia inteiro. Gratuito.
- **Fonte principal:** PagerDuty, ["Incident Response documentation"](https://response.pagerduty.com/). Leia "What is an Incident?", "Severity Levels", "Different Roles" e "During an Incident", nas partes "Before" e "During", mais ["Alerting Principles"](https://response.pagerduty.com/oncall/alerting_principles/) e o ["Postmortem Process"](https://response.pagerduty.com/after/post_mortem_process/). Gratuito.
