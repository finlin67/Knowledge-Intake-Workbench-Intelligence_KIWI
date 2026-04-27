"""Smoke tests for gui/setup_wizard.py."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

_HAS_PYSIDE6 = importlib.util.find_spec("PySide6") is not None
pyside_only = pytest.mark.skipif(not _HAS_PYSIDE6, reason="PySide6 not installed")


if _HAS_PYSIDE6:
    import pytest

    @pytest.fixture(scope="session")
    def qapp():
        """Minimal QApplication fixture (replaces pytest-qt when unavailable)."""
        from PySide6.QtWidgets import QApplication
        import sys

        app = QApplication.instance() or QApplication(sys.argv[:1])
        yield app


# ---------------------------------------------------------------------------
# Pure-Python (no Qt) tests — always run
# ---------------------------------------------------------------------------


def test_list_personas_returns_five_entries() -> None:
    from gui.setup_wizard import list_personas

    personas = list_personas()
    assert len(personas) == 5
    keys = {p.key for p in personas}
    assert "marketing_professional" in keys
    assert "developer_engineer" in keys


def test_list_personas_have_required_fields() -> None:
    from gui.setup_wizard import list_personas

    for p in list_personas():
        assert p.key
        assert p.icon
        assert p.name
        assert p.description


def test_apply_persona_defaults_writes_force_rules(tmp_path: Path) -> None:
    """Applying a persona adds keyword rules to the project classification config."""
    from services.project_service import PROJECT_DIR_NAME
    from services.classification_config import (
        DEFAULT_CONFIG_FILENAME,
        write_classification_config_from_seed,
    )
    from gui.setup_wizard import _apply_persona_defaults

    config_dir = tmp_path / PROJECT_DIR_NAME
    config_dir.mkdir()
    config_path = config_dir / DEFAULT_CONFIG_FILENAME
    write_classification_config_from_seed(config_path)

    _apply_persona_defaults(output_folder=tmp_path, persona="marketing_professional")

    raw = json.loads(config_path.read_text(encoding="utf-8"))
    contains_values = {r["contains"].lower() for r in raw.get("FORCE_RULES", [])}
    # Marketing persona must add at least one of its known terms.
    assert any(term in contains_values for term in ("campaign brief", "abm", "pipeline report", "go-to-market"))


def test_apply_persona_defaults_unknown_persona_no_crash(tmp_path: Path) -> None:
    from services.project_service import PROJECT_DIR_NAME
    from services.classification_config import (
        DEFAULT_CONFIG_FILENAME,
        write_classification_config_from_seed,
    )
    from gui.setup_wizard import _apply_persona_defaults

    config_dir = tmp_path / PROJECT_DIR_NAME
    config_dir.mkdir()
    config_path = config_dir / DEFAULT_CONFIG_FILENAME
    write_classification_config_from_seed(config_path)
    # An unknown key must not raise.
    _apply_persona_defaults(output_folder=tmp_path, persona="totally_unknown")


def test_ensure_project_service_persona_api_patches_missing(tmp_path: Path) -> None:
    from gui.setup_wizard import ensure_project_service_persona_api

    service = MagicMock(spec=[])  # no attributes
    assert not hasattr(service, "apply_persona")
    ensure_project_service_persona_api(service)
    assert hasattr(service, "apply_persona")
    # Calling it should not raise even though it's a stub.
    service.apply_persona(output_folder=tmp_path, persona="marketing_professional")


def test_ensure_project_service_persona_api_leaves_existing(tmp_path: Path) -> None:
    from gui.setup_wizard import ensure_project_service_persona_api

    called: list[str] = []

    def _real_apply(*, output_folder: Path, persona: str) -> None:
        called.append(persona)

    service = MagicMock()
    service.apply_persona = _real_apply
    ensure_project_service_persona_api(service)
    service.apply_persona(output_folder=tmp_path, persona="sales_professional")
    assert called == ["sales_professional"]


# ---------------------------------------------------------------------------
# Qt-dependent tests
# ---------------------------------------------------------------------------


@pyside_only
def test_wizard_imports() -> None:
    from gui.setup_wizard import (  # noqa: F401
        SetupWizardDialog,
        SetupWizardResult,
        PersonaCard,
        list_personas,
    )


@pyside_only
def test_wizard_instantiates(qapp) -> None:  # type: ignore[no-untyped-def]
    from gui.setup_wizard import SetupWizardDialog

    service = MagicMock()
    service.create_project.return_value = MagicMock()
    service.apply_persona = MagicMock()

    wizard = SetupWizardDialog(project_service=service)
    assert wizard is not None
    assert wizard.result_data is None
    wizard.close()


@pyside_only
def test_wizard_step_navigation(qapp) -> None:  # type: ignore[no-untyped-def]
    """Back/Next advance and retreat through steps without crashing."""
    from gui.setup_wizard import SetupWizardDialog

    service = MagicMock()
    wizard = SetupWizardDialog(project_service=service)

    # Step 0: welcome
    assert wizard._step == 0
    assert not wizard._back_btn.isEnabled()

    # Advance to step 1
    wizard._set_step(1)
    assert wizard._step == 1
    assert wizard._back_btn.isEnabled()
    assert not wizard._next_btn.isHidden()

    # Advance to step 2 (folders)
    wizard._set_step(2)
    assert wizard._step == 2

    # Retreat
    wizard._go_back()
    assert wizard._step == 1

    wizard.close()


@pyside_only
def test_persona_card_selection(qapp) -> None:  # type: ignore[no-untyped-def]
    from gui.setup_wizard import SetupWizardDialog, list_personas

    service = MagicMock()
    wizard = SetupWizardDialog(project_service=service)
    personas = list_personas()

    # First card is default.
    assert wizard._selected_persona.key == personas[0].key

    # Click a different card.
    wizard._persona_cards[2].setChecked(True)
    wizard._on_persona_selected(personas[2])
    assert wizard._selected_persona.key == personas[2].key

    wizard.close()


@pyside_only
def test_folder_validation_rejects_empty(qapp) -> None:  # type: ignore[no-untyped-def]
    from gui.setup_wizard import SetupWizardDialog

    service = MagicMock()
    wizard = SetupWizardDialog(project_service=service)

    # No paths set yet — validation must fail silently.
    assert not wizard._validate_step_three(show_messages=False)
    wizard.close()


@pyside_only
def test_folder_validation_rejects_same_folder(qapp, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    from gui.setup_wizard import SetupWizardDialog

    service = MagicMock()
    wizard = SetupWizardDialog(project_service=service)
    wizard._docs_path_label.setText(str(tmp_path))
    wizard._out_path_label.setText(str(tmp_path))
    assert not wizard._validate_step_three(show_messages=False)
    wizard.close()


@pyside_only
def test_folder_validation_rejects_output_inside_docs(qapp, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    from gui.setup_wizard import SetupWizardDialog

    service = MagicMock()
    wizard = SetupWizardDialog(project_service=service)
    docs = tmp_path
    output = tmp_path / "output_inside"
    output.mkdir()
    wizard._docs_path_label.setText(str(docs))
    wizard._out_path_label.setText(str(output))
    assert not wizard._validate_step_three(show_messages=False)
    wizard.close()


@pyside_only
def test_folder_validation_passes_valid_pair(qapp, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    from gui.setup_wizard import SetupWizardDialog

    service = MagicMock()
    wizard = SetupWizardDialog(project_service=service)
    docs = tmp_path / "docs"
    docs.mkdir()
    out = tmp_path / "out"
    out.mkdir()
    wizard._docs_path_label.setText(str(docs))
    wizard._out_path_label.setText(str(out))
    assert wizard._validate_step_three(show_messages=False)
    wizard.close()


@pyside_only
def test_project_name_prefilled_on_persona_change(qapp) -> None:  # type: ignore[no-untyped-def]
    from gui.setup_wizard import SetupWizardDialog, list_personas

    service = MagicMock()
    wizard = SetupWizardDialog(project_service=service)
    personas = list_personas()
    wizard._set_step(2)

    # Name should already be prefilled with default persona.
    name = wizard._project_name_edit.text()
    assert personas[0].name in name

    # Switching persona updates the prefilled name.
    wizard._on_persona_selected(personas[3])
    new_name = wizard._project_name_edit.text()
    assert personas[3].name in new_name

    wizard.close()


@pyside_only
def test_ai_section_hidden_by_default(qapp) -> None:  # type: ignore[no-untyped-def]
    from gui.setup_wizard import SetupWizardDialog

    service = MagicMock()
    wizard = SetupWizardDialog(project_service=service)
    wizard._set_step(3)
    # Step 3 may set step=2 if folders aren't valid, so force it directly.
    wizard._stack.setCurrentIndex(3)
    assert not wizard._ai_section.isVisible()
    wizard.close()


@pyside_only
def test_ollama_row_visible_when_selected(qapp) -> None:  # type: ignore[no-untyped-def]
    from gui.setup_wizard import SetupWizardDialog

    service = MagicMock()
    wizard = SetupWizardDialog(project_service=service)
    wizard._radio_ollama.setChecked(True)
    wizard._sync_ai_rows()
    # Use isHidden() since the dialog parent hasn't been shown yet.
    assert not wizard._ollama_row.isHidden()
    assert wizard._claude_row.isHidden()
    assert wizard._openai_row.isHidden()
    wizard.close()


@pyside_only
def test_finish_calls_create_and_apply(qapp, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    """Finish triggers create_project and apply_persona on the injected service."""
    from pathlib import Path as _Path
    from gui.setup_wizard import SetupWizardDialog, list_personas
    from services.project_service import ProjectContext

    docs = tmp_path / "docs"
    docs.mkdir()
    out = tmp_path / "out"
    out.mkdir()

    fake_ctx = ProjectContext(
        name="Test Project",
        raw_folder=docs,
        output_folder=out,
        db_path=out / ".kiw" / "state.sqlite3",
        project_file=out / ".kiw" / "project.json",
    )
    service = MagicMock()
    service.create_project.return_value = fake_ctx
    service.apply_persona = MagicMock()

    wizard = SetupWizardDialog(project_service=service)
    wizard._docs_path_label.setText(str(docs))
    wizard._out_path_label.setText(str(out))
    wizard._project_name_edit.setText("Test Project")
    wizard._radio_skip.setChecked(True)

    wizard._finish()

    service.create_project.assert_called_once()
    service.apply_persona.assert_called_once()
    assert wizard.result_data is not None
    assert wizard.result_data.persona_key == list_personas()[0].key


@pyside_only
def test_main_window_opens_wizard_on_no_last_project(qapp) -> None:  # type: ignore[no-untyped-def]
    """When no last project is found the wizard dialog is invoked."""
    with (
        patch("gui.main_window.ProjectService") as mock_ps_cls,
        patch("gui.main_window.SetupWizardDialog") as mock_wizard_cls,
    ):
        mock_service = MagicMock()
        mock_service.try_load_last_project.return_value = None
        mock_ps_cls.return_value = mock_service

        mock_wizard = MagicMock()
        from PySide6.QtWidgets import QDialog
        mock_wizard.exec.return_value = QDialog.Rejected
        mock_wizard.result_data = None
        mock_wizard_cls.return_value = mock_wizard

        from gui.main_window import MainWindow
        win = MainWindow()

        mock_wizard_cls.assert_called_once()
        win.close()


@pyside_only
def test_main_window_skips_wizard_when_project_loaded(qapp) -> None:  # type: ignore[no-untyped-def]
    """When last project loads, the wizard is never opened."""
    from services.project_service import ProjectContext

    fake_ctx = MagicMock(spec=ProjectContext)
    fake_ctx.name = "Existing"
    fake_ctx.raw_folder = Path("/tmp/docs")
    fake_ctx.output_folder = Path("/tmp/out")
    fake_ctx.db_path = Path("/tmp/out/.kiw/state.sqlite3")

    with (
        patch("gui.main_window.ProjectService") as mock_ps_cls,
        patch("gui.main_window.SetupWizardDialog") as mock_wizard_cls,
    ):
        mock_service = MagicMock()
        mock_service.try_load_last_project.return_value = fake_ctx
        mock_service.load_project.return_value = fake_ctx
        mock_ps_cls.return_value = mock_service

        from gui.main_window import MainWindow
        win = MainWindow()

        mock_wizard_cls.assert_not_called()
        win.close()
