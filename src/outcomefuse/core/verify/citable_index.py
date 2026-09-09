"""The citable index (AD-7) — a pinned argument, not a lookup.

`citation-resolves` is handed this by its caller and never fetches anything. The
index is a core-owned typed model so two implementations cannot derive it
differently and reach different verdicts on the same run; its AD-6 hash is
appended before any verifier is invoked.
"""

from __future__ import annotations

import re
from typing import Final

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..canon import Digest, hash_structure

#: An index large enough to hold a whole corpus is a sign the driver stopped
#: deriving and started dumping.
MAX_ENTRIES: Final[int] = 4096
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/:-]{0,255}$")


class CitableEntry(BaseModel):
    """One thing a deliverable is allowed to cite."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    target: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @field_validator("id")
    @classmethod
    def _id_is_well_formed(cls, value: str) -> str:
        if not _ID.match(value):
            raise ValueError(f"citable id is not well-formed: {value!r}")
        return value


class CitableIndex(BaseModel):
    """The closed set of citable identifiers for one run."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    entries: tuple[CitableEntry, ...] = ()

    @field_validator("entries")
    @classmethod
    def _entries_are_bounded_and_unique(
        cls, value: tuple[CitableEntry, ...]
    ) -> tuple[CitableEntry, ...]:
        if len(value) > MAX_ENTRIES:
            raise ValueError(f"citable index holds {len(value)} entries, limit is {MAX_ENTRIES}")
        ids = [entry.id for entry in value]
        duplicates = sorted({i for i in ids if ids.count(i) > 1})
        if duplicates:
            raise ValueError(f"duplicate citable ids: {duplicates}")
        return value

    def __contains__(self, identifier: object) -> bool:
        return isinstance(identifier, str) and identifier in self._ids

    @property
    def _ids(self) -> frozenset[str]:
        return frozenset(entry.id for entry in self.entries)

    def digest(self) -> Digest:
        """Hash through the one structure route, entries sorted by id."""
        return hash_structure(
            {
                "entries": [
                    {"id": e.id, "sha256": e.sha256, "target": e.target}
                    for e in sorted(self.entries, key=lambda e: e.id)
                ]
            }
        )
