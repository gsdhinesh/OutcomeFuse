"""Contract loading and validation (AD-7, FR8, FR9, FR10, FR12).

The loader is the boundary where a data file becomes a quality floor. It is
also, per AD-7, the place a contract-driven RCE would have to start.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest
from pydantic import ValidationError

from outcomefuse.core.contract import (
    MAX_CONTRACT_BYTES,
    Contract,
    ContractError,
    load_path,
    load_text,
    unsatisfiability_warnings,
)

ROOT = Path(__file__).resolve().parent.parent.parent.parent
WORKLOADS = ("data-sql", "code-triage", "supply-chain", "doc-research")

MINIMAL = """
contract_id: ofc-test
version: 1
workload: testing
task_goal: A goal.
deliverable:
  structure:
    answer: string
criteria:
  mandatory:
    - id: answer-present
      classification: E
      verifier: { type: field-present, args: { path: $.answer } }
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


def contract(**edits: str) -> str:
    text = MINIMAL
    for old, new in edits.items():
        text = text.replace(old.replace("__", " "), new)
    return text


class TestRealContracts:
    @pytest.mark.parametrize("workload", WORKLOADS)
    def test_every_authored_contract_loads(self, workload):
        loaded = load_path(ROOT / "contracts" / f"{workload}.contract.yaml")
        assert loaded.workload == workload

    @pytest.mark.parametrize("workload", WORKLOADS)
    def test_no_authored_contract_is_internally_unsatisfiable(self, workload):
        loaded = load_path(ROOT / "contracts" / f"{workload}.contract.yaml")
        assert unsatisfiability_warnings(loaded) == []

    @pytest.mark.parametrize("workload", WORKLOADS)
    def test_every_mandatory_criterion_is_reference_or_constraint_backed(self, workload):
        loaded = load_path(ROOT / "contracts" / f"{workload}.contract.yaml")
        counts = loaded.mandatory_modes()
        assert sum(counts.values()) == len(loaded.criteria.mandatory)

    @pytest.mark.parametrize("workload", WORKLOADS)
    def test_the_digest_is_stable_across_loads(self, workload):
        path = ROOT / "contracts" / f"{workload}.contract.yaml"
        assert load_path(path).digest() == load_path(path).digest()

    def test_different_contracts_have_different_digests(self):
        digests = {
            load_path(ROOT / "contracts" / f"{w}.contract.yaml").digest().sha256
            for w in WORKLOADS
        }
        assert len(digests) == len(WORKLOADS)


class TestSafeLoading:
    def test_a_contract_executes_no_code(self):
        # The whole point of AD-7. python/object/apply is the classic vector.
        hostile = "!!python/object/apply:os.system ['echo pwned']\n"
        with pytest.raises(ContractError, match=r"does not parse|expected a mapping"):
            load_text(hostile)

    def test_an_arbitrary_tag_is_refused(self):
        with pytest.raises(ContractError):
            load_text("contract_id: !!python/name:os.system 'x'\n")

    def test_aliases_are_refused(self):
        # The billion-laughs shape: small input, unbounded expansion.
        bomb = textwrap.dedent(
            """
            a: &anchor [x, x, x, x, x, x, x, x, x]
            b: [*anchor, *anchor, *anchor, *anchor]
            """
        )
        with pytest.raises(ContractError, match="alias"):
            load_text(bomb)

    def test_an_oversized_contract_is_refused_before_parsing(self):
        with pytest.raises(ContractError, match="bytes, limit"):
            load_text("x: y\n" + "# padding\n" * MAX_CONTRACT_BYTES)

    def test_a_deeply_nested_contract_is_refused(self):
        nested = "a:\n" + "".join(f"{' ' * (i * 2)}b:\n" for i in range(1, 40)) + "  c: 1"
        with pytest.raises(ContractError, match="nests deeper"):
            load_text(nested)

    def test_a_non_mapping_document_is_refused(self):
        with pytest.raises(ContractError, match="expected a mapping"):
            load_text("- just\n- a\n- list\n")

    def test_unparseable_yaml_is_refused(self):
        with pytest.raises(ContractError, match="does not parse"):
            load_text("contract_id: [unclosed\n")

    def test_a_refusal_carries_the_digest_of_what_was_refused(self):
        # Parsing precedes the run manifest, so the rejection binds to content.
        with pytest.raises(ContractError) as caught:
            load_text("- not a mapping\n")
        assert caught.value.sha256 is not None and len(caught.value.sha256) == 64


