# Verification Review — ARCHITECTURE-SPINE.md

- **Artifact:** `_bmad-output/planning-artifacts/architecture/architecture-OutcomeFuse-2026-09-07/ARCHITECTURE-SPINE.md`
- **Review type:** Live-web verification of committed technical decisions
- **Review date:** 2026-09-07
- **Method:** Direct fetch of PyPI project pages, python.org, the Python devguide, the OpenTelemetry semantic-conventions-genai repository and its generated attribute registry, and Microsoft Learn policy reference pages. No claim below is asserted from model training data; every VERIFIED line cites the URL fetched and what was seen on it.

## Verdict

**No CONTRADICTED items.** Every load-bearing claim in the spine — the Python version floor/ceiling, the litellm `<3.15` constraint that justifies the ceiling, the OpenTelemetry GenAI Development-status and repo-move claim, the Azure APIM streaming-estimation claim that AD-10's streaming ban rests on, the Microsoft Agent Framework past-preview claim, and every version in the Stack table — checked out against live sources. Six caveats are recorded, none of which invalidate an invariant; the two worth acting on are the LangGraph Python 3.14 declaration gap and the APIM tier/token-granularity questions the spine leaves open.

---

## 1. Stack table — row by row

Every row was checked against the live PyPI project page (which renders the current version, the release date, `Requires: Python`, and the trove classifiers). "Current on 2026-09-07" is the spine's own claim; PyPI's "LATEST RELEASE" marker is the test applied.

| Row | Spine says | Live finding | Status |
| --- | --- | --- | --- |
| Python | 3.14 (3.14.7 current; ceiling below 3.15) | 3.14.7 released Aug 5 2026; 3.14 in `bugfix` (stable) phase | **VERIFIED** |
| uv | 0.12.10 | 0.12.10 is LATEST RELEASE, released Sep 5 2026 | **VERIFIED** |
| ruff | 0.16.6 | 0.16.6 is LATEST RELEASE, released Sep 3 2026 | **VERIFIED** |
| pytest | 9.1.1 | 9.1.1 is LATEST RELEASE, released Jun 19 2026 | **VERIFIED** |
| pydantic | 2.13.5 | 2.13.5 is LATEST RELEASE, released Aug 28 2026 | **VERIFIED** |
| PyYAML | 6.0.3 | 6.0.3 is LATEST RELEASE, released Sep 26 2025 | **VERIFIED** |
| typer | 0.27.2 | 0.27.2 is LATEST RELEASE, released Aug 28 2026 | **VERIFIED** (see Caveat C6) |
| Jinja2 | 3.1.6 | 3.1.6 is LATEST RELEASE, released Mar 6 2025 | **VERIFIED** (see Caveat C7) |
| litellm | 1.100.0 | 1.100.0 is the current version | **VERIFIED** |
| SQLite | stdlib `sqlite3` | Standard library module; no external dependency to verify | **VERIFIED (trivially)** |
| langgraph | 1.2.11 | 1.2.11 is LATEST RELEASE, released Aug 11 2026 | **VERIFIED** (see Caveat C1) |
| agent-framework | 1.17.0 | 1.17.0 is LATEST RELEASE, released Sep 3 2026 | **VERIFIED** |
| openai-agents | 0.22.0 — pre-1.0 | 0.22.0 is LATEST RELEASE, released Aug 19 2026 | **VERIFIED** (see Caveat C2) |
| Azure APIM | `llm-token-limit` + `llm-emit-token-metric` | Both policies exist and are documented | **VERIFIED** (see section 5) |

### Per-row detail and maintenance status

**Python — VERIFIED.**
`https://www.python.org/downloads/` — "Download Python 3.14.7"; the release table lists `Python 3.14.7 — Aug. 5, 2026` as the most recent 3.14 patch, and shows 3.14 with maintenance status `bugfix`, first released 2025-10-07, end of support 2030-10.
`https://devguide.python.org/versions/` — 3.14 row: schedule PEP 745, status `bugfix`, first release 2025-10-07. The status key on that page defines `bugfix` as "Once a version has been fully released… This phase is also called **maintenance** mode or **stable** release." So "3.14 is current stable" is exactly right, and 3.14.7 is the correct current patch.

