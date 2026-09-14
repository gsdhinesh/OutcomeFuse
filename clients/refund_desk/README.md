# The refund desk — a loop with OutcomeFuse plugged in and plugged out

A client of the library, not part of it. Nothing under `src/` imports this and
the wheel does not ship it (AD-17). It exists to answer two questions the
in-tree tests cannot, because they are written from inside the distribution:

1. **Can OutcomeFuse be plugged into a use case it was not built around?**
2. **Does plugging it in change what happens?**

```powershell
uv run python clients/refund_desk/run_desk.py
uv run python clients/refund_desk/run_desk.py --case rd-001 --approval denied
uv run python clients/refund_desk/run_desk.py --case rd-001 --approval channel-unavailable
uv run pytest tests/clients -q
```

Nothing is spent and no model is called. The agent is scripted through the
library's own `ScriptedModelPort`, so both arms see a byte-identical transcript
and every difference below is attributable to the wiring and to nothing else.

## The use case

A support desk adjudicates a customer's refund request. It reads the order, the
shipment and the published refund policy, then either moves money or does not.

It was chosen because the last step is irreversible. Everything before it is a
read that can be repeated at no cost beyond tokens; `issue_refund` pays a real
customer real money, and no amount of care in a prompt makes that safe to leave
to an agent's discretion. That is what a governor is *for*, and a use case
without one makes governance a latency tax with nothing on the other side.

Three cases, one of each shape the policy can produce:

| case | situation | disposition |
| --- | --- | --- |
| `rd-001` | opened electronics, inside the window | `approve-partial`, less a 15% restocking fee |
| `rd-002` | carrier confirmed the parcel lost | `approve-full` |
| `rd-003` | requested 96 days after delivery | `deny` |

## Where the library plugs in

The whole seam is one type in [loop.py](loop.py):

```python
class Wiring(Protocol):
    def call_tool(self, call: ToolCall) -> ToolOutcome: ...
    def charge_model_turn(self, *, step_id, tokens, cost, model_used) -> str | None: ...
    def note_progress(self, *, task_state, evidence_count) -> str | None: ...
    def finish(self, deliverable, *, answer_key, parse_failure) -> Finish: ...
```

`Ungoverned` executes every proposal and records what happened. `Governed` puts
every proposal to a `Driver` first. The loop is written once and does not know
which it has — it proposes a step and applies the verdict, which is AD-1's
cooperative enforcement written as ordinary application code.

All the library imports live in [compose.py](compose.py), the composition root,
so "what did plugging it in cost me?" is a one-file answer.

### The contract names a workload the library has never heard of

`refund-desk` is not one of the four frozen workloads.
`outcomefuse.workloads.tool_port_for` raises on it, and
`tests/clients/test_refund_desk.py` asserts that it does. The client builds its
own `WorkloadToolPort` from a handler table instead. **A new use case needs a
handler table, not an edit to the library** — which is question 1, answered.

## What plugging it in changed

With the approval channel answering `approved`, on `rd-001`:

```
                        plugged out           plugged in
  model turns           4                     4
  tokens                1345                  1345
  tool calls proposed   6                     6
  tool calls executed   6                     4
  withheld              0                     2
                                              - order_lookup: cache-hit
                                              - order_lookup: cache-hit
  gate                  pass                  pass
  terminal reason       -                     stop-sufficient
```

Two things are worth saying plainly about that table.

**The token counts are identical, and that is not a defect.** The model is
scripted, so both arms emit the same turns; what the governor bought here is two
tool invocations, not tokens. A client that reported a token saving off this run
would be reporting an artefact of its own fixture.

**The answer did not move.** Both arms pass the gate with the same deliverable.
A governor that changes the answer is worse than no governor, and this is the
assertion (`test_the_wiring_does_not_change_the_answer`) that would catch it.

### The part that is actually worth the money

Same case, approval channel answering `denied`:

```
  tool calls executed   6                     3
  withheld              0                     3
                                              - order_lookup: cache-hit
                                              - order_lookup: cache-hit
                                              - issue_refund: approval-denied
  gate                  pass                  pass
  money moved           plugged out: issue_refund: ORD-4417 160.65 restocking-fee-applied
                        plugged in:  none
```

The ungoverned loop paid a customer £160.65 with no human anywhere near the
decision. The governed loop asked, was told no, did not pay, **and still
adjudicated the case and still passed its quality gate**. The refusal is not a
failed run; it is the run working.

And with `--approval channel-unavailable` the governed run terminates
`fail-closed` without paying, because FR89 ranks an unreachable approval channel
above the approval gate: a gate you cannot consult is not a gate you may skip.

Every assertion about whether money moved reads the tool port's own probe
(AD-15), never the decision log. The log is the artefact a broken run would
falsify, so it cannot also be the evidence that the run was not broken.

## What validating the library turned up

`check_order` does not describe the event sequence a real `Driver` writes. Four
families of finding come out of a clean, correct governed run:

- nothing emits `verdict-applied` (pre-existing, already disclosed in the repo);
- `bind_citable_index` and the deliverable sidecar observe evidence that no tool
  requested;
- a model turn reserves and settles budget without proposing a decision, because
  a model turn is a spend and not a decision cycle;
- a suppressed call records a decision without reserving budget, because it
  spends none.

`test_check_order_does_not_describe_what_the_driver_writes` pins exactly those
four and fails on anything else, so the gap is characterised rather than either
asserted away or quietly tolerated.

## Files

| file | what it holds |
| --- | --- |
| [refund-desk.contract.yaml](refund-desk.contract.yaml) | the Outcome Contract: deliverable, criteria, budget, tools, approval clause |
| [desk.py](desk.py) | the dataset, the tools, the citable policy index, the three cases |
| [loop.py](loop.py) | the loop, the `Wiring` seam, and the two wirings |
| [compose.py](compose.py) | the composition root — every library import lives here |
| [run_desk.py](run_desk.py) | the CLI and the comparison table |

Tools expose data and never answers. `refund_policy_lookup` returns every clause
sorted by id, so the ordering implies nothing about which clause governs, and
nothing in `desk.py` decides whether a refund is owed. Both wirings draw from one
handler table and one dataset, so nothing done here can flatter the governor
without flattering its control identically.
