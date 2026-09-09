"""Tests for the case-set checker.

The checker is what stops a distractor claiming rigour it does not have. It
already caught two real defects during authoring — ds-e-007's trap returning
the correct answer either way, and dr-e-007's traps changing nothing — so its
own correctness is load-bearing.

Each workload has a different notion of a wrong reading, and each is tested
here for both directions: a genuine trap passes, a hollow one is reported.
"""

from __future__ import annotations

import pytest

from check_cases import (
    check_code_triage,
    check_data_sql,
    check_doc_research,
    check_supply_chain,
    context_for,
)


class TestDataSqlDistractors:
    def setup_method(self):
        self.db = context_for("data-sql", "cases/corpora/data-sql/v1")
        self.case = {
            "case_id": "x-1",
            "expected_outcome": "answer",
            "units": "count",
            "reference": {"value_sql": "SELECT 42"},
        }
        self.key = {"expected_outcome": "answer", "units": "count"}

    def test_a_discriminating_wrong_reading_passes(self):
        out = []
        self.case["distractors"] = [{"id": "d", "wrong_sql": "SELECT 41"}]
        check_data_sql(self.case, self.key, self.db, out)
        assert out == []

    def test_a_wrong_reading_that_returns_the_right_answer_is_reported(self):
        out = []
        self.case["distractors"] = [{"id": "d", "wrong_sql": "SELECT 42"}]
        check_data_sql(self.case, self.key, self.db, out)
        assert len(out) == 1 and "does not discriminate" in out[0]

    def test_a_distractor_with_neither_sql_nor_a_declaration_is_reported(self):
        out = []
        self.case["distractors"] = [{"id": "d", "detail": "hand-waving"}]
        check_data_sql(self.case, self.key, self.db, out)
        assert len(out) == 1 and "needs wrong_sql" in out[0]

    def test_an_explicitly_non_discriminating_distractor_is_accepted(self):
        out = []
        self.case["distractors"] = [{"id": "d", "discriminates": False, "detail": "why"}]
        check_data_sql(self.case, self.key, self.db, out)
        assert out == []

    def test_key_units_disagreeing_with_the_case_is_reported(self):
        out = []
        check_data_sql(self.case, {"expected_outcome": "answer", "units": "usd"}, self.db, out)
        assert any("units disagree" in m for m in out)


class TestCodeTriageDistractors:
    def setup_method(self):
        self.repo = context_for("code-triage", "cases/corpora/code-triage/v1")
        self.case = {
            "case_id": "x-1",
            "expected_outcome": "answer",
            "reference": {
                "file": "orderflow/cache.py",
                "anchor": "self._entries.pop(key)",
                "span_before": 0,
                "span_after": 0,
                "severity": "minor",
            },
        }

    def key(self, **over):
        base = {
            "expected_outcome": "answer",
            "root_cause_file": "orderflow/cache.py",
            "root_cause_line_min": 1,
            "root_cause_line_max": 999,
            "severity": "minor",
        }
        return base | over

    def test_a_declared_non_discriminating_distractor_passes(self):
        out = []
        self.case["distractors"] = [{"id": "d", "discriminates": False, "detail": "why"}]
        check_code_triage(self.case, self.key(), self.repo, out)
        assert out == []

    def test_a_distractor_claiming_to_discriminate_is_refused(self):
        # A wrong file or line has no executable form, so the claim cannot be proven.
        out = []
        self.case["distractors"] = [{"id": "d", "detail": "why"}]
        check_code_triage(self.case, self.key(), self.repo, out)
        assert len(out) == 1 and "no executable" in out[0]

    def test_a_non_discriminating_distractor_still_needs_a_reason(self):
        out = []
        self.case["distractors"] = [{"id": "d", "discriminates": False}]
        check_code_triage(self.case, self.key(), self.repo, out)
        assert len(out) == 1 and "needs a reason" in out[0]

    def test_a_span_that_does_not_contain_the_anchor_is_reported(self):
        out = []
        check_code_triage(
            self.case, self.key(root_cause_line_min=1, root_cause_line_max=2), self.repo, out)
        assert any("does not contain the anchor" in m for m in out)

    def test_a_severity_outside_the_controlled_set_is_reported(self):
        out = []
        check_code_triage(self.case, self.key(severity="catastrophic"), self.repo, out)
        assert any("outside the controlled set" in m for m in out)

    def test_an_ambiguous_anchor_is_reported_rather_than_raising(self):
        # `return True` occurs four times in validation.py, so the anchor cannot
        # identify a single line and the checker must say so rather than throw.
        out = []
        self.case["reference"]["file"] = "orderflow/validation.py"
        self.case["reference"]["anchor"] = "return True"
        check_code_triage(self.case, self.key(root_cause_file="orderflow/validation.py"),
                          self.repo, out)
        assert len(out) == 1 and "must match exactly 1" in out[0]

    def test_a_reference_file_absent_from_the_corpus_is_reported(self):
        out = []
        self.case["reference"]["file"] = "orderflow/nope.py"
        check_code_triage(self.case, self.key(root_cause_file="orderflow/nope.py"), self.repo, out)
        assert len(out) == 1 and "no file" in out[0]


