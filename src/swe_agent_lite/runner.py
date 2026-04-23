"""Drive a benchmark run: iterate tasks, stage workspaces, run the agent,
score, and aggregate into a RunResult."""

from __future__ import annotations

import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import anthropic

from swe_agent_lite.agent import run_agent, task_prompt
from swe_agent_lite.analysis import categorize_failure
from swe_agent_lite.config import Settings
from swe_agent_lite.models import RunResult, ScoreResult, Task, TaskResult, ToolCall, Trajectory
from swe_agent_lite.scorer import score_workspace
from swe_agent_lite.tasks import list_tasks, stage_task
from swe_agent_lite.tools import Workspace


def _default_client_factory(settings: Settings) -> anthropic.Anthropic:
    if not settings.anthropic_api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not set. Copy .env.example to .env or export it.")
    return anthropic.Anthropic(
        api_key=settings.anthropic_api_key, timeout=settings.request_timeout_s
    )


def run_one_task(
    task: Task,
    *,
    client: anthropic.Anthropic,
    settings: Settings,
    workspace_root: Path | None = None,
    on_tool_call: Callable[[ToolCall], None] | None = None,
) -> TaskResult:
    """Stage the task into a tmp workspace and run the agent end-to-end."""
    t0 = time.monotonic()

    # Use an explicit workspace dir if the caller provided one (tests do this
    # so they can inspect the workspace afterwards); otherwise a fresh tmp.
    cleanup_needed = workspace_root is None
    if workspace_root is None:
        workspace_root = Path(tempfile.mkdtemp(prefix=f"swe-agent-lite-{task.id}-"))

    try:
        repo_dir, tests_dir = stage_task(task, workspace_root)
        ws = Workspace(
            root=workspace_root,
            repo_dir=repo_dir,
            tests_dir=tests_dir,
            pytest_timeout_s=settings.pytest_timeout_s,
        )

        prompt = task_prompt(task, ws)
        traj = run_agent(
            prompt,
            ws,
            client=client,
            model=settings.model,
            max_iterations=settings.max_iterations,
            on_tool_call=on_tool_call,
        )
        traj.task_id = task.id

        score = score_workspace(ws.root, ws.tests_dir, timeout_s=settings.pytest_timeout_s)

        return TaskResult(
            task_id=task.id,
            passed=score.passed,
            duration_s=time.monotonic() - t0,
            trajectory=traj,
            score=score,
            failure_modes=categorize_failure(traj, score),
        )
    finally:
        if cleanup_needed:
            import shutil

            shutil.rmtree(workspace_root, ignore_errors=True)


def run_benchmark(
    settings: Settings,
    *,
    task_ids: list[str] | None = None,
    client_factory: Callable[[Settings], anthropic.Anthropic] = _default_client_factory,
    on_task_start: Callable[[Task], None] | None = None,
    on_task_done: Callable[[TaskResult], None] | None = None,
    on_tool_call: Callable[[ToolCall], None] | None = None,
) -> RunResult:
    tasks = list_tasks()
    if task_ids is not None:
        task_set = set(task_ids)
        tasks = [t for t in tasks if t.id in task_set]

    client = client_factory(settings)

    results: list[TaskResult] = []
    for task in tasks:
        if on_task_start is not None:
            on_task_start(task)
        try:
            r = run_one_task(task, client=client, settings=settings, on_tool_call=on_tool_call)
        except Exception as exc:  # noqa: BLE001
            # A task that blows up the framework (rather than just the agent)
            # shouldn't torpedo the whole run. Record a failing result with
            # the exception text and keep going.
            r = TaskResult(
                task_id=task.id,
                passed=False,
                duration_s=0.0,
                trajectory=Trajectory(task_id=task.id, iterations=0, tool_calls=[]),
                score=ScoreResult(passed=False, stderr=f"framework_error: {exc}"),
                failure_modes=[f"framework_error:{type(exc).__name__}"],
            )
        results.append(r)
        if on_task_done is not None:
            on_task_done(r)

    started = datetime.now(timezone.utc)
    return RunResult(
        run_id=started.strftime("%Y%m%dT%H%M%SZ"),
        model=settings.model,
        started_at=started,
        tasks=results,
    )
