---
title: "OutcomeFuse — Brief Addendum"
status: draft
created: 2026-09-02
updated: 2026-09-03
---

# OutcomeFuse — Addendum

Depth captured during the brief conversation that belongs downstream (PRD, architecture, solution design) or earned a place but did not fit the two-page brief. Sourced from [doc/info.md](../../../../doc/info.md) and the discovery session.

---

## 1. Component specifications

The **runtime policy** — "is another unit of AI work worth paying for, given this contract?" — is the product. The Outcome Contract is its input; everything from the Preflight Planner down is an enforcement mechanism acting on the policy's decision. Specifications below are for the contract and the mechanisms; the policy itself is one question applied before every unit of work.

### Outcome Contract — fields

`task_goal` · `quality_floor` · `max_tokens` / `max_estimated_cost` · `allowed_tools` · `max_tool_calls` · `max_iterations` · `escalation_policy` · `human_approval_conditions`

### Preflight Planner

- Generates a small, typed execution graph
- Assigns an estimated token/tool envelope per step
- Separates mandatory evidence from optional enrichment

_Design note: the planner is itself a model pass and therefore counts against the net-savings figure. Its envelope must be measured, not assumed negligible._

### Budget Ledger

- Maintains `allocated`, `spent`, `reserved`, `remaining`
- Holds a protected reserve for final synthesis and quality verification, so verification can never be starved by earlier overspend
- Rejects a proposed step when expected benefit is low, duplicated, unsafe, or unaffordable

### Context Governor

- Selects only evidence needed for the current step
- Compresses tool output into structured "evidence capsules"
- Preserves citations, identifiers, numbers, and policy clauses verbatim — compression must never drop an attributable fact
- LLMLingua-style compression (budget controller plus sentence- and token-level compression) is a candidate implementation

### Model Governor

- Starts on the lowest-cost eligible model
- Escalates on task complexity, low confidence, policy criticality, or a failed quality evaluation
- Candidate integration: Foundry Model Router (Balanced / Quality / Cost modes). Benchmark quality, cost, and latency against the workload baseline before trusting it
- For MVP reliability, prefer two explicit model deployments with Model Router behind a feature flag

### Tool Governor

- Canonicalizes tool name plus arguments into a stable key
- Reuses cached deterministic results
- Prevents duplicate and semantically equivalent calls
- Rejects optional calls once sufficient evidence has been acquired
- Measurable via Tool Selection, Tool Call Accuracy, Tool Output Utilization, Tool Call Success, and Task Navigation Efficiency evaluators

### Loop Fuse

- Computes a progress fingerprint per iteration: evidence gained, task state changed, quality delta
- Halts on repeated state, no new evidence, repeated tool arguments, budget exhaustion, or iteration limit
- Rationale: autonomous loops must always be bounded — completion criteria can fail, models can stall, evaluators are probabilistic

### Quality Gate

- Evaluates task completion, task adherence, groundedness / evidence coverage, and tool-use quality
- `pass` → stop immediately
- `fail` + budget available → targeted retry or model escalation
- `fail` + no safe budget → disclose partial result or request human intervention
- Combine bespoke rubric evaluators with built-in quality and safety evaluators; report pass/fail counts and per-model token usage

---

## 2. Production stack (mostly deferred — one slice in MVP)

The MVP otherwise runs as an in-process governor. **In scope: token metering via the APIM AI gateway**, so the headline savings figure is measured at the gateway rather than self-reported by the governor being evaluated. Redis-backed tool caching is the fallback slice if APIM proves unstable. Everything else below is the credible production path for the viability story, not demo work.

| Layer | Service |
|---|---|
| Orchestration, middleware, bounded loop | Microsoft Agent Framework |
| Agents and models | Foundry Agent Service / Azure OpenAI |
| Identity, quotas, policy, token metrics, semantic caching | Azure API Management AI gateway |
| Tool-result / semantic response cache | Azure Managed Redis |
| Per-step telemetry | Application Insights + Azure Monitor + OpenTelemetry |
| Offline A/B evaluation and quality gates | Foundry Evaluations |
| Governor API and demo services | Azure Container Apps or Functions |
| Contracts, ledgers, experiment results | Cosmos DB or PostgreSQL |
| Identity and secrets | Entra ID / managed identity / Key Vault |

