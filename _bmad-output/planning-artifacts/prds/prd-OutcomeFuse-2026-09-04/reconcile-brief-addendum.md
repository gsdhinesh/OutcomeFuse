---
title: "Reconciliation — Brief Addendum → PRD"
status: draft
created: 2026-09-04
source: ../../briefs/brief-OutcomeFuse-2026-09-02/addendum.md
derived: ./prd.md
---

# Reconciliation: Brief Addendum → PRD

Mechanism-by-mechanism check of every documented behaviour in the brief addendum (§1 component specifications, §3 evaluation methodology, §6 Responsible AI and security posture, §8 build sequencing) against the PRD's functional requirements FR1–FR73 and NFR1–NFR11.

**Excluded by instruction:** production-stack technology choices (§2), parked extensions (§7), demo narrative (§5), supply-chain workload detail (§9), alternatives considered (§4). Also excluded: capacity estimates and build ordering, which are plan artifacts rather than requirements — except where a sequencing item states a normative rule (rubric freeze), which is checked.

---

## Part A — Component specifications (§1)

### A.1 Outcome Contract — no gaps

All eight declared fields (`task_goal`, `quality_floor`, `max_tokens` / `max_estimated_cost`, `allowed_tools`, `max_tool_calls`, `max_iterations`, `escalation_policy`, `human_approval_conditions`) are enumerated in FR6. Contract validation, immutability and versioning (FR7, FR8) exceed the source. **Carried in full.**

One consequential caveat is filed as gap **G1** below: `human_approval_conditions` is accepted as a field but no requirement obliges the runtime to act on it.

### A.2 Preflight Planner — no gaps

| Source behaviour | PRD |
|---|---|
| Generates a small, typed execution graph | FR37 |
| Assigns an estimated token/tool envelope per step | FR37 |
| Separates mandatory evidence from optional enrichment | FR38 |
| Planner is itself a model pass; envelope must be measured, not assumed negligible | FR39, NFR2 |

**Carried in full.**

### A.3 Budget Ledger

| Source behaviour | PRD |
|---|---|
| Maintains `allocated`, `spent`, `reserved`, `remaining` | FR11 |
| Protected reserve for final synthesis and quality verification | FR12 |
| Rejects a proposed step when expected benefit is low, duplicated, unsafe, or unaffordable | FR14 (partial — see **G2**, **G3**) |

---

#### G2 — Marginal-value rejection has no requirement — **HIGH**

> **Source (§1, Budget Ledger):** "Rejects a proposed step when expected benefit is **low**, duplicated, unsafe, or unaffordable"

FR14 carries exactly one of the four rejection grounds: *unaffordable* — "The ledger SHALL reject a proposed step that is unaffordable within `remaining` less `reserved`." *Duplicated* is carried elsewhere, at the tool layer (FR27). *Low expected benefit* and *unsafe* have no FR anywhere in FR1–FR73.

**Why it matters.** Low-expected-benefit rejection is not a peripheral ledger feature — it is the operational form of the PRD's own headline question. §1.1 states the product is a policy that "asks one question: is another unit of work worth paying for." FR1 requires the policy to "evaluate whether that unit is justified given the contract, the ledger state and the most recent quality assessment," but names no criterion by which marginal benefit is judged and no obligation to deny on that ground. As written, the only grounds a builder is required to implement are affordability, duplication, evidence sufficiency and loop-progress — all of which are variants of *exhaustion* or *repetition*. That is precisely the category the PRD distinguishes itself from in §1.3: "every existing mechanism stops a run when it runs out. OutcomeFuse stops a run when it is done." Without a marginal-value denial requirement, the differentiating behaviour is asserted in the vision section and unspecified in the requirements.

**Partially mitigated:** §4.2 places "learned marginal-value estimation" out of scope. That correctly excludes the *learned* variant; the source describes a heuristic rejection rule, which is not excluded and not required either. The gap is that the heuristic floor was dropped along with the learned ceiling.

---

#### G3 — Rejection of unsafe steps has no requirement — **MEDIUM**

> **Source (§1, Budget Ledger):** "Rejects a proposed step when expected benefit is low, duplicated, **unsafe**, or unaffordable"

No FR permits or requires denial of a proposed step on safety grounds. FR1's decision vocabulary includes `deny`, but no requirement establishes unsafety as a ground for it. The nearest PRD content is a secondary metric — "Zero accepted safety or adherence regressions" (§3.2) — which measures an outcome without specifying the mechanism that produces it, and §9's human-control bullet, which is permissive (`MAY`).

