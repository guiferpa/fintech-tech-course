# Checkpoints

[Back to the syllabus](../README.md) · [Leia em português](checkpoints.pt-BR.md)

Checkpoint weeks bring no new content: a timed mock interview, a review of what was weak, and time to catch up on cut scope.

| Day | Checkpoint 1 (week 5, modules 1 to 4) | Checkpoint 2 (week 9, modules 5 to 7) |
| --- | --- | --- |
| Mon | Review all flashcards; reread code and notes; list cut scope | Same |
| Tue | Catch up on cut scope, without AI | Same |
| Wed | 45-min system design, recorded: **digital wallet** | 45-min system design, recorded: **payment gateway or Pix system** |
| Thu | 5 random mastery tests + 30-min code review | Same, for modules 5 to 7 |
| Fri | 3 answers in English, 1 STAR story, 1 question outside your experience | Same, plus update your CV and LinkedIn |

**Pass if** every recording covers failures and idempotency without being asked. Whatever was missing becomes a flashcard.

## DSA (Monday to Wednesday, first 30 min)

| Day | Checkpoint 1 (week 5) | Checkpoint 2 (week 9) |
| --- | --- | --- |
| Mon | Re-solve 2 problems you marked "redo" in weeks 1 to 4, from scratch, no hints. | Re-solve 2 problems you marked "redo" in weeks 6 to 8, from scratch, no hints. |
| Tue | Mock coding interview (30 min, recorded): pick a random problem from weeks 1 to 4 and solve it explaining out loud, as in an interview. | Mock coding interview (30 min, recorded): pick a random problem from weeks 6 to 8 and solve it explaining out loud, as in an interview. |
| Wed | Complexity review: write the time and space complexity of every problem so far from memory, check, and turn mistakes into flashcards. | Complexity review: write the time and space complexity of every problem so far from memory, check, and turn mistakes into flashcards. |

Solve without AI, 30-minute timebox. Method and full list: [DSA track](../DSA.md).

## Code review checklist

Read it out loud before every review:

1. Money stored as float?
2. Non-idempotent operation with retries?
3. Read and write without a transaction or lock?
4. External call inside a database transaction?
5. Swallowed error, or unknown status treated as failure?
6. Secret or personal data in logs?
7. Missing timeout?
8. (From module 5) Consumer without dedupe?
9. (From module 6) Ledger entry that doesn't sum to zero?
