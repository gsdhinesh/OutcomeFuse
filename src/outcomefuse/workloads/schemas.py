"""Tool schemas, as the model is told about them (AD-13, FR33).

The frozen task block names each tool and its arguments in prose but specifies
no call format, and nothing may be added to it — both arms send it
byte-identical. So the invocation protocol is the provider's own, and these
schemas declare it.

**Every schema is keyed by a name the contract declares.** `schemas_for` reads
the contract's tool list and refuses to offer anything outside it, so a model
cannot be handed a tool the contract never admitted. The side-effecting tools
are offered like any other: FR33 exempts them from optimisation-driven
suppression, not from existing.
"""

from __future__ import annotations

from typing import Any, Final

from ..core.contract import Contract
from ..ports.model import ToolSchema
from .toolport import ToolError


def _object(properties: dict[str, Any], required: list[str] | None = None) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": required or [],
        "additionalProperties": False,
    }


_STRING: Final[dict[str, Any]] = {"type": "string"}
_INTEGER: Final[dict[str, Any]] = {"type": "integer"}

#: Descriptions restate what the frozen prose already tells the agent. They add
#: no capability and name no criterion, threshold or answer key.
SCHEMAS: Final[dict[str, ToolSchema]] = {
    schema.name: schema
    for schema in (
        # ---- data-sql -------------------------------------------------------
        ToolSchema(
            name="schema_describe",
            description="Return the schema. With no argument, list every table.",
            parameters=_object({"table": _STRING}),
        ),
        ToolSchema(
            name="sql_query",
            description="Run one read-only SELECT and return its rows.",
            parameters=_object({"sql": _STRING}, ["sql"]),
        ),
        ToolSchema(
            name="sql_execute_write",
            description="Run one mutating statement.",
            parameters=_object({"sql": _STRING}, ["sql"]),
        ),
        # ---- code-triage ----------------------------------------------------
        ToolSchema(
            name="repo_grep",
            description="Search the repository for a regular expression.",
            parameters=_object({"pattern": _STRING, "path": _STRING}, ["pattern"]),
        ),
        ToolSchema(
            name="read_file",
            description="Read a file, optionally between two line numbers.",
            parameters=_object(
                {"path": _STRING, "start": _INTEGER, "end": _INTEGER}, ["path"]
            ),
        ),
        ToolSchema(
            name="symbol_refs",
            description="Every textual mention of a name, definitions included.",
            parameters=_object({"symbol": _STRING}, ["symbol"]),
        ),
        ToolSchema(
            name="run_tests",
            description="Run the test suite for a path.",
            parameters=_object({"path": _STRING}),
        ),
        # ---- doc-research ---------------------------------------------------
        ToolSchema(
            name="corpus_search",
            description=(
                "Find documents by topic, region or body text. Returns every "
                "match in doc_id order; no precedence is applied."
            ),
            parameters=_object({"topic": _STRING, "region": _STRING, "text": _STRING}),
        ),
        ToolSchema(
            name="document_fetch",
            description="Fetch one document in full by its doc_id.",
            parameters=_object({"doc_id": _STRING}, ["doc_id"]),
        ),
        ToolSchema(
            name="passage_extract",
            description="Lines of one document's body that mention a term.",
            parameters=_object({"doc_id": _STRING, "query": _STRING}, ["doc_id", "query"]),
        ),
        # ---- supply-chain ---------------------------------------------------
        ToolSchema(
            name="order_lookup",
            description="A purchase order with its part, supplier, invoices and exceptions.",
            parameters=_object({"po_id": _INTEGER}, ["po_id"]),
        ),
        ToolSchema(
            name="shipment_trace",
            description="Shipments and receipts for one purchase order.",
            parameters=_object({"po_id": _INTEGER}, ["po_id"]),
        ),
        ToolSchema(
            name="supplier_policy_lookup",
            description="A policy clause by clause_ref, or every clause.",
            parameters=_object({"clause_ref": _STRING}),
        ),
        ToolSchema(
            name="notify_planner",
            description="Send a message a planner will see.",
            parameters=_object({"message": _STRING}, ["message"]),
        ),
    )
}


def schemas_for(contract: Contract) -> tuple[ToolSchema, ...]:
    """The schemas for exactly the tools this contract declares."""
    missing = sorted({tool.name for tool in contract.tools} - set(SCHEMAS))
    if missing:
        raise ToolError(f"no schema for declared tools: {missing}")
    return tuple(SCHEMAS[tool.name] for tool in contract.tools)
