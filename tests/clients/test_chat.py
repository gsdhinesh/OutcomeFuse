"""The chat client: a new use case, a live approval, and one honest mistake.

The tests that matter here are the ones that would fail if the *integration*
broke rather than the desk: the plug-in point, the verdict table, the live
approval actually blocking, and the claim that a denied action cannot be
reported as done.
"""

from __future__ import annotations

import ast
import json
import threading
from pathlib import Path

import pytest
from chat import agent, desk, govern, loop, session
from console.approval import LiveApprovalPort

from outcomefuse.core.gate import QualityGate
from outcomefuse.workloads import tool_port_for
from outcomefuse.workloads.toolport import ToolError

ROOT = Path(__file__).resolve().parents[2]
DAMAGED = "order 1001 arrived damaged, can we refund it?"


@pytest.fixture
def runs(tmp_path: Path) -> Path:
    return tmp_path / "chat"


def talk(runs: Path, message: str = DAMAGED, **kwargs: object) -> session.Exchange:
    chat = session.Conversation(session="t", runs_dir=runs, **kwargs)  # type: ignore[arg-type]
    return chat.ask(message)


# ------------------------------------------------------------- the plug-in point


def test_a_new_workload_is_refused_by_the_dispatcher_and_built_by_hand() -> None:
    """Why `desk.tool_port` exists at all.

    `tool_port_for` dispatches on the workload name and knows only the four
    frozen ones. A new use case is a handler table, not an edit under `src/`.
    """
    spec = govern.contract()

    with pytest.raises(ToolError):
        tool_port_for(spec)

    port = desk.tool_port(spec)
    assert port.contract.workload == "support-chat"


def test_the_handler_table_must_match_the_contract() -> None:
    """A tool name that surfaces mid-run is the failure that fails a run closed."""
    spec = govern.contract()
    missing = spec.model_copy(update={"tools": spec.tools[:-1]})

    with pytest.raises(ToolError, match="does not match"):
        desk.tool_port(missing)


@pytest.mark.parametrize("module", ["agent.py", "loop.py"])
def test_the_agent_and_the_loop_do_not_import_outcomefuse(module: str) -> None:
    """The governor goes in front of an agent you already have, not inside it.

    Asserted against the syntax tree, so a docstring may *mention* the library
    while a code path may not.
    """
    tree = ast.parse((ROOT / "clients" / "chat" / module).read_text(encoding="utf-8"))
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


# ---------------------------------------------------------------- the contract


def test_every_mandatory_criterion_is_constraint_backed_except_the_citation() -> None:
    """There is no answer key in a live chat, and the contract does not pretend.

    `citation-resolves` is the one reference-backed criterion, and its reference
    is the desk's own policy — built here, not frozen elsewhere.
    """
    spec = govern.contract()
    verifiers = {c.id: c.verifier.type for c in spec.criteria.mandatory if c.verifier}

    assert verifiers["policy-is-cited"] == "citation-resolves"
    assert "exact-match-against-answer-key" not in verifiers.values()


def test_the_gate_says_out_loud_that_it_had_no_reference(runs: Path) -> None:
    exchange = talk(runs)

    assert exchange.summaries[0].gate == "pass"
    assert exchange.summaries[0].qualifier == "constraint-backed"


def test_an_invented_clause_does_not_resolve() -> None:
    """The failure that would most damage a support desk: an authoritative
    sentence resting on a clause nobody can look up."""
    spec = govern.contract()
    answer = {
        "resolution": "refund-issued",
        "order_id": 1001,
        "amount_cents": 7400,
        "policy_refs": [{"id": "RP-99"}],
        "explanation": "x" * 60,
        "next_steps": [],
    }

    verdict = QualityGate().evaluate(spec, answer, citable_index=desk.citable_index())

    assert not verdict.passed
    assert "policy-is-cited" in verdict.unmet


# ------------------------------------------------------------- the approval gate


def test_an_approved_refund_moves_money_and_a_denied_one_does_not(runs: Path) -> None:
    approved = talk(runs / "yes", approval="approved").summaries[0]
    denied = talk(runs / "no", approval="denied").summaries[0]

    assert approved.side_effects == ("issue_refund:1001:7400",)
    assert denied.side_effects == ()
    assert denied.suppressed == 1
    assert denied.gate == "pass", "refusing the action did not cost the answer"


