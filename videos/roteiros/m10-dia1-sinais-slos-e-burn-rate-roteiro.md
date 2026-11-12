# Roteiro · M10 · Dia 1 · Sinais, SLOs e burn rate


## Abertura

Esta é a aula em vídeo do módulo dez, dia um: sinais de ouro, SLOs e alertas por burn rate.

Numa carteira, as piores falhas são silenciosas. Uma API que devolve 500 é percebida em minutos. Um worker que cobra alguns clientes duas vezes, ou um provedor que recusa em silêncio trinta por cento dos pagamentos, roda por horas até alguém abrir um chamado. A essa altura, o dinheiro já se moveu. O objetivo do módulo é saber que o sistema está errado antes do cliente. Hoje: o que observar, o que é bom o suficiente, e quando acordar um humano.


## Vocabulário

O livro de S R E do Google define monitoramento como coletar, processar, agregar e exibir números em tempo real sobre um sistema. E divide em dois.

Monitoramento white-box usa dados que o sistema expõe sobre o próprio funcionamento: métricas, logs, páginas de status. Seu serviço contando requisições por rota é white-box. Ele vê problemas prestes a acontecer, como uma fila que não para de crescer.

Monitoramento black-box testa por fora, como o usuário: uma sonda que chama a API de transferência com uma conta de teste a cada minuto. Só vê o que já está acontecendo. A posição do livro: uso intenso de white-box, e um uso modesto, mas crítico, de black-box.

E um alerta é uma notificação feita para um humano ler. O livro separa tickets, e-mails e pages. Um page interrompe alguém agora, talvez às três da manhã. Um ticket espera o horário comercial.


## Sintomas x causas

A ideia central: seu monitoramento responde duas perguntas. O que está quebrado, e por quê. O que está quebrado é o sintoma. O porquê é a causa.

Transferências devolvem 500: a causa pode ser o pool do Postgres esgotado.

Transferências levam quatro segundos: banco parceiro lento, com retries se acumulando.

Mais cartões recusados que o normal: o provedor rejeitando um certificado novo.

Um cliente cobrado duas vezes: um consumer reprocessou uma mensagem do Kafka sem checar o inbox.

Saldos desatualizados: a réplica de leitura está atrasada.

Por que importa? A lista de causas não tem fim, e a de sintomas é curta. Page por causa, como CPU acima de oitenta por cento, acorda à toa e perde falhas em que você não pensou. Page por sintoma garante que cada page é um problema real, e as causas viram ferramentas de depuração. E o sintoma de um time é a causa de outro: queries lentas são causa para a API, e sintoma para o time de banco.

> **Pausa:** Pergunta: CPU a noventa por cento deve gerar um page?

Não, sozinha não. É uma causa possível. O page deve vir do sintoma, como transferências falhando ou lentas para o usuário.


## Sinais de ouro

Se você só puder medir quatro coisas de um sistema voltado ao usuário, meça estas.

Latência: o tempo de resposta, como o P 99 da API de transferência. E separe sucessos de falhas: um 500 rápido puxa a média para baixo e faz tudo parecer melhor. E um erro lento é ainda pior que um rápido.

Tráfego: transferências por segundo, pagamentos por provedor.

Erros: mais do que status codes. Falhas explícitas, como 500. Implícitas, como um 200 com conteúdo errado. E por política, como uma resposta prometida em um segundo que levou mais. Uma transferência que devolve 201 mas grava um posting desbalanceado é um erro.

Saturação: o quão cheio o serviço está. Pool do banco em uso, consumer lag do Kafka, profundidade da fila. Muitos sistemas degradam antes de cem por cento: um pool a noventa e cinco por cento ainda não falha, mas toda requisição nova espera.

E cuidado com médias. Mil requisições por segundo com média de cem milissegundos podem ter um por cento levando cinco segundos. São dez clientes por segundo olhando um spinner, e alguns vão tocar em pagar de novo. Registre a latência como histograma, com faixas que crescem umas três vezes: zero a dez, dez a trinta, trinta a cem milissegundos.

> **Pausa:** Pergunta: por que separar a latência de sucessos e de falhas?

Porque falhas rápidas puxam a latência média para baixo e escondem o problema. E erros lentos, que são os piores, ficam misturados.


## SLI, SLO e SLA

Três termos que as pessoas confundem. O S L I é um número bem definido que mede o serviço, como a fração de transferências que dão certo. O S L O é uma meta para o S L I: noventa e nove vírgula nove por cento, em trinta dias. E o S L A é um contrato, com consequências se não cumprir. O teste: o que acontece se o S L O não for cumprido? Se nada explícito, não é S L A. E o S L A deve ser mais folgado que o S L O interno, para sobrar espaço para reagir. Escreva cada S L I como eventos bons divididos por eventos válidos.

Disponibilidade: resposta que não é 5 X X, sobre toda transferência bem formada.

Latência: respondida em menos de trezentos milissegundos. Percentis, não médias: noventa e nove por cento abaixo de trezentos.

Atualidade da liquidação: o pagamento sai de pendente em até dez minutos.

