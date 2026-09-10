"""The tool port, and the probe that does not trust the log (AD-15).

Enforcement is **cooperative** by AD-1's construction: the adapter, not the
governor, applies the verdict. So an adapter that executes a denied or gated
call while recording a clean pause produces a plausible, internally consistent
and entirely false audit trail — and every claim then rests on it.

**A decision record cannot detect the one failure it is the evidence for.** The
probe is therefore out of band: scripted tools assert for themselves whether
they were invoked, and the battery compares that against what the log claims.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field


class ToolCall(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    tool: str = Field(min_length=1)
    arguments: dict[str, Any] = Field(default_factory=dict)
    step_id: str = Field(min_length=1)


class ToolResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    tool: str
    output: Any
    tokens: int = Field(default=0, ge=0)


@runtime_checkable
class ToolPort(Protocol):
    def invoke(self, call: ToolCall) -> ToolResult: ...


class ProbedToolPort:
    """Records every invocation independently of the decision log.

    The recording lives here rather than in the driver on purpose: a driver that
    would falsify the log is exactly the driver that would falsify a record it
    also owns.
    """

    def __init__(self, handlers: dict[str, Callable[[ToolCall], Any]] | None = None) -> None:
        self._handlers = dict(handlers or {})
        self._invocations: list[ToolCall] = []

    def invoke(self, call: ToolCall) -> ToolResult:
        self._invocations.append(call)
        handler = self._handlers.get(call.tool)
        output = handler(call) if handler is not None else None
        return ToolResult(tool=call.tool, output=output)

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
