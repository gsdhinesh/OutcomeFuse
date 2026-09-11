"""The enforcing runtime (E7), the observing one (E11), and the recording one.

Three peers. `Driver` enforces. `ShadowDriver` observes a counterfactual, as a
second driver rather than a flag on the first, so the fail-closed paths carry no
shadow branch. `BaselineRecorder` writes down an ungoverned run, deciding
nothing, because an unrecorded arm cannot be admitted or paired.
"""

from __future__ import annotations

from .baseline import BaselineRecorder
from .driver import Driver, StepVerdict
from .shadow import (
    Divergence,
    ShadowDriver,
    ShadowRefused,
    ShadowReport,
    build_shadow_report,
)
from .tool_governor import (
    Action,
    Disposition,
    ToolGovernor,
    ToolGovernorError,
    canonical_key,
)

__all__ = [
    "Action",
    "BaselineRecorder",
    "Disposition",
    "Divergence",
    "Driver",
    "ShadowDriver",
    "ShadowRefused",
    "ShadowReport",
    "StepVerdict",
    "ToolGovernor",
    "ToolGovernorError",
    "build_shadow_report",
    "canonical_key",
]
