"""Validating the library through a client that was never anticipated.

The suite's other tests exercise OutcomeFuse from inside the distribution, where
every import is a sibling and every fixture was written alongside the thing it
fixes. These do not. They drive the same code through `clients/refund_desk`,
which names a workload the library has never heard of, builds its own tool port,
and runs one loop twice with the governor plugged in and plugged out.

Two questions are being answered, and only the second is about behaviour:

- **Can the library be plugged into a use case it was not built around?** If a
  new workload needs an edit under `src/`, the answer is no, and every claim
  about generality is really a claim about four frozen workloads.
- **Does plugging it in change what happens?** A governor that changes nothing
  costs latency and buys nothing. A governor that changes the *answer* is worse
  than useless. The interesting result is the one in between, and asserting on
  it is the only way to know which of the three this is.

Every assertion about a side effect reads the tool port's own probe rather than
the decision log (AD-15): the log is the artefact a broken run would falsify, so
it cannot also be the evidence that the run was not broken.
"""

from __future__ import annotations

import pytest
from refund_desk.compose import adjudicate, load_contract, run_governed, run_ungoverned
from refund_desk.desk import POLICY, DeskCase, case_by_id, cases, citable_index, tool_port
from refund_desk.loop import parse_deliverable

from outcomefuse.core.record import check_order, open_store
from outcomefuse.workloads import tool_port_for
from outcomefuse.workloads.toolport import ToolError


@pytest.fixture(scope="module")
def contract():
    return load_contract()


@pytest.fixture
def partial_case() -> DeskCase:
    return case_by_id("rd-001")


class TestThePlugPoint:
    """A new use case needs a handler table, not a change to the library."""

    def test_the_library_has_never_heard_of_this_workload(self, contract) -> None:
        assert contract.workload == "refund-desk"
        with pytest.raises(ToolError):
            tool_port_for(contract)

    def test_and_the_client_builds_its_own_port_anyway(self, contract) -> None:
        port = tool_port(contract)
        assert {tool.name for tool in contract.tools} == {
            "order_lookup",
            "shipment_status",
            "refund_policy_lookup",
            "issue_refund",
        }
        assert port.invocation_count("order_lookup") == 0

    def test_a_handler_table_that_lies_is_refused_at_construction(self, contract) -> None:
        from outcomefuse.workloads.toolport import WorkloadToolPort

        with pytest.raises(ToolError, match="does not match the contract's tools"):
            WorkloadToolPort(contract=contract, handlers={"order_lookup": lambda _: None})

    def test_the_citable_index_is_the_published_policy_and_nothing_else(self) -> None:
        index = citable_index()
        assert {entry.id for entry in index.entries} == set(POLICY)
        assert "RP-9" not in index


class TestTheSameLoopBothWays:
    def test_the_wiring_does_not_change_the_answer(self, contract, tmp_path) -> None:
        pair = adjudicate(case_by_id("rd-001"), contract=contract, runs_dir=tmp_path)
        assert pair.ungoverned.deliverable == pair.governed.deliverable
        assert pair.ungoverned.passed and pair.governed.passed

    @pytest.mark.parametrize("case_id", [case.case_id for case in cases()])
    def test_every_case_passes_its_gate_on_both_arms(self, contract, tmp_path, case_id) -> None:
        pair = adjudicate(case_by_id(case_id), contract=contract, runs_dir=tmp_path)
        assert pair.ungoverned.passed, pair.ungoverned.deliverable
        assert pair.governed.passed, pair.governed.deliverable

    def test_the_ungoverned_arm_executes_everything_it_proposes(
        self, contract, tmp_path, partial_case
    ) -> None:
        outcome = run_ungoverned(partial_case, contract=contract, runs_dir=tmp_path)
        assert outcome.proposed == outcome.invoked
        assert outcome.withheld == []

    def test_the_governed_arm_executes_fewer_calls_than_it_was_asked_for(
        self, contract, tmp_path, partial_case
    ) -> None:
        outcome = run_governed(partial_case, contract=contract, runs_dir=tmp_path)
        assert outcome.invoked < outcome.proposed
        assert outcome.withheld


