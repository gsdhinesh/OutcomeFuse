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
from outcomefuse.harness.proofcard import headline
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


class Thriftier(Model):
    """The smaller model answers in fewer tokens than the larger one.

    Not a thumb on the scale: it reproduces what the live runs measured, where
    the arms differed because the models did. A fixture returning identical
    counts for both arms produces no saving at all, and then every attribution
    test passes vacuously against an empty breakdown.
    """

    THRIFTY = "gpt-5-mini"

    def complete(self, request):
        response = super().complete(request)
        if request.model_id != self.THRIFTY:
            return response
        return response.model_copy(update={"prompt_tokens": 60, "completion_tokens": 20})


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


class TestAnAgentThatNeverAnswers:
    # Found live on doc-research, which ran out of turns. Every offline test had
    # the model answering on turn one, so this whole path was unexercised.

    def test_a_case_with_no_deliverable_still_pairs(self, contract, tmp_path):
        report = run_campaign(
            a_plan(contract, model=Model("I am thinking about it.")),
            runs_dir=tmp_path,
            max_cases=1,
        )
        assert len(report.results) == 1
        assert report.results[0].baseline_passed is False

    def test_no_gate_verdict_is_written_when_the_gate_did_not_run(self, contract, tmp_path):
        # The record spine refuses a `gate-verdict` with no verification mode,
        # which is what caught this: writing down a `fail` the gate never
        # produced puts a verdict in the log that nothing evaluated.
        report = run_campaign(
            a_plan(contract, model=Model("not json at all")),
            runs_dir=tmp_path,
            max_cases=1,
        )
        case_id = report.results[0].case_id
        with RecordStore(tmp_path / f"{case_id}-baseline.db", writer=False).open() as s:
            events = s.events(f"{case_id}-baseline")
        assert [e.kind for e in events].count("gate-verdict") == 0
        assert [e.kind for e in events][-1] == "run-closed"

    def test_the_run_is_still_sealed(self, contract, tmp_path):
        report = run_campaign(
            a_plan(contract, model=Model("not json at all")),
            runs_dir=tmp_path,
            max_cases=1,
        )
        assert len(report.results[0].baseline_seal) == 64

    def test_a_gate_verdict_is_written_when_it_did_run(self, contract, tmp_path):
        # The mirror: a recorder that never wrote a verdict at all would pass
        # the test above and lose every real score.
        report = run_campaign(a_plan(contract), runs_dir=tmp_path, max_cases=1)
        case_id = report.results[0].case_id
        with RecordStore(tmp_path / f"{case_id}-baseline.db", writer=False).open() as s:
            verdicts = [e for e in s.events(f"{case_id}-baseline") if e.kind == "gate-verdict"]
        assert len(verdicts) == 1
        assert verdicts[0].verification_mode


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

    def test_a_cost_reduction_is_quotable_once_the_table_is_priced(self, contract, tmp_path):
        # FR66 sets a net_cost_reduction target, so the figure has to reach the
        # headline or the target has nothing to be checked against.
        table = CostTable(
            version="ct-9", currency="USD", per_tokens=1_000_000,
            rates={
                "gpt-5": Rate(input=1.25, output=10.0),
                "gpt-5-mini": Rate(input=0.25, output=2.0),
            },
        )
        report = run_campaign(
            a_plan(contract, cost_table=table), runs_dir=tmp_path, max_cases=1
        )
        assert "net_cost_reduction" in headline(report.proof_card())

    def test_an_unpriced_campaign_reports_a_zero_cost_reduction(self, contract, tmp_path):
        # Zero rather than absent, and the manifest's cost_table_version says
        # why. A missing key would read as an oversight.
        report = run_campaign(a_plan(contract), runs_dir=tmp_path, max_cases=1)
        assert headline(report.proof_card())["net_cost_reduction"] == 0.0


PRICED = CostTable(
    version="ct-9",
    currency="USD",
    per_tokens=1_000_000,
    rates={
        "gpt-5": Rate(input=1.25, output=10.0),
        "gpt-5-mini": Rate(input=0.25, output=2.0),
    },
)


