"""The agent loop, and the two arms that run it (FR52, AD-9, AD-13).

This is the piece that turns a case into a run: it renders the frozen prompt,
offers the contract's tools, and drives model → tools → model until the agent
answers or is stopped.

**The loop is arm-agnostic on purpose.** The governed and baseline arms differ
in exactly one thing — what happens when the agent asks for a tool — and that
difference is behind an `Arm`. Two loops would be two agents, and every
comparison between them would measure the loops as much as the governor. That
is the single most expensive mistake available in this codebase, because it
produces a complete, self-consistent, entirely invalid result.

The baseline is not a crippled governed run. It is what an ordinary competent
team ships: carry the whole transcript forward, call the strong model, stop when
the agent says it is done. It has no governor to disable, which is why
`BaselineArm` holds no `Driver` rather than holding one with its mechanisms
switched off.
"""

from __future__ import annotations

import json
from typing import Any, Final, Protocol

from pydantic import BaseModel, ConfigDict, Field

from ..core.contract import Contract
from ..ports import Message, ModelPort, ModelRequest, ToolCall, ToolSchema
from ..runtime import Driver, StepVerdict
from ..workloads import ToolError, WorkloadToolPort, schemas_for
from .cases import Case
from .deliverable import Parsed, parse_deliverable
from .prompts import render

#: A run that has gone round this many times is not going to finish. This is a
#: backstop against an unbounded bill, not a governing mechanism: the governed
#: arm's LoopFuse should always fire first, and a run that hits this cap in the
#: governed arm is a defect worth knowing about. The baseline has nothing else.
MAX_ITERATIONS: Final[int] = 24

#: What a tool result is truncated to before going back to the model. Large
#: enough that no legitimate result is cut, small enough that one runaway query
#: cannot eat the context window. Identical for both arms.
MAX_TOOL_OUTPUT: Final[int] = 16_000


class RunnerError(RuntimeError):
    """The runner could not start. Never used for an agent's own failure."""


class Spend(BaseModel):
    """What the run consumed, counted rather than estimated."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    prompt_tokens: int = Field(default=0, ge=0)
    completion_tokens: int = Field(default=0, ge=0)
    reasoning_tokens: int = Field(default=0, ge=0)
    tool_calls: int = Field(default=0, ge=0)
    model_turns: int = Field(default=0, ge=0)

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens

    def plus_turn(self, prompt: int, completion: int, reasoning: int) -> Spend:
        return self.model_copy(
            update={
                "prompt_tokens": self.prompt_tokens + prompt,
                "completion_tokens": self.completion_tokens + completion,
                "reasoning_tokens": self.reasoning_tokens + reasoning,
                "model_turns": self.model_turns + 1,
            }
        )

    def plus_tool_call(self) -> Spend:
        return self.model_copy(update={"tool_calls": self.tool_calls + 1})


class ToolOutcome(BaseModel):
    """What the arm did with a tool the agent asked for."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    #: Goes back to the model as the tool's reply, whatever happened.
    content: str
    #: The run must stop, and this is why.
    terminal_reason: str | None = None
    #: The tool did not run. The agent is told so, plainly, and may try again.
    refused: bool = False


