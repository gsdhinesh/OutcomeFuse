"""code-triage tools: `repo_grep`, `read_file`, `symbol_refs`, `run_tests`.

The repo holds unmarked defects and finding them is the task, so these tools
expose the source and nothing more. None of them knows what a defect looks
like, and none reports one.

`run_tests` is declared non-deterministic and side-effecting, which is the
honest description of running a suite: its duration varies and its effect is
observable outside the run. FR33 therefore exempts it from every
optimisation-driven suppression, and the battery proves that by watching it.
"""

from __future__ import annotations

import re
from typing import Any, Final

from ..core.contract import Contract
from .corpus import repo_files
from .toolport import ToolError, WorkloadToolPort, required

CORPUS: Final[str] = "cases/corpora/code-triage/v1"

MAX_MATCHES: Final[int] = 200
MAX_PATTERN: Final[int] = 200


def _files() -> dict[str, str]:
    return repo_files(CORPUS)


def repo_grep(arguments: dict[str, Any]) -> Any:
    pattern = str(required(arguments, "pattern"))
    if len(pattern) > MAX_PATTERN:
        raise ToolError(f"pattern longer than {MAX_PATTERN} characters")
    try:
        # Compiled without DOTALL and matched per line: a pattern that can only
        # ever see one line cannot backtrack across the whole repo.
        compiled = re.compile(pattern)
    except re.error as exc:
        raise ToolError(f"the pattern does not compile: {exc}") from exc

    wanted = arguments.get("path")
    matches: list[dict[str, Any]] = []
    for path, text in _files().items():
        if wanted is not None and not path.startswith(str(wanted)):
            continue
        for number, line in enumerate(text.splitlines(), start=1):
            if compiled.search(line):
                matches.append({"path": path, "line": number, "text": line.rstrip()})
                if len(matches) >= MAX_MATCHES:
                    return {"matches": matches, "truncated": True}
    return {"matches": matches, "truncated": False}


def read_file(arguments: dict[str, Any]) -> Any:
    path = str(required(arguments, "path"))
    files = _files()
    text = files.get(path)
    if text is None:
        raise ToolError(f"no file at {path!r}; the repo holds {sorted(files)}")
    lines = text.splitlines()
    start = max(1, int(arguments.get("start", 1)))
    end = min(len(lines), int(arguments.get("end", len(lines))))
    if start > len(lines):
        raise ToolError(f"{path!r} has {len(lines)} lines; {start} is past the end")
    return {
        "path": path,
        "start": start,
        "end": end,
        "lines": [
            {"line": n, "text": lines[n - 1]} for n in range(start, end + 1)
        ],
    }


def symbol_refs(arguments: dict[str, Any]) -> Any:
    """Every mention of a name, definitions included. Textual, and says so.

    A real index would resolve scope; this does not, and reporting it as
    `references` rather than `resolved_references` is the difference between a
    tool an agent can reason about and one that quietly misleads it.
    """
    symbol = str(required(arguments, "symbol"))
    if not symbol.isidentifier():
        raise ToolError(f"{symbol!r} is not an identifier")
    word = re.compile(rf"\b{re.escape(symbol)}\b")
    found: list[dict[str, Any]] = []
    for path, text in _files().items():
        for number, line in enumerate(text.splitlines(), start=1):
            if word.search(line):
                found.append(
                    {
                        "path": path,
                        "line": number,
                        "text": line.strip(),
                        "is_definition": bool(
                            re.match(rf"\s*(def|class)\s+{re.escape(symbol)}\b", line)
                        ),
                    }
                )
    return {"symbol": symbol, "references": found, "resolution": "textual"}


def run_tests(arguments: dict[str, Any], *, side_effects: list[str]) -> Any:
    """Declared non-deterministic and side-effecting, and left that way.

    The corpus ships no suite, so this reports that rather than inventing a
    pass. An invented pass would be a tool telling the agent its work is done.
    """
    target = str(arguments.get("path", "orderflow"))
    side_effects.append(f"run_tests: {target}")
    return {
        "target": target,
        "status": "no-suite",
        "detail": (
            "the corpus ships source without a test suite; this tool records that "
            "it ran and reports no result to reason from"
        ),
    }


def tool_port(contract: Contract) -> WorkloadToolPort:
    side_effects: list[str] = []
    return WorkloadToolPort(
        contract=contract,
        side_effects=side_effects,
        handlers={
            "repo_grep": repo_grep,
            "read_file": read_file,
            "symbol_refs": symbol_refs,
            "run_tests": lambda a: run_tests(a, side_effects=side_effects),
        },
    )
