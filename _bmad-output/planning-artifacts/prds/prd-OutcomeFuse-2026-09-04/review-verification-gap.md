---
title: "OutcomeFuse PRD — Verification-Gap Review"
status: review
created: 2026-09-04
reviewer: verification-gap lens
artifact: prd.md
supporting: addendum.md
---

# Verification-Gap Review — OutcomeFuse PRD

**The single question applied to every claim, requirement and metric in this document:**
_What observation would show this to be false, and does the PRD require that observation to be made?_

Two failure classes are distinguished throughout:

- **[UNFALSIFIABLE]** — the statement is written so that no observation could contradict it. The defect is in the wording.
- **[UNCHECKED]** — the statement is falsifiable, but no requirement obliges anyone to make the observation that would falsify it. The defect is a missing requirement.

A third label, **[SELF-ENFORCING]**, marks the cases the PRD gets right — where a requirement makes the harness refuse to proceed rather than asking a human to remember.

---

## 0. Headline verdict

This PRD is unusually strong on *stating* falsifiability obligations and unusually weak on *mechanizing* them. It contains a small number of genuinely self-enforcing requirements — FR61 (harness refuses drifted baselines), FR57 (refuses under-powered workloads), FR65 (refuses a tool-call figure without its accuracy) — and these are the model the rest of the document should have followed and did not.

The dominant pattern is that §8's evidence standards are enforced exactly where the PRD happened to write a refusal into the harness, and are honour-system everywhere else. The most consequential instance: **§8.1's baseline freeze is mechanically enforced by FR61, while §8.2's rubric freeze — the mitigation for the risk the PRD itself names as most serious — has no enforcing requirement at all.**

The second most consequential: the PRD deliberately defers its three headline savings targets to post-measurement (§3.1 restatement gate) while simultaneously insisting elsewhere that numbers must be fixed *before* seeing results (Q4, Q6). It applies pre-registration discipline to the counter-metric sample and withholds it from the target the product will be judged by.

---

## 1. Claims in sections 1, 3 and 8

### 1.1 Section 1 — Vision & Positioning

#### C-1. The four compounding costs (§1.2) — **[UNCHECKED, critical]**

> "**Overrun loops** — the most expensive failure. The agent reaches a sufficient answer at iteration three and works to iteration eight because nothing told it to stop."

This is a ranking claim: of four named cost drivers, one is asserted to dominate. It is falsifiable — an ablation showing that context carry-forward or redundant tool calls account for more recovered spend than overrun loops would contradict it directly.

**No requirement produces that observation.** FR13 is the only attribution requirement in the document and it is a two-way split:

> "**FR13.** The ledger SHALL attribute every unit of spend to either **task work** or **governor overhead** (evaluation, planning, compression), and SHALL report the two separately."

Task-work spend is never decomposed by which mechanism recovered it. The harness (FR55–FR65) reports baseline versus governed totals. Nothing measures the contribution of any individual mechanism.

**Missing requirement:** the harness SHALL execute per-mechanism ablation configurations — each conditional mechanism disabled in turn — and SHALL report savings attributable to each. NFR10 already mandates independent disableability, so the capability exists and is simply never exercised for measurement. See §4 of this review for the full consequences.

#### C-2. The category-boundary claim (§1.3) — **[UNCHECKED, moderate]**

> "**no mechanism we could examine terminates a run early because the output already meets a declared, measured bar while budget remains.**"

Credit where due: this was correctly narrowed from a categorical claim to a scoped survey claim, and §1.3 states its own limitation ("it is a survey — not a proof of absence"). It is falsifiable: one counter-example retires it.

But the addendum records that the survey is partly unverified:

> "Langfuse and LangGraph rows were not fetched successfully and rest on prior knowledge; re-verify before external use."

**No requirement obliges that re-verification.** §8.4 "Claim discipline" governs claims about *measured generalization across workloads* and *shadow-mode labeling*; it says nothing about competitive-positioning claims. FR76 requires that every **figure** in the submission be traceable to a harness run — the positioning claim is not a figure, so it passes through the submission gate untouched. The strongest verbal claim in the product is the one claim the evidence standards do not cover.

**Missing requirement:** competitive claims restated in any external artifact SHALL cite a dated, re-verified source, and SHALL be downgraded to "not examined" where verification failed.

#### C-3. "Turn the UI off and the savings still happen" (§1.5 principle 3) — **[UNCHECKED, low]**

FR71 asserts the property — "Disabling it SHALL NOT change governed behaviour or realized savings" — but no requirement asks the harness to ever run with F14 disabled and compare. The property is testable in one line and is never tested. Low severity only because F14 is cut position 1 and will likely not exist.

