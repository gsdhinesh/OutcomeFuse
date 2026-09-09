---
title: "Reconciliation — PRD → Architecture Spine"
artifact_under_test: _bmad-output/planning-artifacts/architecture/architecture-OutcomeFuse-2026-09-07/ARCHITECTURE-SPINE.md
source_of_truth: _bmad-output/planning-artifacts/prds/prd-OutcomeFuse-2026-09-04/prd.md
created: 2026-09-08
---

# Reconciliation — PRD → Architecture Spine

**Verdict:** Structurally strong and correctly terse on the runtime, but the spine systematically under-binds the *evidence and honesty* half of the PRD — three critical misses (reportability accompaniment rules, model access for core-resident advisors and the Gate, and the FR17 floor-protection carve-out), five high, and a handful of medium/low.

---

## Calibration note

Findings below are limited to cases where the omission (a) creates a genuine divergence risk between two independently-built units, (b) loses a normative obligation the PRD marks SHALL, or (c) contradicts or silently re-scopes the PRD. Requirements the spine correctly leaves to code (FR13 field names, FR29 key layout, FR36 selection heuristics, FR43 graph shape, FR72–FR76 view layout, FR81/FR84 video content) are **not** reported.

Where the spine is genuinely good and it matters, it is noted so the fixes below do not undo it: AD-2 (log-as-fold) discharges FR5/FR6/FR55/NFR3 cleanly; AD-7 forecloses contract-driven RCE that FR7–FR9 leave open; AD-11 removes the shadow branch from the fail-closed path, which is the correct reading of FR91; AD-14 discharges NFR6 by construction rather than by policy; AD-17's "generated, not served" is the right answer to the FR77 + §4.3 cut-order tension. AD-3's reservation model, however, collides with FR14 — see F-6.

---

## Critical

### F-1 — AD-10 claims sole ownership of reportability, then drops every accompaniment obligation in §8.3

- **Severity:** Critical
- **PRD anchor:** §8.3 (all bullets), §3.3 "Reporting standard", FR59, FR61, FR62, FR63, FR70, FR97; §3.1 restatement gate
- **Spine anchor:** AD-10

**What didn't land.** AD-10 declares: *"A run is reportable only if all hold… The harness evaluates this predicate once; no other component re-derives it."* That is exactly the right architectural move — one predicate, one owner, refusal rather than labelling. But the predicate it actually states is entirely about *provenance*: non-streaming, gateway route, matched route across arms, conformance-passed adapter, manifest present, evaluation set.

Every **accompaniment** obligation in §8.3 is missing from it:

| PRD obligation | In AD-10? |
|---|---|
| FR62 — headline savings SHALL NOT be published without its per-mechanism breakdown | No |
| FR70 / §8.3 — tool-call reduction figure SHALL NOT be published without tool-suppression accuracy | No |
| FR61 / §8.3 — net is the headline; gross MAY be shown alongside but SHALL NOT be the headline | No |
| FR59 / §8.3 — no workload reported below its declared minimum case count | No |
| FR63 / §8.3 — failures and escalations published alongside successes | No |
| FR58 / §8.3 — absolute pass counts SHALL accompany every percentage | No |
| §3.3 — counter-metrics reported with equal prominence, each against its preregistered threshold | No |
| §8.3 — prompt-caching savings reported separately, never attributed to OutcomeFuse | No |

By declaring itself the single owner and then omitting these, AD-10 is worse than silence: a builder reading it reasonably concludes reportability *is* the six listed conditions, ships a proof card that passes them, and publishes a bare tool-call-reduction number with no FR70 denominator. §3.3 exists precisely because the primary metric has a perverse optimum; the spine has bound the plumbing that proves the number is real and left out the guards that prove the number is *not gamed*.

Note also that FR97's proof-card content list does not itself include counter-metrics, so no other requirement backstops this. AD-17 renders "the rendered proof card" and AD-10 gates provenance — between them, no invariant makes a counter-metric appear anywhere.

**Suggested fix.** Extend AD-10's rule with a second clause, e.g.:

