from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from dependencies import get_active_context, serialize_context

router = APIRouter(prefix="/monitor", tags=["monitor"])


def _monitor_service() -> Any:
    try:
        from services.run_monitor_service import RunMonitorService  # type: ignore
    except ImportError as exc:
        raise HTTPException(status_code=500, detail=f"RunMonitorService import failed: {exc}") from exc
    return RunMonitorService()


@router.get("/preflight")
def preflight(session_token: str = Query(...)) -> dict[str, Any]:
    context = get_active_context(session_token)
    service = _monitor_service()
    summary = service.get_preflight_summary(context)
    return {"summary": serialize_context(summary)}

