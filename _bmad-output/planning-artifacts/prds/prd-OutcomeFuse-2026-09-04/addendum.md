---
title: "OutcomeFuse PRD — Addendum"
status: final
created: 2026-09-04
updated: 2026-09-04
---

# OutcomeFuse PRD — Addendum

This document holds the depth that surfaced during the PRD conversation and belongs downstream — architecture, solution design, positioning collateral — or that earned a place but does not fit the PRD's main narrative. The brief's own addendum at [briefs/brief-OutcomeFuse-2026-09-02/addendum.md](../../briefs/brief-OutcomeFuse-2026-09-02/addendum.md) remains the source for component specifications, the production stack, evaluation methodology, alternatives considered, demo narrative and build sequencing. This document does not duplicate it.

---

## 1. Competitive landscape — research findings

Web research conducted during Discovery on the 2025–2026 landscape for runtime cost governance of LLM agents. The positioning table in **PRD §1.3** is a distillation of this; the detail lives here.

### 1.1 Enforcement versus reporting

| Name | Category | When it acts | Quality-aware | Note |
|---|---|---|---|---|
| LiteLLM Proxy | OSS gateway | Before — pre-call budget reservation, rejects if over | No | Budgets per key/user/team/customer/agent; `max_iterations` and `max_budget_per_session` for agent sessions. Dollar caps only |
| Kong AI Gateway | Commercial gateway | Before — token/cost rate limits, tiered budgets, semantic cache, prompt compressor | No — guardrails are safety/PII, not output quality | Positions as a "connectivity and governance layer" |
| Azure APIM `llm-token-limit` | Cloud gateway policy | Before/during — 429/403 on TPM or token quota | No | Documentation notes concurrency can overshoot the limit |
| Portkey | Gateway plus guardrails | Before and after — sync guardrails driving fallback/retry | Partial — checks are schema, regex, PII, gibberish | Guardrail verdicts can drive orchestration, but are not coupled to spend |
| Helicone, Langfuse, LangSmith, Braintrust, Arize Phoenix, W&B Weave | Observability and eval | After — logging, cost attribution, eval scores | Quality yes, but decoupled from spend control | Quality lives in dashboards and CI, not in the run loop |
| OpenAI Agents SDK | Agent framework | During — `max_turns` | No | Step cap only; no cost cap, no quality gate |
| LangGraph | Agent framework | During — `recursion_limit` | No | Step cap only |
| CrewAI, AutoGen, Microsoft Agent Framework | Agent frameworks | During — iteration and turn limits, some token maxima | No | Same shape |
| Commercial in-loop runtime layers | Agent runtime layer | During, in-process — allow / switch model / deny tool / stop | Claimed | Nearest analogue; see §1.2 |
| Pre-spend governors | Local spend gate | Before — estimate then cap | Partial — cost-per-good-result framing, offline quality gating | Ledger plus provider reconciliation |
| FrugalGPT (2023), RouteLLM (2024) | Research | During — cascade escalate or accept | Yes — a scorer decides escalate-or-accept | Per-call, not per-run budget |

### 1.2 Closest analogues and where they stop short

1. **Commercial in-loop runtime layers.** At least one vendor markets a per-run dollar budget with an in-loop `stop` decision, scoring cost, latency, quality, budget and compliance. Documented quality appears to be **static model-quality priors used for routing weights** — a prior about which model is generally better — not a measured assessment of whether *this run's current output* satisfies a task-level acceptance criterion. Its `stop` appears budget-triggered rather than sufficiency-triggered. Vendor documentation only; adoption, benchmarks and maturity unverified.
2. **Pre-spend governors.** An explicit cost-per-good-result metric and a claim that downgrades are quality-gated. The gate itself is a dollar cap; the quality gating validates configuration choices *offline*, not a live stop/continue decision mid-run. Typically fails open by design.
3. **FrugalGPT / RouteLLM.** Genuinely quality-conditioned spend, but scoped to one query and one call: is the cheap model's answer good enough, or escalate? No notion of a multi-step run budget, a tool loop, or cumulative marginal value.
4. **Portkey guardrails plus configs.** The mechanism for verdict-drives-orchestration exists, but verdicts are deterministic safety checks and the wiring is retry-on-fail, not stop-on-good-enough. No spend coupling.
5. **LiteLLM agent session caps.** Enforcement at run granularity, but blind counters.

### 1.3 White space