> A **figure** is publishable only alongside its mandated companions: a savings headline with its FR62 per-mechanism breakdown; a tool-call reduction with its FR70 suppression accuracy and unverified count; any percentage with its absolute counts; any workload with its FR59 case count met; every §3.3 counter-metric with its preregistered threshold and its pass/fail against it; failures and escalations in the same artifact as successes; net as the headline with gross subordinate; prompt-caching savings as a separate, unattributed line. The harness computes this companion set as part of the proof card; a figure without its companions is refused, not labelled.

Add the counter-metric block and threshold comparison to the proof-card entity in the Structural Seed so F14 and F16 inherit them structurally.

---

### F-2 — AD-4 forbids advisors from calling ports, but four PRD mechanisms and the Quality Gate cannot function without a model call

- **Severity:** Critical
- **PRD anchor:** FR20 (rubric signal), FR22 (model-judged tool-use quality), FR37 (compression), FR41 (complexity / confidence estimation), FR43 (planner envelopes), FR15, FR39, FR45, FR98
- **Spine anchor:** AD-4 rule 1; source tree `core/advisors`, `core/gate`; Design Paradigm ("The governor core is pure: no I/O… no network")

**What didn't land.** AD-4 states a mechanism *"never mutates run state and never calls a port"*, and the paradigm places `advisors/` and `gate/` inside the pure core. Yet:

- FR37 compression **is** a model pass (FR39 attributes its spend to overhead).
- FR43 planner envelopes are model-derived (FR45 attributes the spend).
- FR41 escalation triggers on *"task complexity, low model confidence"* — both model-derived; FR6 requires them recorded as decision inputs.
- FR20's rubric signal and FR22's advisory tool-quality signal are model judgements produced inside the Gate.
- FR98 requires *every* Gate execution to be counted in overhead accounting — which presupposes the Gate consumes billable model tokens.

The spine gives no invariant for how a pure, port-less core component obtains a model call, nor for how the resulting spend reaches the Ledger under AD-4's rule 3 (*"the Ledger… debits from the recorded outcome of a port call — never from a mechanism's self-report"*).

This is a real divergence, not a restatement request. Two builders will resolve it two ways: (a) inject `ModelPort` into the advisor, quietly breaking core purity and AD-4; or (b) have the advisor return a *deferred request* that the driver fulfils and re-submits. These produce different decision-log shapes, different step counts, and — critically — **different FR15 per-mechanism attribution**, which is the exact failure AD-4 was written to prevent. It also silently makes the Context Governor, Model Governor, Preflight Planner and the rubric signal unimplementable as specified, i.e. it lands hardest on the mechanisms §4.3 already marks sacrificial.

**Suggested fix.** Add an AD (or a third clause to AD-4):

> **A mechanism that needs the world asks for it.** An advisor never calls a port. Where an advisor requires model-derived input (FR37 compression, FR43 envelopes, FR41 complexity/confidence, FR20 rubric, FR22 tool-use quality), it returns a typed **assist request** naming the mechanism, the purpose and a token envelope. The driver fulfils it through `ModelPort`, the Ledger settles the resulting spend as governor overhead attributed to the *requesting mechanism*, and the assist and its outcome are appended to the log before the advisor is re-invoked with the result. The Quality Gate follows the same path for its rubric signal; a Gate execution that made no assist request is still counted per FR98 at zero model spend. Advisor purity is preserved because the advisor is a function of state plus fulfilled assists.

---

### F-3 — The floor-protection carve-out (FR17) — the product's first design principle — has no invariant; it appears only as a clause in **Deferred**

- **Severity:** Critical
- **PRD anchor:** §1.5 principle 1, FR11, FR17 (*"FR17 SHALL NOT deny a step required to establish, verify or correct an unmet mandatory criterion or evidence field"*), FR93, FR99, §9 ("The floor is never starved to save money")
- **Spine anchor:** AD-4 (marginal-value advisor is one advisor among five); Deferred → "Learned marginal-value estimation… its floor-protection carve-out is not [pluggable]"

