"""The six counter-metrics (FR66, §3.3).

A threshold with no reading is decoration, which is why the preregistration
refuses a metric without one. This is the other half: a reading that was never
taken must not look like one that was.

**Unmeasured is not zero.** `0.0` means we looked and found none; `None` means
nobody looked. They render identically on a slide and mean opposite things, and
the one that flatters happens by accident — a counter-metric defaulting to zero
passes its threshold forever while looking like evidence. Most of this file
exists to hold that line.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pytest

from outcomefuse.evidence.counter_metrics import BlindReview
from outcomefuse.harness.counters import Reading, read_counter_metrics
from outcomefuse.harness.overhead import load_study
from outcomefuse.harness.preregistration import COUNTER_METRICS, load_preregistration

STUDY = Path("preregistration/overhead-study-1.yaml")


@dataclass
class FakeSpend:
    total_tokens: int = 1000
    prompt_tokens: int = 800
    completion_tokens: int = 200
    tool_calls: int = 2


@dataclass
class FakeOutcome:
    escalations: int = 0
    terminal_reason: str | None = "stop-sufficient"
    cut_short: bool = False
    spend: FakeSpend = field(default_factory=FakeSpend)
    cost: float = 0.01
    models_used: tuple[str, ...] = ("gpt-5-mini",)
    case_id: str = "c1"


@dataclass
class FakeResult:
    case_id: str = "c1"
    baseline: FakeOutcome = field(default_factory=FakeOutcome)
    governed: FakeOutcome = field(default_factory=FakeOutcome)
    baseline_passed: bool = True
    governed_passed: bool = True
    gate_qualifier: str = "constraint-backed"


@dataclass
class FakeSavings:
    overhead_share: float = 0.0


@dataclass
class FakeCard:
    savings: FakeSavings = field(default_factory=FakeSavings)


@dataclass
class FakeReport:
    results: list
    _card: FakeCard = field(default_factory=FakeCard)

    def proof_card(self):
        return self._card


def a_report(**over) -> FakeReport:
    governed = FakeOutcome(**over)
    return FakeReport(results=[FakeResult(governed=governed)])


@pytest.fixture(scope="module")
def prereg():
    return load_preregistration("prereg-1")


@pytest.fixture(scope="module")
def study():
    return load_study(STUDY)


class TestAllSixAreAccountedFor:
    def test_every_preregistered_metric_gets_a_reading(self, prereg, study):
        metrics = read_counter_metrics(a_report(), study=study, preregistration=prereg)
        assert {r.metric for r in metrics.readings} == COUNTER_METRICS

    def test_each_reading_carries_its_threshold(self, prereg, study):
        metrics = read_counter_metrics(a_report(), study=study, preregistration=prereg)
        for reading in metrics.readings:
            assert reading.threshold == prereg.counter_metric_thresholds[reading.metric]

    def test_each_reading_says_what_it_was_computed_from(self, prereg, study):
        metrics = read_counter_metrics(a_report(), study=study, preregistration=prereg)
        for reading in metrics.readings:
            assert reading.basis.strip()


class TestUnmeasuredIsNotZero:
    def test_false_sufficiency_is_unmeasured_without_a_blind_review(self, prereg, study):
        # FR69's review is a human who never saw the verdict. A campaign cannot
        # produce one: the gate is the thing under suspicion.
        metrics = read_counter_metrics(a_report(), study=study, preregistration=prereg)
        reading = next(r for r in metrics.readings if r.metric == "false-sufficiency-rate")
        assert reading.value is None
        assert not reading.measured

    def test_a_blind_review_does_produce_a_rate(self, prereg, study):
        # The mirror: a metric that could never be measured would pass the test
        # above and be permanently decorative.
        metrics = read_counter_metrics(
            a_report(),
            study=study,
            preregistration=prereg,
            blind_review=BlindReview(reviewed=4, rejected=1, sample_size=4),
        )
        reading = next(r for r in metrics.readings if r.metric == "false-sufficiency-rate")
        assert reading.value == 0.25

    def test_suppression_is_unmeasured_when_nothing_was_suppressed(self, prereg, study):
        # Measured live: 0 of 26 tool calls were exact repeats, so the governor
        # suppressed nothing. A rate of zero would claim a perfect record for a
        # check that never ran.
        metrics = read_counter_metrics(a_report(), study=study, preregistration=prereg)
        reading = next(
            r for r in metrics.readings if r.metric == "tool-suppression-error-rate"
        )
        assert reading.value is None
        assert "not a rate of zero" in reading.basis.lower()

    def test_suppression_is_measured_once_there_is_something_to_check(
        self, prereg, study
    ):
        metrics = read_counter_metrics(
            a_report(),
            study=study,
            preregistration=prereg,
            suppressions_checked=10,
            suppression_errors=1,
        )
        reading = next(
            r for r in metrics.readings if r.metric == "tool-suppression-error-rate"
        )
        assert reading.value == 0.1

    def test_added_latency_is_unmeasured_without_a_study(self, prereg):
        metrics = read_counter_metrics(a_report(), study=None, preregistration=prereg)
        reading = next(r for r in metrics.readings if r.metric == "added-latency")
        assert reading.value is None

    def test_an_unmeasured_metric_neither_breaches_nor_passes(self):
        reading = Reading(metric="x", value=None, threshold=0.0, basis="nobody looked")
        assert not reading.breached
        assert not reading.measured

    def test_a_measured_metric_with_no_threshold_does_not_breach(self, study):
        # A campaign run without a preregistration reads real values against no
        # thresholds at all. Comparing a number to a missing threshold is not a
        # breach, and it must not be a crash either.
        metrics = read_counter_metrics(a_report(), study=study, preregistration=None)
        assert metrics.breaches == ()
        assert all(r.threshold is None for r in metrics.readings)
        assert any(r.measured for r in metrics.readings)

    def test_a_threshold_of_zero_is_a_threshold_not_an_absence(self):
        # `0.0` is falsy, so a truthiness check here would silently drop the
        # tightest threshold anyone can set.
        assert Reading(metric="x", value=0.1, threshold=0.0, basis="b").breached
        assert not Reading(metric="x", value=0.0, threshold=0.0, basis="b").breached

    def test_only_measured_metrics_are_reported_as_reported(self, prereg, study):
        # Accompaniment is told this. Naming an unmeasured metric would claim a
        # check that did not happen, and FR66's threshold test would then pass
        # against an absent number.
        metrics = read_counter_metrics(a_report(), study=study, preregistration=prereg)
        assert "false-sufficiency-rate" not in metrics.reported
        assert "escalation-rate" in metrics.reported


class TestWhatTheCampaignCanRead:
    def test_escalation_rate_counts_runs_that_escalated(self, prereg, study):
        report = FakeReport(
            results=[
                FakeResult(case_id="a", governed=FakeOutcome(escalations=1)),
                FakeResult(case_id="b", governed=FakeOutcome(escalations=0)),
            ]
        )
        metrics = read_counter_metrics(report, study=study, preregistration=prereg)
        reading = next(r for r in metrics.readings if r.metric == "escalation-rate")
        assert reading.value == 0.5

    def test_a_campaign_that_never_escalates_reads_zero_not_unmeasured(
        self, prereg, study
    ):
        # Here zero is the honest answer: the runs were inspected and none
        # escalated. The distinction from `None` is the point of the whole file.
        metrics = read_counter_metrics(a_report(), study=study, preregistration=prereg)
        reading = next(r for r in metrics.readings if r.metric == "escalation-rate")
        assert reading.value == 0.0
        assert reading.measured

    def test_added_latency_comes_from_the_study_not_the_campaign(self, prereg, study):
        metrics = read_counter_metrics(a_report(), study=study, preregistration=prereg)
        reading = next(r for r in metrics.readings if r.metric == "added-latency")
        assert reading.value == study.added_latency_p95_ms
        assert study.digest().sha256[:12] in reading.basis


class TestBreaches:
    def test_a_reading_over_its_threshold_breaches(self):
        assert Reading(metric="x", value=0.5, threshold=0.3, basis="b").breached

    def test_a_reading_at_its_threshold_does_not(self):
        # The preregistration says "no more than", so equality passes.
        assert not Reading(metric="x", value=0.3, threshold=0.3, basis="b").breached

    def test_the_shipped_campaign_breaches_nothing(self, prereg, study):
        metrics = read_counter_metrics(a_report(), study=study, preregistration=prereg)
        assert metrics.breaches == ()

    def test_an_escalating_campaign_can_breach(self, prereg, study):
        # The mirror. A breach that could never fire would make every threshold
        # in the preregistration decorative.
        report = FakeReport(results=[FakeResult(governed=FakeOutcome(escalations=1))])
        metrics = read_counter_metrics(report, study=study, preregistration=prereg)
        breached = [r.metric for r in metrics.breaches]
        assert "escalation-rate" in breached