- **Stop-when-sufficient, not stop-when-broke.** Nothing found terminates a run early *because the output already meets a declared bar* while budget remains. Every mechanism found terminates on exhaustion or on a safety violation.
- A declared, machine-checkable outcome contract evaluated each step and treated as the stopping condition.
- Marginal-value-per-step accounting — whether step N+1 is expected to improve the artifact enough to justify its cost.
- Published evidence that stopping early was correct. No product found publishes a quality-preserved-at-lower-spend artifact per run.

### 1.4 Positioning vocabulary

**Crowded:** observability, guardrails, governance, AI gateway, FinOps for AI, routing, cascade, cost optimization, budgets and rate limits, semantic caching.

**Under-used and available:** outcome contract, sufficiency, marginal value per step, cost-per-accepted-result.

Savings claims in the commercial space are largely unsubstantiated marketing. The research literature is the exception — FrugalGPT and RouteLLM both publish benchmark-grounded reductions. This is an argument for the PRD's evidence standards (§8) being a differentiator in themselves, not merely diligence.

### 1.5 Sources

- https://docs.litellm.ai/docs/proxy/users
- https://developer.konghq.com/ai-gateway/
- https://learn.microsoft.com/en-us/azure/api-management/llm-token-limit-policy
- https://portkey.ai/docs/product/guardrails
- https://openai.github.io/openai-agents-python/running_agents/
- https://arxiv.org/abs/2305.05176 — FrugalGPT
- https://arxiv.org/abs/2406.18665 — RouteLLM
- https://www.helicone.ai/

**Verification caveat.** Two of the closest commercial analogues were reachable only through vendor-controlled documentation and could not be independently verified for adoption or benchmark validity. Langfuse and LangGraph rows were not fetched successfully and rest on prior knowledge; re-verify before external use. No specific LLM-as-judge reliability critique was sourced during this research — worth citing one before relying on that framing in the risk section.

---

## 2. Contract authorship — the product position beyond the MVP

Deferred from the PRD, which scopes contract authoring out entirely (FR10).

The agent owner owns the quality floor. OutcomeFuse's role beyond the MVP is to make authoring easy without ever taking ownership of the bar:

- **Templates** per common task shape, giving the owner a starting structure rather than a blank file
- **Import and adaptation from an existing eval suite**, so teams that already encode quality expectations do not restate them
- **Versioned Outcome Contracts** as first-class stored artifacts, so a contract's evolution is auditable alongside the results produced under each version
- **Eventual recommendation or inference** of contracts for recognized task shapes

The invariant across all of these: **OutcomeFuse may propose, but never silently decides that lower quality is acceptable.** Any inferred or templated floor is a suggestion the owner accepts, not a default the system applies on their behalf.

This is the direct answer to open question Q2 in the PRD, and it is the main threat to the scale story — hand-authoring a floor per task type does not scale, and the MVP does not attempt to solve it.

---

## 3. Design tensions recorded during the PRD conversation

**Cut order versus the seven-mechanism narrative.** The declared cut order (PRD §4.3) makes the Context Governor, Model Governor and Preflight Planner sacrificial, makes the model-judged rubric signal in the Quality Gate sacrificial, and makes workload breadth the last thing to go. The brief presents seven mechanisms as in-scope without ranking. Both are true, but external material must present them as *committed with a declared cut order*, not as seven equally load-bearing components. Architecture should treat NFR10 — independent disableability of F7, F8 and F9 — as a hard constraint rather than a nicety: it is what makes the cut order executable, and it is also what makes the per-mechanism ablation in FR62 affordable.

**The perverse optimum.** Net token reduction per completed outcome, taken alone, is maximized by a system that always stops immediately. False-sufficiency rate is the counter-metric that closes this, and it is why FR69 exists. The same shape recurs on the deny decision — a tool-call reduction figure alone is maximized by denying everything — which is why FR70 pairs suppression accuracy to the reduction figure, and why FR71 does the same for compression fidelity. Every headline number in this product needs a paired number that can embarrass it.

**Fail-open versus fail-closed asymmetry.** Optimization mechanisms fail open, the Quality Gate and budget ceiling fail closed, and shadow mode is exempt from both (FR91). The rationale: losing an optimization costs money, losing the gate costs correctness, and a governor that halts an agent it promised only to observe destroys the adoption path. Architecture should treat ledger durability and evaluator timeout behaviour as reliability concerns distinct from the compression and routing paths, since they carry opposite failure postures.

