---
title: "PRD Quality Review — OutcomeFuse (F17 update pass)"
created: 2026-09-14
scope: "Weighted toward F17 / FR72–FR77 / FR110–FR117 and reconciled sections; whole-document assessment"
---

# PRD Quality Review — OutcomeFuse

## Overall verdict

This remains an unusually disciplined PRD: it names its own perverse optimum, pairs every headline number with one that can embarrass it, and states the honest limit of its strongest claim (§8.2a) rather than burying it. The F17 substitution was made with the same nerve — the schedule risk row says plainly that "F17 increased it," design principle 3 was *amended* rather than quietly dropped, and FR97's prior move of proof-card computation into F13 meant the supersession cost the submission nothing.

What is at risk is reconciliation, not judgment. F17 introduced a new fail-closed condition (`channel-unavailable`), a new personal-data field (approver identity), and a new reporting category (`human-approved`) — and each was integrated into the *prose* sections that discuss it while being missed by the *machinery* sections that would have to carry it: FR104's reason registry, FR100's failure-case battery, NFR12's access matrix, and the harness path that would actually produce a `human-approved` run. None of these is a judgment error; all four are places where an implementer following the document hits a contradiction or a hole.

Verdict: **ship-ready on substance, not yet clean for handoff.** Four high-severity reconciliation gaps, all in changed material, all narrow.

---

## Decision-readiness — **strong**

The F17 change is presented as a decision with its cost attached, which is the hard part and the part most PRDs duck. §4.3 opens with "F17 made it worse rather than better." The §11.2 schedule row restates it as "**Material, accepted deliberately — and F17 increased it.**" The "surface becomes the product" risk names the failure mode in the first person — "the pull is to spend evidence time on it, and for the submission to acquire a dependency on it without anyone deciding to" — and then names the three structural defences rather than promising vigilance. F16's note goes further than it had to: "This holds even though F17 is now the most demonstrative thing in the build."

The reopening of Q5 is handled correctly. Rather than editing the old resolution away, it reads "**Re-opened and re-resolved — both,**" and names what was superseded. Q10 is genuinely open — "Whether a threshold on that rate is the right instrument is unresolved and rides with the Q8 thresholds" — not a rhetorical question with its answer in the next clause.

The one place the document smooths something is the protected-core bullet, addressed under Scope honesty below.

### Findings

- **medium** Approval-pause wall-clock has no stated relationship to the "Added latency" counter-metric (§3.3, FR117) — FR117 rules that "surface cost SHALL NOT be attributed to governor overhead," and the reasoning is exact ("charging it to overhead would make the net figure depend on whether anyone was watching"). It says nothing about *latency*. §3.3 defines added latency as "Wall-clock cost of governor decisions per step," and an approval pause is a governor decision that can consume minutes of wall clock. As written, a single interactive approval would dominate the latency counter-metric for its run. *Fix:* add one clause to FR117 excluding time spent inside an FR34 pause from the added-latency counter-metric, and state where that time *is* reported instead — the FR115 elapsed-time field is the obvious home.

---

## Substance over theater — **strong**

F17 is not furniture. The test is whether removing it would cost the document an argument, and it would: FR112's second rule — "**Suppressed calls SHALL appear in the tree with their reason** … and SHALL NOT be omitted because they did not execute" — is doing product work, not presentation work, and the accompanying note earns it ("a view showing only the calls that ran would render the governor invisible, because everything it did, it did to the calls that did not").

UJ-5 is the strongest new material in the document. It survives the persona-theater test because the two things it demonstrates are both load-bearing and neither is the interface: that denials are visible, and that Marcus "decided from the clause and the trail rather than from the payload — which is what makes FR112's redaction survivable in practice rather than only on paper." The journey is an argument that a redacted approval surface is *usable*, which is a claim the PRD needed and could not make abstractly.

