"""Thin GUI controllers to keep MainWindow focused on composition/wiring."""

from __future__ import annotations

import csv
import json
import os
import subprocess
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QComboBox, QLineEdit, QMessageBox, QTableWidgetItem, QWidget

from gui.widgets import (
    ExportsTabWidget,
    InventoryTabWidget,
    ProjectHeaderWidget,
    QueueTabWidget,
    ReviewTabWidget,
    RunMonitorTabWidget,
    SettingsTabWidget,
)
from services.inventory_filter import (
    FILTER_ALL,
    FILTER_FAILED,
    FILTER_MATCHED_BY,
    FILTER_REVIEW_REQUIRED,
    FILTER_WORKSPACE,
)
from services.inventory_service import InventoryService
from services.classification_config import (
    ClassificationConfig,
    DEFAULT_CONFIG_FILENAME,
    load_classification_config,
    save_classification_config,
    write_classification_config_from_seed,
)
from services.project_service import ProjectContext, ProjectService
from services.review_service import WORKSPACE_OPTIONS, ReviewService
from services.run_monitor_service import RunMonitorService
from services.ai_classifier import OllamaAIClassifier


class ProjectController:
    """Project create/load and context-to-UI synchronization."""

    __slots__ = (
        "_service",
        "_monitor",
        "_header",
        "_settings",
        "_on_context_set",
        "_info",
        "_error",
        "_ctx",
        "_append_log",
        "__weakref__",  # required: Qt signals weak-ref the receiver for bound methods
    )

    def __init__(
        self,
        *,
        service: ProjectService,
        monitor_service: RunMonitorService,
        header: ProjectHeaderWidget,
        settings_tab: SettingsTabWidget,
        on_context_set: Callable[[], None],
        info: Callable[[str], None],
        error: Callable[[str], None],
        append_log: Callable[[str], None],
    ) -> None:
        self._service = service
        self._monitor = monitor_service
        self._header = header
        self._settings = settings_tab
        self._on_context_set = on_context_set
        self._info = info
        self._error = error
        self._ctx: ProjectContext | None = None
        self._header.export_profile_combo.currentTextChanged.connect(self._apply_export_profile)
        self._append_log = append_log

    @property
    def context(self) -> ProjectContext | None:
        return self._ctx

    def create_project(self) -> None:
        try:
            ctx = self._service.create_project(
                raw_folder=Path(self._header.raw_folder_edit.text()),
                output_folder=Path(self._header.output_folder_edit.text()),
                name=self._header.project_name_edit.text(),
            )
            self._set_context(ctx)
            self._info(f"Created project: {ctx.name}")
        except Exception as exc:  # noqa: BLE001
            self._error(str(exc))

    def load_project(self) -> None:
        try:
            ctx = self._service.load_project(
                output_folder=Path(self._header.output_folder_edit.text())
            )
            self._set_context(ctx)
            self._info(f"Loaded project: {ctx.name}")
        except Exception as exc:  # noqa: BLE001
            self._error(str(exc))

    def create_then_load_project(self) -> bool:
        """Create a project at header paths, then reload it from metadata."""
        try:
            created = self._service.create_project(
                raw_folder=Path(self._header.raw_folder_edit.text()),
                output_folder=Path(self._header.output_folder_edit.text()),
                name=self._header.project_name_edit.text(),
            )
            loaded = self._service.load_project(output_folder=created.output_folder)
            self._set_context(loaded)
            self._info(f"Created and loaded project: {loaded.name}")
            return True
        except Exception as exc:  # noqa: BLE001
            self._error(str(exc))
            return False

    def auto_load_last_project(self) -> bool:
        ctx = self._service.try_load_last_project()
        if ctx is None:
            return False
        self._set_context(ctx)
        return True

    def ensure_context(self) -> bool:
        if self._ctx is None:
            self._error("Create or load a project first.")
            return False
        return True

    def clear_context(self) -> None:
        self._ctx = None

    def refresh_settings(self) -> None:
        if self._ctx is None:
            self._settings.info_label.setText("Project settings will appear here after a project is loaded.")
            return
        self._settings.info_label.setText(
            "\n".join(
                [
                    f"Project: {self._ctx.name}",
                    f"Database: {self._ctx.db_path}",
                    f"Raw Folder: {self._ctx.raw_folder}",
                    f"Output Folder: {self._ctx.output_folder}",
                    f"Active Export Profile: {self._header.export_profile_combo.currentText()}",
                ]
            )
        )

    def switch_raw_folder(self, *, raw_folder: Path) -> None:
        if self._ctx is None:
            raise RuntimeError("Create or load a project first.")
        new_raw = raw_folder.expanduser().resolve()
        if not new_raw.is_dir():
            raise ValueError(f"Raw folder does not exist or is not a directory: {new_raw}")

        try:
            payload = json.loads(self._ctx.project_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Project metadata is invalid JSON: {self._ctx.project_file}") from exc
        if not isinstance(payload, dict):
            raise ValueError(f"Project metadata is invalid: {self._ctx.project_file}")

        payload["raw_folder"] = str(new_raw)
        self._ctx.project_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")

        updated = ProjectContext(
            name=self._ctx.name,
            raw_folder=new_raw,
            output_folder=self._ctx.output_folder,
            db_path=self._ctx.db_path,
            project_file=self._ctx.project_file,
        )
        self._set_context(updated)

    def _set_context(self, ctx: ProjectContext) -> None:
        self._ctx = ctx
        self._header.project_name_edit.setText(ctx.name)
        self._header.raw_folder_edit.setText(str(ctx.raw_folder))
        self._header.output_folder_edit.setText(str(ctx.output_folder))
        self._monitor.configure(
            db_path=ctx.db_path,
            raw_folder=ctx.raw_folder,
            output_folder=ctx.output_folder,
            export_profile=self._header.export_profile_combo.currentText(),
            log=self._append_log,
        )
        self._on_context_set()

    def _apply_export_profile(self, profile: str) -> None:
        if self._ctx is None:
            return
        self._monitor.configure(
            db_path=self._ctx.db_path,
            raw_folder=self._ctx.raw_folder,
            output_folder=self._ctx.output_folder,
            export_profile=profile,
            log=self._append_log,
        )
        self.refresh_settings()
        self._append_log(f"Active export profile set to '{profile}'.")


class ReviewController:
    """Review tab read/update operations."""

    __slots__ = ("_service", "_tab", "_context", "_error", "_info", "_refresh_inventory", "__weakref__")

    def __init__(
        self,
        *,
        service: ReviewService,
        tab: ReviewTabWidget,
        context: Callable[[], ProjectContext | None],
        error: Callable[[str], None],
        info: Callable[[str], None],
        refresh_inventory: Callable[[], None],
    ) -> None:
        self._service = service
        self._tab = tab
        self._context = context
        self._error = error
        self._info = info
        self._refresh_inventory = refresh_inventory

    def refresh(self) -> None:
        ctx = self._context()
        if ctx is None:
            return
        cfg = load_classification_config(ctx.output_folder / ".kiw" / DEFAULT_CONFIG_FILENAME)
        data = self._service.get_audit_queue(
            db_path=ctx.db_path,
            low_confidence_threshold=cfg.review_confidence_threshold,
        )
        self._fill_group_table(self._tab.review_required_table, data.review_required)
        self._fill_group_table(self._tab.fallback_table, data.fallback)
        self._fill_group_table(self._tab.failed_table, data.failed)
        self._fill_group_table(self._tab.low_confidence_table, data.low_confidence)
        self._tab.summary_panel.setPlainText(self._format_summary(data))
        self._tab.token_panel.setPlainText(self._format_tokens(data))

    def mark_selected_approved(self) -> None:
        ctx = self._context()
        if ctx is None:
            return
        file_ids = self._selected_file_ids()
        if not file_ids:
            self._error("Select one or more audit rows first.")
            return
        count = self._service.mark_reviewed(db_path=ctx.db_path, file_ids=tuple(file_ids))
        self._info(f"Marked {count} file(s) as approved.")
        self._refresh_inventory()
        self.refresh()

    def assign_workspace_selected(self) -> None:
        ctx = self._context()
        if ctx is None:
            return
        file_ids = self._selected_file_ids()
        if not file_ids:
            self._error("Select one or more audit rows first.")
            return
        try:
            ws = self._tab.review_workspace_combo.currentText()
            for fid in file_ids:
                self._service.override_workspace(db_path=ctx.db_path, file_id=fid, workspace=ws)
            self._info(f"Assigned workspace '{ws}' to {len(file_ids)} file(s).")
            self._refresh_inventory()
            self.refresh()
        except Exception as exc:  # noqa: BLE001
            self._error(str(exc))

    def assign_subfolder_selected(self) -> None:
        ctx = self._context()
        if ctx is None:
            return
        file_ids = self._selected_file_ids()
        if not file_ids:
            self._error("Select one or more audit rows first.")
            return
        subfolder = self._tab.review_subfolder_edit.text()
        try:
            for fid in file_ids:
                self._service.override_subfolder(db_path=ctx.db_path, file_id=fid, subfolder=subfolder)
            self._info(f"Assigned subfolder to {len(file_ids)} file(s).")
            self._refresh_inventory()
            self.refresh()
        except Exception as exc:  # noqa: BLE001
            self._error(str(exc))

    def retry_selected(self) -> None:
        ctx = self._context()
        if ctx is None:
            return
        ids = self._selected_file_ids()
        if not ids:
            self._error("Select one or more audit rows first.")
            return
        count = self._service.retry_failed_files(db_path=ctx.db_path, file_ids=tuple(ids))
        self._info(f"Queued {count} failed file(s) for retry.")
        self._refresh_inventory()
        self.refresh()

    def _selected_file_ids(self) -> list[int]:
        ids: list[int] = []
        for table in (
            self._tab.review_required_table,
            self._tab.fallback_table,
            self._tab.failed_table,
            self._tab.low_confidence_table,
        ):
            for idx in table.selectionModel().selectedRows():
                item = table.item(idx.row(), 0)
                if item is None:
                    continue
                try:
                    ids.append(int(item.text()))
                except ValueError:
                    continue
        seen: set[int] = set()
        out: list[int] = []
        for fid in ids:
            if fid not in seen:
                seen.add(fid)
                out.append(fid)
        return out

    @staticmethod
    def _fill_group_table(table, rows) -> None:
        table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            table.setItem(i, 0, QTableWidgetItem(str(row.file_id)))
            table.setItem(i, 1, QTableWidgetItem(row.file_name))
            table.setItem(i, 2, QTableWidgetItem(row.workspace))
            table.setItem(i, 3, QTableWidgetItem(row.subfolder))
            table.setItem(i, 4, QTableWidgetItem(f"{row.confidence:.2f}"))
            table.setItem(i, 5, QTableWidgetItem(row.matched_by))
            table.setItem(i, 6, QTableWidgetItem(row.reason))

    @staticmethod
    def _format_summary(data) -> str:
        lines = [f"Unresolved files: {data.summary.unresolved_count}", "", "Count by matched_by:"]
        if data.summary.by_matched_by:
            lines.extend(f"- {k}: {v}" for k, v in data.summary.by_matched_by)
        else:
            lines.append("- (none)")
        lines.extend(["", "Count by workspace:"])
        if data.summary.by_workspace:
            lines.extend(f"- {k}: {v}" for k, v in data.summary.by_workspace)
        else:
            lines.append("- (none)")
        return "\n".join(lines)

    @staticmethod
    def _format_tokens(data) -> str:
        if not data.summary.common_tokens:
            return "No common unmatched filename tokens found from fallback files."
        return "\n".join(f"- {token}: {count}" for token, count in data.summary.common_tokens)


_INVENTORY_FILTER_LABEL_TO_MODE: dict[str, str] = {
    "All": FILTER_ALL,
    "Needs review": FILTER_REVIEW_REQUIRED,
    "Failed": FILTER_FAILED,
    "Workspace": FILTER_WORKSPACE,
    "Matched By": FILTER_MATCHED_BY,
}


class InventoryController:
    """Inventory table rendering and workspace/category actions."""

    __slots__ = (
        "_service",
        "_review_service",
        "_tab",
        "_context",
        "_error",
        "_info",
        "_refresh_review",
        "__weakref__",
    )

    def __init__(
        self,
        *,
        service: InventoryService,
        review_service: ReviewService,
        tab: InventoryTabWidget,
        context: Callable[[], ProjectContext | None],
        error: Callable[[str], None],
        info: Callable[[str], None],
        refresh_review: Callable[[], None],
    ) -> None:
        self._service = service
        self._review_service = review_service
        self._tab = tab
        self._context = context
        self._error = error
        self._info = info
        self._refresh_review = refresh_review

    def refresh(self) -> None:
        ctx = self._context()
        if ctx is None:
            return
        workspaces, matched_by_vals = self._service.load_filter_options(db_path=ctx.db_path)
        self._populate_filter_combos(workspaces, matched_by_vals)
        self._sync_filter_widgets()

        mode = _INVENTORY_FILTER_LABEL_TO_MODE.get(
            self._tab.filter_mode_combo.currentText(),
            FILTER_ALL,
        )
        ws_filter: str | None = None
        mb_filter: str | None = None
        if mode == FILTER_WORKSPACE:
            ws_filter = self._tab.workspace_filter_combo.currentText().strip() or None
        elif mode == FILTER_MATCHED_BY:
            mb_filter = self._tab.matched_by_filter_combo.currentText().strip() or None

        rows = self._service.load_rows(
            db_path=ctx.db_path,
            filter_mode=mode,
            workspace_filter=ws_filter,
            matched_by_filter=mb_filter,
        )
        self._tab.table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            name_item = QTableWidgetItem(row.file_name)
            name_item.setData(0x0100, row.file_id)
            self._tab.table.setItem(i, 0, name_item)
            self._tab.table.setItem(i, 1, QTableWidgetItem(row.file_type))
            self._tab.table.setItem(i, 2, QTableWidgetItem(str(row.size)))
            self._tab.table.setItem(i, 3, QTableWidgetItem(row.status))
            self._tab.table.setItem(i, 4, QTableWidgetItem(row.category))
            ws_combo = QComboBox()
            ws_combo.addItems(list(WORKSPACE_OPTIONS))
            display_ws = row.workspace if row.workspace in WORKSPACE_OPTIONS else "unassigned"
            ws_combo.setCurrentText(display_ws)
            ws_combo.currentTextChanged.connect(
                lambda value, fid=row.file_id: self._set_workspace_for_file(fid, value)
            )
            self._tab.table.setCellWidget(i, 5, ws_combo)
            sf_edit = QLineEdit()
            sf_edit.setText(row.subfolder)
            sf_edit.editingFinished.connect(
                lambda fid=row.file_id, ed=sf_edit: self._set_subfolder_for_file(fid, ed.text())
            )
            self._tab.table.setCellWidget(i, 6, sf_edit)
            matched_item = QTableWidgetItem(row.matched_by or "")
            self._tab.table.setItem(i, 7, matched_item)
            self._tab.table.setItem(i, 8, QTableWidgetItem(f"{row.confidence:.2f}"))
            self._tab.table.setItem(i, 9, QTableWidgetItem("yes" if row.review_required else "no"))
            self._tab.table.setItem(i, 10, QTableWidgetItem(row.classification_reason))
        self._refresh_review()

    def _populate_filter_combos(self, workspaces: tuple[str, ...], matched_by: tuple[str, ...]) -> None:
        w = self._tab.workspace_filter_combo
        m = self._tab.matched_by_filter_combo
        keep_ws = w.currentText()
        keep_mb = m.currentText()
        w.blockSignals(True)
        m.blockSignals(True)
        w.clear()
        w.addItems(list(workspaces))
        m.clear()
        m.addItems(list(matched_by))
        if keep_ws and w.findText(keep_ws) >= 0:
            w.setCurrentIndex(w.findText(keep_ws))
        if keep_mb and m.findText(keep_mb) >= 0:
            m.setCurrentIndex(m.findText(keep_mb))
        w.blockSignals(False)
        m.blockSignals(False)

    def _sync_filter_widgets(self) -> None:
        mode = self._tab.filter_mode_combo.currentText()
        self._tab.workspace_filter_combo.setEnabled(mode == "Workspace")
        self._tab.matched_by_filter_combo.setEnabled(mode == "Matched By")

    def bulk_assign_workspace_selected(self) -> None:
        ctx = self._context()
        if ctx is None:
            return
        file_ids = self._selected_file_ids()
        if not file_ids:
            self._error("Select one or more inventory rows first.")
            return
        ws = self._tab.bulk_workspace_combo.currentText()
        try:
            for fid in file_ids:
                self._review_service.override_workspace(db_path=ctx.db_path, file_id=fid, workspace=ws)
            self._info(f"Assigned workspace '{ws}' to {len(file_ids)} file(s).")
            self.refresh()
        except Exception as exc:  # noqa: BLE001
            self._error(str(exc))

    def bulk_assign_subfolder_selected(self) -> None:
        ctx = self._context()
        if ctx is None:
            return
        file_ids = self._selected_file_ids()
        if not file_ids:
            self._error("Select one or more inventory rows first.")
            return
        sub = self._tab.bulk_subfolder_edit.text()
        try:
            for fid in file_ids:
                self._review_service.override_subfolder(db_path=ctx.db_path, file_id=fid, subfolder=sub)
            self._info(f"Updated subfolder for {len(file_ids)} file(s).")
            self.refresh()
        except Exception as exc:  # noqa: BLE001
            self._error(str(exc))

    def mark_review_resolved_selected(self) -> None:
        ctx = self._context()
        if ctx is None:
            return
        file_ids = self._selected_file_ids()
        if not file_ids:
            self._error("Select one or more inventory rows first.")
            return
        count = self._review_service.mark_reviewed(db_path=ctx.db_path, file_ids=tuple(file_ids))
        self._info(f"Marked review resolved for {count} file(s).")
        self.refresh()

    def apply_selected(self) -> None:
        ctx = self._context()
        if ctx is None:
            return
        file_ids = self._selected_file_ids()
        if not file_ids:
            self._error("Select one or more inventory rows first.")
            return
        try:
            count = self._review_service.apply_category_workspace(
                db_path=ctx.db_path,
                file_ids=tuple(file_ids),
                category=self._tab.category_combo.currentText(),
                workspace=self._tab.workspace_combo.currentText(),
            )
            self._info(f"Updated {count} file(s).")
            self.refresh()
        except Exception as exc:  # noqa: BLE001
            self._error(str(exc))

    def assign_selected(self, workspace: str) -> None:
        ctx = self._context()
        if ctx is None:
            return
        file_ids = self._selected_file_ids()
        if not file_ids:
            self._error("Select one or more inventory rows first.")
            return
        try:
            for fid in file_ids:
                self._review_service.override_workspace(
                    db_path=ctx.db_path,
                    file_id=fid,
                    workspace=workspace,
                )
            self._info(f"Assigned workspace '{workspace}' to {len(file_ids)} file(s).")
            self.refresh()
        except Exception as exc:  # noqa: BLE001
            self._error(str(exc))

    def auto_assign_selected(self) -> None:
        ctx = self._context()
        if ctx is None:
            return
        file_ids = self._selected_file_ids()
        if not file_ids:
            self._error("Select one or more inventory rows first.")
            return
        try:
            count = self._review_service.auto_assign_workspaces(db_path=ctx.db_path, file_ids=tuple(file_ids))
            self._info(f"Auto-assigned workspaces for {count} file(s).")
            self.refresh()
        except Exception as exc:  # noqa: BLE001
            self._error(str(exc))

    def _set_workspace_for_file(self, file_id: int, workspace: str) -> None:
        ctx = self._context()
        if ctx is None:
            return
        try:
            self._review_service.override_workspace(
                db_path=ctx.db_path,
                file_id=file_id,
                workspace=workspace,
            )
        except Exception as exc:  # noqa: BLE001
            self._error(str(exc))

    def _set_subfolder_for_file(self, file_id: int, subfolder: str) -> None:
        ctx = self._context()
        if ctx is None:
            return
        try:
            self._review_service.override_subfolder(
                db_path=ctx.db_path,
                file_id=file_id,
                subfolder=subfolder,
            )
        except Exception as exc:  # noqa: BLE001
            self._error(str(exc))

    def _selected_file_ids(self) -> list[int]:
        ids: list[int] = []
        for idx in self._tab.table.selectionModel().selectedRows():
            item = self._tab.table.item(idx.row(), 0)
            if item is None:
                continue
            fid = item.data(0x0100)
            if isinstance(fid, int):
                ids.append(fid)
        seen: set[int] = set()
        out: list[int] = []
        for fid in ids:
            if fid not in seen:
                seen.add(fid)
                out.append(fid)
        return out


class QueueController:
    """Queue tab rendering for current raw folder vs other pending items."""

    __slots__ = ("_service", "_monitor", "_tab", "_header", "_context", "_error", "_info", "__weakref__")

    def __init__(
        self,
        *,
        service: InventoryService,
        monitor_service: RunMonitorService,
        tab: QueueTabWidget,
        header: ProjectHeaderWidget,
        context: Callable[[], ProjectContext | None],
        error: Callable[[str], None],
        info: Callable[[str], None],
    ) -> None:
        self._service = service
        self._monitor = monitor_service
        self._tab = tab
        self._header = header
        self._context = context
        self._error = error
        self._info = info

    def refresh(self) -> None:
        ctx = self._context()
        if ctx is None:
            self._tab.summary_label.setText("Load a project to inspect queue state.")
            self._tab.current_batch_table.setRowCount(0)
            self._tab.other_pending_table.setRowCount(0)
            return
        try:
            current_rows, other_rows = self._service.load_pending_queue_split(
                db_path=ctx.db_path,
                raw_folder=ctx.raw_folder,
                export_profile=self._header.export_profile_combo.currentText(),
            )
            self._fill_table(self._tab.current_batch_table, current_rows)
            self._fill_table(self._tab.other_pending_table, other_rows)
            profile = self._header.export_profile_combo.currentText()
            self._tab.summary_label.setText(
                f"Active profile: {profile} | Raw folder: {ctx.raw_folder} | "
                f"Current batch pending: {len(current_rows)} | Other pending: {len(other_rows)}"
            )
        except Exception as exc:  # noqa: BLE001
            self._error(str(exc))

    def clear_other_pending(self) -> None:
        if not self._ensure_loaded_project_paths_match_header():
            return
        try:
            count = self._monitor.clear_pending_outside_current_raw()
            self.refresh()
            self._info(f"Cleared {count} pending file(s) outside the current raw folder.")
        except Exception as exc:  # noqa: BLE001
            self._error(str(exc))

    def requeue_current_batch(self) -> None:
        if not self._ensure_loaded_project_paths_match_header():
            return
        try:
            count = self._monitor.requeue_current_raw()
            self.refresh()
            self._info(f"Requeued {count} file(s) in the current raw folder.")
        except Exception as exc:  # noqa: BLE001
            self._error(str(exc))

    def _ensure_loaded_project_paths_match_header(self) -> bool:
        ctx = self._context()
        if ctx is None:
            self._error("Create or load a project first.")
            return False
        header_raw = Path(self._header.raw_folder_edit.text().strip() or ".").expanduser().resolve()
        header_out = Path(self._header.output_folder_edit.text().strip() or ".").expanduser().resolve()
        if header_raw != ctx.raw_folder or header_out != ctx.output_folder:
            self._error(
                "Raw/Output folder fields do not match the loaded project context. "
                "Click Load Project (for existing output) or Create Project (for new output) before queue actions."
            )
            return False
        return True

    @staticmethod
    def _fill_table(table, rows) -> None:
        table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            table.setItem(i, 0, QTableWidgetItem(str(row.file_id)))
            table.setItem(i, 1, QTableWidgetItem(row.file_name))
            table.setItem(i, 2, QTableWidgetItem(row.folder))
            table.setItem(i, 3, QTableWidgetItem(row.next_stage))
            table.setItem(i, 4, QTableWidgetItem(row.queue_status))
            table.setItem(i, 5, QTableWidgetItem(row.workspace))
            table.setItem(i, 6, QTableWidgetItem(row.subfolder))
            table.setItem(i, 7, QTableWidgetItem(row.updated_at))


class RunController:
    """Run/scan controls and live monitor status synchronization."""

    __slots__ = (
        "_monitor",
        "_header",
        "_queue_tab",
        "_run_tab",
        "_timer",
        "_context",
        "_refresh_inventory",
        "_refresh_queue",
        "_refresh_exports",
        "_set_tab",
        "_switch_raw_folder",
        "_error",
        "_info",
        "_ask_yes_no",
        "_last_status_note",
        "_last_handled_run_id",
        "_auto_follow_openwebui",
        "__weakref__",
    )

    def __init__(
        self,
        *,
        monitor_service: RunMonitorService,
        header: ProjectHeaderWidget,
        queue_tab: QueueTabWidget,
        run_tab: RunMonitorTabWidget,
        timer: QTimer,
        context: Callable[[], ProjectContext | None],
        refresh_inventory: Callable[[], None],
        refresh_queue: Callable[[], None],
        refresh_exports: Callable[[], None],
        set_tab: Callable[[int], None],
        switch_raw_folder: Callable[[Path], None],
        error: Callable[[str], None],
        info: Callable[[str], None],
        ask_yes_no: Callable[[str, str], bool],
    ) -> None:
        self._monitor = monitor_service
        self._header = header
        self._queue_tab = queue_tab
        self._run_tab = run_tab
        self._timer = timer
        self._context = context
        self._refresh_inventory = refresh_inventory
        self._refresh_queue = refresh_queue
        self._refresh_exports = refresh_exports
        self._set_tab = set_tab
        self._switch_raw_folder = switch_raw_folder
        self._error = error
        self._info = info
        self._ask_yes_no = ask_yes_no
        self._last_status_note = ""
        self._last_handled_run_id = 0
        self._auto_follow_openwebui = False

    def append_log(self, text: str) -> None:
        self._run_tab.append_log(text)

    def start(self) -> None:
        if not self._ensure_context() or not self._ensure_loaded_project_paths_match_header():
            return
        if self._maybe_load_next_batch_from_run_click():
            if self._sticky_dual_profiles_enabled():
                self.start()
            return
        try:
            if self._sticky_dual_profiles_enabled():
                self._auto_follow_openwebui = True
                if self._header.export_profile_combo.currentText() != "anythingllm":
                    self._header.export_profile_combo.setCurrentText("anythingllm")
            summary = self._monitor.build_preflight_summary(preview_limit=5)
            self._render_preflight(summary)
            if summary.wiki_share_cap_exceeded and summary.classification_total_files > 0:
                self._error(
                    "Run blocked by preflight: predicted wiki share "
                    f"{summary.classification_wiki_share:.0%} exceeds cap "
                    f"{summary.preflight_wiki_share_cap:.0%}. Adjust settings/rules, then retry."
                )
                self._set_tab(4)
                return
            self._monitor.start(scan_first=False)
            self.append_log("Run requested.")
            self._set_status_note("Run started.")
            self._timer.start()
            self.sync_buttons()
            self._set_tab(4)
        except Exception as exc:  # noqa: BLE001
            self._error(str(exc))

    def run_both_profiles(self) -> None:
        if not self._ensure_context() or not self._ensure_loaded_project_paths_match_header():
            return
        if self._monitor.is_running():
            self._error("A run is already active.")
            return
        self._auto_follow_openwebui = True
        if self._header.export_profile_combo.currentText() != "anythingllm":
            self._header.export_profile_combo.setCurrentText("anythingllm")
        self.start()

    def _sticky_dual_profiles_enabled(self) -> bool:
        return bool(self._header.sticky_dual_profiles_check.isChecked())

    def scan_once(self) -> None:
        if not self._ensure_context() or not self._ensure_loaded_project_paths_match_header():
            return
        try:
            self._monitor.scan_once()
            self._refresh_inventory()
            self._refresh_queue()
            self._refresh_exports()
            self._set_tab(0)
        except Exception as exc:  # noqa: BLE001
            self._error(str(exc))

    def clear_pending_queue(self) -> None:
        if not self._ensure_context() or not self._ensure_loaded_project_paths_match_header():
            return
        try:
            count = self._monitor.clear_pending_queue()
            self.append_log(f"Clear pending queue requested for {count} file(s).")
            self._set_status_note(f"Cleared {count} pending file(s) at {datetime.now().strftime('%H:%M:%S')}.")
            self.sync_buttons()
            self.refresh_preflight()
            self._refresh_inventory()
            self._refresh_queue()
            self._refresh_exports()
            self._info(f"Cleared {count} pending file(s) for the active profile.")
        except Exception as exc:  # noqa: BLE001
            self._error(str(exc))

    def pause(self) -> None:
        self._monitor.pause()
        self._set_status_note("Run paused.")
        self.sync_buttons()

    def resume(self) -> None:
        self._monitor.resume()
        self._set_status_note("Run resumed.")
        self.sync_buttons()

    def stop(self) -> None:
        self._monitor.stop()
        self._set_status_note("Stop requested.")
        self.sync_buttons()

    def requeue_all(self) -> None:
        if not self._ensure_context():
            return
        try:
            count = self._monitor.requeue_all()
            self.append_log(f"Requeue requested for {count} file(s).")
            self._set_status_note(f"Requeued {count} file(s) at {datetime.now().strftime('%H:%M:%S')}.")
            self.sync_buttons()
            self.refresh_preflight()
            self._refresh_inventory()
            self._refresh_queue()
            self._refresh_exports()
            self._info(f"Requeued {count} file(s) for processing.")
        except Exception as exc:  # noqa: BLE001
            self._error(str(exc))

    def refresh_preflight(self) -> None:
        if self._context() is None:
            self._run_tab.set_preflight_summary("Load a project to preview what Run will do.")
            return
        try:
            summary = self._monitor.build_preflight_summary(preview_limit=5)
            self._render_preflight(summary)
        except Exception as exc:  # noqa: BLE001
            self._run_tab.set_preflight_summary(f"Preflight preview unavailable: {exc}")

    def _render_preflight(self, summary) -> None:
        targets = "AnythingLLM, Open WebUI"
        self._run_tab.set_preflight_dashboard(
            summary_sentence=summary.human_summary,
            total_files=summary.total_files,
            pending_files=summary.pending_files,
            processed_files=summary.processed_files,
            failed_files=summary.failed_files,
            active_target=summary.active_export_profile,
            available_targets=targets,
            ai_mode=summary.ai_mode,
            ollama_enabled=summary.ollama_enabled,
        )

    def sync_buttons(self) -> None:
        for line in self._monitor.drain_logs():
            self.append_log(line)
        snap = self._monitor.snapshot()
        self._run_tab.set_snapshot(
            state=snap.state,
            total_files=snap.total_files,
            processed=snap.processed,
            failed=snap.failed,
            review_required=snap.review_required,
            current_file=snap.current_file,
            current_stage=snap.current_stage,
        )
        running = self._monitor.is_running()
        ready = self._context() is not None
        self._header.scan_btn.setEnabled(ready and not running)
        self._header.run_btn.setEnabled(ready and not running)
        self._header.run_both_btn.setEnabled(ready and not running)
        self._header.pause_btn.setEnabled(running)
        self._header.resume_btn.setEnabled(running)
        self._header.stop_btn.setEnabled(running)
        self._queue_tab.requeue_all_btn.setEnabled(ready and not running)
        self._queue_tab.clear_pending_btn.setEnabled(ready and not running)
        self._sync_run_button_label(ready=ready, running=running)
        if not running and self._timer.isActive():
            self._timer.stop()
            if ready:
                self._refresh_inventory()
                self._refresh_queue()
                self._refresh_exports()
                self.refresh_preflight()
        self._maybe_offer_or_start_followup()

    def _default_run_button_label(self) -> str:
        return "Run" if self._header.simple_mode_check.isChecked() else "Run Queue"

    def _sync_run_button_label(self, *, ready: bool, running: bool) -> None:
        if running or not ready:
            self._header.run_btn.setText(self._default_run_button_label())
            return
        overview = self._monitor.pending_batch_overview()
        if overview.current_pending == 0 and overview.other_pending > 0 and overview.next_batch_folder is not None:
            self._header.run_btn.setText("Load Next Batch")
            return
        self._header.run_btn.setText(self._default_run_button_label())

    def _maybe_load_next_batch_from_run_click(self) -> bool:
        overview = self._monitor.pending_batch_overview()
        next_batch = overview.next_batch_folder
        if overview.current_pending > 0 or overview.other_pending <= 0 or next_batch is None:
            return False
        self._switch_raw_folder(next_batch)
        self.append_log(f"Loaded next batch folder: {next_batch}")
        self._set_status_note(f"Loaded next batch folder: {next_batch}")
        self._refresh_inventory()
        self._refresh_queue()
        self._refresh_exports()
        self.refresh_preflight()
        self._set_tab(3)
        self.sync_buttons()
        self._info(f"Loaded next batch folder: {next_batch}")
        return True

    def _maybe_offer_or_start_followup(self) -> None:
        summary = self._monitor.get_last_completed_run()
        if summary is None:
            return
        if summary.run_id <= self._last_handled_run_id:
            return
        self._last_handled_run_id = summary.run_id
        if summary.final_state != "completed":
            self._auto_follow_openwebui = False
            return
        if self._monitor.is_running():
            return

        sticky_dual = self._sticky_dual_profiles_enabled()
        if summary.export_profile == "open_webui":
            if sticky_dual:
                self._auto_follow_openwebui = True
                if self._maybe_load_next_batch_from_run_click():
                    self.append_log("Sticky dual-profile mode: starting next batch automatically.")
                    self.start()
            return

        if summary.export_profile != "anythingllm":
            return

        if self._auto_follow_openwebui or sticky_dual:
            self._auto_follow_openwebui = False
            self._run_openwebui_followup(summary)
            return

        message = (
            f"AnythingLLM run completed. Processed {summary.files_started} file(s) "
            f"(ok: {summary.files_finished_ok}, failed: {summary.files_marked_failed}).\n\n"
            "Do you also want to process the current batch for OpenWebUI?"
        )
        if self._ask_yes_no("Process OpenWebUI Batch", message):
            self._run_openwebui_followup(summary)

    def _run_openwebui_followup(self, summary) -> None:
        if not self._ensure_context() or not self._ensure_loaded_project_paths_match_header():
            return
        if self._header.export_profile_combo.currentText() != "open_webui":
            self._header.export_profile_combo.setCurrentText("open_webui")
        try:
            requeued = self._monitor.requeue_current_raw()
            self.append_log(
                f"AnythingLLM processed {summary.files_started} file(s); preparing OpenWebUI follow-up. "
                f"Requeued {requeued} current-batch file(s)."
            )
            self._monitor.start(scan_first=False)
            self._set_status_note("OpenWebUI follow-up run started.")
            self._timer.start()
            self.sync_buttons()
            self._set_tab(4)
        except Exception as exc:  # noqa: BLE001
            self._error(str(exc))

    def _set_status_note(self, text: str) -> None:
        self._last_status_note = text
        self._run_tab.set_status_note(text)

    def _ensure_context(self) -> bool:
        if self._context() is None:
            self._error("Create or load a project first.")
            return False
        return True

    def _ensure_loaded_project_paths_match_header(self) -> bool:
        ctx = self._context()
        if ctx is None:
            self._error("Create or load a project first.")
            return False
        header_raw = Path(self._header.raw_folder_edit.text().strip() or ".").expanduser().resolve()
        header_out = Path(self._header.output_folder_edit.text().strip() or ".").expanduser().resolve()
        if header_raw != ctx.raw_folder or header_out != ctx.output_folder:
            self._error(
                "Raw/Output folder fields do not match the loaded project context. "
                "Click Load Project (for existing output) or Create Project (for new output) before Scan/Run."
            )
            return False
        return True


class ExportsController:
    """Export summary rendering for local manual workflows."""

    __slots__ = ("_tab", "_header", "_context", "__weakref__")

    def __init__(
        self,
        *,
        tab: ExportsTabWidget,
        header: ProjectHeaderWidget,
        context: Callable[[], ProjectContext | None],
    ) -> None:
        self._tab = tab
        self._header = header
        self._context = context

    def refresh(self) -> None:
        ctx = self._context()
        if ctx is None:
            self._tab.anythingllm_summary.setPlainText("Create or load a project to view export locations.")
            self._tab.openwebui_summary.setPlainText("Create or load a project to view export locations.")
            self._tab.latest_manifest_label.setText("Latest manifests: n/a")
            self._tab.preview_table.setRowCount(0)
            return
        root = ctx.output_folder / "exports"
        anything = self._profile_summary(root / "anythingllm")
        openweb = self._profile_summary(root / "open_webui")
        self._tab.anythingllm_summary.setPlainText(anything)
        self._tab.openwebui_summary.setPlainText(openweb)
        self._tab.latest_manifest_label.setText(self._latest_manifest_line(root))
        self._fill_preview_table(root)

    def open_export_folder(self) -> None:
        ctx = self._context()
        if ctx is None:
            return
        exports_root = ctx.output_folder / "exports"
        exports_root.mkdir(parents=True, exist_ok=True)
        try:
            os.startfile(str(exports_root))  # type: ignore[attr-defined]
            return
        except Exception:  # noqa: BLE001
            pass
        try:
            if os.name == "nt":
                subprocess.Popen(["explorer", str(exports_root)])  # noqa: S603
            else:
                subprocess.Popen(["xdg-open", str(exports_root)])  # noqa: S603
        except Exception:  # noqa: BLE001
            return

    def _profile_summary(self, profile_root: Path) -> str:
        files_manifest = profile_root / "files_manifest.csv"
        if not files_manifest.is_file():
            return f"Destination: {profile_root}\nNo manifest yet."
        rows = _read_csv_rows(files_manifest)
        counts: dict[str, int] = {}
        path_counts: dict[str, int] = {}
        for row in rows:
            ws = (row.get("workspace") or "").strip() or "(unknown)"
            counts[ws] = counts.get(ws, 0) + 1
            export_path = (row.get("export_path") or row.get("normalized_export_path") or "").strip()
            if export_path:
                path_counts[export_path] = path_counts.get(export_path, 0) + 1
        collision_paths = sum(1 for n in path_counts.values() if n > 1)
        collision_sources = sum(n for n in path_counts.values() if n > 1)
        collision_extra_sources = max(0, collision_sources - collision_paths)
        lines = [
            f"Destination: {profile_root}",
            f"Exported files: {len(rows)}",
            f"Export path collisions: {collision_extra_sources} extra source(s) reusing {collision_paths} path(s)",
            "By workspace:",
        ]
        if counts:
            for ws, count in sorted(counts.items(), key=lambda kv: kv[0]):
                lines.append(f"- {ws}: {count}")
        else:
            lines.append("- (none)")
        return "\n".join(lines)

    def _latest_manifest_line(self, root: Path) -> str:
        candidates = [
            root / "anythingllm" / "files_manifest.csv",
            root / "anythingllm" / "chunks_manifest.json",
            root / "open_webui" / "files_manifest.csv",
            root / "open_webui" / "chunks_manifest.json",
        ]
        items: list[tuple[str, float]] = []
        for p in candidates:
            if p.is_file():
                items.append((str(p), p.stat().st_mtime))
        if not items:
            return "Latest manifests: none found"
        items.sort(key=lambda x: x[1], reverse=True)
        top = items[:4]
        parts = [
            f"{Path(path).name} ({datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')})"
            for path, ts in top
        ]
        return "Latest manifests: " + " | ".join(parts)

    def _fill_preview_table(self, root: Path) -> None:
        rows: list[tuple[str, str, str, str]] = []
        for profile in ("anythingllm", "open_webui"):
            manifest = root / profile / "files_manifest.csv"
            for row in _read_csv_rows(manifest):
                rows.append(
                    (
                        profile,
                        row.get("workspace", ""),
                        row.get("source_file", ""),
                        row.get("export_path") or row.get("normalized_export_path", ""),
                    )
                )
        rows.sort(key=lambda r: (r[0], r[1], r[2]))
        rows = rows[-20:]
        self._tab.preview_table.setRowCount(len(rows))
        for i, (profile, workspace, source_file, export_path) in enumerate(rows):
            self._tab.preview_table.setItem(i, 0, QTableWidgetItem(profile))
            self._tab.preview_table.setItem(i, 1, QTableWidgetItem(workspace))
            self._tab.preview_table.setItem(i, 2, QTableWidgetItem(source_file))
            self._tab.preview_table.setItem(i, 3, QTableWidgetItem(export_path))


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    out: list[dict[str, str]] = []
    with path.open("r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            if not row:
                continue
            out.append({k: v for k, v in row.items() if isinstance(k, str) and isinstance(v, str)})
    return out


class SettingsController:
    """Settings tab load/save for project-local classification config."""

    __slots__ = ("_tab", "_context", "_error", "_info", "__weakref__")

    def __init__(
        self,
        *,
        tab: SettingsTabWidget,
        context: Callable[[], ProjectContext | None],
        error: Callable[[str], None],
        info: Callable[[str], None],
    ) -> None:
        self._tab = tab
        self._context = context
        self._error = error
        self._info = info
        self._tab.reset_rules_btn.clicked.connect(self.reset_to_seed_rules)
        self._tab.ai_provider_combo.currentTextChanged.connect(self._sync_provider_ui)
        self._sync_provider_ui(self._provider_text())

    def refresh(self) -> None:
        ctx = self._context()
        if ctx is None:
            self._tab.info_label.setText("Project settings will appear here after a project is loaded.")
            return
        cfg = load_classification_config(ctx.output_folder / ".kiw" / DEFAULT_CONFIG_FILENAME)
        self._tab.info_label.setText(
            "\n".join(
                [
                    f"Project: {ctx.name}",
                    f"Config: {ctx.output_folder / '.kiw' / DEFAULT_CONFIG_FILENAME}",
                ]
            )
        )
        self._tab.enable_ollama_check.setChecked(cfg.enable_ollama)
        self._tab.ollama_model_edit.setCurrentText(cfg.ollama_model)
        self._tab.ai_provider_combo.setCurrentText(cfg.ai_provider)
        self._tab.api_key_edit.setText(cfg.api_key)
        self._tab.cloud_model_combo.setCurrentText(cfg.cloud_model)
        self._tab.ai_mode_combo.setCurrentText(cfg.ai_mode)
        self._tab.auto_assign_workspace_check.setChecked(cfg.auto_assign_workspace)
        self._tab.duplicate_filename_policy_combo.setCurrentText(cfg.duplicate_filename_policy)
        self._tab.chunk_target_spin.setValue(cfg.chunk_target_size)
        self._tab.minimum_chunk_spin.setValue(cfg.minimum_chunk_size)
        self._tab.low_confidence_spin.setValue(cfg.review_confidence_threshold)
        self._tab.relevance_min_score_spin.setValue(cfg.relevance_min_score)
        self._tab.small_file_char_threshold_spin.setValue(cfg.small_file_char_threshold)
        self._tab.preflight_wiki_share_cap_spin.setValue(cfg.preflight_wiki_share_cap)
        self._sync_provider_ui(preferred_model=cfg.cloud_model)
        self._sync_ollama_status()

    def save(self) -> None:
        ctx = self._context()
        if ctx is None:
            self._error("Create or load a project first.")
            return
        path = ctx.output_folder / ".kiw" / DEFAULT_CONFIG_FILENAME
        base = load_classification_config(path)
        cfg = ClassificationConfig(
            workspaces=base.workspaces,
            force_rules=base.force_rules,
            negative_rules=base.negative_rules,
            company_map=base.company_map,
            project_map=base.project_map,
            doc_type_patterns=base.doc_type_patterns,
            code_ext=base.code_ext,
            rule_confidence=base.rule_confidence,
            risky_keywords=base.risky_keywords,
            broad_keywords=base.broad_keywords,
            broad_match_force_review=base.broad_match_force_review,
            enable_ollama=self._tab.enable_ollama_check.isChecked(),
            ollama_model=self._ollama_model_text() or base.ollama_model,
            ai_provider=self._provider_text(),
            api_key=self._tab.api_key_edit.text().strip(),
            cloud_model=self._tab.cloud_model_combo.currentText().strip(),
            ai_mode=self._tab.ai_mode_combo.currentText(),
            auto_assign_workspace=self._tab.auto_assign_workspace_check.isChecked(),
            duplicate_filename_policy=self._tab.duplicate_filename_policy_combo.currentText(),
            chunk_target_size=self._tab.chunk_target_spin.value(),
            minimum_chunk_size=self._tab.minimum_chunk_spin.value(),
            review_confidence_threshold=float(self._tab.low_confidence_spin.value()),
            relevance_min_score=self._tab.relevance_min_score_spin.value(),
            small_file_char_threshold=self._tab.small_file_char_threshold_spin.value(),
            preflight_wiki_share_cap=float(self._tab.preflight_wiki_share_cap_spin.value()),
        )
        try:
            save_classification_config(path, cfg)
            self._sync_ollama_status()
            self._info("Settings saved.")
        except Exception as exc:  # noqa: BLE001
            self._error(str(exc))

    def update_status(self) -> None:
        self._sync_ollama_status()

    def reset_to_seed_rules(self) -> None:
        ctx = self._context()
        if ctx is None:
            self._error("Create or load a project first.")
            return
        answer = QMessageBox.question(
            self._tab,
            "Reset Classification Rules",
            (
                "This will overwrite your current classification_rules.json "
                "with the bundled seed. Continue?"
            ),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        path = ctx.output_folder / ".kiw" / DEFAULT_CONFIG_FILENAME
        try:
            used_seed = write_classification_config_from_seed(path)
            load_classification_config(path)
            self.refresh()
            if not used_seed:
                self._info(
                    "Bundled seed file not found or invalid; used built-in defaults instead. "
                    "Classification rules reloaded from seed."
                )
                return
            self._info("Classification rules reloaded from seed.")
        except Exception as exc:  # noqa: BLE001
            self._error(str(exc))

    def test_ollama_connection(self) -> None:
        model = self._ollama_model_text()
        if not model:
            self._error("Set an Ollama model name first.")
            return
        checker = OllamaAIClassifier(model=model, timeout_s=5.0)
        ok, message = checker.test_connection()
        if ok:
            self._tab.ollama_status_label.setText(f"Ollama status: ✓ connected ({model})")
            self._tab.ollama_status_label.setStyleSheet("color: #2e7d32;")
            return
        self._error(message)
        self._tab.ollama_status_label.setText(f"Ollama status: connection failed ({model})")
        self._tab.ollama_status_label.setStyleSheet("color: #b00020;")

    def refresh_ollama_models(self) -> None:
        model = self._ollama_model_text() or "llama3.2:3b"
        checker = OllamaAIClassifier(model=model, timeout_s=5.0)
        ok, models, message = checker.list_models()
        if not ok:
            self._error(message)
            return
        current = self._ollama_model_text()
        self._tab.ollama_model_edit.blockSignals(True)
        self._tab.ollama_model_edit.clear()
        if models:
            self._tab.ollama_model_edit.addItems(list(models))
        if current:
            self._tab.ollama_model_edit.setCurrentText(current)
        elif models:
            self._tab.ollama_model_edit.setCurrentIndex(0)
        else:
            self._tab.ollama_model_edit.setCurrentText("llama3.2:3b")
        self._tab.ollama_model_edit.blockSignals(False)
        self._sync_ollama_status()
        self._info(message)

    def _sync_ollama_status(self) -> None:
        self._tab.ollama_status_label.setStyleSheet("")
        if self._tab.enable_ollama_check.isChecked():
            model = self._ollama_model_text() or "unset-model"
            self._tab.ollama_status_label.setText(f"Ollama status: enabled ({model})")
        else:
            self._tab.ollama_status_label.setText("Ollama status: disabled")

    def _sync_provider_ui(self, provider: str | None = None, *, preferred_model: str | None = None) -> None:
        selected = (provider or self._provider_text()).strip().lower() or "ollama"
        is_ollama = selected == "ollama"
        is_claude = selected == "claude"
        is_openai = selected == "openai"

        self._set_field_visible(self._tab.enable_ollama_label, self._tab.enable_ollama_check, is_ollama)
        self._set_field_visible(self._tab.ollama_model_label, self._tab.ollama_model_edit, is_ollama)
        self._set_field_visible(self._tab.ollama_status_label_label, self._tab.ollama_status_label, is_ollama)
        self._tab.refresh_ollama_models_btn.setVisible(is_ollama)
        self._tab.test_ollama_btn.setVisible(is_ollama)

        is_cloud = is_claude or is_openai
        self._set_field_visible(self._tab.api_key_label, self._tab.api_key_edit, is_cloud)
        self._set_field_visible(self._tab.cloud_model_label, self._tab.cloud_model_combo, is_cloud)
        self._tab.api_key_help_label.setVisible(is_cloud)

        if is_claude:
            models = ["claude-sonnet-4-5", "claude-haiku-4-5-20251001", "claude-opus-4-5"]
            help_text = "Get your API key at console.anthropic.com"
        elif is_openai:
            models = ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo"]
            help_text = "Get your API key at platform.openai.com"
        else:
            models = []
            help_text = ""

        if models:
            current = (preferred_model or self._tab.cloud_model_combo.currentText()).strip()
            self._tab.cloud_model_combo.blockSignals(True)
            self._tab.cloud_model_combo.clear()
            self._tab.cloud_model_combo.addItems(models)
            self._tab.cloud_model_combo.setCurrentText(current or models[0])
            self._tab.cloud_model_combo.blockSignals(False)
        self._tab.api_key_help_label.setText(help_text)

    @staticmethod
    def _set_field_visible(label: QWidget, widget: QWidget, visible: bool) -> None:
        label.setVisible(visible)
        widget.setVisible(visible)

    def _ollama_model_text(self) -> str:
        return self._tab.ollama_model_edit.currentText().strip()

    def _provider_text(self) -> str:
        provider = self._tab.ai_provider_combo.currentText().strip().lower()
        if provider in {"claude", "openai", "ollama"}:
            return provider
        return "ollama"

    # ------------------------------------------------------------------ #
    # My Categories helpers                                                #
    # ------------------------------------------------------------------ #

    def _config_path(self) -> Path | None:
        ctx = self._context()
        if ctx is None:
            return None
        return ctx.output_folder / ".kiw" / DEFAULT_CONFIG_FILENAME

    def _load_config(self) -> dict:
        path = self._config_path()
        if path is None or not path.is_file():
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            return {}

    def _save_config(self, cfg: dict) -> None:
        path = self._config_path()
        if path is None:
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(cfg, indent=2), encoding="utf-8")

    def load_categories(self) -> None:
        """Populate all four category sub-tabs from current config."""
        cfg = self._load_config()

        ws_table = self._tab.workspace_list
        ws_table.blockSignals(True)
        ws_table.setRowCount(0)
        for label, name in cfg.get("WORKSPACES", {}).items():
            row = ws_table.rowCount()
            ws_table.insertRow(row)
            ws_table.setItem(row, 0, QTableWidgetItem(label))
            ws_table.setItem(row, 1, QTableWidgetItem(name))
        ws_table.blockSignals(False)

        self._refresh_workspace_combos(cfg)

        co_table = self._tab.company_list
        co_table.blockSignals(True)
        co_table.setRowCount(0)
        for keyword, workspace in cfg.get("COMPANY_MAP", {}).items():
            row = co_table.rowCount()
            co_table.insertRow(row)
            co_table.setItem(row, 0, QTableWidgetItem(keyword))
            co_table.setItem(row, 1, QTableWidgetItem(workspace))
        co_table.blockSignals(False)

        pr_table = self._tab.project_list
        pr_table.blockSignals(True)
        pr_table.setRowCount(0)
        for keyword, workspace in cfg.get("PROJECT_MAP", {}).items():
            row = pr_table.rowCount()
            pr_table.insertRow(row)
            pr_table.setItem(row, 0, QTableWidgetItem(keyword))
            pr_table.setItem(row, 1, QTableWidgetItem(workspace))
        pr_table.blockSignals(False)

        self._tab.rules_table.setRowCount(0)
        for rule in cfg.get("FORCE_RULES", []):
            row = self._tab.rules_table.rowCount()
            self._tab.rules_table.insertRow(row)
            self._tab.rules_table.setItem(row, 0, QTableWidgetItem(rule.get("contains", "")))
            self._tab.rules_table.setItem(row, 1, QTableWidgetItem(rule.get("workspace", "")))
            self._tab.rules_table.setItem(row, 2, QTableWidgetItem(rule.get("subfolder", "None")))
            self._tab.rules_table.setItem(row, 3, QTableWidgetItem(rule.get("reason", "")))

    def _refresh_workspace_combos(self, cfg: dict) -> None:
        """Keep all workspace dropdowns in sync with current WORKSPACES."""
        workspaces = list(cfg.get("WORKSPACES", {}).values())
        for combo in [
            self._tab.company_ws_combo,
            self._tab.project_ws_combo,
            self._tab.rule_ws_combo,
        ]:
            current = combo.currentText()
            combo.clear()
            combo.addItems(workspaces)
            if current in workspaces:
                combo.setCurrentText(current)

    def save_workspace_edits(self) -> None:
        """Persist inline cell edits in the Workspaces table."""
        cfg = self._load_config()
        workspaces: dict[str, str] = {}
        table = self._tab.workspace_list
        for row in range(table.rowCount()):
            label_item = table.item(row, 0)
            name_item = table.item(row, 1)
            if label_item and name_item:
                label = label_item.text().strip()
                name = name_item.text().strip()
                if label and name:
                    workspaces[label] = name
        cfg["WORKSPACES"] = workspaces
        self._save_config(cfg)
        self._refresh_workspace_combos(cfg)

    def save_company_edits(self) -> None:
        """Persist inline cell edits in the Companies table."""
        cfg = self._load_config()
        company_map: dict[str, str] = {}
        table = self._tab.company_list
        for row in range(table.rowCount()):
            kw_item = table.item(row, 0)
            ws_item = table.item(row, 1)
            if kw_item and ws_item:
                kw = kw_item.text().strip()
                ws = ws_item.text().strip()
                if kw and ws:
                    company_map[kw] = ws
        cfg["COMPANY_MAP"] = company_map
        self._save_config(cfg)

    def save_project_edits(self) -> None:
        """Persist inline cell edits in the Projects table."""
        cfg = self._load_config()
        project_map: dict[str, str] = {}
        table = self._tab.project_list
        for row in range(table.rowCount()):
            kw_item = table.item(row, 0)
            ws_item = table.item(row, 1)
            if kw_item and ws_item:
                kw = kw_item.text().strip()
                ws = ws_item.text().strip()
                if kw and ws:
                    project_map[kw] = ws
        cfg["PROJECT_MAP"] = project_map
        self._save_config(cfg)

    def add_workspace(self) -> None:
        label = self._tab.ws_label_edit.text().strip().lower().replace(" ", "_")
        name = self._tab.ws_name_edit.text().strip().lower().replace(" ", "_")
        if not label or not name:
            self._error("Please enter both a label and folder name.")
            return
        cfg = self._load_config()
        cfg.setdefault("WORKSPACES", {})[label] = name
        self._save_config(cfg)
        self._tab.ws_label_edit.clear()
        self._tab.ws_name_edit.clear()
        self.load_categories()

    def remove_workspace(self) -> None:
        row = self._tab.workspace_list.currentRow()
        if row < 0:
            return
        label_item = self._tab.workspace_list.item(row, 0)
        if not label_item:
            return
        label = label_item.text().strip()
        cfg = self._load_config()
        cfg.get("WORKSPACES", {}).pop(label, None)
        self._save_config(cfg)
        self.load_categories()

    def add_company(self) -> None:
        keyword = self._tab.company_keyword_edit.text().strip().lower()
        workspace = self._tab.company_ws_combo.currentText()
        if not keyword:
            self._error("Please enter a company name or keyword.")
            return
        cfg = self._load_config()
        cfg.setdefault("COMPANY_MAP", {})[keyword] = workspace
        self._save_config(cfg)
        self._tab.company_keyword_edit.clear()
        self.load_categories()

    def remove_company(self) -> None:
        row = self._tab.company_list.currentRow()
        if row < 0:
            return
        kw_item = self._tab.company_list.item(row, 0)
        if not kw_item:
            return
        keyword = kw_item.text().strip()
        cfg = self._load_config()
        cfg.get("COMPANY_MAP", {}).pop(keyword, None)
        self._save_config(cfg)
        self.load_categories()

    def add_project(self) -> None:
        keyword = self._tab.project_keyword_edit.text().strip().lower()
        workspace = self._tab.project_ws_combo.currentText()
        if not keyword:
            self._error("Please enter a project keyword.")
            return
        cfg = self._load_config()
        cfg.setdefault("PROJECT_MAP", {})[keyword] = workspace
        self._save_config(cfg)
        self._tab.project_keyword_edit.clear()
        self.load_categories()

    def remove_project(self) -> None:
        row = self._tab.project_list.currentRow()
        if row < 0:
            return
        kw_item = self._tab.project_list.item(row, 0)
        if not kw_item:
            return
        keyword = kw_item.text().strip()
        cfg = self._load_config()
        cfg.get("PROJECT_MAP", {}).pop(keyword, None)
        self._save_config(cfg)
        self.load_categories()

    def add_rule(self) -> None:
        keyword = self._tab.rule_keyword_edit.text().strip().lower()
        workspace = self._tab.rule_ws_combo.currentText()
        subfolder = self._tab.rule_subfolder_edit.text().strip() or "None"
        if not keyword:
            self._error("Please enter a keyword or phrase.")
            return
        cfg = self._load_config()
        cfg.setdefault("FORCE_RULES", []).append({
            "contains": keyword,
            "category": workspace,
            "workspace": workspace,
            "subfolder": subfolder,
            "reason": f"User-defined rule: {keyword}",
        })
        self._save_config(cfg)
        self._tab.rule_keyword_edit.clear()
        self._tab.rule_subfolder_edit.clear()
        self.load_categories()

    def remove_rule(self) -> None:
        row = self._tab.rules_table.currentRow()
        if row < 0:
            return
        keyword = self._tab.rules_table.item(row, 0).text()
        cfg = self._load_config()
        cfg["FORCE_RULES"] = [
            r for r in cfg.get("FORCE_RULES", [])
            if r.get("contains") != keyword
        ]
        self._save_config(cfg)
        self.load_categories()
