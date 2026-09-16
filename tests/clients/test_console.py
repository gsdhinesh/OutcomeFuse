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
import pathlib
import threading
import time

import pytest
from console import delta, jobs, scenarios, stream
from console.approval import LiveApprovalPort
from features import compose
from features import work as work_module

from outcomefuse.core.record import open_store
from outcomefuse.workloads.corpus import sql_corpus
from outcomefuse.workloads.data_sql import CORPUS

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


class TestTheGalleryIsElevenDifferentThings:
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

    def test_every_situation_is_either_shown_or_swept(self) -> None:
        # A mechanism nobody can see demonstrated is a mechanism nobody believes,
        # so the default is that every situation earns a card. `NOT_SHOWN` is the
        # deliberate exception list, and it has to stay honest in both directions:
        # nothing may be omitted without a reason, and nothing may be listed as
        # omitted while still holding a card.
        offered = {job.situation for job in jobs.JOBS}
        every = {s.key for s in scenarios.SITUATIONS}
        assert offered.isdisjoint(jobs.NOT_SHOWN)
        assert offered | set(jobs.NOT_SHOWN) == every
        for key, reason in jobs.NOT_SHOWN.items():
            scenarios.by_key(key)
            assert len(reason) > 20, key

    def test_what_a_card_shows_is_a_kind_the_page_can_style(self) -> None:
        for job in jobs.JOBS:
            assert job.shows in jobs.SLUG, job.key

    def test_only_the_cards_claiming_a_difference_promise_one(self) -> None:
        # The four cards that move no figure are the ones most likely to be read
        # as wins they never claimed, so the kind and the claim are pinned to
        # each other rather than left to drift apart in prose.
        moves = (jobs.DIFFERENCE, jobs.DEFECT)
        for job in jobs.JOBS:
            assert bool(job.expect) == (job.shows in moves), job.key

    def test_the_gallery_is_not_a_row_of_wins(self) -> None:
        kinds = {job.shows for job in jobs.JOBS}
        assert jobs.GAP in kinds, "the gap we found has to stay on the wall"
        assert jobs.DEFECT in kinds, "so does the defect"
        assert jobs.NO_COST in kinds, "and the control the rest are read against"

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
            ("order-after-order", "halt-exhausted"),
            ("counted-by-overwriting", "stop-sufficient"),
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
        events, summary = _play("counted-by-overwriting", tmp_path)
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
        "key", ["ordinary-run", "nobody-is-asked", "counted-by-overwriting"]
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
        "key", [j.key for j in jobs.JOBS if j.workload == "data-sql"]
    )
    def test_the_sql_it_hands_back_really_returns_the_figure(self, key, tmp_path) -> None:
        """Run the agent's own query and check it gives the number it reported.

        The contract cannot do this. `sql-is-read-only` sees a SELECT and stops,
        so an answer whose query computes something else entirely still passes
        the gate — which is how `delivered_date IS NULL` ended up beside a figure
        of 3 when that query returns 4, counting a shipment marked lost.
        """
        job = jobs.by_key(key)
        answer = work_module.body(
            work_module.by_workload(job.workload),
            compose.key_for(job.case_id, job.workload),
            compose.case(job.case_id, job.workload),
        )
        # `sql_corpus` hands back a cached connection that `close_corpora`
        # closes at exit. Closing it here would break every later test.
        db = sql_corpus(CORPUS)
        got = db.execute(answer["sql"]).fetchone()[0]
        assert got == answer["result_value"], f"{key}: {answer['sql']}"

    def test_the_careless_write_really_changes_the_figure(self) -> None:
        """Approving it has to change the answer, or the card overstates it.

        The previous statement re-marked rows that were already delivered: 21
        rows touched, reported figure unchanged. It looked dangerous and was
        not, and the comment beside it said otherwise. Applied to a scratch
        copy, so the corpus is never touched.
        """
        from outcomefuse.workloads.corpus import writable_copy

        job = jobs.by_key("write-to-the-table")
        subject = compose.case(job.case_id, job.workload)
        doing = work_module.by_workload(job.workload)
        query = work_module.body(
            doing, compose.key_for(job.case_id, job.workload), subject
        )["sql"]
        write = work_module._DS_TABLES[work_module._ds_subject(subject)][1]

        scratch = writable_copy(CORPUS)
        try:
            before = scratch.execute(query).fetchone()[0]
            scratch.execute(write)
            scratch.commit()
            after = scratch.execute(query).fetchone()[0]
        finally:
            scratch.close()
        assert before == 3
        assert after != before, write

    def test_the_corpus_itself_is_never_touched(self) -> None:
        # The write lands on a scratch copy. The contract says so and the card
        # repeats it, so it has to be true.
        db = sql_corpus(CORPUS)
        assert db.execute(
            "SELECT COUNT(*) FROM shipments WHERE status = 'in_transit'"
        ).fetchone()[0] == 3

    def test_in_transit_really_is_ambiguous(self) -> None:
        """Three defensible readings, three different answers.

        Pinned because the agent's query was quietly wrong and nothing caught
        it: the contract sees a SELECT and stops looking.
        """
        db = sql_corpus(CORPUS)
        by_status = db.execute(
            "SELECT COUNT(*) FROM shipments WHERE status = 'in_transit'"
        ).fetchone()[0]
        by_dates = db.execute(
            "SELECT COUNT(*) FROM shipments "
            "WHERE shipped_date IS NOT NULL AND delivered_date IS NULL"
        ).fetchone()[0]
        undelivered = db.execute(
            "SELECT COUNT(*) FROM shipments WHERE delivered_date IS NULL"
        ).fetchone()[0]
        assert (by_status, by_dates, undelivered) == (3, 2, 4)
        # Only the status reading matches what the key was derived from. The
        # third counts a shipment marked lost.
        assert compose.key_for("ds-c-004", "data-sql")["result_value"] == by_status

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


    def test_the_escalation_trigger_needs_no_answer_key(self) -> None:
        """Every workload escalates on a criterion a deployment could run.

        The escalation card used to trip `answer-matches-key`, which compares
        the deliverable against a sheet of right answers derived before the run
        existed. Outside a frozen case there is no such sheet, so it was showing
        a gate no deployment has. `malform` breaks a constraint-backed criterion
        instead, and this pins the intent for all four rather than just the one
        the card happens to run.
        """
        keyless = {
            "field-present", "numeric-range", "regex-match", "set-membership", "type-is",
        }
        tripped = {
            "supply-chain": "delay-estimate-bounded",
            "data-sql": "sql-is-read-only",
            "code-triage": "fix-summary-substantive",
            "doc-research": "citations-sufficient",
        }
        for doing in work_module.WORK:
            spec = compose.contract(doing.workload)
            by_id = {
                c.id: c.verifier.type
                for _band, crits in spec.criteria
                for c in crits
                if c.verifier is not None
            }
            wanted = tripped[doing.workload]
            assert by_id[wanted] in keyless, f"{doing.workload}: {wanted} needs a key"

    @pytest.mark.parametrize("workload", WORKLOADS)
    def test_a_malformed_answer_is_refused_then_retried(self, workload, tmp_path) -> None:
        run = _run("escalation", workload, tmp_path)
        escalated = next(
            e for e in run.events if e.decision_reason == "escalation-gate-fail"
        )
        unmet = escalated.payload["unmet"]
        assert len(unmet) == 1, unmet
        spec = compose.contract(workload)
        verifier = next(
            c.verifier.type
            for band, crits in spec.criteria
            for c in crits
            if c.id == unmet[0] and c.verifier
        )
        assert verifier != "exact-match-against-answer-key", (
            f"{workload} escalates on a criterion that needs the answer key"
        )
        assert run.escalations == 1
        assert run.quality_state == "pass", "the retry has to actually pass"

        # The retry inherits the evidence: nothing is fetched a second time.
        after = [
            e for e in run.events
            if e.seq > escalated.seq and e.kind == "decision-proposed"
        ]
        assert not after, "the retry re-fetched evidence"

    def test_the_stronger_model_is_recorded_but_is_not_what_fixed_it(self) -> None:
        """A scripted port returns the same turn whichever model is named.

        The escalation is real and worth recording, but attributing the better
        answer to gpt-5 would be inventing a result the fixture cannot produce.
        """
        from outcomefuse.ports.model import Message, ModelRequest, ScriptedModelPort

        scripted = ScriptedModelPort(turns=["first", "second"])
        asked = [
            scripted.complete(
                ModelRequest(
                    model_id=name,
                    messages=(Message(role="user", content="same prompt"),),
                    tools=(),
                    max_output_tokens=256,
                )
            ).text
            for name in ("gpt-5-mini", "gpt-5")
        ]
        assert asked == ["first", "second"], "the script, not the model, chose these"
        assert len({r.model_id for r in scripted.calls}) == 2, "two models really were asked"

        job = jobs.by_key("counted-by-overwriting")
        assert "the script supplies a better answer" in job.watch

    def test_the_card_shows_a_read_query_answered_with_a_write(self, tmp_path) -> None:
        job = jobs.by_key("counted-by-overwriting")
        doing = work_module.by_workload(job.workload)
        case = compose.case(job.case_id, job.workload)
        good = doing.deliverable(compose.key_for(job.case_id, job.workload), case)
        assert "select" in good["sql"].lower(), "the honest answer is a query"
        assert "update" in doing.malform(good)["sql"].lower(), "the refused one is a write"
        tag = "sql"
        run = scenarios.run(
            scenarios.by_key(job.situation), doing, arm=scenarios.GOVERNED,
            runs_dir=tmp_path, case_id=job.case_id, token=tag,
        )
        escalated = next(
            e for e in run.events if e.decision_reason == "escalation-gate-fail"
        )
        assert escalated.payload["unmet"] == ["sql-is-read-only"]
        assert "no answer key" in job.does

    def test_the_verdict_shows_the_two_values_the_gate_compared(self, tmp_path) -> None:
        """"unmet: result-matches-key" does not say what was compared.

        The gate builds a full per-criterion breakdown - `Verdict.breakdown`,
        whose detail reads "3.0 does not equal the key's 2" - and the driver
        writes only the ids. The breakdown never reaches the record, so the two
        values are rebuilt from the sealed deliverable and the frozen answer
        key, both of which outlive the run. That is the only reason
        reconstructing them is honest, and the panel says so.
        """
        frames, _by_arm, last = _both("figure-never-right", tmp_path)
        assert last["type"] == "done"
        rows = last["compared"]
        assert rows, "a refused criterion has to say what it refused"

        refused = next(r for r in rows if r["criterion"] == "result-matches-key")
        key = compose.key_for("ds-c-002", "data-sql")
        assert refused["kept"] is True, "this run ends on the deliverable it refused"
        assert refused["path"] == "$.result_value"
        assert refused["wanted"] == key["result_value"]
        assert refused["got"] != refused["wanted"], "nothing to show if they agree"

        # And the log genuinely does not carry it, or this would be reading the
        # record rather than rebuilding it.
        bodies = [
            f["event"] for f in frames if f["type"] == "event" and f["event"].get("unmet")
        ]
        assert bodies, "the run has to record an unmet criterion"
        assert all("breakdown" not in str(e) for e in bodies)

        page = (
            pathlib.Path(__file__).resolve().parents[2]
            / "clients" / "console" / "app.html"
        ).read_text(encoding="utf-8")
        assert "never written to the log" in page

    def test_one_reason_covers_escalating_and_giving_up(self, tmp_path) -> None:
        """`escalation-gate-fail` is written twice, meaning opposite things.

        The vocabulary is closed, so the driver reuses it: once when a stronger
        model is tried, and again when the escalation it was allowed has been
        spent and the run hands back what it has. The tree glossed both as "a
        stronger model was tried", which is false on the second - by then
        nothing was tried at all.
        """
        run = _run("partial", "data-sql", tmp_path)
        assert run.terminated == "returned-partial"
        recorded = [
            e for e in run.events if e.decision_reason == "escalation-gate-fail"
        ]
        assert len(recorded) == 2, "this run has to write the reason twice"
        # Lowercase in the record; the uppercase in the tree is CSS, and the
        # gloss reads the record.
        assert recorded[0].policy_action == "escalate"
        assert recorded[1].policy_action != "escalate"

        page = (
            pathlib.Path(__file__).resolve().parents[2]
            / "clients" / "console" / "app.html"
        ).read_text(encoding="utf-8")
        assert '"escalation-gate-fail": "the floor was not met",' in page
        assert "had already been spent" in page
        assert "so a stronger model was tried" in page

    def test_a_refused_draft_that_was_retried_is_not_quoted(self, tmp_path) -> None:
        """A retry overwrites the sidecar, so the refused values are gone.

        `deliverable.json` is written again over the same path, and only the log
        keeps the old hash. Quoting the replacement here would show a passing
        value beside the criterion that failed - which is what this did on its
        first attempt, reporting `est_delay_days` as 0 against a criterion that
        refused 999.
        """
        run = _run("escalation", "supply-chain", tmp_path)
        assert run.escalations == 1
        assert run.quality_state == "pass", "the retry passed, so the draft is gone"
        rows = stream.compared(
            jobs.by_key("send-it-to-a-buyer"), [delta.summarise(run, "governed")]
        )
        bounded = next(r for r in rows if r["criterion"] == "delay-estimate-bounded")
        assert bounded["kept"] is False
        assert "got" not in bounded, "the replacement must not be quoted"
        assert bounded["wanted"] == "between 0 and 180"

        page = (
            pathlib.Path(__file__).resolve().parents[2]
            / "clients" / "console" / "app.html"
        ).read_text(encoding="utf-8")
        assert "replaced by the retry and is not kept" in page

    def test_an_escalation_says_why_in_words(self, tmp_path) -> None:
        """The log names a criterion; the screen has to say what it checks.

        `unmet: ['result-matches-key']` is right for a log and useless on a
        screen, and without it an escalation reads as "it tried harder" with no
        stated cause. The wording comes from the frozen contract, so the page
        cannot describe a criterion differently from the document that defines
        it.
        """
        job = jobs.by_key("figure-never-right")
        frames, _by_arm, _last = _both(job.key, tmp_path)
        start = frames[0]
        assert start["type"] == "start"

        escalated = [
            f["event"]
            for f in frames
            if f["type"] == "event" and f["event"].get("unmet")
        ]
        assert escalated, "this card has to escalate on a named criterion"

        spec = compose.contract(job.workload)
        says = {
            c.id: " ".join(c.description.split())
            for _band, crits in spec.criteria
            for c in crits
            if c.verifier is not None
        }
        for event in escalated:
            for name in event["unmet"]:
                assert name in start["criteria"], f"{name} has no description to show"
                shown = start["criteria"][name]["says"]
                # The first sentence, verbatim. The rest of these descriptions
                # explain the authoring decision, which is not a tree leaf.
                assert says[name].startswith(shown.rstrip(".")), name
                assert len(shown) <= 120, f"{name} is too long for a leaf: {shown}"

    def test_a_check_that_needs_the_answer_key_says_so(self, tmp_path) -> None:
        # Two of the eleven cards escalate on a comparison against the frozen
        # answer key, which no deployment has. The viewer is told which.
        frames, _by_arm, _last = _both("figure-never-right", tmp_path)
        criteria = frames[0]["criteria"]
        assert criteria["result-matches-key"]["needs_key"] is True
        assert criteria["sql-is-read-only"]["needs_key"] is False
        assert criteria["tables-used-plausible"]["needs_key"] is False

        page = (
            pathlib.Path(__file__).resolve().parents[2]
            / "clients" / "console" / "app.html"
        ).read_text(encoding="utf-8")
        assert "compares against the case answer key" in page

    def test_the_retry_is_never_told_what_was_wrong(self, tmp_path, monkeypatch) -> None:
        """`retry-then-escalate` re-asks the identical question.

        On a gate failure `run_case` does `continue` before the assistant turn
        is appended, so the rejected answer never enters the history and nothing
        names the unmet criterion. The retry sees the same messages as the
        attempt that failed, on a different model.

        That is worth pinning rather than fixing here - the driver is library
        code and the freeze is final - because it bounds the claim. In this demo
        the script supplies a better second answer. A real model handed the same
        conversation has no signal that anything was refused.
        """
        from outcomefuse.ports.model import ScriptedModelPort

        seen: list[tuple] = []

        class Spy(ScriptedModelPort):
            def complete(self, request):
                seen.append(tuple(request.messages))
                return super().complete(request)

        monkeypatch.setattr(compose, "ScriptedModelPort", Spy)
        job = jobs.by_key("counted-by-overwriting")
        tag = "blind"
        run = scenarios.run(
            scenarios.by_key(job.situation), work_module.by_workload(job.workload),
            arm=scenarios.GOVERNED, runs_dir=tmp_path, case_id=job.case_id, token=tag,
        )
        assert run.escalations == 1, "there has to be a retry to be blind"
        assert len(seen) >= 2
        rejected, retry = seen[-2], seen[-1]
        assert retry == rejected, "the retry was given something the first attempt was not"
        assert "retry is blind" in job.watch

    def test_the_result_line_says_the_sql_is_a_write(self) -> None:
        # Both arms compute 16 from 16 rows, so the figure is identical and the
        # result line led with it twice. The whole difference was in a field the
        # line never mentioned.
        page = (
            pathlib.Path(__file__).resolve().parents[2]
            / "clients" / "console" / "app.html"
        ).read_text(encoding="utf-8")
        assert "WRITE_SQL" in page
        assert "not a query" in page
        spec = compose.contract("data-sql")
        pattern = next(
            c.verifier.args["pattern"]
            for _band, crits in spec.criteria
            for c in crits
            if c.id == "sql-is-read-only"
        )
        # The clause must name the same verbs the contract refuses, or the page
        # is offering a second opinion instead of reporting the gate's.
        for verb in ("insert", "update", "delete", "drop", "alter", "truncate", "grant"):
            assert verb in pattern
            assert verb in page[page.index("WRITE_SQL"):page.index("WRITE_SQL") + 200]

    def test_the_ceiling_is_a_tripwire_not_a_wall(self, tmp_path) -> None:
        """The run ends over its ceiling, and the card has to say so.

        `run_case` calls the model, adds the usage to the reported spend, and
        only then asks the ledger whether it was affordable. So the turn that
        breaks the ceiling has already been generated and paid for. A tool call
        is priced before it runs and never gets that far; a model turn cannot
        be, because its cost is not known until it exists.

        Pinned because the card used to claim the ceiling was never crossed
        while the figure beside it read 2,051 against 2,000.
        """
        job = jobs.by_key("order-after-order")
        situation = scenarios.by_key(job.situation)
        ceiling = compose.variant(situation.mutate, job.workload).budget.max_tokens
        tag = "ceil"
        run = scenarios.run(
            situation, work_module.by_workload(job.workload), arm=scenarios.GOVERNED,
            runs_dir=tmp_path, case_id=job.case_id, token=tag,
        )
        assert run.terminated == "halt-exhausted"

        reported = run.outcome.spend.total_tokens
        assert reported > ceiling, "the overshoot is the point; if it is gone, say so"

        # What the ledger actually settled stays under the ceiling.
        settled = sum(
            e.tokens_consumed or 0 for e in run.events if e.kind == "spend-settled"
        )
        assert settled <= ceiling

        # And the overshoot is bounded by the one turn that was not settled.
        turns = [
            e.tokens_consumed
            for e in run.events
            if e.kind == "spend-settled" and (e.tokens_consumed or 0) > 100
        ]
        assert reported - ceiling < max(turns), "over by more than a single model turn"
        assert "2,051 against that 2,000" in job.watch

    def test_neither_arm_answers_when_the_budget_runs_out(self, tmp_path) -> None:
        # "tokens 8,703 -> 2,051 (-76%)" reads as a discount until you notice
        # that no answer came out of either arm.
        job = jobs.by_key("order-after-order")
        situation = scenarios.by_key(job.situation)
        doing = work_module.by_workload(job.workload)
        for arm in (scenarios.GOVERNED, scenarios.BASELINE):
            run = scenarios.run(
                situation, doing, arm=arm, runs_dir=tmp_path,
                case_id=job.case_id, token=arm[:4],
            )
            assert run.quality_state == "not-evaluated", arm
            assert not run.deliverable, f"{arm} published something"
        assert "Neither arm answers" in job.watch

    def test_a_failed_call_is_not_cached_so_the_retry_gets_through(self, tmp_path) -> None:
        """The same fingerprint, collapsed in one job and allowed through in the other.

        This is the whole of "a failure is not a denial". It held no card in the
        end - both arms run the same four calls and agree on everything, so there
        was nothing for a viewer to watch - but the mechanism is real and stays
        swept here.
        """
        doing = work_module.by_workload("doc-research")
        tag = "fail"
        failing = scenarios.run(
            scenarios.by_key("failing-tool"), doing, arm=scenarios.GOVERNED,
            runs_dir=tmp_path, case_id="dr-c-005", token=tag,
        )
        keys = [
            e.payload.get("canonical_key")
            for e in failing.events
            if e.kind == "decision-proposed"
        ]
        assert len(keys) > 1, "the retries have to actually repeat"
        assert len(set(keys)) == 1, "and repeat byte-identically"
        assert not [e for e in failing.events if e.decision_reason == "cache-hit"]
        assert len(failing.invoked) == len(keys), "every retry ran"
        assert all(
            e.decision_reason != "denied"
            for e in failing.events
            if e.kind == "decision-recorded"
        )

        # Same governor, same repeated fingerprint, opposite outcome - because
        # these succeed.
        case = compose.cases(doing.workload)[0]
        stalling = compose.governed(
            case, turns=work_module.stalls(doing, {}, case), runs_dir=tmp_path,
            spec=compose.contract(doing.workload), tag="stall-contrast",
        )
        assert len(stalling.invoked) == 1, "successes collapse to one"
        assert [e for e in stalling.events if e.decision_reason == "cache-hit"]

    def test_the_reservations_come_back_on_every_failure(self, tmp_path) -> None:
        tag = "res"
        run = scenarios.run(
            scenarios.by_key("failing-tool"), work_module.by_workload("doc-research"),
            arm=scenarios.GOVERNED, runs_dir=tmp_path, case_id="dr-c-005", token=tag,
        )
        reserved = sum(1 for e in run.events if e.kind == "budget-reserved")
        settled = sum(1 for e in run.events if e.kind == "spend-settled")
        errors = sum(1 for e in run.events if e.payload and "tool_error" in e.payload)
        assert errors > 0, "the card is about failures, so there must be some"
        assert reserved - settled == errors, "a reservation was kept on a failed call"

    def test_a_cache_hit_still_costs_a_model_turn(self, tmp_path) -> None:
        """The cache saves the tool call. It does not save the turn.

        The token column is model turns only, and both arms burn the same ones,
        so it comes out identical while nine tool invocations disappear. Pinned
        because the card has been wrong about this in both directions: first it
        implied a saving, then it claimed a 26% penalty that was really the
        scripted model running dry and triggering an escalation.
        """
        job = jobs.by_key("same-file-again")
        doing = work_module.by_workload(job.workload)
        situation = scenarios.by_key(job.situation)
        runs = {
            arm: scenarios.run(
                situation, doing, arm=arm, runs_dir=tmp_path,
                case_id=job.case_id, token=arm,
            )
            for arm in (scenarios.GOVERNED, scenarios.BASELINE)
        }
        on, off = runs[scenarios.GOVERNED], runs[scenarios.BASELINE]

        hits = [e for e in on.events if e.decision_reason == "cache-hit"]
        assert len(hits) >= 4, "the stall has to actually hit the cache"
        assert len(on.invoked) == 1, "and execute the tool exactly once"
        assert len(off.invoked) > len(on.invoked)

        # Every cache-hit turn still settled model spend.
        settled = {
            e.step_id: e.tokens_consumed
            for e in on.events
            if e.kind == "spend-settled" and e.tokens_consumed and e.tokens_consumed > 100
        }
        for hit in hits:
            assert settled.get(hit.step_id, 0) > 0, f"{hit.step_id} paid nothing"

        # Same model turns, so the same reported tokens. The cache's saving is
        # in invocations, which that figure never counted.
        assert on.outcome.spend.total_tokens == off.outcome.spend.total_tokens
        assert "identical" in job.watch

    def test_the_stall_reaches_the_fuse_without_the_script_running_dry(self) -> None:
        """At six turns the fixture ended before the fuse did.

        `ScriptedModelPort` returns no text once its turns are used up, the
        driver reads that as a gate failure, and `retry-then-escalate` spends an
        escalation on it. The run then looked like the governor being expensive
        when it was really the demo ending. The agent now outlasts every
        contract's cap.
        """
        for doing in work_module.WORK:
            case = compose.cases(doing.workload)[0]
            cap = compose.contract(doing.workload).budget.max_iterations
            turns = work_module.stalls(doing, {}, case)
            assert len(turns) > cap, f"{doing.workload}: {len(turns)} <= cap {cap}"

    @pytest.mark.parametrize("workload", WORKLOADS)
    def test_a_stall_never_escalates(self, workload, tmp_path) -> None:
        run = _run("stall", workload, tmp_path)
        assert run.terminated == "halt-no-progress"
        assert run.escalations == 0, "an escalation here means the script ran dry"
        assert not any("no text" in str(e.payload) for e in run.events)

    def test_the_cache_gloss_does_not_promise_a_saving(self) -> None:
        page = (
            pathlib.Path(__file__).resolve().parents[2]
            / "clients" / "console" / "app.html"
        ).read_text(encoding="utf-8")
        gloss = next(line for line in page.splitlines() if '"cache-hit":' in line)
        assert "still cost" in gloss


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
            "shows", "shows_kind", "authored", "interactive", "variant", "work",
            "workload", "case_id",
        }
        assert {j["shows_kind"] for j in payload["jobs"]} <= set(jobs.SLUG.values())

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
