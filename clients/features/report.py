"""Every feature of OutcomeFuse, demonstrated against the frozen supply-chain workload.

    uv run python clients/features/report.py
    uv run python clients/features/report.py --out submission/outcomefuse-features.html

**One use case, not four.** Features here are driven by the contract and the
scenario, not by the domain: a second workload would add surface and no coverage.
Supply-chain is the one chosen because it is frozen — real cases, derived answer
keys, a real corpus — and because a recorded live campaign already exists for it,
so the report can end with what actually happened rather than only what can be
made to happen.

The report has two halves and they disagree:

- **Demonstrated** — each mechanism driven deliberately through the library's own
  loop, sealed, and read back from the log. Shows the mechanisms work.
- **Measured** — the recorded gpt-5 campaign, counted. Shows how often they
  mattered, which is much less often.

Nothing here calls a model or spends anything.
"""

from __future__ import annotations

import argparse
import html
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "clients"))

# The report is full of arrows and dashes and a Windows console is cp1252 by
# default, which would make an encoding error the thing that stops it.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from features import measured  # noqa: E402
from features.catalogue import DEFECT, DEMONSTRATED, GAP, Finding, run_all  # noqa: E402

TONE = {
    DEMONSTRATED: ("demonstrated", "ok"),
    GAP: ("GAP", "gap"),
    DEFECT: ("DEFECT", "bad"),
    "not-demonstrated": ("NOT DEMONSTRATED", "bad"),
}

CSS = """
*{box-sizing:border-box}
body{margin:0;padding:2rem;background:#0f1115;color:#d7dae0;
font:15px/1.6 -apple-system,Segoe UI,Roboto,sans-serif}
h1{font-size:1.7rem;margin:0 0 .3rem}
h2{font-size:1.15rem;margin:2.4rem 0 .8rem;color:#7aa2f7;
border-bottom:1px solid #232833;padding-bottom:.4rem}
.sub{color:#8b93a1;font-size:.9rem;max-width:62rem;margin-bottom:1.6rem}
.sub b{color:#d7dae0}
.tally{display:flex;gap:1.6rem;flex-wrap:wrap;margin:1.2rem 0 0;padding:1rem 1.2rem;
background:#151821;border:1px solid #232833;border-radius:6px;max-width:62rem}
.tally div{font-size:.85rem;color:#8b93a1}
.tally b{display:block;font-size:1.5rem;color:#d7dae0}
.f{background:#151821;border:1px solid #232833;border-radius:6px;margin:0 0 1rem;
max-width:62rem;overflow:hidden}
.f.gap{border-left:3px solid #e0af68}
.f.bad{border-left:3px solid #ff8391}
.f.ok{border-left:3px solid #2c3340}
.fh{padding:.9rem 1.2rem;border-bottom:1px solid #232833;display:flex;
justify-content:space-between;gap:1rem;align-items:baseline}
.fh h3{margin:0;font-size:1rem;font-weight:600}
.badge{font-size:.7rem;letter-spacing:.09em;text-transform:uppercase;white-space:nowrap}
.badge.ok{color:#5dd98c}.badge.gap{color:#e0af68}.badge.bad{color:#ff8391}
.claim{padding:.8rem 1.2rem;color:#a7aebb;font-size:.9rem;border-bottom:1px solid #1b1f27}
.ev{padding:.4rem 1.2rem .9rem}
.line{display:flex;justify-content:space-between;gap:1.5rem;padding:.3rem 0;
border-bottom:1px solid #1b1f27;font-size:.88rem}
.line span:first-child{color:#8b93a1;flex:none;min-width:16rem}
.line span:last-child{text-align:right;font-family:ui-monospace,Consolas,monospace;
font-size:.85rem}
.note{padding:.7rem 1.2rem;background:#1a1712;color:#c9b489;font-size:.85rem}
.lvl{color:#5a6270;font-size:.72rem;letter-spacing:.08em;text-transform:uppercase}
.verdict{max-width:62rem;padding:1.1rem 1.3rem;background:#1a1712;border-radius:6px;
color:#e0af68;font-size:1rem;margin:0 0 1.2rem}
.foot{margin-top:2.5rem;color:#8b93a1;font-size:.85rem;max-width:62rem}
code{color:#d7dae0}
"""


#: The console is cp1252 on Windows and the report is full of dashes and arrows.
#: Only the console is folded down; the page keeps them.
PLAIN = str.maketrans({"\u2014": "--", "\u2192": "->", "\u2026": "...", "\u00d7": "x"})


def _flat(text: str) -> str:
    return text.translate(PLAIN)


def _tally(findings: list[Finding]) -> dict[str, int]:
    counts = {"demonstrated": 0, "gap": 0, "defect": 0, "not-demonstrated": 0}
    for finding in findings:
        counts[finding.status] = counts.get(finding.status, 0) + 1
    return counts


