from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from dependencies import create_session_token, serialize_context, set_active_context

router = APIRouter(prefix="/projects", tags=["projects"])


class CreateProjectRequest(BaseModel):
    name: str
    raw_folder: str
    output_folder: str


class LoadProjectRequest(BaseModel):
    output_folder: str


def _project_service() -> Any:
    try:
        from services.project_service import ProjectService  # type: ignore
    except ImportError as exc:
        raise HTTPException(status_code=500, detail=f"ProjectService import failed: {exc}") from exc
    return ProjectService()


@router.post("/create")
def create_project(payload: CreateProjectRequest) -> dict[str, Any]:
    service = _project_service()
    try:
        context = service.create_project(
            name=payload.name,
            raw_folder=Path(payload.raw_folder),
            output_folder=Path(payload.output_folder),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    session_token = create_session_token()
    set_active_context(session_token, context)
    return {"session_token": session_token, "project_context": serialize_context(context)}


@router.post("/load")
def load_project(payload: LoadProjectRequest) -> dict[str, Any]:
    service = _project_service()
    try:
        context = service.load_project(output_folder=Path(payload.output_folder))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    session_token = create_session_token()
    set_active_context(session_token, context)
    return {"session_token": session_token, "project_context": serialize_context(context)}


@router.get("/last")
def try_load_last_project() -> dict[str, Any] | None:
    service = _project_service()
    try:
        context = service.try_load_last_project()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if context is None:
        return None
    session_token = create_session_token()
    set_active_context(session_token, context)
    return {"session_token": session_token, "project_context": serialize_context(context)}

