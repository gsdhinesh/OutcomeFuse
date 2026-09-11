"""supply-chain tools: `order_lookup`, `shipment_trace`,
`supplier_policy_lookup`, `notify_planner`.

**Classification is the work, so no tool classifies.** The corpus ships
`classification.sql`, which is the ladder the answer keys are derived from and
is not agent-visible. These tools return rows: the purchase order, what
happened to it, and the policy text. Deciding which exception class applies,
and why, is left entirely to the agent.

`clause_ref` values are this workload's citable index, built here from the
policies table, so a fabricated clause fails the gate rather than scoring down.
"""

from __future__ import annotations

import sqlite3
from typing import Any, Final

from ..core.contract import Contract
from ..core.verify import CitableEntry, CitableIndex
from .corpus import sql_corpus
from .toolport import ToolError, WorkloadToolPort, required

CORPUS: Final[str] = "cases/corpora/supply-chain/v1"


def _rows(sql: str, parameters: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    db = sql_corpus(CORPUS)
    cursor = db.execute(sql, parameters)
    columns = [c[0] for c in cursor.description]
    return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]


def order_lookup(arguments: dict[str, Any]) -> Any:
    """The purchase order, its part and supplier, plus any raised exception.

    The exception's note says something is wrong. It does not say what class of
    wrong, because that is the task.
    """
    po_id = int(required(arguments, "po_id"))
    orders = _rows(
        """
        SELECT po.po_id, po.ordered_qty, po.order_date, po.promised_date,
               po.buyer_region, p.part_id, p.sku, p.name AS part_name,
               p.lead_time_days, s.supplier_id, s.name AS supplier_name,
               s.country, s.on_time_rate_pct, s.committed_units_per_week,
               pa.agreed_unit_cost_cents, pa.effective_from
          FROM purchase_orders po
          JOIN parts p     ON p.part_id = po.part_id
          JOIN suppliers s ON s.supplier_id = p.supplier_id
          LEFT JOIN price_agreements pa ON pa.part_id = p.part_id
         WHERE po.po_id = ?
        """,
        (po_id,),
    )
    if not orders:
        raise ToolError(f"no purchase order {po_id}")
    return {
        "order": orders[0],
        "invoices": _rows("SELECT * FROM invoices WHERE po_id = ? ORDER BY invoice_id", (po_id,)),
        "exceptions": _rows(
            "SELECT * FROM exceptions WHERE po_id = ? ORDER BY exception_id", (po_id,)
        ),
    }


def shipment_trace(arguments: dict[str, Any]) -> Any:
    """Shipments and receipts for one order, in the order they happened."""
    po_id = int(required(arguments, "po_id"))
    shipments = _rows(
        "SELECT * FROM shipments WHERE po_id = ? ORDER BY shipment_id", (po_id,)
    )
    receipts = _rows(
        "SELECT * FROM receipts WHERE po_id = ? ORDER BY receipt_id", (po_id,)
    )
    if not shipments and not receipts:
        # Distinguished from "no such order": nothing has moved yet is itself
        # an answer, and conflating the two would hide it.
        return {"po_id": po_id, "shipments": [], "receipts": [], "movement": "none"}
    return {
        "po_id": po_id,
        "shipments": shipments,
        "receipts": receipts,
        "movement": "recorded",
    }


def supplier_policy_lookup(arguments: dict[str, Any]) -> Any:
    """Policy clauses. By `clause_ref`, or all of them when none is named."""
    clause_ref = arguments.get("clause_ref")
    if clause_ref is None:
        return {"policies": _rows("SELECT * FROM policies ORDER BY clause_ref")}
    found = _rows("SELECT * FROM policies WHERE clause_ref = ?", (str(clause_ref),))
    if not found:
        raise ToolError(f"no policy clause {clause_ref!r}")
    return {"policy": found[0]}


def notify_planner(arguments: dict[str, Any], *, side_effects: list[str]) -> Any:
    """Declared side-effecting: a human would see this. Never suppressed (FR33).

    Nothing is sent from a synthetic run, but the effect is recorded where the
    conformance probe can see it \u2014 which is the point of the tool existing.
    """
    message = str(required(arguments, "message"))
    side_effects.append(f"notify_planner: {message}")
    return {"delivered": True, "channel": "recorded", "message": message}


def citable_index() -> CitableIndex:
    db: sqlite3.Connection = sql_corpus(CORPUS)
    rows = db.execute(
        "SELECT clause_ref, title, body FROM policies ORDER BY clause_ref"
    ).fetchall()
    from ..core.canon import hash_structure

    entries = tuple(
        CitableEntry(
            id=clause_ref,
            target=f"{CORPUS}#policies/{clause_ref}",
            sha256=hash_structure({"body": body, "clause_ref": clause_ref, "title": title}).sha256,
        )
        for clause_ref, title, body in rows
    )
    return CitableIndex(entries=entries)


def tool_port(contract: Contract) -> WorkloadToolPort:
    side_effects: list[str] = []
    return WorkloadToolPort(
        contract=contract,
        side_effects=side_effects,
        handlers={
            "order_lookup": order_lookup,
            "shipment_trace": shipment_trace,
            "supplier_policy_lookup": supplier_policy_lookup,
            "notify_planner": lambda a: notify_planner(a, side_effects=side_effects),
        },
    )
