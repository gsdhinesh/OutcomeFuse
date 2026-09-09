---
title: "PRD Quality Review — OutcomeFuse"
status: review
created: 2026-09-04
reviewer: rubric-walker
artifact: prd.md
supporting: addendum.md
rubric: .agents/skills/bmad-prd/assets/prd-validation-checklist.md
---

# PRD Quality Review — OutcomeFuse

**Gate verdict: PASS WITH CONDITIONS.** Approve for downstream architecture and story work once the four must-fix items are closed.

## Overall verdict

This is a strong, unusually self-aware PRD. It has a real thesis (stop on sufficiency, not exhaustion), it prices its own overhead into the headline claim, it names counter-metrics that could kill the claim, and it declares a cut order before schedule pressure arrives. Decision-readiness and scope honesty are its best dimensions; the `[NOTE FOR PM]` callouts land at genuine tensions rather than safe checkpoints.

What is at risk is done-ness and downstream extractability. The requirement that carries the entire differentiation — FR15's marginal-value denial — has no specified decision rule, and the PRD says so itself (Q7). The counter-metrics are named but none carries a threshold, so a system could report every one of them and still be unfalsifiable. And for a PRD that feeds architecture and stories, the absence of a Glossary and an Assumptions Index is a real extraction cost, not a formatting nit.

Scope-of-review note: per the review brief, the following are treated as deliberate decisions and are **not** scored as defects — MVP-only scoping with a non-normative Vision (§12), contract authoring out of scope (FR10, §4.2), the three savings targets deliberately unset pending the overhead study (§3.1), the four `[ASSUMPTION]`-tagged user journeys (§6), and the absence of a standalone persona section.

---

## Rubric walk — item by item

### Dimension 1 — Decision-readiness — **strong**

| # | Item | Verdict | Evidence |
|---|---|---|---|
| 1.1 | Decisions stated as decisions, not buried as considerations | **PASS** | §3.1 "Restatement gate" states the unset-targets decision explicitly with a trigger (FR62); §4.3 declares a numbered cut order; Q5 marked **Resolved** with the choice named (replay, not live). |
| 1.2 | Trade-offs named with what was given up | **PASS** | F14 preamble concedes replay loses live streaming to avoid concurrency/cancellation cost; §4.3 `[NOTE FOR PM]` concedes three of seven mechanisms are sacrificial. |
| 1.3 | Open Questions actually open | **PASS** | Q4, Q6, Q7 are all marked **Unset** with a deadline ("before the first evidence run", "before F3 is built") — no rhetorical answers. |
| 1.4 | `[NOTE FOR PM]` at real tensions | **PASS** | Three callouts: cut-order vs seven-mechanism narrative (§4.3), contract-authoring friction as the true adoption cost (UJ-4), rubric-circularity/self-blinding bias (§11.1). All are uncomfortable, none is decorative. |

No findings. This dimension is the PRD's strongest.

### Dimension 2 — Substance over theater — **strong**

| # | Item | Verdict | Evidence |
|---|---|---|---|
| 2.1 | Persona theater | **PASS** | Three stakeholders, each traceable to requirements: agent owner → FR9/FR21; FinOps → F2 contract-as-policy-surface; compliance → F12/UJ-3. None is ornamental. |
| 2.2 | Innovation theater | **PASS** | §1.3 downgrades the novelty claim to a survey claim, names two unverifiable analogues, and explicitly disclaims two adjacent claims ("not a new agent framework", "the individual mechanisms are not novel"). |
| 2.3 | NFR theater | **PARTIAL** | NFR2, NFR8, NFR10, NFR11 are sharply product-specific. But NFR6 (cache partitioned by tenant) and NFR7 (least-privilege identity) cannot be exercised under NFR9's synthetic-only, in-process MVP — they are production-story NFRs carried in an MVP-scoped PRD. |
| 2.4 | Vision theater | **PASS** | §12 is explicitly non-normative and is not swappable — "replaces restriction with sufficiency" is this product's specific bet, not a category platitude. |

#### Findings
- **low** — Production NFRs unexercisable in MVP (§7 NFR6, NFR7 vs NFR9) — Multi-tenant cache isolation and least-privilege tool identity have no MVP verification path, since evaluation is synthetic and in-process. *Fix:* mark NFR6/NFR7 as production-posture constraints binding on architecture but not MVP-verifiable, so a reviewer does not expect evidence for them.

### Dimension 3 — Strategic coherence — **adequate**

