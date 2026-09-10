"""The record spine (AD-2, AD-16, AD-19).

BUILD-ORDER states five acceptance criteria for E2. Each has a test class named
after it, because an epic that says "done when" deserves to be checked against
that sentence rather than against a plausible paraphrase:

  1. a synthetic event stream folds to the same run state twice
  2. a mutated row breaks its run's chain detectably
  3. opening against a library below 3.51.3 is refused
  4. a second process opening a writer on the same file is refused, not blocked
  5. two concurrent runs on one database produce two independently valid chains
"""

from __future__ import annotations

import sqlite3
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest
from pydantic import ValidationError

from outcomefuse.core.record import (
    MIN_SQLITE,
    ChainBroken,
    Event,
    LedgerState,
    RecordStore,
    RunManifest,
    StoreError,
    check_order,
    family_of,
    fold,
    open_store,
    reason_registry_digest,
    replay_equivalent,
)

SHA = "c" * 64
WHEN = "2026-09-10T12:00:00Z"


def manifest(run_id: str = "run-1", **over) -> RunManifest:
    base = {
        "run_id": run_id,
        "mode": "governed",
        "data_class": "synthetic",
        "retention_profile": "mvp-synthetic-v1",
        "contract_hash": SHA,
        "rubric_hash": SHA,
        "answer_key_hash": SHA,
        "verifier_registry_version": "v1",
        "verifier_registry_hash": SHA,
        "coverage_report_hash": SHA,
        "baseline_configuration_hash": SHA,
        "case_set_id": "calibration/data-sql",
        "split": "calibration",
        "model_ids": ("gpt-4o",),
        "provider_versions": {"gpt-4o": "2026-05-01"},
        "cost_table_version": "ct-1",
        "route": "direct",
        "streaming_disabled": True,
        "adapter_id": "synthetic",
        "adapter_version": "1",
        "governor_code_version": "0.1.0",
        "sqlite_library_version": sqlite3.sqlite_version,
        "seed": 7,
    }
    return RunManifest(**(base | over))


def event(run_id: str, seq: int, kind: str, **over) -> Event:
    return Event(run_id=run_id, seq=seq, kind=kind, recorded_at=WHEN, **over)


def a_full_run(store: RecordStore, run_id: str) -> None:
    store.open_run(manifest(run_id), recorded_at=WHEN)
    ledger = LedgerState(
        allocated_tokens=1000,
        spent_tokens=120,
        reserved_tokens=0,
        allocated_cost=1.0,
        spent_cost=0.12,
        reserved_cost=0.0,
    )
    store.append(event(run_id, 1, "decision-proposed", step_id="s1"))
    store.append(event(run_id, 2, "budget-reserved", step_id="s1"))
    store.append(
        event(
            run_id,
            3,
            "decision-recorded",
            step_id="s1",
            policy_action="proceed",
            decision_reason="justified",
            ledger=ledger,
            model_used="gpt-4o",
            tokens_consumed=120,
        )
    )
    store.append(event(run_id, 4, "verdict-applied", step_id="s1"))
    store.append(event(run_id, 5, "outcome-observed", step_id="s1"))
    store.append(event(run_id, 6, "spend-settled", step_id="s1"))
    store.append(
        event(
            run_id,
            7,
            "gate-verdict",
            gate_verdict="pass",
            verification_mode="reference-backed",
        )
    )
    store.append(
        event(run_id, 8, "run-closed", terminal_reason="stop-sufficient")
    )


@pytest.fixture
def store(tmp_path: Path):
    with open_store(tmp_path / "workspace.db") as opened:
        yield opened


