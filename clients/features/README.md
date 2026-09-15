# Every feature of OutcomeFuse, demonstrated and then measured

A client of the library, not part of it. Nothing under `src/` imports this and
the wheel does not ship it (AD-17).

```powershell
uv run python clients/features/report.py
uv run pytest tests/clients -q
```

Writes [submission/outcomefuse-features.html](../../submission/outcomefuse-features.html)
and sealed logs to `runs/features/`. No model is called and nothing is spent.
Exits non-zero if any feature stops demonstrating itself.

## One use case, and why that is enough

**Supply-chain, and nothing else.** Features here are driven by the *contract*
and the *scenario*, not by the domain. Budget exhaustion needs a small ceiling,
not a different industry; the approval gate needs a side-effecting tool, which
this workload has; escalation needs a failing gate, which any workload can
produce. A second use case would add surface and no coverage.

Supply-chain specifically, because it is **frozen**: real cases
(`cases/calibration/supply-chain`), derived answer keys, a real SQLite corpus,
and — the part that matters most — a recorded gpt-5 campaign already exists for
it, so the report can end with what actually happened instead of only what can
be made to happen.

**The loop is not written here.** It is
`outcomefuse.harness.runner.run_case` — the same loop that drove the recorded
campaign — and the governor plugs into it through the `Arm` seam the library
already defines: `GovernedArm` holds a `Driver`, `BaselineArm` holds nothing.
Swapping one for the other is the entire difference between a governed run and
an ungoverned one, and it is a constructor argument. Demonstrating a
re-implementation would prove something about the re-implementation.

## The two halves, and why they disagree

| | shows | how |
| --- | --- | --- |
| **Demonstrated** | the mechanisms *work* | 22 scenarios, each driven deliberately, sealed, read back from the log |
| **Measured** | how often they *mattered* | the recorded gpt-5 campaign, counted |

The second half is the honest one. Across 38 sealed supply-chain runs and 66
tool calls driven by a real model:

```
  identical repeats          0 in 66 proposed calls
  cache substitutions        0
  calls the governor denied  0
  approval pauses            0
  loop-fuse halts            0
  escalations                7
```

The tool governor's cache, its denials, the loop fuse and the approval gate
**never fired at all**. The scripted scenarios above them show those mechanisms
work; they say nothing about how often they are needed, and the report says so
in those words. The proof card's own headline attributes 100% of the saving to
`agent-stopped-unaided` — the agent finishing by itself — and records
`reportable: false`.

## What the report asserts, rather than claims

Every status is **computed** from a sealed log, a verdict or a returned value.
A mechanism that quietly stopped working reports `NOT DEMONSTRATED` instead of
continuing to be advertised, and `tests/clients/test_feature_report.py` turns
that into a failing suite. One of those tests plants a broken deliverable to
confirm the instrument can actually fail.

Three statuses are not successes and are meant to be read:

### `GAP` — an approval condition on a criterion is never evaluated

The frozen contract declares:

```yaml
- criterion: recommended_action
  when: value_in
  value: [escalate-to-buyer, resource-alternate-supplier]
```

`ToolGovernor.requires_approval` matches only `condition.tool`. No code path
reads a criterion-scoped condition. It is validated at load and dead at runtime:
a reader would assume `escalate-to-buyer` needs a human, and nothing happens.
Contract validation is not execution.

### `DEFECT` — a hallucinated tool name kills the governed run

```
  governed terminal    fail-closed      governed answered    not-evaluated
  ungoverned terminal  ran to the end   ungoverned answered  pass
```

An agent naming a tool that does not exist is an agent error, like an
unparseable deliverable — which the same driver correctly returns as a value.
Instead `ToolGovernor` raises, `Driver.execute_step` catches it as a
governing-component failure, and the run terminates fail-closed. On the
commonest model mistake the governor is strictly worse than no governor.

### Scenarios that had to misbehave say so

An agent that stalls, cites a clause that does not exist, or answers wrongly is
**authored** to do that — detecting a stall requires one. Those are stimuli for
a code path, never samples of behaviour. Rows marked `mechanism-level` call a
component directly rather than through a run, which is honest about proving
less. Budget exhaustion and the referred-to-human ending use **variant**
contracts built in memory, because the frozen contract does not configure them;
each says so on its own row. The frozen contract is never edited.

## Files

| file | what it holds |
| --- | --- |
| [compose.py](compose.py) | the composition root — stores, ledgers, manifests, both arms |
| [agents.py](agents.py) | the scripted agents, one per scenario |
| [catalogue.py](catalogue.py) | the 22 features, each asserting its own evidence |
| [measured.py](measured.py) | the recorded campaign, counted |
| [report.py](report.py) | the CLI and the HTML |
