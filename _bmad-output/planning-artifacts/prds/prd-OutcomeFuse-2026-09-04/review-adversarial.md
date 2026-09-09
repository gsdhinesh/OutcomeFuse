---
title: "Adversarial Review: OutcomeFuse PRD"
status: review
created: 2026-09-04
reviewer: "Skeptical hackathon judge, submission 41 of the week"
artifact: prd.md
supporting: addendum.md
---

# Adversarial Review — OutcomeFuse PRD

**Posture:** I have read forty submissions this week. Thirty-eight of them claimed a percentage. I am looking for reasons to score this one down, and I will only credit what the document actually commits to.

---

## Verdict

This is the most epistemically honest PRD in the pile and I still cannot score it above the middle, because the two things that would make it exceptional — the marginal-value decision (FR15) and the savings number (§3.1) — are both explicitly unspecified, and the document's own risk table admits that without the first, "the distinction is rhetorical."

The PRD has been reviewed before. It shows. Most of the cheap attacks are pre-blocked. What survives is structural, and the surviving attacks are worse than the ones that were closed.

---

## Attack 1 — "This is just a retry loop with an eval, plus 84 requirements"

**X is: `while not judge(result) and budget_remains: iterate`.** That is fifteen lines. Every attack below hangs off whether OutcomeFuse is meaningfully more than that.

The PRD volunteers the ammunition itself:

> "**The individual mechanisms are not novel.** Caching, loop bounds, compression and model routing all exist, and none is claimed as invention. The product is the policy above them" (§1.3)

So the entire novelty claim rests on composition and on one thing: **stopping on sufficiency rather than exhaustion.** Fine. Now the killer.

### The baseline already contains the thing the product claims to add

§1.2 names the flagship waste:

> "**Overrun loops** — the most expensive failure. The agent reaches a sufficient answer at iteration three and works to iteration eight because nothing told it to stop."

§8.1 then defines the baseline as:

> "a *reasonable* agent, not a strawman: full retrieved context per step, one capable model throughout, **a conventional evaluator/retry loop with a maximum-iteration safety limit**."

An evaluator/retry loop *does not run to iteration eight after passing at three*. It stops when its evaluator passes. That is what an evaluator/retry loop is. So one of two things is true, and the PRD does not say which:

- **(a)** The baseline stops on its own evaluator — in which case the largest named waste category does not exist in the baseline, and the headline savings must come from caching, compression and routing, which §1.3 concedes are "not novel." The product becomes X with extra steps by its own definitions.
- **(b)** The baseline has an evaluator that does not gate stopping — in which case §8.1's "not a strawman" pledge is broken and the entire comparison is rigged in exactly the way §8.1 says it must not be: "The baseline is defined by the party who benefits from it losing."

**This is the single most damaging unresolved item in the document.** There is no third reading. The PRD needs a sentence stating precisely what the baseline's evaluator is permitted to do about stopping, and it does not have one.

### The differentiator has no design

§11.2 states the defence and then detonates it:

> "The distinction is per-call escalation versus per-run cumulative sufficiency against a declared, measured contract. It must be articulated, not assumed obvious — **and FR15 must actually be built, or the distinction is rhetorical**"

FR15 is the marginal-value requirement: reject steps "whose **expected benefit is low relative to its cost**." How is expected benefit computed? Q7:

> "How is 'low expected benefit' estimated in FR15? ... **Unset.** A fixed heuristic is acceptable for the MVP"

So the requirement the PRD nominates as the load-bearing differentiator is a TODO, and the acceptable answer is "a fixed heuristic." A fixed heuristic for marginal value is a guess with a threshold on it. If FR15 ships as `if estimated_tokens > remaining * 0.4: deny`, then the differentiator is a second budget cap wearing a different noun, and every word of §1.3 collapses into the "Gateway budget caps" column of its own table.

