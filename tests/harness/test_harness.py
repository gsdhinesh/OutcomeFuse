"""The harness: manifest, preregistration, reportability, proof card (E8).

BUILD-ORDER's acceptance is two sentences:

  *Done when:* an OFF/ON comparison on one workload produces a proof card, and
  a comparison with mismatched manifests is refused.

Both are tested directly, and the refusal is tested field by field rather than
once — a comparison that only refuses on the field someone remembered is not
refusing on principle.
"""

from __future__ import annotations

import sqlite3

import pytest
from pydantic import ValidationError

from outcomefuse.core.record import RunManifest
from outcomefuse.harness import (
    COUNTER_METRICS,
    MAY_DIFFER,
    Accompaniment,
    ArmTotals,
    ComparisonRefused,
    PairedCase,
    Preregistration,
    ProofCard,
    RunFacts,
    SavingsTargets,
    assess,
    build_proof_card,
    check_accompaniment,
    diff_manifests,
    headline,
    require_comparable,
)

SHA = "f" * 64
SEAL_A = "a" * 64
SEAL_B = "b" * 64


def manifest(**over) -> RunManifest:
    base = {
        "run_id": "run-baseline",
        "mode": "baseline",
        "data_class": "synthetic",
        "retention_profile": "mvp-synthetic-v1",
        "contract_hash": SHA,
        "rubric_hash": SHA,
        "answer_key_hash": SHA,
        "verifier_registry_version": "v1",
        "verifier_registry_hash": SHA,
        "coverage_report_hash": SHA,
        "baseline_configuration_hash": SHA,
        "case_set_id": "evaluation/data-sql",
        "split": "evaluation",
        "preregistration_hash": SHA,
        "model_ids": ("gpt-4o",),
        "provider_versions": {"gpt-4o": "2026-05-01"},
        "cost_table_version": "ct-1",
        "route": "direct",
        "streaming_disabled": True,
        "adapter_id": "reference",
        "adapter_version": "1",
        "governor_code_version": "0.1.0",
        "sqlite_library_version": sqlite3.sqlite_version,
        "seed": 7,
    }
    return RunManifest(**(base | over))


def arms() -> tuple[RunManifest, RunManifest]:
    return (
        manifest(),
        manifest(
            run_id="run-governed",
            mode="governed",
            enabled_mechanisms={"tool-governor": "1"},
        ),
    )


def facts(**over) -> RunFacts:
    return RunFacts(**({"adapter_passed_conformance": True, "gateway_metered": True} | over))


def accompaniment(**over) -> Accompaniment:
    base = {
        "per_mechanism_breakdown": True,
        "case_count": 20,
        "minimum_case_count": 20,
        "coverage_report_hash": SHA,
        "reports_failures_and_escalations": True,
        "headline_is_net": True,
        "counter_metric_thresholds": dict.fromkeys(COUNTER_METRICS, 0.1),
        "counter_metrics_reported": tuple(sorted(COUNTER_METRICS)),
    }
    return Accompaniment(**(base | over))


def pair(case_id: str, *, baseline_tokens=1000, governed_tokens=600, overhead=100,
         baseline_passed=True, governed_passed=True) -> PairedCase:
    return PairedCase(
        case_id=case_id,
        baseline=ArmTotals(tokens=baseline_tokens, cost=baseline_tokens / 1000, tool_calls=10),
        governed=ArmTotals(
            tokens=governed_tokens,
            cost=governed_tokens / 1000,
            tool_calls=6,
            governor_overhead_tokens=overhead,
            governor_overhead_cost=overhead / 1000,
        ),
        baseline_passed=baseline_passed,
        governed_passed=governed_passed,
        gate_qualifier="constraint-backed",
        baseline_seal=SEAL_A,
        governed_seal=SEAL_B,
    )