Foundry tracing captures inputs, outputs, tool usage, retries, latency, cost, and token consumption; its OpenTelemetry conventions cover planning, agent invocation, tool execution, and memory operations.

---

## 3. Evaluation methodology

**Baseline definition — freeze before any comparison:** prompt, tools, dataset, model version, temperature and settings. The baseline sends full retrieved context into each step and uses one capable model throughout. It may re-call tools. It uses a conventional evaluator/retry loop with a maximum-iteration safety limit. It must be a *reasonable* agent, not a strawman.

**Method**

- Run baseline and governed versions on the same frozen dataset, with repeats per case
- Capture model/version, tokens, cached tokens, tool calls, retries, duration, and outcome
- Deterministic field-level validation for required recommendations and evidence — preferred over model-judged scoring wherever the field is checkable
- Combine rubric, task-completion, adherence, and tool evaluators on top
- Report mean, median, and pass rate; publish failures and escalations
- Report governor overhead as a separate line item so gross and net are both visible

**Prompt caching caveat.** Azure prompt caching can reduce latency and input cost for repeated identical prefixes without changing output; hits are visible via `cached_tokens`. Treat as a measured secondary lever — do not attribute those savings to OutcomeFuse IP.

### Secondary risks (deferred from the brief)

- **Small-sample quality claims.** With a modest case count, a "within N percentage points" quality claim may not be statistically meaningful. Report absolute pass counts alongside percentages; do not overstate confidence. Largely mitigated by the expanded case counts and repeated runs now in scope.
- **Preview-stage dependencies.** Some managed evaluator and tracing capabilities are preview-stage. Mostly out of MVP scope; the one exception is the APIM token-metering slice, which must have a working fallback — governor-side token counting — so a metering failure degrades the independence of the measurement rather than blocking the demo.

**Original gross targets (superseded).** The source memo set ≥40% token reduction, ≥35% cost reduction, ≥30% tool-call reduction, ≥20% P50 latency reduction, task-completion pass rate within 2 points of baseline, evidence-field accuracy ≥90%, 100% budget compliance, zero safety regressions. These predate overhead accounting and are retained for reference only; net targets replace them once overhead is measured.

---

## 4. Alternatives considered

Assessed on a 1–5 scale during ideation; judgment, not measurement.

| Candidate | Innovation | Savings proof | Quality proof | Feasibility | Demo | Verdict |
|---|---|---|---|---|---|---|
| **OutcomeFuse** — quality-gated runtime budget | 5 | 5 | 5 | 4 | 5 | **Selected** — strongest end-to-end story |
| **ContextCapsule** — relevance-ranked context compiler | 4 | 5 | 4 | 5 | 4 | Very feasible, but risks reading as prompt compression alone |
| **ToolPath** — deduplicate/cache tool trajectories | 4 | 4 | 4 | 4 | 4 | Good component, narrower business story |
| **Eval-Gated Router** — start small, escalate models | 3 | 4 | 5 | 5 | 4 | Valuable, but model routing is already a native platform direction |

**Rationale for selection.** OutcomeFuse subsumes all three rejected candidates as enforcement mechanisms, subordinating them to one differentiated objective: minimum spend required to meet a declared outcome-quality contract. The rejected options are each a single lever; OutcomeFuse is the policy that decides which lever to pull.

_Naming note: the rejected "ContextCapsule" concept survives as the **Context Governor** component, which produces evidence capsules. The difference is subordination — compression serves the contract rather than being the product._

---

## 5. Demo and narrative

**Two-minute structure — problem, artifact, proof, scale.**

- **0:00–0:18 Problem.** Agents waste tokens by carrying irrelevant context, repeating tools, looping past sufficiency, and using premium reasoning everywhere. Dashboards tell you afterward; OutcomeFuse prevents it during execution.
- **0:18–0:38 Artifact.** Show the Outcome Contract on screen — deliverable, required evidence fields, quality floor, budget.
- **0:38–1:15 Mechanism.** Baseline and governed run side by side. Highlight: compressed evidence capsule, duplicate tool call rejected, cheaper model used first, quality gate evaluated, loop stopped when the outcome passed.
- **1:15–1:42 Proof.** One memorable comparison — net tokens, cost, tool calls, with quality held. Brackets replaced only by measured results.
- **1:42–2:00 Scale.** Middleware, not another framework. Same governor, dissimilar agents, no code changes.

