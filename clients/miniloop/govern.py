"""The only file in this client that knows OutcomeFuse exists.

Two implementations of `loop.Site`. `Governed` holds a `Driver`; `Ungoverned`
holds nothing and calls the tool executor directly. That asymmetry is the
integration: FR52's control arm has no governor to switch off, so the honest
comparison is against a loop with no governance in it rather than against a
governor configured to permit everything.

Everything runs against the **frozen** supply-chain workload — its contract, its
calibration cases, its derived answer keys, its corpus. Nothing under
`contracts/`, `cases/` or `freeze/` is read except to load it.

What `Ungoverned` reports is as much the point as what `Governed` reports. It
cannot name a terminal reason, cannot name a gate verdict, and has no log to
verify — not because this client declined to write them, but because there is
nothing in an ungoverned loop that knows them.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from miniloop.loop import CACHED, DENIED, FAILED, RAN, Finish, Reply, Trace
from outcomefuse.core.contract import Contract, load_path
from outcomefuse.core.policy import Ledger, LoopFuse, Reserve
from outcomefuse.core.record import RecordStore, RunManifest, StoreError, open_store
from outcomefuse.core.verify.registry import REGISTRY_VERSION, registry_digest
from outcomefuse.evidence.store import EvidenceStore
from outcomefuse.harness.answer_keys import answer_key_for
from outcomefuse.harness.cases import Case, load_case_set
from outcomefuse.ports import ApprovalPort, Decision, ScriptedApprovalPort, ToolCall
from outcomefuse.runtime import ContextGovernor, Driver, ToolGovernor
from outcomefuse.workloads import citable_index_for, tool_port_for
from outcomefuse.workloads.toolport import ToolError, WorkloadToolPort

WORKLOAD = "supply-chain"
SPLIT = "calibration"
ROOT = Path(__file__).resolve().parents[2]

#: This client has no rubric, coverage report or baseline definition of its own,
#: so the manifest fields that would carry their digests carry nothing. A hash
#: over an artefact that does not exist would make the manifest look more
#: evidential than the run is.
ABSENT = "0" * 64

NOT_EVALUATED = "not-evaluated"


def contract() -> Contract:
    return load_path(ROOT / "contracts" / f"{WORKLOAD}.contract.yaml")


def cases() -> tuple[Case, ...]:
    return load_case_set(WORKLOAD, SPLIT).cases


def case(case_id: str) -> Case:
    return load_case_set(WORKLOAD, SPLIT).by_id(case_id)


def answer_key(case_id: str) -> dict[str, Any]:
    return answer_key_for(case_id, WORKLOAD, SPLIT)


@dataclass(frozen=True)
class Summary:
    """What each arm can say about itself once the run is over."""

    arm: str
    run_id: str
    #: Model tokens the host metered. The governed arm charged them through a
    #: ledger that could refuse; the ungoverned arm merely counted them.
    tokens: int
    metered: bool
    executed: int
    suppressed: int
    side_effects: tuple[str, ...]
    terminal: str | None
    gate: str
    escalations: int
    #: `None` where no log exists, which is the ungoverned arm's whole position.
    events: int | None = None
    sealed: bool = False
    verified: bool = False


# --------------------------------------------------------------- the governed arm


class Governed:
    """`loop.Site` over a `Driver`. INTEGRATION.md §5b-§5e, executed."""

    name = "governed"

    def __init__(
        self,
        subject: Case,
        *,
        runs_dir: Path,
        spec: Contract | None = None,
        approval: Decision | ApprovalPort = "approved",
        tag: str = "governed",
    ) -> None:
        self.case = subject
        self.spec = spec or contract()
        self.run_id = f"{subject.case_id}-{tag}"
        self.key = answer_key(subject.case_id)
        self.tools = tool_port_for(self.spec)

        runs_dir.mkdir(parents=True, exist_ok=True)
        self._path = runs_dir / f"{self.run_id}.db"
        self._store = RecordStore(self._path).open()
        evidence = EvidenceStore(runs_dir / "evidence", data_class="synthetic")

        self.driver = Driver(
            run_id=self.run_id,
            contract=self.spec,
            store=self._store,
            ledger=_ledger(self.spec),
            governor=ToolGovernor(self.spec, approval=_approval(approval)),
            tools=self.tools,
            fuse=LoopFuse(max_iterations=self.spec.budget.max_iterations),
            context=ContextGovernor(self.spec),
            evidence=evidence.for_driver(self.run_id),
        )
        try:
            self.driver.open_run(_manifest(self.run_id, spec=self.spec))

            # AD-7: bound before any verifier runs, or two implementations
            # deriving it differently would reach different verdicts for one run.
            index = citable_index_for(self.spec)
            if index is not None:
                self.driver.bind_citable_index(index)
        except BaseException:
            # The store is open by now. `open_run` refuses a run id that already
            # exists, and leaving the connection behind on that path turns a
            # clear refusal into an unclosed-database warning three tests later.
            self._store.close()
            raise

    # ------------------------------------------------------------ the four calls

    def charge(self, *, step_id: str, tokens: int, cost: float, model: str) -> str | None:
        stop = self.driver.charge_model_turn(
            step_id=step_id, tokens=tokens, cost=cost, model_used=model
        )
        return stop.terminal_reason if stop is not None else None

    def call(self, *, step_id: str, tool: str, arguments: dict[str, Any]) -> Reply:
        verdict = self.driver.execute_step(
            ToolCall(tool=tool, arguments=arguments, step_id=step_id)
        )
        return _as_reply(verdict)

    def progress(self, *, state: Any, facts: int) -> str | None:
        stop = self.driver.observe_progress(task_state=state, evidence_count=facts)
        return stop.terminal_reason if stop is not None else None

    def finish(self, deliverable: dict[str, Any] | None) -> Finish:
        verdict = self.driver.submit_deliverable(deliverable, answer_key=self.key)
        return Finish(terminal=verdict.terminal_reason, escalate_to=verdict.escalate_to)

    # ------------------------------------------------------------------ closing

    def close(self) -> None:
        self._store.close()

    def summary(self, trace: Trace) -> Summary:
        """Read the log back before reporting on it.

        What a run meant to produce and what it durably produced are two
        different claims, and only the second one is evidence.
        """
        events, sealed, verified = _read_back(self._path, self.run_id)
        return Summary(
            arm=self.name,
            run_id=self.run_id,
            tokens=trace.tokens,
            metered=True,
            executed=len(self.tools.invocations),
            suppressed=trace.denied + trace.cached,
            side_effects=tuple(self.tools.side_effects),
            terminal=self.driver.terminated,
            gate=self.driver.quality_state,
            escalations=self.driver.escalations,
            events=events,
            sealed=sealed,
            verified=verified,
        )


# ------------------------------------------------------------- the ungoverned arm


class Ungoverned:
    """The same loop with nothing in front of the executor. FR52's control."""

    name = "ungoverned"

    def __init__(self, subject: Case, *, spec: Contract | None = None) -> None:
        self.case = subject
        self.spec = spec or contract()
        self.run_id = f"{subject.case_id}-ungoverned"
        self.tools: WorkloadToolPort = tool_port_for(self.spec)
        self._tokens = 0

    def charge(self, *, step_id: str, tokens: int, cost: float, model: str) -> str | None:
        # Counted, not governed. There is no ledger to refuse it and no reserve
        # to protect, so this can only ever return None.
        self._tokens += tokens
        return None

    def call(self, *, step_id: str, tool: str, arguments: dict[str, Any]) -> Reply:
        request = ToolCall(tool=tool, arguments=arguments, step_id=step_id)
        try:
            result = self.tools.invoke(request)
        except ToolError as exc:
            return Reply(text=f"tool error: {exc}", how=FAILED)
        return Reply(text=_render(result.output), how=RAN)

    def progress(self, *, state: Any, facts: int) -> str | None:
        return None

    def finish(self, deliverable: dict[str, Any] | None) -> Finish:
        # No gate. The answer is whatever the agent said it was.
        return Finish()

    def close(self) -> None:
        return None

    def summary(self, trace: Trace) -> Summary:
        return Summary(
            arm=self.name,
            run_id=self.run_id,
            tokens=self._tokens,
            metered=False,
            executed=len(self.tools.invocations),
            suppressed=0,
            side_effects=tuple(self.tools.side_effects),
            terminal=None,
            gate=NOT_EVALUATED,
            escalations=0,
        )


