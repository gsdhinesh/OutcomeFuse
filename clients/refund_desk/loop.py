"""One agent loop, two wirings: OutcomeFuse plugged in, and plugged out.

The loop in `run` is written once. It does not know whether it is governed; it
proposes a tool call and applies whatever comes back, which is AD-1's cooperative
enforcement stated as an ordinary piece of application code. Swapping `Governed`
for `Ungoverned` is the entire difference between the two arms, and it is a
constructor argument.

That is the property being demonstrated. A governor you cannot remove is not a
governor, it is a rewrite: nobody can tell you what it bought, because there is
nothing to compare it against. A governor you can remove leaves a loop that
still runs, and the delta between the two runs is the measurement.

**The model is scripted on purpose.** The question here is what the library does
to a loop, not what a model does with a prompt, and a live model would make the
answer neither reproducible nor free. `ScriptedModelPort` is the library's own
deterministic port, so the transcript, the token counts and the tool sequence
are identical on both arms by construction — which is the only way the delta can
be attributed to the wiring.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Protocol

from outcomefuse.core.contract import Contract
from outcomefuse.core.gate import GateUnavailable
from outcomefuse.core.policy import LoopFuse
from outcomefuse.ports import (
    Message,
    ModelPort,
    ModelRequest,
    ModelResponse,
    ToolCall,
    ToolSchema,
)
from outcomefuse.runtime import Driver
from outcomefuse.runtime.baseline import BaselineRecorder
from outcomefuse.workloads.toolport import ToolError, WorkloadToolPort

from .desk import DeskCase

#: What one tool step is expected to cost. Declared rather than measured because
#: the reservation has to be taken *before* the call, which is the whole point
#: of a hold: a budget checked afterwards has already been spent.
TOOL_TOKENS = 60
TOOL_COST = 0.0006

#: A flat rate, stated here so it is obviously a client's assumption and not a
#: number the library produced. Real runs price from a cost table.
COST_PER_1K_TOKENS = 0.002

MAX_OUTPUT_TOKENS = 4096

SYSTEM = (
    "You are a refund desk adjudicator. Read the order, the shipment and the "
    "published refund policy, then answer with a single JSON object holding "
    "order_id, decision, refund_amount, reason_code and policy_refs. Issue the "
    "refund before you answer where one is owed."
)


def price(tokens: int) -> float:
    return tokens / 1000 * COST_PER_1K_TOKENS


def schemas_for(contract: Contract) -> tuple[ToolSchema, ...]:
    """The tools as the model is told about them. Names come from the contract,
    so a tool the contract does not declare cannot be offered."""
    return tuple(ToolSchema(name=tool.name) for tool in contract.tools)


# ------------------------------------------------------------------ wirings


@dataclass(frozen=True)
class ToolOutcome:
    """What the loop learned from proposing one tool call."""

    output: Any
    #: The reason the real call was withheld, or None where it happened.
    suppressed: str | None = None
    terminal: str | None = None
    failed: bool = False


@dataclass(frozen=True)
class Finish:
    passed: bool
    terminal: str | None = None


class Wiring(Protocol):
    name: str

    def model_id(self) -> str: ...

    def charge_model_turn(
        self, *, step_id: str, tokens: int, cost: float, model_used: str
    ) -> str | None: ...

    def call_tool(self, call: ToolCall) -> ToolOutcome: ...

    def note_progress(self, *, task_state: Any, evidence_count: int) -> str | None: ...

    def finish(
        self,
        deliverable: dict[str, Any] | None,
        *,
        answer_key: dict[str, Any],
        parse_failure: str | None,
    ) -> Finish: ...

    def close(self) -> None: ...

    def seal(self) -> str | None: ...


class Ungoverned:
    """OutcomeFuse plugged out. Every proposal is executed.

    The recorder is still here, and that is not a contradiction: recording is
    measurement, not governance. It decides nothing, denies nothing and holds no
    budget. Without it this arm would produce an answer nobody could check, and
    the comparison would be one sealed log against an anecdote.
    """

    name = "ungoverned"

    def __init__(self, *, tools: WorkloadToolPort, recorder: BaselineRecorder, model: str) -> None:
        self._tools = tools
        self._recorder = recorder
        self._model = model

    def model_id(self) -> str:
        return self._model

    def charge_model_turn(
        self, *, step_id: str, tokens: int, cost: float, model_used: str
    ) -> str | None:
        # `cost` is accepted and dropped: nothing ungoverned holds a budget, so
        # there is nothing for a cost to be checked against.
        self._recorder.observe_model_turn(step_id=step_id, tokens=tokens, model_used=model_used)
        return None

    def call_tool(self, call: ToolCall) -> ToolOutcome:
        try:
            result = self._tools.invoke(call)
        except ToolError as exc:
            self._recorder.observe_tool(call, failed=str(exc))
            return ToolOutcome(output={"error": str(exc)}, failed=True)
        self._recorder.observe_tool(call)
        return ToolOutcome(output=result.output)

    def note_progress(self, *, task_state: Any, evidence_count: int) -> str | None:
        return None

    def finish(
        self,
        deliverable: dict[str, Any] | None,
        *,
        answer_key: dict[str, Any],
        parse_failure: str | None,
    ) -> Finish:
        try:
            verdict = self._recorder.score(
                deliverable, answer_key=answer_key, parse_failure=parse_failure
            )
        except GateUnavailable:
            # Not fail-closed: there is nothing to close. The pair simply cannot
            # be scored, and hiding that as a failing arm would be a lie about
            # which of the two produced a worse answer.
            return Finish(passed=False, terminal="gate-unavailable")
        return Finish(passed=verdict is not None and verdict.passed)

    def close(self) -> None:
        if not self._recorder.closed:
            self._recorder.score(None, parse_failure="the loop ended without a deliverable")

    def seal(self) -> str | None:
        return self._recorder.seal()


class Governed:
    """OutcomeFuse plugged in. Every proposal is put to the driver first."""

    name = "governed"

    def __init__(self, driver: Driver) -> None:
        self._driver = driver

    @property
    def driver(self) -> Driver:
        return self._driver

    def model_id(self) -> str:
        return self._driver.model_id or "unknown"

    def charge_model_turn(
        self, *, step_id: str, tokens: int, cost: float, model_used: str
    ) -> str | None:
        verdict = self._driver.charge_model_turn(
            step_id=step_id, tokens=tokens, cost=cost, model_used=model_used
        )
        return verdict.terminal_reason if verdict is not None else None

    def call_tool(self, call: ToolCall) -> ToolOutcome:
        verdict = self._driver.execute_step(
            call, estimated_tokens=TOOL_TOKENS, estimated_cost=TOOL_COST
        )
        if verdict.terminates:
            return ToolOutcome(
                output=None,
                suppressed=verdict.decision_reason,
                terminal=verdict.terminal_reason,
            )
        if verdict.action == "proceed-with-substitution":
            # The tool was never invoked; the stored result stands in for it. The
            # loop is told what happened rather than handed a result that looks
            # like a fresh call, because an agent that cannot see the
            # substitution cannot reason about staleness.
            return ToolOutcome(output=verdict.result, suppressed=verdict.decision_reason)
        if verdict.action == "deny":
            return ToolOutcome(
                output={"refused": verdict.decision_reason},
                suppressed=verdict.decision_reason,
            )
        return ToolOutcome(output=verdict.result, failed=verdict.failed)

    def note_progress(self, *, task_state: Any, evidence_count: int) -> str | None:
        verdict = self._driver.observe_progress(
            task_state=task_state, evidence_count=evidence_count
        )
        return verdict.terminal_reason if verdict is not None else None

    def finish(
        self,
        deliverable: dict[str, Any] | None,
        *,
        answer_key: dict[str, Any],
        parse_failure: str | None,
    ) -> Finish:
        verdict = self._driver.submit_deliverable(
            deliverable, answer_key=answer_key, parse_failure=parse_failure
        )
        return Finish(
            passed=self._driver.quality_state == "pass", terminal=verdict.terminal_reason
        )

    def close(self) -> None:
        if self._driver.terminated is None:
            self._driver.submit_deliverable(
                None, parse_failure="the loop ended without a deliverable"
            )

    def seal(self) -> str | None:
        return self._driver.store.seal(self._driver.run_id)


# --------------------------------------------------------------------- loop


@dataclass
class RunOutcome:
    """What one arm did, in the terms the comparison is drawn in."""

    arm: str
    case_id: str
    turns: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    #: Tool calls the agent asked for, before anything decided about them.
    proposed: int = 0
    #: Tool calls that actually reached the tool, counted by the port's own
    #: probe rather than by the decision log (AD-15). A log cannot be the
    #: evidence for the one failure it would be falsified to hide.
    invoked: int = 0
    withheld: list[str] = field(default_factory=list)
    side_effects: list[str] = field(default_factory=list)
    deliverable: dict[str, Any] | None = None
    parse_failure: str | None = None
    passed: bool = False
    terminal: str | None = None
    seal: str | None = None

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens

    @property
    def estimated_cost(self) -> float:
        return price(self.total_tokens)


def parse_deliverable(text: str) -> tuple[dict[str, Any] | None, str | None]:
    """The agent's answer, or the reason it could not be read.

    A failure here is the agent's, not the harness's, so it is returned as a
    value. Raising would lose the run instead of scoring it.
    """
    stripped = text.strip()
    if not stripped:
        return None, "the model returned no text"
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError as exc:
        return None, f"the answer was not readable JSON: {exc}"
    if not isinstance(parsed, dict):
        return None, f"the answer was {type(parsed).__name__}, expected an object"
    return parsed, None


def run(
    case: DeskCase,
    *,
    contract: Contract,
    wiring: Wiring,
    tools: WorkloadToolPort,
    model: ModelPort,
    max_iterations: int | None = None,
) -> RunOutcome:
    """Adjudicate one refund request. Identical on both arms."""
    limit = max_iterations or contract.budget.max_iterations
    schemas = schemas_for(contract)
    outcome = RunOutcome(arm=wiring.name, case_id=case.case_id)
    messages: list[Message] = [
        Message(role="system", content=SYSTEM),
        Message(role="user", content=f"Order {case.order_id}. {case.request}"),
    ]
    evidence: list[str] = []

    for iteration in range(limit):
        step_id = f"{case.case_id}-t{iteration + 1}"
        response: ModelResponse = model.complete(
            ModelRequest(
                model_id=wiring.model_id(),
                messages=tuple(messages),
                max_output_tokens=MAX_OUTPUT_TOKENS,
                tools=schemas,
            )
        )
        outcome.turns += 1
        outcome.prompt_tokens += response.prompt_tokens
        outcome.completion_tokens += response.completion_tokens

        terminal = wiring.charge_model_turn(
            step_id=step_id,
            tokens=response.total_tokens,
            cost=price(response.total_tokens),
            model_used=response.model_id,
        )
        if terminal is not None:
            outcome.terminal = terminal
            break

        if not response.wants_tools:
            deliverable, failure = parse_deliverable(response.text)
            outcome.deliverable = deliverable
            outcome.parse_failure = failure
            finish = wiring.finish(
                deliverable, answer_key=case.answer_key, parse_failure=failure
            )
            outcome.passed = finish.passed
            outcome.terminal = finish.terminal
            break

        messages.append(Message(role="assistant", tool_calls=response.tool_calls))
        for index, invocation in enumerate(response.tool_calls):
            call = ToolCall(
                tool=invocation.tool,
                arguments=invocation.arguments,
                step_id=f"{step_id}-{index}",
            )
            outcome.proposed += 1
            result = wiring.call_tool(call)
            if result.suppressed is not None:
                outcome.withheld.append(f"{call.tool}: {result.suppressed}")
            else:
                evidence.append(call.tool)
            messages.append(
                Message(
                    role="tool",
                    tool_call_id=invocation.id,
                    content=json.dumps(result.output, default=str, sort_keys=True),
                )
            )
            if result.terminal is not None:
                terminal = result.terminal
                break

        if terminal is not None:
            outcome.terminal = terminal
            break

        terminal = wiring.note_progress(
            task_state={"turn": iteration, "tools": evidence[-4:]},
            evidence_count=len(evidence),
        )
        if terminal is not None:
            outcome.terminal = terminal
            break
    else:
        outcome.terminal = "iteration-limit"

    wiring.close()
    outcome.invoked = len(tools.invocations)
    outcome.side_effects = list(tools.side_effects)
    outcome.seal = wiring.seal()
    return outcome


def build_fuse(contract: Contract) -> LoopFuse:
    return LoopFuse(max_iterations=contract.budget.max_iterations)