**How weak is the rebuttal?** §1.3 is well-argued *prose*. It is not backed by a mechanism. The rebuttal is currently rhetorical by the PRD's own admission, and it will remain rhetorical until Q7 is answered.

**Credit where due:** the survey hedge — "it is a survey — not a proof of absence" plus naming the two unverifiable vendors — is unusually disciplined and I will not attack the white-space claim. It is correctly scoped to "no mechanism we could examine." That is honest. It also means the category claim rests on an admittedly incomplete survey, which is a reason not to lead a two-minute video with it.

**Severity: CRITICAL** (baseline ambiguity), **CRITICAL** (FR15 unspecified).

---

## Attack 2 — The savings claim, which does not exist

There is no savings claim. That is not hyperbole:

| Metric | Target |
|---|---|
| Net token reduction | **To be set** |
| Net cost reduction | **To be set** |
| Tool-call reduction | **To be set** |

> "this PRD carries the measurement obligation, not a number" (§3.1)

I respect the reasoning. Discounting a gross number by guesswork *is* worse than admitting you do not know. But understand what you have handed me: **a product whose one-sentence pitch is "measurably fewer tokens" and whose PRD contains no number, and no floor below which the project would be considered to have failed.** There is not even a "we will abandon this if net savings are under X%." A 3% net reduction and a 45% net reduction both satisfy this PRD equally. That is not a target; it is an option to declare victory at whatever the measurement returns.

Worse: FR62's overhead study *produces* the number, and the study runs on the built governor. The number therefore lands at the end of a one-month window with no time to respond if it is bad. Q1 makes this explicit and then waves it through:

> "At what task length does the governor stop paying for itself? ... Answered by FR62; **not blocking the build**"

If break-even is longer than the tasks anyone runs, the product does not work. Declaring the viability question non-blocking is the single clearest instance of the PRD deferring the question it most needs answered early. A one-day spike measuring evaluator + planner + compression token cost per step on a toy loop would de-risk the entire project and is not scheduled.

### Where the number could be true but meaningless

Six ways, in descending order of how badly they'd hurt at judging:

1. **Attribution.** *Nothing in this PRD requires the savings to be decomposed by mechanism.* FR13 splits task work from governor overhead; FR59 reports overhead as a line item. Neither answers: how much of the reduction came from `stop-sufficient`, versus from the duplicate-tool cache that Kong ships today? If 85% of the win is deduplication, the headline number is true and the product is a cache. **This is a genuine gap, not a hedge — the doc has no requirement covering it.**
2. **The builder authored the cases.** Admitted: "Every savings figure derives from cases the builder authored" (§11.2), NFR9 "synthetic cases only." Synthetic cases can be tuned — even unconsciously — to have a clean sufficiency point at iteration three. A case set where sufficiency is obvious is a case set where sufficiency-stopping wins.
3. **The builder authored the baseline.** See Attack 1.
4. **The builder authored the gate that declares quality held constant.** The proof card (FR69) reports savings "with the quality verdict held constant" — constant per the gate the same person wrote.
5. **The builder is the blind reviewer.** Admitted, in the sharpest note in the document: "the blind reviewer is the same person who wrote the rubric and built the optimizer." FR64 blinds the verdict and the configuration. It cannot blind the author from his own case set.
6. **Sample size unset.** Q6: "**Unset.**" FR57 refuses to publish below a minimum that does not exist yet.

### What I would demand before I credit any number

- **Ablation runs.** Governor ON with *only* cache + loop fuse, versus full governor. The delta between those two is the actual product. Everything else is table stakes shipped by four vendors in the addendum's own table.
- **A stated failure threshold.** "Below N% net, we report this as a negative result." §8.3 mandates publishing failures; it never contemplates the whole project being one.
- **The overhead spike before the build, not after it.**
- **One reviewer who is not the builder.** Even one. Even for ten runs.
- **Break-even in tasks, on screen.** "Pays for itself above N steps" is a more credible headline than any percentage, and it is the number that survives hostile questioning.

