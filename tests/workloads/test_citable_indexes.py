"""Citable indexes (AD-7).

The index is what stops an agent citing a source it invented. A gate pass rests
on every citation resolving, so an index that is too generous makes the
criterion decorative, and one that is too strict fails honest work.

Two failure modes matter here and neither announces itself:

**A missing index.** Three of the four workloads carry a citation criterion. A
workload whose index was never built does not fail loudly — the gate reports
itself *unavailable* and the run terminates fail-closed, having spent its whole
budget first. That is exactly how the code-triage gap was found, live.

**An empty index.** For a workload that genuinely does not cite, `None` is the
honest answer. An empty `CitableIndex` would silently fail every citation put
to it, which looks like an agent inventing sources when it is the harness
having nothing to check against.
"""

from __future__ import annotations

import functools
from pathlib import Path

import pytest

from outcomefuse.core.contract import load_path
from outcomefuse.workloads import citable_index_for, code_triage
from outcomefuse.workloads.corpus import repo_files

WORKLOADS = ("data-sql", "code-triage", "doc-research", "supply-chain")

#: Workloads whose contract carries a `citation-resolves` criterion.
CITING = ("code-triage", "doc-research", "supply-chain")


def contract_for(workload: str):
    return load_path(Path(f"contracts/{workload}.contract.yaml"))


@functools.cache
def triage_index():
    return code_triage.citable_index()


def _cites(contract) -> bool:
    for group in (contract.criteria.mandatory, contract.criteria.optional):
        for criterion in group:
            if criterion.verifier and criterion.verifier.type == "citation-resolves":
                return True
    return False


class TestEveryCitingWorkloadHasAnIndex:
    @pytest.mark.parametrize("workload", WORKLOADS)
    def test_a_contract_that_cites_gets_an_index(self, workload):
        # Derived from the contract rather than from a list I typed, so a
        # criterion added later cannot quietly go unindexed.
        contract = contract_for(workload)
        index = citable_index_for(contract)
        if _cites(contract):
            assert index is not None and index.entries, workload
        else:
            assert index is None, workload

    def test_the_citing_workloads_are_the_three_expected(self):
        # Pins the premise of the test above. If this changes, the change was
        # deliberate rather than a contract quietly losing its criterion.
        assert tuple(w for w in WORKLOADS if _cites(contract_for(w))) == CITING

    @pytest.mark.parametrize("workload", CITING)
    def test_the_index_hashes(self, workload):
        # AD-7 appends this digest before any verifier runs, so two
        # implementations cannot reach different verdicts on one run.
        index = citable_index_for(contract_for(workload))
        assert index is not None
        assert len(index.digest().sha256) == 64


class TestCodeTriageCitesLines:
    def test_every_real_line_is_citable(self):
        # The frozen prompt asks for `{"id": "<path>:<line>"}`.
        index = triage_index()
        files = repo_files(code_triage.CORPUS)
        expected = {
            f"{path}:{n}"
            for path, body in files.items()
            for n in range(1, len(body.splitlines()) + 1)
        }
        assert expected <= {e.id for e in index.entries}

    def test_a_bare_path_is_citable(self):
        assert "orderflow/cache.py" in {e.id for e in triage_index().entries}

    def test_a_line_past_the_end_of_a_file_is_not(self):
        # The whole point: a line the agent never read, in a file that stops
        # short of it, must not resolve.
        ids = {e.id for e in triage_index().entries}
        assert "orderflow/cache.py:1" in ids
        assert "orderflow/cache.py:9999" not in ids

    def test_a_fabricated_file_is_not(self):
        ids = {e.id for e in triage_index().entries}
        assert "orderflow/nonexistent.py" not in ids
        assert "orderflow/nonexistent.py:1" not in ids

    def test_line_numbering_starts_at_one(self):
        # Off by one here would fail every citation an agent made from
        # `read_file`, which numbers from 1.
        assert "orderflow/cache.py:0" not in {e.id for e in triage_index().entries}

    def test_the_index_names_no_defect(self):
        # It is built from the corpus alone. If it carried any hint about which
        # lines matter it would hand over the task, and the workload would
        # measure nothing while still producing numbers.
        files = repo_files(code_triage.CORPUS)
        line_ids = sum(len(b.splitlines()) for b in files.values())
        assert len(triage_index().entries) == line_ids + len(files)

    def test_membership_works_for_the_verifier(self):
        # `citation-resolves` tests with `in`.
        index = triage_index()
        assert "orderflow/cache.py:19" in index
        assert "orderflow/cache.py:19999" not in index
