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

from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ModelRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    model_id: str = Field(min_length=1)
    prompt: str
    max_output_tokens: int = Field(gt=0)
    #: Pinned by the frozen baseline definition and identical on both arms, so
    #: it cannot bias a comparison — only its variance and its cost.
    reasoning_effort: str | None = None
    #: Barred on the evidence path: the gateway estimates token counts when
    #: streaming is on, which would make reconciliation a comparison of guesses.
    stream: bool = False


class ModelResponse(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    model_id: str
    text: str
    prompt_tokens: int = Field(ge=0)
    completion_tokens: int = Field(ge=0)
    #: A subset of `completion_tokens`, never an addition to them.
    reasoning_tokens: int = Field(default=0, ge=0)
    #: What the service said it ran, for the manifest. Two arms differing here
    #: are not comparable (AD-9).
    provider_version: str | None = None
    #: The output budget ran out. Tokens were still spent.
    incomplete: bool = False

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
    """Deterministic responses, so a failure case reproduces exactly."""

    def __init__(self, replies: dict[str, str] | None = None, default: str = "") -> None:
        self._replies = dict(replies or {})
        self._default = default
        self.calls: list[ModelRequest] = []

    def complete(self, request: ModelRequest) -> ModelResponse:
        if request.stream:
            raise StreamingBarred("streaming is barred on the evidence path")
        self.calls.append(request)
        text = self._replies.get(request.prompt, self._default)
        return ModelResponse(
            model_id=request.model_id,
            text=text,
            prompt_tokens=max(1, len(request.prompt) // 4),
            completion_tokens=max(1, len(text) // 4),
        )
