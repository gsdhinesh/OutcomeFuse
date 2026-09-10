"""The model port (AD-13).

LiteLLM sits **behind** this: no LiteLLM type, exception or cost table appears
above the port. The scripted implementation exists because the conformance
battery and FR100's failure cases must be deterministic, and a live model would
make them neither reproducible nor free.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field


class ModelRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    model_id: str = Field(min_length=1)
    prompt: str
    max_output_tokens: int = Field(gt=0)
    #: Barred on the evidence path: the gateway estimates token counts when
    #: streaming is on, which would make reconciliation a comparison of guesses.
    stream: bool = False


class ModelResponse(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    model_id: str
    text: str
    prompt_tokens: int = Field(ge=0)
    completion_tokens: int = Field(ge=0)

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


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
