"""The submission artifact (E15, F16, FR81-FR84, §8.4).

Two minutes, four beats, and every number in them traceable to a run that
satisfies §8. The video is not code; the thing that can be got wrong is which
figures are allowed into it and what has to be said alongside them — so that is
what lives here.

**F16 depends on F13 and F12, never on F14.** Everything below is assembled
from the recorded proof card and the decision records. The viewer sits first in
the cut order, and a protected artifact that could only be produced by a
cut-first component would be protected in name only.

The uncomfortable case this module is built for is the one where the run
succeeded and the claim is still wrong: a calibration figure quoted as a
result, a shadow projection shown as realized savings, a gross number leading
because it is larger, a single flattering case standing in for a workload.
Every one of those is a refusal here rather than a note in a review checklist.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Final

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..core.canon import Digest, hash_structure
from ..core.record import Event
from ..harness import Preregistration, ProofCard, Reportability
from .disclosures import DISCLOSURE_KEYS, FROZEN_DEFECTS, Disclosure
from .figures import Figure

#: FR81, in order. The order is the argument: what is wrong, what was built,
#: what it proves, and why it holds beyond the demo.
BEAT_ORDER: Final[tuple[str, ...]] = ("problem", "artifact", "proof", "scale")

MAX_SECONDS: Final[int] = 120

#: FR84's minimum. Showing results without showing the mechanism running is how
#: a system that does not work produces a convincing video.
REQUIRED_DEMONSTRATIONS: Final[frozenset[str]] = frozenset(
    {"outcome-contract", "decision-stream", "sufficiency-stop"}
)


class SubmissionRefused(ValueError):
    """The submission would have shown something §8 does not permit."""


class MechanismEvidence(BaseModel):
    """Proof that a recorded run actually did what the video says it does.

    Derived from a decision log rather than asserted, so a demonstration cannot
    be promised for behaviour no run exhibits.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    run_id: str = Field(min_length=1)
    seal: str = Field(pattern=r"^[0-9a-f]{64}$")
    contract_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    decisions: tuple[tuple[str, str], ...] = Field(min_length=1)
    sufficiency_stop: bool

    @property
    def demonstrates(self) -> frozenset[str]:
        shown = {"outcome-contract", "decision-stream"}
        if self.sufficiency_stop:
            shown.add("sufficiency-stop")
        return frozenset(shown)


def evidence_of_mechanism(events: Iterable[Event], *, seal: str) -> MechanismEvidence:
    """Read FR84's three demonstrations out of one run's observed lane."""
    rows = [e for e in events if e.lane == "observed"]
    if not rows or rows[0].kind != "run-manifest":
        raise SubmissionRefused("a demonstration needs a run whose log opens with its manifest")

    manifest = rows[0].payload.get("manifest", {})
    contract_hash = manifest.get("contract_hash")
    if not contract_hash:
        raise SubmissionRefused(f"run {rows[0].run_id!r} records no contract hash to show")

    decisions = tuple(
        (e.policy_action, e.decision_reason or "")
        for e in rows
        if e.kind == "decision-recorded" and e.policy_action
    )
    if not decisions:
        raise SubmissionRefused(f"run {rows[0].run_id!r} has no decision stream to show")

    return MechanismEvidence(
        run_id=rows[0].run_id,
        seal=seal,
        contract_hash=contract_hash,
        decisions=decisions,
        sufficiency_stop=any(
            e.decision_reason == "sufficiency" and e.terminal_reason == "stop-sufficient"
            for e in rows
        ),
    )


