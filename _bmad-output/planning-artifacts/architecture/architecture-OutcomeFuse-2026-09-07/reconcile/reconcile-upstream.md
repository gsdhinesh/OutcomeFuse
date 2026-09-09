---
title: "Upstream Reconciliation — ARCHITECTURE-SPINE vs brief, PRD addendum, source memo"
status: draft
created: 2026-09-08
artifact_under_test: _bmad-output/planning-artifacts/architecture/architecture-OutcomeFuse-2026-09-07/ARCHITECTURE-SPINE.md
sources:
  - _bmad-output/planning-artifacts/prds/prd-OutcomeFuse-2026-09-04/addendum.md
  - _bmad-output/planning-artifacts/briefs/brief-OutcomeFuse-2026-09-02/brief.md
  - _bmad-output/planning-artifacts/briefs/brief-OutcomeFuse-2026-09-02/addendum.md
  - doc/info.md
---

# Upstream Reconciliation

**Verdict: the spine lands the hard governance invariants convincingly, but it silently resolves three recorded upstream tensions in the riskier direction and leaves four evidence obligations — gateway fallback, counter-metric content, preregistration, latency — with no architectural home, which makes several of the product's headline claims unprovable as currently specified.**

Scope note: this review deliberately ignores omissions that are correctly the code's business. Everything below is either a commitment the architecture makes impossible or unprovable, a recorded design tension resolved without acknowledgement, or a judging obligation the architecture obstructs.

---

## Critical

### C1 — AD-10 turns the APIM slice into a binary submission-killer, reversing an explicitly recorded fallback

**Source anchor.**
Brief, Scope → *"Redis-backed tool caching is the fallback if APIM integration proves unstable."*
Brief addendum §3, Secondary risks → *"the APIM token-metering slice … must have a working fallback — governor-side token counting — so a metering failure degrades the **independence of the measurement** rather than blocking the demo."*
PRD §4.1 → *"A response/tool cache slice is the fallback if gateway integration proves unstable."*

**What didn't land.** AD-10 makes *routed through the gateway* a hard conjunct of the reportability predicate, and closes with **"A non-reportable run is not merely labelled — it is refused."** The Deployment section reinforces this: *"A working APIM instance is a **critical-path dependency** before any evaluation-set run,"* and the deployment diagram marks the direct path *"dev and demo only, never reportable."*

Upstream deliberately engineered a graceful degradation: lose APIM, lose *independence* of the token count, keep the run and the proof card. The spine converts that into a hard gate with no degraded tier. Under AD-10 as written, an APIM outage or a policy misconfiguration in the final days of a one-month solo build produces **zero reportable runs** — no proof card, no headline number, no F16 submission artifact. A hedged risk has been silently promoted to a single point of failure for the whole deliverable, and the spine does not acknowledge that it made that choice.

Aggravating: AD-10 also requires *"both arms of the comparison used the same route."* That is correct discipline, but it means a mid-campaign APIM failure invalidates already-completed baseline arms rather than merely downgrading them.

**Suggested fix.** Make reportability graded rather than binary, and put the grade in the manifest and on the proof card:

- Add a `metering_provenance` field to AD-9's manifest: `gateway-measured` | `governor-measured`.
- Restate AD-10 as: a run is **reportable** if non-streaming, same-route across both arms, conformant adapter, complete manifest, and evaluation-set-sourced for a headline claim. Gateway routing is not a reportability conjunct — it is a **claim-strength qualifier** that the proof card must render, and a headline stated on `governor-measured` runs must carry the qualifier visibly.
- Keep the refusal semantics for the things that genuinely cannot be repaired after the fact (missing manifest, mixed routes, non-conformant adapter, calibration-set headline).
- Record in Deferred or Open Questions that gateway metering is an *evidence-strength* dependency, not a build-blocking one.

---

### C2 — AD-5 forecloses the evidence that every counter-metric, the blind review and the demo all require

**Source anchor.**
PRD addendum §3, *The perverse optimum* → *"Every headline number in this product needs a paired number that can embarrass it"* (FR69 false-sufficiency, FR70 suppression accuracy, FR71 compression fidelity).
Brief addendum §1, Context Governor → *"Preserves citations, identifiers, numbers, and policy clauses **verbatim** — compression must never drop an attributable fact."*
PRD FR69 → blind human review; *"The reviewer SHALL see **the deliverable** and the contract."*
doc/info.md §1 → judges want *"an artifact whose mechanism can be watched running"*; §5 key screens → *"cache hit," "duplicate denied," "quality passed."*

