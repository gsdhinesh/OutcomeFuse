"""The campaign: both arms, paired (AD-9, AD-10, FR52).

The claim this file defends is that the two arms are *comparable*. Everything
else in the product can be right and the result still be worthless if the arms
differ somewhere the experiment does not exist to vary — and that failure is
silent, because a campaign with mismatched arms still runs, still pairs, still
renders a proof card with a confident number on it.

`require_comparable` is the check, so these tests put the campaign's own
manifests through it rather than re-deriving what comparable means.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from outcomefuse.core.contract import load_path
from outcomefuse.core.record import RecordStore
from outcomefuse.harness.campaign import (
    GOVERNED_MECHANISMS,
    CampaignError,
    Plan,
    build_manifest,
    run_campaign,
)
from outcomefuse.harness.comparison import ComparisonRefused, require_comparable
from outcomefuse.harness.costs import CostTable, Rate
from outcomefuse.ports import ModelResponse

WORKLOAD = "data-sql"
VERSIONS = {"gpt-5": "gpt-5-2025-08-07", "gpt-5-mini": "gpt-5-mini-2025-08-07"}


@pytest.fixture(scope="module")
def contract():
    return load_path(Path(f"contracts/{WORKLOAD}.contract.yaml"))


#: A deliverable the data-sql gate passes for ds-c-001, whose derived key is
#: 16 rows, 16, count. Written out in full because a partial one would fail on
#: `sql-present` and the tests would be measuring the fixture.
CORRECT = json.dumps(
    {
        "result_value": 16,
        "units": "count",
        "row_count": 16,
        "sql": "SELECT COUNT(*) FROM orders WHERE order_date >= '2026-01-01'",
        "tables_used": ["orders"],
        "assumptions": ["inclusive date bounds"],
    }
)


class Model:
    """Answers on the first turn, so a pair forms without a network."""

    def __init__(self, text: str = CORRECT) -> None:
        self._text = text
        self.requests: list = []

    def complete(self, request):
        self.requests.append(request)
        return ModelResponse(
            model_id=request.model_id,
            text=self._text,
            prompt_tokens=100,
            completion_tokens=50,
            reasoning_tokens=30,
            provider_version=VERSIONS.get(request.model_id, request.model_id),
        )


def a_plan(contract, **over) -> Plan:
    base = {
        "workload": WORKLOAD,
        "split": "calibration",
        "contract": contract,
        "model": Model(),
        "max_output_tokens": 25000,
        "reasoning_effort": "medium",
        "provider_versions": dict(VERSIONS),
    }
    return Plan(**(base | over))


class TestTheArmsAreComparable:
    def test_the_two_manifests_pass_the_comparison_check(self, contract):
        plan = a_plan(contract)
        baseline = build_manifest(plan, run_id="c-baseline", mode="baseline", mechanisms={})
        governed = build_manifest(
            plan, run_id="c-governed", mode="governed", mechanisms=dict(GOVERNED_MECHANISMS)
        )
        require_comparable(baseline, governed)  # raises if not

    def test_both_arms_declare_the_whole_eligible_model_set(self, contract):
        # The governed arm starts on gpt-5-mini and the baseline on gpt-5, but
        # `model_ids` must match: escalation is a mechanism, not a different set
        # of models. An arm declaring only what it happened to start on would be
        # refused, and widening MAY_DIFFER to allow it is how a comparison stops
        # being about governance.
        plan = a_plan(contract)
        baseline = build_manifest(plan, run_id="a", mode="baseline", mechanisms={})
        governed = build_manifest(plan, run_id="b", mode="governed", mechanisms={})
        assert baseline.model_ids == governed.model_ids == tuple(contract.models.eligible)

    def test_the_mechanisms_are_where_the_arms_differ(self, contract):
        plan = a_plan(contract)
        baseline = build_manifest(plan, run_id="a", mode="baseline", mechanisms={})
        governed = build_manifest(
            plan, run_id="b", mode="governed", mechanisms=dict(GOVERNED_MECHANISMS)
        )
        assert baseline.enabled_mechanisms == {}
        assert governed.enabled_mechanisms == GOVERNED_MECHANISMS

    def test_a_differing_seed_is_refused(self, contract):
        # Proves the check above is load-bearing rather than vacuous.
        baseline = build_manifest(a_plan(contract), run_id="a", mode="baseline", mechanisms={})
        governed = build_manifest(
            a_plan(contract, seed=2), run_id="b", mode="governed", mechanisms={}
        )
        with pytest.raises(ComparisonRefused, match="seed"):
            require_comparable(baseline, governed)

    def test_a_differing_cost_table_is_refused(self, contract):
        table = CostTable(
            version="ct-9", currency="USD", per_tokens=1_000_000,
            rates={"gpt-5": Rate(input=1.0, output=2.0)},
        )
        baseline = build_manifest(a_plan(contract), run_id="a", mode="baseline", mechanisms={})
        governed = build_manifest(
            a_plan(contract, cost_table=table), run_id="b", mode="governed", mechanisms={}
        )
        with pytest.raises(ComparisonRefused, match="cost_table_version"):
            require_comparable(baseline, governed)

    def test_an_unobserved_provider_version_refuses_rather_than_blanks(self, contract):
        # AD-9. Two arms that each guessed a version would be silently
        # incomparable, and the manifest would record the guess as fact.
        plan = a_plan(contract, provider_versions={"gpt-5": "gpt-5-2025-08-07"})
        with pytest.raises(CampaignError, match="gpt-5-mini"):
            build_manifest(plan, run_id="a", mode="baseline", mechanisms={})

    def test_the_contract_hash_is_the_real_digest(self, contract):
        manifest = build_manifest(a_plan(contract), run_id="a", mode="baseline", mechanisms={})
        assert manifest.contract_hash == contract.digest().sha256


class TestACampaignRuns:
    @pytest.fixture
    def report(self, contract, tmp_path):
        # ds-c-001 only: the scripted answer is correct for that case, and a
        # second case would fail the key and leave nothing quality-matched.
        return run_campaign(a_plan(contract), runs_dir=tmp_path, max_cases=1)

    def test_both_arms_ran_for_each_case(self, report):
        assert len(report.results) == 1
        for result in report.results:
            assert result.baseline.arm == "baseline"
            assert result.governed.arm == "governed"

    def test_both_arms_are_sealed(self, report):
        # A paired case carries both seals. An unsealed arm cannot be paired,
        # which is why the baseline is recorded at all.
        for result in report.results:
            assert len(result.baseline_seal) == 64
            assert len(result.governed_seal) == 64
            assert result.baseline_seal != result.governed_seal

    def test_both_arms_were_gated(self, report):
        # FR52 removes the governor from the baseline, not the measurement.
        # An ungated baseline has no pass rate and cannot be quality-matched.
        for result in report.results:
            assert isinstance(result.baseline_passed, bool)
            assert isinstance(result.governed_passed, bool)

    def test_a_proof_card_is_produced(self, report):
        card = report.proof_card()
        assert card.workload == WORKLOAD
        assert card.case_count == 1
        assert len(card.digest().sha256) == 64

    def test_both_arms_passed_so_the_pair_is_quality_matched(self, report):
        # The premise of the card above. Savings are only computed over pairs
        # both arms passed: spend compared across different outcomes reports a
        # saving that bought a worse answer.
        card = report.proof_card()
        assert card.quality_matched_pairs == 1

    def test_the_pairs_are_per_case_not_aggregate(self, report):
        card = report.proof_card()
        assert [p.case_id for p in card.pairs] == [r.case_id for r in report.results]

    def test_nothing_was_excluded(self, report):
        assert report.excluded == []


class TestTheBaselineIsScoredButNotSteered:
    def test_the_baseline_gate_runs_once_at_the_end(self, contract, tmp_path):
        # The governed arm consults the gate at every evidence step and may stop
        # on sufficiency — that is the mechanism under test. If the baseline's
        # gate ran early it would inherit that mechanism and the experiment
        # would compare the governor against itself.
        report = run_campaign(a_plan(contract), runs_dir=tmp_path, max_cases=1)
        result = report.results[0]
        with RecordStore(tmp_path / f"{result.case_id}-baseline.db", writer=False).open() as s:
            kinds = [e.kind for e in s.events(f"{result.case_id}-baseline")]
        assert kinds.count("gate-verdict") == 1
        assert kinds[-1] == "run-closed"

    def test_the_baseline_log_carries_no_decision(self, contract, tmp_path):
        # Nothing in the baseline arm decides anything. A `decision-recorded`
        # here would mean a governor had got in by the back door.
        report = run_campaign(a_plan(contract), runs_dir=tmp_path, max_cases=1)
        result = report.results[0]
        with RecordStore(tmp_path / f"{result.case_id}-baseline.db", writer=False).open() as s:
            kinds = {e.kind for e in s.events(f"{result.case_id}-baseline")}
        assert "decision-recorded" not in kinds
        assert "budget-reserved" not in kinds

    def test_the_governed_log_does_carry_decisions(self, contract, tmp_path):
        # The mirror. Without it, a baseline log that was simply empty would
        # pass the test above and prove nothing.
        report = run_campaign(a_plan(contract), runs_dir=tmp_path, max_cases=1)
        result = report.results[0]
        with RecordStore(tmp_path / f"{result.case_id}-governed.db", writer=False).open() as s:
            kinds = {e.kind for e in s.events(f"{result.case_id}-governed")}
        assert "decision-recorded" in kinds


class TestCostIsNeverInvented:
    def test_an_unpriced_campaign_reports_zero_cost_and_real_tokens(self, contract, tmp_path):
        report = run_campaign(a_plan(contract), runs_dir=tmp_path, max_cases=1)
        result = report.results[0]
        assert result.baseline.cost == 0.0
        assert result.baseline.spend.total_tokens > 0

    def test_the_manifest_says_the_table_was_unpriced(self, contract):
        manifest = build_manifest(a_plan(contract), run_id="a", mode="baseline", mechanisms={})
        assert manifest.cost_table_version == "ct-unpriced"

    def test_a_priced_table_is_used_and_named(self, contract, tmp_path):
        table = CostTable(
            version="ct-9", currency="USD", per_tokens=1_000_000,
            rates={
                "gpt-5": Rate(input=1.25, output=10.0),
                "gpt-5-mini": Rate(input=0.25, output=2.0),
            },
        )
        plan = a_plan(contract, cost_table=table)
        report = run_campaign(plan, runs_dir=tmp_path, max_cases=1)
        assert report.results[0].baseline.cost > 0
        assert build_manifest(
            plan, run_id="a", mode="baseline", mechanisms={}
        ).cost_table_version == "ct-9"
