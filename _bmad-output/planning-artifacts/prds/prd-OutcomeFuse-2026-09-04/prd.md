---
title: "PRD: OutcomeFuse"
status: final
created: 2026-09-04
updated: 2026-09-09
---

# PRD: OutcomeFuse

**The quality-gated budget runtime for AI agents.**
_Stop paying for work after the outcome is already good enough._

> **Scope of this document.** This PRD specifies the **MVP** — the artifact to be built and demonstrated within the current window. The longer product vision appears only as context; it generates no requirements here. Requirements carrying FR identifiers are normative for the MVP.

---

## 1. Vision & Positioning

### 1.1 The product in one sentence

OutcomeFuse is a runtime policy that, before every unit of AI work, asks one question: **is another unit of work worth paying for, given the declared quality contract?** Everything else in the system is an enforcement mechanism carrying out that decision.

### 1.2 The problem being solved

An agent given a business task and a set of tools has no notion of what its answer is worth. It optimizes for finishing, not for finishing efficiently. Four costs compound:

- **Context carry-forward** — every step inherits the accumulated transcript, so spend grows superlinearly while marginal relevance falls.
- **Redundant tool calls** — the same query is reissued because nothing remembers it was answered.
- **Uniform premium reasoning** — the most capable model handles reformatting and routing at the same rate as genuinely hard steps.
- **Overrun loops** — the most expensive failure. The agent reaches a sufficient answer at iteration three and works to iteration eight because nothing told it to stop. Every token past sufficiency is pure waste, and it is invisible without a quality signal.

  A fair objection: conventional agents *do* have retry loops with evaluators, and those stop. The difference is what they stop on. A conventional evaluator asks whether **the agent believes it is finished**, against a completion notion the agent itself carries, and falls back to a fixed iteration budget when it cannot tell. It does not ask whether **an externally declared quality floor with named evidence fields has been met**. The gap between "the model thinks it is done" and "the contract says it is done" is where overrun lives — and it is a narrower claim than "agents never stop," which is why the PRD makes the narrower one.

### 1.3 Positioning — what OutcomeFuse is not

| | Post-run auditors | Gateway budget caps and step limits | In-loop routers and cascades | OutcomeFuse |
|---|---|---|---|---|
| When it acts | After the run | Before/during, per call | During, per call | During, per run |
| Stopping condition | n/a | Exhaustion — tokens, dollars, turns | Model-confidence or per-call escalation | **Declared task-level sufficiency** |
| Quality in the spend decision | Reported separately | None | Per-call, model-quality priors | Measured against a contract, per run |
| Output | Analysis and recommendations | A blocked call | A cheaper call | A completed task that cost less |

The category boundary that matters: **the mechanisms surveyed stop a run when it runs out. OutcomeFuse stops a run when it is done.** Stopping on exhaustion protects the budget. Stopping on sufficiency protects the budget *and* returns the outcome.

The survey behind that claim is recorded in the addendum, and it is a survey — not a proof of absence. Two of the closest commercial analogues were reachable only through vendor documentation and could not be independently verified. The claim this PRD is willing to defend is the narrower one: **no mechanism we could examine terminates a run early because the output already meets a declared, measured bar while budget remains.**

And the difference from an observability product is structural, not positional. A dashboard's output is information a human must interpret and act on. **The deliverable here is not a report about a run — it is a cheaper run.** There is no insight-to-action gap, because the action already happened mid-execution.

Two adjacent claims this PRD explicitly does not make:

- **It is not a new agent framework.** It wraps existing tool-using loops. Low adoption cost is the reason to believe it can spread.
- **The individual mechanisms are not novel.** Caching, loop bounds, compression and model routing all exist, and none is claimed as invention. The product is the policy above them, and the subordination of all of them to a single declared objective.

### 1.4 The falsifiable claim

> The same task, completed to the same declared quality bar, for measurably fewer tokens — **net of the governor's own overhead** — with no silent quality substitution.

Gross savings are how this category flatters itself. Net is the only number that survives scrutiny.

### 1.5 Design principles

1. **The quality floor outranks the budget, always.** The runtime will exceed a cost ceiling and request human intervention rather than return a cheaper answer that fails the contract. A budget that silently degrades output is not a saving; it is a defect.
2. **The policy decides; mechanisms execute.** No mechanism optimizes for itself.
3. **Turn the UI off and the savings still happen.** The interface is evidence, not product.
4. **Never conflate "done" with "stuck."** Stopping because the outcome is sufficient and stopping because the loop made no progress are different events, and are reported differently.
5. **Report net, publish failures.** Evidence standards are requirements, not methodology notes.

---

## 2. Users & Stakeholders

### 2.1 Primary — the agent owner

The engineer or platform team responsible for an agent already running against real workloads, accountable for both its bill and its output quality. Today they choose between capping tokens and risking silently worse answers, or leaving it uncapped and absorbing the cost. They need a third option: spend whatever the outcome genuinely requires and not one token more.

- **Success for them:** falling cost per completed outcome, no quality regression, no ongoing manual tuning.
- **They own the quality floor.** OutcomeFuse never decides on their behalf that lower quality is acceptable.

> `[ASSUMPTION]` The primary persona is drawn from the builder's experience, not research. Two to three structured conversations with engineers who own a production agent are in scope to confirm or correct it. Until those happen, the persona is labeled assumed.

### 2.2 Secondary — platform / FinOps owner

Governs AI spend across many teams without becoming the bottleneck that blocks experimentation. The Outcome Contract gives them a policy surface that constrains cost without prescribing implementation.

### 2.3 Secondary — compliance and Responsible AI reviewer

Needs an auditable record of why any call was blocked, cached, compressed or escalated, and assurance that cost optimization never silently degraded an answer.

### 2.4 Domain posture

OutcomeFuse is deliberately **domain-agnostic**. It governs tool-using agent loops regardless of the business domain they serve, and **will be evaluated across dissimilar workloads** so that generality can be demonstrated rather than asserted. No workload-specific logic may live in the governor core (NFR8). Stronger wording is available once the benchmark supports it, and not before.

---

## 3. Success Metrics & Counter-Metrics

All measurement is **baseline versus governed** on a frozen case set — same tasks, same tools, same model versions, same settings — against a deliberately reasonable baseline, not a strawman.

### 3.1 Primary metrics

| Metric | Target | Status |
|---|---|---|
| Net token reduction per completed outcome, inclusive of all governor overhead | **To be set** | Awaiting the overhead study |
| Net estimated cost reduction per completed outcome | **To be set** | Awaiting the overhead study |
| Tool-call reduction | **To be set** | Source figure was gross and predates overhead accounting; set after measurement. Reportable only alongside tool-suppression accuracy (FR70) |
| Task-completion pass rate versus baseline | within 2 percentage points | Carried from source targets |
| Required evidence-field accuracy | ≥ baseline, and ≥ 90% absolute | Carried from source targets |
| Budget compliance — runs terminating cleanly (stopped, safely escalated, or referred for human review) | 100% | Non-negotiable |

**Restatement gate.** The three savings targets are deliberately unset. The original source targets (≥ 40% tokens, ≥ 35% cost, ≥ 30% tool calls) were gross figures set before governor overhead was accounted for, and discounting them by guesswork would produce a number with no more standing than the one it replaced. **On completion of the overhead study (FR67) against the calibration set, savings targets SHALL be set against measured overhead — and per FR66, recorded before any governed evaluation-set result is executed or inspected.** A target set after the evaluation results are known cannot be missed.

There is no circularity here, because the two obligations refer to different data: overhead is measured on the calibration set, targets are tested on the sealed evaluation set (§8.5, FR102).

The two quality targets are retained because they are not overhead-sensitive: overhead changes what a result costs, not whether it is correct.

### 3.2 Secondary metrics

- Reduction in P50 end-to-end latency
- Zero accepted safety or adherence regressions
- Break-even task length — the point at which the governor starts paying for itself

### 3.3 Counter-metrics

The primary metric has a perverse optimum: **the system that stops earliest always wins.** These counter-metrics make premature stopping visible and costly, and are reported with equal prominence to the savings figures.

| Counter-metric | Definition | Why it exists |
|---|---|---|
| **False-sufficiency rate** | Runs the Quality Gate passed that a blind human review fails | The direct inverse of the headline claim. Without it, the savings number is unfalsifiable |
| **Tool-suppression error rate** | Suppressed tool calls that should have been made, defined as **1 − tool-suppression accuracy** (FR70) | The same guard applied to the deny decision. A tool-call reduction figure alone is maximized by denying everything |
| **Escalation rate** | Share of runs requiring model escalation or human intervention | Savings bought by pushing work onto people are not savings |
| **Governor overhead share** | Percentage of total run spend consumed by evaluator, planner and compression passes | Distinguishes gross from net; the number that decides whether this works on short tasks |
| **Added latency** | Wall-clock cost of governor decisions per step | Cheaper but unusably slower is a failed trade |
| **Budget-breach rate** | Runs that exceeded the cost ceiling in order to protect quality | Not a defect — it is the design working — but it must be visible and bounded |

**Reporting standard.** Mean and median across repeated runs, never a cherry-picked execution. Failures and escalations published alongside successes. Overhead reported as its own line item. Savings attributed per mechanism (FR62). See §8.

**Every counter-metric above SHALL carry a numeric threshold, set and recorded before any governed evaluation-set result is executed or inspected** (FR66, FR102). A counter-metric without a threshold cannot fail, and a counter-metric that cannot fail is decoration. The thresholds themselves are unset for the same reason the savings targets are — see Q8 in §11.

---

## 4. Scope & MVP Boundary

### 4.1 In scope

**The governed runtime.** The runtime policy, the Outcome Contract that feeds it, and seven enforcement mechanisms: Budget Ledger, Quality Gate, Loop Fuse, Tool Governor, Context Governor, Model Governor, Preflight Planner.

**Shadow mode.** The governor observing without enforcing, logging every decision it would have made. This earns its place twice: in production it is the risk-free adoption path; in the MVP it is a measurement instrument, recording the executed ungoverned path alongside an estimated governed counterfactual from a single run. Only one path is ever observed — FR96 marks where the estimate stops being evidence. **In the MVP it is exercised on synthetic and replayed workloads only** (FR106); shadowing live traffic is the production story.

**Proving grounds — four committed workloads.** Research and investigation over a document corpus; codebase Q&A and triage; data/SQL analysis; supply-chain exception investigation. Synthetic cases only — no production or confidential data. All four are committed scope, not stretch. The harness is built once; each additional workload is then mock tools plus cases.

