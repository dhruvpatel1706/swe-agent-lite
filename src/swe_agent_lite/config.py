"""Runtime settings."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    anthropic_api_key: str = Field(default="", description="ANTHROPIC_API_KEY")
    model: str = Field(default="claude-opus-4-7", description="Agent model.")
    # Hard cap on tool-use iterations per task. Cheap safety net against
    # infinite loops where the agent gets stuck re-reading the same file.
    max_iterations: int = Field(default=20, ge=1, le=100)
    # Pytest timeout per scoring call. Deliberately short — the curated tasks
    # all run in under 5s when correct.
    pytest_timeout_s: float = Field(default=30.0, ge=1.0)
    runs_dir: Path = Field(
        default_factory=lambda: Path.home() / ".swe-agent-lite" / "runs",
    )
    request_timeout_s: float = 180.0

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
