"""Frozen-in defects must reach the submission (§8.2).

The freeze is final once any run exists, so a defect found afterwards is worked
around and disclosed rather than fixed. The failure mode this guards against is
not a bug — it is a decision, made late, by someone who can see that the number
looks better without the paragraph. Every entry in the registry is one that
makes the result look worse, which is precisely why the check is mechanical.
"""

from __future__ import annotations

import re

import pytest
from pydantic import ValidationError
from test_submission import beats, mechanism

from outcomefuse.submission import (
    DISCLOSURE_KEYS,
    FROZEN_DEFECTS,
    Disclosure,
    Submission,
    build_submission,
)


def a_submission(**over) -> Submission:
    base = {
        "beats": tuple(beats()),
        "mechanism": mechanism(),
        "workloads_completed": ("data-sql",),
    }
    return Submission(**(base | over))


class TestTheRegistry:
    def test_every_defect_says_what_it_is_why_and_what_instead(self):
        for defect in FROZEN_DEFECTS:
            assert defect.finding.strip()
            assert defect.why_not_fixed.strip()
            assert defect.workaround.strip()

    def test_keys_are_unique(self):
        assert len(DISCLOSURE_KEYS) == len(FROZEN_DEFECTS)

    def test_every_defect_declares_which_way_it_pushes_the_result(self):
        # A reader weighs a defect that flatters us differently from one that
        # costs us. Leaving it unsaid lets the reader assume the kinder one.
        assert all(
            d.direction in {"for", "against", "neutral", "unknown"} for d in FROZEN_DEFECTS
        )

    def test_the_two_measured_findings_are_registered(self):
        # Both were found after runs existed, which is what makes them permanent.
        assert "doc-research-iteration-cap" in DISCLOSURE_KEYS
        assert "start-model-is-not-uniformly-better" in DISCLOSURE_KEYS


class TestTheyCannotBeDropped:
    def test_a_submission_carries_them_by_default(self):
        assert a_submission().disclosures == FROZEN_DEFECTS

    def test_dropping_one_is_refused(self):
        # The act this exists to prevent: a late edit by someone who can see the
        # number looks better without the paragraph.
        kept = tuple(d for d in FROZEN_DEFECTS if d.key != "doc-research-iteration-cap")
        with pytest.raises(ValidationError, match="doc-research-iteration-cap"):
            a_submission(disclosures=kept)

    def test_dropping_all_of_them_is_refused(self):
        with pytest.raises(ValidationError, match=re.escape("§8.2")):
            a_submission(disclosures=())

    def test_extra_disclosures_are_allowed(self):
        # The registry is a floor, not a ceiling. Telling more is never refused.
        extra = Disclosure(
            key="something-else",
            finding="x",
            why_not_fixed="y",
            workaround="z",
            direction="unknown",
        )
        assert len(a_submission(disclosures=(*FROZEN_DEFECTS, extra)).disclosures) == len(
            FROZEN_DEFECTS
        ) + 1

    def test_build_submission_carries_them_too(self):
        # The assembled path, not just the model. A default that only applied to
        # direct construction would be absent from every real submission.
        built = build_submission(
            beats(), mechanism=mechanism(), workloads_completed=("data-sql",)
        )
        assert {d.key for d in built.disclosures} >= DISCLOSURE_KEYS


class TestTheyAreRendered:
    def test_the_script_prints_every_disclosure(self):
        # Carried in the model but missing from the rendered script would be a
        # disclosure nobody reads, which is the same as no disclosure.
        rendered = a_submission().render()
        for defect in FROZEN_DEFECTS:
            assert defect.key in rendered

    def test_the_rendered_disclosure_says_why_it_was_not_fixed(self):
        rendered = a_submission().render()
        assert "Not fixed:" in rendered
        assert "§8.2" in rendered

    def test_they_change_the_digest(self):
        # A submission whose disclosures were edited is a different artifact.
        one = a_submission()
        two = a_submission(disclosures=(*FROZEN_DEFECTS, Disclosure(
            key="extra", finding="x", why_not_fixed="y", workaround="z", direction="for"
        )))
        assert one.digest().sha256 != two.digest().sha256
