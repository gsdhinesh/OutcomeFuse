"""Where the library is wired, for every scenario in the feature report.

The loop itself is **not** here and is not written by this client. It is
`outcomefuse.harness.runner.run_case` — the same loop that drove the recorded
campaign — and the governor plugs into it through the `Arm` seam the library
already defines: `GovernedArm` holds a `Driver`, `BaselineArm` holds nothing.
Swapping one for the other is the whole difference between a governed run and an
ungoverned one, and it is an argument.

Demonstrating a re-implementation would prove something about the
re-implementation. This drives the shipped loop instead.

Everything here runs against the **frozen** supply-chain workload: its contract,
its calibration cases, its derived answer keys, its corpus. Nothing under
`contracts/`, `cases/` or `freeze/` is read except to load it.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from outcomefuse.core.contract import Contract, load_path, load_text
from outcomefuse.core.policy import Ledger, LoopFuse, Reserve
from outcomefuse.core.record import Event, RecordStore, RunManifest, StoreError, open_store
from outcomefuse.core.verify.registry import REGISTRY_VERSION, registry_digest
from outcomefuse.evidence.store import EvidenceStore
from outcomefuse.harness.answer_keys import answer_key_for
from outcomefuse.harness.cases import Case, load_case_set
from outcomefuse.harness.runner import BaselineArm, GovernedArm, Outcome, run_case
from outcomefuse.ports import ApprovalPort, Decision, ScriptedApprovalPort, ScriptedModelPort
from outcomefuse.runtime import Driver, ToolGovernor
from outcomefuse.runtime.baseline import BaselineRecorder
from outcomefuse.workloads import citable_index_for, tool_port_for
from outcomefuse.workloads.toolport import WorkloadToolPort

WORKLOADS = ("supply-chain", "data-sql", "code-triage", "doc-research")
WORKLOAD = "supply-chain"
SPLIT = "calibration"


def contract_path(workload: str = WORKLOAD) -> Path:
    return Path("contracts") / f"{workload}.contract.yaml"


#: Kept for the feature report, which is about one workload on purpose.
CONTRACT_PATH = contract_path()

#: This client has no rubric, coverage report or baseline definition of its own,
#: so the manifest fields that would carry their digests carry nothing. Zeros are
#: the honest option: a hash over an artefact that does not exist would make the
#: manifest look more evidential than the run is.
ABSENT = "0" * 64

MAX_OUTPUT_TOKENS = 25_000


def contract(workload: str = WORKLOAD) -> Contract:
    return load_path(contract_path(workload))


def variant(
    mutate: Callable[[dict[str, Any]], None], workload: str = WORKLOAD
) -> Contract:
    """A contract that is *not* the frozen one, and is validated like one.

    Some mechanisms only fire under a configuration the frozen contract does not
    use — a budget small enough to exhaust, a gate directed at a human. Editing
    `contracts/` to show them is forbidden and would be dishonest anyway, so the
    variant is built in memory and every scenario that uses one says so.
    """
    raw = yaml.safe_load(contract_path(workload).read_text(encoding="utf-8"))
    mutate(raw)
    return load_text(yaml.safe_dump(raw, sort_keys=False))


def cases(workload: str = WORKLOAD) -> tuple[Case, ...]:
    return load_case_set(workload, SPLIT).cases


def case(case_id: str, workload: str = WORKLOAD) -> Case:
    return load_case_set(workload, SPLIT).by_id(case_id)


def key_for(case_id: str, workload: str = WORKLOAD) -> dict[str, Any]:
    return answer_key_for(case_id, workload, SPLIT)


def manifest(run_id: str, *, mode: str, spec: Contract, models: tuple[str, ...]) -> RunManifest:
    return RunManifest(
        run_id=run_id,
        mode=mode,
        data_class="synthetic",
        retention_profile="mvp-synthetic-v1",
        contract_hash=spec.digest().sha256,
        rubric_hash=ABSENT,
        answer_key_hash=ABSENT,
        verifier_registry_version=REGISTRY_VERSION,
        verifier_registry_hash=registry_digest().sha256,
        coverage_report_hash=ABSENT,
        baseline_configuration_hash=ABSENT,
        case_set_id=f"{SPLIT}/{spec.workload}",
        split=SPLIT,
        model_ids=models,
        provider_versions=dict.fromkeys(models, "scripted"),
        cost_table_version="unpriced",
        route="direct",
        streaming_disabled=True,
        adapter_id="feature-report",
        adapter_version="1",
        governor_code_version="0.1.0",
        sqlite_library_version=sqlite3.sqlite_version,
        seed=1,
    )


def ledger_for(spec: Contract) -> Ledger:
    declared = spec.budget.verification_reserve
    reserve = (
        Reserve(
            max_tokens=declared.max_tokens,
            max_estimated_cost=declared.max_estimated_cost,
            sizing="declared",
        )
        if declared is not None
        else Reserve(
            max_tokens=spec.budget.max_tokens // 10,
            max_estimated_cost=spec.budget.max_estimated_cost / 10,
            sizing="derived",
        )
    )
    return Ledger(
        allocated_tokens=spec.budget.max_tokens,
        allocated_cost=spec.budget.max_estimated_cost,
        reserve=reserve,
    )


@dataclass
class Run:
    """One completed run, and everything a scenario may assert against."""

    run_id: str
    outcome: Outcome
    events: list[Event] = field(default_factory=list)
    seal: str = ""
    verified: bool = False
    #: The tool port's own record, kept apart from the log on purpose (AD-15).
    invoked: tuple[str, ...] = ()
    side_effects: tuple[str, ...] = ()
    terminated: str | None = None
    escalations: int = 0
    quality_state: str = "not-evaluated"
    #: The answer it handed over, read back from the evidence sidecar. None where
    #: the run ended before producing one.
    deliverable: dict[str, Any] | None = None

    def actions(self, action: str) -> list[Event]:
        return [e for e in self.events if e.policy_action == action]

    def reasons(self) -> list[str]:
        return [e.decision_reason for e in self.events if e.decision_reason]


def _read_back(path: Path, run_id: str) -> tuple[list[Event], str, bool]:
    """Reopen the sealed log. A scenario asserts against the record, not memory."""
    with open_store(path, writer=False) as store:
        events = store.events(run_id)
        seal = store.seal(run_id) or ""
        try:
            store.verify_run(run_id)
            verified = True
        except (StoreError, ValueError):
            verified = False
    return events, seal, verified


def _read_deliverable(runs_dir: Path, run_id: str) -> dict[str, Any] | None:
    """The answer the run handed over, from the sidecar it was written to.

    Read back rather than kept, for the same reason the events are: what the
    run meant to produce and what it durably produced are two different claims,
    and only the second one is evidence. A run that never got that far has none.
    """
    path = runs_dir / "evidence" / run_id / "deliverable.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


Sink = Callable[[Event], None]


class TeeStore(RecordStore):
    """Hands each event to an observer *after* it is durably written.

    The order matters. Emitting first would let a watcher see a decision the log
    does not contain, which is the one thing FR5 exists to prevent — and a live
    view that can show a step the record cannot is worse than no live view.

    It observes and governs nothing: the sink cannot refuse, delay or alter an
    event, and an exception from it is swallowed rather than allowed to unwind
    into the run it is only watching.
    """

    def __init__(self, path: Path | str, *, sink: Sink) -> None:
        super().__init__(path)
        self._sink = sink
        #: A watcher that raised. Kept rather than discarded, so a broken view is
        #: visible afterwards instead of looking like a run that emitted nothing.
        self.sink_errors: list[str] = []

    def append(self, event: Event) -> str:
        digest = super().append(event)
        try:
            self._sink(event)
        except Exception as exc:  # noqa: BLE001 - a watcher may never break a run
            self.sink_errors.append(f"{type(exc).__name__}: {exc}")
        return digest


#: Run ids with a log currently open. A run id names one run, and two runs
#: sharing one would share a database file: on Windows the second cannot open it
#: while the first holds it, and on POSIX the unlink below silently deletes the
#: first run's log out from under it. The second is the worse failure because
#: nothing reports it, so both are refused here rather than left to the
#: filesystem to notice or not.
_LIVE: set[str] = set()
_LIVE_LOCK = threading.Lock()


def _claim(run_id: str) -> None:
    with _LIVE_LOCK:
        if run_id in _LIVE:
            raise RuntimeError(
                f"run id {run_id!r} is already in flight: its log is still open. "
                "Two runs are two runs \u2014 give the second one its own id."
            )
        _LIVE.add(run_id)


def _release(run_id: str) -> None:
    with _LIVE_LOCK:
        _LIVE.discard(run_id)


def _store(runs_dir: Path, run_id: str, sink: Sink | None = None) -> tuple[RecordStore, Path]:
    runs_dir.mkdir(parents=True, exist_ok=True)
    _claim(run_id)
    path = runs_dir / f"{run_id}.db"
    try:
        path.unlink(missing_ok=True)
        store = TeeStore(path, sink=sink) if sink is not None else RecordStore(path)
        return store.open(), path
    except Exception:
        _release(run_id)
        raise


def governed(
    subject: Case,
    *,
    turns: list[Any],
    runs_dir: Path,
    spec: Contract | None = None,
    approval: Decision | ApprovalPort | None = "approved",
    with_fuse: bool = True,
    tag: str = "governed",
    answer_key: dict[str, Any] | None = None,
    sink: Sink | None = None,
) -> Run:
    """OutcomeFuse plugged in: the loop's `Arm` is a `GovernedArm` over a Driver."""
    spec = spec or contract()
    run_id = f"{subject.case_id}-{tag}"
    tools = tool_port_for(spec)
    store, path = _store(runs_dir, run_id, sink)
    start = spec.models.start if spec.models else "gpt-5-mini"
    eligible = tuple(spec.models.eligible) if spec.models else (start,)
    try:
        evidence = EvidenceStore(runs_dir / "evidence", data_class="synthetic")
        driver = Driver(
            run_id=run_id,
            contract=spec,
            store=store,
            ledger=ledger_for(spec),
            governor=ToolGovernor(spec, approval=_approval_port(approval)),
            tools=tools,
            fuse=LoopFuse(max_iterations=spec.budget.max_iterations) if with_fuse else None,
            evidence=evidence.for_driver(run_id),
        )
        driver.open_run(manifest(run_id, mode="governed", spec=spec, models=eligible))
        index = citable_index_for(spec)
        if index is not None:
            driver.bind_citable_index(index)
        outcome = run_case(
            subject,
            contract=spec,
            arm=GovernedArm(driver, start_model=start),
            model=ScriptedModelPort(turns=list(turns)),
            max_output_tokens=MAX_OUTPUT_TOKENS,
            reasoning_effort=None,
            answer_key=answer_key
            if answer_key is not None
            else key_for(subject.case_id, spec.workload),
            max_iterations=spec.budget.max_iterations,
        )
        terminated, quality = driver.terminated, driver.quality_state
    finally:
        store.close()
        _release(run_id)

    events, seal, verified = _read_back(path, run_id)
    return Run(
        run_id=run_id,
        outcome=outcome,
        events=events,
        seal=seal,
        verified=verified,
        invoked=tuple(c.tool for c in tools.invocations),
        side_effects=tuple(tools.side_effects),
        terminated=terminated,
        escalations=outcome.escalations,
        quality_state=quality,
        deliverable=_read_deliverable(runs_dir, run_id),
    )


