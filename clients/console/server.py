"""Pick a job, watch it run with the governor and without.

    uv run python clients/console/server.py
    then open http://127.0.0.1:8765

Standard library only — `ThreadingHTTPServer` and server-sent events. A web
framework would be a dependency this repo has not taken and does not need for
one page and one stream.

**Local only, on purpose.** It binds to 127.0.0.1, serves four routes, and the
only value it reads from a request is a job key checked against the gallery. It
runs scripted agents against synthetic corpora, so there is nothing here worth
reaching over a network for.
"""

from __future__ import annotations

import argparse
import json
import sys
import threading
import uuid
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "clients"))

from features import compose, work  # noqa: E402

from console import jobs, scenarios, stream  # noqa: E402
from console.approval import LiveApprovalPort  # noqa: E402

PAGE = Path(__file__).resolve().parent / "app.html"
RUNS = Path("runs/console")

DECISIONS = frozenset({"approved", "denied"})

#: The pause between events, in seconds. The run itself takes milliseconds.
DEFAULT_DELAY = 0.12
MAX_DELAY = 2.0

#: Runs currently waiting on a person. One per open stream, dropped when it ends.
_SESSIONS: dict[str, LiveApprovalPort] = {}
_LOCK = threading.Lock()


def gallery() -> dict:
    """Every job, grouped. One card, one mechanism, one real task."""
    return {"groups": list(jobs.GROUPS), "jobs": [card(job) for job in jobs.JOBS]}


def card(job: jobs.Job) -> dict:
    doing = work.by_workload(job.workload)
    situation = scenarios.by_key(job.situation)
    return {
        "key": job.key,
        "group": job.group,
        "title": job.title,
        "does": job.does,
        "without": job.without,
        "feature": job.feature,
        "watch": job.watch,
        "expect": job.expect,
        "authored": job.authored,
        "interactive": scenarios.is_interactive(situation, doing),
        "variant": situation.variant,
        "work": doing.name,
        "workload": job.workload,
        "case_id": job.case_id,
    }


