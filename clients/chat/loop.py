"""The conversational loop, and the four moments that make it engineered.

**Imports nothing from OutcomeFuse.** It is written against `Site`, a
four-method seam implemented in `govern.py`, so the loop cannot tell whether
anything is governing it.

What makes this loop a *chat* loop rather than a batch one is `say`: every frame
is handed to the caller the moment it happens, so the browser sees the agent
working instead of a spinner and a verdict. The ordering below is load-bearing
for that — the agent's sentence goes out *before* the tool call it explains, and
the tool frame goes out after the governor has decided, never before.

The four moments:

- **`charge`** — the model turn is the largest spend in the run. Skip it and the
  budget governs only the cheap half.
- **`call`** — the decision is written *before* the tool runs, so a step that
  happened cannot be missing from the log.
- **`progress`** — an agent circling is stopped by something that understands
  progress, not by a turn cap that has already paid for every turn.
- **`finish`** — the agent claiming it is done is the only moment at which a
  quality floor can be applied.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Protocol

RAN = "ran"
CACHED = "cached"
DENIED = "denied"
FAILED = "failed"

#: One chat frame. The caller decides whether that means an SSE write, a print,
#: or a list append; the loop neither knows nor waits.
Say = Callable[[dict[str, Any]], None]


@dataclass(frozen=True)
class Reply:
    """What the site gives back for one proposed call."""

    text: str
    data: Any = None
    how: str = RAN
    terminal: str | None = None

    @property
    def allowed(self) -> bool:
        return self.how in (RAN, CACHED, FAILED)


@dataclass(frozen=True)
class Finish:
    terminal: str | None = None
    escalate_to: str | None = None
    gate: str = "not-evaluated"
    unmet: tuple[str, ...] = ()


class Site(Protocol):
    name: str

    def charge(self, *, step_id: str, tokens: int, cost: float, model: str) -> str | None: ...

    def call(self, *, step_id: str, tool: str, arguments: dict[str, Any]) -> Reply: ...

    def progress(self, *, state: Any, facts: int) -> str | None: ...

    def finish(self, deliverable: dict[str, Any] | None) -> Finish: ...


@dataclass
class Outcome:
    """What the loop saw. The log is the evidence; this is for the reader."""

    arm: str
    turns: int = 0
    proposed: int = 0
    ran: int = 0
    cached: int = 0
    denied: int = 0
    failed: int = 0
    escalations: int = 0
    tokens: int = 0
    ended: str = ""
    answered: bool = False
    gate: str = "not-evaluated"
    unmet: tuple[str, ...] = ()
    deliverable: dict[str, Any] | None = None
    frames: list[dict[str, Any]] = field(default_factory=list)


def converse(
    agent: Any,
    site: Site,
    *,
    request_id: str,
    say: Say | None = None,
    max_turns: int = 6,
) -> Outcome:
    """Work one customer message to an answer, a refusal, or a stop."""
    outcome = Outcome(arm=site.name)

    def emit(**frame: Any) -> None:
        frame.setdefault("arm", site.name)
        outcome.frames.append(frame)
        if say is not None:
            say(frame)

    for turn in range(max_turns):
        step_id = f"{request_id}-{turn:02d}"
        plan = agent.think(turn)
        outcome.turns += 1
        outcome.tokens += plan.tokens

        stop = site.charge(
            step_id=step_id, tokens=plan.tokens, cost=plan.cost, model=plan.model
        )
        if stop is not None:
            emit(kind="stop", reason=stop, detail="the run could not afford to continue")
            return _end(outcome, stop)

        if plan.say:
            emit(kind="assistant", text=plan.say, model=plan.model)

        for step in plan.calls:
            outcome.proposed += 1
            reply = site.call(step_id=step_id, tool=step.tool, arguments=step.arguments)
            _count(outcome, reply)
            emit(
                kind="tool",
                tool=step.tool,
                arguments=step.arguments,
                how=reply.how,
                detail=reply.text,
            )
            if reply.terminal is not None:
                emit(kind="stop", reason=reply.terminal, detail=reply.text)
                return _end(outcome, reply.terminal)
            agent.observe(step.tool, reply.text, data=reply.data, allowed=reply.allowed)

        if plan.deliverable is not None:
            finished = site.finish(plan.deliverable)
            if finished.escalate_to is not None:
                # An escalated run has **not** ended. Treating it as ended would
                # make the retry a second run that no comparison could pair.
                outcome.escalations += 1
                agent.retry(finished.escalate_to)
                emit(kind="escalated", model=finished.escalate_to, unmet=list(finished.unmet))
                continue
            outcome.answered = True
            outcome.gate = finished.gate
            outcome.unmet = finished.unmet
            outcome.deliverable = plan.deliverable
            emit(
                kind="answer",
                deliverable=plan.deliverable,
                gate=finished.gate,
                unmet=list(finished.unmet),
                terminal=finished.terminal,
            )
            return _end(outcome, finished.terminal or "answered")

        # Only a turn that did not conclude is put to the fuse. An agent that
        # just answered has the same task state as the turn before — it spent
        # the turn writing, not looking — and a fuse fed that reads the moment
        # of success as a stall.
        stop = site.progress(state=agent.state(), facts=agent.facts())
        if stop is not None:
            emit(kind="stop", reason=stop, detail="the loop fuse fired")
            return _end(outcome, stop)

    emit(kind="stop", reason="turn-cap", detail="the host's own limit, not the governor's")
    return _end(outcome, "turn-cap")


def _count(outcome: Outcome, reply: Reply) -> None:
    setattr(outcome, reply.how, getattr(outcome, reply.how) + 1)


def _end(outcome: Outcome, reason: str) -> Outcome:
    outcome.ended = reason
    return outcome