**Evidence work.** Expanded case counts with repeated runs per case, so quality claims rest on absolute pass counts rather than percentages over a thin sample. A dedicated overhead break-even study. Structured conversations with two to three production agent owners.

**One thin managed-service slice.** Token metering through an AI gateway, so the headline savings figure is independently measured rather than self-reported by the system being evaluated. A response/tool cache slice is the fallback if gateway integration proves unstable.

**Surfaces.** An in-process middleware library wrapping an existing agent loop; a CLI benchmark harness that computes the proof card as a recorded artifact; and a read-only web view that replays baseline and governed execution side by side and renders that artifact.

**The submission artifact.** A two-minute video covering problem, artifact, proof and scale. This is the thing that is actually evaluated, and it is in scope with its own requirements (F16).

### 4.2 Out of scope for this iteration

- **Contract authoring.** The MVP accepts hand-written contract files only. No authoring UI, no template library, no import from existing eval suites, no contract-versioning surface. The product position — that OutcomeFuse should ease authoring — is real, but it is not built here.
- **Shadowing live production traffic.** Shadow mode is in scope and protected, but the MVP exercises it on synthetic and replayed workloads (FR106). Running it against a team's real traffic is the adoption story, not MVP evidence.
- **Full production deployment.** Beyond the single metering slice, the managed-service path remains the production story, not the demo. The MVP otherwise runs as an in-process governor. Keeping these separate strengthens the viability argument rather than weakening it.
- Policy DSL for reusable contracts; learned marginal-value estimation; multi-agent budget transfer; CI cost-regression gates.
- Any claim of measured generalization beyond the workloads actually completed.

### 4.3 Declared cut order

Roughly 7.5 days of estimated build work sits inside a one-month window, solo — against seven mechanisms, four workloads, two agent implementations, a harness, a replay UI and a submission artifact. **That is a material schedule risk, accepted deliberately** (§11.2). The mitigation is not optimism; it is that the cuts below are declared in advance and made mechanically executable by NFR10, and that the protected core is close to what the source memo recommended as an achievable scope.

**The MVP SHALL prioritize proving quality-gated runtime stopping and measurable net resource reduction over breadth of optimization techniques, integration coverage, or interface completeness.**

**Protected core — never cut:**

Outcome Contract · Budget Ledger including the marginal-value decision (FR17) · deterministic Quality Gate · duplicate-tool protection · loop protection · early-stop decision · **decision record (F12)** · **shadow mode (F10)** · reproducible OFF/ON benchmark · **submission artifact (F16)**.

> F12 is protected because FR5 forbids any decision from taking effect before it is recorded — cutting it would not degrade the system, it would stop it. F10 is protected because it is the adoption path: the mechanism a team uses to evaluate the governor before trusting it. Its MVP demonstration is synthetic (FR106); the persona assumption is tested by the agent-owner interviews (§2.1), not by shadow mode.

**Cut order under schedule pressure, first to go:**

1. The side-by-side execution view and any admin surfaces (F14) — **not** the submission video, which is protected
2. **The third host adapter.** Three host frameworks are committed where FR51 requires two dissimilar ones. The third is dropped first among mechanisms, because a third adapter multiplies the benchmark matrix — a wrapper, conformance passage (FR107), four workloads of tools rebound, a frozen baseline definition under FR64, and a share of FR100's failure cases — without adding an argument FR51 does not already have at two
3. Automated contract authoring
4. Multi-agent capabilities
5. Semantic-equivalence deduplication (FR32)
6. Dynamic model routing (F8)
7. Context compression (F7)
8. Preflight planning (F9) — cut alongside F7 and F8, since its envelopes feed both
9. Model-based evaluation — the rubric signal in FR20
10. Advanced platform integrations (F15)
11. **Workload breadth** — committed workloads are dropped last, one at a time, in reverse build order. §8.4 then applies: no claim of generalization beyond the workloads actually completed

> `[NOTE FOR PM]` This cut order makes the Context Governor, Model Governor and Preflight Planner explicitly sacrificial. That is a defensible position, but it means the "seven mechanisms" story is committed *with a declared cut order*, not as seven equally load-bearing components. The demo narrative and any external claim must not imply otherwise.

---

## 5. Features & Functional Requirements

### Core — the policy and its protected mechanisms

#### F1 — Runtime Decision Policy

The product. One question applied before every unit of work.

- **FR1.** Before each unit of work, the system SHALL evaluate whether that unit is justified given the contract, the ledger state and the current `quality_state`, and SHALL emit exactly one **policy action** together with the **decision reason** that produced it. The runtime models three separate concepts and SHALL NOT collapse them:

  | Concept | What it answers | Values |
  |---|---|---|
  | **`policy_action`** | What the runtime does next | `proceed` · `proceed-with-substitution` · `deny` · `pause-for-approval` · `escalate` · `request-human` · `return-partial` · `terminate` |
  | **`decision_reason`** | Why that action was taken | A stable code from the versioned registry (FR104) |
  | **`terminal_reason`** | Why the run *ended* — recorded at most once | `stop-sufficient` · `halt-exhausted` · `halt-no-progress` · `approval-timeout` · `fail-closed` · `referred-human` · `returned-partial` |

  `policy_action` and `decision_reason` SHALL be recorded on every decision. `terminal_reason` SHALL be recorded only where the run ends, and SHALL be derived per FR103. The run additionally carries a `quality_state` (FR105).

  `proceed-with-substitution` means proceed, but on a cheaper model, compressed context, or a cached tool result rather than the step as proposed.

  > The concepts are separate because they answer different questions, and conflating them loses information the audit trail exists to carry. `deny` and `pause-for-approval` are actions a run survives; `sufficiency` is a reason that may or may not end the run; `halt-exhausted` is an ending. A record holding only one of them can answer neither "why did this step not happen" nor "how did this run finish."

- **FR2.** Where more than one terminating or blocking condition applies to the same step, the system SHALL resolve them in this fixed order:

  1. **`fail-closed`** (FR87–FR89) — the system cannot establish its own state, so nothing downstream can be trusted
  2. **Human-approval gate** (FR34, FR95) — a declared human gate outranks any automated decision. A pause carries the triggering contract clause as its reason; expiry carries `approval-timeout`
  3. **`sufficiency`** (FR23) — the contract is satisfied; further work is waste
  4. **`exhaustion`** (FR92) — no affordable step remains that could advance the floor
  5. **`no-progress`** (FR27) — progress has stalled while budget remains
  6. **`low-value` / `unaffordable`** (FR16, FR17) — this particular step is denied; the run continues

  **The winning condition SHALL be recorded as the decision reason. A terminal reason SHALL be recorded only where the resulting policy action terminates the run**, and SHALL be derived per FR103.

  > Two placements in the ladder carry weight. Sufficiency outranks everything below it because a run that has met its floor is *done*, not *stuck*, and mislabeling it corrupts the metric the entire product rests on (FR28, FR90). Exhaustion outranks no-progress because when both fire together the Loop Fuse demonstrably failed to halt in time — reporting the fuse would credit the governor for a save it did not make.

- **FR103.** `terminal_reason` SHALL name the **cause** of the ending, never the disposition. Where two causes could apply, the more specific wins, following the ladder in FR2. `returned-partial` and `referred-human` SHALL be recorded as terminal reasons **only where the hand-off is itself the cause** — a contract directing partial return or human referral with no exhaustion, stall, timeout or fail-closed condition present.

  | Situation | `decision_reason` | `policy_action` | `terminal_reason` |
  |---|---|---|---|
  | Floor met, budget remains | `sufficiency` | `terminate` | `stop-sufficient` |
  | Floor unmet, nothing affordable advances it | `exhaustion` | `return-partial` or `request-human` | `halt-exhausted` |
  | Floor unmet, budget remains, no progress across N iterations | `no-progress` | `terminate` | `halt-no-progress` |
  | Gate fails, budget remains, contract directs human review | `escalation-gate-fail` | `request-human` | `referred-human` |
  | Gate fails, budget remains, contract directs partial return | `escalation-gate-fail` | `return-partial` | `returned-partial` |
  | Approval gate elapsed, `on_timeout` terminates | `approval-timeout` | `terminate` | `approval-timeout` |
  | Approval gate elapsed, `on_timeout` escalates | `approval-timeout` | `escalate` | *none — the run continues* |
  | Gate cannot produce a verdict | `fail-closed` | `request-human` | `fail-closed` |
  | Ledger state lost | `fail-closed` | `terminate` | `fail-closed` |

  > This is the distinction that was previously ambiguous. A run that exhausts its budget and hands back a partial result has *one* cause and *one* disposition: `halt-exhausted` is why it stopped, `return-partial` is what the caller received. Recording `returned-partial` as the terminal reason would erase the cost story — and the cost story is the product.

- **FR104.** `decision_reason` SHALL be a stable code drawn from a **versioned, extensible registry**. New codes MAY be added at any time; a published code SHALL NOT be redefined, repurposed or removed. Every code SHALL declare the family it belongs to, so reporting can aggregate without enumerating. The MVP registry SHALL include at least:

  | Family | Codes |
  |---|---|
  | **Progress** | `justified` — the step advances an unmet mandatory criterion within budget |
  | **Denial** | `unaffordable` · `low-value` · `duplicate` · `semantic-duplicate` · `optional-satisfied` · `unsafe` |
  | **Substitution** | `cache-hit` · `context-compressed` · `cheaper-model-eligible` |
  | **Escalation** | `escalation-complexity` · `escalation-low-confidence` · `escalation-criticality` · `escalation-gate-fail` |
  | **Governance** | `approval-required` · `approval-granted` · `approval-denied` · `approval-timeout` |
  | **Termination** | `sufficiency` · `exhaustion` · `no-progress` · `fail-closed` |

  > A closed list would have to be complete on the first attempt, and it would not be. Stable codes with declared families let FR60 capture and §3.3 aggregation keep working as the runtime grows, while guaranteeing that a code in an old decision record still means what it meant when it was written. Immutability is the part that matters: a reused code silently rewrites history.

- **FR3.** Each decision SHALL cite the contract clause, the ledger state and the `quality_state` on which it rests, together with the Gate verdict where one exists.
- **FR4.** No enforcement mechanism SHALL alter execution except as directed by a policy decision. Mechanisms do not act autonomously.
- **FR5.** Every decision SHALL be recorded per F12 before it takes effect.
- **FR6.** A policy decision SHALL be replayable. The recorded state SHALL include the contract, the ledger, the `quality_state`, the Gate verdict where one exists, and **every model-derived input the decision consumed** — complexity and confidence estimates, rubric scores, planner envelopes, marginal-value estimates. A decision whose inputs were not recorded is not replayable, and no audit claim may be made about it.