**What didn't land.** AD-5 rules that *"Raw prompts, tool arguments and tool results never leave the adapter that produced them,"* and that FR6's model-derived inputs are *"scores, estimates, envelopes, canonical keys and content hashes — **never raw text**."* AD-16 makes the run database the only durable store; AD-2 rules that *"Anything not in the log did not happen and may not be claimed"*; AD-17 generates the side-by-side view *from the decision log* only.

Chain those four and the consequences are severe:

1. **FR71 compression fidelity is unmeasurable.** Establishing that a citation or identifier survived compression requires comparing pre- and post-compression content. Neither exists anywhere durable.
2. **FR69 blind review has no artifact.** The reviewer must see the deliverable. The deliverable is raw text produced at the adapter boundary and is, under AD-5, barred from crossing inward — and therefore from the run database that AD-16 makes the sole record.
3. **FR70 suppression accuracy** requires knowing what a denied tool call *would have returned* — again content, not a hash.
4. **The demo's most persuasive moment degrades to hex.** "Duplicate denied" rendered from a decision log that holds only canonical keys is two matching SHA-256 strings side by side. The memo's 0:38–1:15 beat — compressed evidence capsule, duplicate rejected, quality gate evaluated — becomes unwatchable, which directly hits the *"Make Something / show the mechanism running"* judging signal.

AD-5 is defending a real NFR5/NFR12 concern and should survive. What is missing is the distinction between *telemetry* (redact) and *evidence* (retain, in a separately governed store).

**Suggested fix.** Split the concern into two invariants:

- **AD-5 (narrowed):** raw content never enters the **governor core** or any application log. Core structures and log lines carry derived values only. This preserves the leak-prevention rationale verbatim.
- **AD-5b (new) — the evidence sidecar.** Add a distinct, adapter-written, run-scoped **evidence store** (a second table in the same per-run SQLite file, or a sibling file) holding the artifacts that FR69/FR70/FR71 and F14/F16 require: candidate deliverables, pre- and post-compression capsule pairs, and tool-result digests-plus-payloads for cases where suppression accuracy must be scored. Bind it to NFR5/NFR12 explicitly: synthetic cases only (NFR9 already guarantees this for the MVP), whole-file retention per AD-16, and never read by core.
- Amend AD-17: the viewer generator may read the decision log **and** the evidence sidecar; autoescaping already covers the untrusted-input risk.
- Amend AD-2's *"may not be claimed"* to read: claims about decisions rest on the log; claims about content rest on the evidence store. Both are records; neither is a mutable second truth.

---

## High

### H1 — Preregistration is not recorded, so the sealed-evaluation-set argument is unverifiable

**Source anchor.**
PRD addendum §3, *The calibration/evaluation split* → *"Architecture should treat the two sets as separate artifacts with a **recorded preregistration timestamp**, not as a naming convention over one corpus."*
PRD §8.5 / FR66 / FR102; brief Risks → *rubric circularity* (*"The same person writes the quality rubric and the optimizer that must satisfy it. A reviewer will notice."*)
PRD addendum §1.4 → *"the PRD's evidence standards (§8) being a differentiator in themselves, not merely diligence."*

**What didn't land.** AD-9's manifest carries *"case-set identity and `calibration` | `evaluation`"* — which is precisely the naming convention the addendum warned against. There is no preregistration artifact anywhere in the spine: no preregistered target values, no counter-metric thresholds, no Q4 sample size, no Q6 minimum case count, no timestamp, no hash binding the run to the record that was written before results were seen. AD-10 requires headline claims be *"drawn from the sealed evaluation set,"* but under AD-2's own rule the seal is an assertion, not a fact in the log — and the one property most likely to be attacked by a sceptical judge is the one property the architecture cannot demonstrate.

**Suggested fix.**

