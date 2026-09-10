"""The calibration overhead study (§8.5, FR66, FR102, AD-3).

§8.5 gives the calibration set one job before any evaluation result exists:
*measure governor overhead, determine break-even behaviour, and establish the
targets and thresholds FR66 requires.* This module does the measuring. It does
**not** set the targets — deriving them is a judgement with claim consequences,
and a target that arrives with the measurement is a target nobody chose.

What it measures, and why each is separate:

- **Token overhead.** What the governor spends on its own behalf, from the
  Ledger's `overhead` holds rather than from a counter kept alongside them.
  With only deterministic mechanisms registered this is structurally zero, and
  the study says so rather than implying a cost that is not there.
- **Added latency.** Wall clock per decision against the same work done with no
  governor in the call path — FR52's OFF is an adapter state, so the baseline
  arm here really does share no governor code.

Latency is reported as a distribution, never a mean. A mean added latency hides
exactly the tail that makes a governor unacceptable in production, and the
durable write behind every decision (AD-16 runs `synchronous=FULL`) is the kind
of cost that lives in the tail rather than the middle.
"""

from __future__ import annotations

import platform
import statistics
import sys
import time
from collections.abc import Callable, Sequence
from typing import Final

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..core.canon import Digest, hash_structure
from .preregistration import Preregistration

#: Enough samples for a p95 to mean something, small enough to run in a test.
DEFAULT_REPEATS: Final[int] = 200


class OverheadRefused(RuntimeError):
    """The study was asked for something it must not supply."""


class Latencies(BaseModel):
    """A distribution. Never a mean: the tail is the part that bites."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    samples: int = Field(gt=0)
    p50_ns: int = Field(ge=0)
    p95_ns: int = Field(ge=0)
    max_ns: int = Field(ge=0)

    @model_validator(mode="after")
    def _ordered(self) -> Latencies:
        if not self.p50_ns <= self.p95_ns <= self.max_ns:
            raise ValueError(
                f"percentiles are out of order: {self.p50_ns} / {self.p95_ns} / {self.max_ns}"
            )
        return self

    @property
    def p50_ms(self) -> float:
        return round(self.p50_ns / 1_000_000, 4)

    @property
    def p95_ms(self) -> float:
        return round(self.p95_ns / 1_000_000, 4)


class OverheadStudy(BaseModel):
    """A measurement, hashed so a preregistration can cite it by content."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    recorded_at: str
    workload: str = Field(min_length=1)
    split: str = "calibration"
    governed: Latencies
    baseline: Latencies
    #: From the Ledger's overhead holds. Zero where every registered mechanism
    #: is deterministic, which is the protected core with E12 cut.
    governor_overhead_tokens: int = Field(ge=0)
    governed_tokens: int = Field(ge=0)
    enabled_mechanisms: tuple[str, ...] = ()
    #: The decision log's cost, isolated. Every decision appends several rows,
    #: each an fsync under AD-16's `synchronous=FULL`, so this is where the
    #: added latency mostly lives — and it buys FR5's guarantee that a decision
    #: is recorded before it takes effect rather than buying any governing.
    events_per_decision: int = Field(gt=0)
    durable_write_p50_ns: int = Field(ge=0)
    python_version: str
    platform: str

    @model_validator(mode="after")
    def _calibration_only(self) -> OverheadStudy:
        if self.split != "calibration":
            raise ValueError(
                "an overhead study runs on the calibration set; measuring it on the "
                "evaluation set would inspect the results the split exists to seal (§8.5)"
            )
        return self

    @property
    def added_latency_p50_ms(self) -> float:
        return round((self.governed.p50_ns - self.baseline.p50_ns) / 1_000_000, 4)

    @property
    def added_latency_p95_ms(self) -> float:
        return round((self.governed.p95_ns - self.baseline.p95_ns) / 1_000_000, 4)

    @property
    def token_overhead_share(self) -> float:
        if self.governed_tokens == 0:
            return 0.0
        return round(self.governor_overhead_tokens / self.governed_tokens, 6)

    @property
    def write_p50_ns(self) -> int:
        return self.events_per_decision * self.durable_write_p50_ns

    @property
    def write_share_of_added_latency(self) -> float:
        """How much of the governor's cost is durability rather than governing."""
        added = self.governed.p50_ns - self.baseline.p50_ns
        if added <= 0:
            return 0.0
        return round(min(self.write_p50_ns / added, 1.0), 6)

    @property
    def breaks_even_immediately(self) -> bool:
        """With no token overhead, any positive gross saving is also net."""
        return self.governor_overhead_tokens == 0

    def digest(self) -> Digest:
        return hash_structure(self.model_dump(mode="json"))

    def render(self) -> str:
        lines = [
            f"# Overhead study — {self.workload} ({self.split})",
            f"recorded_at        {self.recorded_at}",
            f"environment        python {self.python_version} on {self.platform}",
            f"mechanisms         {', '.join(self.enabled_mechanisms) or 'none'}",
            "",
            f"baseline  p50      {self.baseline.p50_ms} ms",
            f"baseline  p95      {self.baseline.p95_ms} ms",
            f"governed  p50      {self.governed.p50_ms} ms",
            f"governed  p95      {self.governed.p95_ms} ms",
            f"added     p50      {self.added_latency_p50_ms} ms",
            f"added     p95      {self.added_latency_p95_ms} ms",
            "",
            f"of which writing   {round(self.write_p50_ns / 1_000_000, 4)} ms "
            f"({self.write_share_of_added_latency:.1%}) — "
            f"{self.events_per_decision} durable appends per decision",
            "",
            f"governor tokens    {self.governor_overhead_tokens} "
            f"of {self.governed_tokens} ({self.token_overhead_share:.1%})",
            f"breaks even        {'immediately' if self.breaks_even_immediately else 'no'}",
            "",
            "This study sets no targets. FR66's thresholds are a judgement made "
            "from these numbers, not read off them.",
            f"digest             {self.digest().sha256}",
        ]
        return "\n".join(lines)


