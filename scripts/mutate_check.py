"""Mutation check: break the code on purpose, confirm a test notices.

Not part of the suite. Run deliberately, on a clean tree, to find out whether a
test would actually catch the bug it claims to guard against. A test that
passes under its own mutation is decoration.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

#: `sql_query` and `sql_execute_write` declare identical parameters, so the
#: anchor has to reach the next tool's name to hit only the first of them.
_SQL_QUERY_ARGS = (
    'parameters=_object({"sql": _STRING}, ["sql"]),\n'
    "        ),\n"
    "        ToolSchema(\n"
    '            name="sql_execute_write"'
)

#: (file, find, replace, what it should break)
MUTATIONS = [
    (
        "src/outcomefuse/workloads/schemas.py",
        _SQL_QUERY_ARGS,
        _SQL_QUERY_ARGS.replace('"sql": _STRING}, ["sql"]', '"query": _STRING}, ["query"]'),
        "a schema argument name that disagrees with its handler",
    ),
    (
        "src/outcomefuse/workloads/schemas.py",
        'parameters=_object({"doc_id": _STRING, "query": _STRING}, ["doc_id", "query"]),',
        'parameters=_object({"doc_id": _STRING, "query": _STRING}),',
        "a mandatory argument not marked required",
    ),
    (
        "src/outcomefuse/workloads/schemas.py",
        "return tuple(SCHEMAS[tool.name] for tool in contract.tools)",
        "return tuple(SCHEMAS.values())",
        "offering every tool regardless of the contract",
    ),
    (
        "src/outcomefuse/adapters/model/azure_foundry.py",
        'arguments, malformed = {}, f"arguments are a JSON {type(arguments).__name__}"',
        "pass",
        "accepting a JSON array as a set of named arguments",
    ),
    (
        "src/outcomefuse/adapters/model/azure_foundry.py",
        '"messages": [_wire(message) for message in request.messages],',
        '"messages": [_wire(request.messages[-1])],',
        "sending only the last turn instead of the transcript",
    ),
    (
        "src/outcomefuse/adapters/model/azure_foundry.py",
        "if request.tools:",
        "if False:",
        "never offering the tools at all",
    ),
    # --- the runner: the arms must stay identical everywhere but the tool call
    (
        "src/outcomefuse/harness/runner.py",
        "    tools: tuple[ToolSchema, ...] = schemas_for(contract)",
        "    tools = () if arm.name == 'baseline' else schemas_for(contract)",
        "withholding tools from one arm",
    ),
    (
        "src/outcomefuse/harness/runner.py",
        "                reasoning_effort=reasoning_effort,",
        "                reasoning_effort=(\n"
        "                    'high' if arm.name == 'governed' else reasoning_effort\n"
        "                ),",
        "giving one arm different sampling parameters",
    ),
    (
        "src/outcomefuse/harness/runner.py",
        "                messages=tuple(messages),",
        "                messages=(messages[0], messages[-1]),",
        "dropping the transcript instead of carrying it forward",
    ),
    (
        "src/outcomefuse/harness/runner.py",
        "            if response.incomplete and not response.text.strip():",
        "            if False:",
        "scoring an exhausted output budget as a wrong answer",
    ),
    (
        "src/outcomefuse/harness/runner.py",
        "        spend = spend.plus_turn(\n"
        "            response.prompt_tokens, response.completion_tokens, "
        "response.reasoning_tokens\n"
        "        )",
        "        spend = spend.plus_turn(\n"
        "            response.prompt_tokens,\n"
        "            response.completion_tokens + response.reasoning_tokens,\n"
        "            response.reasoning_tokens,\n"
        "        )",
        "counting reasoning tokens twice",
    ),
    (
        "src/outcomefuse/harness/costs.py",
        "        if not rate.known:",
        "        if False:",
        "pricing an unknown rate at zero",
    ),
    (
        "src/outcomefuse/runtime/driver.py",
        "        if not self.ledger.can_afford(tokens, cost):",
        "        if False:",
        "spending a model turn the budget cannot afford",
    ),
    (
        "src/outcomefuse/runtime/driver.py",
        "            self.ledger.release_unspent(hold_id)",
        "            pass",
        "leaking the budget reserved for a tool that then failed",
    ),
    (
        "src/outcomefuse/harness/runner.py",
        "    if verdict.failed:",
        "    if False:",
        "reporting a broken tool to the agent as a refusal",
    ),
    (
        "src/outcomefuse/harness/answer_keys.py",
        "    if split == SEALED_SPLIT and not preregistration_hash:",
        "    if False:",
        "opening the evaluation split with no preregistration",
    ),
    (
        "src/outcomefuse/harness/runner.py",
        "        verdict = self._driver.observe_progress(\n"
        "            task_state=task_state, evidence_count=evidence_count\n"
        "        )\n"
        "        return verdict.terminal_reason if verdict is not None else None",
        "        return None",
        "never consulting the loop fuse",
    ),
    (
        "src/outcomefuse/harness/runner.py",
        "    if not finished and terminal is None:",
        "    if False:",
        "leaving a run open when the loop gives up",
    ),
    (
        "src/outcomefuse/harness/campaign.py",
        "        model_ids=eligible,",
        "        model_ids=(\n"
        "            (_governed_model(plan),) if mode == 'governed'\n"
        "            else (plan.baseline_model,)\n"
        "        ),",
        "declaring only the model each arm started on",
    ),
    (
        "src/outcomefuse/harness/campaign.py",
        "        if missing:",
        "        if False:",
        "blanking an unobserved provider version",
    ),
    (
        "src/outcomefuse/harness/runner.py",
        "        if self._recorder is not None:\n"
        "            self._recorder.score(",
        "        if False:\n"
        "            self._recorder.score(",
        "never gating the baseline arm",
    ),
]

TESTS = [
    "tests/workloads/test_tool_schemas.py",
    "tests/adapters/test_azure_model_port.py",
    "tests/harness/test_runner.py",
    "tests/harness/test_costs.py",
    "tests/harness/test_answer_keys.py",
    "tests/harness/test_campaign.py",
]


def main() -> int:
    # Only the files about to be rewritten need to be clean. Requiring the whole
    # tree to be clean would make this unrunnable while writing the very tests
    # it exists to check.
    targets = sorted({path for path, *_ in MUTATIONS})
    git = shutil.which("git")
    if git is None:
        print("git is not on PATH")
        return 2
    # Arguments are literal constants declared above; nothing here is user input.
    dirty = subprocess.run(  # noqa: S603
        [git, "status", "--porcelain", "--", *targets],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    if dirty:
        print(f"refusing to mutate uncommitted files; commit or stash first:\n{dirty}")
        return 2

    survivors = []
    for path, find, replace, description in MUTATIONS:
        file = Path(path)
        original = file.read_text(encoding="utf-8")
        if find not in original:
            print(f"SKIP  {description}\n      (pattern not found in {path})")
            survivors.append(description)
            continue
        file.write_text(original.replace(find, replace, 1), encoding="utf-8")
        try:
            result = subprocess.run(  # noqa: S603
                [sys.executable, "-m", "pytest", "-q", *TESTS], capture_output=True, text=True
            )
        finally:
            file.write_text(original, encoding="utf-8")

        if result.returncode == 0:
            print(f"SURVIVED  {description}")
            survivors.append(description)
        else:
            tail = result.stdout.strip().splitlines()[-1]
            print(f"caught    {description}\n          {tail}")

    print()
    if survivors:
        print(f"{len(survivors)} mutation(s) survived. Those tests do not defend what they claim.")
        return 1
    print(f"All {len(MUTATIONS)} mutations were caught.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
