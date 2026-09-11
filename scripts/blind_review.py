"""FR69's blind review: prepare a packet, then record the verdicts.

A human reads deliverables and judges them without seeing what the gate said.
The review exists to *contradict* the gate, so anything that lets the reviewer
see the verdict first destroys the only thing it measures.

Two phases on purpose, rather than one interactive prompt:

    python scripts/blind_review.py prepare data-sql --preregistration prereg-1
    ...a human edits runs/review/data-sql/answers.yaml...
    python scripts/blind_review.py record data-sql

**Preparing records the sample.** The seed and the chosen run ids are written
before any judging happens, so a reviewer who dislikes the result cannot quietly
re-draw. Re-preparing with the same seed picks the same runs; a different seed
writes a different file and both survive.

**What the reviewer sees**: the case prompt, which is public, and the
deliverable, read through `BlindReviewHandle` — a class with no method that
returns a verdict, a decision record or a manifest. What they do not see: the
gate's answer, the answer key, or which arm produced it.
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path
from typing import Any

import yaml

from outcomefuse.core.record import RecordStore
from outcomefuse.evidence.counter_metrics import BlindReview
from outcomefuse.evidence.store import AccessDenied, EvidenceStore
from outcomefuse.harness.cases import load_case_set
from outcomefuse.harness.preregistration import PreregistrationError, load_preregistration

RUNS = Path("runs/campaign")
REVIEWS = Path("runs/review")


def _gate_passes(workload: str) -> list[str]:
    """Run ids whose gate recorded a pass. Reading this is the harness's job."""
    passed = []
    for path in sorted((RUNS / workload).glob("*.db")):
        with RecordStore(path, writer=False).open() as store:
            for run_id in store.run_ids():
                verdicts = [
                    e.gate_verdict for e in store.events(run_id) if e.kind == "gate-verdict"
                ]
                if verdicts and verdicts[-1] == "pass":
                    passed.append(run_id)
    return sorted(passed)


def _case_of(run_id: str) -> str:
    return run_id.rsplit("-", 1)[0]


def prepare(workload: str, *, sample_size: int, seed: int) -> Path:
    passes = _gate_passes(workload)
    if not passes:
        raise SystemExit(f"no gate passes recorded for {workload}; run a campaign first")

    # Seeded so the draw is reproducible and recorded; nothing here is a secret.
    chosen = sorted(random.Random(seed).sample(passes, min(sample_size, len(passes))))  # noqa: S311
    if len(chosen) < sample_size:
        print(
            f"! only {len(chosen)} gate passes exist; the preregistered sample is "
            f"{sample_size} and a partial sample cannot establish the rate"
        )

    prompts = {c.case_id: c.prompt for c in load_case_set(workload, "calibration").cases}
    store = EvidenceStore(RUNS / workload / "evidence", data_class="synthetic")
    out = REVIEWS / workload
    out.mkdir(parents=True, exist_ok=True)

    items = []
    for index, run_id in enumerate(chosen, start=1):
        try:
            deliverable = store.for_blind_review(run_id).deliverable()
        except AccessDenied as exc:
            print(f"! {exc}")
            continue
        items.append({"item": index, "run_id": run_id})
        (out / f"item-{index:02d}.md").write_text(
            f"# Item {index}\n\n## The task\n\n{prompts.get(_case_of(run_id), '(unknown case)')}\n"
            f"\n## The answer given\n\n```json\n{deliverable}\n```\n"
            "\n## Your judgement\n\n"
            "Does this answer the task, on its own terms? Record `accept` or\n"
            "`reject` against this item number in answers.yaml. You are not\n"
            "being asked whether it matches a key -- you have not been shown one.\n",
            encoding="utf-8",
        )

    # The sample is written before any judging, so it cannot be re-drawn after
    # a result somebody dislikes. It lives *outside* the packet: it maps each
    # item to a run id, and a run id ends in `-governed` or `-baseline`. Knowing
    # which arm produced an answer biases a reviewer as effectively as knowing
    # the verdict, and the reviewer has to open this directory to answer.
    (REVIEWS / f"{workload}.sample.yaml").write_text(
        yaml.safe_dump(
            {
                "workload": workload,
                "seed": seed,
                "sample_size": sample_size,
                "drawn_from": len(passes),
                "items": items,
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    answers = out / "answers.yaml"
    if not answers.exists():
        answers.write_text(
            "# accept or reject, one per item. Nothing here shows you the gate's\n"
            "# verdict; that is the point.\n"
            + yaml.safe_dump({i["item"]: "" for i in items}, sort_keys=True),
            encoding="utf-8",
        )
    print(f"{len(items)} items written to {out}")
    print(f"drawn from {len(passes)} gate passes with seed {seed}")
    print(f"now fill in {answers}")
    return out


def record(workload: str) -> BlindReview:
    out = REVIEWS / workload
    sample = yaml.safe_load(
        (REVIEWS / f"{workload}.sample.yaml").read_text(encoding="utf-8")
    )
    answers: dict[Any, Any] = yaml.safe_load((out / "answers.yaml").read_text(encoding="utf-8"))

    verdicts = {
        int(k): str(v).strip().lower()
        for k, v in (answers or {}).items()
        if str(v).strip()
    }
    unknown = sorted(v for v in verdicts.values() if v not in {"accept", "reject"})
    if unknown:
        raise SystemExit(f"answers must be accept or reject, got {unknown}")

    review = BlindReview(
        reviewed=len(verdicts),
        rejected=sum(1 for v in verdicts.values() if v == "reject"),
        sample_size=sample["sample_size"],
    )
    (REVIEWS / f"{workload}.review.yaml").write_text(
        yaml.safe_dump(review.model_dump(mode="json"), sort_keys=True), encoding="utf-8"
    )
    print(json.dumps(review.model_dump(mode="json"), indent=2, sort_keys=True))
    print(f"false-sufficiency rate: {review.false_sufficiency_rate:.3f}")
    return review


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=["prepare", "record"])
    parser.add_argument("workload")
    parser.add_argument("--preregistration", default=None)
    parser.add_argument("--sample-size", type=int, default=None)
    parser.add_argument("--seed", type=int, default=1)
    args = parser.parse_args()

    if args.phase == "record":
        record(args.workload)
        return 0

    size = args.sample_size
    if size is None:
        if not args.preregistration:
            raise SystemExit("give --sample-size or --preregistration")
        try:
            size = load_preregistration(args.preregistration).blind_review_sample_size
        except PreregistrationError as exc:
            raise SystemExit(str(exc)) from exc
    prepare(args.workload, sample_size=size, seed=args.seed)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
