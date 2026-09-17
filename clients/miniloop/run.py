"""Run the same loop twice — once governed, once not — and print the difference.

    uv run python clients/miniloop/run.py
    uv run python clients/miniloop/run.py --agent repeats
    uv run python clients/miniloop/run.py --agent hasty --approval denied

Free and deterministic: the agent is not a model, so nothing here costs money
and two runs of the same flags produce the same table.
"""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "clients"))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from miniloop import govern, loop  # noqa: E402
from miniloop.agent import STYLES, MiniAgent  # noqa: E402

DEFAULT_CASE = "sc-c-001"
DEFAULT_RUNS = ROOT / "runs" / "miniloop"


def stamp() -> str:
    """A run id nothing has used before.

    The record store **refuses** to reopen a run id that already exists — an
    append-only log that let a second run continue the first one would be
    worthless — so a demo meant to be run twice has to name its runs apart.
    Deleting the previous log instead would be the wrong instinct to teach.
    """
    return "governed-" + datetime.now(UTC).strftime("%Y%m%dT%H%M%S%f")


def play(
    *,
    case_id: str = DEFAULT_CASE,
    style: str = "careful",
    governed: bool = True,
    approval: str = "approved",
    runs_dir: Path = DEFAULT_RUNS,
    max_turns: int = 8,
    tag: str | None = None,
) -> tuple[loop.Trace, govern.Summary]:
    """One arm, end to end. The site is closed before its summary is read."""
    subject = govern.case(case_id)
    spec = govern.contract()
    agent = MiniAgent(
        po_id=int(subject.prompt_context["po_id"]),
        answer=govern.answer_key(case_id),
        style=style,
        model=spec.models.start if spec.models else "gpt-5-mini",
    )
    site: govern.Governed | govern.Ungoverned = (
        govern.Governed(
            subject, runs_dir=runs_dir, spec=spec, approval=approval, tag=tag or stamp()
        )
        if governed
        else govern.Ungoverned(subject, spec=spec)
    )
    try:
        trace = loop.run(agent, site, case_id=case_id, max_turns=max_turns)
    finally:
        site.close()
    return trace, site.summary(trace)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", default=DEFAULT_CASE)
    parser.add_argument("--agent", default="careful", choices=STYLES)
    parser.add_argument(
        "--approval",
        default="approved",
        choices=["approved", "denied", "no-response", "channel-unavailable"],
        help="what the human says when the contract stops to ask",
    )
    parser.add_argument("--runs-dir", type=Path, default=DEFAULT_RUNS)
    parser.add_argument("--max-turns", type=int, default=8)
    args = parser.parse_args(argv)

    arms = [
        play(
            case_id=args.case,
            style=args.agent,
            governed=governed,
            approval=args.approval,
            runs_dir=args.runs_dir,
            max_turns=args.max_turns,
        )
        for governed in (True, False)
    ]

    print(f"case {args.case}  agent {args.agent}  approval {args.approval}")
    print()
    _table(arms)
    print()
    for line in _reading(arms):
        print(line)
    return 0


ROWS: tuple[tuple[str, str], ...] = (
    ("turns", "turns"),
    ("tool calls proposed", "proposed"),
    ("tool calls executed", "executed"),
    ("suppressed by the governor", "suppressed"),
    ("side effects performed", "side_effects"),
    ("model tokens", "tokens"),
    ("escalations", "escalations"),
    ("terminal reason", "terminal"),
    ("gate verdict", "gate"),
    ("events written", "events"),
    ("log verified", "verified"),
)


def _table(arms: list[tuple[loop.Trace, govern.Summary]]) -> None:
    width = max(len(label) for label, _ in ROWS)
    print(f"{'':<{width}}  {'governed':>14}  {'ungoverned':>14}")
    print(f"{'-' * width}  {'-' * 14}  {'-' * 14}")
    for label, field in ROWS:
        cells = [_cell(trace, summary, field) for trace, summary in arms]
        print(f"{label:<{width}}  {cells[0]:>14}  {cells[1]:>14}")


def _cell(trace: loop.Trace, summary: govern.Summary, field: str) -> str:
    if field == "side_effects":
        return str(len(summary.side_effects))
    # The summary is authoritative wherever it has an opinion: it read the log
    # back, and the trace is only what the loop remembers.
    value = getattr(summary, field, None)
    if value is None and not hasattr(summary, field):
        value = getattr(trace, field)
    if value is None:
        return "none"
    if isinstance(value, bool):
        return "yes" if value else "no"
    return str(value)


def _reading(arms: list[tuple[loop.Trace, govern.Summary]]) -> list[str]:
    """Say what the table means, without saying more than it shows."""
    (_, governed), (_, ungoverned) = arms
    lines = []
    if governed.suppressed:
        lines.append(
            f"The governor withheld {governed.suppressed} of the calls the agent asked for; "
            "the same agent, ungoverned, made all of them."
        )
    extra = len(ungoverned.side_effects) - len(governed.side_effects)
    if extra > 0:
        lines.append(
            f"{extra} more side effect(s) reached the world ungoverned. "
            "Nothing was asked and nobody could have said no."
        )
    lines.append(
        f"The governed run ended {governed.terminal or 'without a terminal reason'} "
        f"and the gate said {governed.gate}. The ungoverned run has no verdict to "
        "report, because no gate exists in it to produce one."
    )
    lines.append(
        f"{governed.events} events were written and the chain "
        f"{'verified' if governed.verified else 'did NOT verify'}. "
        "The ungoverned arm wrote no log at all."
    )
    return lines


if __name__ == "__main__":
    raise SystemExit(main())
