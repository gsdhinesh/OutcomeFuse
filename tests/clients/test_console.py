"""The interactive console, under test.

Two layers, tested differently.

**The gallery** is twelve jobs, each a real task that meets one mechanism. Every
card makes a claim — what OutcomeFuse does, what happens without it, whether the
arms should differ — and every claim is checked by running the job. A card whose
run stopped agreeing with it would be a brochure.

**The matrix** behind it is every situation against every kind of work. The
console shows twelve points of it; these sweep all of it, because that is how the
`code-triage` approval gap was found and is the only thing that keeps it found.

A live view has one way to be dangerous: showing something the record does not
contain. The stream must be a **subset of the sealed log, in order**, and a
watcher that raises must not break the run it is watching.

No browser and no server are started here; the streaming layer is driven
directly, which is the part that could lie.
"""

from __future__ import annotations

import dataclasses
import json
import threading
import time

import pytest
from console import delta, jobs, scenarios, stream
from console.approval import LiveApprovalPort
from features import compose
from features import work as work_module

from outcomefuse.core.record import open_store

WORKLOADS = [w.workload for w in work_module.WORK]


def _play(key: str, tmp_path, **kwargs):
    """One job, governed arm only, which is what most of these are about."""
    job = jobs.by_key(key)
    frames = list(stream.play(job, tmp_path, case_id=job.case_id, delay=0, **kwargs))
    assert frames[0]["type"] == "start"
    last = frames[-1]
    assert last["type"] == "done", last
    events = [f["event"] for f in frames if f["type"] == "event"]
    return events, last["summaries"][0]


def _both(key: str, tmp_path, **kwargs):
    """Both arms at once, and the comparison the stream derived from them."""
    job = jobs.by_key(key)
    frames = list(
        stream.play(
            job,
            tmp_path,
            case_id=job.case_id,
            delay=0,
            arms=(scenarios.GOVERNED, scenarios.BASELINE),
            **kwargs,
        )
    )
    last = frames[-1]
    assert last["type"] == "done", last
    return frames, {s["arm"]: s for s in last["summaries"]}, last


def _run(situation_key: str, workload: str, tmp_path, arm=scenarios.GOVERNED):
    doing = work_module.by_workload(workload)
    return scenarios.run(
        scenarios.by_key(situation_key),
        doing,
        arm=arm,
        runs_dir=tmp_path,
        case_id=compose.cases(workload)[0].case_id,
    )


class TestTheGalleryIsTwelveDifferentThings:
    """One card, one job, one mechanism. Not one job shown nine ways."""

    def test_each_job_shows_a_mechanism_no_other_job_shows(self) -> None:
        # Two cards on the same mechanism have to be doing something different
        # with it, or one of them is padding. The approval gate is the one that
        # repeats, deliberately: twice where it fires, once where it cannot.
        seen: dict[str, list[str]] = {}
        for job in jobs.JOBS:
            seen.setdefault(job.situation, []).append(job.key)
        assert seen["acts"] == ["message-the-planner", "write-to-the-table", "nobody-is-asked"]
        assert seen["happy"] == ["cannot-be-answered", "ordinary-run"]
        for key, shown in seen.items():
            if key not in {"acts", "happy"}:
                assert len(shown) == 1, key

    def test_every_situation_reaches_the_gallery(self) -> None:
        # A mechanism nobody can see demonstrated is a mechanism nobody believes.
        offered = {job.situation for job in jobs.JOBS}
        assert offered == {s.key for s in scenarios.SITUATIONS}

    def test_every_kind_of_work_reaches_the_gallery(self) -> None:
        used = {job.workload for job in jobs.JOBS}
        assert used == set(WORKLOADS)

    def test_no_two_jobs_are_the_same_task(self) -> None:
        pairs = [(job.workload, job.case_id) for job in jobs.JOBS]
        assert len(set(pairs)) == len(pairs)
        titles = [job.title for job in jobs.JOBS]
        assert len(set(titles)) == len(titles)

    def test_every_card_answers_the_questions_it_exists_to_answer(self) -> None:
        for job in jobs.JOBS:
            assert len(job.title) >= 20, job.key
            assert len(job.does) > 40, job.key
            assert len(job.without) > 20, job.key
            assert len(job.watch) > 40, job.key
            assert job.feature, job.key
            assert job.group in jobs.GROUPS, job.key

    def test_every_group_has_at_least_one_card(self) -> None:
        assert {job.group for job in jobs.JOBS} == set(jobs.GROUPS)

    def test_every_job_names_a_real_situation_and_a_real_case(self) -> None:
        for job in jobs.JOBS:
            scenarios.by_key(job.situation)
            known = {c.case_id for c in compose.cases(job.workload)}
            assert job.case_id in known, job.key

    def test_a_job_only_runs_a_situation_its_work_can_honour(self) -> None:
        for job in jobs.JOBS:
            doing = work_module.by_workload(job.workload)
            assert scenarios.by_key(job.situation).applies(doing), job.key

    def test_an_unknown_key_is_refused(self) -> None:
        with pytest.raises(KeyError):
            jobs.by_key("no-such-job")

    def test_a_job_owns_its_task_outright(self) -> None:
        # One card is one job is one task. The case is not a request parameter
        # and there is no picker, so a caller cannot point a card's claim at a
        # task the card was never written about.
        import inspect

        from console import server

        assert not hasattr(jobs, "case_of")
        assert not hasattr(server, "cases")
        source = inspect.getsource(server)
        assert 'query.get("case")' not in source
        assert list(inspect.signature(server.context).parameters) == ["job"]


