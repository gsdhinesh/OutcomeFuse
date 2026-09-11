"""Run one case end to end against the live deployment. Costs money.

Deliberate, like `smoke_model.py`, and not part of the suite. Everything the
test suite can check has been checked against a scripted model; what it cannot
check is whether a real gpt-5, given the frozen prompt and the contract's tool
schemas, actually calls the tools and returns a deliverable in the shape the
parser expects. That is the question this answers, one case at a time, before
anything is spent on a campaign.

Run with the venv's interpreter, not `uv run` -- a sync removes the openai and
azure-identity packages, which are deliberately not declared (an unresolvable
dependency broke `uv run pytest` repo-wide, and they are imported lazily):

    .venv\\Scripts\\python.exe scripts/run_one_case.py data-sql
    .venv\\Scripts\\python.exe scripts/run_one_case.py data-sql --governed
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

from outcomefuse.adapters.model import AzureFoundryModelPort, ModelPortError
from outcomefuse.core.contract import load_path
from outcomefuse.core.policy import Ledger, Reserve
from outcomefuse.core.record import RecordStore, RunManifest
from outcomefuse.harness.answer_keys import AnswerKeyError, answer_key_for
from outcomefuse.harness.cases import load_case_set
from outcomefuse.harness.costs import CostTableError, load_cost_table
from outcomefuse.harness.runner import BaselineArm, GovernedArm, run_case
from outcomefuse.runtime import Driver, ToolGovernor
from outcomefuse.workloads import citable_index_for, tool_port_for

BASE = "https://outcomefuse-foundry.services.ai.azure.com/openai/v1"
COST_TABLE = "ct-2"
SHA = "0" * 64

# From the frozen baseline definition. Reasoning models reject temperature and
# top_p, so there are none to pin; 4096 output tokens was hazardous -- the model
# exhausts on reasoning, returns HTTP 200 with no text, and bills for it.
MAX_OUTPUT_TOKENS = 25_000
REASONING_EFFORT = "medium"


def build_manifest(run_id: str, workload: str, split: str, model_id: str) -> RunManifest:
    return RunManifest(
        run_id=run_id,
        mode="governed",
        data_class="synthetic",
        retention_profile="mvp-synthetic-v1",
        contract_hash=SHA,
        rubric_hash=SHA,
        answer_key_hash=SHA,
        verifier_registry_version="v1",
        verifier_registry_hash=SHA,
        coverage_report_hash=SHA,
        baseline_configuration_hash=SHA,
        case_set_id=f"{split}/{workload}",
        split=split,
        model_ids=(model_id,),
        provider_versions={model_id: "unknown-until-observed"},
        cost_table_version=COST_TABLE,
        route="direct",
        streaming_disabled=True,
        adapter_id="reference",
        adapter_version="1",
        governor_code_version="0.1.0",
        sqlite_library_version=sqlite3.sqlite_version,
        seed=1,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workload")
    parser.add_argument("--split", default="calibration")
    parser.add_argument("--case", default=None, help="case_id; defaults to the first")
    parser.add_argument("--governed", action="store_true")
    parser.add_argument(
        "--model",
        default=None,
        help="defaults to the contract's start model when governed, gpt-5 for the baseline",
    )
    parser.add_argument("--max-iterations", type=int, default=None)
    parser.add_argument(
        "--preregistration",
        default=None,
        help="required to open the evaluation split; there is no way to unsee it",
    )
    args = parser.parse_args()

    contract = load_path(Path(f"contracts/{args.workload}.contract.yaml"))
    case_set = load_case_set(args.workload, args.split)
    case = case_set.by_id(args.case) if args.case else case_set.cases[0]
    tools = tool_port_for(contract)

    # Without this the gate cannot evaluate, and the run terminates fail-closed
    # under AD-20 -- correctly, but having spent the whole budget first.
    try:
        answer_key = answer_key_for(
            case.case_id,
            args.workload,
            args.split,
            preregistration_hash=args.preregistration,
        )
    except AnswerKeyError as exc:
        print(f"{exc}")
        return 2

    # The governed arm starts where the contract says to start -- gpt-5-mini,
    # escalating only if the gate demands it. The baseline is pinned to gpt-5 by
    # the frozen baseline definition: an ordinary team reaches for the strong
    # model and leaves it there. That difference is the mechanism, not a thumb
    # on the scale, and it is why the arms' model ids may legitimately differ.
    contract_start = contract.models.start if contract.models else "gpt-5"
    model_id = args.model or (contract_start if args.governed else "gpt-5")
    max_iterations = args.max_iterations or contract.budget.max_iterations

    price = None
    try:
        table = load_cost_table(COST_TABLE)
        if table.priced:
            price = lambda m, p, c: table.price(m, prompt_tokens=p, completion_tokens=c)  # noqa: E731
        else:
            print(f"! cost table {COST_TABLE} is unpriced ({', '.join(table.unpriced_models())});")
            print("  this run is metered in tokens only. Cost is not being invented.\n")
    except CostTableError as exc:
        print(f"! {exc}\n")

    store = None
    if args.governed:
        path = Path("runs") / f"{args.workload}-{case.case_id}.db"
        path.parent.mkdir(exist_ok=True)
        path.unlink(missing_ok=True)
        store = RecordStore(path).open()
        driver = Driver(
            run_id=f"{case.case_id}-governed",
            contract=contract,
            store=store,
            ledger=Ledger(
                allocated_tokens=contract.budget.max_tokens,
                allocated_cost=contract.budget.max_estimated_cost,
                reserve=contract.budget.verification_reserve
                or Reserve(
                    max_tokens=contract.budget.max_tokens // 10,
                    max_estimated_cost=contract.budget.max_estimated_cost / 10,
                    sizing="declared",
                ),
            ),
            governor=ToolGovernor(contract),
            tools=tools,
        )
        driver.open_run(build_manifest(driver.run_id, args.workload, args.split, model_id))
        # AD-7: built, hashed and appended before any verifier runs. Without it
        # a citation criterion cannot be evaluated and the run fail-closes,
        # correctly, having spent its whole budget first.
        index = citable_index_for(contract)
        if index is not None:
            digest = driver.bind_citable_index(index)
            print(f"citable   {len(index.entries)} ids, {digest.sha256[:16]}...")
        arm = GovernedArm(driver, start_model=model_id)
    else:
        arm = BaselineArm(tools, model=model_id)

    print(f"case      {case.case_id}  ({case.difficulty}, expects {case.expected_outcome})")
    print(f"arm       {arm.name}")
    print(f"model     {model_id}")
    print(f"ceiling   {contract.budget.max_tokens} tokens, {max_iterations} iterations\n")

    port = AzureFoundryModelPort(base_url=BASE)
    try:
        outcome = run_case(
            case,
            contract=contract,
            arm=arm,
            model=port,
            max_output_tokens=MAX_OUTPUT_TOKENS,
            reasoning_effort=REASONING_EFFORT,
            max_iterations=max_iterations,
            answer_key=answer_key,
            price=price,
        )
    except ModelPortError as exc:
        print(f"the model call failed: {exc}")
        return 1
    finally:
        if store is not None:
            store.close()

    spend = outcome.spend
    print(f"turns             {outcome.iterations}")
    print(f"tool calls        {spend.tool_calls}")
    print(f"prompt tokens     {spend.prompt_tokens}")
    print(f"completion tokens {spend.completion_tokens}")
    share = (
        spend.reasoning_tokens / spend.completion_tokens * 100 if spend.completion_tokens else 0
    )
    print(f"  of which reasoning {spend.reasoning_tokens} ({share:.0f}%)")
    print(f"total tokens      {spend.total_tokens}")
    if outcome.terminal_reason:
        print(f"terminal          {outcome.terminal_reason}")
    if outcome.stopped_by:
        print(f"stopped by        {outcome.stopped_by}")

    print()
    if outcome.parsed is None:
        print("no deliverable was produced")
        return 1
    if not outcome.parsed.ok:
        print(f"the deliverable did not parse: {outcome.parsed.failure}")
        return 1
    print(f"parsed by         {outcome.parsed.found_by}")
    print(json.dumps(outcome.parsed.deliverable, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