#### F2 — Outcome Contract

- **FR7.** The system SHALL accept a declarative contract specifying: task goal; required deliverable structure; the **mandatory criteria and evidence fields** that together constitute the quality floor, declared separately from **optional or enrichment** criteria and fields; maximum tokens and maximum estimated cost; optionally a `verification_reserve` (`max_tokens`, `max_estimated_cost`), which where omitted is supplied by the deterministic default in FR101; permitted tools; maximum tool calls; maximum iterations; escalation policy; human-approval conditions; and `approval_timeout` with its `on_timeout` behaviour.

  > The mandatory-versus-optional classification lives in the contract, not in the Preflight Planner. F9 is cuttable (§4.3); FR17 and FR31 depend on this distinction and are not. **A protected requirement may not take its meaning from a component that can be cut.**

- **FR8.** Each mandatory quality criterion and evidence field SHALL declare an **executable deterministic verification method** and a verification mode: `reference-backed` (checked against a known-correct value) or `constraint-backed` (checked for presence, type and constraint). A criterion for which no deterministic verifier exists SHALL NOT be mandatory in the MVP and MAY instead be declared advisory. **Contract validation SHALL reject a mandatory criterion that carries no executable verifier.**

  > The rule is deliberately blunt: if it cannot be checked, it cannot be part of the floor. That is a real constraint on what a contract can promise — and it is the constraint that keeps the gate's authority honest, because it forecloses the failure mode where a mandatory criterion quietly resolves to a model's opinion. Criteria that matter but cannot be verified do not disappear; they become advisory and flow to the counter-metrics.
- **FR9.** The system SHALL validate a contract before execution begins and SHALL reject malformed contracts. Where a contract is well-formed but internally unsatisfiable — for example a quality floor unreachable within the declared ceiling — the system SHALL warn before executing rather than discovering it mid-run.
- **FR10.** A contract SHALL be immutable for the duration of a run, and SHALL carry a stable identifier and version recorded alongside every result produced under it.
- **FR11.** No runtime path SHALL relax, reinterpret or waive the quality floor. Cost ceilings may be exceeded only under FR24.
- **FR12.** Contracts SHALL be supplied as hand-authored files. No authoring, templating or inference capability is in MVP scope.
- **FR108.** Before the FR65 freeze, one Outcome Contract SHALL be authored for **each committed workload**, and every intended criterion SHALL be classified as **existing-verifier**, **new-deterministic-verifier-required**, or **advisory**. The review SHALL explicitly cover the criteria most easily missed because they are semantic — root-cause correctness, query-result correctness, code-location correctness, evidence completeness, and whether a conclusion is *supported* rather than merely present.

  New verifier types SHALL be admitted only for a demonstrated gap, and SHALL be deterministic over identical canonical inputs, project-implemented, free of network, filesystem, model and clock I/O, bounded and declarative in their parameters, fixed in verification mode by the registry, reusable beyond a single case, and covered by positive, negative, boundary, malformed-input and replay tests. **The MVP SHALL admit no more than three additional verifier types** without reopening scope. Types that cannot be reduced to deterministic comparison against frozen structured reference data — semantic matching, model-judged quality, or judging whether a citation *supports* a claim — SHALL NOT be admitted.

  > This exists because guessing the registry's breadth has an asymmetric failure mode. FR8 already makes an unverifiable criterion advisory rather than mandatory, so a shortfall never breaks the system — it quietly shrinks the quality floor until the Gate is checking presence and type, and §8.2a's honest limit becomes the ordinary case rather than the boundary. The contracts have to prove the need before the freeze, because after it the registry can no longer change without contaminating the ordering §8.2 depends on.

#### F3 — Budget Ledger

- **FR13.** The ledger SHALL maintain `allocated`, `spent`, `reserved` and `remaining`, in both tokens and estimated cost.
- **FR14.** The ledger SHALL hold a protected reserve sufficient for final synthesis and quality verification. Earlier steps SHALL NOT be able to spend the reserve, so verification can never be starved by overspend.
- **FR101.** The reserve required by FR14 SHALL be sized from the contract's `verification_reserve` where declared (FR7), and otherwise from a **deterministic default derived from the contract's ceilings**. The sizing SHALL be recorded with the run, so a derived reserve is auditable rather than implicit. The reserve SHALL be recalculated before any model escalation, and **an escalation SHALL NOT proceed where it would leave insufficient reserve for final synthesis and the Quality Gate executions FR98 requires**.

  > Escalation is the most expensive thing the governor does voluntarily, and it is triggered precisely when quality is in doubt — which is exactly when the verification that follows must not become unaffordable. An escalation that consumes the reserve buys a better answer nobody can check.
- **FR15.** The ledger SHALL attribute every unit of spend to either **task work** or **governor overhead** (evaluation, planning, compression), and SHALL further attribute each unit to **the mechanism that caused it**. Two-way attribution is insufficient to support any per-mechanism claim (FR62).
- **FR16.** The ledger SHALL reject a proposed step that is unaffordable within `remaining` less `reserved`.
- **FR17.** The ledger SHALL reject a proposed step whose **expected benefit is low relative to its cost**, and SHALL reject steps that are duplicated or unsafe. Affordability is not the only ground for denial.

  For the MVP, expected benefit is estimated by **unmet-criterion targeting**: a step is low-value when it does not advance a mandatory contract criterion or evidence field (FR7) that the Quality Gate currently reports as unmet. The estimator SHALL be pluggable, and the estimate SHALL be recorded as a decision input per FR6.

  **FR17 SHALL NOT deny a step required to establish, verify or correct an unmet mandatory criterion or evidence field.** The marginal-value estimator governs enrichment, never the floor. Where the floor is unmet, any affordable step that advances it is by definition worth paying for, and a denial that prevents the floor being reached is a violation of FR11 rather than an optimization.

  > Without FR17 the system denies only on exhaustion and repetition — precisely what a gateway budget cap already does. This is the marginal-value half of "is another unit of work worth paying for," and it is where the differentiation claimed in §1.3 actually lives. A crude estimator that is measured beats an elegant one that is asserted — but an estimator permitted to starve the floor would invert the product's central promise, which is why the carve-out above is not negotiable.

- **FR18.** The ledger SHALL expose current state to the policy before every decision.
- **FR92.** Budget exhaustion SHALL terminate the run with terminal reason **`halt-exhausted`**, recorded and reported as distinct from `halt-no-progress` (FR27), `stop-sufficient` (FR23) and `fail-closed` (FR90).

  > Running out of money and running out of progress are different events with different remedies. Conflating them credits the Loop Fuse for runs on which it did nothing, and hides the case the overhead study exists to find — a governor that spent the whole budget and still could not reach the floor.

- **FR93.** Where the quality floor is unmet and no affordable step remains that would advance a mandatory criterion, the system SHALL terminate rather than continue proposing steps that FR16 or FR17 will deny. The recorded triple SHALL be `decision_reason = exhaustion`, `policy_action = return-partial` (stating the unmet mandatory criteria explicitly) or `request-human` as the contract directs, and `terminal_reason = halt-exhausted` (FR103). **A governor that neither progresses nor stops is worse than no governor at all.**

#### F4 — Quality Gate & Sufficiency Decision

The mechanism the policy depends on most. Without a signal for *sufficient*, "worth paying for" has no meaning and the system degrades into ordinary cost-capping.

- **FR19.** The gate SHALL evaluate the current result against the contract's **mandatory** criteria and evidence fields (FR7) for deliverable completeness, presence and accuracy, and task adherence. Optional and enrichment criteria SHALL NOT affect the verdict.
- **FR20.** **Deterministic criterion-level validation SHALL be the authoritative gate.** A model-judged rubric MAY contribute an additional signal, but SHALL NOT override a deterministic failure and SHALL NOT alone establish a pass.
- **FR21.** The gate SHALL record the verification mode behind every verdict. A pass resting wholly or partly on `constraint-backed` verification SHALL be labeled **constraint-backed**; only a pass in which every mandatory criterion was `reference-backed` may be labeled **reference-backed**. The label SHALL travel with the result wherever it is reported.
- **FR22.** Tool use SHALL be assessed in two separable ways, and the two SHALL NOT be blended:

  - **Deterministic tool-use conformance**, declared in the contract — that a required tool was invoked, that a mandatory field carries the provenance the contract demands, that no forbidden tool was called. These are **gating**, evaluated exactly as any other mandatory criterion under FR20.
  - **Model-judged tool-use quality** — whether the tool chosen was the best available, whether its output was used well. These SHALL be recorded as **advisory evidence** (FR53) and MAY be reported as a separate diagnostic metric. They SHALL NOT alter the Gate verdict, and SHALL NOT determine the FR70 tool-suppression correctness result.

  > The second exclusion matters as much as the first. FR70 establishes suppression correctness by re-execution against the frozen tools — a mechanical check. Letting a model's opinion contribute to that number would make the counter-metric depend on the same judgement it exists to police.

- **FR94.** The gate SHALL emit exactly one of two verdicts against the contract's mandatory criteria: **`pass`** or **`fail`**. There is no intermediate verdict. Every verdict SHALL carry the `reference-backed` or `constraint-backed` qualifier required by FR21 and the per-criterion breakdown required by FR26.

  > The binary form is deliberate. A `pass-with-concern` state would have to be resolved somewhere: either the policy stops on it, in which case it was a pass, or it does not, in which case it was a fail. A third state moves that judgement out of the contract and into the runtime — exactly what FR20 exists to prevent. Concerns are real, but they belong in the decision record and the counter-metrics where they can be measured, not in a verdict where they would be negotiated.

- **FR23.** On `pass`, the system SHALL stop immediately. No further billable work SHALL be performed beyond finalization of the deliverable. Where a human-approval pause is outstanding, FR2 governs.
- **FR24.** On `fail` with budget available, the system SHALL perform a targeted retry or `escalate` per the contract's escalation policy. On `fail` with no safe budget remaining, the system SHALL either `return-partial` — stating the unmet mandatory criteria explicitly — or `request-human`, as the contract directs. Where the contract requires the floor to be met, exceeding the cost ceiling and requesting a human is the correct behaviour.
- **FR25.** The system SHALL NOT return a result that fails the floor as though it passed. Every returned result SHALL carry the gate verdict.
- **FR26.** The gate SHALL record which specific criteria and evidence fields passed and which failed, not only an aggregate verdict.
- **FR98.** The Quality Gate SHALL execute after every completed unit of work that can change the candidate result, and **before any terminal halt other than a fail-closed halt**. The contract MAY declare additional evaluation checkpoints, and MAY omit checkpoints for steps that cannot affect the candidate result. Every gate execution SHALL be counted in governor-overhead accounting (FR15).

  > Cadence is not a detail. Without it, a run that became sufficient at step four can be halted at step seven and recorded as `halt-exhausted` or `halt-no-progress` — the product's central event, misfiled as a failure. Evaluating before every non-fail-closed terminal halt is what gives `stop-sufficient` first refusal on the ending. The fail-closed exception exists because a gate that cannot produce a verdict cannot be asked for one.

