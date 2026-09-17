"""The desk: a small order book, the published policy, and five tools.

**This is the plug-in point.** `tool_port_for(contract)` dispatches on the
workload name and raises on anything it does not recognise, so a new use case
does not go there — it builds a `WorkloadToolPort` directly from a handler
table. Nothing under `src/` is edited to add a desk, which is the property that
makes the contract the integration surface rather than a configuration file.

The data is invented and small enough to read. It is `synthetic` in the record
spine's sense and the manifest says so; `refuse_persistence` admits nothing
else without an approved governance profile, and none exists.

**The tools expose data and never answers.** `refund_policy_lookup` returns
clauses in clause order and applies no step of the policy; nothing here decides
whether a refund is due. An agent that wants a disposition has to reach one.
"""

from __future__ import annotations

from typing import Any

from outcomefuse.core.canon import hash_structure
from outcomefuse.core.contract import Contract
from outcomefuse.core.verify import CitableIndex
from outcomefuse.core.verify.citable_index import CitableEntry
from outcomefuse.workloads.toolport import ToolError, WorkloadToolPort, required

#: The cap the contract enforces, repeated here only so the seed data stays
#: inside it. The number that governs is the one in the YAML.
CAP_CENTS = 20_000

ORDERS: dict[int, dict[str, Any]] = {
    1001: {
        "order_id": 1001,
        "customer": "R. Okonkwo",
        "item": "wireless keyboard",
        "placed_on": "2026-08-02",
        "delivered_on": "2026-08-06",
        "status": "delivered",
        "total_cents": 7_400,
        "customer_note": "arrived with two keys missing",
    },
    1002: {
        "order_id": 1002,
        "customer": "M. Lindqvist",
        "item": "standing desk mat",
        "placed_on": "2026-09-11",
        "delivered_on": None,
        "status": "in_transit",
        "total_cents": 4_950,
        "customer_note": "",
    },
    1003: {
        "order_id": 1003,
        "customer": "A. Farouk",
        "item": "desk lamp",
        "placed_on": "2026-06-01",
        "delivered_on": "2026-06-05",
        "status": "delivered",
        "total_cents": 3_200,
        "customer_note": "stopped working last week",
    },
    1004: {
        "order_id": 1004,
        "customer": "J. Whitfield",
        "item": "monitor arm",
        "placed_on": "2026-08-28",
        "delivered_on": None,
        "status": "lost",
        "total_cents": 11_900,
        "customer_note": "tracking has not moved in two weeks",
    },
    1005: {
        "order_id": 1005,
        "customer": "S. Bhattacharya",
        "item": "office chair",
        "placed_on": "2026-09-02",
        "delivered_on": "2026-09-09",
        "status": "delivered",
        "total_cents": 24_500,
        "customer_note": "gas lift is broken, box was crushed",
    },
    1006: {
        "order_id": 1006,
        "customer": "T. Nguyen",
        "item": "laptop stand",
        "placed_on": "2026-09-14",
        "delivered_on": None,
        "status": "cancelled",
        "total_cents": 5_600,
        "customer_note": "cancelled before dispatch",
    },
}

SHIPMENTS: dict[int, dict[str, Any]] = {
    1001: {"carrier": "Northwind", "tracking": "NW-88213",
           "last_scan_on": "2026-08-06", "last_event": "delivered"},
    1002: {"carrier": "Northwind", "tracking": "NW-90114",
           "last_scan_on": "2026-09-15", "last_event": "out for delivery"},
    1003: {"carrier": "Beacon", "tracking": "BC-10477",
           "last_scan_on": "2026-06-05", "last_event": "delivered"},
    1004: {"carrier": "Beacon", "tracking": "BC-12009",
           "last_scan_on": "2026-09-01", "last_event": "depot scan"},
    1005: {"carrier": "Northwind", "tracking": "NW-89907",
           "last_scan_on": "2026-09-09", "last_event": "delivered"},
    1006: {"carrier": None, "tracking": None,
           "last_scan_on": None, "last_event": "never dispatched"},
}

