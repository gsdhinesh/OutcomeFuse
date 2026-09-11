"""Reading the agent's final answer out of what the model actually said.

The frozen templates ask for "a single JSON object" and "Emit only the JSON
object". Models comply imperfectly: a fenced block, a sentence of preamble, a
trailing offer to help further. This extracts the object from that.

**Nothing here repairs malformed JSON.** No quote fixing, no trailing-comma
tolerance, no asking a model to try again. Repair would be the harness
improving the agent's output, and it would improve it most for whichever arm
produced the worse output — which is a thumb on the scale in whichever
direction happens to help. An agent that cannot emit the shape it was asked for
has failed the case, and that failure belongs to the arm that produced it.

**A parse failure is a result, not an exception.** It is returned, recorded and
gated like any other outcome. Raising here would let "the model emitted prose"
unwind past the ladder and out of the run, turning a case the agent failed into
a case the harness crashed on.
"""

from __future__ import annotations

import json
import re
from typing import Any, Final

from pydantic import BaseModel, ConfigDict, Field

#: Long enough for any deliverable the templates ask for, short enough that a
#: runaway response cannot make parsing the expensive part of a run.
MAX_TEXT: Final[int] = 256 * 1024

#: What the templates permit instead of an answer, on every case and
#: load-bearing on a few.
INSUFFICIENT_EVIDENCE: Final[str] = "insufficient_evidence"

_FENCE = re.compile(r"```(?:json)?\s*\n(.*?)\n```", re.S)


class Parsed(BaseModel):
    """The outcome of reading one response. Always returned, never raised."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    ok: bool
    deliverable: dict[str, Any] | None = None
    #: Why it could not be read, in terms a decision record can carry.
    failure: str | None = None
    #: Which strategy found it. Recorded because "the model fenced its JSON" and
    #: "the model buried it in prose" are different behaviours, and the
    #: difference between the arms is worth being able to see.
    found_by: str | None = None

    @property
    def claims_insufficient_evidence(self) -> bool:
        """The agent said the corpus cannot answer. A verdict, not a failure."""
        return bool(self.deliverable and self.deliverable.get(INSUFFICIENT_EVIDENCE))


def _candidates(text: str) -> list[tuple[str, str]]:
    """Every plausible JSON span, in the order they should be tried."""
    stripped = text.strip()
    found: list[tuple[str, str]] = [("whole-response", stripped)]
    found += [("fenced-block", block.strip()) for block in _FENCE.findall(text)]
    span = _outermost_object(stripped)
    if span is not None:
        found.append(("embedded-object", span))
    return found


def _outermost_object(text: str) -> str | None:
    """The first brace-balanced object in the text, ignoring braces in strings."""
    start = text.find("{")
    if start < 0:
        return None
    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    return None


def parse_deliverable(text: str) -> Parsed:
    """Read the deliverable, or say why it could not be read."""
    if text is None or not text.strip():
        return Parsed(ok=False, failure="the model returned no text")
    if len(text) > MAX_TEXT:
        return Parsed(
            ok=False, failure=f"the response exceeds {MAX_TEXT} bytes and was not parsed"
        )

    for strategy, candidate in _candidates(text):
        if not candidate:
            continue
        try:
            loaded = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(loaded, dict):
            return Parsed(ok=True, deliverable=loaded, found_by=strategy)
        # Valid JSON of the wrong shape. Reaching inside it for an object — the
        # single element of an array, say — would override a structural choice
        # the model made, which is a different thing from stripping prose off
        # something already well formed. So this stops here rather than trying
        # the remaining strategies.
        return Parsed(
            ok=False,
            failure=f"the response is a JSON {type(loaded).__name__}, not the single "
            "object the template asked for; it is not reached into, because that "
            "would override the shape the model chose",
        )

    return Parsed(
        ok=False,
        failure="no JSON object could be read from the response; it is not repaired, "
        "because repairing it would improve whichever arm emitted the worse output",
    )


class Transcript(BaseModel):
    """One run's conversation, carried forward whole (FR64's context policy)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    entries: tuple[str, ...] = Field(default_factory=tuple)

    def with_entry(self, entry: str) -> Transcript:
        return Transcript(entries=(*self.entries, entry))

    def rendered(self) -> str:
        return "\n\n".join(self.entries)
