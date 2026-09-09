---
title: "Rubric Review — ARCHITECTURE-SPINE.md (OutcomeFuse)"
artifact: _bmad-output/planning-artifacts/architecture/architecture-OutcomeFuse-2026-09-07/ARCHITECTURE-SPINE.md
prd: _bmad-output/planning-artifacts/prds/prd-OutcomeFuse-2026-09-04/prd.md
reviewer: rubric review (good-spine checklist, 8 items)
date: 2026-09-08
verdict: CONCERNS
---

# Rubric Review — OutcomeFuse Architecture Spine

## Gate verdict

**CONCERNS — conditional pass.** This is a strong, genuinely terse spine that fixes most of the real divergence points and resists the usual temptation to restate the PRD. It is blocked from a clean pass by four internal-consistency defects that would let two independently-built units diverge in exactly the places the product's headline claim rests on: the ledger's relationship to the log, shadow-mode overhead, the redaction boundary around evidence capsules, and the reportability/route contradiction. None requires re-architecture; all require a sentence each.

**Scoring summary**

| # | Checklist item | Rating |
|---|---|---|
| 1 | Fixes the real divergence points, misses none | **Concern** |
| 2 | Every Rule is enforceable and prevents what it claims | **Concern** |
| 3 | Nothing under Deferred can cause divergence meanwhile | **Pass** |
| 4 | Named technology verified-current | **Concern (minor)** |
| 5 | F1–F16 covered where an invariant is genuinely needed | **Concern** |
| 6 | Every initiative-altitude dimension decided, deferred, or open | **Concern** |
| 7 | Internal consistency — no AD contradicts another | **Fail** |
| 8 | Mermaid valid and structural, not decorative | **Concern (minor)** |

---

## Preamble — what this review deliberately does not flag

The brief is correct that terseness is a feature and that structural omission is not a finding. Accordingly this review does **not** treat as findings: the absence of a data model beyond the ER seed; the absence of module-level API signatures; the absence of a CI pipeline definition; the absence of error-code catalogues; the absence of a logging format; the absence of SQLite pragmas, WAL configuration or indexing; the absence of a packaging/release process. Those are code-owned.

What this review *does* treat as findings is any point where two units built from this document, both obeying every stated rule, could still produce incompatible behaviour or incomparable numbers — and any whole dimension the initiative altitude owns that the document leaves silent.

---

## Item 1 — Does it fix the real divergence points, and does it miss any?

**Rating: Concern.**

### What it gets right

The divergence surface for a governed-runtime product of this shape is: who may call whom; what is authoritative; who writes what; what crosses the durable boundary; what is comparable to what; and what happens when something breaks. The spine hits all six deliberately:

- **Who may call whom** — AD-1 (mediated boundary, no host framework type above the adapter layer) plus the layer/dependency table. This is the invariant that stops three host adapters from becoming three architectures.
- **What is authoritative** — AD-2. The strongest single decision in the document. "Anything not in the log did not happen and may not be claimed" converts FR5 from an obligation into a structural property.
- **Who writes what** — AD-4's four single writers is the highest-leverage rule here. It pre-empts the exact failure the *Prevents* clause names (FR15 attribution acquiring two meanings, so FR62's ablation compares numbers computed differently). The `EvidenceRequest` concept is a genuinely good invention: it makes advisor purity survive contact with the fact that most advisors need model output, and it makes replay definitionally equal to "feed recorded outcomes back to a pure function."
- **What crosses the durable boundary** — AD-5 and AD-19 together. The insight that the blind-review packet must be rendered from a store the renderer cannot see the verdict through (AD-19) is the difference between FR69 being a protocol and FR69 being a guarantee. That is the best AD in the document.
- **What is comparable to what** — AD-9 (manifest) and AD-10 (three gates) are the pair that makes §8 enforceable rather than aspirational. Splitting admissibility (hard, refuses), independence (graded, degrades the label) and publication accompaniment (hard, refuses) is precisely right, and it is the correct reading of the difference between FR102 and FR80.
- **What happens when something breaks** — AD-20's "fail-open is a property of the registry, fail-closed is a property of the driver" places the posture once instead of per-site, which is exactly what §10 needed and did not itself provide.

AD-7 deserves separate credit. FR8's phrase "executable deterministic verification method" is a latent RCE in a product whose adoption story is *platform teams hand contracts to agent owners*. AD-7 spots it and closes it with a closed registry, and it correctly derives the FR21 qualifier from *which registry entry ran* rather than from a separate assertion — removing a divergence nobody would have noticed until two adapters labelled the same pass differently.

AD-18 is likewise a real catch: FR17's floor-protection carve-out is described in the PRD as living "in FR17," which structurally would have put it inside a pluggable estimator. Moving it into the Policy is the difference between the carve-out being non-negotiable and being one dependency-injection away from gone.

### What it misses

