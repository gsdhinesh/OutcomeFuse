"""Render a sealed run as a step tree (F19, FR111, FR112).

A client, not a component. It lives outside the distribution -- nothing under
`src/` imports it, and the wheel does not ship it (AD-17). It reads a sealed
decision log, verifies the hash chain before drawing anything, and computes no
savings, rates or comparisons. Those live in the proof cards, which carry their
own digests.

**The tree is a projection, not a stored shape.** Events are a flat sequence
carrying a `step_id` and no parent pointer. Grouping by that field yields the
tree at render time, which is why FR111 forbids adding a parent/child field to
the record for a viewer's benefit: a sealed run and a live one then draw the
same tree from the same data, and the tree owes nothing to anyone having been
watching when the run happened.

**Suppressed calls are drawn, not omitted.** A tree showing only the calls that
executed renders the governor invisible, because everything it did it did to the
calls that did not. A denial, a cache hit and a duplicate are the *point*, so
they are the rows that get the accent.

    .venv\\Scripts\\python.exe clients/tree/render_tree.py \\
        --runs-dir runs/demo-compare --run-id sc-e-001-governed
"""

from __future__ import annotations

import argparse
import html
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from outcomefuse.core.record import Event, StoreError, open_store

# Wording only. Every code itself comes from the log.
MEANING = {
    "justified": "worth its budget",
    "duplicate": "this exact call had already been made",
    "semantic-duplicate": "an equivalent call had already been made",
    "cache-hit": "already called with these arguments, so the stored result was "
    "reused and the tool was never invoked",
    "context-compressed": "the context was compressed before the call",
    "cheaper-model-eligible": "a cheaper model was enough",
    "unaffordable": "the budget could not cover it",
    "low-value": "the expected gain did not justify the spend",
    "optional-satisfied": "an enrichment call, and the floor was already met",
    "escalation-gate-fail": "the floor was not met, so a stronger model was tried",
    "approval-required": "a contract clause requires a human to authorise this",
    "approval-granted": "a human authorised it",
    "approval-denied": "a human refused it",
    "approval-timeout": "nobody answered inside the contract's window",
    "approval-channel-unavailable": "no approval channel was reachable, so the call was not made",
    "sufficiency": "the quality floor was met",
    "exhaustion": "the budget ran out",
    "no-progress": "the run stopped making progress",
    "fail-closed": "a governing component failed, so the run refused to continue",
}

# Reasons where the governor *withheld* work. These are the ones worth seeing.
SUPPRESSING = {
    "cache-hit",
    "duplicate",
    "semantic-duplicate",
    "low-value",
    "unaffordable",
    "optional-satisfied",
    "approval-denied",
    "approval-timeout",
    "approval-channel-unavailable",
}

WHEN = {
    "mid-run": "consulted while the agent still wanted tools, so it could stop it",
    "at-submission": "consulted after the agent had already stopped, so it confirmed",
}

