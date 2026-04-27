from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from api.dependencies import create_session, project_context_payload
from services.project_service import ProjectService

router = APIRouter(tags=["projects"])
_project_service = ProjectService()


class CreateProjectRequest(BaseModel):
    name: str
    raw_folder: str
    output_folder: str


class LoadProjectRequest(BaseModel):
    output_folder: str


@router.post("/projects/create")
def create_project(request: CreateProjectRequest) -> dict[str, object]:
    try:
        context = _project_service.create_project(
            name=request.name,
            raw_folder=Path(request.raw_folder),
            output_folder=Path(request.output_folder),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    token = create_session(context)
    return {"project_context": project_context_payload(context), "session_token": token}


@router.post("/projects/load")
def load_project(request: LoadProjectRequest) -> dict[str, object]:
    try:
        context = _project_service.load_project(output_folder=Path(request.output_folder))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    token = create_session(context)
    return {"project_context": project_context_payload(context), "session_token": token}


@router.get("/projects/last")
def load_last_project() -> dict[str, object] | None:
    context = _project_service.try_load_last_project()
    if context is None:
        return None
    token = create_session(context)
    return {"project_context": project_context_payload(context), "session_token": token}


@router.get("/projects/resolve-path")
def resolve_path(value: str, must_exist: bool = True) -> dict[str, object]:
    resolved = _project_service._resolve_user_path(Path(value), must_exist=must_exist)
    return {
        "input": value,
        "resolved_path": str(resolved),
        "exists": resolved.exists(),
        "is_dir": resolved.is_dir(),
    }
