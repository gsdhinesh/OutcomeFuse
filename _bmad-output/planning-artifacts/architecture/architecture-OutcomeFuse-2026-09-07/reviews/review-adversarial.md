# Adversarial Review — ARCHITECTURE-SPINE.md

- **Artifact under attack:** `_bmad-output/planning-artifacts/architecture/architecture-OutcomeFuse-2026-09-07/ARCHITECTURE-SPINE.md`
- **Supporting source:** `_bmad-output/planning-artifacts/prds/prd-OutcomeFuse-2026-09-04/prd.md`
- **Review type:** Constructive adversarial — build two compliant units, show them diverge
- **Review date:** 2026-09-08
- **Method:** For every AD, construct two hypothetical units one level down that each obey the AD's literal text, then attempt to build them incompatibly. Only pairs that actually construct are reported. Nothing here is a readability note; every entry names two units, shows each unit's compliance argument, names the observable divergence, and proposes exact closing rule text.

---

## Verdict

The spine is unusually strong on *ownership of components* and unusually weak on *ownership of shapes and orders*: it names a single writer for spend, a single canonicaliser and a single reportability predicate, but it never declares the schema of the objects those writers exchange (`EvidenceRequest`, ledger view, log entry, comparison arm), never declares the order in which one decision's events reach the log, and never declares the lifetime of the advisor registry. Twenty constructible incompatibilities follow from that gap; three of them silently corrupt the exact number the product exists to publish, and one of them (H4) makes the only natural implementation of the evidence store illegal under AD-5.

---

## Severity index

| # | Hole | Category | Severity |
|---|---|---|---|
| H1 | Composed substitutions have no resolution rule → FR62 per-mechanism breakdown is implementation-defined | Two owners / shared shape | **Critical** |
| H2 | Advisor-registry lifetime unbound → FR85 deregistration leaks across runs in one process | Conflicting mutation paths | **Critical** |
| H3 | Reserve-before-append contradicts AD-2; no canonical decision-cycle order | Ordering | **Critical** |
| H4 | Nobody legal may write the evidence store | Two owners / boundary | **High** |
| H5 | Comparison-arm equality and label propagation undefined | Shared shape | **High** |
| H6 | Shadow counterfactual after a would-be terminal decision; no arm discriminator on log rows | Conflicting mutation paths | **High** |
| H7 | Preregistration hash absent from the manifest; case-set identity not a content hash | Shared shape | **High** |
| H8 | "Could change the candidate result" predicate is unowned → gate cadence differs | Two owners | **High** |
| H9 | Verifier-entry → `reference-backed`/`constraint-backed` mapping table absent | Under-specified extension point | **High** |
| H10 | Governor-overhead spend is settled but never reserved; reservation release unspecified | Conflicting mutation paths | **High** |
| H11 | `fail-closed` terminal rows: driver-written or Policy-written | Two owners | **High** |
| H12 | `EvidenceRequest` kind set is open and its outcome payload has no schema | Under-specified extension point | **High** |
| H13 | `citation-resolves` needs the evidence store, which AD-19 seals | Boundary evasion | **High** |
| H14 | Log entry kinds unenumerated, yet AD-2 makes the log the sole state source | Shared shape | **High** |
| H15 | OFF is a driver in the layer table but "no governor participation" in FR52 | Boundary / measurement bias | **High** |
| H16 | `quality_state` is both a stamped column and a fold output | Two owners | **Medium-high** |
| H17 | Freeze-time hasher predates the canonicaliser AD-6 says is the only one | Shared shape | **Medium-high** |
| H18 | "Ledger view" is a named shared object defined nowhere | Shared shape | **Medium-high** |
| H19 | Ledger as fold vs ledger as mutable state → FR88/FR100 state-loss case unconstructible | Conflicting mutation paths | **Medium** |
| H20 | Reason-code allocation has no namespace or authority → family collisions | Under-specified extension point | **Medium** |

---

## H1 — Composed substitutions have no resolution rule

**Severity: Critical.** Directly determines the per-mechanism breakdown that AD-10 makes mandatory for any headline figure.

**The two units.**

- **`PrecedencePolicy`** — collects proposals, sorts them by a fixed mechanism precedence, applies the winner only. One step, one substitution, one `decision_reason`, one causing mechanism.
- **`ComposingPolicy`** — collects proposals and applies all compatible ones. On a single step it serves a cached tool result, compresses the surviving context and drops to a cheaper model; it records `policy_action = proceed-with-substitution` and picks the reason code of the mechanism it judges dominant.

**Why each obeys every AD.** AD-4.1 makes every mechanism a pure advisor emitting proposals — satisfied by both. AD-4.3 makes the Policy the only component that converts proposals into a decision — satisfied by both; nothing in AD-4 says *how many* proposals a decision may consume. FR1 demands exactly one `policy_action` and exactly one `decision_reason` — satisfied by both. FR2's ladder governs only terminating and blocking conditions and is silent below `low-value` / `unaffordable`, so it does not rank substitutions.

**The incompatibility.** FR15 requires every unit of spend to be attributed to *the* mechanism that caused it, and FR62 forbids publishing a headline savings figure without its per-mechanism breakdown. Under `PrecedencePolicy` a saved step has exactly one causer. Under `ComposingPolicy` a saved step has three, and the recorded `decision_reason` names one of them arbitrarily — so the breakdown is a function of the tie-break, not of the mechanisms. Worse, the two units produce *different total savings* on the same case, because composition saves more per step than precedence does. AD-4's own "Prevents" clause states its purpose as stopping FR62's ablation from comparing numbers computed differently; that is precisely what these two units do. The FR62 ablation then compounds it: ablating the Model Governor under `ComposingPolicy` removes one layer of a composed saving whose attribution was never separable, so the ablation delta measures the tie-break rather than the mechanism.

**Closing rule — new AD-21, or a fifth numbered clause under AD-4.**

> **AD-21 — Proposal resolution is declared, and attribution follows composition**
>
> - **Binds:** F1, F3, F6, F7, F8, FR1, FR15, FR62, FR104
> - **Rule:** A decision consumes a **proposal set**, not a single proposal. The Policy resolves it in two declared stages.
>   1. **Blocking resolution** — any proposal carrying a terminating or blocking condition is resolved by the FR2 ladder. If one wins, no substitution is applied and the decision ends here.
>   2. **Substitution composition** — remaining `proceed-with-substitution` proposals compose in a fixed, core-declared order: **tool substitution → context substitution → model substitution**. A later stage sees the output of the earlier one. A mechanism that declares a proposal incompatible with an earlier-stage substitution is dropped, and the drop is recorded.
>
>   The decision records **one `policy_action`** and **one `decision_reason`** per FR1, and additionally a **`contributing_mechanisms` list in composition order**. FR15 attribution is per-contribution, not per-decision: each composed substitution carries its own estimated saving, so FR62's breakdown is read off the record rather than inferred from the reason code. Reporting cites the `decision_reason` for narrative and `contributing_mechanisms` for arithmetic; the two are never substituted for one another.

