---
title: "Product Brief: OutcomeFuse"
status: draft
created: 2026-09-02
updated: 2026-09-03
---

# Product Brief: OutcomeFuse

**The quality-gated budget runtime for AI agents.**
_Stop paying for work after the outcome is already good enough._

## Executive Summary

**OutcomeFuse is the runtime policy that continuously asks whether another unit of AI work is worth paying for, given the declared quality contract. Everything else is an enforcement mechanism.**

It is middleware that lowers what an AI agent costs to run, without lowering what it produces — designed to wrap existing tool-using agent loops with minimal integration change.

The expensive waste in enterprise agents is not usually badly worded prompts. It is irrelevant context carried forward, tools re-called after they have already answered, premium reasoning spent on trivial steps, and — most expensively — iteration that continues after the answer is already good enough. Many existing optimization approaches are primarily retrospective, or optimize individual levers independently: they surface the waste in a report someone has to read and act on, or tune one dimension without reference to whether the outcome was already sufficient. By then the money is spent, and the fix depends on a human getting around to it.

OutcomeFuse turns a task into an **Outcome Contract** — required deliverable, measurable quality floor, cost ceiling, permitted tools, escalation and human-review conditions — and enforces it during execution. It stops the moment quality passes, escalates when quality genuinely demands it, and will not trade quality for savings under any circumstances. The deliverable is not a report about a run. It is a cheaper run.

The distinction that matters: **turn the OutcomeFuse UI off and the savings still happen.** Turn a dashboard off and its value disappears entirely.

## The Problem

An agent given a business task and a set of tools has no notion of what its answer is worth. It optimizes for finishing, not for finishing efficiently. In practice that produces four compounding costs:

- **Context carry-forward.** Every step inherits the accumulated transcript, so token spend grows superlinearly with iteration count while marginal relevance falls.
- **Redundant tool calls.** The same query is issued repeatedly across steps because nothing remembers it was already answered.
- **Uniform premium reasoning.** The most capable model handles trivial steps — reformatting, extraction, routing — at the same rate as genuinely hard ones.
- **Overrun loops.** The most expensive failure mode. The agent reaches a sufficient answer at iteration three and keeps working to iteration eight because nothing told it to stop. Every token after the point of sufficiency is pure waste, and it is invisible without a quality signal.

The common response is observability: capture the run, score the waste, recommend a change, wait for someone to implement it. That loop is slow, human-dependent, and retrospective. Meanwhile the same agent runs the same wasteful way thousands more times.

The cost of the status quo is not only money. Overrun loops add latency users feel, and an agent with no quality floor can return a confidently wrong answer that no budget control would have caught — because budget controls measure spend, not sufficiency.

## The Solution

A declarative contract, a policy that reads it, and a set of mechanisms that enforce what the policy decides.

**The Outcome Contract** states what "done" means before execution begins: the required deliverable and evidence fields, a measurable quality floor, token and cost ceilings, permitted tools and call limits, iteration bounds, escalation policy, and the conditions requiring human approval.

**The policy — this is OutcomeFuse.** Before every unit of work, one question: *is another unit of AI work worth paying for, given this contract?* Concretely — what is the cheapest next action likely to move this task above its quality floor, and has the floor already been reached? Nothing else in the system decides anything. The policy decides; the rest carry it out.

**The enforcement mechanisms.** Each is a well-understood technique. Their significance here is not novelty but subordination: none of them optimizes for itself, and each acts only when the policy says the next unit of work is or is not justified.

| Mechanism | What it enforces |
|---|---|
| **Budget Ledger** | Tracks allocated / spent / reserved / remaining; holds a protected reserve for final synthesis and verification; rejects steps that are unaffordable, duplicated, or low-expected-value |
| **Quality Gate** | Evaluates completion, adherence, and evidence coverage. Pass → stop. Fail with budget → targeted retry or escalation. Fail without budget → disclose partial result or request a human |
| **Loop Fuse** | Computes a progress fingerprint per iteration; halts on repeated state, no new evidence, or repeated tool arguments |
| **Tool Governor** | Canonicalizes and caches tool calls; denies duplicates and optional calls once evidence is sufficient |
| **Context Governor** | Compresses tool output into structured evidence capsules, preserving citations, identifiers, figures, and policy clauses |
| **Model Governor** | Starts on the cheapest eligible model; escalates only when complexity, criticality, or a failed quality evaluation justifies it |
| **Preflight Planner** | Produces a typed execution graph with per-step cost envelopes, separating mandatory evidence from optional enrichment |

The Quality Gate is the mechanism the policy depends on most — without a signal for *sufficient*, "worth paying for" has no meaning and the rest degrades into ordinary cost-capping.

**The quality floor outranks the budget, always.** The runtime is designed to exceed a cost ceiling and request human intervention rather than return a cheaper answer that fails the contract. A budget that silently degrades output is not a saving — it is a defect.

