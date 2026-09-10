"""Generate the verification-mode coverage report (FR108, AD-7).

The report is derived from the contracts and the registry, never hand-written.
A hand-maintained coverage table drifts from the contracts it describes, and
E1b freezes it — so this regenerates and the test suite fails if what is
committed no longer matches what the contracts say.

    uv run python freeze/coverage_report.py [--check]
"""

from __future__ import annotations

import sys
from pathlib import Path

from outcomefuse.core.contract import Contract, load_path, unsatisfiability_warnings
from outcomefuse.core.verify import REGISTRY, REGISTRY_VERSION, registry_digest

ROOT = Path(__file__).resolve().parent.parent
WORKLOADS = ("doc-research", "code-triage", "data-sql", "supply-chain")
REPORT = ROOT / "freeze" / "COVERAGE-REPORT.md"

#: FR108 names the criteria most easily missed because they are semantic. Each
#: is tied to the criterion ids that carry it, so the mapping is checkable
#: rather than narrated.
SEMANTIC_PROPERTIES: dict[str, tuple[str, ...]] = {
    "Root-cause correctness": ("root-cause-file-correct", "root-cause-explanation-correct"),
    "Query-result correctness": ("result-matches-key", "question-actually-answered"),
    "Code-location correctness": ("root-cause-file-correct", "root-cause-line-in-span"),
    "Evidence completeness": ("citations-resolve", "evidence-completeness"),
    "Conclusion supported rather than present": ("conclusion-is-supported",),
}


def load_all() -> dict[str, Contract]:
    return {w: load_path(ROOT / "contracts" / f"{w}.contract.yaml") for w in WORKLOADS}


def classify(contract: Contract) -> list[tuple[str, str, str, str, str]]:
    """(tier, id, class, verifier, mode) for every criterion, derived."""
    rows = []
    for tier, criterion in contract.criteria.tiers():
        if criterion.verifier is None:
            rows.append((tier, criterion.id, criterion.classification, "—", "—"))
        else:
            rows.append(
                (
                    tier,
                    criterion.id,
                    criterion.classification,
                    criterion.verifier.type,
                    criterion.verifier.mode.removesuffix("-backed"),
                )
            )
    return rows


def mandatory_usage(contracts: dict[str, Contract]) -> dict[str, int]:
    counts = dict.fromkeys(REGISTRY, 0)
    for contract in contracts.values():
        for criterion in contract.criteria.mandatory:
            if criterion.verifier is not None:
                counts[criterion.verifier.type] += 1
    return counts


