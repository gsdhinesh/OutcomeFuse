"""Answer keys, and the seal on the evaluation split (FR66, AD-7).

Two jobs, because they are the same concern.

**Loading.** The keys are derived from the frozen corpora by
`freeze/derive_answer_keys.py` and committed. Nothing here derives, repairs or
infers one: a key that disagrees with the corpus is regenerated, never corrected
in place, or the benchmark stops measuring the corpus and starts measuring
whoever last edited the file.

**The seal.** The evaluation split stays closed until a preregistration exists.
The whole point of writing targets down in advance is that they were written
before anyone saw how the system performs — and a single peek at the evaluation
answer keys destroys that, permanently and invisibly. There is no way to unsee
them and no test that can detect it afterwards. So the seal is enforced at the
only place that can enforce it: the read.

Structural checks over the case *files* are not sealed. Validating that the YAML
parses and that the ids line up reveals nothing about difficulty or answers, and
sealing it would only push those checks somewhere less careful.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Final

import yaml

ROOT: Final[Path] = Path(__file__).resolve().parents[3]

SEALED_SPLIT: Final[str] = "evaluation"


class AnswerKeyError(ValueError):
    """The keys could not be loaded."""


class SealBroken(AnswerKeyError):
    """The evaluation split was opened without a preregistration.

    Its own type, and deliberately not catchable by accident: a caller that
    wanted calibration and got here has a bug that would otherwise burn the
    evaluation split silently.
    """


def load_answer_keys(
    workload: str,
    split: str,
    *,
    preregistration_hash: str | None = None,
) -> dict[str, dict[str, Any]]:
    """Every answer key for one workload and split, keyed by case id.

    `preregistration_hash` is required for the evaluation split and ignored for
    calibration. It is not validated against a registry here — the manifest
    records it and FR66's own checks compare it — but its *absence* is fatal,
    because absence is the case that cannot be repaired later.
    """
    if split == SEALED_SPLIT and not preregistration_hash:
        raise SealBroken(
            "the evaluation split is sealed until a preregistration exists. "
            "Targets written after seeing the evaluation answer keys are not "
            "predictions, and no later check can tell the difference"
        )

    path = ROOT / "cases" / split / workload / "answer-keys.yaml"
    if not path.is_file():
        raise AnswerKeyError(f"no answer keys at {path}")

    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict) or not document:
        raise AnswerKeyError(f"{path} is not a mapping of case ids to keys")
    for case_id, key in document.items():
        if not isinstance(key, dict):
            raise AnswerKeyError(f"{path}: the key for {case_id!r} is not a mapping")
    return document


def answer_key_for(
    case_id: str,
    workload: str,
    split: str,
    *,
    preregistration_hash: str | None = None,
) -> dict[str, Any]:
    keys = load_answer_keys(workload, split, preregistration_hash=preregistration_hash)
    if case_id not in keys:
        # Not a missing-key default. A case with no key cannot be scored, and
        # scoring it against `{}` would pass anything.
        raise AnswerKeyError(f"no answer key for {case_id!r} in {split}/{workload}")
    return keys[case_id]
