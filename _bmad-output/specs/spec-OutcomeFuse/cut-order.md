# Cut Order and Committed Workloads

Companion to [SPEC.md](SPEC.md). Roughly 7.5 days of estimated build work sits inside a one-month solo window against eighteen capabilities, four workloads, three host frameworks, a harness, a replay view and a submission artifact. **That is a material schedule risk, accepted deliberately.** The mitigation is not optimism: the cuts below are declared in advance, and independent disableability makes them mechanically executable rather than aspirational.

**The priority, stated once:** prove quality-gated runtime stopping and measurable net resource reduction over breadth of optimization techniques, integration coverage, or interface completeness.

## Committed workloads

Four, all committed scope — not stretch. Synthetic cases only; no production or confidential data. The harness is built once; each additional workload is then mock tools plus cases.

1. Research and investigation over a document corpus
2. Codebase Q&A and triage
3. Data / SQL analysis
4. Supply-chain exception investigation

## Protected core — never cut

Outcome Contract · Budget Ledger including the marginal-value decision · deterministic Quality Gate · duplicate-tool protection · loop protection · early-stop decision · **decision record** · **shadow mode** · reproducible OFF/ON benchmark · **submission artifact** · the evidence apparatus (canonicaliser, freeze, manifest, reportability gates, counter-metrics, evidence store and retention).

The decision record is protected because no decision may take effect before it is recorded — cutting it would not degrade the system, it would stop it. Shadow mode is protected because it is the adoption path: the mechanism a team uses to evaluate the governor before trusting it.

The evidence apparatus is as protected as the runtime, because the claim itself is a deliverable.

## Cut order under schedule pressure — first to go

1. The side-by-side execution view and any admin surfaces — **not** the submission video, which is protected
2. **The third host adapter.** Three host frameworks are committed where two dissimilar ones are required. The third goes first among mechanisms because it multiplies the benchmark matrix — a wrapper, conformance passage, four workloads of tools rebound, a frozen baseline definition, and a share of the required failure cases — without adding an argument two adapters do not already carry
3. Automated contract authoring
4. Multi-agent capabilities
5. Semantic-equivalence deduplication
6. Dynamic model routing (Model Governor)
7. Context compression (Context Governor)
8. Preflight planning — cut alongside the two above, since its envelopes feed both
9. Model-based evaluation — the advisory rubric signal in the Quality Gate
10. Advanced platform integrations (gateway metering)
11. **Workload breadth** — committed workloads are dropped last, one at a time, in reverse build order. No claim of generalization beyond the workloads actually completed

## What the cut order costs, stated plainly

This makes the Context Governor, Model Governor and Preflight Planner explicitly **sacrificial**. That is defensible, but it means the multi-mechanism story is committed *with a declared cut order*, not as a set of equally load-bearing components. The demo narrative and any external claim must not imply otherwise.

The uncomfortable reading: if the schedule collapses to the protected core, what ships is a governor with exact tool deduplication, a sufficiency stop and a loop fuse — and the per-mechanism ablation will show precisely how much of the saving came from deduplication alone. The attribution risk is the one the cut order makes *more* likely, not less.

Slack in the schedule goes to **evidence** — more cases, repeated runs, overhead baseline, agent-owner interviews — never to an additional mechanism. Anything further must displace planned work.

## What is not cuttable, and why

The canonicaliser, the case/key/rubric/contract drafting, the verifier registry and coverage review, the freeze, the record spine, the harness and the evidence store cannot be cut: the freeze must precede the governor, the harness must precede any published number, and the counter-metrics must precede the headline or reporting it is forbidden outright. Build ordering and its load-bearing dependencies are in [BUILD-ORDER.md](../../planning-artifacts/architecture/architecture-OutcomeFuse-2026-09-07/BUILD-ORDER.md).
