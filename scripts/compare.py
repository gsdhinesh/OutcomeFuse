"""One task, done twice, side by side. For someone who has never seen this repo.

    .venv\\Scripts\\python.exe scripts/compare.py --case sc-e-001 --runs-dir runs/rerun

Left is a plain agent with no budget and no quality gate. Right is the same
task through OutcomeFuse. Both timelines are read from the sealed logs: what
each one did, what each step cost, what stopped it, and whether the answer was
judged correct.

The only arithmetic is adding up recorded tokens and the difference between the
two totals. Everything else is quoted from the log, because a page that
recomputes the result is a second place the result can be wrong.
"""

from __future__ import annotations

import argparse
import html
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from outcomefuse.core.record import open_store
from outcomefuse.harness.answer_keys import AnswerKeyError, answer_key_for
from outcomefuse.harness.cases import load_case_set

# The fields worth putting in front of someone. The full deliverable is in the
# evidence sidecar; a wall of JSON hides the difference rather than showing it.
SHOW = {
    "supply-chain": ("exception_type", "root_cause_code", "recommended_action"),
    "data-sql": ("value", "unit", "as_of"),
    "code-triage": ("root_cause_file", "root_cause_line", "severity"),
    "doc-research": ("answer", "effective_from"),
}

STOPPED_BECAUSE = {
    "stop-sufficient": ("the quality floor was met", "good"),
    "halt-exhausted": ("it ran out of budget", "warn"),
    "halt-no-progress": ("it stopped making progress", "warn"),
    "returned-partial": ("it gave up and handed over what it had", "warn"),
    "fail-closed": ("a governing part failed, so it refused to continue", "warn"),
}

CSS = """
*{box-sizing:border-box}
body{margin:0;padding:2rem;background:#0f1115;color:#d7dae0;
font:15px/1.55 -apple-system,Segoe UI,Roboto,sans-serif}
h1{font-size:1.5rem;margin:0 0 .3rem}
.task{background:#171a21;border-left:3px solid #7aa2f7;padding:1rem 1.2rem;margin:1rem 0 2rem;
max-width:75rem}
.task b{color:#7aa2f7;display:block;font-size:.75rem;letter-spacing:.1em;margin-bottom:.4rem}
.cols{display:flex;gap:1.5rem;align-items:stretch;flex-wrap:wrap}
.col{flex:1 1 26rem;background:#151821;border:1px solid #232833;border-radius:6px;overflow:hidden;
display:flex;flex-direction:column}
.steps{flex:1}
.head{padding:1rem 1.2rem;border-bottom:1px solid #232833}
.head h2{margin:0;font-size:1.05rem}
.head .who{color:#8b93a1;font-size:.85rem;margin-top:.2rem}
.off .head{background:#1d1a17}.on .head{background:#141d1a}
.step{display:flex;gap:.8rem;padding:.55rem 1.2rem;border-bottom:1px solid #1b1f27;
align-items:baseline}
.n{color:#4d5566;width:1.4rem;flex:none;font-size:.8rem}
.what{flex:1}.tok{color:#8b93a1;font-variant-numeric:tabular-nums;white-space:nowrap}
.tool{color:#9ece6a}.think{color:#bb9af7}
.allowed{color:#5a6270;font-size:.8rem;display:block}
.total{display:flex;justify-content:space-between;padding:1rem 1.2rem;
border-top:2px solid #232833;font-size:1.25rem;font-weight:600}
.foot{padding:0 1.2rem 1.2rem}
.line{display:flex;justify-content:space-between;padding:.35rem 0;
border-bottom:1px solid #1b1f27}
.line span:first-child{color:#8b93a1}
.good{color:#5dd98c;font-weight:600}.bad{color:#ff8391;font-weight:600}
.warn{color:#e0af68;font-weight:600}
.answers{margin-top:1rem;padding-top:.8rem;border-top:1px solid #232833}
.answers b{display:block;color:#8b93a1;font-size:.75rem;letter-spacing:.08em;
text-transform:uppercase;margin-bottom:.4rem}
.answers .line span:last-child{text-align:right}
.verdict{margin:2rem 0 0;padding:1.2rem 1.4rem;background:#171a21;border-radius:6px;
max-width:75rem;font-size:1.05rem}
.verdict b{font-size:1.5rem}
.note{margin-top:1.5rem;color:#8b93a1;font-size:.85rem;max-width:75rem}
"""