#### C-4. "No silent quality substitution" (§1.4) versus the 2pp allowance (§3.1) — **[UNFALSIFIABLE as written, moderate]**

> §1.4: "with no silent quality substitution."
> §3.1: "Task-completion pass rate versus baseline | within 2 percentage points"

These are in tension and the tension is never resolved. A 2pp pass-rate drop *is* a quality substitution; the PRD's defence is that it is not *silent*, because FR22 attaches a gate verdict to every result. But "silent" is nowhere defined, so no observation can establish that a substitution was silent rather than disclosed. As written the claim cannot fail.

**Missing definition:** state the operational test — e.g. a substitution is silent if any of {model escalation, compression, cache reuse, denied step} affected a returned result and is absent from that result's decision record. That is checkable against FR51.

#### C-5. The falsifiable claim itself (§1.4) — **[UNFALSIFIABLE until §3.1 is restated, critical]**

> "The same task, completed to the same declared quality bar, for measurably fewer tokens — **net of the governor's own overhead**"

"Measurably fewer" has no threshold, because §3.1 deliberately leaves all three savings targets unset. The section titled "The falsifiable claim" is, at the moment of writing, the least falsifiable statement in the document: any net reduction above zero satisfies it, including 0.5%. This is defensible *only* if the restatement gate is itself binding — and it is not (see G-1 below).

### 1.2 Section 3 — Success Metrics

#### C-6. The restatement gate (§3.1) — **[UNCHECKED, critical] — the single most serious gap**

> "**On completion of the overhead study (FR62), savings targets SHALL be set against measured overhead.** Until then this PRD carries the measurement obligation, not a number."

The reasoning for deferral is sound. The gap is what the deferral does not constrain:

- It does not say **who** sets the targets.
- It does not say the targets are set **before** the governed results are known — only after the *overhead study*, which is a different measurement.
- It does not prohibit setting the target to whatever the measured result turns out to be.

Compare the discipline the PRD applies to itself two sections later:

> §11, Q4: "**Sample size N still unset** — must be fixed before the first evidence run, not after seeing results"
> §11 note: "Fixing N and the minimum case count *before* seeing any results is what prevents the sample from being chosen to flatter the outcome."

The PRD identifies post-hoc number selection as a bias vector, writes a guard for the counter-metric sample, and omits the identical guard for the headline target. A target set after the result is known cannot be missed. **The primary metric is currently unfailable by construction.**

**Missing requirement:** savings targets SHALL be recorded, timestamped and published on completion of FR62 and **before** any governed comparison run is executed, and SHALL NOT be revised downward thereafter. If revised, both figures SHALL be published with the revision reason.

#### C-7. "Budget compliance — runs terminating cleanly … 100%" (§3.1) — **[UNFALSIFIABLE as written, moderate]**

> "runs terminating cleanly (stopped, safely escalated, or referred for human review) | 100%"

The parenthetical enumerates three states, and between them plus the fail-closed halts of FR81–FR83 they cover essentially every terminal state the system can reach other than an uncaught crash. The metric is near-tautological: it is 100% unless the process dies. A metric that can only be failed by a segfault is not measuring budget compliance.

**Missing definition:** enumerate *unclean* termination explicitly — e.g. a run that exceeded the ceiling without the contract requiring the floor; a run that returned a result with no gate verdict; a run whose stop classification (FR26/FR84) cannot be reconstructed from its record. Then 100% means something.

#### C-8. "Task-completion pass rate … within 2 percentage points" — **[UNCHECKED, high — arithmetic risk]**

§8.3 flags the problem honestly:

> "With a modest case count a 'within N percentage points' quality claim may not be statistically meaningful, so absolute counts SHALL accompany every percentage."

But the 2pp target is retained regardless. Q6 leaves the minimum case count unset. At any plausible MVP case count — 20 cases per workload makes one case worth 5pp; 50 cases makes it 2pp — the target is either unmeasurable or has a resolution of exactly one case. Nothing in the PRD requires the case count to be large enough for the retained target to be evaluable.

**Missing requirement:** the minimum case count (FR57) SHALL be set such that the declared quality tolerance is resolvable at that count, or the tolerance SHALL be restated in absolute case counts.

#### C-9. "Zero accepted safety or adherence regressions" (§3.2) — **[UNFALSIFIABLE, moderate]**

The word "accepted" makes this self-fulfilling: a regression that is not accepted is not counted, and nothing defines who accepts or on what grounds. Rewrite as "zero safety or adherence regressions; any observed regression published with its disposition."

#### C-10. "Break-even task length" (§3.2) — **[SELF-ENFORCING]** via FR62. One of the better-instrumented claims in the document. Note the scope limit flagged in §4 below: it is whole-governor break-even, not per-mechanism.

### 1.3 Section 8 — see §5 of this review, which treats §8 in full.