**Why it matters.** A metric with no corresponding requirement cannot be satisfied by construction, only by luck. The counter-metric will be reported against a system that has no specified safety-denial path. See also **G7** (safety evaluators).

---

### A.4 Context Governor — no gaps

| Source behaviour | PRD |
|---|---|
| Selects only evidence needed for the current step | FR30 |
| Compresses tool output into structured evidence capsules | FR31 |
| Preserves citations, identifiers, numbers, policy clauses verbatim | FR32 |
| Compression must never drop an attributable fact | FR32, §9 |

**Carried in full.** LLMLingua candidacy is an implementation choice, correctly downstream.

### A.5 Model Governor

| Source behaviour | PRD |
|---|---|
| Starts on the lowest-cost eligible model | FR34 |
| Escalates on task complexity | FR35 |
| Escalates on **low confidence** | *(absent — **G4**)* |
| Escalates on policy criticality | FR35 |
| Escalates on a failed quality evaluation | FR35 |
| Escalation disclosed, never silent | FR36 |

---

#### G4 — "Low confidence" dropped as an escalation trigger — **MEDIUM**

> **Source (§1, Model Governor):** "Escalates on task complexity, **low confidence**, policy criticality, or a failed quality evaluation"

FR35 reproduces three of the four triggers verbatim and omits low confidence: "The system SHALL escalate model capability only on task complexity, policy criticality, or a failed quality evaluation."

**Why it matters.** The omission is load-bearing because FR35 is written as a closed list — "**only** on" — so the drop is not a silent narrowing but an active prohibition. The three surviving triggers are all *post hoc* or *static*: complexity and criticality are known before the step, a failed evaluation is known after the work has already been paid for. Low confidence is the only trigger that fires *during* a step, before the spend on a likely-failing cheap-model attempt is sunk. Removing it means every low-confidence path must be paid for at the cheap model, fail the gate, then be paid for again at the escalated model — the retry cost the Model Governor exists to avoid.

If the drop is deliberate (confidence signals being unreliable, or the deterministic-gate stance in FR17 extending to model self-report), that reasoning should be stated, because the source lists it and a reader comparing the documents will read the absence as an oversight.

---

### A.6 Tool Governor

| Source behaviour | PRD |
|---|---|
| Canonicalizes tool name plus arguments into a stable key | FR25 |
| Reuses cached deterministic results | FR26 (narrowed — **G9**) |
| Prevents duplicate calls | FR27 |
| Prevents **semantically equivalent** calls | *(absent — **G5**)* |
| Rejects optional calls once sufficient evidence acquired | FR27 |
| Measurable via tool-use evaluators | *(absent — **G6**)* |

FR28 (no caching or denial for side-effecting/non-deterministic tools) and FR29 (recorded reasons) are PRD additions beyond the source and are sound.

---

#### G5 — Semantic-equivalence deduplication absent — **MEDIUM**

> **Source (§1, Tool Governor):** "Prevents **duplicate and semantically equivalent** calls"

FR27 covers exact duplicates only: "The system SHALL deny **exact** duplicate calls." Semantic equivalence — the same query expressed differently, or a call whose result is already derivable from cached evidence — has no requirement.

**Why it matters.** Exact-duplicate denial is the weakest form of the mechanism and the one an agent loop least often triggers, because a re-issued call usually carries drifted phrasing or a widened parameter. The realistic waste mode described in §1.2 — "the same query is reissued because nothing remembers it was answered" — is mostly semantic, not literal. Restricting to exact match may materially reduce the achievable tool-call reduction against the ≥ 30% target in §3.1, which was carried over from source figures that presumably assumed the fuller mechanism.

**Partially mitigated:** §4.3 lists "Semantic optimization" at cut position 4. But a cut-order entry for something that has no FR is not a scoped-then-deprioritized item — there is nothing to cut. Either add an FR and let the cut order govern it, or state plainly that the mechanism is not in scope and re-examine whether the tool-call target still holds.

---

#### G6 — Tool-use quality evaluation absent from the Quality Gate — **HIGH**

> **Source (§1, Tool Governor):** "Measurable via Tool Selection, Tool Call Accuracy, Tool Output Utilization, Tool Call Success, and Task Navigation Efficiency evaluators"
>
> **Source (§1, Quality Gate):** "Evaluates task completion, task adherence, groundedness / evidence coverage, and **tool-use quality**"
>
> **Source (§3, Method):** "Combine rubric, task-completion, adherence, and **tool evaluators** on top"

