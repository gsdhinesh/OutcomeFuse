"""The file-digest route — for artifacts that are source rather than structure.

A Windows freeze and a Linux freeze over the same tree must agree, so paths are
POSIX-separated, NFC-normalised and byte-sorted, and text artifacts are digested
with LF line endings.
"""

from __future__ import annotations

import hashlib
import os
import unicodedata
from collections.abc import Iterable
from pathlib import Path, PurePosixPath
from typing import Final, Literal, get_args

from pydantic import BaseModel, ConfigDict, Field

from .digest import ROUTE_FILE_DIGEST, Digest, sealed

Mode = Literal["text", "binary"]
PathLike = str | os.PathLike[str]
ManifestEntryInput = PathLike | tuple[PathLike, Mode]

MODES: Final[frozenset[str]] = frozenset(get_args(Mode))

#: Suffixes digested with LF line endings when no explicit mode is declared.
#: Deliberately excludes ``.csv``: under RFC 4180 a CRLF inside a quoted field is data,
#: so folding it would make two genuinely different files hash identically. A caller who
#: really wants CSV in text mode must declare that mode per entry.
DEFAULT_TEXT_SUFFIXES: Final[frozenset[str]] = frozenset(
    {
        ".cfg",
        ".css",
        ".html",
        ".ini",
        ".js",
        ".json",
        ".jsonl",
        ".md",
        ".ps1",
        ".py",
        ".rst",
        ".sh",
        ".sql",
        ".toml",
        ".ts",
        ".txt",
        ".yaml",
        ".yml",
    }
)


class ManifestError(Exception):
    """A manifest entry is not admissible under the file-digest route."""


class ManifestEntry(BaseModel):
    """One recorded file: its POSIX/NFC path, its digest, and the mode it was read under."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    path: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    #: Recorded rather than re-derived by a reader, so suffix rules cannot drift underneath it.
    mode: Mode


def build_file_manifest(
    root: PathLike,
    entries: Iterable[ManifestEntryInput],
    text_suffixes: Iterable[str] = DEFAULT_TEXT_SUFFIXES,
) -> list[ManifestEntry]:
    """Build the sorted manifest for ``entries``, resolved beneath ``root``."""
    suffixes = _validate_suffixes(text_suffixes)

    root_path = Path(root)
    try:
        resolved_root = root_path.resolve(strict=True)
    except OSError as exc:
        raise ManifestError(f"manifest root does not resolve: {root_path}") from exc
    if not resolved_root.is_dir():
        raise ManifestError(f"manifest root is not a directory: {root_path}")

    built: list[ManifestEntry] = []
    seen: set[str] = set()
    for entry in entries:
        raw_path, declared = _split_entry(entry)
        segments = _safe_segments(raw_path)

        # Lookup uses the caller's spelling: the filesystem stores the name it was given,
        # and NFC-normalising before the syscall breaks on NTFS.
        target = resolved_root.joinpath(*segments)
        resolved = _resolve(target)
        # Resolved, not textual: a symlink inside the root defeats the `..` guard entirely.
        if not resolved.is_relative_to(resolved_root):
            raise ManifestError(f"manifest path escapes the root: {raw_path}")
        if not resolved.exists():
            raise FileNotFoundError(f"manifest path is missing: {raw_path}")
        if not resolved.is_file():
            raise ManifestError(f"manifest path is not a regular file: {raw_path}")

        recorded = unicodedata.normalize("NFC", "/".join(segments))
        if recorded in seen:
            raise ManifestError(f"duplicate manifest path: {recorded}")
        seen.add(recorded)

        mode: Mode = declared or _infer_mode(recorded, suffixes)
        data = resolved.read_bytes()
        if mode == "text":
            data = data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
        built.append(
            ManifestEntry(path=recorded, sha256=hashlib.sha256(data).hexdigest(), mode=mode)
        )

    built.sort(key=lambda item: item.path.encode("utf-8"))
    return built


def hash_file_manifest(
    root: PathLike,
    entries: Iterable[ManifestEntryInput],
    text_suffixes: Iterable[str] = DEFAULT_TEXT_SUFFIXES,
) -> Digest:
    """Build a manifest over ``entries`` and seal it through the shared envelope."""
    manifest = build_file_manifest(root, entries, text_suffixes)
    return sealed(ROUTE_FILE_DIGEST, list(manifest))


def _resolve(target: Path) -> Path:
    """Named seam so the post-resolve containment check is testable without link privileges."""
    return target.resolve()


def _validate_suffixes(text_suffixes: Iterable[str]) -> frozenset[str]:
    if isinstance(text_suffixes, str | bytes):
        raise ManifestError("text_suffixes must be a collection of strings, not a string")
    collected: set[str] = set()
    for suffix in text_suffixes:
        if not isinstance(suffix, str):
            raise ManifestError(
                f"text_suffixes members must be strings, got {type(suffix).__name__}"
            )
        # The lookup lowercases, so a ".PY" entry would otherwise match nothing silently.
        if len(suffix) < 2 or not suffix.startswith(".") or suffix != suffix.lower():
            raise ManifestError(
                f"text_suffixes members must be lowercase and dot-prefixed, got {suffix!r}"
            )
        collected.add(suffix)
    return frozenset(collected)


def _split_entry(entry: ManifestEntryInput) -> tuple[str, Mode | None]:
    if isinstance(entry, tuple):
        if len(entry) != 2:
            raise ManifestError(f"manifest entry tuple must be (path, mode), got {entry!r}")
        raw, mode = entry
        if mode not in MODES:
            raise ManifestError(f"manifest mode must be 'text' or 'binary', got {mode!r}")
        return _as_str(raw), mode
    return _as_str(entry), None


def _as_str(raw: object) -> str:
    if isinstance(raw, str):
        return raw
    if isinstance(raw, os.PathLike):
        return os.fspath(raw)
    raise ManifestError(f"manifest path must be a string or PathLike, got {type(raw).__name__}")


def _safe_segments(raw_path: str) -> list[str]:
    if not raw_path.strip():
        raise ManifestError("manifest path is empty")
    if "\x00" in raw_path:
        raise ManifestError(f"manifest path contains a null byte: {raw_path!r}")

    normalised = raw_path.replace("\\", "/")
    if normalised.startswith("/"):
        raise ManifestError(f"manifest path must be relative: {raw_path}")

    segments = normalised.split("/")
    if len(segments[0]) >= 2 and segments[0][1] == ":":
        raise ManifestError(f"manifest path must be relative: {raw_path}")
    for segment in segments:
        if segment in {"", ".", ".."}:
            raise ManifestError(f"manifest path is not a plain relative path: {raw_path}")
    return segments


def _infer_mode(recorded: str, suffixes: frozenset[str]) -> Mode:
    return "text" if PurePosixPath(recorded).suffix.lower() in suffixes else "binary"
