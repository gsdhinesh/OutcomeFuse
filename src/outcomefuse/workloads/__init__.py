"""Workload tools, served from the frozen corpora.

**Tools expose data; they never expose answers.** The corpora ship the
derivation material each workload's answer keys come from — a classification
ladder, a document-selection rule, a repo with unmarked defects — and none of
it reaches these tools. A tool that filtered, classified or diagnosed would
hand over the task and leave a benchmark measuring nothing.

Tool implementations are **not** frozen, which would matter if they could
favour one arm. They cannot: both arms draw the same tools from the same
contract, so anything done here lands on the baseline identically.
"""

from __future__ import annotations

from ..core.contract import Contract
from ..ports import ToolCall, ToolResult
from .corpus import (
    CorpusError,
    close_corpora,
    corpus_path,
    documents,
    repo_files,
    sql_corpus,
    writable_copy,
)
from .toolport import Handler, ToolError, WorkloadToolPort, required

#: Which module serves which workload. The keys are contract `workload` values.
_BUILDERS = {
    "data-sql": "data_sql",
    "code-triage": "code_triage",
    "doc-research": "doc_research",
    "supply-chain": "supply_chain",
}


def tool_port_for(contract: Contract) -> WorkloadToolPort:
    """The tool port for a contract's workload, or a refusal naming what exists."""
    module_name = _BUILDERS.get(contract.workload)
    if module_name is None:
        raise ToolError(
            f"no tools for workload {contract.workload!r}; "
            f"the four built are {sorted(_BUILDERS)}"
        )
    from importlib import import_module

    module = import_module(f".{module_name}", __package__)
    return module.tool_port(contract)


__all__ = [
    "CorpusError",
    "Handler",
    "ToolCall",
    "ToolError",
    "ToolResult",
    "WorkloadToolPort",
    "close_corpora",
    "corpus_path",
    "documents",
    "repo_files",
    "required",
    "sql_corpus",
    "tool_port_for",
    "writable_copy",
]
