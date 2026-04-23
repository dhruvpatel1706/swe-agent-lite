"""Run pytest in a workspace and report pass/fail.

Used by the scorer phase at the end of each task (NOT by the agent's
run_tests tool — the agent's version runs with `-x --tb=short -q` to stay
readable; this one runs the full suite so a pass means *all* tests pass,
not just the first one).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from swe_agent_lite.models import ScoreResult


def score_workspace(
    workspace_root: Path,
    tests_dir: Path,
    *,
    timeout_s: float = 30.0,
) -> ScoreResult:
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", str(tests_dir), "-v"],
            cwd=workspace_root,
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
    except subprocess.TimeoutExpired as exc:
        return ScoreResult(
            passed=False,
            stdout=(exc.stdout.decode() if isinstance(exc.stdout, bytes) else (exc.stdout or "")),
            stderr=(exc.stderr.decode() if isinstance(exc.stderr, bytes) else (exc.stderr or "")),
            returncode=-1,
            timed_out=True,
        )

    return ScoreResult(
        passed=proc.returncode == 0,
        stdout=proc.stdout,
        stderr=proc.stderr,
        returncode=proc.returncode,
        timed_out=False,
    )
