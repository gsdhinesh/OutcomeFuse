# chat — a governed support desk you can talk to

A real-time chat where an agent works a customer's order, and the governor sits
between it and anything that costs money.

```
uv run python clients/chat/server.py
```

→ <http://127.0.0.1:8770>. Stdlib only, free, deterministic, nothing billed.

Ask it something. It looks the order up, reads the policy, and when it wants to
refund or email a customer **it stops and asks you** — in the chat, while the
run is genuinely blocked. Tick *also run it ungoverned* to see the same message
go through a loop with nothing in front of it.

---

## Why this is a fresh solution and not another demo

It is a **new use case brought to the governor from outside**. None of it is in
`contracts/`, none of it is frozen, and nothing under `src/` was edited to add
it:

| piece | where it lives |
| --- | --- |
| the Outcome Contract | [chat.contract.yaml](chat.contract.yaml) |
| the tools | [desk.py](desk.py) — a handler table, built directly |
| the agent | [agent.py](agent.py) — imports no OutcomeFuse |
| the loop | [loop.py](loop.py) — imports no OutcomeFuse |
| the integration | [govern.py](govern.py) — **the only file that does** |
| one run per message | [session.py](session.py) |
| the wire | [server.py](server.py) + [app.html](app.html) |

`tool_port_for(contract)` dispatches on the workload name and raises on anything
it does not know, so a new desk builds a `WorkloadToolPort` from a handler table
instead. That is the plug-in point, and a test asserts the dispatcher refuses.

**It is also the first contract here with no answer key.** Nothing in a live
support chat has a reference answer sitting beside it, so every mandatory
criterion checks shape, bounds or citations. The gate says so out loud: its
qualifier reads `constraint-backed`, which is a weaker claim than the frozen
workloads make.

---

## The four moments, in a conversation

[loop.py](loop.py) is written against a four-method seam, implemented twice in
[govern.py](govern.py) — once holding a `Driver`, once holding nothing.

| moment | governed | ungoverned |
| --- | --- | --- |
| `charge` | the turn is held against a ledger that can refuse | counted; nothing can refuse |
| `call` | the decision is written **before** the tool runs | the tool runs |
| `progress` | the fuse sees whether anything changed | nothing is watching |
| `finish` | the answer meets the contract's floor | the answer is whatever the agent said |

What makes it a *chat* loop is that every frame is handed to the caller the
moment it happens. The agent's sentence goes out **before** the call it
explains; the tool line goes out **after** the governor has decided, never
before.

---

## What you will see

Measured, on the seeded desk:

| you ask | the desk | governed | ungoverned |
| --- | --- | --- | --- |
| *order 1001 arrived damaged* → **Deny** | wants a $74.00 refund | `referred-to-a-person`, **$0 moved**, gate pass, 31 events, chain verified | `refund-issued`, **$74.00 gone**, no verdict, no log |
| *order 1005 is broken* | $245.00 is over the desk's authority | `replacement-offered`, emails on approval | same, asks nobody |
| *order 1004 never turned up* | no carrier scan in 16 days | `escalate-to-carrier`, emails on approval | same |
| *where is order 1002?* | still in transit | `in-transit-no-action`, no approval needed | same |
| *refund order 1003* | delivered 104 days ago | `not-eligible`, no money moves | same |
| *my parcel is late* | no order number | one question, **no run opened** | — |

The first row is the one to read. Same agent, same message, same answer — and
one of them spent seventy-four dollars.

Approvals that are not answers behave differently, and deliberately:
`channel-unavailable` is **fail-closed** (silence is never consent) and nobody
answering follows the contract's `on_timeout`, which is `request-human`.

---

## What building it taught

**The deliverable vocabulary has to be able to describe what actually happened.**
It started with five dispositions and needed seven.

- Deny the refund and the answer came back `refund-issued`, amount `$74.00` — a
  run that had been *stopped* from spending money reported that it had. There
  was no way to say *decided, and not carried out*. → `referred-to-a-person`.
- Ask *"where is order 1001?"* and the desk reached an approval prompt for
  $74.00, because the order's own note mentions two missing keys. There was no
  way to say *asked a question, answered it, changed nothing*, so a request for
  a location was pushed into a refund disposition. → `information-provided`, and
  the customer's note is now evidence for a refund question rather than a
  trigger for one.

Both are the same shape. A schema written before the governor was wired in
usually cannot express a refusal, and a schema written around one outcome cannot
express the others.

**The gate passed every one of these.** `explanation-is-substantive` checks a
length floor and `policy-is-cited` checks the clause resolves; neither can tell
you the answer was about something else. That is what the contract's two
**advisory** criteria are for — named, never evaluated, because no deterministic
verifier reaches them. A person reading the transcript found all three.

Also fixed and commented in the code: *"where is order 1002?"* was answered by
explaining the refund window and asserted the last scan was "today" whatever the
shipment record said. Every fact in that sentence is now read back from the tool
result.

Two carried over from [miniloop](../miniloop): a refusal is a state change
(leave it out of the fuse's task state and the governor halts the agent for
complying with the governor), and the answering turn must not be put to the
fuse.

---

## Things worth knowing

- **One message is one run.** A contract governs a task, and "resolve this
  customer's question" is the task. It follows that the Tool Governor's cache is
  per-run: asking the same thing twice in one conversation pays twice. The
  second message is a new task that happens to look like the first.
- **The threading is load-bearing.** `/ask` runs the loop inline on its own
  thread and blocks inside the approval port; `/answer` arrives on a different
  thread and releases it. One thread and the demo deadlocks the first time the
  desk tries to spend money.
- **The log is written before the page sees it.** `TeeStore` hands each event to
  the sink *after* the durable write, so the viewer can never get ahead of the
  record.
- **Port 8770, not 8765.** The console lives there, and a stale process on a
  reused port serves the previous client without saying so.

Logs land in `runs/chat/<session>-<n>.db`, deliverables under
`runs/chat/evidence/`.

---

Not part of the distribution. Nothing under `src/` imports this and the wheel
does not ship it (AD-17). See [INTEGRATION.md](../../INTEGRATION.md) for the
integration modes and [clients/miniloop](../miniloop) for the same seam without
a browser.
