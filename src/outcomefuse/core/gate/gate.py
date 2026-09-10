"""The Quality Gate (FR19-FR26, FR94, FR105).

**Deterministic criterion-level validation is the authoritative gate.** A
model-judged rubric may contribute an additional signal, but may not override a
deterministic failure and may not alone establish a pass — so advisory signals
are recorded here and are structurally unable to reach the verdict.

The verdict is **binary**. A `pass-with-concern` state would have to resolve
somewhere: either the policy stops on it, in which case it was a pass, or it
does not, in which case it was a fail. A third state moves that judgement out of
the contract and into the runtime. Concerns are real, and they belong in the
decision record and the counter-metrics where they can be measured.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from ..contract import Contract
from ..verify import CitableIndex, Outcome, VerifierError, verify

VerdictValue = Literal["pass", "fail"]
Qualifier = Literal["reference-backed", "constraint-backed"]


class GateUnavailable(RuntimeError):
    """The gate could not produce a verdict.

    Distinct from `fail`, and the distinction is load-bearing: FR103 maps an
    unavailable gate to `fail-closed`, whereas a failing gate with budget left
    is a retry or an escalation. Returning `fail` here would silently convert a
    broken verifier into a quality judgement about the deliverable.
    """


class CriterionResult(BaseModel):
    """One criterion's outcome. FR26 wants these, not only an aggregate."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    tier: str
    passed: bool
    mode: Qualifier
    verifier: str
    detail: str = ""


class AdvisorySignal(BaseModel):
    """A model-judged observation. Recorded, never gating (FR20, FR22)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    source: str
    criterion_id: str | None = None
    observation: str


class Verdict(BaseModel):
    """Binary, qualified, and carrying its per-criterion breakdown (FR94)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    verdict: VerdictValue
    qualifier: Qualifier
    breakdown: tuple[CriterionResult, ...]
    unmet: tuple[str, ...] = ()
    advisory: tuple[AdvisorySignal, ...] = ()
    #: Recorded alongside the verdict rather than recomputed by a reader.
    mandatory_evaluated: int = Field(ge=0)

    @property
    def passed(self) -> bool:
        return self.verdict == "pass"


class QualityGate:
    """Evaluates a deliverable against a contract's mandatory criteria."""

    def evaluate(
        self,
        contract: Contract,
        deliverable: Mapping[str, Any],
        *,
        answer_key: Mapping[str, Any] | None = None,
        citable_index: CitableIndex | None = None,
        advisory: tuple[AdvisorySignal, ...] = (),
    ) -> Verdict:
        breakdown: list[CriterionResult] = []
        unmet: list[str] = []

        for criterion in contract.criteria.mandatory:
            spec = criterion.verifier
            if spec is None:
                # Contract validation forbids this; reaching it means the
                # contract was built by some path that skipped validation.
                raise GateUnavailable(
                    f"mandatory criterion {criterion.id!r} carries no verifier"
                )
            try:
                outcome: Outcome = verify(
                    spec.type,
                    spec.args,
                    deliverable,
                    answer_key=answer_key,
                    citable_index=citable_index,
                )
            except (VerifierError, ValueError) as exc:
                raise GateUnavailable(
                    f"criterion {criterion.id!r} could not be evaluated: {exc}"
                ) from exc

            breakdown.append(
                CriterionResult(
                    id=criterion.id,
                    tier="mandatory",
                    passed=outcome.passed,
                    mode=outcome.mode,
                    verifier=spec.type,
                    detail=outcome.detail,
                )
            )
            if not outcome.passed:
                unmet.append(criterion.id)

        # FR19: optional and enrichment criteria are recorded but never gate.
        for tier in ("optional",):
            for criterion in getattr(contract.criteria, tier):
                spec = criterion.verifier
                if spec is None:
                    continue
                try:
                    outcome = verify(
                        spec.type,
                        spec.args,
                        deliverable,
                        answer_key=answer_key,
                        citable_index=citable_index,
                    )
                except (VerifierError, ValueError):
                    # An optional criterion that cannot run does not make the
                    # gate unavailable; it simply contributes nothing.
                    continue
                breakdown.append(
                    CriterionResult(
                        id=criterion.id,
                        tier=tier,
                        passed=outcome.passed,
                        mode=outcome.mode,
                        verifier=spec.type,
                        detail=outcome.detail,
                    )
                )

        mandatory = [r for r in breakdown if r.tier == "mandatory"]
        if not mandatory:
            raise GateUnavailable("a contract with no mandatory criteria has no floor")

        # FR21: only a verdict in which every mandatory criterion was
        # reference-backed may be labelled reference-backed.
        qualifier: Qualifier = (
            "reference-backed"
            if all(r.mode == "reference-backed" for r in mandatory)
            else "constraint-backed"
        )

        return Verdict(
            verdict="fail" if unmet else "pass",
            qualifier=qualifier,
            breakdown=tuple(breakdown),
            unmet=tuple(unmet),
            advisory=tuple(advisory),
            mandatory_evaluated=len(mandatory),
        )
