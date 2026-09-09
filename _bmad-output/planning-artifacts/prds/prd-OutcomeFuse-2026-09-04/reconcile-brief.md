---
title: "Reconciliation — Brief → PRD"
status: draft
created: 2026-09-04
source: "briefs/brief-OutcomeFuse-2026-09-02/brief.md (+ its addendum)"
derived: "prds/prd-OutcomeFuse-2026-09-04/prd.md, addendum.md"
---

# Reconciliation: what the brief carries that the PRD dropped or distorted

Scope note: deliberate decisions are **not** counted as gaps here. Excluded from findings — MVP-only framing, contract authoring scoped out (FR10), net numeric targets stripped pending the overhead study, and Q5's resolution of F14 from live streaming to replay (recorded as a decision with rationale).

Findings are ordered by severity.

---

## CRITICAL

### G1 — The Vision is missing entirely, including the product's moral/positioning stance

The PRD's own preamble promises: _"The longer product vision appears only as context; it generates no requirements here."_ It then never appears. §1 is titled "Vision & Positioning" and contains only positioning.

What the brief said:

> "If this works, declaring an outcome contract becomes as ordinary as declaring a timeout. Any agent, in any framework, states what 'good enough' means and what it may spend getting there — and the runtime handles the rest."

> "The longer-term change is in how enterprises govern AI spend at all. Today the lever is restriction — quotas, caps, and approval gates that slow teams down to save money. OutcomeFuse replaces restriction with sufficiency: unlimited ambition, bounded waste. Spend whatever the outcome is worth, and nothing on work that was already done."

**Why it matters.** "Restriction → sufficiency / unlimited ambition, bounded waste" is the brief's central moral argument and the only place the product is positioned against how enterprises actually behave today, rather than against competing tools. It is also the answer to the FinOps persona's real objection. The PRD's positioning table compares OutcomeFuse to *products*; nothing compares it to the *governance posture* it intends to replace. Also lost: "as ordinary as declaring a timeout" — the single most portable analogy in the brief, and the entire scale story ("contracts become reusable policy artifacts owned by platform teams", "cost-per-verified-outcome as a first-class CI gate"), which survives in the PRD only as bare out-of-scope bullet items with no stated destination.

**Severity: critical.** Not a scope decision — an explicit promise the document does not keep.

---

### G2 — Low-expected-value step rejection was dropped; only *unaffordable* survives

The brief, Solution table:

> "**Budget Ledger** | Tracks allocated / spent / reserved / remaining; holds a protected reserve for final synthesis and verification; **rejects steps that are unaffordable, duplicated, or low-expected-value**"

Brief addendum, §1:

> "Rejects a proposed step when **expected benefit is low**, duplicated, unsafe, or unaffordable"

And the policy question itself:

> "what is the cheapest next action **likely to move this task above its quality floor**, and has the floor already been reached?"

What the PRD has: FR14 covers *unaffordable* only. FR27 covers duplicates (Tool Governor). FR1 lists a `deny` decision but names no expected-value criterion. **Nothing in FR1–FR73 requires the system to reject a step on grounds of low expected benefit, and nothing requires it to prefer the cheapest next action likely to reach the floor.** FR37–FR38 estimate cost envelopes but do not gate on value.

**Why it matters.** The product is stated in both documents as *"is another unit of AI work worth paying for."* "Worth paying for" has two halves — affordability and expected value. The PRD implements only affordability, which is the half every gateway budget cap already does. The PRD's own addendum §1.3 names "marginal-value-per-step accounting" as identified white space and §1.4 lists "marginal value per step" as available positioning vocabulary — yet no requirement produces it. The out-of-scope list defers "learned marginal-value estimation", which is correct, but the brief's *fixed-heuristic* version was in scope ("the marginal-value policy learns from historical runs **instead of relying on fixed heuristics**" — i.e. fixed heuristics are the MVP baseline, not the deferred part).

