# Module 4, Wednesday: durable workflows and the transfer saga state machine

[Module 4](../../modules/04-sagas-outbox.md) · [Leia em português](day-3.pt-BR.md)

**Reading time:** about 45 minutes. Use the rest of the 2-hour block on the references at the end, then draw the state machine described in section 6 on paper.

This is an original text written for this course. It is based on the references listed at the end, and each section names the source it follows. Where an idea comes from a specific author, the text says so.

## Why this matters for a fintech

On Thursday you build an orchestrator, and on Friday you kill it 20 times at random points. The pass criteria are strict: total balance unchanged and no saga stuck. That is the real difficulty of sagas. Writing the happy path takes an hour. Making every step survive a crash, a retry, a timeout and a restart is the work.

Some companies solve this with a homemade `sagas` table and a recovery worker. Others adopt a durable workflow engine, such as Temporal or AWS Step Functions, that sells "your code survives crashes" as a product. Today you see what those engines do, so you can build the same guarantees by hand this week and explain in an interview when an engine is worth paying for.

## 1. The orchestrator is the weakest point

*This section applies Monday's and Tuesday's sources to the capstone; no single reference.*

An orchestrator is a loop that reads a saga's state, calls a participant, and writes the new state. A crash can hit at any of these points:

| Crash point | What survives | What must happen on restart |
| --- | --- | --- |
| After saving `STARTED`, before calling `accounts` | The saga row | Call the debit; it hasn't happened |
| After `accounts` debited Ana, before saving `DEBITED` | Ana's debit, saga still `STARTED` | Call the debit again; `accounts` must answer "already done" |
| After saving `DEBITED`, before calling credit | Debit and state | Call the credit |
| During the credit call (timeout) | Unknown | Retry the credit with the same key, or ask its status |
| After the credit failed for good, during compensation | Debit, state `COMPENSATING` | Retry the reversal until it succeeds |

Two rules cover every row of that table. **Each step is idempotent**, keyed by `saga_id` plus step, so repeating a step is harmless. **Something resumes non-terminal sagas**, so a saga whose orchestrator died doesn't wait forever. A durable workflow engine is, at its core, a product that gives you those two rules plus timers, retries and visibility.

## 2. Temporal: durable execution

*Main source: Temporal documentation, "What is Temporal?", plus its linked pages on Workflow Definitions and Activities.*

Temporal describes itself as a runtime for durable function executions. Its documentation says it "enables you to develop as if failures don't even exist." The core idea is **Durable Execution**: a Workflow Execution keeps its state and progress through crashes and outages. Temporal records each step in an **Event History**, and a Workflow Execution can resume from its last recorded event.

The platform has two parts. The **Temporal Service** (the Temporal Server, written in Go, plus a database, or Temporal Cloud as a hosted option) supervises executions. **Worker Processes**, which you host and operate, run your code using Temporal's SDKs. Note what that means operationally: Temporal doesn't remove the database from your design; it moves your saga state into its own database, which you must run or pay for.

Your code is split into two kinds of function:

- **Workflows** hold the orchestration logic: call this, then that, compensate on failure. The documentation says a Workflow Execution runs its Workflow Definition exactly once and to completion, whatever the duration, load or failures.
- **Activities** do the real work with side effects, such as calling `accounts` or a partner bank. The Activities page recommends that each Activity be idempotent, "so retries can be processed without duplicate side effects."

The split exists because of **replay**. When a worker crashes, another worker rebuilds the workflow's state by running the workflow code again and comparing what it does against the Event History. The Workflow Definition page says "Workflow code must be deterministic to support replay." So workflow code can't call APIs, read the clock or generate random numbers directly. Those go into Activities, which run outside the replay path, or through SDK functions whose results are stored in the history. A transfer saga in Temporal looks like ordinary TypeScript:

```typescript
// Workflow code: deterministic orchestration only (Temporal TypeScript SDK style).
// debit, credit and reverseDebit are Activities obtained with proxyActivities().
export async function transferSaga(t: Transfer): Promise<void> {
  await debit(t.from, t.amount, `${t.id}:debit`);        // Activity call
  try {
    await credit(t.to, t.amount, `${t.id}:credit`);      // Activity call
  } catch (err) {
    await reverseDebit(t.from, t.amount, `${t.id}:reversal`); // compensation
    throw err;
  }
}
```

If the worker dies after `debit` returns, a new worker replays the history, sees that `debit` already completed, skips calling it, and continues at `credit`. Your recovery worker does the same job by hand: it reads the saga's state from the `sagas` table and continues from there.

## 3. Retries, timeouts and timers in Temporal

