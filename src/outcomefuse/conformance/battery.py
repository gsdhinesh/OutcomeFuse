"""The adapter conformance battery (AD-15, FR107).

Six scripted scenarios — deny honoured, substitution applied, approval pause
observed, sufficiency stop terminates, fail-closed halts, shadow decisions not
applied — asserted **against the resulting decision log**, never against adapter
internals. An adapter that has not passed cannot produce a reportable run.

The battery is written before the adapters on purpose. It is the specification
they are written against; written afterwards it would become a description of
whatever they already do.

Every scenario also carries an **out-of-band probe**, because enforcement is
cooperative: an adapter that executes a denied call while recording a clean
pause produces a plausible and entirely false audit trail, and a decision record
cannot detect the one failure it is the evidence for.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from ..core.record import Event
from ..ports import ProbedToolPort


class Scenario(BaseModel):
    """One scripted case and what the log must show afterwards."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(min_length=1)
    description: str
    expect_policy_action: str
    expect_decision_reason: str
    #: Asserted only where execution actually terminates. A case that survives
    #: its failure - an escalating approval timeout, a degraded mechanism - is
    #: asserted to record *no* terminal reason and to continue (FR100).
    expect_terminal_reason: str | None = None
    expect_continues: bool = False
    #: Tools that must not have run, checked by the tools themselves.
    forbidden_tools: tuple[str, ...] = ()
    #: Tools that must have run, so "nothing happened" cannot pass by accident.
    required_tools: tuple[str, ...] = ()


class ScenarioResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    scenario: str
    passed: bool
    findings: tuple[str, ...] = ()


class BatteryResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    results: tuple[ScenarioResult, ...]

    @property
    def passed(self) -> bool:
        return all(result.passed for result in self.results)

    @property
    def findings(self) -> tuple[str, ...]:
        return tuple(f"{r.scenario}: {f}" for r in self.results for f in r.findings)


#: The fixed battery. Adding a scenario is a change to the specification every
#: adapter is measured against, so the set is declared here rather than assembled
#: per adapter.
BATTERY: tuple[Scenario, ...] = (
    Scenario(
        name="deny-honoured",
        description="A denied step does not happen and the run continues.",
        expect_policy_action="deny",
        expect_decision_reason="duplicate",
        expect_continues=True,
        forbidden_tools=("denied_tool",),
    ),
    Scenario(
        name="substitution-applied",
        description="A substituted step executes on the cheaper path.",
        expect_policy_action="proceed-with-substitution",
        expect_decision_reason="cache-hit",
        expect_continues=True,
        forbidden_tools=("expensive_tool",),
        required_tools=("cached_tool",),
    ),
    Scenario(
        name="approval-pause-observed",
        description="A gated call waits, and is not made when approval is withheld.",
        expect_policy_action="terminate",
        expect_decision_reason="approval-timeout",
        expect_terminal_reason="approval-timeout",
        forbidden_tools=("gated_tool",),
    ),
    Scenario(
        name="sufficiency-stop-terminates",
        description="On pass the run stops; no further billable work happens.",
        expect_policy_action="terminate",
        expect_decision_reason="sufficiency",
        expect_terminal_reason="stop-sufficient",
        forbidden_tools=("after_stop_tool",),
    ),
    Scenario(
        name="fail-closed-halts",
        description="An unavailable gate halts the run rather than reporting a pass.",
        expect_policy_action="request-human",
        expect_decision_reason="fail-closed",
        expect_terminal_reason="fail-closed",
        forbidden_tools=("after_halt_tool",),
    ),
    Scenario(
        name="shadow-decisions-not-applied",
        description="In shadow the decision is recorded and the host is not altered.",
        expect_policy_action="deny",
        expect_decision_reason="low-value",
        expect_continues=True,
        # The point of shadow: the decision says deny, and the tool runs anyway
        # because the governor promised only to observe.
        required_tools=("observed_tool",),
    ),
)


@runtime_checkable
class ConformanceRunner(Protocol):
    """What an adapter must supply to be measured.

    It returns the decision log it produced and the probe that watched it, so
    the battery never inspects adapter internals.
    """

    def run_scenario(self, scenario: Scenario) -> tuple[Sequence[Event], ProbedToolPort]: ...


def check_scenario(
    scenario: Scenario, events: Sequence[Event], probe: ProbedToolPort
) -> ScenarioResult:
    """Assert one scenario against the log and the out-of-band probe."""
    findings: list[str] = []

    actions = [e.policy_action for e in events if e.policy_action]
    reasons = [e.decision_reason for e in events if e.decision_reason]
    terminals = [e.terminal_reason for e in events if e.terminal_reason]

    if scenario.expect_policy_action not in actions:
        findings.append(
            f"log has no {scenario.expect_policy_action!r} decision; saw {actions}"
        )
    if scenario.expect_decision_reason not in reasons:
        findings.append(
            f"log has no {scenario.expect_decision_reason!r} reason; saw {reasons}"
        )

    if scenario.expect_terminal_reason is None:
        if scenario.expect_continues and terminals:
            findings.append(f"run should have continued but recorded {terminals}")
    elif scenario.expect_terminal_reason not in terminals:
        findings.append(
            f"log has no {scenario.expect_terminal_reason!r} terminal reason; saw {terminals}"
        )

    if len(terminals) > 1:
        findings.append(f"terminal_reason recorded {len(terminals)} times")

    # The out-of-band probe. This is the check the log cannot make about itself.
    for tool in scenario.forbidden_tools:
        if probe.was_invoked(tool):
            findings.append(
                f"{tool!r} was invoked although the log claims it was not; the adapter "
                "did not honour the verdict it recorded"
            )
    for tool in scenario.required_tools:
        if not probe.was_invoked(tool):
            findings.append(f"{tool!r} never ran, so the scenario proved nothing")

    return ScenarioResult(
        scenario=scenario.name, passed=not findings, findings=tuple(findings)
    )


def run_battery(
    runner: ConformanceRunner, scenarios: Sequence[Scenario] = BATTERY
) -> BatteryResult:
    """Run every scenario. An adapter passes only if all of them pass."""
    results = []
    for scenario in scenarios:
        events, probe = runner.run_scenario(scenario)
        results.append(check_scenario(scenario, events, probe))
    return BatteryResult(results=tuple(results))


def admissible(result: BatteryResult) -> bool:
    """AD-15: an adapter that has not passed cannot produce a reportable run."""
    return result.passed


def scenario(name: str) -> Scenario:
    try:
        return next(s for s in BATTERY if s.name == name)
    except StopIteration:
        raise KeyError(f"no conformance scenario named {name!r}") from None