| # | Item | Verdict | Evidence |
|---|---|---|---|
| 3.1 | Stated thesis | **PASS** | §1.1 one-sentence policy framing plus §1.4's falsifiable claim; §1.5 principle 1 makes the thesis operative ("the quality floor outranks the budget, always"). |
| 3.2 | Prioritization follows the thesis | **PARTIAL** | The protected core (contract, ledger, gate, loop, benchmark, video) is exactly what the thesis needs. But §4.1 commits **four workloads** as "committed scope, not stretch" while the §4.3 cut order contains no workload entry — the only cuttable axis is mechanisms and UI, so schedule pressure cannot reach the largest breadth commitment. |
| 3.3 | SMs validate the thesis, not activity | **PASS** | "Net token reduction per completed outcome" and "task-completion pass rate vs baseline" measure the claim itself; no DAU/MAU-style activity proxies. |
| 3.4 | Counter-metrics named | **PARTIAL** | Six counter-metrics defined in §3.3 with genuine rationale, but **not one carries a threshold or a fail condition** — including false-sufficiency rate, which §3.3 itself calls "the direct inverse of the headline claim". Budget-breach rate is said to "must be visible and bounded" with no bound given. |
| 3.5 | Coherent MVP scope kind | **PASS** | Problem-solving MVP plus an evidence artifact; §4.3's priority statement and §8's normative evidence standards match that kind. |

#### Findings
- **high** — Counter-metrics have no thresholds (§3.3, §3.1) — Every counter-metric is defined and reportable but none is bounded, so no measured value can falsify the headline claim. The perverse optimum the section names is documented, not closed. *Fix:* set a maximum acceptable false-sufficiency rate and a maximum tool-suppression error rate before the first evidence run (same gate as Q4/Q6), even if provisional; state budget-breach and escalation-rate bounds or say explicitly that they are observational only.
- **medium** — Cut order cannot cut breadth (§4.1, §4.3) — Four workloads are committed as non-stretch scope but appear nowhere in the numbered cut order, so the declared de-scoping mechanism cannot touch the largest schedule driver. *Fix:* add a workload-reduction entry to the cut order (e.g. "workloads 3 and 4 reduce to shadow-only evidence") with the §8.4 generalization limit applied automatically.

### Dimension 4 — Done-ness clarity — **thin**

| # | Item | Verdict | Evidence |
|---|---|---|---|
| 4.1 | Testable consequence per FR | **PARTIAL** | The large majority are crisp (FR20 stop-immediately, FR26 distinct halt reporting, FR61 refuse-drifted-comparison, FR65 paired reporting). Four are not implementable as written: FR15, FR19, FR12, FR48. |
| 4.2 | No vague adjectives / unbounded qualifiers | **PARTIAL** | Flagged verbatim: FR15 "expected benefit is **low relative to its cost**"; FR19 "whether the tools called were **the right ones**"; FR12 "a protected reserve **sufficient for** final synthesis"; FR48 "without requiring that agent to be **re-architected**". |
| 4.3 | Acceptance criteria implied or explicit | **PARTIAL** | §8 supplies strong acceptance rules for the *evidence claim*, and many FRs carry their own consequence. But there is no acceptance surface for the runtime FRs themselves — e.g. nothing states how FR5 replayability or FR53 reconstructability is demonstrated. |
| 4.4 | Non-functional sections give bounds, not adjectives | **FAIL** | NFR1 explicitly sets no latency target; the "Added latency" counter-metric has no bound; §3.3's counter-metrics are all unbounded. The result is that the "cheaper but unusably slower is a failed trade" test cannot be adjudicated in the MVP. |

#### Findings
- **critical** — FR15's decision rule is undefined while FR15 is protected core (§5 F3, §11.1 Q7) — FR15 carries the marginal-value half of the product thesis; §1.3 and the §11.2 differentiation risk both state the distinction is rhetorical unless FR15 is built. Q7 concedes the estimation method is unset. A protected-core requirement in a build-now PRD cannot be left without a decision rule. *Fix:* specify the MVP heuristic inline in FR15 (e.g. deny when the planned step targets only already-satisfied contract fields, or when projected step cost exceeds remaining unmet-field value by a declared factor); Q7 already says a fixed heuristic is acceptable — write it down.
- **high** — FR19 tool-use quality has no stated evaluation mechanism (§5 F4) — FR19 asks whether tools were "the right ones" and whether output "was actually used", but FR18 makes deterministic validation authoritative and the rubric advisory. FR19 does not say which side of that line it falls on, so it is unbuildable and its relationship to FR65 is unclear. *Fix:* state whether FR19 is deterministic (e.g. every cited evidence field traces to a tool result actually consumed) or advisory-rubric, and bind it explicitly to the FR65 measurement.
- **medium** — FR12 reserve is unsized (§5 F3) — "sufficient for final synthesis and quality verification" gives no sizing rule, yet the reserve is what makes UJ-2's escalation path and FR21's safe-budget test decidable. *Fix:* declare the reserve as a contract field or a stated percentage-of-allocated default.
- **medium** — NFR1 sets no latency bound and no deadline (§7) — Unlike §3.1's savings targets, NFR1 carries no explicit restatement gate of its own beyond a pointer to §3.1, and "Added latency" in §3.3 is likewise unbounded. *Fix:* bind NFR1 to the same FR62 completion trigger as §3.1 and state the interim reporting obligation.
- **low** — FR48 integration cost is stated as an adjective (§5 F11) — "without requiring that agent to be re-architected" is not testable. UJ-4 implies the real bar (wrap the loop plus one contract file, one afternoon). *Fix:* restate FR48 as a bounded consequence, e.g. integration requires no change to the host agent's tool signatures or control flow beyond wrapping the loop entry point.

