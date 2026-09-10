"""The Tool Governor (F6, FR29-FR35, AD-14).

The rule that shapes this module is FR33: **no optimisation-driven suppression
applies to tools declared side-effecting or non-deterministic.** Caching,
exact deduplication and semantic deduplication are all optimisations and are all
excluded. Denials grounded in safety, affordability or a human-approval
requirement are *not* optimisations and still apply.

    Refusing to cache a payment call is correct; refusing to *stop* a payment
    call that is unaffordable or unapproved would not be.

So the tool's declaration is consulted before any optimisation is considered,
and the check is structural rather than a condition someone can forget.

The cache is **run-scoped and process-local** (AD-14). No cross-run,
cross-process or persistent cache exists, which discharges tenant isolation by
construction rather than by policy.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from ..core.canon import hash_structure
from ..core.contract import Contract
from ..ports import ApprovalPort, ApprovalRequest, ToolCall

Action = Literal["proceed", "proceed-with-substitution", "deny", "pause-for-approval"]


class ToolGovernorError(RuntimeError):
    """The governor could not decide. Never a silent proceed."""


class Disposition(BaseModel):
    """What happens to one proposed tool call, and why (FR35)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    action: Action
    reason: str
    key: str
    cached_result: Any = None
    #: FR89: an unavailable approval channel is fail-closed, not a denial.
    channel_unavailable: bool = False
    detail: str = ""

    @property
    def executes(self) -> bool:
        return self.action == "proceed"


def canonical_key(call: ToolCall) -> str:
    """FR29: tool name and arguments canonicalised into a stable key.

    Through AD-6's one canonicaliser, so `1` and `1.0` cannot produce two keys
    for the same call and the governor and the harness cannot disagree.
    """
    return hash_structure({"arguments": call.arguments, "tool": call.tool}).sha256


class ToolGovernor:
    """One per run. Holds the run-scoped cache."""

    def __init__(self, contract: Contract, approval: ApprovalPort | None = None) -> None:
        self._tools = {tool.name: tool for tool in contract.tools}
        self._approvals = tuple(contract.human_approval_conditions)
        self._timeout = contract.approval_timeout_seconds or 60
        self._approval_port = approval
        self._cache: dict[str, Any] = {}
        self._seen: set[str] = set()
        self.records: list[Disposition] = []

    # ---------------------------------------------------------------- checks

    def _declaration(self, tool: str):
        try:
            return self._tools[tool]
        except KeyError:
            raise ToolGovernorError(f"tool {tool!r} is not declared by the contract") from None

    def optimisable(self, tool: str) -> bool:
        """FR33, as one predicate rather than three scattered conditions."""
        declared = self._declaration(tool)
        return declared.deterministic and not declared.side_effecting

    def requires_approval(self, call: ToolCall) -> str | None:
        """The triggering clause, or None."""
        for condition in self._approvals:
            if condition.tool == call.tool and condition.when == "always":
                return f"human_approval_conditions[{self._approvals.index(condition)}]"
        return None

    # ---------------------------------------------------------------- assess

    def assess(
        self,
        call: ToolCall,
        *,
        run_id: str,
        unmet_mandatory: set[str] | None = None,
        step_is_enrichment: bool = False,
    ) -> Disposition:
        key = canonical_key(call)
        self._declaration(call.tool)

        # Approval outranks every automated decision below it, and applies to
        # side-effecting tools precisely because they are side-effecting.
        clause = self.requires_approval(call)
        if clause is not None:
            disposition = self._seek_approval(call, key, clause, run_id)
            if disposition is not None:
                return self._record(disposition)

        if not self.optimisable(call.tool):
            # FR33: no cache, no dedup, no optional-satisfied denial. The call
            # happens unless something non-optimisation stopped it above.
            return self._record(
                Disposition(
                    action="proceed",
                    reason="justified",
                    key=key,
                    detail="declared side-effecting or non-deterministic, so exempt "
                    "from optimisation-driven suppression",
                )
            )

        if key in self._cache:
            return self._record(
                Disposition(
                    action="proceed-with-substitution",
                    reason="cache-hit",
                    key=key,
                    cached_result=self._cache[key],
                )
            )

        if key in self._seen:
            return self._record(Disposition(action="deny", reason="duplicate", key=key))

        # FR31: enrichment calls are denied once every mandatory criterion is met.
        if step_is_enrichment and not unmet_mandatory:
            return self._record(
                Disposition(action="deny", reason="optional-satisfied", key=key)
            )

        return self._record(Disposition(action="proceed", reason="justified", key=key))

    def _seek_approval(
        self, call: ToolCall, key: str, clause: str, run_id: str
    ) -> Disposition | None:
        if self._approval_port is None:
            # FR89: the condition cannot be evaluated, so the gated call is not made.
            return Disposition(
                action="pause-for-approval",
                reason="approval-required",
                key=key,
                channel_unavailable=True,
                detail="no approval channel is available",
            )
        outcome = self._approval_port.request(
            ApprovalRequest(
                run_id=run_id,
                step_id=call.step_id,
                tool=call.tool,
                clause=clause,
                timeout_seconds=self._timeout,
            )
        )
        if outcome.decision == "approved":
            return None  # fall through to the ordinary path
        if outcome.is_channel_failure:
            return Disposition(
                action="pause-for-approval",
                reason="approval-required",
                key=key,
                channel_unavailable=True,
                detail="the approval channel is unavailable",
            )
        reason = "approval-denied" if outcome.decision == "denied" else "approval-timeout"
        return Disposition(action="pause-for-approval", reason=reason, key=key, detail=clause)

    # ----------------------------------------------------------------- after

    def observe(self, call: ToolCall, result: Any) -> None:
        """Record an executed call. Only optimisable tools enter the cache."""
        key = canonical_key(call)
        self._seen.add(key)
        if self.optimisable(call.tool):
            self._cache[key] = result

    def _record(self, disposition: Disposition) -> Disposition:
        self.records.append(disposition)
        return disposition

    @property
    def cache_size(self) -> int:
        return len(self._cache)
