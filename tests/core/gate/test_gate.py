"""The Quality Gate (FR19-FR26, FR94, FR98, FR105).

The gate is where E3's registry meets a running decision, so these tests use a
real frozen contract as well as synthetic ones — a gate that only works against
fixtures shaped to suit it is not evidence that it works.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from outcomefuse.core.contract import load_path, load_text
from outcomefuse.core.gate import (
    DEFAULT_CADENCE,
    STEP_CLASSES,
    AdvisorySignal,
    CadenceError,
    GateUnavailable,
    QualityGate,
    cadence_for,
    should_evaluate,
    should_evaluate_before_halt,
    validate_cadence,
)
from outcomefuse.core.verify import CitableEntry, CitableIndex

ROOT = Path(__file__).resolve().parent.parent.parent.parent
SHA = "d" * 64

MIXED = """
contract_id: ofc-mixed
version: 1
workload: testing
task_goal: A goal.
deliverable:
  structure:
    answer: string
    count: integer
    note: string
criteria:
  mandatory:
    - id: answer-matches-key
      classification: E
      verifier:
        type: exact-match-against-answer-key
        args: { path: $.answer, key: answer }
    - id: count-in-range
      classification: E
      verifier:
        type: numeric-range
        args: { path: $.count, min: 1, max: 10 }
  optional:
    - id: note-present
      classification: E
      verifier: { type: field-present, args: { path: $.note } }
  advisory:
    - id: is-it-any-good
      classification: A
budget:
  max_tokens: 1000
  max_estimated_cost: 0.1
  max_tool_calls: 5
  max_iterations: 3
tools:
  - name: search
    deterministic: true
    side_effecting: false
"""

ALL_REFERENCE = MIXED.replace(
    """    - id: count-in-range
      classification: E
      verifier:
        type: numeric-range
        args: { path: $.count, min: 1, max: 10 }
""",
    """    - id: count-matches-key
      classification: E
      verifier:
        type: exact-match-against-answer-key
        args: { path: $.count, key: count }
""",
)


@pytest.fixture
def gate() -> QualityGate:
    return QualityGate()


class TestVerdictIsBinary:
    def test_a_satisfied_deliverable_passes(self, gate):
        verdict = gate.evaluate(
            load_text(MIXED), {"answer": "x", "count": 5}, answer_key={"answer": "x"}
        )
        assert verdict.verdict == "pass" and verdict.passed

    def test_an_unsatisfied_deliverable_fails(self, gate):
        verdict = gate.evaluate(
            load_text(MIXED), {"answer": "wrong", "count": 5}, answer_key={"answer": "x"}
        )
        assert verdict.verdict == "fail"

    def test_there_is_no_third_verdict(self, gate):
        # FR94: a pass-with-concern state would have to resolve somewhere.
        verdict = gate.evaluate(
            load_text(MIXED), {"answer": "x", "count": 5}, answer_key={"answer": "x"}
        )
        assert verdict.verdict in {"pass", "fail"}

    def test_a_gate_that_cannot_evaluate_is_unavailable_not_failing(self, gate):
        # FR103 maps an unavailable gate to fail-closed; a failing gate with
        # budget left is a retry. Returning `fail` here would convert a broken
        # verifier into a quality judgement about the deliverable.
        with pytest.raises(GateUnavailable, match="could not be evaluated"):
            gate.evaluate(load_text(MIXED), {"answer": "x", "count": 5}, answer_key={})

    def test_a_contract_with_no_floor_cannot_produce_a_verdict(self, gate):
        floorless = MIXED.replace(
            """  mandatory:
    - id: answer-matches-key
      classification: E
      verifier:
        type: exact-match-against-answer-key
        args: { path: $.answer, key: answer }
    - id: count-in-range
      classification: E
      verifier:
        type: numeric-range
        args: { path: $.count, min: 1, max: 10 }
