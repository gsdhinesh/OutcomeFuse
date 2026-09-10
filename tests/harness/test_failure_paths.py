"""FR100: every declared failure path, run end to end (E8, §8.5).

Each test below drives a real `Driver` against a real store and then checks the
**log**, not the return value. A driver that returned one verdict and recorded
another is exactly the failure worth catching, and FR5 makes the record the
thing that happened.

The two cases that *survive* their failure carry the weight here. An escalating
approval timeout and a degraded optimisation mechanism both continue, and an
implementation that files either as a termination has conflated the disposition
with the cause — which is the confusion FR103 exists to prevent.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from outcomefuse.core.contract import load_text
from outcomefuse.core.gate import GateUnavailable
from outcomefuse.core.policy import (
    AdvisorRegistry,
    Ledger,
    LedgerError,
    LoopFuse,
    Reserve,
)
from outcomefuse.core.record import RunManifest, open_store
from outcomefuse.harness import CASES_BY_NAME, FR100_CASES, check_case
from outcomefuse.ports import ProbedToolPort, ScriptedApprovalPort, ToolCall
from outcomefuse.runtime import Driver, ToolGovernor

SHA = "e" * 64

CONTRACT = """
contract_id: ofc-failure-paths
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


class UnavailableGate:
    def evaluate(self, *_args, **_kwargs):
        raise GateUnavailable("no verdict is obtainable")


class BrokenAdvisor:
    name = "context-governor"

    def advise(self, _state):
        raise RuntimeError("compression pass exploded")


class LostLedger(Ledger):
    """The step was affordable when asked, and the hold cannot be taken.

    FR88's fail-closed condition: the system cannot establish its own state.
    Distinct from running out of budget, which `can_afford` answers honestly.
    """

    def hold(self, *_args, **_kwargs):
        raise LedgerError("ledger state is unreadable")


def a_ledger(cls=Ledger, *, allocated_tokens=10000, reserve_tokens=1000) -> Ledger:
    return cls(
        allocated_tokens=allocated_tokens,
        allocated_cost=1.0,
        reserve=Reserve(
            max_tokens=reserve_tokens, max_estimated_cost=0.1, sizing="declared"
        ),
    )


def manifest(run_id: str = "run-1") -> RunManifest:
    return RunManifest(
        run_id=run_id,
        mode="governed",
        data_class="synthetic",
        retention_profile="mvp-synthetic-v1",
        contract_hash=SHA,
        rubric_hash=SHA,
        answer_key_hash=SHA,
        verifier_registry_version="v1",
        verifier_registry_hash=SHA,
        coverage_report_hash=SHA,
        baseline_configuration_hash=SHA,
        case_set_id="calibration/testing",
        split="calibration",
        model_ids=("gpt-4o",),
        provider_versions={"gpt-4o": "2026-05-01"},
        cost_table_version="ct-1",
        route="direct",
        streaming_disabled=True,
        adapter_id="reference",
        adapter_version="1",
        governor_code_version="0.1.0",
        sqlite_library_version=sqlite3.sqlite_version,
        seed=1,
    )


class _Passing(Driver):
    def deliverable(self):
        return {"answer": "42"}

    def answer_key(self):
        return {"answer": "42"}


@pytest.fixture
def make_driver(tmp_path: Path):
    stores = []
    counter = {"n": 0}

    def build(
        *,
        cls=Driver,
        approval="approved",
        ledger=None,
        contract_text=CONTRACT,
        **kwargs,
    ):
        counter["n"] += 1
        store = open_store(tmp_path / f"f{counter['n']}.db")
        stores.append(store)
        contract = load_text(contract_text)
        driver = cls(
            run_id="run-1",
            contract=contract,
            store=store,
            ledger=ledger if ledger is not None else a_ledger(),
            governor=ToolGovernor(contract, ScriptedApprovalPort(default=approval)),
            tools=ProbedToolPort({"search": lambda c: "found", "pay": lambda c: "paid"}),
            **kwargs,
        )
        driver.open_run(manifest())
        return driver

    yield build
    for store in stores:
        store.close()


def search(step_id: str, q: str = "a") -> ToolCall:
    return ToolCall(tool="search", arguments={"q": q}, step_id=step_id)