- Add a **preregistration record** as a first-class, hash-identified artifact: targets, counter-metric thresholds, `N` per FR69, minimum case count per FR59, evaluation-set identity hash, and an RFC 3339 timestamp — written once, append-only, in its own file under the record store.
- Add `preregistration_hash` and `preregistration_timestamp` to AD-9's manifest, and add *"preregistration record exists and predates the run's first log entry"* to AD-10's predicate for any headline claim.
- Make the evaluation-set seal structural, not procedural: the evaluation case-set hash must appear in the preregistration record; the harness refuses to execute a governed evaluation-set run whose case-set hash is absent from a preregistration written earlier.

### H2 — The governor's own model work has no owner, and no invariant routes it through the ledger

**Source anchor.**
Brief, *What Makes This Different* → *"OutcomeFuse reports **net** savings, inclusive of its own overhead — evaluator calls, planning passes, compression passes. Gross savings are how this category flatters itself."*
PRD FR15 (two-way attribution plus per-mechanism attribution), FR61, FR62, FR98, NFR2.
PRD FR22 / addendum §3 → model-judged tool-use quality survives as an **advisory** signal.

**What didn't land.** AD-4 states that a mechanism *"never mutates run state and **never calls a port**,"* and the layer table makes the core pure with no I/O. The Preflight Planner is a model pass. The Context Governor's compression is a model pass. The advisory rubric signal is a model pass. The Quality Gate lives in `core/gate`, which is pure. **The spine therefore names no component permitted to perform the governor's own model work**, and the "One decision" sequence diagram shows only the *host's* step being reserved, settled and attributed.

Two consequences follow. First, the advisory rubric signal (FR22) is architecturally homeless — the very thing AD-7 and FR20 are careful to keep *out* of the verdict still has to be produced by something. Second, and more damaging: nothing requires the governor's own spend to traverse the same reserve-then-settle lane as host work. Overhead calls that bypass AD-3's reservation can breach the ceiling that AD-3 exists to protect, and can arrive at the ledger by a second route — which is exactly the failure AD-4's "Prevents" clause claims to have eliminated, reintroduced one level up.

**Suggested fix.** Extend AD-4 with a fourth clause and one sentence in AD-3:

- *"Governor-initiated work is driver-executed."* An advisor may request a port call by returning a typed request in its proposal; the **driver** executes it against the port and the **Ledger** settles from the recorded outcome, attributed to the requesting mechanism and classified as `governor-overhead` per FR15. Advisors remain pure and port-free; nothing gains a second write path.
- *"Every model call, task or overhead, is reserved before it is made and settled from its recorded outcome."* This closes the ceiling-bypass and makes FR61's gross/net line item derivable from the log alone.
- Name the executor of the advisory rubric explicitly — an evaluator port called by the driver on the Gate's request, with the Gate remaining pure and the verdict remaining deterministic-only per FR20.

### H3 — AD-5 and AD-6 contradict each other, and F6/F7 are the casualties

**Source anchor.**
Brief addendum §1, Tool Governor → *"Canonicalizes tool name plus **arguments** into a stable key."*
Brief addendum §1, Context Governor → compresses tool output, *"preserving citations, identifiers, numbers, and policy clauses verbatim."*

**What didn't land.** AD-6 mandates *a single core-owned canonicaliser* for, among other things, *tool-call keys* — which requires the tool arguments to reach core. AD-5 forbids tool arguments from leaving the adapter. AD-4 forbids the Tool Governor and Context Governor from calling ports. As written, F6 cannot compute its key and F7 cannot see the text it is supposed to compress. Both mechanisms are load-bearing for the headline (tool-call reduction is a committed secondary metric; F6 and F7 sit at cut positions that keep F6 protected).

This is repairable and probably intended, but the spine does not say how, and "the code will figure it out" is not available here because two invariants are in direct conflict — a build following the spine literally will resolve it inconsistently in two places, which is precisely what a spine exists to prevent.

**Suggested fix.** State the resolution in AD-6: *"Canonicalisation is performed **by the adapter**, using the single core-owned pure function imported into the adapter layer. The function is core-owned so there is one algorithm; it is **called** at the boundary so raw arguments never cross inward. Only the resulting key crosses."* Apply the same construction to the Context Governor: the compression *decision* (what to keep, what budget) is the advisor's pure output; the compression *execution* over raw text is driver-plus-port work per H2's fourth clause. Add a line to AD-5 acknowledging that core-owned pure functions may execute outside core — this is the one legitimate exception and should be named rather than discovered.

### H4 — Latency is a committed metric that the record cannot support

