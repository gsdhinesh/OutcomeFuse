"""The live model adapter (AD-13, AD-16, FR79).

Tested against a fake client rather than the endpoint. A test that needs a
credential and a network is a test that gets skipped, and the things worth
checking here — that streaming is refused, that `temperature` is never sent,
that reasoning tokens are counted rather than dropped — are all properties of
the request we build and the response we read, not of the service.

The live smoke test lives in `scripts/`, is run deliberately, and costs money.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from outcomefuse.adapters.model import AzureFoundryModelPort, ModelPortError
from outcomefuse.ports import ModelRequest, ModelResponse, StreamingBarred

BASE = "https://outcomefuse-foundry.services.ai.azure.com/openai/v1"


def a_completion(
    *,
    text: str = "an answer",
    prompt_tokens: int = 29,
    completion_tokens: int = 2919,
    reasoning_tokens: int = 1792,
    finish_reason: str = "stop",
    model: str = "gpt-5-2025-08-07",
):
    """Shaped like Microsoft's own documented response."""
    return SimpleNamespace(
        model=model,
        choices=[
            SimpleNamespace(
                finish_reason=finish_reason,
                message=SimpleNamespace(content=text),
            )
        ],
        usage=SimpleNamespace(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            completion_tokens_details=SimpleNamespace(reasoning_tokens=reasoning_tokens),
        ),
    )


class FakeClient:
    def __init__(self, completion=None, raises: Exception | None = None) -> None:
        self._completion = completion if completion is not None else a_completion()
        self._raises = raises
        self.payloads: list[dict] = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **payload):
        self.payloads.append(payload)
        if self._raises is not None:
            raise self._raises
        return self._completion


def a_port(client: FakeClient | None = None, **over) -> AzureFoundryModelPort:
    return AzureFoundryModelPort(
        base_url=BASE, client=client if client is not None else FakeClient(), **over
    )


def a_request(**over) -> ModelRequest:
    base = {
        "model_id": "gpt-5",
        "prompt": "What is the capital of France?",
        "max_output_tokens": 25000,
        "reasoning_effort": "medium",
    }
    return ModelRequest(**(base | over))


class TestWhatItRefusesToSend:
    def test_streaming_is_barred_at_the_port(self):
        # FR79 would otherwise reconcile two estimates against each other.
        client = FakeClient()
        with pytest.raises(StreamingBarred, match="barred on the evidence path"):
            a_port(client).complete(a_request(stream=True))
        assert client.payloads == []

    def test_temperature_and_top_p_are_never_sent(self):
        # Reasoning models reject them, and the frozen baseline definition
        # records them as unavailable rather than pretending a value applied.
        client = FakeClient()
        a_port(client).complete(a_request())
        assert "temperature" not in client.payloads[0]
        assert "top_p" not in client.payloads[0]

    def test_there_is_no_temperature_to_send(self):
        with pytest.raises(ValidationError):
            ModelRequest(
                model_id="gpt-5", prompt="x", max_output_tokens=100, temperature=0
            )

    def test_the_output_budget_uses_the_parameter_reasoning_models_accept(self):
        client = FakeClient()
        a_port(client).complete(a_request(max_output_tokens=25000))
        assert client.payloads[0]["max_completion_tokens"] == 25000
        assert "max_tokens" not in client.payloads[0]

    def test_reasoning_effort_travels_when_set_and_not_when_absent(self):
        client = FakeClient()
        port = a_port(client)
        port.complete(a_request(reasoning_effort="minimal"))
        port.complete(a_request(reasoning_effort=None))
        assert client.payloads[0]["reasoning_effort"] == "minimal"
        assert "reasoning_effort" not in client.payloads[1]


class TestWhatItReadsBack:
    def test_reasoning_tokens_are_counted_not_dropped(self):
        # They are billed as output. Excluding them would understate both arms
        # and flatter whichever one thinks less.
        response = a_port().complete(a_request())
        assert response.completion_tokens == 2919
        assert response.reasoning_tokens == 1792
        assert response.visible_tokens == 1127
        assert response.total_tokens == 2948

    def test_reasoning_is_part_of_output_never_additional_to_it(self):
        with pytest.raises(ValidationError, match="part of that total"):
            ModelResponse(
                model_id="gpt-5",
                text="x",
                prompt_tokens=10,
                completion_tokens=100,
                reasoning_tokens=101,
            )

    def test_a_provider_over_reporting_reasoning_does_not_take_the_run_down(self):
        client = FakeClient(a_completion(completion_tokens=100, reasoning_tokens=999))
        assert a_port(client).complete(a_request()).reasoning_tokens == 100

    def test_the_provider_version_is_captured_for_the_manifest(self):
        # AD-9: two arms differing here are not comparable.
        assert a_port().complete(a_request()).provider_version == "gpt-5-2025-08-07"

    def test_an_exhausted_budget_is_a_failure_not_an_empty_answer(self):
        # HTTP 200, no visible output, and a bill. The frozen baseline
        # definition calls this a failure of the arm that produced it.
        client = FakeClient(a_completion(text="", finish_reason="length"))
        response = a_port(client).complete(a_request())
        assert response.incomplete
        assert response.text == ""
        assert response.completion_tokens > 0

    def test_a_completed_answer_is_not_marked_incomplete(self):
        assert not a_port().complete(a_request()).incomplete

    def test_a_missing_content_field_reads_as_empty_rather_than_none(self):
        client = FakeClient(a_completion(text=None))
        assert a_port(client).complete(a_request()).text == ""


class TestTheDeploymentMapping:
    def test_a_logical_id_maps_to_its_deployment(self):
        client = FakeClient()
        a_port(client, deployments={"gpt-5": "my-gpt-5-deployment"}).complete(a_request())
        assert client.payloads[0]["model"] == "my-gpt-5-deployment"

    def test_an_unmapped_id_is_used_as_the_deployment_name(self):
        client = FakeClient()
        a_port(client).complete(a_request())
        assert client.payloads[0]["model"] == "gpt-5"

    def test_the_response_reports_the_logical_id_the_contract_named(self):
        # The contract names `gpt-5`; the deployment may be called anything.
        response = a_port(deployments={"gpt-5": "whatever"}).complete(a_request())
        assert response.model_id == "gpt-5"


class TestFailures:
    def test_a_provider_error_becomes_a_decision_input(self):
        # AD-20: it reaches the driver as a failure it can route, never as a
        # provider exception unwinding past the ladder.
        client = FakeClient(raises=RuntimeError("429 rate limited"))
        with pytest.raises(ModelPortError, match="the model call failed"):
            a_port(client).complete(a_request())

    def test_the_port_satisfies_the_protocol(self):
        from outcomefuse.ports import ModelPort

        assert isinstance(a_port(), ModelPort)
