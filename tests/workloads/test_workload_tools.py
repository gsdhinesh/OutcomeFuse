"""Workload tools over the frozen corpora.

The property these tests exist to defend is easy to lose and expensive to lose
quietly: **tools expose data, never answers.** Each corpus ships the material
its answer keys are derived from — a classification ladder, a six-step document
selection rule, a repo of unmarked defects — and a tool that leaked any of it
would leave a benchmark that measures nothing while still producing numbers.

The other property is determinism. The Tool Governor caches and deduplicates on
the contract's word that a tool is deterministic, so a "deterministic" tool
that drifts makes the cache serve wrong answers, and it does so silently.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from outcomefuse.core.contract import load_path
from outcomefuse.ports import ToolCall
from outcomefuse.workloads import (
    ToolError,
    WorkloadToolPort,
    data_sql,
    doc_research,
    supply_chain,
    tool_port_for,
)

WORKLOADS = ("data-sql", "code-triage", "doc-research", "supply-chain")


def contract_for(workload: str):
    return load_path(Path(f"contracts/{workload}.contract.yaml"))


@pytest.fixture(scope="module")
def ports() -> dict[str, WorkloadToolPort]:
    return {w: tool_port_for(contract_for(w)) for w in WORKLOADS}


def call(port: WorkloadToolPort, tool: str, **arguments):
    return port.invoke(ToolCall(tool=tool, arguments=arguments, step_id="s1")).output


class TestEveryDeclaredToolIsServed:
    @pytest.mark.parametrize("workload", WORKLOADS)
    def test_the_handler_table_matches_the_frozen_contract(self, workload, ports):
        # A tool the contract declares and nothing serves would surface
        # mid-run; a handler nothing declares would never be reachable.
        declared = {t.name for t in contract_for(workload).tools}
        assert declared == set(ports[workload]._handlers)

    def test_a_handler_table_that_does_not_match_is_refused(self):
        with pytest.raises(ToolError, match="does not match the contract's tools"):
            WorkloadToolPort(contract=contract_for("data-sql"), handlers={})

    def test_an_unknown_workload_names_what_exists(self):
        contract = contract_for("data-sql").model_copy(update={"workload": "weather"})
        with pytest.raises(ToolError, match="no tools for workload 'weather'"):
            tool_port_for(contract)


class TestDeterminismTheGovernorRelieson:
    @pytest.mark.parametrize(
        ("workload", "tool", "arguments"),
        [
            ("data-sql", "sql_query", {"sql": "SELECT count(*) AS n FROM orders"}),
            ("data-sql", "schema_describe", {"table": "orders"}),
            ("code-triage", "repo_grep", {"pattern": "def "}),
            ("code-triage", "symbol_refs", {"symbol": "cache"}),
            ("doc-research", "corpus_search", {"topic": "data-retention"}),
            ("supply-chain", "order_lookup", {"po_id": 5004}),
            ("supply-chain", "shipment_trace", {"po_id": 5004}),
        ],
    )
    def test_a_deterministic_tool_answers_identically_twice(
        self, workload, tool, arguments, ports
    ):
        port = ports[workload]
        assert call(port, tool, **arguments) == call(port, tool, **arguments)

    @pytest.mark.parametrize("workload", WORKLOADS)
    def test_every_tool_the_contract_calls_deterministic_is_cacheable(
        self, workload, ports
    ):
        # FR33's exemption is keyed on these flags, so the flags have to be true.
        for tool in contract_for(workload).tools:
            if tool.deterministic:
                assert not tool.side_effecting


class TestDataSql:
    def test_the_corpus_is_read_only_at_the_engine(self, ports):
        # Not a regex over the query text: that is a guess a creative query
        # wins. `query_only` makes the write fail inside SQLite.
        with pytest.raises(ToolError, match="the query failed"):
            call(ports["data-sql"], "sql_query", sql="DELETE FROM orders")

    def test_a_read_still_works_after_a_refused_write(self, ports):
        with pytest.raises(ToolError):
            call(ports["data-sql"], "sql_query", sql="DELETE FROM orders")
        # The refusal must not poison the connection every later read shares.
        assert call(ports["data-sql"], "sql_query", sql="SELECT count(*) FROM orders")[
            "rows"
        ][0][0] == 30

    def test_one_statement_per_call(self, ports):
        with pytest.raises(ToolError, match="one statement per call"):
            call(ports["data-sql"], "sql_query", sql="SELECT 1; SELECT 2")

    def test_a_trailing_semicolon_is_still_one_statement(self, ports):
        assert call(ports["data-sql"], "sql_query", sql="SELECT 1 AS n;")["rows"] == [[1]]

    def test_a_broken_query_is_a_tool_error_not_a_crash(self, ports):
        with pytest.raises(ToolError, match="the query failed"):
            call(ports["data-sql"], "sql_query", sql="SELECT * FROM nowhere")

    def test_an_empty_query_is_refused(self, ports):
        with pytest.raises(ToolError, match="answers nothing"):
            call(ports["data-sql"], "sql_query", sql="   ")

    def test_a_huge_result_is_capped_and_says_so(self, ports):
        out = call(
            ports["data-sql"],
            "sql_query",
            sql="WITH RECURSIVE n(i) AS (SELECT 1 UNION ALL SELECT i+1 FROM n WHERE i<5000)"
            " SELECT i FROM n",
        )
        assert out["truncated"]
        assert out["row_count"] == data_sql.MAX_ROWS

    def test_an_unknown_table_is_named(self, ports):
        with pytest.raises(ToolError, match="no table named 'nowhere'"):
            call(ports["data-sql"], "schema_describe", table="nowhere")

    def test_the_write_tool_cannot_reach_the_shared_corpus(self, ports):
        # It is declared side-effecting, so it really writes — to a scratch
        # copy. Reaching the read corpus would make every later cached read
        # wrong, on a connection the governor was told is stable.
        port = ports["data-sql"]
        before = call(port, "sql_query", sql="SELECT count(*) FROM orders WHERE status='closed'")[
            "rows"
        ][0][0]
        out = call(port, "sql_execute_write", sql="UPDATE orders SET status='closed'")
        assert out["rows_changed"] == 30
        after = call(port, "sql_query", sql="SELECT count(*) FROM orders WHERE status='closed'")[
            "rows"
        ][0][0]
        assert after == before

    def test_a_write_the_schema_forbids_is_a_tool_error(self, ports):
        # The seed has referential integrity and the scratch copy keeps it.
        with pytest.raises(ToolError, match="the write failed"):
            call(ports["data-sql"], "sql_execute_write", sql="DELETE FROM orders")

    def test_the_side_effect_is_observable_out_of_band(self, ports):
        # AD-15: the probe does not trust the decision log.
        port = tool_port_for(contract_for("data-sql"))
        call(port, "sql_execute_write", sql="UPDATE orders SET status='on_hold'")
        assert any("sql_execute_write" in effect for effect in port.side_effects)


class TestCodeTriage:
    def test_it_reads_the_repo_not_a_diagnosis(self, ports):
        out = call(ports["code-triage"], "read_file", path="orderflow/cache.py")
        assert out["lines"][0]["line"] == 1
        # No tool names a defect; finding them is the task.
        assert "defect" not in str(out).lower()

    def test_a_missing_file_lists_what_exists(self, ports):
        with pytest.raises(ToolError, match=r"no file at 'orderflow/nope\.py'"):
            call(ports["code-triage"], "read_file", path="orderflow/nope.py")

    def test_a_pattern_that_does_not_compile_is_a_tool_error(self, ports):
        with pytest.raises(ToolError, match="does not compile"):
            call(ports["code-triage"], "repo_grep", pattern="(unclosed")

    def test_an_overlong_pattern_is_refused(self, ports):
        with pytest.raises(ToolError, match="longer than"):
            call(ports["code-triage"], "repo_grep", pattern="a" * 500)

    def test_grep_is_scoped_by_path_when_asked(self, ports):
        out = call(ports["code-triage"], "repo_grep", pattern="def ", path="orderflow/cache.py")
        assert {m["path"] for m in out["matches"]} == {"orderflow/cache.py"}

    def test_symbol_refs_admits_it_is_textual(self, ports):
        # A tool that implied scope resolution would mislead an agent that
        # reasoned about shadowing.
        out = call(ports["code-triage"], "symbol_refs", symbol="cache")
        assert out["resolution"] == "textual"

    def test_a_non_identifier_symbol_is_refused(self, ports):
        with pytest.raises(ToolError, match="is not an identifier"):
            call(ports["code-triage"], "symbol_refs", symbol="not a name")

    def test_run_tests_reports_no_suite_rather_than_inventing_a_pass(self, ports):
        # An invented pass is a tool telling the agent its work is done.
        port = tool_port_for(contract_for("code-triage"))
        out = call(port, "run_tests")
        assert out["status"] == "no-suite"
        assert any("run_tests" in effect for effect in port.side_effects)


class TestDocResearchLeavesSelectionToTheAgent:
    def test_search_applies_no_step_of_the_rule(self, ports):
        # SELECTION.md is key-derivation material and not agent-visible. A
        # search that filtered drafts, applied supersession or preferred the
        # region would be doing the task.
        out = call(ports["doc-research"], "corpus_search", topic="data-retention")
        statuses = {h["status"] for h in out["hits"]}
        regions = {h["region"] for h in out["hits"]}
        assert len(out["hits"]) > 1
        assert statuses != {"active"} or len(regions) > 1

    def test_results_are_ordered_by_id_so_order_implies_no_precedence(self, ports):
        out = call(ports["doc-research"], "corpus_search", topic="data-retention")
        ids = [h["doc_id"] for h in out["hits"]]
        assert ids == sorted(ids)

    def test_superseded_documents_are_still_returned(self, ports):
        # Step 4 of the rule is the agent's to apply.
        everything = call(ports["doc-research"], "corpus_search")
        superseded = {h["supersedes"] for h in everything["hits"] if h["supersedes"]}
        returned = {h["doc_id"] for h in everything["hits"]}
        assert superseded and superseded <= returned

    def test_an_unknown_document_is_refused(self, ports):
        with pytest.raises(ToolError, match="no document 'doc-999'"):
            call(ports["doc-research"], "document_fetch", doc_id="doc-999")

    def test_the_citable_index_is_built_from_the_corpus(self, ports):
        index = doc_research.citable_index()
        ids = [e.id for e in index.entries]
        assert ids == sorted(ids)
        assert "doc-001" in ids
        assert index.digest().sha256

    def test_a_fabricated_citation_is_not_in_the_index(self):
        assert "doc-999" not in {e.id for e in doc_research.citable_index().entries}


class TestSupplyChainLeavesClassificationToTheAgent:
    def test_the_exception_note_does_not_carry_its_class(self, ports):
        # classification.sql derives the keys and is not agent-visible.
        out = call(ports["supply-chain"], "order_lookup", po_id=5004)
        assert out["exceptions"]
        for raised in out["exceptions"]:
            assert "classification" not in raised
            assert "exception_class" not in raised

    def test_an_unknown_order_is_refused(self, ports):
        with pytest.raises(ToolError, match="no purchase order 99999"):
            call(ports["supply-chain"], "order_lookup", po_id=99999)

    def test_nothing_moved_is_distinguished_from_no_such_order(self, ports):
        out = call(ports["supply-chain"], "shipment_trace", po_id=99999)
        assert out["movement"] == "none"

    def test_policies_are_returned_verbatim(self, ports):
        out = call(ports["supply-chain"], "supplier_policy_lookup")
        assert out["policies"]
        assert all("body" in p for p in out["policies"])

    def test_an_unknown_clause_is_refused(self, ports):
        with pytest.raises(ToolError, match="no policy clause 'SP-999'"):
            call(ports["supply-chain"], "supplier_policy_lookup", clause_ref="SP-999")

    def test_notify_planner_is_recorded_where_the_probe_can_see_it(self, ports):
        port = tool_port_for(contract_for("supply-chain"))
        call(port, "notify_planner", message="PO 5004 needs a decision")
        assert any("notify_planner" in effect for effect in port.side_effects)

    def test_the_citable_index_is_the_policy_clauses(self, ports):
        ids = {e.id for e in supply_chain.citable_index().entries}
        assert "SP-4.1" in ids


class TestTheProbe:
    def test_invocations_are_recorded_independently_of_any_log(self, ports):
        port = tool_port_for(contract_for("data-sql"))
        call(port, "sql_query", sql="SELECT 1")
        call(port, "sql_query", sql="SELECT 2")
        assert port.invocation_count("sql_query") == 2
        assert port.was_invoked("sql_query", step_id="s1")
        assert not port.was_invoked("schema_describe")


class TestTheToolsCannotReachTheAnswers:
    """The runtime being unable to consult the answers is the property the whole
    benchmark rests on, so it is checked rather than trusted.

    Checked against string literals that are **not** docstrings: a module may
    say in prose that it does not read the selection rule, and this must not
    mistake that sentence for the thing it disclaims.
    """

    FORBIDDEN = (
        "derive_answer_keys",
        "check_cases",
        "answer-keys",
        "answer_keys",
        "SELECTION.md",
        "classification.sql",
    )

    @staticmethod
    def code_literals(source: Path) -> list[str]:
        """Every string constant in the module except its docstrings."""
        tree = ast.parse(source.read_text(encoding="utf-8"))
        docstrings = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef):
                doc = ast.get_docstring(node, clean=False)
                if doc is not None:
                    docstrings.add(doc)
        return [
            node.value
            for node in ast.walk(tree)
            if isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and node.value not in docstrings
        ]

    @pytest.mark.parametrize("forbidden", FORBIDDEN)
    def test_no_tool_names_the_derivation_material(self, forbidden):
        import outcomefuse.workloads as package

        for source in Path(package.__file__).parent.glob("*.py"):
            for literal in self.code_literals(source):
                assert forbidden not in literal, f"{source.name} names {forbidden!r}"

    def test_no_tool_imports_anything_from_the_freeze_directory(self):
        import outcomefuse.workloads as package

        for source in Path(package.__file__).parent.glob("*.py"):
            tree = ast.parse(source.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    assert "freeze" not in (node.module or "")
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        assert "freeze" not in alias.name

    def test_the_check_would_catch_a_tool_that_did_reach_them(self, tmp_path: Path):
        # The instrument gets checked too: a literal outside a docstring is
        # caught, and the same words inside one are not.
        offender = tmp_path / "offender.py"
        offender.write_text(
            '"""This module does not read SELECTION.md."""\n'
            'path = "cases/corpora/doc-research/v1/SELECTION.md"\n',
            encoding="utf-8",
        )
        literals = self.code_literals(offender)
        assert any("SELECTION.md" in literal for literal in literals)
        assert not any("does not read" in literal for literal in literals)