class TestWhatTheGovernorIsAllowedToWithhold:
    """FR33: optimisation never touches a tool that moves money."""

    def test_the_repeat_is_real_before_anything_is_claimed_about_catching_it(
        self, partial_case
    ) -> None:
        # Without this the suppression count could be an artefact of a script
        # that happens to call one tool twice by accident.
        proposed = [
            invocation.tool
            for turn in partial_case.script
            if not isinstance(turn, str)
            for invocation in turn
        ]
        assert proposed.count("order_lookup") == 3

    def test_only_the_read_only_lookups_are_substituted(
        self, contract, tmp_path, partial_case
    ) -> None:
        outcome = run_governed(partial_case, contract=contract, runs_dir=tmp_path)
        assert outcome.withheld == ["order_lookup: cache-hit", "order_lookup: cache-hit"]

    def test_the_payment_is_never_cached_however_often_it_repeats(self, contract) -> None:
        from outcomefuse.ports import ToolCall
        from outcomefuse.runtime import ToolGovernor

        governor = ToolGovernor(contract)
        call = ToolCall(
            tool="issue_refund",
            arguments={"order_id": "ORD-4417", "amount": 1.0, "reason_code": "x"},
            step_id="s1",
        )
        governor.observe(call, {"posted": True})
        assert governor.optimisable("issue_refund") is False
        assert governor.optimisable("order_lookup") is True


class TestTheApprovalChannel:
    """The four things a human channel can do, and where each takes the run."""

    def test_approved_lets_the_money_move(self, contract, tmp_path, partial_case) -> None:
        outcome = run_governed(
            partial_case, contract=contract, runs_dir=tmp_path, approval="approved"
        )
        assert outcome.side_effects == ["issue_refund: ORD-4417 160.65 restocking-fee-applied"]

    def test_denied_stops_it_while_the_ungoverned_arm_pays_out(
        self, contract, tmp_path, partial_case
    ) -> None:
        governed = run_governed(
            partial_case, contract=contract, runs_dir=tmp_path, approval="denied"
        )
        ungoverned = run_ungoverned(partial_case, contract=contract, runs_dir=tmp_path)
        assert governed.side_effects == []
        assert ungoverned.side_effects != []
        # The refusal is not a failure of the run: the desk still adjudicated,
        # and a human now owns the payment.
        assert "issue_refund: approval-denied" in governed.withheld
        assert governed.passed

    def test_no_response_follows_the_contract_and_not_the_denial_path(
        self, contract, tmp_path, partial_case
    ) -> None:
        outcome = run_governed(
            partial_case, contract=contract, runs_dir=tmp_path, approval="no-response"
        )
        assert contract.on_timeout == "request-human"
        assert outcome.terminal == "approval-timeout"
        assert outcome.side_effects == []

    def test_an_unreachable_channel_is_fail_closed_not_a_denial(
        self, contract, tmp_path, partial_case
    ) -> None:
        outcome = run_governed(
            partial_case, contract=contract, runs_dir=tmp_path, approval="channel-unavailable"
        )
        assert outcome.terminal == "fail-closed"
        assert outcome.side_effects == []

    def test_the_deny_case_needs_no_approval_because_nothing_is_paid(
        self, contract, tmp_path
    ) -> None:
        outcome = run_governed(
            case_by_id("rd-003"), contract=contract, runs_dir=tmp_path, approval="denied"
        )
        assert outcome.side_effects == []
        assert outcome.passed


