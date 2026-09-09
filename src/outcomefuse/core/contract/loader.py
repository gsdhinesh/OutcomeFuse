"""Loading a contract (AD-7, FR9).

Safe loader only — no tag resolution, no object construction — under bounded
size and depth. Parsing precedes the run manifest, so a rejection is recorded
against the contract's content hash rather than against a run: `load_text`
returns the file-digest of the bytes even when validation fails.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Final

import yaml
from pydantic import ValidationError

from ..verify.path import PathError, root_field
from .models import Contract

#: A contract is hand-authored (FR12). These are generous for that and hostile
#: to a file designed to exhaust the parser.
MAX_CONTRACT_BYTES: Final[int] = 256 * 1024
MAX_DEPTH: Final[int] = 24


class ContractError(ValueError):
    """A contract was refused. Carries the digest of the bytes that were refused."""

    def __init__(self, message: str, *, sha256: str | None = None) -> None:
        super().__init__(message)
        self.sha256 = sha256


class SafeContractLoader(yaml.SafeLoader):
    """SafeLoader with implicit tag resolution and aliases removed.

    SafeLoader already refuses arbitrary object construction. Two things it
    still does are unwanted in a file that decides a quality floor: resolving
    `yes`/`on` to booleans and country-code-like strings to other types, and
    expanding aliases, which is the billion-laughs shape.
    """

    def compose_node(self, parent: Any, index: Any) -> Any:
        if self.check_event(yaml.events.AliasEvent):
            event = self.peek_event()
            raise yaml.constructor.ConstructorError(
                None, None, "aliases are not permitted in a contract", event.start_mark
            )
        return super().compose_node(parent, index)


for _tag in ("tag:yaml.org,2002:timestamp",):
    SafeContractLoader.yaml_implicit_resolvers = {
        first: [(tag, regexp) for tag, regexp in resolvers if tag != _tag]
        for first, resolvers in SafeContractLoader.yaml_implicit_resolvers.items()
    }


def _depth(value: Any, level: int = 1) -> int:
    if level > MAX_DEPTH:
        raise ContractError(f"contract nests deeper than {MAX_DEPTH}")
    if isinstance(value, dict):
        return max((_depth(v, level + 1) for v in value.values()), default=level)
    if isinstance(value, list):
        return max((_depth(v, level + 1) for v in value), default=level)
    return level


def load_text(text: str, *, sha256: str | None = None) -> Contract:
    """Parse and validate contract source. Raises `ContractError` on refusal."""
    encoded = text.encode("utf-8")
    digest = sha256 or hashlib.sha256(encoded).hexdigest()
    if len(encoded) > MAX_CONTRACT_BYTES:
        raise ContractError(
            f"contract is {len(encoded)} bytes, limit is {MAX_CONTRACT_BYTES}", sha256=digest
        )

    try:
        raw = yaml.load(text, Loader=SafeContractLoader)  # noqa: S506 - loader is safe by class
    except yaml.YAMLError as exc:
        raise ContractError(f"contract does not parse: {exc}", sha256=digest) from exc

    if not isinstance(raw, dict):
        raise ContractError(
            f"contract is a {type(raw).__name__}, expected a mapping", sha256=digest
        )
    _depth(raw)

    try:
        return Contract.model_validate(raw)
    except ValidationError as exc:
        raise ContractError(f"contract is invalid: {exc}", sha256=digest) from exc


def load_path(path: Path) -> Contract:
    data = path.read_bytes()
    return load_text(data.decode("utf-8"), sha256=hashlib.sha256(data).hexdigest())


def unsatisfiability_warnings(contract: Contract) -> list[str]:
    """FR9: warn before executing, rather than discovering it mid-run.

    Well-formed contracts only. Each finding is a floor that cannot be reached
    as written — not a style complaint, because a warning nobody believes is
    worse than no warning.
    """
    warnings: list[str] = []
    reserve = contract.budget.verification_reserve
    if reserve is not None:
        if reserve.max_tokens >= contract.budget.max_tokens:
            warnings.append(
                f"verification reserve of {reserve.max_tokens} tokens leaves nothing "
                f"for the run within {contract.budget.max_tokens}"
            )
        if reserve.max_estimated_cost >= contract.budget.max_estimated_cost:
            warnings.append(
                f"verification reserve of {reserve.max_estimated_cost} leaves nothing "
                f"for the run within {contract.budget.max_estimated_cost}"
            )

    declared = set(contract.deliverable.structure)
    for tier, criterion in contract.criteria.tiers():
        if criterion.verifier is None:
            continue
        try:
            field = root_field(criterion.verifier.args.get("path", ""))
        except PathError:
            continue
        if field not in declared:
            warnings.append(
                f"{tier} criterion {criterion.id!r} verifies {field!r}, which the "
                "deliverable never asks for, so it can never pass"
            )

    if contract.budget.max_iterations < 2 and any(
        c.verifier is not None for c in contract.criteria.mandatory
    ):
        warnings.append(
            "max_iterations of 1 leaves no iteration in which to act on a gate failure"
        )

    tool_names = {tool.name for tool in contract.tools}
    if not tool_names:
        warnings.append("no tools are permitted, so no evidence can be gathered")

    return warnings
