"""Read every persisted proof card and show the workloads side by side.

    python scripts/report.py
    python scripts/report.py --split evaluation

Per-workload and never pooled. Pooling would let one workload's result carry
another's, and §8.4 forbids a claim of measured generalization beyond what was
actually completed. A workload whose counter-metrics breached is shown breaching
rather than dropped: choosing what to report after seeing which results are
flattering is the reporting form of amending a freeze once you know which way it
moves the number.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

CARDS = Path("runs/cards")


def _load(split: str, cards_dir: Path) -> list[dict[str, Any]]:
    return [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(cards_dir.glob(f"{split}-*.json"))
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split", default="calibration")
    parser.add_argument("--cards-dir", default=str(CARDS))
    args = parser.parse_args()

    cards = _load(args.split, Path(args.cards_dir))
    if not cards:
        print(f"no {args.split} cards in {args.cards_dir}; run a campaign first")
        return 1

    print(f"{args.split} results, per workload\n")
    head = (
        f"{'workload':<14} {'cases':>5} {'b pass':>7} {'g pass':>7} "
        f"{'tokens':>9} {'cost':>9} {'esc':>6}  reportable"
    )
    print(head)
    print("-" * len(head))

    for card in cards:
        h = card["headline"]
        esc = next(
            (
                r["value"]
                for r in card["counter_metrics"]
                if r["metric"] == "escalation-rate"
            ),
            None,
        )
        flag = "" if not card["counter_metric_breaches"] else "  BREACHED"
        print(
            f"{card['workload']:<14} {h['case_count']:>5} {h['baseline_passes']:>7} "
            f"{h['governed_passes']:>7} {h['net_token_reduction']:>8.1%} "
            f"{h['net_cost_reduction']:>8.1%} {('-' if esc is None else f'{esc:.2f}'):>6}  "
            f"{card['reportable']}{flag}"
        )

    print("\nwhy a workload was refused")
    for card in cards:
        for refusal in card["refusals"]:
            print(f"  {card['workload']}: {refusal}")

    unmeasured = {
        r["metric"]
        for card in cards
        for r in card["counter_metrics"]
        if r["value"] is None
    }
    if unmeasured:
        print("\nnot measured on any workload")
        for metric in sorted(unmeasured):
            print(f"  {metric}")

    print("\nproof cards")
    for card in cards:
        print(f"  {card['workload']:<14} {card['proof_card_sha256'][:16]}...")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
