"""Frozen-in defects, and the rule that they must be told (§8.2, FREEZE.md).

> The freeze may be amended only while **no run of any kind exists**. From the
> moment the first run is recorded the freeze is final: a defect found
> afterwards is **worked around and disclosed in the submission, never fixed.**

Runs exist. So everything below is permanent for this submission, and the
submission carries it.

The registry is checked rather than trusted. `Submission` refuses to validate
unless every entry here appears in its disclosures, because a disclosure that
is merely *encouraged* is the first thing cut when a deadline arrives and the
number looks good — and the entries below are precisely the ones that make the
number look worse.

To be explicit about the thing the rule exists to prevent: each of these was
found *after* measurements existed, so it is now known which way amending the
freeze would move the result. That knowledge is the contamination. Fixing them
would produce a better number and a worthless one.
"""

from __future__ import annotations

from typing import Final

from pydantic import BaseModel, ConfigDict, Field


class Disclosure(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    key: str = Field(min_length=1)
    #: What is wrong, in terms a reader who did not build this can check.
    finding: str = Field(min_length=1)
    #: Why it was not fixed. Almost always the freeze being final.
    why_not_fixed: str = Field(min_length=1)
    #: What was done instead, and what it costs the result.
    workaround: str = Field(min_length=1)
    #: Which way the defect pushes the headline. `against` means it makes the
    #: reported result worse than a corrected one, `for` means better — and a
    #: `for` is the one a reader should weigh hardest.
    direction: str = Field(pattern="^(for|against|neutral|unknown)$")


FROZEN_DEFECTS: Final[tuple[Disclosure, ...]] = (
    Disclosure(
        key="one-pass-is-not-a-measurement",
        finding=(
            "supply-chain was run twice over the identical frozen cases, the same "
            "contract, the same models and the same preregistration. The headline "
            "moved 37 points: the first pass reduced tokens 30.2% and cost 75.9% at "
            "5 of 7 correct in both arms, and the second *increased* tokens 6.7%, "
            "reduced cost 31.0%, and produced only 4 comparable pairs. The escalation "
            "rate went from 0.43 to 0.71. Nothing changed but the sampling. At eight "
            "cases per workload, a single pass cannot distinguish a 20% effect from "
            "noise, which means the preregistered target was never measurable by the "
            "design that was registered to measure it."
        ),
        why_not_fixed=(
            "The case set is frozen and runs exist, so the split cannot be enlarged. "
            "Repeating every workload and averaging would be the right design, and "
            "adopting it now -- after seeing which way the second pass moved -- is "
            "choosing a method by its result."
        ),
        workaround=(
            "The first pass stands as the reported result because it was the "
            "pre-committed one, not because it is the flattering one. The second is "
            "published beside it in `runs/rerun` rather than discarded, since the "
            "variance is the finding: it says every figure in this submission should "
            "be read as one draw, and that the 30.2% reduction reported for "
            "supply-chain is substantially luck. The second pass was run to capture "
            "tool identities the first did not record, and its numbers are reported "
            "only because suppressing an unflattering measurement one happens to hold "
            "is the whole failure this apparatus exists to prevent."
        ),
        direction="against",
    ),
    Disclosure(
        key="sufficiency-stop-never-fires-early",
        finding=(
            "The product's central claim is stopping on sufficiency rather than on "
            "exhaustion. As measured, the sufficiency stop never shortens a run. The "
            "quality gate can only evaluate a deliverable, and the frozen prompts ask "
            "the agent to 'stop when you judge the [task] dispositioned, then emit the "
            "final JSON object' — one deliverable, at the end. So the gate fires after "
            "the agent has already stopped asking for tools (measured at event 21 of "
            "24) and confirms a result rather than causing one. Across the calibration "
            "campaigns, 100% of the token saving is attributed to "
            "'agent-stopped-unaided' and 0% to any governor mechanism."
        ),
        why_not_fixed=(
            "The prompts are inside the freeze and runs exist, so §8.2 makes them "
            "final. Reaching an early stop needs the agent to emit interim "
            "deliverables the gate can evaluate mid-run, which is a change to the "
            "shared task block that both arms receive byte-identical."
        ),
        workaround=(
            "It is reported rather than implied. FR62's breakdown names "
            "'agent-stopped-unaided' explicitly instead of crediting the gate for a "
            "saving it did not cause, and the cost split separates model routing from "
            "token reduction. The other governing mechanisms do act: the budget ledger "
            "and the loop fuse cut runs short, and escalation retries on the stronger "
            "model when the gate fails — observed live on code-triage, where "
            "gpt-5-mini's answer was refused and the run continued on gpt-5. None of "
            "those *save* tokens, which is why the breakdown still credits them with "
            "none: escalation spends more to restore quality rather than less. The "
            "video cannot paper over it either: a confirming verdict and a real stop "
            "leave identical decision events, so each gate verdict now records whether "
            "it was consulted mid-run or at submission, and FR84's sufficiency-stop "
            "demonstration is refused unless a run shows the former."
        ),
        direction="against",
    ),
    Disclosure(
        key="doc-research-iteration-cap",
        finding=(
            "The doc-research contract allows 8 iterations. Measured live, both arms "
            "spend all 8 turns making one tool call each and neither reaches an answer: "
            "the workload requires selecting among 20 documents under a six-step "
            "precedence rule, which does not fit in 8 tool calls. Baseline and governed "
            "both score 0 on the cases tried, so the workload currently contributes no "
            "quality-matched pairs at all."
        ),
        why_not_fixed=(
            "The contract is inside the freeze and runs already exist, so §8.2 makes it "
            "final. The cap was set before any measurement, which is the point; raising "
            "it now would be an amendment chosen in full knowledge of what it does to "
            "the result."
        ),
        workaround=(
            "doc-research is reported as attempted and unscoreable rather than dropped "
            "quietly, and it is excluded from any generalisation claim under §8.4."
        ),
        direction="against",
    ),
    Disclosure(
        key="start-model-is-not-uniformly-better",
        finding=(
            "The contracts start the governed arm on gpt-5-mini and escalate. Measured "
            "on calibration, that is not uniformly good: on supply-chain it gives a "
            "~56% token reduction at equal quality, but on data-sql the governed arm "
            "fell to 1/3 passes against the baseline's 3/3 and used ~12% MORE tokens, "
            "because the smaller model flounders and pays for the flailing. Running "
            "both arms on gpt-5 restored 3/3 and a ~5% reduction."
        ),
        why_not_fixed=(
            "`models.start` is a frozen contract field and runs exist. The measurement "
            "that revealed this is exactly the knowledge §8.2 forbids acting on."
        ),
        workaround=(
            "Per-workload results are reported separately and never pooled into one "
            "cross-workload average, which would let supply-chain's result carry "
            "data-sql's. Where the governed arm loses, it is shown losing."
        ),
        direction="against",
    ),
    Disclosure(
        key="escalation-threshold-was-set-blind",
        finding=(
            "The preregistered escalation-rate threshold is 0.30, and every workload "
            "measured breaches it: 0.43 on supply-chain and 0.63 on data-sql at "
            "evaluation, 0.36 and 0.83 at calibration. That refusal is what stops the "
            "savings figures being published. The threshold was chosen before any run "
            "existed and therefore before anyone knew how often gpt-5-mini fails this "
            "quality floor, so it encodes an assumption about the start model rather "
            "than a measured property of the system."
        ),
        why_not_fixed=(
            "FR66 fixes targets and thresholds before the evaluation set is touched, "
            "and the whole value of doing that is lost the moment a threshold moves "
            "because the result came back wrong. A threshold revised after seeing the "
            "number it refuses is not a threshold."
        ),
        workaround=(
            "It stands, and the headline stays refused. Reporting it this way keeps "
            "two findings apart that a revision would have merged: the claim was not "
            "supported, and the threshold may have been miscalibrated. The second is "
            "a reason to preregister differently next time, never a reason to publish "
            "this time."
        ),
        direction="unknown",
    ),
    Disclosure(
        key="code-triage-fix-summary-is-a-vocabulary-lottery",
        finding=(
            "code-triage scored 0 of 8 on the evaluation set in BOTH arms, including "
            "the gpt-5 baseline, so no proof card exists for it at all. The cause is "
            "the instrument, not the models. `fix-summary-substantive` is a regex "
            "requiring forty characters and one of ten literal verbs (add, remove, "
            "guard, reorder, rename, clamp, await, close, validate, initialise), and "
            "the frozen prompt asks only for 'what is wrong and what would correct "
            "it' -- it never discloses the list. Sampling ten real deliverables, nine "
            "failed, and all ten were accurate, specific diagnoses. Two further traps "
            "compound it: the list spells `initialise` in British English while models "
            "write `initialize`, and `\\bvalidate\\b` does not match `validate_lines` "
            "because the underscore is a word character, so a summary naming the very "
            "function at fault is rejected for naming it."
        ),
        why_not_fixed=(
            "The contract, the rubric and the prompt are all inside the freeze, and "
            "runs exist. This is precisely the defect §8.2 anticipated: one found by "
            "measuring, whose fix would improve our own numbers."
        ),
        workaround=(
            "code-triage is reported as measured and unscoreable, never dropped and "
            "never re-scored. Its 0/8 must not be read as a capability result for "
            "either model. It also inflates the escalation-rate counter-metric, since "
            "runs escalated to gpt-5 over a spelling rule -- by contrast supply-chain's "
            "escalations are genuine, driven by root-cause and recommended-action "
            "mismatches against the key, so that workload's refusal stands on real "
            "grounds and is not excused by this."
        ),
        direction="unknown",
    ),
    Disclosure(
        key="verdict-applied-never-emitted",
        finding=(
            "AD-2's canonical event order lists `verdict-applied` between "
            "`decision-recorded` and `outcome-observed`, and no driver emits one, so "
            "`check_order` reports a finding for every decision of every correct run."
        ),
        why_not_fixed=(
            "Pre-existing since E7 and reaching it needs the adapter to report back "
            "that it applied the verdict, which is an E7/E10 interface change."
        ),
        workaround=(
            "The finding is known and ignored by the reader rather than silenced in the "
            "checker, so the checker keeps its meaning for every other ordering rule."
        ),
        direction="neutral",
    ),
    Disclosure(
        key="conformance-covers-the-reference-adapter",
        finding=(
            "AD-15's battery is run and passed, but it is run against the reference "
            "adapter in adapters/host/reference. The campaign drives its own loop "
            "(harness/runner.py), which shares the Driver, the ports and the record "
            "spine with it but is not itself put through the six scenarios. So "
            "`adapter_passed_conformance` is true of the adapter the battery "
            "measured, not of every line of code that produced the runs."
        ),
        why_not_fixed=(
            "The battery's substitution scenario asserts that a substituted step "
            "runs a cheaper *tool*; the campaign loop substitutes by returning a "
            "cached result and running no tool at all. Both are valid "
            "substitutions, but making the loop pass would mean editing the "
            "specification every adapter is measured against so that this one "
            "passes it — fitting the test to the code, after results exist."
        ),
        workaround=(
            "The battery is run at campaign time and its real verdict is recorded, "
            "never asserted. The loop's own verdict-honouring is covered by the "
            "runner's tests instead: that a denied call does not reach the tool "
            "port, that a terminal verdict stops the loop, and that a refusal is "
            "reported to the agent as a refusal."
        ),
        direction="unknown",
    ),
    Disclosure(
        key="attribution-is-per-run-not-per-decision",
        finding=(
            "FR62's per-mechanism breakdown credits each case's token saving to the "
            "mechanism that *terminated* that run. A case stopped by the quality "
            "gate may also have had tool calls denied along the way, and the gate "
            "is credited for the whole of it."
        ),
        why_not_fixed=(
            "Decomposing within a run needs a counterfactual — what the run would "
            "have done had a denied tool been allowed — and no such run exists. An "
            "invented one would make the breakdown finer and less true."
        ),
        workaround=(
            "The granularity is stated rather than implied. Tool-call reductions "
            "are counted exactly and reported separately, and the cost split "
            "between governing and model routing is exact arithmetic on measured "
            "token counts rather than an estimate."
        ),
        direction="unknown",
    ),
    Disclosure(
        key="cost-is-list-price-not-billed",
        finding=(
            "Cost is computed from published list prices (cost table ct-2: Azure "
            "OpenAI Global rates for gpt-5 and gpt-5-mini, 2025-08-07, read from the "
            "vendor's pricing page with the GlobalStandard deployment SKU confirmed "
            "against the resource itself). It is not reconciled against an invoice, "
            "and any enterprise agreement discount would lower the real figure for "
            "both arms."
        ),
        why_not_fixed=(
            "An invoice for these runs does not exist yet, and reconciling one would "
            "not change the ratio the claim rests on: both arms are priced from the "
            "same table, so a uniform discount cancels."
        ),
        workaround=(
            "The cost table version travels in every run manifest, so any figure can "
            "be re-derived against a different table. Token and tool-call reductions "
            "are counted rather than priced and do not depend on this at all."
        ),
        direction="neutral",
    ),
    Disclosure(
        key="doc-research-citations-minimum-was-never-requested",
        finding=(
            "The doc-research contract makes `citations-sufficient` mandatory and "
            "requires at least two distinct citations. The frozen baseline prompt "
            "asks only for 'citations array objects {\"id\": \"<doc_id>\"} supporting "
            "the answer' and states no minimum anywhere. On the evaluation split the "
            "consequence is measurable: dr-e-001, 003, 004 and 005 each returned the "
            "CORRECT answer_code and the CORRECT primary_source_id with exactly one "
            "citation and were failed; dr-e-006, the only case passing either arm, is "
            "the only deliverable carrying two. Six of eight cases were answered "
            "correctly and the gate passed one. The requirement also sits awkwardly "
            "with the task itself, which exists to identify the single document that "
            "governs -- rejected documents already have their own field."
        ),
        why_not_fixed=(
            "Contract and prompt are both inside the freeze and runs exist, so "
            "FREEZE.md makes both final. Correcting either now would be done in full "
            "knowledge of which way it moves the result, which is the contamination "
            "the rule exists to prevent."
        ),
        workaround=(
            "doc-research is reported as defective and supports no claim. The "
            "measured gate failures are reported as what they are -- a floor failing "
            "correct answers on an unannounced structural requirement -- rather than "
            "as evidence about model capability. This also supersedes the earlier "
            "reading recorded under `doc-research-iteration-cap`: on the evaluation "
            "split the runs DO reach answers and the answers are largely right."
        ),
        direction="against",
    ),
    Disclosure(
        key="false-sufficiency-threshold-is-unreachable-at-n-4",
        finding=(
            "The preregistration sets false-sufficiency-rate at 0.05 and the blind "
            "review sample at 4. The smallest non-zero rate expressible from four "
            "items is 1/4 = 0.25, so the threshold can be met only by zero "
            "rejections and is breached five-fold by a single one. The metric is a "
            "pass/fail on 'did the reviewer reject anything', not a rate. The "
            "supply-chain review recorded 4 reviewed and 1 rejected."
        ),
        why_not_fixed=(
            "Both numbers were preregistered before any evaluation result was "
            "executed or inspected, which is the property that makes them worth "
            "anything. Enlarging the sample or loosening the threshold now would be "
            "done knowing the result, and a target adjusted after the fact cannot be "
            "reported as met."
        ),
        workaround=(
            "The rate is reported with its denominator visible, so a reader can see "
            "it is one rejection out of four rather than a stable rate. No claim "
            "rests on false-sufficiency being below threshold, because on this design "
            "it could not have been demonstrated."
        ),
        direction="unknown",
    ),
    Disclosure(
        key="write-tools-were-gated-by-authoring-habit-not-validation",
        finding=(
            "Contract validation checks that a human-approval condition names a "
            "declared tool, but never checked the converse: that a tool declared "
            "`side_effecting: true` carries a condition at all. Three of the four "
            "contracts gate every write on `always` and doc-research declares none "
            "because it has no write tools. The fourth does not: code-triage gates "
            "`run_tests` at `call_index_exceeds: 3`, so its first three invocations "
            "proceed with no human asked."
        ),
        why_not_fixed=(
            "The contracts are frozen and runs exist. The validation rule itself is "
            "code rather than a frozen artefact and has been tightened (FR122), but "
            "the code-triage contract it would now refuse cannot be amended."
        ),
        workaround=(
            "The rule is stated as a requirement so it binds every future contract, "
            "and the code-triage deviation travels with any claim drawn from that "
            "workload. No headline figure depends on it: code-triage produced no "
            "campaign card."
        ),
        direction="neutral",
    ),
    Disclosure(
        key="a-blind-review-verdict-was-revised-after-its-result-was-seen",
        finding=(
            "The data-sql blind review was answered, recorded, and then changed. The "
            "reviewer first accepted all four items, which recorded 0 of 4 rejected "
            "and a false-sufficiency rate of 0.000 -- a pass. The reviewer was shown "
            "that number, then revised items 3 and 4 to reject, which re-recorded as "
            "2 of 4 and a rate of 0.500. The drawn sample and its seed never changed; "
            "`prepare` refuses to re-draw over an existing answer set, so only the "
            "judgements moved. The record cannot distinguish honest reconsideration "
            "from a verdict adjusted to taste, and it should not be asked to."
        ),
        why_not_fixed=(
            "Nothing here is repairable by re-running: a reviewer who has seen a "
            "result cannot be made not to have seen it, and re-drawing the sample "
            "would destroy the one property the two-phase design exists to protect. "
            "The blind review is a single human judgement on four items and always "
            "was."
        ),
        workaround=(
            "The sequence is published rather than the final number alone. Two facts "
            "weigh against the obvious reading: the revision moved the result "
            "*against* the project, from a pass to a ten-fold breach, which is the "
            "opposite direction from tuning; and items 3 and 4 carry defensible "
            "grounds -- item 4 reports a USD figure its cited SQL does not compute, "
            "selecting only cents and a row count. Both figures are stated wherever "
            "this workload's review is cited, and no claim rests on either."
        ),
        direction="unknown",
    ),
)

DISCLOSURE_KEYS: Final[frozenset[str]] = frozenset(d.key for d in FROZEN_DEFECTS)
