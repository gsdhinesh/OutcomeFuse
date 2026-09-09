# Evidence Standards

Companion to [SPEC.md](SPEC.md). The deliverable is partly a *claim*, so the rules that make the claim credible are normative, not methodology notes. Around a third of the build is apparatus whose only job is to make the headline number capable of being wrong.

**The falsifiable claim:** the same task, completed to the same declared quality bar, for measurably fewer tokens — **net of the governor's own overhead** — with no silent quality substitution.

## Primary metrics

All measurement is **baseline versus governed** on a frozen case set — same tasks, same tools, same model versions, same settings.

| Metric | Target |
| --- | --- |
| Net token reduction per completed outcome, inclusive of all governor overhead | Unset — awaiting the overhead study |
| Net estimated cost reduction per completed outcome | Unset — awaiting the overhead study |
| Tool-call reduction | Unset; reportable only alongside tool-suppression accuracy |
| Task-completion pass rate versus baseline | within 2 percentage points |
| Required evidence-field accuracy | ≥ baseline, and ≥ 90% absolute |
| Runs terminating cleanly — stopped, safely escalated, or referred for human review | 100%, non-negotiable |

The three savings targets are deliberately unset. The original figures were gross, set before governor overhead was accounted for; discounting them by guesswork would produce a number with no more standing than the one it replaced. They are set against **measured overhead on the calibration set**, and recorded before any governed evaluation-set result is executed or inspected. The two quality targets are retained because overhead changes what a result costs, not whether it is correct.

**Secondary:** P50 end-to-end latency reduction; zero accepted safety or adherence regressions; break-even task length.

## Counter-metrics

The primary metric has a perverse optimum: **the system that stops earliest always wins.** Every headline number here needs a paired number that can embarrass it. These are reported with equal prominence to the savings figures, and **every one carries a numeric threshold preregistered before any evaluation-set result** — a counter-metric that cannot fail is decoration.

| Counter-metric | Definition |
| --- | --- |
| False-sufficiency rate | Runs the gate passed that a blind human review fails |
| Tool-suppression error rate | `1 − tool-suppression accuracy`; one measurement reported in two directions, never computed independently |
| Escalation rate | Share of runs requiring model escalation or human intervention |
| Governor overhead share | Percentage of total run spend consumed by evaluator, planner and compression passes |
| Added latency | Wall-clock cost of governor decisions per step |
| Budget-breach rate | Runs that exceeded the cost ceiling to protect quality — the design working, but visible and bounded |

**Tool-suppression accuracy** has a fixed denominator: every tool call the governor suppressed — denied, deduplicated or served from cache. The numerator is those confirmed correct by **re-execution against the frozen case's tool implementation**: for a cache or duplicate suppression the re-executed result must be equivalent to the result reused; for an optional-call denial, a counterfactual run including the call must not change the gate verdict. Suppressions that cannot be checked are reported **unverified**, never assumed correct. Model-judged tool-use quality never contributes to this number.

**Marginal-value denials are measured separately.** Every denial is reported with the mandatory criteria unmet at decision time, the estimated benefit, the estimated cost, the resulting action, and whether it complied with the floor-protection rule. A denial that blocked progress toward an unmet mandatory criterion is reported as a **violation, not a saving**.

**Compression fidelity** is the rate at which citations, identifiers, numeric values, policy clauses and contract-required attributable facts present in raw tool output survive into the evidence capsule.

## Baseline fairness

- The baseline is a *reasonable* agent, not a strawman: full retrieved context per step, one capable model throughout, and a conventional evaluator/retry loop with a maximum-iteration safety limit.
- **The baseline's evaluator is genuine.** It checks the agent's own completion notion. What it does not check is an externally declared quality floor with named evidence fields, because that artifact does not exist without an Outcome Contract. Results are described as *self-assessed completion* versus *contract-assessed sufficiency* — never as "the baseline never stops."
- Prompt, tools, dataset, model version, temperature and settings are frozen, versioned and published before any comparison. The harness refuses a comparison where the executing baseline configuration differs from the frozen definition.
- The baseline is defined by the party who benefits from it losing. Publishing its definition is the only defence against that.
- The baseline arm is built by nobody: OFF is an **adapter state**, with the governor out of the call path entirely, so the arm shares no governor code and its latency is not governor-inflated.

## Rubric integrity

The quality rubric and case answer keys are frozen, versioned and content-hashed **before governor implementation begins**, in one operation with the per-workload contracts, the verifier registry, its tests and the coverage report. The harness refuses to publish a comparison on a drifted rubric hash. The same person writes the rubric and the optimizer that must satisfy it; freezing first is what prevents the optimizer being fitted to a moving target.

