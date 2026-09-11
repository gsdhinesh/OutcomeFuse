"""The campaign: every case, both arms, paired into a proof card (AD-9, AD-10).

This is where the two arms meet. It builds the manifests, runs each case twice,
seals both records and pairs the results.

**The manifests are built together, from one shape.** `require_comparable`
refuses two arms that differ anywhere except run id, mode and the enabled
mechanisms — route, seed, cost table, adapter version, *and the model set*
included. So both arms declare the contract's whole eligible model list and the
same provider versions. Escalation is a mechanism, recorded in
`enabled_mechanisms`, not a different set of models: an arm that declared only
the model it happened to start on would be refused, and papering over that by
widening `MAY_DIFFER` is how a comparison stops being about governance and
starts being about configuration.

**Pairs are formed per case, never across cases.** The whole design is paired:
the same case, the same corpus, the same prompt, differing only in whether a
governor was present. Comparing aggregate baseline spend against aggregate
governed spend would let case mix do the work.

**Unscoreable cases are dropped loudly.** A case whose gate could not run on one
arm is excluded and named, not folded in as a failure: a gate that could not
produce a verdict says nothing about the agent, and counting it as a loss for
one arm would move the headline by the amount of our own breakage.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..adapters.host.reference import ReferenceAdapter
from ..conformance import BatteryResult, run_battery
from ..core.contract import Contract
from ..core.gate import GateUnavailable
from ..core.policy import Ledger, Reserve
from ..core.record import RecordStore, RunManifest
from ..core.verify import CitableIndex
from ..evidence.counter_metrics import BlindReview
from ..evidence.store import EvidenceStore
from ..ports import ModelPort
from ..runtime import BaselineRecorder, Driver, ToolGovernor
from ..workloads import WorkloadToolPort, citable_index_for, tool_port_for
from .answer_keys import load_answer_keys
from .attribution import (
    AttributionError,
    CaseSaving,
    attribute_cost,
    attribute_tokens,
)
from .cases import Case, load_case_set
from .costs import CostTable
from .counters import CounterMetrics, read_counter_metrics
from .overhead import OverheadStudy
from .preregistration import Preregistration
from .proofcard import ArmTotals, PairedCase, ProofCard, build_proof_card
from .reportability import Accompaniment, Reportability, RunFacts, assess
from .runner import BaselineArm, GovernedArm, Outcome, run_case


class CampaignError(RuntimeError):
    """The campaign could not be set up. Never an agent's own failure."""


@dataclass(frozen=True)
class Plan:
    """Everything a campaign needs that is not a live connection."""

    workload: str
    split: str
    contract: Contract
    model: ModelPort
    max_output_tokens: int
    reasoning_effort: str | None
    #: Observed from the service, identical on both arms (AD-9).
    provider_versions: dict[str, str]
    cost_table: CostTable | None = None
    preregistration_hash: str | None = None
    #: Carried from the preregistration so accompaniment can be checked (FR59,
    #: FR62, FR70). Zero and empty mean no record was supplied, which
    #: `check_admissibility` already refuses for a headline.
    minimum_case_count: int = 0
    counter_metric_thresholds: dict[str, float] = field(default_factory=dict)
    counter_metrics_reported: tuple[str, ...] = ()
    #: The record itself, and the study its targets were derived from, so the
    #: counter-metrics can be read against their thresholds.
    preregistration: Preregistration | None = None
    overhead_study: OverheadStudy | None = None
    blind_review: BlindReview | None = None
    baseline_model: str = "gpt-5"
    #: Overrides the contract's `models.start`. Calibration only, and it exists
    #: for one question: when the governed arm loses, was that the governor or
    #: was it the cheaper model it was told to start on? Running both arms on
    #: the same model answers it. The manifests are unaffected — both still
    #: declare the whole eligible set — so the arms stay comparable.
    governed_model: str | None = None
    adapter_id: str = "reference"
    adapter_version: str = "1"
    governor_code_version: str = "0.1.0"
    seed: int = 1
    #: Digests of the frozen artefacts. Identical on both arms by construction.
    hashes: dict[str, str] = field(default_factory=dict)