FR114's note is the opposite of NFR theater — it enumerates the specific interface events that would cause the defect ("a dialog that dismisses on an outside click, a socket that drops and reconnects into fresh state, a tab closed while a pause is open") rather than asserting robustness. NFR12 continues to carry real numbers (60 / 180 calendar days, a named profile `mvp-synthetic-v1`, an explicit access matrix) where boilerplate would say "appropriate retention."

No findings.

---

## Strategic coherence — **strong**

The thesis survives the change intact, and the change was checked against it explicitly: FR117's note reduces design principle 3 to an accounting rule — "If watching a run changed its net number, the number would be measuring the audience." FR110's second paragraph catches a naming collision that would have corrupted the headline figure ("A live view that quietly enabled it to feel more responsive would trade the product's central number for an animation"), which is exactly the kind of cross-check that distinguishes a thesis from a feature list.

The counter-metric discipline extended to the new surface rather than exempting it: §3.3's escalation row now reads "an approval surface that is pleasant to use is exactly the thing that would let human load grow without appearing in any figure." That is the right instinct — see the finding below for where the instrument doesn't match it.

### Findings

- **medium** Requirement mass is inversely proportional to survival probability (F17 vs §4.3 cut position 1) — F17 now carries fourteen FRs, a dedicated user journey, five glossary entries, two risk rows and an Appendix B split, and sits **first** in the cut order. The PRD is internally consistent about this, but it means the single largest block of newly specified detail describes the component most likely not to exist. The asymmetry is not flagged anywhere as a planning input, and §4.3's `[NOTE FOR PM]` addresses only the seven-mechanisms narrative. *Fix:* add a sentence to §4.3's cut item 1 or the F17 preamble stating that FR110–FR112's specification depth is deliberate insurance against a *partial* build, not a signal of priority — or, if the intent is that F17 will in fact be built, say so and move it off cut position 1.

- **medium** §3.3's escalation rate conflates two different phenomena — the row counts "interactively granted approvals" into a metric defined as "Share of runs requiring model escalation or human intervention." A contract-declared approval gate on mutating tools fires on *every* qualifying run by design; it is a fixed property of the contract, not a signal that the governor pushed work onto a person. Folding it into the same figure as FR24 escalations means escalation rate becomes partly a function of contract authoring, and cross-workload comparison stops meaning anything. The intent behind the amendment is right; the instrument is blunt. *Fix:* split the row into `governor-initiated escalation rate` and `contract-gated approval rate`, or report interactive approvals as a declared sub-component of the figure so a threshold can be set against the part the governor controls. Q10 already senses this — "Whether a threshold on that rate is the right instrument is unresolved" — but does not name the conflation as the reason.

---

## Done-ness clarity — **adequate**

Most F17 requirements are testable as written. FR111 is unusually good: it enumerates the node fields and then adds the constraint that makes it verifiable — "**Nesting SHALL be derived from fields already recorded; no parent/child relationship SHALL be added to the record spine for the surface's benefit,**" with a stated consequence ("A sealed run therefore renders the same tree as a live one"). FR110's three prohibitions (no store read in progress, no writer lock, no altered sealing) are each independently checkable. FR114 is a clean negative requirement with an enumerated event list. FR116 hooks the control into an existing battery rather than inventing a new one.

The gaps are where F17 introduced new vocabulary and new run categories without wiring them into the mechanisms that would test or type them. Two of the four are hard contradictions rather than omissions.

### Findings

- **high** `channel-unavailable` has no home in the FR1 / FR104 type system (FR113, §9, §10.2) — FR113 states "the outcome SHALL be **`channel-unavailable`**," and §9 repeats it as a first-class value ("An absent or unreachable surface is `channel-unavailable` and fail-closed"). But FR1 fixes three recorded fields, FR104 requires `decision_reason` to be "a stable code drawn from a **versioned, extensible registry**," and the registry's Governance family lists only `approval-required` · `approval-granted` · `approval-denied` · `approval-timeout`. `channel-unavailable` is not a `policy_action`, not a registered `decision_reason`, and not a `terminal_reason` (FR113 maps the *halt* to `fail-closed`). An implementer cannot record it without violating FR104. *Fix:* add `channel-unavailable` to FR104's Governance family, and state in FR113 that it is the `decision_reason` while `fail-closed` is the `terminal_reason` — the FR103 table already has the shape for this row.

