"""Render one sealed run as a static HTML page.

This is E14, un-cut deliberately and kept to the one job FR84 needs: showing
the mechanism running. It reads a sealed decision log and displays it. It
computes no savings, rates or comparisons -- those live in the proof cards,
which carry their own digests. A second path to a number is a second thing
that can be wrong, and the disclosures cover only the first one.

The seal is verified before anything is drawn and the result is printed on the
page. A viewer you have to trust is worth less than the log it renders.

    .venv\\Scripts\\python.exe scripts/render_run.py
"""

from __future__ import annotations

import argparse
import html
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from outcomefuse.core.record import Event, StoreError, open_store

# Shown beside each code so the stream reads without knowing the vocabulary.
# Wording only; every code itself comes from the log.
MEANING = {
    "justified": "the step was worth its budget",
    "duplicate": "this exact call had already been made",
    "semantic-duplicate": "an equivalent call had already been made",
    "cache-hit": "already called with these arguments, so the stored result was reused "
    "and the tool was never invoked",
    "context-compressed": "the context was compressed before the call",
    "cheaper-model-eligible": "a cheaper model was enough for this step",
    "unaffordable": "the budget could not cover it",
    "low-value": "the expected gain did not justify the spend",
    "escalation-gate-fail": "the quality floor was not met, so a stronger model was tried",
    "sufficiency": "the quality floor was met",
    "exhaustion": "the budget ran out",
    "no-progress": "the run stopped making progress",
    "fail-closed": "a governing component failed, so the run refused to continue",
}

# The distinction the entire sufficiency-stop claim turns on.
WHEN = {
    "mid-run": "consulted while the agent still wanted tools, so it could stop it",
    "at-submission": "consulted after the agent had already stopped, so it confirmed",
}

CSS = """
*{box-sizing:border-box}body{margin:0;padding:2.5rem;background:#0f1115;color:#d7dae0;
font:15px/1.6 ui-monospace,SFMono-Regular,Menlo,monospace}
h1{font-size:1.4rem;margin:0 0 .5rem}h2{font-size:.85rem;margin:2.5rem 0 .75rem;
color:#8b93a1;text-transform:uppercase;letter-spacing:.08em}
.sub{color:#8b93a1;margin-bottom:2rem;font-size:.9rem}
.seal{display:inline-block;padding:.3rem .65rem;border-radius:3px;font-size:.8rem}
.ok{background:#12301d;color:#5dd98c;border:1px solid #1e5233}
.bad{background:#3a1418;color:#ff8391;border:1px solid #6b2028}
table{border-collapse:collapse;width:100%}
td,th{padding:.45rem .7rem;border-bottom:1px solid #1c2028;vertical-align:top;text-align:left}
th{color:#8b93a1;font-size:.75rem;text-transform:uppercase;letter-spacing:.05em}
.seq{color:#5a6270;width:3rem}.kind{color:#7aa2f7;white-space:nowrap}
.act{color:#e0af68;white-space:nowrap}.why{color:#c0c5ce}
.term{color:#ff8391;font-weight:600}
.gate-pass{color:#5dd98c;font-weight:600}.gate-fail{color:#ff8391;font-weight:600}
.tool{color:#9ece6a}
.bar{display:inline-block;height:8px;width:90px;background:#2a3140;border-radius:2px;
vertical-align:middle}
.bar i{display:block;height:100%;background:#7aa2f7;border-radius:2px}
.k{color:#8b93a1}.v{color:#d7dae0}
.note{margin-top:2.5rem;padding:1rem 1.2rem;border-left:3px solid #2a3140;color:#8b93a1;
font-size:.9rem;max-width:60rem}
"""


def pick_run(runs_dir: Path, run_id: str | None) -> tuple[Path, str, str]:
    """The run that best exercises the mechanism, or the one asked for.

    Baseline runs hold no policy and record no decisions, and plenty of governed
    runs never reach a gate, so the newest sealed run tends to demonstrate
    nothing. Ranking picks one that does and reports what it was picked for --
    choosing a run to *show a mechanism* is fair, choosing one to flatter a
    number is not, so the basis is printed either way.
    """
    best: tuple[int, float, Path, str, str] | None = None
    for path in sorted(runs_dir.rglob("*.db")):
        try:
            with open_store(path, writer=False) as store:
                for found in store.run_ids():
                    if run_id is not None and found != run_id:
                        continue
                    events = store.events(found)
                    if not any(e.kind == "decision-recorded" and e.policy_action for e in events):
                        continue
                    gated = any(e.kind == "gate-verdict" for e in events)
                    escalated = any(e.policy_action == "escalate" for e in events)
                    shows = [
                        name
                        for name, present in (("gate verdict", gated), ("escalation", escalated))
                        if present
                    ]
                    rank = len(shows)
                    candidate = (
                        rank,
                        path.stat().st_mtime,
                        path,
                        found,
                        ", ".join(shows) or "decision stream only",
                    )
                    if best is None or candidate[:2] > best[:2]:
                        best = candidate
        except (sqlite3.Error, StoreError, ValueError, OSError) as err:
            print(f"  skipped {path.name}: {err}", file=sys.stderr)
    if best is None:
        raise SystemExit(f"no run with a decision stream under {runs_dir}")
    return best[2], best[3], best[4]


