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
from outcomefuse.ports.model import Message, ToolInvocation, ToolSchema, user_turn

BASE = "https://outcomefuse-foundry.services.ai.azure.com/openai/v1"


def a_completion(
    *,
    text: str = "an answer",
    prompt_tokens: int = 29,
    completion_tokens: int = 2919,
    reasoning_tokens: int = 1792,
    finish_reason: str = "stop",
    model: str = "gpt-5-2025-08-07",
    tool_calls=None,
):
    """Shaped like Microsoft's own documented response."""
    return SimpleNamespace(
        model=model,
        choices=[
            SimpleNamespace(
                finish_reason=finish_reason,
                message=SimpleNamespace(content=text, tool_calls=tool_calls),
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
        "messages": user_turn("What is the capital of France?"),
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
        # Passing `prompt=` here too would make this pass on the wrong ground:
        # `prompt` is itself a forbidden extra now.
        with pytest.raises(ValidationError, match="temperature"):
            ModelRequest(**(a_request().model_dump() | {"temperature": 0}))

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


def a_tool_call(*, id="call_1", name="sql_query", arguments='{"sql": "SELECT 1"}'):
    return SimpleNamespace(
        id=id, type="function", function=SimpleNamespace(name=name, arguments=arguments)
    )


class TestTheToolProtocol:
    # The frozen task block names the tools but specifies no call format, and
    # nothing may be added to it. So the provider's own protocol is the only
    # one available, and this is where it is spoken.

    def test_no_tools_key_is_sent_when_none_are_offered(self):
        # An empty `tools: []` is not the same request as no tools at all.
        client = FakeClient()
        a_port(client).complete(a_request())
        assert "tools" not in client.payloads[0]

    def test_a_declared_tool_reaches_the_provider_in_its_own_shape(self):
        client = FakeClient()
        schema = ToolSchema(
            name="sql_query",
            description="Run one read-only SELECT.",
            parameters={"type": "object", "properties": {"sql": {"type": "string"}}},
        )
        a_port(client).complete(a_request(tools=(schema,)))
        assert client.payloads[0]["tools"] == [
            {
                "type": "function",
                "function": {
                    "name": "sql_query",
                    "description": "Run one read-only SELECT.",
                    "parameters": {
                        "type": "object",
                        "properties": {"sql": {"type": "string"}},
                    },
                },
            }
        ]

    def test_a_tool_call_comes_back_structured(self):
        response = a_port(
            FakeClient(a_completion(text="", tool_calls=[a_tool_call()]))
        ).complete(a_request())
        assert response.wants_tools
        assert len(response.tool_calls) == 1
        call = response.tool_calls[0]
        assert (call.id, call.tool, call.arguments) == (
            "call_1",
            "sql_query",
            {"sql": "SELECT 1"},
        )
        assert call.malformed is None

    def test_an_answer_carries_no_tool_calls(self):
        # `wants_tools` is what the runner loops on, so it must be false here.
        response = a_port(FakeClient(a_completion(text="done"))).complete(a_request())
        assert response.tool_calls == ()
        assert not response.wants_tools

    def test_several_tool_calls_in_one_turn_all_survive(self):
        response = a_port(
            FakeClient(
                a_completion(
                    text="",
                    tool_calls=[a_tool_call(id="a"), a_tool_call(id="b", name="schema_describe")],
                )
            )
        ).complete(a_request())
        assert [(c.id, c.tool) for c in response.tool_calls] == [
            ("a", "sql_query"),
            ("b", "schema_describe"),
        ]

    def test_unreadable_arguments_are_carried_not_raised(self):
        # A model emitting broken JSON has failed the step. That failure belongs
        # to the arm that produced it; crashing here would charge it to the
        # harness and lose the run.
        response = a_port(
            FakeClient(a_completion(text="", tool_calls=[a_tool_call(arguments="{not json")]))
        ).complete(a_request())
        call = response.tool_calls[0]
        assert call.malformed is not None
        assert call.arguments == {}
        assert call.tool == "sql_query"

    def test_arguments_that_are_valid_json_but_not_an_object_are_malformed(self):
        # `[1, 2]` parses. It is still not a set of named arguments, and
        # reaching into it would be the harness repairing the agent's output.
        response = a_port(
            FakeClient(a_completion(text="", tool_calls=[a_tool_call(arguments="[1, 2]")]))
        ).complete(a_request())
        assert response.tool_calls[0].malformed == "arguments are a JSON list"
        assert response.tool_calls[0].arguments == {}

    def test_empty_arguments_are_an_empty_mapping_not_a_failure(self):
        # `schema_describe()` takes none. That is a legitimate call.
        response = a_port(
            FakeClient(a_completion(text="", tool_calls=[a_tool_call(arguments="")]))
        ).complete(a_request())
        assert response.tool_calls[0].arguments == {}
        assert response.tool_calls[0].malformed is None


class TestTheConversation:
    def test_the_whole_transcript_is_sent_not_just_the_last_turn(self):
        # FR64: the baseline carries context forward uncompressed. If the port
        # dropped the history there would be nothing for a Context Governor to
        # improve on, and the comparison would be meaningless.
        client = FakeClient()
        a_port(client).complete(
            a_request(
                messages=(
                    Message(role="system", content="you are an agent"),
                    Message(role="user", content="the task"),
                    Message(role="assistant", content="thinking"),
                )
            )
        )
        assert client.payloads[0]["messages"] == [
            {"role": "system", "content": "you are an agent"},
            {"role": "user", "content": "the task"},
            {"role": "assistant", "content": "thinking"},
        ]

    def test_a_tool_result_is_sent_against_the_call_it_answers(self):
        client = FakeClient()
        a_port(client).complete(
            a_request(
                messages=(
                    Message(role="user", content="the task"),
                    Message(
                        role="assistant",
                        tool_calls=(
                            ToolInvocation(id="call_1", tool="sql_query", arguments={"sql": "x"}),
                        ),
                    ),
                    Message(role="tool", tool_call_id="call_1", content="[[1]]"),
                )
            )
        )
        assistant, tool = client.payloads[0]["messages"][1:]
        assert assistant["tool_calls"] == [
            {
                "id": "call_1",
                "type": "function",
                "function": {"name": "sql_query", "arguments": '{"sql": "x"}'},
            }
        ]
        assert assistant["content"] is None
        assert tool == {"role": "tool", "tool_call_id": "call_1", "content": "[[1]]"}

    def test_a_conversation_must_have_at_least_one_turn(self):
        with pytest.raises(ValidationError):
            ModelRequest(model_id="gpt-5", messages=(), max_output_tokens=100)

    def test_the_prompt_view_reads_the_conversation(self):
        # Kept so a port that takes no messages can still be driven.
        request = a_request(
            messages=(
                Message(role="system", content="rules"),
                Message(role="user", content="task"),
            )
        )
        assert request.prompt == "rules\n\ntask"
