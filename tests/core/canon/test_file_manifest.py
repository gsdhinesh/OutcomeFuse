from __future__ import annotations

import subprocess
import sys
import unicodedata
from pathlib import Path

import pytest

from outcomefuse.core.canon import (
    DEFAULT_TEXT_SUFFIXES,
    ROUTE_FILE_DIGEST,
    ManifestError,
    build_file_manifest,
    hash_file_manifest,
    require_route,
)
from outcomefuse.core.canon import file_manifest as file_manifest_module


def _write(root: Path, relative: str, data: bytes) -> None:
    target = root / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)


def test_text_files_are_line_ending_insensitive(tmp_path: Path) -> None:
    crlf, lf = tmp_path / "crlf", tmp_path / "lf"
    _write(crlf, "a.py", b"one\r\ntwo\r\n")
    _write(lf, "a.py", b"one\ntwo\n")
    assert hash_file_manifest(crlf, ["a.py"]) == hash_file_manifest(lf, ["a.py"])


def test_lone_carriage_returns_are_normalised(tmp_path: Path) -> None:
    cr, lf = tmp_path / "cr", tmp_path / "lf"
    _write(cr, "a.py", b"one\rtwo\r")
    _write(lf, "a.py", b"one\ntwo\n")
    assert hash_file_manifest(cr, ["a.py"]) == hash_file_manifest(lf, ["a.py"])


def test_an_explicitly_declared_extensionless_text_file_is_line_ending_insensitive(
    tmp_path: Path,
) -> None:
    crlf, lf = tmp_path / "crlf", tmp_path / "lf"
    _write(crlf, "Dockerfile", b"FROM scratch\r\n")
    _write(lf, "Dockerfile", b"FROM scratch\n")

    assert hash_file_manifest(crlf, [("Dockerfile", "text")]) == hash_file_manifest(
        lf, [("Dockerfile", "text")]
    )
    # Without the declaration the same file falls to binary and re-acquires the sensitivity.
    assert hash_file_manifest(crlf, ["Dockerfile"]) != hash_file_manifest(lf, ["Dockerfile"])


def test_text_file_content_still_changes_the_digest(tmp_path: Path) -> None:
    one, two = tmp_path / "one", tmp_path / "two"
    _write(one, "a.py", b"value = 1\n")
    _write(two, "a.py", b"value = 2\n")
    assert hash_file_manifest(one, ["a.py"]) != hash_file_manifest(two, ["a.py"])


def test_binary_file_bytes_change_the_digest(tmp_path: Path) -> None:
    one, two = tmp_path / "one", tmp_path / "two"
    _write(one, "b.bin", b"\x00\x01")
    _write(two, "b.bin", b"\x00\x02")
    assert hash_file_manifest(one, ["b.bin"]) != hash_file_manifest(two, ["b.bin"])


def test_path_separator_style_does_not_matter(tmp_path: Path) -> None:
    _write(tmp_path, "a/b.py", b"x = 1\n")
    assert hash_file_manifest(tmp_path, ["a\\b.py"]) == hash_file_manifest(tmp_path, ["a/b.py"])


def test_recorded_paths_are_nfc_normalised(tmp_path: Path) -> None:
    nfd = "cafe\u0301.py"
    _write(tmp_path, nfd, b"x = 1\n")
    entries = build_file_manifest(tmp_path, [nfd])
    assert entries[0].path == unicodedata.normalize("NFC", nfd)


def test_entries_are_byte_sorted(tmp_path: Path) -> None:
    for name in ("z.py", "a.py", "Z.py", "m/n.py"):
        _write(tmp_path, name, b"x = 1\n")
    entries = build_file_manifest(tmp_path, ["z.py", "m/n.py", "a.py", "Z.py"])
    paths = [entry.path for entry in entries]
    assert paths == sorted(paths, key=lambda item: item.encode("utf-8"))
    assert paths == ["Z.py", "a.py", "m/n.py", "z.py"]


def test_mode_is_recorded_per_entry(tmp_path: Path) -> None:
    _write(tmp_path, "a.py", b"x = 1\n")
    _write(tmp_path, "b.bin", b"\x00")
    modes = {entry.path: entry.mode for entry in build_file_manifest(tmp_path, ["a.py", "b.bin"])}
    assert modes == {"a.py": "text", "b.bin": "binary"}


