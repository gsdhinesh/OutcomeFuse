"""Evidence store, retention and counter-metrics (E9).

BUILD-ORDER's acceptance for E9 is a list, so each clause is tested as one:

  the access matrix is enforced rather than documented; every completed run is
  sealed by an appended run-closed event and the sweep appends run-abandoned to
  the rest, with max(run_closed_at) <= campaign_sealed_at asserted at seal,
  sealing twice refused, sealing while a run is unsealed refused, and a writer
  refused against a sealed store; a deterministic test performs a whole-run
  deletion that removes generated temporary copies and writes a content-free
  receipt without touching any run's chain; and persistence is refused for both
  tiers on any class other than synthetic.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from pydantic import ValidationError

from outcomefuse.core.record import Event, RunManifest, open_store
from outcomefuse.evidence import (
    ADMISSIBLE_DATA_CLASS,
    RAW_EVIDENCE_DAYS,
    AccessDenied,
    BlindReview,
    Campaign,
    DenialReport,
    EvidenceRefused,
    EvidenceStore,
    MarginalValueDenial,
    RetentionError,
    Suppression,
    measure_compression_fidelity,
    measure_suppression_accuracy,
    run_closed_at,
    sweep,
    unsealed_runs,
)

SHA = "1" * 64
CLOSED = "2026-09-10T12:00:00Z"
AFTER_EXPIRY = "2026-12-01T12:00:00Z"


def manifest(run_id: str) -> RunManifest:
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
        case_set_id="calibration/data-sql",
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
def workspace(tmp_path: Path):
    record = open_store(tmp_path / "workspace.db")
    evidence = EvidenceStore(tmp_path / "evidence", data_class="synthetic")
    campaign = Campaign(tmp_path / "campaign", record, evidence)
    yield record, evidence, campaign
    record.close()


def a_closed_run(record, evidence, run_id: str, *, closed_at: str = CLOSED) -> None:
    record.open_run(manifest(run_id), recorded_at="2026-09-10T11:00:00Z")
    driver = evidence.for_driver(run_id)
    driver.write("deliverable.json", '{"answer": "x"}')
    driver.write("capsules/step-1.json", '{"capsule": "y"}')
    driver.write("tmp/scratch.txt", "temporary copy")
    record.append(
        Event(run_id=run_id, seq=1, kind="run-closed", recorded_at=closed_at,
              terminal_reason="stop-sufficient")
    )


class TestTheAccessMatrixIsEnforced:
    def test_the_driver_writes_only_its_own_run(self, workspace):
        _, evidence, _ = workspace
        driver = evidence.for_driver("run-1")
        assert driver.write("a.json", "{}").run_id == "run-1"
        assert not hasattr(driver, "read")
        assert not hasattr(driver, "delete_run")

    def test_the_driver_cannot_escape_its_run_directory(self, workspace):
        _, evidence, _ = workspace
        with pytest.raises(AccessDenied, match="escapes its run"):
            evidence.for_driver("run-1").write("../run-2/stolen.json", "{}")

    def test_the_harness_reads_and_cannot_write_or_delete(self, workspace):
        _, evidence, _ = workspace
        evidence.for_driver("run-1").write("a.json", "{}")
        harness = evidence.for_harness()
        assert harness.read("run-1", "a.json") == "{}"
        assert not hasattr(harness, "write")
        assert not hasattr(harness, "delete_run")

    def test_the_retention_command_deletes_and_cannot_read_content(self, workspace):
        _, evidence, _ = workspace
        evidence.for_driver("run-1").write("a.json", "{}")
        retention = evidence.for_retention()
        assert retention.exists("run-1")
        assert not hasattr(retention, "read")
        assert not hasattr(retention, "write")

    def test_the_blind_reviewer_sees_the_deliverable(self, workspace):
        _, evidence, _ = workspace
        evidence.for_driver("run-1").write("deliverable.json", '{"answer": "x"}')
        assert evidence.for_blind_review("run-1").deliverable() == '{"answer": "x"}'

    def test_the_blind_reviewer_is_structurally_denied_the_verdict(self, workspace):
        # FR69: not merely undisplayed - there is no method that returns it.
        _, evidence, _ = workspace
        reviewer = evidence.for_blind_review("run-1")
        for forbidden in ("verdict", "decision_record", "manifest", "read", "gate_verdict"):
            assert not hasattr(reviewer, forbidden)

    def test_withheld_artifacts_do_not_appear_in_what_the_reviewer_can_read(
        self, workspace
    ):
        _, evidence, _ = workspace
        driver = evidence.for_driver("run-1")
        driver.write("deliverable.json", "{}")
        driver.write("verdict.json", '{"verdict": "pass"}')
        driver.write("manifest.json", "{}")
        readable = evidence.for_blind_review("run-1").readable()
        assert "deliverable.json" in readable
        assert "verdict.json" not in readable
        assert "manifest.json" not in readable


class TestNonSyntheticIsRefused:
    @pytest.mark.parametrize("data_class", ["non-synthetic", "replayed", "production"])
    def test_persistence_is_refused_for_any_other_class(self, tmp_path, data_class):
        # AD-21: replayed inherits the class of the run it replays, so keying
        # the refusal on non-synthetic alone would let it walk straight past.
        with pytest.raises(EvidenceRefused, match="persistence is refused"):
            EvidenceStore(tmp_path / "e", data_class=data_class)

    def test_the_refusal_covers_the_decision_log_too(self, tmp_path):
        # Refusing only evidence would leave the record with no permitted
        # retention profile, which is NFR12 unmet by a narrower route.
        with pytest.raises(EvidenceRefused, match="evidence and decision log alike"):
            EvidenceStore(tmp_path / "e", data_class="replayed")

    def test_only_synthetic_is_admissible(self):
        assert ADMISSIBLE_DATA_CLASS == "synthetic"

    def test_a_non_synthetic_manifest_is_refused_by_the_record_too(self):
        payload = manifest("run-1").model_dump() | {"data_class": "replayed"}
        with pytest.raises(ValidationError, match="governance profile"):
            RunManifest.model_validate(payload)


class TestSealing:
    def test_a_completed_run_is_sealed_by_its_appended_event(self, workspace):
        record, evidence, _ = workspace
        a_closed_run(record, evidence, "run-1")
        assert record.seal("run-1") is not None
        assert run_closed_at(record, "run-1") == CLOSED

    def test_run_closed_at_is_read_not_written(self, workspace):
        # No column is ever mutated, so it comes from the terminal row.
        record, evidence, _ = workspace
        a_closed_run(record, evidence, "run-1")
        assert record.verify_run("run-1")

    def test_sealing_while_a_run_is_unsealed_is_refused(self, workspace):
        record, evidence, campaign = workspace
        a_closed_run(record, evidence, "run-1")
        record.open_run(manifest("run-2"), recorded_at=CLOSED)
        with pytest.raises(RetentionError, match="while runs are unsealed"):
            campaign.seal(at="2026-09-11T12:00:00Z")

    def test_the_sweep_appends_run_abandoned_to_the_rest(self, workspace):
        record, evidence, _ = workspace
        a_closed_run(record, evidence, "run-1")
        record.open_run(manifest("run-2"), recorded_at=CLOSED)
        assert unsealed_runs(record) == ["run-2"]
        assert sweep(record, at="2026-09-11T12:00:00Z") == ["run-2"]
        assert unsealed_runs(record) == []

    def test_an_abandoned_run_acquires_an_expiry(self, workspace):
        # Without the sweep it would never acquire one and would live forever.
        record, _, campaign = workspace
        record.open_run(manifest("run-2"), recorded_at=CLOSED)
        sweep(record, at="2026-09-11T12:00:00Z")
        assert campaign.scheduled_expiry("run-2")

    def test_sealing_succeeds_once_everything_is_sealed(self, workspace):
        record, evidence, campaign = workspace
        a_closed_run(record, evidence, "run-1")
        sealed = campaign.seal(at="2026-09-11T12:00:00Z")
        assert sealed.run_count == 1
        assert sealed.latest_run_closed_at == CLOSED

    def test_sealing_twice_is_refused(self, workspace):
        record, evidence, campaign = workspace
        a_closed_run(record, evidence, "run-1")
        campaign.seal(at="2026-09-11T12:00:00Z")
        with pytest.raises(RetentionError, match="already sealed"):
            campaign.seal(at="2026-09-12T12:00:00Z")

    def test_a_run_closed_after_the_seal_moment_is_refused(self, workspace):
        # max(run_closed_at) <= campaign_sealed_at.
        record, evidence, campaign = workspace
        a_closed_run(record, evidence, "run-1", closed_at="2026-09-20T12:00:00Z")
        with pytest.raises(RetentionError, match="is after campaign_sealed_at"):
            campaign.seal(at="2026-09-11T12:00:00Z")

    def test_a_writer_is_refused_against_a_sealed_store(self, workspace):
        record, evidence, campaign = workspace
        a_closed_run(record, evidence, "run-1")
        campaign.seal(at="2026-09-11T12:00:00Z")
        with pytest.raises(AccessDenied, match="campaign is sealed"):
            evidence.for_driver("run-2")

    def test_the_redacted_tier_outlives_the_raw_tier(self, workspace):
        # Seal is refused while any run is unsealed, so this holds by ordering.
        record, evidence, campaign = workspace
        a_closed_run(record, evidence, "run-1")
        sealed = campaign.seal(at="2026-09-11T12:00:00Z")
        assert sealed.redacted_expiry_at > campaign.scheduled_expiry("run-1")


class TestWholeRunDeletion:
    def test_deletion_removes_the_whole_directory_including_temporaries(self, workspace):
        record, evidence, campaign = workspace
        a_closed_run(record, evidence, "run-1")
        assert (evidence.run_dir("run-1") / "tmp" / "scratch.txt").exists()
        campaign.expire_run("run-1", now=AFTER_EXPIRY)
        assert not evidence.run_dir("run-1").exists()

    def test_deletion_writes_a_content_free_receipt(self, workspace):
        record, evidence, campaign = workspace
        a_closed_run(record, evidence, "run-1")
        receipt = campaign.expire_run("run-1", now=AFTER_EXPIRY)
        assert receipt.run_id == "run-1"
        assert receipt.retention_profile == "mvp-synthetic-v1"
        assert receipt.result == "deleted"
        assert len(receipt.evidence_manifest_hash) == 64

    def test_the_receipt_carries_no_content(self, workspace):
        record, evidence, campaign = workspace
        a_closed_run(record, evidence, "run-1")
        receipt = campaign.expire_run("run-1", now=AFTER_EXPIRY)
        serialised = receipt.model_dump_json()
        assert "answer" not in serialised and "temporary copy" not in serialised
        assert set(receipt.model_dump()) == {
            "run_id",
            "evidence_manifest_hash",
            "retention_profile",
            "scheduled_expiry_at",
            "deleted_at",
            "result",
        }

    def test_deletion_does_not_touch_the_run_chain(self, workspace):
        # A receipt is never written into a run's hash chain, so no act of
        # retention can alter a seal.
        record, evidence, campaign = workspace
        a_closed_run(record, evidence, "run-1")
        before = record.seal("run-1")
        campaign.expire_run("run-1", now=AFTER_EXPIRY)
        assert record.verify_run("run-1") == before

    def test_the_receipt_goes_to_a_separate_append_only_manifest(self, workspace):
        record, evidence, campaign = workspace
        a_closed_run(record, evidence, "run-1")
        a_closed_run(record, evidence, "run-2")
        campaign.expire_run("run-1", now=AFTER_EXPIRY)
        campaign.expire_run("run-2", now=AFTER_EXPIRY)
        assert [r.run_id for r in campaign.receipts()] == ["run-1", "run-2"]

    def test_early_deletion_is_refused(self, workspace):
        # There is no ad hoc per-run extension, and no early deletion either.
        record, evidence, campaign = workspace
        a_closed_run(record, evidence, "run-1")
        with pytest.raises(RetentionError, match="no per-run extension"):
            campaign.expire_run("run-1", now="2026-09-11T12:00:00Z")

    def test_expiry_is_sixty_days_from_run_closed_at(self, workspace):
        record, evidence, campaign = workspace
        a_closed_run(record, evidence, "run-1")
        assert RAW_EVIDENCE_DAYS == 60
        assert campaign.scheduled_expiry("run-1").startswith("2026-11-09")

    def test_an_unsealed_run_has_no_expiry(self, workspace):
        record, _, campaign = workspace
        record.open_run(manifest("run-2"), recorded_at=CLOSED)
        with pytest.raises(RetentionError, match="no run_closed_at"):
            campaign.scheduled_expiry("run-2")


class TestToolSuppressionAccuracy:
    def suppression(self, kind="cache-hit", reused="result") -> Suppression:
        return Suppression(
            run_id="r", step_id="s1", tool="search", kind=kind, reused_result=reused
        )

    def test_a_matching_re_execution_confirms_the_suppression(self):
        measured = measure_suppression_accuracy(
            [self.suppression()], re_execute=lambda s: "result"
        )
        assert measured.confirmed_correct == 1
        assert measured.accuracy == 1.0

    def test_a_differing_re_execution_marks_it_incorrect(self):
        measured = measure_suppression_accuracy(
            [self.suppression()], re_execute=lambda s: "different"
        )
        assert measured.confirmed_incorrect == 1
        assert measured.accuracy == 0.0

    def test_a_suppression_that_cannot_be_checked_is_unverified(self):
        # Never assumed correct.
        measured = measure_suppression_accuracy([self.suppression()])
        assert measured.unverified == 1
        assert measured.accuracy == 0.0

    def test_a_tool_that_raises_is_unverified_not_correct(self):
        def explode(_: Suppression) -> str:
            raise RuntimeError("tool is gone")

        measured = measure_suppression_accuracy([self.suppression()], re_execute=explode)
        assert measured.unverified == 1

    def test_an_optional_denial_is_correct_when_the_verdict_is_unchanged(self):
        measured = measure_suppression_accuracy(
            [self.suppression(kind="optional-satisfied")],
            counterfactual_verdict=lambda s: "pass",
            observed_verdict="pass",
        )
        assert measured.confirmed_correct == 1

    def test_an_optional_denial_that_would_have_changed_the_verdict_is_incorrect(self):
        measured = measure_suppression_accuracy(
            [self.suppression(kind="optional-satisfied")],
            counterfactual_verdict=lambda s: "fail",
            observed_verdict="pass",
        )
        assert measured.confirmed_incorrect == 1

    def test_error_rate_is_one_minus_accuracy_from_the_same_measurement(self):
        # They are one measurement in two directions and never computed apart.
        measured = measure_suppression_accuracy(
            [self.suppression(), self.suppression(reused="stale")],
            re_execute=lambda s: "result",
        )
        assert measured.accuracy == 0.5
        assert measured.error_rate == 0.5
        assert measured.accuracy + measured.error_rate == 1.0

    def test_the_counts_must_cover_every_suppression(self):
        from outcomefuse.evidence import SuppressionAccuracy

        with pytest.raises(ValidationError, match="outcomes cover"):
            SuppressionAccuracy(
                suppressed=5, confirmed_correct=1, confirmed_incorrect=1, unverified=1
            )


class TestCompressionFidelity:
    def test_every_fact_surviving_is_full_fidelity(self):
        measured = measure_compression_fidelity(
            ["doc-001", "17046", "SP-4.2"], "cites doc-001, 17046 under SP-4.2"
        )
        assert measured.fidelity == 1.0 and measured.intact

    def test_a_dropped_fact_is_named(self):
        # FR38 forbids dropping an attributable fact, so this must not merely
        # lower a score - it must fail.
        measured = measure_compression_fidelity(
            ["doc-001", "17046"], "cites doc-001 only"
        )
        assert measured.lost == ("17046",)
        assert not measured.intact

    def test_no_facts_is_trivially_intact(self):
        assert measure_compression_fidelity([], "anything").intact


class TestMarginalValueDenialReporting:
    def denial(self, **over) -> MarginalValueDenial:
        base = {
            "run_id": "r",
            "step_id": "s1",
            "unmet_mandatory_at_decision": ("result-matches-key",),
            "advances_criteria": ("something-optional",),
            "estimated_benefit": 0.1,
            "estimated_cost": 50.0,
            "policy_action": "deny",
        }
        return MarginalValueDenial(**(base | over))

    def test_a_denial_that_did_not_touch_the_floor_is_a_saving(self):
        report = DenialReport(denials=(self.denial(),))
        assert report.savings and not report.violations
        assert report.estimated_saving == 50.0

    def test_a_denial_that_blocked_the_floor_is_a_violation(self):
        report = DenialReport(
            denials=(self.denial(advances_criteria=("result-matches-key",)),)
        )
        assert report.violations and not report.savings

    def test_a_violation_is_never_counted_as_a_saving(self):
        # The specific dishonesty FR99 exists to prevent.
        report = DenialReport(
            denials=(self.denial(advances_criteria=("result-matches-key",)),)
        )
        assert report.estimated_saving == 0.0

    def test_the_report_keeps_both_kinds(self):
        report = DenialReport(
            denials=(
                self.denial(),
                self.denial(step_id="s2", advances_criteria=("result-matches-key",)),
            )
        )
        assert len(report.savings) == 1 and len(report.violations) == 1


class TestBlindReview:
    def test_the_rate_is_rejections_over_reviews(self):
        review = BlindReview(reviewed=30, rejected=3, sample_size=30)
        assert review.false_sufficiency_rate == 0.1

    def test_a_partial_sample_cannot_establish_the_rate(self):
        with pytest.raises(ValidationError, match="partial sample"):
            BlindReview(reviewed=10, rejected=1, sample_size=30)

    def test_more_rejections_than_reviews_is_refused(self):
        with pytest.raises(ValidationError, match="more rejections"):
            BlindReview(reviewed=5, rejected=9, sample_size=5)