class Outcome(BaseModel):
    """One case, one arm, one result."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    case_id: str
    arm: str
    spend: Spend
    parsed: Parsed | None = None
    terminal_reason: str | None = None
    iterations: int = Field(ge=0)
    #: Set where the loop stopped for its own reasons rather than the agent's.
    stopped_by: str | None = None


class Arm(Protocol):
    """The one thing the two arms disagree about."""

    name: str

    def run_tool(self, call: ToolCall) -> ToolOutcome: ...

    def charge_model_turn(
        self, *, step_id: str, tokens: int, cost: float, model_used: str
    ) -> str | None:
        """Returns a terminal reason where the run must stop."""
        ...

    def finish(self, parsed: Parsed, *, answer_key: Any | None) -> str | None: ...

    def model_id(self) -> str: ...


# --------------------------------------------------------------------- arms


class GovernedArm:
    """Every tool call goes through the driver, which may refuse it."""

    name = "governed"

    def __init__(self, driver: Driver, *, start_model: str) -> None:
        self._driver = driver
        self._start_model = start_model

    def model_id(self) -> str:
        return self._start_model

    def run_tool(self, call: ToolCall) -> ToolOutcome:
        try:
            verdict = self._driver.execute_step(call)
        except ToolError as exc:
            # The tool itself failed. That is information the agent can act on,
            # not a reason to lose the run.
            return ToolOutcome(content=f"tool error: {exc}", refused=True)
        return _from_verdict(verdict)

    def charge_model_turn(
        self, *, step_id: str, tokens: int, cost: float, model_used: str
    ) -> str | None:
        verdict = self._driver.charge_model_turn(
            step_id=step_id, tokens=tokens, cost=cost, model_used=model_used
        )
        return verdict.terminal_reason if verdict is not None else None

    def finish(self, parsed: Parsed, *, answer_key: Any | None) -> str | None:
        verdict = self._driver.submit_deliverable(
            parsed.deliverable if parsed.ok else None,
            answer_key=answer_key,
            parse_failure=parsed.failure,
        )
        return verdict.terminal_reason


class BaselineArm:
    """No governor. The tool runs, the answer is taken, the bill is what it is.

    FR52: the baseline holds no `Driver`. A driver with its mechanisms disabled
    would still impose the driver's own control flow — its ordering, its
    fail-closed paths, its bookkeeping — on the arm that is supposed to show
    what happens without any of it.
    """

    name = "baseline"

    def __init__(self, tools: WorkloadToolPort, *, model: str) -> None:
        self._tools = tools
        self._model = model

    def model_id(self) -> str:
        return self._model

    def run_tool(self, call: ToolCall) -> ToolOutcome:
        try:
            result = self._tools.invoke(call)
        except ToolError as exc:
            return ToolOutcome(content=f"tool error: {exc}", refused=True)
        return ToolOutcome(content=_render(result.output))

    def charge_model_turn(
        self, *, step_id: str, tokens: int, cost: float, model_used: str
    ) -> str | None:
        # Nothing to charge against. Spending is counted by the loop for the
        # proof card either way; the baseline simply has no budget to breach.
        return None

    def finish(self, parsed: Parsed, *, answer_key: Any | None) -> str | None:
        return None


def _from_verdict(verdict: StepVerdict) -> ToolOutcome:
    if verdict.terminates:
        return ToolOutcome(
            content=f"the run was stopped: {verdict.decision_reason}",
            terminal_reason=verdict.terminal_reason,
        )
    if verdict.action == "deny":
        # Told plainly, because an agent that cannot tell refusal from failure
        # will retry the same call until the loop cap stops it.
        return ToolOutcome(
            content=f"this call was not allowed: {verdict.decision_reason}", refused=True
        )
    return ToolOutcome(content=_render(verdict.result))


def _render(output: Any) -> str:
    """A tool result, as the model will read it."""
    if isinstance(output, str):
        text = output
    else:
        try:
            text = json.dumps(output, default=str, sort_keys=True)
        except (TypeError, ValueError):
            text = str(output)
    if len(text) > MAX_TOOL_OUTPUT:
        return text[:MAX_TOOL_OUTPUT] + f"\n[truncated at {MAX_TOOL_OUTPUT} characters]"
    return text


# -------------------------------------------------------------- the loop


def run_case(
    case: Case,
    *,
    contract: Contract,
    arm: Arm,
    model: ModelPort,
    max_output_tokens: int,
    reasoning_effort: str | None,
    answer_key: Any | None = None,
    max_iterations: int = MAX_ITERATIONS,
    price: Any | None = None,
) -> Outcome:
    """Drive one case to an answer, a refusal, or a stop.

    `price` is a callable taking `(model_id, prompt_tokens, completion_tokens)`
    and returning a cost. It may be `None`, in which case the run is metered in
    tokens only and the ledger sees a cost of zero. That is honest — an unpriced
    cost table refuses to invent a number — and it means the cost ceiling cannot
    bind, which the manifest's `cost_table_version` records.
    """
    prompt = render(case)
    tools: tuple[ToolSchema, ...] = schemas_for(contract)
    messages: list[Message] = [
        Message(role="system", content=prompt.system),
        Message(role="user", content=prompt.user),
    ]

    spend = Spend()
    parsed: Parsed | None = None
    terminal: str | None = None
    stopped_by: str | None = None
    iteration = 0

    while iteration < max_iterations:
        step_id = f"{case.case_id}-{iteration:02d}"
        response = model.complete(
            ModelRequest(
                model_id=arm.model_id(),
                messages=tuple(messages),
                tools=tools,
                max_output_tokens=max_output_tokens,
                reasoning_effort=reasoning_effort,
            )
        )
        spend = spend.plus_turn(
            response.prompt_tokens, response.completion_tokens, response.reasoning_tokens
        )
        iteration += 1

        cost = (
            price(response.model_id, response.prompt_tokens, response.completion_tokens)
            if price is not None
            else 0.0
        )
        terminal = arm.charge_model_turn(
            step_id=step_id,
            tokens=response.prompt_tokens + response.completion_tokens,
            cost=cost,
            model_used=response.provider_version or response.model_id,
        )
        if terminal is not None:
            return Outcome(
                case_id=case.case_id,
                arm=arm.name,
                spend=spend,
                terminal_reason=terminal,
                iterations=iteration,
            )

        if not response.wants_tools:
            # The budget ran out mid-thought: there is no answer to parse, and
            # treating the empty string as one would score a billing accident as
            # a reasoning failure.
            if response.incomplete and not response.text.strip():
                stopped_by = "output budget exhausted before any answer"
                break
            parsed = parse_deliverable(response.text)
            terminal = arm.finish(parsed, answer_key=answer_key)
            break

        messages.append(
            Message(role="assistant", content=response.text, tool_calls=response.tool_calls)
        )
        for invocation in response.tool_calls:
            spend = spend.plus_tool_call()
            if invocation.malformed is not None:
                messages.append(
                    Message(
                        role="tool",
                        tool_call_id=invocation.id,
                        content=f"could not read the arguments: {invocation.malformed}",
                    )
                )
                continue
            outcome = arm.run_tool(
                ToolCall(
                    tool=invocation.tool, arguments=invocation.arguments, step_id=step_id
                )
            )
            messages.append(
                Message(role="tool", tool_call_id=invocation.id, content=outcome.content)
            )
            if outcome.terminal_reason is not None:
                terminal = outcome.terminal_reason
                break
        if terminal is not None:
            break
    else:
        # The `while` ran out rather than breaking: the agent never stopped.
        stopped_by = f"the agent did not finish within {max_iterations} turns"

    return Outcome(
        case_id=case.case_id,
        arm=arm.name,
        spend=spend,
        parsed=parsed,
        terminal_reason=terminal,
        iterations=iteration,
        stopped_by=stopped_by,
    )