**Source anchor.**
doc/info.md §5 success criteria → *"P50 end-to-end latency ≥20% reduction."*
Brief, Success Criteria (secondary) → *"Reduction in P50 end-to-end latency."*
PRD §3 → *"Added latency — wall-clock cost of governor decisions per step. **Cheaper but unusably slower is a failed trade.**"*
PRD NFR1 → *"Governor decision overhead per step SHALL be bounded, measured and reported."*

**What didn't land.** No timestamp or duration appears anywhere in the spine's record obligations: not in AD-8's schema statement, not in AD-9's manifest field list, not in the "One decision" sequence. The Consistency Conventions establish a clock port and a time *format*, but nothing requires a decision to carry a time. AD-2 then finishes the job: latency was never in the log, so under the spine's own rule it did not happen and may not be claimed.

Aggravating: AD-3 rules that the host *"may not obtain verdicts in parallel."* The frozen baseline (brief addendum §3) is a conventional agent under no such constraint and may fan out tool calls. AD-3 anticipates this for NFR1 (*"measured against batch width"*) but not for the end-to-end P50 comparison, where the governed arm carries a serialisation penalty the baseline does not — a structural bias against the product on a metric it has publicly committed to.

**Suggested fix.**

- Add to AD-8: every decision row carries `decided_at` and `decision_duration_ms`, sourced from the clock port at the driver; the run manifest carries `run_started_at` and the terminal entry carries `run_ended_at`. One line, and it makes NFR1 and the P50 claim derivable from the log.
- Add a sentence to AD-3: where the baseline arm executes steps concurrently, end-to-end latency is reported **alongside** decision-serialisation overhead as a separate line item, so a latency regression attributable to AD-3 is visible rather than absorbed into the headline. This mirrors the FR61 gross/net treatment and keeps the reporting posture consistent.

### H5 — The fail-open / fail-closed asymmetry is flattened into a single uniform rule

**Source anchor.**
PRD addendum §3, *Fail-open versus fail-closed asymmetry* → *"Optimization mechanisms fail open, the Quality Gate and budget ceiling fail closed… **Architecture should treat ledger durability and evaluator timeout behaviour as reliability concerns distinct from the compression and routing paths, since they carry opposite failure postures.**"*

**What didn't land.** This is a recorded design tension with an explicit instruction to architecture, and the spine answers it only for shadow mode (AD-11) and approval unavailability (AD-12). The general posture is set in a single Consistency Conventions line: *"A port error is a **decision input**, never an escape."* That is one uniform rule applied to two categories with opposite required behaviour. A ModelPort timeout during a compression pass must degrade to uncompressed context and continue; a ledger write failure or an evaluator timeout must halt. Under the current wording both are "a decision input," and the Policy is left to distinguish them with no invariant telling it how — meaning the distinction will be re-derived per call site, which is the failure mode the addendum specifically warns about for FR103.

Ledger durability is also unaddressed. AD-2 requires append *before* the decision takes effect and AD-16 makes the store append-only, but nothing states that the append must be durably committed before the verdict is returned — which is the whole content of "the decision log is the system of record" under crash.

**Suggested fix.** Add **AD-18 — Failure posture is a property of the port, not of the call site**:

- Each port declares its posture at registration: `fail-open` (ModelPort when serving an optimisation mechanism, tool cache, metering) or `fail-closed` (record sink, ledger, evaluator, approval).
- A `fail-open` port error yields a recorded degradation reason from the FR104 registry and the run continues ungoverned on that dimension. A `fail-closed` port error yields a fail-closed halt.
- The record-sink append is durably committed before the verdict is returned to the adapter; a failed append is a fail-closed halt, never a silent continue.
- AD-11's shadow exemption is stated as an override of this AD, in one place, rather than as a property shadow mode happens to have.

---

## Medium

### M1 — The adoption-cost differentiator is neither guaranteed nor measured

**Source anchor.**
Brief, *What Makes This Different* → *"It is not a new agent framework… designed to wrap existing tool-using agent loops with minimal integration change. **Adoption cost is the reason to believe it can spread.**"*
Brief, Vision → *"middleware that any team can wrap around an existing agent in an afternoon."*
doc/info.md §1 (Feasibility signal) → *"Insert as middleware around an existing agent rather than requiring customers to rebuild their agents."*
doc/info.md §8, 1:42–2:00 → *"Same governor, dissimilar agents, no code changes."*

