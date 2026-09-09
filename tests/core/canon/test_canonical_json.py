from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest
from pydantic import BaseModel

from outcomefuse.core.canon import (
    MAX_DECIMAL_EXPONENT,
    MAX_DEPTH,
    MAX_INT_DIGITS,
    CanonicalisationError,
    canonical_bytes,
)


class _Model(BaseModel):
    b: int
    a: str


def test_int_and_float_of_the_same_value_are_indistinguishable() -> None:
    assert canonical_bytes({"a": 1}) == canonical_bytes({"a": 1.0})
    assert canonical_bytes({"a": 1}) == canonical_bytes({"a": Decimal("1.000")})


def test_key_order_does_not_affect_the_canonical_form() -> None:
    assert canonical_bytes({"a": 1, "b": 2}) == canonical_bytes({"b": 2, "a": 1})


def test_array_order_is_significant() -> None:
    assert canonical_bytes([1, 2]) != canonical_bytes([2, 1])


def test_nfc_and_nfd_spellings_agree() -> None:
    nfc, nfd = "caf\u00e9", "cafe\u0301"
    assert nfc != nfd
    assert canonical_bytes(nfc) == canonical_bytes(nfd)
    assert canonical_bytes({nfc: 1}) == canonical_bytes({nfd: 1})


def test_bool_does_not_collide_with_int() -> None:
    assert canonical_bytes(True) != canonical_bytes(1)
    assert canonical_bytes(False) != canonical_bytes(0)
    assert canonical_bytes({"a": True}) == b'{"a":true}'


def test_exact_canonical_form_is_pinned() -> None:
    value = {"b": [1, 2.5, True, None], "a": "x\ny", "": {}}
    assert canonical_bytes(value) == b'{"":{},"a":"x\\ny","b":[1,2.5,true,null]}'


def test_keys_are_sorted_by_their_encoded_bytes() -> None:
    assert canonical_bytes({"\u00e9": 1, "z": 2, "Z": 3}) == b'{"Z":3,"z":2,"\xc3\xa9":1}'


def test_non_bmp_keys_sort_by_utf8_bytes_not_utf16_code_units() -> None:
    # U+FFFD encodes as EF BF BD and U+1F600 as F0 9F 98 80, so UTF-8 puts U+FFFD first.
    # A UTF-16 implementation sees the surrogate D83D for U+1F600 and orders it first instead.
    emoji, replacement = "\U0001f600", "\ufffd"
    assert canonical_bytes({emoji: 1, replacement: 2}) == (
        b'{"' + replacement.encode("utf-8") + b'":2,"' + emoji.encode("utf-8") + b'":1}'
    )
    utf16_order = sorted([emoji, replacement], key=lambda key: key.encode("utf-16-be"))
    utf8_order = sorted([emoji, replacement], key=lambda key: key.encode("utf-8"))
    assert utf16_order != utf8_order


def test_numbers_never_use_exponent_notation() -> None:
    assert canonical_bytes(1e21) == b"1" + b"0" * 21
    assert canonical_bytes(Decimal("1E-8")) == b"0.00000001"
    assert canonical_bytes(-0.0) == b"0"
    assert canonical_bytes(Decimal("-0")) == b"0"
    assert canonical_bytes(Decimal("1.50")) == b"1.5"


def test_pydantic_models_are_dumped_and_sorted() -> None:
    assert canonical_bytes(_Model(b=2, a="x")) == b'{"a":"x","b":2}'


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_non_finite_numbers_are_rejected(value: float) -> None:
    with pytest.raises(CanonicalisationError, match="non-finite"):
        canonical_bytes(value)


def test_non_finite_decimal_is_rejected() -> None:
    with pytest.raises(CanonicalisationError, match="non-finite"):
        canonical_bytes(Decimal("NaN"))


@pytest.mark.parametrize("key", [1, None, (1, 2), True])
def test_non_string_mapping_keys_are_rejected(key: object) -> None:
    with pytest.raises(CanonicalisationError, match="mapping keys must be str"):
        canonical_bytes({key: "a"})