- **high** FR100's failure-case battery was not reconciled with F17's new fail-closed path — FR100 enumerates "sufficiency stop, budget exhaustion, no-progress halt, approval timeout under **both** `on_timeout` postures, Quality Gate unavailable, Budget Ledger state loss, and optimization-mechanism failure." Approval-channel unavailability is absent, despite being newly elevated by FR113, restated in §9 as the distinction that "matters for the same reason §9 separates a timeout from an outage," and already present in §10.2 via FR89. FR100's own note says "Untested failure paths are the ones that turn out, under demonstration, to have been aspirations" — and this is now the newest untested one. *Fix:* add an approval-channel-unavailable case to FR100's list, asserting `channel-unavailable` as the reason and `fail-closed` as the terminal reason, with the gated call not made.

- **high** Nothing in the PRD produces a `human-approved` run that could support a reported figure (FR115, FR113, FR82, FR84) — FR115 builds real apparatus for interactive runs: a recorded transcript, a `human-approved` label, FR68 satisfaction by replaying the transcript through the scripted port, and a bar ("A run whose approvals were not recorded SHALL NOT be reported"). §8.4 carries the label into claim discipline. But FR113's own note says "the scripted port remains the channel every harness run uses," FR82 requires every submission figure to trace to "an **evaluation-set** harness run," and FR102 seals the evaluation set. No requirement says whether an evaluation-set run may be executed interactively, or which harness path yields a `human-approved` run at all. FR84 assumes one exists — "Where the submission shows the F17 step tree or an approval pause, it SHALL do so over a run that satisfies FR82 and carries its FR115 label." As written, that run has no way of coming into being. *Fix:* state in FR102 or FR115 whether interactive execution is permitted against the sealed evaluation set and under what controls; if it is not, amend FR84 to say the submission's approval pause is shown over a calibration or demonstration run and is explicitly not a source of figures.

- **medium** No requirement establishes that the FR115 approver identity is authentic (F17, Appendix B) — FR115 requires the identity to be *recorded*; nothing requires the surface to authenticate it, and F17 carries no authentication requirement at all. Appendix B's guard table nonetheless claims "A human really approved it → FR115 recorded approval transcript, FR116 out-of-band side-effect probe." FR116 proves the gated call did not go out early; it says nothing about who resolved the pause. For a single-operator synthetic MVP this is tolerable, but the guard-table row overstates what the requirements deliver, and §2.3's compliance persona is the reader who would notice. *Fix:* either add an authentication clause to FR113/FR115, or soften the Appendix B row to "A human decision was recorded against a gate that was genuinely held open," and note the identity-assurance gap as a post-MVP item alongside Q9.

- **low** "the unit of work proposed" (FR111) is undefined and is the one node field with no redaction rule — FR112 is explicit that "Tool arguments and tool results SHALL NOT be displayed, transmitted, cached or persisted by the surface," and NFR5 redacts prompts. FR111's first node field sits outside both rules and is not in the glossary. If a proposed unit of work is a prompt or a tool invocation, the surface is rendering the thing FR112 exists to keep off it. *Fix:* define the term in Appendix A and state that it is rendered as the step's declared intent, never as prompt or argument text.

- **low** `scripted-approved` is used as a normative label in FR115 and §8.4 but never defined — it appears only as the contrast to `human-approved`. Whether a run with no approval pauses at all is `scripted-approved` or uncategorized is unstated. *Fix:* one glossary line, or drop the label and define `human-approved` as the only positive marking.

---

## Scope honesty — **strong**

The F14 supersession is handled with more care than the situation demanded. F14's heading survives as a tombstone with the reason attached — "**FR72–FR77 are retained and amended inside F17, not withdrawn** — identifiers are never reused or renumbered" — and Appendix B repeats the rule at document level. The addendum's §3 entry is candid about what was lost: F14's inertness "was doing real argumentative work, because it is what made 'turn the UI off and the savings still happen' true without qualification," followed by the three fences that replaced the blanket prohibition. That is a de-scoping-and-re-scoping argument made in public.