def run_for(name: str, make_driver):
    """Drive the named FR100 path and return the run's log."""
    if name == "sufficiency-stop":
        driver = make_driver(cls=_Passing)
        driver.execute_step(search("s1"))

    elif name == "budget-exhaustion":
        # The reserve is the whole allocation, so no step may spend (FR14).
        driver = make_driver(ledger=a_ledger(allocated_tokens=100, reserve_tokens=100))
        driver.execute_step(search("s1"))

    elif name == "no-progress-halt":
        driver = make_driver(fuse=LoopFuse(max_iterations=5))
        driver.observe_progress(task_state={"draft": "unchanged"}, evidence_count=1)
        driver.observe_progress(task_state={"draft": "unchanged"}, evidence_count=1)

    elif name == "approval-timeout-terminates":
        driver = make_driver(approval="no-response")
        driver.execute_step(ToolCall(tool="pay", arguments={"amount": 1}, step_id="s1"))

    elif name == "approval-timeout-escalates":
        driver = make_driver(
            approval="no-response",
            contract_text=CONTRACT.replace("on_timeout: terminate", "on_timeout: escalate"),
        )
        driver.execute_step(ToolCall(tool="pay", arguments={"amount": 1}, step_id="s1"))

    elif name == "gate-unavailable":
        driver = make_driver(cls=_Passing, gate=UnavailableGate())
        driver.execute_step(search("s1"))

    elif name == "ledger-state-lost":
        # Affordable when asked, unholdable afterwards: a system fault, and a
        # different cause from running out of budget.
        driver = make_driver(ledger=a_ledger(LostLedger))
        driver.execute_step(search("s1"))

    elif name == "mechanism-failure":
        driver = make_driver(
            advisors=AdvisorRegistry({"context-governor": BrokenAdvisor()})
        )
        driver.consult_advisors({"iteration": 0})
        driver.execute_step(search("s1"))

    else:  # pragma: no cover - a case with no runner is a suite bug
        raise AssertionError(f"no runner for {name!r}")

    return driver.store.events("run-1")


class TestEveryDeclaredPath:
    @pytest.mark.parametrize("case", FR100_CASES, ids=lambda c: c.name)
    def test_the_recorded_triple_is_what_the_case_declares(self, case, make_driver):
        assert check_case(case, run_for(case.name, make_driver)) == []

    def test_the_suite_covers_FR100s_named_minimum(self):
        assert set(CASES_BY_NAME) == {
            "sufficiency-stop",
            "budget-exhaustion",
            "no-progress-halt",
            "approval-timeout-terminates",
            "approval-timeout-escalates",
            "gate-unavailable",
            "ledger-state-lost",
            "mechanism-failure",
        }


class TestSurvivingAFailureIsNotTerminating:
    def test_an_escalating_timeout_records_no_terminal_reason(self, make_driver):
        events = run_for("approval-timeout-escalates", make_driver)
        assert not any(e.terminal_reason for e in events)

    def test_a_degraded_mechanism_does_not_end_the_run(self, make_driver):
        events = run_for("mechanism-failure", make_driver)
        assert not any(e.terminal_reason for e in events)
        assert any(e.kind == "degraded" for e in events)

    def test_a_case_may_not_claim_to_survive_and_name_a_cause(self):
        from outcomefuse.harness import FailureCase

        with pytest.raises(ValueError, match="exactly for the cases that terminate"):
            FailureCase(
                name="incoherent",
                policy_action="escalate",
                decision_reason="approval-timeout",
                terminal_reason="approval-timeout",
                terminates=False,
            )


class TestExhaustionIsNotFailClosed:
    def test_running_out_of_budget_halts_exhausted(self, make_driver):
        # FR92 and AD-3: affordability is queried before deciding, so this is a
        # routine outcome. Filing it as fail-closed would report the product's
        # central cost event as a system fault.
        events = run_for("budget-exhaustion", make_driver)
        decision = [e for e in events if e.kind == "decision-recorded"][-1]
        assert decision.decision_reason == "exhaustion"
        assert decision.terminal_reason == "halt-exhausted"

    def test_a_refused_reservation_is_still_fail_closed(self, make_driver):
        # FR88: reaching a rejected hold *after* deciding is a system fault,
        # and the two causes stay distinct.
        events = run_for("ledger-state-lost", make_driver)
        decision = [e for e in events if e.kind == "decision-recorded"][-1]
        assert decision.decision_reason == "fail-closed"

    def test_the_unaffordable_step_never_runs(self, make_driver):
        driver = make_driver(ledger=a_ledger(allocated_tokens=100, reserve_tokens=100))
        driver.execute_step(search("s1"))
        assert not driver.tools.was_invoked("search")
