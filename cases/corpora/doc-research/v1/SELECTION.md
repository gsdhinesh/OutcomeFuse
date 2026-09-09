# Document Selection Rule — doc-research workload, v1

**KEY-DERIVATION MATERIAL.** Not agent-visible. The agent sees only the tools
the contract declares (`corpus_search`, `document_fetch`, `passage_extract`).

No document in the corpus carries an answer code. Each carries a primitive
`control_value` and `control_unit`. The answer is produced by selecting the one
document that governs a given topic, region and date, and rendering its value.
Grepping every `control_value` in the corpus therefore tells an agent nothing
about which one applies — selection *is* the task.

## The rule

Given a query of `topic`, `region` and `as_of` date, from all documents:

1. **Topic must match** exactly.
2. **Drafts have no force.** Discard anything whose `status` is not `active`.
3. **Nothing applies before its effective date.** Discard anything whose
   `effective_from` is after `as_of`.
4. **Supersession applies from the successor's effective date.** Discard any
   document that is named in the `supersedes` field of another document which
   has itself survived steps 2 and 3.
5. **Region beats global.** If any surviving document has `region == region`,
   discard the `global` ones. Documents for other regions never survive step 1
   plus this step.
6. **Latest wins.** Of what remains, take the greatest `effective_from`; break
   any tie on `doc_id` ascending.

If nothing survives, the query has **no governing document** and is
unanswerable — not a licence to fall back to the global standard, which step 3
or step 2 has already excluded on its own terms.

## Rendering

- `primary_source_id` — the `doc_id` of the surviving document.
- `answer_code` — `"{control_unit}-{control_value}"`, e.g. `days-90`,
  `hours-12`, `usd-25000`.

## Why the order matters

Steps 3 and 4 are separable and both necessary. A future-dated successor must
not retire its predecessor early: `doc-019` supersedes `doc-018` from
2026-05-15, so a query dated before that must still land on `doc-018`. Applying
supersession before effective-dating would silently leave EMEA backup frequency
with no governing standard for nine months.

## Step 4 is inert on v1 data, and that is recorded rather than hidden

Every supersession in this corpus is by a document with a *later* effective
date and the *same* region, so step 6 would have selected the successor anyway.
Disabling step 4 changes no answer for any case in the set — verified, not
assumed, by re-running selection with the step removed.

The step is retained rather than deleted because it becomes load-bearing the
moment the corpus contains a supersession that step 6 would not reproduce — a
global standard retiring a regional one, or a successor backdated ahead of its
predecessor. Until such a document exists, no case may claim step 4 as its
trap, and `check_cases.py` enforces that by refusing a distractor whose skipped
step does not change the answer.