**Key screens.** Outcome Contract · side-by-side live execution · Budget Ledger · governor decision stream ("cache hit", "duplicate denied", "quality passed", "escalation approved") · proof card · single trace drill-down. One path, not a dashboard-heavy product.

**Elevator pitch.** OutcomeFuse is a quality-gated budget runtime for enterprise AI agents. Instead of auditing token waste after a run, it decides in real time whether another context block, model call, tool invocation, or loop iteration is worth paying for. It stops when the outcome meets its quality contract, escalates when quality needs it, and proves the result with baseline-versus-governed tokens, cost, latency, and tool calls — net of its own overhead.

---

## 6. Responsible AI and security posture

- **Quality floor outranks budget.** Optimization may never accept a cheaper failing answer.
- **Human control.** Approval required for side-effecting or high-impact tools.
- **Transparency.** Record why every call was blocked, cached, compressed, or escalated.
- **Privacy.** Redact prompts, tool arguments, and results before telemetry; traces can contain sensitive input and tool data and need production-grade access and retention controls.
- **Identity.** Managed identities, least-privilege tool access.
- **Cache isolation.** Tenant and use-case partitioning; no cross-user reuse for personalized or authorization-sensitive responses.
- **No hidden quality substitution.** Model escalation and evaluator decisions are disclosed, never silent.
- **Preview awareness.** Some evaluator and tracing capabilities are preview-stage; pin stable fallbacks and state this honestly rather than demoing on unstable ground.

---

## 7. Parked extensions

Credible directions, explicitly out of scope for this iteration.

- Policy DSL for reusable Outcome Contracts
- Marginal-quality learner trained on prior runs, replacing fixed heuristics
- APIM semantic cache and prompt-cache-aware scheduling
- Multi-agent budget transfer — unused retrieval budget funds verification
- CI quality gate rejecting an agent version whose cost rises without quality gain

_Shadow mode was previously parked here and has been promoted into scope — see the brief. It doubles as a measurement instrument, capturing governed and ungoverned paths from a single run._

---

## 8. Build sequencing

Recommended order, harness-first so partial completion still yields a defensible result:

1. Freeze scenario and quality rubric — before any governor work, to avoid rubric circularity
2. Implement baseline agent and automated test harness
3. Add Outcome Contract and Budget Ledger
4. Add Tool Governor and Loop Fuse
5. Add Quality Gate and early stop
6. Add Context Governor
7. Add Model Governor and Preflight Planner
8. Add shadow mode — a non-enforcing flag over the existing decision path
9. Record reproducible benchmark runs, including the overhead break-even study
10. Wire the APIM token-metering slice so reported savings are gateway-measured
11. Build the side-by-side demo around the strongest representative case

Additional workloads are additive after step 2 — each is mock tools plus cases against the existing harness. Agent-owner interviews run in parallel throughout and are not on the critical path.

**Capacity reference (solo, from zero):** baseline + harness 1.0d · dataset 0.5d · Ledger/Tool Governor/Loop Fuse 1.0d · Quality Gate 0.75d · Context Governor 0.75d · Model Governor 0.5d · Preflight Planner 0.5d · side-by-side web app 1.5d · benchmark runs 0.5d · video 0.5d. Roughly 7.5 days against a one-month window — the surplus is intended for evidence depth (more cases, repeated runs, overhead measurement), not additional components.

---

## 9. Supply-chain workload detail

Retained as one of the demo workloads; no longer the product's defining vertical.

**Scenario.** A planning operations engineer investigating a Network CapEx exception and producing an evidence-backed recommendation.

**Case construction (20–30 synthetic cases).** Capacity plan CSV · open/released order data · contract constraints · regional demand and inventory · 3–5 policy documents · expected tools · golden decision and required evidence fields. No production or confidential data.

**Why it shows waste well.** Repeated context across steps, multiple tool calls over overlapping data, and investigation loops that naturally overrun — the three waste modes OutcomeFuse targets, in one workflow.
