---
title: "Reconciliation — Source Memo vs PRD"
source: doc/info.md
derived: _bmad-output/planning-artifacts/prds/prd-OutcomeFuse-2026-09-04/prd.md
created: 2026-09-04
---

# Reconciliation: concept memo → PRD

**Question answered here:** what does `doc/info.md` contain that survived neither the product brief nor the PRD?

**Explicitly excluded from findings** (per instruction, deliberate refinements): the supply-chain persona pivot to a domain-agnostic agent owner; the stripped gross numeric targets (≥40% tokens, ≥35% cost, ≥20% latency); production Azure stack detail (APIM, Redis, Cosmos, Container Apps, Entra).

---

## Findings summary

| # | Finding | Type | Severity |
|---|---|---|---|
| 1 | The two-minute submission video — the memo's primary deliverable — is absent from PRD scope | Omission | **Critical** |
| 2 | Tool-use *quality* evaluators dropped; the ≥30% tool-call reduction target has no accuracy guard | Omission | **Critical** |
| 3 | The judging rubric and its "not a confirmed 2026 contract" caveat vanish entirely | Omission | **High** |
| 4 | Memo's resourcing plan assumed a six-role team; PRD is solo and 4× the workload scope | Omission / over-assertion | **High** |
| 5 | "Every existing mechanism stops a run when it runs out" — universal claim the memo never made | Over-assertion | **High** |
| 6 | No minimum case-set size anywhere in the PRD (memo: 20–30 cases) | Omission | **Medium** |
| 7 | Scale calculator / quantified business value deliverable dropped | Omission | **Medium** |
| 8 | Overrun loops asserted as "the most expensive failure" without memo support | Over-assertion | **Medium** |
| 9 | No FR enforces the contract's `human_approval_conditions` before a side-effecting tool call | Omission | **Medium** |
| 10 | Build-order sequencing constraints lost | Omission | **Medium** |
| 11 | Named-competitor boundary (TokenLens, Copilot Token Optimizer Agent) generalized away | Omission | **Low** |
| 12 | Demo screen 1 — the Outcome Contract itself — missing from F14 | Omission | **Low** |
| 13 | "Efficiency feedback loops" challenge theme has no counterpart | Omission | **Low** |

---

## 1. The two-minute submission video is absent from PRD scope — **Critical**

**Source:**

> "The submission video is capped at two minutes and should land four beats: problem, artifact, proof, and scale."

and the entire §8, "Two-minute demo/storytelling flow", with timings 0:00–0:18 problem / 0:18–0:38 what was built / 0:38–1:15 live mechanism / 1:15–1:42 proof / 1:42–2:00 scale, plus:

> "Only replace brackets with measured results."

**What the PRD says instead.** §4.1 lists surfaces as: middleware library, CLI harness, read-only web view. §4.3 places "Presentation and admin experiences" **first in the cut order**. There is no FR, no scope line, and no deliverable anywhere in the PRD covering a video, a script, a pitch, or any submission artifact.

**Why it matters.** This is a hackathon entry. The video is not a nice-to-have adjacent to the build — under the memo's own framing it is *the* judged artifact ("show a working mechanism rather than slides alone", "an artifact whose mechanism can be watched running"). The PRD has scoped the thing being demonstrated with great rigour and scoped the demonstration itself to zero. Worse, the cut order actively instructs that presentation work be sacrificed first, which under schedule pressure produces an unsubmittable entry.

The memo's four beats also constrain the build: beat 4 ("scale") requires a scale story the PRD does not produce (see finding 7), and beat 3 ("proof") requires a *single memorable comparison sentence* — which the PRD's deliberate refusal to set net targets (§3.1) leaves with no number to fill. That is a defensible measurement position but it collides with a submission deadline, and the PRD does not acknowledge the collision.

**Recommendation.** Add the submission video as an explicit, protected deliverable with a scripted beat structure, and remove presentation from cut position 1 — or state plainly that the video is out of PRD scope and tracked elsewhere. Silence is the failure mode.

---

## 2. Tool-use quality evaluators dropped — **Critical**

