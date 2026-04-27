"""Structured logging helpers for desktop + CLI runtime diagnostics."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from utils.paths import get_kiw_data_dir

_CONFIGURED = False


def configure_logging(*, level: int = logging.INFO) -> None:
    """Configure process-wide logging once (console + JSONL file)."""
    global _CONFIGURED
    if _CONFIGURED:
        return
    log_dir = get_kiw_data_dir() / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "app.log.jsonl"

    root = logging.getLogger()
    root.setLevel(level)

    console = logging.StreamHandler()
    console.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s", "%H:%M:%S")
    )
    root.addHandler(console)

    json_file = logging.FileHandler(log_path, encoding="utf-8")
    json_file.setFormatter(_JsonLineFormatter())
    root.addHandler(json_file)
    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    configure_logging()
    return logging.getLogger(name)


class _JsonLineFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)
