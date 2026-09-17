"""The wire. Stdlib only: `ThreadingHTTPServer` plus server-sent events.

    uv run python clients/chat/server.py
    -> http://127.0.0.1:8770

No web framework, and not only because `uv` cannot fetch one on this network. A
chat that streams a governed run needs two things a framework would hide: each
request on its own thread, so the run can **block** on the approval gate while
another request carries the answer to it; and frames written and flushed the
moment they happen, so the page shows the agent working rather than a spinner
and a verdict.

The threading is load-bearing. `/ask` runs the loop inline on its own thread and
blocks inside `LiveApprovalPort.request`; `/answer` arrives on a different
thread and puts the decision on the queue that releases it. One thread and the
demo would deadlock the first time the desk tried to spend money.
"""

from __future__ import annotations

import json
import sys
import traceback
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "clients"))

from console.approval import LiveApprovalPort  # noqa: E402

from chat import desk, govern, session  # noqa: E402

PAGE = Path(__file__).resolve().parent / "app.html"
HOST = "127.0.0.1"
#: Not 8765. The console lives there, and a stale process on a reused port
#: serves the previous client without saying so.
PORT = 8770

#: session id -> the port holding that conversation's run while a person decides.
_PORTS: dict[str, LiveApprovalPort] = {}
_CHATS: dict[str, session.Conversation] = {}


def frame(payload: dict[str, Any]) -> bytes:
    """One server-sent event. Two newlines end it; a missing one hangs the reader."""
    return f"data: {json.dumps(payload, default=str)}\n\n".encode()


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt: str, *args: Any) -> None:
        return

    #: Whether a response has already started. Once it has, a failure can only
    #: be reported as an SSE frame; a 500 would be a second set of headers.
    headers_sent = False

    def end_headers(self) -> None:
        super().end_headers()
        self.headers_sent = True

    # ------------------------------------------------------------------ routing

    def do_GET(self) -> None:
        route = urlparse(self.path)
        query = parse_qs(route.query)
        with self._reported():
            if route.path == "/":
                self._html(PAGE.read_bytes())
            elif route.path == "/orders":
                self._json({"orders": _orders(), "policy": [dict(c) for c in desk.POLICY]})
            elif route.path == "/contract":
                self._json(_contract())
            elif route.path == "/ask":
                self._ask(query)
            else:
                self.send_error(404)

    def do_POST(self) -> None:
        route = urlparse(self.path)
        query = parse_qs(route.query)
        with self._reported():
            if route.path != "/answer":
                self.send_error(404)
                return
            name = _one(query, "session")
            decision = _one(query, "decision")
            port = _PORTS.get(name)
            # Only approved and denied arrive over HTTP. `no-response` is the
            # *absence* of an answer and `channel-unavailable` is not a person's
            # to declare on their own behalf.
            if port is None or decision not in ("approved", "denied"):
                self._json({"accepted": False}, status=400)
                return
            self._json({"accepted": port.answer(decision)})

    @contextmanager
    def _reported(self) -> Iterator[None]:
        """Say what broke. An unhandled error here just closes the socket, and
        the page shows nothing at all — which is how a one-character typo in the
        contract looked like the client being broken."""
        try:
            yield
        except ConnectionError:
            raise
        except Exception as exc:  # noqa: BLE001 - the page gets the failure, not a blank
            detail = f"{type(exc).__name__}: {exc}"
            traceback.print_exc()
            with suppress(ConnectionError, OSError):
                if self.headers_sent:
                    self.wfile.write(frame({"kind": "error", "message": detail}))
                    self.wfile.flush()
                else:
                    self._json({"error": detail}, status=500)

    # ---------------------------------------------------------------- the chat

    def _ask(self, query: dict[str, list[str]]) -> None:
        name = _one(query, "session") or "anon"
        message = _one(query, "message")
        compare = _one(query, "compare") == "1"

        port = LiveApprovalPort(timeout_seconds=_timeout())
        _PORTS[name] = port
        chat = _CHATS.get(name)
        if chat is None or chat.compare != compare:
            chat = session.Conversation(
                session=name, runs_dir=_runs(), approval=port, compare=compare
            )
            _CHATS[name] = chat
        chat.approval = port

        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self.end_headers()

        def emit(payload: dict[str, Any]) -> None:
            self.wfile.write(frame(payload))
            self.wfile.flush()

        try:
            chat.ask(message, emit)
        except ConnectionError:
            # The reader went away mid-run. Release the approval rather than
            # hold the desk's thread for the whole contract window.
            port.abandon()
        finally:
            _PORTS.pop(name, None)
        self.close_connection = True

    # ---------------------------------------------------------------- responses

    def _html(self, body: bytes) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        # Read fresh every time. A cached page silently demonstrates the
        # previous version of itself.
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, payload: Any, *, status: int = 200) -> None:
        body = json.dumps(payload, default=str).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


# -------------------------------------------------------------------- the panels


def _orders() -> list[dict[str, Any]]:
    return [
        {
            "order_id": order["order_id"],
            "customer": order["customer"],
            "item": order["item"],
            "status": order["status"],
            "total_cents": order["total_cents"],
            "note": order["customer_note"],
        }
        for order in desk.ORDERS.values()
    ]


def _contract() -> dict[str, Any]:
    spec = govern.contract()
    return {
        "contract_id": spec.contract_id,
        "workload": spec.workload,
        "digest": spec.digest().sha256,
        "goal": spec.task_goal.strip(),
        "mandatory": [
            {"id": c.id, "verifier": c.verifier.type if c.verifier else ""}
            for c in spec.criteria.mandatory
        ],
        "optional": [c.id for c in spec.criteria.optional],
        "advisory": [c.id for c in spec.criteria.advisory],
        "tools": [
            {"name": t.name, "deterministic": t.deterministic, "side_effecting": t.side_effecting}
            for t in spec.tools
        ],
        "approval": [
            {"tool": c.tool, "when": c.when} for c in spec.human_approval_conditions
        ],
        "budget": {
            "max_tokens": spec.budget.max_tokens,
            "max_iterations": spec.budget.max_iterations,
            # Declared and not enforced: nothing in the library reads it. Saying
            # so beside two numbers that are enforced is the honest option.
            "max_tool_calls": spec.budget.max_tool_calls,
        },
        "timeout_seconds": spec.approval_timeout_seconds,
        "on_timeout": spec.on_timeout,
    }


def _timeout() -> int:
    return govern.contract().approval_timeout_seconds or 120


def _runs() -> Path:
    return ROOT / "runs" / "chat"


def main(argv: list[str] | None = None) -> int:
    args = list(argv if argv is not None else sys.argv[1:])
    port = int(args[args.index("--port") + 1]) if "--port" in args else PORT
    server = ThreadingHTTPServer((HOST, port), Handler)
    print(f"support desk on http://{HOST}:{port}  (ctrl-c to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    finally:
        server.server_close()
    return 0


def _one(query: dict[str, list[str]], key: str) -> str:
    values = query.get(key) or [""]
    return values[0]


if __name__ == "__main__":
    raise SystemExit(main())
