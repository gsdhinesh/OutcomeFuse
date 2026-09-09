# Decision Model

Companion to [SPEC.md](SPEC.md). Holds the four taxonomies CAP-1 emits, the precedence ladder that resolves competing conditions, and the cause-versus-disposition mapping. The runtime models these as separate concepts and never collapses them: a record holding only one can answer neither "why did this step not happen" nor "how did this run finish."

## `policy_action` — what the runtime does next

Recorded on every decision.

| Value | Meaning |
| --- | --- |
| `proceed` | Execute the step as proposed |
| `proceed-with-substitution` | Execute, but on a cheaper model, compressed context, or a cached tool result |
| `deny` | This step does not happen; the run continues |
| `pause-for-approval` | Execution suspends until approval or timeout |
| `escalate` | Move to a more capable model per the contract's escalation policy |
| `request-human` | Hand the run to a person |
| `return-partial` | Return what exists, naming the unmet mandatory criteria explicitly |
| `terminate` | End the run |

## `decision_reason` — why that action was taken

Recorded on every decision. A stable code from a **versioned, extensible registry**. New codes may be added at any time; a published code is never redefined, repurposed or removed — a reused code silently rewrites the meaning of every historical record. Every code declares its family, so reporting aggregates by family rather than by enumerating codes.

| Family | Codes |
| --- | --- |
| Progress | `justified` |
| Denial | `unaffordable` · `low-value` · `duplicate` · `semantic-duplicate` · `optional-satisfied` · `unsafe` |
| Substitution | `cache-hit` · `context-compressed` · `cheaper-model-eligible` |
| Escalation | `escalation-complexity` · `escalation-low-confidence` · `escalation-criticality` · `escalation-gate-fail` |
| Governance | `approval-required` · `approval-granted` · `approval-denied` · `approval-timeout` |
| Termination | `sufficiency` · `exhaustion` · `no-progress` · `fail-closed` |

`justified` means the step advances an unmet mandatory criterion within budget.

## `terminal_reason` — why the run ended

Recorded **at most once**, only where the resulting action terminates the run. It names the **cause**, never the disposition. Where two causes could apply, the more specific wins, following the ladder below.

`stop-sufficient` · `halt-exhausted` · `halt-no-progress` · `approval-timeout` · `fail-closed` · `referred-human` · `returned-partial`

`returned-partial` and `referred-human` are terminal reasons **only where the hand-off is itself the cause** — a contract directing partial return or human referral with no exhaustion, stall, timeout or fail-closed condition present.

## `quality_state` — run-level

`not-evaluated` until the gate first executes, then `pass` or `fail`. `not-evaluated` is the *absence* of a verdict, not a third one: gate verdicts stay binary. `sufficiency` is not a valid decision reason while the state is `not-evaluated`, and no result is returned as passing in that state.

## Precedence ladder

Where more than one terminating or blocking condition applies to the same step, they resolve in this fixed order. The winning condition is recorded as the decision reason; a terminal reason is recorded only where the resulting action terminates the run.

1. **`fail-closed`** — the system cannot establish its own state, so nothing downstream can be trusted
2. **Human-approval gate** — a declared human gate outranks any automated decision
3. **`sufficiency`** — the contract is satisfied; further work is waste
4. **`exhaustion`** — no affordable step remains that could advance the floor
5. **`no-progress`** — progress has stalled while budget remains
6. **`low-value` / `unaffordable`** — this step is denied; the run continues

Two placements carry weight. Sufficiency outranks everything below it because a run that has met its floor is *done*, not *stuck*, and mislabelling it corrupts the metric the product rests on. Exhaustion outranks no-progress because when both fire together the Loop Fuse demonstrably failed to halt in time, and reporting the fuse would credit the governor for a save it did not make.

## Cause-versus-disposition mapping

Authoritative. Encode as a mapping; do not re-derive per call site.

| Situation | `decision_reason` | `policy_action` | `terminal_reason` |
| --- | --- | --- | --- |
| Floor met, budget remains | `sufficiency` | `terminate` | `stop-sufficient` |
| Floor unmet, nothing affordable advances it | `exhaustion` | `return-partial` or `request-human` | `halt-exhausted` |
| Floor unmet, budget remains, no progress across N iterations | `no-progress` | `terminate` | `halt-no-progress` |
| Gate fails, budget remains, contract directs human review | `escalation-gate-fail` | `request-human` | `referred-human` |
| Gate fails, budget remains, contract directs partial return | `escalation-gate-fail` | `return-partial` | `returned-partial` |
| Approval gate elapsed, `on_timeout` terminates | `approval-timeout` | `terminate` | `approval-timeout` |
| Approval gate elapsed, `on_timeout` escalates | `approval-timeout` | `escalate` | *none — the run continues* |
| Gate cannot produce a verdict | `fail-closed` | `request-human` | `fail-closed` |
| Ledger state lost | `fail-closed` | `terminate` | `fail-closed` |

A run that exhausts its budget and hands back a partial result has one cause and one disposition: `halt-exhausted` is why it stopped, `return-partial` is what the caller received. Recording `returned-partial` as the terminal reason would erase the cost story, and the cost story is the product.