class Beat(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    seconds: int = Field(gt=0)
    says: str = Field(min_length=1)
    figures: tuple[Figure, ...] = ()
    shows: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _known(self) -> Beat:
        if self.name not in BEAT_ORDER:
            raise ValueError(f"{self.name!r} is not one of FR81's beats: {BEAT_ORDER}")
        unknown = sorted(set(self.shows) - REQUIRED_DEMONSTRATIONS)
        if unknown:
            raise ValueError(f"unknown demonstrations: {unknown}")
        return self


class Submission(BaseModel):
    """The shooting script, with every figure carrying its provenance."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    beats: tuple[Beat, ...]
    mechanism: MechanismEvidence
    #: §8.4: no claim of measured generalization beyond what was completed.
    workloads_completed: tuple[str, ...] = Field(min_length=1)
    #: §8.2: defects found after the first run are worked around and disclosed.
    #: Defaults to the full registry so omitting them takes a deliberate act,
    #: and the validator below refuses that act.
    disclosures: tuple[Disclosure, ...] = FROZEN_DEFECTS

    @model_validator(mode="after")
    def _well_formed(self) -> Submission:
        if tuple(b.name for b in self.beats) != BEAT_ORDER:
            raise ValueError(
                f"FR81 wants {BEAT_ORDER} in that order, got "
                f"{tuple(b.name for b in self.beats)}"
            )
        if self.seconds > MAX_SECONDS:
            raise ValueError(f"the video runs {self.seconds}s, over FR81's {MAX_SECONDS}s")

        undisclosed = sorted(DISCLOSURE_KEYS - {d.key for d in self.disclosures})
        if undisclosed:
            # The entries are the ones that make the number look worse, which is
            # exactly why dropping them cannot be left to an author's judgement
            # on the last day.
            raise ValueError(
                f"§8.2 requires every frozen-in defect to be disclosed; missing "
                f"{undisclosed}"
            )

        promised = {show for beat in self.beats for show in beat.shows}
        missing = sorted(REQUIRED_DEMONSTRATIONS - promised)
        if missing:
            raise ValueError(f"FR84's minimum is not shown: {missing}")
        unbacked = sorted(promised - self.mechanism.demonstrates)
        if unbacked:
            raise ValueError(
                f"promised but not present in the recorded run: {unbacked}; a "
                "demonstration is shown from an artifact, not re-enacted"
            )

        if len(self.headlines) > 1:
            raise ValueError(
                f"{len(self.headlines)} headline figures; one number leads or the "
                "audience picks the largest"
            )
        return self

    @property
    def seconds(self) -> int:
        return sum(beat.seconds for beat in self.beats)

    @property
    def figures(self) -> tuple[Figure, ...]:
        return tuple(figure for beat in self.beats for figure in beat.figures)

    @property
    def headlines(self) -> tuple[Figure, ...]:
        return tuple(f for f in self.figures if f.headline)

    def digest(self) -> Digest:
        return hash_structure(self.model_dump(mode="json"))

    def render(self) -> str:
        """The script as text, with every figure rendered with its labels."""
        lines = [f"# Submission — {self.seconds}s / {MAX_SECONDS}s"]
        for beat in self.beats:
            lines.append(f"\n## {beat.name} ({beat.seconds}s)")
            lines.append(beat.says)
            for show in sorted(beat.shows):
                lines.append(f"- shows: {show} (run {self.mechanism.run_id})")
            for figure in beat.figures:
                marker = "HEADLINE " if figure.headline else ""
                lines.append(f"- {marker}{figure.rendered()}")
        if self.disclosures:
            lines.append("\n## Disclosed (§8.2)")
            for disclosure in self.disclosures:
                lines.append(
                    f"- **{disclosure.key}** ({disclosure.direction}): "
                    f"{disclosure.finding} Not fixed: {disclosure.why_not_fixed} "
                    f"Instead: {disclosure.workaround}"
                )
        return "\n".join(lines)


def check_submission(
    submission: Submission,
    *,
    cards: Sequence[ProofCard],
    preregistration: Preregistration | None,
    reportability: Reportability | None,
) -> list[str]:
    """FR82: every figure traceable to an artifact that satisfies §8.

    Returns refusals rather than raising, so an author sees all of them at once
    rather than fixing them one screening at a time.
    """
    refusals: list[str] = []
    admitted = {card.digest().sha256 for card in cards}
    for card in cards:
        admitted.update(card.run_seals)
    admitted.add(submission.mechanism.seal)

    for figure in submission.figures:
        if figure.provenance.digest not in admitted:
            refusals.append(
                f"{figure.key!r} cites {figure.provenance.digest[:12]}…, which is not "
                "the digest of any proof card or run seal supplied"
            )
        if figure.role == "claim" and figure.provenance.workload not in (
            submission.workloads_completed
        ):
            refusals.append(
                f"{figure.key!r} claims for workload {figure.provenance.workload!r}, "
                "which is not among the workloads completed (§8.4)"
            )

    claims = [f for f in submission.figures if f.role == "claim"]
    if claims:
        if preregistration is None:
            refusals.append(
                "no preregistration record: targets and thresholds are recorded before "
                "any evaluation-set result is executed or inspected (FR66, FR102)"
            )
        else:
            for figure in claims:
                if figure.provenance.case_count < preregistration.minimum_case_count:
                    refusals.append(
                        f"{figure.key!r} rests on {figure.provenance.case_count} cases, "
                        f"below the preregistered minimum of "
                        f"{preregistration.minimum_case_count} (FR59)"
                    )

    if submission.headlines:
        if reportability is None:
            refusals.append("a headline figure without a reportability assessment (AD-10)")
        elif not reportability.publishable:
            refusals.append(
                "the headline rests on a comparison the harness refused: "
                + "; ".join(reportability.refusals)
            )

    return refusals


def build_submission(
    beats: Sequence[Beat],
    *,
    mechanism: MechanismEvidence,
    workloads_completed: Sequence[str],
    cards: Sequence[ProofCard] = (),
    preregistration: Preregistration | None = None,
    reportability: Reportability | None = None,
) -> Submission:
    """Assemble it, or refuse. There is no partially-admissible submission."""
    submission = Submission(
        beats=tuple(beats),
        mechanism=mechanism,
        workloads_completed=tuple(workloads_completed),
    )
    refusals = check_submission(
        submission,
        cards=cards,
        preregistration=preregistration,
        reportability=reportability,
    )
    if refusals:
        raise SubmissionRefused("; ".join(refusals))
    return submission