**Severity: HIGH** (no number, no floor), **HIGH** (no per-mechanism attribution requirement), **MEDIUM** (break-even declared non-blocking).

---

## Attack 3 — The quality gate: determinism is bought by narrowing "quality"

FR18 is the PRD's proudest defensive move:

> "**Deterministic field-level validation SHALL be the authoritative gate.** A model-judged rubric MAY contribute an additional signal, but SHALL NOT override a deterministic failure and SHALL NOT alone establish a pass."

It works as a defence against "you moved the unreliability into the judge." It fails as a definition of quality, in three ways the PRD does not admit.

### 3a. The gate only works because the ground truth is synthetic — and the PRD never says so

FR17 requires "presence and **accuracy** of required evidence fields." Accuracy against *what*? On a synthetic case, against an answer key the builder wrote. That is deterministic. In Priya's production stream (UJ-1) there is no answer key. The deterministic gate degrades to **presence, shape and format** — which the addendum's own competitor table describes as already shipping:

> "Portkey ... Partial — checks are schema, regex, PII, gibberish"

**So the demo's gate and the production gate are different objects, and the PRD presents them as one.** The benchmark measures a gate that has ground truth; the adoption story sells a gate that does not. Nowhere does the document acknowledge that the authoritative signal is only authoritative inside the harness. This is a bigger hole than the judge-reliability attack the PRD spent so much effort pre-blocking.

### 3b. What field checks cannot see

Present, well-formed, correctly-typed, citation-bearing, and **wrong in judgment**. For the committed workload "research and investigation over a document corpus," the difference between a good output and a mediocre one is synthesis, prioritization, what was *not* said, and whether the conclusion follows. None of that enumerates into fields. A run that fills every required field with defensible-but-shallow content passes the authoritative gate and stops immediately (FR20: "On pass, the system SHALL stop immediately"). The three iterations that would have made it good are precisely the ones the product exists to prevent.

Bluntly: **field-completeness is a proxy for done-ness, not for goodness, and early stopping optimizes against the proxy.** The false-sufficiency counter-metric is the only thing standing between the product and Goodhart's law, and per Attack 2 it is self-graded on an unset sample.

### 3c. FR19 smuggles the judge back in

> "The gate SHALL additionally assess **tool-use quality** — whether the tools called were the right ones, whether their output was actually used, and whether denied calls were correctly denied."

"Were the right ones" is not deterministic. It is a judgment about counterfactual tool selection. Either FR19 is implemented by a model — in which case a model-judged signal sits in the authoritative gate path, breaking FR18's argument — or it is implemented as `did the tool output string appear downstream`, which is a usage check wearing the word "quality." FR19 is not marked cuttable in the appendix, unlike the FR18 rubric signal. **The document has not noticed that FR19 and FR18 are in tension.**

**Does the PRD admit any of this?** It admits rubric circularity, the judge-reliability attack, and reviewer bias — all well. It does not admit 3a, 3b or 3c. Those are the ones that matter.

**Severity: CRITICAL** (3a — gate is only deterministic under synthetic ground truth, unacknowledged), **HIGH** (3b), **MEDIUM** (3c).

---

## Attack 4 — Scope: this is a wish with a very good filing system

The document contradicts itself in two places about its own schedule, roughly forty lines apart.

> §4.3: "Roughly 7.5 days of estimated build work sits inside a one-month window, solo. **The schedule risk is low**; the replacement risk is gold-plating."

> §11.2: "This PRD commits a solo builder to seven mechanisms, four workloads, a harness, a replay UI and a submission artifact | **Material, and accepted deliberately.**"

Low, or material. Pick one. I will pick for you: **material**, and the 7.5-day figure is not credible. Here is what it purports to cover:

