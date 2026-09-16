"""Turn one run into a stream of events a browser can watch.

The run happens on a worker thread and emits through `TeeStore`, which hands
over each event **after** it is durably written. So the view can never show a
step the record does not contain — which is the point of FR5, and a live view
that could get ahead of the log would be worse than no live view at all.

**The pacing is inserted and the UI says so.** A scripted run finishes in
milliseconds; a delay between events is the only way a person can watch one. The
events, their order and their contents are exactly what was written. Only the
interval is added.
"""

from __future__ import annotations

import json
import queue
import threading
import time
import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from features import compose
from features import work as work_module

from outcomefuse.core.record import Event
from outcomefuse.ports import ApprovalRequest

from . import scenarios
from .approval import LiveApprovalPort
from .delta import summarise, verdict
from .jobs import Job

#: Long enough to cover a person thinking. The approval port has its own window,
#: taken from the contract; this only stops a genuinely wedged run hanging here.
MAX_WAIT_SECONDS = 400.0


def as_json(event: Event) -> dict[str, Any]:
    """One event, flattened to what the view draws. Nothing is computed here."""
    return {
        "seq": event.seq,
        "kind": event.kind,
        "lane": event.lane,
        "step_id": event.step_id,
        "policy_action": event.policy_action,
        "decision_reason": event.decision_reason,
        "terminal_reason": event.terminal_reason,
        "gate_verdict": event.gate_verdict,
        "verification_mode": event.verification_mode,
        "quality_state": event.quality_state,
        "model_used": event.model_used,
        "tokens": event.tokens_consumed,
        "tool": (event.payload or {}).get("tool"),
        "unmet": list((event.payload or {}).get("unmet") or []),
        "detail": _detail(event),
    }


#: Verifier types that read the case answer key or the citable index. Whether a
#: criterion can fire outside a frozen case turns on this, so the viewer is told.
REFERENCE_BACKED = frozenset({"exact-match-against-answer-key", "citation-resolves"})


def _first_sentence(text: str) -> str:
    flat = " ".join((text or "").split())
    head, stop, _rest = flat.partition(". ")
    return head + "." if stop else flat