---

## H2 — Advisor-registry lifetime is unbound

**Severity: Critical.** Silently corrupts FR58 repeated runs, FR62 ablation and FR68 re-executability, and produces no error.

**The two units.**

- **`RunScopedAdvisorRegistry`** — the composition root builds a fresh registry per run from the manifest's enabled set; AD-20 deregistration mutates that per-run copy.
- **`ProcessAdvisorRegistry`** — the composition root builds one registry at process start; AD-20 deregistration removes the advisor from it and, since the registry is not rebuilt, the advisor stays gone.

**Why each obeys every AD.** AD-4 says "disabled means not registered" and treats an FR62 ablation as a registry change — neither unit contradicts that. AD-20 says a raising advisor "is deregistered for the remainder of the run"; `ProcessAdvisorRegistry` satisfies that literally (it is certainly deregistered for the remainder of *this* run) and the spine never says re-registration must occur at run boundaries. AD-9 requires the manifest to record the enabled set at start — `ProcessAdvisorRegistry` writes the manifest from the registry as it stands, which is honest per-run. AD-14 run-scopes the *tool cache* explicitly and nothing else, which is the tell: the spine knew to say it once and did not generalise.

**The incompatibility.** FR58 requires repeated runs per case, and the harness naturally executes them in one process. Under `ProcessAdvisorRegistry`, a transient failure of the Context Governor on repeat 1 removes it from repeats 2–30. Every one of those runs is correctly marked degraded per AD-20, so nothing looks broken — but the arm's mean is now the mean of one governed configuration and twenty-nine of a different one, and AD-10's degraded label is applied to runs whose degradation was inherited rather than experienced. `RunScopedAdvisorRegistry` produces a completely different set of thirty runs from identical inputs. FR68 re-executability then fails asymmetrically: replaying run 17 alone from its manifest re-registers the advisor and produces a non-degraded run that does not match its own record.

**Closing rule — tighten AD-20, final paragraph.**

> **The registry is run-scoped.** The advisor registry is constructed by the composition root **once per run** from the manifest's enabled set and is discarded when the run ends. A deregistration under FR85 mutates only the current run's registry; no deregistration outlives the run that caused it, and no process may share a registry instance across runs. A harness executing repeated runs in one process constructs one registry per run. This mirrors AD-14: the registry, like the tool cache, is run-scoped and process-local by construction.

---

## H3 — Reserve-before-append contradicts AD-2, and no canonical event order exists

**Severity: Critical.** Two compliant implementations produce non-identical logs for the same run, which makes AD-15's conformance suite — which asserts against the log — unwritable once.

**The two units.**

- **`AppendThenActDriver`** — reads AD-2's rule text literally: nothing takes effect before it is in the log. Order per decision: append decision → reserve → return verdict → append outcome → settle → append gate verdict.
- **`SequenceDiagramDriver`** — implements the spine's own "One decision" diagram: `P->>L: reserve`, `L-->>P: reserved or rejected`, `P-->>D: policy_action…`, `D->>R: append decision`. Order: reserve → append decision → return verdict → outcome → settle → gate → append gate verdict.

**Why each obeys every AD.** `SequenceDiagramDriver` obeys the spine's normative diagram exactly. `AppendThenActDriver` obeys AD-2's rule text exactly — "Every decision is appended to the log **before it takes effect**" — and argues a reservation is an effect. Both obey AD-3 ("reserved at decision time"), which does not order reservation against the append.

**The incompatibility.** Three distinct failures, all constructible.

1. **The fold diverges from the live run.** AD-2 makes run state a fold over the log. Under `SequenceDiagramDriver`, a crash between `reserve` and `append` leaves reserved budget that exists in no log row; replaying the log yields a different `remaining` than the run actually had, and the crash is invisible. AD-2's own "Prevents" clause names this exact failure — mutable state and the written log drifting apart — and the diagram reintroduces it.
2. **`unaffordable` is unreachable in one unit.** `AppendThenActDriver` must append the decision before it knows whether the reservation succeeded, so it cannot produce `decision_reason = unaffordable` from the reservation result; it must ask the Ledger a pure affordability question first and then reserve, which is a third design. `SequenceDiagramDriver` gets `unaffordable` from `L-->>P: reserved or rejected`. FR104's `unaffordable` code therefore originates from different computations in the two units.
3. **Logs are not comparable.** AD-15 asserts a fixed battery "against the resulting decision log, never against adapter internals." With no canonical intra-decision order, the same scenario yields two legal row orderings, and the conformance suite must either be written twice or weakened to order-insensitive assertions — at which point it cannot assert "the deny was recorded before it was applied," which is the one thing AD-2 exists to guarantee.

**Closing rule — new AD-22, plus a correction to the "One decision" diagram.**

> **AD-22 — The decision cycle has one canonical order**
>
> - **Binds:** F1, F3, F12, F13, AD-2, AD-3, AD-15, FR5, FR53, FR68, FR98
> - **Rule:** Every governed step emits log entries in exactly this order, and a run whose log departs from it is malformed:
>   1. `evidence_request` and `evidence_outcome` pairs, in the order the driver fulfilled them, each with its overhead settlement;
>   2. `decision` — carrying `policy_action`, `decision_reason`, the reservation amount, and `terminal_reason` where the run ends;
>   3. `reservation` — the Ledger's acceptance of the amount named on the decision row;
>   4. `outcome` — the host-reported result of an applied verdict, if any;
>   5. `settlement` — task-work spend, attributed per AD-21;
>   6. `gate_verdict` and the resulting `quality_state`, where the gate executed under FR98;
>   7. `degraded`, appended immediately after the entry during whose production the advisor raised.
>
>   **Affordability is a query; reservation is a write.** The Policy obtains a pure affordability answer from the ledger fold *before* deciding, so `unaffordable` is a decision input rather than a reservation failure. The reservation that follows a decision cannot be rejected; a rejected reservation is a fail-closed condition under FR88, not a routine outcome. The "One decision" sequence diagram is corrected to place `reserve` after `append decision`.

---

## H4 — Nobody legal may write the evidence store

**Severity: High.** A direct contradiction between AD-5 and AD-19 that both compliant units resolve in opposite, incompatible ways.

**The two units.**

