# Verification-Mode Coverage Report (FR108)

**Generated** by `freeze/coverage_report.py` from the four contracts and the
registry. Do not edit by hand — regenerate. Frozen at E1b in one operation
with the cases, answer keys, rubric, contracts and registry.

Registry version `v1`, digest `71ea885351f1aa9afd8b7904360566bad949410a7fa5aae21f8b9d7533a576f6`.

## Mandatory criteria by verification mode

Mode is a property of the verifier type, fixed by the registry. No contract
asserts it, which is what stops `reference-backed` being claimed for a check
that never compared against a known-correct value.

| Workload | Mandatory | Reference-backed | Constraint-backed | Reference % | Predominantly constraint-backed |
| --- | ---: | ---: | ---: | ---: | --- |
| doc-research | 6 | 3 | 3 | 50% | No |
| code-triage | 6 | 3 | 3 | 50% | No |
| data-sql | 6 | 3 | 3 | 50% | No |
| supply-chain | 6 | 4 | 2 | 67% | No |

No workload is predominantly constraint-backed, and every workload has at least one reference-backed mandatory criterion.

**Read that result carefully.** doc-research, code-triage, data-sql sit exactly on the boundary — equal counts either side. The rule labels a workload predominantly constraint-backed only where constraint-backed *exceeds* reference-backed, so a tie passes. One criterion moving in either direction would flip the label. This is a defensible rule and not a precise one: it counts criteria and is blind to which one carries the decision. A weighted rule was considered and rejected because the weighting would itself be an unverified judgement, and an arguable number presented precisely is worse than a blunt one presented plainly.

## Registry usage

| Verifier type | Mode | Mandatory uses |
| --- | --- | ---: |
| `citation-resolves` | reference-backed | 3 |
| `exact-match-against-answer-key` | reference-backed | 10 |
| `field-present` | constraint-backed | 3 |
| `numeric-range` | constraint-backed | 5 |
| `regex-match` | constraint-backed | 2 |
| `set-membership` | constraint-backed | 0 |
| `type-is` | constraint-backed | 1 |

**Registered, tested, zero MVP mandatory usage: `set-membership`.** Recorded rather than dropped or given an invented use. Where the answer key pins a field, `exact-match-against-answer-key` proves the value is *right* while `set-membership` proves only that it is *legal* — strictly the weaker check, so there is no reason to prefer it. On a production workload with no answer key, membership is what remains available, which is why it stays registered.

## Classification

**E** expressible with an existing verifier · **N** a new deterministic type is
demonstrably needed · **A** advisory: recorded, fed to counter-metrics, never gating.

**E 28 · N 0 · A 8**

**No `N`.** Every criterion the four contracts declare is expressible with the seven existing types, so the allowance of at most three additional deterministic types is **unused**. That result holds only because the semantic criteria were classified `A` honestly rather than approximated by a proxy verifier and called mandatory — the failure mode FR108 exists to catch, in which the floor quietly shrinks to presence and type.

### doc-research

| Criterion | Tier | Class | Verifier | Mode |
| --- | --- | :-: | --- | --- |
| answer-present | mandatory | E | `field-present` | constraint |
| answer-is-text | mandatory | E | `type-is` | constraint |
| answer-matches-key | mandatory | E | `exact-match-against-answer-key` | reference |
| citations-sufficient | mandatory | E | `numeric-range` | constraint |
| primary-source-matches-key | mandatory | E | `exact-match-against-answer-key` | reference |
| citations-resolve | mandatory | E | `citation-resolves` | reference |
| excluded-candidates-recorded | optional | E | `field-present` | constraint |
| conclusion-is-supported | advisory | **A** | — | — |
| answer-completeness | advisory | **A** | — | — |

### code-triage

| Criterion | Tier | Class | Verifier | Mode |
| --- | --- | :-: | --- | --- |
| root-cause-file-present | mandatory | E | `field-present` | constraint |
| root-cause-file-correct | mandatory | E | `exact-match-against-answer-key` | reference |
| root-cause-line-in-span | mandatory | E | `numeric-range` | constraint |
| severity-matches-key | mandatory | E | `exact-match-against-answer-key` | reference |
| fix-summary-substantive | mandatory | E | `regex-match` | constraint |
| evidence-refs-resolve | mandatory | E | `citation-resolves` | reference |
| regression-test-named | optional | E | `field-present` | constraint |
| root-cause-explanation-correct | advisory | **A** | — | — |
| fix-is-appropriate | advisory | **A** | — | — |

### data-sql

| Criterion | Tier | Class | Verifier | Mode |
| --- | --- | :-: | --- | --- |
| result-matches-key | mandatory | E | `exact-match-against-answer-key` | reference |
| units-match-key | mandatory | E | `exact-match-against-answer-key` | reference |
| sql-present | mandatory | E | `field-present` | constraint |
| sql-is-read-only | mandatory | E | `regex-match` | constraint |
| row-count-matches-key | mandatory | E | `exact-match-against-answer-key` | reference |
| tables-used-plausible | mandatory | E | `numeric-range` | constraint |
| assumptions-recorded | optional | E | `field-present` | constraint |
| question-actually-answered | advisory | **A** | — | — |
| query-is-idiomatic | advisory | **A** | — | — |

### supply-chain

| Criterion | Tier | Class | Verifier | Mode |
| --- | --- | :-: | --- | --- |
| exception-type-matches-key | mandatory | E | `exact-match-against-answer-key` | reference |
| root-cause-matches-key | mandatory | E | `exact-match-against-answer-key` | reference |
| impacted-orders-identified | mandatory | E | `numeric-range` | constraint |
| recommended-action-matches-key | mandatory | E | `exact-match-against-answer-key` | reference |
| policy-refs-resolve | mandatory | E | `citation-resolves` | reference |
| delay-estimate-bounded | mandatory | E | `numeric-range` | constraint |
| alternate-considered | optional | E | `field-present` | constraint |
| recommendation-is-justified | advisory | **A** | — | — |
| evidence-completeness | advisory | **A** | — | — |

## The semantic criteria, explicitly

FR108 requires the review to cover the criteria most easily missed because they
are semantic. Each is traced to the criteria that carry it.

| Semantic property | Carried by | Landed |
| --- | --- | --- |
| Root-cause correctness | `root-cause-file-correct` (E), `root-cause-explanation-correct` (A) | **split E/A** |
| Query-result correctness | `result-matches-key` (E), `question-actually-answered` (A) | **split E/A** |
| Code-location correctness | `root-cause-file-correct` (E), `root-cause-line-in-span` (E) | **E** |
| Evidence completeness | `citations-resolve` (E), `evidence-completeness` (A) | **split E/A** |
| Conclusion supported rather than present | `conclusion-is-supported` (A) | **A** |

**This is the honest limit of the MVP gate.** In every workload the property a user cares about most — is the conclusion *justified* — is advisory. What the gate enforces is that the answer matches a known-correct value and that its evidence exists and resolves. That is real and checkable, and it is not the same as understanding. Any claim drawn from these runs must be phrased against what was actually verified.

## Weakest mandatory criterion, named

`fix-summary-substantive` (code-triage) is a length-and-keyword regex. It is a proxy for *a real fix was described*, and it is the weakest thing in the floor. It was kept mandatory rather than demoted because the alternative is that `fix_summary` is checked only for presence, which accepts a single character. It is honest as a **constraint** and must never be read as evidence the fix is correct — `fix-is-appropriate` is advisory and is where that judgement lives.

## Unsatisfiability (FR9)

No contract is internally unsatisfiable. Every mandatory criterion reads a
field the deliverable declares, and every declared reserve leaves room to run.