*Main source: Temporal documentation, "Retry Policies", "Detecting Activity failures" and "Workflow Definition".*

Temporal's defaults are worth knowing because they show what a mature engine considers safe.

**Retries.** Activities retry by default. The Retry Policies page gives the defaults: initial interval 1 second, backoff coefficient 2.0, maximum interval 100 times the initial interval, unlimited attempts, and no non-retryable errors. Workflows are different: the page says "Workflow Executions do not retry by default." The lesson for your design is the same split: retry the individual step forever with backoff (it is idempotent), but don't restart the whole saga.

Unlimited retries are wrong for business failures. If `accounts` answers "Bruno's account is closed", retrying for a week won't help. You mark that error as non-retryable so the workflow sees the failure and compensates.

**Timeouts.** Temporal has four Activity timeouts:

| Timeout | Limits | Capstone equivalent |
| --- | --- | --- |
| Schedule-To-Start | Time a task waits in the queue for a worker | Rarely needed; the documentation suggests monitoring the latency metric instead |
| Start-To-Close | One attempt | HTTP timeout on each call to `accounts` |
| Schedule-To-Close | All attempts together | The per-step `deadline` in your `sagas` row |
| Heartbeat | Gap between progress reports from a long Activity | Not needed for short HTTP calls |

The documentation explains why Start-To-Close matters: the server doesn't detect that a worker crashed, so this timeout is what forces a retry after a crash. Either Start-To-Close or Schedule-To-Close must be set. Your recovery worker relies on the same idea: a saga whose `deadline` has passed is presumed abandoned and gets resumed.

**Timers.** A workflow can sleep durably. The Workflow Definition page shows that starting a timer emits a `StartTimer` command and suspends the execution until it fires, so "wait 24 hours, then check the partner bank" survives restarts. In your table, a timer is just `deadline` plus a worker that queries for expired rows.

## 4. AWS Step Functions: state machines as a service

*Main source: AWS Step Functions Developer Guide, "What is Step Functions?".*

Step Functions takes a different approach to the same problem. Instead of code that gets replayed, you declare a **state machine** (the guide calls it a workflow) of event-driven steps. Each step is a **state**. A **Task state** is a unit of work done by another service, such as calling a Lambda function or another AWS API. Each running instance is an **execution**. Work can also be done by **Activities**, workers that run outside Step Functions.

The guide describes two workflow types, and the difference is the most important thing on the page:

| | Standard | Express |
| --- | --- | --- |
| Semantics | Each step runs exactly once | Each step runs at least once, possibly more |
| Maximum duration | Up to one year | Up to five minutes |
| Pricing | Per state transition | Per number and duration of executions |
| History | Kept in Step Functions, visual debugging | Sent to CloudWatch |
| Fits | Long-running, auditable flows | High-volume event processing |

For a money transfer, Standard is the natural fit: it is auditable and can wait for a partner bank for days. Even so, "exactly once" describes the engine's step transitions. If a Task calls your `accounts` API and the response is lost, your API may still have done the work. Idempotency keys stay your job.

The guide also shows patterns that map to sagas. **Retry and Catch** let you retry a failed task or catch the failure and run alternative steps, which is where a compensation goes. A **Choice** state branches on data (the guide's example: auto-approve a credit increase below a limit, otherwise send it to a manager). **Wait for a callback with a task token** pauses the execution until an external system or person sends the token back, useful when a partner bank confirms a payout by webhook.

## 5. When is an engine worth the cost?

*This section compares the two engines above with the homemade approach of the capstone.*

| | Homemade (`sagas` table + worker) | Temporal | Step Functions |
| --- | --- | --- | --- |
| State lives in | Your Postgres | Temporal's database | AWS |
| Flow written as | State machine in code | Ordinary code, replayed | Declarative state machine |
| Retries, timers | You build them | Built in | Built in |
| Visibility | Your queries and dashboards | Event History UI | Execution history, visual console |
| Cost | Your engineering time | A cluster to run, or Temporal Cloud | Per transition (Standard) |
| Lock-in | None | Temporal SDK and model | AWS |
| Learning curve | Low to start, grows with every edge case | Determinism rules, versioning | AWS-specific definitions |

A reasonable interview answer: a few short sagas, owned by one team, with Postgres already in place, are fine with a table and a recovery worker. Many long-running flows (onboarding with KYC, payouts that wait days for a partner, disputes and chargebacks with human steps), across teams, justify an engine. The engine doesn't remove the need for idempotent participants, compensations or reconciliation. It removes the plumbing: persisted state, retries, timers and the resume loop.

Building it by hand this week is still the right call. You can't judge an engine's value until you have felt what it replaces.

## 6. On paper: the transfer saga state machine

*This section turns today's paper task into a checklist. It applies the sources above; the design is yours.*

Draw the state machine of the cross-service transfer saga before writing any code on Thursday. It should answer five questions.

**States.** List every state, and mark which are terminal. A starting set to argue with: `STARTED`, `DEBITED`, `CREDITED`, `COMPLETED`, `COMPENSATING`, `COMPENSATED` (or `FAILED`). Ask yourself whether you need an `UNKNOWN` state for a timed-out call, as in Module 1.

**Transitions.** For each state, which event moves it and to where? For example, "debit confirmed" moves `STARTED` to `DEBITED`; "credit rejected" moves `DEBITED` to `COMPENSATING`. Mark which transitions are retries of the same step and which advance the saga.

**Compensations.** For each state reached after a compensatable step, what undoes it? The debit's compensation is a reversal entry, never a delete. Mark the pivot: after which transition is the saga committed to finishing? In an internal transfer, the credit to Bruno is the last step that can fail; once it succeeds, only retriable steps remain.

**Per-step timeouts.** Give every non-terminal state a deadline and an action when it expires: retry with the same idempotency key, ask the participant for the status, or start compensating. Decide how many attempts a step gets before it gives up, and which errors are non-retryable (account closed, currency mismatch).

**Recovery.** Write in one sentence how a restarted orchestrator finds its work. The capstone's answer is a worker that selects non-terminal sagas past their deadline with `FOR UPDATE SKIP LOCKED` (Tuesday's pattern), so two workers never resume the same saga, and then executes the step for the saga's current state.