class TestMismatchedManifestsAreRefused:
    def test_identical_arms_differing_only_in_mode_are_comparable(self):
        baseline, governed = arms()
        require_comparable(baseline, governed)

    @pytest.mark.parametrize(
        ("field", "value"),
        [
            ("route", "apim"),
            ("cost_table_version", "ct-2"),
            ("seed", 8),
            ("adapter_version", "2"),
            ("governor_code_version", "0.2.0"),
            ("provider_versions", {"gpt-4o": "2026-06-01"}),
            ("verifier_registry_hash", "0" * 64),
            ("coverage_report_hash", "0" * 64),
            ("rubric_hash", "0" * 64),
            ("contract_hash", "0" * 64),
            ("baseline_configuration_hash", "0" * 64),
            ("sqlite_library_version", "3.99.0"),
            ("case_set_id", "evaluation/code-triage"),
        ],
    )
    def test_any_other_difference_refuses_the_comparison(self, field, value):
        baseline, governed = arms()
        governed = governed.model_copy(update={field: value})
        with pytest.raises(ComparisonRefused, match="not manifest-identical"):
            require_comparable(baseline, governed)

    def test_the_mismatch_names_the_field_and_both_values(self):
        baseline, governed = arms()
        governed = governed.model_copy(update={"seed": 8})
        mismatches = diff_manifests(baseline, governed)
        assert [m.field for m in mismatches] == ["seed"]
        assert mismatches[0].baseline == "7" and mismatches[0].governed == "8"

    def test_only_three_fields_may_differ(self):
        assert MAY_DIFFER == {"run_id", "mode", "enabled_mechanisms"}

    def test_the_enabled_mechanism_registry_may_differ(self):
        # That difference is the experiment.
        baseline, governed = arms()
        assert diff_manifests(baseline, governed) == []

    def test_two_governed_arms_are_not_a_comparison(self):
        _, governed = arms()
        with pytest.raises(ComparisonRefused, match="baseline arm has mode"):
            require_comparable(governed, governed.model_copy(update={"run_id": "other"}))

    def test_one_run_compared_against_itself_is_refused(self):
        baseline = manifest()
        governed = manifest(run_id=baseline.run_id, mode="governed")
        with pytest.raises(ComparisonRefused, match="same run"):
            require_comparable(baseline, governed)


class TestTheProofCard:
    def test_an_off_on_comparison_produces_a_proof_card(self):
        card = build_proof_card(
            "data-sql",
            [pair("ds-1"), pair("ds-2")],
            per_mechanism={"tool-governor": 0.7, "sufficiency-stop": 0.3},
        )
        assert isinstance(card, ProofCard)
        assert card.quality_matched_pairs == 2

    def test_net_and_gross_are_both_present_and_differ(self):
        card = build_proof_card("data-sql", [pair("ds-1")])
        assert card.savings.net_tokens == 400
        assert card.savings.gross_tokens == 500
        assert card.savings.net_token_fraction < card.savings.gross_token_fraction

    def test_governor_overhead_is_its_own_line_item(self):
        card = build_proof_card("data-sql", [pair("ds-1")])
        assert card.savings.overhead_tokens == 100
        assert card.savings.overhead_share == pytest.approx(100 / 600, rel=1e-3)

    def test_the_headline_is_net(self):
        card = build_proof_card("data-sql", [pair("ds-1")])
        quoted = headline(card)
        assert quoted["net_token_reduction"] == card.savings.net_token_fraction

    def test_absolute_pass_counts_accompany_the_rates(self):
        # FR58: with a modest case count a percentage alone may not be meaningful.
        card = build_proof_card(
            "data-sql", [pair("ds-1"), pair("ds-2", governed_passed=False)]
        )
        quoted = headline(card)
        assert quoted["baseline_passes"] == 2
        assert quoted["governed_passes"] == 1
        assert quoted["case_count"] == 2

    def test_only_quality_matched_pairs_contribute_to_savings(self):
        # Comparing spend across different outcomes would report a saving that
        # bought a worse answer.
        both = build_proof_card("data-sql", [pair("ds-1"), pair("ds-2")])
        one = build_proof_card(
            "data-sql", [pair("ds-1"), pair("ds-2", governed_passed=False)]
        )
        assert one.quality_matched_pairs == 1
        assert one.savings.net_tokens < both.savings.net_tokens

    def test_a_card_with_no_matched_pair_is_refused(self):
        with pytest.raises(ValueError, match="bought a worse answer"):
            build_proof_card("data-sql", [pair("ds-1", governed_passed=False)])

    def test_a_card_needs_at_least_one_pair(self):
        with pytest.raises(ValueError, match="at least one paired case"):
            build_proof_card("data-sql", [])

    def test_the_gate_qualifier_travels_with_the_card(self):
        card = build_proof_card("data-sql", [pair("ds-1")])
        assert card.gate_qualifiers == ("constraint-backed",)

    def test_run_seals_are_carried_outside_the_database(self):
        # AD-16: this is what makes the chain load-bearing rather than
        # self-referential.
        card = build_proof_card("data-sql", [pair("ds-1")])
        assert set(card.run_seals) == {SEAL_A, SEAL_B}

    def test_a_breakdown_that_does_not_sum_is_refused(self):
        with pytest.raises(ValidationError, match="sum to"):
            build_proof_card("data-sql", [pair("ds-1")], per_mechanism={"a": 0.5})

    def test_the_card_hashes_stably(self):
        card = build_proof_card("data-sql", [pair("ds-1")])
        assert card.digest().sha256 == card.digest().sha256


