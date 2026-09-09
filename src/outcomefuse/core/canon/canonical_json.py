"""Normalisation ``v1`` — the only serialisation admitted on the hashing path.

Two independent implementations of AD-6 must agree byte for byte, so every rule
here is explicit: no ``json.dumps`` defaults, no locale- or platform-dependent
formatting, no coercion of anything ambiguous.

Mapping keys are sorted by their **UTF-8 byte sequence**. This is the rule a
non-Python implementation is most likely to get wrong: languages whose native
string order is UTF-16 code-unit order (Java, JavaScript, C#) sort non-BMP
characters *before* the U+E000 to U+FFFD range, because a surrogate pair starts at
0xD800, whereas in UTF-8 the same characters sort *after*. Sorting by the encoded
bytes is mandatory; sorting by the host language's default string order is not.

Closed error contract: :func:`canonical_bytes` raises :class:`CanonicalisationError`
and nothing else.
"""

from __future__ import annotations

import math
import unicodedata
from collections.abc import Mapping, Sequence
from decimal import Decimal
from typing import Any, Final

from pydantic import BaseModel

#: Containers nested deeper than this are rejected rather than surfacing as ``RecursionError``.
MAX_DEPTH: Final = 64

#: Output is exponent-free, so ``Decimal("1E+1000000")`` would expand without bound.
MAX_DECIMAL_EXPONENT: Final = 4096

#: Integers wider than this are rejected. Without a declared bound the limit would be
#: ``sys.int_max_str_digits``, which the ``PYTHONINTMAXSTRDIGITS`` environment variable
#: can change — so one process would hash what another rejects.
MAX_INT_DIGITS: Final = 4096

_INT_BOUND: Final = 10**MAX_INT_DIGITS
_INT_CHUNK: Final = 10**18

_ESCAPES: Final[dict[str, str]] = {
    '"': '\\"',
    "\\": "\\\\",
    "\b": "\\b",
    "\f": "\\f",
    "\n": "\\n",
    "\r": "\\r",
    "\t": "\\t",
}


class CanonicalisationError(Exception):
    """Input cannot be represented under normalisation ``v1``."""


def canonical_bytes(value: Any) -> bytes:
    """Serialise ``value`` to the canonical UTF-8 byte form of normalisation ``v1``."""
    parts: list[str] = []
    _emit(value, parts, 0, [])
    return "".join(parts).encode("utf-8")


def _emit(value: Any, parts: list[str], depth: int, stack: list[int]) -> None:
    if value is None:
        parts.append("null")
        return
    if isinstance(value, bool):
        # Checked before the numeric branch: True is an int subclass, and must not collide with 1.
        parts.append("true" if value else "false")
        return
    if isinstance(value, str):
        parts.append(_encode_string(value))
        return
    if isinstance(value, int | float | Decimal):
        parts.append(_encode_number(value))
        return
    if isinstance(value, BaseModel):
        _emit(_dump_model(value), parts, depth, stack)
        return
    if isinstance(value, bytes | bytearray | memoryview):
        raise CanonicalisationError(
            f"unsupported type on the hashing path: {type(value).__name__}"
        )
    if isinstance(value, Mapping):
        _emit_mapping(value, parts, depth, stack)
        return
    if isinstance(value, Sequence):
        _emit_sequence(value, parts, depth, stack)
        return
    raise CanonicalisationError(f"unsupported type on the hashing path: {type(value).__name__}")


def _dump_model(model: BaseModel) -> Any:
    try:
        return model.model_dump(mode="python")
    except Exception as exc:
        raise CanonicalisationError(
            f"model {type(model).__name__} could not be dumped: {exc}"
        ) from exc


def _enter(container: Any, depth: int, stack: list[int]) -> None:
    if depth >= MAX_DEPTH:
        raise CanonicalisationError(f"structure is nested deeper than {MAX_DEPTH} levels")
    if id(container) in stack:
        raise CanonicalisationError(
            f"structure contains a cycle through a {type(container).__name__}"
        )
    stack.append(id(container))


