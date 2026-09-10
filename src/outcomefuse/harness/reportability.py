"""Reportability is one predicate, evaluated by the harness alone (AD-10).

Three gates, and their strengths differ on purpose:

- **Admissibility — hard.** A failing run is *refused*, not labelled.
- **Independence — graded.** It degrades the label and never refuses: a figure
  that fell back to governor-side counting is `self-reported` rather than
  discarded, because the measurement is weaker, not absent.
- **Publication accompaniment — hard.** A bare savings number ships without the
  measurement that exists to refute it, or it does not ship.

No other component re-derives any of these. Each surface inventing its own
notion of which figures may be quoted is how a demo convenience leaks into a
judged claim.

**Reportable and presentable are different words.** A shadow arm may be
rendered, labelled `projected`, with its first divergence beside it; it may not
back a headline claim, because the governed path it describes never ran. So
shadow is a headline *refusal* rather than a blanket one, and the mode is read
off the manifest rather than passed in beside it.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from ..core.record import RunManifest
from .comparison import ComparisonRefused, require_comparable

Independence = Literal["measured", "self-reported", "projected"]


class RunFacts(BaseModel):
    """What the harness knows about one arm, apart from its manifest."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    adapter_passed_conformance: bool
    degraded_mechanisms: tuple[str, ...] = ()
    gateway_metered: bool = False
    gate_qualifier: str | None = None

    @property
    def degraded(self) -> bool:
        return bool(self.degraded_mechanisms)


class Accompaniment(BaseModel):
    """What must travel with a figure for it to be publishable."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    per_mechanism_breakdown: bool = False
    tool_suppression_accuracy: float | None = None
    reports_tool_call_reduction: bool = False
    case_count: int = 0
    minimum_case_count: int = 0
    coverage_report_hash: str | None = None
    predominantly_constraint_backed_declared: bool = False
    predominantly_constraint_backed: bool = False
    reports_failures_and_escalations: bool = False
    headline_is_net: bool = True
    counter_metric_thresholds: dict[str, float] = Field(default_factory=dict)
    counter_metrics_reported: tuple[str, ...] = ()


class Reportability(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    admissible: bool
    independence: Independence
    labels: tuple[str, ...]
    refusals: tuple[str, ...]

    @property
    def publishable(self) -> bool:
        return self.admissible and not self.refusals


def check_admissibility(
    baseline: RunManifest,
    governed: RunManifest,
    baseline_facts: RunFacts,
    governed_facts: RunFacts,
    *,
    headline: bool,
) -> list[str]:
    """Hard. A failing run is refused rather than labelled."""
    refusals: list[str] = []

    for name, manifest, facts in (
        ("baseline", baseline, baseline_facts),
        ("governed", governed, governed_facts),
    ):
        if not manifest.streaming_disabled:
            refusals.append(f"{name} arm streamed; token counts would be estimates")
        if not facts.adapter_passed_conformance:
            refusals.append(f"{name} adapter has not passed the conformance battery")
        if headline:
            if manifest.split != "evaluation":
                refusals.append(
                    f"{name} arm is a {manifest.split} run; only evaluation-set results "
                    "may support a headline claim"
                )
            elif manifest.preregistration_hash is None:
                refusals.append(f"{name} arm carries no preregistration hash")

    try:
        require_comparable(baseline, governed)
    except ComparisonRefused as exc:
        refusals.append(str(exc))

    return refusals


def grade_independence(
    baseline: RunManifest,
    governed: RunManifest,
    baseline_facts: RunFacts,
    governed_facts: RunFacts,
) -> tuple[Independence, list[str]]:
    """Graded. Degrades the label, never refuses."""
    labels: list[str] = []
    if "shadow" in {baseline.mode, governed.mode}:
        # FR49: never presented as realized savings.
        return "projected", ["projected"]

    metered = baseline_facts.gateway_metered and governed_facts.gateway_metered
    independence: Independence = "measured" if metered else "self-reported"
    if not metered:
        labels.append("self-reported")
    if baseline_facts.degraded or governed_facts.degraded:
        labels.append("degraded")
    if "constraint-backed" in {baseline_facts.gate_qualifier, governed_facts.gate_qualifier}:
        labels.append("constraint-backed")
    return independence, labels


def check_accompaniment(accompaniment: Accompaniment) -> list[str]:
    """Hard. A bare number ships with its refutation or not at all."""
    refusals: list[str] = []
    a = accompaniment

    if not a.per_mechanism_breakdown:
        refusals.append("a headline savings figure has no per-mechanism breakdown (FR62)")
    if a.reports_tool_call_reduction and a.tool_suppression_accuracy is None:
        # A tool-call reduction alone is maximised by denying everything.
        refusals.append(
            "a tool-call reduction is reported without tool-suppression accuracy (FR70)"
        )
    if a.minimum_case_count and a.case_count < a.minimum_case_count:
        refusals.append(
            f"the workload has {a.case_count} cases, below its declared minimum "
            f"of {a.minimum_case_count} (FR59)"
        )
    if not a.headline_is_net:
        refusals.append("a gross figure is presented as the headline (FR61)")
    if not a.reports_failures_and_escalations:
        refusals.append("successes are presented without failures and escalations (FR63)")
    if a.coverage_report_hash is None:
        refusals.append("the workload result carries no verification-mode coverage report")
    if a.predominantly_constraint_backed and not a.predominantly_constraint_backed_declared:
        refusals.append(
            "the workload is predominantly constraint-backed and is not labelled as such"
        )
    unthresholded = sorted(
        m for m in a.counter_metrics_reported if m not in a.counter_metric_thresholds
    )
    if unthresholded:
        refusals.append(
            f"counter-metrics reported without a preregistered threshold: {unthresholded}"
        )

    return refusals


def assess(
    baseline: RunManifest,
    governed: RunManifest,
    baseline_facts: RunFacts,
    governed_facts: RunFacts,
    accompaniment: Accompaniment,
    *,
    headline: bool = True,
) -> Reportability:
    admissibility = check_admissibility(
        baseline, governed, baseline_facts, governed_facts, headline=headline
    )
    independence, labels = grade_independence(
        baseline, governed, baseline_facts, governed_facts
    )
    accompaniment_refusals = check_accompaniment(accompaniment) if headline else []
    return Reportability(
        admissible=not admissibility,
        independence=independence,
        labels=tuple(labels),
        refusals=tuple(admissibility + accompaniment_refusals),
    )
