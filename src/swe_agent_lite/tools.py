"""Tools the agent can call. Five tools, no bash, no network.

Why the small surface: the whole benchmark is "can Claude fix a small bug".
Anything we hand the agent beyond the bare minimum is a confound — if it
passes, was it the agent fixing the bug or was it a bash pipeline we didn't
think hard enough about? Five tools is enough for every task in the curated
set and small enough that failure attributions are clean.

Each tool has:
  - A JSON schema (the `SCHEMA` constant) passed to the Anthropic tool-use API.
  - An executor function that takes the parsed inputs + a Workspace and
    returns a string (what the agent sees as tool_result).

The Workspace is the sandbox. Every filesystem operation is routed through
it and the workspace refuses to read or write outside its root.
"""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class WorkspaceError(ValueError):
    """Raised when a tool tries to touch a path outside the workspace."""


@dataclass
class Workspace:
    """A sandboxed per-task directory. Every tool resolves paths through it."""

    root: Path
    repo_dir: Path  # repo_dir and tests_dir are convenience handles; both live
    tests_dir: Path  # under `root`. Used by the agent prompt for context.
    pytest_timeout_s: float = 30.0

    def resolve(self, rel_or_abs: str) -> Path:
        """Resolve a user-supplied path against the workspace root, refusing
        anything outside. Symlink escape attempts get rejected too."""
        p = Path(rel_or_abs)
        if not p.is_absolute():
            p = self.root / p
        p = p.resolve()
        root_resolved = self.root.resolve()
        try:
            p.relative_to(root_resolved)
        except ValueError as exc:
            raise WorkspaceError(f"path {rel_or_abs!r} is outside workspace {self.root}") from exc
        return p


# ---------------------------------------------------------------------------
# Individual tools: (SCHEMA, executor). We build one TOOLS list downstream
# and dispatch on the name.
# ---------------------------------------------------------------------------


_READ_FILE_SCHEMA = {
    "name": "read_file",
    "description": (
        "Read a file in the workspace. Returns the full contents as a string. "
        "Use this to inspect source files before editing them. Paths can be "
        "relative to the workspace root or absolute (as long as they're inside "
        "the workspace)."
    ),
    "input_schema": {
        "type": "object",
        "properties": {"path": {"type": "string", "description": "File path."}},
        "required": ["path"],
    },
}


def _exec_read_file(inputs: dict, ws: Workspace) -> str:
    try:
        p = ws.resolve(inputs["path"])
    except WorkspaceError as exc:
        return f"ERROR: {exc}"
    if not p.is_file():
        return f"ERROR: {inputs['path']!r} is not a file"
    try:
        return p.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return f"ERROR: {inputs['path']!r} is not a UTF-8 text file"


_LIST_DIR_SCHEMA = {
    "name": "list_dir",
    "description": (
        "List files in a directory (non-recursive). Returns one path per line. "
        "Good first call on every new task — the agent should know what files "
        "exist before trying to read them."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Directory path. '.' for the workspace root.",
            }
        },
        "required": ["path"],
    },
}


def _exec_list_dir(inputs: dict, ws: Workspace) -> str:
    try:
        p = ws.resolve(inputs["path"])
    except WorkspaceError as exc:
        return f"ERROR: {exc}"
    if not p.is_dir():
        return f"ERROR: {inputs['path']!r} is not a directory"
    lines = []
    for child in sorted(p.iterdir()):
        kind = "d" if child.is_dir() else "f"
        lines.append(f"{kind} {child.relative_to(ws.root)}")
    return "\n".join(lines) if lines else "(empty directory)"


_EDIT_FILE_SCHEMA = {
    "name": "edit_file",
    "description": (
        "Edit a file by replacing an exact substring. Use `old_string` (must "
        "match the current file exactly, including whitespace) and "
        "`new_string` (what to replace it with). For inserts, make "
        "`new_string` the old text plus the addition. For deletes, make it "
        "empty. The edit fails if `old_string` doesn't appear exactly once; "
        "either make it more specific or read the file again."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "old_string": {"type": "string"},
            "new_string": {"type": "string"},
        },
        "required": ["path", "old_string", "new_string"],
    },
}