- 84 functional requirements across 16 features (Appendix)
- Seven enforcement mechanisms
- **Four** workloads, each needing mock tools, a synthetic case corpus with answer keys, and a frozen baseline
- FR49: "**at least two dissimilar agent implementations**" — a second integration axis, multiplied against the four workloads
- A harness that does frozen-config drift detection (FR61), replay-from-record (FR63), repeated runs, blind-review sampling (FR64), tool-suppression accuracy (FR65) and a break-even study (FR62)
- A replay web UI with concurrent dual-timeline playback and drill-down (FR66–FR71)
- A gateway metering integration with reconciliation (FR72–FR74)
- Two to three recruited interviews with production agent owners
- A two-minute video

The dismissal that makes it fit is one clause:

> "The harness is built once; each additional workload is then **mock tools plus cases**." (§4.1)

"Mock tools plus cases" for supply-chain exception investigation, SQL analysis, codebase triage and document research is not a rounding error. It is a realistic corpus, a plausible tool surface and an answer key **per workload** — and the answer keys are what the entire quality claim rests on (Attack 3a). This is the load-bearing estimate in the schedule and it is asserted in nine words.

**Nothing in the PRD decomposes the 7.5 days.** There is no per-feature estimate anywhere in 84 requirements. A number with no decomposition, contradicted by the same document's risk table, defending the largest scope commitment in the document, is not a plan.

### The cut order is genuinely good — and its endpoint is Attack 1

§4.3 is the best-engineered section in the document. Naming the cut order in advance, protecting the submission artifact, and making NFR10 (independent disableability) a hard constraint so the cuts are "mechanically executable rather than aspirational" — that is real discipline and I will say so plainly. The `[NOTE FOR PM]` conceding that three of seven mechanisms are sacrificial is more honesty than I have seen all week.

But follow it to the end. Execute cuts 1 through 8 and what remains is: contract file, ledger, deterministic gate, dedup cache, loop fuse, benchmark. **That is a retry loop with a schema check and a counter.** The cut order's terminal state is precisely the thing Attack 1 accuses the product of being — and the PRD, having designed the cut order so carefully, never asks whether the post-cut artifact still supports the §1.3 claim. It doesn't. §8.4 says "claims narrow with it," which is the right principle stated at the wrong altitude; it needs to say *which* claim survives which cut.

**Severity: HIGH** (undecomposed and self-contradicted estimate), **MEDIUM** (post-cut artifact does not support the positioning).

---

## Attack 5 — The demo: 120 seconds, and the differentiator is invisible

FR75 mandates four beats — problem, artifact, proof, scale — in at most two minutes. Thirty seconds each. FR78 requires the video show "at minimum the Outcome Contract, a governor decision stream, and **a stop caused by sufficiency**."

**Here is the problem: a sufficiency stop and a `max_iterations` stop look identical on screen.** Both are a run ending and a log line. The visible artifact of the entire product thesis is the string `stop-sufficient` in a decision stream, next to a number. Nothing on that screen distinguishes "stopped because it was done" from "stopped because a counter fired," and nothing on that screen shows that stopping was *correct*. I have watched forty demos where a number went down. I discount all of them.

The proof card (FR69) reports net tokens, cost and calls "with the quality verdict held constant" — held constant by the system's own gate. On camera, that is a product grading its own homework in 4-point type.

### The counter-metrics cannot fit, and the PRD's own standard requires them

§3.3 commits:

> counter-metrics "are reported with equal prominence to the savings figures"

§8.4 extends the evidence obligations to the submission: "These obligations apply to the submission artifact exactly as they apply to a written report (FR76, FR77)."

Equal prominence to savings, inside a thirty-second proof beat, means fifteen seconds of false-sufficiency rate, tool-suppression accuracy, escalation rate, overhead share and added latency. Either the video breaks §3.3 or the video is unwatchable. **FR75–FR78 do not resolve this** — FR76 and FR77 govern *labeling* (net not gross, self-reported, shadow vs enforced), not *co-reporting the counter-metrics*. That is a real gap between §3.3 and F16.

### The video depends on the first thing you cut

