from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from db.session import Database
from api.dependencies import get_project_context
from services.scan_service import ScanService

router = APIRouter(tags=["scan"])


class ScanRequest(BaseModel):
    session_token: str


@router.post("/scan")
def scan_project(request: ScanRequest) -> dict[str, int]:
    context = get_project_context(request.session_token)
    db = Database(context.db_path)
    db.connect()
    try:
        result = ScanService(db).scan(context.raw_folder)
    finally:
        db.close()
    scanned = int(result.files_matched)
    return {"files_scanned": scanned, "scanned_count": scanned}