def _emit_mapping(value: Mapping[Any, Any], parts: list[str], depth: int, stack: list[int]) -> None:
    _enter(value, depth, stack)
    try:
        items: list[tuple[bytes, str, Any]] = []
        seen: dict[bytes, str] = {}
        for raw_key, item in value.items():
            if not isinstance(raw_key, str):
                raise CanonicalisationError(
                    f"mapping keys must be str, got {type(raw_key).__name__}"
                )
            key = _nfc(raw_key)
            encoded = _utf8(key)
            previous = seen.get(encoded)
            if previous is not None:
                raise CanonicalisationError(
                    f"mapping keys {previous!r} and {raw_key!r} collide after NFC normalisation"
                )
            seen[encoded] = raw_key
            items.append((encoded, key, item))
        items.sort(key=lambda entry: entry[0])
        parts.append("{")
        for index, (_, key, item) in enumerate(items):
            if index:
                parts.append(",")
            parts.append(_encode_string(key))
            parts.append(":")
            _emit(item, parts, depth + 1, stack)
        parts.append("}")
    finally:
        stack.pop()


def _emit_sequence(
    value: Sequence[Any], parts: list[str], depth: int, stack: list[int]
) -> None:
    _enter(value, depth, stack)
    try:
        parts.append("[")
        for index, item in enumerate(value):
            if index:
                parts.append(",")
            _emit(item, parts, depth + 1, stack)
        parts.append("]")
    finally:
        stack.pop()


def _nfc(value: str) -> str:
    return unicodedata.normalize("NFC", value)


def _utf8(value: str) -> bytes:
    try:
        return value.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise CanonicalisationError(
            f"string is not encodable as UTF-8 (lone surrogate?): {value!r}"
        ) from exc


def _encode_string(raw: str) -> str:
    value = _nfc(raw)
    _utf8(value)
    out = ['"']
    for char in value:
        escape = _ESCAPES.get(char)
        if escape is not None:
            out.append(escape)
        elif char < "\x20":
            out.append(f"\\u{ord(char):04x}")
        else:
            out.append(char)
    out.append('"')
    return "".join(out)


def _int_text(value: int) -> str:
    """Render an integer, bounded and independent of ``sys.int_max_str_digits``."""
    if value >= _INT_BOUND or value <= -_INT_BOUND:
        raise CanonicalisationError(
            f"integer has more than {MAX_INT_DIGITS} digits and is not representable"
        )
    magnitude = -value if value < 0 else value
    # Chunked so no single str() call can trip the interpreter's process-local digit limit.
    chunks: list[str] = []
    while magnitude >= _INT_CHUNK:
        magnitude, low = divmod(magnitude, _INT_CHUNK)
        chunks.append(f"{low:018d}")
    chunks.append(str(magnitude))
    return ("-" if value < 0 else "") + "".join(reversed(chunks))


def _encode_number(value: int | float | Decimal) -> str:
    if isinstance(value, int):
        return _int_text(value)
    if isinstance(value, float):
        if not math.isfinite(value):
            raise CanonicalisationError(f"non-finite number is not representable: {value!r}")
        # Python's shortest round-trip repr is deterministic for IEEE-754 doubles.
        dec = Decimal(str(value))
    else:
        if not value.is_finite():
            raise CanonicalisationError(f"non-finite number is not representable: {value}")
        dec = value

    exponent = dec.as_tuple().exponent
    if not isinstance(exponent, int) or abs(exponent) > MAX_DECIMAL_EXPONENT:
        raise CanonicalisationError(
            f"decimal exponent exceeds the {MAX_DECIMAL_EXPONENT} bound: {value}"
        )

    try:
        if dec == dec.to_integral_value():
            return _int_text(int(dec))
        text = format(dec, "f")
    except (ArithmeticError, ValueError) as exc:
        raise CanonicalisationError(f"number is not representable: {value}") from exc

    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"
