"""An approval port that blocks the run until a person answers.

Every other port in this client is scripted, because the question elsewhere is
what the library does and a human in the loop would make it neither reproducible
nor fast. This one is the exception, and deliberately so: the approval gate is
the mechanism whose whole point is that a person decides, and demonstrating it
with a pre-recorded answer demonstrates the wrong thing.

**It really blocks.** `ToolGovernor.assess` calls `request()` on the driver's
thread and does not return until someone clicks or the contract's window
elapses. The tool is not invoked in the meantime, because the call has not been
authorised yet — that is what the gate means.

The timeout is the contract's own `approval_timeout_seconds`, not a number
chosen to make a demonstration comfortable. Nobody answering is a real outcome
and it routes through `on_timeout` like any other.
"""

from __future__ import annotations

import queue
from collections.abc import Callable
from typing import Any

from outcomefuse.ports import ApprovalOutcome, ApprovalRequest, Decision

#: Set by the stream so the request reaches the viewer. Until it is, an approval
#: would block on a question nobody was ever asked.
Ask = Callable[[ApprovalRequest], None]


class LiveApprovalPort:
    """One per run. Holds the run's thread while a person decides."""

    def __init__(self, *, timeout_seconds: int) -> None:
        self.timeout_seconds = timeout_seconds
        self.on_ask: Ask | None = None
        self.asked: list[ApprovalRequest] = []
        self._answer: queue.Queue[Decision] = queue.Queue(maxsize=1)

    def request(self, request: ApprovalRequest) -> ApprovalOutcome:
        self.asked.append(request)
        if self.on_ask is None:
            # Nobody is listening, so nobody can answer. Reporting this as an
            # unavailable channel is the truth and is fail-closed under FR89 —
            # far better than waiting out a window no question was asked in.
            return ApprovalOutcome(decision="channel-unavailable", clause=request.clause)
        self.on_ask(request)
        try:
            decision = self._answer.get(timeout=self.timeout_seconds)
        except queue.Empty:
            decision = "no-response"
        return ApprovalOutcome(decision=decision, clause=request.clause)

    def answer(self, decision: Decision) -> bool:
        """Called from the HTTP thread. False if nothing was waiting for it."""
        try:
            self._answer.put_nowait(decision)
        except queue.Full:
            return False
        return True

    def abandon(self) -> None:
        """The viewer went away. Release the run rather than hold it to the window."""
        self.answer("no-response")

    def describe(self, request: ApprovalRequest) -> dict[str, Any]:
        return {
            "run_id": request.run_id,
            "step_id": request.step_id,
            "tool": request.tool,
            "clause": request.clause,
            "timeout_seconds": self.timeout_seconds,
        }
