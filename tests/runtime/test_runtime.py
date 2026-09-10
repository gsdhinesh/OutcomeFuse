"""The enforcing driver and Tool Governor (E7, FR29-FR35, FR85-FR91, AD-20).

The rule these tests lean on hardest is FR33. Caching, exact deduplication and
semantic deduplication are optimisations and must never touch a side-effecting
or non-deterministic tool; safety, affordability and approval are not
optimisations and must still apply to it. A naive implementation keys on the
call and gets this exactly backwards for the one tool where it matters.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from outcomefuse.core.contract import load_text
from outcomefuse.core.policy import Ledger, Reserve
from outcomefuse.core.record import RunManifest, fold, open_store
from outcomefuse.core.verify import CitableEntry, CitableIndex
from outcomefuse.ports import ProbedToolPort, ScriptedApprovalPort, ToolCall
from outcomefuse.runtime import Driver, ToolGovernor, ToolGovernorError, canonical_key

SHA = "e" * 64

CONTRACT = """
contract_id: ofc-runtime
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
  - name: enrich
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


@pytest.fixture
def contract():
    return load_text(CONTRACT)


def a_ledger() -> Ledger:
    return Ledger(
        allocated_tokens=10000,
        allocated_cost=1.0,
        reserve=Reserve(max_tokens=1000, max_estimated_cost=0.1, sizing="declared"),
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


@pytest.fixture
def make_driver(tmp_path: Path, contract):
    """Builds drivers and closes their stores however the test ends.

    A store left open by a failing assertion surfaces later as an unraisable
    ResourceWarning against an unrelated test, which is a miserable way to find
    out about it.
    """
    stores = []
    counter = {"n": 0}

    def build(*, approval="approved", handlers=None):
        counter["n"] += 1
        store = open_store(tmp_path / f"w{counter['n']}.db")
        stores.append(store)
        driver = Driver(
            run_id="run-1",
            contract=contract,
            store=store,
            ledger=a_ledger(),
            governor=ToolGovernor(contract, ScriptedApprovalPort(default=approval)),
            tools=ProbedToolPort(
                handlers
                if handlers is not None
                else {"search": lambda c: "found", "pay": lambda c: "paid"}
            ),
        )
        driver.open_run(manifest())
        return driver

    yield build
    for store in stores:
        store.close()


class TestCanonicalToolKey:
    def test_the_same_call_gives_the_same_key(self):
        left = ToolCall(tool="search", arguments={"q": "a"}, step_id="s1")
        right = ToolCall(tool="search", arguments={"q": "a"}, step_id="s2")
        assert canonical_key(left) == canonical_key(right)

    def test_argument_order_does_not_change_the_key(self):
        left = ToolCall(tool="search", arguments={"a": 1, "b": 2}, step_id="s1")
        right = ToolCall(tool="search", arguments={"b": 2, "a": 1}, step_id="s1")
        assert canonical_key(left) == canonical_key(right)

    def test_one_and_one_point_zero_are_the_same_key(self):
        # AD-6's single numeric form, arriving where FR29 needs it.
        left = ToolCall(tool="search", arguments={"n": 1}, step_id="s1")
        right = ToolCall(tool="search", arguments={"n": 1.0}, step_id="s1")
        assert canonical_key(left) == canonical_key(right)

    def test_a_different_tool_gives_a_different_key(self):
        left = ToolCall(tool="search", arguments={"q": "a"}, step_id="s1")
        right = ToolCall(tool="enrich", arguments={"q": "a"}, step_id="s1")
        assert canonical_key(left) != canonical_key(right)


class TestFR33SideEffectingExclusion:
    """Optimisation must not touch it; safety and approval still must."""

    def governor(self, contract, decision="approved"):
        return ToolGovernor(contract, ScriptedApprovalPort(default=decision))

    def test_a_side_effecting_tool_is_never_cached(self, contract):
        governor = self.governor(contract)
        call = ToolCall(tool="pay", arguments={"amount": 10}, step_id="s1")
        governor.assess(call, run_id="r")
        governor.observe(call, "receipt")
        assert governor.cache_size == 0

    def test_a_repeated_side_effecting_call_is_not_denied_as_duplicate(self, contract):
        governor = self.governor(contract)
        call = ToolCall(tool="pay", arguments={"amount": 10}, step_id="s1")
        governor.observe(call, "receipt")
        again = governor.assess(call, run_id="r")
        assert again.action == "proceed"
        assert again.reason != "duplicate"

    def test_a_side_effecting_call_is_never_substituted_from_cache(self, contract):
        governor = self.governor(contract)
        call = ToolCall(tool="pay", arguments={"amount": 10}, step_id="s1")
        governor.observe(call, "receipt")
        assert governor.assess(call, run_id="r").action != "proceed-with-substitution"

    def test_a_side_effecting_call_is_not_denied_as_optional_satisfied(self, contract):
        governor = self.governor(contract)
        call = ToolCall(tool="pay", arguments={"amount": 10}, step_id="s1")
        disposition = governor.assess(
            call, run_id="r", unmet_mandatory=set(), step_is_enrichment=True
        )
        assert disposition.action == "proceed"

    def test_approval_still_applies_to_a_side_effecting_tool(self, contract):
        # Refusing to cache a payment is correct; refusing to stop an unapproved
        # one would not be.
        governor = self.governor(contract, decision="denied")
        call = ToolCall(tool="pay", arguments={"amount": 10}, step_id="s1")
        assert governor.assess(call, run_id="r").action == "pause-for-approval"

    def test_a_deterministic_tool_is_optimisable(self, contract):
        assert ToolGovernor(contract).optimisable("search")

    def test_a_side_effecting_tool_is_not_optimisable(self, contract):
        assert not ToolGovernor(contract).optimisable("pay")

    def test_an_undeclared_tool_is_refused(self, contract):
        with pytest.raises(ToolGovernorError, match="not declared"):
            ToolGovernor(contract).assess(
                ToolCall(tool="mystery", step_id="s1"), run_id="r"
            )


class TestOptimisationOnDeterministicTools:
    def test_a_repeat_is_served_from_cache(self, contract):
        governor = ToolGovernor(contract)
        call = ToolCall(tool="search", arguments={"q": "a"}, step_id="s1")
        governor.observe(call, "result")
        disposition = governor.assess(call, run_id="r")
        assert disposition.action == "proceed-with-substitution"
        assert disposition.cached_result == "result"

    def test_an_exact_duplicate_without_a_cached_result_is_denied(self, contract):
        governor = ToolGovernor(contract)
        call = ToolCall(tool="search", arguments={"q": "a"}, step_id="s1")
        governor._seen.add(canonical_key(call))
        assert governor.assess(call, run_id="r").reason == "duplicate"

    def test_enrichment_is_denied_once_the_floor_is_met(self, contract):
        governor = ToolGovernor(contract)
        call = ToolCall(tool="enrich", arguments={"q": "a"}, step_id="s1")
        disposition = governor.assess(
            call, run_id="r", unmet_mandatory=set(), step_is_enrichment=True
        )
        assert disposition.reason == "optional-satisfied"

    def test_enrichment_is_permitted_while_the_floor_is_unmet(self, contract):
        governor = ToolGovernor(contract)
        call = ToolCall(tool="enrich", arguments={"q": "a"}, step_id="s1")
        disposition = governor.assess(
            call, run_id="r", unmet_mandatory={"answer-matches-key"}, step_is_enrichment=True
        )
        assert disposition.action == "proceed"

    def test_the_cache_is_run_scoped(self, contract):
        # AD-14: no cross-run, cross-process or persistent cache exists.
        first = ToolGovernor(contract)
        call = ToolCall(tool="search", arguments={"q": "a"}, step_id="s1")
        first.observe(call, "result")
        second = ToolGovernor(contract)
        assert second.assess(call, run_id="r").action == "proceed"

    def test_every_disposition_is_recorded_with_its_reason(self, contract):
        # FR35: every denial, cache hit, pause and timeout.
        governor = ToolGovernor(contract)
        call = ToolCall(tool="search", arguments={"q": "a"}, step_id="s1")
        governor.assess(call, run_id="r")
        governor.observe(call, "result")
        governor.assess(call, run_id="r")
        assert [r.reason for r in governor.records] == ["justified", "cache-hit"]


class TestDriver:
    @pytest.fixture
    def driver(self, make_driver):
        return make_driver()

    def test_a_decision_is_recorded_before_it_takes_effect(self, driver):
        # FR5. The tool cannot have run before the row that authorises it.
        driver.execute_step(ToolCall(tool="search", arguments={"q": "a"}, step_id="s1"))
        kinds = [e.kind for e in driver.store.events("run-1")]
        assert kinds.index("decision-recorded") < kinds.index("outcome-observed")

    def test_the_canonical_event_order_is_followed(self, driver):
        driver.execute_step(ToolCall(tool="search", arguments={"q": "a"}, step_id="s1"))
        kinds = [e.kind for e in driver.store.events("run-1")]
        for earlier, later in (
            ("decision-proposed", "budget-reserved"),
            ("budget-reserved", "decision-recorded"),
            ("decision-recorded", "outcome-observed"),
            ("outcome-observed", "spend-settled"),
        ):
            assert kinds.index(earlier) < kinds.index(later)

    def test_a_denied_step_never_invokes_the_tool(self, driver):
        call = ToolCall(tool="search", arguments={"q": "a"}, step_id="s1")
        driver.execute_step(call)
        before = driver.tools.invocation_count("search")
        driver.governor._cache.clear()  # force the duplicate path rather than cache
        verdict = driver.execute_step(call)
        assert verdict.action == "deny"
        assert driver.tools.invocation_count("search") == before

    def test_a_cache_hit_does_not_invoke_the_tool(self, driver):
        call = ToolCall(tool="search", arguments={"q": "a"}, step_id="s1")
        driver.execute_step(call)
        driver.execute_step(call)
        assert driver.tools.invocation_count("search") == 1

    def test_the_ledger_holds_before_it_spends(self, driver):
        driver.execute_step(ToolCall(tool="search", arguments={"q": "a"}, step_id="s1"))
        assert driver.ledger.in_flight_tokens == 0
        assert driver.ledger.spent_tokens > 0

    def test_the_run_chain_verifies_after_a_step(self, driver):
        driver.execute_step(ToolCall(tool="search", arguments={"q": "a"}, step_id="s1"))
        assert driver.store.verify_run("run-1")

    def test_the_log_folds_to_a_coherent_state(self, driver):
        driver.execute_step(ToolCall(tool="search", arguments={"q": "a"}, step_id="s1"))
        state = fold(driver.store.events("run-1"))
        assert state.decisions == ("proceed",)
        assert state.tokens_spent > 0


class TestFailClosed:
    def test_an_unavailable_channel_halts_and_the_call_is_not_made(self, make_driver):
        driver = make_driver(approval="channel-unavailable")
        verdict = driver.execute_step(
            ToolCall(tool="pay", arguments={"amount": 1}, step_id="s1")
        )
        assert verdict.terminal_reason == "fail-closed"
        assert not driver.tools.was_invoked("pay")

    def test_a_timeout_is_not_routed_to_fail_closed(self, make_driver):
        # Merging them would rank an ordinary timeout above the approval gate.
        driver = make_driver(approval="no-response")
        verdict = driver.execute_step(
            ToolCall(tool="pay", arguments={"amount": 1}, step_id="s1")
        )
        assert verdict.decision_reason == "approval-timeout"
        assert verdict.terminal_reason == "approval-timeout"
        assert not driver.tools.was_invoked("pay")

    def test_a_denied_approval_does_not_make_the_call(self, make_driver):
        driver = make_driver(approval="denied")
        verdict = driver.execute_step(
            ToolCall(tool="pay", arguments={"amount": 1}, step_id="s1")
        )
        assert verdict.action == "deny"
        assert not driver.tools.was_invoked("pay")

    def test_a_terminated_run_refuses_further_steps(self, make_driver):
        driver = make_driver(approval="channel-unavailable")
        driver.execute_step(ToolCall(tool="pay", arguments={"amount": 1}, step_id="s1"))
        with pytest.raises(RuntimeError, match="already terminated"):
            driver.execute_step(ToolCall(tool="pay", arguments={"amount": 2}, step_id="s2"))

    def test_a_fail_closed_halt_releases_outstanding_holds(self, make_driver):
        driver = make_driver(approval="channel-unavailable")
        driver.execute_step(ToolCall(tool="pay", arguments={"amount": 1}, step_id="s1"))
        assert driver.ledger.outstanding() == ()


class TestTheGovernedArmEnforces:
    def test_the_governed_arm_withholds_the_call(self, make_driver):
        # The pair with the shadow tests is the point: same condition,
        # opposite effect on the host.
        governed = make_driver(approval="channel-unavailable")
        governed.execute_step(ToolCall(tool="pay", arguments={"amount": 1}, step_id="s1"))
        assert not governed.tools.was_invoked("pay")

    def test_the_enforcing_driver_refuses_a_shadow_manifest(self, make_driver, tmp_path):
        # AD-11: a shadow run is a different driver, not this one with a flag.
        driver = make_driver()
        assert not hasattr(driver, "shadow")
        with pytest.raises(ValueError, match="belongs to ShadowDriver"):
            driver.open_run(manifest("run-2").model_copy(update={"mode": "shadow"}))


class TestCitableIndex:
    def test_the_index_hash_is_appended_before_any_verifier_runs(self, make_driver):
        # AD-7: two implementations deriving it differently would otherwise
        # produce different verdicts for the same run.
        driver = make_driver()
        index = CitableIndex(entries=(CitableEntry(id="doc-1", target="t", sha256=SHA),))
        digest = driver.bind_citable_index(index)
        payloads = [
            e.payload.get("citable_index_sha256")
            for e in driver.store.events("run-1")
            if e.payload
        ]
        assert digest.sha256 in payloads
