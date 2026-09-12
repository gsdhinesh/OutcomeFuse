"""Assemble the submission script from the evaluation cards and one real log.

The division of labour is the point. A human writes the narration in
`submission/narration.yaml` and nothing else. Every number, label, digest and
permission comes from artifacts, and anything the artifacts do not support is
refused here rather than quietly narrated.

    .venv\\Scripts\\python.exe scripts/build_submission.py
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from outcomefuse.core.record import open_store
from outcomefuse.harness.preregistration import load_preregistration
from outcomefuse.harness.reportability import Reportability
from outcomefuse.submission.figures import Figure, Provenance, required_labels
from outcomefuse.submission.script import (
    Beat,
    CardRef,
    SubmissionRefused,
    build_submission,
    evidence_of_mechanism,
)

# Which card field backs each figure key, and what it is measured in. A key
# absent from here cannot be put in the narration file at all, which stops a
# number being invented in the one file a human edits.
FIGURES: dict[str, tuple[str, str]] = {
    "net_token_fraction": ("net_token_reduction", "net"),
    "net_cost_fraction": ("net_cost_reduction", "net"),
    "gross_token_fraction": ("gross_token_reduction", "gross"),
    "baseline_passes": ("baseline_passes", "count"),
    "governed_passes": ("governed_passes", "count"),
}


def load_cards(cards_dir: Path, split: str) -> dict[str, dict[str, Any]]:
    cards: dict[str, dict[str, Any]] = {}
    for path in sorted(cards_dir.glob(f"{split}-*.json")):
        card = json.loads(path.read_text(encoding="utf-8"))
        cards[card["workload"]] = card
    return cards


def make_figure(spec: dict[str, Any], card: dict[str, Any], *, split: str) -> Figure:
    key = spec["key"]
    if key not in FIGURES:
        raise SubmissionRefused(f"{key!r} is not a figure any card supplies: {sorted(FIGURES)}")
    field, basis = FIGURES[key]
    if field not in card["headline"]:
        raise SubmissionRefused(f"{key!r} is not on the {card['workload']} card")

    provenance = Provenance(
        artifact="proof-card",
        digest=card["proof_card_sha256"],
        run_ids=tuple(card["case_ids"]),
        split=split,
        # A proof card is a paired comparison, and the figure is the governed
        # arm's result against its baseline. Nothing here is projected from a
        # shadow run, which is what the mode literal exists to catch.
        mode="governed",
        case_count=card["case_count"],
        workload=card["workload"],
    )
    return Figure(
        key=key,
        value=card["headline"][field],
        basis=basis,
        # Only an evaluation-set number may lead. Calibration set the ruler.
        role="claim" if split == "evaluation" else "illustration",
        provenance=provenance,
        # Derived from the run, never typed in: there is no gateway meter, so
        # every figure here is self-reported and has to say so.
        labels=required_labels(provenance, gateway_metered=False),
        headline=bool(spec.get("headline", False)),
    )


def pick_run(runs_dir: Path) -> tuple[Any, str]:
    """A governed run whose log opens with its manifest and records decisions.

    Baseline runs are sealed and readable too, and they hold no policy at all,
    so taking the first sealed run finds one that cannot demonstrate anything.
    The demonstration has to come from the arm that governs.
    """
    for path in sorted(runs_dir.rglob("*.db"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            with open_store(path, writer=False) as store:
                for run_id in store.run_ids():
                    events = store.events(run_id)
                    seal = store.seal(run_id)
                    if not seal or not events or events[0].kind != "run-manifest":
                        continue
                    if any(e.kind == "decision-recorded" and e.policy_action for e in events):
                        return events, seal
        except (sqlite3.Error, ValueError, OSError) as err:
            print(f"  skipped {path.name}: {err}", file=sys.stderr)
            continue
    raise SubmissionRefused(f"no sealed governed run under {runs_dir}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--narration", default="submission/narration.yaml")
    parser.add_argument("--cards-dir", default="runs/cards")
    parser.add_argument("--runs-dir", default="runs")
    parser.add_argument("--split", default="evaluation")
    parser.add_argument("--preregistration", default="prereg-1")
    parser.add_argument("--out", default="submission/SCRIPT.md")
    args = parser.parse_args()

    narration = yaml.safe_load(Path(args.narration).read_text(encoding="utf-8"))
    cards = load_cards(Path(args.cards_dir), args.split)
    if not cards:
        print(f"no {args.split} cards under {args.cards_dir}; run the campaign first")
        return 1

    events, seal = pick_run(Path(args.runs_dir))
    mechanism = evidence_of_mechanism(events, seal=seal)

    beats: list[Beat] = []
    for spec in narration["beats"]:
        figures = []
        for fig_spec in spec.get("figures") or []:
            workload = fig_spec["workload"]
            if workload not in cards:
                raise SubmissionRefused(
                    f"beat {spec['name']!r} cites {workload!r}, which has no "
                    f"{args.split} card"
                )
            figures.append(make_figure(fig_spec, cards[workload], split=args.split))
        beats.append(
            Beat(
                name=spec["name"],
                seconds=spec["seconds"],
                says=" ".join(spec["says"].split()),
                shows=tuple(spec.get("shows") or []),
                figures=tuple(figures),
            )
        )

    # A headline is only permitted if the workload behind it survived its own
    # counter-metrics. The harness decides that; this script only reports it.
    headline_workloads = {
        f.provenance.workload for beat in beats for f in beat.figures if f.headline
    }
    reportability = None
    if headline_workloads:
        card = cards[sorted(headline_workloads)[0]]
        reportability = Reportability(
            # `publishable` is derived, not set: admissible and unrefused. The
            # card already carries the harness's own verdict and its reasons, so
            # this reconstructs them rather than re-deciding anything.
            admissible=bool(card["reportable"]),
            independence=card["independence"] or "self-reported",
            labels=(),
            refusals=tuple(card["refusals"])
            + tuple(
                f"counter-metric {m} breached its preregistered threshold"
                for m in card["counter_metric_breaches"]
            ),
        )

    try:
        submission = build_submission(
            beats,
            mechanism=mechanism,
            workloads_completed=tuple(sorted(cards)),
            cards=[
                CardRef(sha256=c["proof_card_sha256"], run_seals=tuple(c["run_seals"]))
                for c in cards.values()
            ],
            preregistration=load_preregistration(args.preregistration),
            reportability=reportability,
        )
    except SubmissionRefused as refused:
        print("SUBMISSION REFUSED\n")
        for line in str(refused).split("; "):
            print(f"  - {line}")
        print(
            "\nThis is the apparatus working. Fix the claim or drop the figure; "
            "do not loosen the check."
        )
        return 1

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(submission.render() + "\n", encoding="utf-8")
    print(submission.render())
    print(f"\n{submission.seconds}s, digest {submission.digest().sha256[:16]}...")
    print(f"written to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