**What didn't land.** The single rule the PRD marks *"not negotiable"* — that the marginal-value estimator governs enrichment and may never deny a step advancing an unmet mandatory criterion — exists in the spine only as a subordinate clause inside the **Deferred** section, which is by construction non-normative. No AD binds it. The Capability Map routes F3 to AD-3/AD-4/AD-13, none of which mention the floor.

Under AD-4 the marginal-value advisor is a peer advisor returning `low-value` as a candidate reason, and the Policy resolves proposals. Nothing in the spine tells the Policy that a `low-value` denial is **invalid** when `quality_state` is `fail` (or `not-evaluated`) and the step targets an unmet mandatory criterion. A builder implementing the FR2 ladder literally will place `low-value` at rung 6 and stop — the ladder governs *precedence between conditions*, not *validity of a condition*, and FR17's carve-out is a validity rule. The result is the exact inversion the PRD calls "a violation of FR11 rather than an optimization."

FR99's obligation — that every marginal-value denial be reported with its FR17 compliance, and that a floor-blocking denial *"SHALL be reported as a violation, not as a saving"* — is likewise unowned: it is neither a manifest fact (AD-9) nor part of reportability (AD-10) nor part of the proof card.

**Suggested fix.** Promote it to a first-class invariant, e.g. **AD-18 — The floor is not negotiable**:

> The Policy SHALL reject any proposal carrying `low-value` (or any future enrichment-suppression reason) where the step advances a mandatory criterion the Gate currently reports unmet, or where `quality_state` is `not-evaluated`. This is a validity constraint on the Policy, not a rung on the FR2 ladder, and it is enforced above every advisor including future learned estimators. `unaffordable` (FR16) and `unsafe` denials are unaffected. Every marginal-value denial is appended with the unmet-criterion set at decision time, the estimated benefit and cost, and a compliance flag; a non-compliant denial is emitted by the harness as a **violation**, and is structurally barred from contributing to any savings figure.

---

## High

### F-4 — FR69 blind human review has no structural owner, and AD-17 pushes in the opposite direction

- **Severity:** High
- **PRD anchor:** FR69, §3.3 false-sufficiency rate, §11.1 Q4 + the `[NOTE FOR PM]` on reviewer bias
- **Spine anchor:** AD-16, AD-17, `harness/` (no blinding component listed)

**What didn't land.** FR69 is a *data-exposure* requirement with real structural consequences: the reviewer SHALL see the deliverable and the contract, and SHALL NOT see the gate verdict, the decision record, or which configuration produced the run. False-sufficiency rate is named in §3.3 as *"the direct inverse of the headline claim. Without it, the savings number is unfalsifiable."*

The spine contains nothing that owns this. Worse, AD-16 puts everything in one SQLite file per run, and AD-17 generates *"one self-contained file per comparison, embedding the replay timeline, ledger state at each decision, the rendered proof card and enough record to satisfy FR76 offline."* The path of least resistance for a builder — render the review packet from the same store with the same generator — leaks the verdict, the mode and the ledger in the same artifact. And this leak is silent: the resulting false-sufficiency number still computes, still looks plausible, and is worthless. The PRD already concedes the reviewer is the same person who wrote the rubric; blinding is the only remaining defence, and it is structural or it is nothing.

**Suggested fix.** Add an invariant:

> **Blinding is a projection, not a discipline.** The blind-review packet is produced by a dedicated harness projection that emits only the deliverable and the contract, keyed by an opaque review id. Run mode, arm, gate verdict, qualifier, decision log, ledger state and manifest are excluded by construction — the projection selects an allow-list of fields, never redacts a full record. Review verdicts are ingested against the review id and joined to runs only after the full sample is submitted. The viewer generator (AD-17) is not a review surface and may not produce review packets.

---

### F-5 — §10.1 fail-open has no invariant, and "degraded" collides with AD-4's "disabled means not registered"