def _console(findings: list[Finding], stats: measured.Measured, proof: dict, total) -> None:
    width = shutil.get_terminal_size((100, 24)).columns
    print("OUTCOMEFUSE - FEATURE REPORT")
    print("frozen supply-chain workload, scripted agent, no model called\n")
    area = ""
    for finding in findings:
        if finding.area != area:
            area = finding.area
            print(f"\n{_flat(area).upper()}")
        label, _tone = TONE[finding.status]
        suffix = "  [mechanism-level]" if finding.level == "mechanism" else ""
        print(f"  {label:<18} {_flat(finding.title)[: width - 30]}{suffix}")
        for key, value in finding.evidence:
            print(f"      {_flat(key):<34} {_flat(value)}")
    counts = _tally(findings)
    print(
        f"\n{counts['demonstrated']} demonstrated, {counts.get('gap', 0)} gap, "
        f"{counts.get('defect', 0)} defect, {counts.get('not-demonstrated', 0)} not demonstrated"
    )
    print("\nMEASURED - the recorded gpt-5 campaign, counted")
    print(f"  {_flat(measured.verdict(stats))}\n")
    for key, value in measured.rows(stats, proof, total):
        print(f"      {_flat(key):<34} {_flat(value)}")


def _finding_html(finding: Finding) -> str:
    label, tone = TONE[finding.status]
    level = '<span class="lvl">mechanism-level</span>' if finding.level == "mechanism" else ""
    lines = "".join(
        f'<div class="line"><span>{html.escape(k)}</span>'
        f"<span>{html.escape(v)}</span></div>"
        for k, v in finding.evidence
    )
    note = f'<div class="note">{html.escape(finding.note)}</div>' if finding.note else ""
    claim = f'<div class="claim">{html.escape(finding.claim)}</div>' if finding.claim else ""
    return f"""
<div class="f {tone}">
  <div class="fh"><h3>{html.escape(finding.title)} {level}</h3>
    <span class="badge {tone}">{label}</span></div>
  {claim}
  <div class="ev">{lines}</div>
  {note}
</div>"""


def render(findings: list[Finding], stats: measured.Measured, proof: dict, total) -> str:
    counts = _tally(findings)
    blocks: list[str] = []
    area = ""
    for finding in findings:
        if finding.area != area:
            area = finding.area
            blocks.append(f"<h2>{html.escape(area)}</h2>")
        blocks.append(_finding_html(finding))

    rows = "".join(
        f'<div class="line"><span>{html.escape(k)}</span><span>{html.escape(v)}</span></div>'
        for k, v in measured.rows(stats, proof, total)
    )
    return f"""<!doctype html>
<html lang="en"><meta charset="utf-8">
<title>OutcomeFuse — feature report</title>
<style>{CSS}</style>
<h1>OutcomeFuse, feature by feature</h1>
<div class="sub">
Driven against the <b>frozen supply-chain workload</b> — its contract, its calibration
cases, its derived answer keys, its corpus — through the library's own loop
(<code>harness.runner.run_case</code>), not a re-implementation. One use case, because
features here are driven by the contract and the scenario rather than by the domain:
a second workload would add surface and no coverage.
<br><br>
Every status below is <b>computed from a sealed log or a returned value</b>, never
asserted. A mechanism that stopped working reports <b>NOT DEMONSTRATED</b> instead of
continuing to be advertised. The model is scripted, so this shows the mechanisms
<b>work</b> — for how often they <b>matter</b>, read the measured section at the end,
which counts the recorded gpt-5 campaign and disagrees.
</div>

<div class="tally">
  <div><b>{counts['demonstrated']}</b>demonstrated</div>
  <div><b>{counts.get('gap', 0)}</b>gap</div>
  <div><b>{counts.get('defect', 0)}</b>defect</div>
  <div><b>{counts.get('not-demonstrated', 0)}</b>not demonstrated</div>
</div>

{"".join(blocks)}

<h2>Measured — what a real model actually did</h2>
<div class="verdict">{html.escape(measured.verdict(stats))}</div>
<div class="f ok"><div class="ev">{rows}</div></div>

<div class="foot">
Scenarios marked <b>mechanism-level</b> call a component directly rather than through a
run. That is honest about what they prove: the component behaves as specified, under
conditions the run did not have to produce.
<br><br>
Scenarios that misbehave — an agent that stalls, cites a clause that does not exist, or
answers wrongly — are authored to do that. Detecting a stall requires one. They are
stimuli for a code path, never samples of behaviour, and the measured section is where
the frequencies live.
<br><br>
Budget exhaustion and the referred-to-human ending use <b>variant</b> contracts built in
memory, because the frozen contract does not configure them. Each says so on its own row.
The frozen contract itself is never edited.
</div>
</html>
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs-dir", default="runs/features")
    parser.add_argument("--out", default="submission/outcomefuse-features.html")
    parser.add_argument("--campaign", default="runs/campaign")
    parser.add_argument("--quiet", action="store_true", help="write the page, print a summary")
    args = parser.parse_args()

    runs_dir = Path(args.runs_dir)
    findings = run_all(runs_dir)
    campaign = Path(args.campaign)
    stats = measured.read_campaign(campaign, workload="supply-chain")
    total = measured.read_campaign(campaign)
    proof = measured.card()

    if args.quiet:
        counts = _tally(findings)
        print(
            f"{counts['demonstrated']} demonstrated, {counts.get('gap', 0)} gap, "
            f"{counts.get('defect', 0)} defect, "
            f"{counts.get('not-demonstrated', 0)} not demonstrated"
        )
    else:
        _console(findings, stats, proof, total)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(findings, stats, proof, total), encoding="utf-8")
    print(f"\nwritten to {out}")
    print(f"sealed logs in {runs_dir}")
    # A feature that stopped working is a failing exit code, not a line in a table.
    return 1 if any(f.status == "not-demonstrated" for f in findings) else 0


if __name__ == "__main__":
    raise SystemExit(main())