class TestEveryCardsClaimIsTrue:
    """Each card is a promise about what the run does. These check the runs."""

    @pytest.mark.parametrize("key", [j.key for j in jobs.JOBS])
    def test_the_job_runs_and_seals(self, key, tmp_path) -> None:
        events, summary = _play(key, tmp_path)
        assert events, key
        assert summary["run_id"] and summary["seal"]
        assert summary["verified"] is True
        assert summary["terminal"], "every run must say why it ended"

    @pytest.mark.parametrize(
        ("key", "terminal"),
        [
            # No viewer in a test, so the approval question reaches nobody and the
            # governed arm fail-closes rather than treating silence as consent.
            ("message-the-planner", "fail-closed"),
            ("write-to-the-table", "fail-closed"),
            ("nobody-is-asked", "stop-sufficient"),
            ("same-file-again", "halt-no-progress"),
            ("fetch-keeps-failing", "stop-sufficient"),
            ("order-after-order", "halt-exhausted"),
            ("withdrawn-policy", "stop-sufficient"),
            ("figure-never-right", "returned-partial"),
            ("send-it-to-a-buyer", "referred-human"),
            ("asks-for-git-blame", "fail-closed"),
            ("cannot-be-answered", "fail-closed"),
            ("ordinary-run", "stop-sufficient"),
        ],
    )
    def test_the_card_and_the_ending_agree(self, key, terminal, tmp_path) -> None:
        _events, summary = _play(key, tmp_path)
        assert summary["terminal"] == terminal

    @pytest.mark.parametrize("key", [j.key for j in jobs.JOBS])
    def test_a_card_promising_agreement_gets_it(self, key, tmp_path) -> None:
        # `expect` is a claim about the two arms. Empty means "they agree", and a
        # job quietly starting to differ would make the card a lie.
        job = jobs.by_key(key)
        if job.expect or scenarios.is_interactive(
            scenarios.by_key(job.situation), work_module.by_workload(job.workload)
        ):
            pytest.skip("this card claims a difference, or waits on a person")
        _frames, _by_arm, last = _both(key, tmp_path)
        assert last["verdict"]["material"] == [], key

    @pytest.mark.parametrize("key", [j.key for j in jobs.JOBS])
    def test_a_card_promising_a_difference_gets_one(self, key, tmp_path) -> None:
        job = jobs.by_key(key)
        if not job.expect:
            pytest.skip("this card claims the arms agree")
        _frames, _by_arm, last = _both(key, tmp_path)
        assert last["verdict"]["material"] or last["crashed"], key

    def test_only_the_governed_arm_withholds_the_message(self, tmp_path) -> None:
        _frames, by_arm, last = _both("message-the-planner", tmp_path)
        assert by_arm["baseline"]["side_effects"]
        assert by_arm["governed"]["side_effects"] == []
        assert by_arm["governed"]["terminal"] == "fail-closed"
        assert "only the ungoverned arm acted on the world" in last["verdict"]["material"]

    def test_and_the_ungated_card_says_nobody_is_asked_because_nobody_is(
        self, tmp_path
    ) -> None:
        # Same mechanism, same agent, opposite result, and the card says so.
        _frames, by_arm, last = _both("nobody-is-asked", tmp_path)
        assert by_arm["governed"]["side_effects"]
        assert by_arm["baseline"]["side_effects"]
        assert last["verdict"]["material"] == []
        assert "**Nothing.**" in jobs.by_key("nobody-is-asked").does

    def test_the_governor_can_be_worse_and_the_card_says_so(self, tmp_path) -> None:
        _frames, by_arm, last = _both("asks-for-git-blame", tmp_path)
        assert by_arm["baseline"]["quality"] == "pass"
        assert by_arm["governed"]["terminal"] == "fail-closed"
        assert any("gate pass -> not-evaluated" in d for d in last["verdict"]["material"])
        assert "strictly worse" in jobs.by_key("asks-for-git-blame").watch

    def test_the_ungoverned_arm_raises_where_the_governed_one_refuses(
        self, tmp_path
    ) -> None:
        # The unanswerable case. With a governor an unevaluable gate is a recorded,
        # sealed decision; without one it is an unhandled exception and there is no
        # log at all. The stream must report the surviving arm, not lose both.
        frames, by_arm, last = _both("cannot-be-answered", tmp_path)
        assert set(by_arm) == {"governed"}
        assert by_arm["governed"]["terminal"] == "fail-closed"
        assert by_arm["governed"]["verified"] is True
        assert [c["arm"] for c in last["crashed"]] == ["baseline"]
        assert "GateUnavailable" in last["crashed"][0]["error"]
        assert last["verdict"]["compared"] is False
        assert any(f["type"] == "event" for f in frames)

    def test_a_run_with_no_surviving_arm_is_an_error_not_a_verdict(self, tmp_path) -> None:
        job = jobs.by_key("cannot-be-answered")
        frames = list(
            stream.play(
                job,
                tmp_path,
                case_id=job.case_id,
                delay=0,
                arms=(scenarios.BASELINE,),
            )
        )
        assert frames[-1]["type"] == "error"
        assert "GateUnavailable" in frames[-1]["message"]