**Deterministic gate as an argument, not just a mechanism.** FR20 makes deterministic field validation authoritative and the model rubric advisory. This is the defence against the strongest anticipated critique — that a model-judged gate relocates unreliability rather than removing it. Any implementation that quietly lets the rubric establish a pass would break the argument, not merely the requirement.

**The gate's authority is borrowed from the answer keys.** PRD §8.2a states the limit: deterministic validation is sound only where a field can be checked against ground truth, which in the MVP holds because the cases are synthetic. On production data with no key, the gate degrades toward structural validation. FR8 (contracts declare which fields are ground-truth-checkable) and FR21 (structural passes labeled as such) contain the damage; Q9 records that closing it is unsolved. Any downstream production design must answer Q9 before claiming the MVP's gate strength carries over.

**The verdict is binary by choice, and the choice is reversible.** FR94 fixes the gate at `pass` or `fail`, with no `pass-with-concern`. The alternative was considered and rejected: an intermediate verdict has to be resolved somewhere, and wherever it is resolved becomes a second, undeclared quality floor living in the runtime instead of the contract — the exact inversion FR20 exists to prevent. Model-judged tool-use quality therefore became advisory (FR22), flowing to the decision record and the counter-metrics rather than the verdict. If a downstream design finds that advisory signals are being ignored in practice rather than acted on, the reopening move is to promote specific model-judged checks into *contract-declared deterministic* checks — not to add a third verdict.

**Two dependency inversions were removed rather than documented.** Mandatory-versus-optional classification originally lived in the Preflight Planner (F9, cut position 7) while FR17 and FR31 — both protected — depended on it. Proof-card computation originally lived in the side-by-side view (F14, cut position 1) while the submission artifact (F16, protected) depended on it. Both are now owned upstream: classification by the Outcome Contract (FR7), proof-card computation by the harness (FR97). The general rule this establishes for architecture: **a protected component may not take its meaning or its output from a cuttable one.** Worth checking against any new component before adding it.

**Terminal reasons are a taxonomy, not a label — and they sit under two other taxonomies plus a run state.** FR1 separates concepts that were previously conflated: `policy_action` (what the runtime does), `decision_reason` (why, drawn from the extensible registry in FR104), and `terminal_reason` (why the run ended, recorded at most once). FR105 adds `quality_state`, which is `not-evaluated` until the gate first runs. The ladder in FR2 has two load-bearing placements: sufficiency outranks everything below it, and exhaustion outranks no-progress. The second is the less obvious one — when a run both stalls and runs out of money, crediting the Loop Fuse would report a save the governor did not make; attributing to exhaustion is the unflattering and correct reading. Architecture should treat all of these as derived by the policy and written once, never as values a mechanism sets for itself.

**Cause versus disposition was the hardest distinction to get right.** FR103 fixes it: `terminal_reason` names the *cause*, `policy_action` names the *disposition*. A run that exhausts its budget and hands back a partial result records `exhaustion` / `return-partial` / `halt-exhausted` — not `returned-partial` as the ending. Recording the disposition as the cause would erase the cost story, and the cost story is the product. `returned-partial` and `referred-human` survive as terminal reasons only where the hand-off is genuinely the cause, with no exhaustion, stall, timeout or fail-closed condition present. FR103's worked table is the authoritative reference; architecture should encode it as a mapping, not re-derive it per call site.

**The reason vocabulary is a registry, not an enum.** FR104 makes `decision_reason` a versioned, extensible set of stable codes with declared families. New codes may be added; published codes may never be redefined or removed. This matters more than it looks: a reused code silently rewrites the meaning of every historical decision record, which would break FR68 replay and every longitudinal counter-metric. Downstream systems should aggregate by family, not by enumerating codes.

**Two conditions had to be separated before the taxonomy worked.** Budget exhaustion was originally folded into the Loop Fuse, which would have let every out-of-money run be reported as a governor save. And `approval-timeout` is a decision reason in every case but a terminal reason only when the contract's `on_timeout` posture terminates — an approval gate that escalates leaves the run alive. Both distinctions exist so the counter-metrics measure what they claim to.

**The calibration/evaluation split resolves an apparent circularity, not a real one.** §3.1 requires savings targets to be derived from measured overhead *and* fixed before results are seen. Both hold because they refer to different data (§8.5, FR102): overhead is measured on the calibration set, and the evaluation set stays sealed until the numbers it will be judged against are written down. Neither half works alone — derive targets on the evaluation set and they are fitted; set them without measuring overhead and they are guesses. Architecture should treat the two sets as separate artifacts with a recorded preregistration timestamp, not as a naming convention over one corpus.

