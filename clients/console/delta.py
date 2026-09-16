"""What differs between two arms of the same scenario, in one place.

The CLI and the page both report this, and two implementations of "what
changed" would eventually disagree about the same pair of runs — which is
exactly the kind of thing a comparison exists to be trusted about.

Every figure is read off a finished run, never accumulated during one.

The split between `material` and `recorded` is the load-bearing part. The
ungoverned arm has no terminal reason because nothing governed it; it simply
stopped. Knowing *why* a run ended is worth something, but counting it beside
"the money did not move" would flatten two very different magnitudes into one
number, and the honest headline here is how often nothing material changes.
"""

from __future__ import annotations

from typing import Any

AGREE = "the arms agree"


def summarise(run: Any, arm: str) -> dict[str, Any]:
    return {
        "arm": arm,
        "run_id": run.run_id,
        "terminal": run.terminated,
        "quality": run.quality_state,
        "seal": run.seal,
        "verified": run.verified,
        "escalations": run.escalations,
        "tools_invoked": list(run.invoked),
        "side_effects": list(run.side_effects),
        "turns": run.outcome.iterations,
        "tokens": run.outcome.spend.total_tokens,
        "models": list(run.outcome.models_used),
        # Which criteria the gate refused. The driver logs the ids and drops the
        # per-criterion breakdown that produced them, so this is all there is.
        "unmet": sorted(
            {u for e in run.events for u in (e.payload or {}).get("unmet", []) or []}
        ),
        # What it actually answered. A console that shows only the machinery
        # never shows whether the question got answered.
        "answer": run.deliverable,
    }


def material(on: dict[str, Any], off: dict[str, Any]) -> list[str]:
    """Differences in what happened. Ordered by how much they matter."""
    found: list[str] = []
    if bool(on["side_effects"]) != bool(off["side_effects"]):
        moved = "the ungoverned arm" if off["side_effects"] else "the governed arm"
        found.append(f"only {moved} acted on the world")
    if on["quality"] != off["quality"]:
        found.append(f"gate {off['quality']} -> {on['quality']}")
    if len(on["tools_invoked"]) != len(off["tools_invoked"]):
        found.append(
            f"tools executed {len(off['tools_invoked'])} -> {len(on['tools_invoked'])}"
        )
    if on["escalations"] != off["escalations"]:
        found.append(f"escalations {off['escalations']} -> {on['escalations']}")
    if on["tokens"] != off["tokens"]:
        delta = (on["tokens"] - off["tokens"]) / off["tokens"] * 100 if off["tokens"] else 0.0
        found.append(f"tokens {off['tokens']:,} -> {on['tokens']:,} ({delta:+.0f}%)")
    return found


def recorded(on: dict[str, Any], off: dict[str, Any]) -> list[str]:
    """Differences in what was written down rather than in what happened."""
    if on["terminal"] == off["terminal"]:
        return []
    return [
        f"the governed arm names why it ended ({on['terminal']}); "
        "the ungoverned one just stopped"
    ]


def verdict(summaries: list[dict[str, Any]]) -> dict[str, Any]:
    """The comparison, or an empty one where only a single arm ran."""
    by_arm = {s["arm"]: s for s in summaries}
    on, off = by_arm.get("governed"), by_arm.get("baseline")
    if on is None or off is None:
        return {"compared": False, "material": [], "recorded": []}
    return {
        "compared": True,
        "material": material(on, off),
        "recorded": recorded(on, off),
    }