class TestTheMatrixBehindIt:
    """Every situation against every kind of work. Where the gap was found."""

    @pytest.mark.parametrize("workload", WORKLOADS)
    @pytest.mark.parametrize("key", [s.key for s in scenarios.SITUATIONS])
    def test_it_runs_and_seals(self, key, workload, tmp_path) -> None:
        doing = work_module.by_workload(workload)
        if not scenarios.by_key(key).applies(doing):
            pytest.skip(f"{key} does not apply to {workload}")
        run = _run(key, workload, tmp_path)
        assert run.verified is True
        assert run.terminated, f"{workload}/{key}"

    @pytest.mark.parametrize("workload", WORKLOADS)
    @pytest.mark.parametrize(
        ("key", "terminal"),
        [
            ("happy", "stop-sufficient"),
            ("partial", "returned-partial"),
            ("refer", "referred-human"),
            ("stall", "halt-no-progress"),
            ("exhaustion", "halt-exhausted"),
            ("unknown-tool", "fail-closed"),
        ],
    )
    def test_a_mechanism_ends_the_same_way_on_every_work(
        self, key, terminal, workload, tmp_path
    ) -> None:
        assert _run(key, workload, tmp_path).terminated == terminal

    @pytest.mark.parametrize("workload", WORKLOADS)
    def test_every_work_can_be_done_correctly(self, workload, tmp_path) -> None:
        # If the well-behaved agent could not pass a gate, every other situation
        # on that work would be measuring the agent rather than the governor.
        run = _run("happy", workload, tmp_path)
        assert run.quality_state == "pass", workload

    @pytest.mark.parametrize("workload", WORKLOADS)
    @pytest.mark.parametrize("key", [s.key for s in scenarios.SITUATIONS])
    def test_both_arms_are_handed_the_same_agent_and_contract(
        self, key, workload, tmp_path, monkeypatch
    ) -> None:
        """The property every number in the verdict panel rests on.

        `scenarios.run` builds the turns before it branches on the arm, so both
        get the same ones. If they ever diverged the comparison would be between
        two different agents and every figure would be meaningless — and nothing
        else here would notice, because both runs would still seal and verify.
        """
        doing = work_module.by_workload(workload)
        situation = scenarios.by_key(key)
        if not situation.applies(doing):
            pytest.skip(f"{key} does not apply to {workload}")

        handed: dict[str, tuple] = {}

        def spy(arm, real):
            def wrapped(subject, *, turns, spec=None, **kw):
                handed[arm] = (turns, spec)
                return real(subject, turns=turns, spec=spec, **kw)

            return wrapped

        monkeypatch.setattr(compose, "governed", spy("governed", compose.governed))
        monkeypatch.setattr(compose, "ungoverned", spy("baseline", compose.ungoverned))
        for arm in (scenarios.GOVERNED, scenarios.BASELINE):
            scenarios.run(
                situation,
                doing,
                arm=arm,
                runs_dir=tmp_path,
                case_id=compose.cases(workload)[0].case_id,
                token=arm,
            )

        governed_turns, governed_spec = handed["governed"]
        baseline_turns, baseline_spec = handed["baseline"]
        assert governed_turns == baseline_turns, f"{workload}/{key}"
        assert governed_spec.digest().sha256 == baseline_spec.digest().sha256

    @pytest.mark.parametrize("workload", ["supply-chain", "data-sql"])
    def test_a_gate_that_fires_fail_closes_with_nobody_listening(
        self, workload, tmp_path
    ) -> None:
        run = _run("acts", workload, tmp_path)
        assert run.terminated == "fail-closed"
        assert list(run.side_effects) == []

    def test_a_gate_that_cannot_fire_lets_the_tool_run(self, tmp_path) -> None:
        run = _run("acts", "code-triage", tmp_path)
        assert run.terminated == "stop-sufficient"
        assert "run_tests" in run.invoked

    def test_a_situation_carries_no_wording_of_its_own(self) -> None:
        # One source of truth per card. A headline on the situation could disagree
        # with the job's, and the gallery would show one while the run showed the
        # other.
        fields = {f.name for f in dataclasses.fields(scenarios.Situation)}
        assert fields.isdisjoint({"title", "situation", "without", "watch", "group"})


