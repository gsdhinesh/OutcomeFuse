"""Advisors propose; they never act (AD-4).

A mechanism is a **pure advisor**. In: read-only state. Out: either a proposal
or an `EvidenceRequest`. It never performs I/O and never mutates run state —
which is what makes replay feeding recorded outcomes back into a pure function.

Two properties here exist to stop the same run producing different totals under
two implementations:

- **Composition order is fixed, core-owned and versioned**, and recorded with
  the decision. Two orders yield different total savings for the same run.
- **Disabled means not registered.** No mechanism carries an `if enabled`
  branch, so an ablation is a registry change and is byte-identical to having
  cut the mechanism.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Final, Literal, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

COMPOSITION_ORDER_VERSION: Final[str] = "v1"

#: Fixed, core-owned order. Advisors compose in this sequence regardless of
#: registration order, so the total is a property of the set, not the sequence
#: someone happened to register in.
COMPOSITION_ORDER: Final[tuple[str, ...]] = (
    "preflight-planner",
    "context-governor",
    "tool-governor",
    "model-governor",
    "marginal-value",
    "quality-gate",
)

EvidenceKind = Literal[
    "rubric-judgement",
    "compression-pass",
    "complexity-estimate",
    "confidence-estimate",
    "planner-envelope",
]

#: Bounded and recorded in the manifest: an advisor cannot drive a decision
#: round the loop forever by asking for one more piece of evidence.
MAX_REINVOCATIONS: Final[int] = 3


class EvidenceRequest(BaseModel):
    """A closed, core-owned sum type with a declared outcome schema per kind."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: EvidenceKind
    mechanism: str = Field(min_length=1)
    args: dict[str, Any] = Field(default_factory=dict)
    estimated_tokens: int = Field(default=0, ge=0)
    estimated_cost: float = Field(default=0.0, ge=0)


#: What the driver must return for each kind. The driver appends the outcome
#: and re-invokes the advisor with it; a kind whose outcome does not match its
#: schema is a driver bug, caught here rather than downstream.
OUTCOME_SCHEMA: Final[dict[str, frozenset[str]]] = {
    "rubric-judgement": frozenset({"verdict", "verification_mode", "unmet"}),
    "compression-pass": frozenset({"capsule", "tokens_before", "tokens_after"}),
    "complexity-estimate": frozenset({"score"}),
    "confidence-estimate": frozenset({"score"}),
    "planner-envelope": frozenset({"steps", "max_tokens", "max_estimated_cost"}),
}


class Proposal(BaseModel):
    """A suggested action, an estimate, and a candidate reason code.

    Candidate: the Policy decides. An advisor proposing `low-value` against an
    unmet mandatory criterion is rejected by the Policy (AD-18), which is why
    the estimator may only ever *propose* it.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    mechanism: str = Field(min_length=1)
    step_id: str = Field(min_length=1)
    action: str
    candidate_reason: str
    estimated_tokens: int = Field(default=0, ge=0)
    estimated_cost: float = Field(default=0.0, ge=0)
    #: Which mandatory criteria this step would establish, verify or correct.
    #: The Policy reads this to apply FR17's floor protection.
    advances_criteria: tuple[str, ...] = ()
    detail: dict[str, Any] = Field(default_factory=dict)


@runtime_checkable
class Advisor(Protocol):
    """Pure: read-only state in, proposal or evidence request out."""

    name: str

    def advise(self, state: Any) -> Proposal | EvidenceRequest | None: ...


class AdvisorRegistry:
    """Run-scoped (AD-20). A deregistration never survives the run.

    Fail-open is a property of this registry: an advisor that raises is
    deregistered for the remainder of the run and execution continues without
    it, with a `degraded` event naming the mechanism. Degraded is not disabled —
    the manifest records the enabled set at start; the log records what dropped.
    """

    def __init__(self, advisors: dict[str, Advisor] | None = None) -> None:
        self._advisors: dict[str, Advisor] = dict(advisors or {})
        unknown = sorted(set(self._advisors) - set(COMPOSITION_ORDER))
        if unknown:
            raise ValueError(f"advisors outside the composition order: {unknown}")
        self.deregistered: list[str] = []

    @property
    def enabled(self) -> tuple[str, ...]:
        return tuple(n for n in COMPOSITION_ORDER if n in self._advisors)

    @property
    def degraded(self) -> bool:
        return bool(self.deregistered)

    def compose(
        self, state: Any, *, on_degraded: Callable[[str, Exception], None] | None = None
    ) -> list[Proposal | EvidenceRequest]:
        """Invoke every registered advisor in the fixed order."""
        collected: list[Proposal | EvidenceRequest] = []
        for name in COMPOSITION_ORDER:
            advisor = self._advisors.get(name)
            if advisor is None:
                continue
            try:
                produced = advisor.advise(state)
            except Exception as exc:  # noqa: BLE001 - fail-open is the posture
                del self._advisors[name]
                self.deregistered.append(name)
                if on_degraded is not None:
                    on_degraded(name, exc)
                continue
            if produced is not None:
                collected.append(produced)
        return collected


def outcome_is_well_formed(kind: EvidenceKind, outcome: dict[str, Any]) -> bool:
    """Whether a driver's fulfilment matches the declared schema for its kind."""
    return OUTCOME_SCHEMA[kind] <= set(outcome)
