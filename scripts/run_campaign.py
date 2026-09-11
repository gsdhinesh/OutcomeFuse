"""Run a calibration campaign against the live deployment. Costs real money.

Both arms, every case, paired into a proof card. Deliberate and not part of the
suite: a full workload is forty model-driven runs.

**Calibration only, by default.** The evaluation split is sealed until a
preregistration exists, and `load_answer_keys` refuses to open it without one.
A calibration proof card is a dry run of the measurement, not a result: FR66's
admissibility check refuses a calibration campaign as the basis of a headline
claim, and it should.

Run with the venv's interpreter, not `uv run` -- a sync removes openai and
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
from outcomefuse.harness.overhead import OverheadRefused, load_study
from outcomefuse.harness.preregistration import PreregistrationError, load_preregistration
from outcomefuse.harness.proofcard import headline

BASE = "https://outcomefuse-foundry.services.ai.azure.com/openai/v1"
COST_TABLE = "ct-2"

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
    parser.add_argument(
        "--preregistration",
        default=None,
        help="a preregistration version, e.g. prereg-1; required to open the evaluation split",
    )
    parser.add_argument("--runs-dir", default="runs/campaign")
    parser.add_argument(
        "--governed-model",
        default=None,
        help="override the contract's start model, to separate governance from model choice",
    )
    parser.add_argument(
        "--overhead-study",
        default="preregistration/overhead-study-1.yaml",
        help="the study the added-latency counter-metric is read from",
    )
    args = parser.parse_args()

    contract = load_path(Path(f"contracts/{args.workload}.contract.yaml"))

    prereg_hash = None
    prereg = None
    if args.preregistration:
        try:
            prereg = load_preregistration(args.preregistration)
        except PreregistrationError as exc:
            print(f"{exc}")
            return 2
        # The manifest cites the record by content, so a record edited after the
        # fact no longer matches the runs that claimed to be bound by it.
        prereg_hash = prereg.digest().sha256
        print(f"preregistration {args.preregistration} -> {prereg_hash[:16]}...")
        print(
            f"  net tokens >= {prereg.savings.net_token_reduction:.0%}, "
            f"pass rate >= {prereg.quality_target_pass_rate:.0%}, "
            f"minimum {prereg.minimum_case_count} cases\n"
        )
    elif args.split == "evaluation":
        print(
            "the evaluation split is sealed: pass --preregistration. Targets written "
            "after seeing the evaluation answer keys are not predictions."
        )
        return 2

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

    study = None
    try:
        study = load_study(Path(args.overhead_study))
    except OverheadRefused as exc:
        print(f"! {exc}; added-latency will report as not measured\n")

    plan = Plan(
        workload=args.workload,
        split=args.split,
        contract=contract,
        model=AzureFoundryModelPort(base_url=BASE),
        max_output_tokens=MAX_OUTPUT_TOKENS,
        reasoning_effort=REASONING_EFFORT,
        provider_versions=dict(PROVIDER_VERSIONS),
        cost_table=table,
        preregistration_hash=prereg_hash,
        governed_model=args.governed_model,
        minimum_case_count=prereg.minimum_case_count if prereg else 0,
        counter_metric_thresholds=dict(prereg.counter_metric_thresholds) if prereg else {},
        preregistration=prereg,
        overhead_study=study,
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

    cost_split = report.cost_attribution()
    if cost_split:
        print("\ncost saving came from:")
        for name, share in sorted(cost_split.items(), key=lambda kv: -kv[1]):
            print(f"  {name:<16} {share:>7.1%}")

    battery = report.battery
    print(
        f"\nadapter conformance {'passed' if battery and battery.passed else 'FAILED'}"
        f" ({len(battery.results) if battery else 0} scenarios)"
    )
    if battery and not battery.passed:
        for finding in battery.findings:
            print(f"  ! {finding}")

    verdict = report.reportability(headline_claim=args.split == "evaluation")
    if verdict is not None:
        print(f"reportable          {verdict.publishable} ({verdict.independence})")
        for refusal in verdict.refusals:
            print(f"  refused: {refusal}")

    counters = report.counter_metrics()
    print("\ncounter-metrics (FR66)")
    print("\n".join(f"  {line}" for line in counters.rendered().splitlines()))
    if counters.breaches:
        print(f"  ! {len(counters.breaches)} breached its preregistered threshold")

    print(f"\nproof card {card.digest().sha256[:16]}...")
    if args.split != "evaluation":
        print(
            "This is a calibration campaign. It is a dry run of the measurement, "
            "not a result, and cannot support a headline claim."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