class TestWhichClausesCanActuallyFire:
    """The finding the matrix produced, pinned so it cannot drift.

    `ToolGovernor.requires_approval` matches a condition only when it names a
    tool **and** its `when` is `always`. Every other form loads from the contract
    and is never evaluated. Two workloads really stop for a person, one declares
    a clause that cannot fire over a tool that acts on the world, and one
    declares nothing — correctly.
    """

    @pytest.mark.parametrize(
        ("workload", "fires"),
        [
            ("supply-chain", True),
            ("data-sql", True),
            ("code-triage", False),
            ("doc-research", False),
        ],
    )
    def test_the_work_knows_whether_its_gate_can_fire(self, workload, fires) -> None:
        from outcomefuse.ports import ToolCall
        from outcomefuse.runtime import ToolGovernor

        doing = work_module.by_workload(workload)
        assert doing.gate_fires is fires
        spec = compose.contract(workload)
        governor = ToolGovernor(spec)
        gated = [
            t.name
            for t in spec.tools
            if governor.requires_approval(ToolCall(tool=t.name, arguments={}, step_id="s"))
        ]
        assert bool(gated) is fires
        if fires:
            assert gated == [doing.side_effecting]

    def test_a_side_effecting_tool_is_left_entirely_ungated(self) -> None:
        from outcomefuse.ports import ToolCall
        from outcomefuse.runtime import ToolGovernor

        spec = compose.contract("code-triage")
        assert [t.name for t in spec.tools if t.side_effecting] == ["run_tests"]
        assert [c.when for c in spec.human_approval_conditions] == ["call_index_exceeds"]
        governor = ToolGovernor(spec)
        call = ToolCall(tool="run_tests", arguments={}, step_id="s")
        assert governor.requires_approval(call) is None

    def test_the_governor_never_reads_a_criterion_scoped_clause(self) -> None:
        from outcomefuse.ports import ToolCall
        from outcomefuse.runtime import ToolGovernor

        spec = compose.contract("supply-chain")
        assert [c for c in spec.human_approval_conditions if c.criterion]
        governor = ToolGovernor(spec)
        for tool in ("order_lookup", "shipment_trace", "supplier_policy_lookup"):
            call = ToolCall(tool=tool, arguments={}, step_id="s")
            assert governor.requires_approval(call) is None

    def test_the_work_with_no_side_effect_declares_no_approval_at_all(self) -> None:
        # The one absence that is right rather than a gap.
        spec = compose.contract("doc-research")
        assert [t.name for t in spec.tools if t.side_effecting] == []
        assert spec.human_approval_conditions == ()
        assert work_module.by_workload("doc-research").side_effecting is None


class TestTheAgents:
    @pytest.mark.parametrize("workload", WORKLOADS)
    def test_the_budget_agent_never_repeats_itself(self, workload) -> None:
        # Its card says every call is fresh and the cache cannot absorb any of
        # them. Repeat one and the run becomes a stall wearing a ceiling's card.
        doing = work_module.by_workload(workload)
        subject = compose.cases(workload)[0]
        turns = work_module.burns_turns(doing, {}, subject)
        made = [(c.tool, tuple(sorted(c.arguments.items()))) for turn in turns for c in turn]
        assert len(made) == 12
        assert len(set(made)) == 12, workload

    @pytest.mark.parametrize("workload", WORKLOADS)
    def test_the_stalling_agent_makes_exactly_one_distinct_call(self, workload) -> None:
        doing = work_module.by_workload(workload)
        subject = compose.cases(workload)[0]
        made = [c.arguments for turn in work_module.stalls(doing, {}, subject) for c in turn]
        assert len({tuple(sorted(a.items())) for a in made}) == 1, workload

    def test_the_invented_tool_is_plausible_and_does_not_exist(self) -> None:
        # `definitely_not_a_tool` demonstrated the governor and nothing else. A
        # model inventing a tool invents a believable one.
        for doing in work_module.WORK:
            declared = {t.name for t in compose.contract(doing.workload).tools}
            assert doing.invented not in declared, doing.workload
        assert len({w.invented for w in work_module.WORK}) == len(work_module.WORK)

    def test_no_two_kinds_of_work_share_a_tool(self) -> None:
        for doing in work_module.WORK:
            mine = {t.name for t in compose.contract(doing.workload).tools}
            theirs = {
                t.name
                for other in work_module.WORK
                if other is not doing
                for t in compose.contract(other.workload).tools
            }
            assert not (mine & theirs), doing.workload


class TestTheStreamCannotGetAheadOfTheLog:
    def test_it_is_the_sealed_log_in_order_and_nothing_else(self, tmp_path) -> None:
        events, summary = _play("withdrawn-policy", tmp_path)
        with open_store(tmp_path / f"{summary['run_id']}.db", writer=False) as store:
            recorded = store.events(summary["run_id"])
        # The manifest at seq 0 is included: `open_run` appends it through the
        # same override, so the viewer sees the run open rather than joining late.
        streamed = [(e["seq"], e["kind"]) for e in events]
        assert streamed == [(e.seq, e.kind) for e in recorded]
        assert streamed[0][1] == "run-manifest"
        assert streamed[-1][1] == "run-closed"

    def test_no_frame_invents_a_field(self, tmp_path) -> None:
        events, summary = _play("ordinary-run", tmp_path)
        with open_store(tmp_path / f"{summary['run_id']}.db", writer=False) as store:
            by_seq = {e.seq: e for e in store.events(summary["run_id"])}
        for frame in events:
            recorded = by_seq[frame["seq"]]
            assert frame["policy_action"] == recorded.policy_action
            assert frame["decision_reason"] == recorded.decision_reason
            assert frame["terminal_reason"] == recorded.terminal_reason
            assert frame["tokens"] == recorded.tokens_consumed

    def test_the_start_frame_names_the_job_it_is_about(self, tmp_path) -> None:
        job = jobs.by_key("ordinary-run")
        frames = list(stream.play(job, tmp_path, case_id=job.case_id, delay=0))
        assert frames[0]["job"] == "ordinary-run"
        assert frames[0]["workload"] == "doc-research"
        assert frames[0]["title"] == job.title
        assert frames[0]["interactive"] is False


class TestTheWatcherGovernsNothing:
    def test_a_sink_that_raises_does_not_break_the_run(self, tmp_path) -> None:
        def hostile(_event):
            raise RuntimeError("the viewer exploded")

        subject = compose.case("sc-c-001", "supply-chain")
        key = compose.key_for(subject.case_id, "supply-chain")
        doing = work_module.by_workload("supply-chain")
        run = compose.governed(
            subject,
            turns=work_module.correct(doing, key, subject),
            runs_dir=tmp_path,
            tag="hostile",
            sink=hostile,
        )
        assert run.quality_state == "pass"
        assert run.terminated == "stop-sufficient"
        assert run.verified

    def test_and_the_failure_is_kept_rather_than_swallowed(self, tmp_path) -> None:
        seen: list[str] = []
        store = compose.TeeStore(tmp_path / "x.db", sink=lambda _e: seen.append("ok"))
        assert store.sink_errors == []
        store.close()