**What didn't land.** The spine's adapter obligations are substantial: AD-1 requires the adapter to propose every step and apply every verdict *including termination*; AD-5 makes the adapter responsible for all redaction and derived-value production; AD-15 requires it to pass a six-scenario conformance battery before producing anything reportable; AD-3 forbids parallel verdict acquisition, which is a real change to any host loop that fans out. That may all be correct — but "minimal integration change" is a *claim the submission makes*, and nothing in the spine bounds the adapter surface or requires the integration delta to be recorded as an artifact. The scale beat of the video asserts a property the architecture neither guarantees nor evidences.

**Suggested fix.** Add to AD-1 a bounded adapter contract — an explicit maximum surface (propose, apply, report-outcome, plus registration) with a note that anything beyond it belongs in the runtime, not the adapter. Add to AD-9 or the harness an `integration_delta` artifact per adapter: lines changed in the host agent, and whether any host control flow was restructured. It costs almost nothing and converts an asserted differentiator into a measured one — consistent with how the rest of this product treats its claims.

### M2 — Demo runs are non-reportable by construction, so the video's proof cannot be tied to its footage

**Source anchor.**
doc/info.md §1 (Make Something) → *"Show the budget ledger **actively** approving, denying, compressing, caching, or escalating agent steps."*
doc/info.md §8 → the 0:38–1:15 mechanism beat and the 1:15–1:42 proof beat as one continuous narrative.

**What didn't land.** The deployment diagram marks the direct-to-model path *"dev and demo only, **never reportable**,"* and AD-10 confines headline claims to the sealed evaluation set. Nothing requires the run shown in the video to itself be a reportable run. The likely outcome is that a judge watches one execution and is then shown numbers from a different set of executions, with no artifact connecting the two — which weakens exactly the beat the source memo says separates strong entries (*"a clear before/after cost story with quality held constant"* observed on a mechanism that can be watched running).

**Suggested fix.** Add to AD-17 or the F16 row: *"The run rendered in the submission artifact SHALL itself be a reportable run drawn from the evaluation set, and its comparison HTML SHALL be the same artifact from which the quoted proof card is read."* This is free — it is a constraint on which run you film, not on the build — and it makes the demo and the claim the same object.

---

## Low

### L1 — AD-14 multiplies the cost of FR62 ablation against a schedule already flagged as material

AD-14's run-scoped, non-persistent cache is well-argued for FR64/FR68 honesty. The consequence is that FR62's per-mechanism ablation — seven mechanisms plus a governed and a baseline arm, across four workloads, with repeats per case, all at full model cost with no cache warmth — is a large and unpriced multiplier on the evaluation budget. PRD §11 already records the schedule as *"material, and accepted deliberately,"* and Q-A already notes the third adapter has no cut-order entry. Worth adding one line to Q-A or a third open question: the evaluation-run budget (case count × repeats × arms × ablations × workloads) should be estimated before preregistration fixes `N` and the minimum case count, because those two numbers and this multiplier are the same decision.

---

## What landed well (recorded so it is not re-litigated)

- **NFR10 as a hard constraint.** The addendum asked architecture to treat independent disableability as load-bearing for the cut order; AD-4's *"Disabled means not registered… byte-identical to having cut the mechanism"* is a stronger answer than the addendum asked for.
- **"A protected component may not take its meaning or its output from a cuttable one."** AD-17 explicitly keeps proof-card computation out of F14, and the Capability Map places F16 on the harness. The rule the addendum established is honoured.
- **The reason registry as a project-owned artifact.** AD-8 correctly refuses to let FR104's stability promise depend on an external Development-status specification, and the OTel deferral is stated as an additive mapping.
- **The deterministic-gate argument.** AD-7's closed verifier registry with no callable reference crossing the contract boundary defends FR20's position better than FR20 alone did, and closes an RCE vector that upstream never raised.
- **Shadow mode's counterfactual barred from reportability.** AD-11 gets FR48/FR96 right, including the correction the PRD made to the brief's "both paths from one run" framing.
- **Terminal-reason precedence.** The addendum's hardest distinction (cause vs disposition, exhaustion outranking no-progress) is respected by AD-4's single-writer rule and the FR103 mapping requirement.
