"""The closed verifier registry (AD-7).

FR108 requires positive, negative, boundary, malformed-input and replay tests
for every verifier type. The registry is frozen at E1b alongside the rubric, so
a verifier that is wrong here is wrong permanently.
"""

from __future__ import annotations

from typing import Any, ClassVar

import pytest
from pydantic import ValidationError

from outcomefuse.core.verify import (
    REGISTRY,
    CitableEntry,
    CitableIndex,
    PathError,
    VerifierError,
    build_args,
    mode_for,
    registry_digest,
    verify,
)

SHA = "a" * 64


def index(*ids: str) -> CitableIndex:
    return CitableIndex(
        entries=tuple(CitableEntry(id=i, target=f"t/{i}", sha256=SHA) for i in ids)
    )


class TestRegistryShape:
    def test_the_registry_holds_exactly_the_seven_declared_types(self):
        assert set(REGISTRY) == {
            "field-present",
            "type-is",
            "numeric-range",
            "set-membership",
            "regex-match",
            "exact-match-against-answer-key",
            "citation-resolves",
        }

    @pytest.mark.parametrize(
        ("verifier_type", "expected"),
        [
            ("field-present", "constraint-backed"),
            ("type-is", "constraint-backed"),
            ("numeric-range", "constraint-backed"),
            ("set-membership", "constraint-backed"),
            ("regex-match", "constraint-backed"),
            ("exact-match-against-answer-key", "reference-backed"),
            ("citation-resolves", "reference-backed"),
        ],
    )
    def test_mode_is_fixed_by_type(self, verifier_type, expected):
        assert mode_for(verifier_type) == expected

    def test_an_unregistered_type_has_no_mode(self):
        with pytest.raises(VerifierError, match="unregistered"):
            mode_for("llm-judge")

    def test_an_unregistered_type_cannot_be_run(self):
        with pytest.raises(VerifierError, match="unregistered"):
            verify("semantic-match", {"path": "$.a"}, {"a": 1})

    def test_the_registry_digest_is_stable_across_calls(self):
        assert registry_digest().sha256 == registry_digest().sha256


class TestFieldPresent:
    @pytest.mark.parametrize("value", [1, "x", ["a"], {"k": 1}, 0, False])
    def test_a_present_value_passes(self, value):
        assert verify("field-present", {"path": "$.a"}, {"a": value}).passed

    @pytest.mark.parametrize("deliverable", [{}, {"b": 1}])
    def test_an_absent_field_fails(self, deliverable):
        assert not verify("field-present", {"path": "$.a"}, deliverable).passed

    @pytest.mark.parametrize("value", [None, "", [], {}])
    def test_an_empty_value_is_not_presence(self, value):
        # A contract asking for evidence is not satisfied by an empty list.
        assert not verify("field-present", {"path": "$.a"}, {"a": value}).passed


class TestTypeIs:
    @pytest.mark.parametrize(
        ("declared", "value"),
        [
            ("string", "x"),
            ("number", 1),
            ("number", 1.5),
            ("integer", 3),
            ("boolean", True),
            ("array", []),
            ("object", {}),
        ],
    )
    def test_matching_types_pass(self, declared, value):
        assert verify("type-is", {"path": "$.a", "type": declared}, {"a": value}).passed

    @pytest.mark.parametrize("declared", ["number", "integer"])
    def test_a_boolean_is_not_a_number(self, declared):
        # bool subclasses int in Python; no contract means that when it says integer.
        assert not verify("type-is", {"path": "$.a", "type": declared}, {"a": True}).passed

    def test_a_float_is_not_an_integer(self):
        assert not verify("type-is", {"path": "$.a", "type": "integer"}, {"a": 1.5}).passed

    def test_an_undeclared_type_is_refused_at_build(self):
        with pytest.raises(ValidationError, match="type"):
            build_args("type-is", {"path": "$.a", "type": "decimal"})