def ungoverned(
    subject: Case,
    *,
    turns: list[Any],
    runs_dir: Path,
    spec: Contract | None = None,
    tag: str = "baseline",
    answer_key: dict[str, Any] | None = None,
    sink: Sink | None = None,
) -> Run:
    """OutcomeFuse plugged out: the same loop, with a `BaselineArm`.

    The recorder is still here, and that is not a contradiction: recording is
    measurement, not governance. It decides nothing, denies nothing and holds no
    budget. Without it the arm produces an answer nobody could check.
    """
    spec = spec or contract()
    run_id = f"{subject.case_id}-{tag}"
    tools = tool_port_for(spec)
    store, path = _store(runs_dir, run_id, sink)
    # Nothing routes an ungoverned loop, so it sits on the strong model.
    model = spec.models.eligible[-1] if spec.models else "gpt-5"
    raised: Exception | None = None
    outcome = None
    quality = "not-evaluated"
    try:
        evidence = EvidenceStore(runs_dir / "evidence", data_class="synthetic")
        recorder = BaselineRecorder(
            run_id=run_id,
            contract=spec,
            store=store,
            citable_index=citable_index_for(spec),
            evidence=evidence.for_driver(run_id),
        )
        recorder.open_run(manifest(run_id, mode="baseline", spec=spec, models=(model,)))
        outcome = run_case(
            subject,
            contract=spec,
            arm=BaselineArm(tools, model=model, recorder=recorder),
            model=ScriptedModelPort(turns=list(turns)),
            max_output_tokens=MAX_OUTPUT_TOKENS,
            reasoning_effort=None,
            answer_key=answer_key
            if answer_key is not None
            else key_for(subject.case_id, spec.workload),
            max_iterations=spec.budget.max_iterations,
        )
        quality = recorder.verdict.verdict if recorder.verdict else "not-evaluated"
    except Exception as exc:  # noqa: BLE001 - re-raised below, never swallowed
        raised = exc
    finally:
        store.close()
        _release(run_id)

    events, seal, verified = _read_back(path, run_id)
    if raised is not None:
        # `BaselineRecorder` appends the reason and closes before it re-raises,
        # so the log is complete, chained and sealable even though there is no
        # `Outcome` to return. Dropping it here is what made the console say
        # there was nothing to seal, which is the opposite of what happened.
        raised.sealed = {  # type: ignore[attr-defined]
            "run_id": run_id,
            "events": len(events),
            "seal": seal,
            "verified": verified,
            "why": next(
                (
                    str(e.payload.get("gate_unavailable"))
                    for e in events
                    if (e.payload or {}).get("gate_unavailable")
                ),
                "",
            ),
        }
        raise raised
    return Run(
        run_id=run_id,
        outcome=outcome,
        events=events,
        seal=seal,
        verified=verified,
        invoked=tuple(c.tool for c in tools.invocations),
        side_effects=tuple(tools.side_effects),
        quality_state=quality,
        deliverable=_read_deliverable(runs_dir, run_id),
    )


def port_and_index(spec: Contract | None = None) -> tuple[WorkloadToolPort, Any]:
    """The workload's tools and citable index, for mechanism-level scenarios."""
    spec = spec or contract()
    return tool_port_for(spec), citable_index_for(spec)


def _approval_port(approval: Decision | ApprovalPort | None) -> ApprovalPort | None:
    """A canned decision or a real channel. `None` means there is no channel at
    all, which FR89 treats as fail-closed rather than as permission."""
    if approval is None:
        return None
    if isinstance(approval, str):
        return ScriptedApprovalPort(default=approval)
    return approval
