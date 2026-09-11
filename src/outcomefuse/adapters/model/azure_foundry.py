"""The live model adapter for Azure Foundry (AD-13).

Everything provider-specific stops here. Above this module the system knows
about `ModelRequest` and `ModelResponse` and nothing else, which is what lets
the conformance battery and every failure case run against a scripted port for
free while the benchmark runs against a real one.

**A deviation worth stating.** BUILD-ORDER names LiteLLM for this seam. The
deployment this project has exposes the `/openai/v1` surface, which the OpenAI
SDK addresses directly and which LiteLLM's Azure route would have to have its
path construction talked out of. AD-13's invariant is that the seam is *owned*,
not that a particular library sits behind it, and swapping the library later
touches this file alone. The SDK is used directly for that reason.

Three things are enforced here rather than trusted to a caller:

- **Streaming is refused**, because the gateway estimates token counts when it
  is on and FR79's reconciliation would become a comparison of two guesses.
- **`temperature` and `top_p` are never sent.** Reasoning models reject them,
  and the frozen baseline definition records that they are unavailable rather
  than pretending a value was applied.
- **Usage is read, never estimated.** Reasoning tokens come from the response's
  own accounting and are counted as the output tokens they are billed as.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any, Final

from ...ports.model import (
    Message,
    ModelRequest,
    ModelResponse,
    StreamingBarred,
    ToolInvocation,
)

#: The scope Foundry's `/openai/v1` surface expects for an Entra token. Not a
#: secret: it names an audience, and the credential is fetched at call time.
TOKEN_SCOPE: Final[str] = "https://ai.azure.com/.default"  # noqa: S105


class ModelPortError(RuntimeError):
    """The provider could not be reached or answered unusably."""


def default_token_provider() -> Callable[[], str]:
    """A bearer-token provider from whatever credential the machine has.

    The Azure CLI is tried **before** `DefaultAzureCredential`, which is not the
    usual order and is deliberate. A machine can advertise a managed-identity
    endpoint it cannot actually reach — `IDENTITY_ENDPOINT` and `MSI_ENDPOINT`
    left pointing at localhost by some other tool — and the default chain then
    fails on the connection and stops, never reaching the signed-in CLI. Both
    are chained rather than either being chosen, so a deployment with a real
    managed identity still works.

    Imported lazily: a machine running the deterministic suite needs neither
    `azure-identity` nor a credential, and requiring them would make the core's
    tests depend on being logged in to a cloud.
    """
    try:
        from azure.identity import (
            AzureCliCredential,
            ChainedTokenCredential,
            DefaultAzureCredential,
            get_bearer_token_provider,
        )
    except ImportError as exc:  # pragma: no cover - exercised by not installing it
        raise ModelPortError(
            "azure-identity is not installed. It is imported lazily so the suite "
            "runs without a credential on the machine; to reach a live deployment "
            "run: pip install openai azure-identity"
        ) from exc
    chain = ChainedTokenCredential(AzureCliCredential(), DefaultAzureCredential())
    return get_bearer_token_provider(chain, TOKEN_SCOPE)


class AzureFoundryModelPort:
    """Talks to one Foundry endpoint. One instance may serve several deployments.

    `deployments` maps the **logical** model id a contract names to the
    deployment that actually serves it. The mapping exists so the manifest can
    record what ran rather than what was asked for; where the two agree, as they
    do today, it is the identity.
    """

    def __init__(
        self,
        *,
        base_url: str,
        deployments: dict[str, str] | None = None,
        token_provider: Callable[[], str] | None = None,
        client: Any = None,
        timeout: float = 120.0,
    ) -> None:
        self.base_url = base_url.rstrip("/") + "/"
        self.deployments = dict(deployments or {})
        self.timeout = timeout
        self.calls: list[ModelRequest] = []
        self._client = client if client is not None else self._build_client(token_provider)

    def _build_client(self, token_provider: Callable[[], str] | None) -> Any:
        try:
            from openai import OpenAI
        except ImportError as exc:  # pragma: no cover - exercised by not installing it
            raise ModelPortError(
                "openai is not installed. It is imported lazily so the suite runs "
                "without it; to reach a live deployment run: "
                "pip install openai azure-identity"
            ) from exc
        provider = token_provider or default_token_provider()
        return OpenAI(base_url=self.base_url, api_key=provider, timeout=self.timeout)

    def deployment_for(self, model_id: str) -> str:
        return self.deployments.get(model_id, model_id)

    def complete(self, request: ModelRequest) -> ModelResponse:
        if request.stream:
            raise StreamingBarred(
                "streaming is barred on the evidence path: the gateway estimates both "
                "prompt and completion tokens when it is on"
            )
        self.calls.append(request)

        payload: dict[str, Any] = {
            "model": self.deployment_for(request.model_id),
            "messages": [_wire(message) for message in request.messages],
            # Reasoning models take `max_completion_tokens`; `max_tokens` is refused.
            "max_completion_tokens": request.max_output_tokens,
        }
        if request.reasoning_effort is not None:
            payload["reasoning_effort"] = request.reasoning_effort
        if request.tools:
            payload["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.parameters,
                    },
                }
                for tool in request.tools
            ]

        try:
            completion = self._client.chat.completions.create(**payload)
        except Exception as exc:
            # AD-20: a port failure reaches the driver as a decision input it can
            # route, never as a provider exception unwinding past the ladder.
            raise ModelPortError(f"the model call failed: {exc}") from exc

        return _read(completion, request)


def _wire(message: Message) -> dict[str, Any]:
    """One message in the provider's shape."""
    if message.role == "tool":
        return {
            "role": "tool",
            "tool_call_id": message.tool_call_id,
            "content": message.content,
        }
    if message.tool_calls:
        return {
            "role": "assistant",
            "content": message.content or None,
            "tool_calls": [
                {
                    "id": call.id,
                    "type": "function",
                    "function": {
                        "name": call.tool,
                        "arguments": json.dumps(call.arguments),
                    },
                }
                for call in message.tool_calls
            ],
        }
    return {"role": message.role, "content": message.content}