class TestBothArmsAtOnce:
    def test_both_arms_stream_and_seal(self, tmp_path) -> None:
        frames, by_arm, _last = _both("ordinary-run", tmp_path)
        assert set(by_arm) == {"governed", "baseline"}
        assert all(s["verified"] for s in by_arm.values())
        assert by_arm["governed"]["run_id"] != by_arm["baseline"]["run_id"]
        # Every frame says which arm it came from, or the two trees would merge.
        assert all(f["arm"] in by_arm for f in frames if f["type"] == "event")

    def test_the_ordinary_run_changes_nothing_and_says_so(self, tmp_path) -> None:
        # The honest null result. A comparison that only ever found differences
        # would not be a comparison.
        _frames, by_arm, last = _both("ordinary-run", tmp_path)
        assert last["verdict"]["compared"] is True
        assert last["verdict"]["material"] == []
        assert by_arm["governed"]["quality"] == by_arm["baseline"]["quality"] == "pass"
        # It still differs in what was written down, which is not the same thing.
        assert last["verdict"]["recorded"]

    def test_one_arm_alone_reports_no_comparison(self, tmp_path) -> None:
        _events, summary = _play("ordinary-run", tmp_path)
        assert summary["arm"] == "governed"
        assert delta.verdict([summary])["compared"] is False


class TestTheComparisonLogic:
    """Shared by the page and the CLI, so it is tested once for both."""

    def _summary(self, **over):
        base = {
            "arm": "governed", "run_id": "r", "terminal": None, "quality": "pass",
            "seal": "x", "verified": True, "escalations": 0, "tools_invoked": ["a"],
            "side_effects": [], "turns": 1, "tokens": 100, "models": [],
        }
        return {**base, **over}

    def test_identical_runs_show_nothing(self) -> None:
        one = self._summary()
        assert delta.material(one, dict(one, arm="baseline")) == []

    def test_a_side_effect_outranks_everything_else(self) -> None:
        on = self._summary(tokens=999, quality="fail")
        off = self._summary(arm="baseline", side_effects=["sent"])
        assert delta.material(on, off)[0] == "only the ungoverned arm acted on the world"

    def test_a_terminal_reason_is_recorded_not_material(self) -> None:
        on = self._summary(terminal="stop-sufficient")
        off = self._summary(arm="baseline", terminal=None)
        assert delta.material(on, off) == []
        assert delta.recorded(on, off)

    def test_a_token_delta_carries_its_direction(self) -> None:
        on = self._summary(tokens=150)
        off = self._summary(arm="baseline", tokens=100)
        assert "tokens 100 -> 150 (+50%)" in delta.material(on, off)


class TestRunningTheSameJobTwice:
    """Clicking a card twice used to collide on one database file.

    Both runs took the id `<case>-<workload>-<situation>`, so both wrote to one
    path. `_store` unlinks before opening, and Windows refuses to unlink a file
    another thread still holds — so the second run died with `WinError 32` and
    the lane showed "this arm threw". Every play now gets its own id.
    """

    def test_two_plays_of_one_job_get_different_ids_and_both_seal(self, tmp_path) -> None:
        _events, first = _play("ordinary-run", tmp_path)
        _events, second = _play("ordinary-run", tmp_path)
        assert first["run_id"] != second["run_id"]
        assert first["seal"] != second["seal"]
        assert first["verified"] and second["verified"]

    def test_the_id_still_says_what_the_run_was(self, tmp_path) -> None:
        # Unique, but not anonymous: the case, the work and the mechanism stay
        # legible in the id the verdict panel shows.
        job = jobs.by_key("same-file-again")
        _events, summary = _play(job.key, tmp_path)
        assert summary["run_id"].startswith(f"{job.case_id}-{job.workload}-{job.situation}")

    def test_both_arms_of_one_play_share_the_token(self, tmp_path) -> None:
        _frames, by_arm, _last = _both("ordinary-run", tmp_path)
        governed = by_arm["governed"]["run_id"]
        baseline = by_arm["baseline"]["run_id"]
        # The baseline is the governed id plus `-off`, so a pair is readable as a
        # pair rather than as two unrelated runs that happen to share a case.
        assert baseline == f"{governed}-off"

    def test_a_reused_id_says_what_went_wrong(self, tmp_path) -> None:
        # The bare mechanism, without the console. Refused in the composition
        # rather than left to the filesystem: Windows would raise WinError 32
        # and POSIX would silently delete the first run's log, so this is the
        # same failure on both.
        doing = work_module.by_workload("supply-chain")
        subject = compose.cases("supply-chain")[0]
        held, _path = compose._store(tmp_path, f"{subject.case_id}-open")
        try:
            with pytest.raises(RuntimeError, match="already in flight"):
                compose.governed(
                    subject,
                    turns=work_module.correct(
                        doing, compose.key_for(subject.case_id, "supply-chain"), subject
                    ),
                    runs_dir=tmp_path,
                    tag="open",
                )
        finally:
            held.close()
            compose._release(f"{subject.case_id}-open")

    def test_the_id_is_free_again_once_the_run_closes(self, tmp_path) -> None:
        # Or the second run of a one-shot caller, like the feature report, would
        # be refused for a run that had already finished.
        doing = work_module.by_workload("doc-research")
        subject = compose.cases("doc-research")[0]
        spec = compose.contract("doc-research")
        turns = work_module.correct(
            doing, compose.key_for(subject.case_id, "doc-research"), subject
        )
        for _ in range(2):
            run = compose.governed(
                subject, turns=turns, runs_dir=tmp_path, spec=spec, tag="twice"
            )
            assert run.verified
        assert compose._LIVE == set()

    def test_a_job_run_twice_in_a_row_never_reports_a_crashed_arm(self, tmp_path) -> None:
        # The symptom as the viewer met it: the second lane saying "this arm
        # threw" where the first had been fine.
        for _ in range(2):
            _frames, _by_arm, last = _both("same-file-again", tmp_path)
            assert last["crashed"] == []


