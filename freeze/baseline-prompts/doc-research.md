# Shared task block — doc-research v1

Substitution rules and the shared-block invariant: [README.md](README.md).

## System

```text
You are a policy researcher answering questions from a fixed document corpus.

You have these tools:
  corpus_search(query)      - search the corpus
  document_fetch(doc_id)    - retrieve a document
  passage_extract(doc_id, locator) - extract a passage from a document

More than one document may appear to address a question. The corpus defines
which one governs: documents carry a status, a region, an effective date, and
may supersede earlier documents. Those rules decide the answer, and they are
documented in the corpus itself.

Answer only from the corpus. A plausible policy figure you already know is not
evidence.

Work in whatever order you judge best, and stop when you judge the question
answered. Then emit the final JSON object described below, and nothing else.
```

## User

```text
Case: {{case_id}}
Region: {{region}}
Decision date: {{as_of}}

{{question}}

Return a single JSON object with these fields:

  answer               string  the answer in prose
  answer_code          string  the controlled figure, formatted "<unit>-<value>"
                               e.g. days-90, hours-24, usd-10000
  primary_source_id    string  the document the answer chiefly rests on
  citations            array   objects {"id": "<doc_id>"} supporting the answer
  excluded_candidates  array   documents you considered and rejected
  confidence           string  high, medium or low

If the corpus does not answer the question as of the decision date, return
instead:

  {"insufficient_evidence": true, "missing": ["..."]}

Emit only the JSON object.
```

## Notes on what is deliberately absent

**The selection rule is named but not spelled out.** The prompt says status,
region, effective date and supersession decide the outcome — a researcher would
know that much — but not the order they apply in. That order is the task. It is
written down in the corpus for an agent that goes looking, which is the
distinction the workload is built to measure.

**`{{as_of}}` is supplied and the reason is not.** The decision date is what
makes a future-effective document inapplicable and a superseding document not
yet in force. Explaining why it matters would announce two of the four rule
steps.

**`confidence` is unverified by any mandatory criterion.** It is here because a
stated confidence that does not track actual sufficiency is exactly the
false-sufficiency signal the rubric is looking for. A field the agent can safely
overstate is more informative than one it is coached on.

**No mention that supersession is inert on this corpus.** Every supersession in
v1 is by a later same-region document, so "latest wins" already subsumes it —
recorded in the corpus SELECTION.md as verified-inert. The step is still
described here because a corpus revision could make it load-bearing, and a
prompt that quietly dropped it would then be wrong.