def measure(operation: Callable[[int], None], *, repeats: int = DEFAULT_REPEATS) -> Latencies:
    """Time one operation `repeats` times and return its distribution.

    `perf_counter_ns` rather than `time()`: the quantity is an interval on this
    machine, and a wall clock that can step is the wrong instrument for it.
    """
    if repeats < 1:
        raise ValueError("a distribution needs at least one sample")
    timings: list[int] = []
    for n in range(repeats):
        started = time.perf_counter_ns()
        operation(n)
        timings.append(time.perf_counter_ns() - started)

    ordered = sorted(timings)
    return Latencies(
        samples=len(ordered),
        p50_ns=int(statistics.median(ordered)),
        p95_ns=ordered[min(len(ordered) - 1, int(len(ordered) * 0.95))],
        max_ns=ordered[-1],
    )


def build_study(
    *,
    recorded_at: str,
    workload: str,
    governed: Latencies,
    baseline: Latencies,
    governor_overhead_tokens: int,
    governed_tokens: int,
    events_per_decision: int,
    durable_write_p50_ns: int,
    enabled_mechanisms: Sequence[str] = (),
) -> OverheadStudy:
    return OverheadStudy(
        recorded_at=recorded_at,
        workload=workload,
        governed=governed,
        baseline=baseline,
        governor_overhead_tokens=governor_overhead_tokens,
        governed_tokens=governed_tokens,
        events_per_decision=events_per_decision,
        durable_write_p50_ns=durable_write_p50_ns,
        enabled_mechanisms=tuple(enabled_mechanisms),
        python_version=platform.python_version(),
        platform=f"{sys.platform}",
    )


def check_targets_are_derived(
    preregistration: Preregistration, study: OverheadStudy
) -> list[str]:
    """§8.5: targets are *derived* from measured overhead, never guessed.

    The PRD says so in prose and nothing enforced it, so a preregistration could
    cite an overhead study it had never seen. Citing the study by content
    closes that: the digest changes if the measurement does.
    """
    findings: list[str] = []
    if study.digest().sha256 not in preregistration.derived_from:
        findings.append(
            "the preregistration does not cite this study's digest, so its targets "
            "are asserted rather than derived from a measurement (§8.5)"
        )
    if preregistration.recorded_at < study.recorded_at:
        findings.append(
            f"the preregistration is dated {preregistration.recorded_at}, before the "
            f"study it claims to derive from ({study.recorded_at})"
        )
    return findings
