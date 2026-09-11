"""Answer keys and the evaluation seal (FR66, AD-7).

The seal is the only control here that cannot be repaired after it fails. Every
other mistake in this codebase can be found and fixed; a peek at the evaluation
answer keys cannot be unseen, leaves no trace, and quietly converts a
preregistered prediction into a postdiction. No later test can tell the
difference. So the seal is checked at the read, and these tests exist to make
sure the check is actually reachable.
"""

from __future__ import annotations

import pytest

from outcomefuse.harness.answer_keys import (
    AnswerKeyError,
    SealBroken,
    answer_key_for,
    load_answer_keys,
)

WORKLOADS = ("data-sql", "code-triage", "doc-research", "supply-chain")
A_HASH = "a" * 64


class TestTheSeal:
    @pytest.mark.parametrize("workload", WORKLOADS)
    def test_evaluation_is_closed_without_a_preregistration(self, workload):
        with pytest.raises(SealBroken, match="sealed until a preregistration"):
            load_answer_keys(workload, "evaluation")

    @pytest.mark.parametrize("workload", WORKLOADS)
    def test_calibration_is_open(self, workload):
        # The mirror. Without it, a seal that refused everything would pass the
        # test above and make the whole harness unusable.
        assert load_answer_keys(workload, "calibration")

    def test_an_empty_preregistration_is_not_a_preregistration(self):
        # `""` is what an unset environment variable or a missing CLI flag looks
        # like by the time it arrives here, and it is exactly the case that must
        # not squeak through.
        with pytest.raises(SealBroken):
            load_answer_keys("data-sql", "evaluation", preregistration_hash="")

    def test_evaluation_opens_once_a_preregistration_exists(self):
        assert load_answer_keys("data-sql", "evaluation", preregistration_hash=A_HASH)

    def test_the_seal_is_checked_before_the_file_is_touched(self):
        # Ordering matters: if the read came first, a debugging session against a
        # nonexistent workload would still have opened the real file for a
        # workload that did exist.
        with pytest.raises(SealBroken):
            load_answer_keys("no-such-workload", "evaluation")

    def test_the_single_case_path_is_sealed_too(self):
        # A second door into the same room. Sealing only the bulk loader would
        # leave this one open, and it is the one a runner actually calls.
        with pytest.raises(SealBroken):
            answer_key_for("ds-e-001", "data-sql", "evaluation")

    def test_seal_broken_is_its_own_type(self):
        # A caller that meant to handle "no keys here" must not swallow this.
        assert issubclass(SealBroken, AnswerKeyError)


class TestLoading:
    @pytest.mark.parametrize("workload", WORKLOADS)
    def test_every_calibration_case_has_a_key(self, workload):
        from outcomefuse.harness.cases import load_case_set

        keys = load_answer_keys(workload, "calibration")
        missing = [c.case_id for c in load_case_set(workload, "calibration").cases
                   if c.case_id not in keys]
        assert not missing

    def test_a_key_is_returned_whole(self):
        key = answer_key_for("ds-c-001", "data-sql", "calibration")
        assert key["expected_outcome"] == "answer"
        assert "result_value" in key

    def test_a_case_with_no_key_refuses_rather_than_returning_nothing(self):
        # Scoring against `{}` would pass anything, which is worse than failing.
        with pytest.raises(AnswerKeyError, match="no answer key"):
            answer_key_for("ds-c-999", "data-sql", "calibration")

    def test_a_missing_workload_refuses(self):
        with pytest.raises(AnswerKeyError, match="no answer keys at"):
            load_answer_keys("weather", "calibration")

    def test_the_unanswerable_cases_carry_a_key_that_says_so(self):
        # An unanswerable case must be scored on refusing, not on being absent
        # from the keys — absence is indistinguishable from an oversight.
        keys = load_answer_keys("doc-research", "calibration")
        assert {k["expected_outcome"] for k in keys.values()} == {"answer", "partial"}

    def test_the_keys_and_the_cases_agree_on_which_are_unanswerable(self):
        # Two files, written by different means, must not disagree about which
        # cases can be answered — the case file drives the prompt and the key
        # file drives the score.
        from outcomefuse.harness.cases import load_case_set

        for workload in WORKLOADS:
            keys = load_answer_keys(workload, "calibration")
            for case in load_case_set(workload, "calibration").cases:
                assert case.expected_outcome == keys[case.case_id]["expected_outcome"]

    def test_the_unanswerable_share_is_about_one_case_in_ten(self):
        # If this drifts to zero the benchmark quietly stops testing refusal,
        # which is the behaviour the whole sufficiency claim rests on.
        total = partial = 0
        for workload in WORKLOADS:
            for key in load_answer_keys(workload, "calibration").values():
                total += 1
                partial += key["expected_outcome"] == "partial"
        assert 0 < partial < total
        assert partial / total == pytest.approx(0.1, abs=0.05)