### Dimension 5 — Scope honesty — **strong**

| # | Item | Verdict | Evidence |
|---|---|---|---|
| 5.1 | Non-Goals doing real work | **PASS** | §4.2 rules out contract authoring, full production deployment, policy DSL, learned marginal-value estimation, multi-agent transfer, CI gates — and rules out "any claim of measured generalization beyond the workloads actually completed", which is a non-goal with teeth. |
| 5.2 | `[ASSUMPTION]` tags on inferences | **PASS** | Four inline tags: §2.1 persona, §6 all journeys, FR57 minimum case count, FR64 sample size. Each carries a revisit condition. |
| 5.3 | `[NOTE FOR PM]` at deferred decisions | **PASS** | §4.3, UJ-4, §11.1 — all at unresolved tensions. |
| 5.4 | De-scoping honest / open-items density vs stakes | **PARTIAL** | De-scoping is exemplary (§4.3 cut order + NFR10 makes it mechanically executable). But three of seven Open Questions are **Unset** and two of those (Q6, Q7) gate work that is in the protected core, on a PRD that is otherwise green-lit to build inside a fixed window. |

#### Findings
- **medium** — Three blocking unknowns on a build-now PRD (§11.1 Q4, Q6, Q7) — Sample size N, minimum case count, and the FR15 heuristic are all unset, and all three gate protected-core or evidence work with no owner or date attached. *Fix:* assign each a "resolve by" milestone tied to a build step (Q7 before F3 implementation, Q4 and Q6 before the first harness run) rather than a soft "before the first evidence run".

### Dimension 6 — Downstream usability — **thin**

This is a chain-top PRD — it explicitly feeds architecture (the addendum instructs architecture on NFR10 and failure-posture separation) and story creation. Traceability therefore matters more here than for a standalone PRD.

| # | Item | Verdict | Evidence |
|---|---|---|---|
| 6.1 | Glossary present; domain nouns used identically | **FAIL** | No Glossary section exists. The PRD carries at least fifteen load-bearing coined terms — Outcome Contract, Budget Ledger, Quality Gate, Loop Fuse, Tool Governor, Context Governor, Model Governor, Preflight Planner, Shadow Mode, sufficiency, marginal value, false sufficiency, governor overhead, evidence capsule, proof card — none formally defined in one place. |
| 6.2 | IDs contiguous, unique, cross-refs resolve | **PARTIAL** | FR1–FR84 are contiguous with no gaps or duplicates, and the Appendix accounts for every block. Two defects: F9 (Preflight Planner) appears in no numbered §4.3 cut-order entry yet the Appendix claims "Cut alongside F7 and F8" and the §4.3 note calls it sacrificial; and the addendum mis-cites FR17 for the deterministic-gate requirement (it is FR18) and FR59 for false-sufficiency (it is FR64). |
| 6.3 | Sections extractable standalone | **PASS** | §5, §8, §10 and the Appendix each stand alone; §8 in particular reads as a self-contained normative evidence standard. |
| 6.4 | UJs have named protagonists | **PASS** | Priya (UJ-1), Marcus (UJ-2), Dana (UJ-3), Sam (UJ-4) — each carries role, context and stake inline, which is what makes the absent persona section a non-issue. |

#### Findings
- **high** — No Glossary in a chain-top PRD (§ document-level) — Fifteen-plus coined terms are load-bearing across FRs, UJs, SMs and the addendum, and downstream architecture/story extraction will re-derive definitions inconsistently. *Fix:* add a Glossary defining the seven mechanisms, Outcome Contract, quality floor, sufficiency, marginal value, governor overhead, false sufficiency, evidence capsule and proof card, and make cross-references point at glossary terms.
- **medium** — F9 missing from the numbered cut order (§4.3 vs Appendix) — The Appendix asserts a cut position F9 does not have; a reader executing the cut order under pressure has no instruction for the Preflight Planner. *Fix:* add F9 as an explicit numbered entry, or state in §4.3 that F9 cuts with F7.
- **low** — Addendum cross-reference drift (addendum §2, §3) — "the reason FR59 exists" should be FR64; "FR17 makes deterministic field validation authoritative" should be FR18. *Fix:* correct both citations.

