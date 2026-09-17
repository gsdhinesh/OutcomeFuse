"""The loop. Four calls to a seam, and every one of them is load-bearing.

**This file imports nothing from OutcomeFuse either.** It is written against
`Site`, a four-method protocol implemented twice in `govern.py` — once by the
governor and once by nothing at all. The loop cannot tell which it has, which is
why the difference the CLI prints is attributable to the governor and not to two
loops that happen to disagree.

Loop engineering is the claim that these four moments are the product:

- **`charge`** — the model turn is the largest spend in the run. Skip it and the
  budget governs only the cheap half.
- **`call`** — the decision is written *before* the tool runs, so a step that
  happened cannot be missing from the log.
- **`progress`** — an agent circling is stopped by something that understands
  progress, not by a turn cap that has already paid for every turn.
- **`finish`** — the agent claiming it is done is the only moment at which a
  quality floor can be applied.

Everything else here is bookkeeping.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

#: How a proposed tool call actually resolved. `denied` and `failed` are
#: different things and the agent is told which: one means *you may not*, the
#: other means *that did not work, try something else*. Collapsing them is the
#: commonest way to make a governed agent look stupid.
RAN = "ran"
CACHED = "cached"
DENIED = "denied"
FAILED = "failed"


@dataclass(frozen=True)
class Reply:
    """What the site gives back for one proposed call."""

    text: str
    how: str = RAN
    #: Set where the run must stop now. The loop does not get a say.
    terminal: str | None = None

    @property
    def allowed(self) -> bool:
        return self.how in (RAN, CACHED, FAILED)


@dataclass(frozen=True)
class Finish:
    terminal: str | None = None
    escalate_to: str | None = None


class Site(Protocol):
    """Where a proposed step meets whatever is governing it."""

    name: str

    def charge(self, *, step_id: str, tokens: int, cost: float, model: str) -> str | None: ...

    def call(self, *, step_id: str, tool: str, arguments: dict[str, Any]) -> Reply: ...

    def progress(self, *, state: Any, facts: int) -> str | None: ...

    def finish(self, deliverable: dict[str, Any] | None) -> Finish: ...


@dataclass
class Trace:
    """What the loop saw. Not evidence — the log is. This is for the reader."""

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
    notes: list[str] = field(default_factory=list)


def run(agent: Any, site: Site, *, case_id: str, max_turns: int = 8) -> Trace:
    """Drive one case to an answer, a refusal, or a stop."""
    trace = Trace(arm=site.name)

    for turn in range(max_turns):
        step_id = f"{case_id}-{turn:02d}"
        plan = agent.think(turn)
        trace.turns += 1
        trace.tokens += plan.tokens

        stop = site.charge(
            step_id=step_id, tokens=plan.tokens, cost=plan.cost, model=plan.model
        )
        if stop is not None:
            return _end(trace, stop)

        for step in plan.calls:
            trace.proposed += 1
            reply = site.call(step_id=step_id, tool=step.tool, arguments=step.arguments)
            _count(trace, reply)
            if reply.terminal is not None:
                return _end(trace, reply.terminal)
            # `allowed` is not enough. A cached reply is allowed and is also not
            # a new fact, and an agent told otherwise reports rising evidence on
            # every turn of a stall — so the fuse never sees repeated state and
            # the turn cap is the only thing left to stop it.
            agent.observe(
                step.tool, reply.text, allowed=reply.allowed, fresh=reply.how != CACHED
            )

        if plan.deliverable is not None:
            outcome = site.finish(plan.deliverable)
            if outcome.escalate_to is not None:
                # An escalated run has **not** ended. Treating it as ended would
                # make the retry a second run, and no comparison could pair them.
                trace.escalations += 1
                agent.retry(outcome.escalate_to)
                continue
            trace.answered = True
            return _end(trace, outcome.terminal or "answered")

        # Only a turn that did not conclude is put to the fuse. An agent that
        # just answered has the same task state as the turn before — it spent
        # the turn writing, not looking — and a fuse fed that reads the moment
        # of success as a stall. Measured: it halted `careful` one call short.
        stop = site.progress(state=agent.state(), facts=agent.facts())
        if stop is not None:
            return _end(trace, stop)

    return _end(trace, "turn-cap")


def _count(trace: Trace, reply: Reply) -> None:
    setattr(trace, reply.how, getattr(trace, reply.how) + 1)


def _end(trace: Trace, reason: str) -> Trace:
    trace.ended = reason
    return trace
