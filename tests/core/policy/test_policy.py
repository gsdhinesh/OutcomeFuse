"""Ledger, Policy and Loop Fuse (AD-3, AD-4, AD-18).

BUILD-ORDER's acceptance for E4 is exact:

  *Done when:* the FR103 nine-row mapping table passes as a test table, and a
  `low-value` proposal against an unmet mandatory criterion is rejected and
  recorded as a violation.

So the mapping is driven as a literal table rather than paraphrased into
branches, and the floor-protection rule is tested for both directions.
"""

from __future__ import annotations

from typing import Any, ClassVar

import pytest
from pydantic import ValidationError

from outcomefuse.core.policy import (
    COMPOSITION_ORDER,
    FR103_TABLE,
    PRECEDENCE_LADDER,
    AdvisorRegistry,
    Attribution,
    EvidenceRequest,
    Ledger,
    LedgerError,
    LoopFuse,
    Policy,
    Proposal,
    Reserve,
    Situation,
    outcome_is_well_formed,
    size_reserve,
)


def a_ledger(tokens: int = 1000, cost: float = 1.0, reserve_tokens: int = 100) -> Ledger:
    return Ledger(
        allocated_tokens=tokens,
        allocated_cost=cost,
        reserve=Reserve(max_tokens=reserve_tokens, max_estimated_cost=0.1, sizing="declared"),
    )


class TestFR103MappingTable:
    """The nine rows, driven as a table."""

    SITUATIONS: ClassVar[dict[str, Situation]] = {
        "stop-sufficient": Situation(floor_met=True, quality_state="pass"),
        "halt-exhausted-partial": Situation(
            affordable_step_advances_floor=False, contract_directs="return-partial"
        ),
        "halt-exhausted-human": Situation(
            affordable_step_advances_floor=False, contract_directs="request-human"
        ),
        "halt-no-progress": Situation(no_progress=True),
        "referred-human": Situation(gate_failed=True, contract_directs="request-human"),
        "returned-partial": Situation(gate_failed=True, contract_directs="return-partial"),
        "approval-terminates": Situation(approval_elapsed=True, on_timeout="terminate"),
        "approval-escalates": Situation(approval_elapsed=True, on_timeout="escalate"),
        "gate-unavailable": Situation(gate_unavailable=True),
        "ledger-lost": Situation(ledger_state_lost=True),
    }

    EXPECTED: ClassVar[dict[str, tuple[str, str, Any]]] = {
        "stop-sufficient": ("sufficiency", "terminate", "stop-sufficient"),
        "halt-exhausted-partial": ("exhaustion", "return-partial", "halt-exhausted"),
        "halt-exhausted-human": ("exhaustion", "request-human", "halt-exhausted"),
        "halt-no-progress": ("no-progress", "terminate", "halt-no-progress"),
        "referred-human": ("escalation-gate-fail", "request-human", "referred-human"),
        "returned-partial": ("escalation-gate-fail", "return-partial", "returned-partial"),
        "approval-terminates": ("approval-timeout", "terminate", "approval-timeout"),
        "approval-escalates": ("approval-timeout", "escalate", None),
        "gate-unavailable": ("fail-closed", "request-human", "fail-closed"),
        "ledger-lost": ("fail-closed", "terminate", "fail-closed"),
    }

    @pytest.mark.parametrize("name", sorted(EXPECTED))
    def test_each_row_maps_as_the_prd_states(self, name):
        outcome = Policy().resolve(self.SITUATIONS[name])
        reason, action, terminal = self.EXPECTED[name]
        assert (outcome.decision_reason, outcome.policy_action, outcome.terminal_reason) == (
            reason,
            action,
            terminal,
        )

    def test_the_shipped_table_covers_every_situation(self):
        shipped = {(r, a, t) for _, r, a, t in FR103_TABLE}
        assert set(self.EXPECTED.values()) <= shipped

    def test_the_table_has_the_rows_the_prd_lists(self):
        assert len(FR103_TABLE) == 10  # nine PRD rows; exhaustion splits by disposition

    def test_an_escalating_timeout_records_no_terminal_reason(self):
        # The run continues, so naming a terminal reason would close a run that
        # did not end.
        assert Policy().resolve(self.SITUATIONS["approval-escalates"]).terminal_reason is None

    def test_terminal_reason_names_the_cause_not_the_disposition(self):
        # A run that exhausts and returns a partial has one cause and one
        # disposition; recording `returned-partial` here would erase the cost story.
        outcome = Policy().resolve(self.SITUATIONS["halt-exhausted-partial"])
        assert outcome.policy_action == "return-partial"
        assert outcome.terminal_reason == "halt-exhausted"