**uv 0.12.10 — VERIFIED and maintained.**
`https://pypi.org/project/uv/` — header reads `uv 0.12.10`; "Key dates — Released: Sep 5, 2026 — LATEST RELEASE". `Requires: Python >=3.8`. Classifiers include `Python :: 3.14` **and** `Python :: 3.15`, so uv is already ahead of the pinned interpreter. Development Status `5 - Production/Stable`. Repo shows 89,560 stars, 2,361 open issues, active. Note the README states plainly: "Yes, uv is stable and widely used in production."

**ruff 0.16.6 — VERIFIED and maintained.**
`https://pypi.org/project/ruff/` — header `ruff 0.16.6`; "Released: Sep 3, 2026 — LATEST RELEASE". `Requires: Python >=3.7`. Classifiers include `Python :: 3.14`. The README's feature list explicitly advertises "🤝 Python 3.14 compatibility". Development Status `5 - Production/Stable`, 49,534 stars.

**pytest 9.1.1 — VERIFIED and maintained.**
`https://pypi.org/project/pytest/` — header `pytest 9.1.1`; "Released: Jun 19, 2026 — LATEST RELEASE". `Requires: Python >=3.10`. Classifiers include `Python :: 3.14` **and** `Python :: 3.15`. Development Status `6 - Mature`.

**pydantic 2.13.5 — VERIFIED and maintained.**
`https://pypi.org/project/pydantic/` — header `pydantic 2.13.5`; "Released: Aug 28, 2026 — LATEST RELEASE". Changelog on the same page confirms `v2.13.5 (2026-08-28)`. `Requires: Python >=3.9`; classifiers include `Python :: 3.14`. Two points of direct relevance to this project: the 2.12.0 notes state "initial Python 3.14 support" and warn "Pydantic V1 is not compatible with Python 3.14 and greater" (irrelevant here — the spine uses V2), and 2.13.0 ships the `pydantic.v1` namespace at 1.10.26 which does support 3.14. Nothing in the changelog suggests 2.13.x is unsuitable for 3.14.

**PyYAML 6.0.3 — VERIFIED and maintained.**
`https://pypi.org/project/PyYAML/` — header `PyYAML 6.0.3`; "Released: Sep 26, 2025 — LATEST RELEASE". `Requires: Python >=3.8`; classifiers include `Python :: 3.14`. Development Status `5 - Production/Stable`. Release is ~11 months old but it is the current release and it declares 3.14 — not a staleness problem, this package simply moves slowly.

**typer 0.27.2 — VERIFIED and maintained.**
`https://pypi.org/project/typer/` — header `typer 0.27.2`; "Released: Aug 28, 2026 — LATEST RELEASE". `Requires: Python >=3.10`; classifiers include `Python :: 3.14`. Only 1 open issue on the repo — actively maintained. Development Status is `4 - Beta` (see Caveat C6). Also worth knowing for the harness CLI: since 0.26.0 Typer **vendors Click** rather than depending on it, and the README warns "some Click functionality will not be available anymore in the future" — so any Click-level assumption in the harness is on notice.

**Jinja2 3.1.6 — VERIFIED, maintenance cadence slow.**
`https://pypi.org/project/Jinja2/` — header `Jinja2 3.1.6`; "Released: Mar 6, 2025 — LATEST RELEASE". `Requires: Python >=3.7`. This is the oldest release in the Stack table (~18 months), and its classifier list stops well short of 3.14 — but classifiers here are simply not maintained (the list has no per-version Python entries at all beyond the generic `Python`), and the `Requires-Python >=3.7` floor does not exclude 3.14. Pallets is an established maintainer org; 78 open issues, active repo. Not stale in the sense of abandoned.

**litellm 1.100.0 — VERIFIED and maintained.** See section 3 for the version-ceiling claim. Actively developed (docs moved to a separate `BerriAI/litellm-docs` repo, Terraform modules published, cosign-signed images).

