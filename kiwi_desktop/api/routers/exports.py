from __future__ import annotations

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

from db.session import Database
from api.dependencies import get_project_context, json_payload
from services.pipeline_runner import PipelineRunner

router = APIRouter(tags=["exports"])


class RunExportsRequest(BaseModel):
    session_token: str
    export_profile: Literal["anythingllm", "open_webui", "both"]


@router.post("/exports/run")
def run_exports(request: RunExportsRequest) -> dict[str, object]:
    context = get_project_context(request.session_token)
    profiles = ["anythingllm", "open_webui"] if request.export_profile == "both" else [request.export_profile]
    results: dict[str, object] = {}
    db = Database(context.db_path)
    db.connect()
    try:
        for profile in profiles:
            runner = PipelineRunner(
                db,
                normalized_work_dir=context.output_folder / "normalized",
                export_root=context.output_folder / "exports",
                export_profile=profile,
            )
            results[profile] = json_payload(runner.run())
    finally:
        db.close()
    return {"results": results}
