"""Reading the six counter-metrics off a campaign (FR66, §3.3).

The preregistration sets a threshold for each of six metrics, and until now
nothing computed any of them. A threshold with no reading is decoration; the
record said so itself when it refused a metric without one.

**A metric that was not measured reports as unmeasured, never as zero.** This is
the whole design. Zero means "we looked and found none". `None` means "nobody
looked". They render identically on a slide and mean opposite things, and the
one that flatters is the one that happens by accident — a counter-metric
defaulting to 0.0 passes every threshold it has, forever, while looking like
evidence. So a reading carries its basis, `check_accompaniment` is told only
about the metrics actually read, and FR66 refuses a headline whose reported
metrics have no threshold.

Two of the six cannot be read from a campaign alone and say so:

- **false-sufficiency-rate** needs FR69's blind review — a human who never saw
  the verdict, so the review can contradict it. A machine cannot supply it,
  because the gate is the thing under suspicion and asking it to grade itself
  answers a different question.
- **tool-suppression-error-rate** needs suppressions to check. Measured live,
  the governor suppressed nothing at all (0 of 26 tool calls were exact
  repeats), so there is no rate — which is not the same as a rate of zero.
"""

from __future__ import annotations

from typing import Any, Final

from pydantic import BaseModel, ConfigDict, Field

from ..evidence.counter_metrics import BlindReview
from .overhead import OverheadStudy
from .preregistration import COUNTER_METRICS, Preregistration

#: Lower is better for all six, so a reading breaches by exceeding.
LOWER_IS_BETTER: Final[frozenset[str]] = COUNTER_METRICS


class Reading(BaseModel):
    """One counter-metric, or an honest admission that it was not read."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    metric: str = Field(min_length=1)
    #: `None` means not measured. It is never coerced to zero.
    value: float | None = None
    threshold: float | None = None
    #: What the number was computed from, in terms a reader can check.
    basis: str = Field(min_length=1)

    @property
    def measured(self) -> bool:
        return self.value is not None

    @property
    def breached(self) -> bool:
        """An unmeasured metric does not breach. It also does not pass."""
        if self.value is None or self.threshold is None:
            return False
        return self.value > self.threshold

    def rendered(self) -> str:
        if self.value is None:
            return f"{self.metric}: not measured ({self.basis})"
        against = f" (threshold {self.threshold})" if self.threshold is not None else ""
        flag = "  BREACHED" if self.breached else ""
        return f"{self.metric}: {self.value:.4g}{against}{flag}"


class CounterMetrics(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    readings: tuple[Reading, ...]

    @property
    def measured(self) -> tuple[Reading, ...]:
        return tuple(r for r in self.readings if r.measured)

    @property
    def unmeasured(self) -> tuple[Reading, ...]:
        return tuple(r for r in self.readings if not r.measured)

    @property
    def breaches(self) -> tuple[Reading, ...]:
        return tuple(r for r in self.readings if r.breached)

    @property
    def reported(self) -> tuple[str, ...]:
        """Only what was actually read. Accompaniment is told this, not all six."""
        return tuple(sorted(r.metric for r in self.measured))

    def rendered(self) -> str:
        return "\n".join(r.rendered() for r in self.readings)


def _rate(numerator: int, denominator: int) -> float:
    return 0.0 if denominator == 0 else round(numerator / denominator, 6)


def read_counter_metrics(
    report: Any,
    *,
    study: OverheadStudy | None = None,
    preregistration: Preregistration | None = None,
    blind_review: BlindReview | None = None,
    suppressions_checked: int = 0,
    suppression_errors: int = 0,
) -> CounterMetrics:
    """Read what the campaign supports, and admit the rest.

    `report` is a `CampaignReport`; it is untyped here only to keep the harness
    free of a cycle between the campaign and its own reporting.
    """
    thresholds = (
        dict(preregistration.counter_metric_thresholds) if preregistration else {}
    )
    results = list(report.results)
    card = report.proof_card() if results else None

    readings: list[Reading] = []

    # --- false sufficiency: FR69's blind review, or nothing -----------------
    if blind_review is not None:
        readings.append(
            Reading(
                metric="false-sufficiency-rate",
                value=round(blind_review.false_sufficiency_rate, 6),
                threshold=thresholds.get("false-sufficiency-rate"),
                basis=(
                    f"{blind_review.rejected} of {blind_review.reviewed} gate passes "
                    "rejected by a blind human review"
                ),
            )
        )
    else:
        readings.append(
            Reading(
                metric="false-sufficiency-rate",
                threshold=thresholds.get("false-sufficiency-rate"),
                basis=(
                    "FR69 requires a blind human review, which no campaign can "
                    "produce: the gate is the thing under suspicion, so asking it "
                    "to grade itself answers a different question"
                ),
            )
        )

    # --- tool suppression: needs suppressions to check ----------------------
    if suppressions_checked:
        readings.append(
            Reading(
                metric="tool-suppression-error-rate",
                value=_rate(suppression_errors, suppressions_checked),
                threshold=thresholds.get("tool-suppression-error-rate"),
                basis=(
                    f"{suppression_errors} of {suppressions_checked} suppressions "
                    "failed re-execution or counterfactual check (FR70)"
                ),
            )
        )
    else:
        readings.append(
            Reading(
                metric="tool-suppression-error-rate",
                threshold=thresholds.get("tool-suppression-error-rate"),
                basis=(
                    "the governor suppressed nothing, so there is no rate. Not a "
                    "rate of zero: nothing was checked"
                ),
            )
        )

    # --- escalation: measurable from the runs themselves --------------------
    escalated = sum(1 for r in results if r.governed.escalations)
    readings.append(
        Reading(
            metric="escalation-rate",
            value=_rate(escalated, len(results)) if results else None,
            threshold=thresholds.get("escalation-rate"),
            basis=(
                f"{escalated} of {len(results)} governed runs escalated to a stronger "
                "model after a gate failure"
                if results
                else "no runs"
            ),
        )
    )

    # --- governor overhead --------------------------------------------------
    readings.append(
        Reading(
            metric="governor-overhead-share",
            value=card.savings.overhead_share if card else None,
            threshold=thresholds.get("governor-overhead-share"),
            basis=(
                "the ledger's overhead holds as a share of governed tokens; zero "
                "while every registered mechanism is deterministic (E12 cut)"
                if card
                else "no proof card"
            ),
        )
    )

    # --- added latency: from the calibration study, not from the campaign ----
    readings.append(
        Reading(
            metric="added-latency",
            value=study.added_latency_p95_ms if study else None,
            threshold=thresholds.get("added-latency"),
            basis=(
                f"p95 milliseconds per governed decision, calibration study "
                f"{study.digest().sha256[:12]}…, of which "
                f"{study.write_share_of_added_latency:.0%} is durable writes"
                if study
                else "no overhead study supplied"
            ),
        )
    )

    # --- budget breach ------------------------------------------------------
    breached = sum(1 for r in results if r.governed.terminal_reason == "budget-breach")
    readings.append(
        Reading(
            metric="budget-breach-rate",
            value=_rate(breached, len(results)) if results else None,
            threshold=thresholds.get("budget-breach-rate"),
            basis=(
                f"{breached} of {len(results)} governed runs exceeded the contract "
                "ceiling; the ledger holds before it spends, so a non-zero rate "
                "means the ledger is wrong"
                if results
                else "no runs"
            ),
        )
    )

    return CounterMetrics(readings=tuple(readings))