**langgraph 1.2.11 — VERIFIED as current.**
`https://pypi.org/project/langgraph/` — header `langgraph 1.2.11`; "Released: Aug 11, 2026 — LATEST RELEASE". `Requires: Python >=3.10`. Development Status `5 - Production/Stable`. 41,171 stars, 513 open issues, highly active. See Caveat C1 for the 3.14 gap.

**agent-framework 1.17.0 — VERIFIED.** See section 6.

**openai-agents 0.22.0 — VERIFIED as current.**
`https://pypi.org/project/openai-agents/` — header `openai-agents 0.22.0`; "Released: Aug 19, 2026 — LATEST RELEASE". `Requires: Python >=3.10`; classifiers include `Python :: 3.14`. 29,242 stars, 24 open issues, very active. See Caveat C2.

---

## 2. Claim: Python 3.14 is current stable and 3.15 lands 2026-10-01

**Status: VERIFIED (with a precision note).**

Fetched `https://www.python.org/downloads/`. The "Active Python releases" table reads:

> `3.15 | pre-release | 2026-10-01 (planned) | 2031-10 | PEP 790`
> `3.14 | bugfix | 2025-10-07 | 2030-10 | PEP 745`

Fetched `https://devguide.python.org/versions/`. The Supported versions table reads:

> `3.15 | PEP 790 | prerelease | _2026-10-01_ | _2031-10_ | Hugo van Kemenade`
> `3.14 | PEP 745 | bugfix | 2025-10-07 | _2030-10_ | Hugo van Kemenade`

The devguide page states explicitly: "Dates shown in *italic* are scheduled and can be adjusted." `2026-10-01` for 3.15 is rendered in italic on that page and carries "(planned)" on python.org.

The spine's Deferred/stack rationale phrasing — "3.15" as a near-term event — is therefore correct but should be read as *scheduled*, not *fixed*. The devguide also confirms 3.14 is in `bugfix` phase, which its own status key defines as the stable/maintenance phase, so "3.14 is current stable" is accurate as written. Also confirmed on the same page: `main` is now the future **3.16** (PEP 826, targeted 2027-10-06), so 3.15 is genuinely the next release and not further out.

---

## 3. Claim: litellm requires `<3.15` (the stated reason for the Python ceiling)

**Status: VERIFIED — exactly and unambiguously.**

Fetched the PyPI JSON endpoint `https://pypi.org/pypi/litellm/json`. The `info` block for the current release reads:

> `"requires_python": "<3.15,>=3.10"`, `"version": "1.100.0"`

This is the single most consequential dependency fact in the spine and it is confirmed verbatim from the authoritative metadata, not inferred. The ceiling pin at "below 3.15" is not a guess or a conservatism — litellm's own `Requires-Python` **hard-excludes** 3.15, so a 3.15 interpreter would fail resolution outright. The spine's stated rationale is correct and the ceiling is load-bearing rather than decorative.

Two secondary facts observed in the same payload that are worth carrying into the build:

- litellm's declared floor is `>=3.10`, so the 3.14 pin sits comfortably inside its supported band.
- litellm's `semantic-router` extra is gated `python_full_version < "3.14"`. That extra is not used by this project (nothing in AD-13 or the source tree needs it), but if it were ever pulled in, it would silently drop out on 3.14. Recording it here so the omission is deliberate rather than accidental.

---

## 4. Claim: OTel GenAI semconv is Development, has moved repo, has no releases, and `gen_ai.usage.*_tokens` are not stable

This is the claim AD-8 uses to justify owning the record schema rather than delegating to the specification. All four parts check out.

**4a. Moved repo — VERIFIED.**
Fetched `https://opentelemetry.io/docs/specs/semconv/gen-ai/`. The page title is now literally "**Moved: Generative AI semantic conventions**" and the body carries an IMPORTANT callout:

> "GenAI semantic conventions have moved to the OpenTelemetry GenAI semantic conventions repository. This page has moved and is no longer maintained in this repository."