class TestValidation:
    def test_the_minimal_contract_is_valid(self):
        assert isinstance(load_text(MINIMAL), Contract)

    def test_a_mandatory_criterion_without_a_verifier_is_rejected(self):
        # FR8, stated bluntly: if it cannot be checked, it cannot be the floor.
        text = MINIMAL.replace(
            "      verifier: { type: field-present, args: { path: $.answer } }\n", ""
        )
        with pytest.raises(ContractError, match="no executable verifier"):
            load_text(text)

    def test_a_mandatory_criterion_naming_an_unregistered_verifier_is_rejected(self):
        text = MINIMAL.replace("type: field-present", "type: llm-judge")
        with pytest.raises(ContractError, match="unregistered"):
            load_text(text)

    @pytest.mark.parametrize("classification", ["N", "A"])
    def test_only_an_expressible_criterion_may_be_mandatory(self, classification):
        text = MINIMAL.replace("classification: E", f"classification: {classification}")
        with pytest.raises(ContractError, match="only E may be mandatory"):
            load_text(text)

    def test_an_unclassified_criterion_is_rejected(self):
        text = MINIMAL.replace("classification: E", "classification: X")
        with pytest.raises(ContractError):
            load_text(text)

    def test_an_unknown_top_level_key_is_rejected(self):
        with pytest.raises(ContractError, match=r"[Ee]xtra"):
            load_text(MINIMAL + "surprise: true\n")

    def test_duplicate_criterion_ids_are_rejected(self):
        text = MINIMAL.replace(
            "budget:",
            "  advisory:\n    - id: answer-present\n      classification: A\nbudget:",
        )
        with pytest.raises(ContractError, match="duplicate criterion"):
            load_text(text)

    def test_an_approval_condition_naming_an_undeclared_tool_is_rejected(self):
        text = MINIMAL + textwrap.dedent(
            """
            human_approval_conditions:
              - tool: nonexistent
                when: always
            """
        )
        with pytest.raises(ContractError, match="undeclared tool"):
            load_text(text)

    def test_an_approval_condition_naming_both_a_tool_and_a_criterion_is_rejected(self):
        text = MINIMAL + textwrap.dedent(
            """
            human_approval_conditions:
              - tool: search
                criterion: answer
                when: always
            """
        )
        with pytest.raises(ContractError, match="either a tool or a criterion"):
            load_text(text)

    def test_fail_closed_is_not_a_policy_action(self):
        # `fail-closed` is a decision_reason and a terminal_reason. `on_timeout`
        # names a disposition, so the vocabularies must not be mixed.
        with pytest.raises(ContractError):
            load_text(MINIMAL + "on_timeout: fail-closed\n")

    @pytest.mark.parametrize(
        "action", ["terminate", "escalate", "return-partial", "request-human"]
    )
    def test_the_permitted_timeout_dispositions_are_accepted(self, action):
        assert load_text(MINIMAL + f"on_timeout: {action}\n").on_timeout == action

    def test_a_contract_is_frozen_once_loaded(self):
        # FR10: immutable for the duration of a run.
        loaded = load_text(MINIMAL)
        with pytest.raises(ValidationError):
            loaded.contract_id = "something-else"

    @pytest.mark.parametrize("budget", ["max_tokens: 0", "max_iterations: 0", "max_tool_calls: 0"])
    def test_a_non_positive_budget_is_rejected(self, budget):
        field = budget.split(":")[0]
        text = MINIMAL.replace(f"  {field}: ", "  ignored_" + field + ": ") + f"  {budget}\n"
        with pytest.raises(ContractError):
            load_text(text)


class TestUnsatisfiabilityWarnings:
    def test_a_reserve_that_consumes_the_whole_ceiling_warns(self):
        text = MINIMAL.replace(
            "  max_tool_calls: 5",
            "  verification_reserve:\n    max_tokens: 1000\n    max_estimated_cost: 0.01\n"
            "  max_tool_calls: 5",
        )
        warnings = unsatisfiability_warnings(load_text(text))
        assert any("leaves nothing" in w for w in warnings)

    def test_a_criterion_verifying_an_undeclared_field_warns(self):
        text = MINIMAL.replace("path: $.answer", "path: $.nowhere")
        warnings = unsatisfiability_warnings(load_text(text))
        assert any("never asks for" in w for w in warnings)

    def test_a_single_iteration_with_a_floor_warns(self):
        text = MINIMAL.replace("max_iterations: 3", "max_iterations: 1")
        warnings = unsatisfiability_warnings(load_text(text))
        assert any("no iteration in which to act" in w for w in warnings)

    def test_a_contract_with_no_tools_warns(self):
        text = MINIMAL.split("tools:")[0]
        warnings = unsatisfiability_warnings(load_text(text))
        assert any("no tools" in w for w in warnings)

    def test_a_well_formed_reachable_contract_warns_about_nothing(self):
        assert unsatisfiability_warnings(load_text(MINIMAL)) == []
