"""Run artifact persistence (JSON per run)."""

from __future__ import annotations

from pathlib import Path

from swe_agent_lite.models import RunResult


def save(runs_dir: Path, r: RunResult) -> Path:
    runs_dir.mkdir(parents=True, exist_ok=True)
    out = runs_dir / f"{r.run_id}.json"
    out.write_text(r.model_dump_json(indent=2), encoding="utf-8")
    return out


def load(p: Path) -> RunResult:
    return RunResult.model_validate_json(p.read_text(encoding="utf-8"))


def list_runs(runs_dir: Path) -> list[Path]:
    if not runs_dir.exists():
        return []
    return sorted(runs_dir.glob("*.json"), reverse=True)