**Severity: critical.** This is the differentiator against gateway caps, silently unrequired.

---

## HIGH

### G3 — "The deliverable is not a report about a run. It is a cheaper run."

> "The deliverable is not a report about a run. It is a cheaper run."

> "**It is not an observability product, and the difference is structural rather than positional.** A dashboard's output is information that a human must interpret and act on. OutcomeFuse's output is a completed task that cost less. **There is no insight to action, because the action already happened mid-run.**"

The PRD's positioning table preserves the *fact* (Output: "A completed task that cost less") and loses the argument and the phrasing. "Structural rather than positional" — the claim that this is a category difference rather than marketing — is gone. So is the insight-to-action collapse, which is the sentence that actually wins the argument with an observability incumbent.

**Severity: high.** Requirements survived; the reason anyone should care did not.

---

### G4 — The critique of the status-quo response is gone from the problem statement

> "The common response is observability: capture the run, score the waste, recommend a change, wait for someone to implement it. That loop is slow, human-dependent, and retrospective. Meanwhile **the same agent runs the same wasteful way thousands more times**."

PRD §1.2 lists the four compounding costs (well preserved, near-verbatim) and stops. It never states what people do about the problem today or why that fails.

**Why it matters.** Without this, §1.2 describes waste and §1.3 asserts a category boundary, with nothing bridging them. The "thousands more times" line is the argument for *urgency* — the reason a retrospective fix is not merely slower but compounding.

**Severity: high.**

---

### G5 — The non-monetary cost of the status quo was dropped

> "The cost of the status quo is not only money. Overrun loops add latency users feel, and **an agent with no quality floor can return a confidently wrong answer that no budget control would have caught — because budget controls measure spend, not sufficiency**."

In the PRD: latency appears only as a secondary metric (§3.2) and a counter-metric; the confidently-wrong-answer argument survives only as a table cell ("Quality in the spend decision: None").

**Why it matters.** This is the brief's strongest *safety* argument, and the only one that gives the compliance/RAI persona (PRD §2.3) a reason to want the product rather than merely tolerate it. It also converts the product from a cost story into a correctness story — which is what justifies §9 and §10.2 existing at all.

**Severity: high.**

---

### G6 — The PRD hardens the four workloads from "additive" to "committed"

Brief:

> "**Sequencing note.** Build the harness once; each additional workload is then mock tools plus cases. **Workloads are additive, not dependencies — report on those completed.**"

PRD §4.1:

> "**All four are committed scope, not stretch.**"

This is a direct reversal of a deliberate hedge. The brief also pairs it with "Any claim of measured generalization beyond the workloads actually completed" being out of scope — which the PRD retains, producing an internal tension: four workloads are *committed*, but the document simultaneously plans for fewer being completed.

**Severity: high.** It removes the brief's declared graceful-degradation path under exactly the schedule pressure §4.3 anticipates.

---

### G7 — "Many existing approaches" became "every existing mechanism"

Brief (hedged):

> "**Many** existing optimization approaches are **primarily** retrospective, or optimize individual levers independently"

PRD §1.3 (categorical):

> "**every existing mechanism stops a run when it runs out.** OutcomeFuse stops a run when it is done."

The PRD addendum §1.5 undercuts this in its own verification caveat — two closest commercial analogues "could not be independently verified", Langfuse and LangGraph rows "were not fetched successfully and rest on prior knowledge; re-verify before external use." None of that caveat surfaces in the PRD body, where the categorical claim sits.

**Why it matters.** This is the single most falsifiable sentence in the PRD, resting on research the PRD's own addendum flags as unverified. The brief was careful here; the PRD is not. The "Differentiation challenge" risk row acknowledges reviewers will push back but does not soften the claim.

**Severity: high.**

---

### G8 — Superseded gross targets were resurrected without the brief's supersession caveat

Brief:

> "**Targets deliberately not yet fixed.** The source memo carried gross targets (≥40% tokens, ≥35% cost, ≥30% tool calls). Those were set before overhead was accounted for and must be restated as net once the first measurement exists."

Brief addendum:

> "**Original gross targets (superseded).** … These predate overhead accounting and are **retained for reference only**; net targets replace them once overhead is measured."

PRD §3.1 restores three of them as live targets — tool-call reduction ≥30%, pass rate within 2 percentage points, evidence-field accuracy ≥90% — marked "Carried from source targets." The brief declared *all* of the source memo's targets superseded and reference-only, not just the two token/cost figures.

**Why it matters.** This is inconsistent with the discipline the PRD elsewhere enforces on itself. The ≥30% tool-call figure is justified as "not overhead-sensitive," which is arguable, but "within 2 points" and "≥90%" get no such justification — they are simply reinstated. If two numbers were stripped for being pre-overhead guesses, the others need an explicit rationale for surviving, not a table note.

**Severity: high.** (Explicitly *not* the same as the deliberate net-target strip — this is the opposite direction.)

---

## MEDIUM

### G9 — The dashboard antithesis lost its second half

> "The distinction that matters: **turn the OutcomeFuse UI off and the savings still happen. Turn a dashboard off and its value disappears entirely.**"

PRD design principle 3 keeps only the first clause: "Turn the UI off and the savings still happen. The interface is evidence, not product." Without the contrast, it reads as a modesty note about the UI rather than as an attack on the incumbent category.

**Severity: medium.**

### G10 — Named comparators dropped

The brief names the specific comparison set: **TokenLens, Copilot Token Optimizer**. The PRD generalizes to "Post-run auditors" and the PRD addendum's competitive table (LiteLLM, Kong, APIM, Portkey, Helicone/Langfuse/…, FrugalGPT, RouteLLM) does not include either. Neither derived document mentions them anywhere.

**Severity: medium.** In a hackathon context, the named-incumbent comparison is the one a judge recognizes.

### G11 — The named Azure slice was genericized, and its justification lost

Brief:

> "**In — one thin Azure slice.** … token metering through the **APIM AI gateway** … it moves the headline savings figure from self-reported to independently measured at the gateway, **which is the difference between a number a judge has to trust and one they can check. Redis-backed tool caching is the fallback** if APIM integration proves unstable."

PRD §4.1 → "an AI gateway" and "A response/tool cache slice is the fallback." F15/FR66–68 are vendor-neutral throughout. The brief's deliberate, named, justified choice became a placeholder, and the "trust vs check" framing — the reason the slice earns its build cost — is gone.

**Severity: medium.** Vendor-neutral FRs are defensible; losing the selection rationale and the fallback's identity is not.

### G12 — The hackathon deliverable and judging context are absent

Neither derived document requires the artifact the brief's addendum §5 specifies in detail: a two-minute demo video with a fixed structure (problem / artifact / mechanism / proof / scale), the elevator pitch, or the named key screens. The brief also states the evaluation frame directly — _"'Customer focus' is an explicit evaluation signal"_ — which is *why* the agent-owner interviews are in scope. The PRD keeps the interviews and drops the reason.

The PRD addendum defers to the brief addendum for demo narrative, which is reasonable, but no requirement anywhere obliges the video to exist, and F14's screens are not reconciled against the brief's key-screen list (Budget Ledger, decision stream, proof card, trace drill-down — mostly covered by FR60–FR64; the Outcome Contract screen is not).

**Severity: medium.**

### G13 — Model Governor lost the "low confidence" escalation trigger

Brief addendum: "Escalates on task complexity, **low confidence**, policy criticality, or a failed quality evaluation."
PRD FR35: "task complexity, policy criticality, or a failed quality evaluation."

**Severity: medium.** FR35 is a SHALL-NOT-exceed list ("SHALL escalate model capability **only** on…"), so the omission is prohibitive, not merely silent — it forecloses confidence-based escalation.

