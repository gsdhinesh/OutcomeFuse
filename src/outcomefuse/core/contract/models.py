"""The Outcome Contract as a typed model (FR7, FR8, FR10).

A contract executes no code (AD-7): a criterion selects a verifier by name from
the closed registry and parameterises it declaratively. Nothing here accepts an
import path, an expression or a callable.
"""

from __future__ import annotations

from typing import Any, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..canon import Digest, hash_structure
from ..verify.registry import VerificationMode, VerifierError, build_args, mode_for

Classification = Literal["E", "N", "A"]
Tier = Literal["mandatory", "optional", "advisory"]
OnTimeout = Literal["terminate", "escalate", "return-partial", "request-human"]

MAX_CRITERIA: Final[int] = 64
MAX_TOOLS: Final[int] = 32


class VerifierSpec(BaseModel):
    """A selection from the registry, never a reference to code."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    type: str
    args: dict[str, Any] = Field(default_factory=dict)

    @property
    def mode(self) -> VerificationMode:
        return mode_for(self.type)


class Criterion(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(min_length=1, max_length=128)
    description: str = ""
    classification: Classification
    verifier: VerifierSpec | None = None


class Criteria(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    mandatory: tuple[Criterion, ...] = ()
    optional: tuple[Criterion, ...] = ()
    advisory: tuple[Criterion, ...] = ()

    def tiers(self) -> list[tuple[Tier, Criterion]]:
        return [
            (tier, criterion)
            for tier in ("mandatory", "optional", "advisory")
            for criterion in getattr(self, tier)
        ]


class Deliverable(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    structure: dict[str, str]


class Reserve(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    max_tokens: int = Field(gt=0)
    max_estimated_cost: float = Field(gt=0)


class Budget(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    max_tokens: int = Field(gt=0)
    max_estimated_cost: float = Field(gt=0)
    verification_reserve: Reserve | None = None
    max_tool_calls: int = Field(gt=0)
    max_iterations: int = Field(gt=0)


class Tool(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(min_length=1)
    deterministic: bool
    side_effecting: bool


class Models(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    eligible: tuple[str, ...] = Field(min_length=1)
    start: str

    @model_validator(mode="after")
    def _start_is_eligible(self) -> Models:
        if self.start not in self.eligible:
            raise ValueError(f"start model {self.start!r} is not in eligible")
        return self


class Escalation(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    on_gate_fail: str
    max_escalations: int = Field(ge=0)
    never_breach_verification_reserve: bool


class ApprovalCondition(BaseModel):
    """Gated on a tool invocation or on a criterion's value, never both."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    tool: str | None = None
    criterion: str | None = None
    when: str
    value: Any = None

    @model_validator(mode="after")
    def _names_exactly_one_subject(self) -> ApprovalCondition:
        if (self.tool is None) == (self.criterion is None):
            raise ValueError("an approval condition names either a tool or a criterion")
        if self.when != "always" and self.value is None:
            raise ValueError(f"condition {self.when!r} needs a value")
        if self.when == "always" and self.value is not None:
            raise ValueError("condition 'always' takes no value")
        return self


class Contract(BaseModel):
    """Immutable for the duration of a run (FR10), and hashable (AD-6)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    contract_id: str = Field(min_length=1, max_length=128)
    version: int = Field(ge=1)
    workload: str = Field(min_length=1)
    task_goal: str
    deliverable: Deliverable
    criteria: Criteria
    budget: Budget
    tools: tuple[Tool, ...] = ()
    models: Models | None = None
    escalation: Escalation | None = None
    human_approval_conditions: tuple[ApprovalCondition, ...] = ()
    approval_timeout_seconds: int | None = Field(default=None, gt=0)
    #: `on_timeout` names a `policy_action`, so it draws from that vocabulary and
    #: not from `decision_reason` — `fail-closed` is a cause, never a disposition.
    #: Restricted further to the actions that can conclude an elapsed approval:
    #: proceeding or denying would let the gate be waited out.
    on_timeout: OnTimeout | None = None

    @model_validator(mode="after")
    def _structural_invariants(self) -> Contract:
        pairs = self.criteria.tiers()
        if len(pairs) > MAX_CRITERIA:
            raise ValueError(f"{len(pairs)} criteria, limit is {MAX_CRITERIA}")
        if len(self.tools) > MAX_TOOLS:
            raise ValueError(f"{len(self.tools)} tools, limit is {MAX_TOOLS}")

        ids = [criterion.id for criterion, in ((c,) for _, c in pairs)]
        duplicates = sorted({i for i in ids if ids.count(i) > 1})
        if duplicates:
            raise ValueError(f"duplicate criterion ids: {duplicates}")

        names = [tool.name for tool in self.tools]
        duplicate_tools = sorted({n for n in names if names.count(n) > 1})
        if duplicate_tools:
            raise ValueError(f"duplicate tool names: {duplicate_tools}")

        for condition in self.human_approval_conditions:
            if condition.tool is not None and condition.tool not in names:
                raise ValueError(f"approval condition names undeclared tool {condition.tool!r}")
            if condition.criterion is not None:
                known = set(self.deliverable.structure) | {c.id for _, c in pairs}
                if condition.criterion not in known:
                    raise ValueError(
                        f"approval condition names {condition.criterion!r}, which is "
                        "neither a deliverable field nor a criterion"
                    )

        # FR8, stated bluntly: if it cannot be checked, it is not the floor.
        for criterion in self.criteria.mandatory:
            if criterion.verifier is None:
                raise ValueError(
                    f"mandatory criterion {criterion.id!r} carries no executable verifier"
                )
            if criterion.classification != "E":
                raise ValueError(
                    f"mandatory criterion {criterion.id!r} is classified "
                    f"{criterion.classification!r}; only E may be mandatory"
                )

        for tier, criterion in pairs:
            if criterion.verifier is None:
                if criterion.classification != "A":
                    raise ValueError(
                        f"{tier} criterion {criterion.id!r} has no verifier but is "
                        f"classified {criterion.classification!r}"
                    )
                continue
            try:
                build_args(criterion.verifier.type, criterion.verifier.args)
            except VerifierError as exc:
                raise ValueError(f"criterion {criterion.id!r}: {exc}") from exc

        return self

    def mandatory_modes(self) -> dict[VerificationMode, int]:
        counts: dict[VerificationMode, int] = {
            "reference-backed": 0,
            "constraint-backed": 0,
        }
        for criterion in self.criteria.mandatory:
            if criterion.verifier is not None:
                counts[criterion.verifier.mode] += 1
        return counts

    def digest(self) -> Digest:
        """Identity under AD-6 (FR10, FR65)."""
        return hash_structure(self.model_dump(mode="json", exclude_none=True))
