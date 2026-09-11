"""The tool port the workloads share (AD-15, FR33).

One dispatcher, one handler table per workload. The table's keys are the tool
names the **frozen contract** declares, and a mismatch is refused at
construction rather than surfacing mid-run as an unknown tool.

Two properties are enforced here because the rest of the system is entitled to
assume them:

- **A tool the contract calls deterministic must be deterministic.** The Tool
  Governor caches and deduplicates on exactly that word, so a "deterministic"
  tool that drifts makes the cache serve wrong answers and FR33's whole model
  collapses quietly.
- **Both arms get the same tools.** The baseline and the governed run draw from
  one implementation, so nothing done here can flatter the governor without
  flattering its control identically. Tool implementations are not frozen, and
  this is the property that keeps that from mattering.

Invocations are recorded the way `ProbedToolPort` records them, so AD-15's
out-of-band probe works against a real workload and not only against fixtures.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from ..core.contract import Contract
from ..ports import ToolCall, ToolResult

Handler = Callable[[dict[str, Any]], Any]


class ToolError(RuntimeError):
    """The tool could not answer. Never a silently empty result."""


class WorkloadToolPort:
    """Serves one workload's declared tools from its corpus."""

    def __init__(
        self,
        *,
        contract: Contract,
        handlers: dict[str, Handler],
        side_effects: list[str] | None = None,
    ) -> None:
        declared = {tool.name for tool in contract.tools}
        missing = sorted(declared - set(handlers))
        unknown = sorted(set(handlers) - declared)
        if missing or unknown:
            raise ToolError(
                f"the handler table does not match the contract's tools: "
                f"missing {missing}, undeclared {unknown}"
            )
        self.contract = contract
        self._handlers = dict(handlers)
        #: What the side-effecting tools actually did, observable out of band.
        self.side_effects: list[str] = side_effects if side_effects is not None else []
        self._invocations: list[ToolCall] = []

    def invoke(self, call: ToolCall) -> ToolResult:
        self._invocations.append(call)
        handler = self._handlers.get(call.tool)
        if handler is None:
            raise ToolError(f"tool {call.tool!r} is not declared by the contract")
        return ToolResult(tool=call.tool, output=handler(dict(call.arguments)))

    # ------------------------------------------------------------- the probe

    @property
    def invocations(self) -> tuple[ToolCall, ...]:
        return tuple(self._invocations)

    def was_invoked(self, tool: str, *, step_id: str | None = None) -> bool:
        return any(
            call.tool == tool and (step_id is None or call.step_id == step_id)
            for call in self._invocations
        )

    def invocation_count(self, tool: str) -> int:
        return sum(1 for call in self._invocations if call.tool == tool)


def required(arguments: dict[str, Any], name: str) -> Any:
    try:
        return arguments[name]
    except KeyError:
        raise ToolError(f"missing required argument {name!r}") from None
