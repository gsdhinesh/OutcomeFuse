"""The preregistration record (FR66, FR102, AD-9).

Targets and thresholds are recorded **before any governed evaluation-set result
is executed or inspected**. A target set after the results are known cannot be
missed, and may not be reported as having been met.

The PRD leaves every number deliberately unset — they are to be derived from the
overhead study on the calibration set. So nothing here supplies a default: the
values are required fields, and a record missing one is refused rather than
filled in. A counter-metric without a threshold cannot fail, and a
counter-metric that cannot fail is decoration.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Final

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..core.canon import Digest, hash_structure

#: §3.3. Every one carries a numeric threshold, set before any evaluation result
#: is executed or inspected.
COUNTER_METRICS: Final[frozenset[str]] = frozenset(
    {
        "false-sufficiency-rate",
        "tool-suppression-error-rate",
        "escalation-rate",
        "governor-overhead-share",
        "added-latency",
        "budget-breach-rate",
    }
)

_TIMESTAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d{1,6})?Z$")


class PreregistrationError(ValueError):
    """The record is incomplete, so no evaluation result may be claimed against it."""


class SavingsTargets(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    net_token_reduction: float = Field(ge=0, le=1)
    net_cost_reduction: float = Field(ge=0, le=1)
    tool_call_reduction: float = Field(ge=0, le=1)


class Preregistration(BaseModel):
    """Its own hashed, timestamped artifact. Every evaluation manifest cites it."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    recorded_at: str
    #: Derived from measured overhead on the calibration set, never guessed.
    savings: SavingsTargets
    quality_target_pass_rate: float = Field(ge=0, le=1)
    counter_metric_thresholds: dict[str, float]
    minimum_case_count: int = Field(gt=0)
    blind_review_sample_size: int = Field(gt=0)
    derived_from: str = Field(min_length=1)

    @model_validator(mode="after")
    def _complete(self) -> Preregistration:
        if not _TIMESTAMP.match(self.recorded_at):
            raise ValueError(f"recorded_at must be RFC 3339 UTC with Z: {self.recorded_at!r}")
        missing = sorted(COUNTER_METRICS - set(self.counter_metric_thresholds))
        if missing:
            raise ValueError(
                f"counter-metrics without a threshold: {missing}; one that cannot fail "
                "is decoration"
            )
        unknown = sorted(set(self.counter_metric_thresholds) - COUNTER_METRICS)
        if unknown:
            raise ValueError(f"unknown counter-metrics: {unknown}")
        return self

    def digest(self) -> Digest:
        return hash_structure(self.model_dump(mode="json"))


ROOT: Final[Path] = Path("preregistration")


def load_preregistration(version: str, *, root: Path | None = None) -> Preregistration:
    """Load a committed record. Never constructs a default.

    A missing record is an error rather than an empty one, because an empty
    preregistration is indistinguishable from a permissive one: no target to
    miss, no threshold to breach, and every result reportable.
    """
    path = (root or ROOT) / f"{version}.yaml"
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise PreregistrationError(f"no preregistration {version!r} at {path}") from exc
    except yaml.YAMLError as exc:
        raise PreregistrationError(f"{path} is not readable YAML: {exc}") from exc
    try:
        return Preregistration.model_validate(raw)
    except ValueError as exc:
        raise PreregistrationError(f"{path} is not a usable preregistration: {exc}") from exc
