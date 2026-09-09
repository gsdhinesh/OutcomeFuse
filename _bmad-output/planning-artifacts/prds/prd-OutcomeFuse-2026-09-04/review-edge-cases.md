---
title: "Edge-Case Review: PRD OutcomeFuse"
artifact: prd.md
reviewer: edge-case lens
date: 2026-09-04
scope: "§5 (FR1–FR78), §7 (NFR1–NFR12), §10 (FR79–FR84)"
---

# Edge-Case Review — PRD: OutcomeFuse

**Verdict.** The requirement set is unusually disciplined about *evidence* and unusually loose about *control flow*. The failure mode is not a missing feature — it is that four independently-worded absolute `SHALL`s can fire on the same step with no precedence rule, and that the audit trail every other requirement depends on is marked cuttable. Two findings are blocking; six are material.

Severity key: **BLOCKING** (PRD cannot be built from as-written) · **HIGH** (will produce a defect or an indefensible claim) · **MEDIUM** (ambiguity that will be resolved arbitrarily at build time) · **LOW** (tighten before freeze).

---

## Part 1 — Direct contradictions

### 1.1 FR4 vs the Appendix cut status of F12 — **BLOCKING**

FR4: *"Every decision SHALL be recorded per F12 before it takes effect."*
Appendix: `F12 Decision Record | FR51–FR54 | **Conditional**`.
§4.3 protected core: Outcome Contract · Budget Ledger · deterministic Quality Gate · duplicate-tool protection · loop protection · early-stop decision · reproducible OFF/ON benchmark · F16. **F12 is not in it.**

If F12 is cut, FR4 is unsatisfiable and therefore *no decision may take effect* — the runtime cannot legally execute a single step. Cutting F12 also voids FR2 (cite the clause), FR33, FR40, FR51–FR54, FR5/NFR3 (replay from recorded decision state), the whole of §9 Transparency, and UJ-3 in its entirety. F12 is load-bearing for the compliance persona (§2.3) who is one of three named stakeholders.

The same defect, less severely, applies to **F10 Shadow Mode**, also marked `Conditional`, while §4.1 calls it a measurement instrument and UJ-1 is the entire adoption narrative. Neither F10 nor F12 appears anywhere in the §4.3 cut order or in NFR10's disableability list — so "Conditional" is a label with no defined semantics.

**Resolution.** Move F12 (at minimum FR51–FR53) into the §4.3 protected core and change its Appendix status to Protected. Either place F10 in the cut order at an explicit position or relabel it Protected. Delete the word "Conditional" from the Appendix wherever it does not correspond to a numbered cut-order position — an unpositioned "Conditional" is exactly the arbitrary cut §4.3 exists to prevent.

### 1.2 FR29/FR30 vs FR31 — **BLOCKING**

FR31: *"The system SHALL NOT cache, deduplicate or **deny** calls to tools declared side-effecting or non-deterministic."* Absolute.
FR29: *"SHALL deny optional calls once the contract's required evidence is satisfied."* Absolute.

An **optional call to a side-effecting tool after required evidence is satisfied** is commanded and forbidden by two protected-core requirements. This is not hypothetical — supply-chain exception investigation (a committed workload) is full of optional side-effecting calls.

The same collision recurs three more times:
- **FR14 vs FR31** — an unaffordable side-effecting call: FR14 says reject, FR31 says never deny.
- **FR15 vs FR31** — a low-marginal-value or *unsafe* side-effecting call: FR15 explicitly says reject unsafe steps; FR31 says never deny.
- **FR83 vs FR31** — approval channel unavailable, so the gated call (almost always a side-effecting one — that is why it is gated) SHALL not proceed. That is a denial of a side-effecting tool.

**Resolution.** FR31 is trying to say *optimization must never suppress a side effect*. Rewrite it to that scope: "No **optimization-driven** suppression — caching (FR28), deduplication (FR29–FR30) or marginal-value denial (FR15) — SHALL apply to tools declared side-effecting or non-deterministic. This does not limit denial on affordability (FR14), safety, contract-policy or approval grounds (FR32, FR83), which SHALL remain available for all tools." Then FR29's optional-call clause must carry the same carve-out.

### 1.3 FR18 vs FR19 — **HIGH**

