"""The Ledger: the only writer of spend (AD-3, AD-4).

Three quantities, never conflated:

- **`verification_reserve`** — no step may spend it (FR14, FR101). An escalation
  that consumes the reserve buys a better answer nobody can check.
- **`in_flight`** — the sum of outstanding holds.
- **`spent`** — settled.

**Every spend is held before it happens, governor overhead included**, and a
hold is released by exactly one of: settlement, a denial, or run termination.

**Affordability is a query; reservation is a write.** `can_afford` is pure and
answers a question the Policy asks *before* deciding, so `unaffordable` is a
decision input rather than a reservation failure. A reservation that follows a
decision cannot be rejected — a rejected reservation is a fail-closed condition
under FR88, not a routine outcome.
"""

from __future__ import annotations

from typing import Final

from pydantic import BaseModel, ConfigDict, Field, model_validator

#: FR101's deterministic default, used only where the contract declares no
#: reserve. Recorded with the run so a derived reserve is auditable rather than
#: implicit.
DEFAULT_RESERVE_FRACTION: Final[float] = 0.15


class LedgerError(RuntimeError):
    """The Ledger refused. A rejected reservation is fail-closed, not routine."""


class Reserve(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    max_tokens: int = Field(ge=0)
    max_estimated_cost: float = Field(ge=0)
    #: "declared" where the contract stated it, "derived" where FR101's default
    #: supplied it. Recorded so the sizing is auditable.
    sizing: str

    @model_validator(mode="after")
    def _sizing_is_known(self) -> Reserve:
        if self.sizing not in {"declared", "derived"}:
            raise ValueError(f"reserve sizing must be declared or derived: {self.sizing!r}")
        return self


class Hold(BaseModel):
    """An outstanding claim on budget, taken before the spend happens."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    hold_id: str = Field(min_length=1)
    decision_id: str = Field(min_length=1)
    mechanism: str = Field(min_length=1)
    tokens: int = Field(ge=0)
    cost: float = Field(ge=0)
    #: Governor overhead is debited like anything else and attributed to the
    #: mechanism that requested it, never self-reported.
    overhead: bool = False


class Attribution(BaseModel):
    """A decomposition over contributing mechanisms, never a winner.

    Where several mechanisms contribute to one step's overhead or avoided
    spend, the shares sum to the total. No tie-break elects a single causer,
    because the per-mechanism breakdown would then be a function of the
    tie-break rather than of the mechanisms.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    total_tokens: int = Field(ge=0)
    total_cost: float = Field(ge=0)
    shares: dict[str, float]

    @model_validator(mode="after")
    def _shares_sum_to_one(self) -> Attribution:
        if not self.shares:
            raise ValueError("an attribution names at least one mechanism")
        if any(share < 0 for share in self.shares.values()):
            raise ValueError("a mechanism's share may not be negative")
        total = sum(self.shares.values())
        if abs(total - 1.0) > 1e-9:
            raise ValueError(f"attribution shares sum to {total}, not 1.0")
        return self

    def tokens_for(self, mechanism: str) -> float:
        return self.total_tokens * self.shares.get(mechanism, 0.0)


def size_reserve(
    max_tokens: int,
    max_estimated_cost: float,
    declared_tokens: int | None = None,
    declared_cost: float | None = None,
) -> Reserve:
    """FR101: from the contract where declared, else a deterministic default."""
    if declared_tokens is not None and declared_cost is not None:
        return Reserve(
            max_tokens=declared_tokens, max_estimated_cost=declared_cost, sizing="declared"
        )
    if declared_tokens is not None or declared_cost is not None:
        raise LedgerError("a declared reserve must state both tokens and cost")
    return Reserve(
        max_tokens=int(max_tokens * DEFAULT_RESERVE_FRACTION),
        max_estimated_cost=round(max_estimated_cost * DEFAULT_RESERVE_FRACTION, 6),
        sizing="derived",
    )


class Ledger:
    """One per run. The only writer of spend."""

    def __init__(
        self,
        *,
        allocated_tokens: int,
        allocated_cost: float,
        reserve: Reserve,
    ) -> None:
        if reserve.max_tokens > allocated_tokens or reserve.max_estimated_cost > allocated_cost:
            raise LedgerError("the verification reserve exceeds the ceiling it is carved from")
        self.allocated_tokens = allocated_tokens
        self.allocated_cost = allocated_cost
        self.reserve = reserve
        self._spent_tokens = 0
        self._spent_cost = 0.0
        self._holds: dict[str, Hold] = {}
        self.attributions: list[Attribution] = []

    # -------------------------------------------------------------- queries

    @property
    def spent_tokens(self) -> int:
        return self._spent_tokens

    @property
    def spent_cost(self) -> float:
        return self._spent_cost

    @property
    def in_flight_tokens(self) -> int:
        return sum(hold.tokens for hold in self._holds.values())

    @property
    def in_flight_cost(self) -> float:
        return sum(hold.cost for hold in self._holds.values())

    def spendable_tokens(self, *, may_use_reserve: bool = False) -> int:
        """What a step may spend. The reserve is excluded unless verifying."""
        floor = 0 if may_use_reserve else self.reserve.max_tokens
        return self.allocated_tokens - floor - self._spent_tokens - self.in_flight_tokens

    def spendable_cost(self, *, may_use_reserve: bool = False) -> float:
        floor = 0.0 if may_use_reserve else self.reserve.max_estimated_cost
        return self.allocated_cost - floor - self._spent_cost - self.in_flight_cost

    def can_afford(
        self, tokens: int, cost: float, *, may_use_reserve: bool = False
    ) -> bool:
        """Pure. Asked before deciding, so `unaffordable` is a decision input."""
        return (
            tokens <= self.spendable_tokens(may_use_reserve=may_use_reserve)
            and cost <= self.spendable_cost(may_use_reserve=may_use_reserve) + 1e-12
        )

    def escalation_leaves_reserve_intact(self, tokens: int, cost: float) -> bool:
        """FR101: recalculated before any model escalation."""
        return self.can_afford(tokens, cost, may_use_reserve=False)

    # --------------------------------------------------------------- writes

    def hold(
        self,
        hold_id: str,
        decision_id: str,
        mechanism: str,
        tokens: int,
        cost: float,
        *,
        overhead: bool = False,
        may_use_reserve: bool = False,
    ) -> Hold:
        """Take a hold. Follows a decision, so refusal here is fail-closed."""
        if hold_id in self._holds:
            raise LedgerError(f"hold {hold_id!r} is already outstanding")
        if not self.can_afford(tokens, cost, may_use_reserve=may_use_reserve):
            raise LedgerError(
                f"hold {hold_id!r} for {tokens} tokens is not affordable; affordability "
                "is queried before deciding, so reaching here is a fail-closed condition"
            )
        taken = Hold(
            hold_id=hold_id,
            decision_id=decision_id,
            mechanism=mechanism,
            tokens=tokens,
            cost=cost,
            overhead=overhead,
        )
        self._holds[hold_id] = taken
        return taken

    def settle(
        self,
        hold_id: str,
        *,
        actual_tokens: int | None = None,
        actual_cost: float | None = None,
        attribution: Attribution | None = None,
    ) -> Hold:
        """Release a hold into `spent`. One of the three release paths."""
        held = self._release(hold_id)
        tokens = held.tokens if actual_tokens is None else actual_tokens
        cost = held.cost if actual_cost is None else actual_cost
        self._spent_tokens += tokens
        self._spent_cost += cost
        if attribution is not None:
            self.attributions.append(attribution)
        return held

    def release_unspent(self, hold_id: str) -> Hold:
        """Release a hold without spending it. The step did not happen.

        Covers both a denial and a tool that failed after the reservation was
        taken. Either way the money must come back: a hold left in flight
        shrinks what the run can spend for the rest of its life, and it does so
        invisibly — the log shows a reservation and simply never shows its
        release.
        """
        return self._release(hold_id)

    def release_denied(self, hold_id: str) -> Hold:
        """Release without spending: the step was denied."""
        return self.release_unspent(hold_id)

    def release_all(self) -> list[Hold]:
        """Run termination releases whatever is still outstanding."""
        released = list(self._holds.values())
        self._holds.clear()
        return released

    def _release(self, hold_id: str) -> Hold:
        try:
            return self._holds.pop(hold_id)
        except KeyError:
            raise LedgerError(f"no outstanding hold {hold_id!r}") from None

    def outstanding(self) -> tuple[Hold, ...]:
        return tuple(self._holds.values())

    def overhead_tokens(self) -> int:
        """Governor overhead is held like anything else, so it is countable."""
        return sum(h.tokens for h in self._holds.values() if h.overhead)
