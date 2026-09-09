---
id: SPEC-OutcomeFuse
companions:
  - glossary.md
  - decision-model.md
  - outcome-contract.md
  - failure-posture.md
  - evidence-standards.md
  - cut-order.md
  - ../../planning-artifacts/architecture/architecture-OutcomeFuse-2026-09-07/ARCHITECTURE-SPINE.md
  - ../../planning-artifacts/architecture/architecture-OutcomeFuse-2026-09-07/BUILD-ORDER.md
  - ../../planning-artifacts/architecture/architecture-OutcomeFuse-2026-09-07/SOLUTION-DESIGN.md
sources:
  - ../../planning-artifacts/prds/prd-OutcomeFuse-2026-09-04/prd.md
  - ../../planning-artifacts/prds/prd-OutcomeFuse-2026-09-04/addendum.md
---

> **Canonical contract.** This SPEC and the files in `companions:` are the complete, preservation-validated contract for what to build, test, and validate. Source documents listed in frontmatter are for traceability — consult them only if you need narrative rationale or prose color this contract intentionally omits.

# OutcomeFuse — the quality-gated budget runtime for AI agents

## Why

**An opportunity to capture, against a pain the agent owner already feels.** An agent given a business task and a set of tools has no notion of what its answer is worth, so it optimizes for finishing rather than for finishing efficiently — carrying the whole transcript forward, reissuing answered queries, running premium reasoning on reformatting, and above all overrunning: reaching a sufficient answer at iteration three and working to iteration eight because nothing told it to stop. The mechanisms that exist today stop a run when it runs *out*: gateways stop on exhaustion, routers escalate per call, observability reports after the fact. None stops a run because the output already meets an externally declared, measured quality bar while budget remains. The affected party is the engineer or platform team accountable for both an agent's bill and its output quality, currently forced to choose between capping tokens and risking silently worse answers, or leaving it uncapped and absorbing the cost. This spec covers the MVP: the artifact to be built and demonstrated inside a one-month solo window.

## Capabilities

- **CAP-1 — Runtime Decision Policy**
  - **intent:** Before every unit of work, the runtime decides whether that unit is worth paying for given the contract, the ledger state and the current quality state.
  - **success:** Every decision emits exactly one `policy_action` with its `decision_reason`, cites the contract clause, ledger state and quality state it rests on plus the gate verdict where one exists, and records a `terminal_reason` only where the run ends — with competing conditions resolved by the fixed precedence ladder in [decision-model.md](decision-model.md). No mechanism alters execution except as directed by a policy decision.

- **CAP-2 — Outcome Contract**
  - **intent:** An agent owner declares, before execution, what "done" means and what may be spent reaching it.
  - **success:** A well-formed contract validates and then runs immutably under a stable identifier and version recorded with every result. A malformed contract is rejected; one declaring a mandatory criterion with no registered deterministic verifier is rejected; one that is well-formed but internally unsatisfiable warns before executing rather than failing mid-run. Field set and validation rules in [outcome-contract.md](outcome-contract.md).

- **CAP-3 — Budget Ledger**
  - **intent:** The runtime rules on spend so no step proceeds unaffordably, wastefully, or at the cost of being able to verify the result.
  - **success:** `verification_reserve`, `in_flight` and `spent` are held separately in both tokens and estimated cost; every spend is held before it happens and settled against that hold; every unit is attributed both to task-work-or-overhead and to the mechanism that caused it, decomposed across contributors rather than assigned to a single winner; unaffordable, low-value, duplicate and unsafe steps are denied with their reason; and no escalation proceeds that would leave insufficient reserve for final synthesis and the gate executions still owed.

- **CAP-4 — Quality Gate and sufficiency stop**
  - **intent:** A run stops as soon as its declared quality floor is met, and never returns a failing result as though it passed.
  - **success:** The gate emits `pass` or `fail` against mandatory criteria only — optional and enrichment criteria never affect the verdict — qualified `reference-backed` or `constraint-backed`, with a per-criterion breakdown. It executes after every unit of work that can change the candidate result and before any terminal halt other than fail-closed. On `pass` the run terminates `stop-sufficient` with no further billable work beyond finalization. On `fail` with budget it retries or escalates per the contract; on `fail` without safe budget it returns a partial result naming the unmet criteria, or requests a human, as the contract directs. Every returned result carries its verdict.

