from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from dependencies import get_active_context

router = APIRouter(prefix="/scan", tags=["scan"])


class ScanRequest(BaseModel):
    session_token: str


def _scan_service() -> Any:
    try:
        from services.scan_service import ScanService  # type: ignore
    except ImportError as exc:
        raise HTTPException(status_code=500, detail=f"ScanService import failed: {exc}") from exc
    return ScanService()


@router.post("")
def scan(payload: ScanRequest) -> dict[str, int]:
    context = get_active_context(payload.session_token)
    service = _scan_service()

    db_path = getattr(context, "db_path", None)
    raw_folder = getattr(context, "raw_folder", None)
    if db_path is None or raw_folder is None:
        raise HTTPException(status_code=400, detail="Project context is missing db_path or raw_folder")

    result = service.scan(db_path=Path(db_path), raw_folder=Path(raw_folder))
    scanned = int(result) if isinstance(result, (int, float)) else len(result or [])
    return {"scanned_count": scanned}

