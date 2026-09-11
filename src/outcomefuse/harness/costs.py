"""The cost table (AD-13, FR79).

Cost is computed from a recorded, versioned rate table whose version travels in
the run manifest. Two runs priced with different tables are not comparable, and
reconstructing a price afterwards from whatever the vendor charges *today* would
silently re-price history.

The table can be **unpriced**: a rate may be `null` while nobody has read the
portal yet. An unpriced table loads, reports itself as unpriced, and refuses to
price anything. It does not fall back to zero. A zero rate yields a clean,
plausible and entirely false cost saving, and every check downstream would agree
with it — the arithmetic would be correct and the claim would be worthless.

Token savings are unaffected by any of this. They are counted, not priced, so
the headline token claim stands whether or not the rates are known.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Final

import yaml
from pydantic import BaseModel, ConfigDict, Field

ROOT: Final[Path] = Path("cost-tables")


class CostTableError(ValueError):
    """The table could not be loaded, or was asked to price what it cannot."""


class Unpriced(CostTableError):
    """A price was asked for that this table does not know.

    Deliberately its own type. A caller may reasonably choose to carry on and
    report tokens only; it may not reasonably mistake this for a zero.
    """


class Rate(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    #: `None` means unknown, never free.
    input: float | None = Field(default=None, ge=0)
    cached_input: float | None = Field(default=None, ge=0)
    output: float | None = Field(default=None, ge=0)

    @property
    def known(self) -> bool:
        # `cached_input` is excluded: prompt caching is a discount we do not
        # currently claim, and a table is usable without it.
        return self.input is not None and self.output is not None


class CostTable(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    version: str = Field(min_length=1)
    currency: str = Field(min_length=1)
    per_tokens: int = Field(gt=0)
    rates: dict[str, Rate]
    source: str = ""
    source_read_at: str | None = None

    @property
    def priced(self) -> bool:
        """Every model this table names has a rate that can be used."""
        return bool(self.rates) and all(rate.known for rate in self.rates.values())

    def unpriced_models(self) -> tuple[str, ...]:
        return tuple(sorted(name for name, rate in self.rates.items() if not rate.known))

    def price(self, model_id: str, *, prompt_tokens: int, completion_tokens: int) -> float:
        """What one call cost.

        `completion_tokens` already includes reasoning tokens — they are a
        subset, not an addition — so passing the reported total prices the
        reasoning without counting it twice.
        """
        if prompt_tokens < 0 or completion_tokens < 0:
            raise CostTableError("token counts cannot be negative")
        rate = self.rates.get(model_id)
        if rate is None:
            raise Unpriced(f"cost table {self.version} does not name model {model_id!r}")
        if not rate.known:
            raise Unpriced(
                f"cost table {self.version} has no rate for {model_id!r}; "
                "fill in cost-tables/ct-1.yaml rather than pricing this at zero"
            )
        assert rate.input is not None and rate.output is not None  # noqa: S101 - narrowed by `known`
        return (prompt_tokens * rate.input + completion_tokens * rate.output) / self.per_tokens


def load_cost_table(version: str, *, root: Path | None = None) -> CostTable:
    path = (root or ROOT) / f"{version}.yaml"
    try:
        raw: Any = yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise CostTableError(f"no cost table {version!r} at {path}") from exc
    except yaml.YAMLError as exc:
        raise CostTableError(f"cost table {version!r} is not readable YAML: {exc}") from exc

    if not isinstance(raw, dict):
        raise CostTableError(f"cost table {version!r} is not a mapping")
    try:
        table = CostTable.model_validate(raw)
    except Exception as exc:
        raise CostTableError(f"cost table {version!r} is malformed: {exc}") from exc

    if table.version != version:
        # The filename and the recorded version are what the manifest and the
        # reader each rely on. If they disagree, one of them is lying.
        raise CostTableError(
            f"cost table at {path} calls itself {table.version!r}, not {version!r}"
        )
    return table
