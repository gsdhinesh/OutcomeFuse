"""The composition root: where OutcomeFuse is plugged in, and where it is not.

Everything the library needs to be wired is wired here and nowhere else, so the
answer to "what did plugging it in cost me?" is one file long. The loop in
`loop.py` never imports `Driver`, `Ledger` or `ToolGovernor`; it takes a
`Wiring` and applies what it is told.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

from outcomefuse.core.contract import Contract, load_path
from outcomefuse.core.policy import Ledger, Reserve
from outcomefuse.core.record import RecordStore, RunManifest
from outcomefuse.core.verify.registry import REGISTRY_VERSION, registry_digest
from outcomefuse.evidence.store import EvidenceStore
from outcomefuse.ports import Decision, ScriptedApprovalPort, ScriptedModelPort
from outcomefuse.runtime import Driver, ToolGovernor
from outcomefuse.runtime.baseline import BaselineRecorder

from .desk import DeskCase, citable_index, tool_port
from .loop import Governed, RunOutcome, Ungoverned, build_fuse, run

CONTRACT_PATH = Path(__file__).resolve().parent / "refund-desk.contract.yaml"

#: This client has no frozen rubric, coverage report or baseline definition, so
#: the manifest fields that would carry their digests carry nothing. Stating that
#: as zeros is the honest option: inventing a hash over an artefact that does not
#: exist would make the manifest look more evidential than the run actually is.
ABSENT = "0" * 64

MODELS = {"gpt-5-mini": "gpt-5-mini-2025-08-07", "gpt-5": "gpt-5-2025-08-07"}


def load_contract(path: Path | str = CONTRACT_PATH) -> Contract:
    return load_path(Path(path))


def _manifest(run_id: str, contract: Contract, model_id: str, mode: str) -> RunManifest:
    return RunManifest(
        run_id=run_id,
        mode=mode,
        data_class="synthetic",
        retention_profile="client-synthetic-v1",
        contract_hash=contract.digest().sha256,
        rubric_hash=ABSENT,
        answer_key_hash=ABSENT,
        verifier_registry_version=REGISTRY_VERSION,
        verifier_registry_hash=registry_digest().sha256,
        coverage_report_hash=ABSENT,
        baseline_configuration_hash=ABSENT,
        case_set_id="client/refund-desk",
        split="calibration",
        model_ids=(model_id,),
        provider_versions={model_id: MODELS.get(model_id, "scripted")},
        cost_table_version="client-flat-rate",
        route="direct",
        streaming_disabled=True,
        adapter_id="refund-desk",
        adapter_version="1",
        governor_code_version="0.1.0",
        sqlite_library_version=sqlite3.sqlite_version,
        seed=1,
    )


def _store(runs_dir: Path, run_id: str) -> RecordStore:
    runs_dir.mkdir(parents=True, exist_ok=True)
    path = runs_dir / f"{run_id}.db"
    path.unlink(missing_ok=True)
    return RecordStore(path).open()


def _ledger(contract: Contract) -> Ledger:
    declared = contract.budget.verification_reserve
    reserve = (
        Reserve(
            max_tokens=declared.max_tokens,
            max_estimated_cost=declared.max_estimated_cost,
            sizing="declared",
        )
        if declared is not None
        else Reserve(
            max_tokens=contract.budget.max_tokens // 10,
            max_estimated_cost=contract.budget.max_estimated_cost / 10,
            sizing="derived",
        )
    )
    return Ledger(
        allocated_tokens=contract.budget.max_tokens,
        allocated_cost=contract.budget.max_estimated_cost,
        reserve=reserve,
    )


@dataclass(frozen=True)
class Pair:
    """The same case, run twice, differing only in whether the library is there."""

    case_id: str
    ungoverned: RunOutcome
    governed: RunOutcome


def run_ungoverned(case: DeskCase, *, contract: Contract, runs_dir: Path) -> RunOutcome:
    run_id = f"{case.case_id}-ungoverned"
    tools = tool_port(contract)
    store = _store(runs_dir, run_id)
    try:
        evidence = EvidenceStore(runs_dir / "evidence", data_class="synthetic")
        # The ungoverned arm reaches for the strong model and leaves it there,
        # because nothing is routing it. That is not a thumb on the scale; it is
        # what an ungoverned loop does, and it is why the arms' model ids differ.
        model_id = contract.models.eligible[-1] if contract.models else "gpt-5"
        recorder = BaselineRecorder(
            run_id=run_id,
            contract=contract,
            store=store,
            citable_index=citable_index(),
            evidence=evidence.for_driver(run_id),
        )
        recorder.open_run(_manifest(run_id, contract, model_id, "baseline"))
        wiring = Ungoverned(tools=tools, recorder=recorder, model=model_id)
        return run(
            case,
            contract=contract,
            wiring=wiring,
            tools=tools,
            model=ScriptedModelPort(turns=list(case.script)),
        )
    finally:
        store.close()


def run_governed(
    case: DeskCase,
    *,
    contract: Contract,
    runs_dir: Path,
    approval: Decision = "approved",
) -> RunOutcome:
    run_id = f"{case.case_id}-governed"
    tools = tool_port(contract)
    store = _store(runs_dir, run_id)
    try:
        evidence = EvidenceStore(runs_dir / "evidence", data_class="synthetic")
        model_id = contract.models.start if contract.models else "gpt-5"
        driver = Driver(
            run_id=run_id,
            contract=contract,
            store=store,
            ledger=_ledger(contract),
            governor=ToolGovernor(contract, approval=ScriptedApprovalPort(default=approval)),
            tools=tools,
            fuse=build_fuse(contract),
            evidence=evidence.for_driver(run_id),
        )
        driver.open_run(_manifest(run_id, contract, model_id, "governed"))
        # AD-7: built, hashed and appended before any verifier runs. Without it
        # `policy-refs-resolve` cannot be evaluated and the run fail-closes,
        # correctly, having spent its whole budget first.
        driver.bind_citable_index(citable_index())
        return run(
            case,
            contract=contract,
            wiring=Governed(driver),
            tools=tools,
            model=ScriptedModelPort(turns=list(case.script)),
        )
    finally:
        store.close()


def adjudicate(
    case: DeskCase,
    *,
    contract: Contract | None = None,
    runs_dir: Path | str = Path("runs/refund-desk"),
    approval: Decision = "approved",
) -> Pair:
    """Run one refund request both ways. The only difference is the wiring."""
    resolved = contract or load_contract()
    directory = Path(runs_dir)
    return Pair(
        case_id=case.case_id,
        ungoverned=run_ungoverned(case, contract=resolved, runs_dir=directory),
        governed=run_governed(
            case, contract=resolved, runs_dir=directory, approval=approval
        ),
    )
