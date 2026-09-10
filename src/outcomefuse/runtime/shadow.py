"""Shadow mode: a driver, not a flag (AD-11, F10, FR46-FR49, FR91, FR96).

The governor watches a run it does not touch. Everything it would have done is
recorded; none of it is applied. Three properties make that claim structural
rather than aspirational:

- **Nothing is returned to the adapter.** AD-1 puts enforcement in the
  adapter's hands, so a shadow driver that handed back a verdict would be one
  cooperative adapter away from enforcing. `observe_step` returns `None`.
- **There is no ledger here.** AD-11 requires that governor spend never be
  debited to the observed run's ledger, and the surest way to honour that is to
  hold no ledger to debit. Estimated spend is written to the log's
  counterfactual lane and folded back out.
- **The `ApprovalPort` is never called.** FR91 forbids pausing the host, and a
  scripted decider that blocks is a pause. The clause is read from the contract
  and the pause is *recorded*, not requested.

**Two lanes, one log.** Every entry carries a `lane`. The observed lane is what
the host did; the counterfactual lane is what the governor would have done. The
counterfactual ledger is the fold restricted to its lane, so the two can never
disagree the way two separately maintained ledgers would.

**The counterfactual seals at its first terminating decision.** Past that point
the governed path never happened at all, so continuing to accrue estimated
spend against it would be inventing evidence. Host execution continues on the
observed lane, and everything it spends after the seal is reported as
*avoided-if-enforced* — never as counterfactual spend, and never without the
seal point and FR96's first divergence beside it.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from ..core.canon import Digest
from ..core.contract import Contract
from ..core.gate import GateUnavailable, QualityGate, should_evaluate
from ..core.policy import EvidenceRequest, Policy, Situation
from ..core.record import Event, Lane, RecordStore, RunManifest, fold
from ..core.verify import CitableIndex
from ..ports import ProbedToolPort, ToolCall
from .driver import WHEN
from .tool_governor import ToolGovernor


class ShadowRefused(RuntimeError):
    """Shadow was asked to do something that would alter the host."""


class Divergence(BaseModel):
    """One decision the governor would have taken and the host did not."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    seq: int
    step_id: str | None
    observed_action: str
    counterfactual_action: str
    counterfactual_reason: str
    terminal_reason: str | None = None


class ShadowReport(BaseModel):
    """What a shadow run may say about itself, and how it must say it.

    Every quantity is named for what it is. `counterfactual_tokens` stops at the
    seal; what the host spent afterwards is `avoided_if_enforced_tokens`, which
    is a different claim and reads like one.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    run_id: str
    mode: Literal["shadow"] = "shadow"
    #: FR49. Never `realized`, and not a field anyone can set to something else.
    label: Literal["projected"] = "projected"

    first_divergence: Divergence | None = None
    divergences: int = 0
    counterfactual_sealed_at: int | None = None
    counterfactual_terminal_reason: str | None = None

    observed_tokens: int = 0
    counterfactual_tokens: int = 0
    avoided_if_enforced_tokens: int = 0
    decisions_after_first_divergence: int = 0

    @property
    def disclosure(self) -> str:
        """FR96's label, derived once so every surface says the same thing."""
        if self.first_divergence is None:
            return (
                "projected: the governor would have acted exactly as the host did, so "
                "nothing here is inference"
            )
        return (
            f"projected: the paths diverge at seq {self.first_divergence.seq}, and the "
            f"{self.decisions_after_first_divergence} decision(s) after it are inference "
            "rather than observation"
        )


