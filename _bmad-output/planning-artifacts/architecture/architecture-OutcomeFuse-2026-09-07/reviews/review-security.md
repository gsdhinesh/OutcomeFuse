# Security Review — ARCHITECTURE-SPINE.md

- **Artifact:** `_bmad-output/planning-artifacts/architecture/architecture-OutcomeFuse-2026-09-07/ARCHITECTURE-SPINE.md`
- **Supporting context:** `_bmad-output/planning-artifacts/prds/prd-OutcomeFuse-2026-09-04/prd.md` — §3.3, §8, §9, §10, NFR5, NFR6, NFR7, NFR12
- **Review type:** Adversarial security architecture review
- **Review date:** 2026-09-08
- **Posture taken:** The system is a mediation layer that sits in front of someone else's working agent, intercepts its tool calls and model calls, enforces human-approval gates, and produces the audit trail that is then used as external evidence. It is therefore a **security control**, a **credential-adjacent in-process component**, and an **evidence system** simultaneously. Each of those three carries a different threat model, and the spine currently reasons explicitly about none of them.
- **Scope note:** No file was modified. This review recommends spine text; it does not apply it.

---

## Verdict

**The spine's *governance* logic is unusually well built and its *security* logic is almost entirely absent.** The separations that matter for correctness — pure core, single-writer ledger, advisory-only mechanisms, floor protection in the Policy rather than the estimator, log-before-effect — are real and structural, and several of them incidentally bound the prompt-injection blast radius better than most systems of this kind manage deliberately. But the spine contains no threat model, no trust-boundary statement, and no adversary. AD-7 is the only invariant whose `Prevents:` clause names an attack, and AD-7 does not survive contact with its own stack table. The result is a document that is rigorous about the things a careless engineer gets wrong and silent about the things a motivated one exploits.

Four properties the product *claims* are not currently *held* by the architecture:

| Claim | Where claimed | Actually held? |
| --- | --- | --- |
| "A contract executes no code" | AD-7 | **No** — contracts are YAML and no safe-loader rule exists; `citation-resolves` implies network I/O from inside the pure core |
| "A contract that requires approval and a runtime that does not enforce it is a governance defect" (FR34) | AD-12, AD-15 | **No** — enforcement is cooperative (the adapter applies the verdict) and conformance is asserted only against the log, which cannot observe a side effect |
| "Anything not in the log did not happen and may not be claimed" (AD-2) | AD-2, AD-16 | **Partially** — the log has no integrity structure, so the converse ("what is in the log did happen") is unbacked, and that is the direction the external claims run |
| "Prompts, tool arguments and tool results ... never enter the decision log" (AD-5, NFR5) | AD-5 | **No** — AD-5's own carve-out admits evidence capsules, which FR37/FR38 define as preserving citations, identifiers, figures and policy clauses **verbatim** |

None of the four requires a bug to break. Each breaks through a flow the spine explicitly permits.

**Disposition:** eleven items are recommended as spine changes before implementation begins; nine are MVP-acceptable if disclosed; the remainder are implementation notes. The eleven are collectively about two pages of Rule text — this is not a redesign, it is a set of missing sentences in a document whose entire method is that the load-bearing sentences are present.

---

## 0. Trust boundaries the spine does not state

Before the findings, the omission that generates most of them. The spine's layer table is a **dependency** boundary. It is not a **trust** boundary, and the two are drawn differently. Here is the trust picture the architecture actually has:

```
UNTRUSTED, ATTACKER-INFLUENCED
  tool results ─┐
  model output ─┤
  deliverable  ─┘──▶ verify-criterion (core) ──▶ gate verdict ──▶ decision log ──▶ HTML ──▶ third party
                └──▶ compress-to-capsule ──▶ capsule ──▶ decision log ──▶ back into context
                └──▶ canonicalise ──▶ key ──▶ decision log
SEMI-TRUSTED, CROSSES AN ORG BOUNDARY
  the Outcome Contract  (§1: "platform teams hand contracts to agent owners")
  the case definition   (drives the scripted approval decider — AD-12)
TRUSTED BY ASSUMPTION, NOT BY CONTROL
  the host adapter      (applies verdicts; AD-1 gives it the enforcement point)
  the tool implementations (co-resident in the process; see S-22)
  the filesystem        (holds the log, the evidence store, the preregistration artifacts)
```

Three observations follow, and they recur throughout this review:

1. **The contract is a trust-boundary-crossing artifact.** AD-7's `Prevents:` clause says so explicitly — "a product whose position is that platform teams hand contracts to agent owners" — and then the rest of the spine treats contract content as configuration. Contract-supplied regex patterns, field selectors, answer-key references and approval conditions are all attacker-reachable in the product's own stated deployment model.
2. **Everything downstream of a tool call is attacker-influenced.** The spine's *governance* reasoning correctly treats model output as unreliable. Its *security* reasoning does not treat it as hostile. Unreliable and hostile need different controls: the first needs a deterministic gate, which the spine has; the second needs the content to be structurally denied an instruction position and denied an egress, which the spine does not have.
3. **The governor shares an OS process with the agent it governs** (Structural Seed, system view: `subgraph proc[Single OS process]`). Every isolation claim in the spine — NFR6 cache partitioning, NFR7 least privilege, AD-19 access control, AD-11's promise that shadow mode cannot hurt you — is bounded by that fact, and none of the four says so.

**Recommendation (meta, and the cheapest high-value change in this review):** add a short `## Trust Boundaries` block after `## Design Paradigm`, containing the diagram above and the three observations. It costs half a page, it makes every subsequent security rule obviously placed rather than arbitrary, and it prevents the recurring failure mode where a later contributor reads "the core is pure" as "the core is safe."

---

## Findings summary

Severity: **Critical** — breaks a stated product guarantee with a practical attack, no other control in the path. **High** — breaks a stated guarantee or provides a strong primitive; another control mitigates partially. **Medium** — real exposure, bounded blast radius or requires a precondition. **Low** — hygiene, disclosure or defence in depth.

