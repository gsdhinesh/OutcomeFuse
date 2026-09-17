"""One conversation, one governed run per message, frames as they happen.

No HTTP here on purpose: everything the browser shows is produced by `ask()`,
so the whole experience can be driven from a test or a terminal without a
socket. `server.py` adds the wire and nothing else.

A message becomes **one run**, not one long-lived session. That is the honest
mapping: a contract governs a task, and "resolve this customer's question" is
the task. It has a consequence worth naming — the Tool Governor's cache is
per-run, so asking the same thing twice in one conversation pays twice. The
second message is a new task that happens to look like the first one, and
pretending otherwise would let a cache hit masquerade as understanding.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from console.approval import LiveApprovalPort

from chat import agent as desk_agent
from chat import govern, loop
from outcomefuse.core.record import Event
from outcomefuse.ports import ApprovalRequest

Emit = Callable[[dict[str, Any]], None]

DEFAULT_RUNS = Path("runs") / "chat"


@dataclass
class Exchange:
    """What one message produced, for the transcript and for a test."""

    message: str
    run_id: str = ""
    answered: bool = False
    frames: list[dict[str, Any]] = field(default_factory=list)
    summaries: list[govern.Summary] = field(default_factory=list)
    clarification: str = ""


class Conversation:
    """A person, a desk, and a governor sitting between them."""

    def __init__(
        self,
        *,
        session: str = "",
        runs_dir: Path = DEFAULT_RUNS,
        approval: LiveApprovalPort | str = "approved",
        compare: bool = False,
    ) -> None:
        self.session = session or uuid.uuid4().hex[:12]
        self.runs_dir = runs_dir
        self.approval = approval
        self.compare = compare
        self.spec = govern.contract()
        self.exchanges: list[Exchange] = []

    # ------------------------------------------------------------------ asking

    def ask(self, message: str, emit: Emit | None = None) -> Exchange:
        say = emit or (lambda _frame: None)
        exchange = Exchange(message=message)
        self.exchanges.append(exchange)

        def send(frame: dict[str, Any] | None = None, **fields: Any) -> None:
            # Takes a frame positionally (the loop's `Say`) or as keywords (this
            # file's own frames), so there is one transcript and one sink.
            payload = {**(frame or {}), **fields}
            exchange.frames.append(payload)
            say(payload)

        routed = desk_agent.read(message)
        if isinstance(routed, str):
            # No run is opened. Opening one to discover the message cannot be
            # worked would spend budget, write a log and end with no
            # deliverable: three kinds of noise in place of one question.
            exchange.clarification = routed
            send(kind="assistant", text=routed, arm="host")
            send(kind="done", answered=False)
            return exchange

        exchange.run_id = f"{self.session}-{len(self.exchanges):02d}"
        self._run_governed(routed, exchange, send)
        if self.compare:
            self._run_ungoverned(routed, exchange, send)
        send(kind="done", answered=exchange.answered)
        return exchange

    # ------------------------------------------------------------- the two arms

    def _run_governed(self, routed: desk_agent.Request, exchange: Exchange, send: Any) -> None:
        port = self.approval
        if isinstance(port, LiveApprovalPort):
            port.on_ask = lambda request: send(
                kind="approval", arm="governed", request=_describe(port, request)
            )

        site = govern.Governed(
            exchange.run_id,
            runs_dir=self.runs_dir,
            spec=self.spec,
            approval=port,
            sink=lambda event: send(kind="event", arm="governed", event=_event(event)),
        )
        brain = desk_agent.DeskAgent(routed, model=self._start_model())
        try:
            outcome = loop.converse(
                brain,
                site,
                request_id=exchange.run_id,
                say=send,
                max_turns=self.spec.budget.max_iterations,
            )
        finally:
            site.close()
        exchange.answered = outcome.answered
        summary = site.summary(outcome)
        exchange.summaries.append(summary)
        send(kind="summary", arm="governed", summary=summary.as_json())

    def _run_ungoverned(self, routed: desk_agent.Request, exchange: Exchange, send: Any) -> None:
        site = govern.Ungoverned(f"{exchange.run_id}-ungoverned", spec=self.spec)
        brain = desk_agent.DeskAgent(routed, model=self._start_model())
        outcome = loop.converse(
            brain,
            site,
            request_id=exchange.run_id,
            say=send,
            max_turns=self.spec.budget.max_iterations,
        )
        summary = site.summary(outcome)
        exchange.summaries.append(summary)
        send(kind="summary", arm="ungoverned", summary=summary.as_json())

    def _start_model(self) -> str:
        return self.spec.models.start if self.spec.models else "gpt-5-mini"


def _event(event: Event) -> dict[str, Any]:
    return event.model_dump(mode="json")


def _describe(port: LiveApprovalPort, request: ApprovalRequest) -> dict[str, Any]:
    described = port.describe(request)
    described["prompt"] = _prompt(request)
    return described


def _prompt(request: ApprovalRequest) -> str:
    """What the person is actually being asked, in their words not the log's."""
    arguments = dict(request.arguments)
    if request.tool == "issue_refund":
        amount = int(arguments.get("amount_cents", 0))
        return f"Refund ${amount / 100:,.2f} on order {arguments.get('order_id')}?"
    if request.tool == "email_customer":
        return f"Email the customer about order {arguments.get('order_id')}?"
    return f"Allow {request.tool}?"
