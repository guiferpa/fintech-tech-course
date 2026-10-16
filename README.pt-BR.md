# Fintech Tech Course

[Read in English](README.md)

Um curso de 13 semanas, no seu ritmo, para virar especialista em sistemas distribuídos para fintech: pagamentos, banco digital, adquirência, carteiras e crédito. O objetivo é chegar nas entrevistas conseguindo **explicar, desenhar e revisar código** sobre esses temas, sempre ligando cada conceito ao risco de dinheiro: cobrar duas vezes, perder um lançamento, saldo negativo.

Foi pensado para **dias úteis, sem fim de semana**: 3 h 30 de segunda a quarta (incluindo 30 min de DSA) e 3 h na quinta e na sexta, 16 h 30 por semana, cerca de 215 h no total. Todas as sessões existem em inglês e em português.

## Adicione o curso à sua agenda

O cronograma não tem datas fixas. Você escolhe quando começar e recebe todas as sessões na sua agenda:

1. Abra o **[gerador de calendário](https://guiferpa.github.io/fintech-tech-course/)**.
2. Escolha o idioma, uma segunda-feira de início, o horário e os dias de folga (feriados, férias). As sessões pulam esses dias e andam para frente.
3. Baixe o arquivo `.ics` e importe. No Google Calendar, crie antes uma agenda só para o curso (Configurações > Adicionar agenda > Criar nova agenda), depois vá em Configurações > Importar e exportar e escolha essa agenda.

### Rodando localmente

Você só precisa de [Git](https://git-scm.com/) e [Node.js 18+](https://nodejs.org/) (confira com `node --version`).

1. Clone o repositório e entre na pasta:

   ```bash
   git clone https://github.com/guiferpa/fintech-tech-course.git
   cd fintech-tech-course
   ```

2. Gere o arquivo escolhendo a segunda-feira de início, o horário, o idioma (`en` ou `pt-BR`) e os dias de folga:

   ```bash
   node scripts/generate-ics.mjs --start 2027-03-01 --time 19:00 --lang pt-BR --skip 2027-04-02,2027-04-21 > fintech-tech-course.ics
   ```

   O terminal mostra quantas sessões foram criadas e as datas da primeira e da última. Rode `node scripts/generate-ics.mjs --help` para ver todas as opções (`--name` define o nome do calendário, `--reminder` o lembrete em minutos, `0` para nenhum).

3. Importe o `fintech-tech-course.ics` na sua agenda como no passo 3 acima.

Prefere a página visual sem internet? Sirva a pasta `docs/` e abra http://localhost:8000 (abrir o `index.html` direto do disco não funciona, o navegador bloqueia):

```bash
python3 -m http.server 8000 --directory docs   # ou: npx serve docs -l 8000
```

Os horários são locais "flutuantes": 19:00 significa 19:00 no fuso que a sua agenda usa. O código da página está em [`docs/`](docs/), e os dois geradores leem o mesmo cronograma de [`docs/sessions.json`](docs/sessions.json).

## Como funciona uma semana

| Dia | O que você faz |
| --- | --- |
| Seg a qua | 30 min de DSA + 2 h de leitura + 1 h de laboratório (por exemplo, das 19:00 às 22:30). Nos laboratórios, IA só para tirar dúvida de conceito; DSA é resolvido sem IA. |
| Qui e sex | **Dias de conclusão (TCM): só implementação, sem IA.** Nada de ChatGPT, Claude, Copilot ou autocomplete com IA; documentação, livros e suas anotações valem. A última meia hora de sexta é a entrega: commit final, teste de domínio gravado e flashcards. |

Os flashcards (Anki) impedem que o que você aprendeu se perca: 10 min de revisão toda segunda e cards novos em toda entrega de sexta. O [guia de flashcards](FLASHCARDS.pt-BR.md) mostra a configuração e como escrever bons cards.

Cada dia de leitura começa com um texto escrito para este curso, baseado nas referências do dia e citando todas elas. Veja os [textos do curso](lessons/README.pt-BR.md); a lista ali mostra quais módulos já estão prontos.

A [trilha de DSA](DSA.pt-BR.md) traz o problema de entrevista de coding de cada dia, do Two Sum ao LFU Cache.

Se algo não couber, corte escopo, nunca o deadline. O escopo cortado vai para a próxima semana de checkpoint.

## Ementa

| Semana | Módulo |
| --- | --- |
| 1 | [Fundamentos de sistemas distribuídos](modules/01-distributed-systems-fundamentals.pt-BR.md) |
| 2 | [Idempotência ponta a ponta](modules/02-end-to-end-idempotency.pt-BR.md) |
| 3 | [Transações, concorrência e Postgres](modules/03-transactions-concurrency-postgres.pt-BR.md) |
| 4 | [Saga, Outbox e transações distribuídas](modules/04-sagas-outbox.pt-BR.md) |
| 5 | [Checkpoint 1](modules/checkpoints.pt-BR.md) |
| 6 | [Mensageria e eventos](modules/05-messaging-and-events.pt-BR.md) |
| 7 | [Ledger e contabilidade](modules/06-ledgers-and-accounting.pt-BR.md) |
| 8 | [Pagamentos, Pix e reconciliação](modules/07-payments-pix-reconciliation.pt-BR.md) |
| 9 | [Checkpoint 2](modules/checkpoints.pt-BR.md) |
| 10 | [Segurança, compliance e risco](modules/08-security-compliance-risk.pt-BR.md) |
| 11 | [Resiliência, alta disponibilidade e consenso](modules/09-resilience-and-consensus.pt-BR.md) |
| 12 | [Observabilidade e operação](modules/10-observability-and-operations.pt-BR.md) |
| 13 | [Projeto final e banca](modules/final-project.pt-BR.md) |

## O projeto prático

Todos os TCMs constroem o mesmo sistema: uma carteira digital com transferências, provedores de pagamento falsos e reconciliação, feita com NestJS, TypeScript, Postgres, Redpanda (API do Kafka), Redis, Docker Compose, Testcontainers, Toxiproxy e k6, mais OpenTelemetry, Prometheus e Grafana no módulo 10. Mantenha esse sistema num repositório público próprio: no fim, é o projeto que você mostra e cita nas entrevistas.

## Acompanhe seu progresso

Faça um fork deste repositório, marque as caixas no [PROGRESS.md](PROGRESS.md) a cada módulo entregue e mantenha um registro curto por semana no [JOURNEY.md](JOURNEY.md).

## Fontes principais

Toda leitura nas sessões e nas páginas dos módulos tem o nome completo e o link. Material gratuito vem primeiro; livro pago só aparece onde nada gratuito cobre o assunto tão bem.

Gratuitas (as mais usadas):

1. [Martin Kleppmann, notas de aula "Distributed Systems" (Universidade de Cambridge)](https://www.cl.cam.ac.uk/teaching/2122/ConcDisSys/dist-sys-notes.pdf): falhas, relógios, replicação, quorums, consenso e consistência (módulos 1 e 9).
2. [Documentação do PostgreSQL](https://www.postgresql.org/docs/current/) e [modelos de consistência do Jepsen](https://jepsen.io/consistency): replicação, níveis de isolamento e locks (módulos 1 e 3).
3. [microservices.io](https://microservices.io/patterns/), de Chris Richardson: saga, transactional outbox e idempotent consumer (módulos 2 e 4).
4. [Blog da Stripe sobre idempotência](https://stripe.com/blog/idempotency) e o [post da Stripe sobre o Ledger](https://stripe.dev/blog/ledger-stripe-system-for-tracking-and-validating-money-movement) (módulos 2 e 6).
5. [Journal e ebooks da Modern Treasury](https://www.moderntreasury.com/journal/accounting-for-developers-part-i) e a [documentação do TigerBeetle](https://docs.tigerbeetle.com/) (módulo 6).
6. [Banco Central do Brasil, Pix](https://www.bcb.gov.br/estabilidadefinanceira/pix): regulamento, manuais e MED (módulo 7).
7. [OWASP Cheat Sheet Series](https://cheatsheetseries.owasp.org/) e [OWASP API Security Top 10](https://owasp.org/API-Security/editions/2023/en/0x11-t10/) (módulo 8).
8. [Amazon Builders' Library](https://aws.amazon.com/builders-library/): timeouts, retries, filas acumuladas e load shedding (módulo 9).
9. [Google, "Site Reliability Engineering"](https://sre.google/sre-book/table-of-contents/) e ["The Site Reliability Workbook"](https://sre.google/workbook/table-of-contents/) (módulo 10).
10. [Gwen Shapira et al., "Kafka: The Definitive Guide", 2ª edição](https://www.confluent.io/resources/kafka-the-definitive-guide-v2/): gratuito no site da Confluent, com cadastro (módulo 5).

Livros pagos:

1. [Chris Richardson, "Microservices Patterns" (Manning)](https://www.manning.com/books/microservices-patterns): o capítulo 4 é a única leitura paga obrigatória (módulo 4, terça), porque nenhuma fonte gratuita cobre as contramedidas de saga tão bem.
2. Opcionais, para aprofundar: [Martin Kleppmann, "Designing Data-Intensive Applications" (O'Reilly)](https://dataintensive.net/), [Michael Nygard, "Release It!", 2ª edição (Pragmatic Bookshelf)](https://pragprog.com/titles/mnee2/release-it-second-edition/) e Alex Xu e Sahn Lam, "System Design Interview, Volume 2" (capítulos de sistema de pagamento e carteira digital).