class TestFoldsToTheSameStateTwice:
    def test_folding_the_same_stream_twice_gives_the_same_state(self, store):
        a_full_run(store, "run-1")
        events = store.events("run-1")
        assert fold(events) == fold(events)

    def test_state_is_derived_not_stored(self, store):
        a_full_run(store, "run-1")
        state = fold(store.events("run-1"))
        assert state.iterations == 1
        assert state.decisions == ("proceed",)
        assert state.reasons == ("justified",)
        assert state.quality_state == "pass"
        assert state.terminal_reason == "stop-sufficient"
        assert state.tokens_spent == 120
        assert state.sealed

    def test_a_run_must_begin_with_its_manifest(self):
        with pytest.raises(Exception, match="must be its manifest"):
            fold([event("run-1", 0, "decision-proposed")])

    def test_a_run_with_no_events_has_no_state(self):
        with pytest.raises(ValueError, match="no events"):
            fold([])

    def test_replay_equivalence_ignores_model_output(self, store):
        a_full_run(store, "run-1")
        first = fold(store.events("run-1"))
        # Same decisions, reasons, terminal reason and totals; different prose.
        second = first.model_copy(update={"gate_verdicts": ("pass", "pass")})
        assert replay_equivalent(first, second) == []

    def test_replay_equivalence_reports_a_different_decision_sequence(self, store):
        a_full_run(store, "run-1")
        first = fold(store.events("run-1"))
        second = first.model_copy(update={"decisions": ("deny",)})
        assert any("decision sequence" in d for d in replay_equivalent(first, second))


class TestAMutatedRowBreaksTheChain:
    def test_an_intact_run_verifies_and_returns_its_seal(self, store):
        a_full_run(store, "run-1")
        assert store.verify_run("run-1") == store.seal("run-1")

    def test_editing_a_row_body_is_detected(self, store):
        a_full_run(store, "run-1")
        # Reach past the writer to simulate someone editing the file.
        raw = sqlite3.connect(store.path)
        raw.execute("DROP TRIGGER events_no_update")
        raw.execute(
            "UPDATE events SET body = replace(body, 'proceed', 'deny') "
            "WHERE run_id='run-1' AND seq=3"
        )
        raw.commit()
        raw.close()
        with pytest.raises(ChainBroken, match="seq 3"):
            store.verify_run("run-1")

    def test_deleting_a_row_is_detected(self, store):
        a_full_run(store, "run-1")
        raw = sqlite3.connect(store.path)
        raw.execute("DROP TRIGGER events_no_delete")
        raw.execute("DELETE FROM events WHERE run_id='run-1' AND seq=4")
        raw.commit()
        raw.close()
        with pytest.raises(ChainBroken):
            store.verify_run("run-1")

    def test_the_writer_refuses_to_update(self, store):
        a_full_run(store, "run-1")
        with pytest.raises(sqlite3.DatabaseError, match="append-only"):
            store.db.execute("UPDATE events SET kind='x' WHERE run_id='run-1'")

    def test_the_writer_refuses_to_delete(self, store):
        a_full_run(store, "run-1")
        with pytest.raises(sqlite3.DatabaseError, match="append-only"):
            store.db.execute("DELETE FROM events WHERE run_id='run-1'")

    def test_nothing_may_follow_a_seal(self, store):
        a_full_run(store, "run-1")
        with pytest.raises(StoreError, match="sealed"):
            store.append(event("run-1", 9, "decision-proposed"))

    def test_a_gap_in_the_sequence_is_refused(self, store):
        store.open_run(manifest("run-1"), recorded_at=WHEN)
        with pytest.raises(StoreError, match="expected seq 1"):
            store.append(event("run-1", 5, "decision-proposed"))

    def test_terminal_reason_is_recorded_at_most_once(self, store):
        store.open_run(manifest("run-1"), recorded_at=WHEN)
        store.append(
            event(
                "run-1",
                1,
                "decision-recorded",
                policy_action="terminate",
                decision_reason="exhaustion",
                terminal_reason="halt-exhausted",
            )
        )
        with pytest.raises(sqlite3.IntegrityError):
            store.append(
                event("run-1", 2, "run-closed", terminal_reason="stop-sufficient")
            )

    def test_a_run_is_unsealed_until_a_terminal_event(self, store):
        store.open_run(manifest("run-1"), recorded_at=WHEN)
        assert store.seal("run-1") is None
        store.append(event("run-1", 1, "run-abandoned", terminal_reason="fail-closed"))
        assert store.seal("run-1") is not None