Every child page (`gen-ai-spans`, `gen-ai-metrics`, `gen-ai-events`, `openai`, `azure-ai-inference`, `aws-bedrock`, `anthropic`, `mcp`, …) is likewise titled "Moved". The relocation is real and total — the spine is right that the canonical location changed.

**4b. No published releases — VERIFIED.**
Fetched `https://github.com/open-telemetry/semantic-conventions-genai`. The Releases panel reads "**No releases published**".
Fetched `https://github.com/open-telemetry/semantic-conventions-genai/releases` directly. The page reads "**There aren't any releases here**".
Corroborating and arguably stronger: the repository README contains a section headed "Schema URL" whose entire content is "**TODO**". A semantic-convention repository that has not yet decided its schema URL has not shipped anything an external schema could safely depend on. AD-8's refusal to bind the decision-record schema to this specification is well founded.

**4c. `gen_ai.usage.input_tokens` / `output_tokens` are NOT stable — VERIFIED.**
Fetched the autogenerated attribute registry at
`https://raw.githubusercontent.com/open-telemetry/semantic-conventions-genai/main/docs/registry/attributes/gen-ai.md`.
The table's Stability column carries a `Development` badge for the two attributes named in the spine:

> `gen_ai.usage.input_tokens` — ![Development] — int — "The number of tokens used in the GenAI input (prompt)."
> `gen_ai.usage.output_tokens` — ![Development] — int — "The number of tokens used in the GenAI response (completion)."

Not merely these two: **every single attribute in the entire `gen_ai.*` registry is marked Development.** So are every enum member of `gen_ai.operation.name`, `gen_ai.output.type`, `gen_ai.provider.name`, `gen_ai.response.status`, and `gen_ai.token.type`. There is no stable surface in the GenAI namespace at all. AD-8's statement that the specification "is still Development-status with no published releases" is, if anything, understated.

**4d. Still actively churning — VERIFIED, and this strengthens the spine's position.**
The repo's commit listing shows changes landing continuously and includes a breaking-shaped change from last week: "gen-ai: deprecate per-message finish reason (#363)", touching both `model/` and `docs/registry/`. 131 open issues, 52 open PRs, 123 contributors, weekly tooling bumps. A specification deprecating attributes on a weekly cadence with no tagged release is precisely the hazard AD-8 names — FR104's promise that a published reason code keeps its meaning could not survive delegation to it.

**Consequence for the Deferred entry.** The spine defers OTel export "until the GenAI semantic conventions reach a tagged stable release." As of today no tag exists and the schema URL is unresolved, so that deferral has no near-term trigger. That is a correct and honest reading of the evidence, not an evasion.

---

## 5. Claim: APIM `llm-token-limit` returns per-request token counts, and with `stream: true` BOTH prompt and completion tokens are ESTIMATED

This is the claim that an entire invariant rests on — AD-10 bars streaming on the evidence path because of it. It is the highest-stakes item in this review.

**5a. Streaming estimates both prompt AND completion tokens — VERIFIED VERBATIM.**

Fetched `https://learn.microsoft.com/en-us/azure/api-management/llm-token-limit-policy`. Under "Considerations for token counts and estimation":

> "**Streaming**: When streaming is enabled in the API request (`stream: true`), prompt tokens are **always estimated regardless of the `estimate-prompt-tokens` setting**. **Completion tokens are also estimated when responses are streamed.**"

Both halves of the spine's claim are stated explicitly by Microsoft, in the same sentence pair. The wording "always estimated regardless of the setting" is stronger than the spine's phrasing — it means the estimation cannot be configured away. AD-10's conclusion that streaming "would make FR79 a reconciliation between two guesses and leave F15 buying nothing" is correct on the evidence, and the invariant is soundly grounded. Page `ms.date: 2026-04-01`, last updated `2026-06-26` — current documentation, not an archived snapshot.

Two additional streaming hazards on the same page reinforce, rather than undermine, the ban:

- "**Image input**: … when streaming is enabled or `estimate-prompt-tokens` is set to `true`, the policy **overcounts each image as a maximum of 1200 tokens**." A fixed 1200-token overcount per image would corrupt any cost figure derived from a streamed multimodal run.
- From `llm-emit-token-metric`: "Certain LLM endpoints support streaming of responses. **If the stream is unexpectedly interrupted or terminated, the captured token counts are inaccurate.**" And: "Certain OpenAI models, especially when streaming, don't include token counts in the response by default. To receive the token counts, set the `include_usage` parameter to `true`."

**5b. Per-request token counts — VERIFIED, with a granularity caveat.**

The same page documents four output surfaces on `llm-token-limit`:

> `tokens-consumed-header-name` — "The name of a response header whose value is **the number of tokens consumed by both prompt and completion**. The header is added to response only after the response is received from backend."
> `tokens-consumed-variable-name` — "A variable initialized to the estimated prompt token count in the `backend` section (or zero if `estimate-prompt-tokens` is `false`), **updated with the actual reported count in the `outbound` section**."
> `remaining-tokens-header-name` / `remaining-tokens-variable-name` — remaining tokens against `tokens-per-minute`.
> `remaining-quota-tokens-header-name` / `remaining-quota-tokens-variable-name` — remaining tokens against `token-quota`.

So yes: the policy does surface a **per-request, gateway-measured** token count to the caller, which is exactly what AD-10's "measured" independence label and FR79's reconciliation require. And crucially, with `estimate-prompt-tokens="false"` and streaming off, the page states: "The policy uses **actual token usage values from the `usage` section of the LLM API response**." That is a real measurement, not an estimate — the non-streaming evidence path gets what the spine promises.

The caveat is granularity — see Caveat C4.

**5c. Policy existence, scope, and tier availability — VERIFIED with a tier caveat.**

- `llm-token-limit`: inbound section; scopes global/workspace/product/API/operation; gateways classic, v2, self-hosted, workspace. **APPLIES TO: Developer | Basic | Basic v2 | Standard | Standard v2 | Premium | Premium v2.**
- `llm-emit-token-metric` (`https://learn.microsoft.com/en-us/azure/api-management/llm-emit-token-metric-policy`): inbound section; **APPLIES TO: All API Management tiers**; emits custom metrics to Application Insights; "Token count metrics are model- and provider-dependent and can include **total, prompt, and completion tokens**." Prerequisites include App Insights integration plus "Enable custom metrics with dimensions in Application Insights."

Both policies support "OpenAI Chat Completions or Responses API" schemas, which covers the Azure OpenAI endpoints in the spine's deployment diagram. See Caveats C3 and C5.

---

## 6. Claim: Microsoft Agent Framework core Python packages are past preview; openai-agents is still pre-1.0 with no stability statement

**6a. agent-framework past preview — VERIFIED, and the spine's precision is notable.**

Fetched `https://pypi.org/project/agent-framework/`. Version `1.17.0`, "Released: Sep 3, 2026 — LATEST RELEASE". Development Status classifier: **`5 - Production/Stable`**. `Requires: Python >=3.10`; classifiers run through `Python :: 3.14`. Maintained by Microsoft (6 maintainers, `af-support@microsoft.com`).

The README states the preview boundary directly:

> "Released packages such as `agent-framework`, `agent-framework-core`, and `agent-framework-foundry` **no longer require `--pre`**, while preview connectors such as `agent-framework-copilotstudio` **still do**."

The spine's careful wording — "**core** Python packages are past preview" — is exactly right and is not an overclaim. The core is GA; specific connectors (Copilot Studio) remain preview and still need `--pre`. Anyone building the `adapters/host/agentframework/` module should stay inside the core surface; reaching for a preview connector would silently reintroduce preview risk that the Stack table does not cover. Supported platforms declared: Python 3.10+, Windows/macOS/Linux — the developer-workstation environment in the deployment diagram is covered.

**6b. openai-agents pre-1.0 — VERIFIED; "no stability statement" — VERIFIED to the limit of a negative claim.**