- **CAP-5 — Loop Fuse**
  - **intent:** A run that has stopped making progress halts rather than burning budget on repetition.
  - **success:** A per-iteration progress fingerprint over evidence gained, task-state change and quality delta halts the run on repeated state, no new evidence across the configured number of iterations, repeated tool arguments, or the contract's iteration limit — recording `halt-no-progress`, never conflated with exhaustion or sufficiency. Budget exhaustion is not a loop-fuse condition.

- **CAP-6 — Tool Governor**
  - **intent:** Redundant tool work is suppressed and gated tool work is approved, without ever suppressing a call that has side effects.
  - **success:** Tool name and arguments canonicalise to a stable key; results of contract-declared deterministic tools are reused within the run; exact duplicates are denied, as are optional or enrichment calls once every mandatory criterion is satisfied. No optimization-driven caching, deduplication or denial applies to tools declared side-effecting or non-deterministic — safety, affordability and approval denials still do. A call meeting a declared approval condition pauses and does not proceed until approval is granted or `approval_timeout` elapses. Every denial, cache hit, pause and timeout is recorded with its reason.

- **CAP-7 — Context Governor** *(conditional — cut position 7)*
  - **intent:** Each step receives only the evidence it needs, compressed, rather than the accumulated transcript.
  - **success:** Tool output becomes structured evidence capsules that preserve citations, identifiers, numeric values, policy clauses and every contract-required attributable fact verbatim; no attributable fact is dropped; compression spend is attributed to governor overhead; and compression fidelity is measured rather than asserted.

- **CAP-8 — Model Governor** *(conditional — cut position 6)*
  - **intent:** Work runs on the cheapest eligible model and escalates only where the task genuinely requires it.
  - **success:** Execution begins on the cheapest contract-eligible model. Escalation occurs only on task complexity, low model confidence, policy criticality or a failed quality evaluation, never outside contract eligibility, and never where it would breach the verification reserve. Every escalation is disclosed in the decision record; model substitution is never silent.

- **CAP-9 — Preflight Planner** *(conditional — cut position 8)*
  - **intent:** The runtime holds a typed plan with per-step cost envelopes to inform its decisions.
  - **success:** A typed execution graph carries an estimated token and tool envelope per step and propagates the contract's mandatory-versus-optional classification onto each step. Planning spend is attributed to governor overhead. Cutting the planner leaves that classification fully available to the ledger, gate and tool governor, because the contract owns it.

- **CAP-10 — Shadow mode**
  - **intent:** A team can evaluate the governor against a workload with nothing at risk, before enabling enforcement.
  - **success:** The host's ungoverned path executes and is recorded while the governor logs every decision it would have made and its estimated effect, producing a decision record of the same shape as an enforced run. The first divergence is marked, and everything the counterfactual asserts after it is labelled inference rather than observation. Shadow figures are labelled projected, never realized, and are structurally inadmissible as headline claims. MVP shadow runs use synthetic and replayed workloads only.

- **CAP-11 — Integration surface**
  - **intent:** An existing tool-using agent loop becomes governed by wrapping it and declaring a contract, with no re-architecture.
  - **success:** Integration consists of wrapping the loop and declaring a contract. The governor is demonstrated against at least two dissimilar agent implementations across the committed workloads. An OFF state runs the host exactly as its baseline with the governor out of the call path entirely. No run from an adapter is reportable until that adapter passes the conformance battery — denial honoured, substitution applied, approval pause observed, sufficiency stop terminating, fail-closed halting, shadow decisions not applied — asserted against the resulting decision log, plus an out-of-band probe in which scripted tools assert for themselves whether they were invoked.

- **CAP-12 — Decision record and audit trail**
  - **intent:** A reviewer can reconstruct why a run stopped where it did without trusting or re-invoking the model.
  - **success:** Every decision is appended before it takes effect, carrying timestamp, step identifier, action, reason, terminal reason where set, quality state, gate verdict where one exists, contract clause, ledger state, model, tokens, and every model-derived input the decision consumed. The record is queryable per run and exportable, and a decision is replayable from it. Prompts, tool arguments and tool results are absent from it.

- **CAP-13 — Benchmark harness and evidence pipeline**
  - **intent:** The savings claim is produced as a measured, reproducible artifact that can be shown to be wrong.
  - **success:** The harness executes a frozen case set baseline-versus-governed with the same tools, model versions and settings; repeats runs per case and reports mean, median and absolute pass counts; ablates every savings-producing policy and mechanism including the protected ones; computes the proof card as a recorded artifact; runs the overhead break-even study; measures tool-suppression accuracy by re-execution, compression fidelity, and every marginal-value denial with its floor-protection compliance; supports blind human review of passed runs; and refuses any comparison failing the admissibility, independence or accompaniment gates in [evidence-standards.md](evidence-standards.md). Any reported run is re-executable from its recorded configuration.