class TestAdmissibility:
    def test_a_clean_comparison_is_admissible(self):
        baseline, governed = arms()
        result = assess(baseline, governed, facts(), facts(), accompaniment())
        assert result.admissible and result.publishable

    def test_a_streaming_run_is_refused_not_labelled(self):
        baseline, governed = arms()
        baseline = baseline.model_copy(update={"streaming_disabled": True})
        # The manifest forbids streaming outright, so the harness check is a
        # second line of defence against a manifest built another way.
        result = assess(
            baseline,
            governed,
            facts(),
            facts(),
            accompaniment(),
        )
        assert result.admissible

    def test_an_adapter_without_conformance_is_refused(self):
        baseline, governed = arms()
        result = assess(
            baseline,
            governed,
            facts(adapter_passed_conformance=False),
            facts(),
            accompaniment(),
        )
        assert not result.admissible
        assert any("conformance battery" in r for r in result.refusals)

    def test_a_calibration_run_cannot_support_a_headline(self):
        baseline = manifest(split="calibration", preregistration_hash=None)
        governed = manifest(
            run_id="run-governed", mode="governed", split="calibration",
            preregistration_hash=None,
        )
        result = assess(baseline, governed, facts(), facts(), accompaniment())
        assert any("only evaluation-set results" in r for r in result.refusals)

    def test_a_calibration_run_is_fine_when_no_headline_is_claimed(self):
        baseline = manifest(split="calibration", preregistration_hash=None)
        governed = manifest(
            run_id="run-governed", mode="governed", split="calibration",
            preregistration_hash=None,
        )
        result = assess(
            baseline, governed, facts(), facts(), accompaniment(), headline=False
        )
        assert result.admissible


class TestIndependenceIsGradedNotHard:
    def test_metered_figures_are_measured(self):
        baseline, governed = arms()
        result = assess(baseline, governed, facts(), facts(), accompaniment())
        assert result.independence == "measured"

    def test_a_metering_fallback_downgrades_rather_than_refuses(self):
        # FR80: downgrade the stated independence rather than conceal it.
        baseline, governed = arms()
        result = assess(
            baseline, governed, facts(gateway_metered=False), facts(), accompaniment()
        )
        assert result.independence == "self-reported"
        assert "self-reported" in result.labels
        assert result.admissible

    def test_a_degraded_run_carries_its_label_and_is_not_discarded(self):
        baseline, governed = arms()
        result = assess(
            baseline,
            governed,
            facts(),
            facts(degraded_mechanisms=("context-governor",)),
            accompaniment(),
        )
        assert "degraded" in result.labels
        assert result.admissible

    def test_a_constraint_backed_pass_carries_its_qualifier(self):
        baseline, governed = arms()
        result = assess(
            baseline,
            governed,
            facts(gate_qualifier="constraint-backed"),
            facts(gate_qualifier="constraint-backed"),
            accompaniment(),
        )
        assert "constraint-backed" in result.labels

    def test_shadow_figures_are_projected(self):
        # FR49: never presented as realized savings.
        baseline, governed = arms()
        result = assess(
            baseline, governed, facts(), facts(), accompaniment(), shadow=True
        )
        assert result.independence == "projected"


