"""A deliberately tiny path language for verifier arguments (AD-7).

The contracts need exactly two shapes: `$.field` and `$.field[*].key`. A general
JSONPath library would accept filter expressions and recursive descent, which
are neither bounded nor declarative in the sense AD-7 requires, and would put an
unaudited dependency inside the verification path. So the grammar is closed
here instead:

    path      := "$" segment*
    segment   := "." name | "[*]"
    name      := [A-Za-z_][A-Za-z0-9_-]*

Anything else is a contract authoring error and is refused at validation time,
not at verification time.
"""

from __future__ import annotations

import re
from typing import Any, Final

#: A wildcard fans out one level; two would let a short path walk a large tree.
MAX_WILDCARDS: Final[int] = 1
MAX_SEGMENTS: Final[int] = 8
MAX_MATCHES: Final[int] = 1024

_SEGMENT = re.compile(r"\.(?P<name>[A-Za-z_][A-Za-z0-9_-]*)|(?P<wildcard>\[\*\])")


class PathError(ValueError):
    """A path is not in the closed grammar. Raised at parse time only."""


class Missing:
    """Distinguishes "the field is absent" from "the field is None".

    `field-present` has to tell those apart; `None` alone cannot.
    """

    _instance: Missing | None = None

    def __new__(cls) -> Missing:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self) -> str:
        return "MISSING"

    def __bool__(self) -> bool:
        return False


MISSING: Final[Missing] = Missing()


def parse(path: str) -> tuple[tuple[str, str], ...]:
    """Parse a path into segments, or raise `PathError`."""
    if not isinstance(path, str):
        raise PathError(f"path must be a string, got {type(path).__name__}")
    if not path.startswith("$"):
        raise PathError(f"path must start with '$': {path!r}")

    segments: list[tuple[str, str]] = []
    position = 1
    wildcards = 0
    while position < len(path):
        match = _SEGMENT.match(path, position)
        if match is None:
            raise PathError(f"unparseable at offset {position} in {path!r}")
        if match.group("wildcard"):
            wildcards += 1
            segments.append(("wildcard", "*"))
        else:
            segments.append(("name", match.group("name")))
        position = match.end()

    if not segments:
        raise PathError("path selects the whole deliverable, which no verifier accepts")
    if len(segments) > MAX_SEGMENTS:
        raise PathError(f"path has {len(segments)} segments, limit is {MAX_SEGMENTS}")
    if wildcards > MAX_WILDCARDS:
        raise PathError(f"path has {wildcards} wildcards, limit is {MAX_WILDCARDS}")
    return tuple(segments)


def root_field(path: str) -> str:
    """The first named segment — the deliverable field a path reads."""
    for kind, name in parse(path):
        if kind == "name":
            return name
    raise PathError(f"path names no field: {path!r}")


def has_wildcard(path: str) -> bool:
    return any(kind == "wildcard" for kind, _ in parse(path))


def select(document: Any, path: str) -> list[Any]:
    """Resolve a parsed path against a document.

    Returns every match. A path that resolves to nothing returns an empty list;
    a non-wildcard path that resolves returns exactly one item. Absent
    intermediate fields yield no match rather than an error, because a
    deliverable missing a field is an ordinary verification failure.
    """
    current: list[Any] = [document]
    for kind, name in parse(path):
        following: list[Any] = []
        for item in current:
            if kind == "wildcard":
                if isinstance(item, list):
                    following.extend(item)
            elif isinstance(item, dict) and name in item:
                following.append(item[name])
            if len(following) > MAX_MATCHES:
                raise PathError(f"path {path!r} matched more than {MAX_MATCHES} nodes")
        current = following
    return current


def select_one(document: Any, path: str) -> Any:
    """Resolve a single-valued path, returning `MISSING` when it resolves to nothing."""
    matches = select(document, path)
    if not matches:
        return MISSING
    if len(matches) > 1:
        raise PathError(f"path {path!r} is single-valued but matched {len(matches)}")
    return matches[0]
