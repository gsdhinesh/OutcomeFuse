"""The agent loop and its two arms (FR52, AD-9, AD-13).

The property defended hardest here is that **both arms run the same loop**. The
governed and baseline arms differ in one place — what happens when the agent
asks for a tool — and if any other difference crept in, every comparison would
measure the loops as much as the governor. That failure is uniquely dangerous
because it is invisible: the result comes out complete, self-consistent and
worthless.

The second property is that an agent's own failure never becomes the harness's.
Unreadable output, a broken tool, a refused call, a budget exhausted
mid-thought: each is scored, not raised. A run lost to an exception is a run
that cannot be scored either way, and it still cost money.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from outcomefuse.core.contract import load_path
from outcomefuse.core.policy import Ledger, Reserve
from outcomefuse.core.record import RecordStore, RunManifest
from outcomefuse.harness.cases import Case, load_case_set
from outcomefuse.harness.runner import (
    MAX_TOOL_OUTPUT,
    BaselineArm,
    GovernedArm,
    Spend,
    _render,
    run_case,
)
from outcomefuse.ports import ModelResponse, ToolCall, ToolInvocation
from outcomefuse.runtime import Driver, StepVerdict, ToolGovernor
from outcomefuse.workloads import tool_port_for

SHA = "0" * 64
WORKLOAD = "data-sql"


@pytest.fixture(scope="module")
def contract():
    return load_path(Path(f"contracts/{WORKLOAD}.contract.yaml"))


@pytest.fixture(scope="module")
def case() -> Case:
    return load_case_set(WORKLOAD, "calibration").cases[0]


@pytest.fixture(scope="module")
def tools(contract):
    return tool_port_for(contract)


# ------------------------------------------------------------------ a model


class Model:
    """Replies from a script, and remembers exactly what it was asked."""

    def __init__(self, *turns) -> None:
        self._turns = list(turns)
        self.requests: list = []

    def complete(self, request):
        self.requests.append(request)
        return self._turns.pop(0) if self._turns else answer('{"answer": "done"}')


def answer(text, *, prompt=10, completion=5, reasoning=0, incomplete=False):
    return ModelResponse(
        model_id="gpt-5",
        text=text,
        prompt_tokens=prompt,
        completion_tokens=completion,
        reasoning_tokens=reasoning,
        provider_version="gpt-5-2025-08-07",
        incomplete=incomplete,
    )


def asks(*calls, prompt=10, completion=5):
    return ModelResponse(
        model_id="gpt-5",
        text="",
        prompt_tokens=prompt,
        completion_tokens=completion,
        tool_calls=tuple(calls),
        provider_version="gpt-5-2025-08-07",
    )


def a_call(tool="schema_describe", arguments=None, id="c1", malformed=None):
    return ToolInvocation(id=id, tool=tool, arguments=arguments or {}, malformed=malformed)


def drive(case, contract, arm, *turns, **over):
    return run_case(
        case,
        contract=contract,
        arm=arm,
        model=Model(*turns),
        max_output_tokens=25000,
        reasoning_effort="medium",
        **over,
    )


# ------------------------------------------------------------------- arms


@pytest.fixture
def governed(tmp_path: Path, contract, tools):
    stores: list[RecordStore] = []

    def build(*, allocated_tokens=1_000_000):
        store = RecordStore(tmp_path / f"g{len(stores)}.db").open()
        stores.append(store)
        driver = Driver(
            run_id=f"run-{len(stores)}",
            contract=contract,
            store=store,
            ledger=Ledger(
                allocated_tokens=allocated_tokens,
                allocated_cost=1.0,
                reserve=Reserve(
                    max_tokens=max(1, allocated_tokens // 100),
                    max_estimated_cost=0.01,
                    sizing="declared",
                ),
            ),
            governor=ToolGovernor(contract),
            tools=tools,
        )
        driver.open_run(
            RunManifest(
                run_id=driver.run_id,
                mode="governed",
                data_class="synthetic",
                retention_profile="mvp-synthetic-v1",
                contract_hash=SHA,
                rubric_hash=SHA,
                answer_key_hash=SHA,
                verifier_registry_version="v1",
                verifier_registry_hash=SHA,
                coverage_report_hash=SHA,
                baseline_configuration_hash=SHA,
                case_set_id=f"calibration/{WORKLOAD}",
                split="calibration",
                model_ids=("gpt-5",),
                provider_versions={"gpt-5": "gpt-5-2025-08-07"},
                cost_table_version="ct-1",
                route="direct",
                streaming_disabled=True,
                adapter_id="reference",
                adapter_version="1",
                governor_code_version="0.1.0",
                sqlite_library_version=sqlite3.sqlite_version,
                seed=1,
            )
        )
        return GovernedArm(driver, start_model="gpt-5"), driver

    yield build
    for store in stores:
        store.close()


@pytest.fixture
def baseline(tools):
    return BaselineArm(tools, model="gpt-5")


class TestBothArmsRunTheSameLoop:
    # The one difference between the arms is what happens at a tool call.
    # Anything else here would make the comparison measure the loops.

    def test_both_arms_are_given_the_identical_opening_conversation(
        self, case, contract, governed, baseline
    ):
        arm, _ = governed()
        g = Model(answer('{"answer": "x"}'))
        b = Model(answer('{"answer": "x"}'))
        run_case(
            case,
            contract=contract,
            arm=arm,
            model=g,
            max_output_tokens=25000,
            reasoning_effort="medium",
        )
        run_case(
            case,
            contract=contract,
            arm=baseline,
            model=b,
            max_output_tokens=25000,
            reasoning_effort="medium",
        )
        assert g.requests[0].messages == b.requests[0].messages

    def test_both_arms_are_offered_the_identical_tools(
        self, case, contract, governed, baseline
    ):
        # A governor that withheld a tool from its own arm would be optimising
        # by removing capability, which FR33 forbids and which would show up as
        # a saving rather than as the cheat it is.
        arm, _ = governed()
        g, b = Model(answer("{}")), Model(answer("{}"))
        for a, m in ((arm, g), (baseline, b)):
            run_case(
                case,
                contract=contract,
                arm=a,
                model=m,
                max_output_tokens=25000,
                reasoning_effort="medium",
            )
        assert g.requests[0].tools == b.requests[0].tools
        assert g.requests[0].tools  # and it is not vacuously empty

    def test_both_arms_send_the_same_sampling_parameters(
        self, case, contract, governed, baseline
    ):
        arm, _ = governed()
        g, b = Model(answer("{}")), Model(answer("{}"))
        for a, m in ((arm, g), (baseline, b)):
            run_case(
                case,
                contract=contract,
                arm=a,
                model=m,
                max_output_tokens=25000,
                reasoning_effort="medium",
            )
        assert g.requests[0].reasoning_effort == b.requests[0].reasoning_effort == "medium"
        assert g.requests[0].max_output_tokens == b.requests[0].max_output_tokens

    def test_the_baseline_holds_no_driver(self, baseline):
        # FR52. A driver with its mechanisms disabled would still impose the
        # driver's ordering, its fail-closed paths and its bookkeeping on the
        # arm that exists to show what happens without any of it.
        assert not any(
            isinstance(value, Driver) for value in vars(baseline).values()
        )


class TestTheConversationGrows:
    def test_the_transcript_carries_forward_uncompressed(self, case, contract, baseline):
        # FR64. If the loop dropped history there would be nothing for a Context
        # Governor to improve on and the whole mechanism would measure zero.
        model = Model(asks(a_call()), answer('{"answer": "x"}'))
        run_case(
            case,
            contract=contract,
            arm=baseline,
            model=model,
            max_output_tokens=25000,
            reasoning_effort="medium",
        )
        first, second = model.requests
        assert len(second.messages) > len(first.messages)
        assert second.messages[: len(first.messages)] == first.messages

    def test_a_tool_result_is_returned_against_the_call_it_answers(
        self, case, contract, baseline
    ):
        model = Model(asks(a_call(id="abc")), answer("{}"))
        run_case(
            case,
            contract=contract,
            arm=baseline,
            model=model,
            max_output_tokens=25000,
            reasoning_effort="medium",
        )
        tool_messages = [m for m in model.requests[1].messages if m.role == "tool"]
        assert [m.tool_call_id for m in tool_messages] == ["abc"]
        assert tool_messages[0].content

    def test_every_call_in_a_multi_call_turn_gets_a_reply(self, case, contract, baseline):
        # A provider may return several. Missing one leaves the conversation
        # malformed and the next turn is rejected by the API.
        model = Model(
            asks(a_call(id="a"), a_call(id="b", tool="sql_query", arguments={"sql": "SELECT 1"})),
            answer("{}"),
        )
        run_case(
            case,
            contract=contract,
            arm=baseline,
            model=model,
            max_output_tokens=25000,
            reasoning_effort="medium",
        )
        replies = [m.tool_call_id for m in model.requests[1].messages if m.role == "tool"]
        assert replies == ["a", "b"]


class TestTheAgentsFailuresAreScoredNotRaised:
    def test_unreadable_output_is_a_recorded_outcome(self, case, contract, baseline):
        outcome = drive(case, contract, baseline, answer("I think the answer is probably 42."))
        assert outcome.parsed is not None
        assert not outcome.parsed.ok
        assert outcome.parsed.failure

    def test_a_broken_tool_is_reported_to_the_agent_not_raised(
        self, case, contract, baseline
    ):
        # A malformed query is the agent's mistake. It should read the error and
        # try again, exactly as a person would.
        model = Model(
            asks(a_call(tool="sql_query", arguments={"sql": "SELECT nonsense FROM nowhere"})),
            answer('{"answer": "x"}'),
        )
        outcome = run_case(
            case,
            contract=contract,
            arm=baseline,
            model=model,
            max_output_tokens=25000,
            reasoning_effort="medium",
        )
        reply = next(m for m in model.requests[1].messages if m.role == "tool")
        assert "tool error" in reply.content
        assert outcome.parsed is not None and outcome.parsed.ok

    def test_a_broken_tool_releases_the_budget_it_reserved(self, case, contract, governed):
        # Found in a real run's log: four tool calls proposed, three
        # `outcome-observed`. The failing one had taken a reservation that was
        # never released, so the run's spendable budget shrank for the rest of
        # its life — invisibly, because the log shows a reservation and simply
        # never shows its release.
        arm, driver = governed()
        before = driver.ledger.in_flight_tokens
        model = Model(
            asks(a_call(tool="sql_query", arguments={"sql": "SELECT nope FROM nowhere"})),
            answer('{"answer": "x"}'),
        )
        run_case(
            case,
            contract=contract,
            arm=arm,
            model=model,
            max_output_tokens=25000,
            reasoning_effort="medium",
        )
        assert driver.ledger.in_flight_tokens == before

    def test_a_broken_tool_is_recorded_as_an_observation(self, case, contract, governed):
        # Every reservation must be answered in the log. A `budget-reserved`
        # with no outcome is the shape the leak took.
        arm, driver = governed()
        model = Model(
            asks(a_call(tool="sql_query", arguments={"sql": "SELECT nope FROM nowhere"})),
            answer('{"answer": "x"}'),
        )
        run_case(
            case,
            contract=contract,
            arm=arm,
            model=model,
            max_output_tokens=25000,
            reasoning_effort="medium",
        )
        events = driver.store.events(driver.run_id)
        observed = [e for e in events if e.kind == "outcome-observed"]
        assert len(observed) == 1
        assert "tool_error" in observed[0].payload

    def test_a_broken_tool_is_not_reported_to_the_agent_as_a_refusal(
        self, case, contract, governed
    ):
        # An agent told "not allowed" stops trying. An agent told the query was
        # wrong fixes the query. Conflating them turns a typo into a dead run.
        arm, _ = governed()
        outcome = arm.run_tool(
            ToolCall(
                tool="sql_query",
                arguments={"sql": "SELECT nope FROM nowhere"},
                step_id="s1",
            )
        )
        assert not outcome.refused
        assert "tool error" in outcome.content
        assert outcome.terminal_reason is None

    def test_a_malformed_tool_call_is_answered_without_running_anything(
        self, case, contract, baseline, tools
    ):
        before = len(tools.invocations)
        model = Model(
            asks(a_call(malformed="arguments are not readable JSON")), answer("{}")
        )
        run_case(
            case,
            contract=contract,
            arm=baseline,
            model=model,
            max_output_tokens=25000,
            reasoning_effort="medium",
        )
        assert len(tools.invocations) == before
        reply = next(m for m in model.requests[1].messages if m.role == "tool")
        assert "could not read the arguments" in reply.content

    def test_an_exhausted_output_budget_is_not_scored_as_a_wrong_answer(
        self, case, contract, baseline
    ):
        # HTTP 200, no text, and a bill. Parsing the empty string would file a
        # billing accident as a reasoning failure.
        outcome = drive(case, contract, baseline, answer("", incomplete=True))
        assert outcome.parsed is None
        assert outcome.stopped_by == "output budget exhausted before any answer"

    def test_an_incomplete_response_that_still_answered_is_scored(
        self, case, contract, baseline
    ):
        outcome = drive(case, contract, baseline, answer('{"answer": "x"}', incomplete=True))
        assert outcome.parsed is not None and outcome.parsed.ok


class TestTheLoopTerminates:
    def test_an_agent_that_never_finishes_is_stopped(self, case, contract, baseline):
        outcome = run_case(
            case,
            contract=contract,
            arm=baseline,
            model=Model(*[asks(a_call()) for _ in range(10)]),
            max_output_tokens=25000,
            reasoning_effort="medium",
            max_iterations=3,
        )
        assert outcome.iterations == 3
        assert outcome.stopped_by is not None and "3 turns" in outcome.stopped_by

    def test_an_agent_that_finishes_is_not_reported_as_stopped(
        self, case, contract, baseline
    ):
        # The mirror of the test above. Without it, always reporting `stopped_by`
        # would pass the one before and be entirely wrong.
        outcome = drive(case, contract, baseline, answer('{"answer": "x"}'))
        assert outcome.stopped_by is None
        assert outcome.iterations == 1

    def test_a_run_stopped_by_the_governor_stops_the_loop(self, case, contract, governed):
        arm, driver = governed(allocated_tokens=100)
        outcome = drive(
            case, contract, arm, asks(a_call(), prompt=5000, completion=5000), answer("{}")
        )
        assert outcome.terminal_reason is not None
        assert driver.terminated is not None

    def test_a_budget_that_cannot_afford_the_turn_is_exhaustion_not_a_fault(
        self, case, contract, governed
    ):
        # `halt-exhausted` and `fail-closed` both stop the run, so a test that
        # accepted either would pass whether or not affordability was ever
        # asked — and the product's central cost event would be filed as a
        # system fault. This is the same defect that was in `execute_step`.
        arm, driver = governed(allocated_tokens=100)
        outcome = drive(
            case, contract, arm, answer('{"answer": "x"}', prompt=5000, completion=5000)
        )
        assert outcome.terminal_reason == "halt-exhausted"
        assert driver.terminated == "halt-exhausted"

    def test_the_model_is_not_called_again_after_exhaustion(self, case, contract, governed):
        arm, _ = governed(allocated_tokens=100)
        model = Model(
            answer("{}", prompt=5000, completion=5000), answer('{"answer": "x"}')
        )
        run_case(
            case,
            contract=contract,
            arm=arm,
            model=model,
            max_output_tokens=25000,
            reasoning_effort="medium",
        )
        assert len(model.requests) == 1


class TestSpendIsCountedNotEstimated:
    def test_every_model_turn_is_added_up(self, case, contract, baseline):
        outcome = drive(
            case,
            contract,
            baseline,
            asks(a_call(), prompt=100, completion=50),
            answer('{"answer": "x"}', prompt=200, completion=60, reasoning=40),
        )
        assert outcome.spend.prompt_tokens == 300
        assert outcome.spend.completion_tokens == 110
        assert outcome.spend.reasoning_tokens == 40
        assert outcome.spend.model_turns == 2
        assert outcome.spend.tool_calls == 1

    def test_reasoning_tokens_are_inside_completion_not_beside_it(self):
        # Counting them twice would inflate the baseline, which is the arm that
        # reasons most, and manufacture a saving out of arithmetic.
        spend = Spend().plus_turn(10, 100, 85)
        assert spend.total_tokens == 110

    def test_the_governed_arm_charges_the_model_turn_to_the_ledger(
        self, case, contract, governed
    ):
        # The measured run spent 85% of completion on reasoning. A ledger that
        # saw only tool calls would govern the cheap half of the run.
        arm, driver = governed()
        before = driver.ledger.spent_tokens
        drive(case, contract, arm, answer('{"answer": "x"}', prompt=1000, completion=500))
        assert driver.ledger.spent_tokens >= before + 1500

    def test_an_unpriced_table_meters_tokens_and_charges_no_cost(
        self, case, contract, governed
    ):
        arm, driver = governed()
        drive(case, contract, arm, answer('{"answer": "x"}', prompt=100, completion=50))
        assert driver.ledger.spent_tokens >= 150
        assert driver.ledger.spent_cost == 0.0

    def test_a_price_function_is_used_when_given(self, case, contract, governed):
        arm, driver = governed()
        drive(
            case,
            contract,
            arm,
            answer('{"answer": "x"}', prompt=100, completion=50),
            price=lambda model, p, c: 0.25,
        )
        assert driver.ledger.spent_cost == pytest.approx(0.25)


class TestToolResultsReachTheModel:
    def test_a_large_result_is_truncated_rather_than_blowing_the_window(self):
        rendered = _render("x" * (MAX_TOOL_OUTPUT * 2))
        assert len(rendered) <= MAX_TOOL_OUTPUT + 64
        assert "truncated" in rendered

    def test_a_result_that_fits_is_left_alone(self):
        assert _render("small") == "small"

    def test_structured_output_is_rendered_as_json_the_model_can_read(self):
        rendered = _render({"rows": [[1, 2]], "columns": ["a", "b"]})
        assert json.loads(rendered) == {"rows": [[1, 2]], "columns": ["a", "b"]}


class TestTheGovernorCanRefuse:
    def test_a_denied_call_is_explained_to_the_agent(self, governed):
        # An agent that cannot tell refusal from failure retries the same call
        # until the loop cap stops it, and the run's cost is the cap's fault
        # rather than the governor's.
        arm, _ = governed()

        class Denying:
            def execute_step(self, call, **_):
                return StepVerdict(action="deny", decision_reason="cache-covers-this")

        arm._driver = Denying()  # type: ignore[assignment]
        outcome = arm.run_tool(ToolCall(tool="schema_describe", arguments={}, step_id="s1"))
        assert outcome.refused
        assert "cache-covers-this" in outcome.content
        assert outcome.terminal_reason is None
