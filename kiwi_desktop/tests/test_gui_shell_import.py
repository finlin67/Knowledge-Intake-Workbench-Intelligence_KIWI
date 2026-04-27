"""Basic GUI shell import checks."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


_HAS_PYSIDE6 = importlib.util.find_spec("PySide6") is not None
pyside_only = pytest.mark.skipif(not _HAS_PYSIDE6, reason="PySide6 not installed")


if _HAS_PYSIDE6:
    @pytest.fixture(scope="session")
    def qapp():
        from PySide6.QtWidgets import QApplication

        app = QApplication.instance() or QApplication(sys.argv[:1])
        yield app


@pytest.mark.skipif(importlib.util.find_spec("PySide6") is None, reason="PySide6 not installed")
def test_gui_main_window_importable() -> None:
    from gui.main_window import MainWindow

    assert MainWindow is not None


@pyside_only
def test_main_window_prep_tool_widgets_exist_and_hint_is_dismissible(qapp) -> None:  # type: ignore[no-untyped-def]
    from services.project_service import ProjectContext

    fake_ctx = MagicMock(spec=ProjectContext)
    fake_ctx.name = "Existing"
    fake_ctx.raw_folder = Path("/tmp/docs")
    fake_ctx.output_folder = Path("/tmp/out")
    fake_ctx.db_path = Path("/tmp/out/.kiw/state.sqlite3")

    with patch("gui.main_window.ProjectService") as mock_ps_cls:
        mock_service = MagicMock()
        mock_service.try_load_last_project.return_value = fake_ctx
        mock_service.load_project.return_value = fake_ctx
        mock_ps_cls.return_value = mock_service

        from gui.main_window import MainWindow

        win = MainWindow()
        win.show()
        qapp.processEvents()

        assert win._header.prep_tool_btn.text() == "📦 Prep Tool"
        assert "Archive Prep Tool" in win._header.prep_tool_btn.toolTip()
        assert win._queue_tab.prep_hint_frame.isVisible() is True
        assert win._queue_tab.prep_hint_open_btn.text() == "Open Prep Tool"
        assert win._queue_tab.prep_hint_dismiss_btn.text() == "✕"

        win._queue_tab.prep_hint_dismiss_btn.click()
        qapp.processEvents()

        assert win._queue_prep_hint_dismissed is True
        assert win._queue_tab.prep_hint_frame.isVisible() is False
        win.close()