- **`DriverEvidenceWriter`** — the driver receives the raw tool result from the tool port as the `outcome` of an applied verdict, writes it to the evidence store keyed by run and step, derives a digest, and appends only the digest to the decision log.
- **`PortDualWriter`** — the tool/model port adapter writes raw content to the evidence store itself and returns to the driver only an evidence handle plus derived values. The driver never holds raw content.

**Why each obeys every AD.** AD-19 says the evidence store holds "deliverables, and the raw tool outputs FR70 re-execution and FR71 fidelity measurement require" and that "only the harness reads it" — it names a reader and never names a writer, so both units comply. AD-4.2 says the driver is the only component that performs port calls and "appends the outcome," which `DriverEvidenceWriter` reads as licence to hold the outcome. AD-5 says raw content "exist[s] inside port adapters and inside the narrow, declared core operations," which `PortDualWriter` reads as the exhaustive list of legal holders.

**The incompatibility.** The two units disagree about whether raw prompts, tool arguments and tool results may exist in `outcomefuse.runtime`. That is not a style difference: it decides where NFR5 redaction is enforced, where NFR12 access control attaches, and whether a stack trace from the driver can leak payload — the exact leak AD-5's "Prevents" clause names. It also decides FR71's measurability: `PortDualWriter` can hash raw-in and capsule-out at one boundary; `DriverEvidenceWriter` must re-read the store from the harness and re-derive, and the two produce different compression-fidelity denominators when a port retried internally. And AD-5's list is exhaustive by construction — under `DriverEvidenceWriter` the driver becomes a fourth legal holder of raw content that AD-5 does not authorise, so one of the two units is not merely different but non-compliant *once someone notices*, which is the worst kind of ambiguity to ship.

**Closing rule — tighten AD-19, second sentence.**

> **The evidence store is written only by port adapters.** A port adapter that obtains raw content persists it to the evidence store, keyed by run and step, and returns upward only an **evidence handle** plus the derived values AD-5 permits. No component above the adapter layer — driver, Policy, advisor, core operation or record sink — ever holds raw prompts, tool arguments or tool results, and none may write the evidence store. The handle is opaque, is recorded on the decision row, and is resolvable **only by the harness**. This closes AD-5's list of legal holders of raw content to port adapters and the three declared core operations, with no fourth.

---

## H5 — Comparison-arm equality and label propagation are undefined

**Severity: High.** Determines whether the published headline is a governor effect or a pricing-table artifact.

**The two units.**

- **`StrictArmBuilder`** — an arm is a set of runs; it refuses to build a comparison unless every manifest field that could move a cost figure is identical across arms except mode, and it propagates any per-run label to the whole arm.
- **`LooseArmBuilder`** — an arm is a set of runs; it enforces exactly what AD-10 lists (same route, conformance, manifest present, sealed set + preregistration) and computes mean/median over runs, excluding degraded ones from the arm so the clean runs are reported clean.

**Why each obeys every AD.** AD-10's admissibility gate is an explicit, closed list of four items; `LooseArmBuilder` satisfies all four. AD-9 requires the manifest to *carry* pinned cost-table version, model ids, seed and sampling parameters, but no AD requires those to be **equal across arms** — AD-10 imposes cross-arm equality on the route alone. AD-20 says "any run carrying a deregistration is marked degraded and every figure it yields carries that label" — `LooseArmBuilder` honours that for the run and then declines to report the run, which carries no label anywhere; `StrictArmBuilder` honours it for the arm.

**The incompatibility.** Three constructible divergences from identical run sets.

1. **Cost-table drift across arms.** AD-13 pins the cost table precisely because "a pricing change between calibration and evaluation would silently move the cost figure" — but nothing forbids the baseline arm carrying pin `v3` and the governed arm `v4`. `LooseArmBuilder` publishes the resulting delta as a net cost saving. The defence AD-13 built is defeated by the gate AD-10 forgot to state.
2. **Degraded-run exclusion changes N.** `LooseArmBuilder` drops the degraded run, which lowers the case count and can silently cross FR59's minimum — and AD-10 refuses "any workload below its declared minimum case count," so the two units disagree about whether the comparison is publishable at all.
3. **Mixed independence within an arm.** If runs 1–20 were gateway-metered and 21–30 fell back to governor counting, `StrictArmBuilder` labels the whole arm self-reported (FR80); `LooseArmBuilder` may label per-run and report an unlabelled mean. §8.4 requires the label to travel with the figure, and a mean is a figure.

**Closing rule — tighten AD-10, admissibility paragraph, and add an arm definition.**

> **A comparison arm is a set of runs over one case set in one mode.** Admissibility gains two cross-arm conditions: **manifest congruence** — every manifest field except `mode`, `run id` and `seed` is byte-identical across the arms of a comparison, and a mismatch refuses the comparison rather than annotating it; and **arm completeness** — the runs contributing to an arm are exactly the runs executed for it, with none excluded after the fact.
>
> **Labels propagate upward and never downward.** Any label attaching to any run in an arm — degraded (AD-20), self-reported (FR80), projected (FR49), constraint-backed (FR21) — attaches to every figure the arm yields. A degraded run is reported inside its arm and carries the arm's case count; it is never dropped to keep an arm clean, because dropping it would move both the mean and the FR59 count without leaving a record.

---

## H6 — The shadow counterfactual has no continuation rule and no arm discriminator

**Severity: High.** F10 is protected core; two compliant shadow drivers produce different projected savings from the same host run.

**The two units.**

- **`SealAtHaltShadow`** — when the Policy emits a terminating action, the shadow driver records it, declines to apply it (FR91), and stops evaluating the counterfactual for the remainder of the host run; subsequent host steps are recorded as executed-ungoverned only.
- **`ContinueAfterHaltShadow`** — records the would-be terminal decision, declines to apply it, and keeps invoking the Policy against a counterfactual ledger that continues to accrue estimated spend, so a second and third would-be halt may follow.

**Why each obeys every AD.** AD-11 says "the Policy is unchanged and always decides as if enforcing" and "a shadow driver records each decision and declines to apply it" — `ContinueAfterHaltShadow` reads "always" and "each" literally. `SealAtHaltShadow` reads FR1's "`terminal_reason` … recorded at most once" as binding on the log, which forces it to stop producing terminal decisions. FR96 requires marking first divergence and forbids extrapolating past it "without disclosing that they were" — both disclose.

**The incompatibility.** The projected saving differs, and it differs in the direction that flatters. `SealAtHaltShadow` credits the governor with everything the host spent after the would-be halt. `ContinueAfterHaltShadow` credits it with the same steps minus a continuing counterfactual spend, producing a smaller number. AD-10 bars shadow figures from headline reportability, which limits the blast radius — but FR49 permits them to be *reported as projected*, and two implementations reporting materially different projections for the same run is exactly the incomparability AD-1 and AD-4 exist to prevent.