**Verifiability is now a gating property of the contract, not a property of the data.** FR8 requires every mandatory criterion to declare an executable deterministic verifier and its mode; a criterion with no verifier cannot be mandatory and becomes advisory instead. This closes the gap where "task adherence" or "completeness" could sit in the floor while resolving, in practice, to a model's opinion. It is also a genuine constraint on expressiveness: contracts can only promise what can be checked, and criteria that matter but resist verification move to the counter-metrics rather than disappearing.

**Shadow mode is protected, but its MVP evidence is synthetic.** UJ-1 narrates a week of production traffic; NFR9 permits synthetic cases only. FR106 resolves the contradiction by scoping what the MVP *demonstrates* — that a shadow run produces a decision record and a marked counterfactual, on authored cases — separately from what the product *is for*. Live-traffic shadowing is post-MVP and is listed out of scope. The persona assumption is tested by the agent-owner interviews, not by shadow mode; an earlier draft claimed otherwise and was wrong. Any production design should treat live shadowing as a distinct capability with its own privacy, retention and tenancy obligations (NFR5, NFR6, NFR12), not as the same feature pointed at different data.

**The interface acquired a path into execution, and it had to be fenced rather than forbidden.** F14 was inert by construction — read-only, replay-only, no path to influence a run — and that inertness was doing real argumentative work, because it is what made "turn the UI off and the savings still happen" true without qualification. F17 keeps the surface but adds a human-approval control, which is by definition a path into execution. Three fences replaced the blanket prohibition: the control is *one adapter behind the existing approval port* rather than a privileged path, so cutting it leaves FR34 enforced through the scripted port; no interface event may constitute a decision (FR114), so the ordinary lifecycle of a UI cannot resolve a governance gate; and surface cost is excluded from governor overhead (FR117), so watching a run cannot change its net figure. Architecture should read FR77's amended form literally — the *observation* half is still inert, and the two halves are separately disableable (NFR10). A design that merges them, or that lets the renderer and the approval adapter share a lifetime, loses the property.

**"Streaming" now means two unrelated things in this project, and one of them is load-bearing.** Model-token streaming is refused at the model port because the gateway estimates token counts while it is on, which would make the FR79 reconciliation a comparison of guesses; `streaming_disabled` is asserted on every recorded run. FR110's interface streaming is a different thing entirely and must never be allowed to imply the first. This is a naming hazard more than a design one, and it is the kind that gets resolved wrongly at three in the morning by someone making a view feel snappier.

---

## 4. The two outward ports — mechanism and transport notes

> Technical-how, recorded here rather than in the PRD. Inputs to architecture and UX design, not requirements. The PRD states the ports transport-agnostically on purpose.

**Why there are two ports and not one.** This came out of a First Principles session and it is the session's main finding. The log and the approval arrived as one sentence — "push logs and approval generically" — and they agree on nothing. The stream is constant, one-way, requires no listener, and silence costs nothing. Approval is rare, blocking, must be heard, bounded in minutes, and silence kills the run. Their failure postures are opposite: the stream fails open and is dropped, the approval fails closed and halts. A single combined abstraction would have to pick one posture, and either choice is wrong for half of what it covers — most likely by giving the firehose a blocking failure mode it has no reason to own. Architecture should resist any later "unify the transport" refactor that erases this.

**Read the published stream, never the store.** The obvious implementation of a live view — tail the run's SQLite log — is wrong for reasons already settled elsewhere. The record store exposes events only once sealed; a single writer holds an advisory lock for the run's duration; and the fold and hash-chain semantics assume a complete log. Tailing means either weakening the seal or reading behind the writer's back, and it also welds every client to internals the library is entitled to change. FR110 bars it explicitly because the cheap wrong version is genuinely tempting.

**The tree is a projection, not a stored shape.** Events are a flat sequence with a `step_id` and no parent pointer. Adding a parent/child field to the record spine was considered and rejected: it would touch the event model, every existing database and the fold, for a benefit that is entirely presentational. Grouping by `step_id` yields the same tree — proposed → decided → executed-or-suppressed → gated → evaluated — derived at render time. FR111 makes *sufficiency* the port's obligation and *drawing* the client's, so no future experience has to re-derive the shape or ask the library a follow-up mid-run.

