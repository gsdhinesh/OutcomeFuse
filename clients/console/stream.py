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
from collections.abc import Iterator
from pathlib import Path
from typing import Any

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
        "detail": _detail(event),
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
        return f"key {str(payload['canonical_key'])[:12]}..."
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
            )
            finished[arm] = summarise(run, arm)
        except Exception as exc:  # noqa: BLE001 - reported to the viewer, never swallowed
            finished[arm] = {"arm": arm, "error": f"{type(exc).__name__}: {exc}"}
        finally:
            channel.put(("end", arm, None))

    workers = [
        threading.Thread(target=worker, args=(arm,), name=f"{job.key}-{arm}", daemon=True)
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
    }


def _asking(port: LiveApprovalPort, request: ApprovalRequest) -> dict[str, Any]:
    return port.describe(request)


def frame(payload: dict) -> bytes:
    """One server-sent event. Two newlines end it; a missing one hangs the reader."""
    return f"data: {json.dumps(payload)}\n\n".encode()