A second, sharper problem sits underneath. AD-11 refers to "the estimated counterfactual ledger" as a thing that exists, while AD-2 derives all state by folding *the* log. Two ledgers folded from one log requires every spend-bearing row to declare which ledger it belongs to, and no row schema in the spine has that field. `SealAtHaltShadow` writes counterfactual rows into the same decision stream — which pollutes the fold that AD-15's conformance battery and AD-17's viewer both consume. `ContinueAfterHaltShadow` writes them to a separate stream — which arguably breaks FR47's "same shape as an enforced run."

**Closing rule — tighten AD-11.**

> **The counterfactual is a second fold over one log, and it seals at its first would-be termination.** Every spend-bearing and state-bearing entry carries a **`lane`** discriminator of `observed` or `counterfactual`. An enforced run writes only `observed` entries, which is what makes FR47's "same shape" true. A shadow run writes both, and the counterfactual ledger is the fold restricted to `counterfactual`; no consumer of the observed fold — conformance suite, viewer, proof card — reads `counterfactual` entries.
>
> **The counterfactual seals at its first terminating decision.** When the Policy emits a terminating `policy_action` in shadow, the shadow driver records it with its `terminal_reason` on the `counterfactual` lane, marks the counterfactual **sealed**, and evaluates no further counterfactual decisions. Host execution continues and is recorded on the `observed` lane. Everything the host spends after the seal is reported as **avoided-if-enforced**, never as counterfactual spend, and never without the seal point alongside FR96's first divergence.

---

## H7 — Preregistration is a free-floating artifact

**Severity: High.** The guard on the headline claim is not bound to the runs it guards.

**The two units.**

- **`BindingPreregHarness`** — writes the preregistration record, then stamps its hash into every evaluation-set run manifest, so a run declares which targets it was executed against.
- **`SidecarPreregHarness`** — writes the preregistration record with a timestamp, records the evaluation-execution-start timestamp, compares the two, and publishes. The manifest carries case-set identity and `evaluation` as AD-9 requires; it carries no preregistration reference, because AD-9's field list does not include one.

**Why each obeys every AD.** AD-9's manifest field list is explicit and closed, and `preregistration hash` is not on it. AD-9's second paragraph requires the preregistration record to exist as "its own hashed, timestamped artifact" and requires the harness to compare two moments and refuse an inversion — `SidecarPreregHarness` does exactly that and nothing more.

**The incompatibility.** Under `SidecarPreregHarness` the FR102 ordering check is a comparison of two self-recorded timestamps by the party that benefits from the comparison passing, with no artifact binding the targets to the results. Regenerating the preregistration file after inspecting results and re-stamping it passes every gate the spine states. `BindingPreregHarness` cannot do that, because the evaluation runs' manifests already name the old hash and manifest congruence (H5) would refuse a mixed comparison. The two units differ in whether §8.5's seal is enforceable or ceremonial — and the PRD's `[NOTE FOR PM]` in §11.1 states plainly that the design's answer to the reviewer-bias problem is that "it makes cheating visible in the record." Under `SidecarPreregHarness` it does not.

A second construction in the same AD: `case-set identity` is not defined as a content hash. `NameIdentity` treats it as the string `evaluation-v1`; `ContentIdentity` treats it as the SHA-256 of the frozen case set. Under `NameIdentity`, editing one evaluation case between runs leaves both manifests congruent and both comparisons admissible.

**Closing rule — tighten AD-9's manifest field list.**

> The run manifest additionally carries: **preregistration-record hash** (mandatory for any run whose case set is `evaluation`; absent and refused otherwise) and **case-set content hash**, computed by the AD-6 canonicaliser over the frozen case-set definition rather than over its name. A run declaring `evaluation` without a preregistration hash is not merely unreportable — it is refused at start. The FR102 ordering check compares the preregistration record's own timestamp against the earliest evaluation run bearing its hash, so the ordering claim is anchored in the run record rather than in a harness-held clock reading.

---

## H8 — The gate-cadence predicate is unowned

**Severity: High.** Moves governor overhead, the gate count, and which terminal reason a run ends with.

**The two units.**

- **`ResultMutatingGateDriver`** — evaluates the gate after any step whose outcome altered the candidate deliverable, and skips retrieval, planning and routing steps.
- **`EveryStepGateDriver`** — evaluates the gate after every completed unit of work, on the reasoning that a retrieval step supplies an evidence field and therefore could change the candidate result.

**Why each obeys every AD.** The spine's "One decision" diagram says `D->>G: evaluate if this unit could change the candidate result` and no AD assigns that predicate an owner or a definition. FR98 permits the contract to "declare additional evaluation checkpoints" and to "omit checkpoints for steps that cannot affect the candidate result," but AD-7 forbids a contract from carrying executable logic, so the contract can only select from something the core defines — and the core is never told to define it.

**The incompatibility.** `EveryStepGateDriver` runs the gate several times more often. Every gate execution is billed as governor overhead under FR98 and AD-4.4, so the two units report materially different overhead shares — the §3.3 counter-metric that decides whether the product works on short tasks. They also terminate differently: FR98's cadence is what gives `stop-sufficient` first refusal on the ending, so a run that becomes sufficient after a retrieval step ends `stop-sufficient` under `EveryStepGateDriver` and, if budget then runs out, `halt-exhausted` under `ResultMutatingGateDriver`. That is the product's headline event misfiled as a failure — the exact outcome FR98's rationale names.

**Closing rule — new clause in AD-4, or an amendment to the Capability map for F4.**

> **The gate-cadence predicate is core-owned and declarative.** `core/gate` declares a closed set of **step classes** — `deliverable-mutating`, `evidence-gathering`, `planning`, `routing`, `verification` — and the driver labels each proposed step with exactly one class at decision time, recording it on the decision row. The gate executes after any step whose class is in the core default cadence set (`deliverable-mutating`, `evidence-gathering`), and before every non-fail-closed terminal halt. A contract may **add** classes to the cadence set and may not remove `deliverable-mutating`. No driver, adapter or advisor may define, override or infer the class of a step by any other route.

---

## H9 — The verifier-to-qualifier mapping is asserted to exist and never given

**Severity: High.** Flips the `reference-backed` / `constraint-backed` label on a published claim.

**The two units.**

- **`StrictQualifierRegistry`** — maps `exact-match-against-answer-key` to `reference-backed`; everything else, including `regex-match` and `citation-resolves`, to `constraint-backed`.
- **`GenerousQualifierRegistry`** — maps `exact-match-against-answer-key` and `citation-resolves` to `reference-backed` (a citation is checked against a known source, therefore against a known-correct value), and a `regex-match` whose pattern is a fully-anchored literal to `reference-backed` as well.

