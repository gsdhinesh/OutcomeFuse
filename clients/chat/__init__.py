"""A governed support desk you can talk to. Not part of the distribution.

Nothing under `src/` imports this and the wheel does not ship it (AD-17).

Read it in this order:

| file | imports OutcomeFuse | what it is |
| --- | --- | --- |
| `chat.contract.yaml` | — | the Outcome Contract, and the whole declarative surface |
| `agent.py` | no | the agent, standing in for your framework |
| `loop.py` | no | the conversational loop, over a four-method seam |
| `desk.py` | yes | the tools, as a handler table |
| `govern.py` | **yes** | the seam, implemented twice |
| `session.py` | yes | one run per message, frames as they happen |
| `server.py` | no | the wire, and nothing else |

`agent.py` and `loop.py` are library-free and a test enforces it. That is the
claim: the governor goes in front of an agent you already have, not inside it.
"""

from __future__ import annotations