**Source (success criteria table):**

> | Tool Call Accuracy / Task Navigation | Equal to or better than baseline |

and:

> "Foundry's agent evaluators include Tool Selection, Tool Call Accuracy, Tool Output Utilization, Tool Call Success and Task Navigation Efficiency, making this measurable rather than subjective."

**What the PRD says instead.** §3.1 retains tool-call reduction (≥30%) as a headline metric. Tool-call *accuracy*, *selection*, *output utilization* and *task-navigation efficiency* appear nowhere — not in §3.1, not in §3.2, not in the §3.3 counter-metrics, not in FR53's per-run capture list.

**Why it matters.** This is a structural hole, not a dropped nice-to-have. The PRD is scrupulous about the perverse optimum on stopping — §3.3 correctly identifies that "the system that stops earliest always wins" and installs false-sufficiency rate as the guard. It installs **no equivalent guard on tool suppression.** A governor that denies a needed tool call improves the ≥30% tool-call figure directly, and the only thing standing between that and a headline claim is the Quality Gate — which is deterministic field validation over the *final deliverable*, and can pass on a run that took a worse investigative path.

The memo's phrasing was precise: tool metrics should be "equal to or better than baseline," i.e. tool-call reduction was always meant to be *paired* with a tool-quality hold-constant. The PRD kept the numerator and dropped the denominator. Note also that this is one of the few places the memo offered an off-the-shelf, non-subjective measurement instrument — the memo explicitly flagged it as "measurable rather than subjective" — and the PRD elsewhere works hard to prefer deterministic signals.

**Recommendation.** Add a tool-use quality counter-metric to §3.3 (tool-call accuracy / task-navigation efficiency, held at or above baseline), and add tool-selection outcome to FR53's capture list.

---

## 3. Judging rubric and its caveat vanish entirely — **High**

**Source:**

> "**Important evidence caveat:** the seven-criterion rubric shown in the executive working deck—impact, innovation, robustness, viability, scalability, presentation readiness, and Responsible AI—is identified there as the 2025 model requiring confirmation for 2026. Treat it as useful design guidance, not a confirmed 2026 scoring contract."

plus the whole §1 signal table: proactive-not-reactive, non-obvious waste angle, quantified savings with credible baseline, named user workflow, production path, Responsible AI posture, watchable mechanism.

**What the PRD says instead.** Six of the seven criteria are addressed *implicitly and well* — impact, innovation, robustness (§10), viability, Responsible AI (§9), and arguably scalability via NFR8 domain neutrality. **"Presentation readiness" is the one criterion with no counterpart at all**, and it is first in the cut order.

**Why it matters.** Two distinct problems. First, an entry evaluated against a criterion it has no scope line for. Second — and this is the subtler loss — the memo's *caveat* is gone. The memo deliberately hedged the rubric as unconfirmed for 2026. The PRD, having dropped the rubric, cannot over-assert it, but it also cannot flag the uncertainty to whoever reads the PRD as the sole planning document. Someone working only from the PRD has no idea a scoring model exists, confirmed or otherwise.

**Recommendation.** Add a short §11 open question: "Is the 2025 seven-criterion rubric the 2026 scoring model?" — status unconfirmed, owner named, with presentation readiness called out as the criterion currently unscoped.

---

## 4. Team-based resourcing plan vs. solo constraint — **High**

**Source (§6 implementation plan):**

> | Optimization | Context capsules, cache, tool dedupe, optional model escalation | **AI/ML engineer** |
> | UX & demo | Live trace, decision timeline, final proof card | **Front-end/data-visualization teammate** |
> | Story & value | Customer narrative, scale calculator, two-minute video | **PM/business teammate** |

and:

> "**Recommendation:** proceed with OutcomeFuse, keep the MVP to **Context Capsule + Tool Governor + Loop Fuse + Quality Gate**"

and:

> "Create 20–30 synthetic but realistic cases" — for **one** scenario.

