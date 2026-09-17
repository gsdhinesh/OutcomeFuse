"""The only file in this client that knows OutcomeFuse exists.

Two implementations of `loop.Site`. `Governed` holds a `Driver`; `Ungoverned`
holds nothing and calls the desk directly. FR52's control arm has no governor to
switch off, so the honest comparison is against a loop with no governance in it
rather than a governor configured to permit everything.

Three things here are specific to a *chat*:

1. **`TeeStore`** hands each event to a sink **after** it is durably written, so
   the browser can never get ahead of the log. A viewer that saw a decision the
   store had not accepted would be showing something that did not happen.
2. **`LiveApprovalPort`** blocks the driver's thread until a person clicks. The
   tool is not invoked while it waits, because the call has not been authorised
   yet — that is what the gate means. It is the console's port, reused rather
   than reimplemented: one implementation of "silence is never consent".
3. **The gate's unmet criteria are read off the log**, not off a private
   attribute, because the log is what a person would have to trust later.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from console.approval import LiveApprovalPort

from chat import desk
from chat.loop import CACHED, DENIED, FAILED, RAN, Finish, Outcome, Reply
from outcomefuse.core.contract import Contract, load_path
from outcomefuse.core.policy import Ledger, LoopFuse, Reserve
from outcomefuse.core.record import Event, RecordStore, RunManifest, StoreError, open_store
from outcomefuse.core.verify.registry import REGISTRY_VERSION, registry_digest
from outcomefuse.evidence.store import EvidenceStore
from outcomefuse.ports import ApprovalPort, Decision, ScriptedApprovalPort, ToolCall
from outcomefuse.runtime import ContextGovernor, Driver, ToolGovernor

ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = Path(__file__).resolve().parent / "chat.contract.yaml"

#: No rubric, coverage report or baseline definition exists for this desk, so
#: the manifest fields that would carry their digests carry nothing. A hash over
#: an artefact that does not exist would make the manifest look more evidential
#: than the run is.
ABSENT = "0" * 64

NOT_EVALUATED = "not-evaluated"

Sink = Callable[[Event], None]


def contract() -> Contract:
    return load_path(CONTRACT_PATH)


class TeeStore(RecordStore):
    """Hands each event to a sink *after* it is durably written.

    `open_run` appends the manifest through `self.append`, so seq 0 is streamed
    too — the viewer gets the whole log, not the part after it started looking.
    A sink that raises is collected, never allowed to break the run.
    """

    def __init__(self, path: Path | str, *, sink: Sink) -> None:
        super().__init__(path)
        self._sink = sink
        self.sink_errors: list[str] = []

    def append(self, event: Event) -> str:
        digest = super().append(event)
        try:
            self._sink(event)
        except Exception as exc:  # noqa: BLE001 - a viewer must not break a run
            self.sink_errors.append(f"{type(exc).__name__}: {exc}")
        return digest


# --------------------------------------------------------------- the governed arm


class Governed:
    """`loop.Site` over a `Driver`. INTEGRATION.md §5b-§5e, over a chat."""

    name = "governed"

    def __init__(
        self,
        run_id: str,
        *,
        runs_dir: Path,
        spec: Contract | None = None,
        approval: Decision | ApprovalPort = "approved",
        sink: Sink | None = None,
    ) -> None:
        self.spec = spec or contract()
        self.run_id = run_id
        self.tools = desk.tool_port(self.spec)
        self._unmet: tuple[str, ...] = ()

        runs_dir.mkdir(parents=True, exist_ok=True)
        self._path = runs_dir / f"{run_id}.db"
        self._store: RecordStore = (
            TeeStore(self._path, sink=self._watch(sink)).open()
            if sink is not None
            else RecordStore(self._path).open()
        )
        evidence = EvidenceStore(runs_dir / "evidence", data_class="synthetic")

        self.driver = Driver(
            run_id=run_id,
            contract=self.spec,
            store=self._store,
            ledger=_ledger(self.spec),
            governor=ToolGovernor(self.spec, approval=_approval(approval)),
            tools=self.tools,
            fuse=LoopFuse(max_iterations=self.spec.budget.max_iterations),
            context=ContextGovernor(self.spec),
            evidence=evidence.for_driver(run_id),
        )
        try:
            self.driver.open_run(_manifest(run_id, spec=self.spec))
            # AD-7: bound before any verifier runs, or two implementations
            # deriving it differently would reach different verdicts for one run.
            self.driver.bind_citable_index(desk.citable_index())
        except BaseException:
            # The store is open by now, and `open_run` refuses a run id that
            # already exists. Leaving the connection behind turns a clear
            # refusal into an unclosed-database warning somewhere else entirely.
            self._store.close()
            raise

    def _watch(self, sink: Sink) -> Sink:
        """Read the gate's unmet criteria off the log on the way past."""

        def observe(event: Event) -> None:
            if event.kind == "gate-verdict":
                self._unmet = tuple(event.payload.get("unmet", ()))
            sink(event)

        return observe

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
        # No answer key: nothing in a live support chat has a reference answer
        # sitting beside it. Every mandatory criterion in this contract is
        # constraint-backed for exactly that reason.
        verdict = self.driver.submit_deliverable(deliverable)
        return Finish(
            terminal=verdict.terminal_reason,
            escalate_to=verdict.escalate_to,
            gate=self.driver.quality_state,
            unmet=self._unmet,
        )

    # ------------------------------------------------------------------ closing

    def close(self) -> None:
        self._store.close()

    def summary(self, outcome: Outcome) -> Summary:
        events, sealed, verified = _read_back(self._path, self.run_id)
        return Summary(
            arm=self.name,
            run_id=self.run_id,
            tokens=outcome.tokens,
            metered=True,
            executed=len(self.tools.invocations),
            suppressed=outcome.denied + outcome.cached,
            side_effects=tuple(self.tools.side_effects),
            terminal=self.driver.terminated,
            gate=self.driver.quality_state,
            qualifier=self.driver.gate_qualifier or "",
            unmet=self._unmet,
            escalations=self.driver.escalations,
            events=events,
            sealed=sealed,
            verified=verified,
        )