F17's preamble volunteers where the build cost went and what was bought back ("F14 avoided live execution to duck concurrency, cancellation and error-state handling… What remains is one subscriber and one modal pause, not a concurrent dual-run renderer"). §4.3's cut item 1 is precise about what is and is not cuttable, including the awkward middle case.

Open-items density is high — Q4, Q6, Q8 and now Q10 all unresolved — but every one is gated by the same mechanism (FR66 preregistration before any evaluation-set result is executed or inspected), which converts them from loose ends into a scheduled event. That is the correct handling for a PRD that is green-lighting a build.

### Findings

- **medium** The protected core promises "human-approval enforcement" but no *human* channel is protected (§4.3) — the protected-core list reads "**human-approval enforcement (FR34, FR95)**," and the note under it is honest as far as it goes: "The obligation is protected; no particular channel is. Cutting the F17 approval control leaves FR34 enforced through the scripted port." What it does not say is that the scripted port answers approvals *from a script*, so in the fully-cut configuration the MVP contains no channel by which an actual person can resolve a gate. The pause, the enforcement and the audit trail are all protected; human participation is not. That is a defensible MVP position and it is the one thing the bullet's own wording obscures. *Fix:* reword to "approval-gate enforcement (FR34, FR95)" and add a clause: in the cut configuration the gate is resolved by the scripted port, and no interactive human channel exists.

- **medium** Approver identity is real personal data persisted under a profile justified for synthetic data (NFR12, FR109) — NFR12 places approver identity on the 180-day redacted tier and calls it "the only personal identifier the record carries," then defers it: "it SHALL be covered by the production-data governance profile required by FR109 before any non-synthetic use." But FR109 triggers on the *run's* declared data class, not on the *record's* contents. A `synthetic` run approved by a real person produces a real identifier under `mvp-synthetic-v1` — a profile the PRD elsewhere justifies on the grounds that it "was written for data the builder authored." The data was authored; the approver was not. *Fix:* state in NFR12 that the approver identity field is governed by record content rather than run data class, and either name the acceptable MVP form (opaque operator handle, not an email or directory identity) or bring it under FR109's refusal.

---

## Downstream usability — **adequate**

This PRD is chain-top — the addendum is written as direct input to architecture ("Architecture should read FR77's amended form literally…"; "Architecture should encode it as a mapping, not re-derive it per call site") — so traceability carries real weight here.

Identifier hygiene is excellent and survived the change. FR1–FR117 are complete with no gaps or duplicates; Appendix B's per-feature ranges account for every one; the sixteen-live-features count (F1–F13, F15–F17) and twelve NFRs both check out. The supersession did not orphan a single reference — F14 appears only as a tombstone, in Appendix B, and in Q5's superseding note. The Appendix B "Requirements that guard the claims" table was extended for the new material rather than left stale.

The problem is one direct contradiction between a new normative constraint and three requirements it governs, plus a range that fell between two halves of a split.

### Findings

- **high** NFR12 forbids the store access that FR72, FR75 and FR76 require (NFR12 access matrix vs F17) — NFR12 states: "**The live execution surface (F17) holds no store access of any kind.** It observes the in-process decision stream (FR110) and never reads evidence, raw tool output or the record store." FR72 requires the surface to "present a recorded run identically **from its sealed log**"; FR76 requires it to "support drilling into a single run's decision record"; FR75 requires it to render the FR97 proof card. All three read stored artifacts. The intended rule is almost certainly *no store access for a run in progress* — which is what FR110 actually says — but NFR12 states it absolutely, and NFR12's access matrix is the normative one. An implementer cannot satisfy both. NFR12 compounds it by listing "the static viewer" among components with "no access at all," while the addendum's working assumption retains "static HTML … for the recorded side-by-side comparison." *Fix:* rewrite the NFR12 sentence as "holds no store access for a run in progress," and add explicit matrix rows for the replay path — read access to sealed decision records and proof artifacts, never to the raw evidence tier.

