"""The Loop Fuse: halt a run that is going nowhere (FR27, FR28).

A progress fingerprint per iteration covering evidence gained, task-state change
and quality delta. The run halts on repeated state, no new evidence across a
configured number of iterations, repeated tool arguments, or the contract's
iteration limit.

**Budget exhaustion is not a loop-fuse condition** — it terminates under FR92,
and conflating the two would file the product's central cost event as a stall.
"""

from __future__ import annotations

from typing import Any, Final

from pydantic import BaseModel, ConfigDict, Field

from ..canon import hash_structure

DEFAULT_STALE_ITERATIONS: Final[int] = 3

HaltReason = str


class Fingerprint(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    iteration: int = Field(ge=0)
    sha256: str
    evidence_count: int = Field(ge=0)
    quality_state: str


class LoopFuse:
    """One per run. Fed one fingerprint per iteration."""

    def __init__(
        self,
        *,
        max_iterations: int,
        stale_iterations: int = DEFAULT_STALE_ITERATIONS,
    ) -> None:
        if max_iterations < 1:
            raise ValueError("max_iterations must be at least 1")
        self.max_iterations = max_iterations
        self.stale_iterations = stale_iterations
        self.fingerprints: list[Fingerprint] = []
        self._tool_calls: set[str] = set()

    def fingerprint(
        self,
        *,
        iteration: int,
        task_state: Any,
        evidence_count: int,
        quality_state: str,
    ) -> Fingerprint:
        """Hash through AD-6's structure route, like everything else."""
        digest = hash_structure(
            {
                "task_state": task_state,
                "evidence_count": evidence_count,
                "quality_state": quality_state,
            }
        ).sha256
        return Fingerprint(
            iteration=iteration,
            sha256=digest,
            evidence_count=evidence_count,
            quality_state=quality_state,
        )

    def observe(self, fingerprint: Fingerprint) -> HaltReason | None:
        """Record an iteration; return a halt reason where one fires."""
        self.fingerprints.append(fingerprint)

        if any(f.sha256 == fingerprint.sha256 for f in self.fingerprints[:-1]):
            return "repeated-state"

        if len(self.fingerprints) > self.stale_iterations:
            window = self.fingerprints[-(self.stale_iterations + 1) :]
            if all(f.evidence_count == window[0].evidence_count for f in window):
                return "no-new-evidence"

        if fingerprint.iteration + 1 >= self.max_iterations:
            return "iteration-limit"

        return None

    def observe_tool_call(self, tool: str, arguments: Any) -> HaltReason | None:
        """Repeated tool arguments are a stall, not a cache concern."""
        key = hash_structure({"tool": tool, "arguments": arguments}).sha256
        if key in self._tool_calls:
            return "repeated-tool-arguments"
        self._tool_calls.add(key)
        return None
