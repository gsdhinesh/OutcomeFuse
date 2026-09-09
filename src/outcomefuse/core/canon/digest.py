"""Digest records, the frozen route registry, and the single sealing step.

Nothing outside this module computes a SHA-256 over a canonical payload: both
admissible routes go through :func:`sealed`, which binds the route id and the
normalisation version into the hashed bytes. The record field alone only
*describes* a digest; the envelope is what *constrains* it.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from typing import Any, Final, Self

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from .canonical_json import canonical_bytes

#: The pinned normalisation. Digests are not comparable across versions.
NORMALISATION_VERSION: Final = "v1"

#: Typed model -> canonical JSON -> SHA-256.
ROUTE_STRUCTURE: Final = "structure/v1"

#: Sorted path + file-byte SHA-256 manifest, itself sealed through the structure envelope.
ROUTE_FILE_DIGEST: Final = "file-digest/v1"

#: Exactly two routes are admissible. No component may hash by any other means.
KNOWN_ROUTES: Final[frozenset[str]] = frozenset({ROUTE_STRUCTURE, ROUTE_FILE_DIGEST})

_SHA256_PATTERN: Final = r"^[0-9a-f]{64}$"


class RouteDeclarationError(Exception):
    """A digest was presented without a usable route declaration.

    Deliberately not a :class:`ValueError`, so pydantic does not absorb it into a
    ``ValidationError`` when raised from a validator: callers face one error type
    whether the record was built or deserialised.
    """


class Digest(BaseModel):
    """An immutable digest carrying the route and normalisation that produced it."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    route: str
    normalisation: str = Field(min_length=1)
    sha256: str = Field(pattern=_SHA256_PATTERN)

    @model_validator(mode="before")
    @classmethod
    def _declare_route(cls, data: Any) -> Any:
        if isinstance(data, Mapping):
            _check_route(data.get("route"), present="route" in data)
        return data

    @model_validator(mode="after")
    def _check_comparability(self) -> Self:
        # Route and normalisation jointly decide whether two digests are comparable, so
        # both are enforced here as well: direct construction never reaches the
        # before-validator's mapping branch.
        _check_route(self.route)
        if self.normalisation != NORMALISATION_VERSION:
            raise RouteDeclarationError(
                f"digest declares normalisation {self.normalisation!r}, "
                f"expected {NORMALISATION_VERSION!r}"
            )
        return self

    def model_copy(self, *, update: Mapping[str, Any] | None = None, deep: bool = False) -> Self:
        """Re-validate on copy: pydantic's ``model_copy`` applies updates unvalidated."""
        copied = super().model_copy(update=dict(update) if update else None, deep=deep)
        return type(self).model_validate(copied.__dict__)


def _check_route(route: Any, *, present: bool = True) -> str:
    if not present or route is None:
        raise RouteDeclarationError("digest route id is absent; a route is never defaulted")
    if not isinstance(route, str):
        raise RouteDeclarationError(
            f"digest route id must be a string, got {type(route).__name__}"
        )
    if not route.strip():
        raise RouteDeclarationError("digest route id is empty; a route is never defaulted")
    if route not in KNOWN_ROUTES:
        raise RouteDeclarationError(f"unknown digest route id: {route!r}")
    return route


def sealed(route: str, payload: Any) -> Digest:
    """The only place a SHA-256 is computed over a canonical payload."""
    envelope = {"normalisation": NORMALISATION_VERSION, "payload": payload, "route": route}
    return Digest(
        route=route,
        normalisation=NORMALISATION_VERSION,
        sha256=hashlib.sha256(canonical_bytes(envelope)).hexdigest(),
    )


def hash_structure(value: Any) -> Digest:
    """Hash a typed model or plain structure through the structure route."""
    return sealed(ROUTE_STRUCTURE, value)


def require_route(digest: Digest | Mapping[str, Any], expected: str) -> None:
    """Verify a digest declares ``expected`` and the pinned normalisation version."""
    _check_route(expected)
    if not isinstance(digest, Digest):
        if not isinstance(digest, Mapping):
            raise RouteDeclarationError(
                f"digest record must be a Digest or a mapping, got {type(digest).__name__}"
            )
        try:
            digest = Digest.model_validate(dict(digest))
        except ValidationError as exc:
            raise RouteDeclarationError(f"digest record is not well-formed: {exc}") from exc
    if digest.route != expected:
        raise RouteDeclarationError(
            f"digest declares route {digest.route!r}, expected {expected!r}"
        )
    if digest.normalisation != NORMALISATION_VERSION:
        raise RouteDeclarationError(
            f"digest declares normalisation {digest.normalisation!r}, "
            f"expected {NORMALISATION_VERSION!r}"
        )
