"""Tool executors: workspace sandbox + each of the five tools."""

from __future__ import annotations

from pathlib import Path

import pytest

from swe_agent_lite.tools import Workspace, WorkspaceError, dispatch


def _ws(tmp_path: Path) -> Workspace:
    repo = tmp_path / "repo"
    tests = tmp_path / "tests"
    repo.mkdir()
    tests.mkdir()
    return Workspace(root=tmp_path, repo_dir=repo, tests_dir=tests, pytest_timeout_s=10)


# ---- Workspace path resolution -------------------------------------------


def test_workspace_resolves_relative_paths(tmp_path):
    ws = _ws(tmp_path)
    p = ws.resolve("repo/solution.py")
    assert p == (tmp_path / "repo" / "solution.py").resolve()


def test_workspace_rejects_parent_escape(tmp_path):
    ws = _ws(tmp_path)
    with pytest.raises(WorkspaceError):
        ws.resolve("../../../etc/passwd")


def test_workspace_rejects_absolute_outside(tmp_path):
    ws = _ws(tmp_path)
    with pytest.raises(WorkspaceError):
        ws.resolve("/etc/passwd")


# ---- read_file -----------------------------------------------------------


def test_read_file_happy(tmp_path):
    ws = _ws(tmp_path)
    (ws.repo_dir / "solution.py").write_text("print('hi')\n", encoding="utf-8")
    out = dispatch("read_file", {"path": "repo/solution.py"}, ws)
    assert out == "print('hi')\n"


def test_read_file_missing(tmp_path):
    ws = _ws(tmp_path)
    out = dispatch("read_file", {"path": "nope.py"}, ws)
    assert "ERROR" in out


def test_read_file_outside_workspace(tmp_path):
    ws = _ws(tmp_path)
    out = dispatch("read_file", {"path": "../../../etc/passwd"}, ws)
    assert "ERROR" in out


# ---- list_dir ------------------------------------------------------------


def test_list_dir_basic(tmp_path):
    ws = _ws(tmp_path)
    (ws.repo_dir / "a.py").write_text("x", encoding="utf-8")
    (ws.repo_dir / "b.py").write_text("y", encoding="utf-8")
    out = dispatch("list_dir", {"path": "repo"}, ws)
    assert "a.py" in out
    assert "b.py" in out


def test_list_dir_empty_says_so(tmp_path):
    ws = _ws(tmp_path)
    out = dispatch("list_dir", {"path": "repo"}, ws)
    assert "empty" in out.lower()


# ---- edit_file -----------------------------------------------------------


def test_edit_file_exact_match(tmp_path):
    ws = _ws(tmp_path)
    (ws.repo_dir / "solution.py").write_text("return age >= 17\n", encoding="utf-8")
    out = dispatch(
        "edit_file",
        {
            "path": "repo/solution.py",
            "old_string": "age >= 17",
            "new_string": "age >= 18",
        },
        ws,
    )
    assert "OK" in out
    assert (ws.repo_dir / "solution.py").read_text() == "return age >= 18\n"


def test_edit_file_rejects_nonexistent_old_string(tmp_path):
    ws = _ws(tmp_path)
    (ws.repo_dir / "solution.py").write_text("x = 1\n", encoding="utf-8")
    out = dispatch(
        "edit_file",
        {"path": "repo/solution.py", "old_string": "missing", "new_string": "y = 2"},
        ws,
    )
    assert "ERROR" in out
    # File shouldn't have changed.
    assert (ws.repo_dir / "solution.py").read_text() == "x = 1\n"


def test_edit_file_rejects_multiple_matches(tmp_path):
    ws = _ws(tmp_path)
    (ws.repo_dir / "solution.py").write_text("x = 1\nx = 2\n", encoding="utf-8")
    out = dispatch(
        "edit_file",
        {"path": "repo/solution.py", "old_string": "x = ", "new_string": "y = "},
        ws,
    )
    assert "ERROR" in out
    assert "matches 2 places" in out


def test_edit_file_missing_file(tmp_path):
    ws = _ws(tmp_path)
    out = dispatch(
        "edit_file",
        {"path": "repo/nope.py", "old_string": "a", "new_string": "b"},
        ws,
    )
    assert "ERROR" in out


# ---- run_tests (real subprocess, small workspace) -----------------------


def test_run_tests_passing_suite(tmp_path):
    ws = _ws(tmp_path)
    (ws.tests_dir / "test_x.py").write_text(
        "def test_ok():\n    assert 1 + 1 == 2\n",
        encoding="utf-8",
    )
    out = dispatch("run_tests", {}, ws)
    assert "PASSED" in out


def test_run_tests_failing_suite(tmp_path):
    ws = _ws(tmp_path)
    (ws.tests_dir / "test_x.py").write_text(
        "def test_fail():\n    assert False\n",
        encoding="utf-8",
    )
    out = dispatch("run_tests", {}, ws)
    assert "FAILED" in out


def test_dispatch_unknown_tool(tmp_path):
    ws = _ws(tmp_path)
    out = dispatch("nonexistent_tool", {}, ws)
    assert "unknown tool" in out
