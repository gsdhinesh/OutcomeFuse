"""doc-research tools: `corpus_search`, `document_fetch`, `passage_extract`.

**Selection is the task, so no tool performs it.** SELECTION.md is marked
key-derivation material and not agent-visible: it describes a six-step rule for
picking the one document that governs a topic, region and date. `corpus_search`
returns candidates in a fixed order and applies none of that rule — not the
status filter, not supersession, not region precedence, not recency. A tool
that filtered would hand over the answer and leave a benchmark measuring
nothing.

The `doc_id` values are this workload's citable index, which is also built
here, from the corpus rather than from anything that knows the answers.
"""

from __future__ import annotations

from typing import Any, Final

from ..core.canon import hash_structure
from ..core.contract import Contract
from ..core.verify import CitableEntry, CitableIndex
from .corpus import documents
from .toolport import ToolError, WorkloadToolPort, required

CORPUS: Final[str] = "cases/corpora/doc-research/v1"

MAX_HITS: Final[int] = 50
#: What a search result may show. `control_value` is present because the task
#: is choosing *which* document governs, not discovering values — and hiding it
#: here would only force an extra fetch per candidate.
SUMMARY_FIELDS: Final[tuple[str, ...]] = (
    "doc_id",
    "topic",
    "region",
    "status",
    "effective_from",
    "supersedes",
    "control_unit",
    "control_value",
    "title",
)


def _docs() -> list[dict[str, Any]]:
    return documents(CORPUS)


def corpus_search(arguments: dict[str, Any]) -> Any:
    topic = arguments.get("topic")
    region = arguments.get("region")
    text = arguments.get("text")

    hits = []
    for doc in _docs():
        if topic is not None and doc.get("topic") != topic:
            continue
        if region is not None and doc.get("region") != region:
            continue
        if text is not None:
            haystack = f"{doc.get('title', '')}\n{doc.get('body', '')}".lower()
            if str(text).lower() not in haystack:
                continue
        hits.append({field: doc.get(field) for field in SUMMARY_FIELDS})

    # Sorted by doc_id, never by relevance or recency: an ordering that
    # implied precedence would be step 6 of the rule, done for the agent.
    hits.sort(key=lambda d: str(d["doc_id"]))
    return {
        "hits": hits[:MAX_HITS],
        "hit_count": len(hits),
        "truncated": len(hits) > MAX_HITS,
        "ordering": "doc_id ascending; no precedence is implied or applied",
    }


def document_fetch(arguments: dict[str, Any]) -> Any:
    doc_id = str(required(arguments, "doc_id"))
    for doc in _docs():
        if doc.get("doc_id") == doc_id:
            return dict(doc)
    raise ToolError(f"no document {doc_id!r}")


def passage_extract(arguments: dict[str, Any]) -> Any:
    """The lines of one document's body that mention a query term."""
    doc_id = str(required(arguments, "doc_id"))
    query = str(required(arguments, "query")).lower()
    document = document_fetch({"doc_id": doc_id})
    body = str(document.get("body", ""))
    passages = [
        line.strip()
        for line in body.splitlines()
        if query in line.lower() and line.strip()
    ]
    return {"doc_id": doc_id, "query": query, "passages": passages}


def citable_index() -> CitableIndex:
    """AD-7: the index the `citation-resolves` verifier is handed.

    A citation that names anything not in this corpus fails the gate, which is
    what stops an agent inventing a plausible document id.
    """
    entries = tuple(
        CitableEntry(
            id=str(doc["doc_id"]),
            target=f"{CORPUS}#{doc['doc_id']}",
            sha256=hash_structure(dict(doc)).sha256,
        )
        for doc in sorted(_docs(), key=lambda d: str(d["doc_id"]))
    )
    return CitableIndex(entries=entries)


def tool_port(contract: Contract) -> WorkloadToolPort:
    return WorkloadToolPort(
        contract=contract,
        handlers={
            "corpus_search": corpus_search,
            "document_fetch": document_fetch,
            "passage_extract": passage_extract,
        },
    )
