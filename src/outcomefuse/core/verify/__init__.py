"""The closed verifier registry and its pinned arguments (AD-7).

Callers import from here and never reach into submodules.
"""

from __future__ import annotations

from .citable_index import MAX_ENTRIES, CitableEntry, CitableIndex
from .path import MISSING, PathError, has_wildcard, root_field, select, select_one
from .registry import (
    REGISTRY,
    REGISTRY_VERSION,
    CitationResolvesArgs,
    ExactMatchArgs,
    FieldPresentArgs,
    NumericRangeArgs,
    Outcome,
    RegexMatchArgs,
    RegisteredVerifier,
    SetMembershipArgs,
    TypeIsArgs,
    VerificationMode,
    VerifierError,
    build_args,
    mode_for,
    registry_digest,
    verify,
)

__all__ = [
    "MAX_ENTRIES",
    "MISSING",
    "REGISTRY",
    "REGISTRY_VERSION",
    "CitableEntry",
    "CitableIndex",
    "CitationResolvesArgs",
    "ExactMatchArgs",
    "FieldPresentArgs",
    "NumericRangeArgs",
    "Outcome",
    "PathError",
    "RegexMatchArgs",
    "RegisteredVerifier",
    "SetMembershipArgs",
    "TypeIsArgs",
    "VerificationMode",
    "VerifierError",
    "build_args",
    "has_wildcard",
    "mode_for",
    "registry_digest",
    "root_field",
    "select",
    "select_one",
    "verify",
]