FR18 makes deterministic field validation *authoritative* and constrains the model rubric in one direction only (it may not override a **failure**, and may not **alone** establish a pass). FR19 then introduces a second veto over a deterministic pass: *"A result that reached its fields through unsound tool use SHALL NOT be recorded as a clean pass."*

Three unresolved questions: (a) "authoritative" plainly implies a deterministic pass is a pass — FR19 says otherwise; (b) **"clean pass" is defined nowhere** — is a non-clean pass still a pass for FR20's stop trigger, for FR22's returned verdict, and for the §3.1 task-completion metric? (c) FR19's substance ("were the tools called the right ones") is a judgment, and §4.3 cut item 7 removes model-based evaluation — cutting the rubric guts a protected-core requirement.

**Resolution.** Define a three-valued verdict in FR17: `pass` / `pass-with-tool-use-concern` / `fail`, and state explicitly which values trigger FR20. Split FR19 into its deterministically checkable subset — denied-call correctness, whether a tool result appears in the deliverable, whether a permitted-tool list was respected — which survives the rubric cut, and its model-judged subset, which inherits FR18's advisory-only rule.

### 1.4 FR20 vs FR32 — **HIGH**

FR20: on pass, *stop immediately; no further billable work.* FR32: on an approval condition, *execution SHALL pause and SHALL NOT proceed until approval is granted.*

Uncovered: the gate passes while a call sits pending approval. Is the pending approval withdrawn? If approval arrives *after* the sufficiency stop, is the call executed (FR32 says do not proceed until granted — it does not say execute once granted, but a real implementation will)? Is executing it "further billable work" prohibited by FR20? Does FR20's stop discard a side effect a human explicitly authorised — a governance-visible act with no requirement covering it?

**Resolution.** State that `stop-sufficient` pre-empts pending approvals; the approval request SHALL be cancelled and recorded as `approval-cancelled-by-sufficiency`; a grant returning after a stop SHALL NOT cause execution. Record it — a human authorising something that then never happened must be visible to FR51.

### 1.5 FR15 vs FR20 and vs FR9 — **HIGH**

