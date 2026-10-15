# Fintech Tech Course

[Read in English](README.md)

Um curso de 13 semanas, no seu ritmo, para virar especialista em sistemas distribuídos para fintech: pagamentos, banco digital, adquirência, carteiras e crédito. O objetivo é chegar nas entrevistas conseguindo **explicar, desenhar e revisar código** sobre esses temas, sempre ligando cada conceito ao risco de dinheiro: cobrar duas vezes, perder um lançamento, saldo negativo.

Foi pensado para **3 horas por dia, de segunda a sexta, sem fim de semana** (15 h por semana, cerca de 195 h no total). Todas as sessões existem em inglês e em português.

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
| Seg a qua | 2 h de leitura + 1 h de laboratório. Nos laboratórios, IA só para tirar dúvida de conceito. |
| Qui e sex | **Dias de conclusão (TCM): só implementação, sem IA.** Nada de ChatGPT, Claude, Copilot ou autocomplete com IA; documentação, livros e suas anotações valem. A última meia hora de sexta é a entrega: commit final, teste de domínio gravado e flashcards. |

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

1. *Designing Data-Intensive Applications*, Martin Kleppmann (1ª edição; capítulos 5 a 9 e 11).
2. *Microservices Patterns*, Chris Richardson, e microservices.io.
3. Blog de engenharia da Stripe: idempotência e o post sobre o Ledger.
4. *Release It!*, Michael Nygard.
5. *Site Reliability Engineering* e *The Site Reliability Workbook* (Google, gratuitos online).
6. Série sobre ledgers da Modern Treasury e a documentação do TigerBeetle.
7. Banco Central do Brasil: regulamento do Pix e MED.
8. *System Design Interview vol. 2*, Alex Xu (capítulos de sistema de pagamento e carteira digital).