Tool-use quality is named three separate times in the source — once as a Tool Governor measurement surface, once as a Quality Gate evaluation dimension, once as an evaluation-methodology requirement. It appears in none of FR16, FR17, FR21, FR51–FR59, or §8. FR16 evaluates "deliverable completeness, presence and accuracy of required evidence fields, and task adherence"; FR53 counts tool calls but does not assess them.

**Why it matters.** This is a counter-metric hole, not a missing nice-to-have. The Tool Governor's entire contribution to the savings figure is *calls not made*. With no evaluator for tool selection quality or output utilization, the system cannot distinguish a denied call that was genuinely redundant from a denied call that was necessary and whose absence quietly degraded the answer. The PRD is otherwise scrupulous about this failure mode — §3.3 builds an entire counter-metric apparatus around premature stopping — but applies it only to the Quality Gate's stop decision, not to the Tool Governor's deny decision. Both are "we spent less because we did less"; only one is instrumented.

Note that **groundedness / evidence coverage** is likewise not named in FR16. It is arguably subsumed by "presence and accuracy of required evidence fields," which is a defensible narrowing to a deterministic check consistent with FR17 — flagged here as a **LOW** observation rather than a separate gap, on the condition that "accuracy" is understood to mean *attributable to retrieved evidence*, not merely *matching the golden value*.

---

### A.7 Loop Fuse — no gaps

| Source behaviour | PRD |
|---|---|
| Progress fingerprint: evidence gained, task state changed, quality delta | FR22 |
| Halts on repeated state, no new evidence, repeated tool arguments, budget exhaustion, iteration limit | FR23 |
| Loops must always be bounded | FR23, FR24 |

**Carried in full**, and strengthened: FR24's requirement that a no-progress halt be reported as distinct from a sufficiency stop is a PRD addition that the source only implies.

### A.8 Quality Gate

| Source behaviour | PRD |
|---|---|
| Evaluates task completion | FR16 |
| Evaluates task adherence | FR16 |
| Evaluates groundedness / evidence coverage | FR16 (partial — see note in **G6**) |
| Evaluates tool-use quality | *(absent — **G6**)* |
| `pass` → stop immediately | FR18 |
| `fail` + budget → targeted retry or model escalation | FR19 |
| `fail` + no safe budget → partial disclosure or human intervention | FR19 |
| Combine bespoke rubric with built-in quality **and safety** evaluators | FR17 (quality only — **G7**) |
| Report pass/fail counts and **per-model token usage** | FR52 (counts), FR53 (partial — **G8**) |

---

#### G7 — Built-in safety evaluators absent — **MEDIUM**

> **Source (§1, Quality Gate):** "Combine bespoke rubric evaluators with built-in quality **and safety** evaluators"

FR17 establishes deterministic field validation as authoritative and admits a model-judged rubric as an advisory signal. Neither FR17 nor any other requirement provides for safety evaluation of the produced deliverable.

**Why it matters.** §3.2 carries "Zero accepted safety or adherence regressions" as a secondary metric and §11.2's differentiation posture depends on the claim that optimization never degrades output. Adherence is covered (FR16). Safety is not measured anywhere, so the "zero safety regressions" claim has no instrument behind it and cannot be substantiated at report time. Pairs with **G3**: no safety denial path, no safety evaluation.

---

#### G8 — Per-model token usage not required in reporting — **LOW**

> **Source (§1, Quality Gate):** "report pass/fail counts and **per-model token usage**"

FR53 captures "model and version, tokens" per run. Where a run escalates mid-execution (FR35), a single model field and a single token total cannot express the split between the cheap-model portion and the escalated portion.

**Why it matters.** The Model Governor's savings contribution is precisely the ratio of cheap-model to premium-model tokens. Without a per-model breakdown, F8's individual value cannot be isolated from the aggregate — which matters more than usual here, because F8 sits at cut position 5 and the decision to cut it should rest on its measured contribution.

---

#### G9 — Deterministic-cache reuse narrowed to a single run — **LOW**

> **Source (§1, Tool Governor):** "Reuses cached deterministic results" *(unscoped)*

FR26 adds a boundary the source does not state: "within the scope of a single run."

