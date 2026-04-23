"""Tests for the tool-use agent loop.

We build a stub Anthropic client whose `messages.create` returns a scripted
sequence of tool-use responses, and verify the loop dispatches tools,
threads tool_results back, and stops correctly.
"""

from __future__ import annotations

from typing import Iterator

from swe_agent_lite.agent import run_agent
from swe_agent_lite.tasks import load_task, stage_task
from swe_agent_lite.tools import Workspace


class _Block:
    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)


class _Response:
    def __init__(self, content, stop_reason="end_turn"):
        self.content = content
        self.stop_reason = stop_reason


class _StubMessages:
    """Feed a scripted list of _Response objects, one per `create()` call."""

    def __init__(self, script: Iterator[_Response]):
        self._script = script
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return next(self._script)


class _StubClient:
    def __init__(self, script):
        self.messages = _StubMessages(iter(script))


def _ws_for(tmp_path, task_id: str) -> Workspace:
    t = load_task(task_id)
    repo, tests = stage_task(t, tmp_path)
    return Workspace(root=tmp_path, repo_dir=repo, tests_dir=tests, pytest_timeout_s=10)


def _text(t):
    return _Block(type="text", text=t)


def _use(tool_id, name, inputs):
    return _Block(type="tool_use", id=tool_id, name=name, input=inputs)


def test_agent_solves_off_by_one_end_to_end(tmp_path):
    """Scripted agent fixes task 01 by editing, re-running tests, and calling finish."""
    ws = _ws_for(tmp_path, "01-off-by-one")

    # The scripted trajectory:
    #   1. list_dir('.')
    #   2. read_file('repo/solution.py')
    #   3. run_tests() — red
    #   4. edit_file replacing range(n) with range(1, n + 1)
    #   5. run_tests() — green
    #   6. finish
    script = [
        _Response([_use("1", "list_dir", {"path": "."})]),
        _Response([_use("2", "read_file", {"path": "repo/solution.py"})]),
        _Response([_use("3", "run_tests", {})]),
        _Response(
            [
                _use(
                    "4",
                    "edit_file",
                    {
                        "path": "repo/solution.py",
                        "old_string": "return sum(range(n))",
                        "new_string": "return sum(range(1, n + 1))",
                    },
                )
            ]
        ),
        _Response([_use("5", "run_tests", {})]),
        _Response([_use("6", "finish", {"summary": "fixed off-by-one"})]),
    ]
    client = _StubClient(script)

    traj = run_agent("Fix the off-by-one.", ws, client=client, model="m", max_iterations=10)
    assert traj.finished_cleanly is True
    assert traj.hit_iteration_limit is False
    assert [tc.name for tc in traj.tool_calls] == [
        "list_dir",
        "read_file",
        "run_tests",
        "edit_file",
        "run_tests",
        "finish",
    ]
    # And the edit actually landed in the workspace
    assert "range(1, n + 1)" in (ws.repo_dir / "solution.py").read_text()


def test_agent_stops_at_iteration_cap(tmp_path):
    """Agent that never finishes should hit the cap and report it."""
    ws = _ws_for(tmp_path, "01-off-by-one")

    # Scripted to loop read_file forever. We cap at 3.
    script = [
        _Response([_use(str(i), "read_file", {"path": "repo/solution.py"})]) for i in range(10)
    ]
    client = _StubClient(script)

    traj = run_agent("Go", ws, client=client, model="m", max_iterations=3)
    assert traj.hit_iteration_limit is True
    assert traj.finished_cleanly is False
    assert traj.iterations == 3


def test_agent_stops_when_no_tool_use(tmp_path):
    """Response with only text (no tool_use) ends the loop gracefully."""
    ws = _ws_for(tmp_path, "01-off-by-one")
    script = [
        _Response([_use("1", "list_dir", {"path": "."})]),
        _Response([_text("I give up")], stop_reason="end_turn"),
    ]
    client = _StubClient(script)
    traj = run_agent("Go", ws, client=client, model="m", max_iterations=10)
    assert traj.finished_cleanly is False
    assert traj.hit_iteration_limit is False
    assert traj.iterations == 2
    assert "I give up" in traj.assistant_text


def test_agent_handles_edit_failure_gracefully(tmp_path):
    """If edit_file returns ERROR, the agent just sees it as tool output."""
    ws = _ws_for(tmp_path, "01-off-by-one")
    script = [
        _Response(
            [
                _use(
                    "1",
                    "edit_file",
                    {"path": "repo/solution.py", "old_string": "xxx", "new_string": "yyy"},
                )
            ]
        ),
        _Response([_use("2", "finish", {"summary": "giving up"})]),
    ]
    client = _StubClient(script)
    traj = run_agent("Go", ws, client=client, model="m", max_iterations=10)
    # Both tool calls recorded
    assert len(traj.tool_calls) == 2
    # First tool call output should have ERROR
    assert "ERROR" in traj.tool_calls[0].output_preview
    assert traj.finished_cleanly is True
