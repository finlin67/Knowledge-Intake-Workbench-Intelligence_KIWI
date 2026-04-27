from __future__ import annotations

import re
from collections import Counter
from pathlib import Path
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from api.dependencies import get_project_context
from db.repositories import FileRepository
from db.session import Database
from services.ai_classifier import OllamaAIClassifier
from services.classification_config import (
    DEFAULT_CONFIG_FILENAME,
    ClassificationConfig,
    load_classification_config,
    save_classification_config,
)

router = APIRouter(tags=["settings"])

STOPWORDS = {
    "the", "and", "for", "with", "from", "this", "that", "have", "are", "was",
    "were", "been", "has", "had", "not", "but", "all", "can", "will", "would",
    "could", "should", "may", "might", "shall", "also", "just", "like", "more",
    "than", "into", "onto", "over", "under", "about", "after", "before",
    "pdf", "doc", "docx", "ppt", "pptx", "md", "txt", "csv", "xlsx",
    "file", "files", "folder", "copy", "final", "draft", "version", "rev",
    "new", "old", "temp", "backup", "archive", "export", "import",
    "content", "model", "hybrid", "system",
}


def clean_token(token: str) -> str | None:
    token = token.lower().strip()
    token = re.sub(r"\.\w{2,5}$", "", token)
    token = re.sub(r"\d{4}-\d{2}-\d{2}", "", token)
    token = re.sub(r"\b[\da-f]{6,}\b", "", token)
    token = token.strip("-_ ")
    if token.count("-") > 2 or token.count("_") > 2:
        return None
    if len(token) < 3:
        return None
    if token in STOPWORDS:
        return None
    alpha_ratio = sum(char.isalpha() for char in token) / max(len(token), 1)
    if alpha_ratio < 0.6:
        return None
    return token


class UpdateSettingsRequest(BaseModel):
    session_token: str
    config: dict[str, Any]


class OllamaTestRequest(BaseModel):
    model: str
    base_url: str = "http://127.0.0.1:11434"


@router.get("/settings")
def get_settings(session_token: str) -> dict[str, object]:
    context = get_project_context(session_token)
    config_path = Path(context.output_folder) / ".kiw" / DEFAULT_CONFIG_FILENAME
    config = load_classification_config(config_path)
    return {"config": config.to_dict()}


@router.put("/settings")
def update_settings(request: UpdateSettingsRequest) -> dict[str, object]:
    context = get_project_context(request.session_token)
    config_path = Path(context.output_folder) / ".kiw" / DEFAULT_CONFIG_FILENAME
    config = ClassificationConfig.from_dict(request.config)
    save_classification_config(config_path, config)
    return {"config": config.to_dict()}


@router.get("/settings/ollama/models")
def list_ollama_models(base_url: str = "http://127.0.0.1:11434") -> dict[str, object]:
    classifier = OllamaAIClassifier(model="llama3.2:3b", base_url=base_url)
    ok, models, message = classifier.list_models()
    return {"ok": ok, "models": list(models), "message": message}


@router.post("/settings/ollama/test")
def test_ollama_connection(request: OllamaTestRequest) -> dict[str, object]:
    classifier = OllamaAIClassifier(model=request.model, base_url=request.base_url)
    ok, message = classifier.test_connection()
    return {"ok": ok, "message": message}


@router.get("/settings/suggestions")
def suggest_categories(session_token: str, limit: int = 2000) -> dict[str, object]:
    context = get_project_context(session_token)
    db = Database(context.db_path)
    db.connect()
    try:
        files = FileRepository(db).list_recent(limit=max(100, min(limit, 5000)))
    finally:
        db.close()

    if not files:
        return {
            "workspace_suggestions": [],
            "company_suggestions": [],
            "project_suggestions": [],
            "message": "No scanned files found yet. Run a scan first, then try suggestions again.",
        }

    token_counts: Counter[str] = Counter()
    raw_child_counts: Counter[str] = Counter()
    token_re = re.compile(r"[a-zA-Z0-9]{3,}")

    raw_folder = context.raw_folder.resolve()
    for record in files:
        file_tokens: set[str] = set()
        path = Path(record.path)
        try:
            relative = path.resolve().relative_to(raw_folder)
            parts = [p for p in relative.parts if p and p not in {".", ".."}]
            if parts:
                candidate = clean_token(parts[0])
                if candidate:
                    raw_child_counts[candidate] += 1
        except Exception:
            pass

        for token in token_re.findall(record.filename.lower()):
            cleaned = clean_token(token)
            if not cleaned:
                continue
            file_tokens.add(cleaned)

        for cleaned in file_tokens:
            token_counts[cleaned] += 1

    workspace_suggestions = []
    for name, count in raw_child_counts.most_common(8):
        if count < 3:
            continue
        workspace_suggestions.append(
            {
                "key": name.replace(" ", "_"),
                "label": name.replace("_", " ").title(),
                "evidence_count": count,
            }
        )

    common_tokens = [item for item in token_counts.most_common(24) if item[1] >= 3]
    company_suggestions = [
        {"token": token, "workspace_key": "operations", "evidence_count": count}
        for token, count in common_tokens[:12]
    ]
    project_suggestions = [
        {"token": token, "workspace_key": "operations", "evidence_count": count}
        for token, count in common_tokens[12:24]
    ]

    return {
        "workspace_suggestions": workspace_suggestions,
        "company_suggestions": company_suggestions,
        "project_suggestions": project_suggestions,
        "message": f"Generated suggestions from {len(files)} scanned files.",
    }