def budget_cell(event: Event) -> str:
    led = event.ledger
    if led is None or not led.allocated_tokens:
        return ""
    used = led.spent_tokens + led.reserved_tokens
    pct = min(100.0, 100.0 * used / led.allocated_tokens)
    return (
        f'<span class="bar"><i style="width:{pct:.0f}%"></i></span> '
        f'<span class="k">{used:,}/{led.allocated_tokens:,}</span>'
    )


def detail(event: Event) -> str:
    if event.kind == "gate-verdict":
        cls = "gate-pass" if event.gate_verdict == "pass" else "gate-fail"
        when = (event.payload or {}).get("when")
        # Absent on every run recorded before the field existed. Saying so beats
        # drawing a verdict with no timing, which reads as though it had none.
        said = WHEN.get(str(when)) if when else (
            "timing not recorded; this run predates the field"
        )
        return (
            f'<span class="{cls}">{html.escape(event.gate_verdict or "")}</span> '
            f'<span class="k">({html.escape(event.verification_mode or "")})</span>'
            + (f'<br><span class="k">{html.escape(said)}</span>' if said else "")
        )
    if event.terminal_reason:
        return f'<span class="term">{html.escape(event.terminal_reason)}</span>'
    if event.kind == "spend-settled" and event.tokens_consumed:
        return f'<span class="k">{event.tokens_consumed:,} tokens</span>'
    payload = event.payload or {}
    if payload.get("tool"):
        # The canonical key is what the tool governor compares to spot a repeat,
        # so showing it lets a reader check that judgement instead of taking it.
        key = str(payload.get("canonical_key") or "")
        return (
            f'<span class="tool">{html.escape(str(payload["tool"]))}</span>'
            + (f' <span class="k">{html.escape(key[:12])}</span>' if key else "")
        )
    if "to" in payload and "from" in payload:
        return (
            f'<span class="k">{html.escape(str(payload["from"]))} &rarr; '
            f'{html.escape(str(payload["to"]))}</span>'
        )
    return ""


def render(events: list[Event], *, run_id: str, seal: str, verified: bool, source: Path) -> str:
    manifest = (events[0].payload or {}).get("manifest", {}) if events else {}
    # Event.ledger exists and no driver populates it, so the column would be
    # empty on every row and read as "no budget activity" rather than "never
    # recorded".
    banked = any(e.ledger is not None for e in events)
    named = any((e.payload or {}).get("tool") for e in events)
    rows = []
    for event in events:
        if event.lane != "observed":
            continue
        why = event.decision_reason or ""
        gloss = f'<br><span class="k">{html.escape(MEANING[why])}</span>' if why in MEANING else ""
        rows.append(
            "<tr>"
            f'<td class="seq">{event.seq}</td>'
            f'<td class="kind">{html.escape(event.kind)}</td>'
            f'<td class="act">{html.escape(event.policy_action or "")}</td>'
            f'<td class="why">{html.escape(why)}{gloss}</td>'
            f"<td>{detail(event)}</td>"
            + (f"<td>{budget_cell(event)}</td>" if banked else "")
            + "</tr>"
        )

    badge = (
        '<span class="seal ok">hash chain verified</span>'
        if verified
        else '<span class="seal bad">SEAL DOES NOT VERIFY</span>'
    )
    models = ", ".join(manifest.get("model_ids") or []) or "&mdash;"
    contract = str(manifest.get("contract_hash", ""))[:32]
    budget_note = (
        ""
        if banked
        else "<p>No ledger position was recorded on any event in this run, so there is "
        "no budget column. <code>Event.ledger</code> exists and no driver fills it; an "
        "empty column would have read as no budget activity.</p>"
    )
    budget_head = "<th>budget</th>" if banked else ""
    tool_note = (
        ""
        if named
        else "<p>No tool name appears on any event in this run, so the steps below "
        "show spend without showing what was called. The governed driver did not "
        "record it until after these runs were made.</p>"
    )
    return f"""<!doctype html>
<html lang="en"><meta charset="utf-8">
<title>OutcomeFuse &mdash; {html.escape(run_id)}</title>
<style>{CSS}</style>
<h1>{html.escape(run_id)}</h1>
<div class="sub">
  {badge}
  &nbsp; <span class="k">seal</span> <span class="v">{html.escape(seal[:32])}&hellip;</span><br>
  <span class="k">contract</span> <span class="v">{html.escape(contract)}&hellip;</span>
  &nbsp; <span class="k">models</span> <span class="v">{models}</span>
  &nbsp; <span class="k">source</span> <span class="v">{html.escape(source.as_posix())}</span>
</div>

<h2>Decision stream &mdash; {len(rows)} recorded events</h2>
<table>
<tr><th>#</th><th>event</th><th>action</th><th>reason</th><th></th>{budget_head}</tr>
{"".join(rows)}
</table>

<div class="note">
Rendered from the sealed log and nothing else. This page computes no savings,
rates or comparisons; those live in the proof cards, which carry their own
digests. The hash chain was verified before the page was written &mdash; had it
not verified, the page would say so rather than not exist.
{tool_note}
{budget_note}
</div>
</html>
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs-dir", default="runs/campaign")
    parser.add_argument("--run-id", default=None, help="defaults to the newest governed run")
    parser.add_argument("--out", default="submission/run-view.html")
    args = parser.parse_args()

    path, run_id, shows = pick_run(Path(args.runs_dir), args.run_id)
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
    print(f"chosen because it shows: {shows}")
    print(f"written to {out}")
    return 0 if verified else 1


if __name__ == "__main__":
    raise SystemExit(main())