Version `0.22.0`, released Aug 19 2026 — unambiguously pre-1.0. Notably, the PyPI classifier list contains **no `Development Status` classifier at all** (compare langgraph, agent-framework, ruff, uv, pydantic, PyYAML and Jinja2, all of which declare `5 - Production/Stable`, and pytest which declares `6 - Mature`). The project therefore declines to assert a maturity level even in metadata.

The README and PyPI metadata contain no versioning-policy or stability section — contrast langgraph, whose README links an explicit "Releases & Versioning" policy at `docs.langchain.com/oss/python/release-policy` and `/versioning`. The absence is genuine on the surfaces checked. Being a negative claim, it can only be verified as "no such statement on the package's own PyPI page or README" rather than "no such statement exists anywhere"; a policy could live in the docs site without surfacing here. Marked **VERIFIED with the scope of the negative stated**, and it does not weaken the spine — the spine's conclusion (pin exactly, never a range) is the correct response to metadata this reticent, and is if anything better justified than the spine argues.

This directly supports **Open Question Q-A**: the reasoning that `openai-agents` is the riskiest of the three adapters, and that the third adapter belongs in the §4.3 cut order, is corroborated by evidence rather than merely asserted.

---

## 7. Other named technologies, APIs and platform capabilities

| Item | Where | Finding | Status |
| --- | --- | --- | --- |
| `sqlite3` (stdlib), one DB file per run, append-only discipline | AD-16 | `sqlite3` is a Python standard-library module; "one file per database" is SQLite's native storage model. The append-only rule is a project-imposed discipline on the writer, not a platform capability, so there is nothing external to falsify. | **VERIFIED (trivially)** |
| Jinja2 static HTML generation with autoescaping | AD-17 | Jinja2 3.1.6 confirmed current (§1). The README lists "HTML templates can use autoescaping to prevent XSS from untrusted user input" and "A sandboxed environment can safely render untrusted templates" — the capability exists. | **VERIFIED**, see Caveat C7 |
| Application Insights as APIM metric sink | Deployment diagram, F15 | Confirmed as a documented prerequisite of `llm-emit-token-metric`: "Your API Management instance must be integrated with Application insights." | **VERIFIED**, see Caveat C5 |
| Azure OpenAI / model endpoints behind APIM | Deployment diagram | Both policies document support for "OpenAI Chat Completions or Responses API" schemas; `azure.ai.openai` is a recognised provider value in the OTel registry. The topology is a supported configuration. | **VERIFIED** |
| ULIDs for run/contract/case ids | Consistency Conventions | A published, stable identifier specification; no version or vendor claim is made that could go stale. | **VERIFIED (no risk)** |
| SHA-256, canonical JSON, RFC 3339 UTC | AD-6, Consistency Conventions | Stable published standards; no currency risk. | **VERIFIED (no risk)** |
| Ports-and-adapters / hexagonal paradigm | Design Paradigm | An architectural pattern, not a product; nothing to verify for currency. | **N/A** |
| PRD/brief FR and NFR references (FR1–FR106, NFR1–NFR12) | Throughout | Internal cross-references to sibling planning artifacts. Out of scope for *web* verification; belongs to a reconcile pass, and `reconcile/reconcile-prd.md` exists for that purpose. | **OUT OF SCOPE** |

---

## Caveats

None of these contradict the spine. Each is a place where the spine is silent, or where a live source adds a constraint the spine has not yet absorbed.

**C1 — LangGraph does not declare Python 3.14. [MEDIUM]**
`https://pypi.org/project/langgraph/` lists `Requires: Python >=3.10` and classifiers `Python :: 3.10`, `3.11`, `3.12`, `3.13` — and then jumps straight to `Python :: Implementation :: CPython`. **There is no `Python :: 3.14` classifier.** Compare every other pinned library in the Stack table: ruff, uv, pytest, pydantic, PyYAML, typer, agent-framework and openai-agents all declare 3.14 explicitly. LangGraph alone does not.