@pytest.mark.parametrize(
    "value",
    [
        dt.datetime(2026, 9, 9, tzinfo=dt.UTC),
        {1, 2},
        object(),
        b"bytes",
        bytearray(b"bytes"),
        frozenset(),
    ],
)
def test_unsupported_types_are_rejected_by_name(value: object) -> None:
    with pytest.raises(CanonicalisationError, match=type(value).__name__):
        canonical_bytes(value)


def test_nfc_key_collisions_are_rejected_rather_than_coerced() -> None:
    with pytest.raises(CanonicalisationError, match="collide after NFC"):
        canonical_bytes({"caf\u00e9": 1, "cafe\u0301": 2})


def test_cycles_raise_the_domain_error_not_recursion_error() -> None:
    cyclic: dict[str, object] = {}
    cyclic["self"] = cyclic
    with pytest.raises(CanonicalisationError, match="cycle"):
        canonical_bytes(cyclic)

    outer: list[object] = []
    outer.append([outer])
    with pytest.raises(CanonicalisationError, match="cycle"):
        canonical_bytes(outer)


def test_over_deep_nesting_raises_the_domain_error() -> None:
    deep: list[object] = []
    cursor = deep
    for _ in range(MAX_DEPTH + 5):
        nxt: list[object] = []
        cursor.append(nxt)
        cursor = nxt
    with pytest.raises(CanonicalisationError, match="nested deeper"):
        canonical_bytes(deep)


def test_nesting_at_the_bound_is_accepted() -> None:
    value: object = 1
    for _ in range(MAX_DEPTH):
        value = [value]
    assert canonical_bytes(value).endswith(b"]")


def test_lone_surrogate_raises_the_domain_error_not_unicode_error() -> None:
    with pytest.raises(CanonicalisationError, match="lone surrogate"):
        canonical_bytes("\ud800")
    with pytest.raises(CanonicalisationError, match="lone surrogate"):
        canonical_bytes({"\ud800": 1})


def test_out_of_range_decimal_exponent_is_rejected() -> None:
    with pytest.raises(CanonicalisationError, match="exponent"):
        canonical_bytes(Decimal("1E+1000000"))
    with pytest.raises(CanonicalisationError, match="exponent"):
        canonical_bytes(Decimal("1E-1000000"))


def test_a_decimal_exponent_at_the_bound_is_accepted() -> None:
    # Negative side only: a positive exponent at the bound is an integer one digit past
    # MAX_INT_DIGITS, and is rejected by that bound instead.
    encoded = canonical_bytes(Decimal(f"1E-{MAX_DECIMAL_EXPONENT}"))
    assert encoded == b"0." + b"0" * (MAX_DECIMAL_EXPONENT - 1) + b"1"


@pytest.mark.parametrize("sign", ["+", "-"])
def test_a_decimal_exponent_just_over_the_bound_is_rejected(sign: str) -> None:
    with pytest.raises(CanonicalisationError, match="exponent"):
        canonical_bytes(Decimal(f"1E{sign}{MAX_DECIMAL_EXPONENT + 1}"))


def test_an_integer_at_the_digit_bound_is_accepted() -> None:
    value = 10 ** (MAX_INT_DIGITS - 1)
    assert canonical_bytes(value) == b"1" + b"0" * (MAX_INT_DIGITS - 1)
    assert canonical_bytes(-value) == b"-1" + b"0" * (MAX_INT_DIGITS - 1)


@pytest.mark.parametrize("sign", [1, -1])
def test_an_integer_just_over_the_digit_bound_is_rejected(sign: int) -> None:
    # str(int) is bounded by sys.int_max_str_digits, which the environment can change:
    # without our own bound the same payload hashes in one process and fails in another.
    with pytest.raises(CanonicalisationError, match=f"more than {MAX_INT_DIGITS} digits"):
        canonical_bytes(sign * 10**MAX_INT_DIGITS)


def test_an_over_wide_integral_decimal_is_rejected_too() -> None:
    with pytest.raises(CanonicalisationError, match=f"more than {MAX_INT_DIGITS} digits"):
        canonical_bytes(Decimal("9" * (MAX_INT_DIGITS + 1)))


def test_control_characters_use_a_fixed_escape_form() -> None:
    assert canonical_bytes("\x00\x1f\t\\\"") == b'"\\u0000\\u001f\\t\\\\\\""'