class TestTheAnswerIsShown:
    """The tree shows the machinery. Something has to show whether it answered.

    Read back from the evidence sidecar, not kept from the run, for the same
    reason the events are: what a run meant to produce and what it durably
    produced are two different claims and only the second is evidence.
    """

    @pytest.mark.parametrize(
        "key", ["ordinary-run", "nobody-is-asked", "withdrawn-policy"]
    )
    def test_a_run_that_answers_carries_its_answer(self, key, tmp_path) -> None:
        _events, summary = _play(key, tmp_path)
        assert summary["answer"], key
        assert isinstance(summary["answer"], dict)

    def test_a_gated_run_nobody_authorised_has_no_answer(self, tmp_path) -> None:
        # It fail-closed at the gate, so it never handed anything over. Showing
        # an answer here would be showing one the run did not produce.
        _events, summary = _play("message-the-planner", tmp_path)
        assert summary["terminal"] == "fail-closed"
        assert summary["answer"] is None

    def test_a_run_that_never_answered_carries_none(self, tmp_path) -> None:
        # It died before handing anything over, so there is nothing to show and
        # nothing is invented to fill the space.
        _events, summary = _play("asks-for-git-blame", tmp_path)
        assert summary["terminal"] == "fail-closed"
        assert summary["answer"] is None

    def test_the_database_answer_is_internally_coherent(self, tmp_path) -> None:
        """The SQL has to be over the table the figure is about.

        `sql-is-read-only` checks the query is a SELECT. It does **not** check
        the query computes the number beside it, so the agent used to report a
        shipment count over `FROM orders` and pass.
        """
        job = jobs.by_key("write-to-the-table")
        run = scenarios.run(
            scenarios.by_key(job.situation),
            work_module.by_workload(job.workload),
            arm=scenarios.GOVERNED,
            runs_dir=tmp_path,
            case_id=job.case_id,
            approval="approved",
        )
        answer = run.deliverable
        subject = compose.case(job.case_id, job.workload).prompt.lower()
        assert "shipments" in subject
        assert answer["tables_used"] == ["shipments"]
        assert "shipments" in answer["sql"].lower()
        assert answer["sql"].lower().startswith("select")
        assert answer["result_value"] == compose.key_for(job.case_id, job.workload)[
            "result_value"
        ]

    @pytest.mark.parametrize(
        "case_id", [c.case_id for c in compose.cases("data-sql")]
    )
    def test_the_query_names_the_table_the_question_is_about(self, case_id) -> None:
        subject = compose.case(case_id, "data-sql")
        table = work_module._ds_subject(subject)
        read, write = work_module._DS_TABLES[table]
        assert table in read
        assert table in write
        assert read.lower().startswith("select")
        # The careless write has to be a write, or the approval card is staging
        # a danger that is not there.
        assert write.lower().startswith("update")

    def test_the_careless_write_touches_the_rows_being_counted(self, tmp_path) -> None:
        # Not an arbitrary statement. It tidies the very table the question is
        # about, so approving it changes the data the answer is computed over.
        job = jobs.by_key("write-to-the-table")
        port = LiveApprovalPort(timeout_seconds=10)
        asked: list[dict] = []
        for frame in stream.play(
            job, tmp_path, case_id=job.case_id, delay=0, approval=port, session="s"
        ):
            if frame["type"] == "approval":
                asked.append(frame["request"])
                threading.Timer(0.05, lambda: port.answer("denied")).start()
        sql = asked[0]["arguments"]["sql"]
        assert "shipments" in sql
        assert sql.lower().startswith("update")


    def test_the_plain_restatement_covers_what_the_contract_wants(self) -> None:
        """The frozen prompt cannot be reworded, so the console says it again.

        `asks` is the console's own words, shown beside the frozen text and
        never given to the agent. It has to cover every field the contract
        requires, or it is a paraphrase that quietly drops a requirement.
        """
        from console.server import context

        for job in jobs.JOBS:
            doing = work_module.by_workload(job.workload)
            fields = compose.contract(job.workload).deliverable.structure
            assert len(doing.asks) > 60, job.workload
            # One clause per required field, so nothing the contract wants is
            # missing from the plain-English version.
            assert doing.asks.count(",") >= len(fields) - 2, job.workload
            assert context(job)["asks"] == doing.asks

    def test_the_frozen_prompt_is_shown_verbatim(self) -> None:
        # The restatement sits beside the prompt, never instead of it. Showing a
        # paraphrase as though it were the task would make every run unreadable
        # against the frozen case.
        from console.server import context

        for job in jobs.JOBS:
            frozen = compose.case(job.case_id, job.workload).prompt
            assert context(job)["prompt"] == " ".join(frozen.split())


