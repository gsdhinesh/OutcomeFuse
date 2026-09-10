"""Failure posture is declared at registration, not chosen per call site (AD-20).

Fail-open is a property of the advisor registry; fail-closed is a property of
the driver. A port sits on one side or the other and says which at registration,
so no call site gets to invent its own behaviour and no degraded run becomes
indistinguishable from a clean one.
"""

from __future__ import annotations

from typing import Final, Literal, get_args

from pydantic import BaseModel, ConfigDict, Field

Posture = Literal["fail-open", "fail-closed"]
POSTURES: Final[frozenset[str]] = frozenset(get_args(Posture))

#: Where a port's posture is not a matter of opinion. A port registered against
#: the wrong posture is refused, because §10's asymmetry is the whole point:
#: losing an optimisation costs money, losing the gate costs correctness.
REQUIRED_POSTURE: Final[dict[str, Posture]] = {
    "record": "fail-closed",
    "approval": "fail-closed",
    "ledger": "fail-closed",
    "gate": "fail-closed",
    "model": "fail-open",
    "metering": "fail-open",
    "tool-cache": "fail-open",
}


class PostureError(ValueError):
    """A port was registered against a posture the architecture does not allow."""


class PortRegistration(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(min_length=1)
    posture: Posture
    version: str = Field(min_length=1)


class PortRegistry:
    """What the manifest records as the enabled set at run start."""

    def __init__(self) -> None:
        self._ports: dict[str, PortRegistration] = {}

    def register(self, name: str, posture: Posture, version: str) -> PortRegistration:
        required = REQUIRED_POSTURE.get(name)
        if required is not None and posture != required:
            raise PostureError(
                f"port {name!r} must be registered {required!r}, not {posture!r}"
            )
        if name in self._ports:
            raise PostureError(f"port {name!r} is already registered")
        entry = PortRegistration(name=name, posture=posture, version=version)
        self._ports[name] = entry
        return entry

    def posture_of(self, name: str) -> Posture:
        try:
            return self._ports[name].posture
        except KeyError:
            raise PostureError(f"port {name!r} is not registered") from None

    def registered(self) -> dict[str, str]:
        """Name to version, for the run manifest."""
        return {name: entry.version for name, entry in sorted(self._ports.items())}
