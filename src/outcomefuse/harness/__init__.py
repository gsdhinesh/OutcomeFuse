"""The benchmark harness (E8): manifest, preregistration, reportability, proof card."""

from __future__ import annotations

from .comparison import (
    MAY_DIFFER,
    ComparisonRefused,
    ManifestMismatch,
    diff_manifests,
    require_comparable,
)
from .preregistration import (
    COUNTER_METRICS,
    Preregistration,
    PreregistrationError,
    SavingsTargets,
)
from .proofcard import (
    ArmTotals,
    PairedCase,
    ProofCard,
    Savings,
    build_proof_card,
    headline,
)
from .reportability import (
    Accompaniment,
    Independence,
    Reportability,
    RunFacts,
    assess,
    check_accompaniment,
    check_admissibility,
    grade_independence,
)

__all__ = [
    "COUNTER_METRICS",
    "MAY_DIFFER",
    "Accompaniment",
    "ArmTotals",
    "ComparisonRefused",
    "Independence",
    "ManifestMismatch",
    "PairedCase",
    "Preregistration",
    "PreregistrationError",
    "ProofCard",
    "Reportability",
    "RunFacts",
    "Savings",
    "SavingsTargets",
    "assess",
    "build_proof_card",
    "check_accompaniment",
    "check_admissibility",
    "diff_manifests",
    "grade_independence",
    "headline",
    "require_comparable",
]
