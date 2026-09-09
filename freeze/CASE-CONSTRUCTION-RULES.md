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

1. **The answer key is derived from the corpus, never hand-written.** Each
   answerable case carries `reference` SQL, and the key is produced by executing
   it against the frozen corpus (`freeze/derive_answer_keys.py`). A key typed by
   hand can silently disagree with the data it describes, and at the freeze both
   are sealed together and the disagreement becomes permanent.
2. **Keys live in a separate file from the cases.** The harness surfaces only
   `prompt` to the agent; the correct answer must not be one field access away
   from the text handed to the model.
3. **Every mandatory criterion in the workload's contract is satisfiable from
   the case's own data.** A case that cannot in principle pass is a broken case,
   not a hard one.
4. **The key pins exactly the fields the contract checks against it** — no more.
   An unused key field invites a later criterion to be fitted to it.
5. **Solvable by a competent agent within the contract's ceilings.** If the
   ceiling makes a case unsolvable, the comparison measures the ceiling.
6. **Not solvable by guessing.** Controlled-vocabulary answers need enough
   plausible alternatives that a blind guess is unlikely to hit. Recorded per
   case as `guess_baseline`, so a suspiciously high pass rate is diagnosable.
7. **The evidence exists in the corpus.** Every citable identifier the key
   references resolves in the case's citable index. A case whose answer cannot
   be evidenced tests fabrication, not competence — those exist, and are tagged.
8. **Deterministic tools return deterministic results.** A tool declared
   deterministic in the contract returns identical output for identical
   canonical arguments across the whole case set. If that fails, cache-hit and
   deduplication measurements are meaningless.
9. **No case requires a side-effecting tool to pass.** Side-effecting tools are
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
- **A distractor must be verified to discriminate.** Compute the wrong reading
  against the corpus and confirm it yields a different answer from the right
  one. A trap that returns the correct value by coincidence of the data tests
  nothing while looking rigorous — this has already happened once, in the first
  draft of `ds-e-007`, and was caught only by checking rather than assuming. A
  distractor that does not discriminate is either fixed or labelled as
  non-discriminating; it is never left to imply a rigour it does not have.

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
case_id: ds-c-014
difficulty: multi-hop          # direct | multi-hop | distractor-heavy | unanswerable
guess_baseline: 0.0           # probability a blind guess satisfies the key
units: usd
expected_outcome: answer      # answer | partial
prompt: >
  The only field the agent ever sees.
reference:                    # omitted for unanswerable cases
  value_sql: SELECT ...
  value_is_cents: true
  rows_sql: SELECT COUNT(*) ...
distractors:                  # distractor-heavy cases only
  - id: adjacent-sku
    detail: >
      What the wrong reading is, and that it was verified to discriminate.
notes: >
  Why this case exists and what it is meant to catch.
```

Split, workload, `data_class` and `corpus_ref` are declared once per file rather
than repeated per case. The derived key carries `result_value`, `units` and
`row_count` for answerable cases, or `expected_outcome: partial` and the
`unmet_criteria` a correct partial result must name.

**`row_count` means contributing base rows, not rows returned.** An aggregate
returns one row whatever it computes, so counting returned rows would make the
criterion vacuous. Counting contributing rows is what catches a right-looking
figure computed over the wrong row set.

## Case counts

Not fixed here. The **minimum case count per workload** is a preregistered
number recorded before any governed evaluation-set result is executed or
inspected, and the harness refuses to publish a comparison for a workload below
it. E1a authors the corpus; preregistration sets the bar the corpus must clear.

Counts are reported as **absolute pass counts** alongside mean and median, never
as percentages alone — with a modest corpus a "within N percentage points" claim
may not be statistically meaningful, and reporting the absolute counts is what
lets a reader see that for themselves.