def build_shadow_report(events: Iterable[Event]) -> ShadowReport:
    """Derive the report from the log. Nothing here is accumulated in a driver.

    A figure a driver carried in memory is a figure the log cannot be checked
    against, which is the whole reason AD-2 makes state a fold.
    """
    rows = list(events)
    if not rows:
        raise ValueError("a run with no events has no shadow report")

    observed = fold(rows, lane="observed")
    counterfactual = fold(rows, lane="counterfactual")

    divergences: list[Divergence] = []
    last_observed_action: str | None = None
    sealed_at: int | None = None

    for event in rows:
        if event.kind != "decision-recorded" or event.policy_action is None:
            continue
        if event.lane == "observed":
            last_observed_action = event.policy_action
            continue
        if event.terminal_reason is not None and sealed_at is None:
            sealed_at = event.seq
        if last_observed_action is None or event.policy_action == last_observed_action:
            continue
        divergences.append(
            Divergence(
                seq=event.seq,
                step_id=event.step_id,
                observed_action=last_observed_action,
                counterfactual_action=event.policy_action,
                counterfactual_reason=event.decision_reason or "",
                terminal_reason=event.terminal_reason,
            )
        )

    first = divergences[0] if divergences else None
    after = (
        sum(
            1
            for e in rows
            if e.lane == "observed"
            and e.kind == "decision-recorded"
            and e.seq > first.seq
        )
        if first is not None
        else 0
    )
    avoided = (
        sum(
            e.tokens_consumed or 0
            for e in rows
            if e.lane == "observed" and e.seq > sealed_at
        )
        if sealed_at is not None
        else 0
    )

    return ShadowReport(
        run_id=observed.run_id,
        first_divergence=first,
        divergences=len(divergences),
        counterfactual_sealed_at=sealed_at,
        counterfactual_terminal_reason=counterfactual.terminal_reason,
        observed_tokens=observed.tokens_spent,
        counterfactual_tokens=counterfactual.tokens_spent,
        avoided_if_enforced_tokens=avoided,
        decisions_after_first_divergence=after,
    )


