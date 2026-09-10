"""The coverage report must describe the contracts as they actually are (FR108).

E1b freezes the report alongside the contracts and the registry. A report that
has drifted from either would be frozen saying something untrue about the floor,
which is the specific failure FR108 exists to prevent.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from coverage_report import REPORT, WORKLOADS, load_all, mandatory_usage, render
from outcomefuse.core.verify import REGISTRY, registry_digest

ROOT = Path(__file__).resolve().parent.parent.parent


def test_the_committed_report_is_not_stale():
    """Regenerating must reproduce what is on disk."""
    assert REPORT.read_text(encoding="utf-8") == render(load_all()), (
        "COVERAGE-REPORT.md is stale — run freeze/coverage_report.py and commit"
    )


def test_the_report_pins_the_registry_it_was_generated_against():
    # A frozen report describing a moved registry is not frozen.
    assert registry_digest().sha256 in REPORT.read_text(encoding="utf-8")


def test_every_workload_appears():
    report = REPORT.read_text(encoding="utf-8")
    for workload in WORKLOADS:
        assert f"### {workload}" in report


def test_no_criterion_needs_a_new_verifier_type():
    """The three-addition allowance stays unspent unless a gap is demonstrated."""
    needed = [
        criterion.id
        for contract in load_all().values()
        for _, criterion in contract.criteria.tiers()
        if criterion.classification == "N"
    ]
    assert needed == [], f"criteria classified N: {needed} — at most three may be admitted"


@pytest.mark.parametrize("workload", WORKLOADS)
def test_no_workload_has_zero_reference_backed_mandatory_criteria(workload):
    """Zero would bar the workload from implying established correctness."""
    counts = load_all()[workload].mandatory_modes()
    assert counts["reference-backed"] > 0


@pytest.mark.parametrize("workload", WORKLOADS)
def test_a_predominantly_constraint_backed_workload_is_labelled(workload):
    counts = load_all()[workload].mandatory_modes()
    predominant = counts["constraint-backed"] > counts["reference-backed"]
    report = REPORT.read_text(encoding="utf-8")
    row = next(line for line in report.splitlines() if line.startswith(f"| {workload} |"))
    assert ("**Yes**" in row) == predominant


def test_unused_registry_types_are_recorded_rather_than_dropped():
    unused = [t for t, n in mandatory_usage(load_all()).items() if n == 0]
    report = REPORT.read_text(encoding="utf-8")
    for verifier_type in unused:
        assert verifier_type in REGISTRY
        assert f"`{verifier_type}`" in report


def test_every_registry_type_appears_in_the_usage_table():
    report = REPORT.read_text(encoding="utf-8")
    for verifier_type in REGISTRY:
        assert f"| `{verifier_type}` |" in report
