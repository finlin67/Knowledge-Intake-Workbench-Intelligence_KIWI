"""Tests for intake service."""

from __future__ import annotations

from pathlib import Path

from services.intake_service import IntakeService


def test_register_and_list(intake_service: IntakeService) -> None:
    item = intake_service.register_file(path="/tmp/example.md", display_name="Example")
    assert item.id is not None
    assert item.path == "/tmp/example.md"

    rows = intake_service.list_recent(limit=10)
    assert len(rows) == 1
    assert rows[0].path == "/tmp/example.md"