FR15 lets the ledger reject a step on marginal-value grounds. FR20 stops only on a gate pass. Nothing covers the state in between: **the gate has failed, budget remains, and every proposed step is rejected by FR15 as low-value.** The run does not stop-sufficient, has not exhausted budget (so FR14 and FR25's exhaustion trigger are silent), and may not register as "no new evidence" if rejected proposals do not count as iterations. That is a livelock in the protected core.

Worse, it is a principle violation. §1.5 principle 1 and FR9 say the floor outranks the budget *always* and no runtime path may relax it. A cost-side mechanism declining further work while a **required** evidence field is unmet is precisely a budget consideration relaxing the floor.

**Resolution.** Add to FR15: "FR15 SHALL NOT deny a step that targets an unmet required evidence field. Marginal-value denial applies only to optional/enrichment steps as classified under FR42." And add a terminal rule: where every affordable proposed step is denied and the floor is unmet, the policy SHALL emit `request-human`, never continue silently. Note that FR15's dependence on FR42 makes it dependent on **F9 Preflight Planner**, which is in the cut order — see §5.2 below.

### 1.6 FR47 vs FR46 and §4.1 — **HIGH**

FR47 forbids presenting shadow figures as realized savings; §8.4 says shadow figures are labeled *projected, never realized*. But §4.1 states shadow mode is "in the MVP … a measurement instrument," and FR46 says it *captures* governed and ungoverned paths from a single execution "so measurement does not require two separate runs."

These cannot both stand. If shadow output is projection-only, it cannot source any §3.1 primary metric, and FR46's stated efficiency benefit for measurement evaporates — §3.1 and FR55 require an actual baseline-vs-governed execution pair anyway.

**Resolution.** Add to FR47: "Shadow-mode output SHALL NOT be an admissible source for any primary metric in §3.1." Amend §4.1 to describe shadow mode as an *adoption* instrument producing a secondary projected estimate. See also §4.4 below for why FR46 is not achievable as worded.

### 1.7 FR71 vs FR69 — **MEDIUM**

FR71 says the view is read-only and "SHALL consume only recorded output." FR69 requires it to present a proof card of net tokens, cost and tool calls **"with the quality verdict held constant."** Holding the verdict constant is a *case-pairing and filtering rule* — an analytical operation over the case set, not a replay of recorded output. FR69 therefore quietly makes F14 an analysis component, contradicting FR71 and the F14 preamble's cost rationale.

**Resolution.** Move net-figure computation and the verdict-held-constant pairing rule into **FR59** (harness). Restate FR69 as: the view SHALL render the harness-produced proof-card artifact. This satisfies FR71 literally and survives the F14 cut (see §5.3).

### 1.8 FR79 vs FR80 vs FR59 — **MEDIUM**

FR79 fail-opens *any* optimization mechanism failure. But FR79 does not distinguish **unavailability** (mechanism absent — safe to skip, genuinely "ungoverned-but-correct") from **faulted output** (mechanism ran and returned something wrong). A Context Governor that silently drops an attributable fact violates FR36 and yields *governed-and-incorrect* execution, which FR79's own framing claims to prevent. Marking the run degraded (FR80) does not repair a corrupted context that the model then reasoned over.

Separately, nothing states whether degraded runs (FR80) are **admissible in §3.1 metric computation**. FR57 and FR61 both give the harness explicit refusal rules; there is no analogous rule here, so degraded runs will silently enter the means that FR56 requires.

**Resolution.** Split FR79: unavailability fail-opens and skips; a faulted-output condition in F7 SHALL discard the capsule and fall back to the unsummarised source, or halt if that source is no longer retained. Add to FR59: degraded runs SHALL be reported as a separate stratum and SHALL NOT be pooled into headline figures.

---

## Part 2 — Uncovered states

Walking the run lifecycle: contract load → validation → plan → step decision → tool call → compression → gate → stop/retry/escalate → finalize.

### 2.1 Approval pause has no time bound — **HIGH**

FR32 pauses indefinitely. FR83 covers a channel that is *unavailable*; it does not cover a reachable channel with no responder — the common case. Consequences with no covering requirement:

- **Budget exhausting during a pause.** Nothing spends during a wait, but the *estimated cost* ceiling may be time-based, model versions may roll, and cached results (FR28, "within the scope of a single run") age arbitrarily.
- **Reserve held indefinitely** (FR12) with no release or expiry rule.
- **Terminal state of an abandoned run.** §3.1's budget-compliance metric demands 100% of runs terminate cleanly — a run parked forever on an unanswered approval terminates in no category at all, and would silently drop out of the denominator.

**Resolution.** Extend FR6's `human_approval_conditions` to carry a required timeout and a declared on-timeout posture, defaulting to fail-closed per FR83. Add a terminal state `abandoned-awaiting-approval` and state its treatment in §3.1.

### 2.2 Shadow mode combined with a fail-closed condition — **HIGH**

FR44: in shadow the governor "decides nothing, enforces nothing." FR81–FR83 are unconditional `SHALL halt` requirements. Directly opposed, and the resolution matters enormously: if fail-closed fires in shadow, **the governor halts a production agent it promised not to touch** — the precise outcome §10's opening paragraph disclaims and the reason Priya (UJ-1) agreed to install it. If it does not fire, FR45 still requires a record "of the same shape," so the record must contain a would-have-halted decision that never happened.

There is a second-order case: **FR82 (ledger state lost) during a shadow run.** Every shadow estimate is derived from ledger arithmetic, so a lost ledger invalidates the run's projections — but FR80's degraded-marking applies only to fail-open mechanisms, so nothing marks it.

**Resolution.** Add: "In shadow mode, FR81–FR83 SHALL record the fail-closed decision that would have been taken and SHALL NOT halt host execution. A shadow run in which FR82 obtains SHALL be marked unusable for measurement and excluded from any reported figure."

### 2.3 FR7 warns but does not reject — **MEDIUM**

FR7 rejects malformed contracts but only *warns* on well-formed-but-unsatisfiable ones. Nothing says what happens next. The run proceeds, cannot reach the floor within the ceiling, and lands on FR21 — exceed the ceiling and request a human. So a *predicted* breach silently inflates the **budget-breach counter-metric** in §3.3, which the PRD treats as a design-honesty signal. A contaminated counter-metric is worse than an absent one.

**Resolution.** Require an explicit acknowledgement field in the contract to execute past an FR7 warning, and state that runs launched on a warned contract are stratified separately in the budget-breach rate.

### 2.4 Cached result that later proves stale — **MEDIUM**

FR28 caches results for tools *declared* deterministic, run-scoped. Two gaps:

- **Cross-tool invalidation.** A side-effecting write executed later in the run (protected from suppression by FR31) can invalidate a cached read from earlier. Nothing invalidates it. The agent then reasons over a value it just changed. FR27's canonical key is per-tool and cannot detect this.
- **Misdeclaration.** A tool declared deterministic that is not. FR31 protects correctly-declared tools; nothing detects or bounds the mis-declared case, and FR65's suppression-accuracy measurement would surface it only after the fact, in aggregate.

**Resolution.** Extend FR6 so tools declare a read/write resource scope, and add: any successful side-effecting call SHALL invalidate cached entries for tools declaring an overlapping read scope. Add a note that FR65 is the detection mechanism for misdeclaration and that a misdeclaration finding invalidates the run.

### 2.5 The reserve being insufficient for verification — **MEDIUM**

FR12 requires a reserve "sufficient for final synthesis and quality verification" but never says how it is **sized**, and never says it is **resized**. FR39 escalates to a more capable model; verification on that model costs more than the reserve was sized for. UJ-2 walks Marcus to exactly this boundary and stops one step short of it. If the reserve underruns mid-verification, the run lands on FR81 (no verdict → halt and escalate/request human) — the worst outcome available: full spend, no verdict, human called anyway.

**Resolution.** Require the reserve to be recomputed whenever the eligible model set changes (FR39), and require FR14 to reject an escalation that would leave the reserve underfunded, routing to `request-human` *before* escalating rather than after.

### 2.6 Gate passes on iteration zero, before any tool call — **MEDIUM**

FR20 fires and the run stops. Unaddressed: **FR19 has no defined verdict for zero tool calls** — vacuously sound, or unsound because required evidence was asserted without being gathered? A contract whose required evidence fields are satisfiable from the prompt alone is the strongest available false-sufficiency signal, and FR64 samples passed runs at random, so it may never be reviewed. It also produces a savings outlier that dominates any mean FR56 computes.

**Resolution.** Define FR19's zero-tool-call verdict explicitly (recommend: not a clean pass). Require FR58 to flag zero-tool-call passes and FR64 to review them exhaustively rather than by sample.

### 2.7 Parallel or batched tool calls — **MEDIUM**

FR1 governs "each unit of work"; FR27–FR29 assume a completed prior call exists to deduplicate against. Real tool loops — including the codebase-triage and SQL workloads in §4.1 — batch calls within one model turn. Two identical calls in the same batch are each not a duplicate *of a completed call* at decision time, so FR29 does not fire, and FR32's pause semantics for a batch containing one gated call are undefined (pause the batch, or the call?).

**Resolution.** Either scope the MVP explicitly to sequential loops in FR48, or add in-flight-key deduplication to FR27 and state that FR32 pauses the entire batch.

### 2.8 OFF state has no record writer — **LOW**

FR50 requires an OFF state with "no governor participation," while FR47 requires run mode "recorded in every result." With the governor absent, no component is assigned to write the baseline result record. FR58 (harness capture) is presumably the answer.

**Resolution.** One clause in FR50 stating the harness, not the governor, records OFF-state results.

---

## Part 3 — Ordering ambiguity

### 3.1 No precedence rule among the terminal and blocking conditions — **HIGH**

Construct a single iteration in which all of the following hold simultaneously — none is exotic:

| Condition | Requirement | Demanded outcome |
|---|---|---|
| Gate passes | FR20 | stop immediately, `stop-sufficient` |
| Progress fingerprint repeated | FR25 | halt, no-progress |
| Next step unaffordable | FR14 | deny |
| Next step low marginal value | FR15 | deny |
| Queued call meets approval condition | FR32 | pause |
| Gate produced no verdict / ledger unreliable | FR81, FR82 | halt, fail-closed |

FR1 requires *exactly one* decision. The PRD never says which wins. And the label is not cosmetic: **FR26 and FR84 make these distinctions normative** ("SHALL NOT be conflated in any result, report or interface"), §1.5 principle 4 elevates it to a design principle, and §3.1's budget-compliance metric scores the categories differently. An arbitrary implementation choice here directly moves a headline number.

**Resolution.** Add an explicit precedence ladder to F1:

1. Fail-closed halts (FR81–FR83) — integrity of the verdict and ledger outranks everything.
2. `stop-sufficient` (FR20) — a passed gate moots budget and loop conditions, since nothing further is billable.
3. Approval pause (FR32) — blocks a call, not the run; re-enter the ladder on resolution.
4. Budget/value rejection (FR14, FR15) — denies a step; the run continues.
5. Loop-fuse halt (FR25) — terminal only when no step is proposable.

### 3.2 FR25 conflates exhaustion with lack of progress — **HIGH**

FR25 lists **"budget exhaustion"** among the Loop Fuse's halt conditions. FR26 then distinguishes only two things: a no-progress halt and a sufficiency stop. Exhaustion is neither — it is a third terminal state, it is FR14's domain, and folding it into the loop fuse means an exhausted run is reported as *stuck*. §1.5 principle 4 exists to forbid exactly this class of conflation, and §3.1's budget-compliance metric and §3.3's escalation rate both read the label.

**Resolution.** Remove budget exhaustion from FR25. Add a fourth distinct terminal state, `halt-exhausted`, owned by F3, and extend FR26/FR84 to a four-way distinction: sufficiency stop · no-progress halt · exhaustion halt · fail-closed halt.

### 3.3 Is the gate evaluated during a pause or after a denial? — **MEDIUM**

FR17 evaluates "the current result." Nothing states the gate's *trigger cadence*. After an FR14/FR15 denial, is the gate re-run against the result as it stands? It should be — the denied step may have been unnecessary precisely because the floor is already met, which is the product's central claim. But as written, a run can deny its way to a loop-fuse halt while a passing result sits unevaluated, and be reported as *stuck* when it was *done*.

**Resolution.** State in FR17 that the gate SHALL be evaluated after every completed unit of work **and** before any terminal halt other than a fail-closed one.

---

## Part 4 — Unimplementable as written

### 4.1 FR5 replayability vs FR39, FR15, FR30, FR18 — **HIGH**

FR5 defines replay inputs as exactly three: recorded contract, ledger state, quality verdict. But:

- **FR39** escalates on "task complexity" and "low model confidence" — model-derived, non-deterministic, and in neither of the three.
- **FR15** denies on estimated expected benefit — same problem.
- **FR30** denies on semantic equivalence — an embedding or model judgment.
- **FR18's** rubric signal — same.

So the four decisions an auditor most wants to replay are the four FR5 cannot reproduce. This directly defeats **FR53** ("sufficient to reconstruct why a run stopped … *without access to the underlying model*") and **NFR3**, and it is what Dana is checking for in UJ-3.

**Resolution.** Amend FR5 to "given the same **recorded decision inputs**," and amend FR51 to require every model-derived input to be recorded **as a value** — confidence score, complexity estimate, marginal-value estimate, semantic-similarity score and threshold — not merely summarised in the prose `reason` field. Without stored scalars, FR53 is unachievable by construction.

### 4.2 FR15 assumes information not available when it applies — **HIGH**

Expected benefit of a step is not knowable before the step runs; Q7 concedes the estimator is unspecified. Three consequences:

- FR15 is a protected-core `SHALL` with **no specified mechanism**, and §11.2 states plainly that if FR15 is not built the §1.3 differentiation "is rhetorical."
- **FR2** requires every decision to cite *the contract clause* it rests on. An FR15 denial rests on a heuristic that exists nowhere in the contract — there is no clause to cite. FR2 and FR15 cannot both be satisfied under FR6 as currently specified.
- **FR8** makes the contract immutable per run, but the heuristic sits outside the contract and is therefore unversioned and unfrozen — it can drift between the baseline and governed arms of a comparison without FR61 detecting it.

**Resolution.** Extend FR6 so the contract declares the marginal-value policy (heuristic identity, thresholds, and the optional/mandatory classification it reads). That gives FR2 a clause, brings the heuristic under FR8's immutability and FR61's drift check, and closes Q7 structurally. Mark Q7 **blocking for F3**, not merely "must be specified."

### 4.3 FR7's unsatisfiability check needs FR62's output — **MEDIUM**

Deciding pre-execution that a quality floor is "unreachable within the declared ceiling" requires a cost model of how much reaching a floor costs — which is precisely what the FR62 break-even study is built to produce, and which does not exist when FR7 runs on day one.

**Resolution.** Narrow FR7's warn condition to structurally checkable contradictions: a required tool absent from the permitted list, `max_iterations` below the count of mandatory evidence steps, `max_tool_calls` below the minimum implied by required evidence fields, reserve exceeding total allocation. Drop the general unsatisfiability claim, or defer it behind FR62.

### 4.4 FR46 cannot capture both paths from one execution — **MEDIUM**

FR46 claims a single execution yields both the governed and ungoverned paths. True only up to the first divergent decision. The moment the governor *would have* denied a call or compressed a context, the counterfactual trajectory becomes unobservable — shadow enforces nothing, so what actually runs is the ungoverned path and everything about the governed one is inference. FR44's own wording ("the **estimated** effect of each") is the honest version; FR46 overstates it.

**Resolution.** Reword FR46: "A shadow run SHALL capture the executed ungoverned path together with the **estimated governed counterfactual**, and SHALL record the first point of divergence beyond which the counterfactual is inferred rather than observed."

### 4.5 FR61 frozen-configuration refusal vs provider-side model updates — **LOW**

FR61 makes the harness refuse comparisons when the executing baseline differs from the frozen definition. Providers deprecate and silently revise model versions. On a version rotation, every prior comparison becomes non-reproducible and FR63 ("any reported run SHALL be re-executable") fails for reasons outside the system.

**Resolution.** State the posture: a provider-side version change invalidates the frozen baseline and requires re-freezing and re-running both arms; previously published figures are annotated, not silently retained.

---

## Part 5 — Cut-order integrity

For each cut-order item, what breaks among surviving requirements.

### 5.1 Cut F14 (position 1) — **MEDIUM–HIGH**

- **FR69 dies**, taking the proof card and the "quality verdict held constant" pairing rule with it. FR59 covers gross/net side by side but **not** the pairing rule — the constraint that makes a savings comparison honest lives only in the first component to be cut.
- **FR78 is protected** and requires the submission to show "a governor decision stream" and "a stop caused by sufficiency." The natural rendering surface for a decision stream is F14. F16 is protected while its most likely visual source sits at cut position 1.
- **FR76** requires every submission figure to trace to a §8-satisfying harness run — achievable from FR52 export, but only if stated.

**Resolution.** Move the proof-card computation and the verdict-held-constant rule into FR59. Add to FR78: "The decision stream and sufficiency stop SHALL be demonstrable from the F12 decision-record export (FR52) and harness output alone, independent of F14." This is the cheapest way to make a protected requirement genuinely independent of a cut-first one.

### 5.2 Cut F9 Preflight Planner (cut "alongside F7 and F8") — **HIGH**

FR42 — the mandatory-versus-optional-enrichment classification — lives in F9. That classification is the **only** stated basis for FR29's "deny optional calls once required evidence is satisfied" and for the fix proposed in §1.5 for FR15. Cutting F9 removes the classifier that two protected-core requirements read, leaving "optional" undefined at the moment it is enforced.

**Resolution.** Relocate the mandatory/optional declaration into the **contract (FR6)**, where it belongs — it is a task-shape fact, not a planner output. F9 then *derives* an envelope from it rather than owning it, and FR29/FR15 survive the cut.

### 5.3 Cut F8 Model Governor (position 5) — **MEDIUM**

- **FR21** offers "targeted retry **or escalate** per the contract's escalation policy." With F8 cut, model escalation is gone; the fail-with-budget path collapses to retry-or-`request-human`. **UJ-2 is built entirely on the escalation branch** and would no longer be a supported journey.
- **FR1's** decision vocabulary retains `escalate` and `proceed-with-substitution`, both of which become unreachable — an enumeration with dead members.
- FR6's `escalation policy` field must still accept a model-free policy; not stated.
- §3.3's escalation-rate counter-metric survives but now measures only human escalation, changing its meaning without changing its name.

**Resolution.** Mark FR1's `proceed-with-substitution` as conditional on F8. Add to FR21: with F8 disabled, fail-with-budget resolves to targeted retry or `request-human`. Add a note that UJ-2 narrates the F8-enabled configuration.

### 5.4 Cut F7 Context Governor (position 6) — **MEDIUM**

- **FR37** becomes vacuous — harmless.
- §1.2 names context carry-forward as the **first** of four compounding costs, and FR34 is the only mechanism addressing it. Cutting F7 removes the mechanism for the largest claimed waste source while §1.2's problem statement stands unchanged.
- **FR62's break-even point is dominated by which mechanisms are active.** A break-even figure measured with F7 enabled does not describe the shipped system if F7 is later cut, and vice versa — yet nothing requires re-running it.
- **FR36** ("compression SHALL NOT drop an attributable fact") is cited in §9 as a Responsible AI commitment. Cutting F7 removes the commitment's subject; §9 should not read as though it still applies.

**Resolution.** Add to §4.3: exercising a cut SHALL trigger restatement of the §1.2 claim scope and re-execution of the FR62 break-even study for the surviving configuration, with §8.4 applied to any figure carried over.

### 5.5 Cut FR30 semantic deduplication (position 4) — **LOW–MEDIUM**

FR29's exact-duplicate denial survives, so nothing breaks structurally. But **FR65's suppression-accuracy counter-metric loses its discriminating power**: exact-duplicate denial is almost always correct, so accuracy reports near-perfect while the tool-call reduction figure shrinks toward triviality. The guard and the number both degrade, in a way that flatters the guard. §3.1's tool-call reduction row should note that its magnitude is contingent on FR30 being retained.

**Resolution.** Add a line to §3.1 and §8.3: where FR30 is disabled, the tool-call reduction figure and its accompanying FR65 accuracy figure SHALL both be labeled exact-duplicate-only.

### 5.6 NFR10's list is incomplete relative to §4.3 — **MEDIUM**

NFR10 names F7, F8, F9, FR30 and FR18's rubric signal as independently disableable "so the cut order is executable rather than aspirational." But §4.3's cut order also contains **F14** (position 1) and **F15** (position 8). FR71 and FR74 happen to provide disableability for those two, but NFR10 does not reference them — so the requirement that *guarantees the cut order is executable* does not cover the first item in the cut order.

**Resolution.** Extend NFR10 to enumerate every cut-order position, cross-referencing FR71 (F14) and FR74 (F15), and add F12/F10 once their status is resolved per §1.1.

---

## Part 6 — Summary table

| # | Finding | Requirements | Severity |
|---|---|---|---|
| 1.1 | F12 marked Conditional while FR4 makes recording a precondition of every decision | FR4, FR51–FR54, Appendix, §4.3 | **BLOCKING** |
| 1.2 | Deny-optional vs never-deny-side-effecting; also FR14/FR15/FR83 vs FR31 | FR29, FR30, FR31, FR14, FR15, FR83 | **BLOCKING** |
| 3.1 | No precedence rule among six simultaneously-applicable terminal/blocking conditions | FR1, FR14, FR15, FR20, FR25, FR32, FR81–FR83 | HIGH |
| 4.1 | Replay inputs exclude the model-derived values the auditable decisions depend on | FR5, FR15, FR18, FR30, FR39, FR51, FR53, NFR3 | HIGH |
| 4.2 | FR15 has no mechanism, no contract clause to cite, and sits outside FR8 immutability | FR15, FR2, FR6, FR8, Q7 | HIGH |
| 2.2 | Shadow mode vs fail-closed: governor may halt the agent it promised not to touch | FR44, FR45, FR81–FR83 | HIGH |
| 1.5 | FR15 can starve an unmet quality floor; livelock when all steps are value-denied | FR15, FR9, FR20, FR25, §1.5 | HIGH |
| 3.2 | Budget exhaustion folded into the Loop Fuse, reported as "stuck" | FR25, FR26, FR84, §1.5 | HIGH |
| 1.3 | "Clean pass" undefined; FR19 vetoes a deterministic pass FR18 calls authoritative | FR18, FR19, FR20, FR22 | HIGH |
| 2.1 | Approval pause unbounded; no timeout, no terminal state, reserve held indefinitely | FR32, FR6, FR12, FR83, §3.1 | HIGH |
| 1.6 | Shadow described as a measurement instrument but inadmissible for realized figures | FR46, FR47, §4.1, §8.4 | HIGH |
| 5.2 | Cutting F9 removes the mandatory/optional classifier FR29 and FR15 depend on | FR42, FR29, FR15 | HIGH |
| 1.4 | Gate pass during an approval pause; late-arriving approval undefined | FR20, FR32 | HIGH |
| 5.1 | Proof card and verdict-pairing rule live in cut-position-1 F14 but are needed by protected F16 | FR69, FR71, FR76, FR78, FR59 | MED–HIGH |
| 1.8 | Fail-open does not distinguish unavailability from faulted output; degraded-run admissibility unstated | FR79, FR80, FR36, FR59 | MEDIUM |
| 2.4 | No cache invalidation on side-effecting writes; misdeclared determinism unhandled | FR28, FR31, FR27, FR65 | MEDIUM |
| 2.5 | Reserve never sized or resized; escalation can underfund verification | FR12, FR39, FR14, FR81 | MEDIUM |
| 2.3 | FR7 warns but does not gate; predicted breaches contaminate the breach counter-metric | FR7, FR21, §3.3 | MEDIUM |
| 2.6 | Iteration-zero pass with zero tool calls: FR19 verdict undefined, outlier dominates means | FR19, FR20, FR56, FR58, FR64 | MEDIUM |
| 2.7 | Parallel/batched tool calls ungoverned by FR27–FR29 and FR32 | FR27, FR29, FR32, FR48 | MEDIUM |
| 3.3 | Gate trigger cadence unstated; a done run can be reported as stuck | FR17, FR20, FR25 | MEDIUM |
| 4.3 | FR7's unsatisfiability check needs the cost model FR62 has not yet produced | FR7, FR62 | MEDIUM |
| 4.4 | FR46 overstates single-execution capture past the first divergence | FR46, FR44, FR47 | MEDIUM |
| 5.3 | Cutting F8 strands FR1's `escalate`/`proceed-with-substitution` and FR21's escalation branch; UJ-2 unsupported | FR1, FR21, FR6, F8 | MEDIUM |
| 5.4 | Cutting F7 removes the mechanism for §1.2's first-named cost and invalidates FR62's figure | FR34, FR37, FR62, §1.2, §9 | MEDIUM |
| 5.6 | NFR10 does not cover the first item in the cut order | NFR10, FR71, FR74, §4.3 | MEDIUM |
| 1.7 | FR69's verdict-pairing makes the "read-only replayer" an analysis component | FR69, FR71 | MEDIUM |
| 5.5 | Cutting FR30 hollows out FR65's discriminating power while flattering it | FR30, FR65, §3.1, §8.3 | LOW–MED |
| 4.5 | Provider-side model rotation breaks FR61/FR63 with no stated posture | FR61, FR63, FR55 | LOW |
| 2.8 | No component assigned to write the OFF-state result record | FR50, FR47, FR58 | LOW |

---

## Part 7 — Minimum set to close before build

Six edits close the two blocking findings and the highest-value ambiguities:

1. **Move F12 into the protected core** and resolve the unpositioned "Conditional" label on F10 and F12. *(§1.1)*
2. **Rescope FR31** to prohibit optimization-driven suppression only, with explicit carve-outs for FR14, FR15-unsafe, FR32 and FR83. *(§1.2)*
3. **Add the precedence ladder to F1** and split budget exhaustion out of FR25 into a fourth distinct terminal state. *(§3.1, §3.2)*
4. **Amend FR5 and FR51** so model-derived decision inputs are recorded as values, making FR53 and NFR3 achievable. *(§4.1)*
5. **Extend FR6** to carry the marginal-value policy, the mandatory/optional classification, and the approval timeout — closing FR2's missing clause for FR15, surviving the F9 cut, and bounding FR32. *(§4.2, §5.2, §2.1)*
6. **State shadow-mode behaviour under fail-closed conditions**, and bar shadow output from §3.1 primary metrics. *(§2.2, §1.6)*

Everything else in Part 6 is a tightening pass and can be batched.