@pytest.mark.parametrize("name", ["A.PY", "README.MD", "Notes.Txt"])
def test_suffix_matching_is_case_insensitive(tmp_path: Path, name: str) -> None:
    crlf, lf = tmp_path / "crlf", tmp_path / "lf"
    _write(crlf, name, b"one\r\ntwo\r\n")
    _write(lf, name, b"one\ntwo\n")
    assert build_file_manifest(lf, [name])[0].mode == "text"
    assert hash_file_manifest(crlf, [name]) == hash_file_manifest(lf, [name])


def test_the_default_text_suffixes_are_pinned() -> None:
    # .csv is deliberately absent: RFC 4180 makes a CRLF inside a quoted field data, so
    # folding it would collapse two genuinely different files onto one digest.
    assert DEFAULT_TEXT_SUFFIXES == frozenset(
        {
            ".cfg",
            ".css",
            ".html",
            ".ini",
            ".js",
            ".json",
            ".jsonl",
            ".md",
            ".ps1",
            ".py",
            ".rst",
            ".sh",
            ".sql",
            ".toml",
            ".ts",
            ".txt",
            ".yaml",
            ".yml",
        }
    )


def test_csv_is_binary_unless_the_caller_declares_otherwise(tmp_path: Path) -> None:
    crlf, lf = tmp_path / "crlf", tmp_path / "lf"
    _write(crlf, "rows.csv", b'"a\r\nb",1\r\n')
    _write(lf, "rows.csv", b'"a\nb",1\n')
    assert build_file_manifest(lf, ["rows.csv"])[0].mode == "binary"
    assert hash_file_manifest(crlf, ["rows.csv"]) != hash_file_manifest(lf, ["rows.csv"])
    assert hash_file_manifest(crlf, [("rows.csv", "text")]) == hash_file_manifest(
        lf, [("rows.csv", "text")]
    )


def test_custom_text_suffixes_override_the_default(tmp_path: Path) -> None:
    crlf, lf = tmp_path / "crlf", tmp_path / "lf"
    _write(crlf, "a.cfgx", b"one\r\n")
    _write(lf, "a.cfgx", b"one\n")
    assert hash_file_manifest(crlf, ["a.cfgx"], [".cfgx"]) == hash_file_manifest(
        lf, ["a.cfgx"], [".cfgx"]
    )
    assert hash_file_manifest(crlf, ["a.cfgx"]) != hash_file_manifest(lf, ["a.cfgx"])


def test_the_digest_declares_the_file_digest_route(tmp_path: Path) -> None:
    _write(tmp_path, "a.py", b"x = 1\n")
    require_route(hash_file_manifest(tmp_path, ["a.py"]), ROUTE_FILE_DIGEST)


def test_a_fixed_tree_hashes_to_a_pinned_value(tmp_path: Path) -> None:
    _write(tmp_path, "a/b.py", b"print(\"hi\")\r\n")
    _write(tmp_path, "bin.dat", b"\x00\x01\x02")
    entries = build_file_manifest(tmp_path, ["bin.dat", "a\\b.py"])
    assert [entry.model_dump(mode="python") for entry in entries] == [
        {
            "path": "a/b.py",
            "sha256": "0ca9091eb4e31fb1ab24c8c5de92a08e4e5f402919f82ea3ca784f38534f03f3",
            "mode": "text",
        },
        {
            "path": "bin.dat",
            "sha256": "ae4b3280e56e2faf83f414a6e3dabe9d5fbe18976544c05fed121accb85b53fc",
            "mode": "binary",
        },
    ]
    assert (
        hash_file_manifest(tmp_path, ["bin.dat", "a\\b.py"]).sha256
        == "f12c23038d39e83f502238683f1d63c6d613b45529d56c07620f4fd65e54eed9"
    )


@pytest.mark.parametrize(
    "bad",
    ["../escape.py", "a/../../escape.py", "/etc/passwd", "\\etc\\passwd", "./a.py", "a//b.py"],
)
def test_traversal_and_absolute_paths_are_rejected(tmp_path: Path, bad: str) -> None:
    with pytest.raises(ManifestError):
        build_file_manifest(tmp_path, [bad])