class TestTheTaskIsTheJobs:
    """A job names one frozen case and runs it. Nothing else is selectable."""

    def test_every_work_has_exactly_one_unanswerable_calibration_case(self) -> None:
        for workload in WORKLOADS:
            unanswerable = [
                c.case_id
                for c in compose.cases(workload)
                if c.expected_outcome != "answer"
            ]
            assert len(unanswerable) == 1, workload
        # And exactly one card is built on one, deliberately.
        built_on = [
            job.key
            for job in jobs.JOBS
            if compose.case(job.case_id, job.workload).expected_outcome != "answer"
        ]
        assert built_on == ["cannot-be-answered"]

    def test_the_other_eleven_jobs_run_answerable_tasks(self) -> None:
        # A card claiming a mechanism cannot rest on a case that fail-closes for
        # an unrelated reason, or the claim is untestable.
        for job in jobs.JOBS:
            if job.key == "cannot-be-answered":
                continue
            subject = compose.case(job.case_id, job.workload)
            assert subject.expected_outcome == "answer", job.key


class TestTheServerSurface:
    def test_the_gallery_payload_carries_what_the_page_draws(self) -> None:
        from console.server import gallery

        payload = gallery()
        assert payload["groups"] == list(jobs.GROUPS)
        assert len(payload["jobs"]) == len(jobs.JOBS)
        assert set(payload["jobs"][0]) == {
            "key", "group", "title", "does", "without", "feature", "watch", "expect",
            "authored", "interactive", "variant", "work", "workload", "case_id",
        }

    def test_only_a_gate_that_fires_offers_you_a_decision(self) -> None:
        from console.server import gallery

        live = [j["key"] for j in gallery()["jobs"] if j["interactive"]]
        assert live == ["message-the-planner", "write-to-the-table"]

    @pytest.mark.parametrize("key", [j.key for j in jobs.JOBS])
    def test_the_context_describes_that_job_s_actual_task(self, key) -> None:
        from console.server import context

        job = jobs.by_key(key)
        ctx = context(job)
        assert ctx["workload"] == job.workload
        assert ctx["case_id"] == job.case_id
        assert ctx["prompt"]
        assert len(ctx["mandatory"]) == 6
        # Tools that reach outside the dataset must be marked, or the approval
        # cards look arbitrary.
        marked = [t["name"] for t in ctx["tools"] if t["side_effecting"]]
        expected = work_module.by_workload(job.workload).side_effecting
        assert marked == ([expected] if expected else [])

    def test_two_jobs_on_the_same_work_still_describe_different_tasks(self) -> None:
        from console.server import context

        one = jobs.by_key("message-the-planner")
        two = jobs.by_key("order-after-order")
        assert one.workload == two.workload
        assert context(one)["prompt"] != context(two)["prompt"]

    def test_the_unanswerable_case_says_so_and_only_there(self) -> None:
        from console.server import context

        noted = [j.key for j in jobs.JOBS if context(j)["unanswerable_note"]]
        assert noted == ["cannot-be-answered"]

    def test_a_frame_is_terminated_so_the_reader_does_not_hang(self) -> None:
        assert stream.frame({"type": "start"}).endswith(b"\n\n")

    def test_only_a_person_s_two_answers_are_accepted(self) -> None:
        from console.server import DECISIONS

        # `no-response` is what happens when they give none, and a channel
        # failure is not theirs to declare. Neither may arrive over HTTP.
        assert DECISIONS == {"approved", "denied"}


