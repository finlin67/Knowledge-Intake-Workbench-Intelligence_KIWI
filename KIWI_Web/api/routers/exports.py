from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from dependencies import get_active_context, serialize_context

router = APIRouter(prefix="/exports", tags=["exports"])


class ExportRequest(BaseModel):
    session_token: str
    export_profile: Literal["anythingllm", "open_webui", "both"]


def _pipeline_runner() -> Any | None:
    try:
        from services.pipeline_runner import PipelineRunner  # type: ignore
    except ImportError:
        return None
    return PipelineRunner()


def _exporter_service() -> Any | None:
    try:
        from services.exporter_service import ExporterService  # type: ignore
    except ImportError:
        return None
    return ExporterService()


@router.post("/run")
def run_exports(payload: ExportRequest) -> dict[str, Any]:
    context = get_active_context(payload.session_token)

    runner = _pipeline_runner()
    if runner is not None and hasattr(runner, "run_exports"):
        result = runner.run_exports(context=context, export_profile=payload.export_profile)
        return {"status": "ok", "result": serialize_context(result)}

    exporter = _exporter_service()
    if exporter is None:
        raise HTTPException(status_code=500, detail="Neither PipelineRunner nor ExporterService is available")

    if payload.export_profile in ("anythingllm", "both"):
        exporter.run(context=context, profile="anythingllm")
    if payload.export_profile in ("open_webui", "both"):
        exporter.run(context=context, profile="open_webui")
    return {"status": "ok"}

