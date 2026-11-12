# Roteiro · M10 · Dia 3 · Incidentes, postmortems e o detector


## Abertura

Esta é a aula em vídeo do módulo dez, dia três: incidentes, postmortems e o detector de cobrança dupla.

Segunda e terça foram sobre saber que algo está errado. Hoje é sobre o que as pessoas fazem em seguida. Um alerta às três da manhã só é útil se quem recebe sabe o que checar, quem chamar e quando parar. E, depois, o time precisa aprender sem caçar culpados. O critério do módulo é que uma cobrança dupla injetada dispare um alerta sem ninguém olhando o dashboard. Por isso a aula termina com dois desenhos no papel: o detector, e o incidente que você vai injetar na sexta.


## Severidade

A PagerDuty define incidente como qualquer interrupção ou degradação não planejada que esteja afetando os clientes. E incidente grave é o que exige resposta coordenada entre vários times. Ela classifica de sev one, o mais grave, a sev five.

Sev one: crítico, justifica aviso público e envolvimento da diretoria. Na carteira, clientes cobrados duas vezes em escala.

Sev two: problema crítico para muitos clientes, como transferências falhando para todo mundo.

Sev three: impacto pequeno, mas exige atenção imediata. Um provedor recusando mais que o normal, com o fallback funcionando.

Sev four: menor, sem impacto no uso. Um pod do worker reiniciando em loop.

Sev five: cosmético, como um rótulo errado num dashboard interno.

Duas orientações para guardar. Na dúvida entre dois níveis, trate como o mais alto. E durante o incidente não é hora de discutir severidade: revise no postmortem. Torne os níveis guiados por métricas, e, numa carteira, some dinheiro: qualquer cobrança dupla confirmada é no mínimo sev two. Qualquer pessoa pode acionar o processo. Nunca hesite em acionar o I C.


## Papéis

A ideia dos papéis: quem conserta não deveria também coordenar, escrever atualizações e responder à diretoria.

O Incident Commander conduz o incidente até a resolução, é a fonte única da verdade, e delega todo o reparo.

O Deputy apoia o I C, acompanha o que está sendo esquecido, e é o I C reserva, em hot standby.

O Scribe escreve a linha do tempo: ações, descobertas, atualizações de status.

O S M E, subject matter expert, é dono de um serviço. Diagnostica, corrige, e reporta ao I C.

O Customer Liaison publica atualizações públicas, depois que o I C aprova.

E o Internal Liaison aciona mais pessoas quando o I C pede, e mantém os stakeholders internos informados.

A frase para lembrar: o Incident Commander não é quem resolve. O I C que começa a ler logs para de coordenar. E o S M E sugere correções ao I C, mas não executa nada sem ordem. Imagine um engenheiro reprocessando a dead-letter queue enquanto outro estorna duplicatas à mão. No seu T C M você faz todos os papéis, mas escreva a linha do tempo como um Scribe: ela vira o núcleo do postmortem.

> **Pausa:** Pergunta: por que o Incident Commander não deve ler logs e consertar?

Porque quem conserta para de coordenar. Ninguém percebe, por exemplo, que o Customer Liaison está esperando aprovação para publicar.


## Alertas e runbooks

A PagerDuty parte de uma definição rigorosa: um alerta é algo que exige que um humano execute uma ação. O resto é notificação, e não deveria acordar ninguém. Bate com a regra de segunda: todo page deve ser acionável.

Alertas têm urgência. Alta gera page vinte e quatro horas por dia. Média vai só em horário comercial. Baixa: alguém age em algum momento. E notificação não gera page, é só contexto.

Um alerta precisa conter: um título claro, a métrica que o disparou, o problema e por que importa, e um caminho de resolução.

Esse caminho são os passos para corrigir, ou um link para um runbook. Sem nenhum dos dois, nas palavras da PagerDuty, o alerta é inútil.

E uma regra para sexta: um alerta não testado equivale a não ter alerta. Teste os limiares, faça a falta de dados disparar um alerta, porque falta de dados geralmente significa que algo quebrou, e verifique que o alerta se resolve sozinho.


## Runbook

O runbook é a página que o plantão abre quando o alerta dispara. A PagerDuty exige o link, mas não define o formato. Esta é a estrutura do curso.