**Why it matters.** Defensible and probably correct for an in-process MVP, and it sidesteps the cross-run staleness and isolation problems NFR6 would otherwise have to handle. Recorded because the narrowing is silent — a reader of both documents should be told it was a decision, not an omission, and because cross-run reuse is where the production savings story is strongest.

---

## Part B — Responsible AI and security posture (§6)

| Source item | PRD |
|---|---|
| Quality floor outranks budget | FR9, FR19, FR20, §1.5, §9 |
| **Human control — approval required for side-effecting or high-impact tools** | *(weakened — **G1**)* |
| Transparency — record why every call was blocked, cached, compressed or escalated | FR29, FR47, FR49, §9 |
| Privacy — redact prompts, tool arguments, results before telemetry | NFR5, FR50 |
| Privacy — **production-grade access and retention controls on traces** | *(absent — **G10**)* |
| Identity — managed identities, least-privilege tool access | NFR7 |
| Cache isolation — tenant and use-case partitioning, no cross-user reuse | NFR6 |
| No hidden quality substitution | FR36, §9 |
| Preview awareness — pin stable fallbacks, state honestly | FR68, §9 |

---

#### G1 — Human approval for side-effecting tools is declared but never enforced — **CRITICAL**

> **Source (§6, Human control):** "Approval **required** for side-effecting or high-impact tools."

The PRD carries this in two places, both non-binding:

- FR6 lists `human_approval_conditions` as an accepted contract field, with no requirement that anything read it.
- §9 restates the item permissively: "The contract **MAY** require human approval for side-effecting or high-impact tools."

No requirement in FR1–FR73 obliges the runtime to suspend execution and obtain approval before invoking a tool that matches the contract's approval conditions. FR1's decision vocabulary includes `request-human`, but the only requirement that triggers it is FR19 — quality-floor failure with no safe budget. Approval-gated tool invocation is a different trigger and has none.

**Why it matters.** Three compounding reasons:

1. **A contract field with no enforcement requirement is a latent defect.** FR6 makes the field mandatory to accept and FR7 requires contract validation, so the MVP will accept, validate and store approval conditions it is under no obligation to honour. Silent non-enforcement of a declared safety control is worse than not offering the field.
2. **It is the one Responsible AI item the PRD downgraded rather than carried.** Every other §6 item survives as `SHALL` (FR9, FR29, FR32, FR36, NFR5, NFR6, NFR7) or as a stated posture. This one alone went from "required" to `MAY` — and `MAY` in a document that uses RFC-style keywords throughout is a real reduction in force, not stylistic drift.
3. **It is the mechanism protecting against the governor's own worst failure mode.** The system is explicitly designed to deny, cache and substitute tool calls autonomously (FR26–FR28). FR28 exempts side-effecting tools from *caching and denial*, which prevents the governor from suppressing a needed side-effect, but nothing prevents the loop from *invoking* a high-impact tool unapproved. Compliance review (§2.3, UJ-3) will ask for this specifically, and the PRD's own audit journey has no approval event to show.

**Suggested remedy.** An FR under F2 or F1 to the effect: *Where a tool invocation matches the contract's declared human-approval conditions, the system SHALL suspend execution, emit `request-human`, and SHALL NOT invoke the tool until approval is recorded. The approval decision and its actor SHALL be written to the decision record.* Then restore §9 to `SHALL`.

---

#### G10 — Trace access and retention controls absent — **MEDIUM**

> **Source (§6, Privacy):** "Redact prompts, tool arguments, and results before telemetry; traces can contain sensitive input and tool data and need **production-grade access and retention controls**."

NFR5 carries the redaction half in full and paraphrases the second half without a requirement: "Traces can contain sensitive input and tool data and SHALL be treated accordingly." *Treated accordingly* is not testable — it names no access control, no retention period, no deletion obligation.

**Why it matters.** F12 requires the decision record to be persisted, queryable and **exportable** (FR48) and complete enough to reconstruct a run (FR49). The PRD therefore mandates a durable, exportable, high-fidelity artifact of every run while leaving its access and lifecycle unspecified. Redaction reduces the sensitivity of that artifact but does not eliminate it — ledger states, contract clauses, evidence field names and tool identities remain. NFR9 restricts MVP evaluation to synthetic data, which contains the immediate risk to the MVP but does not discharge the requirement, since the same record format is the production audit surface for §2.3's compliance persona.

---

## Part C — Evaluation methodology (§3)