- **FR105.** A run SHALL carry a `quality_state` of `not-evaluated`, `pass` or `fail`. It SHALL be `not-evaluated` until the gate first executes (FR98). **Gate verdicts themselves remain binary** (FR94) — `not-evaluated` is the *absence* of a verdict, not a third one. `sufficiency` SHALL NOT be a valid decision reason while `quality_state` is `not-evaluated`, and no result SHALL be returned as passing in that state.

  > Before the first gate execution the honest answer to "is this good enough" is *we have not looked*. Modelling that as `fail` would make every run start in violation of its contract and would corrupt the fail counts; modelling it as `pass` would let a run stop before anything was checked. It belongs in run state, not in the verdict.

#### F5 — Loop Fuse

- **FR27.** The system SHALL compute a progress fingerprint for each iteration, covering evidence gained, task-state change and quality delta, and SHALL halt on any of: repeated state, no new evidence across a configured number of iterations, repeated tool arguments, or the contract's iteration limit. **Budget exhaustion is not a loop-fuse condition**; it terminates under FR92.
- **FR28.** A halt caused by lack of progress SHALL carry terminal reason **`halt-no-progress`**, recorded and reported as distinct from `stop-sufficient` (FR23), `halt-exhausted` (FR92) and `fail-closed` (FR90). These SHALL NOT be conflated in any result, report or interface.

#### F6 — Tool Governor

- **FR29.** The system SHALL canonicalize tool name and arguments into a stable key.
- **FR30.** The system SHALL reuse cached results for tools declared deterministic, within the scope of a single run.
- **FR31.** The system SHALL deny exact duplicate calls, and SHALL deny calls classified by the contract as optional or enrichment (FR7) once every mandatory criterion the contract declares is satisfied.
- **FR32.** The system SHOULD deny semantically equivalent calls that differ only in surface form. *Conditional — this is the "semantic-equivalence deduplication" entry in the cut order (§4.3) and SHALL be independently disableable.*
- **FR33.** **No optimization-driven suppression SHALL apply to tools declared side-effecting or non-deterministic.** Specifically, FR30, FR31 and FR32 SHALL NOT cache, deduplicate or deny such calls. Denials grounded in safety (FR17), affordability (FR16), or a human-approval requirement (FR34) are not optimization-driven and DO apply.

  > This distinction matters: refusing to cache a payment call is correct; refusing to *stop* a payment call that is unaffordable or unapproved would not be.

- **FR34.** The system SHALL enforce the contract's `human_approval_conditions`. Where a tool call meets a declared condition, execution SHALL pause and SHALL NOT proceed until approval is granted or the contract's `approval_timeout` elapses (FR95). **A contract that requires approval and a runtime that does not enforce it is a governance defect, not a configuration choice.**
- **FR95.** An approval pause SHALL be bounded by the contract's `approval_timeout`. On expiry the system SHALL apply the contract's declared `on_timeout` behaviour and SHALL record decision reason **`approval-timeout`**, distinct from `approval-denied`. Where `on_timeout` terminates, `approval-timeout` is also the terminal reason; where a contract explicitly configures escalation, the run continues and no terminal reason is recorded (FR103).

  **Where `on_timeout` is unspecified, the default SHALL be exactly: `decision_reason = approval-timeout`, `policy_action = terminate`, `terminal_reason = approval-timeout`. The gated call SHALL NOT be made.**

  > "Fail closed" named a posture without naming a behaviour, which left the default open to interpretation at the one point where interpretation is least welcome. The default is now a specific triple. Contracts that want the run to survive a timeout must say so.

  > An unbounded pause is not a safe default. It is an outage wearing a governance costume — and it converts a human gate, which exists to protect the run, into the thing that kills it silently.

- **FR35.** Every denial, cache hit, approval pause and approval timeout SHALL be recorded with its reason.

### Conditional mechanisms

> Committed scope, but present in the cut order (§4.3). Each SHALL be independently disableable without affecting the protected core (NFR10).

#### F7 — Context Governor

- **FR36.** The system SHALL select only the evidence required for the current step rather than carrying the accumulated transcript forward.
- **FR37.** The system SHALL compress tool output into structured evidence capsules.
- **FR38.** Compression SHALL preserve citations, identifiers, numeric values, policy clauses and any contract-required attributable fact verbatim. **Compression SHALL NOT drop an attributable fact.**
- **FR39.** Compression spend SHALL be attributed to governor overhead per FR15.

#### F8 — Model Governor

- **FR40.** Execution SHALL begin on the cheapest model eligible under the contract.
- **FR41.** The system SHALL escalate model capability only where justified by task complexity, low model confidence, policy criticality, or a failed quality evaluation; SHALL NOT select a model outside contract eligibility; and SHALL NOT escalate where doing so would breach the verification reserve (FR101).
- **FR42.** Every escalation SHALL be disclosed in the decision record. Model substitution SHALL never be silent.

#### F9 — Preflight Planner

- **FR43.** The system SHALL produce a typed execution graph with an estimated token and tool envelope per step.
- **FR44.** The plan SHALL carry the contract's mandatory-versus-optional classification (FR7) onto each step. **F9 consumes that classification; it does not own it.** Cutting F9 (§4.3) SHALL NOT affect its availability to FR17, FR19 or FR31.
- **FR45.** Planning spend SHALL be attributed to governor overhead per FR15.

### Operating modes and surfaces

#### F10 — Shadow Mode

> **Protected.** Shadow mode is the adoption path (UJ-1) and the risk-free route by which a team can evaluate the governor against their own workload before enabling enforcement. It is not in the cut order and is not covered by NFR10. In the MVP it is exercised on synthetic and replayed workloads only (FR106).

- **FR46.** The system SHALL support running observing-but-not-enforcing: the host agent's **ungoverned path executes and is recorded**, while the governor logs every decision it would have made and the estimated effect of each.
- **FR47.** A shadow run SHALL produce a decision record of the same shape as an enforced run.
- **FR48.** A shadow run SHALL record the **executed ungoverned path** together with the **estimated governed counterfactual**. Only one path is observed. The governed path is inferred, and SHALL NOT be described as captured, measured or realized.
- **FR96.** A shadow run SHALL mark the **first divergence** — the earliest decision at which the governor would have acted differently from the host agent. Everything the counterfactual asserts after that point is inference rather than observation, and SHALL be labeled as such wherever it is reported. Estimates SHALL NOT be extrapolated past a divergence without disclosing that they were.

  > Before the first divergence the two paths are the same run, so the comparison is exact. After it, the governed path never happened. A shadow-mode saving figure is an estimate whose error grows with every subsequent decision, and the divergence marker is what lets a reader judge how far the estimate has travelled from the evidence.

- **FR49.** Run mode SHALL be explicit and recorded in every result. **Shadow-mode figures SHALL NOT be presented as realized savings.**
- **FR106.** In the MVP, shadow mode SHALL be demonstrated against **synthetic and replayed workloads only**, consistent with NFR9. **Shadowing live production traffic is post-MVP**, and no MVP claim SHALL rest on it.

  > UJ-1 describes the product's adoption story, and that story runs against real traffic. The MVP demonstrates the mechanism, not the story: it shows that a shadow run produces a decision record and a marked counterfactual, on cases the builder authored. Conflating the two would let a synthetic demonstration be reported as production evidence — and §8.4 forbids exactly that.

- **FR109.** Every run SHALL declare a **data class** — `synthetic`, `replayed` or `non-synthetic` — supplied by the **frozen case-set attestation** and recorded with the run, where it selects the retention profile. There SHALL be no default: a run whose data class is absent SHALL be refused. A `replayed` run SHALL **inherit the data class of the run it replays**. The system SHALL NOT persist **either evidence or decision records** for any run whose data class is other than `synthetic` until a separate **production-data governance profile** has been approved; where no such profile exists, the runtime SHALL **refuse** persistence rather than applying the MVP retention profile to it. The profile SHALL define approved storage location, tenant and use-case isolation, encryption in transit and at rest, workload and operator identities, role-based read/write/delete permissions, legal and compliance classification, retention period by data class, deletion SLA and deletion verification, backup and replica deletion, incident handling and disclosure, audit access, export restrictions, and whether specific raw fields may be persisted at all. FR106 SHALL remain unchanged until it exists.

  > The MVP retention profile was written for data the builder authored. The failure mode this forecloses needs nobody to decide anything: shadow mode is pointed at real traffic, the stores keep doing what they already do, and a governance boundary is crossed silently. Refusing is the only behaviour that makes the crossing visible. It has to cover the decision record too, because refusing only the evidence would leave the record persisting under a profile that does not cover it — and it has to trigger on anything that is not `synthetic`, because replaying captured production traffic does not launder it.

#### F11 — Integration & Adoption Surface
- **FR50.** The system SHALL wrap an existing tool-using agent loop without requiring that agent to be re-architected. Integration SHALL consist of wrapping the loop and declaring a contract.
- **FR51.** The system SHALL be demonstrated against at least two dissimilar agent implementations across the four committed workloads.
- **FR52.** The system SHALL support an OFF state in which the host agent executes exactly as its baseline, with no governor participation. This is the mechanism by which the OFF/ON benchmark is run.
- **FR107.** Each host adapter SHALL pass a fixed **adapter-conformance battery** before any run it produces may be reported. The battery SHALL assert, against the resulting decision record, that a denial was honoured, a substitution applied, an approval pause observed, a sufficiency stop terminated the run, a fail-closed condition halted it, and shadow-mode decisions were not applied. Because enforcement is **cooperative** — the adapter, not the governor, applies the verdict — the battery SHALL additionally carry an **out-of-band side-effect probe** in which scripted tools assert for themselves whether they were invoked.

  > A decision record cannot detect the one failure it is the evidence for. An adapter that executes a gated or denied call while recording a clean pause produces a plausible, internally consistent and entirely false audit trail — and every claim in §8 then rests on it. The probe is the only thing that catches that, and its cost scales with the number of committed adapters, which is why the third adapter sits at cut position 2 (§4.3).

#### F12 — Decision Record & Audit Trail

> **Protected.** FR5 forbids any decision from taking effect before it is recorded, so cutting F12 would stop the system entirely. It is not conditional and never was.

