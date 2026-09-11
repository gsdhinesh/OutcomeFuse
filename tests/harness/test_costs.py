"""The cost table (AD-13, FR79).

The one thing this must never do is price something at zero because nobody
filled the rates in. A zero rate produces a clean, arithmetically correct and
entirely false cost saving, and every check downstream agrees with it — the
sums add up, the proof card renders, the headline reads well, and the number
means nothing. So an unknown rate refuses.

Token savings are unaffected either way: they are counted, not priced.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from outcomefuse.harness.costs import (
    CostTable,
    CostTableError,
    Rate,
    Unpriced,
    load_cost_table,
)

SHIPPED = Path("cost-tables")


def a_table(tmp_path: Path, **over) -> Path:
    body = {
        "version": "ct-test",
        "currency": "USD",
        "per_tokens": 1_000_000,
        "rates": {"gpt-5": {"input": 1.25, "cached_input": 0.125, "output": 10.0}},
    }
    body.update(over)
    path = tmp_path / f"{body['version']}.yaml"
    path.write_text(yaml.safe_dump(body), encoding="utf-8")
    return path


class TestAnUnknownRateRefuses:
    def test_a_null_rate_is_not_a_free_one(self, tmp_path):
        a_table(tmp_path, rates={"gpt-5": {"input": None, "output": None}})
        table = load_cost_table("ct-test", root=tmp_path)
        with pytest.raises(Unpriced, match="no rate"):
            table.price("gpt-5", prompt_tokens=100, completion_tokens=50)

    def test_a_half_known_rate_still_refuses(self, tmp_path):
        # Pricing the input and dropping the output would under-report the
        # baseline, which is the arm that spends most of its tokens on output.
        a_table(tmp_path, rates={"gpt-5": {"input": 1.25, "output": None}})
        table = load_cost_table("ct-test", root=tmp_path)
        with pytest.raises(Unpriced):
            table.price("gpt-5", prompt_tokens=100, completion_tokens=50)

    def test_a_model_the_table_does_not_name_refuses(self, tmp_path):
        a_table(tmp_path)
        table = load_cost_table("ct-test", root=tmp_path)
        with pytest.raises(Unpriced, match="does not name"):
            table.price("gpt-4o", prompt_tokens=1, completion_tokens=1)

    def test_unpriced_is_its_own_type_a_caller_can_choose_to_survive(self):
        # A caller may reasonably report tokens only. It may not reasonably
        # mistake this for a zero, which a bare ValueError would invite.
        assert issubclass(Unpriced, CostTableError)

    def test_the_table_says_which_models_it_cannot_price(self, tmp_path):
        a_table(
            tmp_path,
            rates={
                "gpt-5": {"input": 1.25, "output": 10.0},
                "gpt-5-mini": {"input": None, "output": None},
            },
        )
        table = load_cost_table("ct-test", root=tmp_path)
        assert not table.priced
        assert table.unpriced_models() == ("gpt-5-mini",)


class TestPricing:
    @pytest.fixture
    def table(self, tmp_path):
        a_table(tmp_path)
        return load_cost_table("ct-test", root=tmp_path)

    def test_input_and_output_are_priced_at_their_own_rates(self, table):
        # 1M input at 1.25 and 1M output at 10.00.
        assert table.price(
            "gpt-5", prompt_tokens=1_000_000, completion_tokens=0
        ) == pytest.approx(1.25)
        assert table.price(
            "gpt-5", prompt_tokens=0, completion_tokens=1_000_000
        ) == pytest.approx(10.0)

    def test_the_two_directions_are_not_interchangeable(self, table):
        # The whole point of a directional table. A run that is mostly output
        # priced at the input rate would report an eighth of its real cost.
        assert table.price("gpt-5", prompt_tokens=1000, completion_tokens=0) != table.price(
            "gpt-5", prompt_tokens=0, completion_tokens=1000
        )

    def test_reasoning_tokens_are_priced_once_as_part_of_completion(self, table):
        # They are a subset of completion tokens, not an addition. Adding them
        # again would inflate the baseline, which reasons most, and manufacture
        # a saving out of double counting.
        measured_completion, of_which_reasoning = 75, 64
        assert table.price(
            "gpt-5", prompt_tokens=13, completion_tokens=measured_completion
        ) == pytest.approx(
            table.price(
                "gpt-5",
                prompt_tokens=13,
                completion_tokens=measured_completion - of_which_reasoning,
            )
            + table.price("gpt-5", prompt_tokens=0, completion_tokens=of_which_reasoning)
        )

    def test_nothing_costs_nothing(self, table):
        assert table.price("gpt-5", prompt_tokens=0, completion_tokens=0) == 0.0

    def test_negative_tokens_are_refused(self, table):
        with pytest.raises(CostTableError, match="negative"):
            table.price("gpt-5", prompt_tokens=-1, completion_tokens=0)


class TestLoading:
    def test_a_missing_table_refuses(self, tmp_path):
        with pytest.raises(CostTableError, match="no cost table"):
            load_cost_table("ct-nope", root=tmp_path)

    def test_a_table_that_disagrees_with_its_filename_refuses(self, tmp_path):
        path = a_table(tmp_path)
        path.rename(tmp_path / "ct-other.yaml")
        # The manifest records the version; the reader loads by filename. If
        # they disagree, one of them is lying about what priced the run.
        with pytest.raises(CostTableError, match="calls itself"):
            load_cost_table("ct-other", root=tmp_path)

    def test_unreadable_yaml_refuses(self, tmp_path):
        (tmp_path / "ct-bad.yaml").write_text("{[", encoding="utf-8")
        with pytest.raises(CostTableError, match="not readable YAML"):
            load_cost_table("ct-bad", root=tmp_path)

    def test_an_unexpected_field_refuses(self, tmp_path):
        a_table(tmp_path, discount=0.5)
        with pytest.raises(CostTableError, match="malformed"):
            load_cost_table("ct-test", root=tmp_path)

    def test_a_negative_rate_refuses(self, tmp_path):
        a_table(tmp_path, rates={"gpt-5": {"input": -1.0, "output": 10.0}})
        with pytest.raises(CostTableError, match="malformed"):
            load_cost_table("ct-test", root=tmp_path)


class TestTheShippedTables:
    def test_ct_1_loads(self):
        assert load_cost_table("ct-1").version == "ct-1"

    def test_ct_1_names_both_deployed_models(self):
        assert set(load_cost_table("ct-1").rates) == {"gpt-5", "gpt-5-mini"}

    def test_ct_1_is_still_unpriced_and_stays_that_way(self):
        # Runs exist whose manifests record `cost_table_version: ct-1`, and it
        # was unpriced when they ran. Filling it in now would change what that
        # recorded version means and silently re-price history — a cost table
        # version is a content identity, so ct-2 was added instead.
        table = load_cost_table("ct-1")
        assert not table.priced
        with pytest.raises(Unpriced):
            table.price("gpt-5", prompt_tokens=1, completion_tokens=1)

    def test_ct_2_is_priced(self):
        assert load_cost_table("ct-2").priced

    def test_ct_2_names_both_deployed_models(self):
        assert set(load_cost_table("ct-2").rates) == {"gpt-5", "gpt-5-mini"}

    def test_ct_2_records_where_and_when_the_rates_were_read(self):
        # A rate with no provenance is indistinguishable from a remembered one.
        table = load_cost_table("ct-2")
        assert table.source_read_at
        assert "azure.microsoft.com" in table.source

    def test_ct_2_says_which_deployment_sku_it_applies_to(self):
        # Global and Data Zone differ by ~10%. The SKU was read from the
        # resource rather than assumed, and the table has to say so or the next
        # reader cannot tell which column was used.
        assert "GlobalStandard" in load_cost_table("ct-2").source

    def test_mini_is_cheaper_than_gpt_5_on_both_directions(self):
        # The escalation ladder's entire premise. If this inverted, starting on
        # the smaller model would cost more by construction.
        table = load_cost_table("ct-2")
        assert table.rates["gpt-5-mini"].input < table.rates["gpt-5"].input
        assert table.rates["gpt-5-mini"].output < table.rates["gpt-5"].output

    def test_output_costs_more_than_input_on_both_models(self):
        # Reasoning bills at the output rate and was 64-79% of completion in the
        # live runs, so an inverted table would badly misprice the baseline.
        table = load_cost_table("ct-2")
        for rate in table.rates.values():
            assert rate.output > rate.input


class TestTheModel:
    def test_a_rate_missing_only_its_cache_price_is_still_usable(self):
        # Prompt caching is a discount we do not claim. A table without it is
        # complete for our purposes.
        assert Rate(input=1.25, output=10.0).known

    def test_a_table_with_no_models_is_not_priced(self):
        assert not CostTable(
            version="v", currency="USD", per_tokens=1000, rates={}
        ).priced