""",
            "  mandatory: []\n",
        )
        with pytest.raises(GateUnavailable, match="no floor"):
            gate.evaluate(load_text(floorless), {"answer": "x"}, answer_key={"answer": "x"})


class TestQualifier:
    def test_a_mixed_pass_is_constraint_backed(self, gate):
        # FR21: a pass resting wholly or partly on constraint-backed
        # verification is labelled constraint-backed.
        verdict = gate.evaluate(
            load_text(MIXED), {"answer": "x", "count": 5}, answer_key={"answer": "x"}
        )
        assert verdict.qualifier == "constraint-backed"

    def test_only_an_all_reference_backed_pass_is_reference_backed(self, gate):
        verdict = gate.evaluate(
            load_text(ALL_REFERENCE),
            {"answer": "x", "count": 5},
            answer_key={"answer": "x", "count": 5},
        )
        assert verdict.qualifier == "reference-backed"

    def test_a_fail_also_carries_a_qualifier(self, gate):
        # FR94: every verdict carries the qualifier.
        verdict = gate.evaluate(
            load_text(MIXED), {"answer": "no", "count": 5}, answer_key={"answer": "x"}
        )
        assert verdict.qualifier in {"reference-backed", "constraint-backed"}

    def test_an_optional_criterion_does_not_soften_the_qualifier(self, gate):
        # Only mandatory criteria decide the label.
        verdict = gate.evaluate(
            load_text(ALL_REFERENCE),
            {"answer": "x", "count": 5, "note": "present"},
            answer_key={"answer": "x", "count": 5},
        )
        assert verdict.qualifier == "reference-backed"


class TestOptionalNeverGates:
    def test_a_failing_optional_criterion_does_not_fail_the_verdict(self, gate):
        # FR19: optional and enrichment criteria never affect the verdict.
        verdict = gate.evaluate(
            load_text(MIXED), {"answer": "x", "count": 5}, answer_key={"answer": "x"}
        )
        note = next(r for r in verdict.breakdown if r.id == "note-present")
        assert not note.passed
        assert verdict.verdict == "pass"

    def test_an_optional_criterion_still_appears_in_the_breakdown(self, gate):
        verdict = gate.evaluate(
            load_text(MIXED), {"answer": "x", "count": 5}, answer_key={"answer": "x"}
        )
        assert any(r.tier == "optional" for r in verdict.breakdown)

    def test_only_mandatory_criteria_are_counted(self, gate):
        verdict = gate.evaluate(
            load_text(MIXED), {"answer": "x", "count": 5}, answer_key={"answer": "x"}
        )
        assert verdict.mandatory_evaluated == 2

    def test_an_optional_criterion_that_cannot_run_does_not_break_the_gate(self, gate):
        text = MIXED.replace(
            "      verifier: { type: field-present, args: { path: $.note } }",
            "      verifier:\n"
            "        type: exact-match-against-answer-key\n"
            "        args: { path: $.note, key: absent-from-key }",
        )
        verdict = gate.evaluate(
            load_text(text), {"answer": "x", "count": 5}, answer_key={"answer": "x"}
        )
        assert verdict.verdict == "pass"


class TestBreakdown:
    def test_every_criterion_is_named_with_its_outcome(self, gate):
        # FR26: which criteria passed and which failed, not only an aggregate.
        verdict = gate.evaluate(
            load_text(MIXED), {"answer": "no", "count": 50}, answer_key={"answer": "x"}
        )
        named = {r.id: r.passed for r in verdict.breakdown}
        assert named["answer-matches-key"] is False
        assert named["count-in-range"] is False

    def test_unmet_criteria_are_stated_explicitly(self, gate):
        # FR24 requires return-partial to state them; the gate supplies them.
        verdict = gate.evaluate(
            load_text(MIXED), {"answer": "no", "count": 50}, answer_key={"answer": "x"}
        )
        assert set(verdict.unmet) == {"answer-matches-key", "count-in-range"}

    def test_a_passing_verdict_has_nothing_unmet(self, gate):
        verdict = gate.evaluate(
            load_text(MIXED), {"answer": "x", "count": 5}, answer_key={"answer": "x"}
        )
        assert verdict.unmet == ()

    def test_each_result_records_the_verifier_that_produced_it(self, gate):
        verdict = gate.evaluate(
            load_text(MIXED), {"answer": "x", "count": 5}, answer_key={"answer": "x"}
        )
        result = next(r for r in verdict.breakdown if r.id == "count-in-range")
        assert result.verifier == "numeric-range"

    def test_a_failure_carries_its_detail(self, gate):
        verdict = gate.evaluate(
            load_text(MIXED), {"answer": "x", "count": 99}, answer_key={"answer": "x"}
        )
        result = next(r for r in verdict.breakdown if r.id == "count-in-range")
        assert "above" in result.detail


class TestAdvisorySignalsNeverGate:
    def test_an_advisory_signal_is_recorded(self, gate):
        signal = AdvisorySignal(source="rubric", observation="reads poorly")
        verdict = gate.evaluate(
            load_text(MIXED),
            {"answer": "x", "count": 5},
            answer_key={"answer": "x"},
            advisory=(signal,),
        )
        assert verdict.advisory == (signal,)

    def test_a_damning_advisory_signal_cannot_turn_a_pass_into_a_fail(self, gate):
        # FR20: a model-judged rubric may not override a deterministic result.
        verdict = gate.evaluate(
            load_text(MIXED),
            {"answer": "x", "count": 5},
            answer_key={"answer": "x"},
            advisory=(AdvisorySignal(source="rubric", observation="this is terrible"),),
        )
        assert verdict.verdict == "pass"

    def test_a_glowing_advisory_signal_cannot_turn_a_fail_into_a_pass(self, gate):
        verdict = gate.evaluate(
            load_text(MIXED),
            {"answer": "wrong", "count": 5},
            answer_key={"answer": "x"},
            advisory=(AdvisorySignal(source="rubric", observation="excellent work"),),
        )
        assert verdict.verdict == "fail"


class TestCadence:
    def test_the_five_step_classes_are_closed(self):
        assert STEP_CLASSES == {
            "deliverable-mutating",
            "evidence-gathering",
            "planning",
            "routing",
            "verification",
        }

    def test_the_default_cadence_set_is_the_two_declared_classes(self):
        assert DEFAULT_CADENCE == {"deliverable-mutating", "evidence-gathering"}

    @pytest.mark.parametrize("step_class", ["deliverable-mutating", "evidence-gathering"])
    def test_the_gate_runs_after_a_default_cadence_class(self, step_class):
        assert should_evaluate(step_class)

    @pytest.mark.parametrize("step_class", ["planning", "routing", "verification"])
    def test_the_gate_does_not_run_after_other_classes_by_default(self, step_class):
        assert not should_evaluate(step_class)

    def test_a_contract_may_add_a_class(self):
        cadence = cadence_for({"planning"})
        assert should_evaluate("planning", cadence=cadence)
        assert should_evaluate("deliverable-mutating", cadence=cadence)

    def test_a_contract_may_not_remove_deliverable_mutating(self):
        with pytest.raises(CadenceError, match="may not remove"):
            validate_cadence({"evidence-gathering"})

    def test_a_contract_may_drop_evidence_gathering(self):
        # FR98 permits omitting checkpoints for steps that cannot affect the
        # candidate result; only `deliverable-mutating` is irremovable.
        assert validate_cadence({"deliverable-mutating"}) == {"deliverable-mutating"}

    def test_an_unknown_step_class_is_refused(self):
        with pytest.raises(CadenceError, match="unknown step class"):
            should_evaluate("vibes")

    def test_an_unknown_added_class_is_refused(self):
        with pytest.raises(CadenceError, match="unknown step classes"):
            cadence_for({"telepathy"})

    def test_the_gate_runs_before_a_terminal_halt(self):
        # This is what gives stop-sufficient first refusal on the ending.
        assert should_evaluate_before_halt(fail_closed=False)

    def test_the_gate_does_not_run_before_a_fail_closed_halt(self):
        # A gate that cannot produce a verdict cannot be asked for one.
        assert not should_evaluate_before_halt(fail_closed=True)


class TestAgainstAFrozenContract:
    """The registry from E3 meeting a contract from E1a."""

    def test_a_correct_data_sql_deliverable_passes(self, gate):
        contract = load_path(ROOT / "contracts" / "data-sql.contract.yaml")
        deliverable = {
            "result_value": 17046.0,
            "units": "usd",
            "sql": "SELECT SUM(amount_cents) FROM orders",
            "row_count": 17,
            "tables_used": ["orders"],
        }
        key = {"result_value": 17046.0, "units": "usd", "row_count": 17}
        verdict = gate.evaluate(contract, deliverable, answer_key=key)
        assert verdict.verdict == "pass"
        assert verdict.mandatory_evaluated == 6

    def test_a_mutating_query_fails_the_read_only_criterion(self, gate):
        contract = load_path(ROOT / "contracts" / "data-sql.contract.yaml")
        deliverable = {
            "result_value": 17046.0,
            "units": "usd",
            "sql": "DELETE FROM orders",
            "row_count": 17,
            "tables_used": ["orders"],
        }
        key = {"result_value": 17046.0, "units": "usd", "row_count": 17}
        verdict = gate.evaluate(contract, deliverable, answer_key=key)
        assert verdict.verdict == "fail"
        assert "sql-is-read-only" in verdict.unmet

    def test_a_wrong_figure_fails_even_with_everything_else_right(self, gate):
        contract = load_path(ROOT / "contracts" / "data-sql.contract.yaml")
        deliverable = {
            "result_value": 999.0,
            "units": "usd",
            "sql": "SELECT 1",
            "row_count": 17,
            "tables_used": ["orders"],
        }
        key = {"result_value": 17046.0, "units": "usd", "row_count": 17}
        verdict = gate.evaluate(contract, deliverable, answer_key=key)
        assert verdict.unmet == ("result-matches-key",)

    def test_the_data_sql_verdict_is_constraint_backed(self, gate):
        # Three of its six mandatory criteria are constraint-backed, so the
        # whole verdict is - which is exactly what FR21 is for.
        contract = load_path(ROOT / "contracts" / "data-sql.contract.yaml")
        deliverable = {
            "result_value": 17046.0,
            "units": "usd",
            "sql": "SELECT 1",
            "row_count": 17,
            "tables_used": ["orders"],
        }
        key = {"result_value": 17046.0, "units": "usd", "row_count": 17}
        verdict = gate.evaluate(contract, deliverable, answer_key=key)
        assert verdict.qualifier == "constraint-backed"

    def test_a_doc_research_deliverable_needs_a_resolvable_citation(self, gate):
        contract = load_path(ROOT / "contracts" / "doc-research.contract.yaml")
        deliverable = {
            "answer": "Ninety days.",
            "answer_code": "days-90",
            "primary_source_id": "doc-001",
            "citations": [{"id": "doc-001"}, {"id": "ghost"}],
            "excluded_candidates": [],
            "confidence": "high",
        }
        key = {"answer_code": "days-90", "primary_source_id": "doc-001"}
        index = CitableIndex(
            entries=(CitableEntry(id="doc-001", target="documents.yaml", sha256=SHA),)
        )
        verdict = gate.evaluate(
            contract, deliverable, answer_key=key, citable_index=index
        )
        assert "citations-resolve" in verdict.unmet

    def test_the_gate_is_unavailable_without_the_citable_index_it_needs(self, gate):
        # AD-7: the index is supplied by the caller. Its absence is a driver
        # fault, not a quality judgement about the deliverable.
        contract = load_path(ROOT / "contracts" / "doc-research.contract.yaml")
        deliverable = {
            "answer": "Ninety days.",
            "answer_code": "days-90",
            "primary_source_id": "doc-001",
            "citations": [{"id": "doc-001"}],
            "excluded_candidates": [],
            "confidence": "high",
        }
        key = {"answer_code": "days-90", "primary_source_id": "doc-001"}
        with pytest.raises(GateUnavailable):
            gate.evaluate(contract, deliverable, answer_key=key)


class TestDeterminism:
    def test_evaluating_twice_gives_the_same_verdict(self, gate):
        contract = load_text(MIXED)
        args = ({"answer": "x", "count": 5}, {"answer": "x"})
        first = gate.evaluate(contract, args[0], answer_key=args[1])
        second = gate.evaluate(contract, args[0], answer_key=args[1])
        assert first == second

    def test_the_gate_does_not_mutate_the_deliverable(self, gate):
        deliverable = {"answer": "x", "count": 5}
        before = dict(deliverable)
        gate.evaluate(load_text(MIXED), deliverable, answer_key={"answer": "x"})
        assert deliverable == before

    def test_a_verdict_is_frozen(self, gate):
        verdict = gate.evaluate(
            load_text(MIXED), {"answer": "x", "count": 5}, answer_key={"answer": "x"}
        )
        with pytest.raises(ValidationError):
            verdict.verdict = "fail"
