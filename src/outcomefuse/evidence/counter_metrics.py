"""The counter-metrics (FR69, FR70, FR71, FR99).

These are what make the headline falsifiable. Without them the savings number is
unfalsifiable, and §8.3 forbids publishing it at all.

Two of them are easy to compute dishonestly, so both are shaped to prevent it:

- **Tool-suppression accuracy** is established by *re-execution against the
  frozen tools* — a mechanical check. A model's opinion may not contribute,
  because that would make the counter-metric depend on the same judgement it
  exists to police. A suppression that cannot be checked is reported
  **unverified**, never assumed correct.
- **Error rate is `1 - accuracy`**, returned from the same computation. They are
  one measurement reported in two directions and are never computed
  independently, which is how they would otherwise drift apart.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

SuppressionKind = Literal["cache-hit", "duplicate", "optional-satisfied"]
Confirmation = Literal["correct", "incorrect", "unverified"]


class Suppression(BaseModel):
    """One tool call the governor suppressed."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    run_id: str
    step_id: str
    tool: str
    kind: SuppressionKind
    #: What the run used instead of executing the call.
    reused_result: Any = None


class SuppressionAccuracy(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    suppressed: int = Field(ge=0)
    confirmed_correct: int = Field(ge=0)
    confirmed_incorrect: int = Field(ge=0)
    unverified: int = Field(ge=0)

    @model_validator(mode="after")
    def _counts_reconcile(self) -> SuppressionAccuracy:
        total = self.confirmed_correct + self.confirmed_incorrect + self.unverified
        if total != self.suppressed:
            raise ValueError(f"outcomes cover {total} of {self.suppressed} suppressions")
        return self

    @property
    def accuracy(self) -> float:
        """Unverified counts against accuracy; it is never assumed correct."""
        return 0.0 if self.suppressed == 0 else self.confirmed_correct / self.suppressed

    @property
    def error_rate(self) -> float:
        """§3.3's counter-metric, from the same measurement rather than its own."""
        return 1.0 - self.accuracy


def measure_suppression_accuracy(
    suppressions: list[Suppression],
    *,
    re_execute: Callable[[Suppression], Any] | None = None,
    counterfactual_verdict: Callable[[Suppression], str] | None = None,
    observed_verdict: str | None = None,
) -> SuppressionAccuracy:
    """FR70. Correctness is established mechanically, never by opinion.

    `re_execute` runs the suppressed call against the frozen case's tool
    implementation. `counterfactual_verdict` runs the case *including* the
    denied optional call. Where either is unavailable for a suppression, that
    suppression is `unverified`.
    """
    correct = incorrect = unverified = 0

    for suppression in suppressions:
        if suppression.kind in {"cache-hit", "duplicate"}:
            if re_execute is None:
                unverified += 1
                continue
            try:
                fresh = re_execute(suppression)
            except Exception:  # noqa: BLE001 - an unrunnable tool is unverified, not correct
                unverified += 1
                continue
            if fresh == suppression.reused_result:
                correct += 1
            else:
                incorrect += 1
        else:
            # An optional-call denial is correct only if including the call
            # would not have changed the verdict.
            if counterfactual_verdict is None or observed_verdict is None:
                unverified += 1
                continue
            try:
                verdict = counterfactual_verdict(suppression)
            except Exception:  # noqa: BLE001 - same reasoning
                unverified += 1
                continue
            if verdict == observed_verdict:
                correct += 1
            else:
                incorrect += 1

    return SuppressionAccuracy(
        suppressed=len(suppressions),
        confirmed_correct=correct,
        confirmed_incorrect=incorrect,
        unverified=unverified,
    )


class CompressionFidelity(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    attributable_facts: int = Field(ge=0)
    survived: int = Field(ge=0)
    lost: tuple[str, ...] = ()

    @property
    def fidelity(self) -> float:
        return 1.0 if self.attributable_facts == 0 else self.survived / self.attributable_facts

    @property
    def intact(self) -> bool:
        """FR38 forbids dropping an attributable fact, so anything under 1.0 fails."""
        return not self.lost


def measure_compression_fidelity(
    raw_facts: list[str], capsule: str
) -> CompressionFidelity:
    """FR71, so FR38 is verified rather than asserted."""
    lost = tuple(fact for fact in raw_facts if fact not in capsule)
    return CompressionFidelity(
        attributable_facts=len(raw_facts),
        survived=len(raw_facts) - len(lost),
        lost=lost,
    )


class MarginalValueDenial(BaseModel):
    """FR99. Reported separately from FR70: different mechanisms, different mistakes."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    run_id: str
    step_id: str
    unmet_mandatory_at_decision: tuple[str, ...]
    advances_criteria: tuple[str, ...]
    estimated_benefit: float
    estimated_cost: float
    policy_action: str

    @property
    def blocked_the_floor(self) -> bool:
        return bool(set(self.advances_criteria) & set(self.unmet_mandatory_at_decision))

    @property
    def complied(self) -> bool:
        return not self.blocked_the_floor


class DenialReport(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    denials: tuple[MarginalValueDenial, ...]

    @property
    def savings(self) -> tuple[MarginalValueDenial, ...]:
        return tuple(d for d in self.denials if d.complied)

    @property
    def violations(self) -> tuple[MarginalValueDenial, ...]:
        """A denial that blocked progress toward an unmet mandatory criterion."""
        return tuple(d for d in self.denials if not d.complied)

    @property
    def estimated_saving(self) -> float:
        # Violations are excluded: reporting one as a saving is the specific
        # dishonesty FR99 exists to prevent.
        return sum(d.estimated_cost for d in self.savings)


class BlindReview(BaseModel):
    """FR69. The reviewer never saw the verdict, so this can contradict it."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    reviewed: int = Field(ge=0)
    rejected: int = Field(ge=0)
    sample_size: int = Field(gt=0)

    @model_validator(mode="after")
    def _sample_is_complete(self) -> BlindReview:
        if self.rejected > self.reviewed:
            raise ValueError("more rejections than reviews")
        if self.reviewed < self.sample_size:
            raise ValueError(
                f"{self.reviewed} of {self.sample_size} preregistered reviews are complete; "
                "a partial sample cannot establish the rate"
            )
        return self

    @property
    def false_sufficiency_rate(self) -> float:
        """Runs the gate passed that a blind human review fails."""
        return 0.0 if self.reviewed == 0 else self.rejected / self.reviewed
