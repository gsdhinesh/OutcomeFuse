"""Run a calibration campaign against the live deployment. Costs real money.

Both arms, every case, paired into a proof card. Deliberate and not part of the
suite: a full workload is forty model-driven runs.

**Calibration only, by default.** The evaluation split is sealed until a
preregistration exists, and `load_answer_keys` refuses to open it without one.
A calibration proof card is a dry run of the measurement, not a result: FR66's
admissibility check refuses a calibration campaign as the basis of a headline
claim, and it should.

Run with the venv's interpreter, not `uv run` — a sync removes openai and
azure-identity, which are deliberately undeclared and imported lazily:

    .venv\\Scripts\\python.exe scripts/run_campaign.py data-sql --cases 3
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from outcomefuse.adapters.model import AzureFoundryModelPort, ModelPortError
from outcomefuse.core.contract import load_path
from outcomefuse.harness.campaign import CampaignError, Plan, run_campaign
from outcomefuse.harness.costs import CostTableError, load_cost_table
from outcomefuse.harness.proofcard import headline

BASE = "https://outcomefuse-foundry.services.ai.azure.com/openai/v1"
COST_TABLE = "ct-1"

# Observed from the service, not guessed. AD-9 requires both arms to declare the
# same versions, so these are pinned here and recorded in both manifests.
PROVIDER_VERSIONS = {
    "gpt-5": "gpt-5-2025-08-07",
    "gpt-5-mini": "gpt-5-mini-2025-08-07",
}

MAX_OUTPUT_TOKENS = 25_000
REASONING_EFFORT = "medium"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workload")
    parser.add_argument("--split", default="calibration")
    parser.add_argument("--cases", type=int, default=None, help="run only the first N")
    parser.add_argument("--preregistration", default=None)
    parser.add_argument("--runs-dir", default="runs/campaign")
    parser.add_argument(
        "--governed-model",
        default=None,
        help="override the contract's start model, to separate governance from model choice",
    )
    args = parser.parse_args()

    contract = load_path(Path(f"contracts/{args.workload}.contract.yaml"))

    table = None
    try:
        table = load_cost_table(COST_TABLE)
        if not table.priced:
            print(
                f"! cost table {COST_TABLE} is unpriced "
                f"({', '.join(table.unpriced_models())}); tokens are counted, "
                "cost is not invented\n"
            )
            table = None
    except CostTableError as exc:
        print(f"! {exc}\n")

    plan = Plan(
        workload=args.workload,
        split=args.split,
        contract=contract,
        model=AzureFoundryModelPort(base_url=BASE),
        max_output_tokens=MAX_OUTPUT_TOKENS,
        reasoning_effort=REASONING_EFFORT,
        provider_versions=dict(PROVIDER_VERSIONS),
        cost_table=table,
        preregistration_hash=args.preregistration,
        governed_model=args.governed_model,
    )

    try:
        report = run_campaign(
            plan, runs_dir=Path(args.runs_dir) / args.workload, max_cases=args.cases
        )
    except (CampaignError, ModelPortError) as exc:
        print(f"the campaign could not run: {exc}")
        return 1

    print(f"{'case':<12} {'baseline':>18}  {'governed':>18}  matched")
    for result in report.results:
        b, g = result.baseline, result.governed
        print(
            f"{result.case_id:<12} "
            f"{b.spend.total_tokens:>7} tok {b.spend.tool_calls:>2} tools  "
            f"{g.spend.total_tokens:>7} tok {g.spend.tool_calls:>2} tools  "
            f"{'yes' if result.baseline_passed and result.governed_passed else 'no':>7}"
            f"  ({'pass' if result.baseline_passed else 'fail'}/"
            f"{'pass' if result.governed_passed else 'fail'})"
        )

    for case_id, why in report.excluded:
        print(f"! excluded {case_id}: {why}")

    if not report.results:
        print("\nno case produced a pair")
        return 1

    try:
        card = report.proof_card()
    except ValueError as exc:
        # No pair passed in both arms. Reporting spend anyway would compare a
        # cheap wrong answer against an expensive right one.
        print(f"\nno proof card: {exc}")
        return 1

    print()
    print(json.dumps(headline(card), indent=2, sort_keys=True))
    print(f"\nproof card {card.digest().sha256[:16]}…")
    if args.split != "evaluation":
        print(
            "This is a calibration campaign. It is a dry run of the measurement, "
            "not a result, and cannot support a headline claim."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
