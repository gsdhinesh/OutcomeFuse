# OutcomeFuse

A quality-gated budget runtime for AI agents.

An agent run stops when a declared **Outcome Contract** is satisfied, not when a
model decides it feels finished. The contract states a quality floor in terms
that can be checked by machine, and the runtime refuses to relax it.

## Status

Pre-MVP. The evidence apparatus is built before the runtime on purpose: a
benchmark authored after the thing it measures is not evidence. Build order is
`E0 → E1a → E3 → E1b → E2 → …`, and E1b is the point of no return.

| Epic | What it is | State |
| --- | --- | --- |
| E0 | Canonicalisation and hashing — one serialiser behind every hash | done |
| E1a | Cases, derived answer keys, rubric, baseline, four contracts | done |
| E3 | Verifier registry, safe contract loading, coverage review | in progress |
| E1b | Freeze everything in one operation | not started |
| E2 | Record spine | not started |

## Layout

| Path | Holds |
| --- | --- |
| `src/outcomefuse/core/canon/` | The one canonicaliser: canonical JSON, digests, file manifests |
| `src/outcomefuse/core/verify/` | The closed verifier registry, path grammar, citable index |
| `src/outcomefuse/core/contract/` | Outcome Contract model and its safe loader |
| `contracts/` | One real Outcome Contract per workload |
| `cases/` | Four workload corpora, 80 cases, derived answer keys |
| `freeze/` | Rubric, baseline definition, prompt templates, derivation scripts |
| `tests/` | Everything above, including the freeze apparatus itself |

## Working on it

```pwsh
uv sync
uv run pytest -q
uv run ruff check src tests freeze
```

Two scripts guard the case set and must pass before the freeze:

```pwsh
uv run python freeze/check_cases.py        # case-set integrity
uv run python freeze/derive_answer_keys.py # regenerate all 80 answer keys
```

Answer keys are **derived, never hand-asserted**. Editing a corpus without
regenerating its keys is caught by the test suite.

## Two rules worth knowing before contributing

**A contract executes no code.** A criterion selects a verifier by name from a
closed registry and parameterises it declaratively. No import path, expression
or callable crosses the contract boundary, and contracts load through a safe
loader under bounded size and depth.

**Verification mode is a property of the verifier type**, fixed in the registry
rather than asserted per contract — which is what stops `reference-backed` being
claimed for a check that never compared against a known-correct value.
