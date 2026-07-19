from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class Settings:
    workspace: Path
    host: str = "127.0.0.1"
    port: int = 8765

    @property
    def database_path(self) -> Path:
        return self.workspace / "app" / "app.sqlite"

    @property
    def projects_path(self) -> Path:
        return self.workspace / "projects"

    def ensure(self) -> None:
        for path in (
            self.workspace / "app" / "logs",
            self.workspace / "app" / "runtime",
            self.workspace / "app" / "cache",
            self.projects_path,
            self.workspace / "templates",
            self.workspace / "diagnostics",
            self.workspace / "crash",
        ):
            path.mkdir(parents=True, exist_ok=True)