| Source rule | PRD |
|---|---|
| Freeze baseline: prompt, tools, dataset, model version, temperature, settings | FR56, §8.1 |
| Baseline is a reasonable agent: full context, one capable model, conventional evaluator/retry loop with max-iteration limit | §8.1 |
| Run baseline and governed on the same frozen dataset, with repeats per case | FR51, FR52 |
| Capture model/version, tokens, cached tokens, tool calls, retries, duration, outcome | FR53 |
| Deterministic field-level validation preferred over model-judged scoring | FR17, §8.2 |
| Combine rubric, task-completion, adherence **and tool evaluators** | FR16, FR17 (tool evaluators absent — **G6**) |
| Report mean, median, pass rate | FR52 |
| Publish failures and escalations | FR55, §8.3 |
| Report governor overhead as a separate line item; gross and net both visible | FR54, NFR2, §8.3 |
| Prompt caching: measured secondary lever, not attributable to OutcomeFuse; `cached_tokens` visibility | §8.3, FR53 |
| Small-sample caution: absolute pass counts alongside percentages | FR52, §8.3 |
| Preview-stage dependencies; APIM metering must have a governor-side fallback that degrades independence rather than blocking | FR68, §9 |
| Original gross targets superseded; net targets replace once overhead measured | §3.1 restatement gate |
| **Rubric frozen before governor work begins** (§8 sequencing step 1) | §8.2 |

**Assessment.** Part C is the most faithfully carried section of the source. The PRD promotes these from methodology notes to normative requirements (its §8 preamble says so explicitly) and in several places strengthens them — FR56's requirement that the harness *refuse* a comparison on baseline drift has no source equivalent, and FR59's blind-review protocol goes beyond anything in the addendum. The single gap is tool evaluators, already filed as **G6**.

One observation, not a gap: the source's rubric-freeze rule appears in §8.2 of the PRD as a `SHALL` but carries no FR identifier, so it does not appear in the requirement index. Given §8's stated normativity this is likely intentional; noting it in case the index is later treated as the complete requirement set.

---

## Part D — Build sequencing (§8)

Sequencing, capacity estimates and ordering are plan content and generate no requirements. The two items in §8 that state normative rules are both carried:

- "Freeze scenario and quality rubric — before any governor work, to avoid rubric circularity" → §8.2, §11.2 rubric-circularity risk row.
- "Add shadow mode — a non-enforcing flag over the existing decision path" → FR40–FR43. Note the source's design constraint that shadow mode is *a flag over the existing decision path* rather than a parallel implementation is not explicitly required; FR41's same-shape requirement approximates it. **LOW**, recorded without a gap number.

No gaps.

---

## Summary table

| # | Gap | Source section | Severity |
|---|---|---|---|
| G1 | Human approval for side-effecting/high-impact tools declared in FR6 but never enforced; §9 downgrades "required" to `MAY` | §6 Human control | **Critical** |
| G2 | Ledger rejection on low expected benefit — the marginal-value judgement — has no FR; FR14 covers affordability only | §1 Budget Ledger | **High** |
| G6 | Tool-use quality evaluation absent from Quality Gate and harness; no counter-metric on denied calls | §1 Tool Governor, §1 Quality Gate, §3 Method | **High** |
| G3 | Rejection of unsafe steps has no FR | §1 Budget Ledger | Medium |
| G4 | "Low confidence" dropped from FR35's closed list of escalation triggers | §1 Model Governor | Medium |
| G5 | Semantically equivalent tool-call prevention has no FR; cut-order entry with nothing to cut | §1 Tool Governor | Medium |
| G7 | Built-in safety evaluators absent; "zero safety regressions" metric has no instrument | §1 Quality Gate | Medium |
| G10 | Trace access and retention controls unspecified; NFR5's "treated accordingly" is untestable against exportable FR48 records | §6 Privacy | Medium |
| G8 | Per-model token usage not required in FR53 reporting | §1 Quality Gate | Low |
| G9 | Deterministic cache reuse silently narrowed to single-run scope | §1 Tool Governor | Low |

**Coverage note.** Of roughly forty discrete documented behaviours across the four in-scope sections, thirty are carried in full and several are strengthened beyond the source. The Preflight Planner, Context Governor, Loop Fuse and Outcome Contract are complete. Concentration of gaps is uneven and informative: the Tool Governor accounts for four, and the human-control item is the only Responsible AI commitment that lost normative force in translation.