class TestFloorProtection:
    """AD-18: the Policy rejects it, not the estimator."""

    def low_value(self, **over) -> Proposal:
        base = {
            "mechanism": "marginal-value",
            "step_id": "s1",
            "action": "skip",
            "candidate_reason": "low-value",
            "advances_criteria": ("result-matches-key",),
        }
        return Proposal(**(base | over))

    def test_low_value_against_an_unmet_mandatory_criterion_is_rejected(self):
        policy = Policy()
        assert policy.screen(self.low_value(), {"result-matches-key"}) is None

    def test_the_rejected_attempt_is_recorded_as_a_violation(self):
        # FR99 reports it as a violation rather than a saving.
        policy = Policy()
        policy.screen(self.low_value(), {"result-matches-key"})
        assert len(policy.violations) == 1
        violation = policy.violations[0]
        assert violation.step_id == "s1"
        assert violation.criteria == ("result-matches-key",)
        assert "never the floor" in violation.detail

    def test_low_value_against_an_already_met_criterion_is_allowed(self):
        # The estimator governs enrichment, which is exactly this case.
        policy = Policy()
        assert policy.screen(self.low_value(), {"something-else"}) is not None
        assert policy.violations == []

    def test_low_value_advancing_nothing_mandatory_is_allowed(self):
        policy = Policy()
        proposal = self.low_value(advances_criteria=())
        assert policy.screen(proposal, {"result-matches-key"}) is not None
        assert policy.violations == []

    def test_a_non_low_value_proposal_is_never_screened_out(self):
        policy = Policy()
        proposal = self.low_value(candidate_reason="justified")
        assert policy.screen(proposal, {"result-matches-key"}) is proposal
        assert policy.violations == []

    def test_every_protected_criterion_is_named(self):
        policy = Policy()
        proposal = self.low_value(advances_criteria=("a", "b", "c"))
        policy.screen(proposal, {"a", "c"})
        assert policy.violations[0].criteria == ("a", "c")


class TestPrecedenceLadder:
    def test_the_ladder_is_the_order_fr2_states(self):
        assert PRECEDENCE_LADDER == (
            "fail-closed",
            "human-approval",
            "sufficiency",
            "exhaustion",
            "no-progress",
            "step-denial",
        )

    def test_fail_closed_outranks_everything(self):
        outcome = Policy().resolve(
            Situation(
                ledger_state_lost=True,
                floor_met=True,
                quality_state="pass",
                approval_elapsed=True,
                on_timeout="terminate",
                no_progress=True,
            )
        )
        assert outcome.terminal_reason == "fail-closed"

    def test_approval_outranks_sufficiency(self):
        outcome = Policy().resolve(
            Situation(
                approval_elapsed=True,
                on_timeout="terminate",
                floor_met=True,
                quality_state="pass",
            )
        )
        assert outcome.decision_reason == "approval-timeout"

    def test_sufficiency_outranks_exhaustion(self):
        outcome = Policy().resolve(
            Situation(floor_met=True, quality_state="pass", affordable_step_advances_floor=False)
        )
        assert outcome.terminal_reason == "stop-sufficient"

    def test_exhaustion_outranks_no_progress(self):
        outcome = Policy().resolve(
            Situation(affordable_step_advances_floor=False, no_progress=True)
        )
        assert outcome.terminal_reason == "halt-exhausted"

    def test_sufficiency_is_invalid_before_the_gate_has_run(self):
        # FR105: before the first gate execution the honest answer is that we
        # have not looked.
        with pytest.raises(ValueError, match="not-evaluated"):
            Policy().resolve(Situation(floor_met=True, quality_state="not-evaluated"))


