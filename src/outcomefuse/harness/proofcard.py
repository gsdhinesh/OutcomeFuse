"""The proof card (FR97, FR58, FR61, FR62).

Pairing and computation live here, in the harness. The viewer renders the
artifact and the submission consumes it — cutting the viewer must not affect the
proof card's availability or content.

**Net is the headline.** Gross may sit alongside it and never leads, and
governor overhead is its own line item. Gross savings are how this category
flatters itself; net is the only number that survives scrutiny.

Percentages never travel alone: with a modest case count a "within N points"
quality claim may not be statistically meaningful, so absolute pass counts
accompany every rate.
"""

from __future__ import annotations

import statistics
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..core.canon import Digest, hash_structure


class ArmTotals(BaseModel):
    """One arm's measured spend on one case."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    tokens: int = Field(ge=0)
    cost: float = Field(ge=0)
    tool_calls: int = Field(ge=0)
    #: Zero for the baseline arm, which shares no governor code at all.
    governor_overhead_tokens: int = Field(default=0, ge=0)
    governor_overhead_cost: float = Field(default=0.0, ge=0)


class PairedCase(BaseModel):
    """A quality-matched pair: the same case, both arms, both verdicts."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    case_id: str = Field(min_length=1)
    baseline: ArmTotals
    governed: ArmTotals
    baseline_passed: bool
    governed_passed: bool
    gate_qualifier: str
    baseline_seal: str = Field(min_length=1)
    governed_seal: str = Field(min_length=1)

    @property
    def quality_matched(self) -> bool:
        """Only pairs both arms passed compare spend for the same outcome."""
        return self.baseline_passed and self.governed_passed


class Savings(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    gross_tokens: int
    net_tokens: int
    gross_token_fraction: float
    net_token_fraction: float
    gross_cost: float
    net_cost: float
    net_cost_fraction: float
    tool_calls_saved: int
    tool_call_fraction: float
    overhead_tokens: int
    overhead_share: float


class ProofCard(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    workload: str
    pairs: tuple[PairedCase, ...]
    quality_matched_pairs: int
    savings: Savings
    #: FR62: the headline may not be published without this.
    per_mechanism: dict[str, float]
    #: FR58: absolute counts, never percentages alone.
    baseline_passes: int
    governed_passes: int
    case_count: int
    median_net_token_fraction: float
    gate_qualifiers: tuple[str, ...]
    #: AD-16: seals live outside the database, which is what makes the chain
    #: load-bearing rather than self-referential.
    run_seals: tuple[str, ...]

    @model_validator(mode="after")
    def _breakdown_sums(self) -> ProofCard:
        if self.per_mechanism:
            total = sum(self.per_mechanism.values())
            if abs(total - 1.0) > 1e-6:
                raise ValueError(f"per-mechanism shares sum to {total}, not 1.0")
        return self

    def digest(self) -> Digest:
        return hash_structure(self.model_dump(mode="json"))


def _fraction(saved: float, of: float) -> float:
    return 0.0 if of == 0 else round(saved / of, 6)


def build_proof_card(
    workload: str,
    pairs: list[PairedCase],
    per_mechanism: dict[str, float] | None = None,
) -> ProofCard:
    """Compute the card. Only quality-matched pairs contribute to savings."""
    if not pairs:
        raise ValueError("a proof card needs at least one paired case")

    matched = [pair for pair in pairs if pair.quality_matched]
    if not matched:
        raise ValueError(
            "no pair passed in both arms; comparing spend across different outcomes "
            "would report a saving that bought a worse answer"
        )

    baseline_tokens = sum(p.baseline.tokens for p in matched)
    governed_tokens = sum(p.governed.tokens for p in matched)
    overhead_tokens = sum(p.governed.governor_overhead_tokens for p in matched)
    baseline_cost = sum(p.baseline.cost for p in matched)
    governed_cost = sum(p.governed.cost for p in matched)
    overhead_cost = sum(p.governed.governor_overhead_cost for p in matched)
    baseline_calls = sum(p.baseline.tool_calls for p in matched)
    governed_calls = sum(p.governed.tool_calls for p in matched)

    # Gross excludes the governor's own spend; net includes it. The governed
    # totals already carry overhead, so gross adds it back rather than net
    # subtracting it — stating which direction the arithmetic runs matters.
    gross_tokens = baseline_tokens - (governed_tokens - overhead_tokens)
    net_tokens = baseline_tokens - governed_tokens
    gross_cost = baseline_cost - (governed_cost - overhead_cost)
    net_cost = baseline_cost - governed_cost

    per_case = [
        _fraction(p.baseline.tokens - p.governed.tokens, p.baseline.tokens) for p in matched
    ]

    savings = Savings(
        gross_tokens=gross_tokens,
        net_tokens=net_tokens,
        gross_token_fraction=_fraction(gross_tokens, baseline_tokens),
        net_token_fraction=_fraction(net_tokens, baseline_tokens),
        gross_cost=round(gross_cost, 6),
        net_cost=round(net_cost, 6),
        net_cost_fraction=_fraction(net_cost, baseline_cost),
        tool_calls_saved=baseline_calls - governed_calls,
        tool_call_fraction=_fraction(baseline_calls - governed_calls, baseline_calls),
        overhead_tokens=overhead_tokens,
        overhead_share=_fraction(overhead_tokens, governed_tokens),
    )

    return ProofCard(
        workload=workload,
        pairs=tuple(pairs),
        quality_matched_pairs=len(matched),
        savings=savings,
        per_mechanism=dict(sorted((per_mechanism or {}).items())),
        baseline_passes=sum(1 for p in pairs if p.baseline_passed),
        governed_passes=sum(1 for p in pairs if p.governed_passed),
        case_count=len(pairs),
        median_net_token_fraction=round(statistics.median(per_case), 6),
        gate_qualifiers=tuple(sorted({p.gate_qualifier for p in pairs})),
        run_seals=tuple(
            sorted({p.baseline_seal for p in pairs} | {p.governed_seal for p in pairs})
        ),
    )


def headline(card: ProofCard) -> dict[str, Any]:
    """What may be quoted, with what must accompany it."""
    return {
        "net_token_reduction": card.savings.net_token_fraction,
        "gross_token_reduction": card.savings.gross_token_fraction,
        # Zero where the cost table was unpriced, which the manifest's
        # `cost_table_version` records. FR66 sets a target for it, so it has to
        # be quotable or the target has nothing to be checked against.
        "net_cost_reduction": card.savings.net_cost_fraction,
        "governor_overhead_share": card.savings.overhead_share,
        "baseline_passes": card.baseline_passes,
        "governed_passes": card.governed_passes,
        "case_count": card.case_count,
        "median_net_token_reduction": card.median_net_token_fraction,
        "per_mechanism": card.per_mechanism,
        "gate_qualifiers": list(card.gate_qualifiers),
    }
