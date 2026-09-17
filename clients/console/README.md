# The console — Twelve jobs, each showing exactly one thing

An interactive client. Nothing under `src/` imports it and the wheel does not
ship it (AD-17).

```powershell
uv run python clients/console/server.py       # the UI
uv run python clients/console/compare.py      # the same twelve, headless
uv run python clients/console/compare.py --matrix   # everything behind them
```

The UI opens `http://127.0.0.1:8765`. Standard library only —
`ThreadingHTTPServer` and server-sent events. A web framework would be a
dependency this repo has not taken and does not need for one page and one
stream. Local-only bind, four routes, and the only value read from a request is
a job key checked against the gallery. Nothing is spent; sealed logs land in
`runs/console/`.

## Why the gallery is flat

It used to ask twice: pick a kind of work, then pick what goes wrong. That is a
**matrix**, and a matrix is a thing you verify, not a thing you show someone. No
real job goes wrong nine different ways, and being asked to choose which way it
goes wrong gives the game away before the run has started.

So there is one screen. **One card is one job is one task** — one real task, on
one frozen case, meeting one mechanism, the way a person would actually meet it.
There is no picker and no variant: a job names the case it runs and runs that.

| | job | work | case | shows | kind |
| --- | --- | --- | --- | --- | --- |
| 1 | The agent wants to message the planner | purchase order | `sc-c-001` | human approval — **you answer** | difference |
| 2 | The agent wants to write to the orders table | database question | `ds-c-004` | the same gate over a *write* | difference |
| 3 | The agent runs the test suite, and nobody is asked | bug report | `ct-c-001` | that clause cannot fire | **a gap** |
| 4 | The agent reads the same file over and over | bug report | `ct-c-002` | cache, then the loop fuse | difference |
| 5 | The agent works through order after order | purchase order | `sc-c-007` | the ledger and the ceiling | difference |
| 6 | The agent answers from a policy that was withdrawn | policy question | `dr-c-002` | escalation to a stronger model | difference |
| 7 | The agent cannot get the figure right | database question | `ds-c-002` | the FR103 ladder — partial | difference |
| 8 | Still cannot settle it, and the contract wants a buyer | purchase order | `sc-c-004` | the FR103 ladder — referred | a decision |
| 9 | The agent asks for git blame | bug report | `ct-c-003` | the governor is worse than none | **a defect** |
| 10 | The dataset cannot support an answer | purchase order | `sc-c-012` | fail-closed vs an exception | difference |
| 11 | The agent simply does the job properly | policy question | `dr-c-003` | the whole loop, changing nothing | no cost |

Twelve different tasks across all four frozen workloads. No two jobs are the
same `(workload, case)` pair, and tests pin that. Ten run answerable cases;
card 10 is deliberately the one that cannot be answered.

**Read the kind column first.** Four of the twelve move no figure at all, and a
gallery that lets them sit unlabelled beside the ones that do is inviting you to
assume every card is a win. One is a gap, one is a defect where the governor is
strictly worse than no governor, one records a disposition without changing an
outcome, and one exists precisely to show that governing a clean run costs
nothing. Each card carries its kind as a badge, and a test pins the kind against
the measured pair so the two cannot drift apart.

A twelfth card — *the document fetch keeps failing* — was removed rather than
explained. Both arms made the same four failing calls and agreed on every
figure, so there was nothing for a viewer to watch. The mechanism behind it is
real and still swept: `compare.py --matrix` runs it, two tests pin it, and each
of its two claims has a mutant in `scripts/mutate_check.py` that the suite
catches. `jobs.NOT_SHOWN` records the omission and why.

Click one and it runs **twice, at once** — with the governor and without — in two
lanes side by side. Both arms get the same agent, the same contract and the same
tools, built from one definition, so nothing can flatter the governor without
flattering its control identically.

Concurrently, not in sequence. That is not a detail: on the approval jobs the
governed run stops at the gate while the ungoverned one carries on, and running
them one after the other would hide the only thing worth seeing — that the
message is already sent by the time you have decided.

The case is not a request parameter. A card makes a claim about a particular
task, and letting a caller point that claim at a different one would make it
untestable — so `job` is the only value any route reads, and a test pins that.

## Three cards, one mechanism, one finding

`ToolGovernor.requires_approval` matches a condition only when it names a tool
**and** its `when` is `always`. Every other form loads from the contract and is
never evaluated:

| work | its clause | fires |
| --- | --- | --- |
| purchase order | `tool: notify_planner`, `when: always` | **yes** |
| purchase order | `criterion: recommended_action`, `when: value_in` | no — never read |
| database question | `tool: sql_execute_write`, `when: always` | **yes** |
| bug report | `tool: run_tests`, `when: call_index_exceeds` | **no** |
| policy question | none declared | correctly absent |

Cards 1 and 2 are the gate working. Card 3 is the same mechanism and the same
agent on a contract whose clause cannot fire, so a tool that genuinely acts on
the world is reached with nobody asked. Its card says OutcomeFuse does
*nothing*, and putting the three side by side is the point.

The policy question is the one where the absence of a clause is right rather
than a gap: nothing there leaves the dataset.

## The matrix is still swept, just not shown

```powershell
uv run python clients/console/compare.py --matrix --quiet
```

Every situation against every kind of work — **20 of 33 differ in what
happened**. That sweep is how the approval gap was found and is the only thing
that keeps it found; the tests run it too. The gallery is the showing, this is
the checking, and they are deliberately different shapes.

Running the twelve cards headless instead (`compare.py` with no flags) checks
each card's own claim: **6 of 10 differ** once the two that wait on a person are
skipped.

