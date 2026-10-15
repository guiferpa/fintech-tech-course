# Fintech Tech Course

[Leia em português](README.pt-BR.md)

A 13-week, self-paced course to become a distributed systems specialist for fintech: payments, digital banking, acquiring, wallets and lending. The goal is to walk into interviews able to **explain, design and review code** on these topics, always tying each concept to money risk: charging twice, losing an entry, a negative balance.

It is designed for **3 hours a day, Monday to Friday, no weekends** (15 h a week, about 195 h in total). Every session exists in English and Portuguese.

## Add the course to your calendar

The schedule has no fixed dates. You pick when to start and get every session on your calendar:

1. Open the **[calendar generator](https://guiferpa.github.io/fintech-tech-course/)**.
2. Pick the language, a start Monday, a start time, and any days off (holidays, vacation). Sessions skip those days and shift forward.
3. Download the `.ics` file and import it. In Google Calendar, create a dedicated calendar first (Settings > Add calendar > Create new calendar), then go to Settings > Import & export and pick that calendar.

### Run it locally

No install needed besides [Git](https://git-scm.com/) and [Node.js 18+](https://nodejs.org/) (check with `node --version`).

1. Clone the repository and enter it:

   ```bash
   git clone https://github.com/guiferpa/fintech-tech-course.git
   cd fintech-tech-course
   ```

2. Generate the file, choosing your start Monday, time, language (`en` or `pt-BR`) and days off:

   ```bash
   node scripts/generate-ics.mjs --start 2027-03-01 --time 19:00 --lang en --skip 2027-04-02,2027-04-21 > fintech-tech-course.ics
   ```

   The terminal prints how many sessions were created and the first and last dates. Run `node scripts/generate-ics.mjs --help` to see every option (`--name` sets the calendar name, `--reminder` the reminder in minutes, `0` for none).

3. Import `fintech-tech-course.ics` into your calendar as described in step 3 above.

Prefer the visual page offline? Serve the `docs/` folder and open http://localhost:8000 (opening `index.html` straight from disk does not work, browsers block it):

```bash
python3 -m http.server 8000 --directory docs   # or: npx serve docs -l 8000
```

Times are "floating" local times: 19:00 means 19:00 in whatever time zone your calendar uses. The page source is in [`docs/`](docs/), and both generators read the same schedule from [`docs/sessions.json`](docs/sessions.json).

## How a week works

| Day | What you do |
| --- | --- |
| Mon to Wed | 2 h reading + 1 h lab. In labs, AI only to clarify concepts. |
| Thu and Fri | **Capstone days (TCM): implementation only, without AI.** No ChatGPT, Claude, Copilot or AI autocomplete; docs, books and your notes are fine. The last 30 min on Friday are delivery: final commit, recorded mastery test, flashcards. |

Flashcards (Anki) keep what you learn from fading: 10 min of review every Monday and new cards from every Friday delivery. The [flashcards guide](FLASHCARDS.md) shows the setup and how to write good cards.

If something doesn't fit, cut scope, never the deadline. Cut scope goes to the next checkpoint week.

## Syllabus

| Week | Module |
| --- | --- |
| 1 | [Distributed systems fundamentals](modules/01-distributed-systems-fundamentals.md) |
| 2 | [End-to-end idempotency](modules/02-end-to-end-idempotency.md) |
| 3 | [Transactions, concurrency and Postgres](modules/03-transactions-concurrency-postgres.md) |
| 4 | [Sagas, Outbox and distributed transactions](modules/04-sagas-outbox.md) |
| 5 | [Checkpoint 1](modules/checkpoints.md) |
| 6 | [Messaging and events](modules/05-messaging-and-events.md) |
| 7 | [Ledgers and accounting](modules/06-ledgers-and-accounting.md) |
| 8 | [Payments, Pix and reconciliation](modules/07-payments-pix-reconciliation.md) |
| 9 | [Checkpoint 2](modules/checkpoints.md) |
| 10 | [Security, compliance and risk](modules/08-security-compliance-risk.md) |
| 11 | [Resilience, high availability and consensus](modules/09-resilience-and-consensus.md) |
| 12 | [Observability and operations](modules/10-observability-and-operations.md) |
| 13 | [Final project and mock panel](modules/final-project.md) |

## The practice project

Every capstone grows the same system: a digital wallet with transfers, fake payment providers and reconciliation, built with NestJS, TypeScript, Postgres, Redpanda (Kafka API), Redis, Docker Compose, Testcontainers, Toxiproxy and k6, plus OpenTelemetry, Prometheus and Grafana in module 10. Keep it in its own public repository: by the end it is the project you show and cite in interviews.

## Track your progress

Fork this repository, tick the boxes in [PROGRESS.md](PROGRESS.md) as you deliver each module, and keep a short weekly log in [JOURNEY.md](JOURNEY.md).

## Main sources

1. *Designing Data-Intensive Applications*, Martin Kleppmann (1st edition; chapters 5 to 9 and 11).
2. *Microservices Patterns*, Chris Richardson, and microservices.io.
3. Stripe engineering blog: idempotency and the Ledger post.
4. *Release It!*, Michael Nygard.
5. *Site Reliability Engineering* and *The Site Reliability Workbook* (Google, free online).
6. Modern Treasury's ledger series and the TigerBeetle docs.
7. Banco Central do Brasil: Pix regulation and MED.
8. *System Design Interview vol. 2*, Alex Xu (payment system and digital wallet chapters).
