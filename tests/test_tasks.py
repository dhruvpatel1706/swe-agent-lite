"""Task loading + staging."""

from __future__ import annotations

from swe_agent_lite.tasks import list_tasks, load_task, stage_task


def test_list_tasks_finds_the_suite():
    tasks = list_tasks()
    # v0.1 ships 8 hand-curated tasks. If any are missing we should know.
    assert len(tasks) == 8
    ids = {t.id for t in tasks}
    for expected in [
        "01-off-by-one",
        "02-empty-list",
        "03-wrong-comparison",
        "04-dict-typo",
        "05-mutable-default",
        "06-silent-swallow",
        "07-missing-filter",
        "08-recursion-base",
    ]:
        assert expected in ids


def test_load_task_by_id():
    t = load_task("01-off-by-one")
    assert t.title.startswith("sum_first_n")
    assert "off-by-one" in t.tags


def test_staging_copies_repo_and_tests(tmp_path):
    t = load_task("01-off-by-one")
    repo_path, tests_path = stage_task(t, tmp_path)
    assert repo_path.is_dir()
    assert tests_path.is_dir()
    assert (repo_path / "solution.py").is_file()
    # The staged repo content should match the canonical task's initial
    # (broken) solution.
    staged = (repo_path / "solution.py").read_text(encoding="utf-8")
    assert "sum(range(n))" in staged  # the pre-fix bug


def test_staging_is_independent_of_source(tmp_path):
    """Writing into the staged copy must not touch the canonical task."""
    t = load_task("01-off-by-one")
    repo_path, _ = stage_task(t, tmp_path)
    (repo_path / "solution.py").write_text("MUTATED\n", encoding="utf-8")
    # Load again — the canonical task must still have the pre-fix bug.
    other_root = tmp_path / "other"
    other_root.mkdir()
    other_repo, _ = stage_task(t, other_root)
    assert "MUTATED" not in (other_repo / "solution.py").read_text()
