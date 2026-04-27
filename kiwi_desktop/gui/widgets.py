"""Reusable PySide6 widgets for the tabbed desktop shell."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtGui import QResizeEvent, QTextCursor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QGroupBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QTabWidget,
    QTableWidget,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from gui.theme import KIWTheme
from services.exporter_service import PROFILE_ANYTHINGLLM, PROFILE_OPEN_WEBUI
from services.review_service import CATEGORY_OPTIONS, WORKSPACE_OPTIONS


class ToggleSwitch(QPushButton):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setCheckable(True)
        self.setFixedSize(44, 24)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def paintEvent(self, event) -> None:  # type: ignore[override]
        from PySide6.QtGui import QColor, QPainter

        _ = event
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        track_color = QColor("#4a9eff") if self.isChecked() else QColor("#555555")
        p.setBrush(track_color)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(0, 4, 44, 16, 8, 8)
        thumb_x = 22 if self.isChecked() else 2
        p.setBrush(QColor("#ffffff"))
        p.drawEllipse(thumb_x, 2, 20, 20)
        p.end()


class ProjectHeaderWidget(QWidget):
    """Header block — step-by-step layout guiding users from setup through run."""

    __slots__ = (
        "project_name_edit",
        "raw_folder_edit",
        "output_folder_edit",
        "export_profile_combo",
        "simple_mode_check",
        "context_frame",
        "context_dot_label",
        "context_project_label",
        "context_path_label",
        "context_profile_badge",
        "quick_start_btn",
        "create_btn",
        "load_btn",
        "factory_reset_btn",
        "prep_tool_btn",
        "scan_btn",
        "run_btn",
        "run_both_btn",
        "sticky_dual_profiles_check",
        "pause_btn",
        "resume_btn",
        "stop_btn",
        "settings_shortcut_btn",
        "help_btn",
        "_help_dot",
        "setup_quick_toggle_btn",
        "setup_quick_panel",
        "setup_ai_summary_label",
        "setup_categories_summary_label",
        "setup_open_ai_btn",
        "setup_open_categories_btn",
        "setup_refresh_summary_btn",
        "setup_ai_provider_combo",
        "setup_ai_enable_check",
        "setup_ai_model_edit",
        "setup_ai_save_btn",
        "setup_workspace_label_edit",
        "setup_workspace_name_edit",
        "setup_add_workspace_btn",
        "setup_keyword_scope_combo",
        "setup_keyword_edit",
        "setup_keyword_workspace_combo",
        "setup_keyword_subfolder_edit",
        "setup_add_keyword_btn",
    )


    def __init__(
        self,
        *,
        on_browse_raw: Callable[[], None],
        on_browse_output: Callable[[], None],
        on_quick_start: Callable[[], None],
        on_create_project: Callable[[], None],
        on_load_project: Callable[[], None],
        on_factory_reset: Callable[[], None],
        on_scan: Callable[[], None],
        on_run: Callable[[], None],
        on_run_both: Callable[[], None],
        on_pause: Callable[[], None],
        on_resume: Callable[[], None],
        on_stop: Callable[[], None],
        on_open_ai_settings: Callable[[], None],
        on_open_categories_settings: Callable[[], None],
        on_refresh_setup_snapshot: Callable[[], None],
        on_setup_quick_ai_save: Callable[[], None],
        on_setup_quick_add_workspace: Callable[[], None],
        on_setup_quick_add_keyword: Callable[[], None],
        on_simple_mode_changed: Callable[[bool], None],
        on_profile_changed: Callable[[str], None],
    ) -> None:
        super().__init__()

        # ── Create widgets ────────────────────────────────────────────────
        self.project_name_edit = QLineEdit("My Knowledge Project")
        self.project_name_edit.setToolTip(
            "A short name for this project — used to label your output and reload it later."
        )

        self.raw_folder_edit = QLineEdit()
        self.raw_folder_edit.setToolTip(
            "The folder containing the files you want KIWI to read and classify.\n"
            "Tip: for large archives, use the Prep Tool first to split them into batches."
        )

        self.output_folder_edit = QLineEdit()
        self.output_folder_edit.setToolTip(
            "Where KIWI writes organized output (exports, metadata).\n"
            "Choose an empty folder or create a new one — do NOT use your source folder."
        )

        self.export_profile_combo = QComboBox()
        self.export_profile_combo.addItems([PROFILE_ANYTHINGLLM, PROFILE_OPEN_WEBUI])
        self.export_profile_combo.setToolTip(
            "Choose which AI tool you're exporting to:\n"
            "  • AnythingLLM — uploads docs to a local AnythingLLM workspace\n"
            "  • Open WebUI  — formats docs for Open WebUI knowledge bases\n"
            "You can run both profiles on the same batch."
        )
        self.export_profile_combo.currentTextChanged.connect(on_profile_changed)

        self.simple_mode_check = ToggleSwitch()
        self.simple_mode_check.setChecked(False)
        self.simple_mode_check.setToolTip(
            "Simple mode hides advanced tabs (Inventory, Review, Triage, Exports).\n"
            "Toggle to Expert mode to access full controls."
        )
        self.simple_mode_check.toggled.connect(lambda checked: on_simple_mode_changed(not checked))

        # Action buttons
        self.quick_start_btn = QPushButton("✚  Create + Load + Scan")
        self.quick_start_btn.setToolTip(
            "One-click shortcut: creates a new project, loads it, then scans your source folder.\n"
            "Best for starting a fresh batch — all three steps in one go."
        )

        self.create_btn = QPushButton("Create")
        self.create_btn.setToolTip(
            "Create a new KIWI project in your output folder.\n"
            "Sets up the metadata database for the current project name and folders."
        )

        self.load_btn = QPushButton("Load")
        self.load_btn.setToolTip(
            "Load an existing KIWI project from your output folder.\n"
            "Use this to continue a previous session or switch between projects."
        )

        self.scan_btn = QPushButton("Scan Folder")
        self.scan_btn.setToolTip(
            "Scan your source folder and queue any new files for processing.\n"
            "Run this again whenever you add more files to your source folder."
        )

        self.run_btn = QPushButton("▶  Run Queue")
        self.run_btn.setToolTip(
            "Start classifying and exporting queued files using the active profile.\n"
            "You can switch tabs while it runs — check Run Monitor for live progress."
        )

        self.run_both_btn = QPushButton("Run Both Profiles")
        self.run_both_btn.setToolTip(
            "Process the queue for both AnythingLLM and Open WebUI in sequence.\n"
            "Useful when you want to export to both AI tools from a single run."
        )

        self.sticky_dual_profiles_check = QCheckBox("Sticky dual-profile mode")
        self.sticky_dual_profiles_check.setToolTip(
            "When enabled, KIWI will run AnythingLLM then Open WebUI for each batch, "
            "and automatically load the next pending batch when available."
        )
        self.sticky_dual_profiles_check.setStyleSheet("color: #a8a8c8; font-size: 11px;")

        self.pause_btn = QPushButton("Pause")
        self.pause_btn.setToolTip("Pause after the current file finishes. Use Resume to continue.")

        self.resume_btn = QPushButton("Resume")
        self.resume_btn.setToolTip("Resume a paused run from where it left off.")

        self.stop_btn = QPushButton("Stop")
        self.stop_btn.setToolTip(
            "Stop the active run. Progress saved so far is kept.\n"
            "You can re-run or continue later by clicking Run Queue again."
        )

        self.factory_reset_btn = QPushButton("🗑  Factory Reset")
        self.factory_reset_btn.setToolTip(
            "⚠ Permanently deletes all KIWI output for this project:\n"
            "  .kiw (metadata & database), exports, and normalized folders.\n\n"
            "Your original source files are NOT touched.\n"
            "You will be asked to type RESET to confirm."
        )
        self.factory_reset_btn.setVisible(False)

        self.prep_tool_btn = QPushButton("📦 Prep Tool")
        self.prep_tool_btn.setToolTip(
            "Open the Archive Prep Tool — split a large folder of files into\n"
            "smaller batches before scanning with KIWI.\n"
            "Recommended for archives with 500+ files."
        )

        self.settings_shortcut_btn = QPushButton("⚙  Open Settings")
        self.settings_shortcut_btn.setToolTip(
            "Open project settings to configure:\n"
            "  • Workspaces (top-level output folders)\n"
            "  • Keyword & company routing rules\n"
            "  • AI classification model preferences"
        )

        # ── Per-button visual hierarchy ───────────────────────────────────
        self.quick_start_btn.setStyleSheet(
            "QPushButton {"
            "  background-color: #4a7fff; color: #ffffff; font-weight: bold;"
            "  font-size: 13px; min-height: 38px; border-radius: 5px; border: none;"
            "  padding: 0 12px;"
            "}"
            "QPushButton:hover { background-color: #6090ff; }"
            "QPushButton:pressed { background-color: #3a6fe8; }"
        )
        self.scan_btn.setStyleSheet(
            "QPushButton {"
            "  background-color: #2d6a4f; color: #a8d8c0;"
            "  font-size: 12px; font-weight: bold;"
            "  min-height: 34px; border-radius: 5px; border: none;"
            "}"
            "QPushButton:hover { background-color: #3a8a65; }"
        )
        self.run_btn.setStyleSheet(
            "QPushButton {"
            "  background-color: #2d2d3d; color: #c0c0d8;"
            "  font-size: 12px; font-weight: bold;"
            "  border: 1px solid #4a7fff;"
            "  min-height: 34px; border-radius: 5px;"
            "}"
            "QPushButton:hover { background-color: #35354a; }"
        )
        self.run_both_btn.setStyleSheet(
            "QPushButton {"
            "  background-color: #2d2d3d; color: #c0c0d8;"
            "  font-size: 12px; font-weight: bold;"
            "  border: 1px solid #35354a;"
            "  min-height: 34px; border-radius: 5px;"
            "}"
            "QPushButton:hover { background-color: #35354a; }"
        )
        for _btn in (self.create_btn, self.load_btn):
            _btn.setStyleSheet(
                "QPushButton {"
                "  background-color: #222230; color: #8888a8;"
                "  border: 1px solid #35354a; min-height: 32px; border-radius: 5px;"
                "}"
                "QPushButton:hover { color: #c0c0d8; }"
            )
        self.settings_shortcut_btn.setStyleSheet(
            "QPushButton {"
            "  background-color: #222230; color: #4a7fff;"
            "  font-size: 12px;"
            "  border: 1px solid #35354a; min-height: 34px; border-radius: 5px;"
            "}"
            "QPushButton:hover { background-color: #2a2a3d; }"
        )
        self.prep_tool_btn.setStyleSheet(
            "QPushButton {"
            "  background-color: #222230; color: #8888a8;"
            "  border: 1px solid #35354a; min-height: 34px; border-radius: 5px;"
            "}"
            "QPushButton:hover { color: #c0c0d8; }"
        )
        self.pause_btn.setStyleSheet(
            "QPushButton {"
            "  background-color: #3d3010; color: #c89a20;"
            "  font-size: 12px; font-weight: bold;"
            "  border: 1px solid #c89a20; min-height: 34px; border-radius: 5px;"
            "}"
            "QPushButton:hover { background-color: #4a3b14; }"
        )
        self.resume_btn.setStyleSheet(
            "QPushButton {"
            "  background-color: #1a3328; color: #3a9e6e;"
            "  font-size: 12px; font-weight: bold;"
            "  border: 1px solid #3a9e6e; min-height: 34px; border-radius: 5px;"
            "}"
            "QPushButton:hover { background-color: #1f3f30; }"
        )
        self.stop_btn.setStyleSheet(
            "QPushButton {"
            "  background-color: #2d1818; color: #b84040;"
            "  font-size: 12px; font-weight: bold;"
            "  border: 1px solid #b84040; min-height: 34px; border-radius: 5px;"
            "}"
            "QPushButton:hover { background-color: #3a1e1e; }"
        )
        self.help_btn = QPushButton("? Help")
        self.help_btn.setFixedHeight(28)
        self.help_btn.setMinimumWidth(72)
        self.help_btn.setToolTip("Open help — quick start guide, FAQ, and glossary")
        self.help_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.help_btn.setStyleSheet(
            "QPushButton {"
            "  background: rgba(74, 127, 255, 0.15); color: #4a7fff;"
            "  border: 1px solid #4a7fff; border-radius: 5px;"
            "  font-size: 12px; font-weight: bold; padding: 0 12px;"
            "}"
            "QPushButton:hover {"
            "  background: rgba(74, 127, 255, 0.28); color: #7ab0ff;"
            "}"
            "QPushButton:pressed { background: rgba(74, 127, 255, 0.4); }"
        )

        self._help_dot = QLabel("●")
        self._help_dot.setStyleSheet("color: #4a7fff; font-size: 8px; background: transparent;")

        self.setup_quick_toggle_btn = QToolButton()
        self.setup_quick_toggle_btn.setText("Quick checks: AI + Keywords + Workspaces")
        self.setup_quick_toggle_btn.setCheckable(True)
        self.setup_quick_toggle_btn.setChecked(False)
        self.setup_quick_toggle_btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.setup_quick_toggle_btn.setArrowType(Qt.RightArrow)
        self.setup_quick_toggle_btn.setStyleSheet(
            "QToolButton {"
            "  color: #c0c0d8;"
            "  background-color: #1a1a28;"
            "  border: 1px solid #35354a;"
            "  border-radius: 4px;"
            "  min-height: 30px;"
            "  padding: 0 8px;"
            "  text-align: left;"
            "}"
            "QToolButton:hover { background-color: #222236; }"
        )
        self.setup_quick_panel = QFrame()
        self.setup_quick_panel.setStyleSheet(
            "QFrame {"
            "  background-color: #1a1a28;"
            "  border: 1px solid #35354a;"
            "  border-radius: 5px;"
            "}"
        )
        quick_layout = QVBoxLayout(self.setup_quick_panel)
        quick_layout.setContentsMargins(10, 8, 10, 8)
        quick_layout.setSpacing(6)
        quick_hint = QLabel(
            "Confirm your AI model and routing setup without leaving Setup."
        )
        quick_hint.setWordWrap(True)
        quick_hint.setStyleSheet("color: #8888a8; font-size: 11px;")
        quick_layout.addWidget(quick_hint)

        quick_ai_title = QLabel("Quick edit: AI setup")
        quick_ai_title.setStyleSheet("color: #4a7fff; font-size: 11px; font-weight: bold;")
        quick_layout.addWidget(quick_ai_title)

        ai_edit_row = QHBoxLayout()
        ai_edit_row.setSpacing(6)
        self.setup_ai_provider_combo = QComboBox()
        self.setup_ai_provider_combo.addItems(["ollama", "claude", "openai"])
        self.setup_ai_provider_combo.setToolTip("AI provider used by classification.")
        self.setup_ai_enable_check = QCheckBox("Enable Ollama")
        self.setup_ai_enable_check.setToolTip("When provider is Ollama, this enables/disables Ollama use.")
        self.setup_ai_model_edit = QLineEdit()
        self.setup_ai_model_edit.setPlaceholderText("Model (example: llama3.2:3b or gpt-4o)")
        self.setup_ai_model_edit.setToolTip("Model name for selected provider.")
        self.setup_ai_save_btn = QPushButton("Save AI")
        self.setup_ai_save_btn.setToolTip("Apply AI provider/model changes immediately.")
        self.setup_ai_save_btn.setStyleSheet(
            "QPushButton {"
            "  background-color: #222230; color: #4a7fff;"
            "  border: 1px solid #35354a; min-height: 28px; border-radius: 5px;"
            "  padding: 0 10px;"
            "}"
            "QPushButton:hover { background-color: #2a2a3d; }"
        )
        ai_edit_row.addWidget(self.setup_ai_provider_combo)
        ai_edit_row.addWidget(self.setup_ai_enable_check)
        ai_edit_row.addWidget(self.setup_ai_model_edit, 1)
        ai_edit_row.addWidget(self.setup_ai_save_btn)
        quick_layout.addLayout(ai_edit_row)

        quick_categories_title = QLabel("Quick edit: Workspaces + Keywords")
        quick_categories_title.setStyleSheet("color: #4a7fff; font-size: 11px; font-weight: bold;")
        quick_layout.addWidget(quick_categories_title)

        ws_edit_row = QHBoxLayout()
        ws_edit_row.setSpacing(6)
        self.setup_workspace_label_edit = QLineEdit()
        self.setup_workspace_label_edit.setPlaceholderText("Workspace label")
        self.setup_workspace_name_edit = QLineEdit()
        self.setup_workspace_name_edit.setPlaceholderText("Folder name")
        self.setup_add_workspace_btn = QPushButton("Add Workspace")
        self.setup_add_workspace_btn.setToolTip("Create a new workspace entry.")
        self.setup_add_workspace_btn.setStyleSheet(
            "QPushButton {"
            "  background-color: #222230; color: #4a7fff;"
            "  border: 1px solid #35354a; min-height: 28px; border-radius: 5px;"
            "  padding: 0 10px;"
            "}"
            "QPushButton:hover { background-color: #2a2a3d; }"
        )
        ws_edit_row.addWidget(self.setup_workspace_label_edit)
        ws_edit_row.addWidget(self.setup_workspace_name_edit)
        ws_edit_row.addWidget(self.setup_add_workspace_btn)
        quick_layout.addLayout(ws_edit_row)

        kw_edit_row = QHBoxLayout()
        kw_edit_row.setSpacing(6)
        self.setup_keyword_scope_combo = QComboBox()
        self.setup_keyword_scope_combo.addItems(["Company", "Project", "Force Rule"])
        self.setup_keyword_scope_combo.setToolTip("Where this keyword should be added.")
        self.setup_keyword_edit = QLineEdit()
        self.setup_keyword_edit.setPlaceholderText("Keyword or phrase")
        self.setup_keyword_workspace_combo = QComboBox()
        self.setup_keyword_workspace_combo.setMinimumWidth(150)
        self.setup_keyword_subfolder_edit = QLineEdit()
        self.setup_keyword_subfolder_edit.setPlaceholderText("Subfolder (Force Rule only)")
        self.setup_add_keyword_btn = QPushButton("Add Keyword")
        self.setup_add_keyword_btn.setToolTip("Add a company/project keyword or force rule.")
        self.setup_add_keyword_btn.setStyleSheet(
            "QPushButton {"
            "  background-color: #222230; color: #4a7fff;"
            "  border: 1px solid #35354a; min-height: 28px; border-radius: 5px;"
            "  padding: 0 10px;"
            "}"
            "QPushButton:hover { background-color: #2a2a3d; }"
        )
        kw_edit_row.addWidget(self.setup_keyword_scope_combo)
        kw_edit_row.addWidget(self.setup_keyword_edit, 1)
        kw_edit_row.addWidget(self.setup_keyword_workspace_combo)
        kw_edit_row.addWidget(self.setup_keyword_subfolder_edit)
        kw_edit_row.addWidget(self.setup_add_keyword_btn)
        quick_layout.addLayout(kw_edit_row)

        ai_row = QHBoxLayout()
        ai_row.setSpacing(8)
        self.setup_ai_summary_label = QLabel("AI: no project loaded")
        self.setup_ai_summary_label.setWordWrap(True)
        self.setup_ai_summary_label.setStyleSheet("color: #c0c0d8; font-size: 11px;")
        self.setup_open_ai_btn = QPushButton("Open AI Settings")
        self.setup_open_ai_btn.setToolTip("Jump to Settings and focus AI model setup.")
        self.setup_open_ai_btn.setStyleSheet(
            "QPushButton {"
            "  background-color: #222230; color: #4a7fff;"
            "  border: 1px solid #35354a; min-height: 28px; border-radius: 5px;"
            "  padding: 0 10px;"
            "}"
            "QPushButton:hover { background-color: #2a2a3d; }"
        )
        ai_row.addWidget(self.setup_ai_summary_label, 1)
        ai_row.addWidget(self.setup_open_ai_btn)
        quick_layout.addLayout(ai_row)

        cat_row = QHBoxLayout()
        cat_row.setSpacing(8)
        self.setup_categories_summary_label = QLabel("Routing: no project loaded")
        self.setup_categories_summary_label.setWordWrap(True)
        self.setup_categories_summary_label.setStyleSheet("color: #c0c0d8; font-size: 11px;")
        self.setup_open_categories_btn = QPushButton("Open Keyword/Workspace Settings")
        self.setup_open_categories_btn.setToolTip(
            "Jump to Settings and focus Workspaces, Companies, Projects, and Rules."
        )
        self.setup_open_categories_btn.setStyleSheet(
            "QPushButton {"
            "  background-color: #222230; color: #4a7fff;"
            "  border: 1px solid #35354a; min-height: 28px; border-radius: 5px;"
            "  padding: 0 10px;"
            "}"
            "QPushButton:hover { background-color: #2a2a3d; }"
        )
        cat_row.addWidget(self.setup_categories_summary_label, 1)
        cat_row.addWidget(self.setup_open_categories_btn)
        quick_layout.addLayout(cat_row)

        refresh_row = QHBoxLayout()
        refresh_row.setSpacing(8)
        self.setup_refresh_summary_btn = QPushButton("Refresh quick checks")
        self.setup_refresh_summary_btn.setStyleSheet(
            "QPushButton {"
            "  background-color: #222230; color: #8888a8;"
            "  border: 1px solid #35354a; min-height: 28px; border-radius: 5px;"
            "  padding: 0 10px;"
            "}"
            "QPushButton:hover { color: #c0c0d8; }"
        )
        refresh_row.addWidget(self.setup_refresh_summary_btn)
        refresh_row.addStretch(1)
        quick_layout.addLayout(refresh_row)
        self.setup_quick_panel.setVisible(False)

        def _toggle_setup_quick(expanded: bool) -> None:
            self.setup_quick_toggle_btn.setArrowType(Qt.DownArrow if expanded else Qt.RightArrow)
            self.setup_quick_panel.setVisible(expanded)

        self.setup_quick_toggle_btn.toggled.connect(_toggle_setup_quick)

        def _sync_setup_ai_quick_fields() -> None:
            is_ollama = self.setup_ai_provider_combo.currentText().strip().lower() == "ollama"
            self.setup_ai_enable_check.setVisible(is_ollama)
            if is_ollama:
                self.setup_ai_model_edit.setPlaceholderText("Ollama model (example: llama3.2:3b)")
            else:
                self.setup_ai_model_edit.setPlaceholderText("Cloud model (example: claude-sonnet-4-5, gpt-4o)")

        def _sync_setup_keyword_quick_fields() -> None:
            is_force_rule = self.setup_keyword_scope_combo.currentText() == "Force Rule"
            self.setup_keyword_subfolder_edit.setVisible(is_force_rule)

        self.setup_ai_provider_combo.currentTextChanged.connect(
            lambda _text: _sync_setup_ai_quick_fields()
        )
        self.setup_keyword_scope_combo.currentTextChanged.connect(
            lambda _text: _sync_setup_keyword_quick_fields()
        )

        _sync_setup_ai_quick_fields()
        _sync_setup_keyword_quick_fields()

        self.setup_open_ai_btn.clicked.connect(on_open_ai_settings)
        self.setup_open_categories_btn.clicked.connect(on_open_categories_settings)
        self.setup_refresh_summary_btn.clicked.connect(on_refresh_setup_snapshot)
        self.setup_ai_save_btn.clicked.connect(on_setup_quick_ai_save)
        self.setup_add_workspace_btn.clicked.connect(on_setup_quick_add_workspace)
        self.setup_add_keyword_btn.clicked.connect(on_setup_quick_add_keyword)

        self.factory_reset_btn.setProperty("class", "btn-danger")
        for _field in (
            self.project_name_edit, self.raw_folder_edit,
            self.output_folder_edit, self.export_profile_combo,
        ):
            _field.setMinimumHeight(32)
            _field.setStyleSheet(
                "background-color: #1a1a28; border: 1px solid #35354a;"
                " border-radius: 4px; color: #c0c0d8; padding: 0 8px;"
            )

        # Wire callbacks
        self.quick_start_btn.clicked.connect(on_quick_start)
        self.create_btn.clicked.connect(on_create_project)
        self.load_btn.clicked.connect(on_load_project)
        self.scan_btn.clicked.connect(on_scan)
        self.run_btn.clicked.connect(on_run)
        self.run_both_btn.clicked.connect(on_run_both)
        self.pause_btn.clicked.connect(on_pause)
        self.resume_btn.clicked.connect(on_resume)
        self.stop_btn.clicked.connect(on_stop)
        self.factory_reset_btn.clicked.connect(on_factory_reset)

        # ── Build layout ──────────────────────────────────────────────────
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 8, 12, 8)
        main_layout.setSpacing(8)
        self.setMinimumHeight(260)

        # Top row: Step 1 (wide) + Step 2 (narrow)
        top_row = QHBoxLayout()
        top_row.setSpacing(10)

        step1_card, s1 = self._build_step_panel(
            "step1_card", "step1_header", "📁",
            "STEP 1 — WHAT DO YOU WANT TO CLASSIFY?",
        )
        s1.addLayout(self._labeled_field("Project Name", self.project_name_edit))
        s1.addLayout(self._labeled_field(
            "Source Folder  (files to classify)",
            self._row_with_browse(self.raw_folder_edit, on_browse_raw),
        ))
        s1.addLayout(self._labeled_field(
            "Output Folder  (where results are saved)",
            self._row_with_browse(self.output_folder_edit, on_browse_output),
        ))

        step2_card, s2 = self._build_step_panel(
            "step2_card", "step2_header", "⚙",
            "STEP 2 — DEFINE YOUR ARCHIVE",
        )
        step2_desc = QLabel(
            "Configure how KIWI sorts your files.\n"
            "Set up workspaces, keyword rules,\n"
            "and your AI classification model."
        )
        step2_desc.setWordWrap(True)
        step2_desc.setStyleSheet("color: #8888a8; font-size: 11px;")
        step2_desc.setMinimumHeight(48)
        s2.addWidget(step2_desc)
        s2.addStretch(1)
        s2.addWidget(self.settings_shortcut_btn)
        s2.addWidget(self.prep_tool_btn)
        s2.addWidget(self.setup_quick_toggle_btn)
        s2.addWidget(self.setup_quick_panel)
        help_row = QHBoxLayout()
        help_row.setSpacing(6)
        help_row.addWidget(self.help_btn)
        help_row.addWidget(self._help_dot)
        help_row.addStretch()
        s2.addLayout(help_row)

        top_row.addWidget(step1_card, 3)
        top_row.addWidget(step2_card, 2)
        main_layout.addLayout(top_row)

        # Bottom row: Step 3 (wide) + Step 4 (narrow)
        bot_row = QHBoxLayout()
        bot_row.setSpacing(10)

        step3_card, s3 = self._build_step_panel(
            "step3_card", "step3_header", "▶",
            "STEP 3 — CREATE & RUN",
        )
        profile_row = QHBoxLayout()
        profile_row.setSpacing(8)
        profile_lbl = QLabel("Export Profile:")
        profile_lbl.setStyleSheet("color: #8888a8; font-size: 11px;")
        profile_row.addWidget(profile_lbl)
        profile_row.addWidget(self.export_profile_combo)
        profile_row.addStretch(1)
        s3.addLayout(profile_row)

        qs_row = QHBoxLayout()
        qs_row.setSpacing(6)
        qs_row.addWidget(self.quick_start_btn, 1)
        qs_sep = QFrame()
        qs_sep.setFrameShape(QFrame.VLine)
        qs_sep.setFrameShadow(QFrame.Sunken)
        qs_row.addWidget(qs_sep)
        qs_row.addWidget(self.create_btn)
        qs_row.addWidget(self.load_btn)
        qs_row.addWidget(self.scan_btn)
        s3.addLayout(qs_row)

        run_row = QHBoxLayout()
        run_row.setSpacing(6)
        run_row.addWidget(self.run_btn)
        run_row.addWidget(self.run_both_btn)
        run_row.addWidget(self.sticky_dual_profiles_check)
        run_row.addStretch(1)
        s3.addLayout(run_row)

        step4_card, s4 = self._build_step_panel(
            "step4_card", "step4_header", "📊",
            "STEP 4 — MONITOR & CONTROL",
        )
        ctrl_row = QHBoxLayout()
        ctrl_row.setSpacing(6)
        ctrl_row.addWidget(self.pause_btn)
        ctrl_row.addWidget(self.resume_btn)
        ctrl_row.addWidget(self.stop_btn)
        s4.addLayout(ctrl_row)

        step4_hint = QLabel(
            "Track progress in the\nQueue and Run Monitor tabs.\n"
            "Use Triage for items needing review."
        )
        step4_hint.setWordWrap(True)
        step4_hint.setStyleSheet("color: #8888a8; font-size: 11px;")
        s4.addWidget(step4_hint)
        s4.addStretch(1)
        s4.addWidget(self.factory_reset_btn)

        bot_row.addWidget(step3_card, 3)
        bot_row.addWidget(step4_card, 2)
        main_layout.addLayout(bot_row)

        # ── Context / status bar ──────────────────────────────────────────
        status_sep = QFrame()
        status_sep.setFrameShape(QFrame.Shape.HLine)
        status_sep.setStyleSheet("background: #28283a; max-height: 1px;")
        main_layout.addWidget(status_sep)

        self.context_frame = QFrame()
        self.context_frame.setProperty("class", "context-status")
        self.context_frame.setFrameShape(QFrame.StyledPanel)
        self.context_frame.setStyleSheet("QFrame { background-color: #1a1a22; border: none; }")
        context_row = QHBoxLayout(self.context_frame)
        context_row.setContentsMargins(12, 4, 12, 4)
        context_row.setSpacing(8)

        self.context_dot_label = QLabel("●")
        self.context_dot_label.setStyleSheet("font-size: 10px; color: #c89a20;")
        self.context_project_label = QLabel("No project loaded")
        self.context_project_label.setStyleSheet(
            "font-weight: bold; color: #c0c0d8; font-size: 12px;"
        )
        ctx_sep = QFrame()
        ctx_sep.setFrameShape(QFrame.VLine)
        ctx_sep.setFrameShadow(QFrame.Sunken)
        ctx_sep.setStyleSheet("color: #35354a;")
        self.context_path_label = QLabel("Source: --")
        self.context_path_label.setStyleSheet("color: #5a5a7a; font-size: 11px;")
        self.context_profile_badge = QLabel(self.export_profile_combo.currentText())
        self.context_profile_badge.setStyleSheet(
            "padding: 2px 10px; border-radius: 10px;"
            " background-color: #1e2d4a; color: #4a7fff;"
            " border: 1px solid #2d3d5a; font-size: 11px;"
        )

        # Light/dark theme toggle (🌙 = dark / ☀️ = light)
        theme_toggle = ToggleSwitch()
        theme_toggle.setObjectName("theme_toggle")
        theme_toggle.setToolTip("Toggle light/dark mode")
        moon_lbl = QLabel("🌙")
        moon_lbl.setStyleSheet("font-size: 13px; color: #686888; background: transparent;")
        sun_lbl = QLabel("☀️")
        sun_lbl.setStyleSheet("font-size: 13px; color: #686888; background: transparent;")

        mode_simple_lbl = QLabel("Simple")
        mode_simple_lbl.setStyleSheet("color: #686888; font-size: 11px;")
        mode_expert_lbl = QLabel("Expert")
        mode_expert_lbl.setStyleSheet("color: #686888; font-size: 11px;")

        context_row.addWidget(self.context_dot_label)
        context_row.addWidget(self.context_project_label)
        context_row.addWidget(ctx_sep)
        context_row.addWidget(self.context_path_label, 1)
        context_row.addWidget(self.context_profile_badge)
        context_row.addSpacing(12)
        context_row.addWidget(moon_lbl)
        context_row.addWidget(theme_toggle)
        context_row.addWidget(sun_lbl)
        context_row.addSpacing(8)
        context_row.addWidget(mode_simple_lbl)
        context_row.addWidget(self.simple_mode_check)
        context_row.addWidget(mode_expert_lbl)
        main_layout.addWidget(self.context_frame)

    def set_setup_snapshot(self, *, ai_summary: str, categories_summary: str) -> None:
        self.setup_ai_summary_label.setText(ai_summary or "AI: unavailable")
        self.setup_categories_summary_label.setText(categories_summary or "Routing: unavailable")

    def set_setup_quick_editor_state(
        self,
        *,
        provider: str,
        ollama_enabled: bool,
        model_name: str,
        workspace_options: tuple[str, ...],
    ) -> None:
        self.setup_ai_provider_combo.blockSignals(True)
        self.setup_ai_provider_combo.setCurrentText(provider or "ollama")
        self.setup_ai_provider_combo.blockSignals(False)
        self.setup_ai_enable_check.setChecked(ollama_enabled)
        self.setup_ai_model_edit.setText(model_name)

        current_ws = self.setup_keyword_workspace_combo.currentText().strip()
        self.setup_keyword_workspace_combo.blockSignals(True)
        self.setup_keyword_workspace_combo.clear()
        self.setup_keyword_workspace_combo.addItems(list(workspace_options))
        if current_ws and current_ws in workspace_options:
            self.setup_keyword_workspace_combo.setCurrentText(current_ws)
        elif workspace_options:
            self.setup_keyword_workspace_combo.setCurrentIndex(0)
        self.setup_keyword_workspace_combo.blockSignals(False)

        is_ollama = self.setup_ai_provider_combo.currentText().strip().lower() == "ollama"
        self.setup_ai_enable_check.setVisible(is_ollama)

    def set_context_status(
        self,
        *,
        level: str,
        project_name: str,
        raw_folder_tail: str,
        export_profile: str,
    ) -> None:
        colors = {
            "ok": "#3a9e6e",
            "warning": "#c89a20",
            "error": "#b84040",
        }
        dot_color = colors.get(level, "#c89a20")
        self.context_dot_label.setStyleSheet(f"font-size: 10px; color: {dot_color};")
        self.context_project_label.setText(project_name or "No project loaded")
        self.context_path_label.setText(raw_folder_tail or "Raw: --")
        self.context_profile_badge.setText(export_profile)

    @staticmethod
    def _build_step_panel(
        card_name: str,
        header_name: str,
        icon: str,
        title: str,
    ) -> tuple[QGroupBox, QVBoxLayout]:
        """Create a neutral step card: dark header bar + dark body, uniform across all steps."""
        card = QGroupBox()
        card.setTitle("")
        card.setObjectName(card_name)
        card.setStyleSheet(
            f"QGroupBox#{card_name} {{"
            f"  border: 1px solid #35354a;"
            f"  border-radius: 6px;"
            f"  background-color: #1e1e2a;"
            f"  padding: 0px;"
            f"  margin: 0px;"
            f"}}"
        )
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(0)

        header = QFrame()
        header.setObjectName(header_name)
        header.setFixedHeight(34)
        header.setStyleSheet(
            f"QFrame#{header_name} {{"
            f"  background-color: #2a2a38;"
            f"  border-radius: 5px 5px 0px 0px;"
            f"  border-bottom: 1px solid #35354a;"
            f"}}"
        )
        header_row = QHBoxLayout(header)
        header_row.setContentsMargins(10, 0, 10, 0)
        icon_lbl = QLabel(icon)
        icon_lbl.setStyleSheet(
            "color: #4a7fff; font-size: 14px; background: transparent; border: none;"
        )
        title_lbl = QLabel(title)
        title_lbl.setStyleSheet(
            "color: #c8c8e0; font-size: 11px; font-weight: bold;"
            " letter-spacing: 0.08em; background: transparent; border: none;"
        )
        header_row.addWidget(icon_lbl)
        header_row.addSpacing(6)
        header_row.addWidget(title_lbl)
        header_row.addStretch(1)
        card_layout.addWidget(header)

        content = QWidget()
        content.setObjectName(f"{card_name}_content")
        content.setStyleSheet(
            f"QWidget#{card_name}_content {{"
            f"  background-color: #1e1e2a;"
            f"  border-radius: 0px 0px 5px 5px;"
            f"}}"
        )
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(14, 14, 14, 14)
        content_layout.setSpacing(8)
        card_layout.addWidget(content, 1)

        return card, content_layout

    def refresh_theme(self) -> None:
        """Update step card colors when the theme changes."""
        c = KIWTheme.colors()
        for card_name in ("step1_card", "step2_card", "step3_card", "step4_card"):
            card = self.findChild(QGroupBox, card_name)
            if card:
                card.setStyleSheet(
                    f"QGroupBox#{card_name} {{"
                    f"  border: 1px solid {c['border']};"
                    f"  border-radius: 6px;"
                    f"  background-color: {c['step_card_bg']};"
                    f"  padding: 0px; margin: 0px;"
                    f"}}"
                )
            content = self.findChild(QWidget, f"{card_name}_content")
            if content:
                content.setStyleSheet(
                    f"QWidget#{card_name}_content {{"
                    f"  background-color: {c['step_card_bg']};"
                    f"  border-radius: 0px 0px 5px 5px;"
                    f"}}"
                )

    @staticmethod
    def _labeled_field(label_text: str, field_widget: QWidget) -> QVBoxLayout:
        block = QVBoxLayout()
        block.setSpacing(2)
        label = QLabel(label_text)
        label.setStyleSheet("font-size: 10px; color: #686888; margin-bottom: 2px;")
        block.addWidget(label)
        block.addWidget(field_widget)
        return block

    @staticmethod
    def _row_with_browse(edit: QLineEdit, browse_cb: Callable[[], None]) -> QWidget:
        row_widget = QWidget()
        row = QHBoxLayout(row_widget)
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(edit, 1)
        btn = QPushButton("Browse")
        btn.setToolTip("Open a folder picker dialog.")
        btn.clicked.connect(browse_cb)
        row.addWidget(btn)
        return row_widget


class InventoryTabWidget(QWidget):
    """Inventory table, filters, classification columns, and bulk actions."""

    __slots__ = (
        "filter_mode_combo",
        "workspace_filter_combo",
        "matched_by_filter_combo",
        "review_help_label",
        "table",
        "category_combo",
        "workspace_combo",
        "apply_btn",
        "assign_career_btn",
        "assign_ai_btn",
        "assign_archive_btn",
        "assign_wiki_btn",
        "auto_assign_btn",
        "bulk_workspace_combo",
        "bulk_subfolder_edit",
        "bulk_assign_workspace_btn",
        "bulk_assign_subfolder_btn",
        "mark_review_resolved_btn",
        "refresh_btn",
    )

    def __init__(
        self,
        *,
        on_apply: Callable[[], None],
        on_assign_career: Callable[[], None],
        on_assign_ai: Callable[[], None],
        on_assign_archive: Callable[[], None],
        on_assign_wiki: Callable[[], None],
        on_auto_assign: Callable[[], None],
        on_bulk_assign_workspace: Callable[[], None],
        on_bulk_assign_subfolder: Callable[[], None],
        on_mark_review_resolved: Callable[[], None],
        on_refresh: Callable[[], None],
        on_filter_changed: Callable[[], None],
    ) -> None:
        super().__init__()
        layout = QVBoxLayout(self)

        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("Show"))
        self.filter_mode_combo = QComboBox()
        self.filter_mode_combo.addItems(
            ["All", "Needs review", "Failed", "Workspace", "Matched By"]
        )
        self.filter_mode_combo.currentIndexChanged.connect(on_filter_changed)
        filter_row.addWidget(self.filter_mode_combo)
        filter_row.addWidget(QLabel("Workspace"))
        self.workspace_filter_combo = QComboBox()
        self.workspace_filter_combo.setMinimumWidth(200)
        self.workspace_filter_combo.currentIndexChanged.connect(on_filter_changed)
        filter_row.addWidget(self.workspace_filter_combo)
        filter_row.addWidget(QLabel("Matched By"))
        self.matched_by_filter_combo = QComboBox()
        self.matched_by_filter_combo.setMinimumWidth(200)
        self.matched_by_filter_combo.currentIndexChanged.connect(on_filter_changed)
        filter_row.addWidget(self.matched_by_filter_combo)
        filter_row.addStretch(1)
        layout.addLayout(filter_row)
        self.review_help_label = QLabel(
            "Needs review: review_required=1 (fallback, confidence below threshold, broad-only map hit, "
            "or risky keyword). Use filter \"Needs review\" to list those rows."
        )
        layout.addWidget(self.review_help_label)

        self.table = QTableWidget(0, 11)
        self.table.setHorizontalHeaderLabels(
            [
                "File Name",
                "Type",
                "Size",
                "Status",
                "Category",
                "Workspace",
                "Subfolder",
                "Matched By",
                "Confidence",
                "Review Required",
                "Classification Reason",
            ]
        )
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        layout.addWidget(self.table)

        override_row = QHBoxLayout()
        self.category_combo = QComboBox()
        self.category_combo.addItems(list(CATEGORY_OPTIONS))
        self.workspace_combo = QComboBox()
        self.workspace_combo.addItems(list(WORKSPACE_OPTIONS))
        self.apply_btn = QPushButton("Apply to Selected Rows")
        self.apply_btn.clicked.connect(on_apply)
        override_row.addWidget(QLabel("Category"))
        override_row.addWidget(self.category_combo)
        override_row.addWidget(QLabel("Workspace"))
        override_row.addWidget(self.workspace_combo)
        override_row.addWidget(self.apply_btn)
        layout.addLayout(override_row)

        bulk_row = QHBoxLayout()
        self.assign_career_btn = QPushButton("Assign to Career Portfolio")
        self.assign_ai_btn = QPushButton("Assign to AI Projects")
        self.assign_archive_btn = QPushButton("Assign to Archive")
        self.assign_wiki_btn = QPushButton("Assign to Wiki")
        self.auto_assign_btn = QPushButton("Auto Assign Workspaces")
        self.assign_career_btn.clicked.connect(on_assign_career)
        self.assign_ai_btn.clicked.connect(on_assign_ai)
        self.assign_archive_btn.clicked.connect(on_assign_archive)
        self.assign_wiki_btn.clicked.connect(on_assign_wiki)
        self.auto_assign_btn.clicked.connect(on_auto_assign)
        bulk_row.addWidget(self.assign_career_btn)
        bulk_row.addWidget(self.assign_ai_btn)
        bulk_row.addWidget(self.assign_archive_btn)
        bulk_row.addWidget(self.assign_wiki_btn)
        bulk_row.addWidget(self.auto_assign_btn)
        layout.addLayout(bulk_row)

        bulk2 = QHBoxLayout()
        self.bulk_workspace_combo = QComboBox()
        self.bulk_workspace_combo.addItems(list(WORKSPACE_OPTIONS))
        self.bulk_assign_workspace_btn = QPushButton("Assign Workspace")
        self.bulk_assign_workspace_btn.clicked.connect(on_bulk_assign_workspace)
        self.bulk_subfolder_edit = QLineEdit()
        self.bulk_subfolder_edit.setPlaceholderText("subfolder (optional)")
        self.bulk_assign_subfolder_btn = QPushButton("Assign Subfolder")
        self.bulk_assign_subfolder_btn.clicked.connect(on_bulk_assign_subfolder)
        self.mark_review_resolved_btn = QPushButton("Mark Review Resolved")
        self.mark_review_resolved_btn.clicked.connect(on_mark_review_resolved)
        bulk2.addWidget(QLabel("Workspace"))
        bulk2.addWidget(self.bulk_workspace_combo)
        bulk2.addWidget(self.bulk_assign_workspace_btn)
        bulk2.addWidget(QLabel("Subfolder"))
        bulk2.addWidget(self.bulk_subfolder_edit, 1)
        bulk2.addWidget(self.bulk_assign_subfolder_btn)
        bulk2.addWidget(self.mark_review_resolved_btn)
        layout.addLayout(bulk2)

        self.refresh_btn = QPushButton("Refresh Inventory")
        self.refresh_btn.clicked.connect(on_refresh)
        layout.addWidget(self.refresh_btn)


class ReviewTabWidget(QWidget):
    """Audit-style review queue with grouped tables and local summaries."""

    __slots__ = (
        "review_required_table",
        "fallback_table",
        "failed_table",
        "low_confidence_table",
        "review_help_label",
        "review_workspace_combo",
        "review_subfolder_edit",
        "assign_workspace_btn",
        "assign_subfolder_btn",
        "mark_reviewed_btn",
        "retry_btn",
        "summary_panel",
        "token_panel",
        "refresh_btn",
    )

    def __init__(
        self,
        *,
        on_assign_workspace: Callable[[], None],
        on_assign_subfolder: Callable[[], None],
        on_mark_approved: Callable[[], None],
        on_retry_selected: Callable[[], None],
        on_refresh: Callable[[], None],
    ) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        self.review_help_label = QLabel(
            "Files need review when fallback/risky keyword matching is used or confidence is below threshold."
        )
        layout.addWidget(self.review_help_label)

        self.review_required_table = self._build_group_table()
        layout.addWidget(QLabel("Files with review_required = 1"))
        layout.addWidget(self.review_required_table)

        self.fallback_table = self._build_group_table()
        layout.addWidget(QLabel("Files classified by fallback"))
        layout.addWidget(self.fallback_table)

        self.failed_table = self._build_group_table()
        layout.addWidget(QLabel("Failed files"))
        layout.addWidget(self.failed_table)

        self.low_confidence_table = self._build_group_table()
        layout.addWidget(QLabel("Low-confidence files"))
        layout.addWidget(self.low_confidence_table)

        action_row = QHBoxLayout()
        self.review_workspace_combo = QComboBox()
        self.review_workspace_combo.addItems(list(WORKSPACE_OPTIONS))
        self.review_subfolder_edit = QLineEdit()
        self.review_subfolder_edit.setPlaceholderText("subfolder (optional)")
        self.assign_workspace_btn = QPushButton("Assign Workspace")
        self.assign_workspace_btn.clicked.connect(on_assign_workspace)
        self.assign_subfolder_btn = QPushButton("Assign Subfolder")
        self.assign_subfolder_btn.clicked.connect(on_assign_subfolder)
        self.mark_reviewed_btn = QPushButton("Mark Approved")
        self.mark_reviewed_btn.clicked.connect(on_mark_approved)
        self.retry_btn = QPushButton("Retry Selected")
        self.retry_btn.clicked.connect(on_retry_selected)
        action_row.addWidget(QLabel("Workspace"))
        action_row.addWidget(self.review_workspace_combo)
        action_row.addWidget(self.assign_workspace_btn)
        action_row.addWidget(QLabel("Subfolder"))
        action_row.addWidget(self.review_subfolder_edit, 1)
        action_row.addWidget(self.assign_subfolder_btn)
        action_row.addWidget(self.mark_reviewed_btn)
        action_row.addWidget(self.retry_btn)
        layout.addLayout(action_row)

        layout.addWidget(QLabel("Summary"))
        self.summary_panel = QTextEdit()
        self.summary_panel.setReadOnly(True)
        self.summary_panel.setMaximumHeight(160)
        layout.addWidget(self.summary_panel)

        layout.addWidget(QLabel("Unmatched Pattern Helper"))
        self.token_panel = QTextEdit()
        self.token_panel.setReadOnly(True)
        self.token_panel.setMaximumHeight(120)
        layout.addWidget(self.token_panel)

        self.refresh_btn = QPushButton("Refresh Review Data")
        self.refresh_btn.clicked.connect(on_refresh)
        layout.addWidget(self.refresh_btn)

    @staticmethod
    def _build_group_table() -> QTableWidget:
        table = QTableWidget(0, 7)
        table.setHorizontalHeaderLabels(
            ["File ID", "File", "Workspace", "Subfolder", "Confidence", "Matched By", "Reason"]
        )
        table.horizontalHeader().setStretchLastSection(True)
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        table.setMaximumHeight(150)
        return table


class RunMonitorTabWidget(QWidget):
    """Live run monitor log panel."""

    log_append_requested = Signal(str)

    __slots__ = (
        "chips_grid",
        "state_chip",
        "total_chip",
        "pending_chip",
        "state_chip_value",
        "state_dot_label",
        "total_files_value",
        "pending_value",
        "summary_card_label",
        "details_toggle_btn",
        "details_frame",
        "details_grid",
        "details_total_value",
        "details_pending_value",
        "details_processed_value",
        "details_failed_value",
        "details_target_value",
        "details_available_targets_value",
        "details_ai_mode_value",
        "details_ollama_value",
        "_chips_wrapped",
        "_detail_pairs",
        "_details_single_column",
        "current_label",
        "status_note_label",
        "behavior_hint_label",
        "log_panel",
        "refresh_preflight_btn",
        "refresh_btn",
    )

    def __init__(self, *, on_refresh_data: Callable[[], None]) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        self.chips_grid = QGridLayout()
        self.chips_grid.setHorizontalSpacing(6)
        self.chips_grid.setVerticalSpacing(6)

        self.state_chip = self._build_chip("State")
        self.state_chip.setMinimumWidth(132)
        self.state_chip.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        state_chip_layout = self.state_chip.layout()
        state_value_row = QHBoxLayout()
        state_value_row.setContentsMargins(0, 0, 0, 0)
        state_value_row.setSpacing(4)
        self.state_dot_label = QLabel("\u25cf")
        self.state_dot_label.setStyleSheet("font-size: 10px; color: #3d9970;")
        self.state_chip_value = QLabel("idle")
        self.state_chip_value.setStyleSheet("font-size: 13pt; font-weight: 700;")
        state_value_row.addWidget(self.state_dot_label)
        state_value_row.addWidget(self.state_chip_value)
        state_value_row.addStretch(1)
        state_chip_layout.insertLayout(0, state_value_row)

        self.total_chip = self._build_chip("Total Files")
        self.total_chip.setMinimumWidth(132)
        self.total_chip.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.total_files_value = QLabel("0")
        self.total_files_value.setStyleSheet("font-size: 15pt; font-weight: 700;")
        self.total_chip.layout().insertWidget(0, self.total_files_value)

        self.pending_chip = self._build_chip("Pending")
        self.pending_chip.setMinimumWidth(132)
        self.pending_chip.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.pending_value = QLabel("0")
        self.pending_value.setStyleSheet("font-size: 15pt; font-weight: 700;")
        self.pending_chip.layout().insertWidget(0, self.pending_value)

        self._chips_wrapped = False
        self._relayout_stat_chips(force=True)
        layout.addLayout(self.chips_grid)

        summary_card = QFrame()
        summary_card.setStyleSheet(
            f"QFrame {{ background-color: {KIWTheme.BG_PANEL}; border-radius: 6px; }}"
        )
        summary_layout = QVBoxLayout(summary_card)
        summary_layout.setContentsMargins(12, 10, 12, 10)
        summary_layout.setSpacing(4)
        self.summary_card_label = QLabel("Load a project to preview what Run will do.")
        self.summary_card_label.setWordWrap(True)
        self.summary_card_label.setStyleSheet(f"color: {KIWTheme.TEXT_PRIMARY};")
        summary_layout.addWidget(self.summary_card_label)
        layout.addWidget(summary_card)

        self.details_toggle_btn = QToolButton()
        self.details_toggle_btn.setText("Details")
        self.details_toggle_btn.setCheckable(True)
        self.details_toggle_btn.setChecked(False)
        self.details_toggle_btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.details_toggle_btn.setArrowType(Qt.RightArrow)
        self.details_toggle_btn.toggled.connect(self._toggle_preflight_details)
        layout.addWidget(self.details_toggle_btn)

        self.details_frame = QFrame()
        self.details_frame.setStyleSheet(
            f"QFrame {{ background-color: {KIWTheme.BG_PANEL}; border-radius: 6px; }}"
        )
        self.details_grid = QGridLayout(self.details_frame)
        self.details_grid.setContentsMargins(12, 10, 12, 10)
        self.details_grid.setHorizontalSpacing(14)
        self.details_grid.setVerticalSpacing(4)

        details_total_key = self._detail_key_label("Total files in scope")
        self.details_total_value = self._detail_value_label("0")
        details_pending_key = self._detail_key_label("Pending for active profile")
        self.details_pending_value = self._detail_value_label("0")
        details_processed_key = self._detail_key_label("Already processed")
        self.details_processed_value = self._detail_value_label("0")
        details_failed_key = self._detail_key_label("Failed")
        self.details_failed_value = self._detail_value_label("0")
        details_target_key = self._detail_key_label("Active export target")
        self.details_target_value = self._detail_value_label("-")
        details_available_targets_key = self._detail_key_label("Available export targets")
        self.details_available_targets_value = self._detail_value_label("-")
        details_ai_mode_key = self._detail_key_label("AI mode")
        self.details_ai_mode_value = self._detail_value_label("-")
        details_ollama_key = self._detail_key_label("Ollama enabled")
        self.details_ollama_value = self._detail_value_label("-")

        self._detail_pairs = [
            (details_total_key, self.details_total_value),
            (details_pending_key, self.details_pending_value),
            (details_processed_key, self.details_processed_value),
            (details_failed_key, self.details_failed_value),
            (details_target_key, self.details_target_value),
            (details_available_targets_key, self.details_available_targets_value),
            (details_ai_mode_key, self.details_ai_mode_value),
            (details_ollama_key, self.details_ollama_value),
        ]
        self._details_single_column = False
        self._relayout_preflight_details(force=True)

        self.details_frame.setVisible(False)
        layout.addWidget(self.details_frame)

        self.current_label = QLabel("Current file: - | Current stage: -")
        self.current_label.setWordWrap(True)
        layout.addWidget(self.current_label)
        self.status_note_label = QLabel("Status note: none")
        self.status_note_label.setWordWrap(True)
        layout.addWidget(self.status_note_label)
        self.behavior_hint_label = QLabel(
            "Pause temporarily halts work, Resume continues, Stop ends the active loop. "
            "You can switch tabs during processing without interrupting the run."
        )
        self.behavior_hint_label.setWordWrap(True)
        layout.addWidget(self.behavior_hint_label)
        self.log_panel = QTextEdit()
        self.log_panel.setReadOnly(True)
        layout.addWidget(self.log_panel)
        self.log_append_requested.connect(self._append_log_on_ui_thread)
        self.refresh_preflight_btn = QPushButton("Refresh Preflight Summary")
        self.refresh_preflight_btn.setProperty("class", "btn-primary")
        self.refresh_btn = QPushButton("Refresh Inventory + Review")
        self.refresh_btn.setProperty("class", "btn-primary")
        self.refresh_btn.clicked.connect(on_refresh_data)

        actions_row = QHBoxLayout()
        actions_row.setSpacing(8)
        actions_row.addWidget(self.refresh_preflight_btn)
        actions_row.addWidget(self.refresh_btn)
        actions_row.addStretch(1)
        layout.addLayout(actions_row)

    @staticmethod
    def _build_chip(label_text: str) -> QFrame:
        chip = QFrame()
        chip.setStyleSheet(
            f"QFrame {{ background-color: {KIWTheme.BG_PANEL}; border-radius: 6px; }}"
        )
        chip_layout = QVBoxLayout(chip)
        chip_layout.setContentsMargins(10, 8, 10, 8)
        chip_layout.setSpacing(2)
        chip_label = QLabel(label_text)
        chip_label.setStyleSheet(f"color: {KIWTheme.TEXT_SECONDARY};")
        chip_layout.addWidget(chip_label)
        return chip

    @staticmethod
    def _detail_key_label(text: str) -> QLabel:
        label = QLabel(text)
        label.setStyleSheet(f"color: {KIWTheme.TEXT_SECONDARY};")
        label.setWordWrap(True)
        return label

    @staticmethod
    def _detail_value_label(text: str) -> QLabel:
        label = QLabel(text)
        label.setStyleSheet(f"color: {KIWTheme.TEXT_PRIMARY};")
        label.setWordWrap(True)
        return label

    def _relayout_stat_chips(self, *, force: bool = False) -> None:
        wrapped = self.width() < 760
        if not force and wrapped == self._chips_wrapped:
            return

        self._chips_wrapped = wrapped
        while self.chips_grid.count():
            item = self.chips_grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(self)

        if wrapped:
            self.chips_grid.setHorizontalSpacing(6)
            self.chips_grid.setVerticalSpacing(6)
            self.chips_grid.setColumnStretch(0, 1)
            self.chips_grid.setColumnStretch(1, 1)
            self.chips_grid.setColumnStretch(2, 0)
            self.chips_grid.addWidget(self.state_chip, 0, 0)
            self.chips_grid.addWidget(self.total_chip, 0, 1)
            self.chips_grid.addWidget(self.pending_chip, 1, 0, 1, 2)
        else:
            self.chips_grid.setHorizontalSpacing(6)
            self.chips_grid.setVerticalSpacing(6)
            self.chips_grid.setColumnStretch(0, 1)
            self.chips_grid.setColumnStretch(1, 1)
            self.chips_grid.setColumnStretch(2, 1)
            self.chips_grid.addWidget(self.state_chip, 0, 0)
            self.chips_grid.addWidget(self.total_chip, 0, 1)
            self.chips_grid.addWidget(self.pending_chip, 0, 2)

    def _relayout_preflight_details(self, *, force: bool = False) -> None:
        single_column = self.width() < 980
        if not force and single_column == self._details_single_column:
            return

        self._details_single_column = single_column
        while self.details_grid.count():
            item = self.details_grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(self.details_frame)

        if single_column:
            self.details_grid.setHorizontalSpacing(10)
            self.details_grid.setVerticalSpacing(6)
            self.details_grid.setColumnStretch(0, 0)
            self.details_grid.setColumnStretch(1, 1)
            self.details_grid.setColumnStretch(2, 0)
            self.details_grid.setColumnStretch(3, 0)
            for row, (key_label, value_label) in enumerate(self._detail_pairs):
                self.details_grid.addWidget(key_label, row, 0)
                self.details_grid.addWidget(value_label, row, 1)
        else:
            self.details_grid.setHorizontalSpacing(14)
            self.details_grid.setVerticalSpacing(4)
            self.details_grid.setColumnStretch(0, 0)
            self.details_grid.setColumnStretch(1, 1)
            self.details_grid.setColumnStretch(2, 0)
            self.details_grid.setColumnStretch(3, 1)
            left_pairs = self._detail_pairs[:4]
            right_pairs = self._detail_pairs[4:]
            for row, ((left_key, left_value), (right_key, right_value)) in enumerate(
                zip(left_pairs, right_pairs, strict=False)
            ):
                self.details_grid.addWidget(left_key, row, 0)
                self.details_grid.addWidget(left_value, row, 1)
                self.details_grid.addWidget(right_key, row, 2)
                self.details_grid.addWidget(right_value, row, 3)

    def _toggle_preflight_details(self, expanded: bool) -> None:
        self.details_toggle_btn.setArrowType(Qt.DownArrow if expanded else Qt.RightArrow)
        self.details_frame.setVisible(expanded)

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._relayout_stat_chips()
        self._relayout_preflight_details()

    def _set_state_chip(self, state: str) -> None:
        lower = state.strip().lower()
        if lower in {"running", "processing"}:
            color = "#4a9eff"
        elif lower in {"paused", "pause"}:
            color = "#e6a817"
        else:
            color = "#3d9970"
        self.state_chip_value.setText(state)
        self.state_dot_label.setStyleSheet(f"font-size: 10px; color: {color};")

    def append_log(self, text: str) -> None:
        # Emit even when called from the UI thread to guarantee queued, thread-safe updates.
        self.log_append_requested.emit(text)

    @Slot(str)
    def _append_log_on_ui_thread(self, text: str) -> None:
        self.log_panel.append(text)
        self.log_panel.moveCursor(QTextCursor.End)

    def set_snapshot(
        self,
        *,
        state: str,
        total_files: int,
        processed: int,
        failed: int,
        review_required: int,
        current_file: str,
        current_stage: str,
    ) -> None:
        self._set_state_chip(state)
        self.current_label.setText(f"Current file: {current_file} | Current stage: {current_stage}")

    def set_status_note(self, text: str) -> None:
        note = text.strip() or "none"
        self.status_note_label.setText(f"Status note: {note}")

    def set_preflight_summary(self, text: str) -> None:
        summary_text = text.strip() or "No preflight summary available."
        self.summary_card_label.setText(summary_text)
        self.total_files_value.setText("0")
        self.pending_value.setText("0")
        self.pending_value.setStyleSheet(f"font-size: 15pt; font-weight: 700; color: {KIWTheme.TEXT_PRIMARY};")
        self.details_total_value.setText("0")
        self.details_pending_value.setText("0")
        self.details_processed_value.setText("0")
        self.details_failed_value.setText("0")
        self.details_target_value.setText("-")
        self.details_available_targets_value.setText("-")
        self.details_ai_mode_value.setText("-")
        self.details_ollama_value.setText("-")

    def set_preflight_dashboard(
        self,
        *,
        summary_sentence: str,
        total_files: int,
        pending_files: int,
        processed_files: int,
        failed_files: int,
        active_target: str,
        available_targets: str,
        ai_mode: str,
        ollama_enabled: bool,
    ) -> None:
        self.summary_card_label.setText(summary_sentence.strip() or "No preflight summary available.")
        self.total_files_value.setText(str(total_files))
        self.pending_value.setText(str(pending_files))
        pending_color = KIWTheme.ACCENT_WARNING if pending_files > 0 else KIWTheme.TEXT_PRIMARY
        self.pending_value.setStyleSheet(f"font-size: 15pt; font-weight: 700; color: {pending_color};")

        self.details_total_value.setText(str(total_files))
        self.details_pending_value.setText(str(pending_files))
        self.details_processed_value.setText(str(processed_files))
        self.details_failed_value.setText(str(failed_files))
        self.details_target_value.setText(active_target)
        self.details_available_targets_value.setText(available_targets)
        self.details_ai_mode_value.setText(ai_mode)
        self.details_ollama_value.setText("yes" if ollama_enabled else "no")


class QueueTabWidget(QWidget):
    """Explicit queue view split into current batch and other pending items."""

    __slots__ = (
        "prep_hint_frame",
        "prep_hint_label",
        "prep_hint_open_btn",
        "prep_hint_dismiss_btn",
        "summary_label",
        "current_batch_table",
        "other_pending_table",
        "clear_pending_btn",
        "requeue_all_btn",
        "clear_other_btn",
        "requeue_current_btn",
        "refresh_btn",
    )

    def __init__(
        self,
        *,
        on_refresh: Callable[[], None],
        on_clear_pending: Callable[[], None],
        on_requeue_all: Callable[[], None],
        on_clear_other: Callable[[], None],
        on_requeue_current: Callable[[], None],
    ) -> None:
        super().__init__()
        layout = QVBoxLayout(self)

        self.prep_hint_frame = QFrame()
        self.prep_hint_frame.setStyleSheet(
            "QFrame {"
            "background: #2d2d30;"
            "border-left: 3px solid #4a9eff;"
            "padding: 8px;"
            "border-radius: 4px;"
            "}"
        )
        prep_hint_row = QHBoxLayout(self.prep_hint_frame)
        prep_hint_row.setContentsMargins(8, 8, 8, 8)
        prep_hint_row.setSpacing(8)
        self.prep_hint_label = QLabel(
            "💡 Working with a large archive? Use the Archive Prep Tool to split it into batches first."
        )
        self.prep_hint_label.setStyleSheet(f"color: {KIWTheme.TEXT_SECONDARY}; font-size: 11px;")
        self.prep_hint_open_btn = QPushButton("Open Prep Tool")
        self.prep_hint_open_btn.setProperty("class", "btn-primary")
        self.prep_hint_dismiss_btn = QPushButton("✕")
        self.prep_hint_dismiss_btn.setToolTip("Dismiss this hint")
        self.prep_hint_dismiss_btn.setMaximumWidth(28)
        prep_hint_row.addWidget(self.prep_hint_label, 1)
        prep_hint_row.addWidget(self.prep_hint_open_btn)
        prep_hint_row.addWidget(self.prep_hint_dismiss_btn)
        layout.addWidget(self.prep_hint_frame)

        self.summary_label = QLabel("Load a project to inspect queue state.")
        self.summary_label.setWordWrap(True)
        layout.addWidget(self.summary_label)

        # Side-by-side table layout: left (60%) current batch / right (40%) other pending
        tables_row = QHBoxLayout()
        tables_row.setSpacing(0)

        left_col = QVBoxLayout()
        left_col.setSpacing(4)
        left_header = QLabel("☰  CURRENT BATCH QUEUE")
        left_header.setStyleSheet(
            "color: #686888; font-weight: bold; font-size: 10px;"
            " letter-spacing: 0.1em; padding: 4px 6px; background: transparent;"
        )
        left_col.addWidget(left_header)
        self.current_batch_table = self._build_queue_table()
        left_col.addWidget(self.current_batch_table, 1)

        vline = QFrame()
        vline.setFrameShape(QFrame.VLine)
        vline.setFrameShadow(QFrame.Sunken)
        vline.setStyleSheet("color: #3a3a5c;")

        right_col = QVBoxLayout()
        right_col.setSpacing(4)
        right_header = QLabel("⋯  OTHER PENDING QUEUE")
        right_header.setStyleSheet(
            "color: #686888; font-weight: bold; font-size: 10px;"
            " letter-spacing: 0.1em; padding: 4px 6px; background: transparent;"
        )
        right_col.addWidget(right_header)
        self.other_pending_table = self._build_queue_table()
        right_col.addWidget(self.other_pending_table, 1)

        tables_row.addLayout(left_col, 3)
        tables_row.addWidget(vline)
        tables_row.addLayout(right_col, 2)
        layout.addLayout(tables_row, 1)

        action_row = QHBoxLayout()
        self.clear_pending_btn = QPushButton("Clear Pending Queue")
        self.clear_pending_btn.clicked.connect(on_clear_pending)
        action_row.addWidget(self.clear_pending_btn)
        self.requeue_all_btn = QPushButton("Requeue All")
        self.requeue_all_btn.clicked.connect(on_requeue_all)
        action_row.addWidget(self.requeue_all_btn)
        self.clear_other_btn = QPushButton("Clear Other Pending")
        self.clear_other_btn.clicked.connect(on_clear_other)
        action_row.addWidget(self.clear_other_btn)
        self.requeue_current_btn = QPushButton("Requeue Current Batch")
        self.requeue_current_btn.clicked.connect(on_requeue_current)
        action_row.addWidget(self.requeue_current_btn)
        action_row.addStretch(1)
        layout.addLayout(action_row)

        self.refresh_btn = QPushButton("Refresh Queue")
        self.refresh_btn.clicked.connect(on_refresh)
        layout.addWidget(self.refresh_btn)

    @staticmethod
    def _build_queue_table() -> QTableWidget:
        table = QTableWidget(0, 8)
        table.setHorizontalHeaderLabels(
            ["File ID", "File", "Folder", "Next Stage", "Status", "Workspace", "Subfolder", "Updated"]
        )
        table.horizontalHeader().setStretchLastSection(True)
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        return table


class ExportsTabWidget(QWidget):
    """Local export destinations and manifest summary."""

    __slots__ = (
        "anythingllm_summary",
        "openwebui_summary",
        "latest_manifest_label",
        "preview_table",
        "open_folder_btn",
        "refresh_btn",
    )

    def __init__(self, *, on_open_folder: Callable[[], None], on_refresh: Callable[[], None]) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("AnythingLLM exports"))
        self.anythingllm_summary = QTextEdit()
        self.anythingllm_summary.setReadOnly(True)
        self.anythingllm_summary.setMaximumHeight(120)
        layout.addWidget(self.anythingllm_summary)

        layout.addWidget(QLabel("Open WebUI exports"))
        self.openwebui_summary = QTextEdit()
        self.openwebui_summary.setReadOnly(True)
        self.openwebui_summary.setMaximumHeight(120)
        layout.addWidget(self.openwebui_summary)

        self.latest_manifest_label = QLabel("Latest manifests: n/a")
        layout.addWidget(self.latest_manifest_label)

        layout.addWidget(QLabel("Recent exported files"))
        self.preview_table = QTableWidget(0, 4)
        self.preview_table.setHorizontalHeaderLabels(["Profile", "Workspace", "Source File", "Export Path"])
        self.preview_table.horizontalHeader().setStretchLastSection(True)
        self.preview_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.preview_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.preview_table.setMaximumHeight(220)
        layout.addWidget(self.preview_table)

        row = QHBoxLayout()
        self.open_folder_btn = QPushButton("Open Export Folder")
        self.open_folder_btn.clicked.connect(on_open_folder)
        row.addWidget(self.open_folder_btn)
        self.refresh_btn = QPushButton("Refresh Export Summary")
        self.refresh_btn.clicked.connect(on_refresh)
        row.addWidget(self.refresh_btn)
        row.addStretch(1)
        layout.addLayout(row)


class SettingsTabWidget(QWidget):
    """Project-scoped settings editor."""

    __slots__ = (
        "info_label",
        "enable_ollama_label",
        "enable_ollama_check",
        "ollama_model_label",
        "ollama_model_edit",
        "refresh_ollama_models_btn",
        "ai_provider_label",
        "ai_provider_combo",
        "api_key_label",
        "api_key_edit",
        "cloud_model_label",
        "cloud_model_combo",
        "api_key_help_label",
        "ai_mode_combo",
        "auto_assign_workspace_check",
        "duplicate_filename_policy_combo",
        "chunk_target_spin",
        "minimum_chunk_spin",
        "low_confidence_spin",
        "relevance_min_score_spin",
        "small_file_char_threshold_spin",
        "preflight_wiki_share_cap_spin",
        "ollama_status_label_label",
        "ollama_status_label",
        "test_ollama_btn",
        "reset_rules_btn",
        "save_btn",
        "_section_grids",
        "_section_items",
        "_settings_two_column",
        "categories_tab_widget",
        "workspace_list",
        "ws_label_edit",
        "ws_name_edit",
        "add_workspace_btn",
        "remove_workspace_btn",
        "company_list",
        "company_keyword_edit",
        "company_ws_combo",
        "add_company_btn",
        "remove_company_btn",
        "project_list",
        "project_keyword_edit",
        "project_ws_combo",
        "add_project_btn",
        "remove_project_btn",
        "rules_table",
        "rule_keyword_edit",
        "rule_ws_combo",
        "rule_subfolder_edit",
        "add_rule_btn",
        "remove_rule_btn",
    )

    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        section_style = (
            "QGroupBox {"
            " font-weight: bold;"
            " font-size: 12px;"
            " color: #a0a0a0;"
            " border: 1px solid #555555;"
            " border-radius: 6px;"
            " margin-top: 10px;"
            " padding-top: 8px;"
            "}"
            "QGroupBox::title {"
            " subcontrol-origin: margin;"
            " subcontrol-position: top left;"
            " padding: 0 6px;"
            " color: #4a9eff;"
            "}"
        )

        self.info_label = QLabel("Project settings will appear here after a project is loaded.")
        layout.addWidget(self.info_label)

        self.enable_ollama_label = self._settings_field_label("Enable Ollama")
        self.enable_ollama_check = QCheckBox()
        self.ollama_model_label = self._settings_field_label("Ollama Model")
        self.ollama_model_edit = QComboBox()
        self.ollama_model_edit.setEditable(True)
        self.ollama_model_edit.addItem("llama3.2:3b")
        self.ollama_model_edit.setCurrentText("llama3.2:3b")
        self.refresh_ollama_models_btn = QPushButton("Refresh Ollama Models")
        self.ai_provider_label = self._settings_field_label("AI Provider")
        self.ai_provider_combo = QComboBox()
        self.ai_provider_combo.addItems(["ollama", "claude", "openai"])
        self.api_key_label = self._settings_field_label("API Key")
        self.api_key_edit = QLineEdit()
        self.api_key_edit.setPlaceholderText("Paste your API key here...")
        self.api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.cloud_model_label = self._settings_field_label("Model")
        self.cloud_model_combo = QComboBox()
        self.cloud_model_combo.setEditable(True)
        self.ai_mode_combo = QComboBox()
        self.ai_mode_combo.addItems(["rules_only", "ai_only_unclassified", "ai_all"])
        self.auto_assign_workspace_check = QCheckBox()
        self.auto_assign_workspace_check.setChecked(True)
        self.duplicate_filename_policy_combo = QComboBox()
        self.duplicate_filename_policy_combo.addItems(["rename", "overwrite", "skip"])
        self.chunk_target_spin = QSpinBox()
        self.chunk_target_spin.setRange(20, 10000)
        self.minimum_chunk_spin = QSpinBox()
        self.minimum_chunk_spin.setRange(1, 10000)
        self.low_confidence_spin = QDoubleSpinBox()
        self.low_confidence_spin.setRange(0.01, 1.0)
        self.low_confidence_spin.setSingleStep(0.01)
        self.low_confidence_spin.setDecimals(2)
        self.relevance_min_score_spin = QSpinBox()
        self.relevance_min_score_spin.setRange(0, 20)
        self.small_file_char_threshold_spin = QSpinBox()
        self.small_file_char_threshold_spin.setRange(50, 10000)
        self.preflight_wiki_share_cap_spin = QDoubleSpinBox()
        self.preflight_wiki_share_cap_spin.setRange(0.05, 1.0)
        self.preflight_wiki_share_cap_spin.setSingleStep(0.05)
        self.preflight_wiki_share_cap_spin.setDecimals(2)

        self.ollama_status_label_label = self._settings_field_label("Ollama Status")
        self.ollama_status_label = QLabel("Ollama status: disabled")
        self.test_ollama_btn = QPushButton("Test Ollama Connection")
        self.api_key_help_label = QLabel()
        self.api_key_help_label.setWordWrap(True)
        self.api_key_help_label.setStyleSheet("color: #a0a0a0; font-size: 11px;")
        self.reset_rules_btn = QPushButton("Reset to Default Rules")
        self.reset_rules_btn.setProperty("class", "btn-danger")
        self.save_btn = QPushButton("Save Settings")
        self.save_btn.setProperty("class", "btn-primary")

        ai_group = QGroupBox("AI Provider")
        ai_group.setStyleSheet(section_style)
        ai_grid = QGridLayout(ai_group)
        ai_grid.setContentsMargins(12, 12, 12, 12)
        ai_grid.setHorizontalSpacing(12)
        ai_grid.setVerticalSpacing(8)

        behavior_group = QGroupBox("Processing Behavior")
        behavior_group.setStyleSheet(section_style)
        behavior_grid = QGridLayout(behavior_group)
        behavior_grid.setContentsMargins(12, 12, 12, 12)
        behavior_grid.setHorizontalSpacing(12)
        behavior_grid.setVerticalSpacing(8)

        chunking_group = QGroupBox("Chunking & Export")
        chunking_group.setStyleSheet(section_style)
        chunking_grid = QGridLayout(chunking_group)
        chunking_grid.setContentsMargins(12, 12, 12, 12)
        chunking_grid.setHorizontalSpacing(12)
        chunking_grid.setVerticalSpacing(8)

        # My Categories group box — four sub-tabs for workspaces, companies, projects, rules
        categories_group = QGroupBox("My Categories")
        categories_group.setStyleSheet(section_style)
        cat_group_layout = QVBoxLayout(categories_group)
        cat_group_layout.setContentsMargins(12, 12, 12, 12)

        self.categories_tab_widget = QTabWidget()

        # Tab 1 — Workspaces
        ws_tab = QWidget()
        ws_layout = QVBoxLayout(ws_tab)
        self.workspace_list = QTableWidget(0, 2)
        self.workspace_list.setHorizontalHeaderLabels(["Label", "Folder Name"])
        self.workspace_list.horizontalHeader().setStretchLastSection(True)
        self.workspace_list.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.workspace_list.setSelectionMode(QAbstractItemView.SingleSelection)
        ws_layout.addWidget(self.workspace_list)
        ws_input_row = QHBoxLayout()
        self.ws_label_edit = QLineEdit()
        self.ws_label_edit.setPlaceholderText("Workspace label (e.g. my_projects)")
        self.ws_name_edit = QLineEdit()
        self.ws_name_edit.setPlaceholderText("Folder name (e.g. my_projects)")
        self.add_workspace_btn = QPushButton("Add Workspace")
        self.add_workspace_btn.setProperty("class", "btn-primary")
        self.remove_workspace_btn = QPushButton("Remove Selected")
        self.remove_workspace_btn.setProperty("class", "btn-danger")
        ws_input_row.addWidget(self.ws_label_edit)
        ws_input_row.addWidget(self.ws_name_edit)
        ws_input_row.addWidget(self.add_workspace_btn)
        ws_input_row.addWidget(self.remove_workspace_btn)
        ws_layout.addLayout(ws_input_row)
        self.categories_tab_widget.addTab(ws_tab, "Workspaces")

        # Tab 2 — Companies
        co_tab = QWidget()
        co_layout = QVBoxLayout(co_tab)
        self.company_list = QTableWidget(0, 2)
        self.company_list.setHorizontalHeaderLabels(["Keyword", "Workspace"])
        self.company_list.horizontalHeader().setStretchLastSection(True)
        self.company_list.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.company_list.setSelectionMode(QAbstractItemView.SingleSelection)
        co_layout.addWidget(self.company_list)
        co_input_row = QHBoxLayout()
        self.company_keyword_edit = QLineEdit()
        self.company_keyword_edit.setPlaceholderText("Company name or keyword")
        self.company_ws_combo = QComboBox()
        self.add_company_btn = QPushButton("Add Company")
        self.add_company_btn.setProperty("class", "btn-primary")
        self.remove_company_btn = QPushButton("Remove Selected")
        self.remove_company_btn.setProperty("class", "btn-danger")
        co_input_row.addWidget(self.company_keyword_edit)
        co_input_row.addWidget(self.company_ws_combo)
        co_input_row.addWidget(self.add_company_btn)
        co_input_row.addWidget(self.remove_company_btn)
        co_layout.addLayout(co_input_row)
        co_help = QLabel(
            "Files containing this company name will be routed to the selected workspace automatically."
        )
        co_help.setStyleSheet(f"color: {KIWTheme.TEXT_SECONDARY}; font-size: 11px;")
        co_help.setWordWrap(True)
        co_layout.addWidget(co_help)
        self.categories_tab_widget.addTab(co_tab, "Companies")

        # Tab 3 — Projects
        pr_tab = QWidget()
        pr_layout = QVBoxLayout(pr_tab)
        self.project_list = QTableWidget(0, 2)
        self.project_list.setHorizontalHeaderLabels(["Keyword", "Workspace"])
        self.project_list.horizontalHeader().setStretchLastSection(True)
        self.project_list.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.project_list.setSelectionMode(QAbstractItemView.SingleSelection)
        pr_layout.addWidget(self.project_list)
        pr_input_row = QHBoxLayout()
        self.project_keyword_edit = QLineEdit()
        self.project_keyword_edit.setPlaceholderText("Project keyword")
        self.project_ws_combo = QComboBox()
        self.add_project_btn = QPushButton("Add Project")
        self.add_project_btn.setProperty("class", "btn-primary")
        self.remove_project_btn = QPushButton("Remove Selected")
        self.remove_project_btn.setProperty("class", "btn-danger")
        pr_input_row.addWidget(self.project_keyword_edit)
        pr_input_row.addWidget(self.project_ws_combo)
        pr_input_row.addWidget(self.add_project_btn)
        pr_input_row.addWidget(self.remove_project_btn)
        pr_layout.addLayout(pr_input_row)
        pr_help = QLabel(
            "Files mentioning this project keyword will be routed to the selected workspace automatically."
        )
        pr_help.setStyleSheet(f"color: {KIWTheme.TEXT_SECONDARY}; font-size: 11px;")
        pr_help.setWordWrap(True)
        pr_layout.addWidget(pr_help)
        self.categories_tab_widget.addTab(pr_tab, "Projects")

        # Tab 4 — Keywords & Rules
        ru_tab = QWidget()
        ru_layout = QVBoxLayout(ru_tab)
        self.rules_table = QTableWidget(0, 4)
        self.rules_table.setHorizontalHeaderLabels(["Keyword", "Workspace", "Subfolder", "Reason"])
        self.rules_table.horizontalHeader().setStretchLastSection(True)
        self.rules_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.rules_table.setSelectionMode(QAbstractItemView.SingleSelection)
        ru_layout.addWidget(self.rules_table)
        ru_input_row = QHBoxLayout()
        self.rule_keyword_edit = QLineEdit()
        self.rule_keyword_edit.setPlaceholderText("Keyword or phrase (e.g. quarterly report)")
        self.rule_ws_combo = QComboBox()
        self.rule_subfolder_edit = QLineEdit()
        self.rule_subfolder_edit.setPlaceholderText("Subfolder (optional)")
        self.add_rule_btn = QPushButton("Add Rule")
        self.add_rule_btn.setProperty("class", "btn-primary")
        self.remove_rule_btn = QPushButton("Remove Selected")
        self.remove_rule_btn.setProperty("class", "btn-danger")
        ru_input_row.addWidget(self.rule_keyword_edit)
        ru_input_row.addWidget(self.rule_ws_combo)
        ru_input_row.addWidget(self.rule_subfolder_edit)
        ru_input_row.addWidget(self.add_rule_btn)
        ru_input_row.addWidget(self.remove_rule_btn)
        ru_layout.addLayout(ru_input_row)
        ru_help = QLabel(
            "Files whose name or content contains this phrase will always be routed to the selected workspace. "
            "These are the highest priority rules."
        )
        ru_help.setStyleSheet(f"color: {KIWTheme.TEXT_SECONDARY}; font-size: 11px;")
        ru_help.setWordWrap(True)
        ru_layout.addWidget(ru_help)
        self.categories_tab_widget.addTab(ru_tab, "Keywords & Rules")

        cat_group_layout.addWidget(self.categories_tab_widget)

        self._section_grids = [ai_grid, behavior_grid, chunking_grid]
        self._section_items = [
            [
                (self.enable_ollama_label, self.enable_ollama_check),
                (self.ollama_model_label, self.ollama_model_edit),
                (None, self.refresh_ollama_models_btn),
                (self.ai_provider_label, self.ai_provider_combo),
                (self.api_key_label, self.api_key_edit),
                (self.cloud_model_label, self.cloud_model_combo),
                (self._settings_field_label("AI Mode"), self.ai_mode_combo),
                (self.ollama_status_label_label, self.ollama_status_label),
                (None, self.test_ollama_btn),
            ],
            [
                (self._settings_field_label("Auto Assign Workspace"), self.auto_assign_workspace_check),
                (self._settings_field_label("Duplicate Filename Policy"), self.duplicate_filename_policy_combo),
                (self._settings_field_label("Confidence threshold (review gating)"), self.low_confidence_spin),
                (self._settings_field_label("Relevance minimum score"), self.relevance_min_score_spin),
                (self._settings_field_label("Small-file threshold (characters)"), self.small_file_char_threshold_spin),
            ],
            [
                (self._settings_field_label("Chunk Target Size"), self.chunk_target_spin),
                (self._settings_field_label("Minimum Chunk Size"), self.minimum_chunk_spin),
                (self._settings_field_label("Preflight wiki-share cap"), self.preflight_wiki_share_cap_spin),
            ],
        ]
        self._settings_two_column = False
        self._relayout_settings_sections(force=True)

        layout.addWidget(categories_group)
        layout.addWidget(ai_group)
        layout.addWidget(self.api_key_help_label)
        layout.addWidget(behavior_group)
        layout.addWidget(chunking_group)
        layout.addStretch(1)

        hint_card = QFrame()
        hint_card.setStyleSheet(
            f"QFrame {{ background-color: {KIWTheme.BG_PANEL}; border-radius: 6px; }}"
        )
        hint_layout = QVBoxLayout(hint_card)
        hint_layout.setContentsMargins(12, 10, 12, 10)
        hint_layout.setSpacing(4)
        hint_title = QLabel("Tuning Tip")
        hint_title.setStyleSheet(f"color: {KIWTheme.TEXT_SECONDARY}; font-weight: 700;")
        hint_layout.addWidget(hint_title)
        hints_label = QLabel(
            "Tip: start with relevance 2-3 and small-file threshold 220-320 chars. "
            "Raise relevance to send more files to review; lower small-file threshold to reduce wiki fragments. "
            "Use wiki-share cap around 0.30-0.40 to prevent over-routing before runs (default: 30%)."
        )
        hints_label.setWordWrap(True)
        hint_layout.addWidget(hints_label)
        layout.addWidget(hint_card)

        action_card = QFrame()
        action_card.setStyleSheet(
            f"QFrame {{ background-color: {KIWTheme.BG_PANEL}; border-radius: 6px; }}"
        )
        action_layout = QVBoxLayout(action_card)
        action_layout.setContentsMargins(12, 10, 12, 10)
        action_layout.setSpacing(6)
        action_title = QLabel("Actions")
        action_title.setStyleSheet(f"color: {KIWTheme.TEXT_SECONDARY}; font-weight: 700;")
        action_layout.addWidget(action_title)

        actions_row = QHBoxLayout()
        actions_row.setContentsMargins(0, 0, 0, 0)
        actions_row.setSpacing(8)
        actions_row.addWidget(self.reset_rules_btn)
        actions_row.addWidget(self.save_btn)
        actions_row.addStretch(1)
        action_layout.addLayout(actions_row)
        layout.addWidget(action_card)

    @staticmethod
    def _settings_field_label(text: str) -> QLabel:
        label = QLabel(text)
        label.setWordWrap(True)
        label.setStyleSheet(f"color: {KIWTheme.TEXT_SECONDARY};")
        return label

    @staticmethod
    def _clear_grid_layout(layout: QGridLayout, parent: QWidget) -> None:
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(parent)

    @staticmethod
    def _add_settings_item(
        layout: QGridLayout,
        row: int,
        base_col: int,
        label: QLabel | None,
        widget: QWidget,
    ) -> None:
        if label is None:
            layout.addWidget(widget, row, base_col, 1, 2)
            return
        layout.addWidget(label, row, base_col)
        layout.addWidget(widget, row, base_col + 1)

    def _relayout_settings_sections(self, *, force: bool = False) -> None:
        two_column = self.width() >= 980
        if not force and two_column == self._settings_two_column:
            return

        self._settings_two_column = two_column
        for grid, items in zip(self._section_grids, self._section_items, strict=False):
            parent = grid.parentWidget()
            if parent is None:
                continue
            self._clear_grid_layout(grid, parent)

            if two_column:
                grid.setHorizontalSpacing(12)
                grid.setVerticalSpacing(8)
                grid.setColumnStretch(0, 0)
                grid.setColumnStretch(1, 1)
                grid.setColumnStretch(2, 0)
                grid.setColumnStretch(3, 1)
                row = 0
                index = 0
                while index < len(items):
                    left_label, left_widget = items[index]
                    self._add_settings_item(grid, row, 0, left_label, left_widget)
                    index += 1
                    if index < len(items):
                        right_label, right_widget = items[index]
                        self._add_settings_item(grid, row, 2, right_label, right_widget)
                        index += 1
                    row += 1
            else:
                grid.setHorizontalSpacing(10)
                grid.setVerticalSpacing(6)
                grid.setColumnStretch(0, 0)
                grid.setColumnStretch(1, 1)
                grid.setColumnStretch(2, 0)
                grid.setColumnStretch(3, 0)
                for row, (label, widget) in enumerate(items):
                    self._add_settings_item(grid, row, 0, label, widget)

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._relayout_settings_sections()


class HelpPanel(QWidget):
    """Slide-in help reference panel shown at the right edge of the main window."""

    class _HoverCard(QFrame):
        _BASE = (
            "QFrame { background-color: #1e1e2a; border: 1px solid #2d2d3d;"
            " border-radius: 6px; }"
        )
        _HOVER = (
            "QFrame { background-color: #1e1e2a; border: 1px solid #4a7fff;"
            " border-radius: 6px; }"
        )

        def __init__(self, parent: QWidget | None = None) -> None:
            super().__init__(parent)
            self.setStyleSheet(self._BASE)

        def enterEvent(self, event) -> None:  # type: ignore[override]
            self.setStyleSheet(self._HOVER)
            super().enterEvent(event)

        def leaveEvent(self, event) -> None:  # type: ignore[override]
            self.setStyleSheet(self._BASE)
            super().leaveEvent(event)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedWidth(340)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet("QWidget { background-color: #15151e; }")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ── Header bar ────────────────────────────────────────────────────
        header_bar = QFrame()
        header_bar.setFixedHeight(56)
        header_bar.setStyleSheet(
            "QFrame {"
            "  background-color: #2a2a38;"
            "  border-bottom: 1px solid #35354a;"
            "}"
        )
        hdr_row = QHBoxLayout(header_bar)
        hdr_row.setContentsMargins(12, 8, 12, 8)
        hdr_row.setSpacing(0)

        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        title_lbl = QLabel("KIWI Help")
        title_lbl.setStyleSheet(
            "font-weight: bold; font-size: 13px; color: #e8e8f0; background: transparent;"
        )
        sub_lbl = QLabel("Quick reference for new users")
        sub_lbl.setStyleSheet("font-size: 11px; color: #6868a8; background: transparent;")
        title_col.addWidget(title_lbl)
        title_col.addWidget(sub_lbl)

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(24, 24)
        close_btn.setStyleSheet(
            "QPushButton { color: #6868a8; background: transparent;"
            " border: none; font-size: 13px; }"
            "QPushButton:hover { color: #e8e8f0; }"
        )
        close_btn.clicked.connect(self.hide)

        hdr_row.addLayout(title_col)
        hdr_row.addStretch()
        hdr_row.addWidget(close_btn)
        outer.addWidget(header_bar)

        # ── Tab widget ────────────────────────────────────────────────────
        tabs = QTabWidget()
        tabs.setDocumentMode(False)
        tabs.setStyleSheet(
            "QTabBar::tab {"
            "  padding: 8px 14px; font-size: 11px; font-weight: bold;"
            "  background: transparent; border: none;"
            "  color: #606080; border-bottom: 2px solid transparent;"
            "}"
            "QTabBar::tab:selected {"
            "  color: #c8c8e0; border-bottom: 2px solid #4a7fff;"
            "}"
            "QTabWidget::pane { border: none; }"
        )
        tabs.addTab(self._build_overview_tab(), "Overview")
        tabs.addTab(self._build_faq_tab(), "FAQ")
        tabs.addTab(self._build_glossary_tab(), "Glossary")
        outer.addWidget(tabs, 1)

    @staticmethod
    def _section_label(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(
            "font-size: 10px; font-weight: bold; color: #5a5a7a;"
            " letter-spacing: 0.08em; background: transparent;"
        )
        return lbl

    @staticmethod
    def _scroll_wrap(inner: QWidget) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        scroll.setWidget(inner)
        return scroll

    def _build_overview_tab(self) -> QScrollArea:
        container = QWidget()
        container.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        layout.addWidget(self._section_label("THE BASIC WORKFLOW"))

        pills_widget = QWidget()
        pills_widget.setStyleSheet("background: transparent;")
        pills_row = QHBoxLayout(pills_widget)
        pills_row.setContentsMargins(0, 0, 0, 0)
        pills_row.setSpacing(4)
        steps = [
            ("1. Point at folder", False),
            ("→", None),
            ("2. Scan", True),
            ("→", None),
            ("3. Review Triage", False),
            ("→", None),
            ("4. Run", True),
            ("→", None),
            ("5. Use in AI tool", False),
        ]
        for text, is_action in steps:
            lbl = QLabel(text)
            if is_action is None:
                lbl.setStyleSheet("color: #404058; font-size: 10px; background: transparent;")
            elif is_action:
                lbl.setStyleSheet(
                    "background-color: #1e1e2a; border: 1px solid #4a7fff;"
                    " border-radius: 4px; padding: 4px 8px; font-size: 11px; color: #4a7fff;"
                )
            else:
                lbl.setStyleSheet(
                    "background-color: #1e1e2a; border: 1px solid #35354a;"
                    " border-radius: 4px; padding: 4px 8px; font-size: 11px; color: #9090b8;"
                )
            pills_row.addWidget(lbl)
        pills_row.addStretch()
        layout.addWidget(pills_widget)

        tip = QFrame()
        tip.setStyleSheet(
            "QFrame { background-color: #1a2a3a; border: 1px solid #2a4a6a;"
            " border-radius: 6px; }"
        )
        tip_layout = QVBoxLayout(tip)
        tip_layout.setContentsMargins(10, 10, 10, 10)
        tip_layout.setSpacing(4)
        tip_title = QLabel("FIRST TIME?")
        tip_title.setStyleSheet(
            "font-size: 10px; font-weight: bold; color: #4a7fff; background: transparent;"
        )
        tip_body = QLabel(
            "Start with Step 1 — enter a project name, point KIWI at a folder of documents, "
            "and click Create + Load + Scan. Then check the Triage tab to see what needs "
            "your attention."
        )
        tip_body.setWordWrap(True)
        tip_body.setStyleSheet("font-size: 11px; color: #a0a0c0; background: transparent;")
        tip_layout.addWidget(tip_title)
        tip_layout.addWidget(tip_body)
        layout.addWidget(tip)

        layout.addWidget(self._section_label("WHAT EACH STEP DOES"))

        cards_data = [
            ("Step 1 — Classify", "Set your project name and point to your documents folder."),
            ("Step 2 — Configure", "Open Settings to define workspaces and rules for your topics."),
            ("Step 3 — Run", "Create+Load+Scan does everything at once. Run Queue exports files."),
            ("Step 4 — Monitor", "Watch progress here. Pause or Stop without losing your work."),
        ]
        grid = QGridLayout()
        grid.setSpacing(8)
        for i, (card_title, card_desc) in enumerate(cards_data):
            card = self._HoverCard()
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(10, 10, 10, 10)
            card_layout.setSpacing(4)
            t = QLabel(card_title)
            t.setStyleSheet(
                "font-size: 12px; font-weight: bold; color: #c8c8e0; background: transparent;"
            )
            d = QLabel(card_desc)
            d.setWordWrap(True)
            d.setStyleSheet("font-size: 11px; color: #707090; background: transparent;")
            card_layout.addWidget(t)
            card_layout.addWidget(d)
            grid.addWidget(card, i // 2, i % 2)
        layout.addLayout(grid)
        layout.addStretch()

        return self._scroll_wrap(container)

    def _build_faq_tab(self) -> QScrollArea:
        container = QWidget()
        container.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(0)

        faqs = [
            (
                "What does 'unassigned' mean in Triage?",
                "KIWI couldn't confidently route the file using your rules. Assign it manually, "
                "add a rule to handle it next time, or mark it to skip.",
            ),
            (
                "Do I need an AI provider?",
                "No. KIWI works entirely on rules you define. AI (Ollama, Claude, OpenAI) is "
                "optional — only used for files that don't match any rule.",
            ),
            (
                "AnythingLLM vs Open WebUI — what's the difference?",
                "AnythingLLM gets a flat folder of files. Open WebUI gets a folder hierarchy "
                "matching your workspaces. Use whichever matches your AI tool.",
            ),
            (
                "My folder has 10,000+ files. Where do I start?",
                "Use the Archive Prep Tool first (Prep Tool button in Step 2) to split into "
                "batches of 300–500 files. Then process each batch with KIWI separately.",
            ),
            (
                "What is Simple vs Expert mode?",
                "Simple shows the three tabs you need for most runs. Expert reveals Inventory, "
                "Review, Triage, and Exports for full control.",
            ),
            (
                "What happens if I click Stop mid-run?",
                "KIWI saves all work completed so far. You can Resume later or start a new run "
                "— nothing is lost.",
            ),
            (
                "How do I teach KIWI about my documents?",
                "Go to Settings → My Categories. Add your company names, project keywords, and "
                "topic rules. KIWI uses these to auto-classify files without AI.",
            ),
        ]
        for question, answer in faqs:
            item = QFrame()
            item.setStyleSheet(
                "QFrame { border: none; border-bottom: 1px solid #1e1e2a;"
                " background: transparent; }"
            )
            item_layout = QVBoxLayout(item)
            item_layout.setContentsMargins(0, 10, 0, 10)
            item_layout.setSpacing(4)
            q_lbl = QLabel(question)
            q_lbl.setWordWrap(True)
            q_lbl.setStyleSheet(
                "font-size: 12px; font-weight: bold; color: #c8c8e0; background: transparent;"
            )
            a_lbl = QLabel(answer)
            a_lbl.setWordWrap(True)
            a_lbl.setStyleSheet("font-size: 11px; color: #787898; background: transparent;")
            item_layout.addWidget(q_lbl)
            item_layout.addWidget(a_lbl)
            layout.addWidget(item)

        layout.addStretch()
        return self._scroll_wrap(container)

    def _build_glossary_tab(self) -> QScrollArea:
        container = QWidget()
        container.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(0)

        terms = [
            ("Workspace",
             "A top-level folder category. Files are sorted into workspaces "
             "(e.g. career_portfolio, ai_projects)."),
            ("Force Rule",
             "A keyword that always routes a file to a specific workspace — no AI needed. "
             "Highest priority rule."),
            ("Triage",
             "Files KIWI couldn't confidently classify. Review these before running to "
             "improve accuracy."),
            ("Batch",
             "A subfolder of files processed in one run. Use the Prep Tool to create batches "
             "from large archives."),
            ("Export Profile",
             "AnythingLLM (flat files) or Open WebUI (folder hierarchy). Controls how output "
             "is structured."),
            ("Confidence threshold",
             "How certain KIWI must be before auto-assigning a file. Lower = more auto-assigns, "
             "less manual review needed."),
            ("Rule gap",
             "A file that didn't match any rule in your config. Adding a rule for it improves "
             "future runs."),
            ("Wiki",
             "Markdown files routed to a special workspace used for notes and reference "
             "documents."),
        ]
        for term, definition in terms:
            item = QFrame()
            item.setStyleSheet(
                "QFrame { border: none; border-bottom: 1px solid #1e1e2a;"
                " background: transparent; }"
            )
            item_row = QHBoxLayout(item)
            item_row.setContentsMargins(0, 10, 0, 10)
            item_row.setSpacing(10)
            term_lbl = QLabel(term)
            term_lbl.setFixedWidth(110)
            term_lbl.setWordWrap(True)
            term_lbl.setStyleSheet(
                "font-size: 12px; font-weight: bold; color: #c8c8e0; background: transparent;"
            )
            def_lbl = QLabel(definition)
            def_lbl.setWordWrap(True)
            def_lbl.setStyleSheet("font-size: 11px; color: #787898; background: transparent;")
            item_row.addWidget(term_lbl)
            item_row.addWidget(def_lbl, 1)
            layout.addWidget(item)

        layout.addStretch()
        return self._scroll_wrap(container)
