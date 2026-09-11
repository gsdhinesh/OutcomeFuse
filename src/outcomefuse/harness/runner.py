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
from ..runtime import BaselineRecorder, Driver, StepVerdict
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
    #: Zero where the cost table is unpriced. Tokens are counted regardless, so
    #: the token claim never depends on anyone having read a pricing page.
    cost: float = Field(default=0.0, ge=0)
    #: Every model the run actually called, in first-use order. FR62's cost
    #: split reprices a governed run at the baseline's rate, which needs to know
    #: what it ran on — and needs to refuse rather than guess once escalation
    #: makes this more than one.
    models_used: tuple[str, ...] = ()
    #: How many times the gate failed and the contract directed a retry on a
    #: stronger model. FR66 sets a threshold on the rate: an arm that escalates
    #: on everything has no cheap path and its saving came from elsewhere.
    escalations: int = Field(default=0, ge=0)
    parsed: Parsed | None = None
    terminal_reason: str | None = None
    #: A mechanism stopped the loop while the agent still wanted to continue.
    #: False when the agent finished by itself and a terminal reason was merely
    #: recorded afterwards — `stop-sufficient` on a run the gate only confirmed
    #: saved nothing, and crediting it would invent the product's whole claim.
    cut_short: bool = False
    iterations: int = Field(ge=0)
    #: Set where the loop stopped for its own reasons rather than the agent's.
    stopped_by: str | None = None


