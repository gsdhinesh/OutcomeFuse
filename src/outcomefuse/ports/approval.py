"""The approval port and its scripted decider (AD-12, FR89, FR95, FR100).

Approval is a real port, and its MVP implementation is a **scripted decider
driven by the case definition** — approve, deny, or never respond. A blocking
interactive prompt would make FR100's timeout cases untestable without a person
sitting in front of a harness whose entire value is reproducibility.

Two failure states are **distinct and must not be merged**, because FR2 ranks
them differently:

- **`channel-unavailable`** — the adapter cannot accept or create the request,
  or loses the decision channel of one it had accepted. Fail-closed; the gated
  call is not made.
- **`no-response`** — the request was accepted, the channel stayed available,
  and no decision arrived within `approval_timeout`. The contract's `on_timeout`
  applies.

Collapsing the second into the first would route an ordinary timeout to
`fail-closed`, which sits *above* the approval gate in the ladder, changing both
the run's terminal reason and what the caller receives.
"""

from __future__ import annotations

from typing import Literal, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

Decision = Literal["approved", "denied", "no-response", "channel-unavailable"]


class ApprovalRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    run_id: str = Field(min_length=1)
    step_id: str = Field(min_length=1)
    tool: str = Field(min_length=1)
    clause: str = Field(min_length=1)
    timeout_seconds: int = Field(gt=0)


class ApprovalOutcome(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    decision: Decision
    #: The triggering contract clause travels with the pause as its reason.
    clause: str

    @property
    def gated_call_permitted(self) -> bool:
        return self.decision == "approved"

    @property
    def is_channel_failure(self) -> bool:
        """Fail-closed under FR89 — ranked above the approval gate."""
        return self.decision == "channel-unavailable"


@runtime_checkable
class ApprovalPort(Protocol):
    def request(self, request: ApprovalRequest) -> ApprovalOutcome: ...


class ScriptedApprovalPort:
    """Driven by the case definition, so timeout cases are reproducible."""

    def __init__(self, script: dict[str, Decision] | None = None,
                 default: Decision = "approved") -> None:
        self._script = dict(script or {})
        self._default = default
        self.seen: list[ApprovalRequest] = []

    def request(self, request: ApprovalRequest) -> ApprovalOutcome:
        self.seen.append(request)
        decision = self._script.get(request.step_id, self._default)
        return ApprovalOutcome(decision=decision, clause=request.clause)
