"""The refund desk: its data, its tools, its policy and its cases.

A client's domain, kept in the client (AD-17). Nothing under `src/` imports
this, and the wheel does not ship it.

Two rules are borrowed from the frozen workloads because they are what make the
measurement mean anything, not because a test enforces them here:

- **Tools expose data, never answers.** `refund_policy_lookup` returns every
  clause sorted by id, so the ordering implies nothing about which clause
  governs. Nothing in this module decides whether a refund is owed; that is the
  task, and a tool that did it would be scoring the agent's homework for it.
- **Both wirings get the same tools.** One handler table, one dataset. Nothing
  done here can flatter the governor without flattering the ungoverned loop
  identically.

The answer keys state a *judgement* (which disposition, which reason code) and
derive every *number* from the dataset, so editing an order's total cannot
silently leave a key asserting the old one.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Final

from outcomefuse.core.canon import hash_structure
from outcomefuse.core.contract import Contract
from outcomefuse.core.verify import CitableEntry, CitableIndex
from outcomefuse.ports import ToolInvocation
from outcomefuse.workloads.toolport import WorkloadToolPort, required

RESTOCKING_FEE: Final[float] = 0.15

ORDERS: Final[dict[str, dict[str, Any]]] = {
    "ORD-4417": {
        "order_id": "ORD-4417",
        "customer_id": "CUS-8812",
        "category": "electronics",
        "total": 189.00,
        "currency": "GBP",
        "placed_on": "2026-08-02",
        "delivered_on": "2026-08-06",
        "packaging_opened": True,
        "requested_on": "2026-08-11",
    },
    "ORD-4418": {
        "order_id": "ORD-4418",
        "customer_id": "CUS-9034",
        "category": "homeware",
        "total": 74.50,
        "currency": "GBP",
        "placed_on": "2026-08-20",
        "delivered_on": None,
        "packaging_opened": False,
        "requested_on": "2026-09-02",
    },
    "ORD-4419": {
        "order_id": "ORD-4419",
        "customer_id": "CUS-7701",
        "category": "furniture",
        "total": 249.00,
        "currency": "GBP",
        "placed_on": "2026-05-01",
        "delivered_on": "2026-05-09",
        "packaging_opened": True,
        "requested_on": "2026-08-13",
    },
}

SHIPMENTS: Final[dict[str, dict[str, Any]]] = {
    "ORD-4417": {
        "carrier": "Northgate",
        "tracking": "NG-99120",
        "state": "delivered",
        "events": ["2026-08-03 collected", "2026-08-06 delivered, signed for"],
    },
    "ORD-4418": {
        "carrier": "Northgate",
        "tracking": "NG-99871",
        "state": "loss-confirmed",
        "events": [
            "2026-08-21 collected",
            "2026-08-24 depot scan missing",
            "2026-08-29 carrier confirmed loss, claim NG-C-441",
        ],
    },
    "ORD-4419": {
        "carrier": "Ravelin",
        "tracking": "RV-20077",
        "state": "delivered",
        "events": ["2026-05-05 collected", "2026-05-09 delivered, left with neighbour"],
    },
}

#: The published policy. The clause bodies describe conditions; none of them
#: names an order, because applying a clause to an order is the task.
POLICY: Final[dict[str, dict[str, str]]] = {
    "RP-1": {
        "title": "Standard return window",
        "body": "A refund may be issued in full where the request is made within "
        "30 days of delivery.",
    },
    "RP-2": {
        "title": "Damaged on arrival",
        "body": "A refund is issued in full where the goods arrived damaged, "
        "regardless of the standard window.",
    },
    "RP-3": {
        "title": "Opened electronics",
        "body": "Electronics returned with the packaging opened are refunded net "
        "of a 15% restocking fee.",
    },
    "RP-4": {
        "title": "Lost in transit",
        "body": "A refund is issued in full once the carrier has confirmed the "
        "consignment is lost. The standard window does not apply.",
    },
    "RP-5": {
        "title": "Outside the window",
        "body": "A request made more than 30 days after delivery is refused "
        "unless another clause applies.",
    },
}


# --------------------------------------------------------------------- tools


def _order(arguments: dict[str, Any]) -> Any:
    order_id = str(required(arguments, "order_id"))
    record = ORDERS.get(order_id)
    if record is None:
        return {"found": False, "order_id": order_id}
    return {"found": True, **record}


def _shipment(arguments: dict[str, Any]) -> Any:
    order_id = str(required(arguments, "order_id"))
    record = SHIPMENTS.get(order_id)
    if record is None:
        return {"found": False, "order_id": order_id}
    return {"found": True, "order_id": order_id, **record}


def _policy(_arguments: dict[str, Any]) -> Any:
    """Every clause, sorted by id. No ranking, no filtering, no selection."""
    return {
        "clauses": [
            {"id": clause_id, **POLICY[clause_id]} for clause_id in sorted(POLICY)
        ]
    }


def _issue_refund(side_effects: list[str]) -> Any:
    def handler(arguments: dict[str, Any]) -> Any:
        order_id = str(required(arguments, "order_id"))
        amount = float(required(arguments, "amount"))
        reason_code = str(required(arguments, "reason_code"))
        # Synthetic: nothing is paid. The effect is recorded where the
        # out-of-band probe can see it, which is the point of the tool existing.
        side_effects.append(f"issue_refund: {order_id} {amount:.2f} {reason_code}")
        return {"posted": True, "order_id": order_id, "amount": amount}

    return handler


def tool_port(contract: Contract) -> WorkloadToolPort:
    """The desk's tools, built directly rather than via `tool_port_for`.

    `outcomefuse.workloads.tool_port_for` dispatches on `contract.workload` and
    has never heard of `refund-desk`. Constructing the port here is the plug-in
    point: a new use case needs a handler table, not an edit to the library.
    """
    side_effects: list[str] = []
    return WorkloadToolPort(
        contract=contract,
        handlers={
            "order_lookup": _order,
            "shipment_status": _shipment,
            "refund_policy_lookup": _policy,
            "issue_refund": _issue_refund(side_effects),
        },
        side_effects=side_effects,
    )


def citable_index() -> CitableIndex:
    """The closed set of clause ids a decision may cite (AD-7)."""
    return CitableIndex(
        entries=tuple(
            CitableEntry(
                id=clause_id,
                target=f"policy/refunds/v1#{clause_id}",
                sha256=hash_structure({"id": clause_id, **POLICY[clause_id]}).sha256,
            )
            for clause_id in sorted(POLICY)
        )
    )


# --------------------------------------------------------------------- cases


@dataclass(frozen=True)
class DeskCase:
    """One request, the answer it should reach, and the agent that reaches it."""

    case_id: str
    order_id: str
    request: str
    answer_key: dict[str, Any]
    #: What the scripted agent does, turn by turn. A tuple of invocations is a
    #: tool turn; a string is the deliverable.
    script: list[Any]


def _call(index: int, tool: str, **arguments: Any) -> ToolInvocation:
    return ToolInvocation(id=f"c{index}", tool=tool, arguments=arguments)


def _deliverable(
    order_id: str, decision: str, amount: float, reason_code: str, refs: list[str]
) -> str:
    return json.dumps(
        {
            "order_id": order_id,
            "decision": decision,
            "refund_amount": round(amount, 2),
            "reason_code": reason_code,
            "policy_refs": [{"id": ref} for ref in refs],
        }
    )


def _script(order_id: str, deliverable: str, *, refund: dict[str, Any] | None) -> list[Any]:
    """A four-turn agent that re-reads the order it already has.

    The repeat is the realistic part, not a contrivance: an agent carrying its
    whole transcript forward still re-fetches what it is unsure it retained, and
    the re-fetch is byte-identical. It is also the only behaviour on which the
    governed and ungoverned wirings can differ *without* either of them being
    wrong, which is what makes it worth measuring.
    """
    third: tuple[ToolInvocation, ...] = (_call(4, "order_lookup", order_id=order_id),)
    if refund is not None:
        third = (*third, _call(5, "issue_refund", order_id=order_id, **refund))
    return [
        (
            _call(0, "order_lookup", order_id=order_id),
            _call(1, "shipment_status", order_id=order_id),
        ),
        (
            _call(2, "refund_policy_lookup"),
            _call(3, "order_lookup", order_id=order_id),
        ),
        third,
        deliverable,
    ]


def _partial_case() -> DeskCase:
    order = ORDERS["ORD-4417"]
    amount = round(float(order["total"]) * (1 - RESTOCKING_FEE), 2)
    return DeskCase(
        case_id="rd-001",
        order_id="ORD-4417",
        request="Customer opened the packaging and wants to return the headphones "
        "delivered on 2026-08-06. They asked on 2026-08-11.",
        answer_key={
            "decision": "approve-partial",
            "reason_code": "restocking-fee-applied",
            "order_total": order["total"],
        },
        script=_script(
            "ORD-4417",
            _deliverable(
                "ORD-4417", "approve-partial", amount, "restocking-fee-applied", ["RP-1", "RP-3"]
            ),
            refund={"amount": amount, "reason_code": "restocking-fee-applied"},
        ),
    )


def _full_case() -> DeskCase:
    order = ORDERS["ORD-4418"]
    amount = float(order["total"])
    return DeskCase(
        case_id="rd-002",
        order_id="ORD-4418",
        request="Customer never received the parcel and the carrier says it is lost. "
        "They asked on 2026-09-02.",
        answer_key={
            "decision": "approve-full",
            "reason_code": "carrier-loss-confirmed",
            "order_total": order["total"],
        },
        script=_script(
            "ORD-4418",
            _deliverable(
                "ORD-4418", "approve-full", amount, "carrier-loss-confirmed", ["RP-4"]
            ),
            refund={"amount": amount, "reason_code": "carrier-loss-confirmed"},
        ),
    )


def _deny_case() -> DeskCase:
    order = ORDERS["ORD-4419"]
    return DeskCase(
        case_id="rd-003",
        order_id="ORD-4419",
        request="Customer wants to return a bookcase delivered on 2026-05-09. "
        "They asked on 2026-08-13.",
        answer_key={
            "decision": "deny",
            "reason_code": "outside-return-window",
            "order_total": order["total"],
        },
        script=_script(
            "ORD-4419",
            _deliverable("ORD-4419", "deny", 0.0, "outside-return-window", ["RP-5"]),
            refund=None,
        ),
    )


def cases() -> tuple[DeskCase, ...]:
    return (_partial_case(), _full_case(), _deny_case())


def case_by_id(case_id: str) -> DeskCase:
    for case in cases():
        if case.case_id == case_id:
            return case
    raise KeyError(f"no such case: {case_id!r}")
