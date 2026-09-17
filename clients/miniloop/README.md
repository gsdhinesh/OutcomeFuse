# miniloop — your own loop, governed

The smallest honest answer to *"we already have an agent loop; what does
integrating OutcomeFuse actually cost?"*

It costs **one file**. `agent.py` and `loop.py` import nothing from the library
and a test enforces that. `govern.py` is the integration.

```
uv run python clients/miniloop/run.py
uv run python clients/miniloop/run.py --agent repeats
uv run python clients/miniloop/run.py --agent hasty
uv run python clients/miniloop/run.py --approval denied
uv run python clients/miniloop/run.py --approval channel-unavailable
```

Every invocation runs **the same loop twice** — once with a `Driver` behind the
seam and once with nothing — and prints the difference. It is free: the agent is
deterministic, not a model, so nothing is billed and the table is reproducible.

---

## The four moments

`loop.py` is written against a four-method protocol. That is the whole surface.

| moment | governed | ungoverned |
| --- | --- | --- |
| `charge` | the model turn is held against a ledger that can refuse | counted, and nothing can refuse |
| `call` | the decision is written **before** the tool runs | the tool runs |
| `progress` | the fuse sees whether anything changed | nothing is watching |
| `finish` | the answer meets the contract's quality floor | the answer is whatever the agent said |

Everything else in a real integration is your framework's business and stays
that way.

---

## What each flag shows

Measured on `sc-c-001`, the frozen supply-chain calibration case.

| invocation | governed | ungoverned |
| --- | --- | --- |
| *(default)* | 4 calls, gate **pass**, `stop-sufficient` | 4 calls, no verdict |
| `--agent repeats` | **1** of 8 calls executed, `halt-no-progress` | **8** of 8 executed |
| `--agent hasty` | gate **fail**, escalated once, `returned-partial` | no verdict, wrong answer kept |
| `--approval denied` | gate **pass**, **0** side effects | gate absent, **1** side effect |
| `--approval channel-unavailable` | `fail-closed`, **0** side effects | unaffected, **1** side effect |

`--approval denied` is the one to read first. Same agent, same answer, gate still
passes — and the message to the planner did not go out, because a person said
no. The ungoverned arm sent it and wrote nothing down.

`--agent hasty` is the uncomfortable one, and is left uncomfortable on purpose:
with approval granted, the governed arm *also* messages the planner before it
knows the answer. The approval gate asked. It did not overrule the answer.

---

## Two things this cost us to learn

**A denial is a state change.** The first version of `agent.state()` returned
only what the agent had been *told*, so a turn spent being refused left the task
state identical and the fuse read it as a stall — halting the agent for having
complied with the governor. Under `--approval denied` the careful agent lost its
answer that way. Refusals are now part of the state the fuse is fed.

**Do not put the fuse on the answering turn.** An agent that just concluded has
the same task state as the turn before; it spent the turn writing, not looking.
Feeding that to the fuse reads the moment of success as a stall, and it halted
the careful agent one call short of its answer.

Both are in the code as comments beside the lines that fix them.

---

## What the ungoverned column cannot say

`terminal reason`, `gate verdict` and `events written` are empty for the
ungoverned arm — not because this client declined to fill them in, but because
nothing in an ungoverned loop knows them. That column is the argument.

---

Not part of the distribution. Nothing under `src/` imports this and the wheel
does not ship it (AD-17). See [INTEGRATION.md](../../INTEGRATION.md) §5 for the
mode this executes, and [clients/features](../features) for the shipped loop.
