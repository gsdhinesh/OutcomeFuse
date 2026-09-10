"""Step classes and the FR98 gate cadence.

The cadence predicate is **core-owned and declarative**. Two drivers that each
obeyed every other rule could still evaluate the gate at different points, and
because every gate execution is billed as governor overhead they would report
materially different overhead shares. Worse, they would *terminate* differently:
cadence is what gives `stop-sufficient` first refusal on the ending, so a run
that became sufficient after a retrieval step could end `stop-sufficient` under
one driver and `halt-exhausted` under another — the product's headline event
misfiled as a failure.

So the classes are closed and declared here, the driver labels each step with
exactly one of them, and no driver, adapter or advisor may define, override or
infer a step's class by any other route.
"""

from __future__ import annotations

from typing import Final, Literal, get_args

StepClass = Literal[
    "deliverable-mutating",
    "evidence-gathering",
    "planning",
    "routing",
    "verification",
]

STEP_CLASSES: Final[frozenset[str]] = frozenset(get_args(StepClass))

#: The gate executes after any step whose class is in this set.
DEFAULT_CADENCE: Final[frozenset[StepClass]] = frozenset(
    {"deliverable-mutating", "evidence-gathering"}
)

#: A contract may add classes to the cadence set; it may not remove this one.
#: Omitting it would let a contract switch the gate off for the only class of
#: step that definitionally changes the thing being judged.
IRREMOVABLE: Final[frozenset[StepClass]] = frozenset({"deliverable-mutating"})


class CadenceError(ValueError):
    """A contract tried to declare a cadence the core does not permit."""


def cadence_for(added: frozenset[str] | set[str] | None = None) -> frozenset[str]:
    """The effective cadence set: the core default plus whatever the contract adds."""
    extra = set(added or set())
    unknown = sorted(extra - STEP_CLASSES)
    if unknown:
        raise CadenceError(f"unknown step classes: {unknown}")
    return frozenset(DEFAULT_CADENCE | extra)


def validate_cadence(declared: frozenset[str] | set[str]) -> frozenset[str]:
    """Check a contract's fully declared cadence set."""
    declared = set(declared)
    unknown = sorted(declared - STEP_CLASSES)
    if unknown:
        raise CadenceError(f"unknown step classes: {unknown}")
    missing = sorted(IRREMOVABLE - declared)
    if missing:
        raise CadenceError(f"a contract may not remove {missing} from the cadence set")
    return frozenset(declared)


def should_evaluate(
    step_class: str,
    *,
    cadence: frozenset[str] | set[str] | None = None,
) -> bool:
    """Whether the gate runs after a step of this class."""
    if step_class not in STEP_CLASSES:
        raise CadenceError(f"unknown step class: {step_class!r}")
    return step_class in (cadence if cadence is not None else DEFAULT_CADENCE)


def should_evaluate_before_halt(*, fail_closed: bool) -> bool:
    """FR98: before every terminal halt other than a fail-closed one.

    The exception exists because a gate that cannot produce a verdict cannot be
    asked for one.
    """
    return not fail_closed