class TestLedger:
    def test_the_three_quantities_are_never_conflated(self):
        ledger = a_ledger()
        ledger.hold("h1", "d1", "tool-governor", 200, 0.2)
        assert ledger.in_flight_tokens == 200
        assert ledger.spent_tokens == 0
        assert ledger.reserve.max_tokens == 100

    def test_no_step_may_spend_the_reserve(self):
        ledger = a_ledger(tokens=1000, reserve_tokens=100)
        assert ledger.spendable_tokens() == 900
        assert not ledger.can_afford(901, 0.0)

    def test_verification_may_use_the_reserve(self):
        ledger = a_ledger(tokens=1000, reserve_tokens=100)
        assert ledger.can_afford(1000, 0.0, may_use_reserve=True)

    def test_affordability_is_a_pure_query(self):
        ledger = a_ledger()
        before = (ledger.spent_tokens, ledger.in_flight_tokens)
        ledger.can_afford(500, 0.5)
        assert (ledger.spent_tokens, ledger.in_flight_tokens) == before

    def test_a_hold_is_taken_before_the_spend_happens(self):
        ledger = a_ledger()
        ledger.hold("h1", "d1", "model-governor", 300, 0.3)
        assert ledger.spendable_tokens() == 600
        ledger.settle("h1")
        assert ledger.spent_tokens == 300
        assert ledger.in_flight_tokens == 0

    def test_settlement_may_differ_from_the_estimate(self):
        ledger = a_ledger()
        ledger.hold("h1", "d1", "model-governor", 300, 0.3)
        ledger.settle("h1", actual_tokens=250, actual_cost=0.25)
        assert ledger.spent_tokens == 250

    def test_a_denial_releases_without_spending(self):
        ledger = a_ledger()
        ledger.hold("h1", "d1", "tool-governor", 300, 0.3)
        ledger.release_denied("h1")
        assert ledger.spent_tokens == 0 and ledger.in_flight_tokens == 0

    def test_termination_releases_everything_outstanding(self):
        ledger = a_ledger()
        ledger.hold("h1", "d1", "tool-governor", 100, 0.1)
        ledger.hold("h2", "d2", "model-governor", 100, 0.1)
        assert len(ledger.release_all()) == 2
        assert ledger.in_flight_tokens == 0

    def test_a_hold_is_released_by_exactly_one_path(self):
        ledger = a_ledger()
        ledger.hold("h1", "d1", "tool-governor", 100, 0.1)
        ledger.settle("h1")
        with pytest.raises(LedgerError, match="no outstanding hold"):
            ledger.release_denied("h1")

    def test_a_duplicate_hold_id_is_refused(self):
        ledger = a_ledger()
        ledger.hold("h1", "d1", "tool-governor", 100, 0.1)
        with pytest.raises(LedgerError, match="already outstanding"):
            ledger.hold("h1", "d2", "tool-governor", 100, 0.1)

    def test_an_unaffordable_hold_is_a_fail_closed_condition(self):
        # Affordability is queried before deciding, so reaching a refusal here
        # means the query was skipped.
        ledger = a_ledger()
        with pytest.raises(LedgerError, match="fail-closed"):
            ledger.hold("h1", "d1", "tool-governor", 5000, 5.0)

    def test_governor_overhead_is_held_like_anything_else(self):
        ledger = a_ledger()
        ledger.hold("h1", "d1", "quality-gate", 50, 0.05, overhead=True)
        assert ledger.overhead_tokens() == 50

    def test_a_reserve_larger_than_the_ceiling_is_refused(self):
        with pytest.raises(LedgerError, match="exceeds the ceiling"):
            Ledger(
                allocated_tokens=100,
                allocated_cost=1.0,
                reserve=Reserve(max_tokens=200, max_estimated_cost=0.1, sizing="declared"),
            )

    def test_an_escalation_may_not_consume_the_reserve(self):
        # FR101: an escalation that consumes the reserve buys a better answer
        # nobody can check.
        ledger = a_ledger(tokens=1000, reserve_tokens=100)
        assert ledger.escalation_leaves_reserve_intact(900, 0.0)
        assert not ledger.escalation_leaves_reserve_intact(950, 0.0)


