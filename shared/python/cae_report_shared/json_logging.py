from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class JsonFormatter(logging.Formatter):
    def __init__(self, process: str) -> None:
        super().__init__()
        self.process = process

    def format(self, record: logging.LogRecord) -> str:
        details = getattr(record, "details", {})
        document: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname.lower(),
            "process": self.process,
            "event": getattr(record, "event", record.name),
            "project_id": getattr(record, "project_id", None),
            "run_id": getattr(record, "run_id", None),
            "task_id": getattr(record, "task_id", None),
            "session_id": getattr(record, "session_id", None),
            "message": record.getMessage(),
            "details": details if isinstance(details, dict) else {"value": str(details)},
        }
        if record.exc_info:
            document["details"]["exception"] = self.formatException(record.exc_info)
        return json.dumps(document, ensure_ascii=False, separators=(",", ":"))


def configure_json_logger(name: str, process: str, path: Path) -> logging.Logger:
    path.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    for handler in logger.handlers:
        if isinstance(handler, logging.FileHandler) and Path(handler.baseFilename) == path.resolve():
            return logger
    handler = logging.FileHandler(path, encoding="utf-8")
    handler.setFormatter(JsonFormatter(process))
    logger.addHandler(handler)
    return logger