def context(job: jobs.Job) -> dict:
    """The actual task. Without it the tree is machinery with no subject."""
    doing = work.by_workload(job.workload)
    spec = compose.contract(job.workload)
    subject = compose.case(job.case_id, job.workload)
    answerable = subject.expected_outcome == "answer"
    return {
        "work": doing.name,
        "blurb": doing.blurb,
        "shows": doing.shows,
        "asks": doing.asks,
        "gate_note": doing.gate_note,
        "workload": job.workload,
        "case_id": subject.case_id,
        "difficulty": subject.difficulty,
        "prompt": " ".join(subject.prompt.split()),
        "contract": f"{spec.contract_id} v{spec.version}",
        "mandatory": [c.id for c in spec.criteria.mandatory],
        "modes": spec.mandatory_modes(),
        "tools": [{"name": t.name, "side_effecting": t.side_effecting} for t in spec.tools],
        "budget": {
            "tokens": spec.budget.max_tokens,
            "tool_calls": spec.budget.max_tool_calls,
            "iterations": spec.budget.max_iterations,
        },
        "models": list(spec.models.eligible) if spec.models else [],
        "answerable": answerable,
        "unanswerable_note": (
            ""
            if answerable
            else "This case pins no values: the dataset cannot support an answer. A "
            "reference-backed criterion cannot be evaluated against a key with no entry, "
            "so the run ends fail-closed whatever the agent says. That is what happened "
            "to sc-e-008 in the recorded campaign, and why it was excluded from the "
            "proof card."
        ),
    }


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_GET(self) -> None:
        route = urlparse(self.path)
        query = parse_qs(route.query)
        try:
            if route.path == "/":
                self._html(PAGE.read_bytes())
            elif route.path == "/jobs":
                self._json(gallery())
            elif route.path == "/context":
                self._json(context(_job_of(query)))
            elif route.path == "/run":
                self._stream(query)
            else:
                self.send_error(404)
        except KeyError as exc:
            self.send_error(404, f"unknown {exc}")

    def do_POST(self) -> None:
        route = urlparse(self.path)
        if route.path != "/answer":
            self.send_error(404)
            return
        query = parse_qs(route.query)
        session = (query.get("session") or [""])[0]
        decision = (query.get("decision") or [""])[0]
        if decision not in DECISIONS:
            # Only the two a person can give. `no-response` is what happens when
            # they give none, and a channel failure is not theirs to declare.
            self.send_error(400, "decision must be approved or denied")
            return
        with _LOCK:
            port = _SESSIONS.get(session)
        if port is None:
            self.send_error(404, "no run is waiting on that session")
            return
        self._json({"accepted": port.answer(decision), "decision": decision})

    def _html(self, body: bytes) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        # Read fresh on every request so an edit shows up on reload. A cached
        # console silently demonstrates the previous version of itself.
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, payload: object) -> None:
        body = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _stream(self, query: dict[str, list[str]]) -> None:
        job = _job_of(query)
        delay = min(_float(query.get("delay"), DEFAULT_DELAY), MAX_DELAY)
        arms = _arms_of(query)

        doing = work.by_workload(job.workload)
        situation = scenarios.by_key(job.situation)
        session = uuid.uuid4().hex
        port: LiveApprovalPort | None = None
        if scenarios.is_interactive(situation, doing) and scenarios.GOVERNED in arms:
            # The contract's own window, not one chosen to suit a demonstration.
            window = compose.contract(job.workload).approval_timeout_seconds or 120
            port = LiveApprovalPort(timeout_seconds=window)
            with _LOCK:
                _SESSIONS[session] = port

        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self.end_headers()
        try:
            for payload in stream.play(
                job,
                RUNS,
                case_id=job.case_id,
                delay=delay,
                approval=port,
                session=session,
                arms=arms,
            ):
                self.wfile.write(stream.frame(payload))
                self.wfile.flush()
        except ConnectionError:
            # The viewer navigated away mid-run. Windows aborts the socket
            # (`ConnectionAbortedError`) where POSIX breaks the pipe, so this
            # catches the base class rather than guessing which. Release anything
            # waiting on them rather than hold the run for the contract's whole
            # window; the run finishes and seals regardless, which is what makes
            # the log complete whether or not anyone was watching.
            if port is not None:
                port.abandon()
        finally:
            with _LOCK:
                _SESSIONS.pop(session, None)
        self.close_connection = True

    def log_message(self, fmt: str, *args: object) -> None:
        if "/run?" in str(args[0] if args else ""):
            sys.stderr.write(f"  {args[0]}\n")


def _float(values: list[str] | None, fallback: float) -> float:
    try:
        return float((values or [""])[0])
    except ValueError:
        return fallback


def _job_of(query: dict[str, list[str]]) -> jobs.Job:
    """A job from the gallery, or `KeyError`. Never an arbitrary string.

    The only value any route reads from a request. A job carries its own task, so
    the case is not something a caller gets to choose.
    """
    return jobs.by_key((query.get("job") or [jobs.JOBS[0].key])[0])


def _arms_of(query: dict[str, list[str]]) -> tuple[str, ...]:
    """Governed alone, or governed beside the same run with nothing governing it."""
    if (query.get("compare") or ["1"])[0] == "1":
        return (scenarios.GOVERNED, scenarios.BASELINE)
    return (scenarios.GOVERNED,)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-open", action="store_true")
    args = parser.parse_args()

    RUNS.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    url = f"http://127.0.0.1:{args.port}"
    print(f"OutcomeFuse console on {url}")
    print(f"{len(jobs.JOBS)} jobs over {len(work.WORK)} frozen workloads, one mechanism each.")
    print(f"Sealed logs land in {RUNS}. Ctrl-C to stop.\n")
    if not args.no_open:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
