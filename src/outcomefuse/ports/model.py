"""The model port (AD-13).

The provider sits **behind** this: no provider type, exception or cost table
appears above the port. The scripted implementation exists because the
conformance battery and FR100's failure cases must be deterministic, and a live
model would make them neither reproducible nor free.

The frozen baseline definition runs a **reasoning** model, which shapes this
seam in two ways worth stating out loud:

- **Reasoning tokens are output tokens.** They are billed as output and are
  counted in the spend of whichever arm incurred them. They are reported
  separately here only so the measurement can *show* them, never so it can
  exclude them.
- **A capped response can cost money and return nothing.** Exhausting the
  output budget on reasoning alone yields a successful HTTP call with no text.
  That is a failure of the arm that produced it, so the response carries the
  fact rather than looking like an empty answer.

There is deliberately no `temperature` here. Reasoning models reject it, and a
field the port could not honour would be a setting someone would later believe.
"""

from __future__ import annotations

from typing import Any, Literal, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, model_validator

Role = Literal["system", "user", "assistant", "tool"]


class ToolSchema(BaseModel):
    """One tool as the model is told about it.

    The frozen task block names the tools in prose but specifies no call
    format, and it cannot be added to — both arms send it byte-identical. So
    the invocation protocol is the provider's own, and this is what declares
    it. The names here come from the contract, so a tool the contract does not
    declare cannot be offered.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(min_length=1)
    description: str = ""
    parameters: dict[str, Any] = Field(default_factory=dict)


class ToolInvocation(BaseModel):
    """A tool call the model asked for, as it came back."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(min_length=1)
    tool: str = Field(min_length=1)
    arguments: dict[str, Any] = Field(default_factory=dict)
    #: The model asked for a tool call whose arguments were not readable JSON.
    #: Carried rather than raised: it is the agent's failure, not the harness's.
    malformed: str | None = None


class Message(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    role: Role
    content: str = ""
    #: Set on a `tool` message, naming the call it answers.
    tool_call_id: str | None = None
    #: Set on an `assistant` message that asked for tools.
    tool_calls: tuple[ToolInvocation, ...] = ()


def user_turn(prompt: str, *, system: str | None = None) -> tuple[Message, ...]:
    """The simple one-shot conversation, for callers with nothing to carry."""
    opening = (Message(role="system", content=system),) if system else ()
    return (*opening, Message(role="user", content=prompt))


class ModelRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    model_id: str = Field(min_length=1)
    #: The whole working transcript. FR64's context policy carries it forward
    #: without compression or eviction, which is the thing the Context Governor
    #: exists to improve on — so the baseline must actually do it.
    messages: tuple[Message, ...] = Field(min_length=1)
    max_output_tokens: int = Field(gt=0)
    tools: tuple[ToolSchema, ...] = ()
    #: Pinned by the frozen baseline definition and identical on both arms, so
    #: it cannot bias a comparison — only its variance and its cost.
    reasoning_effort: str | None = None
    #: Barred on the evidence path: the gateway estimates token counts when
    #: streaming is on, which would make reconciliation a comparison of guesses.
    stream: bool = False

    @property
    def prompt(self) -> str:
        """The conversation as one string, for a port that takes no messages."""
        return "\n\n".join(m.content for m in self.messages if m.content)


class ModelResponse(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    model_id: str
    text: str
    prompt_tokens: int = Field(ge=0)
    completion_tokens: int = Field(ge=0)
    #: A subset of `completion_tokens`, never an addition to them.
    reasoning_tokens: int = Field(default=0, ge=0)
    #: What the model asked to call. Empty means it answered instead.
    tool_calls: tuple[ToolInvocation, ...] = ()
    #: What the service said it ran, for the manifest. Two arms differing here
    #: are not comparable (AD-9).
    provider_version: str | None = None
    #: The output budget ran out. Tokens were still spent.
    incomplete: bool = False

    @property
    def wants_tools(self) -> bool:
        return bool(self.tool_calls)

    @model_validator(mode="after")
    def _reasoning_is_part_of_output(self) -> ModelResponse:
        if self.reasoning_tokens > self.completion_tokens:
            raise ValueError(
                f"{self.reasoning_tokens} reasoning tokens exceeds "
                f"{self.completion_tokens} completion tokens; reasoning is billed as "
                "output and is part of that total, not additional to it"
            )
        return self

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens

    @property
    def visible_tokens(self) -> int:
        """Output the caller can actually read. The rest was thinking."""
        return self.completion_tokens - self.reasoning_tokens


class StreamingBarred(ValueError):
    """Streaming was requested on the evidence path."""


@runtime_checkable
class ModelPort(Protocol):
    def complete(self, request: ModelRequest) -> ModelResponse: ...


class ScriptedModelPort:
    """Deterministic responses, so a failure case reproduces exactly.

    A reply may be a string or a list of `ToolInvocation`s, which is how a
    whole multi-step run is scripted without a network or a bill.
    """

    def __init__(
        self,
        replies: dict[str, str] | None = None,
        default: str = "",
        turns: list[str | tuple[ToolInvocation, ...]] | None = None,
    ) -> None:
        self._replies = dict(replies or {})
        self._default = default
        #: Consumed one per call, so a scripted run can ask for tools and then
        #: answer, which is the shape every real run takes.
        self._turns = list(turns or [])
        self.calls: list[ModelRequest] = []

    def complete(self, request: ModelRequest) -> ModelResponse:
        if request.stream:
            raise StreamingBarred("streaming is barred on the evidence path")
        self.calls.append(request)

        if self._turns:
            turn = self._turns.pop(0)
            if isinstance(turn, str):
                return self._answer(request, turn)
            return ModelResponse(
                model_id=request.model_id,
                text="",
                prompt_tokens=max(1, len(request.prompt) // 4),
                completion_tokens=1,
                tool_calls=tuple(turn),
            )

        return self._answer(request, self._replies.get(request.prompt, self._default))

    def _answer(self, request: ModelRequest, text: str) -> ModelResponse:
        return ModelResponse(
            model_id=request.model_id,
            text=text,
            prompt_tokens=max(1, len(request.prompt) // 4),
            completion_tokens=max(1, len(text) // 4),
        )
