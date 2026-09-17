"""The support agent. Reads a message, works the desk, proposes a disposition.

**Imports nothing from OutcomeFuse, and a test enforces that.** It stands in for
whatever framework you already run. It is deterministic rather than a model
because the thing on show is the loop, and a live turn would cost money and
change its mind between demonstrations.

It has one property worth stating: **it is not trying to be wrong.** Every
disposition below is defensible, and the governor still has work to do — because
two of the five dispositions move money or send mail, and the desk's authority
runs out before order 1005's chair does.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any

#: The desk's clock. Fixed so the same message always reaches the same
#: disposition; a demo whose answer changes overnight teaches nothing.
TODAY = date(2026, 9, 17)

REFUND_WINDOW_DAYS = 30
DESK_AUTHORITY_CENTS = 20_000

#: Flat, because an invented per-turn distribution would look like a
#: measurement. A real integration passes the provider's own numbers.
TOKENS_PER_TURN = 1_400

_ORDER_ID = re.compile(r"\b(\d{4})\b")

_INTENTS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("damaged", ("damaged", "broken", "faulty", "cracked", "missing", "not working", "crushed")),
    ("refund", ("refund", "money back", "return", "reimburse")),
    ("status", ("where", "status", "track", "late", "arrive", "delivery", "shipped")),
    ("cancel", ("cancel",)),
)


@dataclass(frozen=True)
class Step:
    tool: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class Turn:
    """One model turn: what to say, what to call, and whether it is finished."""

    model: str
    tokens: int
    cost: float
    say: str = ""
    calls: tuple[Step, ...] = ()
    deliverable: dict[str, Any] | None = None


@dataclass(frozen=True)
class Request:
    order_id: int
    intent: str


def read(message: str) -> Request | str:
    """Route a typed message, or say what is missing.

    Returning a question rather than starting a run is deliberate. A request
    with no order number cannot be worked, and opening a governed run to
    discover that spends budget, writes a log and ends with no deliverable —
    three kinds of noise in place of one question.
    """
    found = _ORDER_ID.search(message)
    if found is None:
        return "Which order number is this about? They look like 1001."
    lowered = message.lower()
    for intent, words in _INTENTS:
        if any(word in lowered for word in words):
            return Request(order_id=int(found.group(1)), intent=intent)
    return Request(order_id=int(found.group(1)), intent="status")


@dataclass
class Disposition:
    resolution: str
    amount_cents: int
    policy_refs: list[str]
    explanation: str
    next_steps: list[str] = field(default_factory=list)
    #: The one call that reaches outside the desk, where this needs one.
    action: Step | None = None


class DeskAgent:
    """Look up, read the policy, decide, act, answer."""

    def __init__(self, request: Request, *, model: str = "gpt-5-mini") -> None:
        self.request = request
        self.model = model
        self.seen: dict[str, Any] = {}
        self.notes: list[str] = []
        self.refusals: list[str] = []
        self._decided: Disposition | None = None

    # --------------------------------------------------------------- the turns

    def think(self, turn: int) -> Turn:
        if turn == 0:
            return self._turn(
                say=f"Looking up order {self.request.order_id} and its shipment.",
                calls=(
                    Step("order_lookup", {"order_id": self.request.order_id}),
                    Step("shipment_status", {"order_id": self.request.order_id}),
                ),
            )
        if turn == 1:
            return self._turn(
                say="Checking what the published policy says about this.",
                calls=(Step("refund_policy_lookup", {}),),
            )

        decided = self._decide()
        if turn == 2 and decided.action is not None:
            return self._turn(
                say=self._announce(decided),
                calls=(decided.action,),
            )
        # The sentence shown is the one in the answer, not the one the desk
        # decided before it knew whether it would be allowed to act.
        final = self.answer()
        return self._turn(say=str(final["explanation"]), deliverable=final)

    def _turn(self, **fields: Any) -> Turn:
        return Turn(model=self.model, tokens=TOKENS_PER_TURN, cost=0.0, **fields)

    def _announce(self, decided: Disposition) -> str:
        if decided.action is None:
            return decided.explanation
        if decided.action.tool == "issue_refund":
            return f"That qualifies. I need approval to refund {_money(decided.amount_cents)}."
        return "I need approval before emailing the customer."

    # -------------------------------------------------------------- the world

    def observe(self, tool: str, text: str, *, data: Any = None, allowed: bool = True) -> None:
        """A refusal is recorded as a refusal, and both change the state.

        Leaving refusals out of the task state looks harmless and is not: a turn
        spent being refused would leave the fuse's fingerprint unchanged and be
        read as a stall, halting the agent for having complied with the
        governor.
        """
        if not allowed:
            self.refusals.append(f"{tool}: {text}")
            return
        self.notes.append(f"{tool}: {text}")
        if data is not None:
            self.seen[tool] = data

    def state(self) -> list[str]:
        return [*self.notes, *self.refusals]

    def facts(self) -> int:
        return len(self.notes)

    def retry(self, model: str) -> None:
        self.model = model

    def acted(self) -> bool:
        """Whether the side-effecting call it wanted actually happened."""
        decided = self._decide()
        if decided.action is None:
            return True
        return decided.action.tool in self.seen

    # ------------------------------------------------------------- the answer

    def answer(self) -> dict[str, Any]:
        decided = self._decide()
        if not self.acted():
            # The disposition the desk reached is not the disposition it
            # carried out. Reporting `refund-issued` because a refund was
            # *decided* would put a falsehood in a ticket a person reads later.
            action = decided.action.tool if decided.action else "an action"
            return {
                "resolution": "referred-to-a-person",
                "order_id": self.request.order_id,
                "amount_cents": 0,
                "policy_refs": [{"id": ref} for ref in decided.policy_refs],
                "explanation": (
                    f"{decided.explanation} That needed {action}, which did not happen, "
                    "so nothing on the order has changed and a person has to finish it."
                ),
                "next_steps": ["a person carries out the decision above", *decided.next_steps],
            }
        return {
            "resolution": decided.resolution,
            "order_id": self.request.order_id,
            "amount_cents": decided.amount_cents,
            "policy_refs": [{"id": ref} for ref in decided.policy_refs],
            "explanation": decided.explanation,
            "next_steps": decided.next_steps,
        }

    # ------------------------------------------------------------ the decision

    def _shipment(self) -> dict[str, Any]:
        seen = self.seen.get("shipment_status")
        return seen if isinstance(seen, dict) else {}

    def _whereabouts(self, order: dict[str, Any]) -> str:
        """Where the parcel actually is, from the shipment record.

        Every fact in this sentence is read back from the tool result. The first
        version asserted the last scan was "today" whatever the record said,
        which is the kind of confident wrong detail a customer would catch.
        """
        ship = self._shipment()
        item = str(order.get("item", "the order")).capitalize()
        carrier = ship.get("carrier")
        if not carrier:
            return f"{item} has not been handed to a carrier yet."
        return (
            f"{item} is with {carrier} on tracking {ship.get('tracking')}, "
            f"last scanned {ship.get('last_scan_on')} ({ship.get('last_event')})."
        )

    def _stale(self) -> int:
        return _days_since(self._shipment().get("last_scan_on")) or 0

    def _decide(self) -> Disposition:
        if self._decided is None:
            self._decided = self._work_it_out()
        return self._decided

    def _work_it_out(self) -> Disposition:
        order = self.seen.get("order_lookup")
        if not isinstance(order, dict):
            return Disposition(
                resolution="not-eligible",
                amount_cents=0,
                policy_refs=["RP-1"],
                explanation=(
                    f"I could not retrieve order {self.request.order_id} from the order "
                    "book, so I cannot tell whether anything is owed on it."
                ),
                next_steps=["confirm the order number with the customer"],
            )

        status = str(order.get("status"))
        total = int(order.get("total_cents", 0))
        note = str(order.get("customer_note", ""))
        # The note is *evidence* for a refund question, never a reason to start
        # one. Only the request decides which question is being answered.
        damaged = self.request.intent == "damaged" or (
            self.request.intent == "refund" and _looks_damaged(note)
        )

        if status == "cancelled":
            return Disposition(
                resolution="not-eligible",
                amount_cents=0,
                policy_refs=["RP-5"],
                explanation=(
                    "This order was cancelled before dispatch, so the refund is "
                    "automatic and the desk has nothing to do. The money returns to "
                    "the original payment method."
                ),
                next_steps=["tell the customer to expect it within five working days"],
            )

        if status == "lost":
            return Disposition(
                resolution="escalate-to-carrier",
                amount_cents=0,
                policy_refs=["RP-3"],
                explanation=(
                    f"{self._whereabouts(order)} That is {self._stale()} days without "
                    "movement, past the ten-day threshold, so this is a carrier claim "
                    "rather than a refund. No money moves until the claim closes."
                ),
                next_steps=["raise the claim", "review in five working days"],
                action=Step(
                    "email_customer",
                    {
                        "order_id": self.request.order_id,
                        "message": (
                            "We have opened a claim with the carrier for your order "
                            "and will come back to you within five working days."
                        ),
                    },
                ),
            )

        if status == "in_transit":
            asked_about_money = self.request.intent in ("refund", "damaged", "cancel")
            tail = (
                " The refund window does not open until it arrives, so there is nothing"
                " to refund yet."
                if asked_about_money
                else " It is moving to the carrier's schedule, so the desk leaves it alone."
            )
            return Disposition(
                resolution="in-transit-no-action",
                amount_cents=0,
                # A status question is answered out of RP-6. Reaching for the
                # refund clause when nobody mentioned money answers a question
                # the customer did not ask.
                policy_refs=["RP-6", "RP-1"] if asked_about_money else ["RP-6"],
                explanation=self._whereabouts(order) + tail,
                next_steps=["check again if it has not arrived in three days"],
            )

        if self.request.intent == "status":
            # Asking where something is is not asking for money. The order's own
            # note used to be enough to start a refund, so "where is order 1001?"
            # reached an approval prompt for $74.00 on a question that asked
            # only for a location.
            days = _days_since(order.get("delivered_on"))
            since = f" That was {days} days ago." if days is not None else ""
            flagged = (
                f" The order carries a note that it {note.strip()}; nobody has asked "
                "the desk to act on it."
                if note
                else ""
            )
            return Disposition(
                resolution="information-provided",
                amount_cents=0,
                policy_refs=["RP-6"],
                explanation=f"{self._whereabouts(order)}{since}{flagged}",
                next_steps=["ask the customer what they would like done"] if note else [],
            )

        if damaged and total > DESK_AUTHORITY_CENTS:
            # The interesting one. A correct refund is over the desk's authority,
            # so the disposition changes rather than the amount being trimmed.
            return Disposition(
                resolution="replacement-offered",
                amount_cents=0,
                policy_refs=["RP-2", "RP-4"],
                explanation=(
                    f"The item arrived damaged, which is covered whatever the refund "
                    f"window says. A full refund would be {_money(total)}, which is over "
                    "the desk's authority, so I am offering a replacement instead."
                ),
                next_steps=["send a manager the refund request if a replacement is refused"],
                action=Step(
                    "email_customer",
                    {
                        "order_id": self.request.order_id,
                        "message": (
                            "We are sorry your order arrived damaged. We can send a "
                            "replacement straight away — just reply to confirm."
                        ),
                    },
                ),
            )

        if damaged:
            return Disposition(
                resolution="refund-issued",
                amount_cents=total,
                policy_refs=["RP-2", "RP-4"],
                explanation=(
                    "The item arrived damaged, which is refundable regardless of the "
                    f"window, and {_money(total)} is inside the desk's authority, so I "
                    "am refunding the order in full."
                ),
                next_steps=["no return needed for a damaged item"],
                action=Step(
                    "issue_refund",
                    {"order_id": self.request.order_id, "amount_cents": total},
                ),
            )

        days = _days_since(order.get("delivered_on"))
        if days is not None and days <= REFUND_WINDOW_DAYS:
            return Disposition(
                resolution="refund-issued",
                amount_cents=total,
                policy_refs=["RP-1", "RP-4"],
                explanation=(
                    f"This was delivered {days} days ago, inside the thirty-day window, "
                    f"and {_money(total)} is inside the desk's authority, so I am "
                    "refunding it in full."
                ),
                next_steps=["ask the customer to return the item within fourteen days"],
                action=Step(
                    "issue_refund",
                    {"order_id": self.request.order_id, "amount_cents": total},
                ),
            )

        return Disposition(
            resolution="not-eligible",
            amount_cents=0,
            policy_refs=["RP-1"],
            explanation=(
                f"This was delivered {days} days ago, which is outside the thirty-day "
                "refund window, and nothing in the order suggests it arrived damaged. "
                "A warranty claim is the route here, not a refund."
            ),
            next_steps=["point the customer at the manufacturer's warranty"],
        )


def _looks_damaged(note: str) -> bool:
    lowered = note.lower()
    return any(word in lowered for word in ("damag", "broken", "missing", "crushed", "cracked"))


def _days_since(delivered_on: Any) -> int | None:
    if not isinstance(delivered_on, str):
        return None
    return (TODAY - date.fromisoformat(delivered_on)).days


def _money(cents: int) -> str:
    return f"${cents / 100:,.2f}"
