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

import json
from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel, ConfigDict

from ..core.canon import Digest
from ..core.contract import Contract
from ..core.gate import GateUnavailable, QualityGate, should_evaluate
from ..core.policy import (
    AdvisorRegistry,
    Ledger,
    LedgerError,
    LoopFuse,
    Policy,
    Situation,
)
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
    #: The tool was allowed and then failed. Distinct from a denial: the agent
    #: should read the error and try something else, not conclude it is barred.
    failed: bool = False
    #: The run continues on this model instead. Not terminal: an escalated run
    #: has not ended, and treating it as ended would make the retry a second run
    #: that no comparison could pair.
    escalate_to: str | None = None

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
        fuse: LoopFuse | None = None,
        advisors: AdvisorRegistry | None = None,
        evidence: Any | None = None,
    ) -> None:
        self.run_id = run_id
        self.contract = contract
        self.store = store
        self.ledger = ledger
        self.governor = governor
        self.tools = tools
        self.policy = policy or Policy()
        self.gate = gate or QualityGate()
        self.fuse = fuse
        self.advisors = advisors
        #: AD-5b's sidecar. FR69's blind review reads the deliverable from here,
        #: because the decision log carries a reference and a hash, never a body.
        self.evidence = evidence
        self._seq = 0
        self._iterations = 0
        self._citable_index: CitableIndex | None = None
        self._index_digest: Digest | None = None
        self._deliverable: Mapping[str, Any] | None = None
        self._answer_key: Mapping[str, Any] | None = None
        self.quality_state = "not-evaluated"
        self.gate_qualifier: str | None = None
        #: The model the run is currently on. Escalation moves it up the
        #: contract's eligible list; the manifest declares the whole list.
        self.model_id: str | None = contract.models.start if contract.models else None
        self.escalations = 0
        self._unmet: tuple[str, ...] = ()
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

        # AD-3: affordability is a *query*, asked before deciding, so
        # `unaffordable` reaches the Policy as a decision input and exhausts the
        # run under FR92. A rejected reservation further down is fail-closed
        # under FR88 — a different cause, a different terminal reason, and the
        # product's central cost event filed as a system fault if merged.
        if not self.ledger.can_afford(estimated_tokens, estimated_cost):
            return self._resolve(
                Situation(
                    budget_remains=False,
                    affordable_step_advances_floor=False,
                    quality_state=self.quality_state,
                ),
                step_id=call.step_id,
            )

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

        try:
            result = self._execute(call)
        except Exception as exc:  # noqa: BLE001 - any tool failure, released and recorded
            # The hold must come back. A tool that raises after the budget was
            # reserved would otherwise leave that reservation in flight for the
            # rest of the run, quietly shrinking what the agent can spend until
            # it halts exhausted for no reason anyone could find in the log.
            self.ledger.release_unspent(hold_id)
            self._append(
                "outcome-observed",
                step_id=call.step_id,
                payload={"tool_error": str(exc), "tool": call.tool},
            )
            return StepVerdict(
                action="proceed",
                decision_reason=disposition.reason,
                detail=f"tool error: {exc}",
                failed=True,
            )

        self._append("outcome-observed", step_id=call.step_id)
        self.ledger.settle(hold_id)
        self._append("spend-settled", step_id=call.step_id, tokens_consumed=estimated_tokens)

        if should_evaluate(step_class):
            verdict = self._run_gate()
            if verdict is not None:
                return verdict

        return StepVerdict(action="proceed", decision_reason=disposition.reason, result=result)

    # ------------------------------------------------------------ internals

    def charge_model_turn(
        self, *, step_id: str, tokens: int, cost: float, model_used: str
    ) -> StepVerdict | None:
        """A model call is a spend, and it is the largest one in the run.

        `execute_step` is keyed on a `ToolCall` and cannot express this. Without
        a primitive of its own the reasoning tokens — 85% of gpt-5's completion
        on a one-word prompt, as measured — would never reach the ledger, and the
        budget would govern the cheap half of the run while the expensive half
        ran unmetered.

        Returns a verdict only where the run must stop. Affordability is asked
        first so exhaustion reaches the Policy as a decision input (FR92) rather
        than as a rejected reservation, which is fail-closed and a different
        thing entirely.
        """
        if self.terminated is not None:
            raise RuntimeError(f"run already terminated: {self.terminated}")

        if not self.ledger.can_afford(tokens, cost):
            return self._resolve(
                Situation(
                    budget_remains=False,
                    affordable_step_advances_floor=False,
                    quality_state=self.quality_state,
                ),
                step_id=step_id,
            )

        hold_id = f"{step_id}-model-{self._seq}"
        try:
            self.ledger.hold(hold_id, step_id, "model-turn", tokens, cost)
        except LedgerError as exc:
            return self._fail_closed("terminate", f"ledger unusable: {exc}")

        self._append("budget-reserved", step_id=step_id)
        self.ledger.settle(hold_id)
        self._append(
            "spend-settled",
            step_id=step_id,
            tokens_consumed=tokens,
            model_used=model_used,
        )
        return None

    def _resolve(
        self,
        situation: Situation,
        *,
        step_id: str | None = None,
        detail: dict[str, Any] | None = None,
    ) -> StepVerdict:
        """Put a situation to the Policy and record what comes back.

        Every terminating condition routes through here, so the FR2 ladder is
        applied in one place rather than re-derived per path.
        """
        outcome = self.policy.resolve(situation)
        self._append(
            "decision-recorded",
            step_id=step_id,
            policy_action=outcome.policy_action,
            decision_reason=outcome.decision_reason,
            terminal_reason=outcome.terminal_reason,
            payload=detail or {},
        )
        if outcome.terminal_reason is not None:
            self._close(outcome.terminal_reason)
        return StepVerdict(
            action=outcome.policy_action,
            decision_reason=outcome.decision_reason,
            terminal_reason=outcome.terminal_reason,
        )

    def observe_progress(self, *, task_state: Any, evidence_count: int) -> StepVerdict | None:
        """FR27, FR28. The host says what changed; the driver decides what it means.

        Returns a verdict only where the fuse fired. Budget exhaustion is
        deliberately not a fuse condition — it terminates under FR92, and
        conflating the two files the product's central cost event as a stall.
        """
        if self.fuse is None:
            return None
        halt = self.fuse.observe(
            self.fuse.fingerprint(
                iteration=self._iterations,
                task_state=task_state,
                evidence_count=evidence_count,
                quality_state=self.quality_state,
            )
        )
        self._iterations += 1
        if halt is None:
            return None
        return self._resolve(
            Situation(no_progress=True, quality_state=self.quality_state),
            detail={"fuse": halt},
        )

    def consult_advisors(self, state: Any) -> list[Any]:
        """AD-20: fail-open belongs to the registry, never to this control flow.

        An advisor that raises is deregistered for the rest of the run and a
        `degraded` event names it. Degraded is not disabled — the manifest
        records what was enabled at the start, the log records what dropped.
        """
        if self.advisors is None:
            return []
        return self.advisors.compose(
            state,
            on_degraded=lambda name, exc: self._append(
                "degraded", payload={"mechanism": name, "error": str(exc)}
            ),
        )

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
        self.gate_qualifier = verdict.qualifier
        self._unmet = verdict.unmet
        self._append(
            "gate-verdict",
            gate_verdict=verdict.verdict,
            verification_mode=verdict.qualifier,
            quality_state=verdict.verdict,
        )
        if verdict.passed:
            return self._resolve(
                Situation(floor_met=True, quality_state=self.quality_state)
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

    def submit_deliverable(
        self,
        deliverable: Mapping[str, Any] | None,
        *,
        answer_key: Mapping[str, Any] | None = None,
        parse_failure: str | None = None,
    ) -> StepVerdict:
        """The agent stopped calling tools and produced something. Gate it.

        Without this the gate could only ever run *after a tool call*, which
        means the one moment that matters — the agent claiming it is finished —
        had no path to a verdict. A run could end with an ungated answer.

        A deliverable that could not be parsed is a **recorded decision**, not an
        exception. The agent emitting unreadable output is a failure of the arm
        that produced it, and an exception here would lose the run rather than
        score it.
        """
        if self.terminated is not None:
            raise RuntimeError(f"run already terminated: {self.terminated}")

        self._deliverable = deliverable
        self._answer_key = answer_key
        self._keep_evidence(deliverable)

        if deliverable is None:
            # A run that produced nothing has failed harder than one whose answer
            # the gate refused, so it gets the same retry. Measured on data-sql:
            # seven of twelve governed runs spent their whole iteration budget
            # and returned no answer, and stopping there means having charged
            # for nothing at all — the worst outcome available, and worse than a
            # wrong answer because nothing downstream can even detect it.
            escalated = self._escalate(reason=parse_failure or "no deliverable")
            if escalated is not None:
                return escalated
            return self._resolve(
                Situation(no_progress=True, quality_state=self.quality_state),
                detail={"deliverable": parse_failure or "no deliverable was produced"},
            )

        verdict = self._run_gate()
        if verdict is not None:
            return verdict

        # The gate failed. The contract may direct a retry on a stronger model
        # before anything terminal happens, and an escalated run has not ended —
        # so this is checked before the FR103 ladder rather than inside it.
        escalated = self._escalate(reason="gate-fail")
        if escalated is not None:
            return escalated

        # No escalation left, or none directed. FR103 hands this to the
        # contract: return partial, or refer it to a human.
        return self._resolve(
            Situation(
                gate_failed=True,
                quality_state=self.quality_state,
                contract_directs=self._on_gate_fail(),
            ),
            detail={"deliverable": "gate did not pass and the agent stopped"},
        )

    def _keep_evidence(self, deliverable: Mapping[str, Any] | None) -> None:
        """Write the answer where a blind reviewer can read it (AD-5b, FR69).

        Without this the run records that a gate passed and not what it passed,
        so the review that exists to contradict the gate has nothing to read.
        The log gets the reference and the hash; the body stays in the sidecar.
        """
        if self.evidence is None or deliverable is None:
            return
        ref = self.evidence.write(
            "deliverable.json", json.dumps(dict(deliverable), indent=2, sort_keys=True)
        )
        self._append(
            "evidence-observed",
            payload={"deliverable": ref.relative_path, "sha256": ref.sha256},
        )

    def _escalate(self, *, reason: str = "gate-fail") -> StepVerdict | None:
        """FR35: retry on a stronger model when the contract says to.

        Returns `None` where escalation is not available, leaving the caller on
        the terminal ladder. The run is deliberately **not** closed here: an
        escalated run continues, and closing it would make the retry a second
        run that no comparison could pair.
        """
        escalation = self.contract.escalation
        if escalation is None or escalation.on_gate_fail != "retry-then-escalate":
            return None
        if self.escalations >= escalation.max_escalations:
            return None

        stronger = self.next_model()
        if stronger is None:
            return None

        # The verification reserve exists so a run can always afford to check
        # its own work. An escalation that ate it would buy a better answer and
        # lose the ability to tell whether it was better.
        estimate = self._escalation_estimate()
        if escalation.never_breach_verification_reserve and not (
            self.ledger.escalation_leaves_reserve_intact(*estimate)
        ):
            self._append(
                "decision-recorded",
                policy_action="deny",
                decision_reason="unaffordable",
                payload={"escalation": "would breach the verification reserve"},
            )
            return None

        self.escalations += 1
        self._append(
            "decision-recorded",
            policy_action="escalate",
            decision_reason="escalation-gate-fail",
            model_used=stronger,
            payload={
                "from": self.model_id,
                "to": stronger,
                "escalation": self.escalations,
                "because": reason,
                "unmet": sorted(self._unmet),
            },
        )
        self.model_id = stronger
        # The next attempt is a fresh one, so the failed answer must not be left
        # standing: a gate run before the retry submits would otherwise re-read
        # the deliverable that just failed.
        self._deliverable = None
        self.quality_state = "not-evaluated"
        return StepVerdict(
            action="escalate",
            decision_reason="escalation-gate-fail",
            escalate_to=stronger,
        )

    def next_model(self) -> str | None:
        """The next model up the contract's eligible list, or `None` at the top."""
        models = self.contract.models
        if models is None:
            return None
        eligible = list(models.eligible)
        try:
            index = eligible.index(self.model_id or models.start)
        except ValueError:
            return None
        return eligible[index + 1] if index + 1 < len(eligible) else None

    def _escalation_estimate(self) -> tuple[int, float]:
        """What a retry is expected to cost, from what this run has already spent.

        Derived rather than declared: the run itself is the best available
        estimate of what running it again costs, and a constant here would be a
        number nobody could defend.
        """
        return self.ledger.spent_tokens, self.ledger.spent_cost

    def _on_gate_fail(self) -> str:
        directive = getattr(self.contract.escalation, "on_gate_fail", None)
        return directive if directive in ("return-partial", "request-human") else "return-partial"

    def deliverable(self) -> Mapping[str, Any] | None:
        """What the agent produced, once `submit_deliverable` has been called."""
        return self._deliverable

    def answer_key(self) -> Mapping[str, Any] | None:
        return self._answer_key
