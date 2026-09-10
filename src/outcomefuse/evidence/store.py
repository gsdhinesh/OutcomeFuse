"""The evidence store (AD-19, AD-21, FR109).

Separate from the decision log, keyed by run and step. The **driver is its sole
writer; the harness is its sole reader**, and verifiers never touch it — they
read the run's derived citable index instead.

**Access is a matrix, not a convention.** Each actor gets a handle that lacks
the methods it is denied, so the blind-review renderer cannot reach the verdict
by mistake or by later edit. Documenting the matrix and enforcing it in review
would leave the one guarantee the false-sufficiency counter-metric rests on
depending on nobody being careless.

Persistence is refused for any `data_class` the MVP profile was not approved
for (AD-21), by the *same rule* the run manifest applies. Refusing only the
evidence would leave the decision record with no permitted retention profile,
and two copies of the rule would drift. A `replayed` run inherits the class of
the run it replays, so replaying captured production traffic is refused rather
than admitted as synthetic.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any, Final

from pydantic import BaseModel, ConfigDict, Field

from ..core.canon import Digest, build_file_manifest, hash_file_manifest
from ..core.record import refuse_persistence

RETENTION_PROFILE: Final[str] = "mvp-synthetic-v1"
#: AD-21: the profile is approved for this class, and for a replay of it.
ADMISSIBLE_DATA_CLASS: Final[str] = "synthetic"


class EvidenceRefused(RuntimeError):
    """Persistence was refused. Never a silent fallback to the MVP profile."""


class AccessDenied(RuntimeError):
    """An actor reached for something the matrix does not grant it."""


class EvidenceRef(BaseModel):
    """What the decision log carries: a reference and a hash, never a body."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    run_id: str = Field(min_length=1)
    relative_path: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class EvidenceStore:
    """One directory per run under `root`. Handles are obtained by role."""

    def __init__(
        self,
        root: Path | str,
        *,
        data_class: str,
        replayed_from_data_class: str | None = None,
    ) -> None:
        refusal = refuse_persistence(data_class, replayed_from_data_class)
        if refusal is not None:
            raise EvidenceRefused(refusal)
        self.root = Path(root)
        self.data_class = data_class
        self.replayed_from_data_class = replayed_from_data_class
        self.retention_profile = RETENTION_PROFILE
        self._sealed = False

    # ------------------------------------------------------------- lifecycle

    def seal(self) -> None:
        """After campaign seal the store refuses to open a writer."""
        self._sealed = True

    @property
    def sealed(self) -> bool:
        return self._sealed

    def run_dir(self, run_id: str) -> Path:
        return self.root / run_id

    def run_ids(self) -> list[str]:
        if not self.root.exists():
            return []
        return sorted(p.name for p in self.root.iterdir() if p.is_dir())

    # ----------------------------------------------------------------- roles

    def for_driver(self, run_id: str) -> DriverHandle:
        if self._sealed:
            raise AccessDenied("the campaign is sealed; no run may join it")
        return DriverHandle(self, run_id)

    def for_harness(self) -> HarnessHandle:
        return HarnessHandle(self)

    def for_retention(self) -> RetentionHandle:
        return RetentionHandle(self)

    def for_blind_review(self, run_id: str) -> BlindReviewHandle:
        return BlindReviewHandle(self, run_id)


class DriverHandle:
    """Write — its own run only. It cannot read another run, or delete."""

    def __init__(self, store: EvidenceStore, run_id: str) -> None:
        self._store = store
        self.run_id = run_id

    def write(self, relative_path: str, content: str) -> EvidenceRef:
        if ".." in Path(relative_path).parts or Path(relative_path).is_absolute():
            raise AccessDenied(f"evidence path escapes its run: {relative_path!r}")
        target = self._store.run_dir(self.run_id) / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        digest = hash_file_manifest(
            self._store.run_dir(self.run_id), [relative_path]
        )
        return EvidenceRef(
            run_id=self.run_id, relative_path=relative_path, sha256=digest.sha256
        )

    def manifest_digest(self) -> Digest:
        """Hash of everything this run wrote, for the deletion receipt."""
        return _manifest_digest(self._store.run_dir(self.run_id))


class HarnessHandle:
    """Read; generates the FR69-FR71 artifacts. It never writes or deletes."""

    def __init__(self, store: EvidenceStore) -> None:
        self._store = store

    def read(self, run_id: str, relative_path: str) -> str:
        target = self._store.run_dir(run_id) / relative_path
        if not target.exists():
            raise AccessDenied(f"no evidence at {run_id}/{relative_path}")
        return target.read_text(encoding="utf-8")

    def paths(self, run_id: str) -> list[str]:
        run_dir = self._store.run_dir(run_id)
        if not run_dir.exists():
            return []
        return sorted(
            p.relative_to(run_dir).as_posix() for p in run_dir.rglob("*") if p.is_file()
        )

    def manifest_digest(self, run_id: str) -> Digest:
        return _manifest_digest(self._store.run_dir(run_id))


class RetentionHandle:
    """Delete, plus manifest status — nothing else. It cannot read content."""

    def __init__(self, store: EvidenceStore) -> None:
        self._store = store

    def exists(self, run_id: str) -> bool:
        return self._store.run_dir(run_id).is_dir()

    def manifest_digest(self, run_id: str) -> Digest:
        return _manifest_digest(self._store.run_dir(run_id))

    def delete_run(self, run_id: str) -> bool:
        """Delete the whole per-run directory, temporaries included."""
        run_dir = self._store.run_dir(run_id)
        if not run_dir.is_dir():
            return False
        shutil.rmtree(run_dir)
        return True


class BlindReviewHandle:
    """Read evidence and contract. No verdict, decision record or manifest.

    The denial is structural: this class has no method that would return any of
    them, so the renderer cannot be made to leak one by a later edit that adds a
    parameter somewhere else.
    """

    #: Anything under the run directory matching these is not the reviewer's to
    #: see; they are harness artifacts that live alongside the deliverable.
    WITHHELD: Final[frozenset[str]] = frozenset(
        {"verdict.json", "decision-log.json", "manifest.json", "gate.json"}
    )

    def __init__(self, store: EvidenceStore, run_id: str) -> None:
        self._store = store
        self.run_id = run_id

    def deliverable(self) -> str:
        target = self._store.run_dir(self.run_id) / "deliverable.json"
        if not target.exists():
            raise AccessDenied(f"run {self.run_id} has no deliverable")
        return target.read_text(encoding="utf-8")

    def readable(self) -> list[str]:
        run_dir = self._store.run_dir(self.run_id)
        if not run_dir.exists():
            return []
        return sorted(
            p.relative_to(run_dir).as_posix()
            for p in run_dir.rglob("*")
            if p.is_file() and p.name not in self.WITHHELD
        )


def _manifest_digest(run_dir: Path) -> Digest:
    if not run_dir.is_dir():
        raise AccessDenied(f"no evidence directory: {run_dir.name}")
    relative = sorted(
        p.relative_to(run_dir).as_posix() for p in run_dir.rglob("*") if p.is_file()
    )
    return hash_file_manifest(run_dir, relative)


def build_evidence_manifest(run_dir: Path) -> list[Any]:
    relative = sorted(
        p.relative_to(run_dir).as_posix() for p in run_dir.rglob("*") if p.is_file()
    )
    return build_file_manifest(run_dir, relative)
