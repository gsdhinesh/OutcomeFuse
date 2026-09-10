"""Ports, reference adapter and the conformance battery (AD-1, AD-12, AD-15).

The battery's whole purpose is catching an adapter that records a clean log and
does something else. So the central test here is not that the good adapter
passes — it is that a **deliberately dishonest adapter fails**, and fails for
the right reason. A battery that has never rejected anything has not been shown
to work.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from outcomefuse.adapters.host.reference import ReferenceAdapter
from outcomefuse.conformance import (
    BATTERY,
    admissible,
    check_scenario,
    run_battery,
    scenario,
)
from outcomefuse.core.record import Event
from outcomefuse.ports import (
    ApprovalRequest,
    ModelRequest,
    PortRegistry,
    PostureError,
    ProbedToolPort,
    ScriptedApprovalPort,
    ScriptedModelPort,
    StreamingBarred,
    ToolCall,
)

WHEN = "2026-09-10T12:00:00Z"


class TestPortPosture:
    def test_the_record_sink_must_be_fail_closed(self):
        with pytest.raises(PostureError, match="must be registered 'fail-closed'"):
            PortRegistry().register("record", "fail-open", "1")

    def test_the_model_port_must_be_fail_open(self):
        # Losing an optimisation costs money; losing the gate costs correctness.
        with pytest.raises(PostureError, match="must be registered 'fail-open'"):
            PortRegistry().register("model", "fail-closed", "1")

    def test_a_correctly_registered_port_is_accepted(self):
        registry = PortRegistry()
        registry.register("approval", "fail-closed", "1")
        assert registry.posture_of("approval") == "fail-closed"

    def test_a_port_cannot_be_registered_twice(self):
        registry = PortRegistry()
        registry.register("model", "fail-open", "1")
        with pytest.raises(PostureError, match="already registered"):
            registry.register("model", "fail-open", "2")

    def test_an_unregistered_port_has_no_posture(self):
        with pytest.raises(PostureError, match="not registered"):
            PortRegistry().posture_of("model")

    def test_the_registered_set_is_what_the_manifest_records(self):
        registry = PortRegistry()
        registry.register("model", "fail-open", "1.2")
        registry.register("record", "fail-closed", "2.0")
        assert registry.registered() == {"model": "1.2", "record": "2.0"}


class TestApprovalPort:
    def request(self, step_id: str = "s1") -> ApprovalRequest:
        return ApprovalRequest(
            run_id="r", step_id=step_id, tool="notify", clause="clause-1",
            timeout_seconds=30,
        )

    def test_an_approval_permits_the_gated_call(self):
        outcome = ScriptedApprovalPort(default="approved").request(self.request())
        assert outcome.gated_call_permitted

    @pytest.mark.parametrize(
        "decision", ["denied", "no-response", "channel-unavailable"]
    )
    def test_anything_else_withholds_the_gated_call(self, decision):
        outcome = ScriptedApprovalPort(default=decision).request(self.request())
        assert not outcome.gated_call_permitted

    def test_a_channel_failure_is_distinct_from_a_timeout(self):
        # Collapsing the two would route an ordinary timeout to fail-closed,
        # which sits above the approval gate and changes the terminal reason.
        unavailable = ScriptedApprovalPort(default="channel-unavailable").request(
            self.request()
        )
        timeout = ScriptedApprovalPort(default="no-response").request(self.request())
        assert unavailable.is_channel_failure
        assert not timeout.is_channel_failure

    def test_the_decision_is_driven_by_the_case_definition(self):
        port = ScriptedApprovalPort({"s1": "denied", "s2": "approved"})
        assert port.request(self.request("s1")).decision == "denied"
        assert port.request(self.request("s2")).decision == "approved"

    def test_the_triggering_clause_travels_with_the_pause(self):
        assert ScriptedApprovalPort().request(self.request()).clause == "clause-1"


class TestModelPort:
    def test_streaming_is_barred_on_the_evidence_path(self):
        # The gateway estimates token counts when streaming is on, which would
        # make reconciliation a comparison between two guesses.
        with pytest.raises(StreamingBarred):
            ScriptedModelPort().complete(
                ModelRequest(model_id="m", prompt="hi", max_output_tokens=10, stream=True)
            )

    def test_a_scripted_reply_is_deterministic(self):
        port = ScriptedModelPort({"hi": "hello"})
        request = ModelRequest(model_id="m", prompt="hi", max_output_tokens=10)
        assert port.complete(request).text == port.complete(request).text

    def test_token_counts_are_reported(self):
        port = ScriptedModelPort({"hi": "hello"})
        response = port.complete(
            ModelRequest(model_id="m", prompt="hi", max_output_tokens=10)
        )
        assert response.total_tokens == response.prompt_tokens + response.completion_tokens


class TestProbe:
    def test_the_probe_records_invocations_independently(self):
        probe = ProbedToolPort()
        probe.invoke(ToolCall(tool="search", step_id="s1"))
        assert probe.was_invoked("search")
        assert not probe.was_invoked("write")

    def test_the_probe_can_be_scoped_to_a_step(self):
        probe = ProbedToolPort()
        probe.invoke(ToolCall(tool="search", step_id="s1"))
        assert probe.was_invoked("search", step_id="s1")
        assert not probe.was_invoked("search", step_id="s2")

    def test_the_probe_counts_repeats(self):
        probe = ProbedToolPort()
        probe.invoke(ToolCall(tool="search", step_id="s1"))
        probe.invoke(ToolCall(tool="search", step_id="s2"))
        assert probe.invocation_count("search") == 2

    def test_a_handler_supplies_the_result(self):
        probe = ProbedToolPort({"search": lambda call: f"ran {call.tool}"})
        assert probe.invoke(ToolCall(tool="search", step_id="s1")).output == "ran search"


class TestTheBatterySpecification:
    def test_the_six_declared_scenarios_are_present(self):
        assert {s.name for s in BATTERY} == {
            "deny-honoured",
            "substitution-applied",
            "approval-pause-observed",
            "sufficiency-stop-terminates",
            "fail-closed-halts",
            "shadow-decisions-not-applied",
        }

    def test_every_scenario_carries_an_out_of_band_expectation(self):
        # A scenario with no probe expectation would be asserted only against
        # the log, which is the thing that cannot check itself.
        for declared in BATTERY:
            assert declared.forbidden_tools or declared.required_tools

    def test_a_continuing_scenario_expects_no_terminal_reason(self):
        # FR100: cases that survive their failure record none and continue.
        for declared in BATTERY:
            if declared.expect_continues:
                assert declared.expect_terminal_reason is None

    def test_an_unknown_scenario_name_is_refused(self):
        with pytest.raises(KeyError):
            scenario("wishful-thinking")


class TestTheReferenceAdapterPasses:
    def test_the_reference_adapter_passes_the_whole_battery(self):
        result = run_battery(ReferenceAdapter())
        assert result.passed, result.findings

    def test_a_passing_adapter_is_admissible(self):
        assert admissible(run_battery(ReferenceAdapter()))

    @pytest.mark.parametrize("declared", BATTERY, ids=lambda s: s.name)
    def test_each_scenario_passes_individually(self, declared):
        events, probe = ReferenceAdapter().run_scenario(declared)
        assert check_scenario(declared, events, probe).passed


class TestTheBatteryCatchesADishonestAdapter:
    """The check the decision log cannot make about itself."""

    def test_a_dishonest_adapter_fails_the_battery(self):
        result = run_battery(ReferenceAdapter(honour_verdicts=False))
        assert not result.passed

    def test_a_dishonest_adapter_is_not_admissible(self):
        assert not admissible(run_battery(ReferenceAdapter(honour_verdicts=False)))

    def test_executing_a_denied_call_is_caught_by_the_probe_not_the_log(self):
        declared = scenario("deny-honoured")
        events, probe = ReferenceAdapter(honour_verdicts=False).run_scenario(declared)
        # The log is clean: it records the denial exactly as it should.
        assert "deny" in [e.policy_action for e in events if e.policy_action]
        # The tool knows better.
        finding = check_scenario(declared, events, probe)
        assert not finding.passed
        assert any("did not honour the verdict it recorded" in f for f in finding.findings)

    def test_working_after_a_sufficiency_stop_is_caught(self):
        # FR23: no further billable work beyond finalisation.
        declared = scenario("sufficiency-stop-terminates")
        events, probe = ReferenceAdapter(honour_verdicts=False).run_scenario(declared)
        assert not check_scenario(declared, events, probe).passed

    def test_working_after_a_fail_closed_halt_is_caught(self):
        declared = scenario("fail-closed-halts")
        events, probe = ReferenceAdapter(honour_verdicts=False).run_scenario(declared)
        assert not check_scenario(declared, events, probe).passed

    def test_making_a_gated_call_without_approval_is_caught(self):
        declared = scenario("approval-pause-observed")
        events, probe = ReferenceAdapter(honour_verdicts=False).run_scenario(declared)
        assert probe.was_invoked("gated_tool")
        assert not check_scenario(declared, events, probe).passed

    def test_ignoring_a_substitution_is_caught(self):
        declared = scenario("substitution-applied")
        events, probe = ReferenceAdapter(honour_verdicts=False).run_scenario(declared)
        assert not check_scenario(declared, events, probe).passed

    def test_applying_a_shadow_decision_is_caught(self):
        # Shadow alters nothing the host would otherwise do; suppressing the
        # step means the governor acted on a run it promised only to observe.
        declared = scenario("shadow-decisions-not-applied")
        events, probe = ReferenceAdapter(honour_verdicts=False).run_scenario(declared)
        finding = check_scenario(declared, events, probe)
        assert not finding.passed
        assert any("proved nothing" in f for f in finding.findings)


class TestScenarioAssertions:
    def event(self, seq: int, kind: str, **fields) -> Event:
        return Event(run_id="r", seq=seq, kind=kind, recorded_at=WHEN, **fields)

    def test_a_missing_decision_is_reported(self):
        declared = scenario("deny-honoured")
        result = check_scenario(declared, [self.event(0, "run-manifest")], ProbedToolPort())
        assert any("no 'deny' decision" in f for f in result.findings)

    def test_a_missing_terminal_reason_is_reported(self):
        declared = scenario("fail-closed-halts")
        events = [
            self.event(0, "run-manifest"),
            self.event(1, "decision-recorded", policy_action="request-human",
                       decision_reason="fail-closed"),
        ]
        result = check_scenario(declared, events, ProbedToolPort())
        assert any("no 'fail-closed' terminal reason" in f for f in result.findings)

    def test_a_continuing_scenario_that_terminated_is_reported(self):
        declared = scenario("deny-honoured")
        events = [
            self.event(0, "run-manifest"),
            self.event(1, "decision-recorded", policy_action="deny",
                       decision_reason="duplicate", terminal_reason="halt-exhausted"),
        ]
        result = check_scenario(declared, events, ProbedToolPort())
        assert any("should have continued" in f for f in result.findings)

    def test_a_terminal_reason_recorded_twice_is_reported(self):
        declared = scenario("fail-closed-halts")
        events = [
            self.event(0, "run-manifest"),
            self.event(1, "decision-recorded", policy_action="request-human",
                       decision_reason="fail-closed", terminal_reason="fail-closed"),
            self.event(2, "run-closed", terminal_reason="fail-closed"),
        ]
        probe = ProbedToolPort()
        result = check_scenario(declared, events, probe)
        assert any("recorded 2 times" in f for f in result.findings)

    def test_findings_name_the_scenario_they_came_from(self):
        result = run_battery(ReferenceAdapter(honour_verdicts=False))
        assert all(":" in finding for finding in result.findings)


class TestEventModelStillGuardsTheLog:
    def test_a_conformance_log_cannot_carry_an_undeclared_field(self):
        with pytest.raises(ValidationError):
            Event(run_id="r", seq=0, kind="run-manifest", recorded_at=WHEN, invented=True)