@dataclass
class CaseResult:
    """One case, both arms, before pairing."""

    case_id: str
    baseline: Outcome
    governed: Outcome
    baseline_passed: bool
    governed_passed: bool
    gate_qualifier: str
    baseline_seal: str
    governed_seal: str


@dataclass
class CampaignReport:
    workload: str
    split: str
    results: list[CaseResult]
    #: Named rather than silently dropped.
    excluded: list[tuple[str, str]]
    baseline_manifest: RunManifest | None = None
    governed_manifest: RunManifest | None = None
    cost_table: CostTable | None = None
    baseline_model: str = "gpt-5"
    #: The conformance battery's actual verdict on the adapter (AD-15).
    battery: BatteryResult | None = None
    #: From the preregistration, where one was supplied.
    minimum_case_count: int = 0
    counter_metric_thresholds: dict[str, float] = field(default_factory=dict)
    #: Supplied so the counter-metrics can be read against their thresholds.
    preregistration: Preregistration | None = None
    overhead_study: OverheadStudy | None = None
    #: FR69. A human who never saw the verdict, so the review can contradict it.
    #: No campaign can produce one, and its absence is reported rather than
    #: standing in for a rate of zero.
    blind_review: BlindReview | None = None
    #: FR70: a tool-call reduction is meaningless without it, and it is not
    #: measurable until a mechanism actually suppresses a tool.
    tool_suppression_accuracy: float | None = None
    coverage_report_hash: str | None = None

    def savings(self) -> list[CaseSaving]:
        """Quality-matched pairs only: the rest bought a different outcome."""
        return [
            _saving(r, self.cost_table, self.baseline_model)
            for r in self.results
            if r.baseline_passed and r.governed_passed
        ]

    def proof_card(self) -> ProofCard:
        # FR62: the breakdown travels with the figure or the figure does not
        # ship. It decomposes the *token* saving, which is what the headline
        # reports; routing appears only in `cost_attribution`, because a cheaper
        # model emits the same number of tokens.
        return build_proof_card(
            self.workload,
            [_pair(r) for r in self.results],
            per_mechanism=attribute_tokens(self.savings()),
        )

    def cost_attribution(self) -> dict[str, float]:
        """How much of the cost saving was governing, and how much was routing."""
        return attribute_cost(self.savings())

    def counter_metrics(self) -> CounterMetrics:
        """FR66's six, read where readable and admitted where not."""
        return read_counter_metrics(
            self,
            study=self.overhead_study,
            preregistration=self.preregistration,
            blind_review=self.blind_review,
        )

    def run_facts(self) -> tuple[RunFacts, RunFacts]:
        """What the harness knows about each arm, apart from its manifest.

        `adapter_passed_conformance` is the battery's actual result rather than
        an assertion. AD-15 makes an uncertified adapter inadmissible, so a
        hardcoded `True` here would be the single most effective way to publish
        a figure nothing had checked.
        """
        passed = self.battery is not None and self.battery.passed
        qualifiers = {r.gate_qualifier for r in self.results}
        qualifier = "constraint-backed" if "constraint-backed" in qualifiers else None
        facts = RunFacts(
            adapter_passed_conformance=passed,
            gateway_metered=False,
            gate_qualifier=qualifier or (next(iter(qualifiers), None)),
        )
        return facts, facts

    def reportability(self, *, headline_claim: bool) -> Reportability | None:
        """AD-10's one predicate. `None` until both arms have a manifest."""
        if self.baseline_manifest is None or self.governed_manifest is None:
            return None
        baseline_facts, governed_facts = self.run_facts()
        card = self.proof_card()
        return assess(
            self.baseline_manifest,
            self.governed_manifest,
            baseline_facts,
            governed_facts,
            Accompaniment(
                per_mechanism_breakdown=bool(card.per_mechanism),
                reports_tool_call_reduction=True,
                tool_suppression_accuracy=self.tool_suppression_accuracy,
                case_count=card.quality_matched_pairs,
                minimum_case_count=self.minimum_case_count,
                coverage_report_hash=self.coverage_report_hash,
                predominantly_constraint_backed="constraint-backed" in qualifiers_of(card),
                predominantly_constraint_backed_declared=True,
                reports_failures_and_escalations=True,
                headline_is_net=True,
                counter_metric_thresholds=self.counter_metric_thresholds,
                # Only what was actually read. Naming a metric here that nobody
                # measured would claim a check that did not happen, and FR66's
                # threshold check would then pass on an absent number.
                counter_metrics_reported=self.counter_metrics().reported,
            ),
            headline=headline_claim,
        )


