"""The Policy: the only component that converts proposals into a decision (AD-4).

Three things live here because they must live in exactly one place:

- **The FR2 precedence ladder.** Where more than one terminating or blocking
  condition applies, the winner is fixed rather than incidental.
- **The FR103 mapping**, as a table rather than a chain of branches, because
  `terminal_reason` names the *cause* and never the disposition — and a run that
  exhausts its budget and returns a partial result has one of each.
- **AD-18's floor protection.** The marginal-value estimator is pluggable and
  may only ever *propose* `low-value`. The Policy rejects such a proposal where
  the step would establish, verify or correct an unmet mandatory criterion,
  discards it, and records the attempt so FR99 reports it as a violation rather
  than a saving. Putting this in the estimator would mean swapping the
  estimator silently removes the one rule the PRD calls non-negotiable.
"""

from __future__ import annotations

from typing import Final, Literal

from pydantic import BaseModel, ConfigDict

from .advisors import Proposal

Condition = Literal[
    "fail-closed",
    "human-approval",
    "sufficiency",
    "exhaustion",
    "no-progress",
    "step-denial",
]

#: FR2, in order. The winning condition is recorded as the decision reason; a
#: terminal reason is recorded only where the resulting action terminates.
PRECEDENCE_LADDER: Final[tuple[Condition, ...]] = (
    "fail-closed",
    "human-approval",
    "sufficiency",
    "exhaustion",
    "no-progress",
    "step-denial",
)


class Outcome(BaseModel):
    """The recorded triple. `terminal_reason` is absent where the run continues."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    decision_reason: str
    policy_action: str
    terminal_reason: str | None = None


class Situation(BaseModel):
    """What the Policy is asked about. Every field is a decision *input*.

    A port error is a decision input, never an escape — which is why gate
    unavailability and ledger loss appear here as booleans rather than as
    exceptions unwinding through the Policy.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    floor_met: bool = False
    budget_remains: bool = True
    affordable_step_advances_floor: bool = True
    no_progress: bool = False
    quality_state: str = "not-evaluated"
    gate_failed: bool = False
    gate_unavailable: bool = False
    ledger_state_lost: bool = False
    approval_elapsed: bool = False
    on_timeout: str | None = None
    #: What the contract directs when the gate fails or the floor is unreachable.
    contract_directs: Literal["return-partial", "request-human"] = "return-partial"


#: FR103, as data. Every row is (condition, decision_reason, policy_action,
#: terminal_reason) — nine rows, matching the PRD table exactly.
FR103_TABLE: Final[tuple[tuple[str, str, str, str | None], ...]] = (
    ("floor met, budget remains", "sufficiency", "terminate", "stop-sufficient"),
    (
        "floor unmet, nothing affordable advances it",
        "exhaustion",
        "return-partial",
        "halt-exhausted",
    ),
    (
        "floor unmet, nothing affordable advances it, contract directs human",
        "exhaustion",
        "request-human",
        "halt-exhausted",
    ),
    (
        "floor unmet, budget remains, no progress across N iterations",
        "no-progress",
        "terminate",
        "halt-no-progress",
    ),
    (
        "gate fails, budget remains, contract directs human review",
        "escalation-gate-fail",
        "request-human",
        "referred-human",
    ),
    (
        "gate fails, budget remains, contract directs partial return",
        "escalation-gate-fail",
        "return-partial",
        "returned-partial",
    ),
    ("approval gate elapsed, on_timeout terminates", "approval-timeout", "terminate",
     "approval-timeout"),
    ("approval gate elapsed, on_timeout escalates", "approval-timeout", "escalate", None),
    ("gate cannot produce a verdict", "fail-closed", "request-human", "fail-closed"),
    ("ledger state lost", "fail-closed", "terminate", "fail-closed"),
)


class FloorViolation(BaseModel):
    """A rejected `low-value` proposal. FR99 reports these as violations."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    step_id: str
    mechanism: str
    criteria: tuple[str, ...]
    detail: str = (
        "low-value was proposed against an unmet mandatory criterion; the marginal-value "
        "estimator governs enrichment, never the floor"
    )


class Policy:
    """Stateless except for the violations it records."""

    def __init__(self) -> None:
        self.violations: list[FloorViolation] = []

    def resolve(self, situation: Situation) -> Outcome:
        """Apply the FR2 ladder and return the FR103 triple."""
        # 1 — fail-closed: the system cannot establish its own state.
        if situation.ledger_state_lost:
            return Outcome(
                decision_reason="fail-closed", policy_action="terminate",
                terminal_reason="fail-closed",
            )
        if situation.gate_unavailable:
            return Outcome(
                decision_reason="fail-closed", policy_action="request-human",
                terminal_reason="fail-closed",
            )

        # 2 — a declared human gate outranks any automated decision.
        if situation.approval_elapsed:
            if situation.on_timeout == "escalate":
                # The run continues, so no terminal reason is recorded.
                return Outcome(decision_reason="approval-timeout", policy_action="escalate")
            action = situation.on_timeout or "terminate"
            return Outcome(
                decision_reason="approval-timeout",
                policy_action=action,
                terminal_reason="approval-timeout",
            )

        # 3 — sufficiency. FR105: never valid while the gate has not run.
        if situation.floor_met:
            if situation.quality_state == "not-evaluated":
                raise ValueError(
                    "sufficiency is not a valid decision reason while quality_state is "
                    "not-evaluated; before the first gate execution the honest answer is "
                    "that we have not looked"
                )
            return Outcome(
                decision_reason="sufficiency", policy_action="terminate",
                terminal_reason="stop-sufficient",
            )

        # 4 — exhaustion outranks no-progress: nothing affordable advances the floor.
        if not situation.affordable_step_advances_floor:
            return Outcome(
                decision_reason="exhaustion",
                policy_action=situation.contract_directs,
                terminal_reason="halt-exhausted",
            )

        # 5 — progress has stalled while budget remains.
        if situation.no_progress:
            return Outcome(
                decision_reason="no-progress", policy_action="terminate",
                terminal_reason="halt-no-progress",
            )

        # A failed gate with budget left is a retry or escalation (FR24), not a halt.
        if situation.gate_failed and situation.budget_remains:
            terminal = (
                "referred-human"
                if situation.contract_directs == "request-human"
                else "returned-partial"
            )
            return Outcome(
                decision_reason="escalation-gate-fail",
                policy_action=situation.contract_directs,
                terminal_reason=terminal,
            )

        return Outcome(decision_reason="justified", policy_action="proceed")

    def screen(self, proposal: Proposal, unmet_mandatory: set[str]) -> Proposal | None:
        """AD-18: reject `low-value` where the step would advance the floor.

        Returns the proposal to act on, or None where it was discarded.
        """
        if proposal.candidate_reason != "low-value":
            return proposal
        protected = tuple(sorted(set(proposal.advances_criteria) & unmet_mandatory))
        if not protected:
            return proposal
        self.violations.append(
            FloorViolation(
                step_id=proposal.step_id, mechanism=proposal.mechanism, criteria=protected
            )
        )
        return None