**What the PRD says instead.** NFR11: "The system is built solo within a one-month window." §4.3: "Roughly 7.5 days of estimated build work sits inside a one-month window, solo. The schedule risk is low." §4.1 commits **four** workloads, seven mechanisms, gateway metering, agent-owner interviews, an overhead study, blind human review, and a web view.

**Why it matters.** The memo allocated six workstreams across a multi-person team and recommended holding the MVP to **four** mechanisms. The PRD removed the team, expanded to seven mechanisms, quadrupled the workload count, added an independent measurement slice and a human-review protocol — and then declares "schedule risk is low."

The estimate itself is the over-assertion. 7.5 days for four workload harnesses (each needing mock tools, a case corpus, golden decisions and a frozen baseline), a blind-review protocol, an overhead study with repeated runs, three user interviews, and a replay UI is not a low-risk estimate; it is an estimate that has not been reconciled against the memo's own view of what this takes. The PRD's stated replacement risk — "gold-plating" — is exactly backwards if the estimate is wrong.

Nothing here contradicts the domain-agnostic pivot, which is a sound positioning move. The finding is that the *cost* of proving generality across four workloads was never priced against the memo's team assumption.

**Recommendation.** Either re-baseline the estimate with per-workload cost broken out, or demote workloads 3 and 4 to conditional scope with an explicit trigger. Add "estimate is unvalidated" to §11.2 risks.

---

## 5. Over-assertion: "every existing mechanism stops a run when it runs out" — **High**

**PRD §1.3:**

> "The category boundary that matters: **every existing mechanism stops a run when it runs out. OutcomeFuse stops a run when it is done.**"

**What the memo actually claimed.** The memo's differentiation was scoped to *named* artifacts it had actually read — TokenLens, and *Copilot Token Optimizer Agent.pptx*. Its comparison table is headed "TokenLens | OutcomeFuse", not "everything that exists". Its alternatives table carries the disclaimer:

> "Scores below are my assessment on a 1–5 scale, not measured results."

**Why it matters.** The PRD converts a scoped comparison against two known internal proposals into a universal negative claim about all prior art. Universal negatives are the easiest thing in a pitch to falsify — one counter-example from a judge kills it, and the PRD's own §11.2 risk register anticipates precisely this attack ("a reviewer may say this already exists") while §1.3 hands the reviewer the ammunition. The PRD is otherwise unusually disciplined about claim scope (§8.4 forbids claims of generalization beyond workloads completed); this sentence is inconsistent with its own standard.

**Recommendation.** Scope the claim: "the mechanisms we surveyed stop on exhaustion or per-call confidence" — and name the survey. Same discipline §8.4 already imposes on savings claims.

---

## 6. No minimum case-set size — **Medium**

**Source:**

> "Create 20–30 synthetic but realistic cases containing: capacity plan CSV; open/released order data; contract constraints; regional demand and inventory; 3–5 policy documents; expected tools; golden decision and required evidence fields."

**What the PRD says instead.** §4.1: "Expanded case counts with repeated runs per case, so quality claims rest on absolute pass counts rather than percentages over a thin sample." FR52 requires repeated runs and absolute counts. **No number appears anywhere.** §8.3 concedes "with a modest case count a 'within N percentage points' quality claim may not be statistically meaningful" — and then does not set the count.

**Why it matters.** This is not one of the stripped gross performance targets; it is a dataset-adequacy constraint, and the PRD's own statistical argument depends on it. "Expanded" relative to an unstated baseline is unfalsifiable. The PRD identifies exactly this failure mode for sample size N in Q4 — "must be fixed before the first evidence run, not after seeing results" — and applies the reasoning to the review sample but not to the case set itself. Same bias, same fix, applied inconsistently.

Also lost: the memo's per-case *content* checklist (golden decision + required evidence fields + expected tools). FR51 assumes a frozen case set exists but never specifies what a case must contain.

**Recommendation.** Set a minimum cases-per-workload figure and a per-case content schema, both before the first evidence run. Carry them as an open question with an owner if the number cannot be fixed now.

---

## 7. Scale calculator / quantified business value dropped — **Medium**

**Source (judging signal table):**