---

## 2. Section 3.3 counter-metrics — thresholds

### The structural finding

**None of the six counter-metrics has a threshold.** The §3.1 table has a `Target` column; the §3.3 table has `Definition` and `Why it exists`. The reporting standard is:

> "are reported with equal prominence to the savings figures"

Equal prominence is a presentation obligation. It is not a failure condition. **A counter-metric with no threshold cannot fail, and therefore cannot constrain the primary metric it exists to constrain.** The perverse optimum §3.3 opens by naming — "the system that stops earliest always wins" — is left open, because a false-sufficiency rate of 40% is fully compliant with this PRD as long as it is printed next to the savings number in the same font.

Worse, §3.1 at least binds itself to a future restatement. **§3.3 contains no restatement gate at all.** The PRD commits to setting its savings targets later and never commits to setting its counter-metric thresholds ever.

### Per counter-metric

| Counter-metric | Threshold? | Producing requirement? | Assessment |
|---|---|---|---|
| False-sufficiency rate | None | FR64 (protocol; N unset per Q4) | **[UNCHECKED, critical]** — measured but unbounded |
| Tool-suppression error rate | None | FR65 | **[UNCHECKED, high]** — refusal-to-report is enforced, the rate itself is unbounded |
| Escalation rate | None | **None** | **[UNCHECKED, high]** — no FR produces it |
| Governor overhead share | None | FR59, NFR2 | **[UNCHECKED, moderate]** — well produced, unbounded |
| Added latency | None | FR58 (duration), NFR1 explicitly declines | **[UNCHECKED, moderate]** |
| Budget-breach rate | "must be visible and bounded" — no bound given | **None** | **[UNCHECKED, high]** — the PRD says bounded and does not bound it |

### Two counter-metrics have no producing requirement whatsoever

FR58 enumerates what the harness captures per run:

> "model and version, tokens, cached tokens, tool calls, retries, duration, outcome, gate verdict, and any safety or adherence evaluation result"

**Escalation rate** and **budget-breach rate** appear nowhere in F13. Neither is in FR58's capture list, neither has a dedicated requirement, and neither is named in §8.3's reporting standard. Two of six counter-metrics — including the one guarding UJ-2's entire narrative, where Marcus's run "breached its cost ceiling. That shows up in the budget-breach counter-metric, as designed" — are asserted in §3.3 and implemented by nothing.

**Missing requirement:** FR58 SHALL additionally capture escalation events (model and human), budget-ceiling breaches, and fail-closed halts by class, and the harness SHALL report all six §3.3 counter-metrics per workload.

### Thresholds that should be set

Offered as concrete anchors, not as the only defensible values:

1. **False-sufficiency rate** — expressed as an absolute count with its sample size, not a bare percentage (consistent with FR56). A defensible MVP bar: zero false-sufficiency findings in the reviewed sample; any non-zero finding blocks publication of the savings figure until the gate is corrected and the sample re-run. This is the only counter-metric that is a direct inverse of the headline, and it warrants a hard gate rather than a tolerance.
2. **Tool-suppression error rate** — a maximum, symmetric with the above: e.g. ≤ 5% of denied/cached calls incorrectly denied, with absolute counts. Anything above it invalidates the tool-call reduction figure that FR65 already refuses to publish unaccompanied.
3. **Escalation rate** — bounded relative to baseline, not absolute: governed escalation rate SHALL NOT exceed baseline escalation rate by more than a declared margin. Otherwise savings are simply cost transferred to humans, which §3.3 names ("Savings bought by pushing work onto people are not savings") and then does not prevent.
4. **Governor overhead share** — a ceiling above which the run is reported as unprofitable, derived from FR62's break-even output rather than guessed. This one legitimately depends on measurement — but the *rule* for deriving it can be fixed now.
5. **Added latency** — NFR1 already promises a bound "established against measured baseline step latency." Bind NFR1 to the same restatement event as §3.1 so it cannot drift indefinitely.
6. **Budget-breach rate** — the PRD says "bounded." Give it a number, and distinguish breaches where the contract required the floor (design working) from breaches where it did not (defect). Currently both count identically, which means the metric cannot separate the two cases it exists to separate.

### One missing counter-metric

FR64 measures human disagreement **only on passed runs**:

> "blind human review of a fixed sample of **passed** runs per workload"

The inverse error — runs the gate **failed** that a human would have passed — is never sampled. That error costs money in exactly the way this product exists to prevent: unnecessary retries, unnecessary escalation, unnecessary human referral. The gate's calibration is measured in one direction only, and the direction left unmeasured is the one that inflates the escalation rate and the budget-breach rate the PRD also does not bound.

