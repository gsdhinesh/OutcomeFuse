"""The agent. Stands in for LangGraph, AutoGen, Semantic Kernel or your own.

**This file imports nothing from OutcomeFuse, and a test enforces that.** It is
the part of a real integration you do not get to rewrite, so the example is only
honest if it is written as though it could not be.

It is deterministic rather than scripted against a model: a live turn would cost
money and vary, and the point being made here is about the loop, not about what
a model says. Three temperaments, because a governor that only ever meets a
well-behaved agent demonstrates nothing:

| style | what it does | what it is for |
| --- | --- | --- |
| `careful` | looks things up once, messages the planner, answers correctly | the ordinary run |
| `repeats` | asks the same question every turn and never concludes | the stall |
| `hasty` | messages the planner first, then answers wrongly | the side effect |

`hasty` is the uncomfortable one. It acts on the world *before* it knows the
answer, and it is the only one whose output a gate can refuse.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

STYLES = ("careful", "repeats", "hasty")

#: A turn's token count. Flat, because an invented per-turn distribution would
#: look like a measurement. Real integrations pass the provider's own numbers.
TOKENS_PER_TURN = 1_800


@dataclass(frozen=True)
class Step:
    """One tool the agent wants called. Plain data; no library type."""

    tool: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class Turn:
    """What one model turn produced: some tool calls, or an answer, or both."""

    model: str
    tokens: int
    cost: float
    calls: tuple[Step, ...] = ()
    #: The agent claims it is finished. `None` means it wants another turn.
    deliverable: dict[str, Any] | None = None


class MiniAgent:
    """A small ReAct-shaped agent over the supply-chain tools."""

    def __init__(
        self,
        *,
        po_id: int,
        answer: dict[str, Any],
        style: str = "careful",
        model: str = "gpt-5-mini",
    ) -> None:
        if style not in STYLES:
            raise ValueError(f"unknown style {style!r}; expected one of {list(STYLES)}")
        self.po_id = po_id
        self.style = style
        self.model = model
        self._answer = dict(answer)
        #: What it has been told, in the order it was told. The loop hands this
        #: to the fuse as the task state, so a turn that learns nothing new
        #: leaves it unchanged — which is precisely what a stall looks like.
        self.notes: list[str] = []
        self.refusals: list[str] = []

    # --------------------------------------------------------------- the turn

    def think(self, turn: int) -> Turn:
        plan = getattr(self, f"_{self.style}")(turn)
        return Turn(model=self.model, tokens=TOKENS_PER_TURN, cost=0.0, **plan)

    def _careful(self, turn: int) -> dict[str, Any]:
        if turn == 0:
            return {
                "calls": (
                    Step("order_lookup", {"po_id": self.po_id}),
                    Step("shipment_trace", {"po_id": self.po_id}),
                )
            }
        if turn == 1:
            return {"calls": (Step("supplier_policy_lookup", {}),)}
        if turn == 2:
            return {"calls": (Step("notify_planner", self._message()),)}
        return {"deliverable": self.answer()}

    def _repeats(self, turn: int) -> dict[str, Any]:
        # Identical arguments every turn. Nothing new is learned, so the task
        # state stops moving and the fuse has something to see.
        return {"calls": (Step("order_lookup", {"po_id": self.po_id}),)}

    def _hasty(self, turn: int) -> dict[str, Any]:
        if turn == 0:
            return {"calls": (Step("notify_planner", self._message()),)}
        return {
            "calls": (Step("order_lookup", {"po_id": self.po_id}),),
            "deliverable": self._wrong(),
        }

    # -------------------------------------------------------------- the world

    def observe(self, tool: str, text: str, *, allowed: bool = True, fresh: bool = True) -> None:
        """Fold a tool result back into the agent's own memory.

        A refusal is recorded as a refusal. Telling the agent it was *not
        allowed* — rather than quietly returning nothing — is the one obligation
        the verdict table puts on the host that is easy to get wrong, and an
        agent that cannot tell the two apart will retry forever.

        A result served from the cache is neither: the agent already has it, so
        it learns nothing and its state does not move. Appending it anyway is
        how a stall comes to look like progress.
        """
        if not allowed:
            self.refusals.append(f"{tool}: {text}")
        elif fresh:
            self.notes.append(f"{tool}: {text}")

    def state(self) -> list[str]:
        """Everything that has changed, including what was refused.

        Leaving the refusals out looks harmless and is not. A denied call
        produces no evidence, so a turn spent being refused leaves the task
        state identical to the turn before and the fuse reads it as a stall —
        halting the agent for having complied with the governor. Measured: the
        careful agent lost its answer that way under `--approval denied`.
        """
        return [*self.notes, *self.refusals]

    def facts(self) -> int:
        return len(self.notes)

    def retry(self, model: str) -> None:
        """The governor escalated. Same agent, stronger model, one more go."""
        self.model = model

    # -------------------------------------------------------------- the answer

    def answer(self) -> dict[str, Any]:
        return {
            "exception_type": self._answer["exception_type"],
            "root_cause_code": self._answer["root_cause_code"],
            "recommended_action": self._answer["recommended_action"],
            "impacted_orders": [self.po_id],
            "policy_refs": [{"id": "SP-4.1"}],
            "est_delay_days": 0,
            "alternatives": [],
        }

    def _wrong(self) -> dict[str, Any]:
        """Well-formed, plausible, and not what the answer key says."""
        body = self.answer()
        alternatives = [t for t in _TYPES if t != body["exception_type"]]
        return {**body, "exception_type": alternatives[0]}

    def _message(self) -> dict[str, Any]:
        return {
            "po_id": self.po_id,
            "message": f"investigating an exception on PO {self.po_id}",
        }


#: The deliverable structure's controlled taxonomy, quoted from the frozen
#: contract. Duplicated rather than imported, because this file is the half of
#: the example that is allowed to know nothing about OutcomeFuse.
_TYPES = (
    "quality-hold",
    "customs-hold",
    "price-variance",
    "allocation-conflict",
    "short-ship",
    "late-shipment",
)