- **CAP-14 — Side-by-side execution view** *(conditional — cut position 1)*
  - **intent:** A viewer watches a governed and an ungoverned run of the same case side by side and sees why each decision was made.
  - **success:** A self-contained static artifact per comparison replays both recorded runs in execution order with human-readable reasons and the ledger state at each replayed decision, renders the proof card without computing any figure of its own, and supports drilling into a single run's decision record offline. It is read-only, consumes only recorded output, and disabling it changes neither governed behaviour nor realized savings.

- **CAP-15 — Gateway token metering** *(conditional — cut position 10)*
  - **intent:** The headline token figure is measured by something other than the system being evaluated.
  - **success:** Token counts for reported results are obtainable from gateway metering independent of the governor's self-report, reconciled against governor-reported counts with any discrepancy surfaced rather than silently resolved. Where metering is unavailable, figures fall back to governor-side counting and are labelled self-reported, downgrading the stated independence rather than concealing it.

- **CAP-16 — Submission artifact**
  - **intent:** The work is presented as a two-minute video showing the mechanism running and the proof behind it.
  - **success:** The video covers problem, artifact, proof and scale in that order within two minutes; shows at minimum an Outcome Contract, a governor decision stream, and a stop caused by sufficiency; presents no projected, shadow-mode or single-run cherry-picked figure as realized saving; and draws every figure from a recorded evaluation-set run carrying its full labelling. It depends on the harness and the decision record, never on CAP-14.

- **CAP-17 — Failure posture**
  - **intent:** The governor's own failures degrade in the direction each failure's cost demands, and a degraded run is never mistaken for a clean one.
  - **success:** An advisor that raises is deregistered for the remainder of the run, execution continues without it, a `degraded` event names the mechanism, and every figure that run yields carries the degraded label. Gate-verdict unavailability, ledger-state loss and approval-*channel* unavailability terminate through the ladder as `fail-closed`; an approval *timeout* does not, and follows the contract's `on_timeout`. The shadow driver applies neither posture. The registry is run-scoped, so a deregistration never survives into the next repeat. Placement matrix in [failure-posture.md](failure-posture.md).

- **CAP-18 — Data-class and retention governance**
  - **intent:** Data the MVP retention profile was not written for cannot silently acquire it.
  - **success:** Every run's manifest carries a `data_class` supplied by the frozen case-set attestation with no default; a run without one is refused. `replayed` inherits the class of the run it replays. Anything other than `synthetic` refuses persistence of evidence *and* decision log alike until an approved production-data governance profile exists. Raw evidence expires 60 days from `run_closed_at` and is deleted as a whole run directory with a content-free receipt written to a separate append-only manifest; redacted records and proof artifacts are retained 180 days from campaign seal. Expiry never derives from a filesystem timestamp, and there is no per-run extension.

## Constraints

- The quality floor outranks the budget. The runtime exceeds a cost ceiling and requests a human rather than returning a cheaper answer that fails the contract, and no runtime path relaxes, reinterprets or waives the floor.
- Deterministic criterion-level validation is the authoritative gate. A model-judged rubric may contribute signal but cannot override a deterministic failure and cannot alone establish a pass.
- A criterion with no executable deterministic verifier cannot be mandatory. Contracts can only promise what the closed registry can check; the rest becomes advisory and flows to the counter-metrics.
- The marginal-value estimator may only *propose* `low-value`. The Policy rejects any such proposal against an unmet mandatory criterion, and the attempt is reported as a violation rather than a saving. The estimator is pluggable; the carve-out is not.
- No decision takes effect before it is recorded, and run state is a fold over the append-only log — never a second structure kept in sync with it. Anything not in the log did not happen and may not be claimed.
- The governor core is pure: no I/O, no clock, no randomness, no network. Everything worldly is a port the core defines and something outside it implements.
- Decisions are taken strictly one at a time per run. The host may execute approved steps in parallel; it may not obtain verdicts in parallel.
- Raw prompts, tool arguments and tool results never enter the decision log. Only derived values, hashes and evidence-store references cross into the record.
- One canonicalisation function serves every hash in the system, with a specified versioned normalisation and exactly two admissible routes, each hashed artifact declaring which route it used.
- A contract executes no code. Verifier selection is declarative from a closed registry, contracts load through a safe loader under bounded size and nesting depth, and no verifier performs network, filesystem, model or clock I/O or reads run state.
- Rubric, answer keys, per-workload contracts, verifier registry, its tests and the coverage report are content-hashed and frozen in one operation before governor implementation begins.
- Savings targets, counter-metric thresholds, minimum case counts and blind-review sample size are recorded before any evaluation-set result is executed or inspected.
- The calibration set and the evaluation set are separate artifacts. Calibration results never enter a headline figure or the submission; only evaluation-set results support a headline claim.
- Net is the only permitted headline. A headline figure without its per-mechanism breakdown, or a tool-call reduction without its suppression accuracy, is not publishable.
- Conditional mechanisms are independently disableable, and disabled means *not registered* — no mechanism carries an `if enabled` branch, so an ablation is byte-identical to having cut it.
- No workload-specific logic lives in the governor core. Workload specificity lives in contracts, tools and cases.
- Streaming is barred on the evidence path, because the gateway estimates token counts when streaming is enabled.
- Shadow mode alters nothing the host would otherwise do, and is exempt from fail-closed.
- A protected component may not take its meaning or its output from a cuttable one.
- Tool-result reuse is scoped to a single run and a single process. No cross-run, cross-process or persistent cache exists.
- Solo build inside a one-month window. A requirement not demonstrable in that window moves out of scope rather than being carried unmet, and scope reduction follows the declared order in [cut-order.md](cut-order.md).
- No credential appears in a contract, and tool access operates under least-privilege identity.