F14 is cut position 1. FR69's proof card and FR67's human-readable decision stream live in F14. F16 is protected and requires exactly those two artifacts on screen (FR78, and the proof beat). **The PRD protects the video and sacrifices the surface the video films, without declaring a fallback rendering.** Presumably CLI output substitutes — but the document does not say so, and "we'll show terminal output" is a materially weaker two-minute artifact than a side-by-side replay. This dependency is unstated anywhere in §4.3, F14 or F16.

**Is the demo the same thing as the product working?** No — and §1.5 principle 3 already knows it: "Turn the UI off and the savings still happen. The interface is evidence, not product." Correct principle. It also means the two minutes I actually score show me the evidence layer, while the claim lives in a harness I will not run.

**Severity: HIGH** (sufficiency stop is visually indistinguishable from a step cap), **MEDIUM** (F16 depends on F14, which is cut position 1), **MEDIUM** (counter-metric prominence unachievable in 120s).

---

## Attack 6 — Where the confidence is unearned

Three places the prose gets ahead of the evidence.

**1. §1.3, the money line:**

> "**the mechanisms surveyed stop a run when it runs out. OutcomeFuse stops a run when it is done.**"

Beautifully written. Unearned *today*, because "when it is done" is determined by FR15 (design: unset) and FR18 (deterministic only under synthetic ground truth). The sentence is a promissory note on two open items. The hedging paragraph immediately after it is excellent and correctly scopes the survey — but it hedges the *competitive* claim, not the *mechanism* claim. Nobody hedges the mechanism claim anywhere in the document.

**2. §4.3, "The schedule risk is low."** Contradicted forty lines later by its own risk table. The most confident sentence about the hardest constraint, with zero decomposition behind it.

**3. UJ-1's invented statistic:**

> "on 61% of runs, the outcome met your declared floor two iterations before the agent stopped"

A specific two-digit figure, in a document that spends §8 demanding provenance for every number. Yes, §6 is `[ASSUMPTION]`-flagged and says the journeys "SHOULD NOT be quoted externally as user research." That flag saves it from being dishonest. It does not save it from being the number a skimming reader remembers, and it will get quoted. Replace it with "a majority" and lose nothing.

**Where the confidence IS earned — and it is not a small list:**

- **§1.4, net not gross.** "Gross savings are how this category flatters itself. Net is the only number that survives scrutiny." That is the correct falsifiable claim, correctly stated, and it is rarer than it should be.
- **§3.3, the counter-metrics.** Naming the perverse optimum — "the system that stops earliest always wins" — and then instrumenting against it with false-sufficiency rate and tool-suppression error rate, at equal prominence, is a level of self-adversarialism I did not see in the other forty.
- **§10, the fail-open/fail-closed asymmetry.** "losing an optimization costs money; losing the gate costs correctness. Only one of those is allowed to fail quietly." This is correct engineering, correctly justified, and FR79–FR84 implement it cleanly. Strongest section in the document.
- **FR26 / FR84, distinguishing sufficiency from stuck from fail-closed.** Most systems conflate these. This one refuses to, three separate times.
- **§8.1's baseline-fairness reasoning and §11.1's bias note.** Naming that you are the interested party is worth more than any mitigation you could put next to it.
- **§4.3's cut order and NFR10.** See Attack 4.

I want to be clear that this document is well above the median of what I read this week. That is exactly why the remaining holes are worth this much ink — a weaker PRD would not deserve the attention.

---

## Minor findings

