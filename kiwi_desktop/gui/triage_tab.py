"""Triage tab: unassigned files with async DB I/O off the UI thread."""

from __future__ import annotations

import csv
from collections.abc import Callable, Sequence
from pathlib import Path

from PySide6.QtCore import QObject, QThread, Signal, Qt
from PySide6.QtGui import QAction, QColor, QFont, QPalette, QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from db.repositories import FileRepository
from db.session import Database
from models.triage_derivation import UnassignedTriageRow, is_ai_session_row, summary_counts
from services.review_service import WORKSPACE_OPTIONS, ReviewService

_REASON_FILTER_LABELS = (
    "All",
    "Rule gap",
    "Needs review",
    "AI session",
    "PDF chunk",
    "Noise",
)
_PRIORITY_FILTER_LABELS = ("All", "High", "Medium", "Low")

_ROLE_FILE_ID = Qt.ItemDataRole.UserRole
_ROLE_PATH = Qt.ItemDataRole.UserRole + 1
_ROLE_SUBFOLDER = Qt.ItemDataRole.UserRole + 2


class TriageLoadWorker(QThread):
    """Loads unassigned triage rows in a background thread (SQLite must not block the UI)."""

    # Do not name signals ``finished`` / ``error`` — they shadow QThread / QObject APIs and break delivery.
    load_finished = Signal(list)
    load_failed = Signal(str)

    def __init__(self, db_path: Path, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._db_path = db_path

    def run(self) -> None:
        try:
            db = Database(self._db_path)
            db.connect()
            repo = FileRepository(db)
            rows = repo.list_unassigned()
            self.load_finished.emit(list(rows))
        except Exception as exc:  # noqa: BLE001
            self.load_failed.emit(str(exc))


class TriageMutateWorker(QThread):
    """Assign / skip / requeue mutations off the UI thread."""

    finished_ok = Signal(str)
    error = Signal(str)

    def __init__(
        self,
        db_path: Path,
        op: str,
        file_ids: tuple[int, ...],
        *,
        workspace: str | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._db_path = db_path
        self._op = op
        self._file_ids = file_ids
        self._workspace = workspace

    def run(self) -> None:
        try:
            if self._op == "assign":
                if not self._workspace:
                    raise ValueError("Workspace is required for assign.")
                rs = ReviewService()
                for fid in self._file_ids:
                    rs.override_workspace(db_path=self._db_path, file_id=fid, workspace=self._workspace)
                db = Database(self._db_path)
                db.connect()
                repo = FileRepository(db)
                repo.requeue_for_classification(list(self._file_ids))
                self.finished_ok.emit(
                    f"Assigned workspace '{self._workspace}' to {len(self._file_ids)} file(s). "
                    "AnythingLLM and Open WebUI export queues were reset so each profile’s pipeline "
                    "can pick up the file and write it to the folders configured for that workspace."
                )
            elif self._op == "skip":
                db = Database(self._db_path)
                db.connect()
                repo = FileRepository(db)
                for fid in self._file_ids:
                    repo.set_review_required(fid, False)
                    repo.set_workspace(fid, "skip")
                self.finished_ok.emit(f"Marked {len(self._file_ids)} file(s) as skip.")
            elif self._op == "requeue":
                db = Database(self._db_path)
                db.connect()
                repo = FileRepository(db)
                n = repo.requeue_for_classification(list(self._file_ids))
                self.finished_ok.emit(f"Requeued {n} file(s) for classification.")
            else:
                raise ValueError(f"Unknown triage mutation: {self._op!r}")
        except Exception as exc:  # noqa: BLE001
            self.error.emit(str(exc))


class TriageTabWidget(QWidget):
    """Unassigned / review-adjacent files with metrics, filters, and actions."""

    __slots__ = (
        "_metric_total_val",
        "_metric_rule_gap_val",
        "_metric_high_val",
        "_metric_ai_val",
        "_metric_safe_val",
        "reason_combo",
        "priority_combo",
        "workspace_combo",
        "search_edit",
        "refresh_btn",
        "table",
        "_table_model",
        "bulk_bar",
        "bulk_workspace_combo",
        "bulk_apply_btn",
        "bulk_skip_btn",
        "bulk_requeue_btn",
        "bulk_export_btn",
        "_status_label",
        "loading_label",
        "_loading",
        "_worker",
        "_mutate_worker",
        "_reload_after_mutation",
        "_all_rows",
        "_sort_column",
        "_sort_ascending",
        "_populating",
        "_get_db_path",
        "_on_assign_workspace_ids",
        "_on_mark_skip_ids",
        "_on_requeue_ids",
        "_on_export_csv_ids",
        "_select_all_visible_btn",
        "_clear_selection_btn",
        "_table_count_label",
    )

    def __init__(
        self,
        *,
        get_db_path: Callable[[], Path | None],
        on_assign_workspace_ids: Callable[[tuple[int, ...], str], None],
        on_mark_skip_ids: Callable[[tuple[int, ...]], None],
        on_requeue_ids: Callable[[tuple[int, ...]], None],
        on_export_csv_ids: Callable[[tuple[int, ...]], None],
    ) -> None:
        super().__init__()
        self._get_db_path = get_db_path
        # Kept for API compatibility; assign/skip/requeue use TriageMutateWorker instead.
        self._on_assign_workspace_ids = on_assign_workspace_ids
        self._on_mark_skip_ids = on_mark_skip_ids
        self._on_requeue_ids = on_requeue_ids
        self._on_export_csv_ids = on_export_csv_ids
        self._loading = False
        self._worker: TriageLoadWorker | None = None
        self._mutate_worker: TriageMutateWorker | None = None
        self._reload_after_mutation = False
        self._all_rows: list[UnassignedTriageRow] = []
        self._sort_column = 1
        self._sort_ascending = True
        self._populating = False

        layout = QVBoxLayout(self)

        cards_row = QHBoxLayout()
        cards_row.setSpacing(8)
        f1, self._metric_total_val = self._make_metric_card("Total unassigned", color="#e8e8e8")
        f2, self._metric_rule_gap_val = self._make_metric_card("Rule gaps", color="#e6a817")
        f3, self._metric_high_val = self._make_metric_card("High priority", color="#cc4444")
        f4, self._metric_ai_val = self._make_metric_card("AI sessions", color="#4a9eff")
        f5, self._metric_safe_val = self._make_metric_card("Safe to skip", color="#3d9970")
        for w in (f1, f2, f3, f4, f5):
            cards_row.addWidget(w, 1)
        layout.addLayout(cards_row)

        self._status_label = QLabel("")
        self.loading_label = self._status_label
        self._status_label.setObjectName("triageLoadingLabel")
        self._status_label.setWordWrap(True)
        self._status_label.hide()
        layout.addWidget(self._status_label)

        filter_frame = QFrame()
        filter_frame.setStyleSheet(
            "QFrame { background: #2d2d2d; border-radius: 6px; border: none; }"
        )
        filter_frame.setContentsMargins(0, 6, 0, 6)
        filter_row = QHBoxLayout(filter_frame)
        filter_row.setContentsMargins(8, 8, 8, 8)
        filter_row.setSpacing(6)
        _filter_lbl = QLabel("Filter:")
        _filter_lbl.setStyleSheet("color: #a0a0a0; border: none;")
        filter_row.addWidget(_filter_lbl)
        filter_row.addWidget(QLabel("Reason"))
        self.reason_combo = QComboBox()
        self.reason_combo.addItems(list(_REASON_FILTER_LABELS))
        filter_row.addWidget(self.reason_combo)
        filter_row.addWidget(QLabel("Priority"))
        self.priority_combo = QComboBox()
        self.priority_combo.addItems(list(_PRIORITY_FILTER_LABELS))
        filter_row.addWidget(self.priority_combo)
        filter_row.addWidget(QLabel("Suggested workspace"))
        self.workspace_combo = QComboBox()
        self.workspace_combo.setMinimumWidth(180)
        filter_row.addWidget(self.workspace_combo)
        filter_row.addWidget(QLabel("Search"))
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Filename contains…")
        filter_row.addWidget(self.search_edit, 1)
        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.setProperty("class", "btn-primary")
        filter_row.addWidget(self.refresh_btn)
        layout.addWidget(filter_frame)

        table_actions = QHBoxLayout()
        table_actions.setContentsMargins(0, 2, 0, 0)
        self._select_all_visible_btn = QPushButton("Select all visible")
        self._clear_selection_btn = QPushButton("Clear selection")
        self._select_all_visible_btn.setToolTip(
            "Check every row in the current filtered table (respects Reason, Priority, workspace, and search)."
        )
        self._clear_selection_btn.setToolTip("Uncheck all rows in the table.")
        table_actions.addWidget(self._select_all_visible_btn)
        table_actions.addWidget(self._clear_selection_btn)
        table_actions.addStretch(1)
        layout.addLayout(table_actions)

        self._table_count_label = QLabel("Showing 0 files")
        self._table_count_label.setStyleSheet("color: #a0a0a0; font-size: 11px; font-style: italic;")
        layout.addWidget(self._table_count_label)

        self._table_model = QStandardItemModel(0, 7, self)
        self._table_model.setHorizontalHeaderLabels(
            ["", "Filename", "Matched By", "Suggested Workspace", "Priority", "Signals", "Size"]
        )
        self.table = QTableView()
        self.table.setModel(self._table_model)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table.setSortingEnabled(False)
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet("QTableView { gridline-color: #3a3a3a; }")
        self.table.verticalHeader().setDefaultSectionSize(28)
        hdr = self.table.horizontalHeader()
        _hdr_font = QFont()
        _hdr_font.setBold(True)
        _hdr_font.setPixelSize(11)
        hdr.setFont(_hdr_font)
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(0, 36)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        hdr.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        hdr.setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
        hdr.sectionClicked.connect(self._sort_rows)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)
        self._table_model.itemChanged.connect(self._on_model_item_changed)
        layout.addWidget(self.table)

        self.bulk_bar = QWidget()
        bulk_layout = QHBoxLayout(self.bulk_bar)
        bulk_layout.setContentsMargins(0, 4, 0, 0)
        bulk_layout.addWidget(QLabel("Bulk:"))
        self.bulk_workspace_combo = QComboBox()
        self.bulk_workspace_combo.addItems(list(WORKSPACE_OPTIONS))
        bulk_layout.addWidget(self.bulk_workspace_combo)
        self.bulk_apply_btn = QPushButton("Apply workspace")
        self.bulk_apply_btn.setProperty("class", "btn-primary")
        bulk_layout.addWidget(self.bulk_apply_btn)
        self.bulk_skip_btn = QPushButton("Mark skip")
        self.bulk_skip_btn.setProperty("class", "btn-danger")
        bulk_layout.addWidget(self.bulk_skip_btn)
        self.bulk_requeue_btn = QPushButton("Requeue selected")
        bulk_layout.addWidget(self.bulk_requeue_btn)
        self.bulk_export_btn = QPushButton("Export selection to CSV")
        bulk_layout.addWidget(self.bulk_export_btn)
        bulk_layout.addStretch(1)
        self.bulk_bar.hide()
        layout.addWidget(self.bulk_bar)

        self.reason_combo.currentIndexChanged.connect(lambda _i: self._apply_filters())
        self.priority_combo.currentIndexChanged.connect(lambda _i: self._apply_filters())
        self.workspace_combo.currentIndexChanged.connect(lambda _i: self._apply_filters())
        self.search_edit.textChanged.connect(lambda _t: self._apply_filters())
        self.refresh_btn.clicked.connect(self._on_refresh_clicked)
        self.bulk_apply_btn.clicked.connect(self._bulk_apply_workspace)
        self.bulk_skip_btn.clicked.connect(self._bulk_skip)
        self.bulk_requeue_btn.clicked.connect(self._bulk_requeue)
        self.bulk_export_btn.clicked.connect(self._bulk_export)
        self._select_all_visible_btn.clicked.connect(self._select_all_visible)
        self._clear_selection_btn.clicked.connect(self._clear_row_selection)

    def request_load(self, db_path: Path | None) -> None:
        """Load triage data asynchronously. Call from the UI thread only."""
        if self._mutate_worker is not None and self._mutate_worker.isRunning():
            return
        if self._loading:
            return
        self._clear_loading_label()
        if db_path is None:
            self._apply_empty_state()
            return
        self._loading = True
        self._set_loading_ui(True)
        self._worker = TriageLoadWorker(db_path, self)
        self._worker.load_finished.connect(self._on_worker_finished)
        self._worker.load_failed.connect(self._on_worker_error)
        self._worker.start()

    def _on_refresh_clicked(self) -> None:
        self.request_load(self._get_db_path())

    def _clear_loading_label(self) -> None:
        self._status_label.clear()
        self._status_label.hide()
        self._status_label.setVisible(False)

    def _set_loading_ui(self, loading: bool) -> None:
        if loading:
            self._status_label.setText("Loading…")
            self._status_label.setVisible(True)
            self._status_label.show()
        else:
            self._clear_loading_label()
        self.table.setEnabled(not loading)
        self.refresh_btn.setEnabled(not loading)
        self.reason_combo.setEnabled(not loading)
        self.priority_combo.setEnabled(not loading)
        self.workspace_combo.setEnabled(not loading)
        self.search_edit.setEnabled(not loading)
        self.bulk_bar.setEnabled(not loading)
        self._select_all_visible_btn.setEnabled(not loading)
        self._clear_selection_btn.setEnabled(not loading)

    def _apply_empty_state(self) -> None:
        self.set_data([])

    def _on_worker_finished(self, rows: list) -> None:
        results = list(rows)
        self._all_rows = results
        print(f"[Triage] Loaded {len(self._all_rows)} rows")
        self._loading = False
        self._set_loading_ui(False)
        self._update_stat_cards()
        self._populate_suggested_workspace_filter()
        self._apply_filters()
        wk = self._worker
        self._worker = None
        if wk is not None:
            wk.deleteLater()
        if self._reload_after_mutation:
            self._reload_after_mutation = False
            self.request_load(self._get_db_path())

    def _on_worker_error(self, message: str) -> None:
        self._loading = False
        if self._worker is not None:
            self._worker.deleteLater()
            self._worker = None
        self._all_rows = []
        self._set_loading_ui(False)
        self.loading_label.hide()
        self.loading_label.clear()
        self._update_stat_cards()
        self._apply_filters()
        self._status_label.setText(f"Error: {message}")
        self._status_label.setVisible(True)
        self._status_label.show()

    def _update_stat_cards(self) -> None:
        total, rg, hi, ai, safe = summary_counts(tuple(self._all_rows))
        self._metric_total_val.setText(str(total))
        self._metric_rule_gap_val.setText(str(rg))
        self._metric_high_val.setText(str(hi))
        self._metric_ai_val.setText(str(ai))
        self._metric_safe_val.setText(str(safe))

    @staticmethod
    def _make_metric_card(title: str, *, color: str = "#e8e8e8") -> tuple[QFrame, QLabel]:
        frame = QFrame()
        frame.setFrameShape(QFrame.Shape.NoFrame)
        frame.setStyleSheet(
            "QFrame { background: #2d2d2d; border: 1px solid #555555;"
            " border-radius: 8px; } "
        )
        frame.setMinimumWidth(160)
        v = QVBoxLayout(frame)
        v.setContentsMargins(12, 12, 12, 12)
        v.setSpacing(4)
        val = QLabel("0")
        f = QFont()
        f.setPixelSize(28)
        f.setBold(True)
        val.setFont(f)
        val.setStyleSheet(f"color: {color}; border: none;")
        lab = QLabel(title.upper())
        lab.setStyleSheet("color: #a0a0a0; font-size: 11px; border: none;")
        v.addWidget(val)
        v.addWidget(lab)
        return frame, val

    def rows_for_file_ids(self, ids: Sequence[int]) -> tuple[UnassignedTriageRow, ...]:
        wanted = set(ids)
        return tuple(r for r in self._all_rows if r.file_id in wanted)

    def set_data(self, rows: Sequence[UnassignedTriageRow]) -> None:
        """Set in-memory rows and refresh filters/table (no DB)."""
        self._all_rows = list(rows)
        self._update_stat_cards()
        self._populate_suggested_workspace_filter()
        self._apply_filters()

    def _populate_suggested_workspace_filter(self) -> None:
        keep = self.workspace_combo.currentText()
        vals = sorted(
            {r.suggested_workspace for r in self._all_rows if r.suggested_workspace.strip()}
        )
        vals = [v for v in vals if v.strip().lower() != "all"]
        for c in (self.reason_combo, self.priority_combo, self.workspace_combo):
            c.blockSignals(True)
        self.workspace_combo.clear()
        self.workspace_combo.addItem("All")
        self.workspace_combo.addItems(vals)
        if keep and self.workspace_combo.findText(keep) >= 0:
            self.workspace_combo.setCurrentIndex(self.workspace_combo.findText(keep))
        else:
            self.workspace_combo.setCurrentIndex(0)
        for c in (self.reason_combo, self.priority_combo, self.workspace_combo):
            c.blockSignals(False)

    def _passes_filters(self, r: UnassignedTriageRow) -> bool:
        reason_label = self.reason_combo.currentText().strip()
        if reason_label == "Rule gap" and r.reason != "rule_gap":
            return False
        if reason_label == "Needs review" and r.reason != "needs_review":
            return False
        if reason_label == "AI session" and not is_ai_session_row(r):
            return False
        if reason_label == "PDF chunk" and r.reason != "pdf_chunk":
            return False
        if reason_label == "Noise" and r.reason != "noise":
            return False

        pri = self.priority_combo.currentText().strip()
        if pri and pri != "All" and r.priority != pri:
            return False

        ws = self.workspace_combo.currentText().strip()
        if ws and ws != "All" and r.suggested_workspace != ws:
            return False

        q = self.search_edit.text().strip().lower()
        name_lc = (r.filename or "").lower()
        if q and q not in name_lc:
            return False
        return True

    def _filtered_rows(self) -> list[UnassignedTriageRow]:
        return [r for r in self._all_rows if self._passes_filters(r)]

    def _sort_key(self, r: UnassignedTriageRow, col: int) -> str | int | float:
        if col == 1:
            return (r.filename or "").lower()
        if col == 2:
            return (r.matched_by or "").lower()
        if col == 3:
            return r.suggested_workspace.lower()
        if col == 4:
            order = {"High": 0, "Medium": 1, "Low": 2}
            return order.get(r.priority, 3)
        if col == 5:
            return r.signals.lower()
        if col == 6:
            return r.size_bytes if r.size_bytes is not None else -1
        return (r.filename or "").lower()

    def _sort_rows(self, logical_index: int) -> None:
        if logical_index == 0:
            return
        if self._sort_column == logical_index:
            self._sort_ascending = not self._sort_ascending
        else:
            self._sort_column = logical_index
            self._sort_ascending = True
        self._apply_filters()

    def _apply_filters(self) -> None:
        """Filter/sort in memory from self._all_rows only; no DB access."""
        if not self._all_rows:
            self._populate_table([])
            return
        rows = self._filtered_rows()
        col = self._sort_column
        rev = not self._sort_ascending
        try:
            rows.sort(key=lambda r: self._sort_key(r, col), reverse=rev)
        except TypeError:
            rows.sort(key=lambda r: str(self._sort_key(r, col)), reverse=rev)
        self._populate_table(rows)

    @staticmethod
    def _standard_row_for_record(r: UnassignedTriageRow) -> list[QStandardItem]:
        sf = r.record.subfolder or ""
        c0 = QStandardItem()
        c0.setCheckable(True)
        c0.setCheckState(Qt.CheckState.Unchecked)
        c0.setData(r.file_id, _ROLE_FILE_ID)
        c0.setData(r.path, _ROLE_PATH)
        c0.setData(sf, _ROLE_SUBFOLDER)
        c0.setFlags(
            Qt.ItemFlag.ItemIsUserCheckable
            | Qt.ItemFlag.ItemIsEnabled
            | Qt.ItemFlag.ItemIsSelectable
        )
        c1 = QStandardItem(r.filename or "")
        c1.setData(r.file_id, _ROLE_FILE_ID)
        c1.setData(r.path, _ROLE_PATH)
        c1.setData(sf, _ROLE_SUBFOLDER)
        c2 = QStandardItem(r.matched_by or "")
        c2.setData(r.file_id, _ROLE_FILE_ID)
        c2.setData(r.path, _ROLE_PATH)
        c2.setData(sf, _ROLE_SUBFOLDER)
        c3 = QStandardItem(r.suggested_workspace)
        c3.setData(r.file_id, _ROLE_FILE_ID)
        c3.setData(r.path, _ROLE_PATH)
        c3.setData(sf, _ROLE_SUBFOLDER)
        c4 = QStandardItem(r.priority)
        if r.priority == "High":
            c4.setForeground(QColor("#cc4444"))
        elif r.priority == "Low":
            c4.setForeground(QColor("#a0a0a0"))
        c4.setData(r.file_id, _ROLE_FILE_ID)
        c4.setData(r.path, _ROLE_PATH)
        c4.setData(sf, _ROLE_SUBFOLDER)
        c5 = QStandardItem(r.signals)
        c5.setData(r.file_id, _ROLE_FILE_ID)
        c5.setData(r.path, _ROLE_PATH)
        c5.setData(sf, _ROLE_SUBFOLDER)
        sz = r.size_bytes
        c6 = QStandardItem(str(sz) if sz is not None else "")
        c6.setData(r.file_id, _ROLE_FILE_ID)
        c6.setData(r.path, _ROLE_PATH)
        c6.setData(sf, _ROLE_SUBFOLDER)
        return [c0, c1, c2, c3, c4, c5, c6]

    def _populate_table(self, filtered_rows: list[UnassignedTriageRow]) -> None:
        """Replace model contents; all data from memory (no DB)."""
        model = self.table.model()
        if not isinstance(model, QStandardItemModel):
            return

        def _cell(row: object, dict_key: str, *attr_names: str) -> str:
            if isinstance(row, dict):
                v = row.get(dict_key)
                return "" if v is None else str(v)
            for name in attr_names:
                if hasattr(row, name):
                    v = getattr(row, name)
                    return "" if v is None else str(v)
            return ""

        self._populating = True
        model.beginResetModel()
        model.removeRows(0, model.rowCount())
        for row in filtered_rows:
            if isinstance(row, UnassignedTriageRow):
                model.appendRow(self._standard_row_for_record(row))
            else:
                items = [
                    QStandardItem(""),
                    QStandardItem(_cell(row, "filename", "filename")),
                    QStandardItem(_cell(row, "matched_by", "matched_by")),
                    QStandardItem(
                        _cell(row, "suggested_workspace", "suggested_workspace", "workspace")
                    ),
                    QStandardItem(_cell(row, "priority", "priority")),
                    QStandardItem(_cell(row, "signals", "signals", "subfolder")),
                    QStandardItem(_cell(row, "size_bytes", "size_bytes")),
                ]
                model.appendRow(items)
        model.endResetModel()
        self.table.viewport().update()
        self._populating = False
        count = model.rowCount()
        self._table_count_label.setText(
            f"Showing {count:,} {'file' if count == 1 else 'files'}"
            " — select rows to take bulk action"
        )
        self._sync_bulk_bar()
        self._update_select_all_enabled()

    def _update_select_all_enabled(self) -> None:
        n = self._table_model.rowCount()
        self._select_all_visible_btn.setEnabled(n > 0 and not self._loading)
        self._clear_selection_btn.setEnabled(n > 0 and not self._loading)

    def _select_all_visible(self) -> None:
        if self._table_model.rowCount() == 0:
            return
        self._populating = True
        try:
            for row in range(self._table_model.rowCount()):
                it = self._table_model.item(row, 0)
                if it is None or not (it.flags() & Qt.ItemFlag.ItemIsUserCheckable):
                    continue
                it.setCheckState(Qt.CheckState.Checked)
        finally:
            self._populating = False
        self._sync_bulk_bar()

    def _clear_row_selection(self) -> None:
        if self._table_model.rowCount() == 0:
            return
        self._populating = True
        try:
            for row in range(self._table_model.rowCount()):
                it = self._table_model.item(row, 0)
                if it is None or not (it.flags() & Qt.ItemFlag.ItemIsUserCheckable):
                    continue
                it.setCheckState(Qt.CheckState.Unchecked)
        finally:
            self._populating = False
        self._sync_bulk_bar()

    def _on_model_item_changed(self, item: QStandardItem) -> None:
        if self._populating:
            return
        if item.column() != 0:
            return
        self._sync_bulk_bar()

    def _checked_ids(self) -> tuple[int, ...]:
        ids: list[int] = []
        for row in range(self._table_model.rowCount()):
            it = self._table_model.item(row, 0)
            if it is None or it.checkState() != Qt.CheckState.Checked:
                continue
            fid = it.data(_ROLE_FILE_ID)
            if isinstance(fid, int):
                ids.append(fid)
        return tuple(ids)

    def _sync_bulk_bar(self) -> None:
        n = len(self._checked_ids())
        self.bulk_bar.setVisible(n >= 1)

    def _start_mutation(self, op: str, ids: tuple[int, ...], *, workspace: str | None = None) -> None:
        db_path = self._get_db_path()
        if db_path is None or not ids:
            return
        if self._mutate_worker is not None and self._mutate_worker.isRunning():
            return
        self._mutate_worker = TriageMutateWorker(db_path, op, ids, workspace=workspace, parent=self)
        self._mutate_worker.finished_ok.connect(self._on_mutation_finished)
        self._mutate_worker.error.connect(self._on_mutation_error)
        self._mutate_worker.finished_ok.connect(self._mutate_worker.deleteLater)
        self._mutate_worker.error.connect(self._mutate_worker.deleteLater)
        self.bulk_bar.setEnabled(False)
        self._mutate_worker.start()

    def _on_mutation_finished(self, message: str) -> None:
        self._mutate_worker = None
        self.bulk_bar.setEnabled(True)
        QMessageBox.information(self, "Knowledge Intake Workbench", message)
        p = self._get_db_path()
        if self._loading:
            self._reload_after_mutation = True
        elif p is not None:
            self.request_load(p)

    def _on_mutation_error(self, message: str) -> None:
        self._mutate_worker = None
        self.bulk_bar.setEnabled(True)
        QMessageBox.critical(self, "Knowledge Intake Workbench", message)

    def _bulk_apply_workspace(self) -> None:
        ids = self._checked_ids()
        if not ids:
            return
        ws = self.bulk_workspace_combo.currentText().strip()
        self._start_mutation("assign", ids, workspace=ws)

    def _bulk_skip(self) -> None:
        ids = self._checked_ids()
        if not ids:
            return
        self._start_mutation("skip", ids)

    def _bulk_requeue(self) -> None:
        ids = self._checked_ids()
        if not ids:
            return
        self._start_mutation("requeue", ids)

    def _bulk_export(self) -> None:
        ids = self._checked_ids()
        if not ids:
            return
        self._on_export_csv_ids(ids)

    def _row_at_pos(self, pos) -> int:
        idx = self.table.indexAt(pos)
        return idx.row()

    def _show_context_menu(self, pos) -> None:
        row = self._row_at_pos(pos)
        if row < 0:
            return
        item = self._table_model.item(row, 1)
        if item is None:
            return
        fid = item.data(_ROLE_FILE_ID)
        if not isinstance(fid, int):
            return
        menu = QMenu(self)
        act_assign = QAction("Assign workspace…", self)
        act_skip = QAction("Mark as skip", self)
        act_requeue = QAction("Requeue for classification", self)
        menu.addAction(act_assign)
        menu.addAction(act_skip)
        menu.addAction(act_requeue)
        chosen = menu.exec(self.table.viewport().mapToGlobal(pos))
        if chosen == act_assign:
            self._pick_workspace_and_assign((fid,))
        elif chosen == act_skip:
            self._start_mutation("skip", (fid,))
        elif chosen == act_requeue:
            self._start_mutation("requeue", (fid,))

    def _pick_workspace_and_assign(self, ids: tuple[int, ...]) -> None:
        if not ids:
            return
        labels = list(WORKSPACE_OPTIONS)
        choice, ok = QInputDialog.getItem(
            self,
            "Assign workspace",
            "Workspace:",
            labels,
            0,
            False,
        )
        if ok and choice:
            self._start_mutation("assign", ids, workspace=choice)


def export_triage_rows_csv(path: str, rows: Sequence[UnassignedTriageRow]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["file_id", "filename", "matched_by", "suggested_workspace", "priority", "signals", "size_bytes"])
        for r in rows:
            w.writerow(
                [
                    r.file_id,
                    r.filename,
                    r.matched_by or "",
                    r.suggested_workspace,
                    r.priority,
                    r.signals,
                    r.size_bytes if r.size_bytes is not None else "",
                ]
            )