class TestTheBreakdownTravelsWithTheFigure:
    # FR62: a headline savings figure does not ship without it. The breakdown is
    # what lets a reader tell governing from a cheaper model, and a figure
    # nobody can decompose is a figure nobody can refute.

    def test_a_campaign_produces_a_per_mechanism_breakdown(self, contract, tmp_path):
        report = run_campaign(
            a_plan(contract, model=Thriftier()), runs_dir=tmp_path, max_cases=1
        )
        assert report.proof_card().per_mechanism

    def test_the_breakdown_names_the_mechanism_that_stopped_the_run(
        self, contract, tmp_path
    ):
        # The scripted agent answers on turn one, so nothing shortened the run:
        # the gate confirmed a result it did not cause. The breakdown says so
        # rather than crediting the gate, which is the whole point of FR62.
        report = run_campaign(
            a_plan(contract, model=Thriftier()), runs_dir=tmp_path, max_cases=1
        )
        governed = report.results[0].governed
        assert governed.terminal_reason == "stop-sufficient"
        assert not governed.cut_short
        assert set(report.proof_card().per_mechanism) == {"agent-stopped-unaided"}

    def test_a_run_the_governor_cut_short_is_credited_to_it(self, contract, tmp_path):
        # The mirror. Without it, `cut_short` could be hardwired False and the
        # test above would still pass while the breakdown said nothing.
        report = run_campaign(
            a_plan(contract, model=Thriftier()), runs_dir=tmp_path, max_cases=1
        )
        report.results[0].governed = report.results[0].governed.model_copy(
            update={"cut_short": True}
        )
        assert set(report.proof_card().per_mechanism) == {"quality-gate"}

    def test_an_arm_that_saved_nothing_gets_no_breakdown(self, contract, tmp_path):
        # And FR62 then refuses the headline, which is correct: there is no
        # saving to break down.
        report = run_campaign(a_plan(contract), runs_dir=tmp_path, max_cases=1)
        assert report.proof_card().per_mechanism == {}
        assert not report.reportability(headline_claim=True).publishable

    def test_the_cost_split_separates_routing_from_governing(self, contract, tmp_path):
        # The governed arm runs gpt-5-mini and the baseline gpt-5, so the
        # routing term is present and a reader can see it doing the work.
        report = run_campaign(
            a_plan(contract, cost_table=PRICED, model=Thriftier()),
            runs_dir=tmp_path,
            max_cases=1,
        )
        split = report.cost_attribution()
        assert "model-routing" in split
        assert sum(split.values()) == pytest.approx(1.0)

    def test_there_is_no_routing_term_when_both_arms_share_a_model(
        self, contract, tmp_path
    ):
        report = run_campaign(
            a_plan(contract, cost_table=PRICED, governed_model="gpt-5"),
            runs_dir=tmp_path,
            max_cases=1,
        )
        assert "model-routing" not in report.cost_attribution()

    def test_the_run_records_which_model_it_used(self, contract, tmp_path):
        # Repricing needs it, and it has to refuse rather than guess once
        # escalation makes it more than one.
        report = run_campaign(a_plan(contract), runs_dir=tmp_path, max_cases=1)
        assert report.results[0].governed.models_used == ("gpt-5-mini",)
        assert report.results[0].baseline.models_used == ("gpt-5",)


