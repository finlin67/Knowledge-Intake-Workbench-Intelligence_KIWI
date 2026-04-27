from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from dependencies import get_active_context, serialize_context

router = APIRouter(prefix="/queue", tags=["queue"])


def _file_repository() -> Any:
    try:
        from db.file_repository import file_repository  # type: ignore

        return file_repository
    except ImportError:
        pass

    try:
        from db.file_repository import FileRepository  # type: ignore

        return FileRepository()
    except ImportError as exc:
        raise HTTPException(status_code=500, detail=f"file_repository import failed: {exc}") from exc


@router.get("")
def get_queue(session_token: str = Query(...)) -> dict[str, Any]:
    context = get_active_context(session_token)
    repository = _file_repository()
    db_path = getattr(context, "db_path", None)
    if db_path is None:
        raise HTTPException(status_code=400, detail="Project context is missing db_path")

    current_batch = []
    pending = []

    if hasattr(repository, "get_current_batch_queue"):
        current_batch = repository.get_current_batch_queue(db_path)
    elif hasattr(repository, "current_batch_queue"):
        current_batch = repository.current_batch_queue(db_path)

    if hasattr(repository, "get_pending_queue"):
        pending = repository.get_pending_queue(db_path)
    elif hasattr(repository, "other_pending_queue"):
        pending = repository.other_pending_queue(db_path)

    return {
        "current_batch_queue": serialize_context(current_batch),
        "pending_queue": serialize_context(pending),
    }

