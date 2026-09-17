"""The Mode B example, and the two mistakes it made on the way.

`clients/miniloop` exists to execute what INTEGRATION.md §5 documents, so the
tests that matter most are the ones that would fail if the documented mode
stopped working: the verdict table, the fail-closed posture, and the claim that
integrating costs one file.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from miniloop import govern, loop, run
from miniloop.agent import MiniAgent

from outcomefuse.core.record.store import StoreError

CASE = "sc-c-001"
ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def runs(tmp_path: Path) -> Path:
    return tmp_path / "miniloop"


def play(runs: Path, **kwargs: object) -> tuple[loop.Trace, govern.Summary]:
    return run.play(case_id=CASE, runs_dir=runs, tag="governed", **kwargs)  # type: ignore[arg-type]


# ------------------------------------------------- the claim on the front page


@pytest.mark.parametrize("module", ["agent.py", "loop.py"])
def test_the_agent_and_the_loop_do_not_import_outcomefuse(module: str) -> None:
    """Integrating costs one file, and it is not the one your agent lives in.

    Asserted against the syntax tree rather than the text, so a docstring may
    *mention* the library while a code path may not.
    """
    tree = ast.parse((ROOT / "clients" / "miniloop" / module).read_text(encoding="utf-8"))
    imported = [
        name
        for node in ast.walk(tree)
        for name in (
            [alias.name for alias in node.names]
            if isinstance(node, ast.Import)
            else [node.module or ""]
            if isinstance(node, ast.ImportFrom)
            else []
        )
    ]
    assert not [name for name in imported if name.startswith("outcomefuse")]


# --------------------------------------------------------------- the four runs


def test_the_ordinary_run_passes_the_gate_and_seals_a_verified_log(runs: Path) -> None:
    trace, summary = play(runs, style="careful")

    assert trace.answered
    assert summary.gate == "pass"
    assert summary.terminal == "stop-sufficient"
    assert summary.sealed and summary.verified
    assert summary.events and summary.events > 0


def test_the_stall_is_suppressed_and_then_halted(runs: Path) -> None:
    governed, governed_summary = play(runs, style="repeats")
    ungoverned, ungoverned_summary = play(runs, style="repeats", governed=False)

    assert governed_summary.executed == 1, "the identical call is asked for once"
    assert ungoverned_summary.executed == ungoverned.proposed, "nothing stops it"
    assert governed_summary.terminal == "halt-no-progress"
    assert ungoverned_summary.terminal is None
    # The saving is the turns nobody had to pay for. A cached reply is not a new
    # fact, so the second identical turn is the one the fuse stops on; counting
    # it as evidence left the turn cap as the only thing that ever fired.
    assert governed.turns == 2 < ungoverned.turns
    assert governed_summary.tokens < ungoverned_summary.tokens / 2


def test_a_denied_approval_stops_the_side_effect_without_losing_the_answer(
    runs: Path,
) -> None:
    """The headline. Nothing else in this client demonstrates both at once."""
    governed, governed_summary = play(runs, style="careful", approval="denied")
    _, ungoverned_summary = play(runs, style="careful", governed=False)

    assert governed_summary.side_effects == ()
    assert ungoverned_summary.side_effects != ()
    assert governed_summary.gate == "pass", "denying the message did not cost the answer"
    assert governed.denied == 1


def test_an_unreachable_approval_channel_is_fail_closed(runs: Path) -> None:
    """AD-20. Silence is never consent, and the gated call is not made."""
    _, summary = play(runs, style="careful", approval="channel-unavailable")

    assert summary.terminal == "fail-closed"
    assert summary.side_effects == ()


def test_a_wrong_answer_is_escalated_before_anything_terminal(runs: Path) -> None:
    _, summary = play(runs, style="hasty")

    assert summary.gate == "fail"
    assert summary.escalations == 1, "the contract directs one retry"
    assert summary.terminal == "returned-partial"


def test_the_ungoverned_arm_has_no_verdict_to_report(runs: Path) -> None:
    """Not an omission by this client. There is nothing in it that would know."""
    _, summary = play(runs, style="careful", governed=False)

    assert summary.terminal is None
    assert summary.gate == govern.NOT_EVALUATED
    assert summary.events is None
    assert summary.sealed is False
    assert summary.metered is False


# ------------------------------------------------ the two mistakes, pinned down


def test_a_refusal_is_part_of_the_task_state(runs: Path) -> None:
    """Leave it out and the fuse halts the agent for obeying the governor.

    Measured before the fix: the careful agent under `--approval denied` ended
    `halt-no-progress` at turn 2 and never reached the gate.
    """
    agent = MiniAgent(po_id=4102, answer=govern.answer_key(CASE))
    agent.observe("order_lookup", "status=released")
    before = agent.state()
    agent.observe("notify_planner", "not allowed: approval-denied", allowed=False)

    assert agent.state() != before
    assert agent.facts() == 1, "a refusal changed the state without adding evidence"


def test_the_answering_turn_is_not_put_to_the_fuse(runs: Path) -> None:
    """An agent that just concluded has not stalled; it spent the turn writing."""
    observed: list[int] = []

    class Counting(govern.Ungoverned):
        def progress(self, *, state: object, facts: int) -> str | None:
            observed.append(facts)
            return None

    subject = govern.case(CASE)
    agent = MiniAgent(po_id=int(subject.prompt_context["po_id"]), answer=govern.answer_key(CASE))
    trace = loop.run(agent, Counting(subject), case_id=CASE, max_turns=8)

    assert trace.answered
    assert len(observed) == trace.turns - 1


# ------------------------------------------------------- why run ids are unique


def test_reopening_a_run_id_is_refused(runs: Path) -> None:
    """Why `run.stamp()` exists. An append-only log that let a second run
    continue the first one would be worthless."""
    play(runs, style="careful")

    with pytest.raises(StoreError, match="already exists"):
        play(runs, style="careful")


def test_the_verdict_table_maps_every_action_this_client_can_see() -> None:
    """INTEGRATION.md §5b, as code. Terminality is read before the action."""
    assert govern._as_reply(_verdict(action="proceed", result={"ok": 1})).how == loop.RAN
    assert govern._as_reply(_verdict(action="proceed", failed=True)).how == loop.FAILED
    assert govern._as_reply(_verdict(action="proceed-with-substitution")).how == loop.CACHED
    assert govern._as_reply(_verdict(action="deny")).how == loop.DENIED

    terminal = govern._as_reply(_verdict(action="terminate", terminal_reason="fail-closed"))
    assert terminal.terminal == "fail-closed"
    assert terminal.allowed is False


def _verdict(**fields: object):
    from outcomefuse.runtime.driver import StepVerdict

    return StepVerdict(decision_reason="because", **fields)  # type: ignore[arg-type]