### G14 — The Loop Fuse rationale, including an honesty caveat, was dropped

> "Rationale: autonomous loops must always be bounded — completion criteria can fail, **models can stall, evaluators are probabilistic**."

FR22–FR24 preserve the mechanism. "Evaluators are probabilistic" is an admission against interest that directly supports the PRD's own judge-reliability risk row and FR17's deterministic-gate argument — it explains why the Loop Fuse is not redundant with the Quality Gate.

**Severity: medium.**

### G15 — No minimum case count appears anywhere

The brief commits to "expanded case counts with repeated runs per case, so quality claims rest on absolute pass counts rather than percentages over a thin sample," and its addendum specifies **20–30 synthetic cases** for the supply-chain workload. The PRD requires repeated runs and absolute counts (FR52) but sets no floor on cases per workload — and Q4's blind-review sample N is also unset. Both quantities that determine whether the evidence means anything are now unspecified.

**Severity: medium.**

### G16 — "What appears uncommon is the subordination, not the parts" — hedge hardened

Brief: "**What appears uncommon** is the subordination, not the parts." Framed as one of "three further points of **honesty about the moat**" — i.e. an explicit admission the moat is thin.
PRD §1.3: "The product is the policy above them, and the subordination of all of them to a single declared objective." Asserted, not hedged, and no longer labelled as a concession.

**Severity: medium.**

---

## LOW

### G17 — Semantic-equivalence deduplication narrowed to exact duplicates
Brief addendum: "Prevents duplicate **and semantically equivalent** calls." FR27: "deny **exact** duplicate calls." Consistent with "semantic optimization" at cut position 4, but the narrowing is silent rather than declared.
**Severity: low.**

### G18 — Interviews' non-blocking status lost
Brief addendum §8: "Agent-owner interviews run in parallel throughout and are **not on the critical path**." The PRD carries them as scope with no sequencing note, making them look schedule-bearing.
**Severity: low.**

### G19 — "The schedule risk is gone" → "The schedule risk is low"
Minor softening of the brief's own assessment in PRD §4.3; changes the emphasis of the gold-plating argument slightly.
**Severity: low.**

### G20 — "Wrap around an existing agent in an afternoon" survives only inside an `[ASSUMPTION]`-tagged journey
The brief states it as a product property in Vision. In the PRD it appears only in UJ-4, under a blanket disclaimer that the journeys "carry design intent, not evidence, and SHOULD NOT be quoted externally." The adoption-cost claim is thereby quarantined. FR44 preserves the substance ("without requiring that agent to be re-architected") but not the concrete promise.
**Severity: low.**

### G21 — Tool Governor evaluator vocabulary dropped
Brief addendum names measurable evaluators: Tool Selection, Tool Call Accuracy, Tool Output Utilization, Tool Call Success, Task Navigation Efficiency. The PRD addendum defers to the brief addendum for component specs, so this is arguably filed rather than lost — noted for completeness.
**Severity: low.**

---

## Verified as faithfully carried (no action)

Four compounding costs · quality-floor-outranks-budget invariant · net-not-gross discipline · "gross savings are how this category flatters itself" · not-a-new-framework and mechanisms-not-novel honesty points · all three personas incl. assumed-persona tagging · domain-agnostic posture · shadow mode's double justification · baseline fairness and rubric-freeze · publish-failures reporting standard · synthetic-data disclosure · compression-preserves-attributable-facts · human-in-the-loop clarification ("what is removed is the *manual optimization* cycle") · preview-stage honesty and metering fallback · all three open questions · the 7.5-days-in-one-month capacity frame.

The PRD also *adds* material with no source in the brief and no conflict with it: the counter-metric set (§3.3), the declared cut order (§4.3), the fail-open/fail-closed asymmetry (§10), and the "never conflate done with stuck" principle. These are strengthenings, not distortions.