- **Severity:** High
- **PRD anchor:** §10.1, FR85, FR86; §10.2 asymmetry statement; FR60 ("degraded mechanisms"), FR100 ("optimization-mechanism failure" case, asserted to record *no* terminal reason and continue)
- **Spine anchor:** AD-4 ("Disabled means not registered. No mechanism carries an `if enabled` branch"); Capability Map row "§10 Failure posture → AD-4, AD-11, AD-12"

**What didn't land.** The Capability Map routes the §10 failure posture to AD-4, AD-11 and AD-12. AD-11 covers only shadow exemption (FR91); AD-12 covers only the approval port (FR89). Neither AD-4 nor any other invariant states the §10.1 rule: an optimization-mechanism failure SHALL NOT halt the run, execution continues without it, and the run is **marked degraded with its savings labelled accordingly** (FR85, FR86). The PRD's own framing — *"losing an optimization costs money; losing the gate costs correctness. Only one of those is allowed to fail quietly"* — is the asymmetry the whole section exists to state, and no AD carries it.

There is also a direct collision. AD-4's *"disabled means not registered"* is a clean answer for FR62 ablation and NFR10, but it makes runtime degradation structurally unrepresentable: a mechanism that fails at step 7 *was* registered, and the manifest (AD-9) recorded it as enabled. So a degraded run and a fully-enabled run are indistinguishable from the manifest, and a degraded run and an ablated run are indistinguishable from behaviour — which is exactly how an FR86 degradation quietly gets counted as a clean savings result.

**Suggested fix.** Add an invariant, and amend AD-4:

> **Failure posture is a property of the port, not of the caller.** An advisor assist that fails (F7, F8, F9, tool cache, gateway metering) is a **decision input** per the Errors convention: the Policy proceeds without that advisor's proposal, appends a `mechanism-degraded` entry naming the mechanism and the step, and the run continues — never halts (FR85). A failure of the Gate, the Ledger or the `ApprovalPort` fails closed per §10.2 and FR87–FR90. **Degraded ≠ disabled:** disabled means absent from the manifest registry (AD-4, ablation); degraded means present in the manifest and downgraded in the log. Any run carrying a degradation entry is marked degraded by the harness, and its savings figures are labelled per FR86 — this is a condition of AD-10 reportability, not a cosmetic tag.

---

### F-6 — AD-3 reuses "reserved" for step-level reservation, colliding with FR14/FR101's protected verification reserve

- **Severity:** High
- **PRD anchor:** FR13 (`allocated`, `spent`, `reserved`, `remaining`), FR14, FR16 (`remaining` less `reserved`), FR101, FR41
- **Spine anchor:** AD-3 ("Budget is **reserved at decision time and settled at completion**"); source tree `ledger/ # allocate, reserve, settle, attribute`

**What didn't land.** The PRD has two distinct, differently-governed things:

1. **The verification reserve** (FR14, FR101) — a protected floor sized from the contract or a deterministic default, *never spendable by earlier steps*, recorded with the run, recalculated before escalation, and an absolute bar on escalation (FR41, FR101).
2. **Step reservation** (AD-3) — transient hold-and-settle to prevent the concurrency breach AD-3 exists to prevent.

The spine collapses both into `reserve`/`reserved` and never distinguishes them. FR16 tests affordability against `remaining − reserved`; if the verification reserve and in-flight step holds share that field, the semantics of "settle" become ambiguous (does settling a step release the verification reserve?) and the FR14 guarantee — *"verification can never be starved by overspend"* — reduces to a convention. Two builders will land on different ledger algebras and neither will violate a stated rule.

FR101's hardest clause is also unowned: *"an escalation SHALL NOT proceed where it would leave insufficient reserve for final synthesis and the Quality Gate executions FR98 requires."* AD-13 owns the model seam and AD-4 makes the Ledger the single writer, but nothing states that escalation is reserve-gated.

**Suggested fix.** Amend AD-3 and the Ledger conventions:

