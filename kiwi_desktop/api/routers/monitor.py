from __future__ import annotations

from fastapi import APIRouter

from api.dependencies import get_project_context, json_payload
from services.run_monitor_service import RunMonitorService

router = APIRouter(tags=["monitor"])


@router.get("/monitor/preflight")
def monitor_preflight(session_token: str) -> dict[str, object]:
    context = get_project_context(session_token)
    monitor = RunMonitorService()
    monitor.configure(
        db_path=context.db_path,
        raw_folder=context.raw_folder,
        output_folder=context.output_folder,
        log=lambda _msg: None,
    )
    summary = monitor.build_preflight_summary()
    return {"summary": json_payload(summary)}
