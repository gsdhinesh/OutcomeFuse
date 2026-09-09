# Quality Rubric v1 — blind human review

**Status:** E1a draft. Frozen and content-hashed at E1b, in one operation with
the cases, answer keys, contracts, verifier registry, its tests and the coverage
report. The harness refuses to publish a comparison against a drifted hash.

This rubric is **not** the gate. The gate is deterministic and lives in the
verifier registry. This rubric is what a human applies to a sample of runs the
gate already **passed**, in order to compute the **false-sufficiency rate** —
the counter-metric that can embarrass the headline.

It is frozen before governor implementation begins because the same person
writes the rubric and builds the optimizer that must satisfy it. Freezing first
is what stops the target moving.

## What the reviewer sees, and does not

**Sees:** the deliverable, the Outcome Contract it ran under, and the case
prompt.

**Does not see:** the gate verdict, the decision record, the run manifest, which
arm produced it, or whether any mechanism was enabled. The review packet
renderer is structurally denied access to those — not merely instructed to omit
them.

## The judgement

One question, answered before anything else:

> **Would you ship this to the person who asked for it?**

`accept` · `reject`

A `reject` on a run the gate passed is a **false sufficiency**. That is the
number this rubric exists to produce. Everything below exists to make that
judgement consistent between cases, not to produce a score.

## Rejection reasons — record every one that applies

| Reason | Meaning |
| --- | --- |
| `wrong` | The substantive answer is incorrect. |
| `unsupported` | The answer may be right, but the cited evidence does not establish it. |
| `incomplete` | A material part of the question is unaddressed. |
| `fabricated` | Cites something that does not exist, or asserts a fact absent from the corpus. |
| `unusable` | Correct but not actionable — no disposition, no location, no figure a reader could use. |
| `unsafe` | Recommends an action the evidence does not license, or a side-effecting action without justification. |

`unsupported` is the load-bearing one. It is the criterion the deterministic
gate **cannot** reach — every contract classifies "conclusion is supported"
as advisory — so it is the most likely source of a false sufficiency and the
reviewer should look for it first.

## Calibration notes for the reviewer

- **Judge the deliverable, not the effort.** A short answer that is right and
  evidenced beats a thorough one that is wrong.
- **Do not reward format compliance.** The gate already checked structure. If a
  perfectly-shaped deliverable is wrong, it is `reject` / `wrong`.
- **"Right for the wrong reason" is `unsupported`, not `accept`.** A correct
  answer whose cited passages do not support it is precisely the failure mode
  the counter-metric is hunting.
- **Do not infer the arm.** Terser output is not evidence of the governed arm;
  assuming it is would leak the blinding.
- **Abstain rather than guess.** `unsure` is recordable and is reported
  separately. A forced binary on a genuinely ambiguous case adds noise, not
  signal.

## Sampling

The blind-review sample size per workload is **preregistered** alongside the
savings targets, counter-metric thresholds and minimum case counts, before any
governed evaluation-set result is executed or inspected. It is deliberately not
fixed here — E1a authors the instrument, preregistration sets the dosage.

## The bias this does not remove

The blind reviewer is the same person who wrote this rubric and built the
optimizer it judges. Blinding the verdict and the configuration reduces that.
Freezing the rubric by hash reduces it further. Sealing the evaluation set until
every number is recorded stops the remainder from being actionable.

None of it removes the conflict. It makes cheating visible in the record, which
is the most an unaudited solo build can honestly claim.