> The Ledger holds two structurally separate quantities. **`verification_reserve`** is sized once at run open (contract `verification_reserve`, else the deterministic default derived from ceilings), recorded in the manifest, recalculated before any escalation, and never available to any step other than final synthesis and Gate execution. **`in_flight`** is the transient per-decision hold created at decision time and cleared at settlement. Affordability (FR16) is `remaining − verification_reserve − in_flight`. An escalation proposal that would leave `verification_reserve` insufficient for final synthesis plus the remaining FR98 Gate executions is rejected by the Ledger, not by the Model Governor.

---

### F-7 — The baseline arm is unowned: §8.1 requires a genuine evaluator/retry loop, and nothing in the spine builds or freezes one

- **Severity:** High
- **PRD anchor:** §8.1 (all bullets), FR52, FR57, FR64; §11.2 "Baseline fairness" risk
- **Spine anchor:** AD-9 ("frozen baseline-configuration hash", `mode: governed | baseline | shadow`), AD-6, `runtime/ # drivers: enforcing, shadow, off`, `adapters/host/reference/`

**What didn't land.** §8.1 is normative and specific: the baseline SHALL be *"full retrieved context per step, one capable model throughout, and a conventional evaluator/retry loop with a maximum-iteration safety limit"*, and *"the baseline's evaluator SHALL be genuine."* This is a **component that must be built**, and it is the single point at which the entire falsifiable claim (§1.4) can be quietly rigged — the PRD says so: *"the baseline is defined by the party who benefits from it losing."*

The spine's only treatment of the baseline is a hash in the manifest and a mode string. The `off` driver is defined as *"no governor participation"* (FR52), which produces an *ungoverned* agent, not the §8.1 baseline. The source tree has no baseline module. There is no invariant stating that the baseline evaluator is a distinct, frozen, non-governor artifact, or that it may not share code with the Quality Gate — and sharing the Gate's verifiers with the baseline evaluator would be the cheapest implementation and would destroy the comparison, because §8.1's whole point is that the baseline checks *self-assessed completion* while the governed arm checks *contract-assessed sufficiency*.

**Suggested fix.** Add an invariant, and a `harness/baseline/` (or `adapters/host/baseline/`) node to the source tree:

> **The baseline is a built, frozen artifact.** The baseline arm is a distinct component — full context per step, one contract-eligible capable model throughout, its own completion-notion evaluator and a max-iteration safety limit — and it **shares no code with `core/gate` and consumes no contract criteria**. Its prompt, tools, dataset, model version, temperature and settings are canonicalised (AD-6) and hashed at freeze; the harness refuses any comparison whose executing baseline configuration differs from the frozen hash (FR64), and the frozen definition is published with results. The `off` driver disables the governor; it does not constitute a baseline.

---

### F-8 — AD-6's "one canonicaliser" enumerates four uses and omits the FR27 progress fingerprint (and the result digest)

- **Severity:** High
- **PRD anchor:** FR27, FR28, FR68, NFR3
- **Spine anchor:** AD-6 ("A single core-owned function serves contract identity, tool-call keys, rubric/answer-key freeze and baseline-configuration freeze… **No component may hash a structure by any other route**"); sequence diagram `A->>D: outcome (tokens, result digest)`

**What didn't land.** FR27 requires a *progress fingerprint per iteration* covering evidence gained, task-state change and quality delta — a hash of a structure, and the input to the entire Loop Fuse. It is not in AD-6's enumerated list, and the sequence diagram introduces a **`result digest`** that is likewise unenumerated. So either the spine's own absolute ("no component may hash a structure by any other route") is violated by the Fuse and the driver, or there is an undeclared exemption.

This is a live divergence risk with a nasty failure mode: two units fingerprinting differently produce different `halt-no-progress` points on the same case. That breaks FR68 re-executability, and — because FR2 places `no-progress` below `sufficiency` and `exhaustion` — a drifting fingerprint mislabels endings, which is the conflation FR28, FR92 and FR98 were all written to prevent.

**Suggested fix.** Extend AD-6's enumeration to name the FR27 progress fingerprint and the step result digest, and state that the fingerprint's *input projection* (which fields of evidence/task-state/quality-delta participate) is core-owned and versioned into the manifest, so a fingerprint-definition change is visible as a configuration difference rather than as unexplained halt drift.

