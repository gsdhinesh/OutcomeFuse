"""One workspace database, append-only, sealed per run (AD-16).

Concurrency is **imposed, not assumed**. WAL gives one writer at a time and
reports contention as `SQLITE_BUSY`; it does not queue for you. So the store
asserts its preconditions at open and refuses rather than degrading:

- `sqlite3` library **≥ 3.51.3** — the WAL-reset corruption bug present from
  3.7.0 through 3.51.2 triggers on exactly this workload.
- **One writer per database file**, held by an OS advisory lock taken at open
  and released by the OS on process exit. A second writer is **refused, not
  retried**: an in-process lock is void the moment a harness forks a subprocess
  per case, which is a legal implementation.
- `BEGIN IMMEDIATE` rather than the deferred default, so a transaction cannot
  upgrade mid-flight and lose its busy retry.
- An explicit busy timeout, and `synchronous=FULL` — WAL with `NORMAL` syncs
  only at checkpoint and forfeits durability on power loss.
- **Local storage only**: WAL's shared-memory wal-index does not work over a
  network filesystem.

Append-only is writer discipline, so integrity is carried structurally: each
row holds the hash of its predecessor **within its own run**, and the terminal
row's hash is the **run seal**. What that proves is bounded and is not
oversold — see `verify_run`.
"""

from __future__ import annotations

import os
import sqlite3
import sys
from pathlib import Path
from typing import Final

from .events import TERMINAL_KINDS
from .models import Event, RunManifest

MIN_SQLITE: Final[tuple[int, int, int]] = (3, 51, 3)
BUSY_TIMEOUT_MS: Final[int] = 5000

SCHEMA: Final[str] = """
CREATE TABLE IF NOT EXISTS events (
    run_id            TEXT    NOT NULL,
    seq               INTEGER NOT NULL,
    kind              TEXT    NOT NULL,
    recorded_at       TEXT    NOT NULL,
    lane              TEXT    NOT NULL,
    body              TEXT    NOT NULL,
    prev_sha256       TEXT,
    sha256            TEXT    NOT NULL,
    terminal_reason   TEXT,
    PRIMARY KEY (run_id, seq)
) STRICT;

CREATE UNIQUE INDEX IF NOT EXISTS events_sha256 ON events(sha256);

-- terminal_reason is recorded at most once per run per lane (FR103). The
-- counterfactual seals at its own first terminating decision, and that seal is
-- not the observed run's.
CREATE UNIQUE INDEX IF NOT EXISTS events_one_terminal
    ON events(run_id, lane) WHERE terminal_reason IS NOT NULL;

-- The chain is the real defence; these catch our own bugs, not an adversary
-- who can equally drop them.
CREATE TRIGGER IF NOT EXISTS events_no_update
BEFORE UPDATE ON events
BEGIN
    SELECT RAISE(ABORT, 'the decision log is append-only');
END;

CREATE TRIGGER IF NOT EXISTS events_no_delete
BEFORE DELETE ON events
BEGIN
    SELECT RAISE(ABORT, 'the decision log is append-only');
END;
"""


class StoreError(RuntimeError):
    """The store refused. Distinct from a SQLite error escaping."""


class ChainBroken(StoreError):
    """A run's hash chain does not verify."""


def _assert_library_version() -> None:
    if sqlite3.sqlite_version_info < MIN_SQLITE:
        wanted = ".".join(str(p) for p in MIN_SQLITE)
        raise StoreError(
            f"sqlite3 library {sqlite3.sqlite_version} is below {wanted}; the WAL-reset "
            "corruption bug from 3.7.0 through 3.51.2 triggers on concurrent writers "
            "against one file, which is exactly this workload"
        )