**(1a) The Loop Fuse's progress fingerprint has no governing invariant, and AD-6 both excludes it and forbids it.** FR27's progress fingerprint covers "evidence gained, task-state change and quality delta" plus "repeated tool arguments." That is a structural hash, and it is a first-class divergence point: two implementations that fingerprint differently produce different halt points, different `halt-no-progress` counts, and — via FR68 — non-reproducible runs. AD-6's *scope* enumerates only four uses (contract identity, tool-call keys, rubric/answer-key freeze, baseline-configuration freeze); the fingerprint is not among them. But AD-6's closing sentence is absolute: "No component may hash a structure by any other route." So the fingerprint is simultaneously outside AD-6's declared scope and forbidden from having its own route. The capability map compounds this by governing F5 with AD-2 and AD-4 only — not AD-6. Either the fingerprint is an AD-6 use (say so) or it is an explicit exception (say that). Left as-is, this is the most likely place for two units to silently diverge.

**(1b) FR98 gate cadence is owned by nobody in an AD.** The rule that the Gate executes before any terminal halt other than fail-closed is what gives `stop-sufficient` first refusal on the ending — the product's headline event. AD-1's *Prevents* names the failure ("refiling the product's headline event as `halt-exhausted`"), AD-15's battery asserts "sufficiency stop terminates," and the sequence diagram shows the driver deciding when to evaluate. But no **Rule** states that cadence is the driver's, and the enforcing driver and the shadow driver are different objects (AD-11). Two drivers implementing cadence differently is a live risk, and it lands on the one metric §3.3 exists to protect.

**(1c) NFR8 domain neutrality has no rule.** Four committed workloads, a solo builder, and a cut order that drops workloads last is precisely the pressure that produces a workload-specific branch in `core/`. Purity (no I/O) is not neutrality (no domain knowledge); the paradigm section fixes the former and nothing fixes the latter. The Consistency Conventions table would carry this in one row.

**(1d) FR79's reconciliation has no tolerance.** AD-13 pins the cost table and owns the seam, which is the right call, but "surface any discrepancy" needs a definition of discrepancy — exact equality, or a band? The harness and the metering adapter can each answer differently, and the answer decides whether F15 ever reports a clean reconciliation. This is arguably code-owned; noted as low.

---

## Item 2 — Is every Rule enforceable, and does it prevent what it claims?

**Rating: Concern.** Nineteen of twenty Rules are genuinely pointable-at. The exceptions and the near-misses:

### Enforceable, and prevent what they claim

AD-2, AD-6, AD-7, AD-9, AD-12, AD-13, AD-14, AD-15, AD-16, AD-17, AD-18, AD-19 are all clean. Each states a condition a reviewer can hold code against ("no `UPDATE` or `DELETE` is issued against the decision table"; "no import path, expression or callable reference crosses the contract boundary"; "the renderer is structurally denied access to the gate verdict"), and each *Prevents* clause names a divergence the Rule actually forecloses.

AD-14 deserves a note for a small elegance: it discharges NFR6 (tenant partitioning) *structurally* rather than by adding a partitioning rule — "a run belongs to one tenant and one use case, so cross-user reuse is impossible by construction." That is an invariant doing the work of a feature.

AD-12 is the same move: it converts FR89 and FR100 from things a human must sit through into a scripted decider driven by the case definition, and it defines "unavailable" at the port so the fail-closed path has a testable trigger. Without this AD, FR89 would have been asserted and never exercised.

### Platitude or soft language

**(2a) AD-1's second sentence pair is the only genuine platitude.** "Interception and loop-driving are adapter strategies, not architectures" is a slogan, not a rule — a reviewer cannot point at code and say it was violated. The AD survives because the surrounding sentences *are* enforceable ("reached only through a narrow port"; "no host framework type may appear above the adapter layer"). Recommend either deleting the slogan or converting it into the checkable form it implies: that both strategies must produce a decision log that passes the same AD-15 battery.

**(2b) AD-3's final sentence is a measurement convention wearing a rule's clothes.** "Decision latency is measured against batch width, not per step alone" is a definition for NFR1, not an invariant about divergence, and it sits in a Rule whose other two sentences are hard. Harmless, but it dilutes the section.

### Rules that do not fully prevent what they claim

**(2c) AD-11 claims more than its Rule delivers.** *Prevents* is: a shadow branch "inside the Policy, inside every mechanism, and — because FR91 exempts shadow from fail-closed — inside the fail-closed paths." The Rule delivers this for the Policy and for halts. It does **not** deliver it for the mechanisms, because it never says what the shadow driver does with an `EvidenceRequest`. See Finding 7c — this is the highest-value gap in the document.

