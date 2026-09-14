"""Run the refund desk with OutcomeFuse plugged in and plugged out, and compare.

    .venv\\Scripts\\python.exe clients/refund_desk/run_desk.py
    .venv\\Scripts\\python.exe clients/refund_desk/run_desk.py --approval denied

No model is called and nothing is spent: the agent is scripted through the
library's own `ScriptedModelPort`, so both arms see a byte-identical transcript
and every difference below is attributable to the wiring and to nothing else.

The `--approval` flag drives the one port a governed run cannot do without. Its
four settings are the four things a human approval channel can do, and each
takes the run somewhere different -- which is the part of the library most worth
seeing before trusting it with a payment.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "clients"))

from refund_desk.compose import adjudicate, load_contract  # noqa: E402
from refund_desk.desk import case_by_id, cases  # noqa: E402
from refund_desk.loop import RunOutcome  # noqa: E402

COLUMNS = ("", "plugged out", "plugged in")


def _row(label: str, left: object, right: object) -> str:
    return f"  {label:<22}{left!s:<22}{right}"


def _money(outcome: RunOutcome) -> str:
    return "; ".join(outcome.side_effects) if outcome.side_effects else "none"


def _report(outcome_out: RunOutcome, outcome_in: RunOutcome) -> None:
    print(_row(*COLUMNS))
    print(_row("model turns", outcome_out.turns, outcome_in.turns))
    print(_row("tokens", outcome_out.total_tokens, outcome_in.total_tokens))
    print(_row("tool calls proposed", outcome_out.proposed, outcome_in.proposed))
    print(_row("tool calls executed", outcome_out.invoked, outcome_in.invoked))
    print(_row("withheld", len(outcome_out.withheld), len(outcome_in.withheld)))
    for reason in outcome_in.withheld:
        print(f"  {'':<22}{'':<22}- {reason}")
    print(_row("gate", _verdict(outcome_out), _verdict(outcome_in)))
    print(_row("terminal reason", outcome_out.terminal or "-", outcome_in.terminal or "-"))
    print(_row("run seal", (outcome_out.seal or "-")[:16], (outcome_in.seal or "-")[:16]))
    print(f"  {'money moved':<22}plugged out: {_money(outcome_out)}")
    print(f"  {'':<22}plugged in:  {_money(outcome_in)}")


def _verdict(outcome: RunOutcome) -> str:
    if outcome.deliverable is None:
        # Not "fail": the gate never ran, and reporting a verdict nothing
        # produced would put a judgement in the table that nothing made.
        return outcome.parse_failure or "not evaluated"
    return "pass" if outcome.passed else "fail"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", default=None, help="case id; defaults to all of them")
    parser.add_argument(
        "--approval",
        default="approved",
        choices=("approved", "denied", "no-response", "channel-unavailable"),
        help="what the human approval channel does when the refund is proposed",
    )
    parser.add_argument("--runs-dir", default="runs/refund-desk")
    args = parser.parse_args()

    contract = load_contract()
    selected = (case_by_id(args.case),) if args.case else cases()

    print(f"contract  {contract.contract_id} v{contract.version} ({contract.workload})")
    print(f"approval  {args.approval}")
    print(f"runs      {args.runs_dir}\n")

    withheld = 0
    for case in selected:
        pair = adjudicate(
            case, contract=contract, runs_dir=args.runs_dir, approval=args.approval
        )
        withheld += len(pair.governed.withheld)
        print(f"{case.case_id}  {case.request}")
        _report(pair.ungoverned, pair.governed)
        print()

    if withheld == 0:
        print("the governor withheld nothing; on this workload it bought no calls back")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
