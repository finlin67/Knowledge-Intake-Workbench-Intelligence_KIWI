from __future__ import annotations
import json
from dataclasses import asdict, is_dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4
from fastapi import HTTPException
from services.project_service import ProjectContext

SESSION_FILE = Path.home() / ".kiw" / "sessions.json"

def _load_sessions() -> dict[str, dict]:
    try:
        if SESSION_FILE.is_file():
            return json.loads(SESSION_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}

def _save_sessions(sessions: dict[str, dict]) -> None:
    SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
    SESSION_FILE.write_text(json.dumps(sessions, indent=2), encoding="utf-8")

def _json_safe(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if is_dataclass(value):
        return _json_safe(asdict(value))
    return value

def create_session(context: ProjectContext) -> str:
    token = str(uuid4())
    sessions = _load_sessions()
    sessions[token] = {
        "name": context.name,
        "raw_folder": str(context.raw_folder),
        "output_folder": str(context.output_folder),
        "db_path": str(context.db_path),
        "project_file": str(context.project_file),
    }
    _save_sessions(sessions)
    return token

def get_project_context(session_token: str) -> ProjectContext:
    sessions = _load_sessions()
    data = sessions.get(session_token)
    if data is None:
        raise HTTPException(
            status_code=404,
            detail="Session not found. Create or load a project first."
        )
    return ProjectContext(
        name=data["name"],
        raw_folder=Path(data["raw_folder"]),
        output_folder=Path(data["output_folder"]),
        db_path=Path(data["db_path"]),
        project_file=Path(data["project_file"]),
    )

def project_context_payload(context: ProjectContext) -> dict[str, Any]:
    return _json_safe(context)

def json_payload(value: Any) -> Any:
    return _json_safe(value)

