"""Escalation on gate failure (FR35, AD-12).

All four contracts declare `on_gate_fail: retry-then-escalate`, and until now
the driver silently downgraded that to `return-partial`: the contract asked for
a retry on a stronger model and got a partial answer instead.

This is the mechanism the cost claim rests on. Starting a run on the cheaper
model only holds quality if something notices when the cheaper model was not
good enough — measured on data-sql, gpt-5-mini passed 1 case of 3 where gpt-5
passed 3. Without escalation the governed arm is simply a worse agent that costs
less. With it, the quality floor is what makes the cheap path safe to take.

An escalated run is **not** a terminated one. Closing it would make the retry a
second run, which no comparison could pair against a single baseline.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from outcomefuse.core.contract import load_path
from outcomefuse.core.policy import Ledger, Reserve
from outcomefuse.core.record import RecordStore, RunManifest
from outcomefuse.harness.cases import load_case_set
from outcomefuse.harness.runner import GovernedArm, run_case
from outcomefuse.ports import ModelResponse, ToolInvocation
from outcomefuse.runtime import Driver, ToolGovernor
from outcomefuse.workloads import tool_port_for

SHA = "0" * 64
WORKLOAD = "data-sql"

GOOD = json.dumps(
    {
        "result_value": 16,
        "units": "count",
        "row_count": 16,
        "sql": "SELECT COUNT(*) FROM orders",
        "tables_used": ["orders"],
        "assumptions": [],
    }
)
WRONG = json.dumps(
    {
        "result_value": 99,
        "units": "count",
        "row_count": 99,
        "sql": "SELECT COUNT(*) FROM orders",
        "tables_used": ["orders"],
        "assumptions": [],
    }
)


@pytest.fixture(scope="module")
def contract():
    return load_path(Path(f"contracts/{WORKLOAD}.contract.yaml"))


@pytest.fixture(scope="module")
def case():
    return load_case_set(WORKLOAD, "calibration").by_id("ds-c-001")


@pytest.fixture(scope="module")
def answer_key():
    from outcomefuse.harness.answer_keys import answer_key_for

    return answer_key_for("ds-c-001", WORKLOAD, "calibration")


class ByModel:
    """Answers differently depending on which model is asked.

    The whole point of escalation is that the stronger model does better, so a
    fixture where both answer identically could not tell escalation from a retry.
    """

    def __init__(self, answers: dict[str, str]) -> None:
        self.answers = answers
        self.asked: list[str] = []

    def complete(self, request):
        self.asked.append(request.model_id)
        return ModelResponse(
            model_id=request.model_id,
            text=self.answers[request.model_id],
            prompt_tokens=100,
            completion_tokens=50,
            provider_version=f"{request.model_id}-2025-08-07",
        )


@pytest.fixture
def governed(tmp_path, contract):
    stores: list[RecordStore] = []

    def build(*, allocated_tokens=1_000_000, reserve_tokens=10):
        store = RecordStore(tmp_path / f"g{len(stores)}.db").open()
        stores.append(store)
        driver = Driver(
            run_id=f"run-{len(stores)}",
            contract=contract,
            store=store,
            ledger=Ledger(
                allocated_tokens=allocated_tokens,
                allocated_cost=1.0,
                reserve=Reserve(
                    max_tokens=reserve_tokens, max_estimated_cost=0.01, sizing="declared"
                ),
            ),
            governor=ToolGovernor(contract),
            tools=tool_port_for(contract),
        )
        driver.open_run(
            RunManifest(
                run_id=driver.run_id,
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
                case_set_id=f"calibration/{WORKLOAD}",
                split="calibration",
                model_ids=("gpt-5-mini", "gpt-5"),
                provider_versions={"gpt-5-mini": "a", "gpt-5": "b"},
                cost_table_version="ct-2",
                route="direct",
                streaming_disabled=True,
                adapter_id="reference",
                adapter_version="1",
                governor_code_version="0.1.0",
                sqlite_library_version=sqlite3.sqlite_version,
                seed=1,
            )
        )
        return GovernedArm(driver, start_model="gpt-5-mini"), driver

    yield build
    for store in stores:
        store.close()


def drive(case, contract, arm, model, answer_key, **over):
    return run_case(
        case,
        contract=contract,
        arm=arm,
        model=model,
        max_output_tokens=25000,
        reasoning_effort="medium",
        answer_key=answer_key,
        **over,
    )


class TestTheContractIsObeyed:
    def test_a_failed_gate_retries_on_the_stronger_model(
        self, case, contract, governed, answer_key
    ):
        arm, _ = governed()
        model = ByModel({"gpt-5-mini": WRONG, "gpt-5": GOOD})
        outcome = drive(case, contract, arm, model, answer_key)
        assert model.asked == ["gpt-5-mini", "gpt-5"]
        assert outcome.terminal_reason == "stop-sufficient"
        assert outcome.escalations == 1

    def test_a_passing_cheap_model_never_escalates(
        self, case, contract, governed, answer_key
    ):
        # The mirror. Escalating on every run would pass the test above while
        # destroying the saving the cheap path exists to produce.
        arm, driver = governed()
        model = ByModel({"gpt-5-mini": GOOD, "gpt-5": GOOD})
        outcome = drive(case, contract, arm, model, answer_key)
        assert model.asked == ["gpt-5-mini"]
        assert outcome.escalations == 0
        assert driver.escalations == 0

    def test_escalation_stops_at_the_contract_s_limit(
        self, case, contract, governed, answer_key
    ):
        # `max_escalations: 0` with a stronger model still available, so the
        # limit is the only thing that can stop it. Asserting against the
        # shipped `max_escalations: 1` would prove nothing: with two eligible
        # models, running out of models and running out of escalations happen
        # at the same moment.
        arm, driver = governed()
        driver.contract = contract.model_copy(
            update={
                "escalation": contract.escalation.model_copy(
                    update={"max_escalations": 0}
                )
            }
        )
        model = ByModel({"gpt-5-mini": WRONG, "gpt-5": GOOD})
        outcome = drive(case, contract, arm, model, answer_key)
        assert model.asked == ["gpt-5-mini"]
        assert driver.escalations == 0
        assert outcome.terminal_reason == "returned-partial"

    def test_the_shipped_limit_of_one_is_reached_and_then_honoured(
        self, case, contract, governed, answer_key
    ):
        arm, driver = governed()
        model = ByModel({"gpt-5-mini": WRONG, "gpt-5": WRONG})
        outcome = drive(case, contract, arm, model, answer_key)
        assert model.asked == ["gpt-5-mini", "gpt-5"]
        assert driver.escalations == contract.escalation.max_escalations == 1
        assert outcome.terminal_reason == "returned-partial"

    def test_the_top_of_the_eligible_list_cannot_escalate(
        self, case, contract, governed, answer_key
    ):
        arm, driver = governed()
        arm._start_model = "gpt-5"
        driver.model_id = "gpt-5"
        model = ByModel({"gpt-5": WRONG})
        outcome = drive(case, contract, arm, model, answer_key)
        assert model.asked == ["gpt-5"]
        assert outcome.terminal_reason == "returned-partial"


class TestAnEscalatedRunHasNotEnded:
    def test_the_run_stays_open_across_the_retry(
        self, case, contract, governed, answer_key
    ):
        # Closing it would make the retry a second run, and no comparison could
        # pair two governed runs against one baseline.
        arm, driver = governed()
        drive(case, contract, arm, ByModel({"gpt-5-mini": WRONG, "gpt-5": GOOD}), answer_key)
        kinds = [e.kind for e in driver.store.events(driver.run_id)]
        assert kinds.count("run-closed") == 1
        assert kinds[-1] == "run-closed"

    def test_both_attempts_are_in_one_log(self, case, contract, governed, answer_key):
        arm, driver = governed()
        drive(case, contract, arm, ByModel({"gpt-5-mini": WRONG, "gpt-5": GOOD}), answer_key)
        events = driver.store.events(driver.run_id)
        verdicts = [e.gate_verdict for e in events if e.kind == "gate-verdict"]
        assert verdicts == ["fail", "pass"]

    def test_the_escalation_is_recorded_with_both_models(
        self, case, contract, governed, answer_key
    ):
        arm, driver = governed()
        drive(case, contract, arm, ByModel({"gpt-5-mini": WRONG, "gpt-5": GOOD}), answer_key)
        escalations = [
            e
            for e in driver.store.events(driver.run_id)
            if e.policy_action == "escalate"
        ]
        assert len(escalations) == 1
        assert escalations[0].payload["from"] == "gpt-5-mini"
        assert escalations[0].payload["to"] == "gpt-5"
        assert escalations[0].decision_reason == "escalation-gate-fail"

    def test_the_retry_inherits_the_evidence_but_not_the_failed_answer(
        self, case, contract, governed, answer_key
    ):
        # Tool results are facts from the corpus, independent of which model
        # fetched them. Re-fetching costs a second full round of latency and
        # tokens for nothing, and in a real-time system that is the dominant
        # cost. The failed answer is a different matter and is not carried: a
        # turn that produces a deliverable appends no assistant message, so the
        # stronger model inherits what was learned and not the reasoning that
        # failed on it.
        arm, _ = governed()
        seen: list[list[str]] = []

        class ToolThenAnswer:
            def __init__(self) -> None:
                self.turns = 0

            def complete(self, request):
                seen.append([m.role for m in request.messages])
                self.turns += 1
                if request.model_id == "gpt-5-mini" and self.turns == 1:
                    return ModelResponse(
                        model_id=request.model_id,
                        text="",
                        prompt_tokens=100,
                        completion_tokens=10,
                        tool_calls=(
                            ToolInvocation(id="c1", tool="schema_describe", arguments={}),
                        ),
                    )
                text = WRONG if request.model_id == "gpt-5-mini" else GOOD
                return ModelResponse(
                    model_id=request.model_id,
                    text=text,
                    prompt_tokens=100,
                    completion_tokens=50,
                )

        drive(case, contract, arm, ToolThenAnswer(), answer_key)
        assert seen[0] == ["system", "user"]
        assert seen[1] == ["system", "user", "assistant", "tool"]
        # The retry keeps the tool result and gains no assistant answer.
        assert seen[2] == ["system", "user", "assistant", "tool"]
        assert "assistant" not in seen[2][3:]

    def test_the_retry_gets_a_fresh_iteration_budget(
        self, case, contract, governed, answer_key
    ):
        # An escalation that inherited an exhausted counter would be granted and
        # then have no turns to use it, which is the shape the bug took: the
        # mechanism fires, the log says so, and nothing happens.
        arm, _ = governed()
        model = ByModel({"gpt-5-mini": WRONG, "gpt-5": GOOD})
        outcome = drive(case, contract, arm, model, answer_key, max_iterations=1)
        assert model.asked == ["gpt-5-mini", "gpt-5"]
        assert outcome.terminal_reason == "stop-sufficient"

    def test_tokens_are_counted_against_each_model_separately(
        self, case, contract, governed, answer_key
    ):
        # FR62 reprices the governed run at the baseline's rate. An escalated
        # run spends on two models, and pricing the whole of it at either one
        # misstates the routing term in both directions. Observed live: the
        # proof card refused to build until this existed.
        arm, _ = governed()
        outcome = drive(
            case, contract, arm, ByModel({"gpt-5-mini": WRONG, "gpt-5": GOOD}), answer_key
        )
        assert set(outcome.tokens_by_model) == {"gpt-5-mini", "gpt-5"}
        counted = sum(p + c for p, c in outcome.tokens_by_model.values())
        assert counted == outcome.spend.total_tokens

    def test_a_run_that_never_escalated_counts_one_model(
        self, case, contract, governed, answer_key
    ):
        arm, _ = governed()
        outcome = drive(
            case, contract, arm, ByModel({"gpt-5-mini": GOOD, "gpt-5": GOOD}), answer_key
        )
        assert set(outcome.tokens_by_model) == {"gpt-5-mini"}


class TestTheReserveIsProtected:
    # Sized so the *escalation* is what cannot be afforded. An allocation too
    # small for the first turn would kill the run before the guard was reached,
    # and the test would pass without ever exercising it.
    ALLOCATED, RESERVE = 1000, 800

    def test_the_run_does_reach_the_gate_first(self, case, contract, governed, answer_key):
        # The premise of the two tests below.
        arm, driver = governed(allocated_tokens=self.ALLOCATED, reserve_tokens=self.RESERVE)
        drive(case, contract, arm, ByModel({"gpt-5-mini": WRONG, "gpt-5": GOOD}), answer_key)
        kinds = [e.kind for e in driver.store.events(driver.run_id)]
        assert "gate-verdict" in kinds

    def test_an_escalation_that_would_eat_the_reserve_is_refused(
        self, case, contract, governed, answer_key
    ):
        # `never_breach_verification_reserve: true`. The reserve exists so a run
        # can always afford to check its own work; an escalation that ate it
        # would buy a better answer and lose the ability to tell.
        arm, driver = governed(allocated_tokens=self.ALLOCATED, reserve_tokens=self.RESERVE)
        model = ByModel({"gpt-5-mini": WRONG, "gpt-5": GOOD})
        drive(case, contract, arm, model, answer_key)
        assert model.asked == ["gpt-5-mini"]
        assert driver.escalations == 0

    def test_the_refusal_is_recorded_rather_than_silent(
        self, case, contract, governed, answer_key
    ):
        arm, driver = governed(allocated_tokens=self.ALLOCATED, reserve_tokens=self.RESERVE)
        drive(case, contract, arm, ByModel({"gpt-5-mini": WRONG, "gpt-5": GOOD}), answer_key)
        denied = [
            e
            for e in driver.store.events(driver.run_id)
            if e.decision_reason == "unaffordable" and "escalation" in (e.payload or {})
        ]
        assert denied

    def test_a_roomy_budget_does_escalate(self, case, contract, governed, answer_key):
        # The mirror: a guard that refused every escalation would pass both
        # tests above and silently disable the mechanism.
        arm, driver = governed(allocated_tokens=1_000_000, reserve_tokens=10)
        drive(case, contract, arm, ByModel({"gpt-5-mini": WRONG, "gpt-5": GOOD}), answer_key)
        assert driver.escalations == 1
