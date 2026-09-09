"""Derive case answer keys from the frozen corpora.

Answer keys are never hand-asserted. A key written by hand can silently
disagree with the corpus it describes, and by E1b both are frozen together and
the disagreement becomes permanent.

Keys are written to a file separate from the cases so that the authored prompt
and the correct answer are not the same object — the harness surfaces prompts
to the agent and must never be one field access away from the key.

Derivation is per workload:

* ``data-sql``    — execute the case's reference SQL against the corpus.
* ``code-triage`` — locate the defect's anchor line in the corpus and compute
  the span from it. ``severity`` is the one authored field: impact is a
  judgement and cannot be asked of the source. It is copied through, and should
  be read as authored rather than derived.
* ``supply-chain`` — run the corpus's ``classification.sql`` for the case's
  purchase order. The corpus stores no exception type, root cause or
  recommended action; all three are computed from primitive facts under a fixed
  precedence ladder, so no keyed field here is authored.
* ``doc-research`` — apply the corpus's documented selection rule to the case's
  topic, region and as-of date. No document carries an answer code; the winning
  document is selected and its primitive control value rendered.

Run: uv run --with pyyaml python freeze/derive_answer_keys.py
"""

from __future__ import annotations

import sqlite3
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent
SPLITS = ("calibration", "evaluation")
WORKLOADS = ("data-sql", "code-triage", "supply-chain", "doc-research")
SEVERITIES = {"blocker", "major", "minor", "cosmetic"}
RULE_STEPS = {"draft-exclusion", "effective-dating", "supersession", "region-precedence"}


def fail(message: str) -> None:
    raise SystemExit(message)


def sql_corpus(corpus_ref: str) -> sqlite3.Connection:
    corpus = ROOT / corpus_ref
    db = sqlite3.connect(":memory:")
    db.executescript((corpus / "schema.sql").read_text(encoding="utf-8"))
    db.executescript((corpus / "seed.sql").read_text(encoding="utf-8"))
    violations = db.execute("PRAGMA foreign_key_check").fetchall()
    if violations:
        fail(f"corpus {corpus_ref} has foreign-key violations: {violations}")
    return db


def scalar(db: sqlite3.Connection, sql: str) -> Any:
    rows = db.execute(sql).fetchall()
    if len(rows) != 1 or len(rows[0]) != 1:
        fail(f"reference SQL must return exactly one scalar:\n{sql}")
    return rows[0][0]


def derive_data_sql(case: dict[str, Any], context: Any) -> dict[str, Any]:
    db: sqlite3.Connection = context
    case_id = case["case_id"]
    ref = case["reference"]

    raw = scalar(db, ref["value_sql"])
    if raw is None:
        fail(f"{case_id}: reference value SQL returned NULL — the case is unanswerable")
    rows = scalar(db, ref["rows_sql"])
    if not rows:
        fail(f"{case_id}: reference row SQL returned zero contributing rows")

    key: dict[str, Any] = {"expected_outcome": "answer", "units": case["units"]}
    if ref["value_is_cents"]:
        cents = int(raw)
        key["result_value"] = float(Decimal(cents) / 100)
        key["result_value_cents"] = cents
    else:
        key["result_value"] = int(raw)
    key["row_count"] = int(rows)
    return key


def locate_anchor(repo: Path, case_id: str, ref: dict[str, Any]) -> tuple[int, int]:
    """Return the 1-based line span the defect occupies, computed from the anchor."""
    target = repo / ref["file"]
    if not target.is_file():
        fail(f"{case_id}: corpus has no file {ref['file']!r}")

    anchor = ref["anchor"].strip()
    lines = target.read_text(encoding="utf-8").splitlines()
    hits = [n for n, line in enumerate(lines, start=1) if line.strip() == anchor]
    if len(hits) != 1:
        fail(
            f"{case_id}: anchor must match exactly one line in {ref['file']}, "
            f"matched {len(hits)} — {anchor!r}"
        )

    line = hits[0]
    return max(1, line - int(ref["span_before"])), min(len(lines), line + int(ref["span_after"]))


def derive_code_triage(case: dict[str, Any], context: Any) -> dict[str, Any]:
    ref = case["reference"]
    low, high = locate_anchor(context, case["case_id"], ref)

    severity = ref["severity"]
    if severity not in SEVERITIES:
        fail(f"{case['case_id']}: severity {severity!r} is outside the controlled set")

    return {
        "expected_outcome": "answer",
        "root_cause_file": ref["file"],
        "root_cause_line_min": low,
        "root_cause_line_max": high,
        "severity": severity,
    }


