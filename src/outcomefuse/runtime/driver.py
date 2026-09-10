"""The enforcing driver (AD-2, AD-4, AD-20).

The driver is the only component that performs port calls. It fulfils an
`EvidenceRequest`, appends the outcome, then re-invokes the advisor with the
result — which is why replay is feeding recorded outcomes back into a pure
function rather than re-running the world.

Two rules are enforced here because nowhere else can be:

- **Every decision is appended before it takes effect** (FR5). The verdict is
  returned to the adapter only after the row is written, so a step that happened
  cannot be missing from the log.
- **Fail-closed is a property of the driver** (AD-20). Gate-verdict
  unavailability, ledger-state loss and approval-*channel* unavailability
  terminate through the ladder. An approval *timeout* does not — it follows the
  contract's `on_timeout`, and merging the two would route an ordinary timeout
  to a condition ranked above the approval gate.

Fail-open is deliberately *not* here. It belongs to the advisor registry, so a
mechanism failing is a deregistration and a `degraded` event rather than a
branch in the driver's control flow.

Shadow is not here either. It is a **separate driver** (AD-11), because a
`shadow` flag would put a conditional in the fail-closed paths above — the most
safety-critical code in the system, on the branch least exercised by tests.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel, ConfigDict

from ..core.canon import Digest
from ..core.contract import Contract
from ..core.gate import GateUnavailable, QualityGate, should_evaluate
from ..core.policy import Ledger, LedgerError, Policy, Situation
from ..core.record import Event, RecordStore
from ..core.verify import CitableIndex
from ..ports import ProbedToolPort, ToolCall
from .tool_governor import Disposition, ToolGovernor

WHEN = "2026-09-10T12:00:00Z"


class StepVerdict(BaseModel):
    """What the adapter is told to do, after the decision is already recorded."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    action: str
    decision_reason: str
    terminal_reason: str | None = None
    result: Any = None
    detail: str = ""

    @property
    def terminates(self) -> bool:
        return self.terminal_reason is not None