# ------------------------------------------------------------- the ungoverned arm


class Ungoverned:
    """The same loop with nothing in front of the desk."""

    name = "ungoverned"

    def __init__(self, run_id: str, *, spec: Contract | None = None, **_: Any) -> None:
        self.spec = spec or contract()
        self.run_id = run_id
        self.tools = desk.tool_port(self.spec)
        self._tokens = 0

    def charge(self, *, step_id: str, tokens: int, cost: float, model: str) -> str | None:
        # Counted, not governed. No ledger can refuse it and no reserve is
        # protected, so this can only ever return None.
        self._tokens += tokens
        return None

    def call(self, *, step_id: str, tool: str, arguments: dict[str, Any]) -> Reply:
        request = ToolCall(tool=tool, arguments=arguments, step_id=step_id)
        try:
            result = self.tools.invoke(request)
        except Exception as exc:  # noqa: BLE001 - an ungoverned host swallows it
            return Reply(text=f"tool error: {exc}", how=FAILED)
        return Reply(text=_render(result.output), data=result.output, how=RAN)

    def progress(self, *, state: Any, facts: int) -> str | None:
        return None

    def finish(self, deliverable: dict[str, Any] | None) -> Finish:
        # No gate. The answer is whatever the agent said it was.
        return Finish()

    def close(self) -> None:
        return None

    def summary(self, outcome: Outcome) -> Summary:
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
            qualifier="",
            unmet=(),
            escalations=0,
        )


@dataclass(frozen=True)
class Summary:
    """What each arm can say about itself once the conversation turn is over."""

    arm: str
    run_id: str
    #: Model tokens. The governed arm charged them through a ledger that could
    #: refuse; the ungoverned arm merely counted them.
    tokens: int
    metered: bool
    executed: int
    suppressed: int
    side_effects: tuple[str, ...]
    terminal: str | None
    gate: str
    qualifier: str
    unmet: tuple[str, ...]
    escalations: int
    #: `None` where no log exists, which is the ungoverned arm's whole position.
    events: int | None = None
    sealed: bool = False
    verified: bool = False

    def as_json(self) -> dict[str, Any]:
        return {**asdict(self), "side_effects": list(self.side_effects), "unmet": list(self.unmet)}


# ------------------------------------------------------------------- internals


def _as_reply(verdict: Any) -> Reply:
    """INTEGRATION.md §5b's verdict table, and nothing else.

    Terminality is read before the action on purpose: a host that continues past
    a terminal verdict has produced a plausible and entirely false audit trail.
    """
    if verdict.terminates:
        return Reply(
            text=verdict.detail or verdict.decision_reason,
            how=DENIED,
            terminal=verdict.terminal_reason,
        )
    if verdict.action == "proceed-with-substitution":
        return Reply(text=_render(verdict.result), data=verdict.result, how=CACHED)
    if verdict.action == "proceed" and verdict.failed:
        return Reply(text=verdict.detail, how=FAILED)
    if verdict.action == "proceed":
        return Reply(text=_render(verdict.result), data=verdict.result, how=RAN)
    return Reply(text=f"not allowed: {verdict.decision_reason}", how=DENIED)


def _render(output: Any) -> str:
    if isinstance(output, str):
        return output
    return json.dumps(output, default=str, sort_keys=True)


def _approval(approval: Decision | ApprovalPort) -> ApprovalPort:
    if isinstance(approval, str):
        return ScriptedApprovalPort(default=approval)
    return approval


def live_approval(spec: Contract) -> LiveApprovalPort:
    """The contract's own window, not a number chosen to suit a demonstration."""
    return LiveApprovalPort(timeout_seconds=spec.approval_timeout_seconds or 120)


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
        # The desk is invented. `refuse_persistence` admits nothing else without
        # an approved governance profile, and none exists.
        data_class="synthetic",
        retention_profile="mvp-synthetic-v1",
        contract_hash=spec.digest().sha256,
        rubric_hash=ABSENT,
        answer_key_hash=ABSENT,
        verifier_registry_version=REGISTRY_VERSION,
        verifier_registry_hash=registry_digest().sha256,
        coverage_report_hash=ABSENT,
        baseline_configuration_hash=ABSENT,
        # There is no case set: a chat turn is whatever the person typed. Naming
        # the desk is the most this field can honestly carry.
        case_set_id="support-chat/live",
        split="calibration",
        model_ids=models,
        provider_versions=dict.fromkeys(models, "deterministic"),
        cost_table_version="unpriced",
        route="direct",
        streaming_disabled=True,
        adapter_id="support-chat",
        adapter_version="1",
        governor_code_version="0.1.0",
        sqlite_library_version=sqlite3.sqlite_version,
        seed=1,
    )


def _read_back(path: Path, run_id: str) -> tuple[int, bool, bool]:
    """Reopen the sealed log. What a run meant to produce and what it durably
    produced are two different claims, and only the second is evidence."""
    with open_store(path, writer=False) as store:
        events = store.events(run_id)
        sealed = bool(store.seal(run_id))
        try:
            store.verify_run(run_id)
            verified = True
        except (StoreError, ValueError):
            verified = False
    return len(events), sealed, verified
