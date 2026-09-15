"""Scripted agents, one per scenario.

The model is scripted because the question is what the **library** does, not
what a model does with a prompt, and a live model would make each scenario
neither reproducible nor free. `ScriptedModelPort` is the library's own
deterministic port, so the transcript is identical whichever arm runs it.

Two things follow, and the report repeats both:

- **This shows the mechanisms work, never how often they fire.** For frequency
  see `measured.py`, which reads the recorded live campaign and reports what
  actually happened there instead.
- **A scenario that has to misbehave says so.** An agent that stalls, cites a
  clause that does not exist, or answers wrongly is authored to do that. It is
  a stimulus for one code path, not a sample of behaviour.

Every correct deliverable below is built from the case's **derived answer key**,
so editing a corpus and re-deriving the keys moves these with it rather than
leaving them asserting last month's answer.
"""

from __future__ import annotations

import json
from typing import Any

from outcomefuse.ports import ToolInvocation

#: A real clause from the frozen corpus. `citation-resolves` accepts nothing else.
CLAUSE = "SP-4.1"
ABSENT_CLAUSE = "SP-99.9"


def call(index: int, tool: str, **arguments: Any) -> ToolInvocation:
    return ToolInvocation(id=f"c{index}", tool=tool, arguments=arguments)


#: What the frozen prompt says to return when the dataset cannot support a
#: disposition. One calibration case is built that way on purpose.
PINNED = ("exception_type", "root_cause_code", "recommended_action")


def is_answerable(key: dict[str, Any]) -> bool:
    return all(field in key for field in PINNED)


def answer(key: dict[str, Any], po_id: int, **overrides: Any) -> str:
    """The deliverable the frozen contract asks for, built from the answer key.

    An unanswerable case pins no values, so there is nothing to build from and
    the honest deliverable is the one the prompt asks for instead. The gate then
    cannot evaluate a reference-backed criterion against a key with no entry, and
    the run fail-closes \u2014 which is what happened to sc-e-008 in the recorded
    campaign, and why that case was excluded from its proof card.
    """
    if not is_answerable(key):
        return json.dumps(
            {"insufficient_evidence": True, "missing": list(key.get("unmet_criteria", []))}
        )
    body = {
        "exception_type": key["exception_type"],
        "root_cause_code": key["root_cause_code"],
        "recommended_action": key["recommended_action"],
        "impacted_orders": [po_id],
        "policy_refs": [{"id": CLAUSE}],
        "est_delay_days": 0,
        "alternatives": [],
    }
    body.update(overrides)
    return json.dumps(body)


def investigate(po_id: int) -> list[Any]:
    """Two turns of ordinary evidence gathering. No call is repeated."""
    return [
        (
            call(0, "order_lookup", po_id=po_id),
            call(1, "shipment_trace", po_id=po_id),
        ),
        (call(2, "supplier_policy_lookup"),),
    ]


def correct(key: dict[str, Any], po_id: int) -> list[Any]:
    """Gather, then answer correctly. The happy path."""
    return [*investigate(po_id), answer(key, po_id)]


def notifies(key: dict[str, Any], po_id: int) -> list[Any]:
    """The agent messages a human before answering.

    `notify_planner` is declared side-effecting, and the frozen contract gates
    it on a human approval clause. It is the only tool in this workload that
    reaches outside the dataset.
    """
    return [
        *investigate(po_id),
        (call(3, "notify_planner", po_id=po_id, message=f"PO {po_id} needs a decision"),),
        answer(key, po_id),
    ]


def wrong_then_right(key: dict[str, Any], po_id: int) -> list[Any]:
    """A wrong classification, then the right one after the gate refuses it.

    The second answer is what escalation buys; without a first answer that fails
    there is nothing for `retry-then-escalate` to do.
    """
    return [*investigate(po_id), _wrong(key, po_id), answer(key, po_id)]


def always_wrong(key: dict[str, Any], po_id: int) -> list[Any]:
    """Wrong every time, so the run runs out of escalations and the ladder ends it."""
    wrong = _wrong(key, po_id)
    return [*investigate(po_id), wrong, wrong, wrong]


def _wrong(key: dict[str, Any], po_id: int) -> str:
    if not is_answerable(key):
        # Nothing to be wrong about: the key pins no value to miss.
        return answer(key, po_id)
    return answer(key, po_id, exception_type=_other(key["exception_type"]))


def cites_nothing_real(key: dict[str, Any], po_id: int) -> list[Any]:
    """A clause that is not in the citable index. The invented-citation failure.

    Answered twice, because the contract escalates on a failed gate and an agent
    with nothing left to say would end the run on an empty turn \u2014 which looks
    like the governor stalling rather than the citation being refused.
    """
    invented = answer(key, po_id, policy_refs=[{"id": ABSENT_CLAUSE}])
    return [*investigate(po_id), invented, invented]


def stalls(key: dict[str, Any], po_id: int, turns: int = 6) -> list[Any]:
    """The same call, over and over, learning nothing.

    Authored to stall. Detecting a stall requires one, and the measured campaign
    never produced it \u2014 see `measured.py`, which reports how rare this is.
    """
    return [(call(0, "order_lookup", po_id=po_id),) for _ in range(turns)]


def burns_turns(key: dict[str, Any], po_id: int, turns: int = 12) -> list[Any]:
    """Distinct calls, forever, never answering. For the budget ceiling."""
    return [
        (call(i, "supplier_policy_lookup", clause_ref=f"SP-{i}"),) for i in range(turns)
    ]


def invents_a_tool(key: dict[str, Any], po_id: int) -> list[Any]:
    """Asks for a tool the contract does not declare, then behaves normally."""
    return [
        (ToolInvocation(id="x0", tool="invoice_lookup", arguments={}),),
        *correct(key, po_id),
    ]


def tool_keeps_failing(key: dict[str, Any], po_id: int, attempts: int = 4) -> list[Any]:
    """Calls a real tool with a required argument missing, over and over.

    An ordinary model mistake rather than a broken tool: `order_lookup` needs a
    `po_id` and raises when it does not get one. Repeated because the question is
    what a *run* of failures costs, not what one does.
    """
    return [
        *[(ToolInvocation(id=f"f{i}", tool="order_lookup", arguments={}),)
          for i in range(attempts)],
        answer(key, po_id),
    ]


#: The six classifications the frozen prompt offers. Used only to pick a wrong one.
_TYPES = (
    "quality-hold",
    "customs-hold",
    "price-variance",
    "allocation-conflict",
    "short-ship",
    "late-shipment",
)


def _other(correct_type: str) -> str:
    return next(t for t in _TYPES if t != correct_type)