> | Business value | Report tokens, estimated cost and latency per verified outcome, not aggregate consumption. |

> "Story & value | Customer narrative, **scale calculator**, two-minute video"

and beat 4 of the video: *scale*.

**What the PRD says instead.** §3.1 measures per completed outcome — the per-outcome framing survived. The **extrapolation** did not. There is no deliverable anywhere that converts a per-run saving into an enterprise-scale figure, and §4.2 does not list it as out of scope either. It simply is not mentioned.

**Why it matters.** "X% fewer tokens on 30 synthetic cases" and "this is what it means at enterprise volume" are different claims, and the memo treated the second as a required output ("quantify business value"). Without it the entry proves a mechanism works and never says what it is worth. The memo's closing pitch depends on it: "It turns AI cost control from restriction into intelligent execution" is the scale beat, unsupported.

**Recommendation.** Either add a minimal scale-extrapolation deliverable (with stated assumptions, since extrapolating from synthetic cases is itself a claim needing discipline under §8.4), or list it in §4.2 as an explicit cut.

---

## 8. Over-assertion: overrun loops as "the most expensive failure" — **Medium**

**PRD §1.2:**

> "**Overrun loops** — the most expensive failure. The agent reaches a sufficient answer at iteration three and works to iteration eight because nothing told it to stop."

**What the memo claimed.** The memo lists four waste sources without ranking them:

> "They waste them by carrying irrelevant context, repeating tools, looping after the answer is already sufficient, and using premium reasoning for every step."

No cost ordering. No "iteration three / iteration eight" figures — those appear nowhere in the memo.

**Why it matters.** Minor in isolation, but it is a load-bearing sentence: it justifies why the Loop Fuse and Quality Gate are protected while the Context Governor is cut position 6. The PRD's own §4.3 note is honest that this makes three mechanisms sacrificial — but the *justification* for that prioritization rests on an unevidenced cost ranking presented as fact. The specific numbers (three, eight) read as measured and are illustrative.

**Recommendation.** Mark the ranking as a hypothesis to be confirmed by the overhead study, and mark the iteration figures as illustrative. The prioritization can stand on judgment; it should say so.

---

## 9. No FR enforces human-approval conditions — **Medium**

**Source (§7 Responsible AI):**

> "**Human control:** require approval for side-effecting or high-impact tools."

**What the PRD says instead.** FR6 requires the *contract* to specify `human-approval conditions`. FR1 includes `request-human` as a decision type. FR28 forbids caching or denying side-effecting tools. §9 restates the principle in prose. **No FR requires the runtime to actually block a side-effecting tool call pending approval.** The contract can declare the condition; nothing normatively obliges the governor to honour it.

**Why it matters.** The PRD is exhaustive about FR-level enforcement elsewhere — the quality floor gets FR9, FR19, FR20 and three §9 cross-references. Human control gets a contract field and a prose sentence. For a Responsible AI posture that will be read by a compliance persona the PRD itself defines (§2.3, UJ-3), an unenforced control is a gap a reviewer will find.

**Recommendation.** Add an FR under F2 or F6: where the contract declares human-approval conditions, the system SHALL suspend and request approval before invoking a matching tool, and SHALL record the approval.

---

## 10. Build-order sequencing constraints lost — **Medium**

**Source (§6 suggested build order):**

> "1. Freeze scenario and quality rubric first. 2. Implement baseline and automated test harness. 3. Add Outcome Contract and Budget Ledger. 4. Add tool dedupe and loop fuse. 5. Add context capsule. 6. Add quality-gated early stop. **7. Enable model escalation only after the first five work reliably.** 8. Record reproducible benchmark runs. 9. Build the side-by-side demo around the strongest representative case."

**What the PRD says instead.** §4.3 gives a *cut* order — what to drop under pressure — which is not the same thing as a build order. §8.2 preserves step 1 ("the quality rubric SHALL be frozen before governor work begins"), correctly and as a normative requirement. Steps 2–9 have no counterpart.

