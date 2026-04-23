"""Schemas for tasks, trajectories, and results."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Task(BaseModel):
    """One bug-fix task loaded from tasks/<id>/task.yaml."""

    id: str
    title: str
    # Rough-and-ready difficulty marker. Tuned by how many tool-use turns it
    # takes a median run to solve, not a separate cognitive-effort estimate.
    difficulty: Literal["easy", "medium", "hard"] = "easy"
    # Plain-English bug description shown to the agent in the initial prompt.
    problem: str
    # Directory holding the broken source code, relative to the task root.
    repo_dir: str = "repo"
    # Directory holding the pytest test files, relative to the task root.
    # These are run both by the agent (via the run_tests tool) and by the
    # scorer at the end to decide pass/fail.
    tests_dir: str = "tests"
    # Tags for grouping failure modes (e.g. "off-by-one", "edge-case",
    # "type-confusion"). Used only in reporting.
    tags: list[str] = Field(default_factory=list)


class ToolCall(BaseModel):
    """One tool invocation inside a trajectory."""

    name: str
    input: dict[str, Any]
    # Truncated tool output for audit. Full output lives only in memory.
    output_preview: str = ""


class Trajectory(BaseModel):
    """Full record of one agent run on one task."""

    task_id: str
    iterations: int
    tool_calls: list[ToolCall]
    # Every assistant message's text content concatenated, for post-mortem.
    assistant_text: list[str] = Field(default_factory=list)
    # Set if the agent called `finish`.
    finished_cleanly: bool = False
    # Set if we bailed for hitting max_iterations.
    hit_iteration_limit: bool = False


class ScoreResult(BaseModel):
    """Pytest outcome after the agent stopped editing."""

    passed: bool
    stdout: str = ""
    stderr: str = ""
    returncode: int = 0
    timed_out: bool = False


class TaskResult(BaseModel):
    """Outcome of one task: trajectory + scorer verdict + failure-mode tags."""

    task_id: str
    passed: bool
    duration_s: float
    trajectory: Trajectory
    score: ScoreResult
    # Human-readable categorization of why this task failed (if it did).
    # Empty when passed. Populated by `analysis.categorize_failure`.
    failure_modes: list[str] = Field(default_factory=list)


class RunResult(BaseModel):
    """Everything produced by one `swe-agent-lite run` invocation."""

    run_id: str
    model: str
    started_at: datetime = Field(default_factory=_utc_now)
    tasks: list[TaskResult]

    @property
    def total(self) -> int:
        return len(self.tasks)

    @property
    def passed(self) -> int:
        return sum(1 for t in self.tasks if t.passed)

    @property
    def pass_rate(self) -> float:
        return self.passed / self.total if self.total else 0.0
