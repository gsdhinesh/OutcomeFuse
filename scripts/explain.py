"""Explain the results in plain English, for someone who has never seen this repo.

    .venv\\Scripts\\python.exe scripts/explain.py
    .venv\\Scripts\\python.exe scripts/explain.py --workload supply-chain

Every task is run twice: once by a plain agent with no budget and no quality
gate, and once through OutcomeFuse. This prints what each one did, which tools
it called, what it spent, and whether the answer was judged correct.

It reads the sealed run logs and the proof cards. It computes no new figures --
`scripts/report.py` is the formal report, and two paths to one number is two
things that can disagree.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from outcomefuse.core.record import StoreError, open_store
from outcomefuse.harness.cases import load_case_set

WORKLOAD_IS = {
    "supply-chain": "Look at a flagged purchase order, work out what went wrong, "
    "and recommend what to do about it, citing supplier policy.",
    "data-sql": "Answer a question about a business database by querying it.",
    "code-triage": "Find the bug behind a reported failure in a code repository "
    "and describe the fix.",
    "doc-research": "Answer a policy question from a document corpus, citing the "
    "documents the answer rests on.",
}

ARM_IS = {
    "baseline": "plain agent, no budget, no quality gate, uses the big model",
    "governed": "OutcomeFuse: budget, quality gate, starts on the cheaper model",
}


def tools_called(events) -> list[str]:
    """Tool names in call order. Empty for runs recorded before they were logged."""
    seen = []
    for event in events:
        if event.kind not in {"decision-proposed", "evidence-requested"}:
            continue
        tool = (event.payload or {}).get("tool")
        if tool:
            seen.append(str(tool))
    return seen


def read_run(path: Path, run_id: str) -> dict | None:
    try:
        with open_store(path, writer=False) as store:
            if run_id not in store.run_ids():
                return None
            events = store.events(run_id)
    except (sqlite3.Error, StoreError, ValueError, OSError):
        return None

    tokens = sum(e.tokens_consumed or 0 for e in events)
    gate = [e for e in events if e.kind == "gate-verdict"]
    terminal = [e.terminal_reason for e in events if e.terminal_reason]
    escalations = [e for e in events if e.policy_action == "escalate"]
    return {
        "tools": tools_called(events),
        "tokens": tokens,
        "verdict": gate[-1].gate_verdict if gate else None,
        "when": (gate[-1].payload or {}).get("when") if gate else None,
        "stopped": terminal[-1] if terminal else "?",
        "escalated": len(escalations),
    }


STOPPED_BECAUSE = {
    "stop-sufficient": "it judged the answer good enough",
    "halt-exhausted": "it ran out of budget",
    "halt-no-progress": "it stopped making progress",
    "returned-partial": "it gave up and returned what it had",
    "fail-closed": "a governing part failed, so it refused to continue",
}


def explain_case(runs_dir: Path, workload: str, case_id: str, task: str) -> None:
    arms = {}
    for arm in ("baseline", "governed"):
        found = read_run(runs_dir / workload / f"{case_id}-{arm}.db", f"{case_id}-{arm}")
        if found:
            arms[arm] = found
    if len(arms) != 2:
        return

    print(f"\n  {case_id}")
    print(f"    task: {task.strip().splitlines()[0][:96]}")
    for arm, run in arms.items():
        tools = ", ".join(run["tools"]) if run["tools"] else "not recorded in this run"
        right = {"pass": "judged CORRECT", "fail": "judged WRONG"}.get(
            run["verdict"], "never checked"
        )
        print(f"    {arm:<9} {run['tokens']:>7,} tokens   {right}")
        print(f"      tools used : {tools}")
        if run["stopped"] != "?":
            print(f"      stopped    : {STOPPED_BECAUSE.get(run['stopped'], run['stopped'])}")
        elif arm == "baseline":
            print("      stopped    : by itself. Nothing was governing it, so there is")
            print("                   no reason on record -- that is the point of the arm")
        if run["escalated"]:
            print(
                f"      note       : gave up on the cheap model {run['escalated']}x "
                "and retried on the expensive one"
            )
        if arm == "governed" and run["when"] == "at-submission":
            print(
                "      note       : the quality gate only looked AFTER the agent had "
                "already stopped, so it confirmed the answer rather than causing it"
            )

    base, gov = arms["baseline"]["tokens"], arms["governed"]["tokens"]
    if base:
        diff = (base - gov) / base
        word = "cheaper" if diff > 0 else "MORE EXPENSIVE"
        print(f"    => governed was {abs(diff):.0%} {word} in tokens")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workload", default=None, help="default: every workload")
    parser.add_argument("--split", default="evaluation")
    parser.add_argument("--runs-dir", default="runs/campaign")
    parser.add_argument("--cards-dir", default="runs/cards")
    parser.add_argument("--cases", type=int, default=3, help="how many cases to spell out")
    args = parser.parse_args()

    print("WHAT THIS IS")
    print("  Every task is done twice, by two different setups, and compared.")
    for arm, what in ARM_IS.items():
        print(f"    {arm:<9} {what}")
    print("  The hope: the governed one is cheaper and just as correct.")

    # Agent runs are stochastic, so a second pass over the same frozen cases
    # gives different numbers. Reporting whichever came out better is choosing
    # the result after seeing it, which is the one thing none of this permits.
    if args.cards_dir != "runs/cards" or args.runs_dir != "runs/campaign":
        print()
        print("  ! THIS IS A RE-MEASUREMENT, NOT THE REPORTED RESULT.")
        print("    The reported result is the first evaluation pass, in runs/cards.")
        print("    A later pass exists to show mechanism detail the earlier runs did")
        print("    not record. Its numbers are not a second chance at the first.")

    workloads = [args.workload] if args.workload else sorted(WORKLOAD_IS)
    runs_dir = Path(args.runs_dir)

    for workload in workloads:
        print(f"\n\n{'=' * 78}\n{workload.upper()}  --  {WORKLOAD_IS.get(workload, '')}")
        try:
            cases = load_case_set(workload, args.split).cases
        except Exception as exc:  # noqa: BLE001 - a missing case set is reported, not fatal
            print(f"  cannot read the case set: {exc}")
            continue
        for case in cases[: args.cases]:
            explain_case(runs_dir, workload, case.case_id, case.prompt)

        card_path = Path(args.cards_dir) / f"{args.split}-{workload}.json"
        if not card_path.exists():
            print("\n  OVERALL: no result. Not one task was answered correctly by both")
            print("  setups, so there was nothing comparable to measure.")
            continue
        card = json.loads(card_path.read_text(encoding="utf-8"))
        head = card["headline"]
        tok, cost = head["net_token_reduction"], head["net_cost_reduction"]
        print(f"\n  OVERALL, across {card['case_count']} comparable tasks:")
        print(
            f"    correct answers : {head['baseline_passes']} of {card['case_count']} "
            f"plain, {head['governed_passes']} of {card['case_count']} governed"
        )
        print(
            f"    tokens          : governed used {abs(tok):.0%} "
            f"{'FEWER' if tok > 0 else 'MORE'}"
        )
        print(
            f"    money           : governed cost {abs(cost):.0%} "
            f"{'LESS' if cost > 0 else 'MORE'}"
        )
        for name, share in sorted((card["cost_attribution"] or {}).items(), key=lambda kv: -kv[1]):
            plain = {
                "model-routing": "simply using the cheaper model",
                "agent-stopped-unaided": "the agent stopping by itself, unaided",
            }.get(name, name)
            print(f"      {share:>6.0%} of the money saved came from {plain}")
        if card["refusals"]:
            print("\n    CAN THIS BE PUBLISHED? No. Because:")
            for refusal in card["refusals"]:
                print(f"      - {refusal}")
    print(
        "\n\nRules that decide publishable were written down BEFORE any of this ran, "
        "so they could not be bent afterwards to fit the answer."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
