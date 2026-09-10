"""Check case-set integrity before the freeze.

Distinct from contract validation (E3), which checks that a contract names
registered verifiers. This checks that the *cases* are sound: that ids and keys
agree, that every split carries the unanswerable stratum, and above all that
every distractor actually discriminates.

A trap that returns the correct answer by coincidence of the corpus tests
nothing while looking rigorous. That has already happened once here, in the
first draft of ds-e-007, and was caught only by checking. This makes the check
mandatory rather than remembered.

Workload-specific rules:

* ``data-sql``    — a distractor declares ``wrong_sql``, which must return
  something other than the correct answer, or ``discriminates: false``.
* ``code-triage`` — a wrong reading is a wrong file or line, which has no
  executable form, so distractors are declared non-discriminating and carry a
  reason. The anchor is checked to match exactly one line, and the derived span
  is checked to contain it.
* ``supply-chain`` — a distractor names the field it targets and the wrong
  value, which must differ from the derived one. The case's purchase order is
  checked to classify to something, since a clean order cannot be an
  answerable case.
* ``doc-research`` — a distractor names the selection-rule step a wrong reading
  skips. Selection is re-run with that step disabled and the result must
  differ, which proves the trap corresponds to a real reasoning error rather
  than an arbitrary wrong string.

Run: uv run --with pyyaml python freeze/check_cases.py
"""

from __future__ import annotations

import sqlite3
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import yaml

from derive_answer_keys import RULE_STEPS, load_documents, select_document, sql_corpus

ROOT = Path(__file__).resolve().parent.parent
SPLITS = ("calibration", "evaluation")
WORKLOADS = ("data-sql", "code-triage", "supply-chain", "doc-research")
DIFFICULTIES = {"direct", "multi-hop", "distractor-heavy", "unanswerable"}
SEVERITIES = {"blocker", "major", "minor", "cosmetic"}
KEYED_FIELDS = {"exception_type", "root_cause_code", "recommended_action"}


def scalar(db: sqlite3.Connection, sql: str) -> Any:
    return db.execute(sql).fetchone()[0]


def check_data_sql(case: dict[str, Any], key: dict[str, Any], db: Any, out: list[str]) -> None:
    cid = case["case_id"]
    if case["expected_outcome"] == "answer" and key.get("units") != case["units"]:
        out.append(f"{cid}: key units disagree with case")

    for distractor in case.get("distractors") or []:
        did = f"{cid}/{distractor['id']}"
        if distractor.get("discriminates") is False:
            continue
        if "wrong_sql" not in distractor:
            out.append(f"{did}: needs wrong_sql, or discriminates: false with a reason")
            continue
        if scalar(db, case["reference"]["value_sql"]) == scalar(db, distractor["wrong_sql"]):
            out.append(
                f"{did}: does not discriminate — the wrong reading returns the same "
                "answer as the correct one, so the trap tests nothing"
            )


def check_code_triage(case: dict[str, Any], key: dict[str, Any], repo: Any, out: list[str]) -> None:
    cid = case["case_id"]
    if case["expected_outcome"] != "answer":
        return

    ref = case["reference"]
    target = repo / ref["file"]
    if not target.is_file():
        out.append(f"{cid}: corpus has no file {ref['file']!r}")
        return

    lines = target.read_text(encoding="utf-8").splitlines()
    anchor = ref["anchor"].strip()
    hits = [n for n, line in enumerate(lines, start=1) if line.strip() == anchor]
    if len(hits) != 1:
        out.append(
            f"{cid}: anchor matches {len(hits)} lines in {ref['file']}, must match exactly 1"
        )
        return

    if not key["root_cause_line_min"] <= hits[0] <= key["root_cause_line_max"]:
        out.append(f"{cid}: derived span does not contain the anchor line — regenerate keys")
    if key["root_cause_file"] != ref["file"]:
        out.append(f"{cid}: key file disagrees with case")
    if key["severity"] not in SEVERITIES:
        out.append(f"{cid}: severity {key['severity']!r} is outside the controlled set")

    for distractor in case.get("distractors") or []:
        if distractor.get("discriminates") is not False:
            out.append(
                f"{cid}/{distractor['id']}: a code-triage wrong reading has no executable "
                "form, so it must declare discriminates: false with a reason"
            )
        elif not distractor.get("detail"):
            out.append(f"{cid}/{distractor['id']}: non-discriminating distractor needs a reason")


