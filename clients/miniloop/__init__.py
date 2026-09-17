"""A worked example of Mode B: someone else's loop, governed by OutcomeFuse.

Not part of the distribution. Nothing under `src/` imports this and the wheel
does not ship it (AD-17).

`clients/features` drives the **shipped** loop (Mode A). This client does the
other thing [INTEGRATION.md](../../INTEGRATION.md) documents and nothing in the
repository had yet executed: keep your own loop, and put the governor in front
of the tool executor and at the end of the turn.

Read it in this order:

| file | imports OutcomeFuse | what it is |
| --- | --- | --- |
| `agent.py` | no | the agent, standing in for your framework |
| `loop.py` | no | the loop, written against a four-method seam |
| `govern.py` | **yes, all of it** | the seam, implemented twice |
| `run.py` | no | the CLI that runs both and prints the difference |

The first two files are library-free on purpose, and a test asserts it. That is
the whole claim of Mode B: integrating costs you one file, and it is not the one
your agent lives in.
"""

from __future__ import annotations
