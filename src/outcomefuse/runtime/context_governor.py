"""The Context Governor (F7, FR36-FR39), deterministic.

The baseline carries the whole transcript forward and appends every tool result
verbatim (BASELINE.md). That is the ordinary thing to do, and it is why a run
that reads one file ten times pays for that file ten times over: the body lands
in the transcript once per turn and every later prompt carries all of them. The
Tool Governor's cache stops the *tool* from running again; it does nothing about
the bytes, because it hands the stored result back and the loop appends it like
any other.

F7 as designed compresses tool output with a model pass, which is what put it at
cut position 7: it spends tokens to save tokens and it can drop a fact. **This
is the deterministic subset of it, and it does neither.** The only thing elided
is a body byte-identical to one already in the conversation, replaced by a
reference to itself. So:

- **FR38 is discharged structurally.** Nothing is summarised, shortened or
  judged. Every citation, identifier, figure and policy clause stays verbatim in
  the transcript — exactly once instead of once per turn.
- **FR39 is nil by construction.** There is no model pass, so there is no
  compression spend to attribute.
- **FR33 still binds.** A tool declared side-effecting or non-deterministic is
  never elided: two identical readings from a tool that may change its answer
  are two facts, not one fact twice.

Run-scoped and process-local, like the tool cache it sits beside (AD-14).
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from ..core.canon import hash_structure
from ..core.contract import Contract
from ..ports import ToolCall
from .tool_governor import optimisable


def estimate_tokens(payload: Any) -> int:
    """Four characters to the token. An estimate, and never called anything else.

    Nothing in this module bills, reserves or reports against this number; it
    exists so a decision row can say roughly how much text it kept out of the
    next prompt. The measured figure is the prompt-token count the provider
    returns, which falls on its own once the duplicate is gone.
    """
    return max(1, len(_as_text(payload)) // 4)


def _as_text(payload: Any) -> str:
    return payload if isinstance(payload, str) else repr(payload)


class Placement(BaseModel):
    """What the driver should put in the transcript for one tool result."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    elided: bool
    payload: Any = None
    #: The result itself, canonicalised. What the run *learned*, as opposed to
    #: how it was phrased to the model: the Loop Fuse wants the first, and an
    #: elided turn and the turn it points at have to agree on it or the fuse
    #: reads the elision as progress and grants the stall another turn.
    digest: str = ""
    #: The step whose transcript entry already carries these bytes, verbatim.
    first_seen_at: str = ""
    estimated_tokens_avoided: int = Field(default=0, ge=0)

    @property
    def detail(self) -> str:
        return (
            f"identical to the result already in this conversation at {self.first_seen_at}; "
            f"the reference was sent instead of the body, about "
            f"{self.estimated_tokens_avoided:,} tokens of it, and every later turn "
            "carries the reference rather than a second copy"
        )


class ContextGovernor:
    """One per run. Holds what has already been placed in this transcript."""

    def __init__(self, contract: Contract) -> None:
        self._tools = {tool.name: tool for tool in contract.tools}
        self._placed: dict[str, tuple[str, str]] = {}
        self.elisions = 0
        self.estimated_tokens_avoided = 0

    def place(self, call: ToolCall, result: Any, *, step_id: str = "") -> Placement:
        """Decide what goes into the transcript for this result."""
        declared = self._tools.get(call.tool)
        if declared is None or not optimisable(declared):
            return Placement(elided=False, payload=result)

        digest = hash_structure({"result": result}).sha256
        seen = self._placed.get(digest)
        if seen is None:
            self._placed[digest] = (step_id or call.step_id, _describe(call))
            return Placement(elided=False, payload=result, digest=digest)

        first_step, first_call = seen
        avoided = estimate_tokens(result)
        self.elisions += 1
        self.estimated_tokens_avoided += avoided
        placement = Placement(
            elided=True,
            digest=digest,
            first_seen_at=f"{first_call} on turn {first_step}" if first_step else first_call,
            estimated_tokens_avoided=avoided,
        )
        return placement.model_copy(
            update={
                "payload": {
                    "context_governor": "identical-result-not-repeated",
                    "identical_to": placement.first_seen_at,
                    "note": "the full result is unchanged and is already in this "
                    "conversation; it is not repeated here",
                }
            }
        )


def _describe(call: ToolCall) -> str:
    arguments = ", ".join(f"{k}={v!r}" for k, v in sorted(call.arguments.items()))
    return f"{call.tool}({arguments})"
