"""Case loading and prompt construction (FR64, §8.1).

Two properties carry the weight here.

**A case's reference never reaches a prompt.** For data-sql it holds the query
that produces the answer. `Case` drops everything but the three keys the frozen
README names, so the runtime cannot leak an answer into a prompt even by
accident — it never holds one to leak.

**A half-substituted template is refused, not sent.** The frozen README calls
an unsubstituted placeholder a harness bug rather than a prompt variation. A
template that reached a model with `{{as_of}}` still in it would produce a
failure that looked like the agent's.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from outcomefuse.harness.cases import PROMPT_CONTEXT_KEYS, Case, CaseError, load_case_set
from outcomefuse.harness.prompts import PromptError, load_template, render

WORKLOADS = ("data-sql", "code-triage", "doc-research", "supply-chain")

#: The four `partial` cases. Their prompt parameters live in `prompt_context`
#: rather than `reference`, because `reference` means key-derivation input and
#: an unanswerable case correctly has none — the frozen deriver refuses one
#: that does.
PARTIAL_CASES = {"dr-c-012", "dr-e-008", "sc-c-012", "sc-e-008"}


def a_case(**over) -> Case:
    base = {
        "case_id": "x-001",
        "workload": "data-sql",
        "split": "calibration",
        "difficulty": "direct",
        "expected_outcome": "answer",
        "prompt": "How many orders closed in Q1?",
    }
    return Case(**(base | over))


class TestTheReferenceNeverReachesTheRuntime:
    def test_the_answer_sql_is_dropped_on_load(self):
        # data-sql references hold `value_sql`, which is the answer.
        for case in load_case_set("data-sql", "calibration").cases:
            assert case.prompt_context == {}

    def test_only_the_allow_listed_keys_survive(self):
        for split in ("calibration", "evaluation"):
            for workload in WORKLOADS:
                for case in load_case_set(workload, split).cases:
                    assert set(case.prompt_context) <= PROMPT_CONTEXT_KEYS

    def test_the_allow_list_is_exactly_what_the_frozen_readme_names(self):
        assert PROMPT_CONTEXT_KEYS == {"as_of", "region", "po_id"}

    def test_a_rendered_prompt_never_contains_an_answer_artifact(self):
        for workload in WORKLOADS:
            for case in load_case_set(workload, "calibration").cases:
                text = render(case).shared_task_block.lower()
                assert "value_sql" not in text
                assert "answer_key" not in text


class TestLoading:
    @pytest.mark.parametrize("workload", WORKLOADS)
    @pytest.mark.parametrize("split", ["calibration", "evaluation"])
    def test_every_frozen_case_set_loads(self, workload, split):
        case_set = load_case_set(workload, split)
        assert case_set.workload == workload
        assert case_set.split == split
        assert case_set.data_class == "synthetic"
        assert len(case_set.cases) == (12 if split == "calibration" else 8)

    def test_a_missing_case_set_is_named(self):
        with pytest.raises(CaseError, match="no case set at"):
            load_case_set("weather", "calibration")

    def test_a_case_can_be_found_by_id(self):
        assert load_case_set("data-sql", "calibration").by_id("ds-c-001").case_id == "ds-c-001"

    def test_an_unknown_case_id_is_refused(self):
        with pytest.raises(CaseError, match="no case 'ds-c-999'"):
            load_case_set("data-sql", "calibration").by_id("ds-c-999")

    def test_the_unanswerable_cases_are_marked(self):
        # Roughly one in ten, and no prompt says which.
        unanswerable = [
            c for c in load_case_set("doc-research", "calibration").cases if c.is_unanswerable
        ]
        assert unanswerable


class TestTheSharedTaskBlock:
    @pytest.mark.parametrize("workload", WORKLOADS)
    def test_the_frozen_template_has_both_blocks(self, workload):
        template = load_template(workload)
        assert template.system and template.user

    def test_a_workload_without_a_template_is_refused(self):
        with pytest.raises(PromptError, match="no frozen prompt template"):
            load_template("weather")

    @pytest.mark.parametrize("workload", WORKLOADS)
    def test_the_block_names_no_criterion_or_threshold(self, workload):
        # §8.1: a quality floor in the shared block would hand the baseline the
        # artifact BASELINE.md says it does not have.
        text = load_template(workload).shared_task_block.lower()
        for forbidden in ("criterion", "threshold", "answer key", "quality floor"):
            assert forbidden not in text

    def test_substitution_fills_the_structured_header(self):
        case = load_case_set("doc-research", "calibration").by_id("dr-c-001")
        user = render(case).user
        assert "Region: apac" in user
        assert "Decision date: 2026-01-10" in user
        assert case.prompt in user

    def test_code_triage_reads_the_case_text_as_its_report(self):
        # Its template calls the placeholder `report`; it is the same text.
        case = load_case_set("code-triage", "calibration").cases[0]
        assert case.prompt in render(case).user


class TestAHalfSubstitutedPromptIsRefused:
    def test_a_missing_value_refuses_the_run(self):
        with pytest.raises(PromptError, match="leaves"):
            render(a_case(workload="doc-research", case_id="x-002"))

    def test_the_refusal_names_what_was_missing(self):
        with pytest.raises(PromptError, match=r"\['as_of', 'region'\]"):
            render(a_case(workload="doc-research"))

    def test_it_is_called_a_harness_bug_rather_than_a_variation(self):
        with pytest.raises(PromptError, match="harness bug"):
            render(a_case(workload="supply-chain"))

    @pytest.mark.parametrize("case_id", sorted(PARTIAL_CASES))
    def test_the_four_partial_cases_render_like_their_peers(self, case_id):
        # They are the load-bearing unanswerable cases. A blank `Region:` would
        # give exactly the cases that test fabrication a differently shaped
        # prompt from every other case — and an empty header is itself a cue.
        split = "calibration" if "-c-" in case_id else "evaluation"
        workload = "doc-research" if case_id.startswith("dr") else "supply-chain"
        case = load_case_set(workload, split).by_id(case_id)
        assert case.expected_outcome == "partial"
        assert case.prompt_context
        assert render(case).user

    def test_a_partial_case_still_carries_no_key_derivation_reference(self):
        # The frozen deriver refuses an unanswerable case that does, and that
        # invariant was not weakened to make these render.
        import yaml

        raw = yaml.safe_load(
            Path("cases/calibration/supply-chain/cases.yaml").read_text(encoding="utf-8")
        )
        case = next(c for c in raw["cases"] if c["case_id"] == "sc-c-012")
        assert "reference" not in case
        assert case["prompt_context"] == {"po_id": 5009}

    def test_every_frozen_case_renders(self):
        for split in ("calibration", "evaluation"):
            for workload in WORKLOADS:
                for case in load_case_set(workload, split).cases:
                    assert render(case).user
