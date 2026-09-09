from __future__ import annotations

from pathlib import Path

from outcomefuse.core.canon import (
    ROUTE_FILE_DIGEST,
    ROUTE_STRUCTURE,
    build_file_manifest,
    canonical_bytes,
    hash_file_manifest,
    hash_structure,
)


def _tree(root: Path) -> None:
    (root / "a.py").write_bytes(b"print('hi')\n")
    (root / "b.bin").write_bytes(b"\x00\x01\x02")


def test_a_structure_hash_of_a_manifest_cannot_equal_that_manifest_digest(
    tmp_path: Path,
) -> None:
    _tree(tmp_path)
    paths = ["a.py", "b.bin"]
    manifest = build_file_manifest(tmp_path, paths)
    manifest_shaped = [entry.model_dump(mode="python") for entry in manifest]

    file_digest = hash_file_manifest(tmp_path, paths)
    structure_digest = hash_structure(manifest_shaped)

    assert file_digest.route == ROUTE_FILE_DIGEST
    assert structure_digest.route == ROUTE_STRUCTURE
    assert file_digest.sha256 != structure_digest.sha256


def test_the_route_id_is_bound_into_the_hashed_bytes(tmp_path: Path) -> None:
    _tree(tmp_path)
    manifest = build_file_manifest(tmp_path, ["a.py"])
    payload = [entry.model_dump(mode="python") for entry in manifest]

    # The two envelopes differ only in the route field, and that alone must move the digest.
    structure_envelope = canonical_bytes(
        {"normalisation": "v1", "payload": payload, "route": ROUTE_STRUCTURE}
    )
    file_envelope = canonical_bytes(
        {"normalisation": "v1", "payload": payload, "route": ROUTE_FILE_DIGEST}
    )
    assert structure_envelope != file_envelope


def test_the_normalisation_version_is_bound_into_the_hashed_bytes() -> None:
    v1 = canonical_bytes({"normalisation": "v1", "payload": 1, "route": ROUTE_STRUCTURE})
    v2 = canonical_bytes({"normalisation": "v2", "payload": 1, "route": ROUTE_STRUCTURE})
    assert v1 != v2


def test_the_bare_payload_is_never_the_hashed_form() -> None:
    import hashlib

    bare = hashlib.sha256(canonical_bytes({"a": 1})).hexdigest()
    assert hash_structure({"a": 1}).sha256 != bare