class Finish(BaseModel):
    """What the arm made of the agent's answer."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    terminal_reason: str | None = None
    #: The contract directs a retry on this model. The run continues.
    escalate_to: str | None = None


class Arm(Protocol):
    """The one thing the two arms disagree about."""

    name: str

    def run_tool(self, call: ToolCall) -> ToolOutcome: ...

    def charge_model_turn(
        self, *, step_id: str, tokens: int, cost: float, model_used: str
    ) -> str | None:
        """Returns a terminal reason where the run must stop."""
        ...

    def observe_progress(self, *, task_state: Any, evidence_count: int) -> str | None:
        """Tell the arm what changed this turn. Returns a terminal reason."""
        ...

    def finish(self, parsed: Parsed | None, *, answer_key: Any | None) -> Finish: ...

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
            # Kept as a backstop. The driver now catches a failing tool itself,
            # so that it can release the budget it reserved for it; this is here
            # only for a tool port that raises somewhere the driver does not
            # reach.
            return ToolOutcome(content=f"tool error: {exc}", refused=True)
        return _from_verdict(verdict)

    def charge_model_turn(
        self, *, step_id: str, tokens: int, cost: float, model_used: str
    ) -> str | None:
        verdict = self._driver.charge_model_turn(
            step_id=step_id, tokens=tokens, cost=cost, model_used=model_used
        )
        return verdict.terminal_reason if verdict is not None else None

    def observe_progress(self, *, task_state: Any, evidence_count: int) -> str | None:
        # FR27/FR28. Without this call the LoopFuse is wired to nothing and an
        # agent going round in circles is stopped only by the iteration cap,
        # having paid for every turn on the way.
        verdict = self._driver.observe_progress(
            task_state=task_state, evidence_count=evidence_count
        )
        return verdict.terminal_reason if verdict is not None else None

    def finish(self, parsed: Parsed | None, *, answer_key: Any | None) -> Finish:
        # `parsed is None` means the loop stopped for its own reasons. The run
        # is still closed through the ladder: a governed run left open has no
        # `run-closed`, cannot be sealed, and is not admissible evidence of
        # anything — including of the governor having behaved correctly.
        verdict = self._driver.submit_deliverable(
            parsed.deliverable if parsed is not None and parsed.ok else None,
            answer_key=answer_key,
            parse_failure=(
                parsed.failure if parsed is not None else "the agent produced no answer"
            ),
        )
        if verdict.escalate_to is not None:
            self._start_model = verdict.escalate_to
        return Finish(
            terminal_reason=verdict.terminal_reason, escalate_to=verdict.escalate_to
        )


class BaselineArm:
    """No governor. The tool runs, the answer is taken, the bill is what it is.

    FR52: the baseline holds no `Driver`. A driver with its mechanisms disabled
    would still impose the driver's own control flow — its ordering, its
    fail-closed paths, its bookkeeping — on the arm that is supposed to show
    what happens without any of it.

    It does take a `BaselineRecorder`, because recording is measurement rather
    than governance and an unrecorded arm cannot be admitted or paired. The
    recorder decides nothing.
    """

    name = "baseline"

    def __init__(
        self,
        tools: WorkloadToolPort,
        *,
        model: str,
        recorder: BaselineRecorder | None = None,
    ) -> None:
        self._tools = tools
        self._model = model
        self._recorder = recorder

    def model_id(self) -> str:
        return self._model

    def run_tool(self, call: ToolCall) -> ToolOutcome:
        try:
            result = self._tools.invoke(call)
        except ToolError as exc:
            if self._recorder is not None:
                self._recorder.observe_tool(call, failed=str(exc))
            return ToolOutcome(content=f"tool error: {exc}", refused=False)
        if self._recorder is not None:
            self._recorder.observe_tool(call)
        return ToolOutcome(content=_render(result.output))

    def charge_model_turn(
        self, *, step_id: str, tokens: int, cost: float, model_used: str
    ) -> str | None:
        # Recorded, never refused. There is no ledger here to say no — that is
        # the arm's entire point — but the spend still has to appear in the log.
        if self._recorder is not None:
            self._recorder.observe_model_turn(
                step_id=step_id, tokens=tokens, model_used=model_used
            )
        return None

    def observe_progress(self, *, task_state: Any, evidence_count: int) -> str | None:
        # No fuse. The baseline goes round until it finishes or hits the cap,
        # which is the behaviour the governed arm is measured against.
        return None

    def finish(self, parsed: Parsed | None, *, answer_key: Any | None) -> Finish:
        # The gate runs here, once, after the agent has already stopped of its
        # own accord. It scores; it does not steer. Running it any earlier would
        # hand the baseline the sufficiency stop that is the mechanism under
        # test, and the experiment would compare the governor against itself.
        #
        # It never escalates either. FR52's baseline has one model and keeps it.
        if self._recorder is not None:
            self._recorder.score(
                parsed.deliverable if parsed is not None and parsed.ok else None,
                answer_key=answer_key,
                parse_failure=(
                    parsed.failure if parsed is not None else "the agent produced no answer"
                ),
            )
        return Finish()


def _from_verdict(verdict: StepVerdict) -> ToolOutcome:
    if verdict.terminates:
        return ToolOutcome(
            content=f"the run was stopped: {verdict.decision_reason}",
            terminal_reason=verdict.terminal_reason,
        )
    if verdict.failed:
        # The call was allowed and the tool broke. The agent should read the
        # error and try something else, not conclude it is barred from the tool.
        return ToolOutcome(content=verdict.detail, refused=False)
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
    cost = 0.0
    models: list[str] = []
    escalations = 0
    parsed: Parsed | None = None
    terminal: str | None = None
    stopped_by: str | None = None
    finished = False
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
        if response.model_id not in models:
            models.append(response.model_id)

        turn_cost = (
            price(response.model_id, response.prompt_tokens, response.completion_tokens)
            if price is not None
            else 0.0
        )
        cost += turn_cost
        terminal = arm.charge_model_turn(
            step_id=step_id,
            tokens=response.prompt_tokens + response.completion_tokens,
            cost=turn_cost,
            model_used=response.provider_version or response.model_id,
        )
        if terminal is not None:
            return Outcome(
                case_id=case.case_id,
                arm=arm.name,
                spend=spend,
                cost=cost,
                models_used=tuple(models),
                terminal_reason=terminal,
                cut_short=True,
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
            outcome_of_finish = arm.finish(parsed, answer_key=answer_key)
            if outcome_of_finish.escalate_to is not None:
                # FR35. The contract directs a retry on a stronger model, so the
                # run continues. The transcript is dropped rather than carried:
                # a fresh attempt is what the contract asks for, and handing the
                # stronger model the weaker one's failed reasoning anchors it to
                # exactly the answer that just failed the gate.
                escalations += 1
                messages = [
                    Message(role="system", content=prompt.system),
                    Message(role="user", content=prompt.user),
                ]
                parsed = None
                continue
            terminal = outcome_of_finish.terminal_reason
            finished = True
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

        # FR27/FR28: the host says what changed, the arm decides what it means.
        # `task_state` is the conversation's own shape, so an agent repeating
        # the same call with the same result produces the same fingerprint.
        terminal = arm.observe_progress(
            task_state=tuple(
                (m.role, m.content[:200]) for m in messages[-len(response.tool_calls) * 2 :]
            ),
            evidence_count=spend.tool_calls,
        )
        if terminal is not None:
            break
    else:
        # The `while` ran out rather than breaking: the agent never stopped.
        stopped_by = f"the agent did not finish within {max_iterations} turns"

    if not finished and terminal is None:
        # The loop gave up. The run is still closed through the arm: a governed
        # run left open has no `run-closed`, cannot be sealed, and is not
        # admissible evidence of anything — including of the governor having
        # behaved correctly.
        terminal = arm.finish(None, answer_key=answer_key).terminal_reason

    return Outcome(
        case_id=case.case_id,
        arm=arm.name,
        spend=spend,
        cost=cost,
        models_used=tuple(models),
        parsed=parsed,
        terminal_reason=terminal,
        escalations=escalations,
        # `finished` means the agent stopped asking for tools of its own accord.
        # Anything terminal recorded after that confirmed the run; it did not
        # shorten it.
        cut_short=terminal is not None and not finished,
        iterations=iteration,
        stopped_by=stopped_by,
    )