def derive_supply_chain(case: dict[str, Any], context: Any) -> dict[str, Any]:
    db, classification = context
    case_id = case["case_id"]
    po_id = case["reference"]["po_id"]

    rows = db.execute(classification, {"po_id": po_id}).fetchall()
    if len(rows) != 1:
        fail(f"{case_id}: classification returned {len(rows)} rows for PO {po_id}, expected 1")

    exception_type, root_cause_code, recommended_action = rows[0]
    if exception_type is None:
        fail(
            f"{case_id}: PO {po_id} classifies to nothing — it is a clean order, "
            "so it cannot be an answerable case"
        )

    return {
        "expected_outcome": "answer",
        "exception_type": exception_type,
        "root_cause_code": root_cause_code,
        "recommended_action": recommended_action,
    }


def select_document(
    documents: list[dict[str, Any]],
    topic: str,
    region: str,
    as_of: str,
    skip: str | None = None,
) -> dict[str, Any] | None:
    """Apply the corpus selection rule. ``skip`` disables one step, so a
    distractor can be shown to correspond to a real reasoning error."""
    live = [d for d in documents if d["topic"] == topic]
    if skip != "draft-exclusion":
        live = [d for d in live if d["status"] == "active"]
    if skip != "effective-dating":
        live = [d for d in live if d["effective_from"] <= as_of]
    if skip != "supersession":
        retired = {d["supersedes"] for d in live if d["supersedes"]}
        live = [d for d in live if d["doc_id"] not in retired]
    if skip != "region-precedence":
        regional = [d for d in live if d["region"] == region]
        live = regional or [d for d in live if d["region"] == "global"]
    if not live:
        return None
    return sorted(live, key=lambda d: (d["effective_from"], d["doc_id"]))[-1]


def derive_doc_research(case: dict[str, Any], context: Any) -> dict[str, Any]:
    ref = case["reference"]
    winner = select_document(context, ref["topic"], ref["region"], ref["as_of"])
    if winner is None:
        fail(
            f"{case['case_id']}: no document governs {ref['topic']}/{ref['region']} "
            f"as at {ref['as_of']}, so it cannot be an answerable case"
        )
    return {
        "expected_outcome": "answer",
        "primary_source_id": winner["doc_id"],
        "answer_code": f"{winner['control_unit']}-{winner['control_value']}",
    }


DERIVERS = {
    "data-sql": derive_data_sql,
    "code-triage": derive_code_triage,
    "supply-chain": derive_supply_chain,
    "doc-research": derive_doc_research,
}


def load_documents(corpus_ref: str) -> list[dict[str, Any]]:
    path = ROOT / corpus_ref / "documents.yaml"
    return yaml.safe_load(path.read_text(encoding="utf-8"))["documents"]


def context_for(workload: str, corpus_ref: str) -> Any:
    if workload == "data-sql":
        return sql_corpus(corpus_ref)
    if workload == "supply-chain":
        classification = (ROOT / corpus_ref / "classification.sql").read_text(encoding="utf-8")
        return sql_corpus(corpus_ref), classification
    if workload == "doc-research":
        return load_documents(corpus_ref)
    return ROOT / corpus_ref / "repo"


def derive(workload: str, case: dict[str, Any], context: Any) -> dict[str, Any]:
    if case["expected_outcome"] == "partial":
        if "reference" in case:
            fail(f"{case['case_id']}: unanswerable case must not carry reference material")
        return {"expected_outcome": "partial", "unmet_criteria": case["unmet_criteria"]}
    return DERIVERS[workload](case, context)


def main() -> int:
    for workload in WORKLOADS:
        for split in SPLITS:
            source = ROOT / "cases" / split / workload / "cases.yaml"
            doc = yaml.safe_load(source.read_text(encoding="utf-8"))
            context = context_for(workload, doc["corpus_ref"])

            keys = {case["case_id"]: derive(workload, case, context) for case in doc["cases"]}
            if len(keys) != len(doc["cases"]):
                fail(f"{workload}/{split}: duplicate case_id")

            target = source.with_name("answer-keys.yaml")
            header = (
                "# GENERATED by freeze/derive_answer_keys.py — do not hand-edit.\n"
                "# Every value here was derived from the corpus at\n"
                f"# {doc['corpus_ref']}. Regenerate rather than correct.\n"
                f"# Split: {split}. Workload: {workload}.\n\n"
            )
            target.write_text(
                header + yaml.safe_dump(keys, sort_keys=True, allow_unicode=True),
                encoding="utf-8",
                newline="\n",
            )
            print(f"{workload}/{split}: {len(keys)} keys -> {target.relative_to(ROOT).as_posix()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
