"""Persistence for ``files`` (resumable stage + checkpoint)."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Sequence
from datetime import datetime

from db.session import Database
from models.classification_patch import ClassificationFieldsPatch
from models.enums import FileStage, RunnerStatus
from models.file_record import FileRecord
from models.triage_derivation import UnassignedTriageRow, build_unassigned_triage_row

_PROFILE_QUEUE_COLUMNS: dict[str, tuple[str, str]] = {
    "anythingllm": ("runner_status_anythingllm", "pipeline_next_stage_anythingllm"),
    "open_webui": ("runner_status_open_webui", "pipeline_next_stage_open_webui"),
}

_FILE_SELECT = """
SELECT id, path, filename, extension, file_created_at, file_modified_at,
       display_name, size_bytes, sha256, mime_type,
       current_stage, stage_checkpoint, pipeline_version, stage_attempt,
       last_error, runner_status, pipeline_next_stage, workspace,
       subfolder, matched_by, classification_reason, review_required, ai_used, content_hash,
       confidence,
       case_study_candidate, portfolio_candidate,
       created_at, updated_at
FROM files
"""


def _dt_iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        return dt.replace(microsecond=0).isoformat()
    return dt.astimezone().replace(microsecond=0).isoformat()


def _queue_columns_for_profile(export_profile: str) -> tuple[str, str]:
    columns = _PROFILE_QUEUE_COLUMNS.get(export_profile)
    if columns is None:
        raise ValueError(f"Unsupported export profile: {export_profile!r}")
    return columns


class FileRepository:
    """CRUD and stage transitions for tracked files."""

    __slots__ = ("_db",)

    def __init__(self, database: Database) -> None:
        self._db = database

    def get_by_id(self, file_id: int) -> FileRecord | None:
        conn = self._db.connect()
        row = conn.execute(
            f"{_FILE_SELECT} WHERE id = ?",
            (file_id,),
        ).fetchone()
        return FileRecord.from_row(row) if row is not None else None

    def get_by_path(self, path: str) -> FileRecord | None:
        conn = self._db.connect()
        row = conn.execute(
            f"{_FILE_SELECT} WHERE path = ?",
            (path,),
        ).fetchone()
        return FileRecord.from_row(row) if row is not None else None

    def insert(
        self,
        *,
        path: str,
        display_name: str | None = None,
        size_bytes: int | None = None,
        sha256: str | None = None,
        mime_type: str | None = None,
        current_stage: str = FileStage.PENDING.value,
        pipeline_version: int = 1,
    ) -> FileRecord:
        conn = self._db.connect()
        try:
            cur = conn.execute(
                """
                INSERT INTO files (
                    path, display_name, size_bytes, sha256, mime_type,
                    current_stage, pipeline_version,
                    runner_status, pipeline_next_stage,
                    runner_status_anythingllm, pipeline_next_stage_anythingllm,
                    runner_status_open_webui, pipeline_next_stage_open_webui,
                    workspace
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    path,
                    display_name,
                    size_bytes,
                    sha256,
                    mime_type,
                    current_stage,
                    pipeline_version,
                    RunnerStatus.NEW.value,
                    "classified",
                    RunnerStatus.NEW.value,
                    "classified",
                    RunnerStatus.NEW.value,
                    "classified",
                    "",
                ),
            )
            new_id = cur.lastrowid
            conn.commit()
        except sqlite3.IntegrityError:
            conn.rollback()
            raise

        row = conn.execute(
            f"{_FILE_SELECT} WHERE id = ?",
            (new_id,),
        ).fetchone()
        if row is None:
            raise sqlite3.DatabaseError("Insert did not persist a row")
        return FileRecord.from_row(row)

    def upsert_scanned_file(
        self,
        *,
        path: str,
        filename: str,
        extension: str,
        size_bytes: int,
        sha256_hex: str,
        file_created_at: datetime,
        file_modified_at: datetime,
        mime_type: str | None,
        display_name: str | None = None,
    ) -> FileRecord:
        """
        Insert or update a file row by ``path``.

        On conflict: refreshes filesystem metadata and hash; **does not** change
        ``current_stage``, pipeline fields, or the row ``created_at`` timestamp.
        """
        conn = self._db.connect()
        display = display_name if display_name is not None else filename
        conn.execute(
            """
            INSERT INTO files (
                path, filename, extension, display_name, size_bytes, sha256, mime_type,
                file_created_at, file_modified_at, current_stage, pipeline_version,
                runner_status, pipeline_next_stage,
                runner_status_anythingllm, pipeline_next_stage_anythingllm,
                runner_status_open_webui, pipeline_next_stage_open_webui,
                workspace
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(path) DO UPDATE SET
                filename = excluded.filename,
                extension = excluded.extension,
                display_name = COALESCE(excluded.display_name, files.display_name),
                size_bytes = excluded.size_bytes,
                sha256 = excluded.sha256,
                mime_type = excluded.mime_type,
                file_created_at = excluded.file_created_at,
                file_modified_at = excluded.file_modified_at,
                updated_at = datetime('now')
            """,
            (
                path,
                filename,
                extension,
                display,
                size_bytes,
                sha256_hex,
                mime_type,
                _dt_iso(file_created_at),
                _dt_iso(file_modified_at),
                FileStage.PENDING.value,
                1,
                RunnerStatus.NEW.value,
                "classified",
                RunnerStatus.NEW.value,
                "classified",
                RunnerStatus.NEW.value,
                "classified",
                "",
            ),
        )
        conn.commit()
        row = conn.execute(
            f"{_FILE_SELECT} WHERE path = ?",
            (path,),
        ).fetchone()
        if row is None:
            raise sqlite3.DatabaseError("Upsert did not persist a row")
        return FileRecord.from_row(row)

    def list_for_runner(self, *, limit: int, export_profile: str = "anythingllm") -> Sequence[FileRecord]:
        """Files eligible for resumable processing: new, processing, or failed with work left."""
        status_col, next_stage_col = _queue_columns_for_profile(export_profile)
        conn = self._db.connect()
        rows = conn.execute(
            f"""
            {_FILE_SELECT}
            WHERE {status_col} IN (?, ?, ?)
              AND {next_stage_col} IS NOT NULL
            ORDER BY id ASC
            LIMIT ?
            """,
            (
                RunnerStatus.NEW.value,
                RunnerStatus.PROCESSING.value,
                RunnerStatus.FAILED.value,
                limit,
            ),
        ).fetchall()
        return tuple(FileRecord.from_row(r) for r in rows)

    def next_for_runner(self, *, exclude_ids: set[int], export_profile: str = "anythingllm") -> FileRecord | None:
        """Smallest-id eligible file not in ``exclude_ids`` (one attempt per id per run)."""
        status_col, next_stage_col = _queue_columns_for_profile(export_profile)
        conn = self._db.connect()
        if exclude_ids:
            qs = ",".join("?" * len(exclude_ids))
            sql = f"""
            {_FILE_SELECT}
            WHERE {status_col} IN (?, ?, ?)
              AND {next_stage_col} IS NOT NULL
              AND id NOT IN ({qs})
            ORDER BY id ASC
            LIMIT 1
            """
            params = (
                RunnerStatus.NEW.value,
                RunnerStatus.PROCESSING.value,
                RunnerStatus.FAILED.value,
                *sorted(exclude_ids),
            )
        else:
            sql = f"""
            {_FILE_SELECT}
            WHERE {status_col} IN (?, ?, ?)
              AND {next_stage_col} IS NOT NULL
            ORDER BY id ASC
            LIMIT 1
            """
            params = (
                RunnerStatus.NEW.value,
                RunnerStatus.PROCESSING.value,
                RunnerStatus.FAILED.value,
            )
        row = conn.execute(sql, params).fetchone()
        return FileRecord.from_row(row) if row is not None else None

    def get_profile_queue_state(self, file_id: int, *, export_profile: str) -> tuple[str, str | None]:
        status_col, next_stage_col = _queue_columns_for_profile(export_profile)
        conn = self._db.connect()
        row = conn.execute(
            f"SELECT {status_col} AS runner_status, {next_stage_col} AS pipeline_next_stage FROM files WHERE id = ?",
            (file_id,),
        ).fetchone()
        if row is None:
            raise ValueError(f"File id not found: {file_id}")
        return str(row["runner_status"]), row["pipeline_next_stage"]

    def mark_runner_processing(self, file_id: int, *, export_profile: str = "anythingllm") -> None:
        status_col, _next_stage_col = _queue_columns_for_profile(export_profile)
        conn = self._db.connect()
        conn.execute(
            f"""
            UPDATE files
            SET {status_col} = ?,
                runner_status = ?,
                updated_at = datetime('now')
            WHERE id = ?
            """,
            (RunnerStatus.PROCESSING.value, RunnerStatus.PROCESSING.value, file_id),
        )
        conn.commit()

    def commit_pipeline_stage_success(
        self,
        file_id: int,
        *,
        next_stage: str | None,
        export_profile: str = "anythingllm",
    ) -> None:
        """Persist after a successful pipeline stage; ``next_stage`` None means fully exported."""
        status_col, next_stage_col = _queue_columns_for_profile(export_profile)
        conn = self._db.connect()
        if next_stage is None:
            conn.execute(
                f"""
                UPDATE files SET
                    {status_col} = ?,
                    {next_stage_col} = NULL,
                    runner_status = ?,
                    pipeline_next_stage = NULL,
                    last_error = NULL,
                    updated_at = datetime('now')
                WHERE id = ?
                """,
                (RunnerStatus.COMPLETED.value, RunnerStatus.COMPLETED.value, file_id),
            )
        else:
            conn.execute(
                f"""
                UPDATE files SET
                    {status_col} = ?,
                    {next_stage_col} = ?,
                    runner_status = ?,
                    pipeline_next_stage = ?,
                    last_error = NULL,
                    updated_at = datetime('now')
                WHERE id = ?
                """,
                (RunnerStatus.PROCESSING.value, next_stage, RunnerStatus.PROCESSING.value, next_stage, file_id),
            )
        conn.commit()

    def mark_runner_failed(self, file_id: int, message: str, *, export_profile: str = "anythingllm") -> None:
        status_col, _next_stage_col = _queue_columns_for_profile(export_profile)
        conn = self._db.connect()
        conn.execute(
            f"""
            UPDATE files SET
                {status_col} = ?,
                runner_status = ?,
                last_error = ?,
                updated_at = datetime('now')
            WHERE id = ?
            """,
            (RunnerStatus.FAILED.value, RunnerStatus.FAILED.value, message, file_id),
        )
        conn.commit()

    def set_workspace(self, file_id: int, workspace: str | None) -> None:
        conn = self._db.connect()
        conn.execute(
            """
            UPDATE files
            SET workspace = ?, updated_at = datetime('now')
            WHERE id = ?
            """,
            ("" if workspace is None else workspace, file_id),
        )
        conn.commit()

    def update_classification_fields(self, file_id: int, patch: ClassificationFieldsPatch) -> None:
        """Update classification columns present in ``patch`` (workspace, subfolder, matched_by, reason, content_hash, confidence)."""
        if not patch:
            return
        fragments: list[str] = []
        params: list[object] = []
        if "workspace" in patch:
            fragments.append("workspace = ?")
            w = patch["workspace"]
            params.append("" if w is None else w)
        if "subfolder" in patch:
            fragments.append("subfolder = ?")
            params.append(patch["subfolder"])
        if "matched_by" in patch:
            fragments.append("matched_by = ?")
            params.append(patch["matched_by"])
        if "classification_reason" in patch:
            fragments.append("classification_reason = ?")
            params.append(patch["classification_reason"])
        if "content_hash" in patch:
            fragments.append("content_hash = ?")
            params.append(patch["content_hash"])
        if "confidence" in patch:
            fragments.append("confidence = ?")
            c = patch["confidence"]
            params.append(None if c is None else float(c))
        if "case_study_candidate" in patch:
            fragments.append("case_study_candidate = ?")
            params.append(1 if patch["case_study_candidate"] else 0)
        if "portfolio_candidate" in patch:
            fragments.append("portfolio_candidate = ?")
            params.append(1 if patch["portfolio_candidate"] else 0)
        if not fragments:
            return
        fragments.append("updated_at = datetime('now')")
        params.append(file_id)
        conn = self._db.connect()
        conn.execute(
            f"UPDATE files SET {', '.join(fragments)} WHERE id = ?",
            params,
        )
        conn.commit()

    def set_review_required(self, file_id: int, required: bool) -> None:
        conn = self._db.connect()
        conn.execute(
            """
            UPDATE files
            SET review_required = ?, updated_at = datetime('now')
            WHERE id = ?
            """,
            (1 if required else 0, file_id),
        )
        conn.commit()

    def set_ai_used(self, file_id: int, used: bool) -> None:
        conn = self._db.connect()
        conn.execute(
            """
            UPDATE files
            SET ai_used = ?, updated_at = datetime('now')
            WHERE id = ?
            """,
            (1 if used else 0, file_id),
        )
        conn.commit()

    def list_by_stage(self, stage: str, *, limit: int = 100) -> Sequence[FileRecord]:
        conn = self._db.connect()
        rows = conn.execute(
            f"""
            {_FILE_SELECT}
            WHERE current_stage = ?
            ORDER BY updated_at ASC
            LIMIT ?
            """,
            (stage, limit),
        ).fetchall()
        return tuple(FileRecord.from_row(r) for r in rows)

    def list_recent(self, *, limit: int = 100) -> Sequence[FileRecord]:
        conn = self._db.connect()
        rows = conn.execute(
            f"""
            {_FILE_SELECT}
            ORDER BY updated_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return tuple(FileRecord.from_row(r) for r in rows)

    def list_recent_filtered(
        self,
        *,
        limit: int = 1000,
        runner_status: str | None = None,
        review_required_only: bool = False,
        workspace: str | None = None,
        matched_by: str | None = None,
    ) -> Sequence[FileRecord]:
        """Inventory-style filtered listing; all conditions are ANDed when provided."""
        conn = self._db.connect()
        where: list[str] = []
        params: list[object] = []
        if runner_status is not None:
            where.append("runner_status = ?")
            params.append(runner_status)
        if review_required_only:
            where.append("review_required = 1")
        if workspace is not None:
            where.append("workspace = ?")
            params.append(workspace)
        if matched_by is not None:
            where.append("matched_by = ?")
            params.append(matched_by)
        where_sql = " AND ".join(where) if where else "1 = 1"
        sql = f"""
            {_FILE_SELECT}
            WHERE {where_sql}
            ORDER BY updated_at DESC
            LIMIT ?
        """
        params.append(limit)
        rows = conn.execute(sql, params).fetchall()
        return tuple(FileRecord.from_row(r) for r in rows)

    def list_distinct_workspaces(self) -> tuple[str, ...]:
        conn = self._db.connect()
        rows = conn.execute(
            """
            SELECT DISTINCT workspace
            FROM files
            WHERE workspace IS NOT NULL AND TRIM(workspace) != ''
            ORDER BY workspace ASC
            """
        ).fetchall()
        return tuple(str(r[0]) for r in rows)

    def list_distinct_matched_by(self) -> tuple[str, ...]:
        conn = self._db.connect()
        rows = conn.execute(
            """
            SELECT DISTINCT matched_by
            FROM files
            WHERE matched_by IS NOT NULL AND TRIM(matched_by) != ''
            ORDER BY matched_by ASC
            """
        ).fetchall()
        return tuple(str(r[0]) for r in rows)

    def list_unassigned(self) -> tuple[UnassignedTriageRow, ...]:
        """
        Files with no concrete workspace assignment (NULL, blank, or 'unassigned').
        Derived triage fields are computed in Python (see ``models.triage_derivation``).
        """
        conn = self._db.connect()
        rows = conn.execute(
            f"""
            {_FILE_SELECT}
            WHERE workspace IS NULL
               OR TRIM(workspace) = ''
               OR LOWER(TRIM(workspace)) = 'unassigned'
            ORDER BY updated_at DESC
            """
        ).fetchall()
        out: list[UnassignedTriageRow] = []
        for row in rows:
            rec = FileRecord.from_row(row)
            out.append(build_unassigned_triage_row(rec))
        return tuple(out)

    def requeue_for_classification(self, file_ids: Sequence[int]) -> int:
        """Reset runner columns so selected files are eligible for classification/export again."""
        if not file_ids:
            return 0
        conn = self._db.connect()
        q = ",".join("?" * len(file_ids))
        cur = conn.execute(
            f"""
            UPDATE files
            SET runner_status = ?,
                pipeline_next_stage = ?,
                runner_status_anythingllm = ?,
                pipeline_next_stage_anythingllm = ?,
                runner_status_open_webui = ?,
                pipeline_next_stage_open_webui = ?,
                last_error = NULL,
                updated_at = datetime('now')
            WHERE id IN ({q})
            """,
            (
                RunnerStatus.NEW.value,
                "classified",
                RunnerStatus.NEW.value,
                "classified",
                RunnerStatus.NEW.value,
                "classified",
                *file_ids,
            ),
        )
        conn.commit()
        return int(cur.rowcount or 0)

    def get_cached_ollama_classification(self, *, content_hash: str) -> dict[str, object] | None:
        conn = self._db.connect()
        row = conn.execute(
            f"""
            {_FILE_SELECT}
            WHERE content_hash = ?
              AND matched_by = 'ollama'
            ORDER BY updated_at DESC
            LIMIT 1
            """,
            (content_hash,),
        ).fetchone()
        if row is None:
            return None
        rec = FileRecord.from_row(row)
        payload: dict[str, object] = {}
        if rec.stage_checkpoint:
            try:
                raw = json.loads(rec.stage_checkpoint)
            except json.JSONDecodeError:
                raw = {}
            if isinstance(raw, dict):
                payload = raw
        category = payload.get("category")
        confidence = payload.get("confidence")
        if not isinstance(category, str) or not category.strip():
            return None
        if not isinstance(confidence, (int, float)):
            confidence = 0.0
        conf_out = float(rec.confidence) if rec.confidence is not None else float(confidence)
        return {
            "category": category.strip(),
            "workspace": (rec.workspace or "").strip() or str(payload.get("workspace") or ""),
            "subfolder": str(rec.subfolder or payload.get("subfolder") or "").strip(),
            "confidence": conf_out,
            "reason": str(rec.classification_reason or payload.get("classification_reason") or "ollama cache"),
        }

    def update_stage_checkpoint(self, file_id: int, checkpoint: str | None) -> None:
        """Update ``stage_checkpoint`` JSON (e.g. normalized output path) without changing pipeline stage."""
        conn = self._db.connect()
        conn.execute(
            """
            UPDATE files SET stage_checkpoint = ?, updated_at = datetime('now')
            WHERE id = ?
            """,
            (checkpoint, file_id),
        )
        conn.commit()

    def set_stage(
        self,
        file_id: int,
        *,
        stage: str,
        checkpoint: str | None = None,
        pipeline_version: int | None = None,
        last_error: str | None = None,
        clear_error: bool = False,
    ) -> None:
        """Unconditional stage update (repair / forced moves)."""
        conn = self._db.connect()
        fragments = [
            "current_stage = ?",
            "stage_checkpoint = ?",
            "updated_at = datetime('now')",
        ]
        params: list[object] = [stage, checkpoint]
        if pipeline_version is not None:
            fragments.append("pipeline_version = ?")
            params.append(pipeline_version)
        if clear_error:
            fragments.append("last_error = NULL")
        elif last_error is not None:
            fragments.append("last_error = ?")
            params.append(last_error)
        params.append(file_id)
        sql = f"UPDATE files SET {', '.join(fragments)} WHERE id = ?"
        conn.execute(sql, params)
        conn.commit()

    def try_transition_stage(
        self,
        file_id: int,
        *,
        expect_stage: str,
        new_stage: str,
        checkpoint: str | None = None,
        clear_error: bool = True,
        increment_attempt: bool = False,
    ) -> bool:
        """
        Move ``file_id`` from ``expect_stage`` to ``new_stage`` if still at ``expect_stage``.

        Returns True when exactly one row matched (successful compare-and-swap).
        """
        conn = self._db.connect()
        cur = conn.execute(
            """
            UPDATE files SET
                current_stage = ?,
                stage_checkpoint = ?,
                updated_at = datetime('now'),
                last_error = CASE WHEN ? THEN NULL ELSE last_error END,
                stage_attempt = CASE WHEN ? THEN stage_attempt + 1 ELSE stage_attempt END
            WHERE id = ? AND current_stage = ?
            """,
            (
                new_stage,
                checkpoint,
                1 if clear_error else 0,
                1 if increment_attempt else 0,
                file_id,
                expect_stage,
            ),
        )
        conn.commit()
        return cur.rowcount == 1

    def record_failure(self, file_id: int, *, message: str, stage: str | None = None) -> None:
        """Set ``last_error`` and optionally force ``current_stage`` (e.g. to ``failed``)."""
        conn = self._db.connect()
        if stage is None:
            conn.execute(
                """
                UPDATE files SET last_error = ?, updated_at = datetime('now')
                WHERE id = ?
                """,
                (message, file_id),
            )
        else:
            conn.execute(
                """
                UPDATE files SET
                    current_stage = ?,
                    last_error = ?,
                    updated_at = datetime('now')
                WHERE id = ?
                """,
                (stage, message, file_id),
            )
        conn.commit()