**Missing requirement:** the blind review sample SHALL include failed and escalated runs alongside passed runs, and the harness SHALL report false-insufficiency rate alongside false-sufficiency rate.

---

## 3. Section 5 SHALLs asserting unverifiable behaviour

Requirements are listed by severity. Each is a behaviour the PRD mandates with no stated way to observe whether it happened.

### 3.1 Critical

#### FR3 — unverifiable by construction

> "**FR3.** No enforcement mechanism SHALL alter execution except as directed by a policy decision. Mechanisms do not act autonomously."

The audit trail records **decisions** (FR4, FR51). An autonomous mechanism action, by definition, has no decision — so it produces no record, so it is invisible in exactly the artifact that would detect it. Absence of evidence is guaranteed regardless of whether the violation occurred. This is the design principle of §1.5.2 ("The policy decides; mechanisms execute") expressed as a requirement, and it is unfalsifiable as written.

**Missing requirement:** every execution-affecting effect SHALL carry the identifier of the decision that authorized it, and the harness SHALL flag any effect lacking one. This converts an unobservable negative into a checkable join.

#### FR15 — the differentiator, unmeasured and undefined

> "**FR15.** The ledger SHALL reject a proposed step whose **expected benefit is low relative to its cost** … Affordability is not the only ground for denial."

The PRD is explicit about this requirement's importance:

> §5 note: "it is where the differentiation in §1.3 actually lives."
> §11.2: "FR15 must actually be built, or the distinction is rhetorical"

Two gaps compound:

1. **[UNFALSIFIABLE]** "Low expected benefit" is undefined. Q7 concedes this: "**Unset.** … something must be specified before F3 is built." Until it is specified, no observation can show FR15 was violated, because no observation can show a rejection was wrong.
2. **[UNCHECKED]** There is no accuracy measure for FR15 decisions. FR65 measures tool-suppression accuracy, which covers *tool call* denials — but FR15 governs steps generally, including non-tool reasoning steps. The count of FR15-grounded denials is not required to be reported, and their correctness is not required to be assessed.

The result: the requirement the PRD names as the seat of its differentiation is the requirement with the weakest verification story in the document. If FR15 is silently implemented as "deny if unaffordable or duplicated" — precisely the gateway behaviour §1.3 defines itself against — nothing in this PRD would detect it, and the demo would look identical.

**Missing requirements:** (a) FR15's marginal-value estimator SHALL be specified and recorded per decision (the estimate, the cost, the threshold); (b) the harness SHALL report FR15 denial counts and SHALL subject a sample to the same blind-review accuracy check as FR65.

#### FR36 — the strongest correctness claim, entirely unmeasured

> "**FR36.** Compression SHALL preserve citations, identifiers, numeric values and policy clauses verbatim. **Compression SHALL NOT drop an attributable fact.**"

Restated as a governance commitment in §9 ("A saving obtained by losing a citation is a defect") and dramatized in UJ-3 ("evidence compressed, with the citations preserved verbatim through the compression").

This is highly falsifiable — diff the pre-compression evidence against the capsule for retained identifiers, citations and numerals — and **nothing in F13 requires the diff.** No compression-fidelity metric exists in §3.1, §3.2 or §3.3. FR58's capture list does not include it. A compression that drops 5% of citations while cutting tokens 30% would show up as a clean win in every figure this PRD requires anyone to produce, unless the dropped citation happened to be a contract-required evidence field caught by FR17.

**Missing requirement:** the harness SHALL measure compression fidelity — retention of citations, identifiers and numeric values through every compression pass — and report it as a counter-metric. Compression savings SHALL NOT be reported without it, on the FR65 pattern.

### 3.2 High

#### FR26 / FR84 — stop-classification correctness is asserted, never checked

> "**FR26.** A halt caused by lack of progress SHALL be recorded and reported as **distinct** from a stop caused by sufficiency."
> "**FR84.** A fail-closed halt SHALL be recorded and reported as distinct from both a sufficiency stop and a loop-fuse halt."

UJ-3 makes the load-bearing claim: "a stop that was really an exhaustion. The record distinguishes all three." The requirements guarantee that three *labels* exist. They do not guarantee any label is correct. A mislabelling bug converts an exhaustion halt into a sufficiency stop, and every downstream figure — savings, budget compliance, false-sufficiency denominator — inherits the error silently.

The classification has checkable invariants that nothing requires anyone to assert: a sufficiency stop SHALL have a passing gate verdict *and* non-zero remaining budget at decision time; a loop-fuse halt SHALL have a matching progress fingerprint per FR24; a fail-closed halt SHALL have a recorded mechanism failure.

**Missing requirement:** the harness SHALL validate stop-classification invariants on every recorded run and SHALL flag any run whose classification is inconsistent with its ledger state and gate verdict.