- **FR53.** Every decision SHALL be recorded with: timestamp, step identifier, `policy_action`, `decision_reason`, `terminal_reason` where one was set (FR1, FR2, FR103), `quality_state` at decision time and the Gate verdict where one exists (FR105), contract clause referenced, ledger state at decision time, model used, tokens consumed, and the model-derived inputs required by FR6.
- **FR54.** The decision record SHALL be queryable per run and exportable.
- **FR55.** The record SHALL be sufficient to reconstruct **why a run stopped where it did** without re-invoking the underlying model. This holds only because FR6 requires the model-derived inputs to be recorded; without them the reconstruction would be a guess.
- **FR56.** Prompts, tool arguments and tool results SHALL be redacted before persistence, per NFR5.

### Evidence

#### F13 — Benchmark Harness & Evidence Pipeline

- **FR57.** The harness SHALL execute a frozen case set against baseline and governed configurations using the same tools, model versions and settings.
- **FR58.** The harness SHALL support repeated runs per case and SHALL report mean, median and **absolute pass counts** — not percentages alone.
- **FR59.** The harness SHALL enforce a declared minimum case count per workload, and SHALL refuse to publish a comparison for a workload below it. `[ASSUMPTION]` The minimum is unset — see Q6 in §11.
- **FR60.** The harness SHALL capture per run: model and version, tokens, cached tokens, tool calls, retries, duration, the full sequence of policy actions and decision reasons (FR1, FR104), the terminal reason where one was recorded (FR2, FR103), final `quality_state` (FR105), gate verdict with its verification-mode qualifier (FR21, FR94), advisory tool-quality signals (FR22), escalations, human interventions, approval timeouts, budget breaches, degraded mechanisms, and any safety or adherence evaluation result.
- **FR61.** The harness SHALL report governor overhead as its own line item, and SHALL report gross and net figures side by side.
- **FR62.** **For measurement only**, the harness SHALL support ablation of each savings-producing policy or mechanism — including sufficiency stopping, marginal-value denial (FR17), exact tool deduplication, the Loop Fuse, the Context Governor, the Model Governor, the Preflight Planner, and any other enabled optimization mechanism. **A headline savings figure SHALL NOT be published without its per-mechanism breakdown.** Measurement-only ablations SHALL NOT be taken to imply that every ablated configuration is a supported production configuration.

  > Ablating only the *cuttable* mechanisms would answer the easy question and duck the important one. If the savings turn out to come almost entirely from exact tool deduplication, the sufficiency claim is decoration — and deduplication is the one mechanism the addendum attributes to products that already exist. The protected core has to be ablatable precisely because it carries the argument.

- **FR99.** The harness SHALL report every marginal-value denial (FR17), recording the mandatory criteria unmet at decision time, the estimated benefit, the estimated cost, the resulting policy action, and whether the denial complied with FR17's quality-floor protection rule. **A denial that blocked progress toward an unmet mandatory criterion SHALL be reported as a violation, not as a saving.**

  > FR70 measures whether *tool suppression* was sound. FR99 measures whether the *marginal-value policy* was sound. They are different mechanisms making different mistakes, and a single accuracy number covering both would hide whichever is performing worse.

- **FR63.** The harness SHALL publish failures and escalations alongside successes. Reports SHALL NOT present successes in isolation.
- **FR64.** The baseline definition — prompt, tools, dataset, model version, temperature and settings — SHALL be frozen, versioned and published. The harness SHALL refuse to produce a comparison when the executing baseline configuration differs from the frozen definition.
- **FR65.** The quality rubric and case answer keys SHALL be frozen, versioned and content-hashed before governor implementation begins. The harness SHALL refuse to publish a comparison when the rubric hash differs from the one recorded at freeze time.

  The freeze artifact SHALL additionally include the **verifier-registry version and hash**, and, for each workload, the **count and percentage of mandatory criteria that are `reference-backed` and `constraint-backed`**. Every mandatory criterion SHALL resolve to a registered deterministic verifier at freeze time, and advisory criteria SHALL be listed with the reason they are non-gating. A workload is **predominantly constraint-backed** where its constraint-backed mandatory count exceeds its reference-backed mandatory count, and SHALL be reported as such wherever its results are claimed.

  > §8.2 states this obligation. FR65 is what makes it enforceable. Rubric circularity is rated a higher risk than baseline unfairness, so it should not have the weaker defence. The registry joins the same freeze because a criterion takes its executable meaning from a verifier type: a frozen rubric resting on an unfrozen registry is not frozen. The per-workload counts are published because FR21's run-level qualifier reports only that a pass *touched* constraint-backed verification — it cannot show how much of the floor was substantive.

- **FR66.** Savings and quality targets, counter-metric thresholds, the minimum case count (FR59) and the blind-review sample size (FR69) SHALL be recorded **before any governed evaluation-set results are executed or inspected**. Calibration-set results (FR102) MAY inform those numbers. **A target set after the evaluation results are known cannot be missed, and SHALL NOT be reported as having been met.**
- **FR102.** The harness SHALL maintain the **calibration case set** and the **frozen evaluation case set** as separate artifacts, and SHALL refuse to admit calibration-set results into any headline or submission figure. It SHALL record the moment preregistration (FR66) completed and the moment evaluation-set execution began, and SHALL refuse to publish a comparison where the latter precedes the former.

  > This is what dissolves the apparent circularity in §3.1 — targets set after measuring overhead, yet fixed before results are seen. Both hold, because they refer to different data. The calibration set is where the governor's own cost is discovered; the evaluation set is where the claim is tested, and it stays sealed until the numbers it will be judged against are already written down.
- **FR67.** The harness SHALL support an overhead break-even study establishing the task length at which the governor begins paying for itself.
- **FR68.** Any reported run SHALL be re-executable from its recorded configuration.
- **FR69.** The harness SHALL support blind human review of a fixed sample of passed runs per workload, sufficient to compute false-sufficiency rate. The reviewer SHALL see the deliverable and the contract, and SHALL NOT see the gate verdict, the decision record, or which configuration produced the run. `[ASSUMPTION]` Sample size per workload is unset — see Q4 in §11.
- **FR70.** The harness SHALL measure **tool-suppression accuracy**. The **denominator** SHALL be every tool call the governor suppressed — denied, deduplicated, or served from cache. The **numerator** SHALL be those suppressions confirmed correct, where correctness is established by re-executing the suppressed call against the frozen case's tool implementation and comparing:

  - for a cache or duplicate suppression, the re-executed result MUST be equivalent to the result that was reused;
  - for an optional-call denial, a counterfactual run including the call MUST NOT change the gate verdict.

  Suppressions that cannot be checked SHALL be reported as **unverified**, never assumed correct. **Tool-suppression error rate**, the counter-metric in §3.3, is defined as **1 − tool-suppression accuracy**; the two are one measurement reported in two directions and SHALL NOT be computed independently. The harness SHALL NOT report a tool-call reduction figure unless accompanied by this measure. FR70 covers tool suppression only; marginal-value denials are measured separately by FR99.

  > FR70 exists for the same reason false-sufficiency rate exists. A tool-call reduction number on its own is maximized by denying everything. The reduction and the accuracy travel together, or neither is reported — and "accuracy" means nothing without a stated denominator, which is why one is fixed here rather than left to the implementation.

- **FR71.** The harness SHALL measure **compression fidelity** — the rate at which citations, identifiers, numeric values, policy clauses and any contract-required attributable fact present in raw tool output survive into the evidence capsule — so that FR38 is verified rather than asserted.
- **FR100.** The benchmark suite SHALL contain synthetic cases exercising at least: sufficiency stop, budget exhaustion, no-progress halt, approval timeout under **both** `on_timeout` postures, Quality Gate unavailable, Budget Ledger state loss, and optimization-mechanism failure. For **every** case the harness SHALL assert the expected `policy_action` and `decision_reason`. It SHALL assert a `terminal_reason` **only for cases in which execution actually terminates**; cases that survive their failure — an escalating approval timeout, a degraded optimization mechanism under FR85 — SHALL be asserted to record no terminal reason and to continue.

  > Each of those paths is a claim this PRD makes about behaviour under stress, and none of them occurs on a happy-path case. Untested failure paths are the ones that turn out, under demonstration, to have been aspirations. Asserting a terminal reason on every case would bake in the very conflation FR103 exists to prevent.
- **FR97.** The harness SHALL compute the **proof card** as a recorded artifact: quality-matched pairing of baseline and governed runs on the same case, net tokens, net cost, tool calls, the per-mechanism breakdown required by FR62, and the gate verdicts with their qualifiers. **Pairing and computation live in F13, not in F14.** F14 renders the artifact and F16 consumes it; cutting F14 SHALL NOT affect the proof card's availability or content.

  > F14 sits first in the cut order and F16 is protected. A protected artifact that could only be produced by a cut-first component would be protected in name only.

#### F14 — Side-by-Side Execution View & Proof Card

> The view replays **recorded** runs rather than streaming live executions. It reaches the same demonstrative moment at a fraction of the build cost, and avoids concurrency, cancellation and error-state handling in a component that sits first in the cut order.

- **FR72.** The view SHALL replay a recorded baseline run and a recorded governed run of the same case concurrently.
- **FR73.** The view SHALL replay governor decisions in execution order, with human-readable reasons — cache hit, duplicate denied, evidence compressed, quality passed, escalation approved.
- **FR74.** The view SHALL show ledger state as it stood at each replayed decision.
- **FR75.** The view SHALL render the proof card computed by FR97. It SHALL NOT compute proof figures of its own.
- **FR76.** The view SHALL support drilling into a single run's decision record.
- **FR77.** **The view SHALL be read-only, and SHALL consume only recorded output.** It SHALL have no path to influence execution. Disabling it SHALL NOT change governed behaviour or realized savings.

#### F15 — Gateway Token Metering

- **FR78.** Token counts for reported results SHALL be obtainable from gateway metering, independent of the governor's self-report.
- **FR79.** The system SHALL reconcile gateway-measured against governor-reported counts, and SHALL surface any discrepancy rather than silently preferring one.
- **FR80.** Where gateway metering is unavailable, the system SHALL fall back to governor-side counting **and SHALL mark the resulting figures as self-reported**, downgrading the stated independence of the measurement rather than concealing it.

#### F16 — Submission Artifact

The two-minute video is the artifact that is actually evaluated. A PRD that scopes the system but not its submission has scoped the work that does not get judged.

> **F16 depends on F13 and F12, never on F14.** F14 sits first in the cut order; if it is cut, the submission remains producible from the recorded proof card (FR97) and the decision records (F12).