---

## Medium

### F-9 — AD-7 narrows FR8 from "an executable deterministic verification method" to a closed seven-entry registry, without declaring the narrowing

- **Severity:** Medium
- **PRD anchor:** FR8, FR9, §8.2a, §2.4/NFR8, §4.1 (four committed workloads)
- **Spine anchor:** AD-7

AD-7 is a good call — it forecloses contract-driven RCE in a product whose position is that platform teams hand contracts to agent owners. But it is a **scope narrowing** presented as an interpretation. FR8 says a mandatory criterion must declare *an executable deterministic verification method*; AD-7 replaces that with *selection from a closed, project-owned registry* of seven parameterised types. Any mandatory criterion across the four committed workloads (document research, codebase Q&A/triage, SQL analysis, supply-chain exception investigation) that cannot be expressed with those seven becomes non-mandatory — it drops out of the quality floor entirely and flows to advisory. That changes what the four contracts can promise, and therefore what the headline claim covers, and the spine does not say so.

**Fix.** Keep the closed registry, but declare the narrowing explicitly and add a validation obligation: contract validation reports which mandatory criteria were *demoted* for want of a registry entry, and the four committed workloads are checked against the registry before it is frozen. Note that registry extension is a governed core change, not a contract-side capability.

### F-10 — FR102's preregistration-ordering check and FR64/FR65's drift refusals are absent from both AD-9 and AD-10

- **Severity:** Medium
- **PRD anchor:** FR64, FR65, FR66, FR102, §8.2, §8.5
- **Spine anchor:** AD-9 (manifest field list), AD-10 (predicate)

AD-9's manifest carries the contract hash, rubric/answer-key hash, frozen baseline-configuration hash and `calibration | evaluation`. It does **not** carry the two timestamps FR102 explicitly requires — *"the moment preregistration (FR66) completed and the moment evaluation-set execution began"* — nor does AD-10's predicate include *"refuse to publish where the latter precedes the former."* Similarly, the manifest records hashes but no invariant states that the harness **compares** them to the frozen values and refuses on drift (FR64, FR65). AD-6 alludes to a "spurious rubric-drift refusal" but never establishes the refusal itself.

Since AD-10 explicitly forbids any other component from re-deriving reportability, these checks currently have no home at all.

**Fix.** Add `preregistration_completed_at` and `evaluation_execution_began_at` to the manifest, and add to AD-10's predicate: rubric/answer-key hash equals the frozen hash; baseline-configuration hash equals the frozen hash; and, for an evaluation-set run, preregistration precedes execution. Same refusal semantics as the rest of AD-10.

### F-11 — NFR1 decision latency is unmeasurable from the record as specified

- **Severity:** Medium
- **PRD anchor:** NFR1, §3.3 "Added latency" counter-metric, FR60
- **Spine anchor:** AD-3 (measurement convention only), AD-8 (owns the schema, enumerates no timing)

AD-3 usefully fixes the *convention* (decision latency is measured against batch width). But AD-8 owns the decision-record schema and never requires a per-decision governor timing field, and FR60's capture list has run `duration`, not decision overhead. "Added latency" is a §3.3 counter-metric that must carry a preregistered threshold — so it must be derivable from the log, on the same terms as spend. The clock is a port (Conventions), which is correct and makes this cheap.

**Fix.** Require the decision row to carry governor decision wall-time — split at minimum into policy/advisor time and assist (port) time — sourced from the clock port, so NFR1 and the added-latency counter-metric are computed from the record like every other figure.

### F-12 — NFR10 covers conditional *requirements*, not just conditional mechanisms; AD-4's registry only reaches the mechanisms

- **Severity:** Medium
- **PRD anchor:** NFR10 (explicitly names FR32, the rubric signal in FR20, the advisory tool-quality signal in FR22), §4.3 cut positions 4 and 8, FR62
- **Spine anchor:** AD-4 ("Disabled means not registered")

