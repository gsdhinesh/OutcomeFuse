# Failure Posture

Companion to [SPEC.md](SPEC.md). Holds the placement of each failure behaviour. Posture is a property of *where* a component sits, not a choice each component's author makes — otherwise a degraded run becomes indistinguishable from a clean one in the record.

**The asymmetry, plainly:** losing an optimization costs money; losing the gate costs correctness. Only one of those is allowed to fail quietly.

## Fail-open — a property of the advisor registry

On failure of the Context Governor, Model Governor, Preflight Planner, tool cache or gateway metering, the run continues without that mechanism.

- An advisor that raises is **deregistered for the remainder of the run**; execution continues.
- A `degraded` event naming the mechanism is appended to the log.
- Any run carrying a deregistration is marked degraded, and every figure it yields carries that label.
- The registry is **run-scoped** — built at run start from the manifest's enabled set, discarded at run end — so a transient failure in one repeat never silently degrades the repeats that follow it in the same process.

**Degraded is not disabled.** Disabled means never registered, recorded in the manifest at run start. Degraded means deregistered mid-run, recorded in the log.

## Fail-closed — a property of the driver

These terminate through the precedence ladder in [decision-model.md](decision-model.md) at position 1, carrying `fail-closed` as both decision reason and terminal reason.

| Condition | Behaviour |
| --- | --- |
| Quality Gate cannot produce a verdict | No pass is reported; the run halts and escalates per the contract, or requests a human |
| Ledger state lost or unreliable | The run halts rather than continuing to spend against an unknown budget |
| Approval **channel** unavailable | The gated call is not made |

## Approval: two distinct states

These are ranked differently by the ladder and are never merged. Collapsing the second into the first would route an ordinary timeout to `fail-closed`, changing both the run's terminal reason and what the caller receives.

| State | Meaning | Outcome |
| --- | --- | --- |
| `channel-unavailable` | The adapter cannot accept or create the approval request, or loses the decision channel of a request it had accepted | Fail-closed; the gated call is not made |
| `no-response` | The request was accepted and the channel stayed available, but no decision arrived within `approval_timeout` | The contract's `on_timeout` applies |

Where `on_timeout` is unspecified, the default is exactly: `decision_reason = approval-timeout`, `policy_action = terminate`, `terminal_reason = approval-timeout`, and **the gated call is not made**. Contracts that want the run to survive a timeout must say so. An unbounded pause is not a safe default — it is an outage wearing a governance costume.

Approval is obtained through a port. The MVP implementation is a **scripted decider driven by the case definition** (approve · deny · never respond), so the fail-closed path is exercised rather than asserted.

## Shadow mode applies neither posture

In shadow the driver alters nothing the host would otherwise do — including under every fail-closed condition above. It records the halt it would have imposed and lets execution continue. Shadow mode's entire proposition is that it cannot hurt you; a governor that halts a production agent it promised only to observe destroys the adoption path.

## Required failure cases

The benchmark suite contains synthetic cases exercising at least: sufficiency stop, budget exhaustion, no-progress halt, approval timeout under **both** `on_timeout` postures, Quality Gate unavailable, Budget Ledger state loss, and optimization-mechanism failure.

For **every** case the expected `policy_action` and `decision_reason` are asserted. A `terminal_reason` is asserted **only for cases in which execution actually terminates**; cases that survive their failure — an escalating approval timeout, a degraded optimization mechanism — are asserted to record no terminal reason and to continue.
