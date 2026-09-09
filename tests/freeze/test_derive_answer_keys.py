"""Tests for the answer-key deriver.

These scripts decide whether all 80 answer keys are correct, across four
workload branches, and E1b freezes whatever they produce. A bug here corrupts
every workload at once and cannot be corrected afterwards — only absorbed.

The most valuable test in the file is the staleness check at the bottom: it
catches a corpus edited without regenerating its keys, which is silent, easy,
and permanent once frozen.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest
import yaml

from derive_answer_keys import (
    SPLITS,
    WORKLOADS,
    context_for,
    derive,
    locate_anchor,
    select_document,
)

ROOT = Path(__file__).resolve().parent.parent.parent


def doc(doc_id, region, effective_from, *, topic="t", status="active", supersedes=None, value=1):
    return {
        "doc_id": doc_id,
        "topic": topic,
        "region": region,
        "status": status,
        "effective_from": effective_from,
        "supersedes": supersedes,
        "control_unit": "days",
        "control_value": value,
    }


class TestSelectDocument:
    def test_region_beats_global_even_when_older(self):
        docs = [doc("g", "global", "2026-01-01"), doc("r", "emea", "2025-01-01")]
        assert select_document(docs, "t", "emea", "2026-06-01")["doc_id"] == "r"

    def test_falls_back_to_global_when_region_has_nothing(self):
        docs = [doc("g", "global", "2025-01-01"), doc("r", "apac", "2025-01-01")]
        assert select_document(docs, "t", "emea", "2026-06-01")["doc_id"] == "g"

    def test_draft_has_no_force(self):
        docs = [doc("g", "global", "2025-01-01"), doc("d", "emea", "2025-06-01", status="draft")]
        assert select_document(docs, "t", "emea", "2026-06-01")["doc_id"] == "g"

    def test_nothing_applies_before_its_effective_date(self):
        docs = [doc("g", "global", "2025-01-01"), doc("f", "emea", "2026-12-01")]
        assert select_document(docs, "t", "emea", "2026-06-01")["doc_id"] == "g"

    def test_superseded_document_is_retired(self):
        docs = [
            doc("old", "emea", "2025-01-01"),
            doc("new", "emea", "2026-01-01", supersedes="old"),
        ]
        assert select_document(docs, "t", "emea", "2026-06-01")["doc_id"] == "new"

    def test_a_future_successor_does_not_retire_its_predecessor_early(self):
        # The interaction the rule's step order exists to protect.
        docs = [
            doc("old", "emea", "2025-01-01"),
            doc("new", "emea", "2026-12-01", supersedes="old"),
        ]
        assert select_document(docs, "t", "emea", "2026-06-01")["doc_id"] == "old"

    def test_latest_wins_with_doc_id_tie_break(self):
        docs = [doc("b", "emea", "2025-01-01"), doc("a", "emea", "2025-01-01")]
        assert select_document(docs, "t", "emea", "2026-06-01")["doc_id"] == "b"

    def test_topic_must_match(self):
        docs = [doc("g", "global", "2025-01-01", topic="other")]
        assert select_document(docs, "t", "emea", "2026-06-01") is None

    def test_returns_none_when_nothing_is_in_force(self):
        docs = [doc("g", "global", "2026-12-01")]
        assert select_document(docs, "t", "emea", "2026-06-01") is None

    @pytest.mark.parametrize(
        ("step", "docs", "expected"),
        [
            ("draft-exclusion", [doc("g", "global", "2025-01-01"),
                                 doc("d", "emea", "2025-06-01", status="draft")], "d"),
            ("effective-dating", [doc("g", "global", "2025-01-01"),
                                  doc("f", "emea", "2026-12-01")], "f"),
            ("supersession", [doc("old", "emea", "2026-06-01"),
                              doc("new", "emea", "2025-01-01", supersedes="old")], "old"),
            ("region-precedence", [doc("g", "global", "2026-01-01"),
                                   doc("r", "emea", "2025-01-01")], "g"),
        ],
    )
    def test_each_skip_disables_exactly_its_own_step(self, step, docs, expected):
        # Distractor discrimination rests entirely on skip doing what it claims.
        assert select_document(docs, "t", "emea", "2026-06-01", skip=step)["doc_id"] == expected


class TestLocateAnchor:
    def test_computes_the_span_around_the_anchor(self, tmp_path):
        (tmp_path / "m.py").write_text("a\nb\nTARGET\nd\ne\n", encoding="utf-8")
        assert locate_anchor(tmp_path, "c-1", {
            "file": "m.py", "anchor": "TARGET", "span_before": 1, "span_after": 2}) == (2, 5)

    def test_matches_on_stripped_content_so_indentation_is_irrelevant(self, tmp_path):
        (tmp_path / "m.py").write_text("x\n        TARGET\n", encoding="utf-8")
        assert locate_anchor(tmp_path, "c-1", {
            "file": "m.py", "anchor": "TARGET", "span_before": 0, "span_after": 0}) == (2, 2)

    def test_span_is_clamped_to_the_file(self, tmp_path):
        (tmp_path / "m.py").write_text("TARGET\n", encoding="utf-8")
        assert locate_anchor(tmp_path, "c-1", {
            "file": "m.py", "anchor": "TARGET", "span_before": 9, "span_after": 9}) == (1, 1)

    def test_an_ambiguous_anchor_fails_loudly(self, tmp_path):
        (tmp_path / "m.py").write_text("TARGET\nTARGET\n", encoding="utf-8")
        with pytest.raises(SystemExit, match="matched 2"):
            locate_anchor(tmp_path, "c-1", {
                "file": "m.py", "anchor": "TARGET", "span_before": 0, "span_after": 0})

    def test_a_missing_anchor_fails_loudly(self, tmp_path):
        (tmp_path / "m.py").write_text("nothing here\n", encoding="utf-8")
        with pytest.raises(SystemExit, match="matched 0"):
            locate_anchor(tmp_path, "c-1", {
                "file": "m.py", "anchor": "TARGET", "span_before": 0, "span_after": 0})

    def test_a_missing_file_fails_loudly(self, tmp_path):
        with pytest.raises(SystemExit, match="no file"):
            locate_anchor(tmp_path, "c-1", {
                "file": "absent.py", "anchor": "T", "span_before": 0, "span_after": 0})


class TestUnanswerableCases:
    def test_partial_cases_carry_their_unmet_criteria(self):
        case = {"case_id": "x-1", "expected_outcome": "partial", "unmet_criteria": ["a", "b"]}
        assert derive("data-sql", case, None) == {
            "expected_outcome": "partial", "unmet_criteria": ["a", "b"]}

    def test_an_unanswerable_case_may_not_carry_reference_material(self):
        case = {"case_id": "x-1", "expected_outcome": "partial",
                "unmet_criteria": ["a"], "reference": {"po_id": 1}}
        with pytest.raises(SystemExit, match="must not carry reference"):
            derive("data-sql", case, None)


class TestDataSqlDerivation:
    def test_cents_convert_exactly_without_float_drift(self):
        db = context_for("data-sql", "cases/corpora/data-sql/v1")
        case = {
            "case_id": "x-1", "expected_outcome": "answer", "units": "usd",
            "reference": {
                "value_sql": "SELECT 1704600", "value_is_cents": True,
                "rows_sql": "SELECT 17"},
        }
        key = derive("data-sql", case, db)
        assert key["result_value_cents"] == 1704600
        assert Decimal(str(key["result_value"])) == Decimal("17046")
        assert key["row_count"] == 17

    def test_a_null_result_means_the_case_is_not_answerable(self):
        db = context_for("data-sql", "cases/corpora/data-sql/v1")
        case = {
            "case_id": "x-1", "expected_outcome": "answer", "units": "count",
            "reference": {
                "value_sql": "SELECT NULL", "value_is_cents": False,
                "rows_sql": "SELECT 1"},
        }
        with pytest.raises(SystemExit, match="unanswerable"):
            derive("data-sql", case, db)

    def test_zero_contributing_rows_is_refused(self):
        db = context_for("data-sql", "cases/corpora/data-sql/v1")
        case = {
            "case_id": "x-1", "expected_outcome": "answer", "units": "count",
            "reference": {
                "value_sql": "SELECT 5", "value_is_cents": False, "rows_sql": "SELECT 0"},
        }
        with pytest.raises(SystemExit, match="zero contributing rows"):
            derive("data-sql", case, db)

    def test_reference_sql_returning_more_than_a_scalar_is_refused(self):
        db = context_for("data-sql", "cases/corpora/data-sql/v1")
        case = {
            "case_id": "x-1", "expected_outcome": "answer", "units": "count",
            "reference": {
                "value_sql": "SELECT 1, 2", "value_is_cents": False, "rows_sql": "SELECT 1"},
        }
        with pytest.raises(SystemExit, match="exactly one scalar"):
            derive("data-sql", case, db)


class TestSupplyChainDerivation:
    def test_a_clean_purchase_order_cannot_be_an_answerable_case(self):
        ctx = context_for("supply-chain", "cases/corpora/supply-chain/v1")
        case = {"case_id": "x-1", "expected_outcome": "answer", "reference": {"po_id": 5009}}
        with pytest.raises(SystemExit, match="classifies to nothing"):
            derive("supply-chain", case, ctx)

    def test_classification_returns_exactly_one_row_per_order(self):
        db, classification = context_for("supply-chain", "cases/corpora/supply-chain/v1")
        for (po,) in db.execute("SELECT po_id FROM purchase_orders").fetchall():
            assert len(db.execute(classification, {"po_id": po}).fetchall()) == 1


@pytest.mark.parametrize("workload", WORKLOADS)
@pytest.mark.parametrize("split", SPLITS)
def test_committed_answer_keys_are_not_stale(workload, split):
    """Regenerating must reproduce what is on disk, byte for byte.

    A corpus edited without regenerating its keys is silent, easy, and
    permanent once frozen. This is the check that catches it.
    """
    folder = ROOT / "cases" / split / workload
    doc_ = yaml.safe_load((folder / "cases.yaml").read_text(encoding="utf-8"))
    committed = yaml.safe_load((folder / "answer-keys.yaml").read_text(encoding="utf-8"))

    context = context_for(workload, doc_["corpus_ref"])
    fresh = {case["case_id"]: derive(workload, case, context) for case in doc_["cases"]}

    assert fresh == committed, (
        f"{workload}/{split} answer keys are stale — "
        "run freeze/derive_answer_keys.py and commit the result"
    )
