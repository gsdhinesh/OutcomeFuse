"""Run manifest and decision-record models (AD-9, FR53).

Frozen and `extra="forbid"`: a manifest is the thing every published comparison
rests on, so a field nobody declared must not ride along in it.
"""

from __future__ import annotations

import re
from typing import Any, Final

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..canon import Digest, hash_structure
from .events import (
    OBSERVED_ONLY_KINDS,
    REASON_REGISTRY_VERSION,
    SCHEMA_VERSION,
    DataClass,
    EventKind,
    Lane,
    Mode,
    PolicyAction,
    QualityState,
    Split,
    TerminalReason,
    refuse_persistence,
)

_SHA256 = r"^[0-9a-f]{64}$"
#: RFC 3339 with an explicit Z. A local-time record cannot be ordered against
#: one written in another zone, and these are compared across machines.
_TIMESTAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d{1,6})?Z$")

GENESIS_PREV: Final[None] = None


class LedgerState(BaseModel):
    """Ledger position at decision time, in tokens and cost."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    allocated_tokens: int = Field(ge=0)
    spent_tokens: int = Field(ge=0)
    reserved_tokens: int = Field(ge=0)
    allocated_cost: float = Field(ge=0)
    spent_cost: float = Field(ge=0)
    reserved_cost: float = Field(ge=0)

    @property
    def remaining_tokens(self) -> int:
        return self.allocated_tokens - self.spent_tokens - self.reserved_tokens

    @property
    def remaining_cost(self) -> float:
        return self.allocated_cost - self.spent_cost - self.reserved_cost


class RunManifest(BaseModel):
    """The first entry of every run's log (AD-9).

    No comparison may be published from a run without one.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    run_id: str = Field(min_length=1, max_length=128)
    mode: Mode
    #: No default anywhere: a run whose class is absent is refused rather than
    #: assumed benign (FR109).
    data_class: DataClass
    #: The class a `replayed` run inherits from the run it replays (AD-21).
    replayed_from_data_class: DataClass | None = None
    retention_profile: str = Field(min_length=1)

    contract_hash: str = Field(pattern=_SHA256)
    rubric_hash: str = Field(pattern=_SHA256)
    answer_key_hash: str = Field(pattern=_SHA256)
    verifier_registry_version: str = Field(min_length=1)
    verifier_registry_hash: str = Field(pattern=_SHA256)
    coverage_report_hash: str = Field(pattern=_SHA256)
    baseline_configuration_hash: str = Field(pattern=_SHA256)

    case_set_id: str = Field(min_length=1)
    split: Split
    #: Anchors FR102 to content rather than to a timestamp asserted by the
    #: interested party. Required for evaluation runs.
    preregistration_hash: str | None = Field(default=None, pattern=_SHA256)

    model_ids: tuple[str, ...] = Field(min_length=1)
    provider_versions: dict[str, str]
    cost_table_version: str = Field(min_length=1)
    route: str
    streaming_disabled: bool
    enabled_mechanisms: dict[str, str] = Field(default_factory=dict)
    adapter_id: str = Field(min_length=1)
    adapter_version: str = Field(min_length=1)
    governor_code_version: str = Field(min_length=1)
    sqlite_library_version: str = Field(min_length=1)
    seed: int
    sampling: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _coherent(self) -> RunManifest:
        if self.route not in {"apim", "direct"}:
            raise ValueError(f"route must be apim or direct, got {self.route!r}")
        if not self.streaming_disabled:
            # The gateway estimates token counts when streaming is on, so the
            # evidence path bars it outright.
            raise ValueError("streaming must be disabled on any recorded run")
        if self.data_class != "synthetic":
            # FR109: refuse persistence rather than applying the MVP profile to
            # data it was never approved for.
            refusal = refuse_persistence(self.data_class, self.replayed_from_data_class)
            if refusal is not None:
                raise ValueError(refusal)
        elif self.replayed_from_data_class is not None:
            raise ValueError(
                "a synthetic run inherits nothing; replayed_from belongs to a replayed run"
            )
        if self.split == "evaluation" and self.preregistration_hash is None:
            raise ValueError("an evaluation run must carry the preregistration hash")
        missing = [m for m in self.model_ids if m not in self.provider_versions]
        if missing:
            raise ValueError(f"model ids without a provider version: {missing}")
        return self

    def digest(self) -> Digest:
        return hash_structure(self.model_dump(mode="json", exclude_none=True))


class Event(BaseModel):
    """One appended row. Nothing here is ever updated (AD-16, AD-19)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    run_id: str = Field(min_length=1, max_length=128)
    seq: int = Field(ge=0)
    kind: EventKind
    recorded_at: str
    step_id: str | None = None
    #: An enforced run writes only `observed`. A shadow run writes both, and
    #: the counterfactual is the fold restricted to its own lane.
    lane: Lane = "observed"

    policy_action: PolicyAction | None = None
    decision_reason: str | None = None
    terminal_reason: TerminalReason | None = None
    quality_state: QualityState | None = None
    gate_verdict: str | None = None
    verification_mode: str | None = None
    contract_clause: str | None = None
    ledger: LedgerState | None = None
    model_used: str | None = None
    tokens_consumed: int | None = Field(default=None, ge=0)
    model_derived_inputs: dict[str, Any] | None = None
    payload: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _coherent(self) -> Event:
        if not _TIMESTAMP.match(self.recorded_at):
            raise ValueError(f"recorded_at must be RFC 3339 UTC with Z: {self.recorded_at!r}")
        if self.gate_verdict is not None:
            if self.gate_verdict not in {"pass", "fail"}:
                raise ValueError(f"gate_verdict must be pass or fail: {self.gate_verdict!r}")
            if self.verification_mode not in {"reference-backed", "constraint-backed"}:
                # FR21: a pass resting on constraint-backed verification is
                # labelled wherever it is reported, so the qualifier travels
                # with the verdict rather than being reconstructed later.
                raise ValueError("a gate verdict must carry its verification mode")
        if self.terminal_reason is not None and self.kind not in {
            "decision-recorded",
            "run-closed",
            "run-abandoned",
        }:
            raise ValueError(
                f"terminal_reason may not appear on a {self.kind!r} event"
            )
        if self.lane == "counterfactual" and self.kind in OBSERVED_ONLY_KINDS:
            raise ValueError(
                f"a counterfactual may not {self.kind!r}: the run belongs to the host, "
                "and only the observed lane opens or closes it"
            )
        return self

    def chained_hash(self, previous: str | None) -> str:
        """This row's hash, binding its predecessor within the same run.

        Sealed through AD-6's structure route, like everything else that is
        hashed, so a second implementation cannot canonicalise differently.
        """
        body = self.model_dump(mode="json", exclude_none=True)
        return hash_structure(
            {"event": body, "prev": previous, "schema": SCHEMA_VERSION}
        ).sha256


def reason_registry_digest() -> Digest:
    """Hash the versioned reason registry, for the manifest and the freeze."""
    from .events import REASON_FAMILIES

    return hash_structure(
        {
            "version": REASON_REGISTRY_VERSION,
            "families": {family: sorted(codes) for family, codes in REASON_FAMILIES.items()},
        }
    )