**(2d) AD-4's *Prevents* is about attribution, but its Rule leaves the Quality Gate's overhead unattributed.** Writer 4 says every `EvidenceRequest` fulfilment "including every Quality Gate execution under FR98 — is debited as governor overhead, **attributed to the requesting mechanism**." Under FR98 the Gate executes on cadence, requested by the driver or the Policy, not by any mechanism. There is no requesting mechanism, so the attribution rule has no referent for the single largest and most frequent overhead item in the system. FR15 demands per-mechanism attribution; FR62 demands the sufficiency-stopping mechanism be ablatable with a breakdown. Gate overhead is the number that decides whether the net claim survives — leaving its attribution undefined is a material hole in the rule that exists to prevent exactly that.

**(2e) AD-20 does not say which side of the asymmetry the FR20 rubric signal falls on.** The rubric is an `EvidenceRequest` fulfilled by a model call, inside the Gate. If it raises: is that "gate-verdict unavailability" (fail-closed, terminate through the FR2 ladder) or "an advisor raised" (fail-open, deregister, mark degraded)? FR20 makes deterministic validation authoritative, so the correct answer is clearly fail-open — but AD-20's two clauses are keyed to *component type* (advisor vs driver), and the rubric is neither: it is a cuttable signal inside a fail-closed component. Two implementers will answer this differently, and one of them will terminate runs that should have continued degraded.

---

## Item 3 — Could anything under Deferred cause divergence meanwhile?

**Rating: Pass.** This section is unusually disciplined: every deferral is paired with the invariant that holds the line until it is picked up.

| Deferred item | Held by | Assessment |
|---|---|---|
| Managed-service deployment beyond APIM | §4.2 + deployment seed | Safe. In-process is decided, not merely defaulted. |
| Persistent / cross-run tool cache | AD-14 | Safe, and the deferral names the two things a future version must answer (tenant key, FR64/FR68 under varying cache warmth). |
| Multi-process / distributed governor | AD-3 | Safe. The deferral correctly scopes AD-3 as a *per-run, in-process* guarantee rather than a universal claim, so nothing is foreclosed. |
| Contract authoring surface | AD-7 | Safe. AD-7's closed registry is named as the constraint any future surface inherits. |
| Learned marginal-value estimation | AD-4 + AD-18 | Safe, and precisely reasoned: the estimator is pluggable, the carve-out is not. |
| Live production traffic shadowing | FR106 | Safe. |
| OpenTelemetry export | AD-8 | Safe. AD-8 makes later adoption an additive mapping rather than a migration. |
| Production ground truth without answer keys | AD-7 + §8.2a | Safe. Correctly framed as making the limit explicit per contract rather than solving it. |
| CI gate, multi-agent transfer, policy DSL | — | Safe; vision, not MVP. |

No deferral leaves a decision that two units must agree on. This is the item the spine handles best.

---

## Item 4 — Is named technology verified-current?

**Rating: Concern (minor).** The version table is internally plausible for 2026-09-07 and the pins are specific rather than ranged, which is the correct posture. Nothing looks obviously stale or wrong. Two things are asserted rather than shown, and one risk is unmentioned:

**(4a) The Python 3.14 floor is asserted against three third-party agent frameworks and is unhedged.** The table pins Python 3.14 with a ceiling below 3.15 — sensible in itself — but LangGraph 1.2.11, agent-framework 1.17.0 and openai-agents 0.22.0 are all optional extras whose 3.14 support is a compatibility claim the table makes silently. Given Q-A already flags the third adapter as the most reversible commitment, a one-line note that adapter extras are pinned per-adapter and may lag the core interpreter floor would cost nothing. Low severity, but it is the kind of thing that surfaces as a day-one install failure.

**(4b) AD-8's claim about the OpenTelemetry GenAI conventions is an assertion inside a Rule.** "which is still Development-status with no published releases" is a factual claim about an external specification's state on a specific date, embedded in normative text. If it turns out to be wrong, the Rule's *reasoning* collapses even though the Rule's *decision* (own the schema, borrow only names) remains correct. Recommend moving the status claim to a footnote so the decision does not depend on it. Low.

**(4c) The PRD §9 "preview-stage honesty" obligation is discharged, but only implicitly.** §9 requires that where a dependency is preview-stage, "a stable fallback SHALL be pinned and the dependency's status stated plainly." The spine states openai-agents' status plainly (good) and the source tree contains `adapters/host/reference/` — a hand-rolled ReAct loop described as the conformance reference — which *is* the stable fallback. But nothing connects the two. One clause in AD-15 naming the reference adapter as the fallback for any preview-stage host would close a governance obligation that is currently satisfied by accident.

Nothing in the table appears fabricated or self-evidently wrong; the APIM policy names (`llm-token-limit`, `llm-emit-token-metric`) are real and correctly chosen for the FR78 job.

---

## Item 5 — Are F1–F16 covered where an invariant is genuinely needed?

**Rating: Concern.** The Capability → Architecture Map is complete on its face — all sixteen features plus §10 map to at least two ADs, and the mappings are substantively right rather than decorative. Two features are under-governed and one mapping is wrong.

