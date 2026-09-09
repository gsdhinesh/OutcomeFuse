"""Minimal CLI — the second independent process the E0 acceptance bar requires.

Reads a JSON structure or manifest request from stdin under a bounded read size,
prints the resulting :class:`~outcomefuse.core.canon.Digest` as JSON, and exits
non-zero naming the error on rejection.

Trust boundary: stdin is bounded and structurally validated so that malformed or
pathological input is refused rather than hung on, but ``root`` is caller-supplied
and unconfined — any path on the machine can be named. This is a local developer
and freeze tool run by its own operator, not a sandbox.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Sequence
from typing import Any, Final, cast

from .canonical_json import CanonicalisationError
from .digest import Digest, RouteDeclarationError, hash_structure
from .file_manifest import (
    DEFAULT_TEXT_SUFFIXES,
    ManifestEntryInput,
    ManifestError,
    Mode,
    hash_file_manifest,
)

MAX_STDIN_BYTES: Final = 1 << 20

_MODES: Final = ("structure", "file-digest")
_USAGE: Final = f"usage: python -m outcomefuse.core.canon {{{'|'.join(_MODES)}}}"


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 1 or args[0] not in _MODES:
        print(_USAGE, file=sys.stderr)
        return 2

    raw = sys.stdin.buffer.read(MAX_STDIN_BYTES + 1)
    if len(raw) > MAX_STDIN_BYTES:
        return _fail(ValueError(f"stdin exceeds the {MAX_STDIN_BYTES} byte bound"))

    try:
        payload = json.loads(raw.decode("utf-8"))
        digest = (
            hash_structure(payload) if args[0] == "structure" else _hash_request(payload)
        )
    except (
        CanonicalisationError,
        ManifestError,
        RouteDeclarationError,
        UnicodeDecodeError,
        ValueError,
        OSError,
        RecursionError,
    ) as exc:
        return _fail(exc)

    print(digest.model_dump_json())
    return 0


def _hash_request(payload: Any) -> Digest:
    if not isinstance(payload, dict):
        raise ValueError("file-digest request must be a JSON object")

    root = payload.get("root")
    if not isinstance(root, str):
        raise ValueError("file-digest request field 'root' must be a string")

    paths = payload.get("paths")
    if not isinstance(paths, list):
        raise ValueError("file-digest request field 'paths' must be a list")
    entries = [_as_entry(item) for item in paths]

    suffixes: Any = payload.get("text_suffixes", None)
    if suffixes is None:
        suffixes = DEFAULT_TEXT_SUFFIXES
    elif not isinstance(suffixes, list) or not all(isinstance(item, str) for item in suffixes):
        raise ValueError("file-digest request field 'text_suffixes' must be a list of strings")

    unknown = set(payload) - {"root", "paths", "text_suffixes"}
    if unknown:
        raise ValueError(f"unknown file-digest request fields: {sorted(unknown)}")

    return hash_file_manifest(root, entries, suffixes)


def _as_entry(item: Any) -> ManifestEntryInput:
    """A bare path, or a ``[path, mode]`` pair so mode can be declared across the boundary."""
    if isinstance(item, str):
        return item
    if isinstance(item, list) and len(item) == 2 and all(isinstance(part, str) for part in item):
        return (item[0], cast(Mode, item[1]))
    raise ValueError(
        "file-digest request field 'paths' members must be a string or a [path, mode] pair"
    )


def _fail(exc: BaseException) -> int:
    print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