**Why each obeys every AD.** AD-7 states only that "the `reference-backed` / `constraint-backed` qualifier is determined by which registry entry was used, not separately asserted." It gives seven entries and no mapping. Both units determine the qualifier from the entry.

**The incompatibility.** FR21 says only a pass in which *every* mandatory criterion was `reference-backed` may be labelled `reference-backed`, and §8.4 requires that label to travel with the figure wherever it is reported — including the submission video. A contract using `citation-resolves` on one mandatory criterion yields a `constraint-backed` headline under one unit and a `reference-backed` headline under the other. §8.2a identifies this distinction as "the honest boundary of the strongest claim in the document." Two compliant implementations move that boundary.

**Closing rule — tighten AD-7 with the table it presumes.**

> The registry is closed and its qualifier mapping is fixed here, not derived:
>
> | Entry | Qualifier |
> | --- | --- |
> | `exact-match-against-answer-key` | `reference-backed` |
> | `citation-resolves` | `reference-backed` **only** where the citation target is drawn from the case's frozen answer key; `constraint-backed` where it resolves against arbitrary retrieved content |
> | `field-present` · `type-is` · `numeric-range` · `set-membership` · `regex-match` | `constraint-backed`, without exception, regardless of how specific the parameterisation is |
>
> A registry entry added later declares its qualifier in this table as part of the addition; an entry with no declared qualifier is invalid and contract validation rejects any mandatory criterion selecting it.

---

## H10 — Overhead is settled but never reserved, and reservations have no release rule

**Severity: High.** Two compliant ledgers report different `remaining` for the same run.

**The two units.**

- **`ReservingOverheadLedgerDriver`** — treats every `EvidenceRequest` fulfilment as a spend event requiring a prior reservation, so an unaffordable rubric judgement is refused before it is issued.
- **`SettlingOverheadLedgerDriver`** — treats AD-3's "reserved at decision time" as binding only on decisions; `EvidenceRequest` fulfilment precedes the decision, so it is settled after the fact with no affordability check.

**Why each obeys every AD.** AD-3 scopes reservation to decision time and an `EvidenceRequest` is not a decision. AD-4.4 says every fulfilment "is debited as governor overhead … from the driver's recorded outcome," which describes settlement and says nothing about reservation. FR16 rejects an unaffordable "proposed step," and an `EvidenceRequest` is not a proposed step.

**The incompatibility.** `SettlingOverheadLedgerDriver` can spend past `remaining` and into `reserved` through overhead alone, defeating FR14's guarantee that "earlier steps SHALL NOT be able to spend the reserve, so verification can never be starved by overspend" — overhead is not an earlier step, so FR14's letter does not catch it. FR101 explicitly reasons about forward-budgeting "the Quality Gate executions FR98 requires," which only makes sense if gate executions are reserved; the spine never says they are.

A second construction inside the same gap: no AD states when a reservation is **released**. `HoldingLedger` keeps the reservation across a `pause-for-approval` and through an `approval-timeout` that escalates rather than terminates; `ReleasingLedger` releases on any non-`proceed` action. Their `remaining` diverges permanently from the first approval pause onward, and FR16's affordability test then produces different denials for the rest of the run. A third divergence: an applied verdict whose outcome never arrives — an adapter crash between `verdict` and `outcome` — leaks a reservation in one unit and not the other.

**Closing rule — tighten AD-3.**

> **Every spend is reserved before it is incurred, including the governor's own.** A reservation is taken before a port call is made, whether that call fulfils an `EvidenceRequest` or executes an approved step. An `EvidenceRequest` whose reservation is refused is not fulfilled; the advisor is re-invoked with an `unavailable` outcome and proceeds under AD-20's fail-open posture. The **verification reserve (FR14, FR101) is available to Quality Gate executions and to final synthesis, and to nothing else** — no other overhead may draw on it.
>
> **A reservation is released by exactly one of three events, each recorded:** settlement of the corresponding spend; a decision that did not proceed (`deny`, `pause-for-approval` that has not yet been granted, or any terminating action); or run termination, which releases all outstanding reservations before the terminal entry is appended. A reservation outstanding at the terminal entry is a malformed log.

---

## H11 — `fail-closed` has two possible writers

**Severity: High.** Determines whether FR2's ladder is evaluated in one place or two.

**The two units.**

- **`PolicyTerminates`** — the driver detects gate-verdict unavailability, ledger-state loss or approval-channel unavailability and feeds each to the Policy as a decision input; the Policy runs the FR2 ladder and emits `decision_reason = fail-closed`, `policy_action`, `terminal_reason = fail-closed`.
- **`DriverTerminates`** — the driver detects the same conditions and appends a `fail-closed` decision row itself, never invoking the Policy, because AD-20 assigns fail-closed to the driver.

**Why each obeys every AD.** `DriverTerminates` cites AD-20 verbatim: "**Fail-closed is a property of the driver:** Gate-verdict unavailability, ledger-state loss and approval-channel unavailability terminate through the FR2 ladder." `PolicyTerminates` cites AD-4.3 ("the Policy is the only component that converts proposals into a decision") and the Consistency Conventions row on Errors ("A port error is a **decision input**, never an escape"). Both citations are load-bearing and they point in opposite directions.

**The incompatibility.** Under `DriverTerminates` the FR2 ladder exists twice, in two languages, in two layers — and the driver's copy is the one that runs on the safety-critical path. A run in which the gate is unavailable *and* the contract's approval gate is pending resolves differently depending on which copy sees it first. AD-11's rationale explicitly argues against putting safety-critical branches on paths the tests exercise least; `DriverTerminates` does exactly that with the FR2 ladder itself. Under `PolicyTerminates`, by contrast, the shadow exemption (FR91) becomes hard to place, because the Policy "always decides as if enforcing" (AD-11) and would emit a `fail-closed` termination the shadow driver must then decline — which is precisely AD-11's design and confirms this is the intended unit.

**Closing rule — tighten AD-20, fail-closed clause.**

> **Fail-closed is detected by the driver and decided by the Policy.** The driver detects gate-verdict unavailability, ledger-state loss and approval-channel unavailability, and presents each to the Policy as a **typed decision input**. The Policy runs the FR2 ladder — once, in one place, in `core/policy` — and emits the `fail-closed` triple. The driver's obligation is to **apply** the resulting termination; the enforcing driver applies it, the shadow driver declines to (FR91). No driver, adapter or port constructs a decision row, a `decision_reason` or a `terminal_reason` on its own authority.

---

## H12 — `EvidenceRequest` is an open extension point with no payload schema

**Severity: High.** AD-4 requires the outcome to be appended; AD-5 forbids free text in the log; FR6 requires every model-derived input the decision consumed to be recorded. Three rules, one object, no schema.