**Publish must never be on the critical path.** Added latency is the binding threshold (~3.5ms p50 measured, ~93% of it the five durable fsync appends). A synchronous publish per decision would destroy it. The shape that works: enqueue and return, with a bounded buffer per subscriber and a drop when it fills. The drop is recorded — a client that silently missed decisions renders a clean run that never happened, which is worse than no client. Note the asymmetry with durability: the log is the record and is written synchronously; the stream is a courtesy and is lossy by design.

**Wire types are record types.** The strongest rule in this design and the cheapest to enforce: the port may serialize only types that already exist in the record spine and the approval port, and may not introduce a wire DTO with a field the record lacks. `ApprovalRequest` is already `run_id, step_id, tool, clause, timeout_seconds` with `extra="forbid"`, and decision events already carry `{tool, canonical_key}` and never arguments — so both are redaction-safe *by construction*. This converts an egress problem into a type constraint, which is the difference between getting it right once and getting it right on every field anyone ever adds. FR121 adds the second half: publication is egress, so it is refused outright for non-synthetic runs, exactly as persistence already is.

**The approval adapter keeps the same port shape.** `ApprovalPort` is a one-method Protocol returning `approved | denied | no-response | channel-unavailable`, so a transport-backed adapter drops in beside `ScriptedApprovalPort` with no core change. The inversion to watch: over a boundary the natural shape becomes *publish a pending approval, wait for a POST*, and that is precisely where timeout semantics get corrupted. The clock stays with the driver. An adapter able to hold a pause open is an adapter able to extend `approval_timeout`, which moves a contract term into whoever wrote the client. The two mappings that must never merge, restated for the wire: client accepted the request and never answered = `no-response` → `on_timeout`; no client reachable, none configured, or channel lost mid-pause = `channel-unavailable` → fail-closed.

**Authorisation, and what the MVP is not claiming.** Same-host loopback with a local shared token (FR118), and each pending approval carries an authorisation bound to `(run_id, step_id)`, single-use, expiring with the pause (FR119) — without binding, a captured approval approves a later gated call, which is the confused-deputy shape whose audit trail looks perfect.

**Identity is solved; entitlement is not.** The approver comes from the **operating system's peer credential on the loopback connection** — the client's SID on Windows via named-pipe impersonation, `SO_PEERCRED` on Unix — and never from the payload, which is refused (FR120). This is why FR118's same-host binding earns its place twice: it sizes the authorisation obligation, and it hands verified identity over for free, with no identity provider, no token validation and no secret. What remains open is **authorization**: no contract declares which principals may satisfy an approval clause, so the runtime knows who approved and not whether they were entitled to. Runs carry `authorization-unchecked`. Closing it means an approver role or principal list on the contract, which reaches FR7 and AD-7's closed loader — that is the shape of the work, deliberately not done here.

**A limit worth stating to whoever builds the demo:** on one development host the account running the benchmark and the account approving are the same. The identity is genuinely verified and the mechanism genuinely works; separation of duties is not demonstrated and must not be narrated as though it were.

**Approval transcript and replay.** FR115's transcript makes an interactive run re-executable: per approval, the decision, the verified approver, the clause, and the elapsed time within the pause. Replay feeds it to the scripted port in order. Labels then carry what genuinely differs — `human-approved` because a person rather than a script decided, and `authorization-unchecked` because nothing established that the person was entitled to. The transcript is decision-record material, so it sits on the 180-day redacted tier rather than the 60-day raw tier (NFR12).

**Transport realisation is open, but FR120 narrowed it sharply.** The stream half is easy and stays open: loopback HTTP with server-sent events, or a local socket, or a pipe — a browser client argues for HTTP+SSE, a terminal client needs neither.

The **approval** half is now coupled to the identity decision, and this is the non-obvious consequence worth flagging to whoever builds it. Peer-credential identity is nearly free over a **named pipe** on Windows — the server impersonates the client and reads its SID directly from the connection — and over a Unix domain socket via `SO_PEERCRED`. Over **loopback TCP it is not free**: HTTP carries no peer identity, so the server would have to resolve the connection's owning process through the TCP connection table and then its token, which is fragile, racy against port reuse, and exactly the kind of thing that looks fine until it silently returns the wrong account.

**Revised working assumption: named pipe (Windows) / Unix domain socket for the approval port, so FR120 reads identity off the connection; stream transport stays free to be HTTP+SSE if a browser client wants it.** The two ports were already separate for failure-posture reasons (AD-22 fails open, AD-24 fails closed); this is a second, independent reason they should not share a transport. Dhinesh's call to confirm, and it changes no requirement either way — FR120 states *where identity comes from*, not how the bytes move.