@pytest.mark.parametrize("bad", ["C:/x.py", "c:x.py", "Z:\\x.py"])
def test_drive_qualified_paths_are_rejected(tmp_path: Path, bad: str) -> None:
    with pytest.raises(ManifestError, match="must be relative"):
        build_file_manifest(tmp_path, [bad])


def test_a_target_resolving_outside_the_root_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Drives the post-resolve containment check directly: the two link-based tests below
    # both skip without link-creation privileges, leaving this guard otherwise uncovered.
    outside = tmp_path / "outside"
    outside.mkdir()
    secret = outside / "secret.py"
    secret.write_bytes(b"secret\n")
    root = tmp_path / "root"
    root.mkdir()
    (root / "innocent.py").write_bytes(b"x = 1\n")

    monkeypatch.setattr(file_manifest_module, "_resolve", lambda _target: secret.resolve())
    with pytest.raises(ManifestError, match="escapes the root"):
        build_file_manifest(root, ["innocent.py"])


def test_symlink_escape_is_rejected_before_any_bytes_are_read(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.py").write_bytes(b"secret\n")
    root = tmp_path / "root"
    root.mkdir()
    try:
        (root / "link.py").symlink_to(outside / "secret.py")
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation is unavailable on this platform or account")
    with pytest.raises(ManifestError, match="escapes the root"):
        build_file_manifest(root, ["link.py"])


@pytest.mark.skipif(sys.platform != "win32", reason="directory junctions are Windows-only")
def test_directory_junction_escape_is_rejected(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.py").write_bytes(b"secret\n")
    root = tmp_path / "root"
    root.mkdir()
    made = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(root / "link"), str(outside)],
        capture_output=True,
        check=False,
    )
    if made.returncode != 0:
        pytest.skip("junction creation is unavailable on this account")
    with pytest.raises(ManifestError, match="escapes the root"):
        build_file_manifest(root, ["link/secret.py"])


def test_a_directory_is_a_domain_error_not_an_os_error(tmp_path: Path) -> None:
    (tmp_path / "pkg").mkdir()
    with pytest.raises(ManifestError, match="not a regular file"):
        build_file_manifest(tmp_path, ["pkg"])


def test_a_missing_file_is_rejected_rather_than_skipped(tmp_path: Path) -> None:
    _write(tmp_path, "a.py", b"x = 1\n")
    with pytest.raises(FileNotFoundError, match=r"missing\.py"):
        build_file_manifest(tmp_path, ["a.py", "missing.py"])


def test_duplicate_paths_are_rejected(tmp_path: Path) -> None:
    _write(tmp_path, "a.py", b"x = 1\n")
    with pytest.raises(ManifestError, match="duplicate"):
        build_file_manifest(tmp_path, ["a.py", "a.py"])


@pytest.mark.parametrize("bad", [".PY", "py", "", ".", 7, b".py"])
def test_invalid_text_suffixes_are_rejected(tmp_path: Path, bad: object) -> None:
    with pytest.raises(ManifestError):
        build_file_manifest(tmp_path, [], [bad])  # type: ignore[list-item]


def test_a_bare_string_is_not_a_suffix_collection(tmp_path: Path) -> None:
    with pytest.raises(ManifestError, match="not a string"):
        build_file_manifest(tmp_path, [], ".py")


def test_an_invalid_declared_mode_is_rejected(tmp_path: Path) -> None:
    _write(tmp_path, "a.py", b"x = 1\n")
    with pytest.raises(ManifestError, match="'text' or 'binary'"):
        build_file_manifest(tmp_path, [("a.py", "utf8")])  # type: ignore[list-item]


def test_a_missing_root_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ManifestError, match="does not resolve"):
        build_file_manifest(tmp_path / "nope", [])


def test_a_file_as_root_is_rejected(tmp_path: Path) -> None:
    _write(tmp_path, "a.py", b"x = 1\n")
    with pytest.raises(ManifestError, match="not a directory"):
        build_file_manifest(tmp_path / "a.py", [])


def test_an_empty_path_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ManifestError, match="empty"):
        build_file_manifest(tmp_path, ["   "])


def test_a_non_path_entry_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ManifestError, match="string or PathLike"):
        build_file_manifest(tmp_path, [7])  # type: ignore[list-item]


def test_a_null_byte_in_a_path_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ManifestError, match="null byte"):
        build_file_manifest(tmp_path, ["a\x00.py"])
