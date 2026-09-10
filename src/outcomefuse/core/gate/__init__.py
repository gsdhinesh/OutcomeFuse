"""The Quality Gate (F4).

Callers import from here and never reach into submodules.
"""

from __future__ import annotations

from .gate import (
    AdvisorySignal,
    CriterionResult,
    GateUnavailable,
    Qualifier,
    QualityGate,
    Verdict,
    VerdictValue,
)
from .steps import (
    DEFAULT_CADENCE,
    IRREMOVABLE,
    STEP_CLASSES,
    CadenceError,
    StepClass,
    cadence_for,
    should_evaluate,
    should_evaluate_before_halt,
    validate_cadence,
)

__all__ = [
    "DEFAULT_CADENCE",
    "IRREMOVABLE",
    "STEP_CLASSES",
    "AdvisorySignal",
    "CadenceError",
    "CriterionResult",
    "GateUnavailable",
    "Qualifier",
    "QualityGate",
    "StepClass",
    "Verdict",
    "VerdictValue",
    "cadence_for",
    "should_evaluate",
    "should_evaluate_before_halt",
    "validate_cadence",
]
