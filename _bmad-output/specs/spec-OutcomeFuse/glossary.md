# Glossary

Companion to [SPEC.md](SPEC.md). Terms carry these meanings everywhere in the contract.

| Term | Meaning |
| --- | --- |
| **Outcome Contract** | The declarative artifact stating what "done" means before execution begins — deliverable, mandatory and optional criteria with their verifiers, quality floor, ceilings, verification reserve, permitted tools, escalation, approval conditions and approval timeout |
| **Mandatory criterion** | A criterion or evidence field the contract declares as constituting the quality floor. Must carry an executable deterministic verifier. Only mandatory criteria affect the gate verdict |
| **Optional / enrichment** | A criterion, field or tool call the contract declares as desirable but not floor-constituting. The only category marginal-value denial and optional-call suppression may touch |
| **Advisory criterion** | Something that matters but cannot be deterministically verified. Recorded and fed to the counter-metrics; never gating |
| **`reference-backed`** | Verification against a known-correct value. The strong mode |
| **`constraint-backed`** | Verification for presence, type and constraint only. The weaker mode; any pass touching it is labelled accordingly |
| **Quality floor** | The set of mandatory criteria that must be met. Never relaxed by any runtime path, never starved by the marginal-value estimator |
| **Sufficiency** | The state in which every mandatory criterion is met. Distinct from exhaustion, and from the agent's own belief that it is finished |
| **`policy_action`** | What the runtime does next. Recorded on every decision |
| **`decision_reason`** | Why an action was taken. A stable code from a versioned, extensible registry with declared families. Recorded on every decision |
| **`terminal_reason`** | Why the run *ended* — the cause, never the disposition. Recorded only where the action terminates the run |
| **`quality_state`** | Run-level state: `not-evaluated` until the gate first runs, then `pass` or `fail`. The absence of a verdict, not a third verdict |
| **Gate verdict** | Exactly `pass` or `fail`, qualified `reference-backed` or `constraint-backed`. There is no intermediate verdict |
| **Verification reserve** | Budget held back for final synthesis and Quality Gate execution. Declared or deterministically derived, recalculated before escalation, never spendable by earlier steps |
| **Evidence capsule** | Compressed, structured tool output preserving citations, identifiers, figures, policy clauses and contract-required attributable facts verbatim |
| **Governor overhead** | Spend consumed by the governor itself — evaluation, planning, compression passes, and every Quality Gate execution. Always reported separately |
| **Net savings** | Savings inclusive of governor overhead. The only figure permitted as a headline |
| **Calibration set** | Cases used to measure overhead, find break-even, exercise failure paths and set targets. Never contributes to a headline figure |
| **Evaluation set** | Frozen cases held sealed until targets are preregistered. The only source of headline claims |
| **False sufficiency** | A run the gate passed that blind human review fails. The counter-metric to the headline claim |
| **Shadow mode** | The governor observing and logging without enforcing. The ungoverned path is executed and observed; the governed path is an estimated counterfactual |
| **First divergence** | The earliest decision at which the governed counterfactual departs from the observed path. Everything after it is inference |
| **Proof card** | The recorded comparison artifact computed by the harness and rendered by the view. Computation belongs to the harness; the view only displays it |
| **Run manifest** | The first entry of every run's log, carrying the run's full configuration. No comparison may be published from a run without one |
| **Campaign / workspace** | Two words for one thing: the unit a record store covers and the unit a seal closes. Sealing is refused while any run is unsealed |
| **Degraded** | A run in which an advisor was deregistered mid-run after raising. Distinct from disabled, which means never registered |
| **Protected core** | Capabilities and apparatus that survive every cut |
