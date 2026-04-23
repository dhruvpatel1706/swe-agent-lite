"""Scorer: actually run pytest on a staged workspace."""

from __future__ import annotations

from swe_agent_lite.scorer import score_workspace
from swe_agent_lite.tasks import load_task, stage_task


def test_scoring_unfixed_task_fails(tmp_path):
    """A freshly-staged task is broken by design — score must be failing."""
    t = load_task("01-off-by-one")
    repo, tests = stage_task(t, tmp_path)
    r = score_workspace(tmp_path, tests, timeout_s=10)
    assert r.passed is False
    assert r.returncode != 0


def test_scoring_fixed_task_passes(tmp_path):
    """Apply the known fix by hand, score must be passing."""
    t = load_task("01-off-by-one")
    repo, tests = stage_task(t, tmp_path)
    fixed = "def sum_first_n(n):\n    return sum(range(1, n + 1))\n"
    (repo / "solution.py").write_text(fixed, encoding="utf-8")
    r = score_workspace(tmp_path, tests, timeout_s=10)
    assert r.passed is True


def test_scoring_fixed_empty_list_task(tmp_path):
    t = load_task("02-empty-list")
    repo, tests = stage_task(t, tmp_path)
    fixed = (
        "def average(xs):\n"
        "    if not xs:\n"
        "        return 0\n"
        "    return sum(xs) / len(xs)\n"
    )
    (repo / "solution.py").write_text(fixed, encoding="utf-8")
    r = score_workspace(tmp_path, tests, timeout_s=10)
    assert r.passed is True


def test_scoring_timeout_reported(tmp_path):
    """If the test suite hangs, scoring returns `timed_out=True` not a crash."""
    (tmp_path / "repo").mkdir()
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_hang.py").write_text(
        "def test_hang():\n    import time\n    time.sleep(5)\n",
        encoding="utf-8",
    )
    r = score_workspace(tmp_path, tests, timeout_s=1)
    assert r.timed_out is True
    assert r.passed is False
