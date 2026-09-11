"""Which mechanism produced the saving (FR62).

The breakdown exists to answer one question a reader will otherwise ask and be
unable to: did the governed arm get cheaper by governing, or by running a
smaller model? A figure without that split is not falsifiable.

The property that makes the split computable rather than guessed is that **model
routing saves cost and, by construction, zero tokens** — a token is a token
whichever model emits it. So the two decompose differently, and most of these
tests exist to hold that asymmetry in place.
"""

from __future__ import annotations

import pytest

from outcomefuse.harness.attribution import (
    AGENT_STOPPED,
    ROUTING,
    UNATTRIBUTED,
    CaseSaving,
    attribute_cost,
    attribute_tokens,
)


def a_case(**over) -> CaseSaving:
    base = {
        "case_id": "c1",
        "baseline_tokens": 1000,
        "governed_tokens": 600,
        "baseline_cost": 0.010,
        "governed_cost": 0.002,
        "governed_cost_at_baseline_rates": 0.006,
        "terminal_reason": "stop-sufficient",
        "cut_short": True,
    }
    return CaseSaving(**(base | over))


class TestAMechanismIsCreditedOnlyIfItShortenedTheRun:
    # The most important rule here. Measured live, the quality gate fires at
    # event 21 of 24 — after the agent has already stopped asking for tools. On
    # such a run `stop-sufficient` confirms a result rather than causing one,
    # and crediting it would manufacture the product's central claim out of an
    # accounting choice.

    def test_a_run_the_agent_finished_credits_no_mechanism(self):
        assert attribute_tokens([a_case(cut_short=False)]) == {AGENT_STOPPED: 1.0}

    def test_the_same_run_cut_short_does_credit_the_mechanism(self):
        # The pair that makes the rule above load-bearing rather than a blanket
        # refusal to credit anything.
        assert attribute_tokens([a_case(cut_short=True)]) == {"quality-gate": 1.0}

    def test_cut_short_defaults_to_false(self):
        # A caller that forgets to say gets the conservative answer, not the
        # flattering one.
        assert not CaseSaving(
            case_id="c",
            baseline_tokens=1,
            governed_tokens=0,
            baseline_cost=0,
            governed_cost=0,
            governed_cost_at_baseline_rates=0,
        ).cut_short

    def test_a_mixed_campaign_splits_between_the_two(self):
        shares = attribute_tokens(
            [
                a_case(case_id="a", baseline_tokens=1000, governed_tokens=500),
                a_case(
                    case_id="b",
                    baseline_tokens=1000,
                    governed_tokens=500,
                    cut_short=False,
                ),
            ]
        )
        assert shares == {AGENT_STOPPED: 0.5, "quality-gate": 0.5}


class TestTokensAreCreditedToWhatStoppedTheRun:
    def test_a_sufficiency_stop_credits_the_gate(self):
        assert attribute_tokens([a_case()]) == {"quality-gate": 1.0}

    def test_a_stalled_run_credits_the_fuse(self):
        assert attribute_tokens([a_case(terminal_reason="halt-no-progress")]) == {
            "loop-fuse": 1.0
        }

    def test_an_exhausted_run_credits_the_ledger(self):
        assert attribute_tokens([a_case(terminal_reason="halt-exhausted")]) == {
            "budget-ledger": 1.0
        }

    def test_two_mechanisms_split_by_how_much_each_saved(self):
        shares = attribute_tokens(
            [
                a_case(case_id="a", baseline_tokens=1000, governed_tokens=700),
                a_case(
                    case_id="b",
                    baseline_tokens=1000,
                    governed_tokens=900,
                    terminal_reason="halt-no-progress",
                ),
            ]
        )
        assert shares == {"quality-gate": 0.75, "loop-fuse": 0.25}

    def test_an_unknown_terminal_reason_is_not_quietly_credited(self):
        # `fail-closed` is a fault and `approval-timeout` is a human waiting.
        # Folding either into a mechanism would credit it with a saving it did
        # not produce.
        assert attribute_tokens([a_case(terminal_reason="fail-closed")]) == {
            UNATTRIBUTED: 1.0
        }

    def test_a_run_that_never_terminated_is_not_credited(self):
        assert attribute_tokens([a_case(terminal_reason=None)]) == {UNATTRIBUTED: 1.0}

    def test_routing_never_appears_in_the_token_split(self):
        # The whole asymmetry: a cheaper model emits the same number of tokens.
        assert ROUTING not in attribute_tokens([a_case()])


class TestTheCostSplitIsArithmeticNotAGuess:
    def test_routing_is_the_difference_between_the_two_rates(self):
        # governed cost 0.002, repriced at the baseline's model 0.006, so 0.004
        # of the 0.008 saved is routing and 0.004 is the token reduction.
        assert attribute_cost([a_case()]) == {ROUTING: 0.5, "quality-gate": 0.5}

    def test_same_model_on_both_arms_means_no_routing_term(self):
        # Repricing is then the identity, so every penny saved came from tokens.
        shares = attribute_cost([a_case(governed_cost_at_baseline_rates=0.002)])
        assert shares == {"quality-gate": 1.0}
        assert ROUTING not in shares

    def test_a_cheaper_model_that_saved_no_tokens_is_all_routing(self):
        shares = attribute_cost(
            [
                a_case(
                    baseline_tokens=1000,
                    governed_tokens=1000,
                    baseline_cost=0.010,
                    governed_cost=0.002,
                    governed_cost_at_baseline_rates=0.010,
                )
            ]
        )
        assert shares == {ROUTING: 1.0}

    def test_a_governed_arm_that_spent_more_carries_a_negative_share(self):
        # Measured on data-sql: gpt-5-mini floundered and used more. A share
        # clamped at zero would hide the arm losing.
        shares = attribute_cost(
            [
                a_case(
                    baseline_cost=0.010,
                    governed_cost=0.004,
                    governed_cost_at_baseline_rates=0.012,
                )
            ]
        )
        assert shares["quality-gate"] < 0
        assert shares[ROUTING] > 1


class TestSharesAreUsableByTheProofCard:
    def test_shares_sum_to_exactly_one(self):
        # The proof card refuses a set that does not, and three-way rounding
        # will not on its own.
        for shares in (
            attribute_cost([a_case()]),
            attribute_tokens(
                [
                    a_case(case_id="a", governed_tokens=667),
                    a_case(case_id="b", governed_tokens=333, terminal_reason="halt-no-progress"),
                    a_case(case_id="c", governed_tokens=501, terminal_reason="halt-exhausted"),
                ]
            ),
        ):
            assert sum(shares.values()) == pytest.approx(1.0, abs=1e-9)

    def test_no_saving_at_all_yields_no_breakdown(self):
        # An empty dict rather than a fabricated one: the proof card treats
        # empty as "no breakdown", and FR62 then refuses the headline.
        assert attribute_tokens([a_case(governed_tokens=1000)]) == {}

    def test_no_cases_yields_no_breakdown(self):
        assert attribute_tokens([]) == {}
        assert attribute_cost([]) == {}

    def test_a_mechanism_that_saved_nothing_is_omitted(self):
        shares = attribute_tokens(
            [
                a_case(case_id="a", baseline_tokens=1000, governed_tokens=500),
                a_case(
                    case_id="b",
                    baseline_tokens=500,
                    governed_tokens=500,
                    terminal_reason="halt-no-progress",
                ),
            ]
        )
        assert shares == {"quality-gate": 1.0}