This is not a contradiction — the spine never claims langgraph supports 3.14, and `Requires-Python >=3.10` does not *exclude* 3.14, so installation will succeed. But the Stack table pins Python 3.14 and pins langgraph 1.2.11 on adjacent rows, which implies a compatibility that the package's own metadata declines to assert. Classifiers are the maintainer's statement of what they test. The gap means the LangGraph adapter is the one host integration running on an interpreter its framework has not declared support for — and under AD-15, an adapter that cannot pass conformance cannot produce a reportable run, so a 3.14-specific failure here would take a whole comparison arm with it. Worth a smoke test on 3.14 before adapter work begins, and worth noting alongside Q-A's cut-order discussion.

**C2 — "No stability statement" is a negative claim, verified only within scope. [LOW]**
See §6b. Confirmed absent from the PyPI page, metadata classifiers and README. Cannot be confirmed absent from the project's full documentation site, which was not fetched. The spine's conclusion is unaffected and arguably strengthened.

**C3 — The APIM tier is unspecified, and `llm-token-limit` is not available on every tier. [MEDIUM]**
`llm-token-limit` declares "**APPLIES TO: Developer | Basic | Basic v2 | Standard | Standard v2 | Premium | Premium v2**" — the **Consumption** tier is absent from that list, while `llm-emit-token-metric` declares "APPLIES TO: All API Management tiers" and its gateway list includes `consumption` where `llm-token-limit`'s does not. The spine's Deployment section commits to "a single Azure subscription hosting the APIM instance" and calls a working APIM instance a "critical-path dependency before any evaluation-set run," but names no tier. If Consumption is chosen for cost reasons — a plausible instinct for a hackathon-scale MVP — `llm-token-limit` is simply unavailable, and AD-10's "measured" independence label collapses to "self-reported" (FR80) for every run. The tier is a load-bearing choice that the spine currently leaves implicit. Recommend naming it in the Deployment section.

**C4 — `llm-token-limit` surfaces a combined prompt+completion figure, not a per-request split. [MEDIUM]**
`tokens-consumed-header-name` is documented as "the number of tokens consumed by **both** prompt and completion" — one number, not two. A prompt/completion breakdown is available from `llm-emit-token-metric`, but that is an *Application Insights custom metric*, i.e. a dimensioned, aggregated time series, not a value returned inline on the response.

The spine does not claim a per-request split, so nothing here is contradicted. But AD-13 pins a cost table and records it in the manifest precisely so cost can be computed, and cost tables are priced per-direction (input vs output tokens at different rates). Reconciling a governor-side directional estimate against a gateway-side *combined* total under FR79 is a coarser comparison than reconciling like against like. Whether the combined figure is sufficient for FR79, or whether the App Insights metric path must be joined per-run, is a design question the spine has not yet answered. Flagging it for the `adapters/metering/` work rather than proposing a resolution here.

**C5 — Application Insights custom-metric limits can silently discard metering data. [MEDIUM]**
From `llm-emit-token-metric`: "API Management limits each dimension to **100 unique values** and each metric namespace to **1,000 active time series**. When either limit is reached, any new dimension values or time series are **not tracked, and the corresponding metric data is silently discarded**." Also: a maximum of **5 custom dimensions** per policy, and active time series multiply as the product of unique dimension values.

The word to notice is *silently*. If the metering adapter dimensions by run id or case id — the natural choice for per-run attribution, and there are a lot of runs across four workloads plus ablations plus baseline arms — the 100-unique-values-per-dimension ceiling is reachable, and the failure mode is missing data with no error. Under AD-10 that ought to degrade the run's label to self-reported (FR80) rather than yield a figure quietly computed from partial data. Nothing in AD-10 or AD-20 currently describes *detecting* silent metric loss. Worth an explicit check in the metering adapter, and worth choosing low-cardinality dimensions.