class ShadowDriver:
    """Observes one run and applies nothing to it."""

    def __init__(
        self,
        *,
        run_id: str,
        contract: Contract,
        store: RecordStore,
        governor: ToolGovernor,
        tools: ProbedToolPort,
        policy: Policy | None = None,
        gate: QualityGate | None = None,
    ) -> None:
        self.run_id = run_id
        self.contract = contract
        self.store = store
        self.governor = governor
        self.tools = tools
        self.policy = policy or Policy()
        self.gate = gate or QualityGate()
        self._seq = 0
        self._citable_index: CitableIndex | None = None
        self._sealed = False
        self.closed = False

    # ------------------------------------------------------------- the log

    def _append(self, kind: str, *, lane: Lane = "observed", **fields: Any) -> Event:
        event = Event(
            run_id=self.run_id, seq=self._seq, kind=kind, recorded_at=WHEN, lane=lane, **fields
        )
        self.store.append(event)
        self._seq += 1
        return event

    def open_run(self, manifest: RunManifest) -> None:
        if manifest.mode != "shadow":
            raise ShadowRefused(
                f"a shadow run's manifest declares mode 'shadow', not {manifest.mode!r}; "
                "FR49 makes the mode a recorded fact rather than a reader's inference"
            )
        self.store.open_run(manifest, recorded_at=WHEN)
        self._seq = 1

    def bind_citable_index(self, index: CitableIndex) -> Digest:
        self._citable_index = index
        digest = index.digest()
        self._append(
            "evidence-observed",
            lane="counterfactual",
            payload={"citable_index_sha256": digest.sha256},
        )
        return digest

    # ------------------------------------------------------ what it refuses

    def request_evidence(self, request: EvidenceRequest) -> None:
        """AD-11: no `EvidenceRequest` that would spend against the observed path.

        FR48 makes the executed ungoverned path the only measured one, so
        buying evidence for the counterfactual would contaminate the single
        measurement the run exists to produce.
        """
        if request.estimated_tokens or request.estimated_cost:
            raise ShadowRefused(
                f"{request.mechanism!r} asked for {request.kind!r} at "
                f"{request.estimated_tokens} tokens; in shadow the counterfactual is "
                "computed from outcomes already observed and never bought"
            )

    # ------------------------------------------------------------- one step

    def observe_step(
        self,
        call: ToolCall,
        *,
        step_class: str = "evidence-gathering",
        unmet_mandatory: set[str] | None = None,
        step_is_enrichment: bool = False,
        tokens: int = 10,
    ) -> None:
        """Record what the host did and what the governor would have done.

        Returns nothing: there is no verdict for an adapter to apply.
        """
        if self.closed:
            raise ShadowRefused("the run is closed")

        self._append("decision-proposed", step_id=call.step_id)

        # The host acts, and is recorded as having acted. FR47: the observed
        # lane alone is the same shape as an enforced run's log. It is written
        # first so that FR96's divergence falls *between* two host decisions
        # rather than inside one.
        self._append("budget-reserved", step_id=call.step_id)
        self._append(
            "decision-recorded",
            step_id=call.step_id,
            policy_action="proceed",
            decision_reason="justified",
        )

        counterfactual: tuple[str, str] | None = None
        if not self._sealed:
            self._append("decision-proposed", step_id=call.step_id, lane="counterfactual")
            counterfactual = self._would_have(call, unmet_mandatory, step_is_enrichment)
            self._append(
                "decision-recorded",
                step_id=call.step_id,
                lane="counterfactual",
                policy_action=counterfactual[0],
                decision_reason=counterfactual[1],
            )

        result = self.tools.invoke(call)
        self.governor.observe(call, result.output)
        self._append("outcome-observed", step_id=call.step_id)
        self._append("spend-settled", step_id=call.step_id, tokens_consumed=tokens)

        if counterfactual is not None and counterfactual[0] == "proceed":
            self._append(
                "spend-settled",
                step_id=call.step_id,
                lane="counterfactual",
                tokens_consumed=tokens,
            )

        if not self._sealed and should_evaluate(step_class):
            self._run_gate()

    def _would_have(
        self, call: ToolCall, unmet_mandatory: set[str] | None, step_is_enrichment: bool
    ) -> tuple[str, str]:
        """The governor's decision, reached without touching the host.

        The approval clause is read from the contract and answered here.
        `ToolGovernor.assess` is the only route to the `ApprovalPort`, and this
        returns before reaching it.
        """
        if self.governor.requires_approval(call) is not None:
            return "pause-for-approval", "approval-required"
        disposition = self.governor.assess(
            call,
            run_id=self.run_id,
            unmet_mandatory=unmet_mandatory,
            step_is_enrichment=step_is_enrichment,
        )
        return disposition.action, disposition.reason

    def _run_gate(self) -> None:
        deliverable = self.deliverable()
        if deliverable is None:
            return
        try:
            verdict = self.gate.evaluate(
                self.contract,
                deliverable,
                answer_key=self.answer_key(),
                citable_index=self._citable_index,
            )
        except GateUnavailable:
            # The enforcing driver halts here. This one records the halt it
            # would have imposed and lets the host carry on.
            self._seal("request-human", "fail-closed", "fail-closed")
            return

        self._append(
            "gate-verdict",
            lane="counterfactual",
            gate_verdict=verdict.verdict,
            verification_mode=verdict.qualifier,
            quality_state=verdict.verdict,
        )
        if verdict.passed:
            outcome = self.policy.resolve(
                Situation(floor_met=True, quality_state=verdict.verdict)
            )
            self._seal(
                outcome.policy_action,
                outcome.decision_reason,
                outcome.terminal_reason or "stop-sufficient",
            )

    def _seal(self, action: str, reason: str, terminal: str) -> None:
        self._append(
            "decision-recorded",
            lane="counterfactual",
            policy_action=action,
            decision_reason=reason,
            terminal_reason=terminal,
        )
        self._sealed = True

    # ------------------------------------------------------------- the end

    @property
    def counterfactual_sealed(self) -> bool:
        return self._sealed

    def close(self) -> None:
        """Close the host's run. No terminal reason: the governor ended nothing."""
        if self.closed:
            return
        self._append("run-closed")
        self.closed = True

    def report(self) -> ShadowReport:
        return build_shadow_report(self.store.events(self.run_id))

    # ------------------------------------------------- supplied by the host

    def deliverable(self) -> Mapping[str, Any] | None:
        return None

    def answer_key(self) -> Mapping[str, Any] | None:
        return None
