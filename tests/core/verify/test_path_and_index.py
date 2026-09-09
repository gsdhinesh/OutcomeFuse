"""The closed path grammar and the pinned citable index (AD-7)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from outcomefuse.core.verify import (
    MISSING,
    CitableEntry,
    CitableIndex,
    PathError,
    has_wildcard,
    root_field,
    select,
    select_one,
)
from outcomefuse.core.verify.path import MAX_SEGMENTS

SHA = "b" * 64


class TestPathGrammar:
    @pytest.mark.parametrize("path", ["$.a", "$.a.b", "$.a[*].b", "$.a_b", "$.a-b"])
    def test_paths_in_the_grammar_parse(self, path):
        assert root_field(path) == "a" or root_field(path) == "a_b" or root_field(path) == "a-b"

    @pytest.mark.parametrize(
        "path",
        [
            "a.b",                    # no root
            "$",                      # selects everything
            "$.a[0]",                 # indexing is not in the grammar
            "$..a",                   # recursive descent
            "$.a[?(@.b)]",            # filter expression
            "$.a[*][*]",              # two wildcards
            "$.1a",                   # not an identifier
            "$.a b",
        ],
    )
    def test_paths_outside_the_grammar_are_refused(self, path):
        with pytest.raises(PathError):
            select({"a": 1}, path)

    def test_a_path_deeper_than_the_limit_is_refused(self):
        with pytest.raises(PathError, match="segments"):
            select({}, "$" + ".a" * (MAX_SEGMENTS + 1))

    def test_a_non_string_path_is_refused(self):
        with pytest.raises(PathError, match="must be a string"):
            select({}, 5)

    def test_has_wildcard_reports_the_grammar_accurately(self):
        assert has_wildcard("$.a[*].b")
        assert not has_wildcard("$.a.b")


class TestSelection:
    def test_a_single_valued_path_returns_one_match(self):
        assert select_one({"a": {"b": 7}}, "$.a.b") == 7

    def test_an_absent_field_is_missing_not_none(self):
        # `field-present` must tell these apart; None alone cannot.
        assert select_one({}, "$.a") is MISSING
        assert select_one({"a": None}, "$.a") is None

    def test_missing_is_falsey_and_a_singleton(self):
        assert not MISSING
        assert select_one({}, "$.a") is select_one({"b": 1}, "$.c")

    def test_a_wildcard_fans_out_over_a_list(self):
        document = {"c": [{"id": "x"}, {"id": "y"}]}
        assert select(document, "$.c[*].id") == ["x", "y"]

    def test_a_wildcard_over_a_non_list_selects_nothing(self):
        assert select({"c": "xy"}, "$.c[*].id") == []

    def test_a_wildcard_skips_members_lacking_the_field(self):
        document = {"c": [{"id": "x"}, {"other": 1}]}
        assert select(document, "$.c[*].id") == ["x"]

    def test_descending_through_a_scalar_selects_nothing(self):
        assert select({"a": 5}, "$.a.b") == []

    def test_a_multi_valued_path_refuses_single_valued_resolution(self):
        with pytest.raises(PathError, match="single-valued"):
            select_one({"c": [{"id": "x"}, {"id": "y"}]}, "$.c[*].id")


class TestCitableIndex:
    def test_membership_is_by_identifier(self):
        idx = CitableIndex(entries=(CitableEntry(id="doc-1", target="t", sha256=SHA),))
        assert "doc-1" in idx
        assert "doc-2" not in idx

    def test_a_non_string_is_never_a_member(self):
        idx = CitableIndex(entries=(CitableEntry(id="doc-1", target="t", sha256=SHA),))
        assert 1 not in idx

    def test_duplicate_identifiers_are_refused(self):
        entry = CitableEntry(id="doc-1", target="t", sha256=SHA)
        with pytest.raises(ValidationError, match="duplicate"):
            CitableIndex(entries=(entry, entry))

    def test_a_malformed_content_hash_is_refused(self):
        with pytest.raises(ValidationError):
            CitableEntry(id="doc-1", target="t", sha256="nope")

    @pytest.mark.parametrize("identifier", ["", " leading", "has space", "a" * 300, "!bang"])
    def test_a_malformed_identifier_is_refused(self, identifier):
        with pytest.raises(ValidationError):
            CitableEntry(id=identifier, target="t", sha256=SHA)

    def test_the_index_is_frozen(self):
        idx = CitableIndex()
        with pytest.raises(ValidationError):
            idx.entries = ()

    def test_the_digest_does_not_depend_on_entry_order(self):
        # Two drivers deriving the same index must not disagree on its hash.
        a = CitableEntry(id="doc-1", target="t1", sha256=SHA)
        b = CitableEntry(id="doc-2", target="t2", sha256=SHA)
        assert CitableIndex(entries=(a, b)).digest() == CitableIndex(entries=(b, a)).digest()

    def test_the_digest_changes_when_a_target_changes(self):
        first = CitableIndex(entries=(CitableEntry(id="d", target="t1", sha256=SHA),))
        second = CitableIndex(entries=(CitableEntry(id="d", target="t2", sha256=SHA),))
        assert first.digest() != second.digest()

    def test_the_digest_travels_the_structure_route(self):
        assert CitableIndex().digest().route == "structure/v1"
