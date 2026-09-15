"""How often each mechanism fired when a real model was driving.

The catalogue shows the mechanisms *work*. It cannot show how often they matter,
because every scenario in it was authored to make one of them fire. This reads
the recorded campaign instead — `runs/campaign`, driven by gpt-5 and gpt-5-mini
against the Azure deployment — and counts what actually happened.

The two halves disagree, and that disagreement is the most useful thing in the
report. Do not read a scripted demonstration as a rate.

Nothing here runs a model or spends anything. If `runs/campaign` is absent the
section reports that it is absent, rather than reporting zeros that would look
like measurements.
"""

from __future__ import annotations

import json
import sqlite3
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from outcomefuse.core.record import StoreError, open_store

CAMPAIGN = Path("runs/campaign")
CARDS = Path("runs/cards")


@dataclass(frozen=True)
class Measured:
    runs: int = 0
    tool_calls: int = 0
    repeated_calls: int = 0
    substitutions: int = 0
    denials: int = 0
    escalations: int = 0
    fuse_halts: int = 0
    approvals_sought: int = 0
    terminal_reasons: tuple[tuple[str, int], ...] = ()
    available: bool = True
    why: str = ""

    @property
    def repeat_rate(self) -> str:
        if not self.tool_calls:
            return "no tool calls recorded"
        return f"{self.repeated_calls} in {self.tool_calls:,} proposed calls"


def read_campaign(root: Path = CAMPAIGN, workload: str | None = None) -> Measured:
    if not root.is_dir():
        return Measured(available=False, why=f"{root} does not exist")

    runs = tool_calls = repeats = subs = denials = escalations = fuses = approvals = 0
    terminals: Counter[str] = Counter()

    for path in sorted(root.rglob("*.db")):
        if workload is not None and workload not in path.parts:
            continue
        try:
            with open_store(path, writer=False) as store:
                for run_id in store.run_ids():
                    runs += 1
                    keys: Counter[str] = Counter()
                    for event in store.events(run_id):
                        payload = event.payload or {}
                        if (
                            event.kind in {"decision-proposed", "evidence-requested"}
                            and payload.get("tool")
                        ):
                            tool_calls += 1
                            keys[str(payload.get("canonical_key", ""))] += 1
                        if event.policy_action == "proceed-with-substitution":
                            subs += 1
                        elif event.policy_action == "deny":
                            denials += 1
                        elif event.policy_action == "escalate":
                            escalations += 1
                        if event.decision_reason in {
                            "approval-required",
                            "approval-denied",
                            "approval-timeout",
                        }:
                            approvals += 1
                        if payload.get("fuse"):
                            fuses += 1
                        if event.terminal_reason:
                            terminals[event.terminal_reason] += 1
                    repeats += sum(n - 1 for n in keys.values() if n > 1)
        except (sqlite3.Error, StoreError, ValueError, OSError):
            continue

    return Measured(
        runs=runs,
        tool_calls=tool_calls,
        repeated_calls=repeats,
        substitutions=subs,
        denials=denials,
        escalations=escalations,
        fuse_halts=fuses,
        approvals_sought=approvals,
        terminal_reasons=tuple(terminals.most_common()),
    )


def card(workload: str = "supply-chain", split: str = "evaluation") -> dict:
    """The campaign's own proof card, which carries its digest and its refusals."""
    path = CARDS / f"{split}-{workload}.json"
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def rows(
    measured: Measured, proof: dict, everything: Measured | None = None
) -> list[tuple[str, str]]:
    """The measured section, as label/value pairs the report renders directly."""
    if not measured.available:
        return [("recorded campaign", f"unavailable - {measured.why}")]

    out = [
        ("runs read", f"{measured.runs} sealed supply-chain logs in runs/campaign"),
        ("tool calls proposed", f"{measured.tool_calls:,}"),
        ("identical repeats", measured.repeat_rate),
        ("cache substitutions", str(measured.substitutions)),
        ("calls the governor denied", str(measured.denials)),
        ("approval pauses", str(measured.approvals_sought)),
        ("loop-fuse halts", str(measured.fuse_halts)),
        ("escalations", str(measured.escalations)),
        (
            "how runs ended",
            ", ".join(f"{reason} x{n}" for reason, n in measured.terminal_reasons) or "-",
        ),
    ]
    if everything is not None and everything.available:
        out.append(
            (
                "all four workloads",
                f"{everything.runs} runs, {everything.tool_calls:,} calls, "
                f"{everything.repeated_calls} identical repeat(s), "
                f"{everything.substitutions} substitution(s)",
            )
        )
    if proof:
        head = proof.get("headline", {})
        breaches = ", ".join(proof.get("counter_metric_breaches") or []) or "none"
        out += [
            ("— from the proof card —", f"{proof.get('split')}/{proof.get('workload')}"),
            ("cases", str(proof.get("case_count"))),
            (
                "net token reduction",
                f"{head.get('net_token_reduction', 0):.1%}",
            ),
            ("net cost reduction", f"{head.get('net_cost_reduction', 0):.1%}"),
            (
                "attributed to",
                ", ".join(f"{k} {v:.0%}" for k, v in (head.get("per_mechanism") or {}).items()),
            ),
            ("counter-metric breaches", breaches),
            ("reportable", str(proof.get("reportable"))),
        ]
    return out


def verdict(measured: Measured) -> str:
    """One sentence, derived, for the top of the measured section."""
    if not measured.available:
        return "No recorded campaign was found, so nothing here is measured."
    quiet = [
        name
        for name, count in (
            ("the tool governor's cache", measured.substitutions),
            ("its denials", measured.denials),
            ("the loop fuse", measured.fuse_halts),
            ("the approval gate", measured.approvals_sought),
        )
        if count == 0
    ]
    if not quiet:
        return "Every mechanism fired at least once under a real model."
    return (
        f"Under a real model, {', '.join(quiet)} never fired at all across "
        f"{measured.runs} runs and {measured.tool_calls:,} tool calls. The scripted "
        "scenarios above show those mechanisms work; they say nothing about how often "
        "they are needed."
    )
