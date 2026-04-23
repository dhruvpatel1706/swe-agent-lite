"""Categorize why a task failed. Tags are heuristic and meant for a post-hoc
scatter — they're not claims about root cause, just groupings that make
per-task post-mortems faster to scan.

Tags we produce:
  - hit_iteration_limit  — agent never called `finish` and we bailed
  - never_ran_tests      — agent never invoked run_tests at all (sus)
  - didnt_edit           — agent finished without making any edit
  - edit_but_no_retest   — last edit wasn't followed by a run_tests call
  - tests_were_timing_out — agent's infinite loop triggered pytest timeouts
  - agent_timeout        — the scorer's final pytest call itself timed out
  - exit_early           — agent finished but tests still failing
"""

from __future__ import annotations

from swe_agent_lite.models import ScoreResult, Trajectory


def categorize_failure(trajectory: Trajectory, score: ScoreResult) -> list[str]:
    if score.passed:
        return []

    tags: list[str] = []
    tool_names = [tc.name for tc in trajectory.tool_calls]

    if trajectory.hit_iteration_limit:
        tags.append("hit_iteration_limit")

    if "run_tests" not in tool_names:
        tags.append("never_ran_tests")

    if "edit_file" not in tool_names:
        tags.append("didnt_edit")
    else:
        # If the last edit wasn't followed by any run_tests call, the agent
        # didn't verify its own fix.
        last_edit = max(i for i, n in enumerate(tool_names) if n == "edit_file")
        if not any(n == "run_tests" for n in tool_names[last_edit + 1 :]):
            tags.append("edit_but_no_retest")

    # Detect agent-side infinite loops: repeated "TIMEOUT: pytest" in the
    # agent's tool outputs.
    timeouts_during_run = sum(
        1
        for tc in trajectory.tool_calls
        if tc.name == "run_tests" and tc.output_preview.startswith("TIMEOUT")
    )
    if timeouts_during_run >= 2:
        tags.append("tests_were_timing_out")

    if score.timed_out:
        tags.append("agent_timeout")

    if trajectory.finished_cleanly and not score.passed:
        tags.append("exit_early")

    return tags
