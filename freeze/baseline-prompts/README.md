# Baseline prompt templates v1 (FR64)

**Status:** E1a draft. Frozen and content-hashed at E1b together with
[BASELINE.md](../BASELINE.md), which is what promises these files exist.

## The shared-task-block rule

Each template here is the **shared task block**: the bytes both arms send.

The baseline arm sends this block and nothing else. The governed arm sends this
block *verbatim*, then appends whatever the enabled mechanisms produce. The
appended material is the mechanism under test; the block underneath it is held
identical so the comparison is about governance rather than about who got the
better prompt.

Two consequences worth being explicit about, because both are places a
comparison could be quietly rigged:

1. **No template names a criterion, a threshold, or an answer key.** A quality
   floor in the shared block would hand the baseline the very artifact
   BASELINE.md says it does not have, and the governed arm's advantage would
   already be baked in before the governor ran.
2. **Every template names the full output shape and the controlled
   vocabularies.** This is not a floor — it is the parsing contract. Without it
   the baseline fails `units-match-key` on wording rather than on reasoning, and
   the result becomes a story about output formatting.

The line between the two is: *what to produce* is shared, *whether it is good
enough* is not.

## Controlled vocabularies are stated, membership is not the test

Several criteria are exact matches against an answer key drawn from a closed
set. Telling the agent the set is fair — a real analyst knows the taxonomy they
are classifying into. It proves only that the label is legal. Which label is
correct remains entirely unaided, and that is what the key checks.

## Placeholders

Every `{{...}}` is substituted by the harness from the case record. A template
with an unsubstituted placeholder at send time is a harness bug, not a prompt
variation, and the run is refused rather than sent.

| Placeholder | Source |
| --- | --- |
| `{{question}}` | the case's task text |
| `{{case_id}}` | case identifier, for the transcript only |
| `{{as_of}}` | the case's decision date, where the workload has one |
| `{{region}}` | the case's region, where the workload has one |
| `{{report}}` | the failing-behaviour report, code-triage only |
| `{{po_id}}` | the flagged purchase order, supply-chain only |

## Unanswerable cases

Roughly one case in ten cannot be answered from the corpus. No template says so,
because saying so is a hint. Each instead permits `"insufficient_evidence": true`
with the missing evidence named — available on every case, load-bearing on a few.
That is what makes a fabricated answer a choice rather than an inevitability.
