from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, NamedTuple

import pytest

import outcomefuse
from outcomefuse.core.canon import Digest, hash_file_manifest, hash_structure
from outcomefuse.core.canon.__main__ import MAX_STDIN_BYTES

_SRC = Path(outcomefuse.__file__).resolve().parents[1]


class _Result(NamedTuple):
    returncode: int
    stdout: str
    stderr: str


def _env() -> dict[str, str]:
    env = dict(os.environ)
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = f"{_SRC}{os.pathsep}{existing}" if existing else str(_SRC)
    return env


def _spawn(mode: str, **kwargs: Any) -> _Result:
    completed = subprocess.run(
        [sys.executable, "-m", "outcomefuse.core.canon", mode],
        capture_output=True,
        env=_env(),
        check=False,
        **kwargs,
    )
    # Explicit UTF-8 both ways: text=True would encode stdin with the parent's locale
    # (cp1252 on Windows) while the child decodes strictly as UTF-8.
    return _Result(
        completed.returncode,
        completed.stdout.decode("utf-8"),
        completed.stderr.decode("utf-8", errors="replace"),
    )


def _run(mode: str, stdin: str) -> _Result:
    return _spawn(mode, input=stdin.encode("utf-8"))


def _digest(mode: str, stdin: str) -> Digest:
    result = _run(mode, stdin)
    assert result.returncode == 0, result.stderr
    return Digest.model_validate(json.loads(result.stdout))


@pytest.mark.parametrize(
    "payload",
    ['{"a": 1}', '{"a": 1.0}', '[1, 2, "x"]', '{"b": [true, null], "a": {"z": -0.0}}'],
)
def test_a_separate_process_reproduces_the_in_process_digest(payload: str) -> None:
    assert _digest("structure", payload) == hash_structure(json.loads(payload))


@pytest.mark.parametrize(
    "payload",
    [
        '{"\u043a\u043b\u044e\u0447": "\u0437\u043d\u0430\u0447\u0435\u043d\u0438\u0435"}',
        '{"emoji": "\U0001f600", "\U0001f600": "emoji"}',
        '{"caf\u00e9": ["\u4e2d\u6587", "\u0627\u0644\u0639\u0631\u0628\u064a\u0629"]}',
    ],
)
def test_non_ascii_payloads_survive_the_process_boundary(payload: str) -> None:
    assert _digest("structure", payload) == hash_structure(json.loads(payload))


def test_one_and_one_point_zero_agree_across_processes() -> None:
    assert _digest("structure", '{"a": 1.0}') == _digest("structure", '{"a": 1}')
    assert _digest("structure", '{"a": 1.0}') == hash_structure({"a": 1})


def test_a_tree_hashes_identically_across_processes(tmp_path: Path) -> None:
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "mod.py").write_bytes(b"value = 1\r\n")
    (tmp_path / "blob.bin").write_bytes(b"\x00\x01\x02")

    request = json.dumps({"root": str(tmp_path), "paths": ["pkg\\mod.py", "blob.bin"]})
    assert _digest("file-digest", request) == hash_file_manifest(
        tmp_path, ["pkg/mod.py", "blob.bin"]
    )


def test_custom_text_suffixes_survive_the_process_boundary(tmp_path: Path) -> None:
    (tmp_path / "notes.cfgx").write_bytes(b"one\r\n")
    request = json.dumps(
        {"root": str(tmp_path), "paths": ["notes.cfgx"], "text_suffixes": [".cfgx"]}
    )
    assert _digest("file-digest", request) == hash_file_manifest(
        tmp_path, ["notes.cfgx"], [".cfgx"]
    )
    assert _digest("file-digest", request) != _digest(
        "file-digest", json.dumps({"root": str(tmp_path), "paths": ["notes.cfgx"]})
    )


def test_a_declared_text_mode_survives_the_process_boundary(tmp_path: Path) -> None:
    crlf, lf = tmp_path / "crlf", tmp_path / "lf"
    for root, data in ((crlf, b"FROM scratch\r\n"), (lf, b"FROM scratch\n")):
        root.mkdir()
        (root / "Dockerfile").write_bytes(data)

    def request(root: Path) -> str:
        return json.dumps({"root": str(root), "paths": [["Dockerfile", "text"]]})

    assert _digest("file-digest", request(crlf)) == hash_file_manifest(
        crlf, [("Dockerfile", "text")]
    )
    assert _digest("file-digest", request(crlf)) == _digest("file-digest", request(lf))
    # Without the declaration the extensionless file falls to binary and the two diverge.
    bare = json.dumps({"root": str(crlf), "paths": ["Dockerfile"]})
    assert _digest("file-digest", bare) != _digest("file-digest", request(crlf))


def test_a_malformed_declared_mode_is_rejected(tmp_path: Path) -> None:
    (tmp_path / "Dockerfile").write_bytes(b"FROM scratch\n")
    result = _run(
        "file-digest",
        json.dumps({"root": str(tmp_path), "paths": [["Dockerfile", "utf8"]]}),
    )
    assert result.returncode != 0
    assert "ManifestError" in result.stderr


@pytest.mark.parametrize(
    ("mode", "stdin", "expected"),
    [
        ("structure", "{not json", "JSONDecodeError"),
        ("structure", "", "JSONDecodeError"),
        ("structure", '{"a": 1e400}', "CanonicalisationError"),
        ("file-digest", '["not", "an", "object"]', "ValueError"),
        ("file-digest", '{"paths": []}', "ValueError"),
        ("file-digest", '{"root": ".", "paths": "a.py"}', "ValueError"),
        ("file-digest", '{"root": ".", "paths": [1]}', "ValueError"),
        ("file-digest", '{"root": ".", "paths": [["a.py"]]}', "ValueError"),
        ("file-digest", '{"root": ".", "paths": [["a.py", "text", "x"]]}', "ValueError"),
        ("file-digest", '{"root": ".", "paths": [], "text_suffixes": "x"}', "ValueError"),
        ("file-digest", '{"root": ".", "paths": [], "nope": 1}', "ValueError"),
        ("file-digest", '{"root": ".", "paths": ["../escape"]}', "ManifestError"),
    ],
)
def test_rejections_exit_non_zero_naming_the_error(mode: str, stdin: str, expected: str) -> None:
    result = _run(mode, stdin)
    assert result.returncode != 0
    assert expected in result.stderr
    assert result.stdout == ""


def test_a_missing_manifest_file_is_reported(tmp_path: Path) -> None:
    request = json.dumps({"root": str(tmp_path), "paths": ["absent.py"]})
    result = _run("file-digest", request)
    assert result.returncode != 0
    assert "FileNotFoundError" in result.stderr


def test_an_unknown_mode_is_rejected() -> None:
    result = _run("structure/v2", "{}")
    assert result.returncode != 0
    assert "usage:" in result.stderr


def test_oversized_stdin_is_refused(tmp_path: Path) -> None:
    oversized = tmp_path / "oversized.json"
    oversized.write_bytes(b'"' + b"x" * (MAX_STDIN_BYTES + 16) + b'"')
    # Fed from a file rather than a pipe: the child returns as soon as it has read past
    # the bound, which breaks the pipe under a parent still writing ~1 MiB and turns the
    # assertion into a race with BrokenPipeError.
    with oversized.open("rb") as handle:
        result = _spawn("structure", stdin=handle)
    assert result.returncode != 0
    assert "byte bound" in result.stderr
    assert result.stdout == ""
