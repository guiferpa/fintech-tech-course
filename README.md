# Fintech Tech Course

[Leia em português](README.pt-BR.md)

A 13-week, self-paced course to become a distributed systems specialist for fintech: payments, digital banking, acquiring, wallets and lending. The goal is to walk into interviews able to **explain, design and review code** on these topics, always tying each concept to money risk: charging twice, losing an entry, a negative balance.

It is designed for **weekdays only, no weekends**: 3 h 30 Monday to Wednesday (including 30 min of DSA) and 3 h on Thursday and Friday, 16 h 30 a week, about 215 h in total. Every session exists in English and Portuguese.

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
| Mon to Wed | 30 min DSA + 2 h reading + 1 h lab (e.g. 19:00 to 22:30). In labs, AI only to clarify concepts; DSA is solved without AI. |
| Thu and Fri | **Capstone days (TCM): implementation only, without AI.** No ChatGPT, Claude, Copilot or AI autocomplete; docs, books and your notes are fine. The last 30 min on Friday are delivery: final commit, recorded mastery test, flashcards. |

Flashcards (Anki) keep what you learn from fading: 10 min of review every Monday and new cards from every Friday delivery. The [flashcards guide](FLASHCARDS.md) shows the setup and how to write good cards.

The [DSA track](DSA.md) lists the coding interview problem for each day, from Two Sum to LFU Cache.

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

Every reading in the sessions and module pages has the full name and a link. Free material comes first; a paid book is used only where nothing free covers the topic as well.

Free (used most):

1. [Martin Kleppmann, "Distributed Systems" lecture notes (University of Cambridge)](https://www.cl.cam.ac.uk/teaching/2122/ConcDisSys/dist-sys-notes.pdf): failures, clocks, replication, quorums, consensus and consistency (modules 1 and 9).
2. [PostgreSQL documentation](https://www.postgresql.org/docs/current/) and [Jepsen consistency models](https://jepsen.io/consistency): replication, isolation levels and locking (modules 1 and 3).
3. [microservices.io](https://microservices.io/patterns/), by Chris Richardson: saga, transactional outbox and idempotent consumer (modules 2 and 4).
4. [Stripe blog on idempotency](https://stripe.com/blog/idempotency) and [Stripe's Ledger post](https://stripe.dev/blog/ledger-stripe-system-for-tracking-and-validating-money-movement) (modules 2 and 6).
5. [Modern Treasury journal and ebooks](https://www.moderntreasury.com/journal/accounting-for-developers-part-i) and the [TigerBeetle documentation](https://docs.tigerbeetle.com/) (module 6).
6. [Banco Central do Brasil, Pix](https://www.bcb.gov.br/estabilidadefinanceira/pix): regulation, manuals and MED (module 7).
7. [OWASP Cheat Sheet Series](https://cheatsheetseries.owasp.org/) and [OWASP API Security Top 10](https://owasp.org/API-Security/editions/2023/en/0x11-t10/) (module 8).
8. [Amazon Builders' Library](https://aws.amazon.com/builders-library/): timeouts, retries, backlogs and load shedding (module 9).
9. [Google, "Site Reliability Engineering"](https://sre.google/sre-book/table-of-contents/) and ["The Site Reliability Workbook"](https://sre.google/workbook/table-of-contents/) (module 10).
10. [Gwen Shapira et al., "Kafka: The Definitive Guide", 2nd edition](https://www.confluent.io/resources/kafka-the-definitive-guide-v2/): free from Confluent with a sign-up form (module 5).

Paid books:

1. [Chris Richardson, "Microservices Patterns" (Manning)](https://www.manning.com/books/microservices-patterns): chapter 4 is the only required paid reading (module 4, Tuesday), because no free source covers saga countermeasures as well.
2. Optional, for going deeper: [Martin Kleppmann, "Designing Data-Intensive Applications" (O'Reilly)](https://dataintensive.net/), [Michael Nygard, "Release It!", 2nd edition (Pragmatic Bookshelf)](https://pragprog.com/titles/mnee2/release-it-second-edition/) and Alex Xu and Sahn Lam, "System Design Interview, Volume 2" (payment system and digital wallet chapters).
