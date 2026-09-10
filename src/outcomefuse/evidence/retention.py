"""Retention under `mvp-synthetic-v1` (AD-19, NFR12, AD-21).

**A campaign is a workspace.** Campaign seal is a harness command executed
**once**, refused while any run is unsealed, and after it the store refuses to
open a writer so no run can join a sealed workspace.

Run closure is an **appended event, never an update** — no column is ever
mutated — so `run_closed_at` is read from the `run-closed` row rather than
written onto an existing one. The sweep appends `run-abandoned` to whatever is
still unsealed, which both seals it and gives it an expiry; without that,
abandoned evidence would never acquire one and would live forever.

Deletion writes a **content-free receipt** to a separate append-only manifest.
A receipt is never written into any run's hash chain, so no act of retention can
alter a seal. This is logical deletion appropriate to synthetic data; it is not
cryptographic erasure and is not described as such.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Final

from pydantic import BaseModel, ConfigDict, Field

from ..core.record import TERMINAL_KINDS, RecordStore
from .store import RETENTION_PROFILE, EvidenceStore

RAW_EVIDENCE_DAYS: Final[int] = 60
REDACTED_RECORD_DAYS: Final[int] = 180


class RetentionError(RuntimeError):
    """A retention or seal operation was refused."""


class DeletionReceipt(BaseModel):
    """Content-free by construction: identifiers, hashes, times, result."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    run_id: str = Field(min_length=1)
    evidence_manifest_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    retention_profile: str
    scheduled_expiry_at: str
    deleted_at: str
    result: str


class CampaignSeal(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    sealed_at: str
    run_count: int = Field(ge=0)
    latest_run_closed_at: str | None = None
    redacted_expiry_at: str


def _parse(timestamp: str) -> datetime:
    return datetime.fromisoformat(timestamp.replace("Z", "+00:00"))


def _format(moment: datetime) -> str:
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def run_closed_at(store: RecordStore, run_id: str) -> str | None:
    """Read from the terminal row. Nothing is mutated to obtain it."""
    for event in reversed(store.events(run_id)):
        if event.kind in TERMINAL_KINDS:
            return event.recorded_at
    return None


def unsealed_runs(store: RecordStore) -> list[str]:
    return [rid for rid in store.run_ids() if store.seal(rid) is None]


def sweep(store: RecordStore, *, at: str) -> list[str]:
    """Append `run-abandoned` to every run still unsealed.

    Both seals the run and gives it an expiry, which is the point: an abandoned
    run with no terminal row would never acquire one.
    """
    from ..core.record import Event

    abandoned = []
    for run_id in unsealed_runs(store):
        head = store.head(run_id)
        if head is None:
            continue
        store.append(
            Event(
                run_id=run_id,
                seq=head[0] + 1,
                kind="run-abandoned",
                recorded_at=at,
                terminal_reason="fail-closed",
            )
        )
        abandoned.append(run_id)
    return abandoned


class Campaign:
    """The workspace, its seal, and its retention manifest."""

    def __init__(self, root: Path | str, record: RecordStore, evidence: EvidenceStore) -> None:
        self.root = Path(root)
        self.record = record
        self.evidence = evidence
        self.manifest_path = self.root / "retention-manifest.jsonl"
        self.seal_path = self.root / "campaign-seal.json"

    # --------------------------------------------------------------- sealing

    @property
    def is_sealed(self) -> bool:
        return self.seal_path.exists()

    def seal(self, *, at: str, sweep_abandoned: bool = False) -> CampaignSeal:
        if self.is_sealed:
            raise RetentionError("the campaign is already sealed; seal is executed once")

        if sweep_abandoned:
            sweep(self.record, at=at)

        outstanding = unsealed_runs(self.record)
        if outstanding:
            raise RetentionError(
                f"campaign seal refused while runs are unsealed: {outstanding}. "
                "Run the sweep, which appends run-abandoned and gives them an expiry."
            )

        closures = [
            closed
            for rid in self.record.run_ids()
            if (closed := run_closed_at(self.record, rid)) is not None
        ]
        latest = max(closures) if closures else None
        if latest is not None and _parse(latest) > _parse(at):
            raise RetentionError(
                f"max(run_closed_at) {latest} is after campaign_sealed_at {at}"
            )

        sealed = CampaignSeal(
            sealed_at=at,
            run_count=len(self.record.run_ids()),
            latest_run_closed_at=latest,
            redacted_expiry_at=_format(_parse(at) + timedelta(days=REDACTED_RECORD_DAYS)),
        )
        self.root.mkdir(parents=True, exist_ok=True)
        self.seal_path.write_text(sealed.model_dump_json(indent=2), encoding="utf-8")
        # After seal the store refuses to open a writer.
        self.evidence.seal()
        return sealed

    # ------------------------------------------------------------- retention

    def scheduled_expiry(self, run_id: str) -> str:
        closed = run_closed_at(self.record, run_id)
        if closed is None:
            raise RetentionError(
                f"run {run_id!r} is unsealed, so it has no run_closed_at and no expiry"
            )
        return _format(_parse(closed) + timedelta(days=RAW_EVIDENCE_DAYS))

    def expire_run(self, run_id: str, *, now: str) -> DeletionReceipt:
        """Delete the whole per-run evidence directory and receipt it."""
        expiry = self.scheduled_expiry(run_id)
        if _parse(now) < _parse(expiry):
            raise RetentionError(
                f"run {run_id!r} expires at {expiry}; there is no per-run extension "
                "and no early deletion"
            )
        retention = self.evidence.for_retention()
        digest = retention.manifest_digest(run_id)
        deleted = retention.delete_run(run_id)
        receipt = DeletionReceipt(
            run_id=run_id,
            evidence_manifest_hash=digest.sha256,
            retention_profile=RETENTION_PROFILE,
            scheduled_expiry_at=expiry,
            deleted_at=now,
            result="deleted" if deleted else "absent",
        )
        self._append_receipt(receipt)
        return receipt

    def _append_receipt(self, receipt: DeletionReceipt) -> None:
        """A separate append-only artifact, never a run's hash chain."""
        self.root.mkdir(parents=True, exist_ok=True)
        with self.manifest_path.open("a", encoding="utf-8") as handle:
            handle.write(receipt.model_dump_json() + "\n")

    def receipts(self) -> list[DeletionReceipt]:
        if not self.manifest_path.exists():
            return []
        return [
            DeletionReceipt(**json.loads(line))
            for line in self.manifest_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