class TestNumericRange:
    @pytest.mark.parametrize("value", [1, 5, 10])
    def test_values_inside_the_range_pass_including_both_ends(self, value):
        assert verify("numeric-range", {"path": "$.a", "min": 1, "max": 10}, {"a": value}).passed

    @pytest.mark.parametrize("value", [0, 11])
    def test_values_outside_the_range_fail(self, value):
        assert not verify(
            "numeric-range", {"path": "$.a", "min": 1, "max": 10}, {"a": value}
        ).passed

    def test_distinct_count_counts_distinct_members(self):
        args = {"path": "$.a", "of": "distinct-count", "min": 2, "max": 2}
        assert verify("numeric-range", args, {"a": ["x", "x", "y"]}).passed

    def test_distinct_count_survives_dict_members(self):
        args = {"path": "$.a", "of": "distinct-count", "min": 1, "max": 1}
        assert verify("numeric-range", args, {"a": [{"id": "x"}, {"id": "x"}]}).passed

    def test_bounds_may_come_from_the_answer_key(self):
        args = {"path": "$.a", "min_from_key": "lo", "max_from_key": "hi"}
        outcome = verify("numeric-range", args, {"a": 7}, answer_key={"lo": 5, "hi": 9})
        assert outcome.passed

    def test_a_bound_naming_a_missing_key_cannot_run(self):
        args = {"path": "$.a", "min_from_key": "lo"}
        with pytest.raises(VerifierError, match="absent from the answer key"):
            verify("numeric-range", args, {"a": 7}, answer_key={})

    def test_a_range_with_no_bound_is_refused_at_build(self):
        with pytest.raises(ValidationError, match="at least one bound"):
            build_args("numeric-range", {"path": "$.a"})

    def test_an_inverted_range_is_refused_at_build(self):
        with pytest.raises(ValidationError, match="exceeds max"):
            build_args("numeric-range", {"path": "$.a", "min": 10, "max": 1})

    def test_a_non_numeric_value_fails_rather_than_raising(self):
        assert not verify("numeric-range", {"path": "$.a", "min": 1}, {"a": "seven"}).passed

    def test_counting_a_non_array_fails_rather_than_raising(self):
        args = {"path": "$.a", "of": "distinct-count", "min": 1}
        assert not verify("numeric-range", args, {"a": "xyz"}).passed


class TestSetMembership:
    def test_a_permitted_value_passes(self):
        assert verify("set-membership", {"path": "$.a", "allowed": ["x", "y"]}, {"a": "x"}).passed

    def test_a_value_outside_the_set_fails(self):
        assert not verify(
            "set-membership", {"path": "$.a", "allowed": ["x"]}, {"a": "z"}
        ).passed

    def test_an_empty_permitted_set_is_refused_at_build(self):
        # Nothing could ever pass, so the contract is unsatisfiable as written.
        with pytest.raises(ValidationError, match="at least 1"):
            build_args("set-membership", {"path": "$.a", "allowed": []})


class TestRegexMatch:
    ARGS: ClassVar[dict[str, Any]] = {"path": "$.a", "pattern": "^ok", "max_input_bytes": 64}

    def test_a_matching_string_passes(self):
        assert verify("regex-match", self.ARGS, {"a": "okay"}).passed

    def test_a_non_matching_string_fails(self):
        assert not verify("regex-match", self.ARGS, {"a": "nope"}).passed

    def test_input_at_the_declared_limit_is_accepted(self):
        args = {"path": "$.a", "pattern": "^o", "max_input_bytes": 4}
        assert verify("regex-match", args, {"a": "oooo"}).passed

    def test_input_over_the_declared_limit_fails_without_running_the_pattern(self):
        args = {"path": "$.a", "pattern": "^o", "max_input_bytes": 4}
        outcome = verify("regex-match", args, {"a": "ooooo"})
        assert not outcome.passed and "over the declared" in outcome.detail

    def test_the_limit_is_measured_in_bytes_not_characters(self):
        args = {"path": "$.a", "pattern": ".", "max_input_bytes": 3}
        assert not verify("regex-match", args, {"a": "\u00e9\u00e9"}).passed

    def test_a_non_string_fails_rather_than_raising(self):
        assert not verify("regex-match", self.ARGS, {"a": 5}).passed

    def test_an_uncompilable_pattern_is_refused_at_build(self):
        with pytest.raises(ValidationError, match="does not compile"):
            build_args("regex-match", {"path": "$.a", "pattern": "(", "max_input_bytes": 8})

    def test_an_unbounded_input_cap_is_refused_at_build(self):
        with pytest.raises(ValidationError):
            build_args("regex-match", {"path": "$.a", "pattern": "x", "max_input_bytes": 1 << 30})