- **FR81.** The submission SHALL include a video of at most two minutes covering four beats in order: the problem, the artifact, the proof, and the scale argument.
- **FR82.** Every figure shown in the submission SHALL be drawn from the recorded artifacts of F13 and F12, SHALL be traceable to an **evaluation-set** harness run that satisfies §8, and SHALL carry the same labeling obligations — net not gross, per-mechanism attributed, gateway-measured or self-reported, enforced or shadow, `reference-backed` or `constraint-backed`.
- **FR83.** The submission SHALL NOT present projected, shadow-mode or single-run cherry-picked figures as realized savings.
- **FR84.** The submission SHALL show the mechanism running, not only its results — at minimum the Outcome Contract, a governor decision stream, and a stop caused by sufficiency. These MAY be presented from recorded artifacts; F14 is a convenience for producing them, not a dependency.

---

## 6. Selected User Journeys

> `[ASSUMPTION]` All four journeys below are drafted rather than narrated by a real user. Protagonists, sequences and outcomes are inferred. **Revisit condition:** correct or replace them after the two-to-three structured conversations with production agent owners (§2.1). Until then they carry design intent, not evidence, and SHOULD NOT be quoted externally as user research.

### UJ-1 — Priya proves it before she trusts it (shadow-mode adoption)

Priya runs a document-investigation agent that has been in production for four months. It works. It also costs more each month than anyone forecast, and she cannot defend the number in a review because she cannot say which part of the spend was necessary.

She is not going to put an unproven governor in front of a working agent. So she wraps it in shadow mode: the governor observes, decides nothing, enforces nothing, and logs what it *would* have done. She writes one contract by hand for her most common task shape — the required deliverable fields, the evidence citations she already checks manually, a ceiling drawn from her current worst case.

She lets it run against a week of real traffic. At the end she has a log saying: on a majority of runs, the outcome met your declared floor before the agent stopped, and here is what the remaining iterations cost.

That log is what gets her to enable enforcement — not a pitch, and not a dashboard. It lands because she can see the decision she would have made, against her own traffic, with nothing at risk.

> `[NOTE FOR PM]` This journey runs against production traffic, which the MVP does not do. The MVP demonstrates the *mechanism* — a shadow run producing a decision record and a marked counterfactual — on synthetic and replayed cases (FR106). Priya's week of real traffic is the adoption story, and it must not be narrated as something the MVP evidences.

### UJ-2 — The floor is not reached and Marcus gets called (escalation)

Marcus owns a supply-chain exception agent. A run arrives on a case with a missing supplier record. The agent works the problem, the Quality Gate evaluates, and two required evidence fields come back empty. The gate fails.

Budget remains, so the policy escalates — a more capable model, and a targeted retry against the specific unmet fields rather than a blind re-run. The gate fails again on the same field. The reserve is now the only budget left, and the reserve exists for verification, not for another attempt.

The contract says this task type requires the floor. So OutcomeFuse does the thing it is built to do: it does not return a cheaper answer that fails. It stops, marks the run as requiring human intervention, and hands Marcus a result that says plainly *these two fields could not be established, here is what was tried, here is what it cost*.

Marcus resolves it within minutes, because he was given the gap rather than a plausible-looking answer with a hole in it. The run breached its cost ceiling. That shows up in the budget-breach counter-metric, as designed.

### UJ-3 — Dana asks why it stopped there (audit)

Dana reviews AI systems for compliance. Her question is never "did it save money" — it is "can you show me that saving money never changed the answer."

She opens a single run's decision record. She sees the contract it executed under, with its version. She sees each decision in order: a tool call denied as a duplicate, with the canonicalized key that matched; evidence compressed, with the citations preserved verbatim through the compression; a model escalation, with the failed evaluation that triggered it; and the stop, with the specific evidence fields that satisfied the floor.

Nothing in the record requires her to trust the model's account of itself. The reason for each decision sits next to the ledger state at the moment it was made. She can reconstruct why the run stopped where it did.

What she is checking for is silent substitution — a cheaper model quietly used on a critical step, a compression that dropped a fact, a stop that was really an exhaustion. The record distinguishes all three.

### UJ-4 — Sam wraps his agent on a Tuesday afternoon (first-run integration)

Sam has an internal codebase-triage agent — a small service wrapped around a tool loop. He is evaluating OutcomeFuse and has budgeted a short window before he loses interest.

He wraps the loop and writes a contract file. The hardest part is the quality floor — he has to state, for the first time, what a good triage output actually contains. It takes him longer than the integration does.

> `[NOTE FOR PM]` This is the real adoption friction, and the journey should not pretend otherwise. It is also the moment OutcomeFuse creates value before saving a single token, by forcing the question.

He runs it once with the governor OFF to get his baseline, once with it ON. Two numbers, with minimal integration effort. Whether he continues depends entirely on whether those two numbers differ enough to matter on his workload — which is exactly what the break-even study (FR67) exists to predict.

---

## 7. Non-Functional Requirements

- **NFR1 — Decision latency.** Governor decision overhead per step SHALL be bounded, measured and reported. **No latency target is set in this PRD**; a bound SHALL be established against measured baseline step latency alongside the net-savings restatement (§3.1).
- **NFR2 — Overhead share.** Governor overhead SHALL be measured from the first run, never assumed negligible, and SHALL be reported as its own line item in every result.
- **NFR3 — Replayability.** Governed runs SHALL be reproducible from recorded configuration and decision state (FR6, FR68).
- **NFR4 — Failure posture.** The system SHALL behave per §10 on internal failure.
- **NFR5 — Privacy.** Prompts, tool arguments and tool results SHALL be redacted before being written to telemetry or persisted records. Traces can contain sensitive input and tool data and SHALL be treated accordingly.
- **NFR6 — Cache isolation.** Cached tool results SHALL be partitioned by tenant and use case. There SHALL be no cross-user reuse for personalized or authorization-sensitive responses.
- **NFR7 — Least privilege.** Tool access SHALL operate under least-privilege identity. No credential SHALL be embedded in a contract.
- **NFR8 — Domain neutrality.** No workload-specific logic SHALL exist in the governor core. Workload specificity lives in contracts, tools and cases.
- **NFR9 — Data handling.** MVP evaluation SHALL use synthetic cases only. No production or confidential data.
- **NFR10 — Modularity.** Each conditional mechanism (F7, F8, F9) and each conditional requirement (FR32, the rubric signal in FR20, the advisory tool-quality signal in FR22) SHALL be independently disableable without affecting the protected core. This makes the cut order in §4.3 executable rather than aspirational, and it is also what makes the per-mechanism ablation in FR62 cheap.
- **NFR11 — Build constraint.** The system is built solo within a one-month window. Any requirement whose satisfaction depends on capability not demonstrable in that window SHALL be moved out of scope rather than carried as an unmet requirement.
- **NFR12 — Trace retention and access.** Decision records, traces and evidence SHALL carry a declared retention period and access control commensurate with the sensitivity of the input and tool data they may contain. Redaction (NFR5) reduces exposure; it does not remove the need for retention limits.

  Retention is **two-tiered by sensitivity**, under profile `mvp-synthetic-v1`:

  - **Raw synthetic evidence** SHALL be retained for **60 calendar days** from a harness-owned `run_closed_at` — set when the run reaches a terminal state, completes normally, or is explicitly abandoned — and SHALL then be deleted as a **complete per-run evidence directory**, including deliverables, capsules, raw tool outputs, suppression re-execution artifacts, compression-fidelity artifacts, generated blind-review packets and temporary copies. Expiry SHALL NOT be derived from filesystem modification, access or copy time.
  - **Redacted decision records and proof artifacts** SHALL be retained for **180 calendar days** from campaign seal.

  There SHALL be no ad hoc per-run extension: evidence that expires before an FR69, FR70 or FR71 assessment completes SHALL be regenerated by re-running the frozen case. Deletion SHALL produce a **content-free receipt** — run identifier, evidence-manifest hash, retention profile, scheduled expiry, deletion time and result — written to a separate append-only campaign retention manifest, and SHALL NOT be appended after a sealed terminal record row. This is logical deletion appropriate to synthetic data and SHALL NOT be described as cryptographic erasure or media sanitization.

  Access SHALL be enforced as an explicit matrix: the runtime driver writes only its own run's evidence; the harness is the sole programmatic reader; the retention command holds delete and manifest-status permissions only; the blind-review renderer reads evidence and the contract but SHALL NOT hold decision-record, verdict or manifest access; and quality verifiers, host adapters, the static viewer, the submission generator and the model and approval adapters SHALL have no access at all.

---

## 8. Measurement & Evidence Standards

This product's deliverable is, in part, a **claim**. The rules that make the claim credible are requirements, not methodology notes, and are stated here as normative.

### 8.1 Baseline fairness

- The baseline SHALL be a *reasonable* agent, not a strawman: full retrieved context per step, one capable model throughout, and a conventional evaluator/retry loop with a maximum-iteration safety limit.
- **The baseline's evaluator SHALL be genuine.** It checks the agent's own completion notion — which is what a conventional agent has. What it does not check is an externally declared quality floor with named evidence fields, because that artifact does not exist without an Outcome Contract. The comparison is between *self-assessed completion* and *contract-assessed sufficiency*, and results SHALL be described in those terms rather than as "the baseline never stops."
- Prompt, tools, dataset, model version, temperature and settings SHALL be frozen before any comparison, and the frozen definition SHALL be published alongside results (FR64).
- The baseline is defined by the party who benefits from it losing. Publishing its definition is the only defence against that.

### 8.2 Rubric integrity

- **The quality rubric and case answer keys SHALL be frozen, versioned and content-hashed before governor implementation begins**, and the harness SHALL refuse to publish a comparison on a drifted rubric (FR65). The same person writes the rubric and the optimizer that must satisfy it; freezing first is what prevents the optimizer being fitted to a moving target.
- Deterministic criterion-level validation SHALL be preferred over model-judged scoring wherever the criterion is checkable (FR20).

### 8.2a The limit of the deterministic gate

The gate is fully sound only where a criterion can be checked against a known-correct value. In the MVP that condition holds for `reference-backed` criteria because the cases are synthetic and the answer keys were authored alongside them. **On a production workload with no answer key, mandatory criteria collapse toward `constraint-backed` verification — presence, type, constraint — which is a meaningfully weaker guarantee and one that adjacent products already provide.**

This is stated rather than buried because it is the honest boundary of the strongest claim in the document. Three consequences follow:

