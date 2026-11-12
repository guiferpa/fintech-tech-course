# Roteiro · M5 · Dia 1 · Logs, partições e o producer


## Abertura

Esta é a aula em vídeo do módulo cinco, dia um: logs, partições e o producer.

No módulo quatro você gravou eventos no outbox. Agora eles precisam chegar a outros serviços: notificações, fraude, extrato, webhooks. Eles vão passar por um log, o Kafka, ou o Redpanda nos labs. Mas um log não é um cano mágico. Ele só garante ordem dentro de uma partição, pode entregar duas vezes, e é o producer que decide quão durável é uma escrita. Escolha a chave errada, e um saldo pode andar para trás.


## O que é um log

Jay Kreps, um dos criadores do Kafka, descreve o log como a abstração de armazenamento mais simples: uma sequência só de acréscimo, totalmente ordenada. Registros novos vão para o fim, os antigos nunca mudam, e cada um recebe um número, o offset.

Dois pontos importam. O offset é um relógio em que você pode confiar. O módulo um mostrou que relógios de parede discordam. O log troca qual timestamp é anterior por qual offset é menor, e essa pergunta tem uma única resposta.

E processos determinísticos que recebem as mesmas entradas na mesma ordem chegam ao mesmo estado. Um consumidor pode ser descrito pelo último offset que processou.

Tabelas e logs são duais: a tabela guarda o estado atual, e o log, como você chegou lá. O WAL do Postgres é essa ideia dentro do banco, e o Debezium a expõe para fora.

Na carteira, o ledger no Postgres continua sendo a fonte da verdade dos saldos. O log é como o resto da empresa fica sabendo das mudanças, em ordem.


## Filas vs logs

Compare uma fila clássica com um log.

Na fila, a mensagem é apagada quando confirmada. No log, o registro fica, e só a retenção o remove.

Na fila, o broker acompanha cada mensagem. No log, cada consumer group guarda só um número por partição: o offset. Muito mais barato.

Vários leitores independentes: a fila precisa de uma fila por leitor. No log, cada grupo lê os mesmos registros no seu ritmo.

Reprocessar depois de corrigir um bug é impossível numa fila depois do ack. No log, você volta o offset e lê de novo. E se o gerador de extrato cair por uma hora, o producer continua escrevendo, e ele alcança o atraso quando volta.

Ordem: fraca numa fila com consumidores competindo, total dentro de cada partição do log.

E registros não vivem para sempre. Há retenção por tempo ou tamanho, e há log compaction, que mantém só o último valor de cada chave. Compaction serve para estado atual de cada cliente. É errada para dinheiro, onde todo evento importa.

> **Pausa:** Pergunta: depois que um consumidor lê um registro do log, ele é apagado? O que o remove?

Não é apagado. Só a política de retenção, por tempo ou tamanho, ou a compaction removem registros.


## Partições e chaves

Um log numa máquina só não escala. O Kafka divide cada tópico em partições, e cada partição é um log ordenado. Mas não existe ordem global entre partições. Quem escolhe a partição é o producer: se o registro tem chave, o hash da chave decide, e a mesma chave sempre cai na mesma partição. Essa é sua única ferramenta de ordem.

Sem chave, nada fica em ordem. Dois eventos da mesma conta podem ser processados fora de ordem.

Com transfer ID, os eventos de uma transferência ficam em ordem, mas transferências diferentes da mesma conta podem se intercalar.

Com account ID, tudo que toca uma conta fica em ordem. É a escolha usual da carteira. O risco é uma conta muito ativa virar partição quente. Uma transferência toca duas contas, então publique um evento por conta afetada, ou escolha a origem e anote essa limitação.

Customer ID é mais grosso, com mais chance de pontos quentes.


## Dois alertas

Dois alertas. Primeiro: o mapeamento depende do número de partições. Se você adicionar partições depois, registros novos de uma chave podem cair numa partição diferente dos antigos, e a ordem quebra na transição. Escolha um número generoso desde o começo.

Segundo: o paralelismo é limitado pelas partições. Num consumer group, cada partição é lida por um consumidor de cada vez. Seis partições, no máximo seis consumidores ocupados.