def test_a_denied_action_is_never_reported_as_done(runs: Path) -> None:
    """The mistake this client made, and the sixth disposition that fixed it.

    With five dispositions there was no way to say *decided, and not carried
    out*. The answer read `refund-issued` while the money sat where it was.
    """
    exchange = talk(runs, approval="denied")
    answer = next(f for f in exchange.frames if f["kind"] == "answer")["deliverable"]

    assert answer["resolution"] == "referred-to-a-person"
    assert answer["amount_cents"] == 0
    assert "did not happen" in answer["explanation"]


def test_an_unreachable_approval_channel_is_fail_closed(runs: Path) -> None:
    """Silence is never consent, and the gated call is not made."""
    exchange = talk(runs, approval="channel-unavailable")
    summary = exchange.summaries[0]

    assert summary.terminal == "fail-closed"
    assert summary.side_effects == ()
    assert not exchange.answered


def test_nobody_answering_follows_the_contract_not_a_default(runs: Path) -> None:
    exchange = talk(runs, approval="no-response")

    assert exchange.summaries[0].terminal == "approval-timeout"
    assert exchange.summaries[0].side_effects == ()


def test_the_live_port_really_blocks_until_a_person_answers(runs: Path) -> None:
    """The threading is load-bearing: the run holds, and another thread releases it.

    `request()` is called on the desk's thread and does not return until the
    answer arrives. If it did not block, the tool would run before it was
    authorised and the gate would be decoration.

    The conversation owns `on_ask` — that is how the question reaches the page —
    so the wait is observed through the frame it emits, not by replacing it.
    """
    port = LiveApprovalPort(timeout_seconds=30)
    asked = threading.Event()
    done: list[session.Exchange] = []

    def watch(frame: dict[str, object]) -> None:
        if frame.get("kind") == "approval":
            asked.set()

    chat = session.Conversation(session="live", runs_dir=runs, approval=port)
    worker = threading.Thread(target=lambda: done.append(chat.ask(DAMAGED, watch)))
    worker.start()

    assert asked.wait(timeout=10), "the desk never asked"
    assert not done, "the desk did not wait for the answer"

    port.answer("denied")
    worker.join(timeout=10)

    assert done and done[0].summaries[0].side_effects == ()


# ------------------------------------------------------------- the ungoverned arm


def test_the_ungoverned_arm_spends_the_money_and_writes_nothing(runs: Path) -> None:
    chat = session.Conversation(session="c", runs_dir=runs, approval="denied", compare=True)
    exchange = chat.ask(DAMAGED)
    governed, ungoverned = exchange.summaries

    assert governed.side_effects == ()
    assert ungoverned.side_effects == ("issue_refund:1001:7400",)
    assert ungoverned.terminal is None
    assert ungoverned.gate == govern.NOT_EVALUATED
    assert ungoverned.events is None, "nothing in an ungoverned loop knows the log exists"
    assert governed.events and governed.verified


# ----------------------------------------------------------------- the desk itself


def test_a_message_with_no_order_number_opens_no_run(runs: Path) -> None:
    """One question costs less than a budget, a log and no deliverable."""
    exchange = talk(runs, "my parcel is late")

    assert exchange.clarification
    assert exchange.run_id == ""
    assert exchange.summaries == []


@pytest.mark.parametrize(
    ("message", "resolution", "side_effect"),
    [
        ("where is order 1002?", "in-transit-no-action", False),
        ("refund order 1003", "not-eligible", False),
        ("what about order 1006?", "not-eligible", False),
        ("order 1004 never turned up", "escalate-to-carrier", True),
        ("order 1005 is broken", "replacement-offered", True),
        (DAMAGED, "refund-issued", True),
    ],
)
def test_each_order_reaches_its_disposition(
    runs: Path, message: str, resolution: str, side_effect: bool
) -> None:
    exchange = talk(runs / resolution, message)
    answer = next(f for f in exchange.frames if f["kind"] == "answer")["deliverable"]

    assert answer["resolution"] == resolution
    assert bool(exchange.summaries[0].side_effects) is side_effect
    assert exchange.summaries[0].gate == "pass"


def test_a_status_question_is_answered_with_the_shipment_not_the_refund_policy(
    runs: Path,
) -> None:
    """It used to answer "where is my order" by explaining the refund window,
    and assert the last scan was "today" whatever the record said."""
    exchange = talk(runs, "where is order 1002?")
    answer = next(f for f in exchange.frames if f["kind"] == "answer")["deliverable"]
    ship = desk.SHIPMENTS[1002]

    assert "refund" not in answer["explanation"].lower()
    assert str(ship["tracking"]) in answer["explanation"]
    assert str(ship["last_scan_on"]) in answer["explanation"]
    assert [ref["id"] for ref in answer["policy_refs"]] == ["RP-6"]