| # | Finding | AD | OWASP | Severity | Disposition |
| --- | --- | --- | --- | --- | --- |
| S-1 | Contract parse is unspecified; YAML + default loader is the exact RCE AD-7 claims to prevent | AD-7 | A03, A08 | **Critical** | Fix in spine |
| S-2 | `citation-resolves` is an SSRF, exfiltration and verdict-forgery primitive, placed inside the pure core | AD-7 | A10, A01, A04 | **Critical** | Fix in spine |
| S-3 | `regex-match` is unbounded computation in a core that structurally cannot hold a clock; wedges the shared process | AD-7, AD-11, AD-20 | A04 | **High** | Fix in spine |
| S-4 | Approval enforcement is cooperative; AD-15 conformance cannot observe a side effect | AD-1, AD-12, AD-15 | A01, A04 | **High** | Fix in spine |
| S-5 | An approval is an unbound boolean — no identity, no call binding, no single use, replayable in the record | AD-12 | A07, A08 | **High** | Fix in spine |
| S-6 | `approval_timeout` has no owner; the core has no clock and the adapter may hold the pause open | AD-12 | A04 | **High** | Fix in spine |
| S-7 | The decision log has no integrity structure, while being the evidence for external claims made by the interested party | AD-2, AD-16 | A08 | **High** | Fix in spine |
| S-8 | Append-only is writer discipline, not schema | AD-16 | A04 | **Medium** | Fix in spine (cheap) |
| S-9 | "Appended before it takes effect" is not defined as committed and durable | AD-2, AD-16 | A04 | **Medium** | Fix in spine (cheap) |
| S-10 | AD-5 admits evidence capsules into the decision log; capsules preserve sensitive content verbatim by requirement | AD-5 | A01, A02 | **High** | Fix in spine |
| S-11 | "Canonical keys" cross into the record — ambiguous, and on the wrong side of AD-5 | AD-5, AD-6 | A01 | **Medium** | Fix in spine (one word) |
| S-12 | In-spec path from raw tool content to the third-party HTML artifact | AD-17 | A01 | **High** | Fix in spine |
| S-13 | Autoescaping is claimed but script-context and JSON-island escaping is not | AD-17 | A03 | **High** | Fix in spine (cheap) |
| S-14 | Translated port errors are not required to be redacted; pydantic `ValidationError` carries `input` | AD-5 | A09 | **Medium** | Fix in spine (cheap) |
| S-15 | AD-19's "access-controlled" names no mechanism | AD-19 | A01 | **Medium** | Fix in spine (cheap) |
| S-16 | FR69 blind-review isolation is code discipline where it could be argument shape | AD-19 | A01 | **Medium** | Fix in spine (cheap) |
| S-17 | NFR12 retention period is declared nowhere and enforced by nothing | AD-16, AD-19 | — | **Low** | MVP-acceptable with a number |
| S-18 | Injection reaches sufficiency through `constraint-backed` verification; bounded by mode, not prevented | AD-18, §8.2a | A04 | **Medium** | MVP-acceptable, must be stated as a *security* boundary |
| S-19 | Injection can force `halt-no-progress` by returning static content — availability only | AD-2, F5 | A04 | **Low** | MVP-acceptable, disclose |
| S-20 | No bound on the advisor ↔ `EvidenceRequest` fixpoint; injection-driven cost amplification | AD-4 | A04 | **Medium** | Fix in spine (cheap) |
| S-21 | The evidence capsule is a persistent injection carrier that is read back as context and carries no untrusted marking | AD-5 | A03, A04 | **High** | Fix in spine |
| S-22 | In-process co-tenancy defeats NFR7; `permitted tools` is authorization, not capability isolation | — | A01, A05 | **Medium** | MVP-acceptable with disclosure |
| S-23 | Per-criterion gate feedback (FR26) plus targeted retry (FR24) is an answer-key oracle | AD-7 | A04 | **Medium** | MVP-acceptable, disclose |
| S-24 | Answer-key and evidence-store paths are contract-influenced; no traversal constraint stated | AD-7, AD-19 | A01 | **Medium** | Fix in spine (cheap) |
| S-25 | How a criterion addresses a deliverable field is unspecified; an expression language reopens AD-7 | AD-7 | A03 | **Medium** | Fix in spine (cheap) |
| S-26 | AD-10 admissibility permits both arms on the `direct` route, contradicting the deployment note | AD-10 | A08 | **Medium** | Fix in spine (cheap) |
| S-27 | Versions are pinned in prose; no locked, hash-verified dependency set is required | Stack | A06, A08 | **Medium** | Fix in spine (cheap) |
| S-28 | FR84 puts the contract in front of third parties, so NFR7's no-credential rule is a disclosure rule | — | A02 | **Low** | Note |
| S-29 | No threat model or trust-boundary statement exists in the spine | — | A04 | **Medium** | Fix in spine |

---

## 1. OWASP Top 10 relevance

Not every category applies; the ones that do are load-bearing rather than incidental.

### A01 — Broken Access Control · **Applies, materially**

Three distinct access-control surfaces exist and none is enforced by a mechanism.

- **The human-approval gate.** This is authorization in the classic sense: a privileged action requires an out-of-band grant. The spine's enforcement point is the host adapter (AD-1: "A host adapter **proposes** a step and **applies** the returned verdict"), which is the component the governor exists to distrust. See S-4.
- **The evidence store.** AD-19 says "access-controlled" and "Only the harness reads it," and names no mechanism for either. On a developer workstation with a single OS process shared with the host agent and its tools, both statements are conventions. See S-15.
- **The blind-review renderer.** AD-19's strongest structural claim — that the renderer is "structurally denied access to the gate verdict, the decision record and the run manifest" — is the one place the spine reaches for a real access control, and it is expressed as a property of the code rather than of its inputs. It is trivially convertible into the latter. See S-16.

**Structural or left to chance:** left to chance in all three, though S-16 is one sentence from being structural.

### A02 — Cryptographic Failures · **Applies, narrowly**

There is no confidentiality requirement in the PRD beyond redaction, and no encryption-at-rest obligation. But the evidence store, by AD-19's own description, holds "the raw tool outputs FR70 re-execution and FR71 fidelity measurement require" — i.e. unredacted content — on the same filesystem as everything else, and NFR12 acknowledges this content "may contain sensitive input and tool data." SHA-256 is used correctly for identity (AD-6) but nowhere for integrity or authenticity. See S-7 and S-15.

**Structural or left to chance:** left to chance, but MVP-defensible given a single-workstation deployment — *provided the spine says so*, which it does not.

### A03 — Injection · **Applies, and this is where the sharpest findings sit**

Four injection surfaces, in descending order of severity:

1. **Deserialization of the contract** (S-1). Contracts are YAML by the Consistency Conventions table; PyYAML is in the stack; nothing anywhere mandates `safe_load`. `yaml.load` with the default loader constructs arbitrary Python objects. AD-7's `Prevents:` clause is literally "Remote code execution driven by a data file." The spine names the attack and then does not close it.
2. **SSRF via `citation-resolves`** (S-2, treated under A10).
3. **Cross-site scripting in the generated artifact** (S-13). AD-17 says "HTML generation autoescapes; record content is untrusted input" — correct instinct, and better than most specs manage. But Jinja2 autoescaping protects HTML text and attribute contexts, not a `<script>` context, and AD-17 requires a **self-contained** file embedding "the replay timeline, ledger state at each decision ... and enough record to satisfy FR76 offline." That data will be a JSON island. `</script>` inside a string in a JSON island terminates the block regardless of HTML escaping.
4. **Expression injection via field addressing** (S-25). The spine specifies the *verifier types* exhaustively and never specifies how a criterion names the field it verifies. If that is JSONPath, JMESPath, a Jinja expression or anything else evaluable, AD-7's closed registry is closed around an open door.

**Structural or left to chance:** left to chance for 1, 2 and 4; 3 is half-addressed and needs one more sentence.

### A04 — Insecure Design · **Applies, and it is the category that best describes this spine**

The recurring pattern is a guarantee asserted at a layer that cannot enforce it:

- Approval is enforced by the component being governed (S-4).
- Append-only is enforced by the writer's manners rather than the schema (S-8).
- Bounded verification is impossible in a core that is forbidden a clock (S-3) — the purity rule that makes the core replayable is the same rule that forecloses the natural mitigation, and the spine never notices the tension.
- Shadow mode's "cannot hurt you" is a statement about *policy application* (AD-11: "the driver applies no halts") in an architecture where the governor and the host share a process, so resource exhaustion is shared regardless of what the driver applies (S-3).
- Fail-closed (AD-20) presumes failures **raise**. A hang, a wedge, or an unbounded loop does not raise, so it enters neither the fail-open path (deregistration) nor the fail-closed path (FR2 ladder). The §10 posture has a third state it does not model.

**Structural or left to chance:** these are design-level and must be fixed in the spine, not in code review.

### A05 — Security Misconfiguration · **Applies**

The defaults that matter are unstated and every unstated default here is the unsafe one: `yaml.load` vs `yaml.safe_load` (S-1); SQLite `synchronous` and journal mode (S-9); file permissions on the run database and the evidence store (S-7, S-15); Jinja2 script-context handling (S-13); whether the `direct` model route can carry a reportable figure (S-26). The spine is otherwise scrupulous about pinning defaults — the Consistency Conventions table exists precisely for this — which makes the omission a gap in an established pattern rather than an oversight of category.

### A06 — Vulnerable and Outdated Components · **Applies, mildly**

The verification review already established every version as current. Two residual points. `openai-agents` is pre-1.0 with no stability statement, which the spine flags honestly and Q-A proposes to make cuttable — that is the right handling. More relevant here: **litellm is the largest transitive dependency in the stack and it is the one that handles credentials.** AD-13's containment of it behind `ModelPort` is a genuine security control that the spine justifies on measurement grounds; it is worth naming the second benefit. And nothing in the spine requires a **locked, hash-verified dependency set** (S-27) — for a system whose deliverable is evidence, a reproducible dependency closure is part of the evidence, not merely hygiene.

### A07 — Identification and Authentication Failures · **Applies**

There is no notion of identity anywhere in the spine. For the MVP's scripted decider that is defensible; for the *claim* built on it — §9's "Human control is enforced, and bounded," which the PRD lists among its Responsible AI commitments — it is not. An approval with no approver is not a governance record. See S-5.

### A08 — Software and Data Integrity Failures · **Applies, and it is the highest-value category for this product specifically**