#: The published policy. These clause ids are the closed set the
#: `citation-resolves` verifier is handed, so an invented clause is refusable.
POLICY: tuple[dict[str, str], ...] = (
    {
        "id": "RP-1",
        "title": "Refund window",
        "body": "A delivered order may be refunded within 30 days of delivery.",
    },
    {
        "id": "RP-2",
        "title": "Damaged on arrival",
        "body": (
            "An order reported damaged on arrival is refunded or replaced at "
            "the customer's choice, regardless of the refund window."
        ),
    },
    {
        "id": "RP-3",
        "title": "Lost in transit",
        "body": (
            "An order with no carrier movement for ten days is raised with the "
            "carrier as a claim. No refund is issued until the claim closes."
        ),
    },
    {
        "id": "RP-4",
        "title": "Desk authority",
        "body": (
            "The desk may authorise up to 20000 cents on one order. Anything "
            "above that goes to a manager."
        ),
    },
    {
        "id": "RP-5",
        "title": "Cancelled before dispatch",
        "body": (
            "An order cancelled before dispatch is refunded automatically. "
            "The desk takes no action."
        ),
    },
    {
        "id": "RP-6",
        "title": "Status enquiries",
        "body": (
            "A status enquiry is answered from the order and carrier record. The desk "
            "reports what it finds, flags anything the customer may want to raise, and "
            "changes nothing."
        ),
    },
)


def citable_index() -> CitableIndex:
    """AD-7: built here, hashed, bound before any verifier runs."""
    return CitableIndex(
        entries=tuple(
            CitableEntry(
                id=clause["id"],
                target=f"support-chat/policy#{clause['id']}",
                sha256=hash_structure(dict(clause)).sha256,
            )
            for clause in sorted(POLICY, key=lambda c: c["id"])
        )
    )


# ----------------------------------------------------------------- the handlers


def _order(arguments: dict[str, Any]) -> dict[str, Any]:
    order_id = int(required(arguments, "order_id"))
    record = ORDERS.get(order_id)
    if record is None:
        raise ToolError(f"no order {order_id} on this desk")
    return dict(record)


def _shipment(arguments: dict[str, Any]) -> dict[str, Any]:
    order_id = int(required(arguments, "order_id"))
    record = SHIPMENTS.get(order_id)
    if record is None:
        raise ToolError(f"no shipment for order {order_id}")
    return {"order_id": order_id, **record}


def _policy(arguments: dict[str, Any]) -> list[dict[str, str]]:
    """Clauses, in clause order. No step of the policy is applied here."""
    topic = str(arguments.get("topic") or "").strip().lower()
    if not topic:
        return [dict(clause) for clause in POLICY]
    return [
        dict(clause)
        for clause in POLICY
        if topic in clause["title"].lower() or topic in clause["body"].lower()
    ]


def tool_port(spec: Contract) -> WorkloadToolPort:
    """The five tools, with the two that reach outside recording what they did.

    `side_effects` is the port's own list and is handed to the constructor, so
    what the desk really did is observable out of band (AD-15) rather than
    inferred from the decision log. The two views disagreeing is a finding.
    """
    performed: list[str] = []

    def refund(arguments: dict[str, Any]) -> dict[str, Any]:
        order_id = int(required(arguments, "order_id"))
        amount = int(required(arguments, "amount_cents"))
        if order_id not in ORDERS:
            raise ToolError(f"no order {order_id} on this desk")
        if amount <= 0:
            raise ToolError("a refund must be for more than nothing")
        performed.append(f"issue_refund:{order_id}:{amount}")
        return {"refund_id": f"RF-{order_id}", "order_id": order_id, "amount_cents": amount}

    def email(arguments: dict[str, Any]) -> dict[str, Any]:
        order_id = int(required(arguments, "order_id"))
        body = str(required(arguments, "message"))
        if order_id not in ORDERS:
            raise ToolError(f"no order {order_id} on this desk")
        performed.append(f"email_customer:{order_id}")
        return {"sent_to": ORDERS[order_id]["customer"], "characters": len(body)}

    return WorkloadToolPort(
        contract=spec,
        handlers={
            "order_lookup": _order,
            "shipment_status": _shipment,
            "refund_policy_lookup": _policy,
            "issue_refund": refund,
            "email_customer": email,
        },
        side_effects=performed,
    )
