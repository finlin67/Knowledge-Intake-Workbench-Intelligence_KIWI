from __future__ import annotations

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

from db.repositories import FileRepository
from db.session import Database
from api.dependencies import json_payload, get_project_context

router = APIRouter(tags=["queue"])


class QueueRequest(BaseModel):
    session_token: str


class ClearQueueRequest(BaseModel):
    session_token: str
    export_profile: Literal["anythingllm", "open_webui", "both"] = "both"


@router.get("/queue")
def get_queue(session_token: str) -> dict[str, object]:
    context = get_project_context(session_token)
    db = Database(context.db_path)
    db.connect()
    try:
        files = FileRepository(db)
        current_batch = files.list_for_runner(limit=500, export_profile="anythingllm")
        other_pending = files.list_for_runner(limit=500, export_profile="open_webui")
    finally:
        db.close()
    return {
        "current_batch_queue": json_payload(current_batch),
        # Keep both keys for frontend compatibility.
        "pending_queue": json_payload(other_pending),
        "other_pending_queue": json_payload(other_pending),
    }


@router.get("/inventory")
def get_inventory(session_token: str, limit: int = 5000) -> dict[str, object]:
    context = get_project_context(session_token)
    db = Database(context.db_path)
    db.connect()
    try:
        files = FileRepository(db)
        rows = files.list_recent_filtered(limit=max(100, min(limit, 20000)))
    finally:
        db.close()
    return {"rows": json_payload(rows)}


@router.post("/queue/clear")
def clear_queue(request: ClearQueueRequest) -> dict[str, object]:
    context = get_project_context(request.session_token)
    db = Database(context.db_path)
    db.connect()
    try:
        conn = db.connect()
        profiles = (
            ["anythingllm", "open_webui"]
            if request.export_profile == "both"
            else [request.export_profile]
        )
        cleared_total = 0
        for profile in profiles:
            if profile == "anythingllm":
                status_col = "runner_status_anythingllm"
                next_stage_col = "pipeline_next_stage_anythingllm"
            else:
                status_col = "runner_status_open_webui"
                next_stage_col = "pipeline_next_stage_open_webui"
            cur = conn.execute(
                f"""
                UPDATE files
                SET {status_col} = 'completed',
                    {next_stage_col} = NULL,
                    runner_status = 'completed',
                    pipeline_next_stage = NULL,
                    updated_at = datetime('now')
                WHERE {next_stage_col} IS NOT NULL
                """
            )
            cleared_total += int(cur.rowcount or 0)
        conn.commit()
    finally:
        db.close()
    return {"cleared_count": cleared_total}