CSS = """
*{box-sizing:border-box}body{margin:0;padding:2.5rem;background:#0f1115;color:#d7dae0;
font:15px/1.6 ui-monospace,SFMono-Regular,Menlo,monospace}
h1{font-size:1.4rem;margin:0 0 .5rem}
h2{font-size:.85rem;margin:2.5rem 0 1rem;color:#8b93a1;text-transform:uppercase;
letter-spacing:.08em}
.sub{color:#8b93a1;margin-bottom:2rem;font-size:.9rem}
.seal{display:inline-block;padding:.3rem .65rem;border-radius:3px;font-size:.8rem}
.ok{background:#12301d;color:#5dd98c;border:1px solid #1e5233}
.bad{background:#3a1418;color:#ff8391;border:1px solid #6b2028}
.step{border-left:2px solid #2a3140;margin:0 0 .35rem;padding:.1rem 0 .1rem 1rem}
.step.sup{border-left-color:#e0af68}
.step.term{border-left-color:#ff8391}
.step.gate{border-left-color:#5dd98c}
.hdr{color:#7aa2f7}
.hdr .n{color:#5a6270;margin-right:.6rem}
.act{color:#e0af68}
.leaf{padding-left:1.4rem;color:#8b93a1;font-size:.9rem}
.leaf .kind{color:#565e6c;display:inline-block;min-width:11rem}
.tool{color:#9ece6a}
.why{color:#c0c5ce}
.gloss{color:#6b7280;font-style:italic}
.gate-pass{color:#5dd98c;font-weight:600}.gate-fail{color:#ff8391;font-weight:600}
.termr{color:#ff8391;font-weight:600}
.k{color:#8b93a1}.v{color:#d7dae0}
.legend{margin:1rem 0 0;color:#6b7280;font-size:.85rem}
.legend b{color:#e0af68;font-weight:600}
.note{margin-top:2.5rem;padding:1rem 1.2rem;border-left:3px solid #2a3140;color:#8b93a1;
font-size:.9rem;max-width:62rem}
"""


def group_by_step(events: list[Event]) -> list[tuple[str | None, list[Event]]]:
    """Derive the tree from `step_id`, breaking on every change.

    Grouping *contiguously* rather than gathering every event that ever carried
    a given step_id is what keeps the tree in the order the run happened. The
    events outside any step are the clearest case: the manifest opens the run and
    the gate verdict, the stop and the close end it, and they all carry no
    step_id. Pooling them would draw the ending above the work.
    """
    groups: list[tuple[str | None, list[Event]]] = []
    for event in events:
        if event.lane != "observed":
            continue
        if groups and groups[-1][0] == event.step_id:
            groups[-1][1].append(event)
        else:
            groups.append((event.step_id, [event]))
    return groups


def leaf(event: Event) -> str:
    payload = event.payload or {}
    bits: list[str] = []
    if payload.get("tool"):
        key = str(payload.get("canonical_key") or "")
        bits.append(f'<span class="tool">{html.escape(str(payload["tool"]))}</span>')
        if key:
            # The key is what the governor compares to spot a repeat, so showing
            # it lets a reader check that judgement rather than take it.
            bits.append(f'<span class="k">{html.escape(key[:12])}</span>')
    if event.gate_verdict:
        cls = "gate-pass" if event.gate_verdict == "pass" else "gate-fail"
        bits.append(f'<span class="{cls}">{html.escape(event.gate_verdict)}</span>')
        if event.verification_mode:
            bits.append(f'<span class="k">({html.escape(event.verification_mode)})</span>')
        when = payload.get("when")
        if when and str(when) in WHEN:
            bits.append(f'<span class="gloss">{html.escape(WHEN[str(when)])}</span>')
    if event.tokens_consumed:
        bits.append(f'<span class="k">{event.tokens_consumed:,} tokens</span>')
    if event.model_used:
        bits.append(f'<span class="k">{html.escape(event.model_used)}</span>')
    if event.terminal_reason:
        bits.append(f'<span class="termr">{html.escape(event.terminal_reason)}</span>')
    return (
        f'<div class="leaf"><span class="kind">{html.escape(event.kind)}</span>'
        + " ".join(bits)
        + "</div>"
    )


def render_step(step_id: str | None, events: list[Event]) -> str:
    decision = next((e for e in events if e.policy_action or e.decision_reason), None)
    reason = (decision.decision_reason if decision else None) or ""
    action = (decision.policy_action if decision else None) or ""

    classes = ["step"]
    if reason in SUPPRESSING:
        classes.append("sup")
    if any(e.terminal_reason for e in events):
        classes.append("term")
    elif any(e.gate_verdict for e in events):
        classes.append("gate")

    label = html.escape(step_id) if step_id else "run"
    head = f'<span class="n">{events[0].seq}</span><span class="hdr">{label}</span>'
    if action:
        head += f' <span class="act">{html.escape(action)}</span>'
    if reason:
        head += f' <span class="why">{html.escape(reason)}</span>'
        if reason in MEANING:
            head += f' <span class="gloss">&mdash; {html.escape(MEANING[reason])}</span>'

    leaves = "".join(leaf(e) for e in events)
    return f'<div class="{" ".join(classes)}">{head}{leaves}</div>'


