"""The comparison, headless. The gallery's eleven, or the whole matrix behind it.

    uv run python clients/console/compare.py                  # the eleven cards
    uv run python clients/console/compare.py --matrix         # every situation x work
    uv run python clients/console/compare.py --matrix --work code-triage
    uv run python clients/console/compare.py --quiet

The console shows twelve chosen jobs, one mechanism each, because that is what a
person can read. **This is where the rest is checked.** `--matrix` runs every
situation against every kind of work, which is how the `code-triage` approval gap
was found: its side-effecting tool carries a clause the governor cannot read, so
the situation that stops the other workloads at a human sails straight through.

Both arms get the same agent, the same contract and the same tools, so the only
difference between them is whether OutcomeFuse was wired in. Nothing here calls a
model or spends anything, and every figure is read back from a sealed log.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "clients"))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from features import compose  # noqa: E402
from features import work as work_module  # noqa: E402

from console import jobs, scenarios  # noqa: E402
from console.delta import AGREE, material, recorded, summarise  # noqa: E402


@dataclass(frozen=True)
class Pair:
    label: str
    work: work_module.Work
    situation: scenarios.Situation
    case_id: str
    governed: compose.Run
    #: None where the ungoverned arm raised instead of ending. That is a result.
    baseline: compose.Run | None
    threw: str = ""
    #: What the card claims to show. Empty for matrix rows, which are the
    #: instrument rather than the show and claim nothing.
    shows: str = ""

    @property
    def material(self) -> list[str]:
        if self.baseline is None:
            return ["only the governed arm ended at all"]
        return material(
            summarise(self.governed, "governed"), summarise(self.baseline, "baseline")
        )

    @property
    def recorded(self) -> list[str]:
        if self.baseline is None:
            return [f"the ungoverned arm raised {self.threw}"]
        return recorded(
            summarise(self.governed, "governed"), summarise(self.baseline, "baseline")
        )


def compare(
    label: str,
    situation: scenarios.Situation,
    work: work_module.Work,
    case_id: str,
    runs_dir: Path,
    shows: str = "",
) -> Pair:
    governed = scenarios.run(
        situation, work, arm=scenarios.GOVERNED, runs_dir=runs_dir, case_id=case_id
    )
    threw = ""
    baseline = None
    try:
        baseline = scenarios.run(
            situation, work, arm=scenarios.BASELINE, runs_dir=runs_dir, case_id=case_id
        )
    except Exception as exc:  # noqa: BLE001 - reported, never swallowed
        # The unanswerable case does this: with no governor there is no posture
        # to fall back on, so a gate that cannot be evaluated comes out as an
        # exception rather than a decision.
        threw = f"{type(exc).__name__}: {exc}"
    return Pair(label, work, situation, case_id, governed, baseline, threw, shows)


def _row(pair: Pair) -> None:
    on, off = pair.governed, pair.baseline
    print(f"\n{pair.label}")
    print(f"  {'the mechanism':<20}{pair.situation.feature}")
    if pair.situation.variant:
        print(f"  {'variant contract':<20}{pair.situation.variant}")
    print(f"  {'':20}{'plugged out':<24}plugged in")
    if off is None:
        print(f"  {'the run':<20}{'raised':<24}{on.terminated}")
        print(f"  {'':20}{pair.threw}")
    else:
        print(f"  {'tool calls run':<20}{len(off.invoked):<24}{len(on.invoked)}")
        print(
            f"  {'tokens':<20}{off.outcome.spend.total_tokens:<24,}"
            f"{on.outcome.spend.total_tokens:,}"
        )
        print(f"  {'gate':<20}{off.quality_state:<24}{on.quality_state}")
        print(
            f"  {'how it ended':<20}{off.terminated or 'nothing stopped it'!s:<24}"
            f"{on.terminated}"
        )
        print(
            f"  {'acted on the world':<20}"
            f"{('yes: ' + off.side_effects[0] if off.side_effects else 'no'):<24}"
            f"{('yes: ' + on.side_effects[0] if on.side_effects else 'no')}"
        )
    if pair.material:
        print(f"  {'DIFFERENCE':<20}{'; '.join(pair.material)}")
    else:
        # Four cards move no figure on purpose. Printing only "the arms agree"
        # left a gap, a defect and a deliberate control looking like one thing.
        print(f"  {'difference':<20}none in what happened - {AGREE}")
        if pair.shows:
            print(f"  {'which is the point':<20}this card shows {pair.shows}")
    for note in pair.recorded:
        print(f"  {'recorded only':<20}{note}")


def _gallery(runs_dir: Path, quiet: bool) -> list[Pair]:
    """The eleven cards the console offers, each checked against its own claim."""
    pairs = []
    for job in jobs.JOBS:
        doing = work_module.by_workload(job.workload)
        situation = scenarios.by_key(job.situation)
        if scenarios.is_interactive(situation, doing):
            # It waits on a person who is not here, so it would report a channel
            # failure rather than the mechanism it exists to show.
            if not quiet:
                print(f"\n{job.title}\n  {'skipped':<20}this one waits on a person")
            continue
        pairs.append(
            compare(job.title, situation, doing, job.case_id, runs_dir, job.shows)
        )
    return pairs


def _matrix(runs_dir: Path, chosen: list[work_module.Work], quiet: bool) -> list[Pair]:
    """Every situation against every kind of work. The instrument, not the show."""
    pairs = []
    for doing in chosen:
        case_id = compose.cases(doing.workload)[0].case_id
        if not quiet:
            print(f"\n{'=' * 72}\n{doing.name.upper()}  ({doing.workload}, {case_id})")
            print(f"{doing.shows}\n{doing.gate_note}")
        for situation in scenarios.for_work(doing):
            if scenarios.is_interactive(situation, doing):
                continue
            label = f"{doing.workload} / {situation.key}"
            pairs.append(compare(label, situation, doing, case_id, runs_dir))
    return pairs


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matrix", action="store_true", help="every situation x work")
    parser.add_argument("--work", default=None, help="one workload; implies --matrix")
    parser.add_argument("--runs-dir", default="runs/compare")
    parser.add_argument("--quiet", action="store_true", help="one line per comparison")
    args = parser.parse_args()

    runs_dir = Path(args.runs_dir)
    if args.matrix or args.work:
        try:
            chosen = (
                [work_module.by_workload(args.work)] if args.work else list(work_module.WORK)
            )
        except KeyError:
            raise SystemExit(f"no such workload: {args.work}") from None
        pairs = _matrix(runs_dir, chosen, args.quiet)
    else:
        pairs = _gallery(runs_dir, args.quiet)

    for pair in pairs:
        if args.quiet:
            print(f"  {pair.label[:46]:<48}{'; '.join(pair.material) or AGREE}")
        else:
            _row(pair)

    differed = sum(1 for p in pairs if p.material)
    moved = sum(
        1
        for p in pairs
        if p.baseline is not None and p.baseline.side_effects and not p.governed.side_effects
    )
    print(f"\n{'=' * 72}")
    print(f"{differed} of {len(pairs)} comparisons differ in what happened.")
    # Naming them beats a single sentence about "what was written down", which
    # put a gap, a deliberate control and a recorded disposition in one bucket.
    agreed = [p for p in pairs if not p.material and p.shows]
    if agreed:
        print("The rest agree, and each of them agrees for its own reason:")
        for pair in agreed:
            print(f"  - {pair.label}: {pair.shows}")
    if moved:
        print(
            f"In {moved} the ungoverned arm acted on the world and the governed one "
            "did not. That is the difference worth paying for."
        )
    print(f"Sealed logs in {runs_dir}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