**The two units.**

- **`ScoreOnlyFulfiller`** — appends only the derived scalar the advisor asked for (a score, an estimate, an envelope) and discards the model's rationale before the append.
- **`RationaleFulfiller`** — appends the score plus the model's rationale, classifying the rationale as a "capsule," and re-invokes the advisor with both.

**Why each obeys every AD.** AD-4.2 requires the driver to "append the outcome, then re-invoke the advisor with the result" — neither unit skips the append. AD-5 permits "scores, estimates, envelopes, capsules, canonical keys and content hashes" to cross into the record, and `RationaleFulfiller` calls its rationale a capsule, which is a compressed rendering of content and therefore fits the word. FR6 requires "every model-derived input the decision consumed" to be recorded — which `ScoreOnlyFulfiller` violates the moment its advisor consumes the rationale, and which `RationaleFulfiller` is trying to honour.

**The incompatibility.** The two units produce logs of different sensitivity classes for the same run: one is redacted-by-construction, the other carries model prose derived from raw tool output straight into the durable decision record, defeating NFR5 and AD-5's "Prevents" clause. Replay diverges too: AD-4.2 defines replay as "feeding recorded outcomes back into a pure advisor," so under `ScoreOnlyFulfiller` an advisor that consumed a rationale cannot be replayed at all, and FR6 declares such a decision unreplayable and unauditable — silently.

The extension point is open in a second way: the `kind` set is illustrative ("a rubric judgement, a compression pass, a complexity or confidence estimate, a planner envelope"), not closed. Two advisor authors can therefore declare kinds the driver has no fulfilment handler for, or two kinds with the same name and different payloads. AD-7 closed the verifier registry against exactly this failure and AD-4 did not close its own.

**Closing rule — tighten AD-4.1 and AD-4.2.**

> **`EvidenceRequest` is a closed, core-owned sum type.** Its variants are declared in `core/advisors` and are exactly: `rubric-judgement`, `compression`, `complexity-estimate`, `confidence-estimate`, `planner-envelope`. Each variant declares, in the core, both its **request payload type** and its **outcome payload type**, and both types are restricted to the derived values AD-5 permits — no variant's outcome type contains free text. An advisor may not emit a variant not in this set; a driver may not fulfil one. Adding a variant is a core change with a registry version bump, recorded in the manifest alongside the mechanism versions.
>
> **The outcome payload is exactly what the advisor is re-invoked with.** The driver appends the outcome and re-invokes the advisor with that same value; it may not pass the advisor anything it did not append. FR6 is therefore satisfied by construction, and replay is byte-exact.

---

## H13 — `citation-resolves` needs the store AD-19 seals

**Severity: High.** A boundary evasion the spine's own verifier registry forces.

**The two units.**

- **`InFlightCitationVerifier`** — resolves citations against the transient working set, which AD-5 permits `verify-criterion` to see. It can only verify a citation whose source content is still in flight on this step.
- **`StoreBackedCitationVerifier`** — resolves citations against the evidence store, which holds the raw tool outputs the run has accumulated.

**Why each obeys every AD.** AD-5 explicitly names `verify-criterion (FR8)` as one of three core operations that may touch raw content, so `InFlightCitationVerifier` is squarely legal. `StoreBackedCitationVerifier` argues that the evidence store is where the run's raw content lives (AD-19) and that a citation to a document retrieved four steps ago cannot be resolved any other way.

**The incompatibility.** AD-19 says "only the harness reads it" and "nothing in the evidence store may be cited as a decision input." A gate verdict is unambiguously a decision input (FR3, FR53). So `StoreBackedCitationVerifier` violates AD-19, and `InFlightCitationVerifier` — the compliant one — can only verify citations to content retrieved on the current step, which makes `citation-resolves` unusable as a mandatory criterion on any multi-step run. AD-7 nevertheless ships it in the registry, and FR8 says a criterion with no executable verifier cannot be mandatory. The result is a registry entry that either cannot be used or cannot be used legally, and two authors will resolve that in opposite directions without either noticing they disagreed.

**Closing rule — tighten AD-19 and AD-7 together.**

> **A run-scoped citable index sits between the two stores.** Port adapters, on persisting raw content to the evidence store, additionally emit a **citable index** — content hashes, resolvable identifiers, extracted citation targets and numeric values, and nothing else — into run state, where the fold makes it available to `verify-criterion`. `citation-resolves` resolves against the citable index, never against the evidence store. The evidence store remains harness-read-only and remains uncitable as a decision input; the index is derived, redaction-safe and therefore citable. FR71 compression-fidelity measurement compares the evidence store against the capsule **in the harness**, unchanged.

---

## H14 — Log entry kinds are unenumerated

**Severity: High.** AD-2 makes the log the sole source of run state and never says what may be in it.

**The two units.**

- **`SingleTableLog`** — one append-only `decision` table with a nullable `kind` column, carrying manifest, decisions, gate verdicts and `degraded` events in one stream.
- **`MultiStreamLog`** — a `decision` table plus separate `manifest`, `gate_verdict`, `degraded` and `spend` tables, joined by run and sequence.

**Why each obeys every AD.** AD-16 requires the record store to be SQLite, one file per run, with append-only semantics and no `UPDATE`/`DELETE` "against the decision table" — which `MultiStreamLog` satisfies for its decision table and leaves unconstrained for the others. AD-2 requires the fold to be over "the log" without saying whether that is one relation or several. AD-9 requires the manifest to be "the first entry of every run's log" — `MultiStreamLog` satisfies that with sequence 0 in a separate table.

**The incompatibility.** AD-15 asserts a conformance battery "against the resulting decision log"; AD-17 generates the viewer "from the decision log"; AD-10 evaluates admissibility from the manifest and degraded markers. All three are cross-implementation consumers of a shape neither unit is required to share. `MultiStreamLog`'s auxiliary tables are outside AD-16's append-only guarantee as written, so a `degraded` row can legally be deleted — and AD-20's degraded label, which AD-10 propagates onto every published figure, becomes erasable without violating an AD.

**Closing rule — tighten AD-16.**

> **One append-only entry relation.** A run database contains exactly one entry relation. Every entry carries `run_id`, a monotonically increasing `seq`, a `kind` drawn from a closed core-owned set — `manifest`, `decision`, `reservation`, `evidence_request`, `evidence_outcome`, `settlement`, `outcome`, `gate_verdict`, `degraded`, `preregistration_ref` — a `lane` (AD-11), and a kind-typed payload. `seq = 0` is the manifest and nothing else. No `UPDATE` or `DELETE` is issued against this relation for any kind. Derived tables, indices and materialised views may exist for query performance; they are rebuildable from the entry relation by the fold and carry no authority.

