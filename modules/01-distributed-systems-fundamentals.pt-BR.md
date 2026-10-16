# Módulo 1: Fundamentos de sistemas distribuídos

**Semana 1** · [Voltar para a ementa](../README.pt-BR.md) · [Read in English](01-distributed-systems-fundamentals.md)

## Objetivo

Construir o vocabulário que sustenta todo o resto: falhas parciais, semânticas de entrega, replicação, particionamento, modelos de consistência e relógios. Consenso e Raft ficam para o Módulo 9.

## Segunda a quarta: DSA + leitura + laboratório (3 h 30 por dia)

| Dia | DSA (30 min) | Leitura (2 h) | Laboratório (1 h) |
| --- | --- | --- | --- |
| Seg | [Two Sum](https://leetcode.com/problems/two-sum/) (hash map)<br>[Two Sum II](https://leetcode.com/problems/two-sum-ii-input-array-is-sorted/) (two pointers em array ordenado) | [Texto do curso: Falhas, timeouts e tempo](../lessons/01-distributed-systems-fundamentals/day-1.pt-BR.md) (escrito para este curso): leia este primeiro. Ele explica os conceitos do dia e indica quais seções das referências abaixo ler em seguida.<br>[Martin Kleppmann, notas de aula "Distributed Systems" (Universidade de Cambridge), seções 1.1 e 2.1 a 2.4](https://www.cl.cam.ac.uk/teaching/2122/ConcDisSys/dist-sys-notes.pdf) (gratuito): falhas parciais, redes não confiáveis, timeouts e detecção de falhas. Anote os 3 desfechos possíveis de um timeout (aconteceu, não aconteceu, desconhecido).<br>[Martin Kleppmann, notas de aula "Distributed Systems" (Universidade de Cambridge), capítulo 3 e seção 4.1](https://www.cl.cam.ac.uk/teaching/2122/ConcDisSys/dist-sys-notes.pdf) (gratuito): relógios físicos, sincronização, happens-before e Lamport clocks. Anote por que não ordenar eventos pelo relógio da máquina e o que é um Lamport clock.<br>[Jeff Hodges, "Notes on Distributed Systems for Young Bloods"](https://www.somethingsimilar.com/2013/01/14/notes-on-distributed-systems-for-young-bloods/) (gratuito): texto curto e prático; leia se sobrar tempo. | Crie o repositório público (services/, docs/, chaos/) com o esqueleto NestJS e o Docker Compose com Postgres primário + réplica assíncrona (streaming replication). |
| Ter | [3Sum](https://leetcode.com/problems/3sum/) (ordenação + two pointers, generaliza para k-sum) | [Texto do curso: Replicação e atraso de replicação](../lessons/01-distributed-systems-fundamentals/day-2.pt-BR.md) (escrito para este curso): leia este primeiro. Ele explica os conceitos do dia e indica quais seções das referências abaixo ler em seguida.<br>[Documentação do PostgreSQL, "High Availability, Load Balancing, and Replication"](https://www.postgresql.org/docs/current/high-availability.html) (gratuito): líder/seguidor, replicação síncrona x assíncrona, failover e as escritas que se perdem no failover.<br>[Jepsen, modelos de consistência: "Read Your Writes" e "Monotonic Reads"](https://jepsen.io/consistency/models/read-your-writes) (gratuito): o que cada garantia significa e como uma réplica atrasada quebra cada uma (Monotonic Reads está linkado na mesma página).<br>[Martin Kleppmann, notas de aula "Distributed Systems" (Universidade de Cambridge), seção 5.2 (Quorums)](https://www.cl.cam.ac.uk/teaching/2122/ConcDisSys/dist-sys-notes.pdf) (gratuito): replicação sem líder e quorums (R + W > N). | Experimento de leitura velha: script que escreve no primário e lê na réplica em loop, medindo o lag. Coloque o Toxiproxy entre as duas para tornar o lag visível. Anote os números. |
| Qua | [Top K Frequent Elements](https://leetcode.com/problems/top-k-frequent-elements/) (heap, depois bucket sort em O(n)) | [Texto do curso: Particionamento, modelos de consistência e trade-offs](../lessons/01-distributed-systems-fundamentals/day-3.pt-BR.md) (escrito para este curso): leia este primeiro. Ele explica os conceitos do dia e indica quais seções das referências abaixo ler em seguida.<br>[Amazon DynamoDB Developer Guide, "Best practices for designing and using partition keys effectively"](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/bp-partition-key-design.html) (gratuito): particionamento por chave, partições quentes e write sharding. Pense: qual é a chave de partição de uma carteira digital?<br>[Martin Kleppmann, notas de aula "Distributed Systems" (Universidade de Cambridge), seções 7.2 e 7.3](https://www.cl.cam.ac.uk/teaching/2122/ConcDisSys/dist-sys-notes.pdf) (gratuito): linearizabilidade, consistência eventual e o trade-off do CAP.<br>[Daniel Abadi, "Consistency Tradeoffs in Modern Distributed Database System Design" (2012)](https://www.cs.umd.edu/~abadi/papers/abadi-pacelc.pdf) (gratuito): PACELC. Depois rascunhe a tabela das 8 operações da carteira x a consistência que cada uma exige. | Preparação do dia de conclusão (sem escrever o código do TCM): suba o banco parceiro falso (endpoint com atraso configurável) atrás do Toxiproxy e escreva no papel a lista de tarefas e os casos de teste de sábado. |

Resolva sem IA, com limite de 30 minutos. Método e lista completa: [trilha de DSA](../DSA.pt-BR.md).

Nos laboratórios, IA só para tirar dúvida de conceito, nunca para escrever código do TCM.

## Quinta e sexta: trabalho de conclusão (TCM), sem IA

Tudo feito SEM IA. Nada de ChatGPT, Claude, Copilot ou autocomplete com IA no editor. Vale: documentação oficial, livros, suas anotações e os laboratórios das semanas anteriores. O que não couber hoje vira escopo cortado para o próximo checkpoint; o deadline não muda.

1. (1 h) Serviço payments: POST /transfers grava a transferência como PENDING e chama o banco parceiro falso com timeout de 2 s.
2. (1 h) Tratar os 3 desfechos: sucesso vira COMPLETED, erro definitivo vira FAILED, timeout vira UNKNOWN (nunca FAILED). Job que consulta o parceiro e resolve os UNKNOWN.
3. (1 h) Testes de integração com Testcontainers + Toxiproxy cobrindo os 3 desfechos.
4. (1 h) chaos/replica-lag.sh reproduzindo a leitura velha de forma automática.
5. (1 h) docs/m01.md: o experimento, os 3 desfechos de um timeout e a tabela das 8 operações x consistência.

A quinta cobre os itens 1 a 3; a sexta cobre o resto e termina com 30 minutos de entrega.

## Critério de aprovação

A leitura velha é reproduzível por script, e a tabela de consistência justifica cada escolha em uma linha.

## Teste de domínio

Responda em voz alta, em até 2 minutos, sem consultar, e grave:

> Seu serviço chama o banco parceiro, dá timeout e o cliente tenta de novo. O que pode ter acontecido e como seu sistema garante que não cobrou duas vezes?
