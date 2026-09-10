"""E1b — content-hash and freeze, in one operation (FR65, FR64, AD-6, AD-7).

The point of no return. §8.2's whole defence is that the rubric and answer keys
were fixed before the governor existed, so this runs once and what it produces
is not revised afterwards.

Two rules shape the implementation:

**Every artifact declares its route.** AD-6 admits exactly two — `structure/v1`
for things with a typed shape, `file-digest/v1` for things that are source
rather than structure. Recording the route stops two freeze tools silently
picking different ones for the same artifact.

**The output is reproducible.** No timestamps, no environment, nothing ordered
by chance. Regenerating on another machine must produce identical bytes, or
FR65's drift refusal fires on a rubric that never changed — the exact failure
AD-6 exists to prevent. Git records when the freeze happened; the artifact
records only what was frozen.

    uv run python freeze/freeze.py [--check]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import yaml

from outcomefuse.core.canon import (
    NORMALISATION_VERSION,
    ROUTE_FILE_DIGEST,
    ROUTE_STRUCTURE,
    hash_file_manifest,
    hash_structure,
)
from outcomefuse.core.contract import unsatisfiability_warnings
from outcomefuse.core.verify import REGISTRY, REGISTRY_VERSION, registry_digest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "freeze"))

from coverage_report import load_all, render  # noqa: E402
from derive_answer_keys import context_for, derive  # noqa: E402

FREEZE_JSON = ROOT / "freeze" / "FREEZE.json"
FREEZE_MD = ROOT / "freeze" / "FREEZE.md"

FREEZE_VERSION = "v1"
WORKLOADS = ("code-triage", "data-sql", "doc-research", "supply-chain")
SPLITS = ("calibration", "evaluation")

#: Source artifacts, enumerated explicitly. A tree walk would sweep in whatever
#: happened to be on disk - `__pycache__` inside the code-triage corpus being the
#: obvious one, and `.pyc` is byte-exact, mtime-bearing and interpreter-specific.
SOURCE_GROUPS: dict[str, tuple[str, ...]] = {
    "rubric": ("freeze/RUBRIC.md",),
    "baseline_definition": (
        "freeze/BASELINE.md",
        "freeze/baseline-prompts/README.md",
        "freeze/baseline-prompts/code-triage.md",
        "freeze/baseline-prompts/data-sql.md",
        "freeze/baseline-prompts/doc-research.md",
        "freeze/baseline-prompts/supply-chain.md",
    ),
    "case_construction_rules": ("freeze/CASE-CONSTRUCTION-RULES.md",),
    "coverage_report": ("freeze/COVERAGE-REPORT.md",),
    "corpora": (
        "cases/corpora/code-triage/v1/repo/orderflow/__init__.py",
        "cases/corpora/code-triage/v1/repo/orderflow/cache.py",
        "cases/corpora/code-triage/v1/repo/orderflow/inventory.py",
        "cases/corpora/code-triage/v1/repo/orderflow/pricing.py",
        "cases/corpora/code-triage/v1/repo/orderflow/retry.py",
        "cases/corpora/code-triage/v1/repo/orderflow/shipping.py",
        "cases/corpora/code-triage/v1/repo/orderflow/validation.py",
        "cases/corpora/data-sql/v1/schema.sql",
        "cases/corpora/data-sql/v1/seed.sql",
        "cases/corpora/doc-research/v1/SELECTION.md",
        "cases/corpora/doc-research/v1/documents.yaml",
        "cases/corpora/supply-chain/v1/classification.sql",
        "cases/corpora/supply-chain/v1/schema.sql",
        "cases/corpora/supply-chain/v1/seed.sql",
    ),
    "verifier_registry_source": (
        "src/outcomefuse/core/verify/__init__.py",
        "src/outcomefuse/core/verify/citable_index.py",
        "src/outcomefuse/core/verify/path.py",
        "src/outcomefuse/core/verify/registry.py",
    ),
    "verifier_registry_tests": (
        "tests/core/verify/test_path_and_index.py",
        "tests/core/verify/test_registry.py",
    ),
    "derivation_scripts": (
        "freeze/check_cases.py",
        "freeze/coverage_report.py",
        "freeze/derive_answer_keys.py",
    ),
}


class NotReady(SystemExit):
    """The freeze refused. Nothing was written."""


def readiness(contracts: dict[str, Any]) -> list[str]:
    """Everything FR65 requires to be true at freeze time, checked not assumed."""
    problems: list[str] = []

    for workload, contract in contracts.items():
        for warning in unsatisfiability_warnings(contract):
            problems.append(f"{workload}: {warning}")

        # FR65: every mandatory criterion resolves to a registered verifier.
        for criterion in contract.criteria.mandatory:
            if criterion.verifier is None:
                problems.append(f"{workload}: mandatory {criterion.id!r} has no verifier")
            elif criterion.verifier.type not in REGISTRY:
                problems.append(
                    f"{workload}: mandatory {criterion.id!r} names unregistered "
                    f"{criterion.verifier.type!r}"
                )

        # FR65: advisory criteria are listed with the reason they are non-gating.
        for criterion in contract.criteria.advisory:
            if not criterion.description.strip():
                problems.append(
                    f"{workload}: advisory {criterion.id!r} gives no reason for being non-gating"
                )

    coverage_path = ROOT / "freeze" / "COVERAGE-REPORT.md"
    if render(contracts) != coverage_path.read_text(encoding="utf-8"):
        problems.append("COVERAGE-REPORT.md is stale; run freeze/coverage_report.py")

    seen: dict[str, str] = {}
    for split in SPLITS:
        for workload in WORKLOADS:
            folder = ROOT / "cases" / split / workload
            document = yaml.safe_load((folder / "cases.yaml").read_text(encoding="utf-8"))
            committed = yaml.safe_load((folder / "answer-keys.yaml").read_text(encoding="utf-8"))

            if document.get("data_class") != "synthetic":
                problems.append(f"{split}/{workload}: data_class is not declared synthetic")

            context = context_for(workload, document["corpus_ref"])
            fresh = {c["case_id"]: derive(workload, c, context) for c in document["cases"]}
            if fresh != committed:
                problems.append(f"{split}/{workload}: answer keys are stale")

            for case in document["cases"]:
                case_id = case["case_id"]
                if case_id in seen:
                    problems.append(f"case id {case_id!r} appears in {seen[case_id]} and {split}")
                seen[case_id] = f"{split}/{workload}"

    for workload in WORKLOADS:
        template = ROOT / "freeze" / "baseline-prompts" / f"{workload}.md"
        if not template.exists():
            problems.append(f"{workload}: no baseline prompt template")

    for group, paths in SOURCE_GROUPS.items():
        for relative in paths:
            if not (ROOT / relative).exists():
                problems.append(f"{group}: missing {relative}")
            if relative.endswith(".pyc") or "__pycache__" in relative:
                problems.append(f"{group}: {relative} is build output, not source")

    return problems


def source_digests() -> dict[str, dict[str, str]]:
    """One file-digest manifest per group, each declaring its route."""
    frozen = {}
    for group, paths in SOURCE_GROUPS.items():
        digest = hash_file_manifest(ROOT, list(paths))
        frozen[group] = {"route": digest.route, "sha256": digest.sha256, "files": len(paths)}
    return frozen


def structure_digests(contracts: dict[str, Any]) -> dict[str, Any]:
    cases: dict[str, Any] = {}
    for split in SPLITS:
        for workload in WORKLOADS:
            folder = ROOT / "cases" / split / workload
            document = yaml.safe_load((folder / "cases.yaml").read_text(encoding="utf-8"))
            keys = yaml.safe_load((folder / "answer-keys.yaml").read_text(encoding="utf-8"))
            cases[f"{split}/{workload}"] = {
                "route": ROUTE_STRUCTURE,
                "cases_sha256": hash_structure(document).sha256,
                "answer_keys_sha256": hash_structure(keys).sha256,
                "case_count": len(document["cases"]),
                "data_class": document["data_class"],
                "corpus_ref": document["corpus_ref"],
            }

    return {
        "contracts": {
            workload: {
                "route": ROUTE_STRUCTURE,
                "sha256": contract.digest().sha256,
                "contract_id": contract.contract_id,
                "version": contract.version,
            }
            for workload, contract in sorted(contracts.items())
        },
        "case_sets": dict(sorted(cases.items())),
        "verifier_registry": {
            "route": ROUTE_STRUCTURE,
            "sha256": registry_digest().sha256,
            "version": REGISTRY_VERSION,
        },
    }


def coverage_block(contracts: dict[str, Any]) -> dict[str, Any]:
    """FR65: counts and percentages of mandatory criteria by mode, per workload."""
    per_workload = {}
    for workload, contract in sorted(contracts.items()):
        counts = contract.mandatory_modes()
        reference, constraint = counts["reference-backed"], counts["constraint-backed"]
        total = reference + constraint
        per_workload[workload] = {
            "mandatory_count": total,
            "reference_backed_mandatory_count": reference,
            "constraint_backed_mandatory_count": constraint,
            "reference_backed_percent": round(100 * reference / total, 1) if total else 0.0,
            "constraint_backed_percent": round(100 * constraint / total, 1) if total else 0.0,
            "predominantly_constraint_backed": constraint > reference,
            "advisory": [
                {"id": c.id, "non_gating_reason": " ".join(c.description.split())}
                for c in contract.criteria.advisory
            ],
        }
    return per_workload


def build() -> dict[str, Any]:
    contracts = load_all()
    problems = readiness(contracts)
    if problems:
        raise NotReady(
            "FREEZE REFUSED - nothing written. E1b is the point of no return, so it "
            "does not proceed over a known defect:\n  - " + "\n  - ".join(problems)
        )

    record: dict[str, Any] = {
        "freeze_version": FREEZE_VERSION,
        "normalisation": NORMALISATION_VERSION,
        "routes": {"structure": ROUTE_STRUCTURE, "file_digest": ROUTE_FILE_DIGEST},
        **structure_digests(contracts),
        "source": source_digests(),
        "coverage": coverage_block(contracts),
    }
    # The seal covers everything above, so no single artifact can move alone.
    record["freeze_sha256"] = hash_structure(record).sha256
    return record


def render_markdown(record: dict[str, Any]) -> str:
    lines = [
        "# Freeze Record v1 (FR65, FR64)",
        "",
        "**Generated** by `freeze/freeze.py`. Do not edit by hand.",
        "",
        f"**Freeze digest** `{record['freeze_sha256']}`",
        "",
        "This is the point of no return. §8.2's defence is that the rubric and answer",
        "keys were fixed before the governor existed; re-freezing after seeing it is",
        "what that section exists to prevent. The record carries no timestamp, because",
        "regenerating it must reproduce identical bytes — a freeze that differed between",
        "two machines would trip FR65's drift refusal on artifacts that never changed.",
        "",
        "## Coverage at freeze time",
        "",
        "| Workload | Mandatory | Reference-backed | Constraint-backed | Reference % |"
        " Predominantly constraint-backed |",
        "| --- | ---: | ---: | ---: | ---: | --- |",
    ]
    for workload, block in record["coverage"].items():
        lines.append(
            f"| {workload} | {block['mandatory_count']} | "
            f"{block['reference_backed_mandatory_count']} | "
            f"{block['constraint_backed_mandatory_count']} | "
            f"{block['reference_backed_percent']}% | "
            f"{'**Yes**' if block['predominantly_constraint_backed'] else 'No'} |"
        )
    lines += ["", "## Contracts", "", "| Workload | Contract | Version | Route | SHA-256 |",
              "| --- | --- | ---: | --- | --- |"]
    for workload, block in record["contracts"].items():
        lines.append(
            f"| {workload} | `{block['contract_id']}` | {block['version']} | "
            f"`{block['route']}` | `{block['sha256'][:16]}…` |"
        )

    lines += ["", "## Case sets", "",
              "| Set | Cases | Data class | Corpus | Cases SHA-256 | Answer keys SHA-256 |",
              "| --- | ---: | --- | --- | --- | --- |"]
    for name, block in record["case_sets"].items():
        lines.append(
            f"| {name} | {block['case_count']} | {block['data_class']} | "
            f"`{block['corpus_ref']}` | `{block['cases_sha256'][:16]}…` | "
            f"`{block['answer_keys_sha256'][:16]}…` |"
        )
    lines += [
        "",
        "The **evaluation** sets are frozen and sealed. Their case definitions are",
        "authored and known; it is the *results* that must stay unseen until",
        "preregistration (FR66) is complete. Only evaluation results may support a",
        "headline claim, and calibration results may not enter the submission (FR102).",
        "",
        "## Verifier registry",
        "",
        f"Version `{record['verifier_registry']['version']}`, route "
        f"`{record['verifier_registry']['route']}`, digest "
        f"`{record['verifier_registry']['sha256']}`.",
        "",
        "A frozen rubric whose criteria take their executable meaning from an unfrozen",
        "registry is not frozen, so the registry, its source and its tests freeze here",
        "in the same operation.",
        "",
        "## Source artifacts (file-digest route)",
        "",
        "| Group | Files | SHA-256 |",
        "| --- | ---: | --- |",
    ]
    for group, block in sorted(record["source"].items()):
        lines.append(f"| {group} | {block['files']} | `{block['sha256'][:16]}…` |")

    lines += [
        "",
        "Paths are POSIX-separated, NFC-normalised and byte-sorted, and text artifacts",
        "are digested with LF line endings, so a Windows freeze and a Linux freeze agree.",
        "",
        "## Advisory criteria and why they do not gate",
        "",
    ]
    for workload, block in record["coverage"].items():
        lines.append(f"**{workload}**")
        lines.append("")
        for advisory in block["advisory"]:
            lines.append(f"- `{advisory['id']}` — {advisory['non_gating_reason']}")
        lines.append("")
    return "\n".join(lines) + "\n"


def main() -> int:
    record = build()
    serialised = json.dumps(record, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    markdown = render_markdown(record)

    if "--check" in sys.argv:
        stale = [
            path.name
            for path, expected in ((FREEZE_JSON, serialised), (FREEZE_MD, markdown))
            if not path.exists() or path.read_text(encoding="utf-8") != expected
        ]
        if stale:
            print(f"FREEZE DRIFT: {', '.join(stale)} does not match the current artifacts")
            return 1
        print(f"Freeze is intact: {record['freeze_sha256']}")
        return 0

    FREEZE_JSON.write_text(serialised, encoding="utf-8")
    FREEZE_MD.write_text(markdown, encoding="utf-8")
    print(f"froze {len(record['case_sets'])} case sets, {len(record['contracts'])} contracts")
    print(f"freeze digest {record['freeze_sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