---

## H15 — OFF is a driver and also "no governor participation"

**Severity: High.** Biases the baseline arm of every comparison, including the latency counter-metric.

**The two units.**

- **`NullDriver`** — a third runtime driver, as the layer table names it. The adapter proposes each step exactly as in governed mode; the driver returns `proceed` unconditionally, appends a manifest and a minimal decision stream, and applies nothing.
- **`BypassAdapter`** — the adapter detects OFF and never calls the governor; the host loop runs untouched, and the harness records tokens and duration externally.

**Why each obeys every AD.** The layer table lists "Runtime drivers (enforcing, shadow, off)", which is `NullDriver`. FR52 requires the host agent to execute "exactly as its baseline, with no governor participation," which is `BypassAdapter`. AD-9 requires "the first entry of every run's log" to be a manifest and lists `baseline` as a mode — which requires *something* governor-side to be writing, favouring `NullDriver`. AD-1 says a host adapter "proposes a step and applies the returned verdict," with no OFF exemption.

**The incompatibility.** Under `NullDriver` the baseline arm carries the governor's per-step call overhead in its wall-clock time; under `BypassAdapter` it does not. §3.2's latency reduction and NFR1's decision-latency bound are both measured as governed-versus-baseline deltas, so the two units report different — and oppositely signed — latency results from identical execution. AD-8's requirement that "every decision row also carries the governor's own wall-clock decision cost, so NFR1 is measured from the record" only closes the governed side of that comparison. Worse, `NullDriver` produces a baseline run whose adapter code path is the governed one, so AD-15's conformance suite says nothing about whether `BypassAdapter`'s baseline is behaviourally identical to the frozen FR64 baseline definition — the thing the whole comparison rests on.

**Closing rule — new clause under AD-15, and a correction to the layer table.**

> **OFF is an adapter state, not a driver.** There is no `off` driver. In OFF the host adapter makes no governor call on the execution path; the governor's only participation is that the harness opens the run with a manifest (AD-9, `mode = baseline`) and closes it with the observed totals. The layer table's driver list is corrected to `enforcing, shadow`.
>
> **Conformance gains a baseline-equivalence scenario.** The AD-15 battery adds: *the same case executed OFF through the adapter and executed directly against the frozen FR64 baseline definition produce the same tool-call sequence, the same model calls and the same deliverable.* An adapter that has not passed baseline equivalence may not produce a baseline arm.

---

## H16 — `quality_state` is both a stamped column and a fold output

**Severity: Medium-high.**

**The two units.** `FoldedQualityState` derives `quality_state` at read time as a fold over `gate_verdict` entries. `StampedQualityState` reads the `quality_state` column written on the most recent entry that carries one.

**Why each obeys every AD.** AD-2 mandates the fold; `StampedQualityState` argues the stamped column *is* the fold, memoised at write time. FR53 requires `quality_state` at decision time on every decision row and the "One decision" diagram shows the driver appending "gate verdict and `quality_state`" as one act, which is exactly a stamp.

**The incompatibility.** They diverge wherever a decision row is appended between gate executions and wherever no verdict was produced. A fail-closed halt produces no verdict, so `FoldedQualityState` reports the last real verdict while `StampedQualityState` reports whatever the driver chose to stamp — possibly `not-evaluated`, which FR105 defines as "the *absence* of a verdict." Under FR2, `sufficiency` is invalid while `quality_state` is `not-evaluated`, so the two units admit different terminal reasons for the same run.

**Closing rule — tighten AD-2.**

> `quality_state` is **derived only**, by folding `gate_verdict` entries: `not-evaluated` until the first verdict, thereafter the most recent verdict. Where a decision row carries `quality_state` for FR53's benefit, that value is a **denormalised copy of the fold at that `seq`** and carries no authority; a copy that disagrees with the fold makes the log malformed. No component computes, sets or advances `quality_state` by any other route.

---

## H17 — The freeze-time hasher predates the canonicaliser

**Severity: Medium-high.** AD-6 names the exact failure it then fails to prevent.

**The two units.** `FreezeTool` — a standalone script that content-hashes the rubric and answer keys before governor implementation begins, per FR65 and §8.2. `RuntimeCanonicaliser` — the single core-owned function of AD-6, which does not exist yet when `FreezeTool` runs.

**Why each obeys every AD.** AD-6 says "no component may hash a structure by any other route," but FR65 and §8.2 require the freeze to happen *before governor implementation begins*, so the freeze is by construction performed by something that is not the AD-6 canonicaliser. Both units are compliant with their own governing requirement.

**The incompatibility.** The two hashers must agree on numeric normalisation, key ordering and validation-model shape, and AD-6 specifies none of these beyond "sorted keys, no insignificant whitespace, normalised numeric forms." A rubric containing `1.0` hashes differently under `"1.0"` and `1`. The harness then refuses every comparison on a spurious rubric drift — the exact failure AD-6's "Prevents" clause names — or, worse, the freeze is quietly redone with the runtime hasher after the governor exists, which destroys the temporal guarantee that FR65 was built to provide.

**Closing rule — tighten AD-6.**

> The canonicaliser is written **first**, as the project's first committed module, and the FR65 freeze is performed by it. Its normalisation is fully specified and versioned: object keys sorted by Unicode code point; no insignificant whitespace; integers rendered without a decimal point; non-integers rendered as the shortest decimal string that round-trips, never as a binary float; booleans and nulls as JSON literals; strings NFC-normalised. The canonicaliser's **version is recorded in the manifest** and in every freeze artifact, and a hash comparison across differing canonicaliser versions is refused as indeterminate rather than reported as drift.

---

## H18 — "Ledger view" is a named object defined nowhere

**Severity: Medium-high.**

**The two units.** `ThinLedgerView` exposes `remaining` only. `RichLedgerView` exposes `allocated`, `spent`, `reserved`, `remaining`, per-mechanism attribution to date and the decision history.

**Why each obeys every AD.** AD-4.1 says an advisor's input is "read-only state" and constrains nothing further. The "One decision" diagram passes `decide(contract, ledger view, quality_state)` and names no fields. FR18 requires the ledger to "expose current state to the policy," which both do.

**The incompatibility.** FR16 rejects a step unaffordable within `remaining` **less `reserved`**. An advisor holding `ThinLedgerView` estimates affordability against gross remaining and proposes steps the Ledger then refuses, producing `unaffordable` decision rows that `RichLedgerView` never generates — different logs, different reason-code distributions, different §3.3 aggregates. Separately, `RichLedgerView`'s decision history lets one advisor read another's prior proposals and condition on them, which formally preserves AD-4's single-writer discipline while defeating the PRD's §1.5 principle that no mechanism optimizes for itself — and it makes FR62 ablation non-additive, because removing one mechanism changes what the others see.

