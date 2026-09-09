"""Outcome Contracts: the typed model and its safe loader (F2).

Callers import from here and never reach into submodules.
"""

from __future__ import annotations

from .loader import (
    MAX_CONTRACT_BYTES,
    MAX_DEPTH,
    ContractError,
    load_path,
    load_text,
    unsatisfiability_warnings,
)
from .models import (
    ApprovalCondition,
    Budget,
    Classification,
    Contract,
    Criteria,
    Criterion,
    Deliverable,
    Escalation,
    Models,
    Reserve,
    Tier,
    Tool,
    VerifierSpec,
)

__all__ = [
    "MAX_CONTRACT_BYTES",
    "MAX_DEPTH",
    "ApprovalCondition",
    "Budget",
    "Classification",
    "Contract",
    "ContractError",
    "Criteria",
    "Criterion",
    "Deliverable",
    "Escalation",
    "Models",
    "Reserve",
    "Tier",
    "Tool",
    "VerifierSpec",
    "load_path",
    "load_text",
    "unsatisfiability_warnings",
]