Primeiro, o que o alerta significa, em palavras simples: pelo menos um pagamento tem dois postings de captura no ledger.

Impacto: clientes perdem dinheiro até serem estornados. Trate como sev two ou mais alto.

Primeiras checagens, em cinco minutos, com queries exatas e links de dashboards. É um pagamento ou muitos? Um provedor ou todos? Houve deploy na última hora?

Estancar o sangramento: a ação mais segura que impede novos danos. Pausar o consumer group do worker, ou desligar o provedor com uma feature flag. E diga quanto isso custa.

Corrigir o dano: listar os pagamentos afetados e revertê-los pelo ledger, com lançamentos de estorno. Nunca apagando linhas.

Escalonamento: se mais de dez clientes forem afetados, acione o I C. E encerramento: o detector em zero por trinta minutos, e a conciliação limpa.

> **Pausa:** Pergunta: por que corrigir com estornos no ledger, e não apagando as linhas duplicadas?

Porque o ledger é imutável: apagar destrói a trilha de auditoria. O estorno corrige o saldo e preserva a história do que aconteceu.


## Postmortem sem culpados

O livro de S R E define postmortem como um registro escrito do incidente: impacto, ações para mitigar, causas raiz, e ações para não repetir. Escreva quando há degradação visível acima de um limite, perda de dados, intervenção do plantão, como um rollback, resolução demorada, ou falha de monitoramento, quando um humano descobriu à mão. Defina os critérios antes. E na carteira: qualquer movimentação incorreta de dinheiro de cliente, de qualquer tamanho. O princípio é ser sem culpados, ideia que vem da saúde e da aviação. Todos agiram com boa intenção e com a informação que tinham. Se as pessoas são punidas, param de reportar, e os problemas crescem escondidos.

Veja a versão com culpado: a Ana fez deploy de um consumer sem a checagem do inbox e causou trezentas cobranças duplas.

E a versão sem culpado: o consumer foi para produção sem a checagem do inbox. Nenhum teste cobria reentrega. O checklist de revisão não mencionava idempotência. E o detector gerou page quatro minutos depois da primeira duplicata.

A segunda tem mais informação, e cada frase leva a uma ação: um teste de reentrega, uma linha no checklist, um detector mais rápido. A versão curta do capítulo: você não consegue consertar pessoas, mas consegue consertar sistemas e processos.

> **Pausa:** Pergunta: por que punir quem causou o incidente piora a confiabilidade?

Porque as pessoas param de reportar incidentes, e os problemas ficam escondidos até ficarem maiores.


## Processo do postmortem

O processo da PagerDuty acrescenta passos concretos.

O postmortem é obrigatório para todo incidente grave, sev one e sev two. No fim do incidente, o I C designa um dono, que escreve e conduz a investigação.

A reunião acontece em até três dias corridos para sev one, e cinco dias úteis para sev two.

O dono começa pela linha do tempo, e cada item tem uma fonte: uma métrica, um gráfico, uma busca de logs. A análise inclui as queries usadas, e os tickets se limitam ao que é de alta prioridade.

O livro de S R E pede revisão por engenheiros seniores: os dados foram coletados? O impacto está completo? A causa raiz foi fundo? O plano de ação é adequado? Foi compartilhado? E diz: um postmortem não revisado é como se nunca tivesse existido. Culturas fortes fazem o postmortem do mês, clubes de leitura, e a wheel of misfortune, reencenando um incidente antigo.

Para o seu docs m10: resumo, impacto em clientes, valor e duração, linha do tempo com fontes, como foi detectado, causa raiz, o que deu certo e errado, e ações com um dono cada. As entradas mais importantes: primeira duplicata gravada, e alerta disparou. A diferença é o seu tempo de detecção.


## O detector

Agora o desenho do detector. Primeiro, defina com precisão o que é cobrança dupla. Há dois tipos, com detectores diferentes.

A duplicata dura: um pagamento com mais de um posting de captura no ledger. Isso é sempre bug: a idempotency key ou o inbox falhou. Nada legítimo produz isso, então o limiar é zero. A query agrupa as capturas dos últimos quinze minutos por payment I D, com count maior que um. Mais de zero linhas: page, sev two ou mais alto.

