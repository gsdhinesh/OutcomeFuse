"""The freeze record (FR65, FR64, AD-6).

E1b is the point of no return, so these tests guard two different things: that
the committed record still matches the artifacts it describes, and that the
enumerated file lists have not fallen behind the corpus. Explicit enumeration
is only safe if something catches a file nobody added to the list.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from freeze import (
    FREEZE_JSON,
    FREEZE_MD,
    SOURCE_GROUPS,
    SPLITS,
    WORKLOADS,
    build,
    readiness,
    render_markdown,
)
from outcomefuse.core.canon import ROUTE_FILE_DIGEST, ROUTE_STRUCTURE
from outcomefuse.core.contract import load_path
from outcomefuse.core.verify import REGISTRY

ROOT = Path(__file__).resolve().parent.parent.parent


@pytest.fixture(scope="module")
def record() -> dict:
    return build()


@pytest.fixture(scope="module")
def committed() -> dict:
    return json.loads(FREEZE_JSON.read_text(encoding="utf-8"))


class TestTheFreezeHolds:
    def test_the_committed_record_matches_the_artifacts(self, record, committed):
        assert record == committed, "FREEZE.json has drifted — see freeze/freeze.py"

    def test_the_human_readable_record_matches(self, record):
        assert FREEZE_MD.read_text(encoding="utf-8") == render_markdown(record)

    def test_the_freeze_is_reproducible(self):
        # A freeze that differed between two runs would trip FR65's drift refusal
        # on artifacts that never changed.
        assert build()["freeze_sha256"] == build()["freeze_sha256"]

    def test_the_record_carries_no_timestamp_or_environment(self, committed):
        serialised = json.dumps(committed)
        for leaked in ("frozen_at", "timestamp", "hostname", "platform", "user"):
            assert leaked not in serialised

    def test_the_seal_covers_every_part(self, record):
        # Change any one artifact digest and the seal must move.
        from outcomefuse.core.canon import hash_structure

        tampered = {k: v for k, v in record.items() if k != "freeze_sha256"}
        tampered["verifier_registry"] = dict(tampered["verifier_registry"]) | {"sha256": "0" * 64}
        assert hash_structure(tampered).sha256 != record["freeze_sha256"]

    def test_readiness_passes_on_what_was_frozen(self):
        from coverage_report import load_all

        assert readiness(load_all()) == []


class TestRoutesAreDeclared:
    """AD-6: every hashed artifact declares its route; only two are admissible."""

    def test_every_contract_declares_the_structure_route(self, committed):
        for block in committed["contracts"].values():
            assert block["route"] == ROUTE_STRUCTURE

    def test_every_case_set_declares_the_structure_route(self, committed):
        for block in committed["case_sets"].values():
            assert block["route"] == ROUTE_STRUCTURE

    def test_every_source_group_declares_the_file_digest_route(self, committed):
        for block in committed["source"].values():
            assert block["route"] == ROUTE_FILE_DIGEST

    def test_no_third_route_appears(self, committed):
        routes = {b["route"] for b in committed["contracts"].values()}
        routes |= {b["route"] for b in committed["case_sets"].values()}
        routes |= {b["route"] for b in committed["source"].values()}
        routes.add(committed["verifier_registry"]["route"])
        assert routes == {ROUTE_STRUCTURE, ROUTE_FILE_DIGEST}


class TestNothingWasLeftOut:
    def test_every_corpus_file_on_disk_is_frozen(self):
        """The check that makes explicit enumeration safe."""
        listed = {p for p in SOURCE_GROUPS["corpora"]}
        on_disk = {
            f.relative_to(ROOT).as_posix()
            for f in (ROOT / "cases" / "corpora").rglob("*")
            if f.is_file() and "__pycache__" not in f.parts
        }
        assert on_disk == listed, f"corpus files not frozen: {sorted(on_disk - listed)}"

    def test_every_baseline_prompt_on_disk_is_frozen(self):
        listed = set(SOURCE_GROUPS["baseline_definition"])
        on_disk = {
            f.relative_to(ROOT).as_posix()
            for f in (ROOT / "freeze" / "baseline-prompts").glob("*.md")
        }
        assert on_disk <= listed

    def test_every_verify_module_is_frozen(self):
        listed = set(SOURCE_GROUPS["verifier_registry_source"])
        on_disk = {
            f.relative_to(ROOT).as_posix()
            for f in (ROOT / "src" / "outcomefuse" / "core" / "verify").glob("*.py")
        }
        assert on_disk == listed

    def test_no_build_output_is_frozen(self):
        # .pyc is byte-exact, mtime-bearing and interpreter-specific: freezing one
        # would make the freeze irreproducible on any other machine.
        for paths in SOURCE_GROUPS.values():
            for path in paths:
                assert not path.endswith(".pyc")
                assert "__pycache__" not in path

    def test_all_eight_case_sets_are_frozen(self, committed):
        expected = {f"{s}/{w}" for s in SPLITS for w in WORKLOADS}
        assert set(committed["case_sets"]) == expected


class TestFR65Content:
    def test_the_registry_version_and_hash_are_recorded(self, committed):
        assert committed["verifier_registry"]["version"]
        assert len(committed["verifier_registry"]["sha256"]) == 64

    @pytest.mark.parametrize("workload", WORKLOADS)
    def test_counts_and_percentages_are_recorded(self, committed, workload):
        block = committed["coverage"][workload]
        total = block["mandatory_count"]
        assert (
            block["reference_backed_mandatory_count"]
            + block["constraint_backed_mandatory_count"]
            == total
        )
        assert block["reference_backed_percent"] + block["constraint_backed_percent"] == 100.0

    @pytest.mark.parametrize("workload", WORKLOADS)
    def test_every_mandatory_criterion_resolves_to_a_registered_verifier(self, workload):
        contract = load_path(ROOT / "contracts" / f"{workload}.contract.yaml")
        for criterion in contract.criteria.mandatory:
            assert criterion.verifier is not None
            assert criterion.verifier.type in REGISTRY

    @pytest.mark.parametrize("workload", WORKLOADS)
    def test_every_advisory_criterion_is_listed_with_a_reason(self, committed, workload):
        advisory = committed["coverage"][workload]["advisory"]
        assert advisory
        for entry in advisory:
            assert entry["non_gating_reason"].strip()

    @pytest.mark.parametrize("workload", WORKLOADS)
    def test_the_predominant_label_matches_the_counts(self, committed, workload):
        block = committed["coverage"][workload]
        expected = (
            block["constraint_backed_mandatory_count"]
            > block["reference_backed_mandatory_count"]
        )
        assert block["predominantly_constraint_backed"] == expected


class TestCaseSetAttestation:
    @pytest.mark.parametrize("split", SPLITS)
    @pytest.mark.parametrize("workload", WORKLOADS)
    def test_data_class_is_declared_with_no_default(self, committed, split, workload):
        # AD-9: a run whose class is absent is refused rather than assumed benign.
        assert committed["case_sets"][f"{split}/{workload}"]["data_class"] == "synthetic"

    @pytest.mark.parametrize("split", SPLITS)
    @pytest.mark.parametrize("workload", WORKLOADS)
    def test_the_frozen_case_count_matches_the_file(self, committed, split, workload):
        path = ROOT / "cases" / split / workload / "cases.yaml"
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert committed["case_sets"][f"{split}/{workload}"]["case_count"] == len(
            document["cases"]
        )

    def test_no_case_id_is_shared_between_the_two_splits(self):
        """A case in both sets would leak the sealed evaluation set into calibration."""
        seen: dict[str, str] = {}
        for split in SPLITS:
            for workload in WORKLOADS:
                path = ROOT / "cases" / split / workload / "cases.yaml"
                for case in yaml.safe_load(path.read_text(encoding="utf-8"))["cases"]:
                    assert case["case_id"] not in seen
                    seen[case["case_id"]] = split