## What Makes This Different

**It is not an observability product, and the difference is structural rather than positional.** A dashboard's output is information that a human must interpret and act on. OutcomeFuse's output is a completed task that cost less. There is no insight to action, because the action already happened mid-run.

| | Post-run auditors (TokenLens, Copilot Token Optimizer) | OutcomeFuse |
|---|---|---|
| When it acts | After the run | During the run |
| What it produces | Analysis and recommendations | A modified execution |
| Savings | Estimated for a hypothetical future run | Realized in this run |
| Requires manual optimization | Yes — someone must read the findings and change the agent | No — the adjustment happens in-run |
| Unit of concern | Workload analytics | Outcome Contract + runtime policy |
| Flow | Observe → Analyze → Recommend | Contract → Allocate → Act → Verify → Stop/Escalate |

**This does not mean humans are removed from the loop.** The contract can require human approval for side-effecting or high-impact tools, and the Quality Gate escalates to a person when it cannot reach the floor safely. What is removed is the *manual optimization* cycle — nobody has to read a report and re-engineer the agent to capture the saving.

Three further points of honesty about the moat:

- **It is not a new agent framework.** OutcomeFuse is designed to wrap existing tool-using agent loops with minimal integration change. Adoption cost is the reason to believe it can spread.
- **Individual techniques are not novel.** Caching, loop bounds, compression, and model routing all exist, and OutcomeFuse claims none of them as invention — they are enforcement mechanisms. The product is the policy above them: a single declared objective, *the minimum spend required to meet a stated outcome-quality contract*, with a quality signal rather than a token counter deciding when to stop. What appears uncommon is the subordination, not the parts.
- **The savings claim is deliberately conservative.** OutcomeFuse reports **net** savings, inclusive of its own overhead — evaluator calls, planning passes, compression passes. Gross savings are how this category flatters itself. Net is the only number that survives scrutiny.

## Who This Serves

**Primary user — the agent owner.** The engineer or platform team responsible for an agent already running against real workloads, accountable for both its bill and its output quality, has two bad options today: cap tokens and risk silently worse answers, or leave it uncapped and absorb the cost. They need a third — spend whatever the outcome genuinely requires and not one token more. Success for them is a falling cost-per-completed-outcome with no quality regression, and no ongoing manual tuning.

**Secondary — the platform or FinOps owner** who must govern AI spend across many teams without becoming the bottleneck that blocks experimentation. The Outcome Contract gives them a policy surface that constrains cost without prescribing implementation.

**Secondary — compliance and Responsible AI reviewers**, who need an auditable record of why any given call was blocked, cached, compressed, or escalated, and assurance that cost optimization never silently degraded an answer.

OutcomeFuse is deliberately **domain-agnostic**: it governs tool-using agent loops regardless of the business domain they serve. It will be proven on multiple dissimilar workloads rather than tied to one vertical, so that generality is demonstrated rather than asserted.

_The primary persona is currently assumed, drawn from the builder's experience rather than research. Interviews with production agent owners are in scope to confirm or correct it._

## Success Criteria

Measured as baseline versus governed on a frozen case set — same tasks, same tools, same model versions, same settings. A deliberately reasonable baseline, not a strawman.

**Primary**

- **Net token reduction per completed outcome**, inclusive of all OutcomeFuse overhead
- **Quality held constant** — task-completion pass rate not meaningfully below baseline, and required evidence-field accuracy at or above it
- **Budget compliance** — 100% of runs terminate cleanly: stopped, safely escalated, or referred for human review. No silent overruns, no silent quality substitution

**Secondary**

- Reduction in tool calls and in estimated cost
- Reduction in P50 end-to-end latency
- Zero accepted safety or adherence regressions

**Reporting standard.** Mean and median across repeated runs, never a cherry-picked execution. Failures and escalations published alongside successes. Overhead reported as its own line item. Where possible, token counts are taken from gateway metering rather than self-reported by the governor, so the headline figure is independently measured.

> **Targets deliberately not yet fixed.** The source memo carried gross targets (≥40% tokens, ≥35% cost, ≥30% tool calls). Those were set before overhead was accounted for and must be restated as net once the first measurement exists — see Risks. Committing to a net number before measuring the governor's own cost would be guessing.

## Scope

**In — the governed runtime**

The runtime policy, the Outcome Contract that feeds it, and all seven enforcement mechanisms: Budget Ledger, Quality Gate, Loop Fuse, Tool Governor, Context Governor, Model Governor, Preflight Planner. Plus a frozen baseline agent, an automated A/B benchmark harness, a live side-by-side execution view showing governor decisions as they happen, and a proof card reporting net savings against quality.

