"""Shadow mode (E11, AD-11, FR46-FR49, FR91, FR96, FR106).

The claim under test is uncomfortable to make and easy to fake: *this governor
cannot hurt you*. Every test here is a way that claim could be false — the host
losing a call it would have made, the approval port blocking, the governor
debiting a ledger it does not own, the counterfactual quietly accruing spend
against a path that stopped existing several steps ago.

The last of those is the subtle one. Past the counterfactual's first
terminating decision the governed run never happened, so anything still
credited to it is invented. What the host spends afterwards is *avoided if
enforced*, which is a different claim and is reported under a different name.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from pydantic import ValidationError

from outcomefuse.core.contract import load_text
from outcomefuse.core.gate import GateUnavailable
from outcomefuse.core.policy import EvidenceRequest, Ledger, Reserve
from outcomefuse.core.record import Event, RunManifest, check_order, fold, open_store
from outcomefuse.ports import (
    ApprovalRequest,
    ProbedToolPort,
    ScriptedApprovalPort,
    ToolCall,
)
from outcomefuse.runtime import Driver, ShadowDriver, ShadowRefused, ToolGovernor

SHA = "e" * 64

CONTRACT = """
contract_id: ofc-shadow
version: 1
workload: testing
task_goal: A goal.
deliverable:
  structure:
    answer: string
criteria:
  mandatory:
    - id: answer-matches-key
      classification: E
      verifier:
        type: exact-match-against-answer-key
        args: { path: $.answer, key: answer }
budget:
  max_tokens: 10000
  max_estimated_cost: 1.0
  max_tool_calls: 20
  max_iterations: 5
tools:
  - name: search
    deterministic: true
    side_effecting: false
  - name: pay
    deterministic: false
    side_effecting: true
human_approval_conditions:
  - tool: pay
    when: always
