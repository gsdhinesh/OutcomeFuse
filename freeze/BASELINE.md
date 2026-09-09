# Baseline Definition v1 (FR64)

**Status:** E1a draft. Frozen, versioned and content-hashed at E1b. The harness
refuses to produce a comparison when the executing baseline configuration
differs from this definition.

> The baseline is defined by the party who benefits from it losing. Publishing
> its definition is the only defence against that. Read this adversarially.

## What the baseline is

A **reasonable** agent, not a strawman:

- **Full retrieved context per step.** The whole working transcript is carried
  forward. This is the ordinary thing to do and it is the thing the Context
  Governor exists to improve on — so it must be what the baseline actually does.
- **One capable model throughout.** `gpt-4o` for every call. No routing, no
  downgrade on easy steps. Escalation is a governor behaviour; the baseline has
  nothing to escalate from.
- **A genuine evaluator/retry loop.** The agent checks its own completion notion
  and retries when unsatisfied, up to the iteration safety limit.
- **A maximum-iteration safety limit.** Ten. Without it the baseline can run
  forever and the comparison becomes a story about a broken control, not about
  the governor.

## What the baseline is not

The baseline's evaluator is **real**, and it checks the agent's own notion of
done. What it does not check is an externally declared quality floor with named
evidence fields — because that artifact does not exist without an Outcome
Contract.

Results are therefore described as **self-assessed completion** versus
**contract-assessed sufficiency**. They are never described as "the baseline
never stops", which would be false and is the single most tempting overclaim
available here.

## Frozen configuration

| Field | Value |
| --- | --- |
| Model | `gpt-4o`, provider version pinned in the run manifest |
| Temperature | `0` |
| Top-p | `1.0` |
| Max output tokens per call | `4096` |
| Streaming | **disabled** — the gateway estimates token counts when streaming is on, so the evidence path bars it |
| Context policy | full transcript, no compression, no eviction |
| Tool set | identical to the governed arm's, per workload, from the same contract's `tools` |
| Tool result handling | raw results appended verbatim to context |
| Retry policy | self-evaluated; retry while unsatisfied |
| Max iterations | `10` |
| Max tool calls | per-workload contract value, identical to the governed arm |
| Cost table | pinned version recorded in the manifest |
| Seed / sampling | recorded in the manifest |

The prompt template per workload is held alongside this file and hashed with it.

## OFF is an adapter state, not a driver

The baseline arm shares **no governor code**. The governor is out of the call
path entirely, so the arm's latency is not governor-inflated and no ablation can
be confused with it. This is the reason OFF is an adapter state rather than a
third driver.

## Fairness properties this definition is trying to preserve

1. **Same tools, same data, same model version, same settings.** Anything else
   makes the comparison a story about configuration.
2. **The two arms' manifests are identical except for mode and the enabled
   mechanism registry.** The harness compares field by field and refuses on any
   other difference — route, model version, cost-table version, seed and adapter
   version included.
3. **The baseline gets the iteration limit, not an unbounded loop.** A governor
   that only beats an unbounded competitor has proved nothing.
4. **The baseline gets the capable model.** Cheapening the baseline's model
   would hand the Model Governor a win it did not earn.

## Known asymmetries, stated rather than hidden

- **The baseline has no quality floor to stop at.** That is the point of the
  product and also a structural advantage in the comparison: the governed arm
  stops at *sufficient*, the baseline stops at *satisfied-with-itself*. This is
  why the quality counter-metrics exist and why pass-rate parity within two
  percentage points is a hard target rather than a nice-to-have.
- **The baseline pays no governor overhead.** Which is why the headline is
  **net**, and gross is never the headline.
- **Prompt-caching savings accrue to both arms** and are reported as a measured
  secondary lever, never attributed to OutcomeFuse.
