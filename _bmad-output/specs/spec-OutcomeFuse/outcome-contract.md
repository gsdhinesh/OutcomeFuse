# Outcome Contract

Companion to [SPEC.md](SPEC.md). Holds the contract's declared field set, the closed verifier registry and its fixed mode mapping, validation rules, and the pre-freeze coverage review that settles registry breadth.

## Declared fields

- Task goal
- Required deliverable structure
- **Mandatory** criteria and evidence fields — together these constitute the quality floor
- **Optional / enrichment** criteria and fields, declared separately from mandatory ones
- `max_tokens`, `max_estimated_cost`
- `verification_reserve` (`max_tokens`, `max_estimated_cost`) — optional; where omitted, supplied by a deterministic default derived from the contract's ceilings and recorded with the run
- Permitted tools, and which are declared deterministic and which side-effecting
- `max_tool_calls`, `max_iterations`
- Escalation policy
- `human_approval_conditions`
- `approval_timeout` and its `on_timeout` behaviour

The mandatory-versus-optional classification lives **in the contract**, not in the Preflight Planner. The planner is cuttable and the requirements that consume the classification are not; a protected requirement may not take its meaning from a component that can be cut.

## Verifier registry

Closed and project-owned. A criterion **selects** an entry and parameterises it declaratively. No import path, expression or callable reference crosses the contract boundary. The verification mode is a property of the verifier type, fixed here — not asserted per contract.

| Verifier type | Mode |
| --- | --- |
| `field-present` | `constraint-backed` |
| `type-is` | `constraint-backed` |
| `numeric-range` | `constraint-backed` |
| `set-membership` | `constraint-backed` |
| `regex-match` | `constraint-backed` |
| `exact-match-against-answer-key` | `reference-backed` |
| `citation-resolves` | `reference-backed` |

Every verifier is a **pure function of its declared arguments**. `citation-resolves` receives the run's derived citable index as an argument supplied by the caller; it never fetches it and never touches the evidence store. The citable index is a core-owned typed model — identifiers, citation targets, content hashes — built by the driver, canonicalised and hashed, with its hash appended before any verifier is invoked. Regex verifiers run against bounded input under a step budget.

## Validation

- Contracts load through a **safe loader only** — no tag resolution, no object construction — under bounded input size and nesting depth. Parsing precedes the run manifest, so a rejection is recorded against the contract's content hash rather than against a run.
- A malformed contract is rejected before execution begins.
- A mandatory criterion naming an unregistered verifier type is rejected. A criterion for which no deterministic verifier exists cannot be mandatory; it may be declared **advisory** instead, recorded and fed to the counter-metrics, never gating.
- A well-formed but internally unsatisfiable contract — a quality floor unreachable within the declared ceiling — warns before executing rather than being discovered mid-run.
- A contract is immutable for the duration of a run and carries a stable identifier and version recorded alongside every result produced under it.
- No credential appears in a contract.

## Pre-freeze coverage review

Registry breadth is proven, not guessed. Before the freeze, one Outcome Contract is authored **per committed workload** — the contract you would actually run, not a sketch — and every intended criterion is classified:

- **E** — expressible with an existing verifier today
- **N** — a new deterministic type is demonstrably needed
- **A** — advisory

The review explicitly covers the criteria most easily missed because they are semantic: root-cause correctness, query-result correctness, code-location correctness, evidence completeness, and whether a conclusion is *supported* rather than merely present.

**At most three** additional verifier types are admissible, and only for a demonstrated gap. Each must be reusable beyond a single case, deterministic over identical canonical inputs, project-implemented, free of network, filesystem, model and clock I/O, bounded and declarative in its parameters, fixed in mode by the registry, and covered by positive, negative, boundary, malformed-input and replay tests. `semantic-match`, `llm-judge`, `root-cause-quality` and `citation-supports-claim` are barred unless reducible to deterministic comparison against frozen structured reference data.

A per-workload **verification-mode coverage report** — counts and percentages of mandatory criteria that are reference-backed versus constraint-backed — is published with the freeze. A workload is **predominantly constraint-backed** where its constraint-backed mandatory count exceeds its reference-backed count, and is reported as such wherever its results are claimed. A workload with zero reference-backed mandatory criteria may still be evaluated but may not be used to imply that OutcomeFuse independently established semantic correctness.

The registry, its tests and the coverage report are content-hashed in the **same operation** as the rubric and answer keys. A frozen rubric whose criteria take their executable meaning from an unfrozen registry is not frozen.

## The honest limit

The gate is fully sound only where a criterion can be checked against a known-correct value. In the MVP that holds for `reference-backed` criteria because the cases are synthetic and the answer keys were authored alongside them. On a production workload with no answer key, mandatory criteria collapse toward `constraint-backed` verification — presence, type, constraint — which is a meaningfully weaker guarantee and one adjacent products already provide. Closing that is an open question, not a solved problem.