#### FR19 — a new judgement with no declared adjudication method

> "**FR19.** The gate SHALL additionally assess **tool-use quality** — whether the tools called were the right ones, whether their output was actually used, and whether denied calls were correctly denied."

"Were the right ones" and "was actually used" are judgements. FR18 establishes that deterministic validation is authoritative and the model rubric is advisory — but FR19 never says which side of that line it sits on. If it is model-judged, it inherits the judge-reliability critique §11.2 names, and FR18's defence does not cover it. If it is deterministic, the checks need defining. **[UNFALSIFIABLE as written]** until adjudication is specified.

Note also the overlap with FR65: "whether denied calls were correctly denied" is tool-suppression accuracy, assessed in-run by the gate in FR19 and out-of-run by the harness in FR65. Nothing requires the two to agree, and disagreement between them would be a useful signal that neither requirement asks anyone to look at.

#### FR44 / FR46 — shadow estimates never validated against enforced reality

> "**FR44.** … logging every decision it would have made **and the estimated effect of each**."
> "**FR46.** Shadow mode SHALL capture the governed and ungoverned paths from a single execution, so measurement does not require two separate runs."

FR47 correctly forbids presenting shadow figures as realized savings. But **no requirement ever establishes how wrong the shadow estimate is.** FR46 makes shadow mode a *measurement instrument* for the MVP — and an uncalibrated instrument. UJ-1's entire adoption argument rests on a shadow number ("on 61% of runs, the outcome met your declared floor two iterations before the agent stopped"); if shadow estimates are systematically optimistic, that number is a sales artifact, and this PRD contains no requirement that would reveal it.

**Missing requirement:** for a sample of cases, the harness SHALL execute both shadow and enforced configurations and SHALL report shadow-estimate error. Labeling an estimate "projected" is not a substitute for knowing its error bar.

#### FR48 / FR49 — the adoption claim has no unit of measurement

> "**FR48.** The system SHALL wrap an existing tool-using agent loop **without requiring that agent to be re-architected**."

"Re-architected" is undefined, so no integration outcome can falsify it. UJ-4's "one afternoon" and §1.3's "Low adoption cost is the reason to believe it can spread" both rest on this, and neither is measured. **[UNFALSIFIABLE as written.]**

**Missing requirement:** integration cost SHALL be recorded for each of the two dissimilar agent implementations required by FR49 — lines changed in the host agent, files touched, elapsed wall-clock time — and published with the results.

#### FR21 / FR81 / FR82 / FR83 — failure paths that no required case exercises

FR21 (breach the ceiling and request a human), FR81 (gate produces no verdict), FR82 (ledger state lost), FR83 (approval channel unavailable) describe the system's most important behaviours under stress, and §9 elevates FR32/FR83 to a governance commitment: "Human control is enforced, not merely declarable."

**F13 requires no case that triggers any of them.** FR55–FR65 describe a frozen case set for baseline-versus-governed comparison. Nothing requires fault injection, nothing requires a case constructed to be unsatisfiable within its ceiling (the UJ-2 scenario), nothing requires an approval-gated tool call, and the MVP's synthetic solo context means an approval channel may not exist to be tested at all.

**Missing requirement:** the case set SHALL include cases that exercise each declared failure path — ceiling breach with floor required, gate-unavailable, ledger-loss, approval-unavailable, loop-fuse halt — and the harness SHALL assert the specified behaviour for each.

### 3.3 Moderate