class TestExactMatchAgainstAnswerKey:
    def test_an_equal_value_passes(self):
        outcome = verify(
            "exact-match-against-answer-key",
            {"path": "$.a", "key": "a"},
            {"a": "usd"},
            answer_key={"a": "usd"},
        )
        assert outcome.passed and outcome.mode == "reference-backed"

    def test_a_different_value_fails(self):
        assert not verify(
            "exact-match-against-answer-key",
            {"path": "$.a", "key": "a"},
            {"a": "count"},
            answer_key={"a": "usd"},
        ).passed

    def test_an_integer_equals_the_same_value_as_a_float(self):
        assert verify(
            "exact-match-against-answer-key",
            {"path": "$.a", "key": "a"},
            {"a": 17046},
            answer_key={"a": 17046.0},
        ).passed

    @pytest.mark.parametrize(("value", "expected"), [(True, 1), (1, True), (False, 0)])
    def test_a_boolean_never_equals_a_number(self, value, expected):
        # True == 1 in Python. A reference-backed pass may not rest on that.
        assert not verify(
            "exact-match-against-answer-key",
            {"path": "$.a", "key": "a"},
            {"a": value},
            answer_key={"a": expected},
        ).passed

    def test_without_an_answer_key_it_cannot_run(self):
        with pytest.raises(VerifierError, match="needs an answer key"):
            verify("exact-match-against-answer-key", {"path": "$.a", "key": "a"}, {"a": 1})

    def test_a_key_absent_from_the_answer_key_cannot_run(self):
        with pytest.raises(VerifierError, match="no entry"):
            verify(
                "exact-match-against-answer-key",
                {"path": "$.a", "key": "missing"},
                {"a": 1},
                answer_key={"a": 1},
            )

    def test_an_absent_deliverable_field_fails_rather_than_raising(self):
        assert not verify(
            "exact-match-against-answer-key",
            {"path": "$.a", "key": "a"},
            {},
            answer_key={"a": 1},
        ).passed


class TestCitationResolves:
    ARGS: ClassVar[dict[str, Any]] = {"path": "$.citations[*].id"}

    def test_resolvable_citations_pass(self):
        deliverable = {"citations": [{"id": "doc-1"}, {"id": "doc-2"}]}
        assert verify(
            "citation-resolves", self.ARGS, deliverable, citable_index=index("doc-1", "doc-2")
        ).passed

    def test_an_unresolvable_citation_fails_and_is_named(self):
        deliverable = {"citations": [{"id": "doc-1"}, {"id": "ghost"}]}
        outcome = verify(
            "citation-resolves", self.ARGS, deliverable, citable_index=index("doc-1")
        )
        assert not outcome.passed and "ghost" in outcome.detail

    def test_no_citations_fails_the_default_minimum(self):
        assert not verify(
            "citation-resolves", self.ARGS, {"citations": []}, citable_index=index("doc-1")
        ).passed

    def test_the_verifier_never_fetches_its_own_index(self):
        # AD-7: the index is an argument supplied by the caller, never a lookup.
        with pytest.raises(VerifierError, match="needs the citable index"):
            verify("citation-resolves", self.ARGS, {"citations": [{"id": "doc-1"}]})

    def test_an_empty_index_resolves_nothing(self):
        assert not verify(
            "citation-resolves",
            self.ARGS,
            {"citations": [{"id": "doc-1"}]},
            citable_index=CitableIndex(),
        ).passed


