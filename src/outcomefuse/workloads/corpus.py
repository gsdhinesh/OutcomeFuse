"""Corpus access for the workload tools.

**This layer must never be able to reach an answer.** `freeze/` holds the
derivation scripts that know what every case's answer is, and they load these
same corpora. The loading is deliberately duplicated here rather than imported
from there: a runtime that can import the key deriver is one refactor away from
a tool that consults it, and the whole benchmark rests on that being
impossible rather than merely unlikely.

Read-only is imposed by the engine, not by inspecting the SQL the agent wrote.
`PRAGMA query_only` makes a write fail inside SQLite, which is a guarantee; a
regex over a query string is a guess that a determined caller wins.
"""

from __future__ import annotations

import atexit
import sqlite3
from pathlib import Path
from typing import Any, Final

import yaml

ROOT: Final[Path] = Path(__file__).resolve().parents[3]

#: One connection per corpus. Rebuilding an identical in-memory database for
#: every tool call would dominate the latency the overhead study measures.
_CORPORA: dict[str, sqlite3.Connection] = {}


class CorpusError(RuntimeError):
    """The corpus could not be loaded or a tool asked it for the impossible."""


def corpus_path(corpus_ref: str) -> Path:
    path = ROOT / corpus_ref
    if not path.is_dir():
        raise CorpusError(f"no corpus at {corpus_ref}")
    return path


def sql_corpus(corpus_ref: str) -> sqlite3.Connection:
    """A read-only in-memory database built from the corpus's schema and seed."""
    cached = _CORPORA.get(corpus_ref)
    if cached is not None:
        return cached

    corpus = corpus_path(corpus_ref)
    db = sqlite3.connect(":memory:", check_same_thread=False)
    try:
        db.executescript((corpus / "schema.sql").read_text(encoding="utf-8"))
        db.executescript((corpus / "seed.sql").read_text(encoding="utf-8"))
        db.execute("PRAGMA query_only = ON")
    except Exception:
        db.close()
        raise
    _CORPORA[corpus_ref] = db
    return db


def writable_copy(corpus_ref: str) -> sqlite3.Connection:
    """A throwaway writable database, for the side-effecting tool alone.

    Never the shared read-only corpus: a write tool that could reach it would
    make every later deterministic read a different answer, and the Tool
    Governor caches those reads on the contract's word that they are stable.
    """
    corpus = corpus_path(corpus_ref)
    db = sqlite3.connect(":memory:", check_same_thread=False)
    try:
        db.executescript((corpus / "schema.sql").read_text(encoding="utf-8"))
        db.executescript((corpus / "seed.sql").read_text(encoding="utf-8"))
    except Exception:
        db.close()
        raise
    return db


def documents(corpus_ref: str) -> list[dict[str, Any]]:
    path = corpus_path(corpus_ref) / "documents.yaml"
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    return list(loaded["documents"])


def repo_files(corpus_ref: str) -> dict[str, str]:
    """Every source file in the corpus repo, keyed by POSIX-relative path."""
    root = corpus_path(corpus_ref) / "repo"
    if not root.is_dir():
        raise CorpusError(f"no repo under {corpus_ref}")
    return {
        p.relative_to(root).as_posix(): p.read_text(encoding="utf-8")
        for p in sorted(root.rglob("*.py"))
        # A stray __pycache__ would make the same corpus read differently on a
        # machine that had imported it.
        if "__pycache__" not in p.parts
    }


def close_corpora() -> None:
    for db in _CORPORA.values():
        db.close()
    _CORPORA.clear()


atexit.register(close_corpora)