- **FR5 / NFR3 (replay determinism)** — FR5 states the property and FR63 requires runs be re-executable, but **nothing requires a replay to actually be performed and compared.** Reproducibility is asserted as a design property, never as a test result. **[UNCHECKED]**
- **FR12 (protected reserve)** — "Earlier steps SHALL NOT be able to spend the reserve." No test requirement. The failure mode — reserve silently consumed, verification starved — is exactly the one that would make a false-sufficiency pass more likely, and it is unmonitored. **[UNCHECKED]**
- **FR20 ("On pass, the system SHALL stop immediately. No further billable work")** — checkable from the ledger and record in one assertion; no requirement makes the assertion. **[UNCHECKED]**
- **FR38 / FR39 (start cheapest, escalate "only where justified")** — "justified by task complexity, low model confidence, policy criticality, or a failed quality evaluation." Only the last is objectively observable. Escalation *rate* is a counter-metric with no producer (§2 above); escalation *correctness* is measured nowhere. **[UNFALSIFIABLE + UNCHECKED]**
- **FR53 ("sufficient to reconstruct why a run stopped where it did")** — sufficiency for whom? UJ-3 depends entirely on this. A reconstruction test is cheap: give a reader the record alone and ask them to state the stop reason. No such requirement exists. **[UNFALSIFIABLE as written]**
- **FR73 (gateway reconciliation)** — "SHALL reconcile … and SHALL surface any discrepancy rather than silently preferring one." No tolerance. A 30% discrepancy that is surfaced is compliant, and the PRD does not say which number is then reported. **[UNCHECKED — no threshold]**
- **FR29 ("SHALL deny optional calls once the contract's required evidence is satisfied")** — "optional" is contract-declared, so this is checkable, but it interacts badly with FR19's "whether the tools called were the right ones": a call denied as optional that would have improved accuracy is exactly the FR65 error case, and the two requirements are not connected.
- **FR57 / FR64 numbers unset** — the refusal mechanisms are **[SELF-ENFORCING]** and good. But the pre-registration discipline lives only in a `[NOTE FOR PM]`: "Fixing N and the minimum case count *before* seeing any results is what prevents the sample from being chosen to flatter the outcome." A note is an intention. **Missing requirement:** N and the minimum case count SHALL be recorded and published before the first evidence run, and the harness SHALL refuse to run a comparison until both are set.
- **FR64 reviewer independence** — §11 concedes "the blind reviewer is the same person who wrote the rubric and built the optimizer," and blinding "reduces it but does not remove it." No requirement obtains even a single external reviewer for a subset. For the counter-metric the addendum calls the reason the headline is falsifiable at all, that is a thin defence.

---

## 4. Savings claim versus mechanism attribution

**The state of attribution:** FR13 splits spend two ways — task work versus governor overhead. FR59 reports overhead as a line item and gross versus net side by side. FR62 establishes whole-governor break-even. There is **no per-mechanism attribution requirement anywhere in the document.**

Total savings will be measured. Which mechanism produced them will not.

### Claims that become unsupportable

1. **The §1.2 cost-driver ranking.** "Overrun loops — the most expensive failure" cannot be supported. Nor can the implicit ordering of the other three. The narrative that motivates the entire product is unevidenced by the product's own measurements.

2. **The §4.3 cut order.** The cut order is an explicit value ranking — F14 first, semantic dedup fourth, model routing fifth, context compression sixth. If nothing measures per-mechanism contribution, the ranking is judgement asserted as engineering. Worse, it is **unrevisable**: the PRD cannot learn mid-build that context compression is carrying most of the savings and should be protected, because it never measures that. NFR10 makes the cuts mechanically executable; nothing makes them *informed*.

3. **Any claim about a named mechanism.** The submission (FR78) "SHALL show the mechanism running, not only its results — at minimum the Outcome Contract, a governor decision stream, and a stop caused by sufficiency." Showing a mechanism run alongside a total savings figure invites the inference that the mechanism produced the saving. FR76 requires figures be traceable to a harness run; it does not prevent a true total being juxtaposed with a mechanism in a way that implies attribution the data cannot support.

4. **§8.3's prompt-cache exclusion — a requirement with no implementation.**
   > "Prompt-caching savings SHALL be reported as a measured secondary lever and SHALL NOT be attributed to OutcomeFuse."

   This is an *attribution* obligation. Satisfying it requires separating provider-side prompt-cache savings from governor-produced savings. FR13's two-way split cannot do this, and FR58 captures "cached tokens" as a raw count with no requirement to subtract it from the headline. **§8.3 mandates a separation that no requirement in §5 implements.** Either the headline figure will include prompt-cache savings in violation of §8.3, or someone will subtract them by a method this PRD never specifies.

5. **The break-even study's resolution.** FR62 establishes "the task length at which the governor begins paying for itself" — for the governor as a whole. On short tasks the likely reality is that some mechanisms are profitable and others are not. Whole-governor break-even cannot distinguish a uniformly marginal system from a system with two strong mechanisms and three parasitic ones. The actionable version of Q1 requires per-mechanism overhead-versus-savings, and FR13 stops one level short: it aggregates evaluation, planning and compression into a single "governor overhead" bucket rather than attributing each to its mechanism.

### The single missing requirement

The capability already exists. NFR10 requires that F7, F8, F9, FR30 and the FR18 rubric signal each be independently disableable. Ablation is therefore nearly free — and the PRD never asks for it.

**Missing requirement:** the harness SHALL support ablation configurations disabling each conditional mechanism in turn, SHALL report savings and overhead attributable to each, and FR13 SHALL attribute governor overhead to the specific mechanism that incurred it rather than to a single aggregate.

Without it, the honest form of every result this PRD produces is: *the governed configuration cost less than baseline, for reasons not established.*

---

## 5. Section 8 — self-enforcing versus stated intention

The test applied: does a requirement cause a system to **refuse**, or does the standard rely on a human remembering it at write-up time?

### 5.1 Self-enforcing — built into the harness