- **FR46 vs FR55.** §4.1 says shadow mode is "a measurement instrument, capturing governed and ungoverned paths from a single run," and FR46 repeats it. But FR44 describes the governed path as "**the estimated effect**" of decisions not taken, and FR47 correctly forbids presenting shadow figures as realized savings. FR55 then requires the harness to actually "execute a frozen case set against baseline and governed configurations." So shadow mode cannot be the measurement instrument for any reportable figure — it is an adoption tool. §4.1's second justification for shadow mode is weaker than it reads. **Low/medium.**
- **FR20 timing.** "On pass, the system SHALL stop immediately." When does the gate first run? If after every step, gate cost scales with steps and eats the savings on short tasks; if only at plausible completion points, something must decide what those are, and nothing specifies it. Adjacent to Q1/FR62 but not covered by them. **Low.**
- **Interview recruitment.** "Two to three structured conversations with engineers who own a production agent" (§4.1) is treated as a build task with a build estimate. It is a recruitment gamble with an external dependency and no declared fallback. Every `[ASSUMPTION]` flag on the persona and all four journeys unblocks on it. **Medium** — cheap to fix by declaring what happens if zero interviews land.
- **Eight cut positions, F15 at position 8, F15 not in the §4.3 cut list.** The §4.3 list has eight numbered entries; F15 "Advanced platform integrations" is item 8 and the appendix labels F15 "Cut position 8." Consistent — but FR72–FR74 provide the *independent* token measurement, which is the answer to "you counted your own tokens." Making the credibility of the headline measurement the last thing cut is right; the PRD should say that is why, rather than filing it under "advanced platform integrations."

---

## Severity summary

| # | Attack | Severity |
|---|---|---|
| 1a | Baseline "conventional evaluator/retry loop" already stops on sufficiency — either the flagship waste category doesn't exist or §8.1's no-strawman pledge breaks | **Critical** |
| 1b | FR15, the named differentiator, has no design (Q7 "Unset"); §11.2 concedes the distinction is rhetorical without it | **Critical** |
| 3a | Deterministic gate is only deterministic under synthetic answer keys; degrades to schema checking in production, and the PRD never says so | **Critical** |
| 2a | No savings target, no failure floor; number arrives at end of build via FR62 with no time to react | **High** |
| 2b | No requirement anywhere to attribute savings per mechanism — headline could be 85% cache | **High** |
| 3b | Field-completeness is a proxy for done-ness, not goodness; early stopping optimizes the proxy | **High** |
| 4a | "Schedule risk is low" vs "Material, and accepted deliberately"; 7.5 days undecomposed across 84 FRs, 4 workloads, 2 agent implementations | **High** |
| 5a | Sufficiency stop is visually identical to a step cap; the differentiator does not survive video | **High** |
| 2c | Break-even (Q1) declared "not blocking the build" — it is the viability question | **Medium** |
| 3c | FR19 tool-use quality is not deterministic, sits in the authoritative path, not marked cuttable | **Medium** |
| 4b | Post-cut-order artifact no longer supports the §1.3 positioning; §8.4 doesn't map claims to cuts | **Medium** |
| 5b | F16 (protected) depends on F14 (cut position 1); no fallback rendering declared | **Medium** |
| 5c | §3.3 "equal prominence" for counter-metrics is unachievable in 120s; FR76/77 cover labeling only | **Medium** |
| 6c | Invented "61%" in UJ-1 inside an evidence-disciplined document | **Low** |
| — | FR46 shadow-as-measurement-instrument is weaker than §4.1 claims | **Low** |
| — | No fallback if agent-owner interviews don't materialize | **Medium** |

---

## The five things that would change my score

1. **Define the baseline's stopping behaviour in one sentence** and state what it does when its evaluator passes. Attack 1a dies or the project does.
2. **Specify FR15's heuristic now**, even badly. A named, wrong heuristic is defensible; an unset one is not a differentiator.
3. **Add a requirement for per-mechanism savings attribution and an ablation run** (cache + fuse only, versus full). Without it the headline is unattributable.
4. **State plainly that the deterministic gate depends on ground truth**, and say what it degrades to in production. Owning this converts your biggest unadmitted hole into another instance of the honesty that is already this document's strongest asset.
5. **Spike the overhead measurement before building**, and declare a net-savings floor below which the result is published as negative. §8.3 requires publishing failures; give yourself the definition of one.
