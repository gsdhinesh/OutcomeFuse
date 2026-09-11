"""Run the calibration overhead study and print it.

    uv run python -m outcomefuse.harness.overhead_study

Measures the governed path against the same work with no governor in the call
path, and reports the distribution. It sets no targets: FR66's thresholds are a
judgement made from these numbers by a person, not read off them by a script.
"""

from __future__ import annotations

import argparse
import sqlite3
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from ..core.contract import load_text
from ..core.policy import Ledger, Reserve
from ..core.record import Event, RunManifest, open_store
from ..ports import ProbedToolPort, ScriptedApprovalPort, ToolCall
from ..runtime import Driver, ToolGovernor
from .overhead import DEFAULT_REPEATS, Latencies, OverheadStudy, build_study, measure, save_study

SHA = "0" * 64

CONTRACT = """
contract_id: ofc-overhead
version: 1
workload: data-sql
task_goal: Measure the governor's own cost.
deliverable:
  structure:
    answer: string
criteria:
  mandatory:
    - id: answer-matches-key
      classification: E
      verifier:
        type: exact-match-against-answer-key
        args: { path: $.answer, key: answer }
budget:
  max_tokens: 100000000
  max_estimated_cost: 1000.0
  max_tool_calls: 100000
  max_iterations: 100000
tools:
  - name: search
    deterministic: true
    side_effecting: false
"""


def _manifest() -> RunManifest:
    return RunManifest(
        run_id="overhead",
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
        case_set_id="calibration/data-sql",
        split="calibration",
        model_ids=("scripted",),
        provider_versions={"scripted": "0"},
        cost_table_version="ct-1",
        route="direct",
        streaming_disabled=True,
        adapter_id="reference",
        adapter_version="1",
        governor_code_version="0.1.0",
        sqlite_library_version=sqlite3.sqlite_version,
        seed=1,
    )


def _measure_append(repeats: int) -> Latencies:
    """The decision log's own cost, isolated from everything it is logging."""
    with tempfile.TemporaryDirectory() as tmp:
        store = open_store(Path(tmp) / "append.db")
        try:
            store.open_run(_manifest(), recorded_at="2026-09-10T00:00:00Z")
            return measure(
                lambda n: store.append(
                    Event(
                        run_id="overhead",
                        seq=n + 1,
                        kind="decision-proposed",
                        recorded_at="2026-09-10T00:00:00Z",
                    )
                ),
                repeats=repeats,
            )
        finally:
            store.close()


def run(repeats: int = DEFAULT_REPEATS, *, write_to: Path | None = None) -> OverheadStudy:
    contract = load_text(CONTRACT)
    tokens_per_step = 10

    # FR52: the baseline shares no governor code, so it is the tool port alone.
    baseline_tools = ProbedToolPort({"search": lambda c: "found"})
    baseline = measure(
        lambda n: baseline_tools.invoke(
            ToolCall(tool="search", arguments={"q": n}, step_id=f"b{n}")
        ),
        repeats=repeats,
    )

    with tempfile.TemporaryDirectory() as tmp:
        store = open_store(Path(tmp) / "overhead.db")
        try:
            ledger = Ledger(
                allocated_tokens=100_000_000,
                allocated_cost=1000.0,
                reserve=Reserve(max_tokens=1, max_estimated_cost=0.01, sizing="declared"),
            )
            driver = Driver(
                run_id="overhead",
                contract=contract,
                store=store,
                ledger=ledger,
                governor=ToolGovernor(contract, ScriptedApprovalPort(default="approved")),
                tools=ProbedToolPort({"search": lambda c: "found"}),
            )
            driver.open_run(_manifest())
            governed = measure(
                lambda n: driver.execute_step(
                    ToolCall(tool="search", arguments={"q": n}, step_id=f"g{n}"),
                    estimated_tokens=tokens_per_step,
                ),
                repeats=repeats,
            )
            overhead_tokens = ledger.overhead_tokens()
            governed_tokens = ledger.spent_tokens
            # Derived from what the run actually appended, not from the
            # canonical order — the driver emits a subset of it.
            events_per_decision = (len(store.events("overhead")) - 1) // repeats
        finally:
            store.close()

    study = build_study(
        recorded_at=datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        workload="data-sql",
        governed=governed,
        baseline=baseline,
        governor_overhead_tokens=overhead_tokens,
        governed_tokens=governed_tokens,
        events_per_decision=events_per_decision,
        durable_write_p50_ns=_measure_append(repeats).p50_ns,
        enabled_mechanisms=("tool-governor", "quality-gate"),
    )
    print(study.render())
    if write_to is not None:
        # The digest covers the measured latencies, so re-running produces a
        # different one. A preregistration cites a study by content, so the
        # study has to be an artifact rather than something recomputed.
        save_study(study, write_to)
        print(f"\nwritten to {write_to}")
    return study


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repeats", type=int, default=DEFAULT_REPEATS)
    parser.add_argument(
        "--write", default=None, help="save the study for a preregistration to cite"
    )
    args = parser.parse_args()
    run(args.repeats, write_to=Path(args.write) if args.write else None)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
