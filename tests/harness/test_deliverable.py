"""Reading the agent's final answer (E8, §8.1).

The property worth defending is that **nothing here repairs the model's
output**. Repair helps whichever arm produced the worse JSON, which is a thumb
on the scale in whichever direction happens to help — and the direction would
not be chosen, which makes it worse rather than better.

The second property is that a parse failure is *returned*. "The model emitted
prose" is a case the agent failed, not a case the harness crashed on, and the
difference decides whether the run is recorded or lost.
"""

from __future__ import annotations

import pytest

from outcomefuse.harness.deliverable import (
    MAX_TEXT,
    Parsed,
    Transcript,
    parse_deliverable,
)

ANSWER = '{"result_value": 30, "units": "count", "sql": "SELECT count(*) FROM orders"}'


class TestItReadsWhatModelsActuallyEmit:
    def test_a_bare_object(self):
        parsed = parse_deliverable(ANSWER)
        assert parsed.ok
        assert parsed.deliverable["result_value"] == 30
        assert parsed.found_by == "whole-response"

    def test_surrounding_whitespace(self):
        assert parse_deliverable(f"\n\n  {ANSWER}  \n").ok

    def test_a_fenced_block(self):
        parsed = parse_deliverable(f"```json\n{ANSWER}\n```")
        assert parsed.ok
        assert parsed.found_by == "fenced-block"

    def test_a_fenced_block_without_a_language(self):
        assert parse_deliverable(f"```\n{ANSWER}\n```").ok

    def test_an_object_buried_in_prose(self):
        parsed = parse_deliverable(f"Here is my answer.\n\n{ANSWER}\n\nLet me know!")
        assert parsed.ok
        assert parsed.found_by == "embedded-object"

    def test_braces_inside_strings_do_not_end_the_object(self):
        text = 'Sure: {"sql": "SELECT \'{}\' FROM t", "result_value": 1} done'
        parsed = parse_deliverable(text)
        assert parsed.ok
        assert parsed.deliverable["result_value"] == 1

    def test_an_unbalanced_brace_inside_a_string_is_not_counted(self):
        # A balanced pair inside a string still lands on the right span by
        # accident, so it proves nothing. This one only parses if the scanner
        # genuinely tracks string context.
        text = 'Sure: {"sql": "SELECT \'{\' FROM t", "result_value": 1} done'
        assert parse_deliverable(text).deliverable["result_value"] == 1

    def test_an_unbalanced_closing_brace_inside_a_string_is_not_counted(self):
        text = 'Answer: {"note": "close with }", "result_value": 2} done'
        assert parse_deliverable(text).deliverable["result_value"] == 2

    def test_an_escaped_quote_inside_a_string_is_handled(self):
        text = r'{"note": "he said \"no\"", "result_value": 2}'
        assert parse_deliverable(text).deliverable["result_value"] == 2

    def test_nested_objects_survive(self):
        parsed = parse_deliverable('{"a": {"b": {"c": 1}}, "result_value": 3}')
        assert parsed.deliverable["a"]["b"]["c"] == 1

    def test_the_strategy_that_found_it_is_recorded(self):
        # "The model fenced its JSON" and "the model buried it in prose" are
        # different behaviours, and the arms may differ in which they do.
        assert parse_deliverable(ANSWER).found_by == "whole-response"
        assert parse_deliverable(f"```json\n{ANSWER}\n```").found_by == "fenced-block"


class TestInsufficientEvidenceIsAVerdictNotAFailure:
    def test_it_parses_as_a_deliverable(self):
        parsed = parse_deliverable('{"insufficient_evidence": true, "missing": ["a rate"]}')
        assert parsed.ok
        assert parsed.claims_insufficient_evidence

    def test_an_ordinary_answer_does_not_claim_it(self):
        assert not parse_deliverable(ANSWER).claims_insufficient_evidence

    def test_a_false_flag_is_not_a_claim(self):
        parsed = parse_deliverable('{"insufficient_evidence": false, "result_value": 1}')
        assert not parsed.claims_insufficient_evidence


class TestNothingIsRepaired:
    def test_a_trailing_comma_is_not_forgiven(self):
        # json5 tolerance would be repair, and repair helps whichever arm
        # emitted the worse output.
        parsed = parse_deliverable('{"result_value": 30,}')
        assert not parsed.ok
        assert "not repaired" in parsed.failure

    def test_single_quotes_are_not_converted(self):
        assert not parse_deliverable("{'result_value': 30}").ok

    def test_an_unterminated_object_is_not_closed(self):
        assert not parse_deliverable('{"result_value": 30').ok

    def test_a_bare_number_is_not_promoted_to_a_field(self):
        # Guessing which field a scalar was meant to be is repair.
        assert not parse_deliverable("30").ok

    def test_an_array_is_not_reached_into(self):
        # The object inside is well formed, and taking it would override a
        # structural choice the model made. Stripping prose is not the same
        # thing: prose is noise, an array is an answer of the wrong shape.
        parsed = parse_deliverable('[{"result_value": 30}]')
        assert not parsed.ok
        assert "not the single object" in parsed.failure

    def test_a_fenced_array_is_refused_too(self):
        assert not parse_deliverable('```json\n[{"result_value": 30}]\n```').ok

    def test_prose_around_an_object_is_still_stripped(self):
        # The line is between noise and shape, not between tidy and untidy.
        assert parse_deliverable(f"Here you go: {ANSWER} — hope that helps").ok

    def test_prose_alone_fails(self):
        parsed = parse_deliverable("The answer is thirty orders.")
        assert not parsed.ok
        assert parsed.deliverable is None


class TestAFailureIsReturnedNotRaised:
    @pytest.mark.parametrize(
        "text", ["", "   ", "\n\n", "not json at all", '{"unterminated": ']
    )
    def test_nothing_raises(self, text):
        parsed = parse_deliverable(text)
        assert isinstance(parsed, Parsed)
        assert not parsed.ok
        assert parsed.failure

    def test_an_empty_response_says_so(self):
        assert parse_deliverable("").failure == "the model returned no text"

    def test_an_oversized_response_is_refused_by_size_not_parsed(self):
        parsed = parse_deliverable("{" + " " * (MAX_TEXT + 1))
        assert not parsed.ok
        assert "exceeds" in parsed.failure

    def test_the_failure_is_phrased_for_a_decision_record(self):
        # It ends up in a log, so it has to read as a reason rather than a
        # stack trace.
        failure = parse_deliverable("nope").failure
        assert failure and "\n" not in failure


class TestTheTranscript:
    def test_it_carries_everything_forward(self):
        # FR64's context policy: the whole working transcript, no compression
        # and no eviction. That is what the Context Governor exists to improve
        # on, so the baseline must actually do it.
        transcript = Transcript().with_entry("one").with_entry("two")
        assert transcript.rendered() == "one\n\ntwo"

    def test_it_is_immutable(self):
        first = Transcript().with_entry("one")
        first.with_entry("two")
        assert first.entries == ("one",)