## Most comparisons find nothing, and the UI says so

Each card carries an `expect`: where the arms should part company, or nothing.
When they agree the verdict panel says it plainly:

> **The arms agree — nothing material changed.** On this one the governor
> changed nothing about what happened. That is a result, not a gap — the recorded
> campaign found the same on most runs.

A test runs every card and checks its `expect` against the actual verdict, in
both directions: a card promising a difference must get one, and a card
promising agreement must not quietly start differing.

**A difference in what happened is kept apart from a difference in what was
written down.** The ungoverned arm has no terminal reason because nothing
governed it — it simply stopped. Knowing *why* a run ended is worth something,
but counting it beside "the message did not go" would flatten two very different
magnitudes into one number. `delta.py` holds that split, and the page and the CLI
both use it, because two implementations of "what changed" would eventually
disagree about the same pair of runs.

## When one arm throws

Card 11 is the unanswerable case. Its answer key pins no values, so a
reference-backed criterion cannot be evaluated — and the two arms do genuinely
different things about that:

- **Governed:** a *decision*. `fail-closed`, recorded, sealed, verifiable.
- **Ungoverned:** an *exception*. `GateUnavailable` comes straight out of the
  harness, and there is no log at all.

So the stream reports a crashed arm **beside** the surviving one rather than
instead of it. Collapsing that into a single error frame would throw away the
comparison worth seeing. Only when *no* arm survives does it become an error.

This is what excluded `sc-e-008` from the recorded campaign's proof card.

## The one port that is not scripted

Everything else here is scripted, because the question elsewhere is what the
library does and a person in the loop would make it neither reproducible nor
fast. The approval gate is the exception: it is the mechanism whose entire point
is that a human decides, and demonstrating it with a pre-recorded answer
demonstrates the wrong thing.

`LiveApprovalPort` **really blocks**. `ToolGovernor.assess` calls `request()` on
the driver's own thread and does not return until you click or the window
elapses.

| you | what the log records | did it happen |
| --- | --- | --- |
| **Approve** | `proceed` / `justified` | yes |
| **Refuse** | `deny` / `approval-denied`, run continues and still passes | no |
| **nothing** | `approval-timeout` via the contract's `on_timeout` | no |

The countdown is the contract's own window, not a number chosen to make a
demonstration comfortable. Only `approved` and `denied` are accepted over HTTP:
`no-response` is what happens when you give none, and a channel failure is not
yours to declare. With nobody listening at all the port reports
`channel-unavailable`, which FR89 ranks above the gate itself — silence is never
read as consent.

It only ever appears on the two cards whose clause can fire. Offering a decision
button on card 3 would stage a gate that does not exist.

## The two properties that make the view safe to trust

**It can never get ahead of the record.** Events are teed from
`RecordStore.append` *after* the row is durably written, so a lane cannot show a
step the log does not contain — which is what FR5 exists to prevent. A test
asserts the stream is the sealed log: same sequence numbers, same kinds, same
order, nothing invented.

**The watcher governs nothing.** The sink cannot refuse, delay or alter an event,
and one that raises is recorded on the store rather than allowed to unwind into
the run. A test runs a deliberately hostile sink and checks the run still passes,
still terminates `stop-sufficient` and still verifies.

## The pacing is inserted, and the UI says so

A scripted run finishes in milliseconds. The slider inserts a delay between
events so a person can watch one. The events, their order and their contents are
exactly what was written — only the interval is added. Approval questions are
never paced.

## The tree is a projection

Grouped by the `step_id` already on every event. No parent/child field was added
to the record to make this draw, which is why the same tree comes out of a live
stream and a sealed log alike (FR111). Grouping is **contiguous**, not a lookup
by id: pooling every `step_id: null` event into one bucket would draw the run's
ending above the work that led to it.

`sc-c-001-02` reads as *supply-chain / calibration / case 001 / model turn 02* —
the library builds it as `f"{case_id}-{iteration:02d}"`. The UI shows "turn 3"
with the raw id beside it, because the id is what the log contains and hiding it
would make the tree unverifiable against the record.

## The agents are the job's own

The invented tool on card 9 is one that work might plausibly have been given
and was not — `git_blame`, and `supplier_scorecard` / `table_stats` /
`policy_timeline` for the others — rather than a placeholder. The budget agent on
card 5 makes a genuinely **different** call every turn (twelve POs, twelve
SELECTs, twelve greps, twelve search terms), because repeating one would let the
cache absorb it and you would be watching a stall wearing a ceiling's card. Tests
pin both.

Six of the twelve agents are **authored to misbehave**, and every such card says
so. Nothing measured should ever be read off one.

## Files

| file | what it holds |
| --- | --- |
| [jobs.py](jobs.py) | the twelve cards as **data**: a task, a case, a mechanism, a kind, and the claim |
| [../features/work.py](../features/work.py) | the four kinds of work, and agents that do each well and badly |
| [scenarios.py](scenarios.py) | the mechanisms and the agents that provoke them; **no wording** |
| [approval.py](approval.py) | the port that blocks the run until a person answers |
| [delta.py](delta.py) | what differs between two arms, shared by the page and the CLI |
| [stream.py](stream.py) | both arms on worker threads, events as frames |
| [server.py](server.py) | four routes, the SSE stream, and the session registry |
| [app.html](app.html) | the page: the gallery, the task, two lanes, the verdict |
| [compare.py](compare.py) | the twelve headless, or `--matrix` for everything behind them |

The tee itself is `TeeStore` in [../features/compose.py](../features/compose.py),
beside the rest of the wiring.
