# Case Construction Rules v1

**Status:** E1a draft. Frozen at E1b with the cases themselves.

Published so the synthetic case set can be **inspected rather than trusted**.
A case set authored by the same person who builds the optimizer is only credible
if the rules that produced it are visible and the cases can be checked against
them.

## Scope

- **Synthetic only.** No production, customer or confidential data. Every run's
  manifest carries `data_class: synthetic` from the case-set attestation, with
  no default — a run without one is refused. Anything other than `synthetic`
  refuses persistence of evidence and decision log alike until an approved
  production-data governance profile exists.
- **Four committed workloads**, all in scope, none a stretch goal:
  `doc-research`, `code-triage`, `data-sql`, `supply-chain`.

## Rules every case obeys

1. **The answer key is authored with the case, never after a run.** A key
   written after seeing model output is fitted to the output. Keys are committed
   in the same change as the case.
2. **Every mandatory criterion in the workload's contract is satisfiable from
   the case's own data.** A case that cannot in principle pass is a broken case,
   not a hard one.
3. **The key pins exactly the fields the contract checks against it** — no more.
   An unused key field invites a later criterion to be fitted to it.
4. **Solvable by a competent agent within the contract's ceilings.** If the
   ceiling makes a case unsolvable, the comparison measures the ceiling.
5. **Not solvable by guessing.** Controlled-vocabulary answers need enough
   plausible alternatives that a blind guess is unlikely to hit. Recorded per
   case as `guess_baseline`, so a suspiciously high pass rate is diagnosable.
6. **The evidence exists in the corpus.** Every citable identifier the key
   references resolves in the case's citable index. A case whose answer cannot
   be evidenced tests fabrication, not competence — those exist, and are tagged.
7. **Deterministic tools return deterministic results.** A tool declared
   deterministic in the contract returns identical output for identical
   canonical arguments across the whole case set. If that fails, cache-hit and
   deduplication measurements are meaningless.
8. **No case requires a side-effecting tool to pass.** Side-effecting tools are
   present so the conformance battery can prove they are never suppressed, not
   because the work needs them.

## Difficulty mix

Each workload's corpus is authored across a declared mix, recorded per case as
`difficulty`, so results can be read by stratum rather than as one average:

| Stratum | Share | Character |
| --- | --- | --- |
| `direct` | ~30% | One or two tool calls; the answer is retrievable. |
| `multi-hop` | ~45% | Requires combining three or more pieces of evidence. |
| `distractor-heavy` | ~15% | Contains plausible-but-wrong candidates the corpus supports superficially. |
| `unanswerable` | ~10% | The corpus does not contain the answer. The correct outcome is a partial result naming the unmet criteria, or a human referral — never a confident answer. |

The `unanswerable` stratum is the one that matters most and is the easiest to
omit. Without it, a run that fabricates confidently is indistinguishable from
one that answers correctly, and the false-sufficiency counter-metric has nothing
to bite on.

## Distractors

- Every `distractor-heavy` case names its distractors in the key, so a wrong
  answer can be classified as *fell for the intended trap* rather than merely
  wrong.
- Distractors are **plausible**, not adversarial nonsense: near-miss dates,
  superseded policy clauses, a similarly-named symbol in another module, a
  correct figure for the wrong period.

## Calibration and evaluation split

Two sets, different jobs, different rules. Conflating them would let the
governor be tuned against the data it is judged on.

- **Split is by case, authored into the case, and never rebalanced after
  results are seen.** The split field is part of the case and is frozen with it.
- **Calibration set** — measures governor overhead, determines break-even,
  exercises failure paths, establishes preregistered targets. **Calibration
  results never contribute to a headline figure or the submission.**
- **Evaluation set** — sealed. Case definitions are authored and known; it is
  the **results** that stay unseen until savings targets, counter-metric
  thresholds, minimum case counts and blind-review sample size are
  preregistered.
- Both sets carry the same difficulty mix. A calibration set that is easier than
  the evaluation set produces overhead figures that do not transfer.

There is no circularity here: overhead is measured on calibration data, and
targets are tested on evaluation data that was sealed while those targets were
being written.

## Case record shape

```yaml
case_id: dr-014
workload: doc-research
split: calibration          # calibration | evaluation
difficulty: multi-hop
data_class: synthetic
guess_baseline: 0.08        # probability a blind guess satisfies the key
prompt: >
  ...
corpus_ref: corpora/doc-research/v1
answer_key:
  answer_code: ...
  primary_source_id: ...
distractors: [...]          # distractor-heavy cases only
notes: >
  Why this case exists and what it is meant to catch.
```

## Case counts

Not fixed here. The **minimum case count per workload** is a preregistered
number recorded before any governed evaluation-set result is executed or
inspected, and the harness refuses to publish a comparison for a workload below
it. E1a authors the corpus; preregistration sets the bar the corpus must clear.

Counts are reported as **absolute pass counts** alongside mean and median, never
as percentages alone — with a modest corpus a "within N percentage points" claim
may not be statistically meaningful, and reporting the absolute counts is what
lets a reader see that for themselves.