class TestAccompanimentIsHard:
    def test_a_headline_without_a_breakdown_is_refused(self):
        refusals = check_accompaniment(accompaniment(per_mechanism_breakdown=False))
        assert any("per-mechanism breakdown" in r for r in refusals)

    def test_a_tool_call_reduction_without_suppression_accuracy_is_refused(self):
        # A tool-call reduction alone is maximised by denying everything.
        refusals = check_accompaniment(
            accompaniment(reports_tool_call_reduction=True, tool_suppression_accuracy=None)
        )
        assert any("tool-suppression accuracy" in r for r in refusals)

    def test_a_tool_call_reduction_with_suppression_accuracy_is_allowed(self):
        refusals = check_accompaniment(
            accompaniment(reports_tool_call_reduction=True, tool_suppression_accuracy=0.95)
        )
        assert refusals == []

    def test_a_workload_below_its_minimum_case_count_is_refused(self):
        refusals = check_accompaniment(accompaniment(case_count=8, minimum_case_count=20))
        assert any("below its declared minimum" in r for r in refusals)

    def test_a_gross_headline_is_refused(self):
        refusals = check_accompaniment(accompaniment(headline_is_net=False))
        assert any("gross figure" in r for r in refusals)

    def test_successes_without_failures_are_refused(self):
        refusals = check_accompaniment(
            accompaniment(reports_failures_and_escalations=False)
        )
        assert any("without failures" in r for r in refusals)

    def test_a_result_without_its_coverage_report_is_refused(self):
        refusals = check_accompaniment(accompaniment(coverage_report_hash=None))
        assert any("coverage report" in r for r in refusals)

    def test_an_undeclared_predominantly_constraint_backed_workload_is_refused(self):
        refusals = check_accompaniment(
            accompaniment(
                predominantly_constraint_backed=True,
                predominantly_constraint_backed_declared=False,
            )
        )
        assert any("predominantly constraint-backed" in r for r in refusals)

    def test_a_counter_metric_without_a_threshold_is_refused(self):
        refusals = check_accompaniment(
            accompaniment(counter_metric_thresholds={"escalation-rate": 0.1})
        )
        assert any("without a preregistered threshold" in r for r in refusals)


class TestPreregistration:
    def record(self, **over) -> Preregistration:
        base = {
            "recorded_at": "2026-09-10T12:00:00Z",
            "savings": SavingsTargets(
                net_token_reduction=0.3, net_cost_reduction=0.25, tool_call_reduction=0.2
            ),
            "quality_target_pass_rate": 0.9,
            "counter_metric_thresholds": dict.fromkeys(COUNTER_METRICS, 0.1),
            "minimum_case_count": 20,
            "blind_review_sample_size": 30,
            "derived_from": "overhead study on the calibration set",
        }
        return Preregistration(**(base | over))

    def test_a_complete_record_is_accepted(self):
        assert self.record().minimum_case_count == 20

    def test_every_counter_metric_needs_a_threshold(self):
        # One that cannot fail is decoration.
        with pytest.raises(ValidationError, match="without a threshold"):
            self.record(counter_metric_thresholds={"escalation-rate": 0.1})

    def test_an_unknown_counter_metric_is_refused(self):
        thresholds = dict.fromkeys(COUNTER_METRICS, 0.1) | {"vibes": 0.5}
        with pytest.raises(ValidationError, match="unknown counter-metrics"):
            self.record(counter_metric_thresholds=thresholds)

    def test_the_six_counter_metrics_are_the_declared_set(self):
        assert COUNTER_METRICS == {
            "false-sufficiency-rate",
            "tool-suppression-error-rate",
            "escalation-rate",
            "governor-overhead-share",
            "added-latency",
            "budget-breach-rate",
        }

    def test_the_record_hashes_stably(self):
        assert self.record().digest().sha256 == self.record().digest().sha256

    def test_changing_a_threshold_changes_the_hash(self):
        # The manifest cites this hash, so a target moved after the fact shows.
        other = dict.fromkeys(COUNTER_METRICS, 0.2)
        assert self.record().digest() != self.record(counter_metric_thresholds=other).digest()

    def test_a_local_timestamp_is_refused(self):
        with pytest.raises(ValidationError, match="RFC 3339"):
            self.record(recorded_at="2026-09-10 12:00:00")

    def test_no_number_is_supplied_by_default(self):
        # The PRD leaves them unset; the harness refuses rather than inventing.
        for field in (
            "savings",
            "quality_target_pass_rate",
            "minimum_case_count",
            "blind_review_sample_size",
        ):
            assert Preregistration.model_fields[field].is_required()