def qualifiers_of(card: ProofCard) -> set[str]:
    return set(card.gate_qualifiers)


def _saving(
    result: CaseResult, cost_table: CostTable | None, baseline_model: str
) -> CaseSaving:
    governed, baseline = result.governed, result.baseline
    return CaseSaving(
        case_id=result.case_id,
        baseline_tokens=baseline.spend.total_tokens,
        governed_tokens=governed.spend.total_tokens,
        baseline_cost=baseline.cost,
        governed_cost=governed.cost,
        governed_cost_at_baseline_rates=_repriced(governed, cost_table, baseline_model),
        terminal_reason=governed.terminal_reason,
        cut_short=governed.cut_short,
    )


def _repriced(governed: Outcome, cost_table: CostTable | None, baseline_model: str) -> float:
    """The governed run's own tokens, at the baseline model's rate.

    Summed per model, because an escalated run spends on two and pricing the
    whole of it at either one would misstate the routing term in both
    directions.
    """
    if cost_table is None or not cost_table.priced:
        return governed.cost
    if not governed.tokens_by_model:
        raise AttributionError(
            f"{governed.case_id} recorded no per-model token counts to reprice"
        )
    return sum(
        cost_table.price(baseline_model, prompt_tokens=prompt, completion_tokens=completion)
        for prompt, completion in governed.tokens_by_model.values()
    )


def _pair(result: CaseResult) -> PairedCase:
    return PairedCase(
        case_id=result.case_id,
        baseline=_totals(result.baseline),
        governed=_totals(result.governed),
        baseline_passed=result.baseline_passed,
        governed_passed=result.governed_passed,
        gate_qualifier=result.gate_qualifier,
        baseline_seal=result.baseline_seal,
        governed_seal=result.governed_seal,
    )


def _totals(outcome: Outcome) -> ArmTotals:
    return ArmTotals(
        tokens=outcome.spend.total_tokens,
        cost=outcome.cost,
        tool_calls=outcome.spend.tool_calls,
    )


SHA_UNSET = "0" * 64


def build_manifest(
    plan: Plan, *, run_id: str, mode: str, mechanisms: dict[str, str]
) -> RunManifest:
    """One shape, two arms. Only run id, mode and mechanisms differ."""
    models = plan.contract.models
    eligible = tuple(models.eligible) if models else (plan.baseline_model,)
    missing = [m for m in eligible if m not in plan.provider_versions]
    if missing:
        # AD-9: an unobserved provider version is not a blank to fill in later.
        # Two arms that guessed differently would be silently incomparable.
        raise CampaignError(f"no observed provider version for {missing}")

    return RunManifest(
        run_id=run_id,
        mode=mode,
        data_class="synthetic",
        retention_profile="mvp-synthetic-v1",
        contract_hash=plan.contract.digest().sha256,
        rubric_hash=plan.hashes.get("rubric", SHA_UNSET),
        answer_key_hash=plan.hashes.get("answer_keys", SHA_UNSET),
        verifier_registry_version=plan.hashes.get("verifier_registry_version", "v1"),
        verifier_registry_hash=plan.hashes.get("verifier_registry", SHA_UNSET),
        coverage_report_hash=plan.hashes.get("coverage_report", SHA_UNSET),
        baseline_configuration_hash=plan.hashes.get("baseline_configuration", SHA_UNSET),
        case_set_id=f"{plan.split}/{plan.workload}",
        split=plan.split,
        preregistration_hash=plan.preregistration_hash,
        model_ids=eligible,
        provider_versions={m: plan.provider_versions[m] for m in eligible},
        cost_table_version=plan.cost_table.version if plan.cost_table else "ct-unpriced",
        route="direct",
        streaming_disabled=True,
        enabled_mechanisms=mechanisms,
        adapter_id=plan.adapter_id,
        adapter_version=plan.adapter_version,
        governor_code_version=plan.governor_code_version,
        sqlite_library_version=sqlite3.sqlite_version,
        seed=plan.seed,
    )