| §8 standard | Enforcing requirement | Enforcement type |
|---|---|---|
| Frozen, published baseline definition (§8.1) | FR61 | **Refusal** — "SHALL refuse to produce a comparison when the executing baseline configuration differs from the frozen definition" |
| Minimum case count (§8.3) | FR57 | **Refusal** to publish below it |
| Tool-call figure requires suppression accuracy (§8.3) | FR65 | **Refusal** — "SHALL NOT report a tool-call reduction figure unless accompanied by it" |
| Mean, median, absolute counts (§8.3) | FR56 | Mandated output |
| Net and gross side by side; overhead as line item (§8.3) | FR59, NFR2 | Mandated output |
| Failures and escalations published (§8.3) | FR60 | Mandated output |
| Shadow figures labeled projected (§8.4) | FR47 | Mandated label |
| Self-reported label on metering fallback (§8.4) | FR74 | Mandated label |
| Runs re-executable (§8.3 implied) | FR63 | Mandated capability |

FR61, FR57 and FR65 are the three genuinely strong requirements in this PRD. They make the system refuse rather than asking a person to be disciplined. They are the template for everything below.

### 5.2 Stated only — no enforcing requirement

#### E-1. Rubric freeze (§8.2) — **[UNCHECKED, critical]**

> "**The quality rubric SHALL be frozen before governor work begins.** The same person writes the rubric and the optimizer that must satisfy it; freezing the rubric first is what prevents the optimizer from being fitted to a moving target."

§11.2 lists rubric circularity as a top risk and names this freeze as its mitigation. The addendum reinforces it: "Any implementation that quietly lets the rubric establish a pass would break the argument, not merely the requirement."

**There is no FR implementing the freeze.** No requirement that the rubric be versioned, hashed, timestamped, or published. No requirement that the harness refuse a comparison when the executing rubric differs from the frozen one. Contrast FR61, which does precisely that for the baseline.

The asymmetry is the finding: **baseline drift is mechanically prevented; rubric drift — the risk the PRD rates higher — is prevented by the builder remembering not to do it.** The one person who would have to remember is the same person the risk register identifies as conflicted.

**Missing requirement (highest value in this review):** the rubric SHALL carry a version and content hash, SHALL be recorded with every gate verdict and every published result, and the harness SHALL refuse to produce a comparison when the executing rubric differs from the frozen definition — FR61 applied to the rubric.

Note FR8 does exactly this for the *contract*. The pattern is already in the document and was not extended to the rubric.

#### E-2. "The baseline SHALL be a *reasonable* agent, not a strawman" (§8.1) — **[UNFALSIFIABLE, high]**

> "The baseline is defined by the party who benefits from it losing. Publishing its definition is the only defence against that."

The self-awareness is exact and the mitigation is insufficient by its own logic. FR61 freezes and publishes whatever baseline is chosen — **a frozen, published strawman is fully compliant.** Publication is a defence only if someone with an incentive to object reads it, and no requirement produces such a reader. "Reasonable" has no operational test.

**Missing requirement:** the baseline SHALL be reviewed by at least one party other than the builder before freezing, or SHALL be constructed from a published reference implementation whose provenance is cited.

#### E-3. "Case-construction rules SHALL be published" (§8.3) — **[UNCHECKED, high]**

No FR. §11.2 leans on this as the mitigation for the synthetic-data risk ("State it plainly; publish case-construction rules"). F13 requires a frozen case set but never requires the rules governing its construction to be written down or published. Since the builder authors both the cases and the optimizer, this is the same circularity as the rubric, applied to the workload — and it has even less enforcement than the rubric does.

#### E-4. Prompt-cache attribution (§8.3) — **[UNCHECKED, high]** — see §4.4 above. A standard requiring an attribution capability that no requirement builds.

#### E-5. "Gross MAY be shown alongside; it SHALL NOT be the headline" (§8.3) — **[UNCHECKED, moderate]**

FR59 requires both figures be reported side by side. Which one is *the headline* is a human formatting decision at write-up and video-edit time. FR76 requires submission figures be "net not gross" — good — but no requirement governs the written report, and no requirement defines "headline" operationally (first figure stated? largest type?).

#### E-6. "No claim of measured generalization … beyond the workloads actually completed" (§8.4) — **[UNCHECKED, moderate]**

No FR. This is the discipline that stops "works across four workloads" becoming "works across domains" in the two-minute video's fourth beat — which FR75 names as "the scale argument," i.e. the exact beat where the temptation lives. FR76 constrains **figures**; the scale argument is prose. The most likely place for an overclaim is structurally exempt from the only enforcement mechanism nearby.

#### E-7. "Where possible, token counts SHALL be taken from gateway metering" (§8.3) — **[UNFALSIFIABLE, moderate]**

