"""The committed preregistration and the study it derives from (FR66, §8.5).

A preregistration is worth exactly as much as the difficulty of editing it
afterwards. Everything here exists to make that difficulty real:

- the record is loaded from a committed file, never constructed with defaults,
  because an empty preregistration is indistinguishable from a permissive one —
  no target to miss, no threshold to breach, every result reportable;
- its targets cite the overhead study **by content digest**, so a study
  re-measured to be kinder no longer matches;
- the manifest cites the record by digest, so a record edited after the runs no
  longer matches the runs that claimed to be bound by it.

The numbers themselves are a judgement and are not asserted here. What is
asserted is that they are complete, self-consistent, and actually achievable —
a target that cannot be met and a threshold that cannot fail are the same kind
of decoration.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from outcomefuse.harness.cases import load_case_set
from outcomefuse.harness.overhead import check_targets_are_derived, load_study
from outcomefuse.harness.preregistration import (
    COUNTER_METRICS,
    PreregistrationError,
    load_preregistration,
)

VERSION = "prereg-1"
STUDY = Path("preregistration/overhead-study-1.yaml")
WORKLOADS = ("data-sql", "code-triage", "doc-research", "supply-chain")


@pytest.fixture(scope="module")
def prereg():
    return load_preregistration(VERSION)


@pytest.fixture(scope="module")
def study():
    return load_study(STUDY)


class TestItExistsAndIsComplete:
    def test_it_loads(self, prereg):
        assert prereg.recorded_at.endswith("Z")

    def test_every_counter_metric_carries_a_threshold(self, prereg):
        # One that cannot fail is decoration. The model enforces this; the test
        # is here because the committed record is the one that matters.
        assert set(prereg.counter_metric_thresholds) == COUNTER_METRICS

    def test_it_has_a_stable_digest(self, prereg):
        assert prereg.digest().sha256 == load_preregistration(VERSION).digest().sha256

    def test_a_missing_record_refuses_rather_than_defaulting(self, tmp_path):
        with pytest.raises(PreregistrationError, match="no preregistration"):
            load_preregistration("prereg-nope", root=tmp_path)


class TestTheTargetsAreDerivedNotAsserted:
    def test_the_record_cites_the_study_it_was_derived_from(self, prereg, study):
        assert check_targets_are_derived(prereg, study) == []

    def test_a_different_study_does_not_satisfy_the_citation(self, prereg, study):
        # §8.5's whole mechanism: re-measuring overhead to get a kinder number
        # changes the digest, and the citation stops matching.
        kinder = study.model_copy(update={"governor_overhead_tokens": 1})
        findings = check_targets_are_derived(prereg, kinder)
        assert findings and "asserted rather than derived" in findings[0]

    def test_the_record_is_not_dated_before_its_study(self, prereg, study):
        assert prereg.recorded_at >= study.recorded_at

    def test_the_study_is_a_calibration_measurement(self, study):
        # Measuring overhead on the evaluation set would inspect the results the
        # split exists to seal.
        assert study.split == "calibration"


class TestTheNumbersAreAchievable:
    def test_the_minimum_case_count_fits_the_evaluation_split(self, prereg):
        # The trap this guards: a minimum above the cases that exist makes every
        # claim refuse itself, permanently and silently.
        smallest = min(len(load_case_set(w, "evaluation").cases) for w in WORKLOADS)
        assert prereg.minimum_case_count <= smallest

    def test_the_blind_review_sample_fits_the_minimum(self, prereg):
        # It is drawn from quality-matched pairs, so it cannot exceed the
        # smallest number of pairs a claim is allowed to rest on.
        assert prereg.blind_review_sample_size <= prereg.minimum_case_count

    def test_the_latency_threshold_is_above_the_measured_cost_of_durability(
        self, prereg, study
    ):
        # Roughly all the added latency is five fsyncs per decision, which buys
        # FR5's ordering guarantee rather than any governing. A threshold under
        # it would fail on durability and be read as the governor's fault.
        assert prereg.counter_metric_thresholds["added-latency"] > study.added_latency_p95_ms

    def test_the_savings_targets_are_fractions(self, prereg):
        for value in prereg.savings.model_dump().values():
            assert 0 <= value <= 1

    def test_the_tool_call_target_does_not_lead(self, prereg):
        # A tool-call reduction is maximised by denying everything, so it should
        # never be the most demanding number in the record.
        assert prereg.savings.tool_call_reduction <= prereg.savings.net_token_reduction


class TestWhatItAdmits:
    def test_the_overhead_share_threshold_is_currently_non_binding(self, prereg, study):
        # Recorded, not hidden. With E12 cut every registered mechanism is
        # deterministic and spends no tokens, so this counter-metric cannot fail
        # on the current build. It is disclosed in the record's own comments and
        # asserted here so the day it starts binding is visible.
        assert study.governor_overhead_tokens == 0
        assert study.token_overhead_share <= prereg.counter_metric_thresholds[
            "governor-overhead-share"
        ]

    def test_the_record_names_the_unit_of_the_latency_threshold(self, prereg):
        # `counter_metric_thresholds` is a bare dict of floats, so the unit lives
        # nowhere in the type. It has to be stated somewhere a reader will find.
        assert "millisecond" in prereg.derived_from.lower()