def read(path: Path, run_id: str) -> dict:
    with open_store(path, writer=False) as store:
        events = store.events(run_id)
        seal = store.seal(run_id) or ""
        store.verify_run(run_id)

    steps: list[list] = []
    total = 0
    allowed: str | None = None
    for event in events:
        tool = (event.payload or {}).get("tool")
        if event.kind in {"decision-proposed", "evidence-requested"} and tool:
            steps.append(["tool", str(tool), 0, allowed])
            allowed = None
        if event.kind == "decision-recorded" and event.policy_action == "proceed":
            # Recorded after the call it authorises, so it belongs to the last step.
            for step in reversed(steps):
                if step[0] == "tool" and step[3] is None:
                    step[3] = event.decision_reason
                    break
        if event.kind == "spend-settled" and event.tokens_consumed:
            total += event.tokens_consumed
            if event.model_used:
                steps.append(
                    ["think", "the model thinking and writing", event.tokens_consumed, None]
                )
            else:
                # A settle with no model behind it is a tool's own charge. The
                # baseline records none, which is why its tools show no cost.
                for step in reversed(steps):
                    if step[0] == "tool" and not step[2]:
                        step[2] = event.tokens_consumed
                        break

    gate = [e for e in events if e.kind == "gate-verdict"]
    terminal = [e.terminal_reason for e in events if e.terminal_reason]
    models = sorted({e.model_used for e in events if e.model_used})
    # `proceed` and `terminate` are the governor agreeing and then closing the
    # run. Anything else is the only thing that could have changed the answer.
    changed = [
        e.policy_action
        for e in events
        if e.policy_action and e.policy_action not in {"proceed", "terminate"}
    ]
    return {
        "steps": steps,
        "total": total,
        "verdict": gate[-1].gate_verdict if gate else None,
        "gate_when": (gate[-1].payload or {}).get("when") if gate else None,
        "stopped": terminal[-1] if terminal else None,
        "models": models,
        "changed": changed,
        "governed": any(e.policy_action for e in events),
        "escalated": sum(1 for e in events if e.policy_action == "escalate"),
        "seal": seal,
    }


def deliverable_of(runs_dir: Path, workload: str, run_id: str) -> dict:
    path = runs_dir / workload / "evidence" / run_id / "deliverable.json"
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def answers_block(given: dict, key: dict, workload: str) -> str:
    """What it answered, with each field marked against the frozen answer key."""
    if not given:
        return '<div class="line"><span>the answer it gave</span><span>not kept</span></div>'
    rows = []
    for field in SHOW.get(workload, tuple(given)[:3]):
        if field not in given:
            continue
        mine, theirs = given.get(field), key.get(field)
        # A field the key does not pin is not wrong, it is simply not scored.
        tone = "" if theirs is None else ("good" if mine == theirs else "bad")
        wanted = (
            ""
            if theirs is None or mine == theirs
            else f'<span class="allowed">the key says: {html.escape(str(theirs))}</span>'
        )
        rows.append(
            f'<div class="line"><span>{html.escape(field)}</span>'
            f'<span class="{tone}">{html.escape(str(mine))}{wanted}</span></div>'
        )
    return "".join(rows)


