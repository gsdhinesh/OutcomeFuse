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
        key="cost-table-unpriced",
        finding=(
            "Cost table ct-1 ships with null rates: nobody has read the vendor's pricing "
            "page, so no run has been priced."
        ),
        why_not_fixed=(
            "Not a freeze matter. The rates are simply unknown, and inventing a "
            "plausible one would produce a clean, arithmetically correct and entirely "
            "false cost saving that every check downstream would agree with."
        ),
        workaround=(
            "Every figure is reported in tokens and tool calls, which are counted rather "
            "than priced. No cost claim is made at all."
        ),
        direction="neutral",
    ),
)

DISCLOSURE_KEYS: Final[frozenset[str]] = frozenset(d.key for d in FROZEN_DEFECTS)
