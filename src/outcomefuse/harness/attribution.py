"""Which mechanism produced the saving (FR62).

> A headline savings figure SHALL NOT be published without its per-mechanism
> breakdown.

The reason is not bookkeeping. A governed arm that is cheaper because it ran a
smaller model has not demonstrated governance, and without a breakdown nobody
can tell the two apart. The measurement that prompted this: on supply-chain the
governed arm returned 22.7% fewer tokens and 87.5% lower cost. Those numbers are
both true and they are not the same claim.

**Model routing saves cost and, by construction, no tokens at all.** A token is a
token whichever model emits it; only its price changes. So the two savings
decompose differently, and that asymmetry is what makes the split computable
rather than guessed:

- The **token** saving is attributed to the mechanism that *terminated* the
  governed run. Tokens are spent by turns, and the terminating mechanism is what
  stopped the turns. It is read from the run's own terminal reason, not modelled.
- The **cost** saving splits exactly, with no counterfactual: reprice the
  governed run's own tokens at the baseline model's rate. The difference from
  what it actually cost is routing; the rest is the token reduction.

What this does **not** claim: that the terminating mechanism is solely
responsible for everything saved within a run. A run stopped by the quality gate
may also have had tool calls denied along the way, and this credits the gate for
the whole of that case's token saving. Decomposing within a run needs a
counterfactual — what the run would have done had the tool not been denied — and
inventing one here would be worth less than the coarser split being honest about
its granularity. Tool-call reductions are reported separately and counted
exactly (`tool_call_fraction`).

And it credits nothing at all to a mechanism that did not shorten the run. The
gate was measured firing at event 21 of 24, after the agent had already stopped
asking for tools: on such a run `stop-sufficient` confirms a result rather than
causing one, and the saving is booked to `agent-stopped-unaided`. That is the
single most important line in this module, because crediting it to the gate
would manufacture the product's central claim out of an accounting choice.
"""

from __future__ import annotations

from typing import Final

from pydantic import BaseModel, ConfigDict, Field

#: A governed run ends for one reason, and that reason names the mechanism that
#: ended it. Reasons absent from here saved nothing: `fail-closed` is a fault,
#: `approval-timeout` is a human waiting, and neither is a saving to credit.
MECHANISM_BY_TERMINAL: Final[dict[str, str]] = {
    "stop-sufficient": "quality-gate",
    "halt-no-progress": "loop-fuse",
    "halt-exhausted": "budget-ledger",
    "returned-partial": "quality-gate",
    "referred-human": "quality-gate",
}

#: Not a mechanism. It is the escalation ladder choosing a cheaper model, and it
#: is named separately so nobody reads it as the governor stopping early.
ROUTING: Final[str] = "model-routing"

#: A governed run that ended some other way, or none. Kept visible rather than
#: folded into a mechanism that did not earn it.
UNATTRIBUTED: Final[str] = "unattributed"

#: The agent stopped by itself and the governor only recorded what happened.
#: Measured live: the quality gate fires at event 21 of 24, *after* the agent
#: has stopped asking for tools, so `stop-sufficient` on such a run confirms a
#: result rather than shortening the run that produced it. Any saving on that
#: case came from somewhere else, and naming that honestly is the difference
#: between a breakdown and an advertisement.
AGENT_STOPPED: Final[str] = "agent-stopped-unaided"


class AttributionError(ValueError):
    """The saving could not be attributed without guessing."""


class CaseSaving(BaseModel):
    """One quality-matched pair, reduced to what attribution needs."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    case_id: str = Field(min_length=1)
    baseline_tokens: int = Field(ge=0)
    governed_tokens: int = Field(ge=0)
    baseline_cost: float = Field(ge=0)
    governed_cost: float = Field(ge=0)
    #: What the governed run's own tokens would have cost on the baseline's
    #: model. Equal to `governed_cost` when both arms ran the same model.
    governed_cost_at_baseline_rates: float = Field(ge=0)
    terminal_reason: str | None = None
    #: The terminal reason stopped the loop while the agent wanted to continue.
    cut_short: bool = False

    @property
    def mechanism(self) -> str:
        if not self.cut_short:
            return AGENT_STOPPED
        if self.terminal_reason is None:
            return UNATTRIBUTED
        return MECHANISM_BY_TERMINAL.get(self.terminal_reason, UNATTRIBUTED)


def _normalise(parts: dict[str, float]) -> dict[str, float]:
    """Shares of the total, summing to exactly 1.0.

    The last share absorbs the rounding remainder rather than every share being
    rounded independently, because the proof card refuses a set that does not
    sum to one and three-way rounding will not.
    """
    live = {name: value for name, value in parts.items() if value != 0}
    total = sum(live.values())
    if not live or total == 0:
        return {}
    ordered = sorted(live)
    shares = {name: round(live[name] / total, 6) for name in ordered[:-1]}
    shares[ordered[-1]] = round(1.0 - sum(shares.values()), 6)
    return shares


def attribute_tokens(savings: list[CaseSaving]) -> dict[str, float]:
    """Share of the net token saving, by the mechanism that ended each run.

    `model-routing` never appears here, and its absence is the point: a cheaper
    model emits the same number of tokens.
    """
    parts: dict[str, float] = {}
    for case in savings:
        saved = case.baseline_tokens - case.governed_tokens
        parts[case.mechanism] = parts.get(case.mechanism, 0.0) + saved
    return _normalise(parts)


def attribute_cost(savings: list[CaseSaving]) -> dict[str, float]:
    """Share of the net cost saving, splitting routing out exactly.

    No counterfactual: the governed run's own token counts are repriced at the
    baseline model's rate, so the routing term is arithmetic on measured
    quantities rather than a guess about what would have happened.
    """
    parts: dict[str, float] = {}
    for case in savings:
        routing = case.governed_cost_at_baseline_rates - case.governed_cost
        from_tokens = case.baseline_cost - case.governed_cost_at_baseline_rates
        parts[ROUTING] = parts.get(ROUTING, 0.0) + routing
        parts[case.mechanism] = parts.get(case.mechanism, 0.0) + from_tokens
    return _normalise(parts)
