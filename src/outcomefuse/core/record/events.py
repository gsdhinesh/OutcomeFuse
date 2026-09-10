"""The decision taxonomies and the canonical event order (AD-2).

Two compliant implementations must produce the same sequence for the same run,
so the order is data here rather than control flow scattered through a driver.

`decision_reason` is a **versioned, extensible registry**: new codes may be
added at any time, and a published code is never redefined, repurposed or
removed — a reused code silently rewrites the meaning of every historical
record. `policy_action` and `terminal_reason` are closed vocabularies.
"""

from __future__ import annotations

from typing import Final, Literal, get_args

SCHEMA_VERSION: Final[str] = "v1"
REASON_REGISTRY_VERSION: Final[str] = "v1"

Mode = Literal["governed", "baseline", "shadow"]
DataClass = Literal["synthetic", "replayed", "non-synthetic"]
Split = Literal["calibration", "evaluation"]
QualityState = Literal["not-evaluated", "pass", "fail"]

PolicyAction = Literal[
    "proceed",
    "proceed-with-substitution",
    "deny",
    "pause-for-approval",
    "escalate",
    "request-human",
    "return-partial",
    "terminate",
]

TerminalReason = Literal[
    "stop-sufficient",
    "halt-exhausted",
    "halt-no-progress",
    "approval-timeout",
    "fail-closed",
    "referred-human",
    "returned-partial",
]

EventKind = Literal[
    "run-manifest",
    "decision-proposed",
    "evidence-requested",
    "evidence-observed",
    "budget-reserved",
    "decision-recorded",
    "verdict-applied",
    "outcome-observed",
    "spend-settled",
    "gate-verdict",
    "degraded",
    "run-closed",
    "run-abandoned",
]

POLICY_ACTIONS: Final[frozenset[str]] = frozenset(get_args(PolicyAction))
TERMINAL_REASONS: Final[frozenset[str]] = frozenset(get_args(TerminalReason))
EVENT_KINDS: Final[frozenset[str]] = frozenset(get_args(EventKind))
QUALITY_STATES: Final[frozenset[str]] = frozenset(get_args(QualityState))

#: Every code declares its family, so reporting aggregates by family rather
#: than by enumerating codes.
REASON_FAMILIES: Final[dict[str, frozenset[str]]] = {
    "progress": frozenset({"justified"}),
    "denial": frozenset(
        {
            "unaffordable",
            "low-value",
            "duplicate",
            "semantic-duplicate",
            "optional-satisfied",
            "unsafe",
        }
    ),
    "substitution": frozenset({"cache-hit", "context-compressed", "cheaper-model-eligible"}),
    "escalation": frozenset(
        {
            "escalation-complexity",
            "escalation-low-confidence",
            "escalation-criticality",
            "escalation-gate-fail",
        }
    ),
    "governance": frozenset(
        {"approval-required", "approval-granted", "approval-denied", "approval-timeout"}
    ),
    "termination": frozenset({"sufficiency", "exhaustion", "no-progress", "fail-closed"}),
}

DECISION_REASONS: Final[frozenset[str]] = frozenset(
    code for codes in REASON_FAMILIES.values() for code in codes
)

#: AD-2's fixed order for one decision. The evidence cycle is elided here
#: because it may recur at several points; `EVIDENCE_CYCLE_MAY_FOLLOW` says where.
DECISION_EVENT_ORDER: Final[tuple[EventKind, ...]] = (
    "decision-proposed",
    "budget-reserved",
    "decision-recorded",
    "verdict-applied",
    "outcome-observed",
    "spend-settled",
)

#: An evidence cycle is zero or more requested/observed pairs, logged in place.
#: It may recur wherever an advisor or the Gate needs one — including after
#: `outcome-observed`, which is where the Gate's own executions and cost land.
EVIDENCE_CYCLE_MAY_FOLLOW: Final[frozenset[str]] = frozenset(
    {"decision-proposed", "outcome-observed", "spend-settled", "run-manifest"}
)

TERMINAL_KINDS: Final[frozenset[str]] = frozenset({"run-closed", "run-abandoned"})


def family_of(reason: str) -> str:
    """The family a reason code belongs to, for aggregation."""
    for family, codes in REASON_FAMILIES.items():
        if reason in codes:
            return family
    raise KeyError(f"unregistered decision_reason: {reason!r}")
