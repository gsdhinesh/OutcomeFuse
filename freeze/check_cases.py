"""Check case-set integrity before the freeze.

Distinct from contract validation (E3), which checks that a contract names
registered verifiers. This checks that the *cases* are sound: that ids and keys
agree, that the difficulty mix is declared, and above all that every distractor
actually discriminates.

A trap that returns the correct value by coincidence of the data tests nothing
while looking rigorous. That has already happened once here, in the first draft
of ds-e-007, and was caught only by checking. This makes the check mandatory
rather than remembered.

Run: uv run --with pyyaml python freeze/check_cases.py
"""

from __future__ import annotations

import sqlite3
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent
SPLITS = ("calibration", "evaluation")
WORKLOADS = ("data-sql",)
DIFFICULTIES = {"direct", "multi-hop", "distractor-heavy", "unanswerable"}


def corpus(corpus_ref: str) -> sqlite3.Connection:
    path = ROOT / corpus_ref
    db = sqlite3.connect(":memory:")
    db.executescript((path / "schema.sql").read_text(encoding="utf-8"))
    db.executescript((path / "seed.sql").read_text(encoding="utf-8"))
    return db


def scalar(db: sqlite3.Connection, sql: str) -> Any:
    return db.execute(sql).fetchone()[0]


def check_split(workload: str, split: str, failures: list[str]) -> None:
    folder = ROOT / "cases" / split / workload
    doc = yaml.safe_load((folder / "cases.yaml").read_text(encoding="utf-8"))
    keys = yaml.safe_load((folder / "answer-keys.yaml").read_text(encoding="utf-8"))
    db = corpus(doc["corpus_ref"])
    where = f"{workload}/{split}"

    if doc["data_class"] != "synthetic":
        failures.append(f"{where}: data_class must be synthetic, got {doc['data_class']!r}")

    ids = [case["case_id"] for case in doc["cases"]]
    if len(set(ids)) != len(ids):
        failures.append(f"{where}: duplicate case_id")
    if set(keys) != set(ids):
        failures.append(f"{where}: answer keys and cases disagree on ids — regenerate")

    for case in doc["cases"]:
        cid = case["case_id"]
        key = keys.get(cid, {})

        if case["difficulty"] not in DIFFICULTIES:
            failures.append(f"{cid}: unknown difficulty {case['difficulty']!r}")
        if key.get("expected_outcome") != case["expected_outcome"]:
            failures.append(f"{cid}: key outcome disagrees with case")
        if case["expected_outcome"] == "answer" and key.get("units") != case["units"]:
            failures.append(f"{cid}: key units disagree with case")
        if case["expected_outcome"] == "partial" and not case.get("unmet_criteria"):
            failures.append(f"{cid}: unanswerable case must name its unmet criteria")

        if case["difficulty"] == "distractor-heavy" and not case.get("distractors"):
            failures.append(f"{cid}: distractor-heavy case declares no distractors")

        for distractor in case.get("distractors") or []:
            did = f"{cid}/{distractor['id']}"
            if distractor.get("discriminates") is False:
                continue
            if "wrong_sql" not in distractor:
                failures.append(f"{did}: needs wrong_sql, or discriminates: false with a reason")
                continue
            right = scalar(db, case["reference"]["value_sql"])
            wrong = scalar(db, distractor["wrong_sql"])
            if right == wrong:
                failures.append(
                    f"{did}: does not discriminate — the wrong reading returns {wrong!r}, "
                    "the same as the correct one, so the trap tests nothing"
                )

    mix = Counter(case["difficulty"] for case in doc["cases"])
    total = len(doc["cases"])
    if not mix["unanswerable"]:
        failures.append(f"{where}: no unanswerable cases — false sufficiency cannot be measured")
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