class TestTheAdapterIsCertifiedNotAsserted:
    def test_the_battery_actually_runs(self, contract, tmp_path):
        report = run_campaign(a_plan(contract), runs_dir=tmp_path, max_cases=1)
        assert report.battery is not None
        assert len(report.battery.results) == 6

    def test_the_facts_carry_the_battery_s_real_verdict(self, contract, tmp_path):
        # AD-15 makes an uncertified adapter inadmissible, so a hardcoded True
        # here would be the most effective way to publish an unchecked figure.
        report = run_campaign(a_plan(contract), runs_dir=tmp_path, max_cases=1)
        baseline_facts, governed_facts = report.run_facts()
        assert baseline_facts.adapter_passed_conformance is report.battery.passed
        assert governed_facts.adapter_passed_conformance is report.battery.passed

    def test_a_failing_battery_makes_the_run_inadmissible(self, contract, tmp_path):
        # The mirror. Without it, "conformance passed" would be untested and the
        # gate would be decoration.
        report = run_campaign(a_plan(contract), runs_dir=tmp_path, max_cases=1)
        report.battery = None
        verdict = report.reportability(headline_claim=True)
        assert not verdict.admissible
        assert any("conformance" in r for r in verdict.refusals)


class TestTheDeliverableIsKept:
    # AD-5b. Until this existed the run recorded that a gate passed and not
    # what it passed, so FR69's blind review — the check that exists to
    # contradict the gate — had nothing to read.

    def test_both_arms_write_their_deliverable(self, contract, tmp_path):
        report = run_campaign(a_plan(contract), runs_dir=tmp_path, max_cases=1)
        case_id = report.results[0].case_id
        for arm in ("baseline", "governed"):
            path = tmp_path / "evidence" / f"{case_id}-{arm}" / "deliverable.json"
            assert path.is_file(), arm
            assert json.loads(path.read_text(encoding="utf-8"))["result_value"] == 16

    def test_the_log_carries_a_reference_and_a_hash_not_a_body(self, contract, tmp_path):
        # The decision log is the audit trail, not the archive. Putting the
        # answer in it would make every run's log grow with its content and
        # would hand a blind reviewer the verdict alongside the deliverable.
        report = run_campaign(a_plan(contract), runs_dir=tmp_path, max_cases=1)
        case_id = report.results[0].case_id
        with RecordStore(tmp_path / f"{case_id}-governed.db", writer=False).open() as s:
            refs = [
                e
                for e in s.events(f"{case_id}-governed")
                if "deliverable" in (e.payload or {}) and "sha256" in (e.payload or {})
            ]
        assert len(refs) == 1
        assert refs[0].payload["deliverable"] == "deliverable.json"
        assert len(refs[0].payload["sha256"]) == 64

    def test_a_blind_reviewer_can_read_it_without_the_verdict(self, contract, tmp_path):
        from outcomefuse.evidence.store import EvidenceStore

        report = run_campaign(a_plan(contract), runs_dir=tmp_path, max_cases=1)
        case_id = report.results[0].case_id
        store = EvidenceStore(tmp_path / "evidence", data_class="synthetic")
        handle = store.for_blind_review(f"{case_id}-governed")
        assert json.loads(handle.deliverable())["result_value"] == 16
        # Structural: the handle has no method that returns a verdict at all.
        assert not hasattr(handle, "verdict")

    def test_a_run_with_no_deliverable_writes_none(self, contract, tmp_path):
        # Nothing to keep, and an empty file would look like an answer.
        report = run_campaign(
            a_plan(contract, model=Model("not json")), runs_dir=tmp_path, max_cases=1
        )
        case_id = report.results[0].case_id
        assert not (
            tmp_path / "evidence" / f"{case_id}-governed" / "deliverable.json"
        ).exists()


class TestReportability:
    def test_a_calibration_campaign_cannot_support_a_headline(self, contract, tmp_path):
        # Calibration results never contribute to a headline figure (§8.5).
        report = run_campaign(a_plan(contract), runs_dir=tmp_path, max_cases=1)
        verdict = report.reportability(headline_claim=True)
        assert any("calibration" in r for r in verdict.refusals)

    def test_independence_is_self_reported_without_gateway_metering(
        self, contract, tmp_path
    ):
        # E13 is cut, so token counts come from the provider's own usage block
        # rather than an independent meter. Graded, not refused — the
        # measurement is weaker, not absent.
        report = run_campaign(a_plan(contract), runs_dir=tmp_path, max_cases=1)
        assert report.reportability(headline_claim=False).independence == "self-reported"
