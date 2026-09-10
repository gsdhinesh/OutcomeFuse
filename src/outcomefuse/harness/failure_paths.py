"""FR100's failure-path suite.

Every path below is a claim this system makes about its behaviour under stress,
and none of them happens on a happy-path case. Untested failure paths are the
ones that turn out, under demonstration, to have been aspirations — so each is
a declared case here, run end to end through the enforcing driver, and checked
against the log rather than against what the driver returned.

The rule that shapes the model is FR103's: **`terminal_reason` names the cause,
never the disposition**, and a run that survives its failure has none at all. An
escalating approval timeout and a degraded optimisation mechanism both continue,
so asserting a terminal reason on every case would bake in exactly the
conflation FR103 exists to prevent. `_disposition_matches_termination` makes
that structural: a case cannot declare itself terminal and name no cause, or
name a cause and claim to survive.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Final

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..core.record import Event, fold

#: Actions that end a run. `escalate` is deliberately absent: FR103 gives it no
#: terminal reason, because the run carries on afterwards.
TERMINATING_ACTIONS: Final[frozenset[str]] = frozenset(
    {"terminate", "return-partial", "request-human"}
)


class FailureCase(BaseModel):
    """One declared path, and the triple the log must show for it."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(min_length=1)
    policy_action: str = Field(min_length=1)
    decision_reason: str = Field(min_length=1)
    terminal_reason: str | None = None
    terminates: bool
    #: The mechanism expected to have dropped out, for the fail-open path.
    degrades: str | None = None

    @model_validator(mode="after")
    def _disposition_matches_termination(self) -> FailureCase:
        if self.terminates != (self.terminal_reason is not None):
            raise ValueError(
                f"{self.name!r}: a terminal reason is recorded exactly for the cases "
                "that terminate; naming one on a surviving case files the disposition "
                "as the cause (FR103)"
            )
        if self.terminates and self.policy_action not in TERMINATING_ACTIONS:
            raise ValueError(
                f"{self.name!r}: {self.policy_action!r} does not end a run"
            )
        return self


#: FR100's minimum. Two of the eight survive their failure, which is the half of
#: the requirement an implementation is most likely to get wrong.
FR100_CASES: Final[tuple[FailureCase, ...]] = (
    FailureCase(
        name="sufficiency-stop",
        policy_action="terminate",
        decision_reason="sufficiency",
        terminal_reason="stop-sufficient",
        terminates=True,
    ),
    FailureCase(
        name="budget-exhaustion",
        policy_action="return-partial",
        decision_reason="exhaustion",
        terminal_reason="halt-exhausted",
        terminates=True,
    ),
    FailureCase(
        name="no-progress-halt",
        policy_action="terminate",
        decision_reason="no-progress",
        terminal_reason="halt-no-progress",
        terminates=True,
    ),
    FailureCase(
        name="approval-timeout-terminates",
        policy_action="terminate",
        decision_reason="approval-timeout",
        terminal_reason="approval-timeout",
        terminates=True,
    ),
    FailureCase(
        name="approval-timeout-escalates",
        policy_action="escalate",
        decision_reason="approval-timeout",
        terminates=False,
    ),
    FailureCase(
        name="gate-unavailable",
        policy_action="request-human",
        decision_reason="fail-closed",
        terminal_reason="fail-closed",
        terminates=True,
    ),
    FailureCase(
        name="ledger-state-lost",
        policy_action="terminate",
        decision_reason="fail-closed",
        terminal_reason="fail-closed",
        terminates=True,
    ),
    FailureCase(
        name="mechanism-failure",
        policy_action="proceed",
        decision_reason="justified",
        terminates=False,
        degrades="context-governor",
    ),
)

CASES_BY_NAME: Final[dict[str, FailureCase]] = {case.name: case for case in FR100_CASES}


def check_case(case: FailureCase, events: Sequence[Event]) -> list[str]:
    """What the run got wrong, read out of its log.

    Checked against the record rather than the driver's return value: FR5 makes
    the log the thing that happened, and a driver that returned one verdict and
    recorded another is precisely the failure worth catching.
    """
    findings: list[str] = []
    decisions = [
        e for e in events if e.lane == "observed" and e.kind == "decision-recorded"
    ]
    if not decisions:
        return [f"{case.name}: the run recorded no decision at all"]

    last = decisions[-1]
    if last.policy_action != case.policy_action:
        findings.append(
            f"{case.name}: expected policy_action {case.policy_action!r}, "
            f"got {last.policy_action!r}"
        )
    if last.decision_reason != case.decision_reason:
        findings.append(
            f"{case.name}: expected decision_reason {case.decision_reason!r}, "
            f"got {last.decision_reason!r}"
        )

    recorded = fold(events).terminal_reason
    if recorded != case.terminal_reason:
        findings.append(
            f"{case.name}: expected terminal_reason {case.terminal_reason!r}, "
            f"got {recorded!r}"
        )

    if case.degrades is not None:
        degraded = {
            str(e.payload.get("mechanism")) for e in events if e.kind == "degraded"
        }
        if case.degrades not in degraded:
            findings.append(
                f"{case.name}: expected {case.degrades!r} to be recorded as degraded, "
                f"got {sorted(degraded)}"
            )

    return findings