class Driver:
    """Runs one governed run against one contract."""

    def __init__(
        self,
        *,
        run_id: str,
        contract: Contract,
        store: RecordStore,
        ledger: Ledger,
        governor: ToolGovernor,
        tools: ProbedToolPort,
        policy: Policy | None = None,
        gate: QualityGate | None = None,
    ) -> None:
        self.run_id = run_id
        self.contract = contract
        self.store = store
        self.ledger = ledger
        self.governor = governor
        self.tools = tools
        self.policy = policy or Policy()
        self.gate = gate or QualityGate()
        self._seq = 0
        self._citable_index: CitableIndex | None = None
        self._index_digest: Digest | None = None
        self.quality_state = "not-evaluated"
        self.terminated: str | None = None

    # ------------------------------------------------------------- the log

    def _append(self, kind: str, **fields: Any) -> Event:
        event = Event(
            run_id=self.run_id, seq=self._seq, kind=kind, recorded_at=WHEN, **fields
        )
        self.store.append(event)
        self._seq += 1
        return event

    def open_run(self, manifest: Any) -> None:
        if getattr(manifest, "mode", None) == "shadow":
            raise ValueError(
                "a shadow run belongs to ShadowDriver; this driver enforces, and FR91 "
                "forbids shadow altering anything the host would otherwise do"
            )
        self.store.open_run(manifest, recorded_at=WHEN)
        self._seq = 1

    # ----------------------------------------------------- the citable index

    def bind_citable_index(self, index: CitableIndex) -> Digest:
        """AD-7: built by the driver, hashed, appended before any verifier runs.

        Two implementations deriving it differently would otherwise produce
        different verdicts, and so different terminal reasons, for one run.
        """
        self._citable_index = index
        self._index_digest = index.digest()
        self._append(
            "evidence-observed",
            payload={"citable_index_sha256": self._index_digest.sha256},
        )
        return self._index_digest

    # ------------------------------------------------------------- one step

    def execute_step(
        self,
        call: ToolCall,
        *,
        step_class: str = "evidence-gathering",
        unmet_mandatory: set[str] | None = None,
        step_is_enrichment: bool = False,
        estimated_tokens: int = 10,
        estimated_cost: float = 0.001,
    ) -> StepVerdict:
        if self.terminated is not None:
            raise RuntimeError(f"run already terminated: {self.terminated}")

        self._append("decision-proposed", step_id=call.step_id)

        try:
            disposition = self.governor.assess(
                call,
                run_id=self.run_id,
                unmet_mandatory=unmet_mandatory,
                step_is_enrichment=step_is_enrichment,
            )
        except Exception as exc:  # noqa: BLE001 - any governor failure is fail-closed
            # AD-20: a port or component error is a decision input, never an
            # escape. Narrowing this would let an unanticipated failure unwind
            # past the ladder and out of the run entirely.
            return self._fail_closed("terminate", f"tool governor failed: {exc}")

        if disposition.channel_unavailable:
            # FR89 through AD-20: the gated call is not made and the run halts.
            return self._fail_closed("request-human", disposition.detail)

        if disposition.action == "pause-for-approval":
            return self._paused(call, disposition)

        if disposition.action == "deny":
            self._append(
                "decision-recorded",
                step_id=call.step_id,
                policy_action="deny",
                decision_reason=disposition.reason,
            )
            return StepVerdict(action="deny", decision_reason=disposition.reason)

        if disposition.action == "proceed-with-substitution":
            self._append(
                "decision-recorded",
                step_id=call.step_id,
                policy_action="proceed-with-substitution",
                decision_reason="cache-hit",
            )
            return StepVerdict(
                action="proceed-with-substitution",
                decision_reason="cache-hit",
                result=disposition.cached_result,
            )

        # A real spend: held before it happens (AD-3).
        hold_id = f"{call.step_id}-{self._seq}"
        try:
            self.ledger.hold(
                hold_id, call.step_id, "tool-governor", estimated_tokens, estimated_cost
            )
        except LedgerError as exc:
            return self._fail_closed("terminate", f"ledger unusable: {exc}")

        self._append("budget-reserved", step_id=call.step_id)
        self._append(
            "decision-recorded",
            step_id=call.step_id,
            policy_action="proceed",
            decision_reason=disposition.reason,
        )

        result = self._execute(call)
        self._append("outcome-observed", step_id=call.step_id)
        self.ledger.settle(hold_id)
        self._append("spend-settled", step_id=call.step_id, tokens_consumed=estimated_tokens)

        if should_evaluate(step_class):
            verdict = self._run_gate()
            if verdict is not None:
                return verdict

        return StepVerdict(action="proceed", decision_reason=disposition.reason, result=result)

    # ------------------------------------------------------------ internals

    def _execute(self, call: ToolCall) -> Any:
        result = self.tools.invoke(call)
        self.governor.observe(call, result.output)
        return result.output

    def _paused(self, call: ToolCall, disposition: Disposition) -> StepVerdict:
        if disposition.reason == "approval-timeout":
            action = self.contract.on_timeout or "terminate"
            terminal = None if action == "escalate" else "approval-timeout"
            self._append(
                "decision-recorded",
                step_id=call.step_id,
                policy_action=action,
                decision_reason="approval-timeout",
                terminal_reason=terminal,
            )
            if terminal is not None:
                self._close(terminal)
            return StepVerdict(
                action=action, decision_reason="approval-timeout", terminal_reason=terminal
            )

        self._append(
            "decision-recorded",
            step_id=call.step_id,
            policy_action="deny",
            decision_reason=disposition.reason,
        )
        return StepVerdict(action="deny", decision_reason=disposition.reason)

    def _run_gate(self) -> StepVerdict | None:
        deliverable = self.deliverable()
        if deliverable is None:
            return None
        try:
            verdict = self.gate.evaluate(
                self.contract,
                deliverable,
                answer_key=self.answer_key(),
                citable_index=self._citable_index,
            )
        except GateUnavailable as exc:
            return self._fail_closed("request-human", f"gate unavailable: {exc}")

        self.quality_state = verdict.verdict
        self._append(
            "gate-verdict",
            gate_verdict=verdict.verdict,
            verification_mode=verdict.qualifier,
            quality_state=verdict.verdict,
        )
        if verdict.passed:
            outcome = self.policy.resolve(
                Situation(floor_met=True, quality_state=self.quality_state)
            )
            self._append(
                "decision-recorded",
                policy_action=outcome.policy_action,
                decision_reason=outcome.decision_reason,
                terminal_reason=outcome.terminal_reason,
            )
            self._close(outcome.terminal_reason or "stop-sufficient")
            return StepVerdict(
                action=outcome.policy_action,
                decision_reason=outcome.decision_reason,
                terminal_reason=outcome.terminal_reason,
            )
        return None

    def _fail_closed(self, action: str, detail: str) -> StepVerdict:
        self._append(
            "decision-recorded",
            policy_action=action,
            decision_reason="fail-closed",
            terminal_reason="fail-closed",
            payload={"detail": detail},
        )
        self._close("fail-closed")
        return StepVerdict(
            action=action,
            decision_reason="fail-closed",
            terminal_reason="fail-closed",
            detail=detail,
        )

    def _close(self, terminal: str) -> None:
        self.ledger.release_all()
        self._append("run-closed")
        self.terminated = terminal

    # ------------------------------------------------- supplied by the host

    def deliverable(self) -> Mapping[str, Any] | None:
        """Overridden by a runner that actually builds one."""
        return None

    def answer_key(self) -> Mapping[str, Any] | None:
        return None