| Feature | Coverage assessment |
|---|---|
| F1 Runtime Decision Policy | Well covered. AD-18 in particular protects the one rule §1.5 calls non-negotiable. |
| F2 Outcome Contract | Well covered. AD-7 is load-bearing. |
| F3 Budget Ledger | **Under-governed** — see Finding 7a. Reserve/settle semantics are the divergence point and no AD fixes their relationship to the log. |
| F4 Quality Gate | Adequate, with the FR98 cadence gap (1b) and the rubric-failure posture gap (2e). |
| F5 Loop Fuse | **Under-governed** — the progress fingerprint (1a). Mapping to AD-2/AD-4 only is the wrong pair; it needs AD-6 or an explicit exception. |
| F6 Tool Governor | Well covered — AD-6, AD-14, AD-12, AD-5. FR33's side-effect exclusion is left to the code, which is defensible: it is a contract-declared property, not a cross-unit agreement. |
| F7 Context Governor | Covered, but AD-5's treatment of capsules creates the contradiction in 7b. FR38 ("SHALL NOT drop an attributable fact") is arguably feature-altitude and correctly absent as an AD. |
| F8 Model Governor | Well covered. AD-13's cost-table pinning is a genuine catch — a pricing change between calibration and evaluation would have moved the headline silently. |
| F9 Preflight Planner | Adequate. FR44's "F9 consumes the classification, it does not own it" is structurally guaranteed by AD-7 putting the classification in the contract; the spine could say so but does not need to. |
| F10 Shadow Mode | **Incomplete** — AD-11 covers halts and reportability but not overhead or approval. Finding 7c. |
| F11 Integration Surface | Well covered. AD-1 + AD-15 is the right pair, and Q-B honestly flags the cost. |
| F12 Decision Record | Well covered. AD-8's ownership of the schema and reason registry correctly refuses to delegate FR104's promise. |
| F13 Benchmark Harness | Well covered — AD-9, AD-10, AD-15, AD-16, AD-19. |
| F14 Side-by-Side View | Well covered. AD-17 converts FR77 from a discipline into a property of the artifact type, and correctly keeps FR97's computation out of the cut-first component. |
| F15 Gateway Metering | Adequate; see 1d and Finding 7e (APIM config is unpinned). |
| F16 Submission Artifact | Adequate. Architecture can gate what the harness *emits*; it cannot gate what a human puts in a video, and the spine correctly does not pretend otherwise. |

---

## Item 6 — Is every initiative-altitude dimension decided, deferred, or explicitly open?

**Rating: Concern.** Most dimensions are handled; one is effectively silent and two are thin.

| Dimension | Status | Assessment |
|---|---|---|
| **Deployment / environments** | **Decided** | Strong. The deployment diagram plus "Two environments only… No staging tier exists and none is warranted at MVP" plus naming APIM a critical-path dependency is exactly the right amount. |
| **Infra / provider strategy** | **Partly decided** | Azure subscription, APIM, model endpoints, App Insights are named. But how APIM is provisioned and configured reproducibly is unaddressed — see 7e. |
| **Operations** | **Thin but acceptable** | For a solo one-month MVP with no running services (AD-17 removes the only candidate), there is little operational surface. The one operational fact that matters — APIM is on the critical path before any evaluation run — is stated. Acceptable. |
| **Data lifecycle** | **Partly decided** | AD-16 gives the mechanism (archive/delete whole files) and AD-19 says retention-bounded. Neither says where the retention period is *declared*, which is the specific thing NFR12 requires. Also unstated: whether the evidence store is per-run (like the DB) or shared, which decides whether AD-16's whole-file retention story extends to it. Low–medium. |
| **Testing strategy** | **Effectively silent — finding** | See Finding 7d. AD-15's conformance battery and FR100's failure cases are both *product* test obligations inherited from the PRD, not a testing strategy. Nothing states how replay-equivalence is asserted, and replay is the mechanism NFR3, FR6 and FR68 all rest on. |
| **Security posture** | **Decided, with one gap** | Genuinely well handled for a document this short: AD-5 (redaction at the port), AD-7 (no code execution from data), AD-19 (access-controlled store, structurally denied renderer), AD-17 (autoescaping, "record content is untrusted input" — a real catch), and Conventions (secrets from environment only, no credential in a contract). The gap is NFR7's *least-privilege tool identity*, which no rule or convention touches. Low, since tools are workload-owned mocks at MVP. |
| **Observability** | **Decided** | AD-8 puts the governor's own wall-clock decision cost on every decision row so NFR1 is measured from the record rather than instrumented separately — a good decision that removes a whole component. Conventions cleanly separate application logs (no decision authority) from the decision log. OTel export explicitly deferred. The one loose thread is Application Insights appearing in the deployment diagram while no AD, convention or deferral mentions it — see Item 8. |