def _assert_local_storage(path: Path) -> None:
    """Refuse a network filesystem: WAL's wal-index is shared memory."""
    text = str(path)
    if text.startswith("\\\\") or text.startswith("//"):
        raise StoreError(f"the store may not live on a UNC path: {path}")
    if sys.platform == "win32":
        import ctypes

        drive = os.path.splitdrive(path)[0]
        if drive:
            DRIVE_REMOTE = 4
            if ctypes.windll.kernel32.GetDriveTypeW(f"{drive}\\") == DRIVE_REMOTE:
                raise StoreError(f"the store may not live on a network drive: {drive}")
    elif sys.platform.startswith("linux"):
        remote = {"nfs", "nfs4", "cifs", "smbfs", "fuse.sshfs", "9p"}
        try:
            mounts = Path("/proc/mounts").read_text(encoding="utf-8").splitlines()
        except OSError:
            return  # Unreadable /proc is not evidence of a network mount.
        best, kind = "", ""
        for line in mounts:
            parts = line.split()
            if len(parts) >= 3 and text.startswith(parts[1]) and len(parts[1]) > len(best):
                best, kind = parts[1], parts[2]
        if kind in remote:
            raise StoreError(f"the store may not live on a {kind} mount: {path}")


def _assert_current_schema(db: sqlite3.Connection) -> None:
    """Refuse a database file written by an older schema.

    A reader opens without creating anything, and `CREATE TABLE IF NOT EXISTS`
    does not add a column to a table that already exists — so without this the
    first append against a pre-`lane` file fails deep inside an INSERT.
    """
    columns = {row[1] for row in db.execute("PRAGMA table_info(events)")}
    if columns and "lane" not in columns:
        raise StoreError(
            "this database has no `lane` column, so it was written by an earlier "
            "schema; it is refused rather than migrated in place"
        )