A duplicata leve: dois pagamentos diferentes, mesmo cliente, lojista e valor, com menos de dois minutos entre eles. O cliente tocou em pagar duas vezes, e nasceram duas chaves. Algumas são legítimas, dois cafés, então o sinal é uma razão: suspeitas sobre o total de capturas, acima da sua linha de base. Gera ticket, ou page se muito acima, e é sev three até confirmar.

Por que quinze minutos? A janela precisa ser maior que o intervalo do job somado ao atraso do caminho mais lento, como uma reentrega do Kafka depois de um restart do consumer. E curta o bastante para disparar antes de amanhecer. As duas queries precisam de um índice que comece por created at, ou vão varrer a tabela a cada minuto. Esses números são um ponto de partida: anote o seu raciocínio.

> **Pausa:** Pergunta: por que a duplicata dura tem limiar zero e a leve não?

Porque nada legítimo captura o mesmo pagamento duas vezes. Já dois pagamentos iguais e próximos podem ser dois cafés de verdade.


## Do banco ao page

Para levar ao Prometheus, um job pequeno roda as duas queries a cada minuto e preenche gauges: duplicatas duras e a razão de duplicatas leves. A primeira regra: double charge detected, se as duplicatas duras passam de zero, com severidade page e o link do runbook.

O job também preenche o timestamp da última execução bem-sucedida, o conselho de batch job de terça.

As outras duas regras seguem o conselho de No Data. Detector stale: o último sucesso tem mais de cinco minutos. Detector missing: a métrica nem existe. Um detector que parou não reporta nada, e nada parece exatamente nenhuma cobrança dupla. Sem essas regras, um job caído dá um dashboard verde durante o pior incidente do ano.

E a resposta ao teste de domínio: se dois por cento dos pagamentos fossem cobrados duas vezes, o gauge ficaria muito acima de zero em um intervalo do job, e o page dispararia sem ninguém olhando. A conciliação contra o arquivo do provedor, do módulo sete, é a segunda linha de defesa, mas só uma vez por dia.

> **Pausa:** Pergunta: por que alertar quando a métrica do detector está ausente?

Porque um detector caído não reporta nada, e nada parece zero duplicatas. Sem essa regra, o dashboard fica verde no pior momento.


## Game day da sexta

Na sexta você vai quebrar o próprio sistema de propósito. Planeje hoje, no papel, como um game day.

A falha: um jeito realista de criar uma duplicata dura. Uma flag que pula a checagem do inbox, e depois republicar uma mensagem do Kafka já processada. Ou chamar a captura duas vezes num script. Não edite linhas à mão no banco: o caminho real do código precisa gravar a duplicata.

A detecção esperada: com o job a cada minuto e as regras avaliadas a cada quinze segundos, o page chega em cerca de dois minutos. Some o agrupamento do Alertmanager, que você configura no lab de hoje.

As evidências: o horário da injeção, o horário do alerta, a notificação do Alertmanager, o trace do processamento duplicado no Jaeger, e a saída da query.

A recuperação: desligue a falha, reverta a duplicata pelo ledger, e confirme que o alerta se resolve sozinho.

E o relato: o postmortem em docs m10, com o seu tempo de detecção como um número.


## Revisão relâmpago

Hora da revisão relâmpago. Três perguntas, sem olhar.

> **Pausa:** Pergunta um: em dúvida entre sev two e sev three, qual você declara?

Sev two, o mais alto. Durante o incidente não se discute severidade: revise no postmortem.

> **Pausa:** Pergunta dois: o que um alerta precisa ter para não ser inútil?

Um caminho de resolução: os passos para corrigir, ou o link para um runbook. Além de título, métrica e por que importa.

> **Pausa:** Pergunta três: por que o detector de cobrança dupla tem três regras de alerta?

Uma para duplicatas, e duas para o próprio detector: parado e ausente. Sem elas, um job caído parece zero cobranças duplas.


## O que anotar e próximo passo

Anote com as suas palavras: os seis papéis em uma linha cada, e quais você fará. O seu roteiro de postmortem, com uma frase reescrita sem culpado. O detector no papel, com queries, janela, limiar, gauges e as regras de detector parado e ausente. E o incidente que vai injetar, com o tempo de detecção esperado.

Depois, no lab, instale o Alertmanager no Compose, e garanta que ele entregue em algum lugar que você vai mesmo ver. Até a próxima aula.
