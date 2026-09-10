"""The benchmark harness (E8): manifest, preregistration, reportability, proof card."""

from __future__ import annotations

from .comparison import (
    MAY_DIFFER,
    ComparisonRefused,
    ManifestMismatch,
    diff_manifests,
    require_comparable,
)
from .failure_paths import (
    CASES_BY_NAME,
    FR100_CASES,
    TERMINATING_ACTIONS,
    FailureCase,
    check_case,
)
from .overhead import (
    DEFAULT_REPEATS,
    Latencies,
    OverheadRefused,
    OverheadStudy,
    build_study,
    check_targets_are_derived,
    measure,
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
    "CASES_BY_NAME",
    "COUNTER_METRICS",
    "DEFAULT_REPEATS",
    "FR100_CASES",
    "MAY_DIFFER",
    "TERMINATING_ACTIONS",
    "Accompaniment",
    "ArmTotals",
    "ComparisonRefused",
    "FailureCase",
    "Independence",
    "Latencies",
    "ManifestMismatch",
    "OverheadRefused",
    "OverheadStudy",
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
    "build_study",
    "check_accompaniment",
    "check_admissibility",
    "check_case",
    "check_targets_are_derived",
    "diff_manifests",
    "grade_independence",
    "headline",
    "measure",
    "require_comparable",
]
