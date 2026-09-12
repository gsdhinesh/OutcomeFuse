"""The submission artifact (E15, F16, FR81-FR84, §8.4).

These tests are about the failure that survives everything upstream: the run
worked, the proof card is honest, and the video still says something the
evidence does not support. Every refusal below corresponds to a way that has
actually happened to somebody — a calibration number quoted as a result, a
projection shown as a saving, gross leading because it is the bigger number, or
one flattering case standing in for a workload.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from outcomefuse.core.record import Event
from outcomefuse.harness import (
    COUNTER_METRICS,
    ArmTotals,
    PairedCase,
    Preregistration,
    Reportability,
    SavingsTargets,
    build_proof_card,
)
from outcomefuse.submission import (
    BEAT_ORDER,
    MAX_SECONDS,
    Beat,
    Figure,
    Provenance,
    Submission,
    SubmissionRefused,
    build_submission,
    check_submission,
    evidence_of_mechanism,
    required_labels,
)

WHEN = "2026-09-10T12:00:00Z"
SEAL_A = "a" * 64
SEAL_B = "b" * 64
CONTRACT = "c" * 64
UNKNOWN = "d" * 64


def a_card(workload: str = "data-sql"):
    def pair(case_id: str) -> PairedCase:
        return PairedCase(
            case_id=case_id,
            baseline=ArmTotals(tokens=1000, cost=0.10, tool_calls=10),
            governed=ArmTotals(
                tokens=700,
                cost=0.07,
                tool_calls=6,
                governor_overhead_tokens=50,
                governor_overhead_cost=0.005,
            ),
            baseline_passed=True,
            governed_passed=True,
            gate_qualifier="reference-backed",
            baseline_seal=SEAL_A,
            governed_seal=SEAL_B,
        )

    return build_proof_card(
        workload, [pair("c1"), pair("c2")], {"tool-governor": 0.7, "quality-gate": 0.3}
    )


def a_log() -> list[Event]:
    return [
        Event(
            run_id="run-g",
            seq=0,
            kind="run-manifest",
            recorded_at=WHEN,
            payload={"manifest": {"contract_hash": CONTRACT}},
        ),
        Event(
            run_id="run-g",
            seq=1,
            kind="decision-recorded",
            recorded_at=WHEN,
            step_id="s1",
            policy_action="deny",
            decision_reason="duplicate",
        ),
        # Consulted mid-run, so stopping here actually shortened the run. A
        # verdict recorded at submission confirms an agent that had already
        # stopped, and FR84 asks the video to demonstrate the mechanism rather
        # than an event that resembles it.
        Event(
            run_id="run-g",
            seq=2,
            kind="gate-verdict",
            recorded_at=WHEN,
            gate_verdict="pass",
            verification_mode="reference-backed",
            payload={"when": "mid-run"},
        ),
        Event(
            run_id="run-g",
            seq=3,
            kind="decision-recorded",
            recorded_at=WHEN,
            policy_action="terminate",
            decision_reason="sufficiency",
            terminal_reason="stop-sufficient",
        ),
        Event(run_id="run-g", seq=4, kind="run-closed", recorded_at=WHEN),
    ]


def mechanism(events=None):
    return evidence_of_mechanism(events if events is not None else a_log(), seal=SEAL_A)


def provenance(**over) -> Provenance:
    base = {
        "artifact": "proof-card",
        "digest": SEAL_A,
        "run_ids": ("run-g",),
        "split": "evaluation",
        "mode": "governed",
        "case_count": 20,
        "workload": "data-sql",
    }
    return Provenance(**(base | over))


def figure(**over) -> Figure:
    base = {
        "key": "net_token_reduction",
        "value": 0.3,
        "basis": "net",
        "role": "claim",
        "provenance": provenance(),
    }
    return Figure(**(base | over))


def beats(figures=(), shows=("outcome-contract", "decision-stream", "sufficiency-stop")):
    return [
        Beat(name="problem", seconds=20, says="Agents spend without a stopping rule."),
        Beat(name="artifact", seconds=30, says="An Outcome Contract.", shows=shows[:1]),
        Beat(
            name="proof",
            seconds=45,
            says="The governor stops when the floor is met.",
            shows=tuple(shows[1:]),
            figures=tuple(figures),
        ),
        Beat(name="scale", seconds=20, says="The mechanism is workload-shaped."),
    ]


def prereg(**over) -> Preregistration:
    base = {
        "recorded_at": WHEN,
        "savings": SavingsTargets(
            net_token_reduction=0.2, net_cost_reduction=0.2, tool_call_reduction=0.2
        ),
        "quality_target_pass_rate": 0.9,
        "counter_metric_thresholds": dict.fromkeys(COUNTER_METRICS, 0.1),
        "minimum_case_count": 20,
        "blind_review_sample_size": 10,
        "derived_from": "calibration overhead study",
    }
    return Preregistration(**(base | over))


def reportable(publishable: bool = True) -> Reportability:
    return Reportability(
        admissible=publishable,
        independence="measured",
        labels=(),
        refusals=() if publishable else ("baseline arm streamed",),
    )


class TestFourBeatsInOrder:
    def test_the_beats_are_the_four_in_order(self):
        assert Submission(
            beats=tuple(beats()), mechanism=mechanism(), workloads_completed=("data-sql",)
        ).seconds == 115

    def test_a_reordered_script_is_refused(self):
        out_of_order = list(beats())
        out_of_order[1], out_of_order[2] = out_of_order[2], out_of_order[1]
        with pytest.raises(ValidationError, match="in that order"):
            Submission(
                beats=tuple(out_of_order),
                mechanism=mechanism(),
                workloads_completed=("data-sql",),
            )

    def test_a_missing_beat_is_refused(self):
        with pytest.raises(ValidationError, match="in that order"):
            Submission(
                beats=tuple(beats()[:3]),
                mechanism=mechanism(),
                workloads_completed=("data-sql",),
            )

    def test_running_over_two_minutes_is_refused(self):
        long = list(beats())
        long[0] = long[0].model_copy(update={"seconds": MAX_SECONDS})
        with pytest.raises(ValidationError, match=f"over FR81's {MAX_SECONDS}s"):
            Submission(
                beats=tuple(long), mechanism=mechanism(), workloads_completed=("data-sql",)
            )

    def test_the_beat_names_are_a_closed_set(self):
        with pytest.raises(ValidationError, match="not one of FR81's beats"):
            Beat(name="demo", seconds=10, says="...")
        assert BEAT_ORDER == ("problem", "artifact", "proof", "scale")


class TestShowingTheMechanism:
    def test_the_three_demonstrations_are_read_out_of_the_log(self):
        evidence = mechanism()
        assert evidence.contract_hash == CONTRACT
        assert evidence.decisions == (("deny", "duplicate"), ("terminate", "sufficiency"))
        assert evidence.sufficiency_stop

    def test_a_run_with_no_decision_stream_cannot_be_shown(self):
        with pytest.raises(SubmissionRefused, match="no decision stream"):
            evidence_of_mechanism(a_log()[:1], seal=SEAL_A)

    def test_results_without_the_mechanism_are_refused(self):
        # FR84: showing results alone is how a system that does not work
        # produces a convincing video.
        with pytest.raises(ValidationError, match="FR84's minimum is not shown"):
            Submission(
                beats=tuple(beats(shows=("outcome-contract",))),
                mechanism=mechanism(),
                workloads_completed=("data-sql",),
            )

    def test_promising_a_stop_no_run_made_is_refused(self):
        # A demonstration is shown from an artifact, never re-enacted.
        without_stop = [e for e in a_log() if e.decision_reason != "sufficiency"]
        with pytest.raises(ValidationError, match="promised but not present"):
            Submission(
                beats=tuple(beats()),
                mechanism=mechanism(without_stop),
                workloads_completed=("data-sql",),
            )

    def test_a_gate_that_only_confirmed_is_not_a_sufficiency_stop(self):
        # The defect this guards is the one measurement actually found: on every
        # live run the agent stopped itself and the gate scored what it handed
        # over. The events are identical to a real stop -- terminate, on
        # sufficiency, reason stop-sufficient -- so the log alone cannot tell
        # them apart, and a video narrating the second as the first would be
        # accurate about the record and wrong about the product.
        confirmed = [
            e.model_copy(update={"payload": {"when": "at-submission"}})
            if e.kind == "gate-verdict"
            else e
            for e in a_log()
        ]
        evidence = evidence_of_mechanism(confirmed, seal=SEAL_A)
        assert not evidence.sufficiency_stop
        assert "sufficiency-stop" not in evidence.demonstrates

        with pytest.raises(ValidationError, match="promised but not present"):
            Submission(
                beats=tuple(beats()),
                mechanism=evidence,
                workloads_completed=("data-sql",),
            )


class TestAFigureCarriesItsProvenance:
    def test_a_calibration_figure_is_not_a_claim(self):
        # §8.5: calibration measured the overhead that set the targets, so
        # quoting it is quoting the ruler as the measurement.
        with pytest.raises(ValidationError, match="only evaluation-set results"):
            figure(provenance=provenance(split="calibration"))

    def test_calibration_may_still_illustrate(self):
        assert figure(
            role="illustration", provenance=provenance(split="calibration")
        ).role == "illustration"

    def test_a_single_case_is_not_a_claim(self):
        # FR83: cherry-picking is a sample size, not a dishonest intention.
        with pytest.raises(ValidationError, match="is not a claim"):
            figure(provenance=provenance(case_count=1))

    def test_a_shadow_figure_can_never_be_a_claim(self):
        with pytest.raises(ValidationError, match="never as realized savings"):
            figure(provenance=provenance(mode="shadow"), labels=("projected",))

    def test_a_shadow_figure_must_be_labelled_projected(self):
        with pytest.raises(ValidationError, match="not labelled projected"):
            figure(role="illustration", provenance=provenance(mode="shadow"))

    def test_gross_may_not_lead(self):
        # FR61: gross excludes the governor's own spend, which is how this
        # category flatters itself.
        with pytest.raises(ValidationError, match="net is the headline"):
            figure(basis="gross", headline=True)

    def test_gross_may_sit_beside_the_headline(self):
        assert figure(key="gross_token_reduction", basis="gross").basis == "gross"

    def test_only_one_number_leads(self):
        two = [figure(headline=True), figure(key="net_cost_reduction", headline=True)]
        with pytest.raises(ValidationError, match="headline figures"):
            Submission(
                beats=tuple(beats(two)),
                mechanism=mechanism(),
                workloads_completed=("data-sql",),
            )

    def test_a_figure_renders_with_its_labels_never_bare(self):
        rendered = figure(
            role="illustration",
            provenance=provenance(mode="shadow"),
            labels=("projected", "self-reported"),
        ).rendered()
        assert "projected" in rendered and "self-reported" in rendered


class TestLabelsAreDerived:
    def test_governor_side_counting_is_labelled_self_reported(self):
        assert required_labels(provenance(), gateway_metered=False) == ("self-reported",)

    def test_metered_and_clean_needs_no_label(self):
        assert required_labels(provenance(), gateway_metered=True) == ()

    def test_every_label_that_applies_travels(self):
        assert required_labels(
            provenance(mode="shadow"),
            gateway_metered=False,
            degraded_mechanisms=("context-governor",),
            gate_qualifier="constraint-backed",
        ) == ("constraint-backed", "degraded", "projected", "self-reported")


class TestTraceability:
    def test_a_figure_citing_nothing_supplied_is_refused(self):
        # FR82: traceable to a recorded artifact, or it does not appear.
        refusals = check_submission(
            Submission(
                beats=tuple(beats([figure(provenance=provenance(digest=UNKNOWN))])),
                mechanism=mechanism(),
                workloads_completed=("data-sql",),
            ),
            cards=[a_card()],
            preregistration=prereg(),
            reportability=reportable(),
        )
        assert any("is not the digest of any proof card" in r for r in refusals)

    def test_a_figure_citing_the_proof_card_is_traceable(self):
        card = a_card()
        assert (
            check_submission(
                Submission(
                    beats=tuple(
                        beats([figure(provenance=provenance(digest=card.digest().sha256))])
                    ),
                    mechanism=mechanism(),
                    workloads_completed=("data-sql",),
                ),
                cards=[card],
                preregistration=prereg(),
                reportability=reportable(),
            )
            == []
        )

    def test_a_figure_citing_a_run_seal_is_traceable(self):
        card = a_card()
        assert SEAL_B in card.run_seals
        assert (
            check_submission(
                Submission(
                    beats=tuple(beats([figure(provenance=provenance(digest=SEAL_B))])),
                    mechanism=mechanism(),
                    workloads_completed=("data-sql",),
                ),
                cards=[card],
                preregistration=prereg(),
                reportability=reportable(),
            )
            == []
        )

    def test_a_claim_beyond_the_completed_workloads_is_refused(self):
        refusals = check_submission(
            Submission(
                beats=tuple(beats([figure(provenance=provenance(workload="doc-research"))])),
                mechanism=mechanism(),
                workloads_completed=("data-sql",),
            ),
            cards=[a_card()],
            preregistration=prereg(),
            reportability=reportable(),
        )
        assert any("not among the workloads completed" in r for r in refusals)

    def test_a_claim_below_the_preregistered_minimum_is_refused(self):
        refusals = check_submission(
            Submission(
                beats=tuple(beats([figure(provenance=provenance(case_count=5))])),
                mechanism=mechanism(),
                workloads_completed=("data-sql",),
            ),
            cards=[a_card()],
            preregistration=prereg(),
            reportability=reportable(),
        )
        assert any("below the preregistered minimum of 20" in r for r in refusals)

    def test_a_headline_on_a_refused_comparison_is_refused(self):
        refusals = check_submission(
            Submission(
                beats=tuple(beats([figure(headline=True)])),
                mechanism=mechanism(),
                workloads_completed=("data-sql",),
            ),
            cards=[a_card()],
            preregistration=prereg(),
            reportability=reportable(publishable=False),
        )
        assert any("the harness refused" in r for r in refusals)


class TestNoClaimWithoutPreregistration:
    def test_a_claim_without_a_preregistration_record_is_refused(self):
        # FR102: a target set after the results are known cannot be missed.
        with pytest.raises(SubmissionRefused, match="no preregistration record"):
            build_submission(
                beats([figure()]),
                mechanism=mechanism(),
                workloads_completed=("data-sql",),
                cards=[a_card()],
            )

    def test_the_mechanism_may_still_be_shown_today(self):
        # This is the submission this repository can honestly produce right now:
        # the mechanism running, and not one number about how well it does.
        submission = build_submission(
            beats(),
            mechanism=mechanism(),
            workloads_completed=("data-sql",),
        )
        assert submission.figures == ()
        assert "sufficiency-stop" in submission.render()


class TestItDoesNotNeedTheViewer:
    def test_a_full_submission_is_built_from_the_card_and_the_log_alone(self):
        # F16 depends on F13 and F12, never on F14 — which sits first in the
        # cut order.
        card = a_card()
        submission = build_submission(
            beats([figure(provenance=provenance(digest=card.digest().sha256), headline=True)]),
            mechanism=mechanism(),
            workloads_completed=("data-sql",),
            cards=[card],
            preregistration=prereg(),
            reportability=reportable(),
        )
        assert submission.headlines[0].basis == "net"
        assert submission.digest().sha256