def render(
    events: list[Event], *, run_id: str, seal: str, verified: bool, source: Path
) -> str:
    manifest = (events[0].payload or {}).get("manifest", {}) if events else {}
    steps = group_by_step(events)
    suppressed = sum(
        1
        for _sid, group in steps
        if any((e.decision_reason or "") in SUPPRESSING for e in group)
    )
    badge = (
        '<span class="seal ok">hash chain verified</span>'
        if verified
        else '<span class="seal bad">SEAL DOES NOT VERIFY</span>'
    )
    models = ", ".join(manifest.get("model_ids") or []) or "&mdash;"
    contract = str(manifest.get("contract_hash", ""))[:32]
    body = "".join(render_step(sid, group) for sid, group in steps)
    return f"""<!doctype html>
<html lang="en"><meta charset="utf-8">
<title>OutcomeFuse tree &mdash; {html.escape(run_id)}</title>
<style>{CSS}</style>
<h1>{html.escape(run_id)}</h1>
<div class="sub">
  {badge}
  &nbsp; <span class="k">seal</span> <span class="v">{html.escape(seal[:32])}&hellip;</span><br>
  <span class="k">contract</span> <span class="v">{html.escape(contract)}&hellip;</span>
  &nbsp; <span class="k">models</span> <span class="v">{models}</span>
  &nbsp; <span class="k">source</span> <span class="v">{html.escape(source.as_posix())}</span>
</div>

<h2>Step tree &mdash; {len(steps)} steps, {len(events)} events, {suppressed} withheld</h2>
{body}
<p class="legend"><b>Amber</b> marks a step where the governor withheld work &mdash;
a cache hit, a duplicate, a denial, a refused approval. Those steps are the
mechanism; a tree that hid them would show an ordinary agent doing ordinary
work.</p>

<div class="note">
Drawn from the sealed log and nothing else. The tree is grouped by the
<code>step_id</code> already on each event &mdash; no parent/child field was added
to the record to make this render, so the same tree draws from a live stream or a
sealed one. This page computes no savings, rates or comparisons. The hash chain
was verified before it was written; had it not verified, the page would say so
rather than not exist.
</div>
</html>
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs-dir", default="runs/demo-compare")
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--out", default="submission/tree-view.html")
    args = parser.parse_args()

    chosen: tuple[Path, str] | None = None
    for path in sorted(Path(args.runs_dir).rglob("*.db")):
        try:
            with open_store(path, writer=False) as store:
                for found in store.run_ids():
                    if args.run_id is not None and found != args.run_id:
                        continue
                    if chosen is None:
                        chosen = (path, found)
        except (sqlite3.Error, StoreError, ValueError, OSError) as err:
            print(f"  skipped {path.name}: {err}", file=sys.stderr)
    if chosen is None:
        raise SystemExit(f"no run matching {args.run_id!r} under {args.runs_dir}")

    path, run_id = chosen
    with open_store(path, writer=False) as store:
        events = store.events(run_id)
        seal = store.seal(run_id) or ""
        try:
            store.verify_run(run_id)
            verified = True
        except (StoreError, ValueError) as err:
            print(f"! seal does not verify: {err}", file=sys.stderr)
            verified = False

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        render(events, run_id=run_id, seal=seal, verified=verified, source=path),
        encoding="utf-8",
    )
    print(f"{run_id}: {len(events)} events, seal {'verified' if verified else 'BROKEN'}")
    print(f"written to {out}")
    return 0 if verified else 1


if __name__ == "__main__":
    raise SystemExit(main())
