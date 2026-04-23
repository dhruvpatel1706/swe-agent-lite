"""Failure-mode categorization."""

from __future__ import annotations

from swe_agent_lite.analysis import categorize_failure
from swe_agent_lite.models import ScoreResult, ToolCall, Trajectory


def _traj(tool_names: list[str], *, finished=False, hit_limit=False) -> Trajectory:
    return Trajectory(
        task_id="t",
        iterations=len(tool_names),
        tool_calls=[ToolCall(name=n, input={}, output_preview="") for n in tool_names],
        finished_cleanly=finished,
        hit_iteration_limit=hit_limit,
    )


def test_passing_has_no_failure_modes():
    score = ScoreResult(passed=True)
    traj = _traj(["run_tests"], finished=True)
    assert categorize_failure(traj, score) == []


def test_hit_iteration_limit_tag():
    score = ScoreResult(passed=False)
    traj = _traj(["read_file"] * 20, hit_limit=True)
    tags = categorize_failure(traj, score)
    assert "hit_iteration_limit" in tags


def test_never_ran_tests_flagged():
    score = ScoreResult(passed=False)
    traj = _traj(["read_file", "edit_file", "finish"], finished=True)
    tags = categorize_failure(traj, score)
    assert "never_ran_tests" in tags


def test_didnt_edit_flagged():
    score = ScoreResult(passed=False)
    traj = _traj(["read_file", "run_tests", "finish"], finished=True)
    tags = categorize_failure(traj, score)
    assert "didnt_edit" in tags


def test_edit_but_no_retest():
    score = ScoreResult(passed=False)
    traj = _traj(["read_file", "edit_file", "finish"], finished=True)
    tags = categorize_failure(traj, score)
    assert "edit_but_no_retest" in tags


def test_retest_after_edit_does_not_flag():
    score = ScoreResult(passed=False)
    traj = _traj(["read_file", "edit_file", "run_tests", "finish"], finished=True)
    tags = categorize_failure(traj, score)
    assert "edit_but_no_retest" not in tags


def test_pytest_timeout_flagged():
    score = ScoreResult(passed=False, timed_out=True)
    traj = _traj(["read_file", "edit_file", "run_tests"], hit_limit=True)
    tags = categorize_failure(traj, score)
    assert "agent_timeout" in tags


def test_exit_early_flagged_when_finish_but_fail():
    score = ScoreResult(passed=False)
    traj = _traj(["read_file", "edit_file", "run_tests", "finish"], finished=True)
    tags = categorize_failure(traj, score)
    assert "exit_early" in tags