class TestBothRunsAreEvidence:
    def test_each_arm_seals_and_the_seals_differ(self, contract, tmp_path, partial_case) -> None:
        pair = adjudicate(partial_case, contract=contract, runs_dir=tmp_path)
        assert pair.ungoverned.seal and pair.governed.seal
        assert pair.ungoverned.seal != pair.governed.seal

    def test_the_governed_chain_verifies_after_the_fact(
        self, contract, tmp_path, partial_case
    ) -> None:
        run_governed(partial_case, contract=contract, runs_dir=tmp_path)
        store = open_store(tmp_path / "rd-001-governed.db", writer=False)
        try:
            assert store.verify_run("rd-001-governed")
            events = store.events("rd-001-governed")
        finally:
            store.close()
        assert events[0].kind == "run-manifest"
        assert events[-1].kind == "run-closed"

    def test_check_order_does_not_describe_what_the_driver_writes(
        self, contract, tmp_path, partial_case
    ) -> None:
        """A characterisation test, and the one finding this client turned up.

        `check_order` models a run as a repeating decision cycle. A real
        governed run is not only that, and every family below is the driver
        doing something correct that the cycle has no shape for. Asserting the
        findings are *empty* would be asserting a fiction; asserting they all
        fall into these four families means a genuinely new ordering fault still
        breaks the test.
        """
        run_governed(partial_case, contract=contract, runs_dir=tmp_path)
        store = open_store(tmp_path / "rd-001-governed.db", writer=False)
        try:
            findings = check_order(store.events("rd-001-governed"))
        finally:
            store.close()

        known = (
            # Nothing emits `verdict-applied`. Pre-existing since E7.
            "verdict-applied",
            # `bind_citable_index` and the deliverable sidecar observe evidence
            # nobody requested through a tool.
            "evidence-observed must follow evidence-requested",
            # A model turn is a spend, not a decision cycle: it reserves and
            # settles without proposing anything.
            "expected 'decision-proposed', got 'budget-reserved'",
            "expected 'decision-recorded', got 'spend-settled'",
            # A suppressed call reserves no budget, because it spends none.
            "expected 'budget-reserved', got 'decision-recorded'",
            # A terminal decision resolves a situation; there was no proposal.
            "expected 'decision-proposed', got 'decision-recorded'",
        )
        unexplained = [f for f in findings if not any(k in f for k in known)]
        assert unexplained == [], unexplained

    def test_the_substitution_is_in_the_log_not_only_in_the_return_value(
        self, contract, tmp_path, partial_case
    ) -> None:
        run_governed(partial_case, contract=contract, runs_dir=tmp_path)
        store = open_store(tmp_path / "rd-001-governed.db", writer=False)
        try:
            events = store.events("rd-001-governed")
        finally:
            store.close()
        substitutions = [e for e in events if e.policy_action == "proceed-with-substitution"]
        assert len(substitutions) == 2
        assert {e.decision_reason for e in substitutions} == {"cache-hit"}

    def test_the_deliverable_is_kept_where_a_reviewer_can_read_it(
        self, contract, tmp_path, partial_case
    ) -> None:
        run_governed(partial_case, contract=contract, runs_dir=tmp_path)
        written = tmp_path / "evidence" / "rd-001-governed" / "deliverable.json"
        assert written.is_file()
        parsed, failure = parse_deliverable(written.read_text(encoding="utf-8"))
        assert failure is None
        assert parsed is not None
        assert parsed["decision"] == "approve-partial"


class TestTheInstrument:
    """The loop's own parsing, tested so a silent `None` cannot look like a pass."""

    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("", "no text"),
            ("not json", "readable JSON"),
            ("[1, 2]", "expected an object"),
        ],
    )
    def test_an_unreadable_answer_is_a_value_not_an_exception(self, text, expected) -> None:
        parsed, failure = parse_deliverable(text)
        assert parsed is None
        assert failure is not None
        assert expected in failure

    def test_a_readable_answer_carries_no_failure(self) -> None:
        parsed, failure = parse_deliverable('{"decision": "deny"}')
        assert parsed == {"decision": "deny"}
        assert failure is None
