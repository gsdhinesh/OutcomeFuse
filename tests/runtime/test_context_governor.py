"""The Context Governor (F7, FR36-FR39), the deterministic subset.

The claim this file has to keep honest is FR38: **compression shall not drop an
attributable fact.** The mechanism discharges it structurally rather than by
judgement — the only thing it will ever elide is a body byte-identical to one
already in the conversation — so the tests are about proving the "byte-identical"
part is really that, and that FR33's exemption survives here too. A mechanism
that cached a payment's reply and told the model nothing had changed would obey
every other rule in this module and still be wrong.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from outcomefuse.core.contract import load_text
from outcomefuse.core.policy import Ledger, Reserve
from outcomefuse.core.record import RunManifest, open_store
from outcomefuse.ports import ProbedToolPort, ScriptedApprovalPort, ToolCall
from outcomefuse.runtime import ContextGovernor, Driver, ToolGovernor

SHA = "e" * 64

CONTRACT = """
contract_id: ofc-context
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
  - name: read_file
    deterministic: true
    side_effecting: false
  - name: weather
    deterministic: false
    side_effecting: false
  - name: pay
    deterministic: false
    side_effecting: true
human_approval_conditions: []
approval_timeout_seconds: 30
on_timeout: terminate
"""

#: Long enough that eliding it is worth a decision row, which is the whole point.
BODY = {"path": "cache.py", "source": "def get(key):\n    return STORE[key]\n" * 40}


@pytest.fixture
def contract():
    return load_text(CONTRACT)


def a_call(tool: str = "read_file", step: str = "s1") -> ToolCall:
    return ToolCall(tool=tool, arguments={"path": "cache.py"}, step_id=step)


class TestWhatItWillAndWillNotElide:
    def test_the_first_result_is_placed_whole(self, contract):
        context = ContextGovernor(contract)
        placed = context.place(a_call(), BODY)
        assert placed.elided is False
        assert placed.payload == BODY

    def test_the_same_bytes_a_second_time_become_a_reference(self, contract):
        context = ContextGovernor(contract)
        context.place(a_call(step="s1"), BODY)
        again = context.place(a_call(step="s2"), BODY)
        assert again.elided is True
        assert again.payload != BODY
        # The reference has to say where the bytes are, or the model is being
        # told something is missing without being told where to find it.
        assert "read_file" in again.first_seen_at
        assert "s1" in again.first_seen_at
        assert again.estimated_tokens_avoided > 0

    def test_a_different_result_is_never_elided(self, contract):
        context = ContextGovernor(contract)
        context.place(a_call(), BODY)
        other = context.place(a_call(), {**BODY, "source": "def get(key): ..."})
        assert other.elided is False
        assert context.elisions == 0

    def test_a_side_effecting_tool_is_exempt(self, contract):
        # FR33. Two identical receipts from a payment are two payments.
        context = ContextGovernor(contract)
        pay = ToolCall(tool="pay", arguments={"amount": 10}, step_id="s1")
        context.place(pay, {"receipt": "ok"})
        assert context.place(pay, {"receipt": "ok"}).elided is False

    def test_a_non_deterministic_tool_is_exempt(self, contract):
        # FR33 again, and the subtler half: the same answer twice from a tool
        # that may change its answer is a fact about now, not a duplicate.
        context = ContextGovernor(contract)
        look = ToolCall(tool="weather", arguments={"city": "Oslo"}, step_id="s1")
        context.place(look, {"c": 4})
        assert context.place(look, {"c": 4}).elided is False

    def test_an_undeclared_tool_is_left_alone(self, contract):
        context = ContextGovernor(contract)
        ghost = ToolCall(tool="git_blame", arguments={}, step_id="s1")
        context.place(ghost, BODY)
        assert context.place(ghost, BODY).elided is False

    def test_the_elided_placement_agrees_with_the_original_on_what_was_learned(
        self, contract
    ):
        # If these digests differed the Loop Fuse would read the elision as a
        # change of state and grant a stall one more turn - which is exactly
        # what it did before this was carried across.
        context = ContextGovernor(contract)
        first = context.place(a_call(step="s1"), BODY)
        again = context.place(a_call(step="s2"), BODY)
        assert first.digest == again.digest != ""


class TestNothingIsDropped:
    def test_the_facts_are_still_there_verbatim_once(self, contract):
        """FR38, as the only form of it this mechanism can claim.

        Nothing is summarised, shortened or judged, so there is no question of
        which facts survived: the body is in the transcript, unaltered, and the
        second turn points at it.
        """
        context = ContextGovernor(contract)
        placed = context.place(a_call(step="s1"), BODY)
        again = context.place(a_call(step="s2"), BODY)
        transcript = [placed.payload, again.payload]
        assert transcript.count(BODY) == 1
        assert placed.payload["source"] == BODY["source"]
        assert "read_file" in again.payload["identical_to"]

    def test_it_spends_nothing_to_save_anything(self, contract):
        """FR39. The specified F7 is a model pass; this one is a dictionary.

        There is no port on this object and no evidence request, so there is no
        compression spend for FR15 to attribute.
        """
        context = ContextGovernor(contract)
        assert not hasattr(context, "advise")
        context.place(a_call(), BODY)
        context.place(a_call(), BODY)
        assert context.elisions == 1


class TestThroughTheDriver:
    @pytest.fixture
    def make_driver(self, tmp_path: Path, contract):
        stores = []
        counter = {"n": 0}

        def build(*, with_context: bool = True):
            counter["n"] += 1
            store = open_store(tmp_path / f"c{counter['n']}.db")
            stores.append(store)
            driver = Driver(
                run_id="run-1",
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
                tools=ProbedToolPort({"read_file": lambda c: BODY}),
                context=ContextGovernor(contract) if with_context else None,
            )
            driver.open_run(
                RunManifest(
                    run_id="run-1",
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
                    model_ids=("gpt-5",),
                    provider_versions={"gpt-5": "2025-08-07"},
                    cost_table_version="ct-1",
                    route="direct",
                    streaming_disabled=True,
                    adapter_id="reference",
                    adapter_version="1",
                    governor_code_version="0.1.0",
                    sqlite_library_version=sqlite3.sqlite_version,
                    seed=1,
                )
            )
            return driver

        yield build
        for store in stores:
            store.close()

    def test_the_repeat_comes_back_as_a_reference(self, make_driver):
        driver = make_driver()
        first = driver.execute_step(a_call(step="s1"))
        second = driver.execute_step(a_call(step="s2"))
        assert first.result == BODY
        assert second.result != BODY
        assert second.result["context_governor"] == "identical-result-not-repeated"

    def test_the_decision_is_written_down(self, make_driver):
        driver = make_driver()
        driver.execute_step(a_call(step="s1"))
        driver.execute_step(a_call(step="s2"))
        rows = [
            e
            for e in driver.store.events("run-1")
            if e.decision_reason == "context-compressed"
        ]
        assert len(rows) == 1
        assert rows[0].policy_action == "proceed-with-substitution"
        assert rows[0].step_id == "s2"
        assert "already in this conversation" in (rows[0].payload or {})["detail"]

    def test_the_agent_is_recorded_as_having_asked_once_per_call(self, make_driver):
        # Two mechanisms answered the second step. Writing a second proposal row
        # for it would claim the agent asked twice, and it did not.
        driver = make_driver()
        driver.execute_step(a_call(step="s1"))
        driver.execute_step(a_call(step="s2"))
        proposed = [
            e for e in driver.store.events("run-1") if e.kind == "decision-proposed"
        ]
        assert [e.step_id for e in proposed] == ["s1", "s2"]

    def test_not_registered_is_byte_identical_to_cut(self, make_driver):
        # NFR10 and FR62: an ablation is an absent object, never an `if enabled`
        # branch that a later edit can leave half-applied.
        driver = make_driver(with_context=False)
        driver.execute_step(a_call(step="s1"))
        second = driver.execute_step(a_call(step="s2"))
        assert second.result == BODY
        assert not [
            e
            for e in driver.store.events("run-1")
            if e.decision_reason == "context-compressed"
        ]
