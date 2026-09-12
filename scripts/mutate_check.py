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
        "            give_up = arm.finish(None, answer_key=answer_key)",
        "            give_up = Finish()",
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
        "    if missing:\n"
        "        # AD-9: an unobserved provider version is not a blank to fill in later.\n"
        "        # Two arms that guessed differently would be silently incomparable.\n"
        '        raise CampaignError(f"no observed provider version for {missing}")',
        '    plan.provider_versions.update({m: "unknown" for m in missing})',
        "silently filling in an unobserved provider version",
    ),
    (
        "src/outcomefuse/harness/runner.py",
        "        if self._recorder is not None:\n"
        "            self._recorder.score(",
        "        if False:\n"
        "            self._recorder.score(",
        "never gating the baseline arm",
    ),
    (
        "src/outcomefuse/submission/script.py",
        "        undisclosed = sorted(DISCLOSURE_KEYS - {d.key for d in self.disclosures})",
        "        undisclosed = []",
        "letting a frozen-in defect go undisclosed",
    ),
    (
        "src/outcomefuse/harness/attribution.py",
        "        if not self.cut_short:\n"
        "            return AGENT_STOPPED",
        "        if False:\n"
        "            return AGENT_STOPPED",
        "crediting a mechanism that only confirmed an agent that had already stopped",
    ),
    (
        "src/outcomefuse/harness/runner.py",
        "        cut_short=terminal is not None and not finished,",
        "        cut_short=terminal is not None,",
        "calling a confirmed run a shortened one",
    ),
    (
        "src/outcomefuse/harness/campaign.py",
        "        passed = self.battery is not None and self.battery.passed",
        "        passed = True",
        "asserting conformance instead of measuring it",
    ),
    (
        "src/outcomefuse/runtime/driver.py",
        "        escalated = self._escalate(reason=\"gate-fail\")\n"
        "        if escalated is not None:\n"
        "            return escalated",
        "        pass",
        "ignoring the contract's retry-then-escalate directive",
    ),
    (
        "src/outcomefuse/runtime/driver.py",
        "        if self.escalations >= escalation.max_escalations:\n"
        "            return None",
        "        if False:\n"
        "            return None",
        "escalating past the contract's limit",
    ),
    (
        "src/outcomefuse/runtime/driver.py",
        "        if escalation.never_breach_verification_reserve and not (",
        "        if False and not (",
        "escalating into the verification reserve",
    ),
    (
        "src/outcomefuse/harness/runner.py",
        "        seen_prompt, seen_completion = by_model.get(response.model_id, (0, 0))",
        "        seen_prompt, seen_completion = (0, 0)",
        "losing the first model's tokens when a run escalates",
    ),
    (
        "src/outcomefuse/harness/reportability.py",
        "    if a.counter_metric_breaches:",
        "    if False:",
        "publishing a headline whose counter-metric breached its threshold",
    ),
    (
        "src/outcomefuse/submission/script.py",
        "    stopped_early = any(",
        "    stopped_early = True or any(",
        "counting a gate that only confirmed as a sufficiency stop",
    ),
    (
        "src/outcomefuse/submission/script.py",
        '            if show not in EXCUSED_BY or EXCUSED_BY[show] not in filed',
        "            if False",
        "excusing every missing demonstration, not just the disclosed one",
    ),
    (
        "src/outcomefuse/submission/script.py",
        "        if self.disclosures:\n"
        '            lines.append("\\n## Disclosed (§8.2)")',
        "        if False:\n"
        '            lines.append("\\n## Disclosed (§8.2)")',
        "carrying disclosures but never rendering them",
    ),
    (
        "src/outcomefuse/harness/overhead.py",
        "    if study.digest().sha256 not in preregistration.derived_from:",
        "    if False:",
        "accepting targets that cite no measurement",
    ),
    (
        "src/outcomefuse/harness/counters.py",
        "        if self.value is None or self.threshold is None:\n            return False",
        "        if self.value is None:\n            return False",
        "letting an unmeasured metric stand in for a passing one",
    ),
    (
        "src/outcomefuse/harness/counters.py",
        "        return tuple(sorted(r.metric for r in self.measured))",
        "        return tuple(sorted(r.metric for r in self.readings))",
        "reporting a metric nobody measured as reported",
    ),
    (
        "src/outcomefuse/harness/counters.py",
        "    if suppressions_checked:",
        "    if True:",
        "reading a suppression rate of zero from no suppressions",
    ),
    (
        "src/outcomefuse/runtime/driver.py",
        "            escalated = self._escalate(reason=parse_failure or \"no deliverable\")\n"
        "            if escalated is not None:\n"
        "                return escalated",
        "            pass",
        "giving up on a run that produced nothing instead of escalating",
    ),
    (
        "src/outcomefuse/harness/runner.py",
        "                escalations += 1\n"
        "                attempt = 0\n"
        "                parsed = None\n"
        "                continue",
        "                escalations += 1\n"
        "                parsed = None\n"
        "                continue",
        "granting an escalation no turns to use",
    ),
    (
        "src/outcomefuse/harness/runner.py",
        "            give_up = arm.finish(None, answer_key=answer_key)\n"
        "            if give_up.escalate_to is not None:\n"
        "                escalations += 1\n"
        "                attempt = 0\n"
        "                continue",
        "            give_up = arm.finish(None, answer_key=answer_key)\n"
        "            if False:\n"
        "                pass",
        "ignoring an escalation granted after running out of turns",
    ),
]

TESTS = [
    "tests/workloads/test_tool_schemas.py",
    "tests/adapters/test_azure_model_port.py",
    "tests/harness/test_runner.py",
    "tests/harness/test_costs.py",
    "tests/harness/test_answer_keys.py",
    "tests/harness/test_campaign.py",
    "tests/harness/test_attribution.py",
    "tests/harness/test_counters.py",
    "tests/harness/test_preregistration_record.py",
    "tests/runtime/test_escalation.py",
    "tests/submission/test_disclosures.py",
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