"Where possible" is unfalsifiable — impossibility is never defined, and F15 is **cut position 8** in §4.3. If the cut is exercised, FR74 applies and every headline token figure becomes self-reported by the system under evaluation. §4.1 describes this slice as the reason "the headline savings figure is independently measured rather than self-reported by the system being evaluated." The cut order silently removes independent measurement from the evidence chain, and neither §4.3 nor §8 flags that consequence.

#### E-8. No compliance gate on §8 itself — **[UNCHECKED, high]**

FR76 requires submission figures be "traceable to a harness run that satisfies §8." **Nothing computes whether a run satisfies §8.** The standards are distributed across nine bullet points in §8.3 and four in §8.4, several with no enforcing requirement at all. "Satisfies §8" is therefore an unevaluable predicate, and FR76 — the requirement guarding the artifact that is actually judged — rests on it.

**Missing requirement:** the harness SHALL emit a per-report evidence-compliance record enumerating each §8 obligation and whether it was met, and any published figure SHALL carry that record.

---

## 6. Consolidated missing requirements

In descending order of value:

1. **Rubric freeze enforcement** — version, hash, record with every verdict; harness refuses on drift. FR61 applied to §8.2. *(E-1)*
2. **Savings-target pre-registration** — targets recorded and published after FR62 and **before** any governed comparison run; no downward revision without publishing both figures. *(C-6)*
3. **Per-mechanism attribution and ablation** — FR13 attributes overhead per mechanism; harness runs each conditional mechanism disabled in turn and reports its contribution. *(§4)*
4. **Counter-metric thresholds** — all six in §3.3, with the same restatement discipline §3.1 applies to itself. *(§2)*
5. **Producing requirements for escalation rate and budget-breach rate** — extend FR58's capture list; report all six counter-metrics. *(§2)*
6. **Compression-fidelity measurement** — FR36 made checkable; compression savings not reportable without it, on the FR65 pattern. *(FR36)*
7. **FR15 specification and accuracy measurement** — define the marginal-value estimate, record it per decision, blind-review a sample. *(FR15)*
8. **Failure-path cases in the case set** — ceiling breach with floor required, gate-unavailable, ledger-loss, approval-unavailable. *(FR21/FR81–83)*
9. **Decision-authorization join** — every execution effect carries its authorizing decision id; harness flags orphans. Makes FR3 observable. *(FR3)*
10. **Stop-classification invariant checks** — sufficiency stops must have a passing verdict and remaining budget. *(FR26/FR84)*
11. **Shadow-estimate calibration** — run both configurations on a sample; report estimate error. *(FR44/FR46)*
12. **False-insufficiency rate** — extend the blind review sample to failed and escalated runs. *(FR64)*
13. **N and minimum case count fixed before the first evidence run** — promote the `[NOTE FOR PM]` to a requirement with a harness refusal. *(FR57/FR64)*
14. **§8 compliance record** — makes FR76's "satisfies §8" evaluable. *(E-8)*
15. **Integration-cost measurement** — lines changed, files touched, elapsed time, per FR49 implementation. *(FR48/FR49)*
16. **Replay-determinism and reserve-protection tests** — assert FR5 and FR12 rather than asserting them. *(FR5/FR12)*
17. **Independent review of the baseline definition** and **published case-construction rules**. *(E-2, E-3)*
18. **Competitive-claim re-verification** before external restatement of §1.3. *(C-2)*

---

## 7. What the document gets right

Recorded because a verification-gap review that lists only gaps misrepresents the artifact:

- **FR61, FR57, FR65** are refusal-based enforcement, which is the correct form. FR65's accompanying note — "The reduction and the accuracy travel together or neither is reported" — is the exact right instinct, and the review's central recommendation is simply to apply it to compression, to FR15 and to the rubric.
- **§3.1's refusal to carry an unmeasured target** is more honest than publishing a discounted guess, and the reasoning is stated rather than assumed.
- **§1.3's downgrade from a categorical claim to a scoped survey claim**, with its own limitation stated inline, is the correct handling of unverifiable competitive research.
- **FR18's deterministic-authoritative gate** is a genuine structural answer to the judge-reliability critique rather than a deflection.
- **FR47, FR74, FR80** are labeling requirements that degrade a claim's stated strength rather than concealing the degradation.
- **§10's fail-open/fail-closed asymmetry** is stated with its rationale and mapped to specific requirements.
- **Q4, Q6 and Q7 are marked unset rather than filled with plausible numbers**, and the `[NOTE FOR PM]` on post-hoc selection bias is a genuine piece of intellectual honesty — which is precisely why its absence from §3.1's restatement gate is the most surprising gap in the document.

---

_End of review. No document was modified._