def test_the_refund_window_is_raised_only_when_the_customer_raises_money(
    runs: Path,
) -> None:
    exchange = talk(runs, "can I refund order 1002?")
    answer = next(f for f in exchange.frames if f["kind"] == "answer")["deliverable"]

    assert answer["resolution"] == "in-transit-no-action"
    assert "RP-1" in [ref["id"] for ref in answer["policy_refs"]]
    assert "refund window" in answer["explanation"]


@pytest.mark.parametrize("order_id", sorted(desk.ORDERS))
def test_asking_where_something_is_never_spends_money(runs: Path, order_id: int) -> None:
    """The bug this pins reached an approval prompt for $74.00 on a question
    that asked only for a location.

    A lost parcel still raises a carrier claim whoever asks, so the invariant is
    about money rather than about side effects.
    """
    exchange = talk(runs / str(order_id), f"where is order {order_id}?")
    summary = exchange.summaries[0]

    assert not [fx for fx in summary.side_effects if fx.startswith("issue_refund")]
    assert summary.gate == "pass"


def test_the_customer_note_is_evidence_not_a_trigger(runs: Path) -> None:
    """Order 1001's note says two keys are missing. That is a reason to *offer*,
    not a reason to refund on a question that did not ask."""
    asking = talk(runs / "asking", "where is order 1001?")
    answer = next(f for f in asking.frames if f["kind"] == "answer")["deliverable"]

    assert answer["resolution"] == "information-provided"
    assert answer["amount_cents"] == 0
    assert "two keys missing" in answer["explanation"]
    assert asking.summaries[0].side_effects == ()

    # The same note, once the customer does ask, is what makes it refundable.
    asked = talk(runs / "asked", DAMAGED)
    assert asked.summaries[0].side_effects == ("issue_refund:1001:7400",)


def test_the_cap_changes_the_disposition_rather_than_trimming_the_amount(runs: Path) -> None:
    """Order 1005's chair is over the desk's authority. A refund that fitted the
    cap by being smaller would be a worse answer, not a compliant one."""
    exchange = talk(runs, "order 1005 is broken")
    answer = next(f for f in exchange.frames if f["kind"] == "answer")["deliverable"]

    assert desk.ORDERS[1005]["total_cents"] > desk.CAP_CENTS
    assert answer["resolution"] == "replacement-offered"
    assert answer["amount_cents"] == 0


def test_the_policy_tool_applies_no_step_of_the_policy() -> None:
    """Tools expose data, never answers. Every clause comes back, in clause
    order, so the order implies nothing."""
    port = desk.tool_port(govern.contract())
    from outcomefuse.ports import ToolCall

    result = port.invoke(ToolCall(tool="refund_policy_lookup", arguments={}, step_id="s-00"))

    assert [clause["id"] for clause in result.output] == [c["id"] for c in desk.POLICY]


# --------------------------------------------------------------- the verdict table


def test_the_verdict_table_maps_every_action(runs: Path) -> None:
    """INTEGRATION.md §5b, as code. Terminality is read before the action."""
    assert govern._as_reply(_verdict(action="proceed", result={"ok": 1})).how == loop.RAN
    assert govern._as_reply(_verdict(action="proceed", failed=True)).how == loop.FAILED
    assert govern._as_reply(_verdict(action="proceed-with-substitution")).how == loop.CACHED
    assert govern._as_reply(_verdict(action="deny")).how == loop.DENIED

    terminal = govern._as_reply(_verdict(action="terminate", terminal_reason="fail-closed"))
    assert terminal.terminal == "fail-closed"
    assert terminal.allowed is False


def test_a_refusal_is_part_of_the_task_state() -> None:
    """Leave it out and the fuse halts the agent for obeying the governor."""
    brain = agent.DeskAgent(agent.Request(order_id=1001, intent="refund"))
    brain.observe("order_lookup", "{}", data={"status": "delivered"})
    before = brain.state()
    brain.observe("issue_refund", "not allowed: approval-denied", allowed=False)

    assert brain.state() != before
    assert brain.facts() == 1, "a refusal changed the state without adding evidence"


def test_the_transcript_is_json_serialisable(runs: Path) -> None:
    """Every frame goes down a wire. One that cannot be encoded breaks the page
    at the least convenient moment."""
    exchange = talk(runs)

    assert json.loads(json.dumps(exchange.frames, default=str))


def _verdict(**fields: object):
    from outcomefuse.runtime.driver import StepVerdict

    return StepVerdict(decision_reason="because", **fields)  # type: ignore[arg-type]