Para escolher metas: comece pelo que importa ao usuário, não pelo fácil de medir. Poucos S L Os. Nada de cem por cento. E comece folgado, porque afrouxar uma meta de que os usuários já dependem é difícil. O Google chegou a derrubar o Chubby, o serviço de locks, de propósito, porque ele era tão confiável que outros times passaram a supor que nunca falharia. Os usuários dependem da confiabilidade que você entrega, não da que você promete.

> **Pausa:** Pergunta: qual a diferença entre um S L O e um S L A?

O S L O é a meta interna. O S L A é um contrato com consequências quando a meta não é cumprida, e deve ser mais folgado que o S L O.


## Error budget

Se o S L O é noventa e nove vírgula nove por cento, então zero vírgula um por cento de falha é permitido. Essa margem é o error budget. Cem por cento é irreal e indesejável. Um exemplo: dois milhões de transferências em trinta dias, com S L O de noventa e nove vírgula nove. O budget é de duas mil transferências com falha. Cada falha gasta uma unidade.

O budget vira regra de decisão. Se sobrou quase todo perto do fim do mês, o time pode publicar mudanças mais arriscadas. Se um deploy ruim queimou oitenta por cento numa tarde, os releases desaceleram e confiabilidade sobe na prioridade.

E uma pegadinha de fintech: nem toda falha é igual. Um 503 com retry seguro custa segundos ao cliente. Uma cobrança dupla custa dinheiro e confiança, e nunca entra no budget. Ela ganha um detector próprio, com limiar perto de zero, na quarta.

> **Pausa:** Pergunta: com quinhentas mil transferências por mês e S L O de noventa e nove vírgula nove, qual o error budget?

Quinhentas falhas por mês. Zero vírgula um por cento de quinhentas mil.


## Burn rate

Burn rate é a velocidade, relativa ao S L O, com que o serviço consome o error budget.

Burn rate um gasta o budget exatamente na janela: taxa de erro de zero vírgula um, trinta dias.

Burn rate dois: zero vírgula dois por cento, acaba em quinze dias.

Dez: um por cento de erro, acaba em três dias.

Mil: cem por cento de erro, acaba em quarenta e três minutos.

O workbook julga alertas por precisão, recall, tempo de detecção e tempo de reset. E mostra regras simples que falham. Alertar quando a taxa de erro em dez minutos passa do S L O: rápido, mas pode dar cento e quarenta e quatro alertas por dia com o S L O sendo cumprido. Janela de trinta e seis horas: preciso, mas depois de uma queda o alerta fica disparando trinta e seis horas. Duração de uma hora: uma queda total só gera page depois de uma hora, e uma taxa oscilante pode nunca gerar. E um único burn rate: o de trinta e cinco nunca alerta, mesmo gastando tudo em menos de um dia.


## Multijanela

A resposta do workbook combina duas ideias. Vários burn rates: queima rápida gera page, queima lenta abre ticket. O budget consumido é burn rate vezes a janela, dividido pelo período, setecentas e vinte horas.

Page: burn rate de catorze vírgula quatro em uma hora, dois por cento do budget. Confira: catorze vírgula quatro vezes uma hora, dividido por setecentos e vinte, dá dois por cento. Nesse ritmo, o budget dura cinquenta horas. Alguém precisa olhar agora.

Page: burn rate seis em seis horas, cinco por cento.

Ticket: burn rate um em três dias, dez por cento.

E a segunda ideia: uma janela curta para confirmar, com um doze avos da longa. O alerta só dispara quando as duas estão acima do limite. Quando os erros param, a janela curta cai em minutos, e o alerta reseta. No Prometheus, são recording rules da taxa de erro em cada janela, e alertas que as combinam com and. E com pouco tráfego a matemática quebra: dez requisições por hora, uma falha é burn rate de mil. No projeto local, gere carga com um script ao testar.

> **Pausa:** Pergunta: para que serve a janela curta no alerta multijanela?

Para o alerta resetar rápido depois da recuperação, e para confirmar que o problema ainda está acontecendo agora.


## Revisão relâmpago

Hora da revisão relâmpago. São três perguntas, sem olhar.

> **Pausa:** Pergunta um: quais são os quatro sinais de ouro?

Latência, tráfego, erros e saturação.

> **Pausa:** Pergunta dois: S L O de noventa e nove vírgula nove, dois milhões de transferências por mês. Qual o error budget?

Duas mil falhas por mês.

> **Pausa:** Pergunta três: um burn rate de catorze vírgula quatro durante uma hora consome quanto do budget mensal?

Dois por cento. Catorze vírgula quatro vezes uma hora, sobre setecentas e vinte horas.


## O que anotar e próximo passo

Anote com as suas palavras: cinco sintomas com duas causas cada, e os sinais de ouro da API de transferências. O seu S L I e S L O, com o budget em número de requisições. E a tabela de burn rate, com as contas.

Depois, no lab, instale o OpenTelemetry no Nest J S e envie traces para o Jaeger. Até a próxima aula.