**In — shadow mode.** The governor runs observing but not enforcing, logging every decision it *would* have made. This earns its place twice over: in production it is the answer to "how do we adopt this without risk" — prove the savings against real traffic before enabling enforcement — and in the MVP it is a measurement instrument, capturing the governed and ungoverned paths from a single run rather than two.

**In — proving grounds.** Four dissimilar workloads, chosen so that generality is demonstrated rather than claimed: research/investigation over a document corpus, codebase Q&A and triage, data/SQL analysis, and supply-chain exception investigation. Synthetic cases only — no production or confidential data.

**In — evidence work.** Expanded case counts with repeated runs per case, so quality claims rest on absolute pass counts rather than percentages over a thin sample. A dedicated overhead study establishing the task length at which the governor starts paying for itself. Structured conversations with two to three engineers who own a production agent, so the primary persona is evidenced rather than asserted.

**In — one thin Azure slice.** A single real managed-service integration rather than the full stack: token metering through the APIM AI gateway. Chosen deliberately — it moves the headline savings figure from self-reported to independently measured at the gateway, which is the difference between a number a judge has to trust and one they can check. Redis-backed tool caching is the fallback if APIM integration proves unstable.

**Sequencing note.** Build the harness once; each additional workload is then mock tools plus cases. Workloads are additive, not dependencies — report on those completed.

**Out of scope for this iteration**

- Full production Azure deployment. Beyond the single metering slice above, the managed-service path (Foundry Agent Service, Redis, Cosmos, Container Apps, Entra) remains the production story, not the demo. The MVP otherwise runs as an in-process governor. Keeping these separate is a strength for viability, not a weakness.
- Policy DSL for reusable contracts; learned marginal-value estimation; multi-agent budget transfer; CI cost-regression gates. All credible extensions, none required to prove the mechanism.
- Any claim of measured generalization beyond the workloads actually completed.

## Key Risks and Open Questions

| Risk | Why it matters | Current position |
|---|---|---|
| **Scope discipline** | Roughly 7.5 days of estimated build work sits inside a one-month window, solo. The schedule risk is gone; the replacement risk is gold-plating — spending the slack on an eighth mechanism instead of on stronger evidence for the seven that exist. | Most of the slack goes to evidence: more cases, repeated runs, a measured overhead baseline, and user interviews. Two additions were admitted, each because it strengthens the proof rather than the feature set — shadow mode (a measurement instrument as much as a capability) and gateway token metering (independent measurement of the headline claim). Anything further must displace planned work. |
| **Governor overhead unmeasured** | If evaluator, planner, and compression passes consume a large share of the baseline, net savings could fall far below gross — and on short tasks the governor may cost more than it saves. | Overhead instrumented from the first run; net targets set only after measurement. |
| **Rubric circularity** | The same person writes the quality rubric and the optimizer that must satisfy it. A reviewer will notice. | Freeze the rubric before governor work begins; prefer deterministic field-level validation over model-judged scoring. |
| **Baseline fairness** | The baseline is defined by the party who benefits from it losing. | Freeze prompt, tools, dataset, model version and settings before any comparison; publish the baseline definition alongside results. |
| **Synthetic data** | Every savings figure derives from cases the team authored. | State it plainly. Publish the case-construction rules so the set can be inspected rather than trusted. Partially offset by gateway-measured token counts, which are independent of the case set. |
| **Persona evidence** | The primary user was selected from the builder's judgment, not from research. "Customer focus" is an explicit evaluation signal. | Two to three interviews with production agent owners are now in scope. Until those happen, the persona is labeled as assumed. |

Further risks around sampling confidence and preview-stage platform dependencies are recorded in the addendum. Sampling confidence is now largely mitigated by the expanded case counts and repeated runs in Scope.

**Open questions**

- At what task length does the governor stop paying for itself?
- Who authors the quality floor in a real deployment, and how much effort is that per task type? This is the main adoption friction and the main threat to the scale story.
- Can a default contract be inferred for common task shapes, removing hand-authoring entirely?

## Vision

If this works, declaring an outcome contract becomes as ordinary as declaring a timeout. Any agent, in any framework, states what "good enough" means and what it may spend getting there — and the runtime handles the rest.

The near-term shape is middleware that any team can wrap around an existing agent in an afternoon. Beyond that: contracts become reusable policy artifacts owned by platform teams rather than hand-written per task; the marginal-value policy learns from historical runs instead of relying on fixed heuristics; and cost-per-verified-outcome becomes a first-class CI gate, so an agent version that gets more expensive without getting better simply does not ship.

The longer-term change is in how enterprises govern AI spend at all. Today the lever is restriction — quotas, caps, and approval gates that slow teams down to save money. OutcomeFuse replaces restriction with sufficiency: unlimited ambition, bounded waste. Spend whatever the outcome is worth, and nothing on work that was already done.

