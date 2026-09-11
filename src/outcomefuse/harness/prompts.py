"""Prompt construction from the frozen shared task blocks (FR64, §8.1).

The templates under `freeze/baseline-prompts/` are the **shared task block**:
the bytes both arms send. The baseline sends the block alone; the governed arm
sends it verbatim and appends whatever the enabled mechanisms produced. Holding
the block identical is what makes the comparison about governance rather than
about who got the better prompt, so the block is read from the frozen file and
never rebuilt here.

Two rules from the frozen README are enforced rather than remembered:

- **An unsubstituted placeholder is a harness bug, not a prompt variation.**
  The run is refused rather than sent, because a template that reached a model
  with `{{as_of}}` still in it would produce a failure that looked like the
  agent's.
- **A placeholder may only draw from the named sources.** A case's reference
  holds the material its answer key is derived from; `Case` drops all but the
  three allow-listed keys before this module ever sees it.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Final

from pydantic import BaseModel, ConfigDict, Field

from .cases import Case

ROOT: Final[Path] = Path(__file__).resolve().parents[3]
TEMPLATE_DIR: Final[Path] = ROOT / "freeze" / "baseline-prompts"

_PLACEHOLDER = re.compile(r"\{\{(\w+)\}\}")
_BLOCK = re.compile(r"^##\s+(System|User)\s*$\n+```text\n(.*?)\n```", re.M | re.S)


class PromptError(ValueError):
    """The prompt could not be built. Never sent half-substituted."""


class Prompt(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    system: str = Field(min_length=1)
    user: str = Field(min_length=1)

    @property
    def shared_task_block(self) -> str:
        """What both arms send. The governed arm appends beneath it."""
        return f"{self.system}\n\n{self.user}"


def template_path(workload: str) -> Path:
    path = TEMPLATE_DIR / f"{workload}.md"
    if not path.is_file():
        raise PromptError(f"no frozen prompt template for workload {workload!r}")
    return path


def load_template(workload: str) -> Prompt:
    """The raw template, placeholders intact."""
    blocks = dict(_BLOCK.findall(template_path(workload).read_text(encoding="utf-8")))
    missing = {"System", "User"} - set(blocks)
    if missing:
        raise PromptError(f"{workload} template has no {sorted(missing)} block")
    return Prompt(system=blocks["System"].strip(), user=blocks["User"].strip())


def render(case: Case) -> Prompt:
    """Substitute the case's values into its workload's frozen block."""
    template = load_template(case.workload)
    values: dict[str, object] = {
        "case_id": case.case_id,
        # code-triage's template calls it a report; it is the same case text.
        "question": case.prompt,
        "report": case.prompt,
        **case.prompt_context,
    }

    def substitute(text: str) -> str:
        return _PLACEHOLDER.sub(
            lambda m: str(values[m.group(1)]) if m.group(1) in values else m.group(0),
            text,
        )

    rendered = Prompt(system=substitute(template.system), user=substitute(template.user))

    left = sorted(
        set(_PLACEHOLDER.findall(rendered.system) + _PLACEHOLDER.findall(rendered.user))
    )
    if left:
        raise PromptError(
            f"case {case.case_id!r} leaves {left} unsubstituted; the frozen README "
            "calls that a harness bug rather than a prompt variation, so the run is "
            "refused rather than sent"
        )
    return rendered
