"""The feature report, under test.

A report that quietly stopped demonstrating a feature would still render, still
look complete, and still be wrong. These are what make that fail instead:

- every scenario in the catalogue must produce its evidence, so a mechanism that
  breaks turns a row from `demonstrated` into `not-demonstrated` and turns this
  suite red;
- the two rows that are *not* successes are pinned by key, so the known gap and
  the known defect cannot be quietly dropped or quietly renamed;
- the measured section must stay separable from the demonstrated one, because
  the whole point of the report is that they disagree.

They run against the frozen supply-chain workload, the same as the report does.
"""

from __future__ import annotations

import pytest
from features import agents, compose, measured
from features.catalogue import CATALOGUE, DEFECT, DEMONSTRATED, GAP, MISSING, Context, run_all
from features.report import render

from outcomefuse.core.contract import ContractError


@pytest.fixture(scope="module")
def findings(tmp_path_factory):
    return run_all(tmp_path_factory.mktemp("features"))


class TestTheCatalogue:
    def test_every_scenario_produces_its_evidence(self, findings) -> None:
        missing = [f.key for f in findings if f.status == MISSING]
        assert missing == [], missing

    def test_every_finding_carries_evidence_and_a_claim(self, findings) -> None:
        for finding in findings:
            assert finding.evidence, finding.key
            assert finding.claim, finding.key

    def test_the_catalogue_and_the_findings_are_the_same_length(self, findings) -> None:
        assert len(findings) == len(CATALOGUE)

    def test_keys_are_unique(self, findings) -> None:
        keys = [f.key for f in findings]
        assert len(keys) == len(set(keys))


class TestTheRowsThatAreNotSuccesses:
    """Pinned by key. A gap that disappears is either fixed or hidden."""

    def test_the_declared_but_dead_clauses_are_still_reported(self, findings) -> None:
        # Both are the same shape: the contract states it, the loader validates
        # it, and no code path reads it. Pinned by key, because a gap that
        # disappears is either fixed or hidden and the two look identical here.
        gaps = {f.key for f in findings if f.status == GAP}
        assert gaps == {"criterion-approval", "tool-call-ceiling"}, gaps

    def test_the_unknown_tool_defect_is_still_reported(self, findings) -> None:
        defects = {f.key for f in findings if f.status == DEFECT}
        assert defects == {"unknown-tool"}, defects

    def test_the_defect_row_says_the_governed_arm_did_worse(self, findings) -> None:
        row = next(f for f in findings if f.key == "unknown-tool")
        facts = dict(row.evidence)
        assert facts["governed terminal"] == "fail-closed"
        assert facts["ungoverned answered"] == "pass"


class TestScenariosAssertRatherThanAssume:
    """The instrument, checked against a planted failure."""

    def test_a_broken_mechanism_reports_not_demonstrated(self, tmp_path, monkeypatch) -> None:
        # Planted: the agent drops a mandatory field. The gate scenario must
        # report the failure rather than report the feature works because it
        # always has. Mutating the answer key would not do it — the deliverable is
        # built from the key, so both sides would move together and still agree.
        import features.catalogue as catalogue

        def incomplete(ctx):
            body = dict(_intact(ctx))
            body.pop("est_delay_days")
            return body

        _intact = catalogue._deliverable
        monkeypatch.setattr(catalogue, "_deliverable", incomplete)
        assert catalogue.quality_gate(Context(runs_dir=tmp_path)).status == MISSING

    def test_the_runner_catches_a_scenario_that_raises(self, tmp_path, monkeypatch) -> None:
        import features.catalogue as catalogue

        def explodes(_ctx):
            raise ValueError("planted")

        monkeypatch.setattr(catalogue, "CATALOGUE", (explodes,))
        result = catalogue.run_all(tmp_path)
        assert result[0].status == MISSING
        assert "planted" in result[0].evidence[0][1]


class TestItRunsTheFrozenWorkload:
    def test_the_contract_is_the_frozen_one(self) -> None:
        spec = compose.contract()
        assert spec.contract_id == "ofc-supply-chain"
        assert spec.workload == "supply-chain"

    def test_the_answer_key_is_derived_not_authored_here(self) -> None:
        key = compose.key_for("sc-c-001")
        assert key["exception_type"] == "quality-hold"
        assert key["recommended_action"] == "hold-for-quality"

    def test_a_variant_is_validated_like_a_contract(self) -> None:
        small = compose.variant(lambda raw: raw["budget"].update(max_tokens=2_000))
        assert small.budget.max_tokens == 2_000
        assert small.digest() != compose.contract().digest()
        with pytest.raises(ContractError):
            compose.variant(lambda raw: raw["criteria"]["mandatory"][0].pop("verifier"))

    def test_both_arms_reach_the_same_answer_on_the_happy_path(self, tmp_path) -> None:
        case = compose.case("sc-c-001")
        key = compose.key_for(case.case_id)
        po = int(case.prompt_context["po_id"])
        turns = agents.correct(key, po)
        governed = compose.governed(case, turns=turns, runs_dir=tmp_path)
        plain = compose.ungoverned(case, turns=turns, runs_dir=tmp_path)
        assert governed.quality_state == plain.quality_state == "pass"
        assert governed.verified and plain.verified
        assert governed.seal != plain.seal


class TestTheMeasuredHalf:
    def test_a_missing_campaign_is_reported_not_zeroed(self, tmp_path) -> None:
        stats = measured.read_campaign(tmp_path / "nothing")
        assert not stats.available
        assert "does not exist" in measured.rows(stats, {})[0][1]
        assert "nothing here is measured" in measured.verdict(stats)

    def test_a_quiet_mechanism_is_named_rather_than_averaged(self) -> None:
        quiet = measured.Measured(runs=10, tool_calls=100)
        assert "never fired at all" in measured.verdict(quiet)
        assert "the loop fuse" in measured.verdict(quiet)

    def test_the_repeat_rate_carries_its_denominator(self) -> None:
        assert measured.Measured(tool_calls=282, repeated_calls=1).repeat_rate == (
            "1 in 282 proposed calls"
        )
        assert "no tool calls" in measured.Measured().repeat_rate


class TestThePage:
    def test_it_renders_every_finding_and_labels_the_exceptions(self, findings) -> None:
        page = render(findings, measured.Measured(runs=1, tool_calls=1), {}, None)
        for finding in findings:
            assert finding.title in page or finding.title.replace("'", "&#x27;") in page
        assert "DEFECT" in page
        assert "GAP" in page

    def test_the_page_says_the_two_halves_disagree(self, findings) -> None:
        page = render(findings, measured.Measured(runs=1, tool_calls=1), {}, None)
        assert "mechanism-level" in page
        assert "authored" in page
        assert "variant" in page

    def test_a_demonstrated_run_is_not_silently_a_mechanism_check(self, findings) -> None:
        # Mechanism-level rows prove less than run-level ones, so the split has to
        # stay honest: most of the catalogue must still be driven through a run.
        levels = [f.level for f in findings if f.status == DEMONSTRATED]
        assert levels.count("run") > levels.count("mechanism")