**Why it matters.** Two constraints in particular carry risk information the cut order does not encode. Step 7 — model escalation last, gated on the others working — protects against the hardest-to-debug mechanism destabilising the measurement. Step 9 — build the demo around "the strongest representative case", chosen *after* benchmark runs exist — is a sequencing decision the PRD's F14 does not reflect, and is also a mild claim-hygiene concern the memo implicitly accepted.

Note this is partially mitigated: the cut order's inverse roughly reconstructs the build order. The loss is the explicit dependency in step 7.

**Recommendation.** Add the model-escalation dependency as a note under F8. Optional: state that the demo case is selected after benchmark runs and disclosed as representative rather than best.

---

## 11. Named-competitor boundary generalized away — **Low**

**Source (§2):**

> "OutcomeFuse should therefore not lead with traces, waste scores, recommendations, dashboards, or hypothetical savings."

> "A second enterprise proposal, *Copilot Token Optimizer Agent.pptx*, also focuses on usage analysis, prompt-pattern recommendations... That reinforces the need to avoid an 'analytics plus recommendations' concept."

**What the PRD says instead.** §1.3's positioning table generalizes TokenLens to "post-run auditors". The substance survives. What is lost is that these are *specific internal proposals the entry will be judged alongside*, and the memo's derived design prohibition — do not lead with dashboards.

**Why it matters.** Low, because the prohibition is honoured in practice: F14 is a single read-only replay view, deliberately not a dashboard, and §1.5 principle 3 ("turn the UI off and the savings still happen") encodes the same instinct. The residual risk is that a future reader without the memo re-adds dashboard scope without knowing it was a differentiation decision.

**Recommendation.** One line in §1.3 recording that dashboards and post-hoc recommendations are an excluded design direction, not merely an unbuilt feature.

---

## 12. Demo screen 1 — the Outcome Contract — missing from F14 — **Low**

**Source (§5 key screens):**

> "1. **Task / Outcome Contract** — quality floor and budget."

**What the PRD says instead.** F14 covers memo screens 2–6 well: side-by-side replay (FR60), governor decisions (FR61), ledger (FR62), proof card (FR63), trace drill-down (FR64). Screen 1 — displaying the contract under which the run executed — has no FR.

**Why it matters.** Low mechanically, but it is beat 2 of the two-minute video ("Show the Outcome Contract: *for this task, the agent must recommend an action, cite three required evidence fields, score at least 90%...*"). Without it the demo opens on execution with no visible statement of what the run is being held to — which is the one thing that distinguishes OutcomeFuse from a cost cap.

**Recommendation.** Add an FR to F14: the view SHALL display the contract in force for the replayed run.

---

## 13. "Efficiency feedback loops" has no counterpart — **Low**

**Source:**

> "This is directly aligned to the challenge's call for cost-aware prompts, lightweight model choice, budget-guided orchestration, and **efficiency feedback loops**."

**What the PRD says instead.** Three of four map cleanly: cost-aware prompts → F7, lightweight model choice → F8, budget-guided orchestration → F1/F3. The fourth does not. The nearest candidate, "marginal-quality learner from prior runs", is a memo stretch goal and is explicitly out of scope in PRD §4.2 ("learned marginal-value estimation").

**Why it matters.** Low — the cut is deliberate and correct for a one-month MVP. Flagged only because it is a named challenge theme with no acknowledged position. Shadow mode (F10) is arguably a partial answer and could be framed as one.

**Recommendation.** No scope change. Optionally frame shadow mode as the MVP's feedback-loop story in the positioning narrative.

---

## Assessment

The PRD is a stronger document than the memo on everything it chose to carry — measurement discipline, failure posture, counter-metrics and claim hygiene are all substantially better than the source. The losses cluster in one place: **the memo's awareness that this is a competitive submission, not just a build.** Video, judging criteria, presentation readiness, scale story and named-competitor positioning all fell through both filters together, because the brief and the PRD were each reasoning about the *product* while the memo was reasoning about the *entry*.

Findings 1, 2 and 3 should be resolved before the build starts. Finding 4 should be resolved before scope is committed.
