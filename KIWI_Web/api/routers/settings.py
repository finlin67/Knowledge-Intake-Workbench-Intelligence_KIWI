from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from dependencies import get_active_context, serialize_context

router = APIRouter(prefix="/settings", tags=["settings"])


class UpdateSettingsRequest(BaseModel):
    session_token: str
    config: dict[str, Any]


def _settings_service() -> Any:
    try:
        from services.settings_service import SettingsService  # type: ignore
    except ImportError as exc:
        raise HTTPException(status_code=500, detail=f"SettingsService import failed: {exc}") from exc
    return SettingsService()


@router.get("")
def get_settings(session_token: str = Query(...)) -> dict[str, Any]:
    context = get_active_context(session_token)
    service = _settings_service()
    config = service.get_classification_config(context)
    return {"config": serialize_context(config)}


@router.put("")
def update_settings(payload: UpdateSettingsRequest) -> dict[str, Any]:
    context = get_active_context(payload.session_token)
    service = _settings_service()
    saved = service.update_classification_config(context, payload.config)
    return {"saved": bool(saved), "config": serialize_context(payload.config)}

