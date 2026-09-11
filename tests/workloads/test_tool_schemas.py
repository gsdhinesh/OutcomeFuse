"""The tool schemas the model is shown (AD-13, FR33).

The schemas are the only place the invocation protocol is stated — the frozen
task block names the tools in prose and cannot be added to. That makes them a
seam where two things can go wrong quietly:

**A tool could be offered that the contract never declared.** The contract is
what bounds the arm; a schema list assembled independently of it would let a
capability in through the side door, and the governed and baseline arms would
no longer be running the same agent.

**A description could leak an answer.** These strings are sent to the model on
every turn. A description naming a threshold, a precedence rule or a
classification would hand over what the answer keys are derived from, and the
benchmark would keep producing numbers while measuring nothing.
"""

from __future__ import annotations

import ast
import functools
from pathlib import Path

import pytest

from outcomefuse import workloads
from outcomefuse.core.contract import load_path
from outcomefuse.workloads import SCHEMAS, ToolError, schemas_for

WORKLOADS = ("data-sql", "code-triage", "doc-research", "supply-chain")

SOURCES = ("data_sql", "code_triage", "doc_research", "supply_chain")


def contract_for(workload: str):
    return load_path(Path(f"contracts/{workload}.contract.yaml"))


@functools.cache
def _handler_arguments() -> dict[str, tuple[frozenset[str], frozenset[str]]]:
    """Every argument name each handler reads, and which of them it demands.

    Read out of the source so the schemas are checked against the code rather
    than against a second copy of my own assumptions.
    """
    found: dict[str, tuple[set[str], set[str]]] = {}
    for module in SOURCES:
        path = Path(workloads.__file__).parent / f"{module}.py"
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in tree.body:
            if not isinstance(node, ast.FunctionDef) or node.name.startswith("_"):
                continue
            read: set[str] = set()
            mandatory: set[str] = set()
            for call in ast.walk(node):
                if not isinstance(call, ast.Call) or not call.args:
                    continue
                target = call.func
                if isinstance(target, ast.Name) and target.id == "required":
                    # required(arguments, "name")
                    name = _literal(call.args[1]) if len(call.args) > 1 else None
                    if name is not None:
                        read.add(name)
                        mandatory.add(name)
                elif (
                    isinstance(target, ast.Attribute)
                    and target.attr == "get"
                    and isinstance(target.value, ast.Name)
                    and target.value.id == "arguments"
                ):
                    # arguments.get("name") or arguments.get("name", default)
                    name = _literal(call.args[0])
                    if name is not None:
                        read.add(name)
            if read:
                found[node.name] = (read, mandatory)
    return {name: (frozenset(r), frozenset(m)) for name, (r, m) in found.items()}


def _literal(node: ast.expr) -> str | None:
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None


def _arguments_read_by(tool: str, *, mandatory: bool = False) -> frozenset[str]:
    read, demanded = _handler_arguments()[tool]
    return demanded if mandatory else read


class TestTheContractIsTheBoundary:
    @pytest.mark.parametrize("workload", WORKLOADS)
    def test_exactly_the_declared_tools_are_offered(self, workload):
        contract = contract_for(workload)
        offered = [schema.name for schema in schemas_for(contract)]
        assert offered == [tool.name for tool in contract.tools]

    @pytest.mark.parametrize("workload", WORKLOADS)
    def test_no_tool_from_another_workload_leaks_in(self, workload):
        # The registry is global; the offer must not be.
        offered = {schema.name for schema in schemas_for(contract_for(workload))}
        others = {
            tool.name
            for other in WORKLOADS
            if other != workload
            for tool in contract_for(other).tools
        }
        assert not (offered & others)

    def test_a_tool_with_no_schema_refuses_rather_than_being_dropped(self):
        # Silently omitting it would leave the model unable to call a tool the
        # contract promised, and the run would look like a reasoning failure.
        contract = contract_for("data-sql")
        widened = contract.model_copy(
            update={
                "tools": (*contract.tools, contract.tools[0].model_copy(update={"name": "ghost"}))
            }
        )
        with pytest.raises(ToolError, match="ghost"):
            schemas_for(widened)

    def test_a_side_effecting_tool_is_still_offered(self):
        # FR33 exempts it from optimisation-driven suppression. Withholding it
        # here would suppress it for both arms and hide the very behaviour the
        # side-effect rules exist to govern.
        offered = {schema.name for schema in schemas_for(contract_for("data-sql"))}
        assert "sql_execute_write" in offered
        assert any(t.side_effecting for t in contract_for("data-sql").tools)


class TestTheSchemasAreUsable:
    @pytest.mark.parametrize("name,schema", sorted(SCHEMAS.items()))
    def test_every_schema_is_a_closed_object(self, name, schema):
        # `additionalProperties: false` is what makes an invented argument a
        # visible failure rather than a silently ignored one.
        assert schema.parameters["type"] == "object"
        assert schema.parameters["additionalProperties"] is False

    @pytest.mark.parametrize("name,schema", sorted(SCHEMAS.items()))
    def test_required_arguments_are_actually_declared(self, name, schema):
        properties = schema.parameters["properties"]
        assert set(schema.parameters["required"]) <= set(properties)

    @pytest.mark.parametrize("name,schema", sorted(SCHEMAS.items()))
    def test_every_schema_says_what_the_tool_is(self, name, schema):
        assert schema.description.strip()

    def test_the_argument_names_match_what_the_handlers_read(self):
        # Derived from the handlers' own source, not restated from memory. A
        # schema naming `query` where the handler reads `sql` would make every
        # call fail with a message the model cannot act on, and a test that
        # simply repeated my own spelling would agree with the bug.
        for workload in WORKLOADS:
            for tool in contract_for(workload).tools:
                declared = set(SCHEMAS[tool.name].parameters["properties"])
                assert declared == _arguments_read_by(tool.name), tool.name

    def test_required_marks_exactly_what_the_handler_demands(self):
        # `required(arguments, "sql")` raises without it; `arguments.get("table")`
        # does not. The schema must say which is which or the model will omit a
        # mandatory argument and read the refusal as the tool being broken.
        for workload in WORKLOADS:
            for tool in contract_for(workload).tools:
                schema_required = set(SCHEMAS[tool.name].parameters["required"])
                assert schema_required == _arguments_read_by(tool.name, mandatory=True), tool.name


class TestTheDescriptionsLeakNothing:
    #: Words that would hand over what the answer keys are derived from: the
    #: classification ladder, the six-step selection rule, the triage verdicts.
    FORBIDDEN = (
        "expedite",
        "escalate",
        "de-prioritise",
        "deprioritize",
        "supersede",
        "precedence",
        "threshold",
        "root cause",
        "classify",
        "verdict",
        "answer key",
        "insufficient_evidence",
    )

    #: Disclaimers. "no precedence is applied" names the absence of a rule,
    #: which is the opposite of leaking it, so it is removed before scanning
    #: rather than exempting the whole description from the check.
    DISCLAIMED = ("no precedence is applied",)

    @pytest.mark.parametrize("name,schema", sorted(SCHEMAS.items()))
    def test_no_description_names_a_criterion(self, name, schema):
        lowered = schema.description.lower()
        for disclaimer in self.DISCLAIMED:
            lowered = lowered.replace(disclaimer, "")
        assert not [word for word in self.FORBIDDEN if word in lowered]

    def test_corpus_search_says_it_applies_no_precedence(self):
        # The six-step rule is the thing under test in doc-research. The tool
        # must be explicit that it is not doing any of it.
        assert "no precedence" in SCHEMAS["corpus_search"].description.lower()