- FR8 requires every mandatory criterion to declare an executable verifier and its mode, so the distinction is explicit per contract rather than assumed — and a criterion with no deterministic verifier cannot be mandatory at all.
- FR21 requires any pass resting wholly or partly on `constraint-backed` verification to be labeled as such, wherever it is reported.
- How a production deployment establishes ground truth without hand-authored keys is an open question (Q9, §11), not a solved problem this PRD is claiming.

### 8.3 Reporting

- Report **net**, inclusive of all governor overhead. Gross MAY be shown alongside; it SHALL NOT be the headline.
- Report savings **per mechanism**. A headline figure without its breakdown is not reportable (FR62).
- Report mean, median and absolute pass counts. With a modest case count a "within N percentage points" quality claim may not be statistically meaningful, so absolute counts SHALL accompany every percentage.
- No workload SHALL be reported below its declared minimum case count (FR59).
- Failures and escalations SHALL be published alongside successes.
- A tool-call reduction figure SHALL NOT be published without its tool-suppression accuracy (FR70).
- Where possible, token counts SHALL be taken from gateway metering rather than self-reported (FR78–FR80).
- Prompt-caching savings SHALL be reported as a measured secondary lever and SHALL NOT be attributed to OutcomeFuse.
- Case-construction rules SHALL be published so the synthetic case set can be inspected rather than trusted.

### 8.4 Claim discipline

- No claim of measured generalization SHALL be made beyond the workloads actually completed.
- Shadow-mode figures SHALL be labeled projected, never realized (FR49), and SHALL disclose the first divergence past which they are inference rather than observation (FR96).
- Where metering falls back to governor-side counting, the figure SHALL be labeled self-reported (FR80).
- A pass resting wholly or partly on `constraint-backed` verification SHALL be labeled as such, never as `reference-backed` (FR21).
- Targets and thresholds SHALL be recorded before any evaluation-set result is executed or inspected (FR66, FR102).
- These obligations apply to the submission artifact exactly as they apply to a written report (FR82, FR83).

### 8.5 Calibration set and evaluation set

Two case sets, with different jobs and different rules. Conflating them is what would otherwise let the governor be tuned against the data it is judged on.

**Calibration set.** A calibration case set MAY be used to measure governor overhead, determine break-even behaviour, exercise failure paths, and establish the preregistered targets and counter-metric thresholds required by FR66. **Calibration-set results SHALL NOT contribute to any headline benchmark figure or to the submission.**

**Evaluation set.** A separate frozen evaluation case set SHALL be held sealed: **no governed result SHALL be executed against it or inspected** until savings targets, counter-metric thresholds, minimum case counts and blind-review sample sizes have been preregistered. The case definitions are of course authored and known — it is the *results* that must remain unseen. **Only evaluation-set results MAY support a headline OutcomeFuse claim** (FR102).

The split is what makes §3.1's two obligations compatible rather than contradictory. Targets are *derived* from measured overhead on calibration data, and *tested* against evaluation data that was sealed while they were being written. Neither is possible alone: derive targets on the evaluation set and they are fitted; set them without measuring overhead and they are guesses.

---

## 9. Responsible AI & Governance

- **Quality floor outranks budget.** Optimization SHALL NOT accept a cheaper failing answer under any circumstance (FR11, FR24, FR25).
- **No silent quality substitution.** Model escalation, compression, cache reuse and evaluator decisions SHALL be disclosed in the decision record, never silent (FR35, FR42, FR53).
- **Human control is enforced, and bounded.** Where the contract declares human-approval conditions, the runtime **SHALL** pause and obtain approval before proceeding (FR34). The pause is bounded by `approval_timeout`; on expiry the contract's `on_timeout` applies, defaulting to terminate without making the gated call (FR95). **That is distinct from the approval channel being unavailable**, which is a fail-closed condition (FR89) and outranks the approval gate in FR2's ladder — a timeout is not an outage, and conflating them would change both the terminal reason and what the caller receives. Either way a governance gate cannot become an unbounded outage. The Quality Gate SHALL escalate to a person when it cannot reach the floor safely. What OutcomeFuse removes is the *manual optimization* cycle — not the human.
- **The floor is never starved to save money.** The marginal-value estimator governs enrichment only; it may not deny a step needed to reach an unmet mandatory criterion (FR17). Where the floor cannot be reached affordably, the system stops and says so rather than looping (FR93).
- **Transparency.** The record SHALL state why every call was blocked, cached, compressed or escalated (FR53, FR55).
- **Fidelity of compression.** Compression SHALL NOT drop an attributable fact (FR38), and that obligation SHALL be measured rather than asserted (FR71). A saving obtained by losing a citation is a defect.
- **Soundness of denial.** Tool suppression is measured mechanically, not assumed correct and not judged by a model (FR70); marginal-value denials are measured separately (FR99). Denying the right call for the wrong reason is a quality failure even when the output passes.
- **Honesty about the gate's limits.** Where the gate cannot verify correctness it SHALL say so rather than imply it did (FR21, §8.2a).
- **Privacy and isolation.** Per NFR5, NFR6, NFR7 and NFR12.
- **Preview-stage honesty.** Where a dependency is preview-stage, a stable fallback SHALL be pinned and the dependency's status stated plainly, rather than demonstrating on unstable ground.

---

## 10. Governor Failure & Degradation

The governor sits in front of someone else's working agent. Its own failure modes are therefore a first-class concern, and the posture is asymmetric by design.

### 10.1 Fail-open — optimization mechanisms

On failure of the Context Governor, Model Governor, Preflight Planner, tool cache or gateway metering, the system SHALL degrade to ungoverned-but-correct execution rather than blocking the host agent.

- **FR85.** Failure of an optimization mechanism SHALL NOT halt the run. Execution SHALL continue without that mechanism.
- **FR86.** Any run that executed with a degraded mechanism SHALL be marked degraded in its result, and its savings figures SHALL be labeled accordingly.

### 10.2 Fail-closed — the Quality Gate, the budget ceiling, and human approval

On failure of quality evaluation, loss of ledger state, or unavailability of the approval channel, the system SHALL NOT proceed as though unconstrained.

- **FR87.** If the Quality Gate cannot produce a verdict, the system SHALL NOT report a pass. It SHALL halt and escalate per the contract, or request human intervention.
- **FR88.** If ledger state is lost or becomes unreliable, the system SHALL halt rather than continue spending against an unknown budget.
- **FR89.** If a human-approval condition cannot be evaluated or the approval channel is unavailable, the system SHALL NOT proceed with the gated call.
- **FR90.** A fail-closed halt SHALL carry terminal reason **`fail-closed`**, recorded and reported as distinct from `stop-sufficient` (FR23), `halt-no-progress` (FR27) and `halt-exhausted` (FR92), per FR28.

**The asymmetry stated plainly:** losing an optimization costs money; losing the gate costs correctness. Only one of those is allowed to fail quietly.

### 10.3 Shadow mode is exempt from fail-closed

- **FR91.** In shadow mode the system SHALL NOT halt, pause or otherwise alter the host agent under any condition, including the fail-closed conditions in §10.2. It SHALL record the halt it would have imposed and allow execution to continue.

> Shadow mode's entire proposition (UJ-1) is that it cannot hurt you. A governor that halts a production agent it promised only to observe would destroy the adoption path the PRD depends on.

---

## 11. Open Questions & Risks

### 11.1 Open questions

| # | Question | Why it matters | Status |
|---|---|---|---|
| Q1 | At what task length does the governor stop paying for itself? | Determines whether the product works on short tasks at all | Answered by FR67; not blocking the build |
| Q2 | Who authors the quality floor in a real deployment, and at what effort per task type? | The main adoption friction and the main threat to the scale story | Deferred. Not blocking the MVP (contracts hand-written); blocking the product story. Revisit after the agent-owner interviews |
| Q3 | Can a default contract be inferred for common task shapes? | Would remove hand-authoring entirely | Out of scope; parked |
| Q4 | What sample size per workload establishes false-sufficiency rate credibly? | The counter-metric that makes the headline falsifiable | Protocol resolved (FR69). **Sample size N unset** — fix and record before any governed evaluation-set result is executed or inspected (FR66, FR102) |
| Q5 | Does the side-by-side view stream live runs or replay recorded ones? | Materially changes F14 build cost | **Resolved** — replay of recorded runs (F14) |
| Q6 | What is the minimum case count per workload? | Below it, a savings or quality claim is not reportable (FR59) | **Unset** — fix and record before any governed evaluation-set result is executed or inspected (FR66, FR102) |
| Q7 | Is unmet-criterion targeting a good enough marginal-value estimator? | It is the MVP mechanism for FR17, and FR17 carries the differentiation | **Mechanism specified, quality unknown.** Every denial it makes is reported with its FR17 compliance by FR99; FR70 covers tool suppression only and does not validate marginal-value decisions. If the estimator performs poorly it is pluggable and can be replaced without touching the policy. Its floor-protection carve-out (FR17) is not pluggable |
| Q8 | What thresholds apply to the counter-metrics in §3.3? | Without thresholds the counter-metrics cannot fail, and the headline cannot be falsified | **Unset** — fix and record before any governed evaluation-set result is executed or inspected (FR66, FR102) |
| Q9 | How does a production deployment establish ground truth without hand-authored answer keys? | The deterministic gate's authority depends on it (§8.2a) | **Open, and out of MVP scope.** The MVP is honest about the limit rather than solving it |

> `[NOTE FOR PM]` Q4, Q6 and Q8 share a bias problem the PRD cannot design away: the blind reviewer is the same person who wrote the rubric and built the optimizer. Blinding the verdict and the configuration (FR69) reduces it; freezing the rubric by hash (FR65) reduces it further; sealing the evaluation set until every number is recorded (FR66, FR102) is what stops the remainder. None of that removes the conflict — it makes cheating visible in the record.

### 11.2 Risks