def check_supply_chain(case: dict[str, Any], key: dict[str, Any], ctx: Any, out: list[str]) -> None:
    cid = case["case_id"]
    if case["expected_outcome"] != "answer":
        return

    db, _ = ctx
    for distractor in case.get("distractors") or []:
        did = f"{cid}/{distractor['id']}"
        if distractor.get("discriminates") is False:
            if not distractor.get("detail"):
                out.append(f"{did}: non-discriminating distractor needs a reason")
            continue
        field = distractor.get("wrong_field")
        if field not in KEYED_FIELDS or "wrong_sql" not in distractor:
            out.append(f"{did}: needs wrong_sql plus a wrong_field from {sorted(KEYED_FIELDS)}")
            continue
        if scalar(db, distractor["wrong_sql"]) == key[field]:
            out.append(
                f"{did}: does not discriminate — the wrong reading of {field} equals "
                "the derived value, so the trap tests nothing"
            )


def check_doc_research(case: dict[str, Any], key: dict[str, Any], ctx: Any, out: list[str]) -> None:
    cid = case["case_id"]
    if case["expected_outcome"] != "answer":
        return

    ref = case["reference"]
    for distractor in case.get("distractors") or []:
        did = f"{cid}/{distractor['id']}"
        if distractor.get("discriminates") is False:
            if not distractor.get("detail"):
                out.append(f"{did}: non-discriminating distractor needs a reason")
            continue
        step = distractor.get("skip_step")
        if step not in RULE_STEPS:
            out.append(f"{did}: needs skip_step from {sorted(RULE_STEPS)}")
            continue
        wrong = select_document(ctx, ref["topic"], ref["region"], ref["as_of"], skip=step)
        if wrong is not None and wrong["doc_id"] == key["primary_source_id"]:
            out.append(
                f"{did}: does not discriminate — skipping {step} still selects "
                f"{key['primary_source_id']}, so the trap tests nothing"
            )


CHECKERS = {
    "data-sql": check_data_sql,
    "code-triage": check_code_triage,
    "supply-chain": check_supply_chain,
    "doc-research": check_doc_research,
}


def context_for(workload: str, corpus_ref: str) -> Any:
    if workload == "data-sql":
        return sql_corpus(corpus_ref)
    if workload == "supply-chain":
        classification = (ROOT / corpus_ref / "classification.sql").read_text(encoding="utf-8")
        return sql_corpus(corpus_ref), classification
    if workload == "doc-research":
        return load_documents(corpus_ref)
    return ROOT / corpus_ref / "repo"


def check_split(workload: str, split: str, out: list[str]) -> None:
    folder = ROOT / "cases" / split / workload
    doc = yaml.safe_load((folder / "cases.yaml").read_text(encoding="utf-8"))
    keys = yaml.safe_load((folder / "answer-keys.yaml").read_text(encoding="utf-8"))
    context = context_for(workload, doc["corpus_ref"])
    where = f"{workload}/{split}"

    if doc["data_class"] != "synthetic":
        out.append(f"{where}: data_class must be synthetic, got {doc['data_class']!r}")

    ids = [case["case_id"] for case in doc["cases"]]
    if len(set(ids)) != len(ids):
        out.append(f"{where}: duplicate case_id")
    if set(keys) != set(ids):
        out.append(f"{where}: answer keys and cases disagree on ids — regenerate")
        return

    for case in doc["cases"]:
        cid = case["case_id"]
        key = keys[cid]

        if case["difficulty"] not in DIFFICULTIES:
            out.append(f"{cid}: unknown difficulty {case['difficulty']!r}")
        if key.get("expected_outcome") != case["expected_outcome"]:
            out.append(f"{cid}: key outcome disagrees with case")
        if case["expected_outcome"] == "partial" and not case.get("unmet_criteria"):
            out.append(f"{cid}: unanswerable case must name its unmet criteria")
        if case["difficulty"] == "distractor-heavy" and not case.get("distractors"):
            out.append(f"{cid}: distractor-heavy case declares no distractors")

        CHECKERS[workload](case, key, context, out)

    mix = Counter(case["difficulty"] for case in doc["cases"])
    total = len(doc["cases"])
    if not mix["unanswerable"]:
        out.append(f"{where}: no unanswerable cases — false sufficiency cannot be measured")
    spread = " ".join(f"{k}={v} ({v / total:.0%})" for k, v in sorted(mix.items()))
    print(f"{where}: n={total}  {spread}")


def main() -> int:
    failures: list[str] = []
    for workload in WORKLOADS:
        for split in SPLITS:
            check_split(workload, split, failures)

    if failures:
        print("\nFAILED:")
        for failure in failures:
            print(f"  - {failure}")
        return 1
    print("\nAll case-set checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
