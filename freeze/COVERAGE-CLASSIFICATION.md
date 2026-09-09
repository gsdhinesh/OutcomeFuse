# Verifier Coverage Classification — pre-freeze (FR108)

**Status:** E1a output. Input to E3's formal coverage review, which produces the
per-workload coverage report that gets frozen. Nothing here is frozen yet.

Every intended criterion across the four committed workloads is classified:

- **E** — expressible with an existing registry verifier today
- **N** — a new deterministic type is demonstrably needed
- **A** — advisory; recorded, fed to counter-metrics, never gating

## Headline result

**No `N`.** All 24 mandatory and 4 optional criteria across the four contracts
are expressible with the seven existing verifier types. The allowance of at most
three additional deterministic types is **unused**, and E3 should keep it that
way unless the review finds a gap this authoring missed.

That is the outcome the pre-freeze review exists to establish rather than
assume — and it only holds because the semantic criteria were classified `A`
honestly instead of being approximated by a proxy verifier and called mandatory.

## Verification-mode counts

Mode is a property of the verifier type, not asserted per contract.
Reference-backed: `exact-match-against-answer-key`, `citation-resolves`.
Constraint-backed: the other five.

| Workload | Mandatory | Reference-backed | Constraint-backed | Predominantly constraint-backed? |
| --- | ---: | ---: | ---: | --- |
| doc-research | 6 | 3 | 3 | No |
| code-triage | 6 | 3 | 3 | No |
| data-sql | 6 | 3 | 3 | No |
| supply-chain | 6 | 4 | 2 | No |

**No workload is predominantly constraint-backed, and none has zero
reference-backed mandatory criteria.** Both matter: the first is a label that
would otherwise have to accompany every published result for that workload, and
the second would bar the workload from being used to imply that OutcomeFuse
independently established semantic correctness.

### How that was reached, and why it is not fitting

The first draft of these contracts used `set-membership` for `severity`,
`units`, `exception_type` and `recommended_action`. All four workloads then came
out predominantly constraint-backed. The fix was not to add criteria until the
label flipped — that would be fitting the evidence to the standard. It was to
apply one principle uniformly:

> **If the answer key pins the field, check against the key.** `set-membership`
> only proves a value is *legal*; `exact-match-against-answer-key` proves it is
> *right*. Where the key pins the value, membership is strictly the weaker check
> and there is no reason to prefer it.

The counts moved because the verification genuinely got stronger, not because
criteria were padded. Anyone reviewing this should check that claim rather than
take it — the diff is in version control.

### Consequence: `set-membership` has no mandatory use in the MVP

Applying that principle leaves `set-membership` unused by every mandatory
criterion in all four contracts. It stays in the registry, because on a
production workload with no answer key it is exactly what remains available —
which is the honest limit already recorded in the contract companion. E3 should
record it as **registered, tested, zero MVP mandatory usage** rather than
quietly drop it or invent a use for it.

## Per-workload classification

### doc-research

| Criterion | Class | Verifier | Mode |
| --- | --- | --- | --- |
| answer-present | E | field-present | constraint |
| answer-is-text | E | type-is | constraint |
| answer-matches-key | E | exact-match-against-answer-key | reference |
| citations-sufficient | E | numeric-range | constraint |
| primary-source-matches-key | E | exact-match-against-answer-key | reference |
| citations-resolve | E | citation-resolves | reference |
| excluded-candidates-recorded *(optional)* | E | field-present | constraint |
| conclusion-is-supported | **A** | — | — |
| answer-completeness | **A** | — | — |

### code-triage

| Criterion | Class | Verifier | Mode |
| --- | --- | --- | --- |
| root-cause-file-present | E | field-present | constraint |
| root-cause-file-correct | E | exact-match-against-answer-key | reference |
| root-cause-line-in-span | E | numeric-range | constraint |
| severity-matches-key | E | exact-match-against-answer-key | reference |
| fix-summary-substantive | E | regex-match | constraint |
| evidence-refs-resolve | E | citation-resolves | reference |
| regression-test-named *(optional)* | E | field-present | constraint |
| root-cause-explanation-correct | **A** | — | — |
| fix-is-appropriate | **A** | — | — |

### data-sql

| Criterion | Class | Verifier | Mode |
| --- | --- | --- | --- |
| result-matches-key | E | exact-match-against-answer-key | reference |
| units-match-key | E | exact-match-against-answer-key | reference |
| sql-present | E | field-present | constraint |
| sql-is-read-only | E | regex-match | constraint |
| row-count-matches-key | E | exact-match-against-answer-key | reference |
| tables-used-plausible | E | numeric-range | constraint |
| assumptions-recorded *(optional)* | E | field-present | constraint |
| question-actually-answered | **A** | — | — |
| query-is-idiomatic | **A** | — | — |

### supply-chain

| Criterion | Class | Verifier | Mode |
| --- | --- | --- | --- |
| exception-type-matches-key | E | exact-match-against-answer-key | reference |
| root-cause-matches-key | E | exact-match-against-answer-key | reference |
| impacted-orders-identified | E | numeric-range | constraint |
| recommended-action-matches-key | E | exact-match-against-answer-key | reference |
| policy-refs-resolve | E | citation-resolves | reference |
| delay-estimate-bounded | E | numeric-range | constraint |
| alternate-considered *(optional)* | E | field-present | constraint |
| recommendation-is-justified | **A** | — | — |
| evidence-completeness | **A** | — | — |

## The semantic criteria, explicitly

FR108 requires the review to cover the criteria most easily missed because they
are semantic. Each is named here with where it landed and why.

| Semantic property | Where it landed | Why |
| --- | --- | --- |
| Root-cause correctness | Partly **E**, partly **A** | *Location* is checkable — the key pins file, line span and severity. The *explanation* is not, and is advisory. The gate rests on location only, and the coverage report must not let a passing location imply a correct explanation. |
| Query-result correctness | **E** | Fully reference-backed: value, units and row count all pinned by the key. The strongest workload in the set, and it should be reported as the strong case rather than as representative. |
| Code-location correctness | **E** | `exact-match-against-answer-key` on the path, `numeric-range` from key-supplied bounds on the line. |
| Evidence completeness | **A** | `citations-resolve` proves cited evidence *exists*; nothing deterministic proves nothing *material was missed*. Naming a count threshold mandatory would be a proxy dressed as a check. |
| Conclusion supported vs merely present | **A** | The barred `citation-supports-claim` in disguise. It stays advisory in all four workloads. |

**This is the honest limit of the MVP gate.** In every workload, the criterion
the user actually cares about most — is the conclusion *justified* — is
advisory. What the gate enforces is that the answer matches a known-correct
value and that its evidence exists and resolves. That is a real and checkable
property, and it is not the same as understanding. Any claim drawn from these
runs has to be phrased against what was actually verified.

## Open items for E3

1. Confirm the `N`-free result against the contracts as authored, independently
   of this document. If E3 finds a gap, the three-addition allowance is
   available and unspent.
2. Decide how `set-membership` is recorded given zero MVP mandatory usage.
3. Decide whether the **predominantly constraint-backed** label should be
   weighted rather than counted. A workload could carry one decisive
   reference-backed criterion and five incidental constraint-backed ones and be
   labelled constraint-backed, or the reverse. The current rule counts criteria
   and is blind to which one carries the weight. It is a defensible rule and it
   is not a precise one.
4. `fix-summary-substantive` is a length-and-keyword regex — the weakest
   mandatory criterion in the set, and a proxy for "a real fix was described".
   It is honest as a *constraint*, and it should not be read as evidence the fix
   is right. Consider whether it earns its place as mandatory at all.