class TestReserveSizing:
    def test_a_declared_reserve_is_recorded_as_declared(self):
        reserve = size_reserve(1000, 1.0, declared_tokens=250, declared_cost=0.25)
        assert reserve.sizing == "declared" and reserve.max_tokens == 250

    def test_an_undeclared_reserve_uses_the_deterministic_default(self):
        reserve = size_reserve(1000, 1.0)
        assert reserve.sizing == "derived" and reserve.max_tokens == 150

    def test_the_derived_default_is_deterministic(self):
        assert size_reserve(1000, 1.0) == size_reserve(1000, 1.0)

    def test_half_a_declaration_is_refused(self):
        with pytest.raises(LedgerError, match="both tokens and cost"):
            size_reserve(1000, 1.0, declared_tokens=250)


class TestAttribution:
    def test_shares_must_sum_to_one(self):
        with pytest.raises(ValidationError, match="sum to"):
            Attribution(total_tokens=100, total_cost=0.1, shares={"a": 0.5, "b": 0.2})

    def test_a_decomposition_over_several_mechanisms_is_accepted(self):
        # No tie-break elects a single causer: the breakdown would then be a
        # function of the tie-break rather than of the mechanisms.
        attribution = Attribution(
            total_tokens=100, total_cost=0.1, shares={"context-governor": 0.6, "tool-governor": 0.4}
        )
        assert attribution.tokens_for("context-governor") == 60

    def test_an_empty_decomposition_is_refused(self):
        with pytest.raises(ValidationError, match="at least one mechanism"):
            Attribution(total_tokens=100, total_cost=0.1, shares={})

    def test_a_negative_share_is_refused(self):
        with pytest.raises(ValidationError, match="negative"):
            Attribution(total_tokens=10, total_cost=0.1, shares={"a": 1.5, "b": -0.5})


class TestAdvisors:
    class Fine:
        name = "tool-governor"

        def advise(self, state):
            return Proposal(
                mechanism="tool-governor", step_id="s1", action="skip",
                candidate_reason="duplicate",
            )

    class Broken:
        name = "context-governor"

        def advise(self, state):
            raise RuntimeError("boom")

    def test_advisors_compose_in_the_fixed_order_not_registration_order(self):
        registry = AdvisorRegistry(
            {"marginal-value": self.Fine(), "preflight-planner": self.Fine()}
        )
        assert registry.enabled == ("preflight-planner", "marginal-value")

    def test_an_advisor_outside_the_composition_order_is_refused(self):
        with pytest.raises(ValueError, match="outside the composition order"):
            AdvisorRegistry({"mystery-mechanism": self.Fine()})

    def test_a_raising_advisor_is_deregistered_and_the_run_continues(self):
        # Fail-open is a property of the registry (AD-20).
        seen: list[str] = []
        registry = AdvisorRegistry(
            {"context-governor": self.Broken(), "tool-governor": self.Fine()}
        )
        produced = registry.compose(None, on_degraded=lambda name, exc: seen.append(name))
        assert seen == ["context-governor"]
        assert len(produced) == 1
        assert registry.degraded

    def test_a_deregistration_does_not_survive_into_a_new_registry(self):
        # Run-scoped: a transient failure in one repeat cannot degrade every
        # repeat that follows it in the same process.
        first = AdvisorRegistry({"context-governor": self.Broken()})
        first.compose(None)
        second = AdvisorRegistry({"context-governor": self.Broken()})
        assert not second.degraded

    def test_disabled_means_not_registered(self):
        # No mechanism carries an `if enabled` branch, so an ablation is a
        # registry change.
        assert AdvisorRegistry({}).enabled == ()

    def test_the_composition_order_names_the_quality_gate(self):
        # It exists as a registry entry for attribution and ablation even
        # though the Gate itself is protected.
        assert "quality-gate" in COMPOSITION_ORDER

    @pytest.mark.parametrize(
        ("kind", "outcome"),
        [
            ("rubric-judgement", {"verdict": "pass", "verification_mode": "x", "unmet": []}),
            ("compression-pass", {"capsule": "c", "tokens_before": 10, "tokens_after": 5}),
            ("complexity-estimate", {"score": 0.5}),
            ("confidence-estimate", {"score": 0.5}),
            ("planner-envelope", {"steps": [], "max_tokens": 1, "max_estimated_cost": 1.0}),
        ],
    )
    def test_each_evidence_kind_declares_its_outcome_schema(self, kind, outcome):
        assert outcome_is_well_formed(kind, outcome)

    def test_an_outcome_missing_a_declared_field_is_malformed(self):
        assert not outcome_is_well_formed("complexity-estimate", {"wrong": 1})

    def test_an_unregistered_evidence_kind_is_refused(self):
        with pytest.raises(ValidationError):
            EvidenceRequest(kind="vibe-check", mechanism="marginal-value")