class TestTheHumanAtTheGate:
    """The one port in this client that is not scripted."""

    def _answer_after(self, port: LiveApprovalPort, decision: str, seconds: float) -> None:
        threading.Timer(seconds, lambda: port.answer(decision)).start()

    def _live(self, key: str, tmp_path, port):
        job = jobs.by_key(key)
        return stream.play(
            job, tmp_path, case_id=job.case_id, delay=0, approval=port, session="s"
        )

    @pytest.mark.parametrize("key", ["message-the-planner", "write-to-the-table"])
    @pytest.mark.parametrize(
        ("decision", "tool_ran"), [("approved", True), ("denied", False)]
    )
    def test_the_answer_decides_whether_the_tool_runs(
        self, decision, tool_ran, key, tmp_path
    ) -> None:
        expected = work_module.by_workload(jobs.by_key(key).workload).side_effecting
        port = LiveApprovalPort(timeout_seconds=10)
        asked: list[dict] = []
        frames = []
        for frame in self._live(key, tmp_path, port):
            if frame["type"] == "approval":
                asked.append(frame["request"])
                self._answer_after(port, decision, 0.05)
            frames.append(frame)
        summary = frames[-1]["summaries"][0]
        assert len(asked) == 1
        assert asked[0]["tool"] == expected
        assert (expected in summary["tools_invoked"]) is tool_ran
        assert bool(summary["side_effects"]) is tool_ran
        assert summary["terminal"] == "stop-sufficient"

    @pytest.mark.parametrize("key", ["message-the-planner", "write-to-the-table"])
    def test_the_question_says_what_it_is_asking_to_do(self, key, tmp_path) -> None:
        """A gate that names a tool and withholds the call cannot be answered.

        Approving `notify_planner` without seeing the message is a signature on
        a blank page, so the request carries the arguments and the card shows
        them.
        """
        job = jobs.by_key(key)
        expected = work_module.by_workload(job.workload).side_effecting
        port = LiveApprovalPort(timeout_seconds=10)
        asked: list[dict] = []
        for frame in self._live(key, tmp_path, port):
            if frame["type"] == "approval":
                asked.append(frame["request"])
                self._answer_after(port, "denied", 0.05)
        assert len(asked) == 1
        request = asked[0]
        assert request["tool"] == expected
        assert request["arguments"], "the call must travel with the question"
        # The arguments shown are the ones the agent actually proposed.
        proposed = next(
            c
            for turn in work_module.acts_on_the_world(
                work_module.by_workload(job.workload),
                compose.key_for(job.case_id, job.workload),
                compose.case(job.case_id, job.workload),
            )
            if not isinstance(turn, str)
            for c in turn
            if c.tool == expected
        )
        assert request["arguments"] == proposed.arguments

    def test_the_question_carries_the_hash_the_log_will_record(self, tmp_path) -> None:
        # The arguments are deliberately not written to the log, so the hash is
        # what ties what you approved to what the record says happened.
        port = LiveApprovalPort(timeout_seconds=10)
        asked, events = [], []
        for frame in self._live("message-the-planner", tmp_path, port):
            if frame["type"] == "approval":
                asked.append(frame["request"])
                self._answer_after(port, "approved", 0.05)
            elif frame["type"] == "event":
                events.append(frame["event"])
        key = asked[0]["canonical_key"]
        assert len(key) == 64
        proposed = [
            e for e in events if e["kind"] == "decision-proposed" and e["tool"] == "notify_planner"
        ]
        assert proposed, "the gated call must appear in the log"
        assert key[:12] in proposed[0]["detail"]

    def test_the_message_names_the_disposition_it_is_about_to_assert(
        self, tmp_path
    ) -> None:
        # "please review" told the approver nothing. The danger of this tool is
        # that it hands a planner a disposition the gate has not checked, so the
        # message has to carry that disposition or there is nothing to weigh.
        job = jobs.by_key("message-the-planner")
        answer_key = compose.key_for(job.case_id, job.workload)
        port = LiveApprovalPort(timeout_seconds=10)
        asked: list[dict] = []
        for frame in self._live(job.key, tmp_path, port):
            if frame["type"] == "approval":
                asked.append(frame["request"])
                self._answer_after(port, "denied", 0.05)
        message = asked[0]["arguments"]["message"]
        po = compose.case(job.case_id, job.workload).prompt_context["po_id"]
        assert str(po) in message, "the planner must know which order"
        for field in ("exception_type", "root_cause_code", "recommended_action"):
            assert answer_key[field] in message, field
        assert "please review" not in message

    def test_the_arguments_are_not_written_to_the_log(self, tmp_path) -> None:
        # Tool arguments carry whatever the caller put in them and the record
        # spine is retention-governed (AD-19). The hash goes in the log; the
        # values go to the person deciding and no further.
        port = LiveApprovalPort(timeout_seconds=10)
        events, asked = [], []
        for frame in self._live("message-the-planner", tmp_path, port):
            if frame["type"] == "approval":
                asked.append(frame["request"])
                self._answer_after(port, "approved", 0.05)
            elif frame["type"] == "event":
                events.append(frame["event"])
        blob = json.dumps(events)
        assert "notify_planner" in blob
        assert asked[0]["arguments"]["message"] not in blob

    def test_answering_nothing_elapses_the_window(self, tmp_path) -> None:
        port = LiveApprovalPort(timeout_seconds=1)
        started = time.perf_counter()
        _events, summary = _play("message-the-planner", tmp_path, approval=port, session="s")
        # It really waited: the run cannot have finished before the window did.
        assert time.perf_counter() - started >= 1.0
        assert summary["terminal"] == "approval-timeout"
        assert summary["side_effects"] == []

    def test_with_nobody_listening_it_is_fail_closed_not_permitted(self, tmp_path) -> None:
        # FR89 ranks an unreachable channel above the gate itself; treating
        # silence as consent would be the worst possible default here.
        _events, summary = _play("message-the-planner", tmp_path)
        assert summary["terminal"] == "fail-closed"
        assert summary["side_effects"] == []

    def test_a_second_answer_is_refused_rather_than_queued(self) -> None:
        port = LiveApprovalPort(timeout_seconds=1)
        assert port.answer("approved") is True
        assert port.answer("denied") is False

    def test_abandoning_releases_the_run(self, tmp_path) -> None:
        port = LiveApprovalPort(timeout_seconds=60)
        frames = []
        for frame in self._live("message-the-planner", tmp_path, port):
            if frame["type"] == "approval":
                threading.Timer(0.05, port.abandon).start()
            frames.append(frame)
        # Released early rather than held for the whole window, and the ending is
        # the honest one: nobody answered.
        assert frames[-1]["summaries"][0]["terminal"] == "approval-timeout"

    def test_the_ungated_job_never_asks(self, tmp_path) -> None:
        # A live port wired to the job whose clause cannot fire. It must not be
        # asked, and the run must not pretend it was.
        port = LiveApprovalPort(timeout_seconds=5)
        asked = [f for f in self._live("nobody-is-asked", tmp_path, port)
                 if f["type"] == "approval"]
        assert asked == []
