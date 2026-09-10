# Freeze Record v1 (FR65, FR64)

**Generated** by `freeze/freeze.py`. Do not edit by hand.

**Freeze digest** `3ac83cdab77d199cf07bd7d6647d4f4344c30a1d9377073e1c78922819a5e159`

This is the point of no return. §8.2's defence is that the rubric and answer
keys were fixed before the governor existed; re-freezing after seeing it is
what that section exists to prevent. The record carries no timestamp, because
regenerating it must reproduce identical bytes — a freeze that differed between
two machines would trip FR65's drift refusal on artifacts that never changed.

## Coverage at freeze time

| Workload | Mandatory | Reference-backed | Constraint-backed | Reference % | Predominantly constraint-backed |
| --- | ---: | ---: | ---: | ---: | --- |
| code-triage | 6 | 3 | 3 | 50.0% | No |
| data-sql | 6 | 3 | 3 | 50.0% | No |
| doc-research | 6 | 3 | 3 | 50.0% | No |
| supply-chain | 6 | 4 | 2 | 66.7% | No |

## Contracts

| Workload | Contract | Version | Route | SHA-256 |
| --- | --- | ---: | --- | --- |
| code-triage | `ofc-code-triage` | 1 | `structure/v1` | `7578f3291cc8940a…` |
| data-sql | `ofc-data-sql` | 1 | `structure/v1` | `a586ee16371851a9…` |
| doc-research | `ofc-doc-research` | 1 | `structure/v1` | `d3bc6d7fea5dad61…` |
| supply-chain | `ofc-supply-chain` | 1 | `structure/v1` | `657d0e8cd4085c58…` |

## Case sets

| Set | Cases | Data class | Corpus | Cases SHA-256 | Answer keys SHA-256 |
| --- | ---: | --- | --- | --- | --- |
| calibration/code-triage | 12 | synthetic | `cases/corpora/code-triage/v1` | `39b399b2663b5ced…` | `852a2fae36283365…` |
| calibration/data-sql | 12 | synthetic | `cases/corpora/data-sql/v1` | `baf22a55486fad2d…` | `dc38749ad4d3efde…` |
| calibration/doc-research | 12 | synthetic | `cases/corpora/doc-research/v1` | `973815e93bcbdbdd…` | `32053376b335e6eb…` |
| calibration/supply-chain | 12 | synthetic | `cases/corpora/supply-chain/v1` | `256a708550d1368c…` | `fde2e1b542851bb8…` |
| evaluation/code-triage | 8 | synthetic | `cases/corpora/code-triage/v1` | `5f4c432818c22dc4…` | `01a45b9440a04923…` |
| evaluation/data-sql | 8 | synthetic | `cases/corpora/data-sql/v1` | `4a2bc9969d809264…` | `913beb7721d3db5d…` |
| evaluation/doc-research | 8 | synthetic | `cases/corpora/doc-research/v1` | `7c676da669f45dbd…` | `90d1c641de045ae3…` |
| evaluation/supply-chain | 8 | synthetic | `cases/corpora/supply-chain/v1` | `12e76a8a352580a9…` | `51b5d9a47e8812ad…` |

The **evaluation** sets are frozen and sealed. Their case definitions are
authored and known; it is the *results* that must stay unseen until
preregistration (FR66) is complete. Only evaluation results may support a
headline claim, and calibration results may not enter the submission (FR102).

## Verifier registry

Version `v1`, route `structure/v1`, digest `71ea885351f1aa9afd8b7904360566bad949410a7fa5aae21f8b9d7533a576f6`.

A frozen rubric whose criteria take their executable meaning from an unfrozen
registry is not frozen, so the registry, its source and its tests freeze here
in the same operation.

## Source artifacts (file-digest route)

| Group | Files | SHA-256 |
| --- | ---: | --- |
| baseline_definition | 6 | `62f3fb1ec0d93b85…` |
| case_construction_rules | 1 | `3c9e83abd10d7722…` |
| corpora | 14 | `6333cf6d71ad8e2b…` |
| coverage_report | 1 | `25eb7f5812b84d08…` |
| derivation_scripts | 3 | `e946ff683ee83327…` |
| rubric | 1 | `728a02b34048fb22…` |
| verifier_registry_source | 4 | `3d267f1be1c8a550…` |
| verifier_registry_tests | 2 | `4e3a9bce092d7c44…` |

Paths are POSIX-separated, NFC-normalised and byte-sorted, and text artifacts
are digested with LF line endings, so a Windows freeze and a Linux freeze agree.

## Advisory criteria and why they do not gate

**code-triage**

- `root-cause-explanation-correct` — Whether the *explanation* of the defect is right, as distinct from the location being right. Deterministically uncheckable — the location criteria above are what the gate actually rests on, and the coverage report must not let the two be conflated.
- `fix-is-appropriate` — Whether the proposed fix would actually resolve the defect.

**data-sql**

- `question-actually-answered` — Whether the query answers the question asked, as opposed to producing a number that happens to match. With a single answer key these coincide; on a production workload they would not, and that gap is the honest limit of this workload's evidence.
- `query-is-idiomatic` — Whether the SQL is reasonable rather than merely correct.

**doc-research**

- `conclusion-is-supported` — The answer is *supported* by the cited passages rather than merely accompanied by them. No deterministic verifier can establish this, so it is advisory by construction and is named here rather than quietly omitted.
- `answer-completeness` — The answer addresses every part of a multi-part question.

**supply-chain**

- `recommendation-is-justified` — Whether the recommended action follows from the evidence and the cited policy. This is the criterion an operations engineer actually cares about, and no deterministic verifier reaches it. Naming it advisory is the honest position; folding it into the mandatory set by proxy would not be.
- `evidence-completeness` — Whether the investigation gathered everything a competent analyst would have gathered before recommending.

