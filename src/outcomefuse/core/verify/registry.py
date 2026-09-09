"""The closed verifier registry (AD-7).

Seven types, no import path or callable ever crossing the contract boundary,
and the verification **mode fixed by the type** rather than asserted per
contract — which is what stops `reference-backed` being claimed for a pass that
never touched a known-correct value.

Every verifier is a pure function of its declared arguments. None performs I/O,
none reads run state, and `citation-resolves` receives the citable index from
its caller. That purity is what makes the freeze buildable: each verifier is
testable against fixtures alone.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .citable_index import CitableIndex
from .path import MISSING, PathError, has_wildcard, select, select_one

VerificationMode = Literal["reference-backed", "constraint-backed"]

#: A regex is the one verifier whose cost depends on its input, so the input is
#: capped and the cap is itself capped.
MAX_PATTERN_BYTES: Final[int] = 1024
MAX_INPUT_BYTES_CEILING: Final[int] = 1 << 16


class VerifierError(ValueError):
    """A verifier could not run. Distinct from a verifier returning `False`."""


class Outcome(BaseModel):
    """The result of one criterion's verification."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    passed: bool
    mode: VerificationMode
    detail: str = ""


# --------------------------------------------------------------------------
# Argument models. Declarative and bounded: AD-7 forbids anything else.
# --------------------------------------------------------------------------