class TestAnOldLibraryIsRefused:
    def test_the_minimum_is_the_version_the_wal_bug_was_fixed_in(self):
        assert MIN_SQLITE == (3, 51, 3)

    def test_opening_below_the_minimum_is_refused(self, tmp_path, monkeypatch):
        monkeypatch.setattr(sqlite3, "sqlite_version_info", (3, 51, 2))
        monkeypatch.setattr(sqlite3, "sqlite_version", "3.51.2")
        with pytest.raises(StoreError, match=r"below 3\.51\.3"):
            open_store(tmp_path / "w.db")

    def test_the_running_library_satisfies_the_minimum(self):
        # If this fails the toolchain regressed; see .python-version.
        assert sqlite3.sqlite_version_info >= MIN_SQLITE

    def test_a_unc_path_is_refused(self, tmp_path):
        with pytest.raises(StoreError, match=r"UNC"):
            open_store(r"\\server\share\workspace.db")


class TestASecondWriterIsRefusedNotBlocked:
    def test_a_second_writer_in_this_process_is_refused(self, tmp_path):
        path = tmp_path / "w.db"
        with open_store(path):
            with pytest.raises(StoreError, match="refused rather than retried"):
                open_store(path)

    def test_a_second_writer_in_another_process_is_refused(self, tmp_path):
        """An in-process lock is void once the harness forks per case."""
        path = tmp_path / "w.db"
        script = textwrap.dedent(
            f"""
            import sys
            sys.path.insert(0, {str(Path(__file__).resolve().parents[3] / "src")!r})
            from outcomefuse.core.record import open_store, StoreError
            try:
                open_store({str(path)!r})
            except StoreError:
                print("REFUSED")
            else:
                print("ADMITTED")
            """
        )
        with open_store(path):
            result = subprocess.run(
                [sys.executable, "-c", script],
                capture_output=True,
                text=True,
                timeout=60,
                check=False,
            )
        assert "REFUSED" in result.stdout, result.stderr

    def test_the_lock_is_released_when_the_store_closes(self, tmp_path):
        path = tmp_path / "w.db"
        open_store(path).close()
        open_store(path).close()

    def test_a_reader_does_not_take_the_writer_lock(self, tmp_path):
        path = tmp_path / "w.db"
        with open_store(path) as writer:
            a_full_run(writer, "run-1")
            with open_store(path, writer=False) as reader:
                assert reader.verify_run("run-1") == writer.seal("run-1")


class TestConcurrentRunsProduceIndependentChains:
    def test_interleaved_runs_each_verify(self, store):
        store.open_run(manifest("run-a"), recorded_at=WHEN)
        store.open_run(manifest("run-b"), recorded_at=WHEN)
        for seq in range(1, 5):
            store.append(event("run-a", seq, "decision-proposed", step_id=f"a{seq}"))
            store.append(event("run-b", seq, "decision-proposed", step_id=f"b{seq}"))
        store.append(event("run-a", 5, "run-closed", terminal_reason="stop-sufficient"))
        store.append(event("run-b", 5, "run-closed", terminal_reason="halt-exhausted"))

        assert store.verify_run("run-a")
        assert store.verify_run("run-b")
        assert store.seal("run-a") != store.seal("run-b")

    def test_breaking_one_run_leaves_the_other_valid(self, store):
        a_full_run(store, "run-a")
        a_full_run(store, "run-b")
        raw = sqlite3.connect(store.path)
        raw.execute("DROP TRIGGER events_no_update")
        raw.execute("UPDATE events SET body=replace(body,'s1','s9') WHERE run_id='run-a' AND seq=1")
        raw.commit()
        raw.close()

        with pytest.raises(ChainBroken):
            store.verify_run("run-a")
        assert store.verify_run("run-b")  # independent chain, unaffected

    def test_one_database_holds_many_runs(self, store):
        for name in ("run-a", "run-b", "run-c"):
            a_full_run(store, name)
        assert store.run_ids() == ["run-a", "run-b", "run-c"]

    def test_a_run_id_cannot_be_opened_twice(self, store):
        store.open_run(manifest("run-a"), recorded_at=WHEN)
        with pytest.raises(StoreError, match="already exists"):
            store.open_run(manifest("run-a"), recorded_at=WHEN)


