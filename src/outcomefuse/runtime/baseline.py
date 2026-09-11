"""The baseline recorder (FR52, AD-10).

The third peer to `Driver` and `ShadowDriver`. The driver enforces; the shadow
driver observes a counterfactual; this one records an ungoverned run so that it
can be *compared* to a governed one.

FR52's baseline has no governor, and it does not get one here by the back door:
this class holds no Policy, no Ledger, no ToolGovernor and no LoopFuse. It makes
no decision, denies nothing, and cannot terminate a run. Every tool the agent
asks for, it gets.

But a baseline with no record is not evidence of anything. Admissibility is
checked against a `RunManifest` for *both* arms, and a paired case carries both
arms' seals, so an unrecorded baseline cannot be paired, cannot be admitted, and
cannot support a claim. Recording is measurement, not governance.

**The gate scores the baseline; it never steers it.** The governed arm consults
the gate at each evidence step and may stop on sufficiency — that is the
mechanism under test. Here the gate runs exactly once, after the agent has
already stopped of its own accord, and its verdict changes nothing that
happened. Same gate, same contract, same answer key: quality must be measured
identically on both arms or the comparison means nothing. Letting it run early
here would hand the baseline the very mechanism the experiment exists to
isolate.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ..core.contract import Contract
from ..core.gate import GateUnavailable, QualityGate, Verdict
from ..core.record import Event, RecordStore
from ..core.verify import CitableIndex
from ..ports import ToolCall

WHEN = "2026-09-10T12:00:00Z"


class BaselineRecorder:
    """Writes down what an ungoverned run did. Decides nothing."""

    def __init__(
        self,
        *,
        run_id: str,
        contract: Contract,
        store: RecordStore,
        gate: QualityGate | None = None,
        citable_index: CitableIndex | None = None,
    ) -> None:
        self.run_id = run_id
        self.contract = contract
        self.store = store
        self.gate = gate or QualityGate()
        self.citable_index = citable_index
        self.verdict: Verdict | None = None
        self.closed = False
        self._seq = 0

    def _append(self, kind: str, **fields: Any) -> Event:
        event = Event(run_id=self.run_id, seq=self._seq, kind=kind, recorded_at=WHEN, **fields)
        self.store.append(event)
        self._seq += 1
        return event

    def open_run(self, manifest: Any) -> None:
        if getattr(manifest, "mode", None) != "baseline":
            raise ValueError(
                f"this recorder writes baseline runs; the manifest says "
                f"{getattr(manifest, 'mode', None)!r}"
            )
        self.store.open_run(manifest, recorded_at=WHEN)
        self._seq = 1

    def observe_model_turn(self, *, step_id: str, tokens: int, model_used: str) -> None:
        """A model call happened. No affordability was asked, because nothing governs."""
        self._append(
            "spend-settled", step_id=step_id, tokens_consumed=tokens, model_used=model_used
        )

    def observe_tool(self, call: ToolCall, *, failed: str | None = None) -> None:
        """A tool ran, or broke. Either way it was allowed: nothing here can deny."""
        self._append("evidence-requested", step_id=call.step_id, payload={"tool": call.tool})
        self._append(
            "outcome-observed",
            step_id=call.step_id,
            payload={"tool": call.tool, **({"tool_error": failed} if failed else {})},
        )

    def score(
        self,
        deliverable: Mapping[str, Any] | None,
        *,
        answer_key: Mapping[str, Any] | None = None,
        parse_failure: str | None = None,
    ) -> Verdict | None:
        """Run the gate once, for the score. Nothing about the run changes.

        A deliverable that never arrived is recorded as a fail rather than left
        blank: absent and failing are the same outcome for the agent, and a
        blank would be silently dropped from the pass counts instead of counted
        against the arm that produced it.
        """
        if deliverable is None:
            self._append(
                "gate-verdict",
                gate_verdict="fail",
                quality_state="fail",
                payload={"detail": parse_failure or "no deliverable was produced"},
            )
            self._close()
            return None

        try:
            self.verdict = self.gate.evaluate(
                self.contract,
                deliverable,
                answer_key=answer_key,
                citable_index=self.citable_index,
            )
        except GateUnavailable as exc:
            # Not fail-closed: there is nothing to close. An unavailable gate on
            # this arm means the pair cannot be scored, which the campaign must
            # see rather than have quietly resolved into a failing baseline.
            self._append("gate-verdict", payload={"unavailable": str(exc)})
            self._close()
            raise

        self._append(
            "gate-verdict",
            gate_verdict=self.verdict.verdict,
            verification_mode=self.verdict.qualifier,
            quality_state=self.verdict.verdict,
        )
        self._close()
        return self.verdict

    def _close(self) -> None:
        if self.closed:
            return
        self._append("run-closed")
        self.closed = True

    def seal(self) -> str | None:
        return self.store.seal(self.run_id)
