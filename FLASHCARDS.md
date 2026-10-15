[Português](FLASHCARDS.pt-BR.md)

# Flashcards

The course asks for flashcards in three places: **10 minutes of review at the start of every Monday**, **new cards in Friday's delivery** (from what you missed in the recorded mastery test), and **a full review in checkpoint weeks**. This page shows how to set them up and how to write cards that actually help in interviews.

## 1. Install Anki

Use [Anki](https://apps.ankiweb.net/). It is free on desktop (Windows, macOS, Linux), web ([AnkiWeb](https://ankiweb.net/)) and Android ([AnkiDroid](https://play.google.com/store/apps/details?id=com.ichi2.anki)); the iOS app is paid, and AnkiWeb in the phone browser is the free alternative. Anki schedules each card for review right before you would forget it (spaced repetition), so 10 minutes a day is enough.

1. Install Anki on your computer and create a free AnkiWeb account to sync with your phone.
2. In Anki: **Tools > Preferences > Review**, turn on **FSRS** (the modern scheduler, Anki 23.10+).
3. Create the deck **Fintech Tech Course** and one subdeck per module by naming them with `::`, for example `Fintech Tech Course::M01 Fundamentals`, `Fintech Tech Course::M02 Idempotency`, and so on.
4. On the parent deck, open the options (gear icon) and set **New cards/day** to 20 and **Maximum reviews/day** to 200.

## 2. When to create cards

| Moment | What to turn into cards | How many |
| --- | --- | --- |
| Reading (Mon to Wed) | Ideas you would need to explain in an interview: trade-offs, failure modes, "why", numbers | 3 to 6 per session |
| Friday delivery | Listen to your mastery test recording. Every gap, hesitation or wrong answer becomes a card | 5 to 10 |
| Checkpoints | Whatever you missed in the mock system design, mastery tests and code review | As many as needed |

Write the cards yourself, in your own words. Writing is half of the learning; imported decks you didn't write are forgotten quickly.

## 3. How to write a good card

- **One idea per card.** If the answer has a list of 5 things, split it or use cloze.
- **Ask "why" and "what if", not just "what is".** "Why can't a timeout be marked as FAILED?" teaches more than "What is a timeout?".
- **Short answer, recalled in a few seconds.** If you need a paragraph, the question is too broad.
- **Use cloze for lists and formulas.** In Anki, choose the **Cloze** note type and wrap the hidden part like `{{c1::R + W > N}}`.
- **Code cards: show the snippet and ask what happens.** This is how interviews and code reviews test you.
- **Tag the source.** Add the module tag (`m01`, `m02` ...) and `gap` for cards born from a mastery test, so you can study weak spots first.

## 4. Examples

**Basic card** (Front / Back)

> **Front:** A call to the partner bank times out. Why can't you mark the transfer as FAILED?
> **Back:** The request may have been processed. The outcome is unknown: store it as UNKNOWN and reconcile by querying the partner. Marking FAILED and retrying can charge twice.

> **Front:** What does a client-supplied idempotency key protect against, and what does it not?
> **Back:** It makes retries of the same request return the same result. It does not deduplicate two different requests with different keys, and the key must be stored in the same transaction as the effect.

**Code card**

> **Front:** Two sessions run this at the same time under READ COMMITTED. What can go wrong?
> ```sql
> SELECT balance FROM accounts WHERE id = 1;
> -- app computes balance - 100
> UPDATE accounts SET balance = 900 WHERE id = 1;
> ```
> **Back:** Lost update: both read 1000 and both write 900, so one debit disappears. Fix with `SELECT ... FOR UPDATE`, a version column, or a conditional `UPDATE ... SET balance = balance - 100 WHERE balance >= 100`.

**Cloze card**

> In a leaderless system with N replicas, a read is guaranteed to see the latest write when `{{c1::R + W > N}}`.

> The Outbox pattern writes the event `{{c1::in the same database transaction as the business change}}` and publishes it `{{c2::afterwards, from a separate process}}`.

## 5. Daily routine

- **Monday, first 10 minutes of the session:** review all due cards (the schedule reminds you).
- **Recommended:** 5 minutes of due cards on your phone on the other days too. Missing a day is fine; Anki reschedules.
- **Grading:** press **Again** if you couldn't explain it out loud, **Good** if you could. Be strict, it is the only way the scheduler works.
- **Checkpoint weeks:** use **Custom Study > Review forgotten cards** and study the `gap` tag first.

## 6. Optional: import cards from a file

If you prefer writing cards in a text editor, write one per line in a `.tsv` file (front, tab, back, tab, tags) and import it with **File > Import**, choosing the subdeck. [`flashcards/template.tsv`](flashcards/template.tsv) has the examples above in this format.