| Risk | Why it matters | Position |
|---|---|---|
| **Governor overhead unmeasured** | If evaluator, planner and compression consume a large share of the baseline, net savings could fall far below gross — and on short tasks the governor may cost more than it saves | Overhead instrumented from run one; net targets restated only after measurement (§3.1) |
| **Rubric circularity** | The same person writes the rubric and the optimizer that must satisfy it | Rubric and answer keys frozen, versioned and content-hashed before governor work; harness refuses to publish on drift (FR65); deterministic criterion-level validation preferred over model judgement wherever the criterion is checkable (§8.2) |
| **Baseline fairness** | The baseline is defined by the party who benefits from it losing | Freeze, version and publish the definition; harness refuses drifted comparisons (FR64). The baseline keeps a real evaluator loop, and §8.1 states what it does and does not check |
| **Ground-truth dependency** | The gate is authoritative only because the answer keys are synthetic; on production data mandatory criteria collapse toward `constraint-backed` verification | Stated openly (§8.2a); every mandatory criterion must declare an executable verifier and its mode (FR8); constraint-backed passes are labeled as such (FR21). Q9 remains open |
| **Attribution** | Total savings could be almost entirely tool caching while the sufficiency claim carries the narrative | Per-mechanism ablation required before any headline is publishable (FR62) |
| **Synthetic data** | Every savings figure derives from cases the builder authored | State it plainly; publish case-construction rules; partially offset by gateway-measured tokens |
| **Differentiation challenge** | In-loop routers and cascades already make quality-conditioned spend decisions; a reviewer may say this already exists | The distinction is per-call escalation versus per-run cumulative sufficiency against a declared, measured contract. FR17 must be built and FR62 must show it contributed, or the distinction is rhetorical |
| **Judge-reliability attack** | "You moved the unreliability into the evaluator, you did not remove it" | Deterministic criterion-level validation is the authoritative gate; the model rubric is advisory only (FR20). This is the strongest reason to keep FR20 as written — and §8.2a is the honest limit of the defence |
| **Persona evidence** | The primary user was selected from judgment, not research | Two to three agent-owner interviews in scope; the persona and all four journeys labeled assumed until then |
| **Schedule** | The source memo assumed a team across six workstreams and recommended capping the MVP at four mechanisms. This PRD commits a solo builder to seven mechanisms, four workloads, a harness, a replay UI and a submission artifact | **Material, and accepted deliberately.** The mitigation is the declared cut order (§4.3) plus NFR10, which makes the cuts mechanically executable rather than aspirational, and a protected core close to the memo's recommended scope. If the cut order is exercised the claims narrow with it and §8.4 applies unchanged |
| **Scope discipline** | Slack in the schedule invites an eighth mechanism instead of stronger evidence | Slack goes to evidence — more cases, repeated runs, overhead baseline, interviews. Anything further must displace planned work |
| **Cut-order honesty** | The cut order makes three of seven mechanisms sacrificial | Demo narrative and external claims must not imply seven equally load-bearing components (§4.3) |

---

## 12. Vision

> Non-normative. This section generates no requirements. It exists so the MVP's choices can be read against the thing they are a first step toward.

If this works, declaring an Outcome Contract becomes as ordinary as declaring a timeout. Any agent, in any framework, states what "good enough" means and what it may spend getting there, and the runtime handles the rest.

The near-term shape is middleware a team can wrap around an existing agent in an afternoon. Beyond that: contracts become reusable policy artifacts owned by platform teams rather than hand-written per task; the marginal-value policy learns from historical runs instead of relying on fixed heuristics; and cost-per-verified-outcome becomes a first-class CI gate, so an agent version that gets more expensive without getting better simply does not ship.

The longer-term change is in how enterprises govern AI spend at all. Today the lever is restriction — quotas, caps and approval gates that slow teams down to save money. **OutcomeFuse replaces restriction with sufficiency: unlimited ambition, bounded waste.** Spend whatever the outcome is worth, and nothing on work that was already done.

---

## Appendix A — Glossary

| Term | Meaning |
|---|---|
| **Outcome Contract** | The declarative artifact stating what "done" means before execution begins — deliverable, mandatory and optional criteria with their verifiers, quality floor, ceilings, verification reserve, permitted tools, escalation, approval conditions and approval timeout |
| **Mandatory criterion** | A criterion or evidence field the contract declares as constituting the quality floor. Must carry an executable deterministic verifier (FR8). Only mandatory criteria affect the gate verdict |
| **Optional / enrichment** | A criterion, field or tool call the contract declares as desirable but not floor-constituting. The only category FR17 and FR31 may suppress |
| **Advisory criterion** | Something that matters but cannot be deterministically verified. Recorded and fed to counter-metrics; never gating (FR8, FR22) |
| **`reference-backed`** | Verification against a known-correct value. The strong mode |
| **`constraint-backed`** | Verification for presence, type and constraint only. The weaker mode; any pass touching it is labeled accordingly (FR21) |
| **Quality floor** | The set of mandatory criteria that must be met. Never relaxed by any runtime path (FR11), never starved by the marginal-value estimator (FR17) |
| **Sufficiency** | The state in which every mandatory criterion is met. Distinct from exhaustion, and from the agent's own belief that it is finished |
| **`policy_action`** | What the runtime does next: `proceed`, `proceed-with-substitution`, `deny`, `pause-for-approval`, `escalate`, `request-human`, `return-partial`, `terminate`. Recorded on every decision (FR1) |
| **`decision_reason`** | Why an action was taken. A stable code from a versioned, extensible registry with declared families (FR104). Recorded on every decision |
| **`terminal_reason`** | Why the run *ended* — the cause, never the disposition (FR103). One of `stop-sufficient`, `halt-exhausted`, `halt-no-progress`, `approval-timeout`, `fail-closed`, `referred-human`, `returned-partial`. Recorded only where the action terminates the run |
| **`quality_state`** | Run-level state: `not-evaluated` until the gate first runs, then `pass` or `fail` (FR105). The absence of a verdict, not a third verdict |
| **Gate verdict** | Exactly `pass` or `fail` (FR94), qualified `reference-backed` or `constraint-backed` (FR21). There is no intermediate verdict |
| **Verification reserve** | Budget held back for final synthesis and Quality Gate execution. Declared or deterministically derived, recalculated before escalation, and never spendable by earlier steps (FR14, FR101) |
| **Evidence capsule** | Compressed, structured tool output that preserves citations, identifiers, figures, policy clauses and contract-required attributable facts verbatim (FR37, FR38, FR71) |
| **Governor overhead** | Spend consumed by the governor itself — evaluation, planning, compression passes, and every Quality Gate execution. Always reported separately (FR15, FR61, FR98) |
| **Net savings** | Savings inclusive of governor overhead. The only figure this PRD permits as a headline |
| **Calibration set** | Cases used to measure overhead, find break-even, exercise failure paths and set targets. Never contributes to a headline figure (§8.5, FR102) |
| **Evaluation set** | Frozen cases held sealed until targets are preregistered. The only source of headline claims (§8.5, FR102) |
| **False sufficiency** | A run the gate passed that blind human review fails. The counter-metric to the headline claim |
| **Shadow mode** | The governor observing and logging without enforcing. The ungoverned path is executed and observed; the governed path is an estimated counterfactual (FR48). Exercised on synthetic and replayed workloads in the MVP (FR106) |
| **First divergence** | The earliest decision at which the governed counterfactual departs from the observed path. Everything after it is inference (FR96) |
| **Proof card** | The recorded comparison artifact computed by the harness (FR97) and rendered by the view. Computation belongs to F13; F14 only displays it |
| **Protected core** | Requirements that survive every cut. Enumerated in §4.3 |

---

## Appendix B — Requirement Index

One hundred and nine functional requirements (FR1–FR109) across sixteen features plus the failure-posture requirements in §10, and twelve non-functional requirements.

> **FR identifiers are stable.** FR92–FR109 were added across five review passes and are placed within the feature they belong to rather than appended at the end, so several feature ranges are non-contiguous. Identifiers are never reused or renumbered, because review findings and downstream artifacts cite them.

| Feature | FRs | Cut status |
|---|---|---|
| F1 Runtime Decision Policy | FR1–FR6, FR103, FR104 | Protected — FR1 the action / reason / terminal-reason model, FR2 the precedence ladder, FR103 the terminal-state mapping, FR104 the reason registry |
| F2 Outcome Contract | FR7–FR12, FR108 | Protected — FR108 gates verifier breadth before the freeze |
| F3 Budget Ledger | FR13–FR18, FR92, FR93, FR101 | Protected — FR17 carries the marginal-value decision and its floor-protection carve-out |
| F4 Quality Gate | FR19–FR26, FR94, FR98, FR105 | Protected — rubric signal in FR20 and advisory tool quality in FR22 are cuttable |
| F5 Loop Fuse | FR27–FR28 | Protected |
| F6 Tool Governor | FR29–FR35, FR95 | Protected — FR32 cuttable; FR34 and FR95 are governance requirements |
| F7 Context Governor | FR36–FR39 | Cut position 7 |
| F8 Model Governor | FR40–FR42 | Cut position 6 |
| F9 Preflight Planner | FR43–FR45 | Cut position 8 — owns no classification the protected core depends on |
| F10 Shadow Mode | FR46–FR49, FR96, FR106, FR109 | **Protected** — the adoption path; MVP evidence is synthetic and replayed only, and FR109 refuses anything else |
| F11 Integration Surface | FR50–FR52, FR107 | Protected — FR52 required for the benchmark; the *third* adapter is cut position 2 |
| F12 Decision Record | FR53–FR56 | **Protected** — FR5 makes it load-bearing |
| F13 Benchmark Harness | FR57–FR71, FR97, FR99, FR100, FR102 | Protected |
| F14 Side-by-Side View | FR72–FR77 | Cut position 1 — renders only; owns no computation |
| F15 Gateway Metering | FR78–FR80 | Cut position 10 |
| F16 Submission Artifact | FR81–FR84 | **Protected** — depends on F13 and F12, never on F14 |
| §10 Failure posture | FR85–FR91 | Protected |

### Requirements that guard the claims

These exist so that no headline figure can be reported without the evidence that would refute it.

| Claim | The requirement that can falsify it |
|---|---|
| Net savings | FR61 overhead line item, FR62 per-mechanism ablation |
| We stop when it is good enough | FR69 blind human review → false-sufficiency rate |
| Fewer tool calls | FR70 tool-suppression accuracy |
| Compression loses nothing | FR71 compression fidelity |
| The comparison is fair | FR64 baseline freeze, FR65 rubric freeze |
| The target was met | FR66 pre-registration |
| Quality was not degraded | FR21 verification-mode labeling, FR22 deterministic tool-use conformance, FR94 binary verdict |
| The marginal-value policy never starved the floor | FR99 every denial reported, with FR17 compliance |
| The failure paths behave as specified | FR100 synthetic cases per failure and terminal behaviour |
| The host actually obeyed the governor | FR107 adapter conformance battery, with its out-of-band side-effect probe |
| The quality floor is substantive, not structural | FR65 per-workload reference-backed vs constraint-backed counts; FR108 pre-freeze criterion classification |
| The targets were not fitted to the results | FR102 sealed evaluation set, FR66 preregistration |
| The governor stopped it, not the budget | FR92 `halt-exhausted` recorded separately from the loop fuse and the sufficiency stop |
| Shadow mode predicted the saving | FR96 first-divergence marker — the point past which the estimate is inference |
