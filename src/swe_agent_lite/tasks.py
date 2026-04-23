"""Task loading. Tasks live in the `tasks/` directory (in the source tree)
and get bundled into the wheel under `swe_agent_lite/tasks_bundle/`.
"""

from __future__ import annotations

import importlib.resources as resources
import shutil
from pathlib import Path

import yaml

from swe_agent_lite.models import Task


def _tasks_root() -> Path:
    """Root directory of the bundled task suite.

    Installed: points inside the package. Editable: points at the repo's
    `tasks/` dir. We resolve the bundled location via importlib.resources,
    which works under both.
    """
    try:
        bundle = resources.files("swe_agent_lite").joinpath("tasks_bundle")
        # Path-ify; this raises if the bundle isn't a real directory on disk
        # (e.g. zipped), but hatchling builds wheels with real dirs.
        p = Path(str(bundle))
        if p.is_dir():
            return p
    except Exception:  # noqa: BLE001
        pass
    # Editable install fallback — resolve up from this module to the repo root.
    here = Path(__file__).resolve()
    repo_root = here.parent.parent.parent  # src/swe_agent_lite/tasks.py → repo/
    candidate = repo_root / "tasks"
    if candidate.is_dir():
        return candidate
    raise FileNotFoundError(
        "Could not locate the tasks directory. Expected it bundled under "
        "`swe_agent_lite/tasks_bundle/` or as `tasks/` at the repo root."
    )


def list_tasks() -> list[Task]:
    """Every task in the bundled suite, sorted by id."""
    root = _tasks_root()
    out: list[Task] = []
    for task_dir in sorted(root.iterdir()):
        if not task_dir.is_dir():
            continue
        meta = task_dir / "task.yaml"
        if not meta.is_file():
            continue
        raw = yaml.safe_load(meta.read_text(encoding="utf-8"))
        out.append(Task(**raw))
    return out


def load_task(task_id: str) -> Task:
    for t in list_tasks():
        if t.id == task_id:
            return t
    raise KeyError(f"no task with id {task_id!r}")


def stage_task(task: Task, dest: Path) -> tuple[Path, Path]:
    """Copy a task's repo and tests into a fresh working directory.

    Returns (repo_dir_path, tests_dir_path) inside `dest`. This is the
    sandboxing boundary — the agent only ever sees this copy, never the
    canonical task data.
    """
    root = _tasks_root() / task.id
    if not root.is_dir():
        raise FileNotFoundError(f"task directory missing: {root}")

    dest.mkdir(parents=True, exist_ok=True)
    src_repo = root / task.repo_dir
    src_tests = root / task.tests_dir
    dst_repo = dest / task.repo_dir
    dst_tests = dest / task.tests_dir

    if src_repo.is_dir():
        shutil.copytree(src_repo, dst_repo, dirs_exist_ok=True)
    if src_tests.is_dir():
        shutil.copytree(src_tests, dst_tests, dirs_exist_ok=True)

    return dst_repo, dst_tests
