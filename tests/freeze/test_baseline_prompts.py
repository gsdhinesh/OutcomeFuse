"""The prompt templates must offer every controlled value the keys require.

Several criteria are exact matches against a controlled vocabulary. If a value
exists in an answer key but never appears in the prompt, the agent is being
graded on a label it was never shown — the case fails on vocabulary rather than
on reasoning, and E1b freezes both sides of the mismatch together.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent.parent
PROMPTS = ROOT / "freeze" / "baseline-prompts"
SPLITS = ("calibration", "evaluation")


def key_values(workload: str, field: str) -> set[str]:
    values: set[str] = set()
    for split in SPLITS:
        path = ROOT / "cases" / split / workload / "answer-keys.yaml"
        keys = yaml.safe_load(path.read_text(encoding="utf-8"))
        values |= {k[field] for k in keys.values() if field in k}
    return values


@pytest.mark.parametrize(
    ("workload", "field"),
    [
        ("data-sql", "units"),
        ("code-triage", "severity"),
        ("supply-chain", "exception_type"),
        ("supply-chain", "root_cause_code"),
        ("supply-chain", "recommended_action"),
    ],
)
def test_every_controlled_value_appears_in_the_prompt(workload, field):
    template = (PROMPTS / f"{workload}.md").read_text(encoding="utf-8")
    values = key_values(workload, field)
    assert values, f"no {field} values found in the {workload} keys"
    missing = sorted(v for v in values if v not in template)
    assert not missing, f"{workload}.md never offers {field}: {missing}"


def test_doc_research_shows_an_example_of_every_answer_code_unit():
    template = (PROMPTS / "doc-research.md").read_text(encoding="utf-8")
    units = {code.rsplit("-", 1)[0] for code in key_values("doc-research", "answer_code")}
    missing = sorted(u for u in units if f"{u}-" not in template)
    assert not missing, f"doc-research.md shows no answer_code example for: {missing}"


@pytest.mark.parametrize(
    "workload", ["data-sql", "code-triage", "supply-chain", "doc-research"]
)
def test_no_template_leaks_the_quality_floor(workload):
    """A criterion id in the shared block would hand the baseline the floor."""
    contract = yaml.safe_load(
        (ROOT / "contracts" / f"{workload}.contract.yaml").read_text(encoding="utf-8")
    )
    body = (PROMPTS / f"{workload}.md").read_text(encoding="utf-8")
    prompt = body.split("## Notes on what is deliberately absent")[0]
    ids = [c["id"] for group in contract["criteria"].values() for c in group]
    leaked = sorted(i for i in ids if i in prompt)
    assert not leaked, f"{workload}.md names criteria in the shared block: {leaked}"


@pytest.mark.parametrize(
    "workload", ["data-sql", "code-triage", "supply-chain", "doc-research"]
)
def test_every_declared_deliverable_field_is_named_in_the_prompt(workload):
    contract = yaml.safe_load(
        (ROOT / "contracts" / f"{workload}.contract.yaml").read_text(encoding="utf-8")
    )
    template = (PROMPTS / f"{workload}.md").read_text(encoding="utf-8")
    fields = contract["deliverable"]["structure"]
    missing = sorted(f for f in fields if f not in template)
    assert not missing, f"{workload}.md never asks for: {missing}"


@pytest.mark.parametrize(
    "workload", ["data-sql", "code-triage", "supply-chain", "doc-research"]
)
def test_every_verified_path_is_a_declared_deliverable_field(workload):
    """An optional criterion reading an undeclared field can never pass."""
    contract = yaml.safe_load(
        (ROOT / "contracts" / f"{workload}.contract.yaml").read_text(encoding="utf-8")
    )
    declared = set(contract["deliverable"]["structure"])
    undeclared = []
    for group in contract["criteria"].values():
        for criterion in group:
            verifier = criterion.get("verifier")
            if not verifier:
                continue
            path = verifier.get("args", {}).get("path", "")
            if not path.startswith("$."):
                continue
            field = path[2:].split(".")[0].split("[")[0]
            if field not in declared:
                undeclared.append(f"{criterion['id']} -> {path}")
    assert not undeclared, f"{workload} verifies undeclared fields: {undeclared}"
