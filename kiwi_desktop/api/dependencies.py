from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import HTTPException

from services.project_service import ProjectContext

# Single-user local store keyed by lightweight session token.
_ACTIVE_CONTEXTS: dict[str, ProjectContext] = {}


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
    _ACTIVE_CONTEXTS[token] = context
    return token


def get_project_context(session_token: str) -> ProjectContext:
    ctx = _ACTIVE_CONTEXTS.get(session_token)
    if ctx is None:
        raise HTTPException(status_code=404, detail="Session not found. Create or load a project first.")
    return ctx


def project_context_payload(context: ProjectContext) -> dict[str, Any]:
    return _json_safe(context)


def json_payload(value: Any) -> Any:
    return _json_safe(value)
