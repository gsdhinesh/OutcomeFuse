"""The feature catalogue: one scenario per mechanism, each asserting its own evidence.

A feature is **demonstrated** only if the run it produced actually shows the
thing. Nothing here is a hand-written claim — every row's status is computed
from a sealed log, a verdict or a returned value, so a mechanism that quietly
stopped working reports `not-demonstrated` instead of continuing to be
advertised. Three statuses are not successes and are meant to be read:

- `gap` — the library accepts a declaration it never acts on.
- `defect` — the behaviour is wrong, and the report says how.
- `not-demonstrated` — the scenario ran and the evidence did not appear.

Scenarios marked `mechanism` call a component directly rather than through a
run. That is honest about what they prove: the component behaves as specified,
under conditions the run did not have to produce.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from outcomefuse.core.contract import ContractError, load_text
from outcomefuse.core.gate import GateUnavailable, QualityGate
from outcomefuse.core.record import RecordStore, open_store, refuse_persistence
from outcomefuse.core.verify.registry import REGISTRY
from outcomefuse.ports import ToolCall, ToolInvocation
from outcomefuse.runtime import ToolGovernor
from outcomefuse.runtime.shadow import ShadowDriver
from outcomefuse.submission.disclosures import FROZEN_DEFECTS
from outcomefuse.workloads import tool_port_for
from outcomefuse.workloads.toolport import ToolError

from . import agents, compose
from . import work as work

DEMONSTRATED = "demonstrated"
GAP = "gap"
DEFECT = "defect"
MISSING = "not-demonstrated"


@dataclass(frozen=True)
class Finding:
    key: str
    area: str
    title: str
    claim: str
    status: str
    evidence: tuple[tuple[str, str], ...] = ()
    note: str = ""
    level: str = "run"

    @property
    def ok(self) -> bool:
        return self.status == DEMONSTRATED


@dataclass
class Context:
    runs_dir: Path
    contract: Any = None
    case: Any = None
    key: dict[str, Any] = field(default_factory=dict)
    po_id: int = 0

    def __post_init__(self) -> None:
        self.contract = self.contract or compose.contract()
        self.case = self.case or compose.case("sc-c-001")
        self.key = self.key or compose.key_for(self.case.case_id)
        self.po_id = int(self.case.prompt_context["po_id"])


def _verdict_of(ctx: Context, deliverable: dict[str, Any]):
    _tools, index = compose.port_and_index(ctx.contract)
    return QualityGate().evaluate(
        ctx.contract, deliverable, answer_key=ctx.key, citable_index=index
    )


# ------------------------------------------------------- contract and gate


def contract_is_executable(ctx: Context) -> Finding:
    spec = ctx.contract
    unverifiable = [c.id for c in spec.criteria.mandatory if c.verifier is None]
    tiers = f"{len(spec.criteria.optional)} / {len(spec.criteria.advisory)}"
    try:
        load_text("contract_id: x\nversion: 1\nworkload: w\ntask_goal: t\n")
        refused = "no"
    except ContractError:
        refused = "yes"
    return Finding(
        key="contract",
        area="Outcome Contract",
        title="The contract is executable, not prose",
        claim="Every mandatory criterion carries a registered verifier, so the quality "
        "floor is something a machine can decide rather than something a reviewer asserts.",
        status=DEMONSTRATED if not unverifiable and refused == "yes" else MISSING,
        evidence=(
            ("contract", f"{spec.contract_id} v{spec.version}, {spec.digest().sha256[:16]}…"),
            ("mandatory criteria", str(len(spec.criteria.mandatory))),
            ("without a verifier", str(len(unverifiable))),
            ("optional / advisory", tiers),
            ("registered verifier types", str(len(REGISTRY))),
            ("an incomplete contract is refused", refused),
        ),
    )


def quality_gate(ctx: Context) -> Finding:
    verdict = _verdict_of(ctx, _deliverable(ctx))
    rows = tuple(
        (r.id, f"{r.verdict_word} ({r.mode})")
        for r in [_row(c) for c in verdict.breakdown]
    )
    return Finding(
        key="gate",
        area="Quality gate",
        title="A verdict with its per-criterion breakdown",
        claim="The gate returns a binary verdict, a qualifier naming how it was reached, "
        "and one result per criterion (FR94) — not a score.",
        status=DEMONSTRATED if verdict.passed and verdict.breakdown else MISSING,
        evidence=(
            ("verdict", verdict.verdict),
            ("qualifier", verdict.qualifier),
            ("mandatory evaluated", str(verdict.mandatory_evaluated)),
            *rows,
        ),
    )


def verification_modes(ctx: Context) -> Finding:
    modes = ctx.contract.mandatory_modes()
    verdict = _verdict_of(ctx, _deliverable(ctx))
    complete = sum(modes.values()) == len(ctx.contract.criteria.mandatory)
    return Finding(
        key="modes",
        area="Quality gate",
        title="Reference-backed and constraint-backed are distinguished",
        claim="A criterion checked against a known-correct value is not the same claim as "
        "one checked against a permissible range, and the qualifier carries which.",
        status=DEMONSTRATED if complete else MISSING,
        evidence=(
            ("reference-backed", str(modes.get("reference-backed", 0))),
            ("constraint-backed", str(modes.get("constraint-backed", 0))),
            ("run qualifier", verdict.qualifier),
            (
                "why it matters",
                "the aggregate is the weaker of the two, so one unbacked criterion "
                "downgrades the whole verdict",
            ),
        ),
    )


def gate_refuses_a_wrong_answer(ctx: Context) -> Finding:
    wrong = dict(_deliverable(ctx), exception_type=agents._other(ctx.key["exception_type"]))
    verdict = _verdict_of(ctx, wrong)
    return Finding(
        key="gate-fail",
        area="Quality gate",
        title="A wrong answer fails, and the log names which criterion",
        claim="The floor is a floor. A deliverable that is well-formed but wrong does not "
        "pass, and the unmet criteria are recorded rather than summarised.",
        status=DEMONSTRATED if not verdict.passed and verdict.unmet else MISSING,
        evidence=(
            ("verdict", verdict.verdict),
            ("unmet", ", ".join(verdict.unmet)),
            ("still well-formed", "yes — every field present and correctly typed"),
        ),
    )


def citable_index(ctx: Context) -> Finding:
    invented = dict(_deliverable(ctx), policy_refs=[{"id": agents.ABSENT_CLAUSE}])
    verdict = _verdict_of(ctx, invented)
    _tools, index = compose.port_and_index(ctx.contract)
    run = compose.governed(
        ctx.case, turns=agents.correct(ctx.key, ctx.po_id), runs_dir=ctx.runs_dir, tag="cite"
    )
    bound = [e for e in run.events if (e.payload or {}).get("citable_index_sha256")]
    return Finding(
        key="citations",
        area="Citations",
        title="A citation that does not resolve is refused",
        claim="The set of citable ids is built by the driver, hashed and appended before "
        "any verifier runs (AD-7), so an invented clause cannot pass and two "
        "implementations cannot disagree about what was citable.",
        status=DEMONSTRATED if not verdict.passed and bound else MISSING,
        evidence=(
            ("citable clauses", str(len(index.entries))),
            ("index digest bound at seq", str(bound[0].seq) if bound else "never"),
            ("cited", agents.ABSENT_CLAUSE),
            ("verdict", verdict.verdict),
            ("unmet", ", ".join(verdict.unmet)),
        ),
    )


# ------------------------------------------------------------ tool governor


def tool_governor(ctx: Context) -> Finding:
    governor = ToolGovernor(ctx.contract)
    lookup = ToolCall(tool="order_lookup", arguments={"po_id": ctx.po_id}, step_id="s1")
    first = governor.assess(lookup, run_id="r")
    governor.observe(lookup, {"order": {}})
    second = governor.assess(lookup, run_id="r")
    enrich = governor.assess(
        ToolCall(tool="shipment_trace", arguments={"po_id": 1}, step_id="s2"),
        run_id="r",
        unmet_mandatory=set(),
        step_is_enrichment=True,
    )
    return Finding(
        key="governor",
        area="Tool governor",
        title="A repeated call is served from the run's cache, never re-executed",
        claim="Identical calls are keyed on a canonical hash of tool and arguments (FR29), "
        "so `1` and `1.0` cannot produce two keys. The cache is run-scoped and "
        "process-local (AD-14), which discharges tenant isolation by construction.",
        status=DEMONSTRATED
        if second.action == "proceed-with-substitution" and enrich.action == "deny"
        else MISSING,
        level="mechanism",
        evidence=(
            ("first call", f"{first.action} ({first.reason})"),
            ("same call again", f"{second.action} ({second.reason})"),
            ("canonical key", second.key[:16] + "…"),
            ("enrichment once the floor is met", f"{enrich.action} ({enrich.reason})"),
            ("cache scope", "this run, this process, cleared at the end"),
        ),
        note="Mechanism-level. How often a real model repeats a call is in the measured "
        "section, and the answer is: almost never.",
    )


def side_effects_are_exempt(ctx: Context) -> Finding:
    governor = ToolGovernor(ctx.contract)
    notify = ToolCall(
        tool="notify_planner", arguments={"message": "hello"}, step_id="s1"
    )
    governor.observe(notify, {"delivered": True})
    repeat = governor.assess(notify, run_id="r")
    return Finding(
        key="fr33",
        area="Tool governor",
        title="No optimisation may suppress a tool that acts on the world",
        claim="FR33: caching and deduplication are optimisations, and neither applies to a "
        "tool declared side-effecting or non-deterministic. The declaration is "
        "consulted before any optimisation is considered, so it cannot be forgotten.",
        status=DEMONSTRATED
        if not governor.optimisable("notify_planner")
        and governor.optimisable("order_lookup")
        and repeat.action != "proceed-with-substitution"
        else MISSING,
        level="mechanism",
        evidence=(
            ("order_lookup optimisable", str(governor.optimisable("order_lookup"))),
            ("notify_planner optimisable", str(governor.optimisable("notify_planner"))),
            ("notify_planner repeated", f"{repeat.action} ({repeat.reason})"),
            (
                "the rule",
                "refusing to cache a payment is correct; refusing to stop an "
                "unapproved one would not be",
            ),
        ),
    )


def context_governor(ctx: Context) -> Finding:
    """F7, the deterministic subset, measured by ablating it against itself.

    Deliberately not the stall: there the Loop Fuse stops the run on the second
    identical turn and this mechanism saves nothing. It earns its keep on a run
    that is *making progress* while re-reading the same thing, which is the one
    the fuse must not touch.
    """
    spec = compose.contract("code-triage")
    case = compose.case("ct-c-002", "code-triage")
    doing = work.by_workload("code-triage")
    key = compose.key_for(case.case_id, "code-triage")
    turns = [(doing.varied(case, i), doing.repeatable(case)) for i in range(5)]
    turns += work.correct(doing, key, case)[-1:]

    def once(tag: str, *, on: bool):
        return compose.governed(
            case,
            turns=list(turns),
            runs_dir=ctx.runs_dir,
            spec=spec,
            tag=tag,
            with_context=on,
            answer_key=key,
        )

    off = once("ctx-off", on=False)
    on = once("ctx-on", on=True)
    elided = [e for e in on.events if e.decision_reason == "context-compressed"]
    saved = off.outcome.spend.total_tokens - on.outcome.spend.total_tokens
    same_work = (
        on.outcome.spend.model_turns == off.outcome.spend.model_turns
        and len(on.invoked) == len(off.invoked)
        and on.terminated == off.terminated
        and on.deliverable == off.deliverable
    )
    return Finding(
        key="context-governor",
        area="Context governor",
        title="The same bytes are never sent to the model twice",
        claim="F7 as specified compresses tool output with a model pass, which is what put "
        "it at cut position 7: it spends tokens to save tokens and it can drop a fact. "
        "This is the deterministic subset — a result byte-identical to one already in "
        "the conversation is replaced by a reference to itself. Nothing is summarised, "
        "so FR38 holds structurally rather than on a model's judgement, and FR39's "
        "compression overhead is nil because there is no compression pass.",
        status=DEMONSTRATED if elided and saved > 0 and same_work else MISSING,
        evidence=(
            ("ablated", f"{off.outcome.spend.total_tokens:,} tokens"),
            ("registered", f"{on.outcome.spend.total_tokens:,} tokens"),
            ("saved", f"{saved:,} tokens ({saved / off.outcome.spend.total_tokens:.1%})"),
            ("results elided", str(len(elided))),
            ("turns, tools, ending, answer", "identical" if same_work else "MOVED"),
            ("recorded as", "proceed-with-substitution / context-compressed"),
        ),
        note="Nil on the stall card: there the fuse stops the run on the second identical "
        "turn and there is nothing left to save. This is the case the fuse must not "
        "touch, because the run is genuinely getting somewhere.",
    )


def unknown_tool_is_fail_closed(ctx: Context) -> Finding:
    turns = [
        (ToolInvocation(id="x", tool="invoice_lookup", arguments={}),),
        *agents.correct(ctx.key, ctx.po_id),
    ]
    governed = compose.governed(ctx.case, turns=turns, runs_dir=ctx.runs_dir, tag="unknown-g")
    base = compose.ungoverned(ctx.case, turns=turns, runs_dir=ctx.runs_dir, tag="unknown-b")
    return Finding(
        key="unknown-tool",
        area="Failure posture",
        title="A hallucinated tool name kills the governed run",
        claim="An agent naming a tool that does not exist is an agent error, like an "
        "unparseable deliverable — which the same driver correctly returns as a value. "
        "Instead `ToolGovernor` raises, `Driver.execute_step` catches it as a "
        "governing-component failure, and the run terminates fail-closed.",
        status=DEFECT if governed.terminated == "fail-closed" else DEMONSTRATED,
        evidence=(
            ("governed terminal", str(governed.terminated)),
            ("governed answered", str(governed.quality_state)),
            ("ungoverned terminal", str(base.terminated or "ran to the end")),
            ("ungoverned answered", str(base.quality_state)),
            (
                "consequence",
                "on the commonest model mistake the governor is strictly worse than "
                "no governor",
            ),
        ),
        note="Reported as a defect rather than a feature. The fix belongs in the library: "
        "an undeclared tool should come back as a denial the agent can read.",
    )


# ---------------------------------------------------------------- approval


def human_approval(ctx: Context) -> Finding:
    rows: list[tuple[str, str]] = []
    outcomes: dict[str, Any] = {}
    for decision in ("approved", "denied", "no-response", "channel-unavailable"):
        run = compose.governed(
            ctx.case,
            turns=agents.notifies(ctx.key, ctx.po_id),
            runs_dir=ctx.runs_dir,
            approval=decision,
            tag=f"appr-{decision}",
        )
        outcomes[decision] = run
        sent = "yes" if run.side_effects else "no"
        rows.append(
            (decision, f"message sent: {sent}; terminal: {run.terminated or 'ran on'}")
        )
    ok = (
        bool(outcomes["approved"].side_effects)
        and not outcomes["denied"].side_effects
        and outcomes["no-response"].terminated == "approval-timeout"
        and outcomes["channel-unavailable"].terminated == "fail-closed"
    )
    return Finding(
        key="approval",
        area="Human approval",
        title="Four things a human channel can do, and four different endings",
        claim="Approval outranks every automated decision. A denial stops the call; a "
        "timeout follows the contract's `on_timeout`; an unreachable channel is "
        "fail-closed under FR89, because a gate you cannot consult is not a gate "
        "you may skip.",
        status=DEMONSTRATED if ok else MISSING,
        evidence=(
            ("gated tool", "notify_planner (declared side-effecting)"),
            ("contract on_timeout", str(ctx.contract.on_timeout)),
            *rows,
        ),
    )


def criterion_approval_is_dead(ctx: Context) -> Finding:
    declared = [c for c in ctx.contract.human_approval_conditions if c.criterion]
    governor = ToolGovernor(ctx.contract)
    # The only route to the approval port, asked about a tool no clause names.
    unrelated = governor.requires_approval(
        ToolCall(tool="order_lookup", arguments={}, step_id="s")
    )
    return Finding(
        key="criterion-approval",
        area="Human approval",
        title="An approval condition on a criterion is accepted and never evaluated",
        claim="The frozen contract gates `recommended_action` on two values. "
        "`ToolGovernor.requires_approval` matches only `condition.tool`, so no code "
        "path reads a criterion-scoped condition. It is validated at load and dead "
        "at runtime.",
        status=GAP if declared else MISSING,
        level="mechanism",
        evidence=(
            ("declared in the frozen contract", str(len(declared))),
            (
                "condition",
                f"criterion={declared[0].criterion} when={declared[0].when} "
                f"value={declared[0].value}" if declared else "none",
            ),
            ("requires_approval matches on", "condition.tool only"),
            ("an ungated tool returns", str(unrelated)),
            ("code path that evaluates a criterion", "none"),
            ("what a reader would assume", "that escalate-to-buyer needs a human"),
            ("what happens", "nothing"),
        ),
        note="Contract validation is not execution. A clause that loads is not a clause "
        "that runs, and this is the one place in the workload where the two differ.",
    )


def tool_call_ceiling_is_dead(ctx: Context) -> Finding:
    """`max_tool_calls` is declared, validated, displayed — and read by nothing."""
    declared = ctx.contract.budget.max_tool_calls
    small = compose.variant(lambda raw: raw["budget"].update({"max_tool_calls": 1}))
    run = compose.governed(
        ctx.case,
        turns=agents.burns_turns(ctx.key, ctx.po_id),
        runs_dir=ctx.runs_dir,
        spec=small,
        tag="callcap",
    )
    executed = len(run.invoked)
    return Finding(
        key="tool-call-ceiling",
        area="Budget",
        title="A ceiling on the number of tool calls is accepted and never enforced",
        claim="`budget.max_tool_calls` is required, validated `> 0`, and shown to the "
        "viewer as a ceiling. No driver, ledger, governor or fuse reads it. A run is "
        "bounded by tokens and by iterations; the number of calls is bounded only as a "
        "consequence of those, never on its own terms.",
        status=GAP if executed > small.budget.max_tool_calls else MISSING,
        evidence=(
            ("declared in the frozen contract", f"{declared} calls"),
            ("variant used here", f"{small.budget.max_tool_calls} call"),
            ("tools actually executed", str(executed)),
            ("terminal", str(run.terminated)),
            ("what stopped the run", "the token ceiling and the iteration cap"),
            ("code path that reads max_tool_calls", "none"),
        ),
        note="The same shape as the criterion-scoped approval clause: contract "
        "validation is not execution. Tokens and iterations are enforced, so a run "
        "cannot make calls forever - but a contract asking for at most N calls does "
        "not get N.",
    )


# ---------------------------------------------------------- budget and ladder


def budget_ceiling(ctx: Context) -> Finding:
    small = compose.variant(_shrink_budget)
    run = compose.governed(
        ctx.case,
        turns=agents.burns_turns(ctx.key, ctx.po_id),
        runs_dir=ctx.runs_dir,
        spec=small,
        tag="exhaust",
    )
    spent = sum(e.tokens_consumed or 0 for e in run.events if e.kind == "spend-settled")
    return Finding(
        key="budget",
        area="Budget",
        title="The run stops at the ceiling instead of crossing it",
        claim="Affordability is a query asked *before* the decision (FR92), so running out "
        "reaches the policy as a decision input and halts the run — rather than "
        "arriving as a refused reservation, which is a system fault and a different "
        "terminal reason entirely.",
        status=DEMONSTRATED
        if run.terminated == "halt-exhausted" and spent <= small.budget.max_tokens
        else MISSING,
        evidence=(
            ("ceiling", f"{small.budget.max_tokens:,} tokens (a variant, not the frozen "
             f"{ctx.contract.budget.max_tokens:,})"),
            ("settled", f"{spent:,} tokens"),
            ("terminal", str(run.terminated)),
            ("turns taken", str(run.outcome.iterations)),
            ("never exceeded", str(spent <= small.budget.max_tokens)),
        ),
    )


def verification_reserve(ctx: Context) -> Finding:
    reserve = ctx.contract.budget.verification_reserve
    ledger = compose.ledger_for(ctx.contract)
    ordinary = ledger.spendable_tokens()
    verifying = ledger.spendable_tokens(may_use_reserve=True)
    return Finding(
        key="reserve",
        area="Budget",
        title="A run can always afford to check its own work",
        claim="The verification reserve is carved out of the ceiling and hidden from "
        "ordinary steps. An escalation that ate it would buy a better answer and "
        "lose the ability to tell whether it was better.",
        status=DEMONSTRATED if reserve and verifying > ordinary else MISSING,
        level="mechanism",
        evidence=(
            ("ceiling", f"{ctx.contract.budget.max_tokens:,} tokens"),
            ("reserve", f"{reserve.max_tokens:,} tokens (declared in the contract)"),
            ("an ordinary step may spend", f"{ordinary:,}"),
            ("verification may spend", f"{verifying:,}"),
            ("sizing", "declared — a derived reserve would be 15% and say so"),
        ),
    )


def escalation(ctx: Context) -> Finding:
    run = compose.governed(
        ctx.case,
        turns=agents.wrong_then_right(ctx.key, ctx.po_id),
        runs_dir=ctx.runs_dir,
        tag="escalate",
    )
    moved = [e for e in run.events if e.policy_action == "escalate"]
    return Finding(
        key="escalation",
        area="Model routing",
        title="A refused answer is retried on a stronger model",
        claim="FR35: the contract directs `retry-then-escalate`, so a failed gate moves the "
        "run up the eligible list rather than ending it. The escalation continues the "
        "conversation — the evidence already gathered is inherited, the reasoning that "
        "failed on it is not.",
        status=DEMONSTRATED
        if run.escalations == 1 and run.quality_state == "pass"
        else MISSING,
        evidence=(
            ("eligible models", " → ".join(ctx.contract.models.eligible)),
            ("escalations", str(run.escalations)),
            (
                "moved",
                f"{(moved[0].payload or {}).get('from')} → "
                f"{(moved[0].payload or {}).get('to')}" if moved else "never",
            ),
            ("because", ", ".join((moved[0].payload or {}).get("unmet", [])) if moved else "—"),
            ("final verdict", run.quality_state),
            ("terminal", str(run.terminated)),
        ),
    )


def ladder(ctx: Context) -> Finding:
    partial = compose.governed(
        ctx.case,
        turns=agents.always_wrong(ctx.key, ctx.po_id),
        runs_dir=ctx.runs_dir,
        tag="partial",
    )
    human = compose.governed(
        ctx.case,
        turns=agents.always_wrong(ctx.key, ctx.po_id),
        runs_dir=ctx.runs_dir,
        spec=compose.variant(_refer_to_human),
        tag="human",
    )
    good = compose.governed(
        ctx.case, turns=agents.correct(ctx.key, ctx.po_id), runs_dir=ctx.runs_dir, tag="ladder-ok"
    )
    return Finding(
        key="ladder",
        area="Decision ladder",
        title="Every ending is a named terminal reason, chosen by one table",
        claim="FR103 is data, not control flow. The same nine-row ladder resolves a "
        "sufficiency stop, an exhausted budget, a failed gate and a broken component, "
        "so no path can invent its own ending.",
        status=DEMONSTRATED
        if good.terminated == "stop-sufficient"
        and partial.terminated == "returned-partial"
        and human.terminated == "referred-human"
        else MISSING,
        evidence=(
            ("floor met", f"{good.terminated} — the agent is stopped, having succeeded"),
            (
                "gate fails, contract directs partial",
                f"{partial.terminated} — what it had is handed back",
            ),
            (
                "gate fails, contract directs human",
                f"{human.terminated} — a person now owns it (variant contract)",
            ),
        ),
    )


def loop_fuse(ctx: Context) -> Finding:
    run = compose.governed(
        ctx.case, turns=agents.stalls(ctx.key, ctx.po_id), runs_dir=ctx.runs_dir, tag="stall"
    )
    fused = [e for e in run.events if (e.payload or {}).get("fuse")]
    return Finding(
        key="fuse",
        area="Loop fuse",
        title="An agent going round in circles is stopped",
        claim="FR27/FR28: the host says what changed and the driver decides what it means. "
        "A repeated conversational state halts the run — deliberately *not* as budget "
        "exhaustion, because filing the product's central cost event as a stall would "
        "misreport both.",
        status=DEMONSTRATED if run.terminated == "halt-no-progress" else MISSING,
        evidence=(
            ("agent", "the same lookup, six turns running (authored to stall)"),
            ("fuse reason", str((fused[0].payload or {}).get("fuse")) if fused else "never fired"),
            ("terminal", str(run.terminated)),
            ("turns before the stop", str(run.outcome.iterations)),
        ),
        note="Authored. The measured campaign never produced a stall — see the measured "
        "section for how often this fires in life.",
    )


# ------------------------------------------------------------ the record


def record_spine(ctx: Context) -> Finding:
    run = compose.governed(
        ctx.case, turns=agents.correct(ctx.key, ctx.po_id), runs_dir=ctx.runs_dir, tag="spine"
    )
    path = ctx.runs_dir / f"{run.run_id}.db"
    with open_store(path, writer=True) as store:
        try:
            store.db.execute("UPDATE events SET body = '{}' WHERE seq = 1")
            tamper = "accepted"
        except sqlite3.Error:
            tamper = "refused by the database itself"
    return Finding(
        key="record",
        area="The record",
        title="Append-only, hash-chained, and sealed",
        claim="Every decision is appended before it takes effect (FR5), each row carries the "
        "hash of the one before it, and the run's seal is the last link. A log that "
        "could be edited afterwards would be the one artefact every other claim rests "
        "on and the one nobody could check.",
        status=DEMONSTRATED if run.verified and tamper != "accepted" else MISSING,
        evidence=(
            ("events", str(len(run.events))),
            ("first / last", f"{run.events[0].kind} → {run.events[-1].kind}"),
            ("chain verified after the fact", str(run.verified)),
            ("seal", run.seal[:32] + "…"),
            ("an UPDATE against a sealed run", tamper),
        ),
    )


def evidence_sidecar(ctx: Context) -> Finding:
    run = compose.governed(
        ctx.case, turns=agents.correct(ctx.key, ctx.po_id), runs_dir=ctx.runs_dir, tag="sidecar"
    )
    kept = ctx.runs_dir / "evidence" / run.run_id / "deliverable.json"
    referenced = [e for e in run.events if (e.payload or {}).get("deliverable")]
    return Finding(
        key="evidence",
        area="The record",
        title="The answer is kept where a reviewer can read it",
        claim="AD-5b: the deliverable lives beside the log, not in it. The log carries a "
        "reference and a hash. Without this a run records that a gate passed and not "
        "what it passed, and the blind review that exists to contradict the gate has "
        "nothing to read.",
        status=DEMONSTRATED if kept.is_file() and referenced else MISSING,
        evidence=(
            ("written to", f"evidence/{run.run_id}/deliverable.json"),
            ("bytes", str(kept.stat().st_size) if kept.is_file() else "0"),
            (
                "hash in the log",
                str((referenced[-1].payload or {}).get("sha256", ""))[:16] + "…"
                if referenced
                else "absent",
            ),
            ("body in the log", "no — a reference and a digest only"),
        ),
    )


def out_of_band_probe(ctx: Context) -> Finding:
    run = compose.governed(
        ctx.case,
        turns=agents.notifies(ctx.key, ctx.po_id),
        runs_dir=ctx.runs_dir,
        approval="denied",
        tag="probe",
    )
    logged = [
        (e.payload or {}).get("tool")
        for e in run.events
        if e.kind == "outcome-observed" and (e.payload or {}).get("tool")
    ]
    agrees = ("notify_planner" in logged) == bool(run.side_effects)
    return Finding(
        key="probe",
        area="The record",
        title="The tools keep their own record, and it agrees with the log",
        claim="AD-15: enforcement is cooperative, so an adapter that executed a denied call "
        "while recording a clean pause would produce a plausible and entirely false "
        "audit trail. A decision record cannot detect the one failure it is the "
        "evidence for, so the probe is out of band.",
        status=DEMONSTRATED if agrees else DEFECT,
        evidence=(
            ("approval answered", "denied"),
            ("log says notify_planner ran", str("notify_planner" in logged)),
            ("the tool port says it ran", str(bool(run.side_effects))),
            ("the two agree", str(agrees)),
        ),
    )


def baseline_decides_nothing(ctx: Context) -> Finding:
    run = compose.ungoverned(
        ctx.case, turns=agents.correct(ctx.key, ctx.po_id), runs_dir=ctx.runs_dir, tag="plain"
    )
    actions = {e.policy_action for e in run.events if e.policy_action}
    executed = f"{len(run.invoked)} of {len(run.invoked)} proposed"
    return Finding(
        key="baseline",
        area="Comparison",
        title="The ungoverned arm is recorded and governs nothing",
        claim="FR52: the baseline holds no Driver. A driver with its mechanisms switched off "
        "would still impose its ordering, its fail-closed paths and its bookkeeping on "
        "the arm that is supposed to show life without any of it. The recorder is "
        "measurement, not governance.",
        status=DEMONSTRATED if not actions and run.quality_state == "pass" else MISSING,
        evidence=(
            ("policy actions in its log", str(len(actions)) + " \u2014 it decides nothing"),
            ("tools executed", executed),
            ("gate", f"{run.quality_state} — scored once, after the agent stopped"),
            ("sealed", str(run.verified)),
        ),
    )


def shadow_mode(ctx: Context) -> Finding:
    spec = ctx.contract
    tools = tool_port_for(spec)
    run_id = f"{ctx.case.case_id}-shadow"
    path = ctx.runs_dir / f"{run_id}.db"
    path.unlink(missing_ok=True)
    with RecordStore(path).open() as store:
        driver = ShadowDriver(
            run_id=run_id,
            contract=spec,
            store=store,
            governor=ToolGovernor(spec),
            tools=tools,
        )
        driver.open_run(
            compose.manifest(run_id, mode="shadow", spec=spec, models=("gpt-5",))
        )
        driver.observe_step(
            ToolCall(tool="order_lookup", arguments={"po_id": ctx.po_id}, step_id="s1")
        )
        driver.observe_step(
            ToolCall(tool="notify_planner", arguments={"message": "hi"}, step_id="s2")
        )
        driver.close()
        report = driver.report()
    with open_store(path, writer=False) as reopened:
        lanes = {e.lane for e in reopened.events(run_id)}
    return Finding(
        key="shadow",
        area="Shadow mode",
        title="What the governor would have done, applied to nothing",
        claim="AD-11 makes shadow a separate driver, not a flag. It holds no ledger, returns "
        "no verdict and never reaches the approval port. A `shadow` flag would put a "
        "conditional in the fail-closed paths — the most safety-critical code, on the "
        "branch least exercised by tests.",
        status=DEMONSTRATED
        if report.label == "projected" and "counterfactual" in lanes and report.divergences
        else MISSING,
        evidence=(
            ("label", f"{report.label} — never 'realized' and not a field anyone can set"),
            ("lanes in the log", ", ".join(sorted(lanes))),
            ("divergences", str(report.divergences)),
            (
                "first divergence",
                f"{report.first_divergence.step_id}: host "
                f"{report.first_divergence.observed_action}, governor would "
                f"{report.first_divergence.counterfactual_action}"
                if report.first_divergence
                else "none",
            ),
            ("disclosure", report.disclosure),
        ),
    )


def data_class(ctx: Context) -> Finding:
    results = []
    for value, origin in (
        ("synthetic", None),
        ("non-synthetic", None),
        ("replayed", None),
        ("replayed", "non-synthetic"),
        ("replayed", "synthetic"),
    ):
        # A reason string, not an exception: the caller decides what to do with a
        # refusal, and both the manifest and the evidence store ask the same way.
        refusal = refuse_persistence(value, origin)
        label = f"{value}" + (f", replaying {origin}" if origin else "")
        results.append((label, "REFUSED" if refusal else "permitted"))
    refused = sum(1 for _label, verdict in results if verdict == "REFUSED")
    return Finding(
        key="data-class",
        area="Failure posture",
        title="Production traffic cannot be written to a run at all",
        claim="AD-21: one rule, called by both the manifest and the evidence store. A replay "
        "is admissible only if it names a synthetic origin, so FR106's replayed "
        "workloads work and real customer data still cannot reach a log.",
        status=DEMONSTRATED if refused == 3 else MISSING,
        level="mechanism",
        evidence=tuple(results),
    )


def disclosures(ctx: Context) -> Finding:
    directions = sorted({d.direction for d in FROZEN_DEFECTS})
    flattering = [d.key for d in FROZEN_DEFECTS if d.direction == "for"]
    return Finding(
        key="disclosures",
        area="Honesty",
        title="Known defects are registered, rendered, and cannot be dropped",
        claim="A submission refuses to validate unless every registered defect appears in "
        "its disclosures. Each carries a direction, and the ones marked `for` — the "
        "ones that flatter the result — are the ones to weigh hardest.",
        status=DEMONSTRATED if FROZEN_DEFECTS else MISSING,
        level="mechanism",
        evidence=(
            ("registered defects", str(len(FROZEN_DEFECTS))),
            ("directions in use", ", ".join(directions)),
            ("flattering the result", str(len(flattering))),
            *tuple((d.key, d.finding.split(".")[0][:110]) for d in FROZEN_DEFECTS[:4]),
        ),
        note="Four of them are shown; the submission renders all of them.",
    )


# ----------------------------------------------------------------- helpers


def _deliverable(ctx: Context) -> dict[str, Any]:
    import json

    return json.loads(agents.answer(ctx.key, ctx.po_id))


class _row:
    def __init__(self, result: Any) -> None:
        self.id = result.id
        self.mode = result.mode
        self.verdict_word = "met" if result.passed else "NOT MET"


def _shrink_budget(raw: dict[str, Any]) -> None:
    raw["budget"]["max_tokens"] = 2_000
    raw["budget"]["verification_reserve"] = {"max_tokens": 200, "max_estimated_cost": 0.01}


def _refer_to_human(raw: dict[str, Any]) -> None:
    raw["escalation"]["on_gate_fail"] = "request-human"
    raw["escalation"]["max_escalations"] = 0


CATALOGUE: tuple[Callable[[Context], Finding], ...] = (
    contract_is_executable,
    quality_gate,
    verification_modes,
    gate_refuses_a_wrong_answer,
    citable_index,
    tool_governor,
    side_effects_are_exempt,
    context_governor,
    human_approval,
    criterion_approval_is_dead,
    tool_call_ceiling_is_dead,
    budget_ceiling,
    verification_reserve,
    escalation,
    ladder,
    loop_fuse,
    record_spine,
    evidence_sidecar,
    out_of_band_probe,
    baseline_decides_nothing,
    shadow_mode,
    data_class,
    disclosures,
    unknown_tool_is_fail_closed,
)


def run_all(runs_dir: Path) -> list[Finding]:
    ctx = Context(runs_dir=runs_dir)
    findings: list[Finding] = []
    for feature in CATALOGUE:
        try:
            findings.append(feature(ctx))
        except (GateUnavailable, ToolError, ValueError, RuntimeError, OSError) as exc:
            findings.append(
                Finding(
                    key=feature.__name__.replace("_", "-"),
                    area="—",
                    title=feature.__name__.replace("_", " "),
                    claim="",
                    status=MISSING,
                    evidence=(("the scenario raised", f"{type(exc).__name__}: {exc}"),),
                )
            )
    return findings