#: What the governed arm had switched on. The baseline's is empty, and that
#: emptiness is the experiment rather than an omission.
GOVERNED_MECHANISMS: dict[str, str] = {
    "tool-governor": "v1",
    "quality-gate": "v1",
    "budget-ledger": "v1",
    "loop-fuse": "v1",
}


def _price(plan: Plan) -> Callable[[str, int, int], float] | None:
    table = plan.cost_table
    if table is None or not table.priced:
        return None
    return lambda model, p, c: table.price(model, prompt_tokens=p, completion_tokens=c)


def run_campaign(
    plan: Plan,
    *,
    runs_dir: Path,
    cases: list[Case] | None = None,
    max_cases: int | None = None,
) -> CampaignReport:
    """Run every case on both arms and pair the results."""
    case_set = load_case_set(plan.workload, plan.split)
    keys = load_answer_keys(
        plan.workload, plan.split, preregistration_hash=plan.preregistration_hash
    )
    chosen = list(cases if cases is not None else case_set.cases)[:max_cases]

    tools = tool_port_for(plan.contract)
    index = citable_index_for(plan.contract)
    price = _price(plan)
    runs_dir.mkdir(parents=True, exist_ok=True)
    # AD-5b: the deliverable lives here, not in the decision log, so FR69's
    # blind review has something to read that the gate did not write.
    evidence = EvidenceStore(runs_dir / "evidence", data_class=case_set.data_class)

    report = CampaignReport(
        workload=plan.workload,
        split=plan.split,
        results=[],
        excluded=[],
        cost_table=plan.cost_table,
        baseline_model=plan.baseline_model,
        # AD-15: measured, not asserted. Cheap, offline, and it runs before any
        # money is spent so an uncertified adapter is known before the campaign
        # rather than at the moment of publishing.
        battery=run_battery(ReferenceAdapter()),
        minimum_case_count=plan.minimum_case_count,
        counter_metric_thresholds=dict(plan.counter_metric_thresholds),
        preregistration=plan.preregistration,
        overhead_study=plan.overhead_study,
        blind_review=plan.blind_review,
        coverage_report_hash=plan.hashes.get("coverage_report"),
    )

    for case in chosen:
        answer_key = keys.get(case.case_id)
        if answer_key is None:
            report.excluded.append((case.case_id, "no answer key"))
            continue
        try:
            result, manifests = _run_pair(
                case, plan, tools=tools, index=index, price=price, answer_key=answer_key,
                runs_dir=runs_dir, evidence=evidence,
            )
        except GateUnavailable as exc:
            # Our breakage, not the agent's. Counting it as a loss for one arm
            # would move the headline by the size of our own bug.
            report.excluded.append((case.case_id, f"gate unavailable: {exc}"))
            continue
        report.results.append(result)
        report.baseline_manifest, report.governed_manifest = manifests

    return report