class _Args(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    path: str


class FieldPresentArgs(_Args):
    pass


class TypeIsArgs(_Args):
    type: Literal["string", "number", "integer", "boolean", "array", "object"]


class NumericRangeArgs(_Args):
    of: Literal["value", "distinct-count", "count"] = "value"
    min: float | None = None
    max: float | None = None
    min_from_key: str | None = None
    max_from_key: str | None = None

    @model_validator(mode="after")
    def _bounds_are_coherent(self) -> NumericRangeArgs:
        if self.min is not None and self.min_from_key is not None:
            raise ValueError("min and min_from_key are mutually exclusive")
        if self.max is not None and self.max_from_key is not None:
            raise ValueError("max and max_from_key are mutually exclusive")
        if all(b is None for b in (self.min, self.max, self.min_from_key, self.max_from_key)):
            raise ValueError("numeric-range needs at least one bound")
        if self.min is not None and self.max is not None and self.min > self.max:
            raise ValueError(f"min {self.min} exceeds max {self.max}")
        return self


class SetMembershipArgs(_Args):
    allowed: tuple[str, ...] = Field(min_length=1)


class RegexMatchArgs(_Args):
    pattern: str = Field(max_length=MAX_PATTERN_BYTES)
    max_input_bytes: int = Field(gt=0, le=MAX_INPUT_BYTES_CEILING)

    @model_validator(mode="after")
    def _pattern_compiles(self) -> RegexMatchArgs:
        try:
            re.compile(self.pattern)
        except re.error as exc:
            raise ValueError(f"pattern does not compile: {exc}") from exc
        return self


class ExactMatchArgs(_Args):
    key: str


class CitationResolvesArgs(_Args):
    min_citations: int = Field(default=1, ge=0)


# --------------------------------------------------------------------------
# The verifiers. Each is pure: arguments in, Outcome out.
# --------------------------------------------------------------------------


def _numeric(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise VerifierError(f"expected a number, got {type(value).__name__}")
    return float(value)


def field_present(args: FieldPresentArgs, deliverable: Mapping[str, Any], **_: Any) -> Outcome:
    value = select_one(deliverable, args.path)
    if value is MISSING:
        return Outcome(passed=False, mode="constraint-backed", detail=f"{args.path} is absent")
    if value is None or (isinstance(value, str | list | dict) and len(value) == 0):
        return Outcome(passed=False, mode="constraint-backed", detail=f"{args.path} is empty")
    return Outcome(passed=True, mode="constraint-backed")


_TYPES: Final[dict[str, type | tuple[type, ...]]] = {
    "string": str,
    "number": (int, float),
    "integer": int,
    "boolean": bool,
    "array": list,
    "object": dict,
}


def type_is(args: TypeIsArgs, deliverable: Mapping[str, Any], **_: Any) -> Outcome:
    value = select_one(deliverable, args.path)
    if value is MISSING:
        return Outcome(passed=False, mode="constraint-backed", detail=f"{args.path} is absent")
    expected = _TYPES[args.type]
    # bool is an int in Python; no contract means that when it says integer.
    if args.type in {"number", "integer"} and isinstance(value, bool):
        ok = False
    else:
        ok = isinstance(value, expected)
    detail = "" if ok else f"{args.path} is {type(value).__name__}, expected {args.type}"
    return Outcome(passed=ok, mode="constraint-backed", detail=detail)


def numeric_range(
    args: NumericRangeArgs,
    deliverable: Mapping[str, Any],
    answer_key: Mapping[str, Any] | None = None,
    **_: Any,
) -> Outcome:
    if args.of == "value":
        raw = select_one(deliverable, args.path)
        if raw is MISSING:
            return Outcome(passed=False, mode="constraint-backed", detail=f"{args.path} is absent")
        try:
            actual = _numeric(raw)
        except VerifierError as exc:
            return Outcome(passed=False, mode="constraint-backed", detail=str(exc))
    else:
        raw = select_one(deliverable, args.path)
        if raw is MISSING:
            return Outcome(passed=False, mode="constraint-backed", detail=f"{args.path} is absent")
        if not isinstance(raw, list):
            return Outcome(
                passed=False,
                mode="constraint-backed",
                detail=f"{args.path} is {type(raw).__name__}, expected array",
            )
        items = [_hashable(i) for i in raw]
        actual = float(len(set(items)) if args.of == "distinct-count" else len(items))

    low, high = _resolve_bounds(args, answer_key)
    if low is not None and actual < low:
        return Outcome(passed=False, mode="constraint-backed", detail=f"{actual} below {low}")
    if high is not None and actual > high:
        return Outcome(passed=False, mode="constraint-backed", detail=f"{actual} above {high}")
    return Outcome(passed=True, mode="constraint-backed")


def _hashable(item: Any) -> Any:
    """Distinct-count must survive dict and list members without raising."""
    if isinstance(item, dict):
        return tuple(sorted((k, _hashable(v)) for k, v in item.items()))
    if isinstance(item, list):
        return tuple(_hashable(i) for i in item)
    return item


def _resolve_bounds(
    args: NumericRangeArgs, answer_key: Mapping[str, Any] | None
) -> tuple[float | None, float | None]:
    low, high = args.min, args.max
    for attribute, setter in (("min_from_key", "low"), ("max_from_key", "high")):
        key = getattr(args, attribute)
        if key is None:
            continue
        if answer_key is None or key not in answer_key:
            raise VerifierError(f"{attribute} names {key!r}, absent from the answer key")
        bound = _numeric(answer_key[key])
        if setter == "low":
            low = bound
        else:
            high = bound
    if low is not None and high is not None and low > high:
        raise VerifierError(f"resolved bounds are empty: {low} > {high}")
    return low, high


def set_membership(args: SetMembershipArgs, deliverable: Mapping[str, Any], **_: Any) -> Outcome:
    value = select_one(deliverable, args.path)
    if value is MISSING:
        return Outcome(passed=False, mode="constraint-backed", detail=f"{args.path} is absent")
    ok = value in args.allowed
    detail = "" if ok else f"{value!r} is not in the permitted set"
    return Outcome(passed=ok, mode="constraint-backed", detail=detail)


def regex_match(args: RegexMatchArgs, deliverable: Mapping[str, Any], **_: Any) -> Outcome:
    value = select_one(deliverable, args.path)
    if value is MISSING:
        return Outcome(passed=False, mode="constraint-backed", detail=f"{args.path} is absent")
    if not isinstance(value, str):
        return Outcome(
            passed=False,
            mode="constraint-backed",
            detail=f"{args.path} is {type(value).__name__}, expected string",
        )
    encoded = value.encode("utf-8")
    if len(encoded) > args.max_input_bytes:
        return Outcome(
            passed=False,
            mode="constraint-backed",
            detail=f"{args.path} is {len(encoded)} bytes, over the declared "
            f"{args.max_input_bytes}",
        )
    ok = re.compile(args.pattern).search(value) is not None
    detail = "" if ok else f"{args.path} does not match"
    return Outcome(passed=ok, mode="constraint-backed", detail=detail)


def exact_match_against_answer_key(
    args: ExactMatchArgs,
    deliverable: Mapping[str, Any],
    answer_key: Mapping[str, Any] | None = None,
    **_: Any,
) -> Outcome:
    if answer_key is None:
        raise VerifierError("exact-match-against-answer-key needs an answer key")
    if args.key not in answer_key:
        raise VerifierError(f"answer key has no entry {args.key!r}")
    value = select_one(deliverable, args.path)
    if value is MISSING:
        return Outcome(passed=False, mode="reference-backed", detail=f"{args.path} is absent")
    expected = answer_key[args.key]
    # Booleans compare equal to 0 and 1 in Python; a reference-backed pass may
    # not rest on that.
    if isinstance(value, bool) != isinstance(expected, bool):
        ok = False
    elif isinstance(expected, int | float) and isinstance(value, int | float):
        ok = float(value) == float(expected)
    else:
        ok = value == expected
    detail = "" if ok else f"{value!r} does not equal the key's {expected!r}"
    return Outcome(passed=ok, mode="reference-backed", detail=detail)


def citation_resolves(
    args: CitationResolvesArgs,
    deliverable: Mapping[str, Any],
    citable_index: CitableIndex | None = None,
    **_: Any,
) -> Outcome:
    if citable_index is None:
        raise VerifierError("citation-resolves needs the citable index from its caller")
    found = select(deliverable, args.path)
    if len(found) < args.min_citations:
        return Outcome(
            passed=False,
            mode="reference-backed",
            detail=f"{len(found)} citations, needs at least {args.min_citations}",
        )
    unresolved = sorted({str(i) for i in found if i not in citable_index})
    if unresolved:
        return Outcome(
            passed=False,
            mode="reference-backed",
            detail=f"unresolvable citations: {unresolved}",
        )
    return Outcome(passed=True, mode="reference-backed")


class RegisteredVerifier(BaseModel):
    """One registry entry. The mode lives here and nowhere else."""

    model_config = ConfigDict(frozen=True, extra="forbid", arbitrary_types_allowed=True)

    type: str
    mode: VerificationMode
    args_model: type[_Args]
    run: Any


REGISTRY: Final[dict[str, RegisteredVerifier]] = {
    entry.type: entry
    for entry in (
        RegisteredVerifier(
            type="field-present",
            mode="constraint-backed",
            args_model=FieldPresentArgs,
            run=field_present,
        ),
        RegisteredVerifier(
            type="type-is", mode="constraint-backed", args_model=TypeIsArgs, run=type_is
        ),
        RegisteredVerifier(
            type="numeric-range",
            mode="constraint-backed",
            args_model=NumericRangeArgs,
            run=numeric_range,
        ),
        RegisteredVerifier(
            type="set-membership",
            mode="constraint-backed",
            args_model=SetMembershipArgs,
            run=set_membership,
        ),
        RegisteredVerifier(
            type="regex-match",
            mode="constraint-backed",
            args_model=RegexMatchArgs,
            run=regex_match,
        ),
        RegisteredVerifier(
            type="exact-match-against-answer-key",
            mode="reference-backed",
            args_model=ExactMatchArgs,
            run=exact_match_against_answer_key,
        ),
        RegisteredVerifier(
            type="citation-resolves",
            mode="reference-backed",
            args_model=CitationResolvesArgs,
            run=citation_resolves,
        ),
    )
}

REGISTRY_VERSION: Final[str] = "v1"


def mode_for(verifier_type: str) -> VerificationMode:
    """The mode is a property of the type. Nothing may assert it separately."""
    try:
        return REGISTRY[verifier_type].mode
    except KeyError:
        raise VerifierError(f"unregistered verifier type: {verifier_type!r}") from None


def build_args(verifier_type: str, args: Mapping[str, Any]) -> _Args:
    """Validate declared arguments, including the path grammar."""
    try:
        entry = REGISTRY[verifier_type]
    except KeyError:
        raise VerifierError(f"unregistered verifier type: {verifier_type!r}") from None
    built = entry.args_model.model_validate(dict(args))
    try:
        wildcarded = has_wildcard(built.path)
    except PathError as exc:
        raise VerifierError(f"{verifier_type}: {exc}") from exc
    if wildcarded and verifier_type != "citation-resolves":
        raise VerifierError(f"{verifier_type} is single-valued and cannot take a wildcard path")
    return built


def verify(
    verifier_type: str,
    args: Mapping[str, Any],
    deliverable: Mapping[str, Any],
    *,
    answer_key: Mapping[str, Any] | None = None,
    citable_index: CitableIndex | None = None,
) -> Outcome:
    """Run one registered verifier. Pure: everything it reads is an argument."""
    entry = REGISTRY[verifier_type] if verifier_type in REGISTRY else None
    if entry is None:
        raise VerifierError(f"unregistered verifier type: {verifier_type!r}")
    built = build_args(verifier_type, args)
    outcome: Outcome = entry.run(
        built, deliverable, answer_key=answer_key, citable_index=citable_index
    )
    if outcome.mode != entry.mode:
        raise VerifierError(
            f"{verifier_type} reported mode {outcome.mode!r}, registry fixes {entry.mode!r}"
        )
    return outcome


def registry_digest() -> Any:
    """Hash the registry's declared surface, for the E1b freeze."""
    from ..canon import hash_structure

    return hash_structure(
        {
            "version": REGISTRY_VERSION,
            "verifiers": [
                {
                    "type": entry.type,
                    "mode": entry.mode,
                    "args": sorted(entry.args_model.model_fields),
                }
                for entry in sorted(REGISTRY.values(), key=lambda e: e.type)
            ],
        }
    )