# ------------------------------------------------------------------- internals


def _as_reply(verdict: Any) -> Reply:
    """INTEGRATION.md §5b's verdict table, and nothing else.

    Terminality is checked first on purpose: a host that reads the action and
    continues past a terminal verdict has produced a plausible and entirely
    false audit trail.
    """
    if verdict.terminates:
        return Reply(
            text=verdict.detail or verdict.decision_reason,
            how=DENIED,
            terminal=verdict.terminal_reason,
        )
    if verdict.action == "proceed-with-substitution":
        return Reply(text=_render(verdict.result), how=CACHED)
    if verdict.action == "proceed" and verdict.failed:
        return Reply(text=verdict.detail, how=FAILED)
    if verdict.action == "proceed":
        return Reply(text=_render(verdict.result), how=RAN)
    return Reply(text=f"not allowed: {verdict.decision_reason}", how=DENIED)


def _render(output: Any) -> str:
    if isinstance(output, str):
        return output
    return json.dumps(output, default=str, sort_keys=True)


def _approval(approval: Decision | ApprovalPort) -> ApprovalPort:
    if isinstance(approval, str):
        return ScriptedApprovalPort(default=approval)
    return approval


def _ledger(spec: Contract) -> Ledger:
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


def _manifest(run_id: str, *, spec: Contract) -> RunManifest:
    models = tuple(spec.models.eligible) if spec.models else ("gpt-5-mini",)
    return RunManifest(
        run_id=run_id,
        mode="governed",
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
        provider_versions=dict.fromkeys(models, "deterministic"),
        cost_table_version="unpriced",
        route="direct",
        streaming_disabled=True,
        adapter_id="miniloop",
        adapter_version="1",
        governor_code_version="0.1.0",
        sqlite_library_version=sqlite3.sqlite_version,
        seed=1,
    )


def _read_back(path: Path, run_id: str) -> tuple[int, bool, bool]:
    with open_store(path, writer=False) as store:
        events = store.events(run_id)
        sealed = bool(store.seal(run_id))
        try:
            store.verify_run(run_id)
            verified = True
        except (StoreError, ValueError):
            verified = False
    return len(events), sealed, verified