def column(run: dict, *, title: str, who: str, css: str, answer: str) -> str:
    rows = []
    for index, (kind, what, tokens, allowed) in enumerate(run["steps"], start=1):
        label = (
            f'<span class="tool">{html.escape(what)}</span>'
            if kind == "tool"
            else f'<span class="think">{html.escape(what)}</span>'
        )
        why = (
            f'<span class="allowed">allowed: {html.escape(allowed)} &mdash; '
            "the governor judged it worth its budget</span>"
            if allowed
            else ""
        )
        cost = f"{tokens:,}" if tokens else "&mdash;"
        rows.append(
            f'<div class="step"><span class="n">{index}</span>'
            f'<span class="what">{label}{why}</span>'
            f'<span class="tok">{cost}</span></div>'
        )

    if run["stopped"]:
        said, tone = STOPPED_BECAUSE.get(run["stopped"], (run["stopped"], "warn"))
    else:
        said, tone = "by itself &mdash; nothing was watching it", "warn"
    right = {"pass": ("CORRECT", "good"), "fail": ("WRONG", "bad")}.get(
        run["verdict"], ("never checked", "warn")
    )
    escalated = (
        f'<div class="line"><span>had to retry on the big model</span>'
        f'<span class="warn">yes, {run["escalated"]}x</span></div>'
        if run["escalated"]
        else ""
    )
    if not run["governed"]:
        did = '<span class="k">nothing was governing this run</span>'
    elif run["changed"]:
        did = f'<span class="warn">{html.escape(", ".join(sorted(set(run["changed"]))))}</span>'
    else:
        did = '<span class="warn">nothing &mdash; it allowed every step</span>'
    gate_when = (
        '<div class="line"><span>when the quality check looked</span>'
        '<span class="warn">after the agent had already stopped</span></div>'
        if run["gate_when"] == "at-submission"
        else ""
    )
    return f"""
<div class="col {css}">
  <div class="head"><h2>{title}</h2><div class="who">{who}</div></div>
  <div class="steps">{"".join(rows)}</div>
  <div class="total"><span>tokens used</span><span>{run["total"]:,}</span></div>
  <div class="foot">
    <div class="line"><span>model</span>
      <span>{html.escape(", ".join(run["models"]) or "&mdash;")}</span></div>
    <div class="line"><span>why it stopped</span><span class="{tone}">{said}</span></div>
    <div class="line"><span>what the governor changed</span>{did}</div>
    {gate_when}
    {escalated}
    <div class="line"><span>was the answer right?</span>
      <span class="{right[1]}">{right[0]}</span></div>
    <div class="answers"><b>what it actually answered</b>{answer}</div>
  </div>
</div>"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", default="sc-e-001")
    parser.add_argument("--workload", default=None, help="inferred from the case id")
    parser.add_argument("--split", default="evaluation")
    parser.add_argument("--runs-dir", default="runs/rerun")
    parser.add_argument(
        "--preregistration",
        default="87b94e36fdc933c471e97c9df32452d830a8f62e942c6b9daf2451eb045c0c30",
        help="the evaluation split is sealed without one",
    )
    parser.add_argument("--out", default="submission/compare.html")
    args = parser.parse_args()

    workload = args.workload or {
        "sc": "supply-chain", "ds": "data-sql",
        "ct": "code-triage", "dr": "doc-research",
    }[args.case.split("-")[0]]

    runs = Path(args.runs_dir) / workload
    arms = {
        arm: read(runs / f"{args.case}-{arm}.db", f"{args.case}-{arm}")
        for arm in ("baseline", "governed")
    }

    task = next(
        c.prompt for c in load_case_set(workload, args.split).cases if c.case_id == args.case
    )
    task_line = " ".join(task.split())[:400]

    try:
        key = answer_key_for(
            args.case, workload, args.split, preregistration_hash=args.preregistration
        )
    except AnswerKeyError as exc:
        print(f"! no answer key, fields will not be marked: {exc}")
        key = {}
    answers = {
        arm: answers_block(
            deliverable_of(Path(args.runs_dir), workload, f"{args.case}-{arm}"), key, workload
        )
        for arm in ("baseline", "governed")
    }

    base, gov = arms["baseline"]["total"], arms["governed"]["total"]
    diff = (base - gov) / base if base else 0.0
    word, tone = ("fewer", "good") if diff > 0 else ("MORE", "bad")
    same = arms["baseline"]["verdict"] == arms["governed"]["verdict"]
    quality = (
        "and both answers were judged the same way"
        if same
        else f'and the answers differed: plain was {arms["baseline"]["verdict"]}, '
        f'OutcomeFuse was {arms["governed"]["verdict"]}'
    )
    # Without this, two columns and one tick invite the reader to conclude the
    # governor produced the better answer. On these runs it did not: it allowed
    # every step, and the gate scored a deliverable the agent had already
    # finished. The difference is the model and the draw.
    caused = (
        ""
        if same or arms["governed"]["changed"]
        else "<br><br>The governor did not cause that. It allowed every step "
        "unchanged and the quality check ran only after the agent had stopped, so "
        "what differs between these two columns is the model and the luck of one "
        "run &mdash; not the governing."
    )

    page = f"""<!doctype html>
<html lang="en"><meta charset="utf-8">
<title>Same task, twice &mdash; {html.escape(args.case)}</title>
<style>{CSS}</style>
<h1>The same task, done twice</h1>
<div class="task"><b>THE TASK &mdash; {html.escape(args.case)}</b>{html.escape(task_line)}</div>
<div class="cols">
{column(arms["baseline"], title="Without OutcomeFuse",
        who="a plain agent: no budget, no quality check, uses the expensive model",
        css="off", answer=answers["baseline"])}
{column(arms["governed"], title="With OutcomeFuse",
        who="a budget, a quality floor, and it starts on the cheap model",
        css="on", answer=answers["governed"])}
</div>
<div class="verdict">
  OutcomeFuse used <b class="{tone}">{abs(diff):.0%} {word}</b> tokens on this task, {quality}.
  {caused}
</div>
<div class="note">
Both timelines are read from sealed decision logs whose hash chains were
verified before this page was written. The only arithmetic here is adding up
recorded tokens and comparing the two totals.
<br><br>
<b>This is one task.</b> It is not a result, and it is not evidence that the
same thing happens generally &mdash; the same workload run twice moved its
headline by 37 points. The measured results, and the reasons none of them can
be published, are in <code>scripts/report.py</code>.
</div>
</html>
"""
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page, encoding="utf-8")
    print(f"{args.case}: plain {base:,} tokens, OutcomeFuse {gov:,} tokens")
    print(f"written to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