class TestManifestDiscipline:
    def test_a_non_synthetic_run_is_refused(self):
        # FR109: refuse persistence rather than applying the MVP profile to
        # data it was never approved for.
        with pytest.raises(ValidationError, match="governance profile"):
            manifest(data_class="non-synthetic")

    def test_there_is_no_default_data_class(self):
        assert "data_class" not in RunManifest.model_fields or (
            RunManifest.model_fields["data_class"].is_required()
        )

    def test_streaming_must_be_disabled(self):
        with pytest.raises(ValidationError, match="streaming"):
            manifest(streaming_disabled=False)

    def test_an_evaluation_run_must_carry_the_preregistration_hash(self):
        with pytest.raises(ValidationError, match="preregistration"):
            manifest(split="evaluation")

    def test_an_evaluation_run_with_preregistration_is_accepted(self):
        assert manifest(split="evaluation", preregistration_hash=SHA).split == "evaluation"

    def test_a_model_without_a_provider_version_is_refused(self):
        with pytest.raises(ValidationError, match="provider version"):
            manifest(model_ids=("gpt-4o", "gpt-5"))

    def test_an_unknown_field_is_refused(self):
        with pytest.raises(ValidationError):
            manifest(sneaky=True)

    def test_the_manifest_is_the_genesis_row(self, store):
        store.open_run(manifest("run-1"), recorded_at=WHEN)
        first = store.events("run-1")[0]
        assert first.kind == "run-manifest" and first.seq == 0

    def test_the_sqlite_library_version_is_recorded(self, store):
        store.open_run(manifest("run-1"), recorded_at=WHEN)
        body = store.events("run-1")[0].payload["manifest"]
        assert body["sqlite_library_version"] == sqlite3.sqlite_version


class TestEventDiscipline:
    def test_a_gate_verdict_must_carry_its_verification_mode(self):
        # FR21: the qualifier travels with the verdict rather than being
        # reconstructed later.
        with pytest.raises(ValidationError, match="verification mode"):
            event("run-1", 1, "gate-verdict", gate_verdict="pass")

    def test_a_local_timestamp_is_refused(self):
        with pytest.raises(ValidationError, match="RFC 3339"):
            Event(run_id="r", seq=0, kind="run-manifest", recorded_at="2026-09-10 12:00:00")

    def test_a_terminal_reason_may_not_ride_on_an_arbitrary_event(self):
        with pytest.raises(ValidationError, match="may not appear"):
            event("run-1", 1, "budget-reserved", terminal_reason="fail-closed")

    def test_events_are_frozen(self):
        recorded = event("run-1", 1, "decision-proposed")
        with pytest.raises(ValidationError):
            recorded.seq = 2

    def test_the_canonical_order_accepts_a_clean_decision(self, store):
        a_full_run(store, "run-1")
        assert check_order(store.events("run-1")) == []

    def test_the_canonical_order_reports_a_swap(self, store):
        store.open_run(manifest("run-1"), recorded_at=WHEN)
        store.append(event("run-1", 1, "budget-reserved"))
        store.append(event("run-1", 2, "decision-proposed"))
        assert check_order(store.events("run-1"))

    def test_an_evidence_cycle_is_permitted_in_place(self, store):
        store.open_run(manifest("run-1"), recorded_at=WHEN)
        store.append(event("run-1", 1, "decision-proposed"))
        store.append(event("run-1", 2, "evidence-requested"))
        store.append(event("run-1", 3, "evidence-observed"))
        store.append(event("run-1", 4, "budget-reserved"))
        assert check_order(store.events("run-1")) == []

    def test_observed_evidence_must_follow_a_request(self, store):
        store.open_run(manifest("run-1"), recorded_at=WHEN)
        store.append(event("run-1", 1, "decision-proposed"))
        store.append(event("run-1", 2, "evidence-observed"))
        assert any("must follow" in f for f in check_order(store.events("run-1")))


class TestReasonRegistry:
    def test_every_reason_declares_a_family(self):
        from outcomefuse.core.record import DECISION_REASONS

        for reason in DECISION_REASONS:
            assert family_of(reason)

    def test_an_unregistered_reason_has_no_family(self):
        with pytest.raises(KeyError):
            family_of("vibes")

    def test_the_registry_digest_is_stable(self):
        assert reason_registry_digest().sha256 == reason_registry_digest().sha256

    def test_families_do_not_overlap(self):
        from outcomefuse.core.record import REASON_FAMILIES

        seen: set[str] = set()
        for codes in REASON_FAMILIES.values():
            assert not (seen & codes), "a code appears in two families"
            seen |= codes