def compared(job: Job, summaries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The two values the gate put side by side, for each criterion it refused.

    The gate builds a full per-criterion breakdown - `Verdict.breakdown`, with a
    detail string reading "3.0 does not equal the key's 2" - and the driver logs
    only the ids in `unmet`. The breakdown never reaches the record, so this
    cannot be read out of the log and is rebuilt instead from two durable
    artefacts: the sealed deliverable sidecar, and the frozen answer key.

    Which only works while the published deliverable *is* the refused one. A
    retry writes `deliverable.json` again over the same path, so on a run that
    escalated and then passed, the draft the gate objected to is gone - the log
    keeps its hash and nothing keeps its body. Those rows say so rather than
    quoting the replacement, which would show a passing value beside the
    criterion that failed it.
    """
    spec = compose.contract(job.workload)
    args = {
        c.id: (c.verifier.args, c.verifier.type)
        for _band, crits in spec.criteria
        for c in crits
        if c.verifier is not None
    }
    key = compose.key_for(job.case_id, job.workload)
    rows: list[dict[str, Any]] = []
    for summary in summaries:
        answer = summary.get("answer") or {}
        kept = summary.get("quality") == "fail"
        for name in summary.get("unmet") or ():
            spec_args, kind = args.get(name, ({}, ""))
            path = str(spec_args.get("path", ""))
            row: dict[str, Any] = {
                "arm": summary["arm"],
                "criterion": name,
                "path": path,
                "kept": kept,
            }
            if kept:
                row["got"] = answer.get(path.removeprefix("$.").split("[")[0])
            if kind == "exact-match-against-answer-key":
                row["wanted"] = key.get(str(spec_args.get("key", "")))
            elif kind == "numeric-range":
                row["wanted"] = (
                    f"between {spec_args.get('min')} and {spec_args.get('max')}"
                )
            elif kind == "regex-match":
                row["wanted"] = "to match the contract's pattern"
            rows.append(row)
    return rows


def criteria_of(workload: str) -> dict[str, dict[str, Any]]:
    """What each criterion checks, so an escalation can say why in words.

    The log records `unmet: ['result-matches-key']`, which is the right thing
    for a log and useless on a screen. The wording comes from the frozen
    contract rather than being restated here, so the two cannot drift - but only
    the first sentence of it. These descriptions go on to explain the authoring
    decision behind the criterion, which belongs in the contract and not on a
    line in a tree.
    """
    spec = compose.contract(workload)
    return {
        c.id: {
            "says": _first_sentence(c.description) or c.id,
            "verifier": c.verifier.type if c.verifier else "",
            "needs_key": bool(
                c.verifier and c.verifier.type == "exact-match-against-answer-key"
            ),
            "reference_backed": bool(c.verifier and c.verifier.type in REFERENCE_BACKED),
        }
        for _band, crits in spec.criteria
        for c in crits
        if c.verifier is not None
    }


def _detail(event: Event) -> str:
    payload = event.payload or {}
    if payload.get("fuse"):
        return f"fuse: {payload['fuse']}"
    if payload.get("from") and payload.get("to"):
        unmet = ", ".join(payload.get("unmet") or [])
        return f"{payload['from']} -> {payload['to']}" + (f" (unmet: {unmet})" if unmet else "")
    if payload.get("citable_index_sha256"):
        return f"citable index {payload['citable_index_sha256'][:16]}..."
    if payload.get("deliverable"):
        return f"deliverable kept, {str(payload.get('sha256', ''))[:16]}..."
    if payload.get("tool_error"):
        return f"tool error: {payload['tool_error']}"
    if payload.get("detail"):
        return str(payload["detail"])
    if payload.get("when"):
        return f"gate ran {payload['when']}"
    if payload.get("canonical_key"):
        # Identical calls hash alike, which is how a repeat is spotted at all.
        return f"same-call fingerprint {str(payload['canonical_key'])[:12]}..."
    return ""


def play(
    job: Job,
    runs_dir: Path,
    *,
    case_id: str,
    delay: float = 0.0,
    approval: LiveApprovalPort | None = None,
    session: str = "",
    arms: tuple[str, ...] = (scenarios.GOVERNED,),
) -> Iterator[dict]:
    """Run one job on worker threads, yielding frames as they are written.

    Both arms run **at once** when both are asked for. That is not a detail: on
    the approval jobs the governed run stops at the gate while the ungoverned one
    carries on, and running them in sequence would hide the one thing worth
    seeing — that the message is already sent by the time you have decided.
    """
    work = work_module.by_workload(job.workload)
    situation = scenarios.by_key(job.situation)
    # Every play is its own run, with its own id, seal and database. Clicking a
    # card twice used to write both to one file, and the second could not open
    # it while the first still held it.
    token = uuid.uuid4().hex[:8]
    channel: queue.Queue[Any] = queue.Queue()
    finished: dict[str, Any] = {}

    if approval is not None:
        # Without this the port would block on a question nobody was asked.
        approval.on_ask = lambda request: channel.put(
            ("approval", scenarios.GOVERNED, _asking(approval, request))
        )

    def worker(arm: str) -> None:
        try:
            run = scenarios.run(
                situation,
                work,
                arm=arm,
                runs_dir=runs_dir,
                case_id=case_id,
                sink=lambda event, a=arm: channel.put(("event", a, as_json(event))),
                approval=approval,
                token=token,
            )
            finished[arm] = summarise(run, arm)
        except Exception as exc:  # noqa: BLE001 - reported to the viewer, never swallowed
            finished[arm] = {"arm": arm, "error": f"{type(exc).__name__}: {exc}"}
        finally:
            channel.put(("end", arm, None))

    workers = [
        threading.Thread(target=worker, args=(arm,), name=f"{job.key}-{token}-{arm}",
                         daemon=True)
        for arm in arms
    ]
    for thread in workers:
        thread.start()

    yield {
        "type": "start",
        "job": job.key,
        "title": job.title,
        "workload": job.workload,
        "case": case_id,
        "session": session,
        "interactive": scenarios.is_interactive(situation, work),
        "arms": list(arms),
        "expect": job.expect,
        "criteria": criteria_of(job.workload),
    }

    running = len(arms)
    while running:
        try:
            tag, arm, payload = channel.get(timeout=MAX_WAIT_SECONDS)
        except queue.Empty:
            yield {"type": "error", "message": "the run stopped producing events"}
            return
        if tag == "end":
            running -= 1
            continue
        if tag == "approval":
            # Never paced. A question the viewer has to answer is the one frame
            # that must not be held back for effect.
            yield {"type": "approval", "arm": arm, "request": payload}
            continue
        if delay:
            time.sleep(delay)
        yield {"type": "event", "arm": arm, "event": payload}

    for thread in workers:
        thread.join(timeout=5.0)
    # An arm that raised is reported beside the one that did not, never instead of
    # it. On the unanswerable case the ungoverned arm genuinely explodes on a gate
    # it cannot evaluate while the governed one refuses and seals — and collapsing
    # that into one error frame would throw away the comparison worth seeing.
    crashed = [s for s in finished.values() if "error" in s]
    summaries = [
        finished[arm] for arm in arms if arm in finished and "error" not in finished[arm]
    ]
    if not summaries:
        yield {"type": "error", "message": "; ".join(s["error"] for s in crashed)}
        return
    yield {
        "type": "done",
        "summaries": summaries,
        "crashed": crashed,
        "verdict": verdict(summaries),
        "compared": compared(job, summaries),
    }


def _asking(port: LiveApprovalPort, request: ApprovalRequest) -> dict[str, Any]:
    return port.describe(request)


def frame(payload: dict) -> bytes:
    """One server-sent event. Two newlines end it; a missing one hangs the reader."""
    return f"data: {json.dumps(payload)}\n\n".encode()
