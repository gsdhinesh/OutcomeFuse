"""The reference adapter: a hand-rolled ReAct loop (AD-1, E6).

It **proposes** a step and **applies** the returned verdict, including
termination. Interception and loop-driving are adapter strategies, not
architectures — this one is a plain loop, and no host framework type appears
above it because there is no host framework.

It exists to be the thing the conformance battery is proven against. An adapter
that has not passed the battery cannot produce a reportable run, and a battery
that has never failed anything has not been shown to work either.
"""

from __future__ import annotations

from collections.abc import Sequence

from ....conformance import Scenario
from ....core.record import Event
from ....ports import (
    ApprovalRequest,
    ProbedToolPort,
    ScriptedApprovalPort,
    ToolCall,
)

WHEN = "2026-09-10T12:00:00Z"


class _Log:
    """The adapter's view of the decision log: append-only, in order."""

    def __init__(self, run_id: str) -> None:
        self.run_id = run_id
        self._events: list[Event] = []

    def append(self, kind: str, **fields: object) -> None:
        self._events.append(
            Event(run_id=self.run_id, seq=len(self._events), kind=kind,
                  recorded_at=WHEN, **fields)  # type: ignore[arg-type]
        )

    @property
    def events(self) -> list[Event]:
        return list(self._events)


class ReferenceAdapter:
    """Drives one scripted scenario and returns its log and probe."""

    #: A deliberately conforming adapter. `honour_verdicts=False` produces the
    #: adapter AD-15 exists to catch: one that records a clean pause and makes
    #: the call anyway.
    def __init__(self, *, honour_verdicts: bool = True) -> None:
        self.honour_verdicts = honour_verdicts

    def run_scenario(self, scenario: Scenario) -> tuple[Sequence[Event], ProbedToolPort]:
        probe = ProbedToolPort()
        log = _Log(f"run-{scenario.name}")
        log.append("run-manifest")
        getattr(self, f"_{scenario.name.replace('-', '_')}")(scenario, log, probe)
        return log.events, probe

    # ------------------------------------------------------------- scenarios

    def _deny_honoured(self, scenario: Scenario, log: _Log, probe: ProbedToolPort) -> None:
        log.append("decision-proposed", step_id="s1")
        log.append(
            "decision-recorded", step_id="s1", policy_action="deny",
            decision_reason="duplicate",
        )
        if not self.honour_verdicts:
            probe.invoke(ToolCall(tool="denied_tool", step_id="s1"))
        log.append("decision-proposed", step_id="s2")

    def _substitution_applied(
        self, scenario: Scenario, log: _Log, probe: ProbedToolPort
    ) -> None:
        log.append("decision-proposed", step_id="s1")
        log.append(
            "decision-recorded", step_id="s1",
            policy_action="proceed-with-substitution", decision_reason="cache-hit",
        )
        target = "expensive_tool" if not self.honour_verdicts else "cached_tool"
        probe.invoke(ToolCall(tool=target, step_id="s1"))
        if not self.honour_verdicts:
            probe.invoke(ToolCall(tool="cached_tool", step_id="s1"))
        log.append("outcome-observed", step_id="s1")

    def _approval_pause_observed(
        self, scenario: Scenario, log: _Log, probe: ProbedToolPort
    ) -> None:
        approvals = ScriptedApprovalPort(default="no-response")
        outcome = approvals.request(
            ApprovalRequest(
                run_id=log.run_id, step_id="s1", tool="gated_tool",
                clause="human_approval_conditions[0]", timeout_seconds=1,
            )
        )
        log.append("decision-proposed", step_id="s1")
        if outcome.gated_call_permitted or not self.honour_verdicts:
            probe.invoke(ToolCall(tool="gated_tool", step_id="s1"))
        log.append(
            "decision-recorded", step_id="s1", policy_action="terminate",
            decision_reason="approval-timeout", terminal_reason="approval-timeout",
        )
        log.append("run-closed")

    def _sufficiency_stop_terminates(
        self, scenario: Scenario, log: _Log, probe: ProbedToolPort
    ) -> None:
        log.append("decision-proposed", step_id="s1")
        log.append(
            "gate-verdict", gate_verdict="pass", verification_mode="reference-backed"
        )
        log.append(
            "decision-recorded", step_id="s1", policy_action="terminate",
            decision_reason="sufficiency", terminal_reason="stop-sufficient",
        )
        log.append("run-closed")
        if not self.honour_verdicts:
            # No further billable work is permitted beyond finalisation.
            probe.invoke(ToolCall(tool="after_stop_tool", step_id="s2"))

    def _fail_closed_halts(
        self, scenario: Scenario, log: _Log, probe: ProbedToolPort
    ) -> None:
        log.append("decision-proposed", step_id="s1")
        log.append(
            "decision-recorded", step_id="s1", policy_action="request-human",
            decision_reason="fail-closed", terminal_reason="fail-closed",
        )
        log.append("run-closed")
        if not self.honour_verdicts:
            probe.invoke(ToolCall(tool="after_halt_tool", step_id="s2"))

    def _shadow_decisions_not_applied(
        self, scenario: Scenario, log: _Log, probe: ProbedToolPort
    ) -> None:
        log.append("decision-proposed", step_id="s1")
        log.append(
            "decision-recorded", step_id="s1", policy_action="deny",
            decision_reason="low-value",
        )
        # Shadow alters nothing the host would otherwise do: the decision is
        # recorded and the step still runs.
        if self.honour_verdicts:
            probe.invoke(ToolCall(tool="observed_tool", step_id="s1"))
        log.append("outcome-observed", step_id="s1")
