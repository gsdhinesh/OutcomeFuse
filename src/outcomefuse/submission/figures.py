"""What a figure has to carry before it may be shown (FR82, FR83, §8.4).

The submission is the artifact that actually gets judged, which makes it the
place where a number is most likely to arrive without the sentence that
qualifies it. So a figure is not a number here. It is a number **plus its
provenance and its labels**, and one that cannot say where it came from cannot
be constructed at all.

Three rules do most of the work, and each closes a specific way the headline
could be true and misleading at once:

- **Evaluation set or it is not a claim.** Calibration results measured the
  overhead that set the targets, so quoting them is quoting the ruler as the
  measurement (§8.5).
- **Shadow figures are never claims.** Only the observed path of a shadow run
  executed; the governed one is inference. It may be shown, labelled
  `projected`, and it may not be presented as realized savings (FR49, FR83).
- **Net leads.** Gross excludes the governor's own spend, which is how this
  category flatters itself. Gross may sit alongside; it may never be the
  headline (FR61).
"""

from __future__ import annotations

from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..core.canon import Digest, hash_structure
from ..core.record import Mode, Split

_SHA256 = r"^[0-9a-f]{64}$"

#: What a figure may be measured in. `net` and `gross` are savings; the other
#: two are the counts and rates that must accompany them.
Basis = Literal["net", "gross", "count", "rate"]

#: A claim backs an assertion about the system. An illustration shows the
#: mechanism working and asserts nothing about how well it works.
Role = Literal["claim", "illustration"]

#: §8.4's labels. Each attaches to a figure for a structural reason, so each is
#: derived from the run's own facts rather than typed in by whoever is editing.
PROJECTED: Final[str] = "projected"
SELF_REPORTED: Final[str] = "self-reported"
DEGRADED: Final[str] = "degraded"
CONSTRAINT_BACKED: Final[str] = "constraint-backed"


class FigureRefused(ValueError):
    """A figure was assembled without what §8.4 requires it to carry."""


class Provenance(BaseModel):
    """Where a figure came from, in enough detail to go and check it."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    artifact: Literal["proof-card", "decision-record"]
    #: The proof card's digest, or the run seal. Either way it is checkable
    #: outside the database that produced it.
    digest: str = Field(pattern=_SHA256)
    run_ids: tuple[str, ...] = Field(min_length=1)
    split: Split
    mode: Mode
    case_count: int = Field(ge=1)
    workload: str = Field(min_length=1)


def required_labels(
    provenance: Provenance,
    *,
    gateway_metered: bool,
    degraded_mechanisms: tuple[str, ...] = (),
    gate_qualifier: str | None = None,
) -> tuple[str, ...]:
    """The labels this figure must carry, derived from the run rather than chosen.

    Labels propagate upward and never downward: anything attaching to any run
    behind a figure attaches to the figure.
    """
    labels: list[str] = []
    if provenance.mode == "shadow":
        labels.append(PROJECTED)
    if not gateway_metered:
        labels.append(SELF_REPORTED)
    if degraded_mechanisms:
        labels.append(DEGRADED)
    if gate_qualifier == CONSTRAINT_BACKED:
        labels.append(CONSTRAINT_BACKED)
    return tuple(sorted(labels))


class Figure(BaseModel):
    """A number that knows where it came from and what must be said about it."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    key: str = Field(min_length=1)
    value: float | int | str
    basis: Basis
    role: Role
    provenance: Provenance
    labels: tuple[str, ...] = ()
    #: At most one figure in a submission is the headline (FR61, FR62).
    headline: bool = False

    @model_validator(mode="after")
    def _carries_what_it_must(self) -> Figure:
        if self.role == "claim":
            if self.provenance.split != "evaluation":
                raise ValueError(
                    f"{self.key!r} is drawn from the {self.provenance.split} set; only "
                    "evaluation-set results may support a claim (FR82, §8.5)"
                )
            if self.provenance.mode == "shadow":
                raise ValueError(
                    f"{self.key!r} comes from a shadow run, where only the observed "
                    "path executed; it may be shown as a projected illustration and "
                    "never as realized savings (FR83)"
                )
            if self.provenance.case_count < 2:
                raise ValueError(
                    f"{self.key!r} rests on {self.provenance.case_count} case; a "
                    "single-run figure is not a claim (FR83)"
                )
        if self.provenance.mode == "shadow" and PROJECTED not in self.labels:
            raise ValueError(f"{self.key!r} is a shadow figure and is not labelled projected")
        if self.headline:
            if self.role != "claim":
                raise ValueError(f"the headline {self.key!r} must be a claim")
            if self.basis != "net":
                raise ValueError(
                    f"the headline {self.key!r} is {self.basis}; net is the headline and "
                    "gross may only sit beside it (FR61)"
                )
        return self

    def rendered(self) -> str:
        """The figure as it must appear: never the number on its own."""
        labels = f" [{', '.join(self.labels)}]" if self.labels else ""
        return (
            f"{self.key} = {self.value} ({self.basis}, n={self.provenance.case_count}, "
            f"{self.provenance.workload}, {self.provenance.split}){labels}"
        )

    def digest(self) -> Digest:
        return hash_structure(self.model_dump(mode="json"))