---

## Item 7 — Internal consistency

**Rating: Fail.** Four contradictions, one of which is load-bearing. Cross-referencing the pairs the brief calls out plus the rest:

### 7a — CRITICAL: The Ledger mutates outside the log, contradicting AD-2 (AD-2 × AD-3 × AD-4 × "One decision" diagram)

AD-2: "Run state — **ledger position**, `quality_state`, iteration count, decision history — is derived by folding the log, never stored as an independent mutable truth," and "Every decision is appended to the log **before it takes effect**."

AD-3: "Budget is **reserved at decision time and settled at completion**."

The "One decision" sequence diagram shows the actual order:

```
P->>L: reserve for the chosen action
L-->>P: reserved or rejected
P-->>D: policy_action, decision_reason, terminal_reason
D->>R: append decision
```

The reservation mutates ledger state **before** the decision is appended. Under AD-2, ledger position is a fold over the log; a reservation that is not in the log therefore either (i) does not exist, in which case affordability under AD-3 cannot be evaluated, or (ii) exists as independent mutable state, which AD-2 forbids in the same sentence that names ledger position. The same problem appears twice more in the diagram: `D->>L: settle spend` has no corresponding append, and every `EvidenceRequest` fulfilment under AD-4 spends money before any decision row exists for the step it belongs to.

Two implementers will resolve this in the two obvious ways — one appends `reservation` and `settlement` as first-class log entries and folds them; the other keeps a live ledger object and appends only decisions. Both believe they obey the spine. Their logs are not comparable, their folds do not agree, and FR68 re-execution produces different numbers. This is a divergence in the exact component the falsifiable claim (§1.4) is computed from.

**Compounding: AD-3 permits parallel execution but not parallel settlement ordering.** "The host may execute approved steps in parallel; it may not obtain verdicts in parallel" fixes decision order. It does not fix *settlement* order, and settlements change `spent`/`remaining`, which feed the next decision's affordability test. Two runs with identical decision sequences and identical work can therefore produce different `remaining` at decision *n* purely from completion interleaving — a determinism hole under NFR3/FR68 that AD-3's own *Prevents* clause ("a partially ordered log that cannot be replayed deterministically") claims to have closed.

**Recommended resolution:** one clause in AD-2 or AD-3 stating that reservations and settlements are themselves appended log entries, and that settlement entries are appended in a deterministic order (e.g. by step id, not by completion time).

### 7b — HIGH: The redaction boundary contradicts itself on evidence capsules (AD-5 × AD-19 × FR37/FR38/FR71)

AD-5 bars "raw prompts, tool arguments and tool results" from the decision log, then lists what may cross: "scores, estimates, envelopes, **capsules**, canonical keys and content hashes," and concludes "Durable raw content lives solely in the evidence store (AD-19)."

But FR38 requires a capsule to preserve "citations, identifiers, numeric values, policy clauses and any contract-required attributable fact **verbatim**," and FR71 measures exactly the rate at which that verbatim content survives. A capsule is therefore, by requirement, a container of verbatim excerpts of raw tool output. Admitting capsules into the decision log while asserting that raw content lives *solely* in the evidence store is a contradiction, and it is a privacy contradiction (NFR5) rather than a bookkeeping one: the durable record now contains the verbatim policy clauses and identifiers the redaction rule was written to keep out.

Related ambiguity in the same pair: AD-19 says raw tool outputs live in the evidence store because "FR70 re-execution and FR71 fidelity measurement require" them. FR71 compares raw output against the capsule — so the harness must read both. If the capsule is in the log (AD-5) and the raw is in the evidence store (AD-19), the fidelity measurement spans both stores, which is fine but unstated; if the capsule is in the evidence store, then AD-5's list of what crosses into the record is wrong. Pick one.

**Recommended resolution:** state that capsules are persisted to the evidence store and that only a capsule *reference plus content hash* crosses into the decision log — which preserves AD-5's premise, keeps FR6 replayability (the hash pins the input), and leaves FR71 reading one store.

### 7c — HIGH: Shadow mode's overhead and approval behaviour are unspecified (AD-11 × AD-4 × AD-12 × AD-20)

AD-11's Rule is: "The Policy is unchanged and always decides as if enforcing. A shadow driver records each decision and **declines to apply it**. FR91's exemption is the single statement that the driver applies no halts."

Three things follow that the Rule does not address:

1. **`EvidenceRequest` fulfilment costs real money on a run whose value is that it did not change anything.** AD-4 makes the driver the fulfiller of every `EvidenceRequest` — rubric judgements, compression passes, complexity and confidence estimates, planner envelopes — and AD-4 further requires *every Quality Gate execution under FR98* to be debited. In shadow, the Policy must still decide as if enforcing, so it must still receive these. Does the shadow driver fulfil them? If yes, the governor is spending real tokens against a run that FR48 says is the **executed ungoverned path** — the one path that is actually observed, and therefore the one whose token count is evidence. The observed baseline is then contaminated with governor overhead. If no, the Policy is deciding on absent inputs, which contradicts "the Policy is unchanged." The spine bars the *counterfactual* ledger from reportability (good) but says nothing about the observed ledger, which is the one that carries measurement weight.
2. **Approval is unaddressed.** FR91 says shadow shall not "halt, **pause** or otherwise alter the host under any condition." AD-11 renders FR91 as "the driver applies no **halts**" — narrower than FR91. AD-12 makes approval a port call; whether the shadow driver calls `ApprovalPort` (and blocks on a scripted decider) is undetermined. A shadow driver that calls the approval port and waits has violated FR91 while obeying AD-11.
3. **AD-20's interaction is undefined.** "The shadow driver applies neither" covers fail-open and fail-closed at the halt level. But fail-open's mechanism is *deregistering an advisor and appending a `degraded` event* — that is a log mutation, not a halt, so presumably it does apply in shadow. Stating so would remove the ambiguity, since AD-20's sentence currently reads as though shadow applies no failure posture at all.

This is the gap most likely to be discovered late, because F10 is protected and will be built, and because the contamination in (1) is invisible until someone asks why the shadow baseline is more expensive than the OFF baseline.

### 7d — MEDIUM: Testing strategy is a silent dimension, and replay-equivalence in particular has no owner

The spine contains `tests/` in the source seed and AD-15's adapter conformance battery. Neither is a testing strategy, and AD-15 is a *product* obligation (an adapter that has not passed cannot produce a reportable run), not a statement about how the system is verified.

The specific hole: **replay is asserted three ways and defined nowhere as a testable property.** AD-2 says state is a fold; AD-4 says "replay is therefore feeding recorded outcomes back into a pure advisor"; NFR3/FR6/FR68 require reproducibility. But what does it mean for a replay to *match*? Byte-identical decision rows? Identical `policy_action`/`decision_reason`/`terminal_reason` sequence? Identical ledger fold? Two units will pick different equivalence relations, and the harness's FR68 refusal ("any reported run SHALL be re-executable from its recorded configuration") will mean different things in each. Given that replay is the mechanism three separate PRD guarantees rest on, its equivalence relation is an initiative-altitude decision, not a code-owned one.

Secondary: nothing states the boundary between what is tested against the pure core versus against the decision log. AD-15 gets this exactly right for adapters ("asserted **against the resulting decision log**, never against adapter internals") — that same principle, generalised in one convention row, would cover the dimension.

### 7e — MEDIUM: Reportability contradicts the deployment diagram, and APIM configuration is unpinned (AD-10 × AD-9 × AD-13 × deployment seed)

Two separate problems in the same seam.

**The contradiction.** AD-10's Independence gate is explicitly graded: "Where metering is unavailable the run falls back to governor-side counting and every figure it yields is labelled **self-reported** (FR80) — the stated independence is downgraded, **the run is not discarded**." This is the correct reading of FR80. But the deployment diagram states the opposite for the same situation:

```
P1 -.->|dev and demo only, never reportable| AOAI
```

If APIM is unavailable and the run goes direct to the model endpoints, AD-10 says label it self-reported and keep it; the diagram says it is never reportable. A reader cannot tell whether the direct route degrades a run or disqualifies it, and AD-10 explicitly reserves hard refusals for the *admissibility* gate — where "both arms of a comparison used the same route" already lives. Two-arm route parity and per-arm route legality are different rules and are currently in conflict.

**The unpinned dependency.** AD-13's insight is that "a pricing change between calibration and evaluation would silently move the cost figure," so the cost table is pinned and recorded in the manifest. The identical argument applies to APIM: `llm-token-limit` and `llm-emit-token-metric` are policy configuration, and a change to either between calibration and evaluation moves the metered token figure — the number FR78 exists to make independent. AD-9's manifest records `route (apim | direct)` but not the APIM policy or configuration version, and no AD or convention says how the APIM instance is provisioned reproducibly. The spine catches the risk for LiteLLM's cost table and misses the structurally identical risk one hop upstream.

### 7f — MEDIUM: Who invokes advisors — the Policy or the driver? (AD-4 × "One decision" diagram)

AD-4 writer 2: "The **driver** is the only component that performs port calls. It fulfils an `EvidenceRequest`, appends the outcome, **then re-invokes the advisor** with the result."

The sequence diagram: `P->>M: request proposals` / `M-->>P: proposals with estimates and reason codes`.

