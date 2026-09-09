from __future__ import annotations

import hashlib
from typing import Any

import pytest
from pydantic import ValidationError

from outcomefuse.core.canon import (
    KNOWN_ROUTES,
    NORMALISATION_VERSION,
    ROUTE_FILE_DIGEST,
    ROUTE_STRUCTURE,
    Digest,
    RouteDeclarationError,
    canonical_bytes,
    hash_structure,
    require_route,
)

_SHA = "0" * 64


def _record(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "route": ROUTE_STRUCTURE,
        "normalisation": NORMALISATION_VERSION,
        "sha256": _SHA,
    }
    base.update(overrides)
    return base


def test_route_registry_is_exactly_two_routes() -> None:
    assert KNOWN_ROUTES == frozenset({ROUTE_STRUCTURE, ROUTE_FILE_DIGEST})


def test_hash_structure_declares_its_route_and_normalisation() -> None:
    digest = hash_structure({"a": 1})
    assert digest.route == ROUTE_STRUCTURE
    assert digest.normalisation == NORMALISATION_VERSION
    assert len(digest.sha256) == 64


def test_one_and_one_point_zero_hash_identically() -> None:
    assert hash_structure({"a": 1}).sha256 == hash_structure({"a": 1.0}).sha256


def test_the_structure_route_hashes_to_a_pinned_value() -> None:
    # Pins the envelope key names and the route id as well as the digest: without this,
    # renaming "payload" or bumping the route id leaves the suite green while silently
    # invalidating every frozen structure digest.
    envelope = canonical_bytes(
        {"normalisation": NORMALISATION_VERSION, "payload": {"a": 1}, "route": ROUTE_STRUCTURE}
    )
    assert envelope == b'{"normalisation":"v1","payload":{"a":1},"route":"structure/v1"}'
    assert (
        hash_structure({"a": 1}).sha256
        == "fb2dc3f58d6b452db57223cca043cce2f187530ab0d8bf81e8ce8e349408bf20"
    )
    assert hash_structure({"a": 1}).sha256 == hashlib.sha256(envelope).hexdigest()


def test_digest_is_immutable() -> None:
    digest = hash_structure(1)
    with pytest.raises(ValidationError):
        digest.sha256 = _SHA  # type: ignore[misc]


def test_extra_fields_are_forbidden() -> None:
    with pytest.raises(ValidationError):
        Digest.model_validate(_record(extra="x"))


@pytest.mark.parametrize("bad", ["", "0" * 63, "0" * 65, "G" * 64, "A" * 64, " " * 64])
def test_sha256_shape_is_enforced_on_deserialised_records(bad: str) -> None:
    with pytest.raises(ValidationError):
        Digest.model_validate(_record(sha256=bad))


def test_empty_normalisation_is_rejected_on_deserialised_records() -> None:
    with pytest.raises(ValidationError):
        Digest.model_validate(_record(normalisation=""))


def test_absent_route_id_is_unrepresentable() -> None:
    payload = _record()
    del payload["route"]
    with pytest.raises(RouteDeclarationError, match="absent"):
        Digest.model_validate(payload)


def test_null_route_id_is_reported_as_absent() -> None:
    with pytest.raises(RouteDeclarationError, match="absent"):
        Digest.model_validate(_record(route=None))


def test_empty_route_id_is_reported_as_empty() -> None:
    with pytest.raises(RouteDeclarationError, match="empty"):
        Digest.model_validate(_record(route="   "))


def test_non_string_route_id_is_reported_as_a_type_error() -> None:
    with pytest.raises(RouteDeclarationError, match="must be a string, got int"):
        Digest.model_validate(_record(route=7))


def test_unknown_route_id_is_named() -> None:
    with pytest.raises(RouteDeclarationError, match="structure/v2"):
        Digest.model_validate(_record(route="structure/v2"))


def test_direct_construction_rejects_an_unknown_route() -> None:
    with pytest.raises(RouteDeclarationError, match="structure/v2"):
        Digest(route="structure/v2", normalisation=NORMALISATION_VERSION, sha256=_SHA)


def test_direct_construction_rejects_an_unpinned_normalisation() -> None:
    with pytest.raises(RouteDeclarationError, match="normalisation"):
        Digest(route=ROUTE_STRUCTURE, normalisation="v0", sha256=_SHA)


def test_model_copy_cannot_smuggle_in_an_unknown_route() -> None:
    digest = hash_structure("x")
    with pytest.raises(RouteDeclarationError, match="structure/v2"):
        digest.model_copy(update={"route": "structure/v2"})


def test_model_copy_cannot_smuggle_in_a_stale_normalisation() -> None:
    digest = hash_structure("x")
    with pytest.raises(RouteDeclarationError, match="normalisation"):
        digest.model_copy(update={"normalisation": "v0"})


def test_model_copy_to_the_other_known_route_still_works() -> None:
    digest = hash_structure("x")
    copied = digest.model_copy(update={"route": ROUTE_FILE_DIGEST})
    assert copied.route == ROUTE_FILE_DIGEST
    assert copied.sha256 == digest.sha256
    assert digest.model_copy() == digest


def test_require_route_accepts_a_matching_digest() -> None:
    require_route(hash_structure("x"), ROUTE_STRUCTURE)


def test_require_route_accepts_a_mapping() -> None:
    require_route(_record(), ROUTE_STRUCTURE)


def test_require_route_rejects_a_mismatched_route() -> None:
    with pytest.raises(RouteDeclarationError, match="expected"):
        require_route(hash_structure("x"), ROUTE_FILE_DIGEST)


def test_require_route_rejects_a_mismatched_normalisation() -> None:
    stale = _record(normalisation="v0")
    with pytest.raises(RouteDeclarationError, match="normalisation"):
        require_route(stale, ROUTE_STRUCTURE)


def test_require_route_rejects_an_unknown_expected_route() -> None:
    with pytest.raises(RouteDeclarationError, match="file-digest/v2"):
        require_route(hash_structure("x"), "file-digest/v2")


def test_require_route_reports_a_malformed_record_as_a_route_error() -> None:
    with pytest.raises(RouteDeclarationError, match="not well-formed"):
        require_route(_record(sha256="nope"), ROUTE_STRUCTURE)


def test_require_route_rejects_a_non_mapping() -> None:
    with pytest.raises(RouteDeclarationError, match="mapping"):
        require_route("structure/v1", ROUTE_STRUCTURE)  # type: ignore[arg-type]