class _WriterLock:
    """An OS advisory lock, released by the OS if the process dies.

    A lock held in process memory would not survive the harness forking a
    subprocess per case, which AD-16 calls out as a legal implementation.
    """

    def __init__(self, path: Path) -> None:
        self._path = path.with_suffix(path.suffix + ".writer-lock")
        self._fd: int | None = None

    def acquire(self) -> None:
        fd = os.open(self._path, os.O_RDWR | os.O_CREAT, 0o600)
        try:
            if sys.platform == "win32":
                import msvcrt

                msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            os.close(fd)
            raise StoreError(
                f"another writer already holds {self._path.name}; a second writer is "
                "refused rather than retried"
            ) from exc
        self._fd = fd

    def release(self) -> None:
        if self._fd is None:
            return
        try:
            if sys.platform == "win32":
                import msvcrt

                msvcrt.locking(self._fd, msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(self._fd, fcntl.LOCK_UN)
        finally:
            os.close(self._fd)
            self._fd = None


class RecordStore:
    """Append-only writer over one workspace database holding many runs."""

    def __init__(self, path: Path | str, *, writer: bool = True) -> None:
        self.path = Path(path)
        self._writer = writer
        self._lock = _WriterLock(self.path) if writer else None
        self._db: sqlite3.Connection | None = None

    def open(self) -> RecordStore:
        _assert_library_version()
        _assert_local_storage(self.path)
        if self._lock is not None:
            self._lock.acquire()
        try:
            # isolation_level=None puts transaction control here, so every write
            # can start with BEGIN IMMEDIATE instead of upgrading mid-flight.
            db = sqlite3.connect(self.path, isolation_level=None, timeout=BUSY_TIMEOUT_MS / 1000)
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("PRAGMA synchronous=FULL")
            db.execute(f"PRAGMA busy_timeout={BUSY_TIMEOUT_MS}")
            db.execute("PRAGMA foreign_keys=ON")
            if self._writer:
                db.executescript(SCHEMA)
            _assert_current_schema(db)
        except Exception:
            if self._lock is not None:
                self._lock.release()
            raise
        self._db = db
        return self

    def close(self) -> None:
        if self._db is not None:
            self._db.close()
            self._db = None
        if self._lock is not None:
            self._lock.release()

    def __enter__(self) -> RecordStore:
        # `open_store` already opened it; re-opening would take the writer lock
        # a second time and the store would correctly refuse itself.
        return self if self._db is not None else self.open()

    def __exit__(self, *_: object) -> None:
        self.close()

    @property
    def db(self) -> sqlite3.Connection:
        if self._db is None:
            raise StoreError("the store is not open")
        return self._db

    def library_version(self) -> str:
        return sqlite3.sqlite_version

    # ---------------------------------------------------------------- writing

    def open_run(self, manifest: RunManifest, *, recorded_at: str) -> str:
        """Append the manifest as the run's genesis row. Returns its hash."""
        if self.head(manifest.run_id) is not None:
            raise StoreError(f"run {manifest.run_id!r} already exists")
        event = Event(
            run_id=manifest.run_id,
            seq=0,
            kind="run-manifest",
            recorded_at=recorded_at,
            payload={"manifest": manifest.model_dump(mode="json", exclude_none=True)},
        )
        return self.append(event)

    def append(self, event: Event) -> str:
        """Append one row, chaining it to its run's current head."""
        previous = self.head(event.run_id)
        if previous is None and event.seq != 0:
            raise StoreError(f"run {event.run_id!r} has no manifest; append seq 0 first")
        if previous is not None:
            last_seq, last_hash, last_kind = previous
            if event.seq != last_seq + 1:
                raise StoreError(
                    f"run {event.run_id!r} expected seq {last_seq + 1}, got {event.seq}"
                )
            if last_kind in TERMINAL_KINDS:
                raise StoreError(
                    f"run {event.run_id!r} is sealed by {last_kind!r}; nothing may follow it"
                )
            prev_hash: str | None = last_hash
        else:
            prev_hash = None

        digest = event.chained_hash(prev_hash)
        body = event.model_dump_json(exclude_none=True)
        db = self.db
        db.execute("BEGIN IMMEDIATE")
        try:
            db.execute(
                "INSERT INTO events "
                "(run_id, seq, kind, recorded_at, lane, body, prev_sha256, sha256, "
                "terminal_reason) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    event.run_id,
                    event.seq,
                    event.kind,
                    event.recorded_at,
                    event.lane,
                    body,
                    prev_hash,
                    digest,
                    event.terminal_reason,
                ),
            )
        except Exception:
            db.execute("ROLLBACK")
            raise
        db.execute("COMMIT")
        return digest

    # ---------------------------------------------------------------- reading

    def head(self, run_id: str) -> tuple[int, str, str] | None:
        row = self.db.execute(
            "SELECT seq, sha256, kind FROM events WHERE run_id = ? ORDER BY seq DESC LIMIT 1",
            (run_id,),
        ).fetchone()
        return None if row is None else (row[0], row[1], row[2])

    def run_ids(self) -> list[str]:
        return [r[0] for r in self.db.execute("SELECT DISTINCT run_id FROM events ORDER BY run_id")]

    def events(self, run_id: str) -> list[Event]:
        return [
            Event.model_validate_json(row[0])
            for row in self.db.execute(
                "SELECT body FROM events WHERE run_id = ? ORDER BY seq", (run_id,)
            )
        ]

    def seal(self, run_id: str) -> str | None:
        """The terminal row's hash, or None while the run is unsealed."""
        head = self.head(run_id)
        if head is None or head[2] not in TERMINAL_KINDS:
            return None
        return head[1]

    def verify_run(self, run_id: str) -> str:
        """Recompute the chain and return the head hash, or raise `ChainBroken`.

        This detects a selective edit. It does not establish authorship or time,
        and a chain whose seal lives only in this file proves nothing against
        someone who rewrites the file and recomputes — which is why every proof
        card carries the seals of the runs it compares, outside the database.
        """
        rows = self.db.execute(
            "SELECT seq, body, prev_sha256, sha256 FROM events WHERE run_id = ? ORDER BY seq",
            (run_id,),
        ).fetchall()
        if not rows:
            raise ChainBroken(f"run {run_id!r} has no events")

        previous: str | None = None
        for index, (seq, body, stored_prev, stored_hash) in enumerate(rows):
            if seq != index:
                raise ChainBroken(f"run {run_id!r} seq {seq} is out of order at position {index}")
            if stored_prev != previous:
                raise ChainBroken(
                    f"run {run_id!r} seq {seq} claims predecessor {stored_prev!r}, "
                    f"chain says {previous!r}"
                )
            event = Event.model_validate_json(body)
            recomputed = event.chained_hash(previous)
            if recomputed != stored_hash:
                raise ChainBroken(f"run {run_id!r} seq {seq} does not match its recorded hash")
            previous = stored_hash
        return previous  # type: ignore[return-value]


def open_store(path: Path | str, *, writer: bool = True) -> RecordStore:
    return RecordStore(path, writer=writer).open()