So the Policy invokes advisors, and the driver also invokes advisors. Either the `EvidenceRequest` travels advisor → Policy → driver → advisor (a four-hop cycle the diagram does not show), or the driver owns advisor invocation and the diagram's `P->>M` is wrong. The `EvidenceRequest` cycle is the single most distinctive mechanism in AD-4 and the sequence diagram — the one artifact whose job is to show *one decision* — omits it entirely. Two units will wire this differently, and the wiring decides where the re-invocation loop's termination condition lives (nothing currently bounds how many `EvidenceRequest` rounds a single decision may take, which is a Loop Fuse concern the Loop Fuse does not cover).

### Pairs checked and found consistent

Worth recording explicitly, since the brief asked for these specifically:

- **AD-2 × AD-16** — "append-only" and "the log is the record" agree; AD-16 correctly discharges NFR12 by whole-file operations rather than by row deletion, which would have contradicted AD-2.
- **AD-16 × AD-19** — one DB per run and a separate evidence store do not conflict; AD-19's "Nothing in the evidence store may be cited as a decision input" is the clause that keeps them separable, and it is well placed.
- **AD-5 × AD-19** on *raw* content — consistent (the capsule problem in 7b is the only breach).
- **AD-4 × AD-20** on **degraded ≠ disabled** — genuinely consistent and well argued. Runtime deregistration produces the same registry state as ablation, which would have been a real trap; the spine anticipates it and resolves it with the manifest recording the start-state and the log recording deregistrations. This is the document at its best.
- **AD-1 × AD-11** — "the adapter applies the returned verdict" and "the shadow driver declines to apply" do not conflict, because the decline happens at the driver, above the adapter. Correct layering.
- **AD-9 × AD-10** — the manifest's field list is a superset of what admissibility checks; no gap.
- **AD-10 × AD-17** — the viewer renders and does not re-derive; FR97's computation stays in F13. Consistent, and it correctly protects F16 from F14's cut position.
- **AD-3 × AD-14** — run-scoped cache and per-run decision lane reinforce each other.
- **AD-7 × AD-18** — the closed verifier registry and the Policy-held floor carve-out are independent and non-overlapping.

---

## Item 8 — Are the Mermaid diagrams valid and structural?

**Rating: Concern (minor).** All five parse. Syntax is clean: `subgraph id[Label]` forms are correct, `[( )]` cylinder nodes are correct, the `sequenceDiagram` participant aliases and `-->>` returns are correct, and the `erDiagram` cardinality tokens (`||--|{`, `}o--||`, `||--o{`) are all valid and — unusually — semantically right rather than copied. Edge labels with commas and pipes (`-->|dev and demo only, never reportable|`) are legal.

**Do they convey structure?** Four of five earn their place:

- **Layer diagram** — conveys the dependency direction that the layer table asserts, including the non-obvious `IMPL --> CORE` (implementations depend on the core, not the reverse). This is the one thing a hexagonal-architecture reader needs to check, and the diagram makes it checkable.
- **System view** — conveys the process boundary, the two-store split (DB and evidence store as distinct cylinders), and the fact that the blind packet and the HTML come off different paths. Structural.
- **Core entities** — the most load-bearing of the five. `CRITERION }o--|| VERIFIER_TYPE : selects` encodes AD-7 in one line, and `RUN ||--|| RUN_MANIFEST : opens_with` encodes AD-9's "first entry of every run." Genuinely conveys the invariants.
- **Deployment** — conveys the two-environment decision and the reportable/non-reportable route distinction. Structural, but see the contradiction in 7e and the App Insights point below.

**(8a) The "One decision" sequence diagram under-conveys, and is where two of the contradictions surface.** It is the diagram with the most to explain and it omits the `EvidenceRequest` cycle entirely (7f), shows ledger mutation without log append (7a), and shows the Policy calling advisors in a way AD-4 does not describe. A reader reconstructing AD-4 from this diagram would build the wrong thing. Since this diagram is seed rather than invariant, the fix is either to add the cycle or to trim the diagram to what it can show correctly.

**(8b) Application Insights appears only in the deployment diagram.** `APIM --> AI[Application Insights]` introduces a telemetry sink that no AD, no convention, no Deferred entry and no open question mentions. Given AD-8 defers OpenTelemetry export and the Conventions state that application logs "carry no decision authority," a reader cannot tell whether App Insights is (i) incidental APIM plumbing, (ii) where `llm-emit-token-metric` lands and therefore part of the FR78 evidence path, or (iii) decoration. If it is (ii) — which the metric-emission policy name suggests — then it is on the evidence path for the product's independence claim and belongs in AD-13 or AD-10, not only in a diagram. This is the one place a diagram carries an undeclared decision.

---

## Consolidated findings

