"""A scripted walk through every governing mechanism, end to end.

    .venv\\Scripts\\python.exe scripts/demo.py

**This is a demonstration, not a measurement.** The model's replies are fixed,
and the scenario is chosen so each mechanism has something to do. That is the
opposite of what the campaigns found: measured against real models, the tool
governor never denied anything, the loop fuse never fired, and the quality gate
only ever confirmed an answer the agent had already finished. See
`scripts/report.py` for what actually happens, and the disclosures in
`src/outcomefuse/submission/disclosures.py` for why.

What it exists for is the other half of the question. The campaigns show how
*often* a mechanism fires; they cannot show that it works, because on those runs
most of them never ran at all. This drives each one deliberately and seals the
result, so the machinery can be read back from a log rather than described.

Writes a sealed run to runs/demo/, then render it:

    .venv\\Scripts\\python.exe scripts/render_run.py --runs-dir runs/demo
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from outcomefuse.core.contract import load_path
from outcomefuse.core.policy import Ledger, Reserve
from outcomefuse.core.record import RecordStore, RunManifest
from outcomefuse.evidence.store import EvidenceStore
from outcomefuse.ports.tools import ToolCall
from outcomefuse.runtime import Driver, ToolGovernor
from outcomefuse.runtime.baseline import BaselineRecorder
from outcomefuse.workloads import citable_index_for, tool_port_for

SHA = "0" * 64

#: Small on purpose. The real contract allows 70,000 tokens, which no scripted
#: run would ever exhaust, and budget exhaustion is one of the things to show.
DEMO_TOKENS = 4_000
DEMO_COST = 0.50


def manifest(run_id: str, mode: str = "governed") -> RunManifest:
    return RunManifest(
        run_id=run_id,
        mode=mode,
        data_class="synthetic",
        retention_profile="mvp-synthetic-v1",
        contract_hash=SHA,
        rubric_hash=SHA,
        answer_key_hash=SHA,
        verifier_registry_version="v1",
        verifier_registry_hash=SHA,
        coverage_report_hash=SHA,
        baseline_configuration_hash=SHA,
        case_set_id="demo/supply-chain",
        split="calibration",
        model_ids=("gpt-5-mini", "gpt-5"),
        provider_versions={"gpt-5-mini": "scripted", "gpt-5": "scripted"},
        cost_table_version="ct-2",
        route="direct",
        streaming_disabled=True,
        adapter_id="scripted",
        adapter_version="1",
        governor_code_version="0.1.0",
        sqlite_library_version=sqlite3.sqlite_version,
        seed=1,
    )


def build(run_id: str, store: RecordStore, contract, tools, evidence=None) -> Driver:
    driver = Driver(
        run_id=run_id,
        contract=contract,
        store=store,
        ledger=Ledger(
            allocated_tokens=DEMO_TOKENS,
            allocated_cost=DEMO_COST,
            reserve=Reserve(
                max_tokens=DEMO_TOKENS // 10,
                max_estimated_cost=DEMO_COST / 10,
                sizing="declared",
            ),
        ),
        governor=ToolGovernor(contract),
        tools=tools,
        evidence=evidence,
    )
    driver.open_run(manifest(run_id))
    index = citable_index_for(contract)
    if index is not None:
        driver.bind_citable_index(index)
    return driver


def say(step: str, detail: str) -> None:
    print(f"  {step:<26} {detail}")


WRONG = {
    "exception_type": "late-shipment",
    "root_cause_code": "rc-customs-documentation",
    "recommended_action": "accept-and-reschedule",
    "impacted_orders": [5007],
    "est_delay_days": 13,
    "policy_refs": [{"id": "SP-4.1"}],
    "alternatives": ["expedite"],
}
RIGHT = dict(WRONG, exception_type="customs-hold", recommended_action="escalate-to-buyer")
KEY = {
    "exception_type": "customs-hold",
    "root_cause_code": "rc-customs-documentation",
    "recommended_action": "escalate-to-buyer",
}


def last_gate(store: RecordStore, run_id: str) -> tuple[str, list[str]]:
    """The verdict as the log records it, rather than as the driver remembers it."""
    verdict, unmet = "none", []
    for event in store.events(run_id):
        if event.kind == "gate-verdict" and event.gate_verdict:
            verdict = event.gate_verdict
        for name in (event.payload or {}).get("unmet") or []:
            unmet = [*unmet, str(name)] if name not in unmet else unmet
    return verdict, unmet


def governed_walk(runs: Path, contract, tools) -> None:
    """Duplicate denial, a failed gate, escalation, then a pass."""
    print("\n1. THE WHOLE LOOP, WITH THE GOVERNOR DOING SOMETHING AT EVERY TURN")
    path = runs / "walk.db"
    path.unlink(missing_ok=True)
    with RecordStore(path).open() as store:
        driver = build("demo-walk", store, contract, tools)
        say("contract bound", f"{contract.workload} floor, {DEMO_TOKENS} token budget")

        driver.charge_model_turn(step_id="s0", tokens=700, cost=0.02, model_used="gpt-5-mini")
        say("model turn charged", "700 tokens on gpt-5-mini, reserved then settled")

        call = ToolCall(tool="order_lookup", arguments={"po_id": 5007}, step_id="s1")
        verdict = driver.execute_step(call)
        say("tool allowed", f"order_lookup -> {verdict.action} ({verdict.decision_reason})")

        # Byte-identical to the call above, which is what the governor keys on.
        again = driver.execute_step(
            ToolCall(tool="order_lookup", arguments={"po_id": 5007}, step_id="s2")
        )
        say("same call again", f"{again.action} ({again.decision_reason}) - tool never invoked")

        driver.execute_step(
            ToolCall(tool="shipment_trace", arguments={"po_id": 5007}, step_id="s3")
        )
        say("different call", "shipment_trace -> proceed")

        driver.charge_model_turn(step_id="s4", tokens=900, cost=0.03, model_used="gpt-5-mini")
        bad = driver.submit_deliverable(WRONG, answer_key=KEY)
        verdict, unmet = last_gate(store, "demo-walk")
        say("answer submitted", f"gate says {verdict}, unmet {unmet}")
        say("what happened next", f"{bad.action} -> {bad.escalate_to or 'no escalation'}")

        driver.charge_model_turn(step_id="s5", tokens=900, cost=0.05, model_used="gpt-5")
        good = driver.submit_deliverable(RIGHT, answer_key=KEY)
        say("second answer", f"gate says {last_gate(store, 'demo-walk')[0]}, run {good.action}")
        say("terminal reason", str(driver.terminated))
        say("seal", (store.seal("demo-walk") or "")[:32] + "...")


def exhaustion_walk(runs: Path, contract, tools) -> None:
    """The budget runs out, and the run halts rather than overspending."""
    print("\n2. WHAT HAPPENS WHEN THE MONEY RUNS OUT")
    path = runs / "exhausted.db"
    path.unlink(missing_ok=True)
    with RecordStore(path).open() as store:
        driver = build("demo-exhausted", store, contract, tools)
        spent = 0
        for turn in range(1, 12):
            verdict = driver.charge_model_turn(
                step_id=f"t{turn}", tokens=800, cost=0.06, model_used="gpt-5-mini"
            )
            if verdict is not None:
                say("stopped at turn", str(turn))
                say("because", f"{verdict.action} ({verdict.decision_reason})")
                break
            spent += 800
            say(f"turn {turn}", f"800 tokens, {DEMO_TOKENS - spent} left")
        say("terminal reason", str(driver.terminated))
        say("never exceeded", f"{DEMO_TOKENS} token ceiling")
        say("seal", (store.seal("demo-exhausted") or "")[:32] + "...")


def paired_walk(runs: Path, contract, tools) -> None:
    """The same scripted agent, with and without the governor, for compare.py.

    The agent here repeats itself, which is the case the tool governor was built
    for and the case real models never produced: across every campaign, not one
    of their tool calls was an exact repeat.
    """
    print("\n3. THE SAME REPETITIVE AGENT, WITH AND WITHOUT THE GOVERNOR")
    out = runs.parent / "demo-compare" / contract.workload
    (out / "evidence").mkdir(parents=True, exist_ok=True)
    evidence = EvidenceStore(out / "evidence", data_class="synthetic")

    # An agent that looks the same thing up four times. Nothing stops it.
    wasteful = [
        ToolCall(tool="order_lookup", arguments={"po_id": 5007}, step_id=f"s{i}")
        for i in range(4)
    ] + [ToolCall(tool="shipment_trace", arguments={"po_id": 5007}, step_id="s4")]

    path = out / "sc-e-001-baseline.db"
    path.unlink(missing_ok=True)
    with RecordStore(path).open() as store:
        recorder = BaselineRecorder(
            run_id="sc-e-001-baseline",
            contract=contract,
            store=store,
            citable_index=citable_index_for(contract),
            evidence=evidence.for_driver("sc-e-001-baseline"),
        )
        recorder.open_run(manifest("sc-e-001-baseline", mode="baseline"))
        recorder.observe_model_turn(step_id="s0", tokens=700, model_used="gpt-5")
        for call in wasteful:
            recorder.observe_tool(call)
            recorder.observe_model_turn(step_id=call.step_id, tokens=600, model_used="gpt-5")
        recorder.score(RIGHT, answer_key=KEY)
        recorder.seal()
        say("ungoverned", f"{len(wasteful)} tool calls, every one executed")

    path = out / "sc-e-001-governed.db"
    path.unlink(missing_ok=True)
    with RecordStore(path).open() as store:
        driver = build(
            "sc-e-001-governed",
            store,
            contract,
            tools,
            evidence.for_driver("sc-e-001-governed"),
        )
        driver.charge_model_turn(step_id="s0", tokens=700, cost=0.02, model_used="gpt-5-mini")
        served = 0
        for call in wasteful:
            verdict = driver.execute_step(call)
            if verdict.decision_reason == "cache-hit":
                served += 1
            else:
                driver.charge_model_turn(
                    step_id=call.step_id, tokens=600, cost=0.02, model_used="gpt-5-mini"
                )
        driver.submit_deliverable(RIGHT, answer_key=KEY)
        say("governed", f"{served} of {len(wasteful)} served from cache, never executed")
    say("read it back", f"scripts/compare.py --case sc-e-001 --runs-dir {out.parent}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs-dir", default="runs/demo")
    args = parser.parse_args()

    runs = Path(args.runs_dir)
    runs.mkdir(parents=True, exist_ok=True)
    contract = load_path(Path("contracts/supply-chain.contract.yaml"))
    tools = tool_port_for(contract)

    print("SCRIPTED DEMONSTRATION -- the model's replies are fixed.")
    print("It shows the mechanisms work, never how often they fire. Measured")
    print("against real models most of these never fired at all; see report.py.")

    governed_walk(runs, contract, tools)
    exhaustion_walk(runs, contract, tools)
    paired_walk(runs, contract, tools)

    print(f"\nsealed logs in {runs}. Read one back:")
    print(f"  .venv\\Scripts\\python.exe scripts/render_run.py --runs-dir {runs}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