**C6 — typer is pre-1.0 and classified Beta, but is not flagged the way openai-agents is. [LOW]**
`typer 0.27.2` carries Development Status `4 - Beta` and a `0.x` version. The Stack table annotates `openai-agents` with "pre-1.0; pin exactly, never a range" but attaches no equivalent note to typer, even though both are pre-1.0 and typer's classifier is the weaker of the two claims. The exposure is far smaller — typer is a harness CLI dependency, not a governed-path component, and a breaking change there cannot corrupt a decision record — so this is a consistency nit rather than a risk. If the "pin exactly" discipline is a rule, it should read as a rule; if it is specific to host adapters, saying so would make the asymmetry deliberate.

**C7 — Jinja2 autoescaping is opt-in, not the default. [LOW]**
AD-17 states "HTML generation autoescapes; record content is untrusted input." Jinja2's own README words the capability as "HTML templates **can use** autoescaping" — it is a constructor option (`autoescape=True` / `select_autoescape()`), not the default for a bare `Environment`. The spine is stating a *requirement on the implementation*, which is the right thing for a spine to do, and the requirement is achievable. Recording it only so the implementer does not read "autoescapes" as "does so automatically" and skip the flag — the consequence would be XSS in the F14 artifact rendered from untrusted record content, which is exactly the risk AD-17 exists to close.

---

## Sources fetched

| # | URL | Used for |
| --- | --- | --- |
| 1 | `https://www.python.org/downloads/` | 3.14.7 current; 3.15 planned 2026-10-01 |
| 2 | `https://devguide.python.org/versions/` | 3.14 `bugfix`/stable; 3.15 `prerelease`; italic = scheduled |
| 3 | `https://pypi.org/pypi/litellm/json` | `requires_python: "<3.15,>=3.10"`; version 1.100.0 |
| 4 | `https://pypi.org/project/uv/` | 0.12.10, Sep 5 2026, 3.14 + 3.15 classifiers |
| 5 | `https://pypi.org/project/ruff/` | 0.16.6, Sep 3 2026, "Python 3.14 compatibility" |
| 6 | `https://pypi.org/project/pytest/` | 9.1.1, Jun 19 2026, 3.14 + 3.15 classifiers |
| 7 | `https://pypi.org/project/pydantic/` | 2.13.5, Aug 28 2026, 3.14 classifier, changelog |
| 8 | `https://pypi.org/project/PyYAML/` | 6.0.3, Sep 26 2025, 3.14 classifier |
| 9 | `https://pypi.org/project/typer/` | 0.27.2, Aug 28 2026, Beta classifier, vendored Click |
| 10 | `https://pypi.org/project/Jinja2/` | 3.1.6, Mar 6 2025, autoescaping capability |
| 11 | `https://pypi.org/project/langgraph/` | 1.2.11, Aug 11 2026, **no 3.14 classifier** |
| 12 | `https://pypi.org/project/agent-framework/` | 1.17.0, Sep 3 2026, Production/Stable, `--pre` boundary |
| 13 | `https://pypi.org/project/openai-agents/` | 0.22.0, Aug 19 2026, no Development Status classifier |
| 14 | `https://opentelemetry.io/docs/specs/semconv/gen-ai/` | "Moved" notice on every page |
| 15 | `https://github.com/open-telemetry/semantic-conventions-genai` | "No releases published"; Schema URL "TODO" |
| 16 | `https://github.com/open-telemetry/semantic-conventions-genai/releases` | "There aren't any releases here" |
| 17 | `https://github.com/open-telemetry/semantic-conventions-genai/tree/main/docs` | Docs structure, registry location |
| 18 | `https://github.com/open-telemetry/semantic-conventions-genai/tree/main/docs/registry` | Registry index |
| 19 | `https://raw.githubusercontent.com/.../docs/registry/attributes/gen-ai.md` | All `gen_ai.*` attributes marked Development |
| 20 | `https://learn.microsoft.com/en-us/azure/api-management/llm-token-limit-policy` | Streaming estimates both; tokens-consumed; tier list |
| 21 | `https://learn.microsoft.com/en-us/azure/api-management/llm-emit-token-metric-policy` | Token metrics; App Insights limits; streaming accuracy |