AD-4's "disabled means not registered" cleanly handles F7/F8/F9 as advisors. It does not reach the three sub-mechanism switches NFR10 names, all of which live *inside* components that are protected and always registered: FR32 semantic dedup inside the Tool Governor, the FR20 rubric signal and the FR22 advisory tool-quality signal inside the Gate. Under AD-4's own no-`if enabled`-branch rule, these have nowhere to go — yet cut positions 4 and 8 require them to be removable, and FR62 requires them independently ablatable for measurement.

**Fix.** State that these three are modelled as registry entries in their own right — a `SemanticDuplicateAdvisor`, and the rubric and tool-quality signals as **Gate signal contributors** registered alongside the deterministic verifiers — so cutting or ablating any of them is the same registry change, with no branch inside the protected component.

### F-13 — Labels are required to travel with figures (§8.4), but nothing makes them structural

- **Severity:** Medium
- **PRD anchor:** FR21 (*"The label SHALL travel with the result wherever it is reported"*), FR49, FR80, FR82, FR86, §8.4
- **Spine anchor:** AD-7 (qualifier is determined, not asserted — good), AD-10, AD-17

AD-7 correctly makes the `reference-backed` / `constraint-backed` qualifier *derived* rather than asserted. But §8.4 requires five labels to travel with any figure wherever reported — verification mode, projected-vs-realized, self-reported-vs-gateway-measured, degraded, and net-vs-gross — across three consumers (proof card, generated HTML, submission). Nothing binds them to the figure, so each surface can render or drop them independently, and FR82 explicitly extends the obligation to the video.

**Fix.** Make the label set a required attribute of the proof-card figure type rather than of the surface: a figure is a value plus its label set, and a renderer that cannot display the label set may not display the value. That collapses three surfaces to one rule and makes FR82 inheritable rather than a discipline.

### F-14 — AD-11 bars the shadow counterfactual from reportability outright, which is stricter than FR49/FR83 and may conflict with F10's demonstrative purpose

- **Severity:** Medium
- **PRD anchor:** FR46–FR49, FR83, FR84, FR96, §4.3 (F10 protected), §8.4
- **Spine anchor:** AD-11 ("The estimated counterfactual ledger is structurally barred from AD-10 reportability"), AD-10 ("A non-reportable run is not merely labelled — it is refused")

The PRD's rule is a **labelling** rule: shadow figures SHALL be labelled projected, never realized (FR49, §8.4), and SHALL NOT be presented *as realized savings* (FR83). It does not forbid showing them. AD-11 plus AD-10's "refused, not labelled" semantics harden this into a prohibition, which sits awkwardly against F10 being protected scope and against FR84's requirement that the submission show the mechanism running. A builder following the spine literally may find the harness refuses to emit any shadow artifact at all — cutting the demonstration of a protected feature.

**Fix.** Distinguish *reportable* (may back a headline claim) from *presentable* (may be rendered, labelled). Shadow counterfactuals are presentable and never reportable; they carry the FR96 first-divergence marker and the projected label, and are barred only from headline figures and quality-matched pairings.

---

## Low

### F-15 — NFR12 requires a *declared* retention period and access control; AD-16 supplies only a deletion mechanism

- **Severity:** Low
- **PRD anchor:** NFR12, NFR5
- **Spine anchor:** AD-16 ("Retention (NFR12) is discharged by archiving or deleting whole files")

One-file-per-run makes retention *executable*, which is the right structural move, but NFR12 asks for a declared period and commensurate access control — neither of which is a file-layout property. AD-5's redaction reduces exposure but the PRD says explicitly that it *"does not remove the need for retention limits."*

**Fix.** One line in Consistency Conventions: declare the MVP retention period and state that run databases are workstation-local, excluded from version control, and never transported to the viewer or submission except as generated artifacts.

### F-16 — NFR8 domain neutrality has no enforcing invariant

- **Severity:** Low
- **PRD anchor:** NFR8, §2.4
- **Spine anchor:** Layer dependency table, source tree

The layer table forbids core from depending on anything in the project, which prevents *inbound* coupling but not workload-specific logic authored directly inside `core/`. NFR8 is the basis for §2.4's generality posture, and AD-7's generic verifier registry already does most of the work in practice.

