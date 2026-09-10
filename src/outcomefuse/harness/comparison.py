"""Comparing two arms (AD-10).

The two arms of a comparison must be **manifest-identical except for the run id
and the fields the comparison exists to vary** — mode, and the enabled-mechanism
registry. The harness compares field by field and refuses on any other
difference: route, model version, cost-table version, seed and adapter version
included.

The list of varying fields is closed and small on purpose. Widen it and the
comparison stops being about governance and starts being about configuration,
which is exactly how this category flatters itself.
"""

from __future__ import annotations

from typing import Final

from pydantic import BaseModel, ConfigDict

from ..core.record import RunManifest

#: Everything else must match. `run_id` differs because they are two runs;
#: `mode` and `enabled_mechanisms` differ because that is the experiment.
MAY_DIFFER: Final[frozenset[str]] = frozenset({"run_id", "mode", "enabled_mechanisms"})


class ManifestMismatch(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    field: str
    baseline: str
    governed: str


class ComparisonRefused(ValueError):
    """The arms differ somewhere the comparison does not exist to vary."""


def diff_manifests(baseline: RunManifest, governed: RunManifest) -> list[ManifestMismatch]:
    """Every field that differs and is not permitted to."""
    left = baseline.model_dump(mode="json")
    right = governed.model_dump(mode="json")
    return [
        ManifestMismatch(field=name, baseline=repr(left[name]), governed=repr(right[name]))
        for name in sorted(left)
        if name not in MAY_DIFFER and left[name] != right[name]
    ]


def require_comparable(baseline: RunManifest, governed: RunManifest) -> None:
    """Raise unless the two arms are comparable."""
    if baseline.mode != "baseline":
        raise ComparisonRefused(f"the baseline arm has mode {baseline.mode!r}")
    if governed.mode != "governed":
        raise ComparisonRefused(f"the governed arm has mode {governed.mode!r}")
    if baseline.run_id == governed.run_id:
        raise ComparisonRefused("both arms name the same run")

    mismatches = diff_manifests(baseline, governed)
    if mismatches:
        detail = ", ".join(
            f"{m.field}: {m.baseline} vs {m.governed}" for m in mismatches
        )
        raise ComparisonRefused(
            f"the arms are not manifest-identical: {detail}. Only mode and the "
            "enabled-mechanism registry may differ."
        )