def _exec_edit_file(inputs: dict, ws: Workspace) -> str:
    try:
        p = ws.resolve(inputs["path"])
    except WorkspaceError as exc:
        return f"ERROR: {exc}"
    if not p.is_file():
        return (
            f"ERROR: {inputs['path']!r} does not exist. edit_file cannot create new files in v0.1."
        )
    try:
        content = p.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return f"ERROR: {inputs['path']!r} is not a UTF-8 text file"
    old = inputs["old_string"]
    new = inputs["new_string"]
    count = content.count(old)
    if count == 0:
        # Return the first 200 chars of the file so the agent can see why
        # its `old_string` didn't match — usually whitespace drift.
        preview = content if len(content) <= 200 else content[:200] + "..."
        return (
            f"ERROR: old_string not found in {inputs['path']!r}. "
            f"Current file starts with:\n{preview}"
        )
    if count > 1:
        return (
            f"ERROR: old_string matches {count} places in {inputs['path']!r}. "
            "Make it more specific (add surrounding lines)."
        )
    new_content = content.replace(old, new, 1)
    p.write_text(new_content, encoding="utf-8")
    return f"OK. Edited {inputs['path']!r} (one replacement)."


_RUN_TESTS_SCHEMA = {
    "name": "run_tests",
    "description": (
        "Run the task's pytest suite and return the output. This is how you "
        "check whether your fix works. Call it after every meaningful edit. "
        "Runs with a short timeout — a test that hangs counts as a failure."
    ),
    "input_schema": {"type": "object", "properties": {}, "required": []},
}


def _exec_run_tests(inputs: dict, ws: Workspace) -> str:
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", str(ws.tests_dir), "-x", "--tb=short", "-q"],
            cwd=ws.root,
            capture_output=True,
            text=True,
            timeout=ws.pytest_timeout_s,
        )
    except subprocess.TimeoutExpired:
        return (
            f"TIMEOUT: pytest took longer than {ws.pytest_timeout_s}s. "
            "You probably wrote an infinite loop."
        )
    out = proc.stdout + ("\n" + proc.stderr if proc.stderr else "")
    status = "PASSED" if proc.returncode == 0 else f"FAILED (exit {proc.returncode})"
    # Cap output at 4000 chars so the agent doesn't drown in verbose pytest
    # output on a flaky test with 50 assertion failures.
    if len(out) > 4000:
        out = out[:4000] + "\n... (truncated)"
    return f"pytest {status}\n\n{out}"


_FINISH_SCHEMA = {
    "name": "finish",
    "description": (
        "Signal that you believe the bug is fixed and the tests pass. Call "
        "this ONLY after running `run_tests` and seeing it pass. `summary` "
        "should briefly explain what the bug was and how you fixed it."
    ),
    "input_schema": {
        "type": "object",
        "properties": {"summary": {"type": "string"}},
        "required": ["summary"],
    },
}


def _exec_finish(inputs: dict, ws: Workspace) -> str:
    # Handled by the agent loop (it checks for the `finish` name and stops).
    # This executor is just for completeness.
    return "OK. Agent signaled finish."


TOOLS = [
    _READ_FILE_SCHEMA,
    _LIST_DIR_SCHEMA,
    _EDIT_FILE_SCHEMA,
    _RUN_TESTS_SCHEMA,
    _FINISH_SCHEMA,
]

EXECUTORS = {
    "read_file": _exec_read_file,
    "list_dir": _exec_list_dir,
    "edit_file": _exec_edit_file,
    "run_tests": _exec_run_tests,
    "finish": _exec_finish,
}


def dispatch(name: str, inputs: dict, ws: Workspace) -> str:
    """Run one tool call. Returns the string that becomes a tool_result."""
    if name not in EXECUTORS:
        return f"ERROR: unknown tool {name!r}"
    try:
        return EXECUTORS[name](inputs, ws)
    except Exception as exc:  # noqa: BLE001
        return f"ERROR: {type(exc).__name__}: {exc}"


def tool_preview(name: str, inputs: dict[str, Any], output: str) -> str:
    """Short one-line summary used in trajectory records + live logging."""
    if name == "read_file":
        return f"read_file({inputs.get('path')!r}) → {len(output)} chars"
    if name == "list_dir":
        return f"list_dir({inputs.get('path')!r})"
    if name == "edit_file":
        return f"edit_file({inputs.get('path')!r})"
    if name == "run_tests":
        first_line = output.splitlines()[0] if output else ""
        return f"run_tests → {first_line}"
    if name == "finish":
        summary = inputs.get("summary", "")
        return f"finish({summary[:80]!r})"
    return name
