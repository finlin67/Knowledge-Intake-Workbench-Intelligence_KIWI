"""Main window controller for the tabbed desktop shell."""

from __future__ import annotations

import shutil
from pathlib import Path

from PySide6.QtCore import QSettings, QTimer
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QInputDialog,
    QMainWindow,
    QMessageBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from gui.setup_wizard import SetupWizardDialog
from gui.theme import KIWTheme

from gui.controllers import (
    ExportsController,
    InventoryController,
    ProjectController,
    QueueController,
    ReviewController,
    RunController,
    SettingsController,
)
from gui.triage_tab import TriageTabWidget, export_triage_rows_csv
from gui.widgets import (
    ExportsTabWidget,
    HelpPanel,
    InventoryTabWidget,
    ProjectHeaderWidget,
    QueueTabWidget,
    ReviewTabWidget,
    RunMonitorTabWidget,
    SettingsTabWidget,
)
from db.repositories import FileRepository
from db.session import Database
from services.inventory_service import InventoryService
from services.project_service import ProjectService
from services.review_service import ReviewService
from services.run_monitor_service import RunMonitorService


class MainWindow(QMainWindow):
    __slots__ = (
        "_tabs",
        "_header",
        "_monitor_service",
        "_simple_mode_enabled",
        "_inventory_tab",
        "_review_tab",
        "_triage_tab",
        "_queue_tab",
        "_run_tab",
        "_exports_tab",
        "_settings_tab",
        "_project_service",
        "_project_controller",
        "_inventory_controller",
        "_review_controller",
        "_queue_controller",
        "_run_controller",
        "_exports_controller",
        "_settings_controller",
        "_run_state_timer",
        "_review_service",
        "_queue_prep_hint_dismissed",
        "_help_panel",
        "_help_blink_timer",
    )

    def __init__(self) -> None:
        super().__init__()
        app = QApplication.instance()
        if app is not None:
            KIWTheme.apply_base_stylesheet(app)
        self.setWindowTitle("Knowledge Intake Workbench")
        self.resize(1100, 700)
        project_service = ProjectService()
        self._project_service = project_service
        inventory_service = InventoryService()
        review_service = ReviewService()
        self._review_service = review_service
        monitor_service = RunMonitorService()
        self._monitor_service = monitor_service
        self._run_state_timer = QTimer(self)
        self._run_state_timer.setInterval(500)
        self._simple_mode_enabled = True
        self._queue_prep_hint_dismissed = False

        self._header = ProjectHeaderWidget(
            on_browse_raw=self._browse_raw,
            on_browse_output=self._browse_output,
            on_quick_start=lambda: None,
            on_create_project=lambda: None,
            on_load_project=lambda: None,
            on_factory_reset=lambda: None,
            on_scan=lambda: None,
            on_run=lambda: None,
            on_run_both=lambda: None,
            on_pause=lambda: None,
            on_resume=lambda: None,
            on_stop=lambda: None,
            on_open_ai_settings=self._open_ai_settings_from_setup,
            on_open_categories_settings=self._open_categories_settings_from_setup,
            on_refresh_setup_snapshot=self._refresh_setup_snapshot,
            on_setup_quick_ai_save=self._save_ai_settings_from_setup,
            on_setup_quick_add_workspace=self._add_workspace_from_setup,
            on_setup_quick_add_keyword=self._add_keyword_from_setup,
            on_simple_mode_changed=lambda _enabled: None,
            on_profile_changed=lambda _profile: None,
        )
        self._inventory_tab = InventoryTabWidget(
            on_apply=lambda: None,
            on_assign_career=lambda: None,
            on_assign_ai=lambda: None,
            on_assign_archive=lambda: None,
            on_assign_wiki=lambda: None,
            on_auto_assign=lambda: None,
            on_bulk_assign_workspace=lambda: None,
            on_bulk_assign_subfolder=lambda: None,
            on_mark_review_resolved=lambda: None,
            on_refresh=lambda: None,
            on_filter_changed=lambda: None,
        )
        self._review_tab = ReviewTabWidget(
            on_assign_workspace=lambda: None,
            on_assign_subfolder=lambda: None,
            on_mark_approved=lambda: None,
            on_retry_selected=lambda: None,
            on_refresh=lambda: None,
        )
        self._triage_tab = TriageTabWidget(
            get_db_path=lambda: self._project_controller.context.db_path
            if self._project_controller.context
            else None,
            on_assign_workspace_ids=self._triage_assign_workspace,
            on_mark_skip_ids=self._triage_mark_skip,
            on_requeue_ids=self._triage_requeue,
            on_export_csv_ids=self._triage_export_csv,
        )
        self._queue_tab = QueueTabWidget(
            on_refresh=lambda: None,
            on_clear_pending=lambda: None,
            on_requeue_all=lambda: None,
            on_clear_other=lambda: None,
            on_requeue_current=lambda: None,
        )
        self._run_tab = RunMonitorTabWidget(on_refresh_data=lambda: None)
        self._exports_tab = ExportsTabWidget(on_open_folder=lambda: None, on_refresh=lambda: None)
        self._settings_tab = SettingsTabWidget()

        root = QWidget()
        root_layout = QVBoxLayout(root)
        root_layout.addWidget(self._header)
        self._tabs = QTabWidget()
        self._tabs.addTab(self._inventory_tab, "📋 Inventory")
        self._tabs.addTab(self._review_tab, "👁 Review")
        self._tabs.addTab(self._triage_tab, "🔍 Triage")
        self._tabs.addTab(self._queue_tab, "☰ Queue")
        self._tabs.addTab(self._run_tab, "📈 Run Monitor")
        self._tabs.addTab(self._exports_tab, "📤 Exports")
        self._tabs.addTab(self._settings_tab, "⚙ Settings")
        root_layout.addWidget(self._tabs)
        self.setCentralWidget(root)

        self._help_panel = HelpPanel(self)
        self._help_panel.hide()

        _s = QSettings("KIWI", "KnowledgeIntakeWorkbench")
        if not _s.value("help_button_seen", False, type=bool):
            self._help_blink_timer = QTimer(self)
            self._help_blink_timer.timeout.connect(
                lambda: self._header._help_dot.setVisible(
                    not self._header._help_dot.isVisible()
                )
            )
            self._help_blink_timer.start(800)
        else:
            self._help_blink_timer = None
            self._header._help_dot.hide()

        sticky_dual = _s.value("sticky_dual_profiles", False, type=bool)
        self._header.sticky_dual_profiles_check.setChecked(bool(sticky_dual))

        self._project_controller = ProjectController(
            service=project_service,
            monitor_service=monitor_service,
            header=self._header,
            settings_tab=self._settings_tab,
            on_context_set=self._on_context_set,
            info=self._info,
            error=self._error,
            append_log=self._run_tab.append_log,
        )
        self._exports_controller = ExportsController(
            tab=self._exports_tab,
            header=self._header,
            context=lambda: self._project_controller.context,
        )
        self._review_controller = ReviewController(
            service=review_service,
            tab=self._review_tab,
            context=lambda: self._project_controller.context,
            error=self._error,
            info=self._info,
            refresh_inventory=self._refresh_inventory_triggers_triage,
        )
        self._inventory_controller = InventoryController(
            service=inventory_service,
            review_service=review_service,
            tab=self._inventory_tab,
            context=lambda: self._project_controller.context,
            error=self._error,
            info=self._info,
            refresh_review=self._review_controller.refresh,
        )
        self._queue_controller = QueueController(
            service=inventory_service,
            monitor_service=monitor_service,
            tab=self._queue_tab,
            header=self._header,
            context=lambda: self._project_controller.context,
            error=self._error,
            info=self._info,
        )
        self._run_controller = RunController(
            monitor_service=monitor_service,
            header=self._header,
            queue_tab=self._queue_tab,
            run_tab=self._run_tab,
            timer=self._run_state_timer,
            context=lambda: self._project_controller.context,
            refresh_inventory=self._refresh_inventory_triggers_triage,
            refresh_queue=self._queue_controller.refresh,
            refresh_exports=self._exports_controller.refresh,
            set_tab=self._tabs.setCurrentIndex,
            switch_raw_folder=lambda raw_folder: self._project_controller.switch_raw_folder(raw_folder=raw_folder),
            error=self._error,
            info=self._info,
            ask_yes_no=self._ask_yes_no,
        )
        self._settings_controller = SettingsController(
            tab=self._settings_tab,
            context=lambda: self._project_controller.context,
            error=self._error,
            info=self._info,
        )

        self._header.create_btn.clicked.connect(self._project_controller.create_project)
        self._header.load_btn.clicked.connect(self._project_controller.load_project)
        self._header.quick_start_btn.clicked.connect(self._quick_start_create_load_scan)
        self._header.factory_reset_btn.clicked.connect(self._confirm_and_factory_reset)
        self._header.prep_tool_btn.setToolTip(
            "Open Archive Prep Tool — split large file archives into batches before scanning with KIWI"
        )
        self._header.prep_tool_btn.clicked.connect(self.open_prep_tool)
        self._header.settings_shortcut_btn.clicked.connect(
            lambda: self._tabs.setCurrentIndex(6)
        )
        self._header.scan_btn.clicked.connect(self._run_controller.scan_once)
        self._header.run_btn.clicked.connect(self._run_controller.start)
        self._header.run_both_btn.clicked.connect(self._run_controller.run_both_profiles)
        self._header.pause_btn.clicked.connect(self._run_controller.pause)
        self._header.resume_btn.clicked.connect(self._run_controller.resume)
        self._header.stop_btn.clicked.connect(self._run_controller.stop)
        self._header.simple_mode_check.toggled.connect(lambda checked: self._set_simple_mode(not checked))
        self._header.export_profile_combo.currentTextChanged.connect(lambda _v: self._queue_controller.refresh())
        self._header.export_profile_combo.currentTextChanged.connect(lambda _v: self._update_context_banner())
        self._header.raw_folder_edit.textChanged.connect(lambda _v: self._update_context_banner())
        self._header.output_folder_edit.textChanged.connect(lambda _v: self._update_context_banner())
        self._run_state_timer.timeout.connect(self._run_controller.sync_buttons)
        self._run_tab.refresh_preflight_btn.clicked.connect(self._run_controller.refresh_preflight)
        self._tabs.currentChanged.connect(self._on_main_tab_changed)
        self._header.help_btn.clicked.connect(self._on_help_opened)
        self._header.sticky_dual_profiles_check.toggled.connect(
            lambda checked: QSettings("KIWI", "KnowledgeIntakeWorkbench").setValue(
                "sticky_dual_profiles",
                bool(checked),
            )
        )
        self._wire_tab_buttons()
        _theme_toggle = self._header.findChild(QWidget, "theme_toggle")
        if _theme_toggle is not None:
            _theme_toggle.toggled.connect(self._on_theme_toggle)
        self._build_menu()

        self._set_project_tabs_enabled(False)
        self._set_simple_mode(True)
        self._apply_queue_prep_hint_visibility()
        loaded_last_project = self._project_controller.auto_load_last_project()
        if not loaded_last_project:
            self._open_new_project_wizard(first_run=True)
        self._run_controller.sync_buttons()
        self._update_context_banner()

    def open_prep_tool(self) -> None:
        import subprocess
        import sys

        prep_script = Path(__file__).parent.parent / "archive_prep_tool_gui.py"
        if not prep_script.exists():
            QMessageBox.warning(
                self,
                "Archive Prep Tool not found",
                f"Could not find archive_prep_tool_gui.py at:\n{prep_script}\n\n"
                "Please ensure the file is in the project root directory.",
            )
            return
        subprocess.Popen(
            [sys.executable, str(prep_script)],
            creationflags=(subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0),
        )

    def _dismiss_queue_prep_hint(self) -> None:
        self._queue_prep_hint_dismissed = True
        self._apply_queue_prep_hint_visibility()

    def _apply_queue_prep_hint_visibility(self) -> None:
        self._queue_tab.prep_hint_frame.setVisible(not self._queue_prep_hint_dismissed)

    def _build_menu(self) -> None:
        file_menu = self.menuBar().addMenu("File")
        wizard_action = file_menu.addAction("New Project Wizard...")
        wizard_action.triggered.connect(lambda: self._open_new_project_wizard(first_run=False))

    def _open_new_project_wizard(self, *, first_run: bool) -> bool:
        wizard = SetupWizardDialog(
            project_service=self._project_service,
            parent=self if self.isVisible() else None,
        )
        accepted = wizard.exec() == QDialog.Accepted

        if not accepted:
            return False

        result = wizard.result_data
        if result is None:
            return False

        self._project_controller._set_context(result.context)
        self._set_simple_mode(False)
        self._tabs.setCurrentIndex(0)
        self._run_controller.scan_once()
        if not first_run:
            self._info(f"Created project: {result.project_name}")
        return True

    def _wire_tab_buttons(self) -> None:
        self._inventory_tab.apply_btn.clicked.connect(self._inventory_controller.apply_selected)
        self._inventory_tab.assign_career_btn.clicked.connect(
            lambda: self._inventory_controller.assign_selected("career_portfolio")
        )
        self._inventory_tab.assign_ai_btn.clicked.connect(
            lambda: self._inventory_controller.assign_selected("ai_projects")
        )
        self._inventory_tab.assign_archive_btn.clicked.connect(
            lambda: self._inventory_controller.assign_selected("archive")
        )
        self._inventory_tab.assign_wiki_btn.clicked.connect(
            lambda: self._inventory_controller.assign_selected("wiki")
        )
        self._inventory_tab.auto_assign_btn.clicked.connect(self._inventory_controller.auto_assign_selected)
        self._inventory_tab.bulk_assign_workspace_btn.clicked.connect(
            self._inventory_controller.bulk_assign_workspace_selected
        )
        self._inventory_tab.bulk_assign_subfolder_btn.clicked.connect(
            self._inventory_controller.bulk_assign_subfolder_selected
        )
        self._inventory_tab.mark_review_resolved_btn.clicked.connect(
            self._inventory_controller.mark_review_resolved_selected
        )
        self._inventory_tab.refresh_btn.clicked.connect(self._refresh_inventory_triggers_triage)
        self._inventory_tab.filter_mode_combo.currentIndexChanged.connect(self._inventory_controller.refresh)
        self._inventory_tab.workspace_filter_combo.currentIndexChanged.connect(self._inventory_controller.refresh)
        self._inventory_tab.matched_by_filter_combo.currentIndexChanged.connect(self._inventory_controller.refresh)

        self._review_tab.assign_workspace_btn.clicked.connect(self._review_controller.assign_workspace_selected)
        self._review_tab.assign_subfolder_btn.clicked.connect(self._review_controller.assign_subfolder_selected)
        self._review_tab.mark_reviewed_btn.clicked.connect(self._review_controller.mark_selected_approved)
        self._review_tab.retry_btn.clicked.connect(self._review_controller.retry_selected)
        self._review_tab.refresh_btn.clicked.connect(self._refresh_review_and_triage)
        self._queue_tab.refresh_btn.clicked.connect(self._queue_controller.refresh)
        self._queue_tab.clear_pending_btn.clicked.connect(self._confirm_and_clear_pending_queue)
        self._queue_tab.requeue_all_btn.clicked.connect(self._confirm_and_requeue_all)
        self._queue_tab.clear_other_btn.clicked.connect(self._confirm_and_clear_other_pending)
        self._queue_tab.requeue_current_btn.clicked.connect(self._confirm_and_requeue_current_batch)
        self._queue_tab.prep_hint_open_btn.clicked.connect(self.open_prep_tool)
        self._queue_tab.prep_hint_dismiss_btn.clicked.connect(self._dismiss_queue_prep_hint)

        self._run_tab.refresh_btn.clicked.connect(self._refresh_inventory_triggers_triage)
        self._run_tab.refresh_btn.clicked.connect(self._queue_controller.refresh)
        self._exports_tab.refresh_btn.clicked.connect(self._exports_controller.refresh)
        self._exports_tab.open_folder_btn.clicked.connect(self._exports_controller.open_export_folder)
        self._settings_tab.save_btn.clicked.connect(self._settings_controller.save)
        self._settings_tab.save_btn.clicked.connect(self._refresh_setup_snapshot)
        self._settings_tab.test_ollama_btn.clicked.connect(self._settings_controller.test_ollama_connection)
        self._settings_tab.refresh_ollama_models_btn.clicked.connect(self._settings_controller.refresh_ollama_models)
        self._settings_tab.refresh_ollama_models_btn.clicked.connect(self._refresh_setup_snapshot)
        self._settings_tab.enable_ollama_check.toggled.connect(self._settings_controller.update_status)
        self._settings_tab.enable_ollama_check.toggled.connect(lambda _checked: self._refresh_setup_snapshot())
        self._settings_tab.ollama_model_edit.currentTextChanged.connect(self._settings_controller.update_status)
        self._settings_tab.ollama_model_edit.currentTextChanged.connect(lambda _text: self._refresh_setup_snapshot())
        self._settings_tab.ai_provider_combo.currentTextChanged.connect(lambda _text: self._refresh_setup_snapshot())
        self._settings_tab.cloud_model_combo.currentTextChanged.connect(lambda _text: self._refresh_setup_snapshot())
        self._settings_tab.api_key_edit.textChanged.connect(lambda _text: self._refresh_setup_snapshot())

        self._settings_tab.add_workspace_btn.clicked.connect(self._settings_controller.add_workspace)
        self._settings_tab.add_workspace_btn.clicked.connect(self._refresh_setup_snapshot)
        self._settings_tab.remove_workspace_btn.clicked.connect(self._settings_controller.remove_workspace)
        self._settings_tab.remove_workspace_btn.clicked.connect(self._refresh_setup_snapshot)
        self._settings_tab.workspace_list.cellChanged.connect(
            lambda _r, _c: self._settings_controller.save_workspace_edits()
        )
        self._settings_tab.workspace_list.cellChanged.connect(
            lambda _r, _c: self._refresh_setup_snapshot()
        )
        self._settings_tab.add_company_btn.clicked.connect(self._settings_controller.add_company)
        self._settings_tab.add_company_btn.clicked.connect(self._refresh_setup_snapshot)
        self._settings_tab.remove_company_btn.clicked.connect(self._settings_controller.remove_company)
        self._settings_tab.remove_company_btn.clicked.connect(self._refresh_setup_snapshot)
        self._settings_tab.company_list.cellChanged.connect(
            lambda _r, _c: self._settings_controller.save_company_edits()
        )
        self._settings_tab.company_list.cellChanged.connect(
            lambda _r, _c: self._refresh_setup_snapshot()
        )
        self._settings_tab.add_project_btn.clicked.connect(self._settings_controller.add_project)
        self._settings_tab.add_project_btn.clicked.connect(self._refresh_setup_snapshot)
        self._settings_tab.remove_project_btn.clicked.connect(self._settings_controller.remove_project)
        self._settings_tab.remove_project_btn.clicked.connect(self._refresh_setup_snapshot)
        self._settings_tab.project_list.cellChanged.connect(
            lambda _r, _c: self._settings_controller.save_project_edits()
        )
        self._settings_tab.project_list.cellChanged.connect(
            lambda _r, _c: self._refresh_setup_snapshot()
        )
        self._settings_tab.add_rule_btn.clicked.connect(self._settings_controller.add_rule)
        self._settings_tab.add_rule_btn.clicked.connect(self._refresh_setup_snapshot)
        self._settings_tab.remove_rule_btn.clicked.connect(self._settings_controller.remove_rule)
        self._settings_tab.remove_rule_btn.clicked.connect(self._refresh_setup_snapshot)

    def _on_context_set(self) -> None:
        self._set_project_tabs_enabled(True)
        self._refresh_inventory_triggers_triage()
        self._queue_controller.refresh()
        self._exports_controller.refresh()
        self._settings_controller.refresh()
        self._settings_controller.load_categories()
        self._refresh_setup_snapshot()
        self._run_controller.refresh_preflight()
        self._run_controller.sync_buttons()
        self._update_context_banner()
        self._tabs.setCurrentIndex(3 if self._simple_mode_enabled else 0)

    def _set_simple_mode(self, enabled: bool) -> None:
        self._simple_mode_enabled = bool(enabled)
        # Simple mode keeps only Queue, Run Monitor, and Settings visible.
        self._tabs.setTabVisible(0, not enabled)  # Inventory
        self._tabs.setTabVisible(1, not enabled)  # Review
        self._tabs.setTabVisible(2, not enabled)  # Triage
        self._tabs.setTabVisible(3, True)         # Queue
        self._tabs.setTabVisible(4, True)         # Run Monitor
        self._tabs.setTabVisible(5, not enabled)  # Exports
        self._tabs.setTabVisible(6, True)         # Settings

        # Keep primary workflow visible; hide advanced queue controls in Simple Mode.
        self._queue_tab.clear_pending_btn.setVisible(not enabled)
        self._queue_tab.requeue_all_btn.setVisible(not enabled)
        self._queue_tab.clear_other_btn.setVisible(not enabled)

        # Shorter language in Simple Mode to reduce cognitive load.
        if enabled:
            self._header.scan_btn.setText("Scan Folder")
            self._header.run_btn.setText("Run Queue")
            self._queue_tab.requeue_current_btn.setText("Requeue Batch")
            self._queue_tab.refresh_btn.setText("Refresh")
        else:
            self._header.scan_btn.setText("Scan")
            self._header.run_btn.setText("Run")
            self._queue_tab.requeue_current_btn.setText("Requeue Current Batch")
            self._queue_tab.refresh_btn.setText("Refresh Queue")

        if enabled and self._tabs.currentIndex() in {0, 1, 2, 5}:
            self._tabs.setCurrentIndex(3)

    def _update_context_banner(self) -> None:
        ctx = self._project_controller.context
        profile_name = self._header.export_profile_combo.currentText()
        if ctx is None:
            self._header.set_context_status(
                level="warning",
                project_name="No project loaded",
                raw_folder_tail="Raw: --",
                export_profile=profile_name,
            )
            return
        try:
            header_raw = Path(self._header.raw_folder_edit.text().strip() or ".").expanduser().resolve()
            header_out = Path(self._header.output_folder_edit.text().strip() or ".").expanduser().resolve()
        except Exception:  # noqa: BLE001
            self._header.set_context_status(
                level="error",
                project_name=ctx.name,
                raw_folder_tail="Raw path error",
                export_profile=profile_name,
            )
            return
        raw_tail = self._tail_two_components(ctx.raw_folder)
        if header_raw == ctx.raw_folder and header_out == ctx.output_folder:
            self._header.set_context_status(
                level="ok",
                project_name=ctx.name,
                raw_folder_tail=raw_tail,
                export_profile=profile_name,
            )
            return
        self._header.set_context_status(
            level="warning",
            project_name=ctx.name,
            raw_folder_tail=f"Loaded {raw_tail}",
            export_profile=profile_name,
        )

    @staticmethod
    def _tail_two_components(path: Path) -> str:
        parts = path.parts
        if len(parts) >= 2:
            return f"...{parts[-2]}\\{parts[-1]}"
        if parts:
            return f"...{parts[-1]}"
        return "Raw: --"

    def _set_project_tabs_enabled(self, enabled: bool) -> None:
        # Keep Settings visible for guidance even before project load.
        for idx in range(6):
            self._tabs.setTabEnabled(idx, enabled)

    def _browse_raw(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Select Raw Folder")
        if path:
            self._header.raw_folder_edit.setText(path)

    def _browse_output(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Select Output Folder")
        if path:
            self._header.output_folder_edit.setText(path)

    def _quick_start_create_load_scan(self) -> None:
        if self._monitor_service.is_running():
            self._error("Stop the active run before Create+Load+Scan.")
            return
        if not self._project_controller.create_then_load_project():
            return
        self._run_controller.scan_once()

    def _confirm_and_requeue_all(self) -> None:
        answer = QMessageBox.question(
            self,
            "Requeue All Files",
            "Requeue all tracked files for processing?\n\n"
            "This resets run eligibility in the project database so files can be run again.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        self._run_controller.requeue_all()

    def _confirm_and_factory_reset(self) -> None:
        if self._monitor_service.is_running():
            self._error("Stop the active run before factory reset.")
            return
        output_raw = self._header.output_folder_edit.text().strip()
        if not output_raw:
            self._error("Set an Output Folder first.")
            return
        output_folder = Path(output_raw).expanduser().resolve()
        answer = QMessageBox.question(
            self,
            "Factory Reset Project Output",
            "This will permanently delete the following under the selected Output Folder:\n"
            "- .kiw (project metadata + database)\n"
            "- exports\n"
            "- normalized\n\n"
            f"Target: {output_folder}\n\n"
            "Continue?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        typed, ok = QInputDialog.getText(
            self,
            "Confirm Factory Reset",
            "Type RESET to confirm permanent deletion:",
        )
        if not ok:
            return
        if typed.strip() != "RESET":
            self._error("Factory reset cancelled: confirmation text did not match RESET.")
            return
        removed: list[str] = []
        for name in (".kiw", "exports", "normalized"):
            target = output_folder / name
            try:
                if target.is_dir():
                    shutil.rmtree(target)
                    removed.append(str(target))
                elif target.is_file():
                    target.unlink()
                    removed.append(str(target))
            except Exception as exc:  # noqa: BLE001
                self._error(f"Factory reset failed for {target}: {exc}")
                return
        self._project_controller.clear_context()
        self._set_project_tabs_enabled(False)
        self._inventory_controller.refresh()
        self._queue_controller.refresh()
        self._exports_controller.refresh()
        self._settings_controller.refresh()
        self._run_controller.sync_buttons()
        self._update_context_banner()
        self._refresh_triage()
        summary = "\n".join(removed) if removed else "No reset targets were found."
        self._info(f"Factory reset complete.\n\nRemoved:\n{summary}")

    def _confirm_and_clear_pending_queue(self) -> None:
        answer = QMessageBox.question(
            self,
            "Clear Pending Queue",
            "Clear only pending items (new/processing/failed) for the active export profile?\n\n"
            "This keeps file records but marks pending queue entries as completed for this profile.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        self._run_controller.clear_pending_queue()

    def _confirm_and_clear_other_pending(self) -> None:
        answer = QMessageBox.question(
            self,
            "Clear Other Pending Queue",
            "Clear pending items outside the current Raw Folder for the active export profile?\n\n"
            "This preserves file rows and marks those pending queue items completed.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        self._queue_controller.clear_other_pending()

    def _confirm_and_requeue_current_batch(self) -> None:
        answer = QMessageBox.question(
            self,
            "Requeue Current Batch",
            "Requeue all tracked files under the current Raw Folder for the active export profile?\n\n"
            "This makes the current batch eligible to run again.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        self._queue_controller.requeue_current_batch()

    def _refresh_triage(self) -> None:
        ctx = self._project_controller.context
        self._triage_tab.request_load(ctx.db_path if ctx else None)

    def _refresh_inventory_triggers_triage(self) -> None:
        self._inventory_controller.refresh()
        self._refresh_triage()

    def _refresh_review_and_triage(self) -> None:
        self._review_controller.refresh()
        self._refresh_triage()

    def _on_help_opened(self) -> None:
        s = QSettings("KIWI", "KnowledgeIntakeWorkbench")
        s.setValue("help_button_seen", True)
        if self._help_blink_timer is not None:
            self._help_blink_timer.stop()
            self._help_blink_timer = None
        self._header._help_dot.hide()
        self._show_help()

    def _show_help(self) -> None:
        panel = self._help_panel
        panel.setFixedHeight(self.height() - self.menuBar().height())
        panel.move(self.width() - panel.width(), self.menuBar().height())
        panel.show()
        panel.raise_()

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        if self._help_panel.isVisible():
            self._show_help()

    def _on_theme_toggle(self, checked: bool) -> None:
        mode = "light" if checked else "dark"
        app = QApplication.instance()
        if app is not None:
            KIWTheme.apply_full_stylesheet(app, mode)
        self._header.refresh_theme()

    def _on_main_tab_changed(self, index: int) -> None:
        if index == 2:
            self._refresh_triage()
        self._header.factory_reset_btn.setVisible(index == 6)

    def _triage_assign_workspace(self, ids: tuple[int, ...], ws: str) -> None:
        ctx = self._project_controller.context
        if ctx is None or not ids:
            return
        try:
            for fid in ids:
                self._review_service.override_workspace(db_path=ctx.db_path, file_id=fid, workspace=ws)
            self._info(f"Assigned workspace '{ws}' to {len(ids)} file(s).")
        except Exception as exc:  # noqa: BLE001
            self._error(str(exc))
            return
        self._refresh_triage()

    def _triage_mark_skip(self, ids: tuple[int, ...]) -> None:
        ctx = self._project_controller.context
        if ctx is None or not ids:
            return
        db = Database(ctx.db_path)
        repo = FileRepository(db)
        try:
            for fid in ids:
                repo.set_review_required(fid, False)
                repo.set_workspace(fid, "skip")
            self._info(f"Marked {len(ids)} file(s) as skip.")
        except Exception as exc:  # noqa: BLE001
            self._error(str(exc))
            return
        self._refresh_triage()

    def _triage_requeue(self, ids: tuple[int, ...]) -> None:
        ctx = self._project_controller.context
        if ctx is None or not ids:
            return
        db = Database(ctx.db_path)
        repo = FileRepository(db)
        try:
            n = repo.requeue_for_classification(list(ids))
            self._info(f"Requeued {n} file(s) for classification.")
        except Exception as exc:  # noqa: BLE001
            self._error(str(exc))
            return
        self._refresh_triage()

    def _triage_export_csv(self, ids: tuple[int, ...]) -> None:
        if not ids:
            return
        rows = self._triage_tab.rows_for_file_ids(ids)
        if not rows:
            self._error("No rows to export.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export to CSV", "", "CSV Files (*.csv)")
        if not path:
            return
        try:
            export_triage_rows_csv(path, rows)
            self._info(f"Exported {len(rows)} row(s) to {path}")
        except Exception as exc:  # noqa: BLE001
            self._error(str(exc))

    def _info(self, message: str) -> None:
        QMessageBox.information(self, "Knowledge Intake Workbench", message)

    def _error(self, message: str) -> None:
        QMessageBox.critical(self, "Knowledge Intake Workbench", message)

    def _ask_yes_no(self, title: str, message: str) -> bool:
        answer = QMessageBox.question(
            self,
            title,
            message,
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        )
        return answer == QMessageBox.Yes

    def _open_ai_settings_from_setup(self) -> None:
        self._tabs.setCurrentIndex(6)
        self._settings_tab.ai_provider_combo.setFocus()

    def _open_categories_settings_from_setup(self) -> None:
        self._tabs.setCurrentIndex(6)
        self._settings_tab.categories_tab_widget.setCurrentIndex(0)
        self._settings_tab.categories_tab_widget.setFocus()

    def _refresh_setup_snapshot(self) -> None:
        ctx = self._project_controller.context
        if ctx is None:
            self._header.set_setup_snapshot(
                ai_summary="AI: no project loaded",
                categories_summary="Routing: load a project to see workspace/keyword counts",
            )
            self._header.set_setup_quick_editor_state(
                provider="ollama",
                ollama_enabled=False,
                model_name="",
                workspace_options=(),
            )
            return

        provider = self._settings_tab.ai_provider_combo.currentText().strip().lower() or "ollama"
        if provider == "ollama":
            model = self._settings_tab.ollama_model_edit.currentText().strip() or "unset-model"
            enabled = "enabled" if self._settings_tab.enable_ollama_check.isChecked() else "disabled"
            ai_summary = f"AI: Ollama ({enabled}) model={model}"
        else:
            model = self._settings_tab.cloud_model_combo.currentText().strip() or "unset-model"
            key_state = "key set" if self._settings_tab.api_key_edit.text().strip() else "no key"
            ai_summary = f"AI: {provider.title()} model={model} ({key_state})"

        categories_summary = (
            "Routing: "
            f"{self._settings_tab.workspace_list.rowCount()} workspaces, "
            f"{self._settings_tab.company_list.rowCount()} company keywords, "
            f"{self._settings_tab.project_list.rowCount()} project keywords, "
            f"{self._settings_tab.rules_table.rowCount()} force rules"
        )

        workspace_options: list[str] = []
        for row in range(self._settings_tab.workspace_list.rowCount()):
            item = self._settings_tab.workspace_list.item(row, 1)
            if item is None:
                continue
            value = item.text().strip()
            if value and value not in workspace_options:
                workspace_options.append(value)

        if provider == "ollama":
            quick_model = self._settings_tab.ollama_model_edit.currentText().strip()
        else:
            quick_model = self._settings_tab.cloud_model_combo.currentText().strip()

        self._header.set_setup_quick_editor_state(
            provider=provider,
            ollama_enabled=self._settings_tab.enable_ollama_check.isChecked(),
            model_name=quick_model,
            workspace_options=tuple(workspace_options),
        )
        self._header.set_setup_snapshot(
            ai_summary=ai_summary,
            categories_summary=categories_summary,
        )

    def _save_ai_settings_from_setup(self) -> None:
        if self._project_controller.context is None:
            self._error("Create or load a project first.")
            return

        provider = self._header.setup_ai_provider_combo.currentText().strip().lower() or "ollama"
        model = self._header.setup_ai_model_edit.text().strip()

        self._settings_tab.ai_provider_combo.setCurrentText(provider)
        if provider == "ollama":
            self._settings_tab.enable_ollama_check.setChecked(self._header.setup_ai_enable_check.isChecked())
            if model:
                self._settings_tab.ollama_model_edit.setCurrentText(model)
        else:
            if model:
                self._settings_tab.cloud_model_combo.setCurrentText(model)

        self._settings_controller.save()
        self._refresh_setup_snapshot()

    def _add_workspace_from_setup(self) -> None:
        if self._project_controller.context is None:
            self._error("Create or load a project first.")
            return

        label = self._header.setup_workspace_label_edit.text().strip()
        name = self._header.setup_workspace_name_edit.text().strip()
        self._settings_tab.ws_label_edit.setText(label)
        self._settings_tab.ws_name_edit.setText(name)
        self._settings_controller.add_workspace()
        self._header.setup_workspace_label_edit.clear()
        self._header.setup_workspace_name_edit.clear()
        self._refresh_setup_snapshot()

    def _add_keyword_from_setup(self) -> None:
        if self._project_controller.context is None:
            self._error("Create or load a project first.")
            return

        scope = self._header.setup_keyword_scope_combo.currentText().strip()
        keyword = self._header.setup_keyword_edit.text().strip()
        workspace = self._header.setup_keyword_workspace_combo.currentText().strip()
        subfolder = self._header.setup_keyword_subfolder_edit.text().strip()

        if not workspace:
            self._error("Add at least one workspace first, then choose it for the keyword.")
            return

        if scope == "Company":
            self._settings_tab.company_keyword_edit.setText(keyword)
            self._settings_tab.company_ws_combo.setCurrentText(workspace)
            self._settings_controller.add_company()
        elif scope == "Project":
            self._settings_tab.project_keyword_edit.setText(keyword)
            self._settings_tab.project_ws_combo.setCurrentText(workspace)
            self._settings_controller.add_project()
        else:
            self._settings_tab.rule_keyword_edit.setText(keyword)
            self._settings_tab.rule_ws_combo.setCurrentText(workspace)
            self._settings_tab.rule_subfolder_edit.setText(subfolder)
            self._settings_controller.add_rule()

        self._header.setup_keyword_edit.clear()
        self._header.setup_keyword_subfolder_edit.clear()
        self._refresh_setup_snapshot()