def _run_pair(
    case: Case,
    plan: Plan,
    *,
    tools: WorkloadToolPort,
    index: CitableIndex | None,
    price: Callable[[str, int, int], float] | None,
    answer_key: dict[str, Any],
    runs_dir: Path,
    evidence: EvidenceStore | None = None,
) -> tuple[CaseResult, tuple[RunManifest, RunManifest]]:
    baseline_manifest = build_manifest(
        plan, run_id=f"{case.case_id}-baseline", mode="baseline", mechanisms={}
    )
    governed_manifest = build_manifest(
        plan,
        run_id=f"{case.case_id}-governed",
        mode="governed",
        mechanisms=dict(GOVERNED_MECHANISMS),
    )

    with _store(runs_dir / f"{case.case_id}-baseline.db") as baseline_store, _store(
        runs_dir / f"{case.case_id}-governed.db"
    ) as governed_store:
        recorder = BaselineRecorder(
            run_id=baseline_manifest.run_id,
            contract=plan.contract,
            store=baseline_store,
            citable_index=index,
            evidence=(
                evidence.for_driver(baseline_manifest.run_id) if evidence else None
            ),
        )
        recorder.open_run(baseline_manifest)
        baseline = run_case(
            case,
            contract=plan.contract,
            arm=BaselineArm(tools, model=plan.baseline_model, recorder=recorder),
            model=plan.model,
            max_output_tokens=plan.max_output_tokens,
            reasoning_effort=plan.reasoning_effort,
            answer_key=answer_key,
            max_iterations=plan.contract.budget.max_iterations,
            price=price,
        )
        baseline_seal = recorder.seal()

        driver = _driver(
            plan,
            governed_store,
            run_id=governed_manifest.run_id,
            tools=tools,
            evidence=(
                evidence.for_driver(governed_manifest.run_id) if evidence else None
            ),
        )
        driver.open_run(governed_manifest)
        if index is not None:
            driver.bind_citable_index(index)
        governed = run_case(
            case,
            contract=plan.contract,
            arm=GovernedArm(driver, start_model=_governed_model(plan)),
            model=plan.model,
            max_output_tokens=plan.max_output_tokens,
            reasoning_effort=plan.reasoning_effort,
            answer_key=answer_key,
            max_iterations=plan.contract.budget.max_iterations,
            price=price,
        )
        governed_seal = governed_store.seal(driver.run_id)

    baseline_verdict = recorder.verdict
    return (
        CaseResult(
            case_id=case.case_id,
            baseline=baseline,
            governed=governed,
            baseline_passed=bool(baseline_verdict and baseline_verdict.passed),
            governed_passed=driver.quality_state == "pass",
            # FR61: a pair evaluated against the answer key and one evaluated
            # against constraints alone are not the same evidence, so the weaker
            # of the two travels with the pair rather than the flattering one.
            gate_qualifier=_weaker(
                baseline_verdict.qualifier if baseline_verdict else None,
                driver.gate_qualifier,
            ),
            baseline_seal=baseline_seal or SHA_UNSET,
            governed_seal=governed_seal or SHA_UNSET,
        ),
        (baseline_manifest, governed_manifest),
    )


def _governed_model(plan: Plan) -> str:
    if plan.governed_model is not None:
        return plan.governed_model
    return plan.contract.models.start if plan.contract.models else plan.baseline_model


def _weaker(left: str | None, right: str | None) -> str:
    return (
        "constraint-backed"
        if "constraint-backed" in (left, right) or left is None or right is None
        else "reference-backed"
    )


def _driver(
    plan: Plan,
    store: RecordStore,
    *,
    run_id: str,
    tools: WorkloadToolPort,
    evidence: Any | None = None,
) -> Driver:
    budget = plan.contract.budget
    return Driver(
        run_id=run_id,
        contract=plan.contract,
        store=store,
        ledger=Ledger(
            allocated_tokens=budget.max_tokens,
            allocated_cost=budget.max_estimated_cost,
            reserve=budget.verification_reserve
            or Reserve(
                max_tokens=budget.max_tokens // 10,
                max_estimated_cost=budget.max_estimated_cost / 10,
                sizing="declared",
            ),
        ),
        governor=ToolGovernor(plan.contract),
        tools=tools,
        evidence=evidence,
    )


def _store(path: Path) -> RecordStore:
    path.unlink(missing_ok=True)
    return RecordStore(path).open()