approval_timeout_seconds: 30
on_timeout: terminate
"""


class ExplodingApprovalPort:
    """FR91 forbids pausing the host, and asking a human *is* the pause."""

    def request(self, request: ApprovalRequest):
        raise AssertionError(
            "shadow called the ApprovalPort; FR91 says it records the pause it "
            "would have imposed and never requests one"
        )


class UnavailableGate:
    def evaluate(self, *_args, **_kwargs):
        raise GateUnavailable("no verdict")


@pytest.fixture
def contract():
    return load_text(CONTRACT)


def manifest(run_id: str = "run-1", **over) -> RunManifest:
    base = {
        "run_id": run_id,
        "mode": "shadow",
        "data_class": "synthetic",
        "retention_profile": "mvp-synthetic-v1",
        "contract_hash": SHA,
        "rubric_hash": SHA,
        "answer_key_hash": SHA,
        "verifier_registry_version": "v1",
        "verifier_registry_hash": SHA,
        "coverage_report_hash": SHA,
        "baseline_configuration_hash": SHA,
        "case_set_id": "calibration/testing",
        "split": "calibration",
        "model_ids": ("gpt-4o",),
        "provider_versions": {"gpt-4o": "2026-05-01"},
        "cost_table_version": "ct-1",
        "route": "direct",
        "streaming_disabled": True,
        "adapter_id": "reference",
        "adapter_version": "1",
        "governor_code_version": "0.1.0",
        "sqlite_library_version": sqlite3.sqlite_version,
        "seed": 1,
    }
    return RunManifest(**(base | over))


class _WithDeliverable(ShadowDriver):
    """A host whose deliverable already meets the floor, so the gate passes."""

    def deliverable(self):
        return {"answer": "42"}

    def answer_key(self):
        return {"answer": "42"}


@pytest.fixture
def make_shadow(tmp_path: Path, contract):
    stores = []
    counter = {"n": 0}

    def build(*, cls=ShadowDriver, gate=None, open_with=None):
        counter["n"] += 1
        store = open_store(tmp_path / f"s{counter['n']}.db")
        stores.append(store)
        driver = cls(
            run_id="run-1",
            contract=contract,
            store=store,
            governor=ToolGovernor(contract, ExplodingApprovalPort()),
            tools=ProbedToolPort({"search": lambda c: "found", "pay": lambda c: "paid"}),
            gate=gate,
        )
        driver.open_run(open_with or manifest())
        return driver

    yield build
    for store in stores:
        store.close()


def search(step_id: str, q: str = "a") -> ToolCall:
    return ToolCall(tool="search", arguments={"q": q}, step_id=step_id)


@pytest.fixture
def an_enforced_run(tmp_path: Path, contract):
    """The same step through the enforcing driver, for FR47 to be checked against."""
    stores = []

    def build(call: ToolCall) -> list[Event]:
        store = open_store(tmp_path / "governed.db")
        stores.append(store)
        driver = Driver(
            run_id="run-g",
            contract=contract,
            store=store,
            ledger=Ledger(
                allocated_tokens=10000,
                allocated_cost=1.0,
                reserve=Reserve(
                    max_tokens=1000, max_estimated_cost=0.1, sizing="declared"
                ),
            ),
            governor=ToolGovernor(contract, ScriptedApprovalPort(default="approved")),
            tools=ProbedToolPort({"search": lambda c: "found"}),
        )
        driver.open_run(manifest("run-g", mode="governed"))
        driver.execute_step(call)
        return store.events("run-g")

    yield build
    for store in stores:
        store.close()


class TestItAltersNothing:
    def test_the_host_keeps_the_call_the_governor_would_have_suppressed(
        self, make_shadow
    ):
        driver = make_shadow()
        driver.observe_step(search("s1"))
        driver.observe_step(search("s2"))
        # The second call is a cache hit the governed arm would have substituted.
        assert driver.tools.invocation_count("search") == 2

    def test_the_approval_port_is_never_called(self, make_shadow):
        driver = make_shadow()
        driver.observe_step(ToolCall(tool="pay", arguments={"amount": 1}, step_id="s1"))
        assert driver.tools.was_invoked("pay")

    def test_the_pause_is_recorded_rather_than_requested(self, make_shadow):
        driver = make_shadow()
        driver.observe_step(ToolCall(tool="pay", arguments={"amount": 1}, step_id="s1"))
        counterfactual = [
            e
            for e in driver.store.events("run-1")
            if e.lane == "counterfactual" and e.kind == "decision-recorded"
        ]
        assert [e.policy_action for e in counterfactual] == ["pause-for-approval"]
        assert counterfactual[0].decision_reason == "approval-required"

    def test_it_holds_no_ledger_to_debit(self, make_shadow):
        # AD-11: governor spend is never debited to the observed run's ledger.
        # The surest way to honour that is to have no ledger here at all.
        assert not hasattr(make_shadow(), "ledger")

    def test_it_returns_no_verdict_for_an_adapter_to_apply(self, make_shadow):
        # AD-1 puts enforcement in the adapter's hands, so handing one back
        # would leave shadow one cooperative adapter away from enforcing.
        assert make_shadow().observe_step(search("s1")) is None

    def test_a_recorded_halt_does_not_stop_the_host(self, make_shadow):
        driver = make_shadow(cls=_WithDeliverable, gate=UnavailableGate())
        driver.observe_step(search("s1"))
        driver.observe_step(search("s2", q="b"))
        assert driver.counterfactual_sealed
        assert driver.tools.invocation_count("search") == 2
        assert not driver.closed


class TestSpendingEvidenceIsRefused:
    def test_a_request_that_would_spend_is_refused(self, make_shadow):
        # FR48 makes the executed ungoverned path the only measured one.
        with pytest.raises(ShadowRefused, match="never bought"):
            make_shadow().request_evidence(
                EvidenceRequest(
                    kind="rubric-judgement", mechanism="quality-gate", estimated_tokens=200
                )
            )

    def test_a_request_computed_from_what_was_already_observed_is_allowed(
        self, make_shadow
    ):
        assert (
            make_shadow().request_evidence(
                EvidenceRequest(kind="complexity-estimate", mechanism="preflight-planner")
            )
            is None
        )


class TestTwoLanesOneLog:
    def test_an_enforced_run_writes_only_the_observed_lane(self):
        assert Event(
            run_id="r", seq=1, kind="decision-proposed", recorded_at="2026-09-10T00:00:00Z"
        ).lane == "observed"

    def test_a_shadow_run_writes_both(self, make_shadow):
        driver = make_shadow()
        driver.observe_step(search("s1"))
        lanes = {e.lane for e in driver.store.events("run-1")}
        assert lanes == {"observed", "counterfactual"}

    def test_the_observed_lane_alone_is_the_shape_of_an_enforced_run(
        self, make_shadow, an_enforced_run
    ):
        # FR47, checked against the thing it claims to resemble rather than
        # against a shape written down twice.
        driver = make_shadow()
        driver.observe_step(search("s1"))
        driver.close()
        events = driver.store.events("run-1")
        observed = [e for e in events if e.lane == "observed"]

        enforced = an_enforced_run(search("s1"))
        assert [e.kind for e in observed[:-1]] == [e.kind for e in enforced]
        # Same findings, and only the sequence numbers move: the shadow log's
        # observed rows share one numbering with the counterfactual's.
        def without_seq(findings: list[str]) -> list[str]:
            return [f.split(": ", 1)[1] for f in findings]

        assert without_seq(check_order(events, lane="observed")) == without_seq(
            check_order(enforced)
        )

        state = fold(events)
        assert state.sealed
        assert state.decisions == ("proceed",)
        assert state.reasons == ("justified",)

    def test_the_counterfactual_is_the_other_fold_over_the_same_log(self, make_shadow):
        driver = make_shadow()
        driver.observe_step(search("s1"))
        driver.observe_step(search("s2"))
        events = driver.store.events("run-1")
        assert fold(events, lane="observed").tokens_spent == 20
        # The second call would have been served from cache, so it spends nothing.
        assert fold(events, lane="counterfactual").tokens_spent == 10

    def test_a_counterfactual_may_not_open_or_close_the_run(self):
        for kind in ("run-manifest", "run-closed", "run-abandoned"):
            with pytest.raises(ValidationError, match="belongs to the host"):
                Event(
                    run_id="r",
                    seq=1,
                    kind=kind,
                    recorded_at="2026-09-10T00:00:00Z",
                    lane="counterfactual",
                )

    def test_each_lane_may_record_one_terminal_reason(self, make_shadow):
        # The counterfactual's seal is not the observed run's terminal reason,
        # so a single per-run index would have made shadow unrecordable.
        driver = make_shadow(cls=_WithDeliverable)
        driver.observe_step(search("s1"))
        assert fold(driver.store.events("run-1"), lane="counterfactual").terminal_reason
        assert fold(driver.store.events("run-1")).terminal_reason is None

    def test_folding_across_lanes_is_reported_as_a_difference(self, make_shadow):
        from outcomefuse.core.record import replay_equivalent

        driver = make_shadow(cls=_WithDeliverable)
        driver.observe_step(search("s1"))
        events = driver.store.events("run-1")
        differences = replay_equivalent(
            fold(events), fold(events, lane="counterfactual")
        )
        assert any("lane" in d for d in differences)


class TestFirstDivergence:
    def test_an_identical_path_has_no_divergence(self, make_shadow):
        driver = make_shadow()
        driver.observe_step(search("s1"))
        report = driver.report()
        assert report.first_divergence is None
        assert "nothing here is inference" in report.disclosure

    def test_the_first_divergence_is_marked(self, make_shadow):
        driver = make_shadow()
        driver.observe_step(search("s1"))
        driver.observe_step(search("s2"))
        driver.observe_step(search("s3"))
        report = driver.report()
        assert report.first_divergence is not None
        assert report.first_divergence.step_id == "s2"
        assert report.first_divergence.observed_action == "proceed"
        assert report.first_divergence.counterfactual_action == "proceed-with-substitution"

    def test_what_follows_the_divergence_is_counted_as_inference(self, make_shadow):
        # FR96: estimates are not extrapolated past a divergence without
        # disclosing that they were, so the count travels with the figure.
        driver = make_shadow()
        for n in range(1, 5):
            driver.observe_step(search(f"s{n}"))
        report = driver.report()
        assert report.decisions_after_first_divergence == 2
        assert "are inference rather than observation" in report.disclosure

    def test_the_report_is_derived_from_the_log(self, make_shadow):
        from outcomefuse.runtime import build_shadow_report

        driver = make_shadow()
        driver.observe_step(search("s1"))
        driver.observe_step(search("s2"))
        assert build_shadow_report(driver.store.events("run-1")) == driver.report()


class TestTheCounterfactualSeals:
    def test_it_seals_at_its_first_terminating_decision(self, make_shadow):
        driver = make_shadow(cls=_WithDeliverable)
        driver.observe_step(search("s1"))
        report = driver.report()
        assert driver.counterfactual_sealed
        assert report.counterfactual_terminal_reason == "stop-sufficient"
        assert report.counterfactual_sealed_at is not None

    def test_nothing_is_evaluated_on_that_lane_afterwards(self, make_shadow):
        driver = make_shadow(cls=_WithDeliverable)
        driver.observe_step(search("s1"))
        sealed_at = driver.report().counterfactual_sealed_at
        driver.observe_step(search("s2", q="b"))
        driver.observe_step(search("s3", q="c"))
        after = [
            e
            for e in driver.store.events("run-1")
            if e.lane == "counterfactual" and e.seq > sealed_at
        ]
        assert after == []

    def test_host_spend_after_the_seal_is_avoided_not_counterfactual(self, make_shadow):
        # Crediting it to the counterfactual would be spending on a path that
        # stopped existing; it is a different claim and gets a different name.
        driver = make_shadow(cls=_WithDeliverable)
        driver.observe_step(search("s1"))
        driver.observe_step(search("s2", q="b"))
        driver.observe_step(search("s3", q="c"))
        report = driver.report()
        assert report.observed_tokens == 30
        assert report.counterfactual_tokens == 10
        assert report.avoided_if_enforced_tokens == 20

    def test_the_seal_itself_is_a_divergence(self, make_shadow):
        driver = make_shadow(cls=_WithDeliverable)
        driver.observe_step(search("s1"))
        divergence = driver.report().first_divergence
        assert divergence is not None
        assert divergence.counterfactual_action == "terminate"
        assert divergence.terminal_reason == "stop-sufficient"


class TestModeAndLabel:
    def test_the_report_is_projected_and_cannot_be_anything_else(self, make_shadow):
        # FR49: shadow figures are never presented as realized savings.
        report = make_shadow().report()
        assert report.label == "projected"
        with pytest.raises(ValidationError):
            report.model_copy(update={"label": "realized"}).model_validate(
                report.model_dump() | {"label": "realized"}
            )

    def test_a_shadow_driver_refuses_a_manifest_that_says_otherwise(self, make_shadow):
        with pytest.raises(ShadowRefused, match="declares mode 'shadow'"):
            make_shadow(open_with=manifest("run-1", mode="governed"))


class TestReplayedWorkloads:
    def test_a_replay_of_a_synthetic_run_may_be_shadowed(self, make_shadow):
        # FR106: synthetic and replayed workloads only.
        driver = make_shadow(
            open_with=manifest(
                "run-1", data_class="replayed", replayed_from_data_class="synthetic"
            )
        )
        driver.observe_step(search("s1"))
        assert driver.store.verify_run("run-1")

    def test_replaying_captured_production_traffic_is_refused(self):
        with pytest.raises(ValidationError, match="inherits data_class 'non-synthetic'"):
            manifest(
                "run-1", data_class="replayed", replayed_from_data_class="non-synthetic"
            )
