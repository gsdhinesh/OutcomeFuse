"""Run state is a fold over the log (AD-2).

Ledger position, quality state, iteration count and decision history are
*derived*, never held as an independent mutable truth. Anything not in the log
did not happen and may not be claimed — so this module is the only place run
state comes from, and folding twice must give the same answer.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from pydantic import BaseModel, ConfigDict

from .events import (
    DECISION_EVENT_ORDER,
    EVIDENCE_CYCLE_MAY_FOLLOW,
    TERMINAL_KINDS,
)
from .models import Event, LedgerState


class RunState(BaseModel):
    """What the log folds to. Comparable by value."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    run_id: str
    sealed: bool = False
    terminal_reason: str | None = None
    quality_state: str = "not-evaluated"
    iterations: int = 0
    decisions: tuple[str, ...] = ()
    reasons: tuple[str, ...] = ()
    tokens_spent: int = 0
    ledger: LedgerState | None = None
    degraded: tuple[str, ...] = ()
    gate_verdicts: tuple[str, ...] = ()


class OrderViolation(ValueError):
    """The event stream departs from AD-2's canonical order."""


def fold(events: Iterable[Event]) -> RunState:
    """Derive run state. Pure: same events in, same state out."""
    events = list(events)
    if not events:
        raise ValueError("a run with no events has no state")
    if events[0].kind != "run-manifest":
        raise OrderViolation("the first event of a run must be its manifest")

    state: dict[str, object] = {
        "run_id": events[0].run_id,
        "sealed": False,
        "terminal_reason": None,
        "quality_state": "not-evaluated",
        "iterations": 0,
        "tokens_spent": 0,
        "ledger": None,
        "decisions": [],
        "reasons": [],
        "degraded": [],
        "gate_verdicts": [],
    }

    for event in events:
        if event.run_id != state["run_id"]:
            raise OrderViolation("fold received events from more than one run")
        if event.kind == "decision-recorded":
            state["iterations"] = int(state["iterations"]) + 1
            if event.policy_action:
                state["decisions"].append(event.policy_action)  # type: ignore[union-attr]
            if event.decision_reason:
                state["reasons"].append(event.decision_reason)  # type: ignore[union-attr]
        if event.kind == "gate-verdict" and event.gate_verdict:
            state["quality_state"] = event.gate_verdict
            state["gate_verdicts"].append(event.gate_verdict)  # type: ignore[union-attr]
        if event.kind == "degraded":
            mechanism = str(event.payload.get("mechanism", "unknown"))
            state["degraded"].append(mechanism)  # type: ignore[union-attr]
        if event.tokens_consumed:
            state["tokens_spent"] = int(state["tokens_spent"]) + event.tokens_consumed
        if event.ledger is not None:
            state["ledger"] = event.ledger
        if event.terminal_reason is not None:
            if state["terminal_reason"] is not None:
                raise OrderViolation("terminal_reason is recorded at most once per run")
            state["terminal_reason"] = event.terminal_reason
        if event.kind in TERMINAL_KINDS:
            state["sealed"] = True

    return RunState(
        run_id=str(state["run_id"]),
        sealed=bool(state["sealed"]),
        terminal_reason=state["terminal_reason"],  # type: ignore[arg-type]
        quality_state=str(state["quality_state"]),
        iterations=int(state["iterations"]),
        decisions=tuple(state["decisions"]),  # type: ignore[arg-type]
        reasons=tuple(state["reasons"]),  # type: ignore[arg-type]
        tokens_spent=int(state["tokens_spent"]),
        ledger=state["ledger"],  # type: ignore[arg-type]
        degraded=tuple(state["degraded"]),  # type: ignore[arg-type]
        gate_verdicts=tuple(state["gate_verdicts"]),  # type: ignore[arg-type]
    )


def check_order(events: Sequence[Event]) -> list[str]:
    """Report departures from AD-2's fixed per-decision order.

    Returns findings rather than raising, because a driver under test wants all
    of them at once rather than the first.
    """
    findings: list[str] = []
    expected = list(DECISION_EVENT_ORDER)
    position = 0
    last_kind = "run-manifest"

    for event in events[1:]:
        kind = event.kind
        if kind in {"evidence-requested", "evidence-observed"}:
            if kind == "evidence-requested" and last_kind not in (
                EVIDENCE_CYCLE_MAY_FOLLOW | {"evidence-observed", "decision-proposed"}
            ):
                findings.append(f"seq {event.seq}: an evidence cycle may not follow {last_kind!r}")
            if kind == "evidence-observed" and last_kind != "evidence-requested":
                findings.append(
                    f"seq {event.seq}: evidence-observed must follow evidence-requested"
                )
            last_kind = kind
            continue
        if kind in {"degraded", "gate-verdict", "run-closed", "run-abandoned"}:
            last_kind = kind
            continue
        if kind not in expected:
            findings.append(f"seq {event.seq}: {kind!r} is not part of a decision")
            continue
        wanted = expected[position % len(expected)]
        if kind != wanted:
            findings.append(f"seq {event.seq}: expected {wanted!r}, got {kind!r}")
            position = expected.index(kind)
        position += 1
        last_kind = kind

    return findings


def replay_equivalent(left: RunState, right: RunState) -> list[str]:
    """AD-2's replay equivalence, as a list of differences.

    Identical decision sequence, identical reason codes, identical terminal
    reason, identical ledger totals. **Byte equality of model output is not
    required and is never claimed** — so it is not compared here.
    """
    differences: list[str] = []
    if left.decisions != right.decisions:
        differences.append(f"decision sequence: {left.decisions} vs {right.decisions}")
    if left.reasons != right.reasons:
        differences.append(f"reason codes: {left.reasons} vs {right.reasons}")
    if left.terminal_reason != right.terminal_reason:
        differences.append(
            f"terminal reason: {left.terminal_reason!r} vs {right.terminal_reason!r}"
        )
    if left.tokens_spent != right.tokens_spent:
        differences.append(f"tokens spent: {left.tokens_spent} vs {right.tokens_spent}")
    if left.ledger != right.ledger:
        differences.append("ledger totals differ")
    return differences