> **Pausa:** Pergunta: por que adicionar partições a um tópico pode quebrar a ordem por chave?

Porque a partição é o hash da chave módulo o número de partições. Mudando o número, a mesma chave pode ir para outra partição, e eventos novos passam na frente dos antigos.


## Acks e durabilidade

Quando o producer envia, o líder da partição grava, e os seguidores copiam. A configuração acks decide quando o envio está completo.

Com acks zero, basta escrever no socket. Pode perder qualquer coisa.

Com acks um, o líder gravou. Perde o que ele ainda não tinha replicado quando caiu.

Com acks all, todas as réplicas em sincronia têm o registro. Mas há uma armadilha: se o conjunto de réplicas em sincronia, o ISR, encolher até sobrar só o líder, all significa uma cópia. A configuração min insync replicas fecha a brecha: abaixo desse número, a partição rejeita escritas.

Para pagamentos: fator de replicação três, min insync replicas dois, e acks all. Um broker pode cair e as escritas seguem. Se dois caírem, as escritas param. E é isso que você quer: um erro que dá para repetir é melhor que um evento que some em silêncio. Sempre defina esses valores explicitamente no seu cliente.

> **Pausa:** Pergunta: com acks all, como uma escrita ainda pode acabar com uma cópia só, e qual configuração evita isso?

Se o ISR encolher até só o líder, all significa só ele. O min insync replicas faz a partição recusar escritas abaixo do mínimo.


## O producer idempotente

Com acks all, o producer espera o broker, e a resposta pode se perder. É o timeout do módulo um. O producer faz retry, e sem proteção o registro é gravado duas vezes.

O producer idempotente resolve esse caso. O broker dá um ID a cada producer e deduplica pelo número de sequência de cada lote.

Mas leia os limites. Ele cobre os retries do próprio producer, dentro de uma sessão.

Se o processo reinicia, o producer novo tem ID novo.

E reenvios feitos pela sua aplicação não são cobertos.

Aplique ao publicador do outbox. Ele envia, espera o ack e marca a linha como publicada. Se cair entre o envio e o update, a próxima execução envia de novo, com um producer novo. O broker vê dois registros diferentes.

Conclusão: o outbox dá at-least-once, e os consumidores deduplicam pelo ID do evento. Todo evento precisa de um event ID estável, e o ID da linha do outbox serve. Por isso o consumidor de quinta tem uma tabela de inbox.

> **Pausa:** Pergunta: o publicador do outbox caiu depois de enviar e antes de marcar a linha. O producer idempotente evita a duplicata?

Não. O reenvio vem de outra sessão, com outro ID de producer, então o broker vê um registro novo. Quem deduplica é o consumidor, pelo event ID.


## O lab de hoje

O lab roda o Redpanda, que fala o protocolo do Kafka. Crie um tópico com seis partições, produza registros com chave, e consuma imprimindo partição, offset e chave.

Confira três coisas. Todo registro de acc um mostra a mesma partição.

Os offsets crescem de um em um dentro de uma partição, e são independentes entre partições.

E ler o tópico uma segunda vez devolve os mesmos registros, porque ler não apaga nada. É a ideia de log, não fila, num comando.


## Revisão relâmpago

Hora da revisão relâmpago. São três perguntas, sem olhar.

> **Pausa:** Pergunta um: o que Kreps quer dizer quando diz que o log define o tempo sem um relógio?

Que a ordem dos offsets é o tempo. Quem tem offset menor veio antes, sem depender de relógio físico.

> **Pausa:** Pergunta dois: quais registros o Kafka mantém em ordem, e quais não?

Os de uma mesma partição, portanto os de uma mesma chave. Entre partições, não há ordem.

> **Pausa:** Pergunta três: o que é um registro committed no Kafka?

Um registro que todas as réplicas do conjunto em sincronia já aplicaram.


## O que anotar e próximo passo

Anote com as suas palavras: filas contra logs e o que é um offset. Sua chave de partição e a ordem que ela dá. Os três níveis de acks e o min insync replicas. E os limites do producer idempotente.

Depois, rode o lab com rpk e kcat. E se sobrar tempo, leia The Log, de Jay Kreps. Até a próxima aula.
