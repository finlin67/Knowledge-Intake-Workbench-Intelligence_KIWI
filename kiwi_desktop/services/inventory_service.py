"""Inventory read model for GUI table views."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from collections.abc import Sequence

from db.repositories import FileRepository
from db.session import Database
from models.enums import RunnerStatus
from models.file_record import FileRecord
from services.inventory_filter import (
    FILTER_ALL,
    FILTER_FAILED,
    FILTER_MATCHED_BY,
    FILTER_REVIEW_REQUIRED,
    FILTER_WORKSPACE,
)


@dataclass(frozen=True, slots=True)
class InventoryRow:
    file_id: int
    file_name: str
    file_type: str
    size: int
    status: str
    category: str
    workspace: str
    subfolder: str
    sha256: str
    confidence: float
    matched_by: str
    classification_reason: str
    review_required: bool


@dataclass(frozen=True, slots=True)
class QueueRow:
    file_id: int
    file_name: str
    next_stage: str
    queue_status: str
    folder: str
    workspace: str
    subfolder: str
    updated_at: str


class InventoryService:
    __slots__ = ()

    def load_filter_options(self, *, db_path: Path) -> tuple[tuple[str, ...], tuple[str, ...]]:
        """Return (distinct workspaces, distinct matched_by) for filter combos."""
        db = Database(db_path)
        repo = FileRepository(db)
        return repo.list_distinct_workspaces(), repo.list_distinct_matched_by()

    def load_rows(
        self,
        *,
        db_path: Path,
        limit: int = 1000,
        filter_mode: str = FILTER_ALL,
        workspace_filter: str | None = None,
        matched_by_filter: str | None = None,
    ) -> tuple[InventoryRow, ...]:
        db = Database(db_path)
        repo = FileRepository(db)
        rows = self._select_rows(
            repo,
            limit=limit,
            filter_mode=filter_mode,
            workspace_filter=workspace_filter,
            matched_by_filter=matched_by_filter,
        )
        out: list[InventoryRow] = []
        for r in rows:
            payload = _checkpoint_payload(r.stage_checkpoint)
            category = "unknown"
            c = payload.get("category")
            if isinstance(c, str) and c:
                category = c
            confidence_num = _confidence_for_file(r, payload)
            matched_by = r.matched_by or payload.get("matched_by")
            reason = r.classification_reason or payload.get("classification_reason")
            review_required = r.review_required or bool(payload.get("review_required", False))
            subfolder_val = r.subfolder or payload.get("subfolder")
            subfolder = str(subfolder_val).strip() if subfolder_val else ""
            out.append(
                InventoryRow(
                    file_id=r.id,
                    file_name=r.filename or Path(r.path).name,
                    file_type=(r.extension or "").lstrip("."),
                    size=int(r.size_bytes or 0),
                    status=r.runner_status,
                    category=category,
                    workspace=r.workspace or "unassigned",
                    subfolder=subfolder,
                    sha256=r.sha256 or "",
                    confidence=confidence_num,
                    matched_by=str(matched_by) if matched_by else "",
                    classification_reason=str(reason) if reason else "",
                    review_required=review_required,
                )
            )
        return tuple(out)

    def load_pending_queue_split(
        self,
        *,
        db_path: Path,
        raw_folder: Path,
        export_profile: str,
        limit_each: int = 1000,
    ) -> tuple[tuple[QueueRow, ...], tuple[QueueRow, ...]]:
        """Return (current_raw_pending, outside_raw_pending) for the active profile."""
        status_col, next_stage_col = _queue_columns_for_profile(export_profile)
        db = Database(db_path)
        conn = db.connect()
        raw_root = str(raw_folder.expanduser().resolve())
        if raw_root.endswith(("\\", "/")):
            raw_prefix = raw_root
        else:
            raw_prefix = f"{raw_root}\\"
        pending_values = (
            RunnerStatus.NEW.value,
            RunnerStatus.PROCESSING.value,
            RunnerStatus.FAILED.value,
        )
        base_sql = f"""
            SELECT id,
                   COALESCE(filename, path) AS file_name,
                   path,
                   {status_col} AS queue_status,
                   {next_stage_col} AS next_stage,
                   workspace,
                   subfolder,
                   updated_at
            FROM files
            WHERE {status_col} IN (?, ?, ?)
              AND {next_stage_col} IS NOT NULL
        """
        in_rows = conn.execute(
            base_sql + " AND path LIKE ? ORDER BY id ASC LIMIT ?",
            (*pending_values, f"{raw_prefix}%", limit_each),
        ).fetchall()
        out_rows = conn.execute(
            base_sql + " AND path NOT LIKE ? ORDER BY id ASC LIMIT ?",
            (*pending_values, f"{raw_prefix}%", limit_each),
        ).fetchall()
        raw_root_path = raw_folder.expanduser().resolve()
        return tuple(_queue_row_from_db_row(r, raw_root=raw_root_path) for r in in_rows), tuple(
            _queue_row_from_db_row(r, raw_root=raw_root_path) for r in out_rows
        )

    @staticmethod
    def _select_rows(
        repo: FileRepository,
        *,
        limit: int,
        filter_mode: str,
        workspace_filter: str | None,
        matched_by_filter: str | None,
    ) -> Sequence[FileRecord]:
        if filter_mode == FILTER_ALL:
            return repo.list_recent(limit=limit)
        if filter_mode == FILTER_REVIEW_REQUIRED:
            return repo.list_recent_filtered(limit=limit, review_required_only=True)
        if filter_mode == FILTER_FAILED:
            return repo.list_recent_filtered(limit=limit, runner_status=RunnerStatus.FAILED.value)
        if filter_mode == FILTER_WORKSPACE:
            ws = (workspace_filter or "").strip()
            if not ws:
                return tuple()
            return repo.list_recent_filtered(limit=limit, workspace=ws)
        if filter_mode == FILTER_MATCHED_BY:
            mb = (matched_by_filter or "").strip()
            if not mb:
                return tuple()
            return repo.list_recent_filtered(limit=limit, matched_by=mb)
        return repo.list_recent(limit=limit)


def _confidence_for_file(rec: FileRecord, payload: dict[str, object]) -> float:
    if rec.confidence is not None:
        return float(rec.confidence)
    c = payload.get("confidence")
    return float(c) if isinstance(c, (int, float)) else 0.0


def _checkpoint_payload(stage_checkpoint: str | None) -> dict[str, object]:
    if not stage_checkpoint:
        return {}
    try:
        payload = json.loads(stage_checkpoint)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _queue_columns_for_profile(export_profile: str) -> tuple[str, str]:
    if export_profile == "anythingllm":
        return ("runner_status_anythingllm", "pipeline_next_stage_anythingllm")
    if export_profile == "open_webui":
        return ("runner_status_open_webui", "pipeline_next_stage_open_webui")
    raise ValueError(f"Unsupported export profile: {export_profile!r}")


def _queue_row_from_db_row(row, *, raw_root: Path) -> QueueRow:
    subfolder_raw = row["subfolder"]
    subfolder = str(subfolder_raw).strip() if subfolder_raw else ""
    path = Path(str(row["path"]))
    try:
        relative_parent = path.relative_to(raw_root).parent
        folder = "." if str(relative_parent) == "." else str(relative_parent)
    except ValueError:
        folder = str(path.parent)
    return QueueRow(
        file_id=int(row["id"]),
        file_name=str(row["file_name"]),
        next_stage=str(row["next_stage"] or "classified"),
        queue_status=str(row["queue_status"] or "new"),
        folder=folder,
        workspace=str(row["workspace"] or "unassigned"),
        subfolder=subfolder,
        updated_at=str(row["updated_at"] or ""),
    )