**Closing rule — new clause under AD-4.1.**

> **`LedgerView` is a core-declared frozen type** exposing exactly `allocated`, `spent`, `reserved`, `remaining` and `reserve_floor`, in both tokens and estimated cost, with `remaining` reported **net of `reserved`**. Advisors receive `LedgerView`, the contract, `quality_state`, the per-criterion gate breakdown and the current step's classification — **and nothing else**. No advisor receives the decision history, another advisor's proposals, or per-mechanism attribution; an advisor that requires history declares an `EvidenceRequest` for the derived value it needs, so the dependency is recorded and ablatable.

---

## H19 — Ledger as fold versus ledger as state

**Severity: Medium.** One of the two units cannot construct a required test case.

**The two units.** `FoldLedger` — all ledger values are folds over settlement and reservation entries; there is no mutable ledger object. `StateLedger` — a mutable ledger holds counters and emits entries as it changes.

**Why each obeys every AD.** AD-2 mandates the fold and forbids "a second structure kept in sync." AD-4.4 calls the Ledger "the only writer of spend," and the sequence's `L-->>P: reserved or rejected` reads like a stateful object answering. Both readings are supported by spine text.

**The incompatibility.** FR88 and FR100 require ledger-state loss to be a real, exercised failure path with a scripted case. Under `FoldLedger` there is no state to lose — the failure is unconstructible, and the FR100 case must be faked by corrupting the log, which AD-16 forbids. Under `StateLedger` it is constructible but AD-2's drift prohibition is violated. Two authors will build the FR100 case in incompatible ways or one will silently skip it.

**Closing rule — tighten AD-2 and AD-20 together.**

> The ledger is a fold; there is no mutable ledger. **FR88 "ledger state lost" is redefined at the fold:** the fail-closed condition is that the run's entry relation cannot be read, cannot be parsed, or folds to an inconsistent state — a settlement with no matching reservation, a negative `remaining`, or a `seq` gap. The AD-15 and FR100 scripted case induces one of these by pointing the driver at an unreadable or truncated database handle, never by mutating a written entry.

---

## H20 — Reason-code allocation has no authority

**Severity: Medium.**

**The two units.** `ToolGovernorAdvisor` registers `cache-stale` in family **Denial**. `ContextGovernorAdvisor` registers `cache-stale` in family **Substitution**.

**Why each obeys every AD.** AD-8 forbids redefining, repurposing or removing a **published** code; neither unit does that, both are adding. FR104 permits new codes "at any time" and requires each to declare a family. The Conventions row requires the stored code to be unqualified — "prefixed by family in reporting only — never in the stored code" — so codes are a flat namespace with no allocation authority named.

**The incompatibility.** §3.3 aggregation is by family. A flat namespace with per-author family assignment means one stored code aggregates into two families depending on which advisor emitted it, and the log cannot distinguish them because the family is not stored. The FR62 breakdown and the denial-versus-substitution split in the proof card both come apart.

**Closing rule — tighten AD-8.**

> The reason registry is **declared in one core module** and is the sole allocation authority; no advisor, driver, adapter or harness may introduce a code. Each code declares exactly one family, permanently. Adding a code bumps the registry version, which is stamped on every decision row (AD-8) and recorded in the manifest (AD-9). Reporting resolves family by looking the stored code up in the registry version the row declares, so a code's family is stable for the life of every record that cites it.

---

## What is *not* a hole

Recorded so the next reviewer does not re-run these attacks.

- **AD-1 versus AD-15.** Two adapters honouring `deny` differently is closed: AD-1 requires the adapter to apply the returned verdict and AD-15 asserts the outcome against the log, not against adapter internals. The pair does not construct.
- **AD-14 cache scoping.** Two cache implementations cannot diverge on lifetime; the AD is explicit on run and process scope, and NFR6 is discharged structurally rather than by a rule an author could interpret.
- **AD-17 viewer computing figures.** FR75 and AD-17 both forbid it and FR97 places computation in F13. A viewer that computed a figure would violate the AD, not merely differ from another viewer.
- **AD-13 model seam.** "No LiteLLM type, exception or cost table appears above the port" is a checkable structural rule; two compliant adapters cannot leak differently.
- **AD-7 code execution.** The closed registry plus "no import path, expression or callable reference crosses the contract boundary" leaves no legal path to execution. The hole in AD-7 is the qualifier mapping (H9), not the closure.
- **AD-10 streaming ban.** Unconditional and structural; nothing to interpret.

---

## Consolidated change list

| Hole | Change | Where |
|---|---|---|
| H1 | New **AD-21 — Proposal resolution is declared, and attribution follows composition** | New AD |
| H2 | Registry is run-scoped and process-local | AD-20, final paragraph |
| H3 | New **AD-22 — The decision cycle has one canonical order**; correct the "One decision" diagram to reserve after append | New AD + Structural Seed |
| H4 | Evidence store is written only by port adapters; handle returned upward | AD-19 |
| H5 | Manifest congruence + arm completeness + label propagation | AD-10 admissibility |
| H6 | `lane` discriminator; counterfactual seals at first would-be termination | AD-11 |
| H7 | Preregistration hash and case-set content hash in the manifest | AD-9 field list |
| H8 | Core-owned step classes drive gate cadence | AD-4 (new clause) |
| H9 | Verifier-entry → qualifier table | AD-7 |
| H10 | Reserve before every spend incl. overhead; three release events | AD-3 |
| H11 | Driver detects, Policy decides, driver applies | AD-20 fail-closed clause |
| H12 | `EvidenceRequest` closed sum type with declared outcome payloads | AD-4.1, AD-4.2 |
| H13 | Run-scoped citable index between the stores | AD-19 + AD-7 |
| H14 | One append-only entry relation with a closed `kind` set | AD-16 |
| H15 | OFF is an adapter state, not a driver; add baseline-equivalence conformance scenario | AD-15 + layer table |
| H16 | `quality_state` derived only; stamped copies carry no authority | AD-2 |
| H17 | Canonicaliser written first; normalisation fully specified and versioned | AD-6 |
| H18 | `LedgerView` frozen type; advisor input set closed | AD-4.1 |
| H19 | FR88 redefined at the fold | AD-2 + AD-20 |
| H20 | Reason registry is the sole allocation authority; family is permanent | AD-8 |

Twenty holes; five new or substantially new rules (AD-21, AD-22, and the closures in AD-4.1, AD-16 and AD-19); the remaining fifteen are tightenings of existing AD text. No AD needs to be withdrawn, and the paradigm survives every attack — the log-as-record model is sound, and every hole above is a missing shape or a missing order rather than a wrong choice.