class TestSupplyChainDistractors:
    def setup_method(self):
        self.ctx = context_for("supply-chain", "cases/corpora/supply-chain/v1")
        self.case = {"case_id": "x-1", "expected_outcome": "answer", "reference": {"po_id": 5004}}
        self.key = {
            "expected_outcome": "answer",
            "exception_type": "quality-hold",
            "root_cause_code": "rc-qc-defect",
            "recommended_action": "hold-for-quality",
        }

    def test_a_discriminating_wrong_value_passes(self):
        out = []
        self.case["distractors"] = [
            {"id": "d", "wrong_field": "exception_type", "wrong_sql": "SELECT 'late-shipment'"}]
        check_supply_chain(self.case, self.key, self.ctx, out)
        assert out == []

    def test_a_wrong_value_equal_to_the_derived_one_is_reported(self):
        out = []
        self.case["distractors"] = [
            {"id": "d", "wrong_field": "exception_type", "wrong_sql": "SELECT 'quality-hold'"}]
        check_supply_chain(self.case, self.key, self.ctx, out)
        assert len(out) == 1 and "does not discriminate" in out[0]

    def test_a_distractor_naming_an_unkeyed_field_is_reported(self):
        out = []
        self.case["distractors"] = [
            {"id": "d", "wrong_field": "impacted_orders", "wrong_sql": "SELECT 1"}]
        check_supply_chain(self.case, self.key, self.ctx, out)
        assert len(out) == 1 and "wrong_field" in out[0]


class TestDocResearchDistractors:
    def setup_method(self):
        self.docs = context_for("doc-research", "cases/corpora/doc-research/v1")
        # APAC retention: the draft is excluded, so the global standard governs.
        self.case = {
            "case_id": "x-1",
            "expected_outcome": "answer",
            "reference": {"topic": "data-retention", "region": "apac", "as_of": "2026-07-01"},
        }
        self.key = {"expected_outcome": "answer", "primary_source_id": "doc-001"}

    def test_a_step_that_changes_the_answer_passes(self):
        out = []
        self.case["distractors"] = [{"id": "d", "skip_step": "draft-exclusion"}]
        check_doc_research(self.case, self.key, self.docs, out)
        assert out == []

    def test_a_step_that_changes_nothing_is_reported(self):
        out = []
        self.case["distractors"] = [{"id": "d", "skip_step": "supersession"}]
        check_doc_research(self.case, self.key, self.docs, out)
        assert len(out) == 1 and "does not discriminate" in out[0]

    def test_an_unknown_rule_step_is_reported(self):
        out = []
        self.case["distractors"] = [{"id": "d", "skip_step": "vibes"}]
        check_doc_research(self.case, self.key, self.docs, out)
        assert len(out) == 1 and "needs skip_step" in out[0]


@pytest.mark.parametrize(
    "checker", [check_data_sql, check_code_triage, check_supply_chain, check_doc_research]
)
def test_no_checker_inspects_an_unanswerable_case(checker):
    out = []
    case = {"case_id": "x-1", "expected_outcome": "partial", "unmet_criteria": ["a"]}
    checker(case, {"expected_outcome": "partial"}, None, out)
    assert out == []