def _invocations(choice: Any) -> tuple[ToolInvocation, ...]:
    """Tool calls as the model asked for them.

    Unreadable arguments are carried rather than raised. A model that emits
    broken JSON for a tool call has failed the step, and that failure belongs
    to the arm that produced it — not to the harness, which would otherwise
    turn it into a crash.
    """
    raw = getattr(getattr(choice, "message", None), "tool_calls", None) or ()
    calls = []
    for index, call in enumerate(raw):
        function = getattr(call, "function", None)
        text = getattr(function, "arguments", "") or "{}"
        try:
            arguments = json.loads(text)
            malformed = None
            if not isinstance(arguments, dict):
                arguments, malformed = {}, f"arguments are a JSON {type(arguments).__name__}"
        except json.JSONDecodeError as exc:
            arguments, malformed = {}, f"arguments are not readable JSON: {exc.msg}"
        calls.append(
            ToolInvocation(
                id=getattr(call, "id", None) or f"call-{index}",
                tool=getattr(function, "name", "") or "unnamed",
                arguments=arguments,
                malformed=malformed,
            )
        )
    return tuple(calls)


def _read(completion: Any, request: ModelRequest) -> ModelResponse:
    """Map one provider response onto the port's own shape."""
    choice = completion.choices[0] if completion.choices else None
    text = (getattr(choice.message, "content", None) or "") if choice else ""
    usage = completion.usage

    details = getattr(usage, "completion_tokens_details", None)
    reasoning = int(getattr(details, "reasoning_tokens", 0) or 0) if details else 0
    completion_tokens = int(getattr(usage, "completion_tokens", 0) or 0)

    return ModelResponse(
        model_id=request.model_id,
        text=text,
        prompt_tokens=int(getattr(usage, "prompt_tokens", 0) or 0),
        completion_tokens=completion_tokens,
        # Clamped rather than trusted: a provider reporting more reasoning than
        # output would otherwise take the whole run down at validation.
        reasoning_tokens=min(reasoning, completion_tokens),
        tool_calls=_invocations(choice) if choice else (),
        provider_version=getattr(completion, "model", None),
        # The budget ran out mid-thought. Tokens were spent and no answer came
        # back, which is a failed step rather than an empty one.
        incomplete=bool(choice and getattr(choice, "finish_reason", None) == "length"),
    )
