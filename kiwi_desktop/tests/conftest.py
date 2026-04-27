"""Pytest fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest

from db.session import Database
from services.intake_service import IntakeService
from services.pipeline_runner import reset_pipeline_handlers


@pytest.fixture(autouse=True)
def _reset_pipeline_handlers() -> None:
    yield
    reset_pipeline_handlers()


@pytest.fixture
def intake_service() -> IntakeService:
    """Service backed by an in-memory SQLite database."""
    db = Database(Path(":memory:"))
    db.connect()
    return IntakeService(db)