## Non-goals

- Contract authoring in any form — no authoring UI, template library, eval-suite import, inference, or contract-versioning surface. Contracts are hand-authored files.
- Shadowing live production traffic. MVP shadow evidence is synthetic and replayed only.
- Production deployment beyond the single gateway metering slice. The MVP otherwise runs as an in-process governor, and no staging tier exists.
- Any claim of measured generalization beyond the workloads actually completed.
- A new agent framework. OutcomeFuse wraps existing tool-using loops and claims no invention in the individual mechanisms.
- Post-run reporting as the deliverable. The output is a cheaper completed run, not analysis a human must act on.
- Policy DSL for reusable contracts, learned marginal-value estimation, multi-agent budget transfer, CI cost-regression gates.
- A persistent or cross-run tool cache, and any multi-process or distributed governor.
- OpenTelemetry export. Attribute names may be borrowed as convention; the record schema depends on no external specification.
- Solving production ground truth without hand-authored answer keys. The MVP states the limit rather than closing it.

## Success signal

On the sealed evaluation set, paired OFF/ON comparisons across at least two dissimilar host frameworks show the same tasks completed to the same declared quality floor for measurably fewer tokens net of all governor overhead, with every preregistered counter-metric threshold met, per-mechanism attribution published, and failures and escalations published alongside successes.

The demonstrable moment is a single run terminating `stop-sufficient` with budget still remaining — its decision record naming the mandatory criteria that satisfied the floor, and its blind-reviewed deliverable holding up — shown running inside the two-minute submission.

## Assumptions

- The primary persona and all four user journeys are inferred from builder judgment rather than research; two to three structured conversations with production agent owners are in scope to confirm or correct them, and until then they carry design intent, not evidence.
- The stop-when-sufficient white space rests on a survey, not a proof of absence. Two of the closest commercial analogues were reachable only through vendor documentation and could not be independently verified.
- Unmet-criterion targeting is adequate as the MVP marginal-value estimator. Its quality is unknown; it is pluggable if it performs poorly, and every denial it makes is reported with its floor-protection compliance.
- The seven-type verifier registry is sufficient, with at most three deterministic additions admissible on demonstrated need before the freeze.
- The pinned LangGraph release declares Python classifiers only to 3.13 and is assumed to work on 3.14, pending validation before that adapter is committed.

## Open Questions

- What net token, net cost and tool-call reduction targets should be set? Unset pending the overhead break-even study on the calibration set.
- What numeric threshold applies to each counter-metric — false sufficiency, tool-suppression error, escalation rate, overhead share, added latency, budget breach? All unset, and all must be preregistered.
- What is the minimum case count per workload, below which a comparison is unpublishable?
- What blind-review sample size per workload establishes false-sufficiency rate credibly?
- What decision-latency bound applies per step, measured against baseline step latency?
- Who authors the quality floor in a real deployment, and at what effort per task type? This is the main threat to the scale story, and the MVP does not address it.
- How does a production deployment establish ground truth without hand-authored answer keys? Without them, mandatory criteria collapse toward `constraint-backed` verification.
- Is an API Management instance on a tier that supports `llm-token-limit` provisioned? It is a critical-path dependency before any evaluation-set run, and its absence silently downgrades every figure to self-reported.