This system's output *is* an integrity claim. §8 constructs an elaborate apparatus to make results falsifiable — frozen baselines (FR64), hashed rubrics (FR65), preregistration ordering (FR66, FR102), sealed evaluation sets (§8.5), blind review (FR69), counter-metrics that can only hurt (§3.3). §8.1 states the threat model explicitly and correctly: *"The baseline is defined by the party who benefits from it losing."*

That reasoning is applied to the baseline and stops there. Every artifact in the apparatus — the manifest, the preregistration record, the frozen baseline definition, the decision log itself — is written by the same harness, on the same filesystem, under the same user, with the timestamps that prove ordering being self-asserted, and none of them is chained, sealed or signed. The FR102 control that "refuses any comparison in which [evaluation execution] precedes [preregistration]" compares two numbers that the interested party wrote. See S-7.

This is not an accusation; it is the observation that §8 already accepts. The fix is small and already half-built: AD-6's canonicaliser is exactly the machinery a hash chain needs.

### A09 — Security Logging and Monitoring Failures · **Inverted, and worth saying so**

Most systems fail this category by logging too little. This one logs superbly — FR53's field list, FR6's replayability requirement, AD-8's owned schema and immutable reason registry, and the Consistency Conventions rule that "Application logs are for humans and carry no decision authority" are all better than the norm. The failure here is the mirror image: **the logging is excellent and there is no monitoring of the log's own integrity**, no detection of tampering, and no alert on the security-relevant events the log does capture (approval bypass, verifier failure, degradation). At MVP, absence of alerting is fine. Absence of any integrity signal is not, because the log is the product's evidence. See S-7. Secondarily, the redaction obligation (NFR5, FR56) is asserted for the decision record but never for *application* logs or exception text, which is where redaction failures usually happen (S-14).

### A10 — Server-Side Request Forgery · **Applies, directly, via one word in AD-7**

`citation-resolves`. See S-2.

---

## 2. Contract-as-attack-surface — attacking AD-7

AD-7 is the spine's best invariant and its most over-claimed. The rule reads:

> FR8's "executable deterministic verification method" is a selection from a **closed, project-owned verifier registry**, parameterised declaratively (field-present, type-is, numeric-range, set-membership, regex-match, exact-match-against-answer-key, citation-resolves). No import path, expression or callable reference crosses the contract boundary.

The registry of **entries** is closed. The registry of **behaviours** is not, because three of the seven entries take contract-supplied parameters whose effect is not bounded, and one performs I/O. "Closed" is doing work the word cannot support: what AD-7 needs is that each entry is **total, bounded and I/O-free**, and it says none of those.

### S-1 — Contract parsing is the open door AD-7 was built to close · **Critical**

**Attack.** The contract is a YAML file (Consistency Conventions: "Contracts are YAML"). PyYAML 6.0.3 is in the stack. `yaml.load(f)` without an explicit `Loader=` constructs arbitrary Python objects via `!!python/object/apply` tags — arbitrary code execution at parse time. An attacker who can influence a contract file — which, per AD-7's own framing, is a file handed between a platform team and an agent owner, and per FR12 is a hand-authored file that will move by email, ticket attachment or repository — obtains code execution inside the process that holds the model credentials and the host agent.

Two aggravating factors specific to this design:

- **Parsing precedes the record.** AD-9 makes the run manifest the first log entry, and the manifest carries the contract hash — which cannot be computed before the contract is read. So contract parsing happens before any log entry exists. An attack that lands at parse time produces **no audit trail at all**, in the one system whose entire premise is that everything is recorded. AD-2's "Anything not in the log did not happen" becomes true in a way nobody intended.
- **A safe loader is necessary but not sufficient.** `safe_load` prevents object construction; it does not prevent alias-expansion denial of service (the "billion laughs" / YAML bomb), which is a memory-exhaustion attack against a process shared with a customer's production agent.

