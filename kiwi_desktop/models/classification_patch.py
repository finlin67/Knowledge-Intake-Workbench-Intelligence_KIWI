"""Typed partial updates for persisted file classification columns."""

from __future__ import annotations

from typing import TypedDict


class ClassificationFieldsPatch(TypedDict, total=False):
    """Subset of classification columns to update. Omitted keys are left unchanged."""

    workspace: str | None
    subfolder: str | None
    matched_by: str | None
    classification_reason: str | None
    content_hash: str | None
    confidence: float | None
    case_study_candidate: bool
    portfolio_candidate: bool