class TestPurityAndReplay:
    """AD-7: a verifier is a pure function of its declared arguments."""

    CASES: ClassVar[list[Any]] = [
        ("field-present", {"path": "$.a"}, {"a": 1}, {}, None),
        ("type-is", {"path": "$.a", "type": "string"}, {"a": "x"}, {}, None),
        ("numeric-range", {"path": "$.a", "min": 0, "max": 9}, {"a": 4}, {}, None),
        ("set-membership", {"path": "$.a", "allowed": ["x"]}, {"a": "x"}, {}, None),
        (
            "regex-match",
            {"path": "$.a", "pattern": "x", "max_input_bytes": 8},
            {"a": "x"},
            {},
            None,
        ),
        (
            "exact-match-against-answer-key",
            {"path": "$.a", "key": "a"},
            {"a": 2},
            {"a": 2},
            None,
        ),
        (
            "citation-resolves",
            {"path": "$.c[*].id"},
            {"c": [{"id": "doc-1"}]},
            {},
            index("doc-1"),
        ),
    ]

    @pytest.mark.parametrize(("kind", "args", "deliverable", "key", "idx"), CASES)
    def test_repeated_invocation_returns_an_identical_outcome(
        self, kind, args, deliverable, key, idx
    ):
        first = verify(kind, args, deliverable, answer_key=key, citable_index=idx)
        second = verify(kind, args, deliverable, answer_key=key, citable_index=idx)
        assert first == second

    @pytest.mark.parametrize(("kind", "args", "deliverable", "key", "idx"), CASES)
    def test_a_verifier_does_not_mutate_what_it_is_given(
        self, kind, args, deliverable, key, idx
    ):
        before = (dict(deliverable), dict(key), dict(args))
        verify(kind, args, deliverable, answer_key=key, citable_index=idx)
        assert (deliverable, key, args) == before

    @pytest.mark.parametrize(("kind", "args", "deliverable", "key", "idx"), CASES)
    def test_every_outcome_carries_the_mode_the_registry_fixes(
        self, kind, args, deliverable, key, idx
    ):
        outcome = verify(kind, args, deliverable, answer_key=key, citable_index=idx)
        assert outcome.mode == mode_for(kind)


class TestMalformedArguments:
    @pytest.mark.parametrize("kind", sorted(REGISTRY))
    def test_no_verifier_accepts_an_undeclared_argument(self, kind):
        args = {"path": "$.a", "sneaky": "import os"}
        with pytest.raises(ValidationError, match=r"[Ee]xtra"):
            build_args(kind, args)

    @pytest.mark.parametrize("kind", sorted(REGISTRY))
    def test_no_verifier_accepts_a_malformed_path(self, kind):
        with pytest.raises((ValidationError, VerifierError, PathError)):
            build_args(kind, {"path": "a.b", "type": "string", "key": "k", "allowed": ["x"]})

    @pytest.mark.parametrize("kind", sorted(set(REGISTRY) - {"citation-resolves"}))
    def test_only_citation_resolves_accepts_a_wildcard_path(self, kind):
        args = {
            "path": "$.a[*].id",
            "type": "string",
            "key": "k",
            "allowed": ["x"],
            "pattern": "x",
            "max_input_bytes": 8,
            "min": 0,
        }
        accepted = {f for f in args if f in REGISTRY[kind].args_model.model_fields}
        with pytest.raises(VerifierError, match="wildcard"):
            build_args(kind, {f: args[f] for f in accepted})
