"""The calibration overhead study (§8.5, FR66, FR102).

Nothing here asserts a duration. A test that fails when a shared machine is
busy teaches people to rerun it until it passes, which is worse than not having
it. What *is* checked is that the study measures what it claims, refuses the
evaluation set, and cannot be cited by a preregistration that never saw it.

The one substantive claim tested is FR52-adjacent and structural: with only
deterministic mechanisms registered, the governor's **token** overhead is zero
by construction, so net and gross savings coincide and break-even is immediate.
That is a property of which mechanisms exist, not of how fast the machine is.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from pydantic import ValidationError

from outcomefuse.core.contract import load_text
from outcomefuse.core.policy import Ledger, Reserve
from outcomefuse.core.record import RunManifest, open_store
from outcomefuse.harness import (
    COUNTER_METRICS,
    Latencies,
    OverheadStudy,
    Preregistration,
    SavingsTargets,
    build_study,
    check_targets_are_derived,
    measure,
)
from outcomefuse.ports import ProbedToolPort, ScriptedApprovalPort, ToolCall
from outcomefuse.runtime import Driver, ToolGovernor

SHA = "0" * 64

CONTRACT = """
contract_id: ofc-overhead
version: 1
workload: data-sql
task_goal: Measure the governor's own cost.
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
  max_tokens: 1000000
  max_estimated_cost: 100.0
  max_tool_calls: 10000
  max_iterations: 10000
tools:
  - name: search
    deterministic: true
    side_effecting: false
"""


def latencies(p50: int = 10, p95: int = 20, top: int = 30) -> Latencies:
    return Latencies(samples=100, p50_ns=p50, p95_ns=p95, max_ns=top)


def study(**over) -> OverheadStudy:
    base = {
        "recorded_at": "2026-09-10T10:00:00Z",
        "workload": "data-sql",
        "governed": latencies(3_500_000, 4_800_000, 9_000_000),
        "baseline": latencies(2_000, 4_000, 9_000),
        "governor_overhead_tokens": 0,
        "governed_tokens": 2000,
        "events_per_decision": 5,
        "durable_write_p50_ns": 660_000,
        "enabled_mechanisms": ("tool-governor", "quality-gate"),
    }
    return build_study(**(base | over))


def prereg(**over) -> Preregistration:
    base = {
        "recorded_at": "2026-09-10T11:00:00Z",
        "savings": SavingsTargets(
            net_token_reduction=0.2, net_cost_reduction=0.2, tool_call_reduction=0.2
        ),
        "quality_target_pass_rate": 0.9,
        "counter_metric_thresholds": dict.fromkeys(COUNTER_METRICS, 0.1),
        "minimum_case_count": 20,
        "blind_review_sample_size": 10,
        "derived_from": f"overhead study {study().digest().sha256}",
    }
    return Preregistration(**(base | over))


class TestTheMeasurement:
    def test_it_records_every_sample_it_took(self):
        assert measure(lambda _n: None, repeats=25).samples == 25

    def test_a_distribution_needs_a_sample(self):
        with pytest.raises(ValueError, match="at least one sample"):
            measure(lambda _n: None, repeats=0)

    def test_percentiles_out_of_order_are_refused(self):
        with pytest.raises(ValidationError, match="out of order"):
            Latencies(samples=10, p50_ns=50, p95_ns=10, max_ns=100)

    def test_it_reports_a_distribution_rather_than_a_mean(self):
        # A mean added latency hides the tail that makes a governor
        # unacceptable, so there is no mean to report.
        assert not hasattr(latencies(), "mean_ns")


class TestItRunsOnCalibrationOnly:
    def test_build_study_offers_no_way_to_say_otherwise(self):
        with pytest.raises(TypeError):
            build_study(split="evaluation")  # type: ignore[call-arg]

    def test_and_the_model_refuses_it_directly_too(self):
        # §8.5: measuring overhead there would inspect the results the split
        # exists to seal.
        with pytest.raises(ValidationError, match="runs on the calibration set"):
            OverheadStudy(
                **(study().model_dump() | {"split": "evaluation"})
            )


class TestWhatTheStudySays:
    def test_zero_token_overhead_breaks_even_immediately(self):
        assert study().breaks_even_immediately
        assert study().token_overhead_share == 0.0

    def test_a_token_cost_does_not(self):
        costly = study(governor_overhead_tokens=200)
        assert not costly.breaks_even_immediately
        assert costly.token_overhead_share == 0.1

    def test_the_write_share_of_added_latency_is_reported(self):
        # The number a threshold-setter needs: most of the cost is durability,
        # and durability is AD-16, not something the governor can give back.
        assert study().write_share_of_added_latency > 0.9

    def test_the_write_share_never_exceeds_the_whole(self):
        assert study(durable_write_p50_ns=10_000_000).write_share_of_added_latency == 1.0

    def test_it_sets_no_targets(self):
        rendered = study().render()
        assert "sets no targets" in rendered
        for forbidden in ("target", "threshold"):
            assert f"{forbidden}:" not in rendered.lower()


class TestTargetsAreDerivedNotGuessed:
    def test_a_preregistration_citing_the_study_is_accepted(self):
        assert check_targets_are_derived(prereg(), study()) == []

    def test_one_that_cites_nothing_is_refused(self):
        # §8.5 said "derived from measured overhead" in prose and nothing
        # enforced it, so a record could cite a study it had never seen.
        findings = check_targets_are_derived(
            prereg(derived_from="my best guess"), study()
        )
        assert any("asserted rather than derived" in f for f in findings)

    def test_citing_a_different_measurement_is_refused(self):
        findings = check_targets_are_derived(
            prereg(), study(governor_overhead_tokens=500)
        )
        assert any("does not cite this study's digest" in f for f in findings)

    def test_a_preregistration_predating_its_study_is_refused(self):
        findings = check_targets_are_derived(
            prereg(recorded_at="2026-09-09T00:00:00Z"), study()
        )
        assert any("before the study it claims to derive from" in f for f in findings)


class TestTokenOverheadIsZeroByConstruction:
    def test_a_deterministic_governor_spends_no_tokens_of_its_own(self, tmp_path: Path):
        # With E12 cut, every registered mechanism is deterministic. Nothing
        # calls a model on the governor's behalf, so the overhead share that
        # FR66 thresholds is zero for structural reasons rather than lucky ones.
        contract = load_text(CONTRACT)
        store = open_store(tmp_path / "overhead.db")
        try:
            ledger = Ledger(
                allocated_tokens=1_000_000,
                allocated_cost=100.0,
                reserve=Reserve(max_tokens=1, max_estimated_cost=0.01, sizing="declared"),
            )
            driver = Driver(
                run_id="run-1",
                contract=contract,
                store=store,
                ledger=ledger,
                governor=ToolGovernor(contract, ScriptedApprovalPort(default="approved")),
                tools=ProbedToolPort({"search": lambda c: "found"}),
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
                    case_set_id="calibration/data-sql",
                    split="calibration",
                    model_ids=("scripted",),
                    provider_versions={"scripted": "0"},
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
            for n in range(5):
                driver.execute_step(
                    ToolCall(tool="search", arguments={"q": n}, step_id=f"s{n}")
                )
            assert ledger.spent_tokens == 50
            assert ledger.overhead_tokens() == 0
        finally:
            store.close()
