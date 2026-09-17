"""The mechanisms, and the agents that provoke them. **No wording lives here.**

A situation is a mechanism plus an agent that makes it fire. It carries `does`
and `feature` because those describe the mechanism, and nothing else: every
headline the console shows belongs to a job card in `console/jobs.py`, so a
situation cannot say one thing on the gallery and a card say another.

A situation is data and so is a `Work`, and one runner takes both plus an arm.
Any situation therefore runs on any work, with the governor plugged in or out,
from a single definition — so the arms cannot drift and neither can the work.
The console shows twelve chosen points of that matrix; `compare.py` and the
tests sweep all of it, which is where verification belongs.

Not every situation fits every work. `applies` says which, and the one that does
not generalise says why: only three of the four works have a tool that leaves the
dataset at all.

`authored` is the honesty flag. Most of these need an agent that misbehaves —
detecting a stall requires a stall. Nothing measured should ever be read off an
authored situation.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from features import compose, work
from features.work import Work

GOVERNED = "governed"
BASELINE = "baseline"

Agent = Callable[[Work, dict[str, Any], Any], list[Any]]


@dataclass(frozen=True)
class Situation:
    key: str
    #: What OutcomeFuse does about it, as a default. A card may say it better.
    does: str
    #: The mechanism, named for anyone who wants it. Never a headline.
    feature: str
    agent: Agent
    #: A mutation of the frozen contract, where the frozen one cannot show this.
    mutate: Callable[[dict[str, Any]], None] | None = None
    variant: str = ""
    approval: str | None = "approved"
    authored: bool = True
    expect: str = ""
    #: Which works this situation makes sense for.
    applies: Callable[[Work], bool] = lambda _work: True


def _shrink(raw: dict[str, Any]) -> None:
    raw["budget"]["max_tokens"] = 2_000
    raw["budget"]["verification_reserve"] = {"max_tokens": 200, "max_estimated_cost": 0.01}


def _human(raw: dict[str, Any]) -> None:
    raw["escalation"]["on_gate_fail"] = "request-human"
    raw["escalation"]["max_escalations"] = 0


SITUATIONS: tuple[Situation, ...] = (
    Situation(
        key="acts",
        does="Stops the run and waits for a person to authorise it, before the tool is "
        "invoked rather than after.",
        feature="Human approval on a side-effecting tool",
        agent=work.acts_on_the_world,
        approval=None,
        authored=False,
        applies=lambda work: work.side_effecting is not None,
        expect="the ungoverned arm acts while you are still deciding",
    ),
    Situation(
        key="stall",
        does="Serves the repeat from the run's cache so the tool is never re-invoked, "
        "then stops the run once it can see no progress is being made.",
        feature="Tool-governor cache, then the loop fuse (FR27/FR28)",
        agent=work.stalls,
        expect="the governed arm executes the tool once and then stops; the ungoverned one "
        "runs it every time and keeps going",
    ),
    Situation(
        key="failing-tool",
        does="Gives back the budget it had reserved for each failed call, records the "
        "error, and tells the agent it **failed** rather than that it was barred. It "
        "does not stop the failures \u2014 nothing can.",
        feature="Holds released on failure; a failure is not a denial",
        agent=work.keeps_failing,
        # Measured, not assumed: both arms try the same calls, get the same errors
        # and reach the same answer. The contribution here is accounting, not
        # prevention, and claiming otherwise is a lie the comparison would catch.
        expect="",
    ),
    Situation(
        key="exhaustion",
        does="Asks whether the next step is affordable **before** deciding to take it, so "
        "the ceiling is never crossed \u2014 the run halts at it.",
        feature="The ledger and the budget ceiling (FR92)",
        agent=work.burns_turns,
        mutate=_shrink,
        variant="max_tokens: 2,000",
        expect="the governed arm stops at the ceiling; the ungoverned one has no ceiling "
        "to stop at",
    ),
    Situation(
        key="escalation",
        does="Refuses the answer at the quality gate and retries on a stronger model, "
        "inheriting the evidence already gathered rather than re-fetching it.",
        feature="Model routing and escalation (FR35)",
        agent=work.unusable_then_right,
        expect="the governed arm retries and gets it right; the ungoverned one keeps its "
        "first, unusable answer",
    ),
    Situation(
        key="partial",
        does="Spends its one escalation, refuses the answer again, and hands back what it "
        "had \u2014 labelled as partial rather than passed off as an answer.",
        feature="The FR103 ladder \u2014 returned-partial",
        agent=work.always_wrong,
        expect="the governed arm names why it stopped; the ungoverned one just stops",
    ),
    Situation(
        key="refer",
        does="Same ladder, different row: refers the case to a human instead of handing "
        "back a partial answer. The contract chooses, not the code.",
        feature="The FR103 ladder \u2014 referred-human",
        agent=work.always_wrong,
        mutate=_human,
        variant="on_gate_fail: request-human, max_escalations: 0",
        expect="the governed arm refers it to a person",
    ),
    Situation(
        key="revisits",
        does="Sends a reference to the copy already in the conversation instead of a "
        "second copy of the same bytes. Nothing is summarised and nothing is dropped, "
        "so the agent loses no fact \u2014 it just stops being told it twice.",
        feature="The context governor (F7, FR36-FR39)",
        agent=work.revisits,
        # Not authored to misbehave: keeping the thing you are reasoning about in
        # front of you is what a competent agent does. The waste is in the
        # transcript, not in the agent.
        authored=False,
        expect="the governed arm carries the repeated result once; the ungoverned one "
        "carries a fresh copy in every later prompt",
    ),
    Situation(
        key="unknown-tool",
        does="**Kills the run.** The governor raises, the driver files it as a governing "
        "component failure, and the run ends fail-closed with no answer. This is a "
        "defect, shown rather than hidden.",
        feature="A known defect in the failure posture",
        agent=work.invents_a_tool,
        expect="the governed arm dies with no answer; the ungoverned one shrugs and passes "
        "\u2014 the governor is strictly worse here",
    ),
    Situation(
        key="happy",
        does="Nothing it did not have to. Every step is proposed, reserved, recorded and "
        "settled in that order, and the run is stopped once the floor is met.",
        feature="The whole loop: contract, ledger, gate, sufficiency stop",
        agent=work.correct,
        authored=False,
        expect="",
    ),
)


def for_work(work: Work) -> tuple[Situation, ...]:
    return tuple(s for s in SITUATIONS if s.applies(work))


def by_key(key: str) -> Situation:
    for situation in SITUATIONS:
        if situation.key == key:
            return situation
    raise KeyError(key)


def is_interactive(situation: Situation, work: Work) -> bool:
    """Only a clause the governor can read can stop and wait for anybody."""
    return situation.key == "acts" and work.gate_fires


def run(
    situation: Situation,
    work: Work,
    *,
    arm: str,
    runs_dir: Path,
    case_id: str,
    sink: Any = None,
    approval: Any = None,
    token: str = "",
) -> compose.Run:
    """One situation, on one work, on one arm.

    Both arms get the same agent, the same contract and the same tools, built
    from one definition — so nothing here can flatter the governor without
    flattering its control identically.

    `token` makes the run id unique. Two runs of the same job are two runs with
    two seals, and sharing an id would also have them share a database file —
    which on Windows means the second one cannot open it while the first still
    holds it. Callers that run a job once, like the feature report, leave it
    empty and keep the readable deterministic id.
    """
    subject = compose.case(case_id, work.workload)
    key = compose.key_for(case_id, work.workload)
    turns = situation.agent(work, key, subject)
    spec = (
        compose.variant(situation.mutate, work.workload)
        if situation.mutate
        else compose.contract(work.workload)
    )
    tag = f"{work.workload}-{situation.key}" + (f"-{token}" if token else "")

    if arm == BASELINE:
        # FR52: the baseline holds no Driver at all, so there is no ledger, no
        # mid-run gate and no approval channel for an answer to reach.
        return compose.ungoverned(
            subject, turns=turns, runs_dir=runs_dir, spec=spec, tag=f"{tag}-off", sink=sink
        )
    live = is_interactive(situation, work)
    return compose.governed(
        subject,
        turns=turns,
        runs_dir=runs_dir,
        spec=spec,
        approval=approval if live else (situation.approval or "approved"),
        tag=tag,
        sink=sink,
    )