### Dimension 7 — Shape fit — **adequate**

| # | Item | Verdict | Evidence |
|---|---|---|---|
| 7.1 | Shape matches the product | **PASS** | Technical capability spec plus an evidence-claim document, with UJs kept to four and used for adoption/audit/escalation paths rather than decoration. F16 scoping the submission artifact is the right shape call for a judged hackathon deliverable. |
| 7.2 | Formalization level | **PARTIAL** | 84 FRs, 12 NFRs and 16 features against §4.3's stated "roughly 7.5 days of estimated build work". The FRs are individually terse and mostly load-bearing, so this is not gratuitous, but the ratio invites a reader to assume more will be built than the cut order will permit. |

#### Findings
- **high** — Schedule-risk assessment contradicts itself (§4.3 vs §11.2) — §4.3 states "The schedule risk is low; the replacement risk is gold-plating." §11.2 states the same risk is "**Material, and accepted deliberately**" and notes the source memo recommended capping at four mechanisms for a *team*. Both cannot be the operative position, and they lead to opposite behaviour under pressure. *Fix:* adopt the §11.2 framing in both places and rewrite the §4.3 sentence to say the risk is material and the cut order is the mitigation.

---

## Mechanical notes

| # | Item | Verdict | Evidence |
|---|---|---|---|
| M1 | Glossary drift | **PARTIAL** | Same concept, varying surface: "quality floor" / "declared quality bar" / "declared bar" / "the floor"; "cost ceiling" / "budget ceiling" / "maximum estimated cost"; "decision record" / "audit trail" / "log". Most serious: FR1's decision enum includes **`proceed-with-substitution`**, which appears nowhere else in the PRD and is never defined — the closest candidates are FR40 model substitution and F7 compression, but the PRD does not say. |
| M2 | ID continuity | **PARTIAL** | FR1–FR84 contiguous and unique; Appendix roundtrips every feature block. Defects as noted in 6.2 (F9 cut position, addendum FR17/FR59). |
| M3 | Assumptions Index roundtrip | **FAIL** | Four inline `[ASSUMPTION]` tags (§2.1, §6, FR57, FR64) and **no Assumptions Index** anywhere in the document. The Appendix is a Requirement Index only. |
| M4 | Required sections present for stakes and type | **PASS** | Vision, users, metrics + counter-metrics, scope + non-goals, FRs, UJs, NFRs, evidence standards, RAI, failure posture, open questions/risks, requirement index. Nothing structural missing except the Glossary and Assumptions Index above. |

#### Findings
- **high** — `proceed-with-substitution` is an orphan term (§5 FR1) — A first-class policy decision type is enumerated and then never defined, constrained or recorded anywhere; FR2, FR40 and FR51 do not cover it. Story creation would have to invent its semantics. *Fix:* define it in FR1 and bind it to the mechanisms that may perform substitution (FR39/FR40 model, FR34–FR36 context), or remove it from the enum.
- **medium** — No Assumptions Index (§ document-level) — Four assumptions carry revisit conditions but there is no single place to check whether they have been discharged, which is exactly what the post-interview revisit (§2.1, §6) will need. *Fix:* add an Assumptions Index listing each tag, its location, its revisit condition and its status.
- **low** — Terminology drift on floor/ceiling/record (§ throughout) — Cosmetic today, extraction noise downstream. *Fix:* resolve via the new Glossary and normalize usage.

---

## Verdict counts

| Verdict | Count |
|---|---|
| PASS | 17 |
| PARTIAL | 11 |
| FAIL | 3 |
| **Total items** | **31** |

## Findings by severity

| Severity | Count |
|---|---|
| critical | 1 |
| high | 4 |
| medium | 6 |
| low | 4 |

### Must-fix before downstream work
1. **critical** — Define FR15's marginal-value decision rule (closes Q7). It is protected core and it is the differentiator.
2. **high** — Resolve the §4.3 vs §11.2 schedule-risk contradiction.
3. **high** — Set thresholds on the counter-metrics, at minimum false-sufficiency rate and tool-suppression error rate.
4. **high** — Add a Glossary and an Assumptions Index; define or delete `proceed-with-substitution`; state FR19's evaluation mechanism.

### Should-fix
5. **medium** — Add a workload-reduction entry to the cut order; add F9's cut position; size the FR12 reserve; bind NFR1 to a restatement trigger; date the Q4/Q6/Q7 resolutions.