| # | Finding | Item(s) | Severity |
|---|---|---|---|
| F-1 | Ledger reserve/settle mutate state outside the log, contradicting AD-2's fold-of-log rule; settlement ordering under AD-3's permitted parallelism is undetermined, breaking replay determinism | 7a, 1, 2, 5 | **Critical** |
| F-2 | AD-11 exempts only halts: shadow-mode `EvidenceRequest` spend executes for real against the observed ungoverned path (contaminating the only measured path), and `ApprovalPort` behaviour in shadow is unspecified against FR91's "shall not pause" | 7c, 2c, 5 | **High** |
| F-3 | AD-5 admits capsules into the decision log while barring raw tool results, but FR38 requires capsules to carry verbatim attributable facts; store placement conflicts with AD-19 | 7b, 5 | **High** |
| F-4 | AD-10's graded "self-reported" degradation contradicts the deployment diagram's "never reportable" direct route; AD-9 pins the cost table but not the APIM policy/configuration version that produces the metered figure | 7e, 6 | **Medium-High** |
| F-5 | Testing strategy is a silent dimension; replay-equivalence has no defined relation despite NFR3/FR6/FR68 all resting on it | 7d, 6 | **Medium** |
| F-6 | AD-4 leaves Quality Gate overhead unattributed ("attributed to the requesting mechanism" has no referent for FR98 cadence executions), undermining FR15 and FR62 | 2d, 5 | **Medium** |
| F-7 | F5's progress fingerprint is a hash outside AD-6's enumerated scope yet forbidden by AD-6's absolute closing sentence; F5 maps to AD-2/AD-4 only | 1a, 5, 7 | **Medium** |
| F-8 | AD-4 (driver invokes advisors) and the sequence diagram (Policy invokes advisors) disagree; the `EvidenceRequest` cycle is undrawn and unbounded | 7f, 8a | **Medium** |
| F-9 | AD-20 does not place the FR20 rubric signal's failure posture — fail-open advisor or fail-closed gate | 2e | **Medium** |
| F-10 | FR98 gate cadence is owned by no AD Rule, though two drivers (enforcing, shadow) must implement it identically | 1b | **Medium** |
| F-11 | NFR8 domain neutrality has no rule or convention; purity is fixed, neutrality is not | 1c, 6 | **Medium** |
| F-12 | NFR12's *declared retention period* has a mechanism (whole-file delete) but no declared home; evidence-store granularity (per-run?) unstated | 6 | **Low-Medium** |
| F-13 | Application Insights appears only in a diagram; if it is where `llm-emit-token-metric` lands it is on the FR78 evidence path and needs an invariant | 8b, 6 | **Low-Medium** |
| F-14 | Python 3.14 floor asserted against three third-party agent frameworks with no per-adapter hedge; AD-8's OTel status claim is an assertion inside a Rule; §9's preview-stage fallback is satisfied only implicitly by `adapters/host/reference/` | 4 | **Low** |
| F-15 | AD-1 contains a slogan ("interception and loop-driving are adapter strategies, not architectures") that is not pointable-at; AD-3 ends with a measurement convention rather than an invariant | 2a, 2b | **Low** |
| F-16 | FR79 reconciliation has no defined discrepancy tolerance; NFR7 least-privilege tool identity is untouched | 1d, 6 | **Low** |

---

## What this spine does better than most

Recorded because a review that only lists defects misrepresents the artifact.

1. **AD-19 is a structural solution to a methodological problem.** Most documents would have written "the blind reviewer shall not see the verdict" and called it a protocol. Denying the renderer *access* makes FR69 hold even when the person running it wants it not to — which, per the PRD's own `[NOTE FOR PM]` on Q4/Q6/Q8, is the actual threat model.
2. **AD-10's three-way split** correctly distinguishes rules that refuse from rules that degrade a label. Collapsing those — which is the default mistake — would have made FR80 unimplementable or FR102 toothless.
3. **AD-4's "disabled means not registered"** turns FR62's ablation from a test-mode branch into a registry change, and states the consequence precisely ("byte-identical to having cut the mechanism"). That single sentence removes an entire class of "does the ablation really ablate?" objections.
4. **AD-7 caught a security hole the PRD created and did not see.** FR8's wording admits arbitrary callables; AD-7 closes it without weakening FR8's intent, and derives FR21's qualifier from the registry entry rather than from a second assertion.
5. **The Open Questions are honest.** Q-A names a commitment the PRD's own cut order does not cover and recommends a specific fix with an owner and a revisit trigger. Q-B admits AD-15 creates unestimated work rather than hiding it inside an AD. Both are the kind of thing spines usually omit.

---

## Recommended disposition

**Return for a targeted revision, not a rewrite.** F-1 through F-4 are the gate. All four are resolvable in roughly six sentences distributed across AD-2/AD-3, AD-11, AD-5 and AD-10/AD-9 respectively, plus one edit to the "One decision" diagram. F-5 through F-11 should be resolved in the same pass since they are each a sentence. F-12 through F-16 can be carried as open questions or absorbed at epic definition.

The spine should not be re-scoped, re-paradigmed or expanded. Its terseness is earned, its paradigm choice is correct for the problem, and the majority of its ADs are the right invariants stated at the right altitude.
