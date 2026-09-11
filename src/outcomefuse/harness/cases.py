"""Case records, loaded from the frozen case sets.

**A case's `reference` is key-derivation material and is not loaded.** For
data-sql it holds the query that produces the answer; for code-triage the file
and anchor of the defect. Only the three keys the frozen prompt README names as
placeholder sources survive into a `Case`, so the runtime cannot leak an answer
into a prompt even by accident — it never holds one.

Everything else here is what the harness needs to run a case and nothing more.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Final

import yaml
from pydantic import BaseModel, ConfigDict, Field

from ..core.record import DataClass, Split

ROOT: Final[Path] = Path(__file__).resolve().parents[3]

#: The only reference keys a prompt may be built from, per
#: `freeze/baseline-prompts/README.md`. Everything else in a reference exists
#: to derive the answer key, and the runtime has no business seeing it.
#:
#: A case may also carry `prompt_context` directly. The two exist separately
#: because `reference` means *key-derivation input* — the deriver refuses an
#: unanswerable case that carries any — while a prompt parameter is just what
#: the question asks about, and the unanswerable cases need one without having
#: an answer to derive.
PROMPT_CONTEXT_KEYS: Final[frozenset[str]] = frozenset({"as_of", "region", "po_id"})


class CaseError(ValueError):
    """The case set could not be loaded, or a case is unusable."""


class Case(BaseModel):
    """One case, carrying what a run needs and nothing that would give it away."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    case_id: str = Field(min_length=1)
    workload: str = Field(min_length=1)
    split: Split
    difficulty: str
    #: `answer` or `partial`. Eight of the eighty cases are `partial` — the
    #: corpus cannot support a full answer and the right move is to say so —
    #: and no prompt says which. `is_unanswerable` tests against `answer`
    #: rather than for `partial`, so a third value added later is treated as
    #: not-fully-answerable rather than silently scored as answerable.
    expected_outcome: str
    prompt: str = Field(min_length=1)
    #: What a coin-flip would score. Present so a result can be compared
    #: against guessing rather than against zero.
    guess_baseline: float = Field(default=0.0, ge=0, le=1)
    #: The allow-listed subset of the case's reference. Never the whole of it.
    prompt_context: dict[str, Any] = Field(default_factory=dict)

    @property
    def is_unanswerable(self) -> bool:
        return self.expected_outcome != "answer"


class CaseSet(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    workload: str = Field(min_length=1)
    split: Split
    data_class: DataClass
    corpus_ref: str = Field(min_length=1)
    cases: tuple[Case, ...] = Field(min_length=1)

    def by_id(self, case_id: str) -> Case:
        for case in self.cases:
            if case.case_id == case_id:
                return case
        raise CaseError(f"no case {case_id!r} in {self.split}/{self.workload}")


def load_case_set(workload: str, split: str) -> CaseSet:
    """Load one frozen case set, dropping every reference key not allow-listed."""
    path = ROOT / "cases" / split / workload / "cases.yaml"
    if not path.is_file():
        raise CaseError(f"no case set at {path}")
    document = yaml.safe_load(path.read_text(encoding="utf-8"))

    if document["workload"] != workload or document["split"] != split:
        raise CaseError(
            f"{path} declares {document['split']}/{document['workload']}, "
            f"which is not the {split}/{workload} it was loaded as"
        )

    cases = []
    for raw in document["cases"]:
        # `prompt_context` where the case states it; otherwise the allow-listed
        # slice of `reference`. Either way only the three keys survive.
        supplied = raw.get("prompt_context") or raw.get("reference") or {}
        cases.append(
            Case(
                case_id=raw["case_id"],
                workload=workload,
                split=split,
                difficulty=raw["difficulty"],
                expected_outcome=raw["expected_outcome"],
                prompt=raw["prompt"],
                guess_baseline=raw.get("guess_baseline", 0.0),
                prompt_context={
                    key: value
                    for key, value in supplied.items()
                    if key in PROMPT_CONTEXT_KEYS
                },
            )
        )

    return CaseSet(
        workload=workload,
        split=split,
        data_class=document["data_class"],
        corpus_ref=document["corpus_ref"],
        cases=tuple(cases),
    )