- **low** FR117 is allocated to neither half of the F17 split (NFR10, §4.3, Appendix A) — NFR10 enumerates "the observation half of F17 (FR72–FR77, FR110–FR112) and its approval control (FR113–FR116)"; §4.3's cut item 1 uses the same two ranges. FR117 appears in neither, yet it governs both (surface failure, and the approval-channel exception routing to FR89). Appendix A's "Observation surface" entry then assigns it to observation alone — "(FR77, FR117)" — which contradicts FR117's own approval-channel clause. *Fix:* state in NFR10 and §4.3 that FR117 applies to F17 as a whole regardless of which half is enabled, and correct the glossary citation.

---

## Shape fit — **strong**

The document is a chain-top technical capability spec that also ships an evaluated submission artifact, and it is shaped accordingly: FR-dense, evidence-standards-heavy (§8 is normative, not methodological), with UJs carrying only the load they can bear. The `[ASSUMPTION]` preamble to §6 is the right calibration — "they carry design intent, not evidence, and SHOULD NOT be quoted externally as user research" — and UJ-1 and UJ-4 each get a `[NOTE FOR PM]` where the narrative outruns what the MVP evidences.

Five UJs is at the upper bound for a solo one-month build, but none is floating: each has a named protagonist, and UJ-5 reuses UJ-2's Marcus rather than inventing a sixth persona to justify the new feature — a small discipline most PRDs fail. NFR11's build constraint ("Any requirement whose satisfaction depends on capability not demonstrable in that window SHALL be moved out of scope rather than carried as an unmet requirement") is the right shape-fit guard for the stakes, and §4.3 is where it gets teeth.

One shape observation rather than a finding: UJ-5 narrates the component at cut position 1, and unlike UJ-1 it carries no note about MVP demonstrability. Its `[NOTE FOR PM]` addresses what makes the journey work, not whether it will exist. Given how carefully UJ-1 was fenced (FR106, "Priya's week of real traffic is the adoption story, and it must not be narrated as something the MVP evidences"), the omission is visible. A single clause noting that UJ-5 depends on a cuttable surface would restore the symmetry.

No findings.

---

## Mechanical notes

- **No Assumptions Index.** The rubric expects `[ASSUMPTION]` tags "indexed at the end." Four inline tags exist — §2.1 (persona), FR59 (minimum case count), FR69 (blind-review sample size), §6 preamble (all journeys) — and there is no index section; Appendix A is the Glossary and Appendix B the Requirement Index. FR59's and FR69's unset numbers are recoverable via Q6 and Q4, but the persona and journey assumptions are only findable by reading linearly. A short Appendix C would close the roundtrip.
- **Glossary coverage of new vocabulary is good but incomplete.** Five F17 entries were added (Observation surface, Step tree, Approval control, Approval transcript, `human-approved`). Missing: `channel-unavailable` — a new normative value used in FR113, §9 and §11.2 — and `scripted-approved`. "Approval port" is used in FR113, NFR12 and the addendum without a glossary entry, though it is inferable.
- **Glossary drift, minor.** Appendix A's "Observation surface" cites "(FR77, FR117)"; NFR10 and §4.3 place FR117 outside the observation range. One of the three is wrong.
- **ID continuity: clean.** FR1–FR117 complete, unique, fully accounted for in Appendix B. The stated counts ("One hundred and seventeen… sixteen live features… twelve non-functional requirements") all verify. The non-contiguous-by-feature placement is explained rather than left to be discovered.
- **Cross-references resolve.** Spot-checked FR2↔FR103↔FR104, FR97↔FR75↔F16, FR113↔FR89↔§9, FR115↔§8.4↔NFR12, principle 3↔FR77↔FR117, Q5↔F14↔F17. All land. No dangling F14 reference survives outside its tombstone.