**Fix.** One clause on the layer table: `core/` contains no workload name, no workload-specific branch and no case-set-specific constant; workload specificity lives only in `cases/`, `contracts/` and tool implementations.

### F-17 — §8.3's "case-construction rules SHALL be published" has no artifact

- **Severity:** Low
- **PRD anchor:** §8.3 final bullet, §11.2 "Synthetic data" risk, NFR9
- **Spine anchor:** `cases/calibration`, `cases/evaluation` (directories only)

Publishing case-construction rules is the stated mitigation for the synthetic-data risk. The spine gives the case sets a home but no accompanying rules artifact, and no reportability link.

**Fix.** Require each case set to carry a versioned construction-rules document hashed into the manifest alongside case-set identity.

---

## Summary table

| # | Severity | PRD anchor | Spine anchor | One line |
|---|---|---|---|---|
| F-1 | Critical | §8.3, §3.3, FR59/61/62/63/70 | AD-10 | Sole owner of reportability omits every accompaniment obligation |
| F-2 | Critical | FR20/22/37/41/43, FR15/39/45/98 | AD-4, core purity | Core-resident advisors and the Gate need model calls the spine forbids |
| F-3 | Critical | FR11, FR17, FR93, FR99, §9 | AD-4, Deferred | Floor-protection carve-out is normative in the PRD, non-normative in the spine |
| F-4 | High | FR69, §3.3 | AD-16, AD-17 | Blind review has no blinding projection; the viewer leaks the verdict |
| F-5 | High | §10.1, FR85, FR86 | AD-4, Capability Map | Fail-open unstated; degraded collides with "disabled means not registered" |
| F-6 | High | FR14, FR16, FR101 | AD-3, ledger | Verification reserve and step reservation share one word and one field |
| F-7 | High | §8.1, FR64 | AD-9, `runtime/off` | The frozen baseline agent with a genuine evaluator is built by no one |
| F-8 | High | FR27, FR68 | AD-6 | The progress fingerprint hashes a structure outside the one canonicaliser |
| F-9 | Medium | FR8, §8.2a | AD-7 | Closed verifier registry narrows what a contract may make mandatory |
| F-10 | Medium | FR64, FR65, FR102 | AD-9, AD-10 | Preregistration ordering and drift refusals have no owner |
| F-11 | Medium | NFR1, §3.3 | AD-8 | Decision latency absent from the record schema |
| F-12 | Medium | NFR10, FR62 | AD-4 | Conditional *requirements* (FR32, FR20 rubric, FR22 advisory) unreachable by the registry |
| F-13 | Medium | FR21, §8.4, FR82 | AD-10, AD-17 | Label set is not bound to the figure |
| F-14 | Medium | FR49, FR83, FR84 | AD-11, AD-10 | Shadow counterfactual barred outright where the PRD only requires labelling |
| F-15 | Low | NFR12 | AD-16 | Mechanism without a declared period or access control |
| F-16 | Low | NFR8, §2.4 | Layer table | No clause forbidding workload logic inside core |
| F-17 | Low | §8.3, NFR9 | `cases/` | Case-construction rules unpublished and unhashed |

## What the spine got right that these fixes must not disturb

- **AD-2** discharges FR5, FR6, FR55 and NFR3 with one structural idea rather than five rules.
- **AD-7** closes an RCE surface the PRD leaves open, and derives the FR21 qualifier instead of trusting an assertion.
- **AD-11** removes the shadow branch from the fail-closed path — the correct structural reading of FR91.
- **AD-14** discharges NFR6 by construction, not by policy.
- **AD-15** turns FR51/FR52 adapter parity into an asserted property of the decision log rather than of adapter internals.
- **AD-17** resolves the FR77 + §4.3 tension (protected F16 depending on cut-first F14) by making F14 a generated artifact.
- **Q-A** independently caught the missing adapter entry in the §4.3 cut order — a real PRD gap, correctly raised rather than silently absorbed.
