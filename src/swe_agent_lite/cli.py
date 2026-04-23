"""Typer CLI: run, tasks, list, show."""

from __future__ import annotations

from typing import List

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from swe_agent_lite import __version__
from swe_agent_lite import storage as storage_
from swe_agent_lite.config import get_settings
from swe_agent_lite.runner import run_benchmark
from swe_agent_lite.tasks import list_tasks
from swe_agent_lite.tools import tool_preview

app = typer.Typer(
    add_completion=False, no_args_is_help=True, help="SWE-bench-style agent benchmark for Claude."
)
console = Console()
err = Console(stderr=True)


def _version_cb(value: bool) -> None:
    if value:
        console.print(f"swe-agent-lite {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(False, "--version", "-V", callback=_version_cb, is_eager=True),
) -> None:
    return


@app.command("tasks")
def tasks_cmd() -> None:
    """List every task in the bundled suite."""
    table = Table(show_header=True, header_style="bold cyan", title="Tasks")
    table.add_column("id")
    table.add_column("title")
    table.add_column("difficulty")
    table.add_column("tags")
    for t in list_tasks():
        table.add_row(t.id, t.title, t.difficulty, ", ".join(t.tags) or "—")
    console.print(table)


@app.command("run")
def run_cmd(
    ids: List[str] = typer.Argument(
        None,
        help="Specific task ids. Omit to run the full suite. Run `tasks` to see names.",
    ),
    model: str = typer.Option(None, "--model", "-m", help="Override the default model."),
    max_iterations: int = typer.Option(
        None, "--max-iterations", help="Cap tool-use iterations per task."
    ),
    difficulty: str = typer.Option(
        None,
        "--difficulty",
        "-d",
        help="Filter to tasks of a single difficulty: easy, medium, or hard.",
    ),
    only_multifile: bool = typer.Option(
        False,
        "--only-multifile",
        help="Only run tasks tagged with `multi-file`.",
    ),
) -> None:
    """Run the benchmark. Saves a JSON artifact; non-zero exit on any failure."""
    settings = get_settings()
    if model:
        settings = settings.model_copy(update={"model": model})
    if max_iterations is not None:
        settings = settings.model_copy(update={"max_iterations": max_iterations})

    # Apply filters. If both --difficulty and explicit ids are given, the ids
    # win (we trust the user).
    if ids is None and (difficulty or only_multifile):
        filtered = []
        for t in list_tasks():
            if difficulty and t.difficulty != difficulty:
                continue
            if only_multifile and "multi-file" not in t.tags:
                continue
            filtered.append(t.id)
        if not filtered:
            err.print("[yellow]no tasks matched the filter.[/yellow]")
            raise typer.Exit(0)
        ids = filtered

    def _on_task_start(task) -> None:  # type: ignore[no-untyped-def]
        console.print(f"\n[bold cyan]{task.id}[/bold cyan] — {task.title}")

    def _on_tool_call(tc) -> None:  # type: ignore[no-untyped-def]
        console.print(f"  [dim]→[/dim] {tool_preview(tc.name, tc.input, tc.output_preview)}")

    def _on_task_done(result) -> None:  # type: ignore[no-untyped-def]
        mark = "[green]pass[/green]" if result.passed else "[red]fail[/red]"
        extras = f" [dim]{', '.join(result.failure_modes)}[/dim]" if result.failure_modes else ""
        console.print(
            f"  [bold]{mark}[/bold] in {result.trajectory.iterations} iters, "
            f"{result.duration_s:.1f}s{extras}"
        )

    try:
        run_result = run_benchmark(
            settings,
            task_ids=ids or None,
            on_task_start=_on_task_start,
            on_task_done=_on_task_done,
            on_tool_call=_on_tool_call,
        )
    except RuntimeError as exc:
        err.print(f"[red]{exc}[/red]")
        raise typer.Exit(1)

    console.print()
    table = Table(show_header=True, header_style="bold cyan", title=f"Run {run_result.run_id}")
    table.add_column("task")
    table.add_column("status")
    table.add_column("iters", justify="right")
    table.add_column("time", justify="right")
    table.add_column("failure modes")
    for t in run_result.tasks:
        status = "[green]pass[/green]" if t.passed else "[red]fail[/red]"
        fm = ", ".join(t.failure_modes)
        table.add_row(t.task_id, status, str(t.trajectory.iterations), f"{t.duration_s:.1f}s", fm)
    console.print(table)
    console.print(
        f"\n[bold]{run_result.passed}/{run_result.total}[/bold] tasks passed "
        f"([green]{run_result.pass_rate:.0%}[/green])"
    )

    out = storage_.save(settings.runs_dir, run_result)
    console.print(f"[dim]run saved to {out}[/dim]")

    if run_result.passed < run_result.total:
        raise typer.Exit(1)


@app.command("list")
def list_cmd(limit: int = typer.Option(20, "--limit", "-n", min=1)) -> None:
    """Past runs, newest first."""
    settings = get_settings()
    paths = storage_.list_runs(settings.runs_dir)
    if not paths:
        console.print("[dim]no runs yet.[/dim]")
        return
    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("run id")
    table.add_column("model")
    table.add_column("pass", justify="right")
    table.add_column("rate", justify="right")
    for p in paths[:limit]:
        try:
            r = storage_.load(p)
        except Exception:  # noqa: BLE001
            continue
        table.add_row(r.run_id, r.model, f"{r.passed}/{r.total}", f"{r.pass_rate:.0%}")
    console.print(table)


@app.command("show")
def show_cmd(run_id: str = typer.Argument(...)) -> None:
    """Full trajectory dump for one run — every tool call, every task verdict."""
    settings = get_settings()
    candidates = list(settings.runs_dir.glob(f"*{run_id}*.json"))
    if not candidates:
        err.print(f"[red]no run matching {run_id!r}[/red]")
        raise typer.Exit(1)
    if len(candidates) > 1:
        err.print(f"[red]ambiguous — {len(candidates)} runs match[/red]")
        raise typer.Exit(1)
    r = storage_.load(candidates[0])

    console.print(
        Panel.fit(
            f"model [cyan]{r.model}[/cyan]\nstarted {r.started_at.isoformat()}\n"
            f"{r.passed}/{r.total} passed",
            title=r.run_id,
            border_style="cyan",
        )
    )
    for t in r.tasks:
        head = "[green]pass[/green]" if t.passed else "[red]fail[/red]"
        fm = f" [dim]({', '.join(t.failure_modes)})[/dim]" if t.failure_modes else ""
        console.print(f"\n[bold]{t.task_id}[/bold]  {head}{fm}  {t.duration_s:.1f}s")
        for tc in t.trajectory.tool_calls:
            console.print(f"  · {tool_preview(tc.name, tc.input, tc.output_preview)}")


if __name__ == "__main__":
    app()
