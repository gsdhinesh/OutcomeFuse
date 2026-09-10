"""The record spine (AD-2, AD-16): append-only log, per-run chain, run seal.

Callers import from here and never reach into submodules.
"""

from __future__ import annotations

from .events import (
    DECISION_EVENT_ORDER,
    DECISION_REASONS,
    EVENT_KINDS,
    POLICY_ACTIONS,
    REASON_FAMILIES,
    REASON_REGISTRY_VERSION,
    SCHEMA_VERSION,
    TERMINAL_KINDS,
    TERMINAL_REASONS,
    DataClass,
    EventKind,
    Mode,
    PolicyAction,
    QualityState,
    Split,
    TerminalReason,
    family_of,
)
from .fold import OrderViolation, RunState, check_order, fold, replay_equivalent
from .models import Event, LedgerState, RunManifest, reason_registry_digest
from .store import (
    BUSY_TIMEOUT_MS,
    MIN_SQLITE,
    ChainBroken,
    RecordStore,
    StoreError,
    open_store,
)

__all__ = [
    "BUSY_TIMEOUT_MS",
    "DECISION_EVENT_ORDER",
    "DECISION_REASONS",
    "EVENT_KINDS",
    "MIN_SQLITE",
    "POLICY_ACTIONS",
    "REASON_FAMILIES",
    "REASON_REGISTRY_VERSION",
    "SCHEMA_VERSION",
    "TERMINAL_KINDS",
    "TERMINAL_REASONS",
    "ChainBroken",
    "DataClass",
    "Event",
    "EventKind",
    "LedgerState",
    "Mode",
    "OrderViolation",
    "PolicyAction",
    "QualityState",
    "RecordStore",
    "RunManifest",
    "RunState",
    "Split",
    "StoreError",
    "TerminalReason",
    "check_order",
    "family_of",
    "fold",
    "open_store",
    "reason_registry_digest",
    "replay_equivalent",
]