**Affected AD:** AD-7 (directly, and it is the exact attack AD-7's `Prevents:` clause names), AD-9 (unrecorded pre-manifest surface).

**Severity:** Critical. Practical, unauthenticated-in-the-relevant-sense, full compromise, and it defeats the spine's flagship security invariant using the spine's own stack choice.

**Rule text that closes it** — append to AD-7:

> Contract text is parsed with a **safe loader only** (`yaml.safe_load`; no tag construction, no object instantiation), under declared limits on document size, nesting depth, node count and alias expansion. A contract is read, hashed and validated **before any other input is read** and before the run manifest is written; a parse or validation failure is itself recorded as a refused run carrying the contract's file hash, so an unrunnable contract still leaves a record.

### S-2 — `citation-resolves` is SSRF, exfiltration and verdict forgery in one registry entry · **Critical**

**Attack.** The spine never says what "resolves" means. Every natural reading involves dereferencing a locator that came from model or tool output — which is to say, from attacker-influenced content. Take the network reading, which is the one that fits the word:

1. **SSRF.** The governor issues a request to a URL chosen by whoever influenced the deliverable. From inside the customer's process, on the customer's network, with the customer's egress. The standard targets follow: cloud instance-metadata endpoints, internal admin interfaces unreachable from outside, `file://` and other non-HTTP schemes if the client library permits them, and redirect chains that defeat naive allowlisting.
2. **Exfiltration.** This is the worse half and it is specific to this architecture. AD-5 goes to real trouble to ensure raw content never reaches the durable record. A poisoned tool result that induces a citation of the form `https://attacker.example/<encoded-sensitive-content>` causes the **verifier itself** to transmit that content out of the process. The governance layer supplies the egress channel that the redaction rule exists to deny. DNS resolution alone suffices; no successful HTTP response is needed.
3. **Verdict forgery.** The criterion passes if the citation resolves. Anyone who controls a reachable host controls that outcome. A gate pass — the thing the entire product rests on — becomes purchasable for the price of a domain name.
4. **Architectural violation.** AD-5 lists `verify-criterion (FR8)` among the *core* operations permitted to see raw content, and AD-4 states that "an advisor never performs I/O" and "the driver is the only component that performs port calls," while the Capability Map places F4 Quality Gate in `core/gate`. A network-dereferencing verifier inside `core/gate` breaks the paradigm outright — and it also breaks **AD-2 replay** and **FR68 re-executability**, because a verdict that depended on a live network fetch is not reproducible from the record. This is a case where the security fix and the correctness fix are the same fix.

**Affected AD:** AD-7 (registry entry), AD-5 (egress the redaction rule does not contemplate), AD-4 (I/O in a pure component), AD-2/FR68 (non-reproducible verdict).

**Severity:** Critical.

**Rule text that closes it** — append to AD-7:

> Every registry entry is **total, bounded and I/O-free**: it terminates on all inputs, it consumes bounded time and memory on adversarial input, and it performs no network, filesystem or process access. `citation-resolves` resolves **within a closed set** — the frozen case's evidence set and answer key, supplied to the verifier as data — and performs **no dereference of any locator originating in model or tool output**. A check that would require a network call is not a verifier; it is an `EvidenceRequest` fulfilled by the driver through a port, recorded, and replayed from the record thereafter.

### S-3 — `regex-match` is unbounded computation in a core that cannot hold a clock, inside a process it shares with the customer's agent · **High**

**Attack.** `regex-match` compiles a **contract-supplied pattern** and evaluates it against **attacker-influenced text**. Python's `re` is a backtracking engine; a pattern such as `(a+)+$` against a crafted subject exhibits catastrophic backtracking — exponential time, single-threaded, uninterruptible. Both halves of the input are reachable: a hostile contract supplies the pattern, or a merely careless contract supplies a fragile one and a poisoned tool result supplies the subject.

What makes this architectural rather than a code-review note is where the mitigation would have to live:

- The Consistency Conventions state **"The clock is a port; core code never calls `datetime.now`."** The core therefore *cannot* time-bound its own execution without breaking the purity rule that makes it replayable. The mitigation is foreclosed by an invariant.
- AD-20 places fail-closed on Gate-verdict unavailability. A hang is not unavailability — nothing raises, nothing returns, the FR2 ladder is never consulted. The §10 posture models fail-open and fail-closed and has no state for *does not terminate*.
- **The system view puts the governor and the host agent in a single OS process.** So a wedged verifier is not a governor failure; it is the customer's production agent stopping.
- **Therefore it defeats FR91 and AD-11.** Shadow mode's entire proposition (UJ-1) is that it cannot hurt you, and AD-11 discharges that with "the driver applies no halts." That is a statement about **policy application**. It says nothing about **resource consumption**, and resource consumption is shared. A shadow-mode governor that hangs a production agent has done precisely the thing FR91 exists to promise it cannot. This is the single most damaging finding for the product's stated adoption path, because it converts the safest-sounding mode into the one with an unbounded failure.

**Affected AD:** AD-7 (unbounded entry), AD-11 and FR91 (the "cannot hurt you" claim), AD-20 and §10 (unmodelled non-terminating state).

**Severity:** High. Not Critical only because it is availability rather than confidentiality or integrity — but it is availability *of someone else's production system*, via the mode marketed as risk-free.

**Rule text that closes it** — append to AD-7 (first sentence shared with S-2), and to AD-20:

> AD-7: `regex-match` patterns are validated at contract-validation time and rejected unless they evaluate in time linear in subject length; nested quantification and back-references are refused. Subject length is bounded and the bound is declared in the manifest.
>
> AD-20: **Non-termination is a third posture and it is placed at the driver.** Every `EvidenceRequest` fulfilment and every core operation invoked on untrusted content is executed under a driver-owned deadline measured on the `ClockPort`. A deadline breach is a failure with a type: an advisor that breaches is deregistered (fail-open, FR85); a Gate execution that breaches is Gate-verdict unavailability (fail-closed, FR87). The shadow driver applies neither halt but **does** enforce the deadline, because FR91 promises the host will not be altered and an unbounded computation in a shared process alters it.

### S-24 — Answer-key and evidence paths are contract-influenced and unconstrained · **Medium**

`exact-match-against-answer-key` implies the verifier is given an answer key, which lives on disk (`cases/`) and is selected by something — plausibly a contract or case field. Nothing in the spine constrains that selector. A `../` reaches arbitrary files, whose contents then influence a verdict and, through FR26's per-criterion breakdown, become observable. Same for whatever names an entry in the evidence store.

**Rule text** — append to AD-7:

> No verifier receives a path. Answer keys and case evidence are resolved by **identifier** against the frozen, hashed case set by the driver, and supplied to the verifier as data. Identifiers are opaque and validated against the case-set manifest; no path component crosses the contract boundary.

### S-25 — Field addressing is unspecified, and an expression language would reopen AD-7 · **Medium**

The spine enumerates the verifier types with care and never says how a criterion *names the deliverable field it verifies*. If the answer is JSONPath, JMESPath, a Jinja expression or a Python attribute path, then a query or expression evaluator crosses the contract boundary — some with known injection and resource-exhaustion issues of their own — and "no expression ... crosses the contract boundary" becomes false while the registry stays technically closed.

**Rule text** — append to AD-7:

> A criterion addresses a deliverable field by a **literal path of names and indices**. No expression language, query language, template or wildcard crosses the contract boundary; a path that does not resolve is a criterion failure, never an error.

### S-23 — The gate is an answer-key oracle · **Medium, MVP-acceptable, disclose**

FR26 records which specific criteria passed and failed. FR24 performs "a targeted retry against the specific unmet fields." With `exact-match-against-answer-key`, that is a per-criterion oracle with a feedback loop attached. Over enough retries an agent — adversarial, or merely an optimizer doing its job — extracts the key one field at a time, and the resulting `reference-backed` pass measures memorization rather than capability. This is an evidence-integrity issue rather than a classical security one, but evidence integrity is this product's security property.

MVP-acceptable because the cases are synthetic and the agent is not adversarial. Worth one sentence so it is a known limit rather than a discovered one:

> The retry feedback surfaced under FR24 names the **unmet criterion**, never the expected value. A `reference-backed` comparand is never returned above the gate.

### Weaponising validation itself

Beyond parse-time (S-1), contract validation has one further property worth naming: FR9 requires warning on a well-formed but internally unsatisfiable contract — a floor unreachable within the ceiling. That check reasons about cost and reachability, i.e. it is a small solver over contract-supplied numbers. It should be explicitly bounded and non-iterative, and it must run **after** the contract hash is computed so that a contract that defeats the check is still identified in the refusal record. Both follow from the S-1 rule text as written.

---

## 3. Prompt injection — is the blast radius genuinely bounded?

**Partly, and better than most.** The spine deserves real credit here, and then two paths through it.

### What genuinely holds

Three separations bound the classic attack — *poisoned tool content induces an early sufficiency stop* — and they hold structurally rather than by discipline:

- **FR20 + AD-7.** Deterministic criterion-level validation is authoritative; the rubric judge cannot establish a pass alone and cannot override a deterministic failure. Injection aimed at the judge cannot manufacture sufficiency.
- **AD-18.** The marginal-value estimator "may only ever **propose** `low-value`," and the Policy — not the estimator — rejects any such proposal touching an unmet mandatory criterion, recording the attempt as an FR99 violation. So injection aimed at the estimator not only fails to starve the floor, it **leaves evidence**. That is unusually good design: the attack path is instrumented, not merely blocked.
- **AD-4.** Advisors are pure and cannot act. There is no "the model decided to skip verification" path because no advisor can decide anything.

Between them, the direct early-stop attack is closed and the direct wrongful-denial attack is closed *for mandatory criteria*. That is the right pair of things to have closed.

### S-18 — The path through: injection reaches sufficiency through weak verification, not through any advisor · **Medium; MVP-acceptable but must be reframed**

**Attack.** Nothing needs to defeat FR20. The attacker aims one layer lower: induce a deliverable in which every mandatory criterion is **present, correctly typed, in range, and wrong**. Against `constraint-backed` verifiers — which §8.2a concedes is what production workloads collapse to, since answer keys do not exist there — that deliverable passes deterministically. The gate is not fooled; the gate is working exactly as designed on a mode that checks shape rather than truth.

The PRD treats §8.2a as an **epistemic** limit ("the honest boundary of the strongest claim") and handles it with disclosure (FR21 labelling). It is also a **security** limit: `constraint-backed` sufficiency is not resistant to an adversary who controls content, and the FR21 label — which was designed to say *we could not verify correctness* — happens to be exactly the right marker for *this verdict is adversary-reachable*. The spine should say so, because a reader who takes AD-7 plus FR20 as an injection defence will over-trust a `constraint-backed` pass.

**Disposition:** MVP-acceptable — the cases are synthetic and `reference-backed`. The reframe is required.

**Rule text** — append to AD-18:

> The floor protection in this rule bounds what an **advisor** can do. It does not bound what **content** can do: a `constraint-backed` pass verifies shape, not truth, and is therefore reachable by an adversary who controls the deliverable's content. The FR21 qualifier is the marker for that reachability as well as for the epistemic limit in §8.2a, and no security property may be claimed from a `constraint-backed` verdict.

### S-21 — The evidence capsule is a laundering channel · **High**

**Attack.** AD-5 permits `compress-to-capsule (FR37)` to see raw content and admits the **capsule** into the durable record. FR37/FR38 and the PRD glossary define a capsule as preserving "citations, identifiers, figures, policy clauses and contract-required attributable facts **verbatim**," and FR71 measures the system on how faithfully it does so. So the capsule is a component that is (a) produced by a model-derived operation over hostile text, (b) **required** to carry that text through faithfully, (c) durable, and (d) fed back into subsequent context.

That is a persistent prompt-injection carrier with a fidelity requirement attached, and nothing in the spine marks it untrusted on the way back in. Injected instructions that survive compression — which they will, since the compressor is optimized to preserve exactly the kind of specific literal content that instructions are — persist across every subsequent step of the run and into the record. Worse, the compressor is the one place where an attacker gets to influence *what the governor believes it observed*: an injection that suppresses an inconvenient fact from the capsule attacks FR38 and FR71 directly, and the fidelity measurement that would catch it is computed by the same pipeline.

**Affected AD:** AD-5 (the carve-out), AD-19 (where capsules should live — see S-10).

**Severity:** High.

**Rule text** — a new invariant is warranted, because this concern is currently spread across AD-4, AD-5 and AD-18 and owned by none of them:

> ### AD-21 — Untrusted content is data, never instruction
>
> - **Binds:** F4, F6, F7, §9, NFR5, FR22, FR37, FR38, FR53
> - **Prevents:** A poisoned tool result being laundered through compression into a durable capsule, read back as though it were the governor's own observation, and carried into every later step and into the record.
> - **Rule:** Tool results, model completions, deliverable content and evidence capsules are **untrusted data wherever they are handled**. They reach a model-derived advisor only in a delimited, typed data position, never concatenated into an instruction position, and never in a system position. A capsule is untrusted on the way out exactly as its source was on the way in: it carries no authority, cites no contract clause, and can never be the source of a `policy_action` or a `decision_reason`. No verdict, estimate or reason code is ever taken from a claim the content made about itself.

### S-20 — No bound on the governor's own loop · **Medium**

**Attack.** AD-4 establishes the cycle: an advisor emits an `EvidenceRequest`, the driver fulfils it via a port, appends the outcome, and **re-invokes the advisor with the result**. Nothing bounds the number of iterations of that cycle per decision. The Loop Fuse (F5, FR27) governs the *host agent's* iterations — repeated state, repeated tool arguments, iteration limit — and is not described as observing the governor's internal fixpoint at all.

Injection that keeps the complexity or confidence estimator unsettled therefore drives repeated `EvidenceRequest` fulfilments, each debited as governor overhead (AD-4). The ceiling eventually stops it and FR101 protects the reserve, so the damage is bounded — but the bound is "the customer's entire budget," reached through the *governor's own* spending, in a product whose thesis is that the governor saves money. An attacker turns the cost governor into a cost amplifier and the ablation numbers in FR62 absorb the result.

**Rule text** — append to AD-4:

> An advisor is re-invoked a **bounded** number of times per decision; the bound is declared and recorded in the manifest. A decision that reaches the bound is resolved without that advisor and the advisor is deregistered as degraded (AD-20). The Loop Fuse governs the host's loop; nothing else bounds the governor's own, so this bound is stated here.

### S-19 — Injection can terminate any governed run · **Low; MVP-acceptable, disclose**

FR27 halts on repeated state, no new evidence across N iterations, or repeated tool arguments. A poisoned tool that returns byte-identical content on every call drives the progress fingerprint to stall and the run halts with `halt-no-progress`. This is arguably the fuse working correctly — a run that is genuinely not progressing should stop — but it means an attacker with influence over any tool has a reliable, cheap kill switch on any governed run, and the terminal reason recorded will be a governance outcome rather than an attack indication. Availability only, and the alternative (continuing to burn budget) is worse. Worth one line in the spine's Deferred or Open Questions so the pattern is recognisable if it shows up in the failure statistics.

### Denial-of-service against the *gate*, in shadow mode

Worth restating in this section because it is the injection scenario with the worst consequence: per S-3, content that triggers catastrophic backtracking in a `regex-match` verifier is *content-driven* — it is prompt injection whose payload is a pathological string rather than an instruction. In shadow mode, in a shared process, that hangs a production agent. The AD-20 deadline rule proposed under S-3 is the control for this, and it is the reason that rule must apply to the shadow driver too.

---

## 4. Human-approval gate integrity

§9 lists "Human control is enforced, and bounded" among the product's Responsible AI commitments, and FR34 states that "a contract that requires approval and a runtime that does not enforce it is a governance defect, not a configuration choice." Three findings, of which the first is the most consequential in this review after S-1 and S-2.

### S-4 — Approval enforcement is cooperative, and conformance cannot detect the failure it exists to detect · **High**

**Attack.** Trace the enforcement point.

- AD-1: "A host adapter **proposes** a step and **applies** the returned verdict." The governor returns `pause-for-approval`; the *adapter* is what must not execute the tool.
- AD-15: the conformance battery — including "approval pause observed" — is "asserted **against the resulting decision log**, never against adapter internals."

The decision log records what the **governor decided**. It cannot record what the **adapter did**, because the adapter is what writes to the world and the governor is not in that path for tool execution. So an adapter that reports the pause and executes the call anyway — through a bug, a race, a framework's internal retry, a partial integration, or deliberately — produces a decision log that is **indistinguishable from correct behaviour**, and passes conformance.

That is the precise inversion of the product's premise: the audit trail is clean at exactly the moment the governance failed, and the evidence system certifies the failure as a success. Note also that this is the one failure mode with real-world consequences attached — FR33 exists specifically because side-effecting tools are the ones where suppression must not be optimization-driven, i.e. the spine already knows which calls matter.

The architecture already contains the fix and does not use it. The system view shows `GOV --> TOOLS` — the governor reaching workload tool implementations directly. AD-1 says the adapter applies the verdict. **The spine is internally ambiguous about who actually invokes a tool**, and the ambiguity is exactly where the bypass lives.

**Affected AD:** AD-1 (enforcement point), AD-12 (gate), AD-15 (conformance blindness), and FR34/FR89/§9 as claims.

**Severity:** High. It is a governance bypass that the system of record cannot observe.

**Rule text** — append to AD-12 and to AD-15:

> AD-12: For a tool the contract declares **side-effecting** or subject to `human_approval_conditions`, invocation goes **through the governor's `ToolPort`**. The adapter proposes and receives a result; it does not hold the call. Enforcement of a human gate is a property of the governor, not of the adapter's cooperation. For all other tools AD-1 stands unchanged.
>
> AD-15: The approval and denial scenarios are asserted with **sentinel tools that record their own invocation out of band**. Passing requires both that the log shows the pause or the denial **and** that the sentinel shows no invocation. A suite that reads only the log cannot detect an adapter that reports a pause and calls the tool anyway, which is the only adapter failure that matters.

The sentinel rule is worth adopting even if the `ToolPort` change is not, because it preserves AD-15's virtue — no inspection of adapter internals — while removing its blind spot.

### S-5 — An approval is an unbound boolean · **High**

**Attack.** AD-12 defines the port, defines "unavailable," and never defines what an approval *is as evidence*. Consequences, each a distinct weakness:

- **No approver identity.** §9's headline governance claim is human control; the record cannot say who exercised it. For the scripted MVP decider that is fine; for the claim built on it, it is not.
- **No binding to the call.** An approval granted for tool call A is, in the record, indistinguishable from one granted for call B. UJ-3's Dana cannot verify that the approval she is reading authorized the action next to it. AD-6's canonical tool-call key is precisely the binding token and is already computed for other reasons.
- **No single-use, no expiry on the grant.** An approval that arrives, or is re-read, after the pause window can be applied to a later call.
- **Race.** AD-3 permits the host to "execute approved steps in parallel." Approval is per-call; a batch containing an approved call and a pending one is executed by one code path, and the spine says nothing about how a pause inside a batch is honoured or how reservations settle across it.

**Rule text** — append to AD-12:

> An approval is **evidence, not a boolean**. Every approval outcome records the **canonical tool-call key** (AD-6) it was granted against, the contract clause that triggered the gate, the decider identity, and the decision index at which it was requested. The driver refuses an approval whose bound key is not the key of the pending call, and refuses one already applied. An approval is single-use and expires with the pause. A batch containing a gated call is not dispatched until that call's gate resolves.

### S-6 — `approval_timeout` has no owner · **High**

**Attack.** FR95 is emphatic that an unbounded pause is "an outage wearing a governance costume." The spine never says who measures the timeout. The core has no clock by construction ("The clock is a port; core code never calls `datetime.now`"). If the adapter waits, then the bound is adapter-controlled and an adapter that simply never returns produces the unbounded pause FR95 forbids — a governance gate that silently kills the run, with no `approval-timeout` recorded because nothing fired. If the driver polls, the granularity is the driver's and should be stated. Either way this is a placement question, which is exactly what this document is for, and it is unplaced.

**Rule text** — append to AD-12:

> The **driver owns the timeout**, measured on the `ClockPort`. No adapter may hold a pause open: an adapter that does not return within `approval_timeout` is approval-channel unavailability under FR89, resolved through the FR2 ladder. Where `on_timeout` is unspecified, FR95's default triple applies.

---

## 5. Audit-trail integrity

### S-7 — The system of record has no integrity structure, and it is the evidence for external claims made by the interested party · **High**

**Attack.** AD-16: SQLite, one file per run, "the record writer exposes append only; no `UPDATE` or `DELETE` is issued against the decision table." That is a statement about **this writer**. It is not a property of the file. Any process with write access — including the host agent, which shares the OS process and can therefore `import sqlite3` and open the same path — can rewrite any row, delete any row, or replace the file wholesale. There is no chaining, no MAC, no signature, no external anchor, no seal. AD-16 additionally discharges NFR12 retention by "deleting whole files," so deletion is a supported operation on the system of record.

**Does it matter?** For internal consistency, barely — the process is not adversarial to itself. For the **external** claim, materially, and the PRD has already accepted the relevant threat model. §8.1: *"The baseline is defined by the party who benefits from it losing. Publishing its definition is the only defence against that."* §8 then builds an entire falsifiability apparatus on that insight — frozen baseline (FR64), hashed rubric (FR65), preregistered targets (FR66), sealed evaluation set (§8.5), FR102's requirement that the harness "record the moment preregistration completed and the moment evaluation-set execution began, and refuse any comparison in which the latter precedes the former."

Every one of those artifacts is written by the same harness, to the same filesystem, under the same user, and the ordering proof in FR102 is a comparison between two timestamps that the interested party wrote. AD-9 requires a manifest and AD-10 requires the gates; nothing makes any of it checkable by a reader. The apparatus is sound in design and unanchored in fact.

This is not an allegation of intent. It is the observation that §8 already makes about the baseline, applied to the record — and it is the difference between an evidence system and a reporting system.

**Affected AD:** AD-2 (whose "Anything not in the log did not happen" needs a converse it does not have), AD-16, AD-9 and AD-10 (whose controls are only as good as the artifacts they read), FR102.

**Severity:** High. Low exploitation difficulty, and it undermines the product's differentiating claim rather than a side feature.

**What makes this cheap:** AD-6 already mandates a single canonicaliser producing canonical JSON and SHA-256. A hash chain is that function applied to rows instead of contracts. No new machinery, no new dependency, no measurable cost.

**Rule text** — append to AD-16:

> Append-only is enforced by the **schema**, not by the writer's manners: `BEFORE UPDATE` and `BEFORE DELETE` triggers on the decision table `RAISE(ABORT)`. Every row carries `prev_row_hash` and `row_hash`, computed by the AD-6 canonicaliser over the row's canonical form, so the log is a hash chain. The run's final row **seals** the chain, and the sealed head is recorded in the proof card (FR97) and published with any external claim. The preregistration record, the frozen baseline definition and the rubric are hashed the same way, and their hashes are recorded in the manifest at run start — so FR102's ordering claim rests on content that existed at the recorded time rather than on a timestamp alone.
>
> Chaining does not stop a determined local operator, and it is not offered as though it did. It converts a silent edit into a visible one and gives an external reader something to check, which is the whole of what §8 asks for everywhere else.

### S-8 — Append-only is discipline where it could be structure · **Medium**

Folded into the rule text above. The trigger pair is six lines of DDL and turns AD-16's central promise from a convention into a constraint the database enforces against every writer, including one the project did not write.

### S-9 — "Appended before it takes effect" is not defined as durable · **Medium**

**Attack.** AD-2's ordering guarantee is the spine's strongest audit invariant, and "appended" is undefined. Under SQLite's WAL journal with `synchronous=NORMAL` — a common default choice — a committed transaction can be lost on power failure or OS crash. The run then resumes, or is examined, with a log whose tail disagrees with what actually happened: the decision took effect and is not recorded, which is the exact condition AD-2 exists to make impossible. It also lands the system in FR88 (ledger state lost or unreliable) with a record that cannot explain why.

**Rule text** — append to AD-2 or AD-16:

> "Appended" means **committed and flushed to durable storage** before the verdict is returned. The database is opened with `journal_mode=WAL` and `synchronous=FULL`; run database files and the evidence store are created `0600`/`0700` respectively. A write that cannot be confirmed durable is ledger-state unreliability under FR88.

### S-26 — AD-10 admissibility permits both arms on the unreportable route · **Medium**

**Attack.** The deployment diagram annotates the direct path to model endpoints `dev and demo only, never reportable`. AD-10's admissibility gate requires "**both arms of a comparison used the same route**" — which is satisfied by *both arms direct*. A comparison run entirely off the gateway is therefore admissible, contradicting the diagram and hollowing out F15's independence purpose. The Independence gate catches it as `self-reported` (FR80), so the figure is labelled rather than refused — but the diagram says refused, and where two parts of the spine disagree about a publication control, the weaker one wins in practice.

**Rule text** — amend AD-10 admissibility:

> ... both arms of a comparison used the same route, **and a headline claim was drawn from the `apim` route**; a comparison executed wholly on the direct route is a dev or demo artifact and is refused, not labelled.

---

## 6. Data protection — does the transient/durable split hold?

**The design is genuinely good and the split does not hold as written**, because of one carve-out and one ambiguous noun.

AD-5 is the best-reasoned data-protection rule I have seen in an architecture document of this kind: it identifies that some core operations *cannot* function without raw content, names them exhaustively rather than hand-waving, and confines them. That is the right shape. The problem is in the exit list.

### S-10 — AD-5's own carve-out defeats AD-5 · **High**

**Attack.** AD-5 states what may cross into the record: "scores, estimates, envelopes, **capsules**, canonical keys and content hashes."

An evidence capsule is defined by FR37/FR38 and the PRD glossary as *"compressed, structured tool output that preserves citations, identifiers, figures, policy clauses and contract-required attributable facts **verbatim**."* FR71 measures the system on the fidelity of that preservation — the product is graded on how much of the raw content survives.

So the decision log, which AD-5 declares free of tool results and NFR5 requires to be redacted before persistence, contains — by requirement, by design, and with a metric attached — verbatim excerpts of tool results. In a document-investigation or supply-chain workload, "identifiers" and "policy clauses" is where the sensitive content lives. AD-5's own final sentence, "Durable raw content lives solely in the evidence store (AD-19)," is contradicted three clauses earlier by its own list.

**Affected AD:** AD-5 (internal contradiction), AD-19 (where capsules belong), NFR5 and FR56 (the requirement both are meant to discharge), and AD-17 by composition — see S-12.

**Severity:** High.

**Rule text** — amend AD-5:

> What crosses into the record is derived only: scores, estimates, envelopes, canonical **key hashes** and content hashes. **An evidence capsule does not enter the decision log.** It is written to the evidence store (AD-19) under the same access control and retention bound as raw tool output, and what crosses into the record is its hash, its size and its FR71 fidelity measurement. A capsule is compressed sensitive content, not derived metadata, and the compression ratio is not a redaction.

### S-11 — "Canonical keys" is on the wrong side of the boundary · **Medium**

**Attack.** AD-6 canonicalises "tool name and arguments" into canonical JSON, then SHA-256s it. AD-5 permits "canonical keys" into the record. If the key is the hash, this is correct and safe. If the key is the canonical JSON, then **raw tool arguments are in the decision log**, in a normalised form that makes them easier to read, directly violating AD-5's own opening sentence and NFR5. UJ-3 suggests the second reading is live: Dana "sees ... a tool call denied as a duplicate, with the canonicalized key that matched" — a hash tells her nothing, so something readable is intended.

The tension is real and it is not merely editorial: the audit story wants legibility, the privacy rule wants opacity, and the spine currently promises both with one ambiguous noun. Resolve it in favour of the privacy rule and give legibility a redacted surrogate.

**Rule text** — folded into the S-10 amendment above (`canonical **key hashes**`), plus:

> Where a human-facing surface must show *why* two calls matched, it shows the tool name and the **redacted argument shape** — field names, types, and hashes of values — never the values themselves.

### S-12 — There is an in-spec path from raw tool content to the third-party HTML artifact · **High**

**Attack.** Compose the permitted flows; no bug is required at any step.

1. A tool returns sensitive content (customer document, supplier record, internal identifiers).
2. `compress-to-capsule` sees it lawfully under AD-5 and preserves the identifiers **verbatim** by FR38.
3. The capsule enters the decision log, lawfully under AD-5's exit list (S-10).
4. AD-17 generates "a self-contained file per comparison, embedding the replay timeline, ledger state at each decision, the rendered proof card and **enough record to satisfy FR76 offline**." FR76 is "drilling into a single run's decision record" — i.e. the record, including step 3.
5. The self-contained file is handed to a third party. F16 consumes it; the submission is judged by people outside the organisation; FR84 requires showing "a governor decision stream."

Every step is permitted by a stated rule. The output is verbatim customer content in a file distributed outside the trust boundary. AD-17's `Prevents:` clause is about FR77 read-only-ness; nobody asked what leaves.

The proximate cause is S-10, but the fix is separate and independently valuable, because "the generator reads the record" is a standing hazard even after capsules move: any future field added to the record is automatically in the artifact.

**Rule text** — append to AD-17:

> The generator consumes an **explicit allow-list of record fields**, never "the record". Capsules, canonical argument text, deliverable bodies and raw tool output are structurally unavailable to it — it is invoked with a projection, not with a database handle. The conformance battery includes a **leak assertion**: an artifact generated from a case seeded with canary strings in every raw position contains none of them. A field added to the record is absent from the artifact until it is added to the allow-list, which is the correct default for a file that leaves the building.

### S-13 — Autoescaping is claimed; script-context escaping is not · **High**

**Attack.** AD-17's "HTML generation autoescapes; record content is untrusted input" is the right instinct and better than most specs manage. It is also insufficient for what AD-17 requires. A **self-contained** offline artifact with a replay timeline and drill-down needs the record embedded as data, which means a JSON island or an inline script. Jinja2's autoescape applies HTML entity escaping in HTML text and attribute contexts; inside a `<script>` element the parser is in script data state, and the literal sequence `</script>` in a JSON string terminates the block irrespective of entity escaping. Attacker-controlled content reaches that position through any recorded free-text field — capsule content, a canonical key, an error message, a criterion name drawn from the contract.

The result is stored XSS in a file that is opened by judges, auditors and prospects, from local disk, often with `file://` origin privileges.

**Rule text** — append to AD-17:

> Untrusted values are emitted in HTML text or attribute positions only, **never into a script context**. Embedded data is served from a `<script type="application/json">` block with `<`, `>` and `&` escaped in the serialised output, parsed by a script that is itself static; the page declares a Content-Security-Policy forbidding inline and remote script beyond that. There is no running viewer process and there is no executing record content.

### S-14 — Errors are the redaction hole · **Medium**

**Attack.** The Consistency Conventions require that "ports translate foreign exceptions at the boundary" — again the right instinct — and never say the translated error must be free of the payload that caused it. In this stack that is not a hypothetical: pydantic `ValidationError` includes an `input` field carrying the offending value by default, so a malformed tool result produces an exception whose text *is* the tool result. That text then reaches application logs (which NFR5 covers and the spine's own Logging convention does not mention redaction for), stack traces, and any error field on a decision row.

**Rule text** — append to AD-5 or the Errors convention row:

> A translated port error carries a type, a code and a **redacted** message: no request body, no response body, no headers, no credential material, and no `input` value from a validation error. This obligation applies to application logs and stack traces exactly as it applies to the decision record — NFR5 is about persistence, and a stack trace persists.

### S-15 — AD-19's "access-controlled" is decorative · **Medium**

**Attack.** AD-19 says the evidence store is "access-controlled and retention-bounded under NFR12" and that "Only the harness reads it." No mechanism is named for either. The deployment is a developer workstation; the store is a directory; the host agent and every tool implementation run in the same process as the governor and under the same user, so any tool with filesystem access reads the whole store — including the raw tool outputs of every prior run that has not been swept. Meanwhile NFR12 requires "a declared retention period," and no period is declared anywhere in the spine (S-17), so the bound is a bound in name.

Two acceptable resolutions, and the spine should pick one rather than leaving a claim that the deployment does not support:

**Rule text** — append to AD-19:

> "Access-controlled" names a mechanism: a per-run directory created `0700` beneath a root owned by the harness, holding no content from any other run, with a **declared retention period recorded in the run manifest** and enforced by a dated sweep the harness runs at start. Where the deployment cannot support a stronger control than filesystem permissions — as the MVP workstation cannot — the spine says so here rather than implying more.

### S-16 — Blind-review isolation should be a fact about arguments, not about code · **Medium**

AD-19's structurally-denied claim is the most security-shaped statement in the spine, and it is one sentence away from being verifiable. As written, "the renderer is structurally denied access to the gate verdict, the decision record and the run manifest" is a property of the renderer's implementation — which drifts, and whose drift silently invalidates false-sufficiency rate, the counter-metric the headline claim rests on. As an argument shape it is checkable by inspection and cannot drift.

**Rule text** — append to AD-19:

> The FR69 blind-review renderer is a **separate process invoked with the evidence path and the contract path only**. It is never given the run database path, so its isolation is a fact about its arguments rather than a promise about its code. The packet it emits records the paths it was given, so a reviewer can confirm the isolation held for their packet.

### S-17 — Retention is declared nowhere · **Low; MVP-acceptable with a number**

NFR12 requires a declared retention period; AD-16 and AD-19 discharge retention by "archiving or deleting whole files"; no period appears in the spine, and no component owns the sweep. This is a promise with no owner. The S-15 rule text supplies both.

---

## 7. Secrets and least privilege

### What holds

Two conventions are exactly right and should be preserved verbatim: **"secrets come from environment only"** and **"No credential ever appears in a contract (NFR7)."** AD-13's containment of LiteLLM behind `ModelPort` — "no LiteLLM type, exception or cost table appears above the port" — is justified in the spine on measurement grounds and happens to be a strong security control as well, since provider SDK exceptions are a routine credential-leak vector. Worth naming the second benefit so a later contributor does not relax the rule for a measurement-only reason.

### S-22 — In-process co-tenancy defeats NFR7, and `permitted tools` is authorization rather than isolation · **Medium; MVP-acceptable with disclosure**

**Attack.** The system view places the host agent loop, the governor, the tool implementations and the model adapter in a **single OS process**. Environment variables are process-global. Therefore:

- Every tool implementation can read every credential in the environment, including credentials for tools the contract does not permit.
- FR7's `permitted tools` is an **authorization list the governor enforces at the decision point**. It is not a capability boundary. A tool that is called anyway — by the agent, by a framework's internal path, by an adapter bug (S-4) — is not short of credentials.
- NFR7's "least-privilege identity" is therefore achievable only at the granularity of the whole process, not per tool, and the spine implies otherwise by pairing NFR7 with a per-contract tool list.
- Any tool with file-read or shell capability exposes `os.environ`, and any prompt injection that reaches such a tool exfiltrates every credential the process holds. This is the standard confused-deputy shape and the governor does not change it — it is not a sandbox and does not claim to be, but a reader may infer that it is.

**Disposition:** MVP-acceptable. Process isolation per tool is out of scope and correctly so. But an unstated limit on a security NFR reads as a met requirement.

**Rule text** — add to the Consistency Conventions `Config` row or as a note under the system view:

> Credentials are read **once at the composition root** into port-local holders; no advisor, no core module and no tool implementation reads `os.environ`. NFR7 is discharged at the granularity of the process: the governor, the host agent and the tool implementations are co-resident by design (§4.2), so a contract's `permitted tools` list is an **authorization** control enforced at the decision point, not a capability boundary around credentials. Per-tool credential isolation requires the out-of-process deployment listed under Deferred.

### S-27 — No locked, hash-verified dependency set · **Medium**

The Stack table pins versions in prose and the verification review confirmed each. Neither makes an install reproducible or tamper-evident: transitive dependencies float, and a compromised or yanked-and-republished package enters silently. For an ordinary application that is routine supply-chain risk (A06/A08). For **this** application the dependency closure is part of the evidence — FR68 requires any reported run to be re-executable from its recorded configuration, and a configuration that does not pin its dependency closure is not sufficient to re-execute anything.

**Rule text** — append to the Stack section:

> Dependencies are installed from a committed `uv.lock` with hashes; `--frozen` in every environment that produces a reportable run. The lock file's hash is recorded in the run manifest (AD-9), because FR68 re-executability is a claim about the whole closure and not only about the versions this table names.

### S-28 — The contract is a third-party-visible artifact · **Low**

FR84 requires the submission to show "at minimum the Outcome Contract," and AD-17's artifact is handed outside the organisation. NFR7's no-credential-in-a-contract rule is therefore not only hygiene against accidental commits — it is a **disclosure** rule about a document that will be published. Contracts also carry `permitted tools`, `human_approval_conditions` and answer-key references, which together describe an internal control surface. One line is enough:

> A contract is a **published** artifact wherever FR84 or AD-17 applies. NFR7's prohibition is therefore a disclosure control, not only a hygiene one, and any contract field that would not survive publication does not belong in a contract.

---

## 8. What the spine gets right

Recording this because a review that lists only defects mis-states the artifact, and because several of these are the reason the defect list is as short as it is.

- **AD-4's four single writers** eliminate a large class of confused-deputy and race conditions by construction. "Disabled means not registered" removes conditional branches from safety-critical code, which is both a correctness and a security property.
- **AD-18** is the standout. Putting floor protection in the Policy rather than the pluggable estimator means the one non-negotiable rule cannot be removed by swapping a component — and recording the rejected proposal as an FR99 violation means the attack path is *instrumented*, not merely blocked. Most designs would have put the carve-out in the estimator and never noticed.
- **AD-11's "shadow mode is a driver, not a flag"** removes conditionals from the least-tested branch of the most safety-critical code. That is a security argument even though the spine makes it as a testing argument.
- **AD-5's shape** — enumerate exactly which operations cannot function without raw content, confine them, define what crosses — is the correct method. The findings against it are about the exit list, not the approach.
- **AD-17's "generated, not served"** removes an entire attack surface. No process, no endpoint, no authentication to get wrong, no path from the viewer to execution. This is defence by deletion and it is the right call.
- **AD-8's owned schema and immutable reason registry** means audit records retain meaning over time. Immutability of published codes is precisely the property forensic value depends on.
- **AD-14's run-scoped cache** discharges NFR6 structurally rather than with a partitioning scheme that could be got wrong, and the Deferred entry correctly identifies tenant partitioning as the cost of ever changing that.
- **AD-10's admissibility/independence/accompaniment split** — hard gates that refuse, graded gates that label — is a well-judged distinction that most reporting layers collapse.
- **AD-2's log-before-effect** is the correct ordering and the foundation everything in §5 builds on. The finding there is that it needs a durability definition and a chain, not that the ordering is wrong.

---

## 9. Disposition

### Fix in the spine before implementation begins

| # | Finding | Cost |
| --- | --- | --- |
| S-1 | Safe-loader and bounded parsing for contracts; parse before manifest, refusal still recorded | One paragraph in AD-7 |
| S-2 | `citation-resolves` resolves within a closed set; no network dereference; verifiers are total, bounded, I/O-free | One paragraph in AD-7 |
| S-3 | Bounded `regex-match`; driver-owned deadlines as a third failure posture, applied in shadow too | AD-7 + AD-20 |
| S-4 | `ToolPort` for side-effecting and gated tools; sentinel-based conformance assertions | AD-12 + AD-15 |
| S-5 | Approval binds canonical key, clause, decider identity, decision index; single-use | AD-12 |
| S-6 | Driver owns `approval_timeout` on the `ClockPort`; adapter cannot hold a pause | AD-12 |
| S-7 | Hash-chained rows, schema-enforced append-only, sealed chain head published with claims | AD-16 |
| S-10 | Capsules leave the decision log for the evidence store; hash and fidelity cross instead | AD-5 |
| S-12 | AD-17 consumes an allow-list projection, with a canary leak assertion in conformance | AD-17 |
| S-13 | No untrusted content in a script context; hardened JSON island; CSP | AD-17 |
| S-21 | New AD-21 — untrusted content is data, never instruction | One invariant |

Also cheap and worth taking in the same pass: S-8, S-9, S-11, S-14, S-15, S-16, S-20, S-24, S-25, S-26, S-27, and the S-29 trust-boundary block.

### MVP-acceptable, with disclosure

| # | Finding | Why acceptable | What must be written down |
| --- | --- | --- | --- |
| S-17 | Retention undeclared | Single workstation, synthetic data | A number, in the manifest |
| S-18 | `constraint-backed` sufficiency is adversary-reachable | MVP cases are synthetic and `reference-backed` | That FR21's qualifier is a security marker, not only an epistemic one |
| S-19 | Injection can force `halt-no-progress` | Availability only; halting is the safe outcome | One line under Open Questions |
| S-22 | In-process co-tenancy defeats per-tool least privilege | §4.2 in-process design is deliberate | That `permitted tools` is authorization, not isolation |
| S-23 | Gate as answer-key oracle | Non-adversarial agent, synthetic keys | That retry feedback names criteria, never comparands |
| S-28 | Contracts are published | Already required by FR84 | That NFR7 is a disclosure control |

### Explicitly out of scope, and correctly so

Sandboxing tool implementations; per-tool identity; encryption at rest; multi-tenant deployment; authenticated approval with a real identity provider; signed evidence with an external timestamping anchor. Each belongs to the hosted-governor deployment already listed under Deferred. The recommendation is only that the spine **name** them as deferred security work in that section, so their absence is a decision rather than an omission.

---

## 10. Consolidated rule text

Every proposal above, gathered for drop-in. Nothing here changes an existing invariant's intent; each is an addition or a single-word correction.

**New `## Trust Boundaries` block** — after `## Design Paradigm`. The diagram and three observations from §0.

**AD-2** — append: durability definition from S-9.

**AD-4** — append: bounded advisor re-invocation from S-20.

**AD-5** — amend the exit list to `canonical **key hashes**`; remove `capsules`; append the evidence-store placement (S-10), the redacted-argument-shape surrogate (S-11), and the redacted-error rule (S-14).

**AD-7** — append: total/bounded/I/O-free verifiers and closed-set `citation-resolves` (S-2); bounded `regex-match` (S-3); safe-loader and pre-manifest validation (S-1); identifier-not-path resolution (S-24); literal field paths (S-25); no comparand in retry feedback (S-23).

**AD-10** — amend admissibility: headline claims require the `apim` route (S-26).

**AD-12** — append: `ToolPort` enforcement for side-effecting and gated tools (S-4); approval-as-evidence binding (S-5); driver-owned timeout (S-6).

**AD-15** — append: sentinel-tool assertions for the approval and denial scenarios (S-4).

**AD-16** — append: schema-enforced append-only, hash chain, sealed head, artifact hashes in the manifest (S-7, S-8); file permissions (S-9, S-15).

**AD-17** — append: allow-list projection and canary leak assertion (S-12); script-context and CSP rules (S-13).

**AD-18** — append: the `constraint-backed` reachability note (S-18).

**AD-19** — append: named access mechanism and declared retention (S-15, S-17); blind-review renderer as argument shape (S-16).

**AD-20** — append: non-termination as a third posture, driver-owned deadlines, enforced in shadow (S-3).

**AD-21 (new)** — untrusted content is data, never instruction (S-21).

**Stack** — append: locked, hash-verified dependency closure recorded in the manifest (S-27).

**Consistency Conventions** — `Config` row: composition-root credential handling and the NFR7 scope statement (S-22, S-28). `Errors` row: cross-reference the redacted-error rule (S-14). `Logging` row: state that NFR5 redaction applies to application logs and stack traces.

**Deferred** — add: sandboxed tool execution, per-tool identity, authenticated approval, externally anchored evidence — named as deferred security work belonging to the hosted deployment.

---

## Appendix — Questions the spine should answer before implementation

These are genuine ambiguities rather than defects; each currently resolves to an unsafe default by omission.

1. **What does `citation-resolves` resolve against?** Every reading except "a closed, frozen corpus supplied as data" breaks AD-4 purity, AD-2 replay and FR68 re-executability before it reaches the security objections.
2. **Who invokes a tool?** The system view shows `GOV --> TOOLS`; AD-1 says the adapter applies the verdict. Both cannot be true, and the answer determines whether FR34 is enforced or merely requested.
3. **Is a "canonical key" the JSON or the hash?** AD-5 and UJ-3 pull in opposite directions and NFR5 decides it.
4. **Where does a capsule live?** AD-5 says the record; AD-5's last sentence and AD-19 say the evidence store; NFR5 and FR56 decide it.
5. **Who holds the clock during an approval pause?** The core cannot, by its own convention. FR95's insistence that a pause be bounded needs an owner.
6. **How does a criterion name a field?** The one unspecified parameter in an otherwise exhaustively specified registry.
7. **What is the declared retention period?** NFR12 requires one; no artifact contains one.