class TestLoopFuse:
    def state(self, value):
        return {"draft": value}

    def test_a_repeated_state_halts(self):
        fuse = LoopFuse(max_iterations=10)
        first = fuse.fingerprint(
            iteration=0, task_state=self.state("a"), evidence_count=1, quality_state="fail"
        )
        assert fuse.observe(first) is None
        again = fuse.fingerprint(
            iteration=1, task_state=self.state("a"), evidence_count=1, quality_state="fail"
        )
        assert fuse.observe(again) == "repeated-state"

    def test_progress_does_not_halt(self):
        fuse = LoopFuse(max_iterations=10)
        for index, value in enumerate("abcd"):
            printed = fuse.fingerprint(
                iteration=index,
                task_state=self.state(value),
                evidence_count=index + 1,
                quality_state="fail",
            )
            assert fuse.observe(printed) is None

    def test_no_new_evidence_across_the_window_halts(self):
        fuse = LoopFuse(max_iterations=20, stale_iterations=2)
        halt = None
        for index, value in enumerate("abcde"):
            printed = fuse.fingerprint(
                iteration=index, task_state=self.state(value), evidence_count=7,
                quality_state="fail",
            )
            halt = fuse.observe(printed)
            if halt:
                break
        assert halt == "no-new-evidence"

    def test_the_iteration_limit_halts(self):
        fuse = LoopFuse(max_iterations=2)
        fuse.observe(
            fuse.fingerprint(
                iteration=0, task_state=self.state("a"), evidence_count=1, quality_state="fail"
            )
        )
        halt = fuse.observe(
            fuse.fingerprint(
                iteration=1, task_state=self.state("b"), evidence_count=2, quality_state="fail"
            )
        )
        assert halt == "iteration-limit"

    def test_repeated_tool_arguments_halt(self):
        fuse = LoopFuse(max_iterations=10)
        assert fuse.observe_tool_call("sql_query", {"sql": "SELECT 1"}) is None
        repeat = fuse.observe_tool_call("sql_query", {"sql": "SELECT 1"})
        assert repeat == "repeated-tool-arguments"

    def test_different_arguments_are_not_a_repeat(self):
        fuse = LoopFuse(max_iterations=10)
        fuse.observe_tool_call("sql_query", {"sql": "SELECT 1"})
        assert fuse.observe_tool_call("sql_query", {"sql": "SELECT 2"}) is None

    def test_the_fingerprint_is_deterministic(self):
        fuse = LoopFuse(max_iterations=10)
        args = {"iteration": 0, "task_state": {"a": [1, 2]}, "evidence_count": 3,
                "quality_state": "fail"}
        assert fuse.fingerprint(**args).sha256 == fuse.fingerprint(**args).sha256

    def test_key_order_does_not_change_the_fingerprint(self):
        fuse = LoopFuse(max_iterations=10)
        left = fuse.fingerprint(
            iteration=0, task_state={"a": 1, "b": 2}, evidence_count=1, quality_state="fail"
        )
        right = fuse.fingerprint(
            iteration=0, task_state={"b": 2, "a": 1}, evidence_count=1, quality_state="fail"
        )
        assert left.sha256 == right.sha256

    def test_budget_exhaustion_is_not_a_loop_fuse_condition(self):
        # FR27 says so explicitly; it terminates under FR92. Conflating them
        # would file the product's central cost event as a stall.
        fuse = LoopFuse(max_iterations=10)
        assert "exhaust" not in " ".join(
            str(fuse.observe(fuse.fingerprint(
                iteration=i, task_state=self.state(v), evidence_count=i, quality_state="fail"
            )) or "") for i, v in enumerate("ab")
        )