def render(contracts: dict[str, Contract]) -> str:
    lines: list[str] = []
    add = lines.append

    add("# Verification-Mode Coverage Report (FR108)")
    add("")
    add("**Generated** by `freeze/coverage_report.py` from the four contracts and the")
    add("registry. Do not edit by hand — regenerate. Frozen at E1b in one operation")
    add("with the cases, answer keys, rubric, contracts and registry.")
    add("")
    add(f"Registry version `{REGISTRY_VERSION}`, digest `{registry_digest().sha256}`.")
    add("")

    add("## Mandatory criteria by verification mode")
    add("")
    add("Mode is a property of the verifier type, fixed by the registry. No contract")
    add("asserts it, which is what stops `reference-backed` being claimed for a check")
    add("that never compared against a known-correct value.")
    add("")
    add(
        "| Workload | Mandatory | Reference-backed | Constraint-backed | Reference % |"
        " Predominantly constraint-backed |"
    )
    add("| --- | ---: | ---: | ---: | ---: | --- |")
    ties = []
    for workload, contract in contracts.items():
        counts = contract.mandatory_modes()
        reference, constraint = counts["reference-backed"], counts["constraint-backed"]
        total = reference + constraint
        predominant = constraint > reference
        if reference == constraint:
            ties.append(workload)
        share = f"{100 * reference / total:.0f}%" if total else "—"
        add(
            f"| {workload} | {total} | {reference} | {constraint} | {share} | "
            f"{'**Yes**' if predominant else 'No'} |"
        )
    add("")

    zero_reference = [
        w for w, c in contracts.items() if c.mandatory_modes()["reference-backed"] == 0
    ]
    if zero_reference:
        add(
            f"**{', '.join(zero_reference)} has no reference-backed mandatory criterion.** "
            "It may still be evaluated, but may not be used to imply that OutcomeFuse "
            "independently established semantic correctness."
        )
    else:
        add(
            "No workload is predominantly constraint-backed, and every workload has at "
            "least one reference-backed mandatory criterion."
        )
    add("")

    if ties:
        add(
            f"**Read that result carefully.** {', '.join(ties)} sit exactly on the "
            "boundary — equal counts either side. The rule labels a workload "
            "predominantly constraint-backed only where constraint-backed *exceeds* "
            "reference-backed, so a tie passes. One criterion moving in either "
            "direction would flip the label. This is a defensible rule and not a "
            "precise one: it counts criteria and is blind to which one carries the "
            "decision. A weighted rule was considered and rejected because the "
            "weighting would itself be an unverified judgement, and an arguable "
            "number presented precisely is worse than a blunt one presented plainly."
        )
        add("")

    add("## Registry usage")
    add("")
    add("| Verifier type | Mode | Mandatory uses |")
    add("| --- | --- | ---: |")
    usage = mandatory_usage(contracts)
    for verifier_type in sorted(REGISTRY):
        entry = REGISTRY[verifier_type]
        add(f"| `{verifier_type}` | {entry.mode} | {usage[verifier_type]} |")
    add("")

    unused = sorted(t for t, n in usage.items() if n == 0)
    if unused:
        listed = ", ".join(f"`{t}`" for t in unused)
        add(
            f"**Registered, tested, zero MVP mandatory usage: {listed}.** "
            "Recorded rather than dropped or given an invented use. Where the answer "
            "key pins a field, `exact-match-against-answer-key` proves the value is "
            "*right* while `set-membership` proves only that it is *legal* — strictly "
            "the weaker check, so there is no reason to prefer it. On a production "
            "workload with no answer key, membership is what remains available, which "
            "is why it stays registered."
        )
        add("")

    add("## Classification")
    add("")
    add("**E** expressible with an existing verifier · **N** a new deterministic type is")
    add("demonstrably needed · **A** advisory: recorded, fed to counter-metrics, never gating.")
    add("")
    totals = {"E": 0, "N": 0, "A": 0}
    for contract in contracts.values():
        for _, _, classification, _, _ in classify(contract):
            totals[classification] += 1
    add(f"**E {totals['E']} · N {totals['N']} · A {totals['A']}**")
    add("")
    if totals["N"] == 0:
        add(
            "**No `N`.** Every criterion the four contracts declare is expressible with "
            "the seven existing types, so the allowance of at most three additional "
            "deterministic types is **unused**. That result holds only because the "
            "semantic criteria were classified `A` honestly rather than approximated by "
            "a proxy verifier and called mandatory — the failure mode FR108 exists to "
            "catch, in which the floor quietly shrinks to presence and type."
        )
    else:
        add(
            f"**{totals['N']} criteria need a new deterministic type.** The allowance is "
            "three; see the gap analysis below before spending it."
        )
    add("")

    for workload, contract in contracts.items():
        add(f"### {workload}")
        add("")
        add("| Criterion | Tier | Class | Verifier | Mode |")
        add("| --- | --- | :-: | --- | --- |")
        for tier, name, classification, verifier, mode in classify(contract):
            emphasis = f"**{classification}**" if classification != "E" else classification
            shown = f"`{verifier}`" if verifier != "—" else "—"
            add(f"| {name} | {tier} | {emphasis} | {shown} | {mode} |")
        add("")

    add("## The semantic criteria, explicitly")
    add("")
    add("FR108 requires the review to cover the criteria most easily missed because they")
    add("are semantic. Each is traced to the criteria that carry it.")
    add("")
    add("| Semantic property | Carried by | Landed |")
    add("| --- | --- | --- |")
    everything = {
        name: classification
        for contract in contracts.values()
        for _, name, classification, _, _ in classify(contract)
    }
    for prop, ids in SEMANTIC_PROPERTIES.items():
        present = [i for i in ids if i in everything]
        landed = ", ".join(f"`{i}` ({everything[i]})" for i in present) or "not declared"
        classes = {everything[i] for i in present}
        verdict = "E" if classes == {"E"} else ("A" if classes == {"A"} else "split E/A")
        add(f"| {prop} | {landed} | **{verdict}** |")
    add("")
    add(
        "**This is the honest limit of the MVP gate.** In every workload the property a "
        "user cares about most — is the conclusion *justified* — is advisory. What the "
        "gate enforces is that the answer matches a known-correct value and that its "
        "evidence exists and resolves. That is real and checkable, and it is not the "
        "same as understanding. Any claim drawn from these runs must be phrased against "
        "what was actually verified."
    )
    add("")

    add("## Weakest mandatory criterion, named")
    add("")
    add(
        "`fix-summary-substantive` (code-triage) is a length-and-keyword regex. It is a "
        "proxy for *a real fix was described*, and it is the weakest thing in the floor. "
        "It was kept mandatory rather than demoted because the alternative is that "
        "`fix_summary` is checked only for presence, which accepts a single character. "
        "It is honest as a **constraint** and must never be read as evidence the fix is "
        "correct — `fix-is-appropriate` is advisory and is where that judgement lives."
    )
    add("")

    add("## Unsatisfiability (FR9)")
    add("")
    findings = {w: unsatisfiability_warnings(c) for w, c in contracts.items()}
    if any(findings.values()):
        for workload, warnings in findings.items():
            for warning in warnings:
                add(f"- **{workload}** — {warning}")
    else:
        add("No contract is internally unsatisfiable. Every mandatory criterion reads a")
        add("field the deliverable declares, and every declared reserve leaves room to run.")
    add("")
    return "\n".join(lines) + "\n"


def main() -> int:
    contracts = load_all()
    rendered = render(contracts)
    if "--check" in sys.argv:
        current = REPORT.read_text(encoding="utf-8") if REPORT.exists() else ""
        if current != rendered:
            print("COVERAGE-REPORT.md is stale; run freeze/coverage_report.py")
            return 1
        print("COVERAGE-REPORT.md is current.")
        return 0
    REPORT.write_text(rendered, encoding="utf-8")
    print(f"wrote {REPORT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
