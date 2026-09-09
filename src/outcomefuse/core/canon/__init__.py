"""The one canonicaliser (AD-6) — exactly two admissible hashing routes.

Callers import from here and never reach into submodules.
"""

from __future__ import annotations

from .canonical_json import (
    MAX_DECIMAL_EXPONENT,
    MAX_DEPTH,
    MAX_INT_DIGITS,
    CanonicalisationError,
    canonical_bytes,
)
from .digest import (
    KNOWN_ROUTES,
    NORMALISATION_VERSION,
    ROUTE_FILE_DIGEST,
    ROUTE_STRUCTURE,
    Digest,
    RouteDeclarationError,
    hash_structure,
    require_route,
)
from .file_manifest import (
    DEFAULT_TEXT_SUFFIXES,
    ManifestEntry,
    ManifestError,
    Mode,
    build_file_manifest,
    hash_file_manifest,
)

__all__ = [
    "DEFAULT_TEXT_SUFFIXES",
    "KNOWN_ROUTES",
    "MAX_DECIMAL_EXPONENT",
    "MAX_DEPTH",
    "MAX_INT_DIGITS",
    "NORMALISATION_VERSION",
    "ROUTE_FILE_DIGEST",
    "ROUTE_STRUCTURE",
    "CanonicalisationError",
    "Digest",
    "ManifestEntry",
    "ManifestError",
    "Mode",
    "RouteDeclarationError",
    "build_file_manifest",
    "canonical_bytes",
    "hash_file_manifest",
    "hash_structure",
    "require_route",
]
