"""data-sql tools: `schema_describe`, `sql_query`, `sql_execute_write`.

The agent writes its own SQL. That is the workload, so the query tool does not
interpret, rewrite or "help" — it runs what it was given against a read-only
connection and returns rows.

Read-only is the engine's `query_only` pragma rather than a regex over the
query text. The difference matters: one is a guarantee, the other is a guess
that a sufficiently creative query wins. The row cap and the statement limit
are about keeping one bad query from eating a run, not about safety.
"""

from __future__ import annotations

import sqlite3
from typing import Any, Final

from ..core.contract import Contract
from .corpus import sql_corpus, writable_copy
from .toolport import ToolError, WorkloadToolPort, required

CORPUS: Final[str] = "cases/corpora/data-sql/v1"

#: A result larger than this is a query that should have aggregated. Returning
#: it would blow the context window the workload is measured on.
MAX_ROWS: Final[int] = 500
#: SQLite's own instruction budget. An agent can write a cartesian join by
#: accident, and without this the run hangs instead of failing.
MAX_STEPS: Final[int] = 2_000_000


def _rows(db: sqlite3.Connection, sql: str) -> dict[str, Any]:
    steps = {"n": 0}

    def budget() -> int:
        steps["n"] += 1
        return 1 if steps["n"] > MAX_STEPS // 1000 else 0

    db.set_progress_handler(budget, 1000)
    try:
        cursor = db.execute(sql)
        columns = [c[0] for c in cursor.description] if cursor.description else []
        rows = cursor.fetchmany(MAX_ROWS + 1)
    except sqlite3.Error as exc:
        raise ToolError(f"the query failed: {exc}") from exc
    finally:
        db.set_progress_handler(None, 1000)

    truncated = len(rows) > MAX_ROWS
    return {
        "columns": columns,
        "rows": [list(r) for r in rows[:MAX_ROWS]],
        "row_count": min(len(rows), MAX_ROWS),
        "truncated": truncated,
    }


def schema_describe(arguments: dict[str, Any]) -> Any:
    db = sql_corpus(CORPUS)
    table = arguments.get("table")
    if table is None:
        listing = db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        return {"tables": [r[0] for r in listing]}
    ddl = db.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name = ?", (table,)
    ).fetchone()
    if ddl is None:
        raise ToolError(f"no table named {table!r}")
    return {"table": table, "ddl": ddl[0]}


def sql_query(arguments: dict[str, Any]) -> Any:
    sql = str(required(arguments, "sql")).strip()
    if not sql:
        raise ToolError("an empty query answers nothing")
    if sql.rstrip(";").count(";"):
        # One statement per call, so a result maps to a request. The connection
        # is read-only regardless, so this is about legibility, not safety.
        raise ToolError("one statement per call")
    return _rows(sql_corpus(CORPUS), sql)


def sql_execute_write(arguments: dict[str, Any], *, side_effects: list[str]) -> Any:
    """Side-effecting by declaration, and genuinely so, against a scratch copy.

    It exists so the conformance battery can prove the governor never caches,
    deduplicates or optimisation-denies it. No case requires it.
    """
    sql = str(required(arguments, "sql")).strip()
    db = writable_copy(CORPUS)
    try:
        cursor = db.execute(sql)
        db.commit()
        changed = cursor.rowcount
    except sqlite3.Error as exc:
        raise ToolError(f"the write failed: {exc}") from exc
    finally:
        db.close()
    side_effects.append(f"sql_execute_write: {sql}")
    return {"rows_changed": changed, "scratch": True}


def tool_port(contract: Contract) -> WorkloadToolPort:
    side_effects: list[str] = []
    return WorkloadToolPort(
        contract=contract,
        side_effects=side_effects,
        handlers={
            "schema_describe": schema_describe,
            "sql_query": sql_query,
            "sql_execute_write": lambda a: sql_execute_write(a, side_effects=side_effects),
        },
    )
