# OutcomeFuse

A quality-gated budget runtime for AI agents.

An agent run stops when a declared **Outcome Contract** is satisfied, not when a
model decides it feels finished. The contract states a quality floor in terms
that can be checked by machine, and the runtime refuses to relax it.

## Status

The evidence apparatus was built before the runtime on purpose: a benchmark
authored after the thing it measures is not evidence. That decision is the
reason this README can tell you the product did not work.

**The held-out evaluation is complete, and every workload was refused.** The
detail is in [Results](#results). Read that before reading anything else here.

| Epic | What it is | State |
| --- | --- | --- |
| E0 | Canonicalisation and hashing — one serialiser behind every hash | done |
| E1a | Cases, derived answer keys, rubric, baseline, four contracts | done |
| E3 | Verifier registry, safe contract loading, coverage review | done |
| E1b | Freeze everything in one operation | **done — final** |
| E2 | Record spine: append-only log, per-run chain, run seal | done |
| E4 | Budget ledger, Policy, Loop Fuse | done |
| E5 | Quality Gate | done |
| E6 | Ports, reference adapter, conformance battery, workload tools | done |
| E7 | Enforcing driver, Tool Governor, failure posture | done |
| E8 | Harness, run manifest, OFF/ON benchmark, preregistration | done |
| E9 | Evidence store, counter-metrics, blind review tooling | done |
| E11 | Shadow mode | done |
| E15 | Submission artifact | done |
| E10 | Host adapters beyond the reference adapter | **cut** |
| E12 | Context governor, preflight planner, semantic dedup | **cut** |
| E13 | Gateway metering | **cut** |
| E14 | Static viewer | **cut** |

The cuts were planned cut positions, not abandoned work, and each is disclosed
in `src/outcomefuse/submission/disclosures.py` rather than left for a reader to
notice. E13's absence is why every figure is labelled `self-reported`.

## Results

Four workloads, eight held-out cases each, both arms executed live against
gpt-5 and gpt-5-mini. `scripts/report.py --split evaluation` reproduces this
from the committed proof cards. Positive is a **reduction**, so a negative
token figure means the governed arm spent more.

| workload | cases | baseline | governed | token cut | cost cut | escalation | publishable |
| --- | --- | --- | --- | --- | --- | --- | --- |
| supply-chain | 7 | 5 pass | 5 pass | **+30.2%** | +75.9% | 0.43 | **no** |
| data-sql | 8 | 6 pass | 6 pass | **−23.3%** | +46.9% | 0.62 | **no** |
| doc-research | 8 | 1 pass | 1 pass | **−32.7%** | +41.7% | 1.00 | **no** |
| code-triage | 8 | 0 pass | 0 pass | — | — | — | **no card at all** |

Only supply-chain reduced tokens at all. The other two spent more to reach the
same quality, because escalating to the larger model costs more than starting
there. Cost still fell everywhere, which is the routing effect, not the
governing one.

All four breached the escalation-rate threshold of 0.30 preregistered in
`preregistration/prereg-1.yaml`. Three fell below the declared minimum case
count. The threshold stands: one revised after seeing the number it refuses is
not a threshold.

Three findings matter more than the table:

**The governor saved nothing.** Every campaign attributes 100% of the token
saving to `agent-stopped-unaided`. The cost reduction is model routing — running
the cheaper model — not quality-gated governing. On doc-research, routing
accounts for 103.2% of the saving and the agent's own stopping *costs* 3.2%.

**The sufficiency stop never fires early.** The frozen prompts ask for one
deliverable at the end, so the gate scores what the agent already decided to
hand over. It confirms; it does not cause. A confirming verdict and a real early
stop leave identical decision events, so each gate verdict now records whether
it was consulted `mid-run` or `at-submission`, and FR84's sufficiency-stop
demonstration is refused unless a run shows the former. No run does.

**code-triage's 0/8 is the instrument, not the models.** `fix-summary-substantive`
is a regex demanding one of ten literal verbs that the frozen prompt never
discloses. Nine of ten sampled deliverables failed it; all ten were accurate
diagnoses. The list spells `initialise` while models write `initialize`, and
`\bvalidate\b` does not match `validate_lines` because the underscore is a word
character — so a summary naming the broken function is rejected for naming it.
It is frozen, so it is disclosed and worked around, never fixed.

## What is pending

| Item | Who | Why it is not done |
| --- | --- | --- |
| Blind review (FR69) | a human | The gate is the thing under suspicion, so it cannot grade itself. Packet is prepared at `runs/review/supply-chain/`; run `scripts/blind_review.py record supply-chain` after judging. Until then `false-sufficiency-rate` reports **not measured**, never 0. |
| The video | a human | `submission/SCRIPT.md` is the shooting script: four beats, 120s, disclosures rendered. Narration wording lives in `submission/narration.yaml`. |
| `tool-suppression-error-rate` | nobody | Permanently unmeasurable here. The models never repeated a tool call, so nothing was suppressed. Reported as **not measured**, not as a rate of zero. |
| `verdict-applied` events | deferred | AD-2's canonical order expects one and no driver emits it, so `check_order` reports a finding per decision on correct logs. Pre-existing since E7. |

## Verifying this yourself

Nothing above needs to be taken on trust. The run evidence is committed —
126 sealed databases, both arms, calibration and evaluation.

```pwsh
uv run pytest -q                              # 1388 passed
uv run ruff check src tests freeze scripts
uv run python freeze/freeze.py --check        # 42e4a45b…
uv run python scripts/mutate_check.py         # 40 mutations, all caught
uv run python scripts/report.py --split evaluation
```

Every run seal verifies from a clean clone, which is what makes "the benchmark
was frozen before the governor existed" checkable rather than asserted. The
calibration runs are published for the same reason.

## Layout

| Path | Holds |
| --- | --- |
| `src/outcomefuse/core/` | Canonicaliser, verifier registry, contract loader, record spine |
| `src/outcomefuse/runtime/` | Enforcing driver, shadow driver, baseline recorder |
| `src/outcomefuse/harness/` | Campaign runner, proof card, counter-metrics, reportability |
| `src/outcomefuse/submission/` | Figures, shooting script, frozen-defect disclosures |
| `contracts/` | One real Outcome Contract per workload |
| `cases/` | Four workload corpora, 80 cases, derived answer keys |
| `freeze/` | Rubric, baseline definition, prompt templates, derivation scripts |
| `preregistration/` | Targets and thresholds, fixed before the evaluation set was touched |
| `runs/` | Sealed decision logs, deliverables, proof cards — the evidence |
| `submission/` | Narration source and the rendered shooting script |
| `tests/` | Everything above, including the freeze apparatus itself |


## Working on it

```pwsh
uv sync
uv run pytest -q
uv run ruff check src tests freeze
```

The library supports Python 3.12 and later, but the pinned development
interpreter is **3.14.6** because the record spine asserts **SQLite ≥ 3.51.3**
at store open and 3.12 bundles 3.49.1. A conforming store cannot be opened on
an older SQLite; that refusal is the designed behaviour, not a bug.

Two scripts guard the case set and must pass before the freeze:

```pwsh
uv run python freeze/check_cases.py        # case-set integrity
uv run python freeze/derive_answer_keys.py # regenerate all 80 answer keys
```

Answer keys are **derived, never hand-asserted**. Editing a corpus without
regenerating its keys is caught by the test suite.

## The freeze

The evidence apparatus is content-hashed and frozen (FR65):

```pwsh
uv run python freeze/freeze.py --check     # verify nothing has drifted
```

**The freeze may be amended only while no run of any kind exists.** From the
moment the first run is recorded it is final: a defect found afterwards is
worked around and disclosed, never fixed. Runs exist, so it is final now.

That rule is why `code-triage` reports 0/8 against a rubric known to be broken,
and why the fix that would have improved our own numbers was not applied. A
benchmark you may repair after seeing your score is not a benchmark.

The freeze is reproducible across platforms and SQLite versions, which is what
makes drift detection meaningful rather than noisy. Verify it yourself:

```pwsh
docker run --rm -v "${PWD}:/w" -w /w python:3.12-slim sh /w/freeze/verify-linux.sh
```

## Two rules worth knowing before contributing

**A contract executes no code.** A criterion selects a verifier by name from a
closed registry and parameterises it declaratively. No import path, expression
or callable crosses the contract boundary, and contracts load through a safe
loader under bounded size and depth.

**Verification mode is a property of the verifier type**, fixed in the registry
rather than asserted per contract — which is what stops `reference-backed` being
claimed for a check that never compared against a known-correct value.
