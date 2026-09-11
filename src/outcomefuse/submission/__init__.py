"""The submission artifact (E15, F16).

Protected, and dependent on the harness and the record spine alone — never on
the viewer, which sits first in the cut order.
"""

from __future__ import annotations

from .disclosures import DISCLOSURE_KEYS, FROZEN_DEFECTS, Disclosure
from .figures import (
    CONSTRAINT_BACKED,
    DEGRADED,
    PROJECTED,
    SELF_REPORTED,
    Basis,
    Figure,
    FigureRefused,
    Provenance,
    Role,
    required_labels,
)
from .script import (
    BEAT_ORDER,
    MAX_SECONDS,
    REQUIRED_DEMONSTRATIONS,
    Beat,
    MechanismEvidence,
    Submission,
    SubmissionRefused,
    build_submission,
    check_submission,
    evidence_of_mechanism,
)

__all__ = [
    "BEAT_ORDER",
    "CONSTRAINT_BACKED",
    "DEGRADED",
    "DISCLOSURE_KEYS",
    "FROZEN_DEFECTS",
    "MAX_SECONDS",
    "PROJECTED",
    "REQUIRED_DEMONSTRATIONS",
    "SELF_REPORTED",
    "Basis",
    "Beat",
    "Disclosure",
    "Figure",
    "FigureRefused",
    "MechanismEvidence",
    "Provenance",
    "Role",
    "Submission",
    "SubmissionRefused",
    "build_submission",
    "check_submission",
    "evidence_of_mechanism",
    "required_labels",
]