## Calibration set and evaluation set

Two case sets, different jobs, different rules. Conflating them would let the governor be tuned against the data it is judged on.

- **Calibration set** — may be used to measure governor overhead, determine break-even, exercise failure paths and establish preregistered targets and thresholds. Calibration results never contribute to a headline figure or the submission.
- **Evaluation set** — held sealed. No governed result is executed against it or inspected until savings targets, counter-metric thresholds, minimum case counts and blind-review sample sizes are preregistered. Case definitions are of course authored and known; it is the *results* that stay unseen. Only evaluation-set results support a headline claim.

There is no circularity: overhead is measured on calibration data, targets are tested on evaluation data that was sealed while they were being written. Derive targets on the evaluation set and they are fitted; set them without measuring overhead and they are guesses.

The **preregistration record** — targets, thresholds, minimum case counts, blind-review sample size — is its own hashed, timestamped artifact, and every evaluation-set run's manifest carries its hash. The harness refuses any comparison in which evaluation execution precedes preregistration.

## Run manifest

The first entry of every run's log. **No comparison may be published from a run without one.**

Run id · mode (`governed` · `baseline` · `shadow`) · `data_class` and the retention profile it selects, from the frozen case-set attestation with no default · contract hash · rubric and answer-key hash · verifier-registry version and hash · coverage-report hash · frozen baseline-configuration hash · case-set identity and `calibration` | `evaluation` · preregistration record hash (evaluation runs) · model ids with provider versions · pinned cost-table version · route · streaming disabled · enabled-mechanism registry with versions · adapter id and version · governor code version · record-store library version · seed and sampling parameters.

## Reportability — three gates

Evaluated by the harness alone. No other component re-derives any of them.

**Admissibility — hard; a failing run is refused, not labelled.** Non-streaming; adapter has passed conformance; manifest present and complete; and, for a headline claim, drawn from the sealed evaluation set with the preregistration hash present. The two arms of a comparison are **manifest-identical except for the run id and the fields the comparison exists to vary** — mode, and the enabled-mechanism registry. The harness compares manifests field by field and refuses on any other difference: route, model version, cost-table version, seed and adapter version included.

**Independence — graded; degrades the label, never refuses.** Gateway-metered figures are labelled *measured*. Where metering is unavailable the run falls back to governor-side counting and every figure it yields is labelled **self-reported**. Shadow figures are labelled *projected*. Degraded runs carry their degradation. Constraint-backed passes carry their qualifier.

**Publication accompaniment — hard.** The harness refuses to emit:

- a headline figure without its per-mechanism breakdown
- a tool-call reduction without tool-suppression accuracy
- any workload below its declared minimum case count
- a gross figure as the headline
- successes without the failures and escalations alongside them
- any counter-metric lacking its preregistered threshold
- any workload result without its verification-mode coverage report, carrying the **predominantly constraint-backed** label where it applies

## Reporting standard

- Report **net**, inclusive of all governor overhead. Gross may be shown alongside; it is never the headline. Overhead is its own line item.
- Report savings **per mechanism**. Ablation covers every savings-producing mechanism including the protected ones — if the savings turn out to come almost entirely from exact tool deduplication, the sufficiency claim is decoration. Measurement-only ablations do not imply every ablated configuration is a supported production configuration.
- Report mean, median and **absolute pass counts** across repeated runs, never a cherry-picked execution. With a modest case count a "within N percentage points" claim may not be statistically meaningful.
- Publish failures and escalations alongside successes.
- Prompt-caching savings are reported as a measured secondary lever and are never attributed to OutcomeFuse.
- Case-construction rules are published so the synthetic case set can be inspected rather than trusted.

## Claim discipline

- No claim of measured generalization beyond the workloads actually completed.
- Shadow-mode figures are labelled projected, never realized, and disclose the first divergence past which they are inference rather than observation.
- A pass resting wholly or partly on `constraint-backed` verification is labelled as such, never as `reference-backed`.
- Every obligation here applies to the submission artifact exactly as it applies to a written report.

## Blind review

A fixed sample of passed runs per workload is reviewed blind, sufficient to compute false-sufficiency rate. The reviewer sees the deliverable and the contract, and does **not** see the gate verdict, the decision record, or which configuration produced the run. The renderer that produces the review packet is structurally denied access to the verdict, the decision record and the run manifest.

The residual bias is stated rather than designed away: the blind reviewer is the same person who wrote the rubric and built the optimizer. Blinding the verdict and configuration reduces it; freezing the rubric by hash reduces it further; sealing the evaluation set until every number is recorded stops the remainder. None of that removes the conflict — it makes cheating visible in the record.