A check for your drawing: pick any arrow, imagine the process dies in the middle of it, and follow what the recovery worker does. If any arrow leads to a saga that never reaches a terminal state, or to a balance that changes twice, fix the drawing before you write the code.

## 7. Preparing the chaos test

*This section prepares today's lab. It applies the module's pass criteria.*

The lab today is a plan, not capstone code. Write the skeleton of `chaos/kill-orchestrator.sh` as comments and a task list:

1. Record the total balance across all accounts before the test.
2. Start a steady stream of transfers, including some designed to fail on the credit (a closed account, for example).
3. Twenty times: wait a random interval, kill the orchestrator container hard (`docker kill`, not a graceful stop), start it again.
4. Stop sending transfers and wait for the recovery worker to drain.
5. Check that the total balance equals the starting total.
6. Check that no saga is in a non-terminal state after its deadline plus a margin.
7. Exit non-zero if either check fails, so the script can run in CI.

Then list the failure cases you expect the test to hit, one line each, using the crash table from section 1. Each case should name the state the saga was in, what the recovery worker will do and which idempotency key protects the repeat. That list becomes the test plan for Friday.

## Notes to write today

1. What durable execution means in Temporal: Event History, replay, and why workflow code must be deterministic.
2. Workflows versus Activities: which one calls `accounts`, and why Activities should be idempotent.
3. Temporal's default Activity retry policy and the four Activity timeouts, mapped to your capstone.
4. Step Functions Standard versus Express: semantics, maximum duration and pricing basis.
5. When a workflow engine is worth its cost, and what it does not solve for you.
6. On paper: the transfer saga state machine, with states, transitions, compensations and a timeout for every non-terminal state.

## Check yourself

These make good flashcards (see the [flashcards guide](../../FLASHCARDS.md)).

- Why can't Temporal workflow code call an HTTP API directly?
- What happens to a Temporal workflow when its worker crashes after an Activity completes?
- Which Temporal timeout makes a retry happen after a worker crash, and why?
- What execution semantics do Step Functions Standard and Express workflows offer?
- Does "exactly once" in Step Functions remove the need for idempotency keys in your API? Why?
- Name two situations where a durable workflow engine is worth its cost.
- How does a recovery worker avoid two instances resuming the same saga?

## References

- **Main source:** Temporal documentation, ["What is Temporal?"](https://docs.temporal.io/temporal). Free. Then follow its links to ["Workflow Definition"](https://docs.temporal.io/workflow-definition) (determinism and timers) and ["Activities"](https://docs.temporal.io/activities). For retries and timeouts, read ["Retry Policies"](https://docs.temporal.io/encyclopedia/retry-policies) and ["Detecting Activity failures"](https://docs.temporal.io/encyclopedia/detecting-activity-failures). All free.
- **Main source:** AWS Step Functions Developer Guide, ["What is Step Functions?"](https://docs.aws.amazon.com/step-functions/latest/dg/welcome.html). Read the whole page, especially the Standard versus Express comparison and the use cases. Free.
- On paper: the state machine of the cross-service transfer saga, with states, transitions, compensations and per-step timeouts (section 6).
