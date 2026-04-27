"""Run monitor control flow for GUI: start/pause/resume + log streaming."""

from __future__ import annotations

import json
import os
import re
import sqlite3
import threading
from collections.abc import Callable
from queue import Empty, SimpleQueue
from dataclasses import dataclass
from pathlib import Path

from db.repositories import FileRepository
from db.session import Database
from models.enums import RunnerStatus
from services.classification_config import DEFAULT_CONFIG_FILENAME, load_classification_config
from services.classification_service import MATCH_FALLBACK, MATCH_FORCE_RULE, MATCH_NEGATIVE_RULE, ClassificationService
from services.pipeline_runner import PipelineRunner
from services.scan_service import ScanService
from utils.logging_utils import get_logger


def _profile_queue_columns(profile: str) -> tuple[str, str]:
    if profile == "anythingllm":
        return ("runner_status_anythingllm", "pipeline_next_stage_anythingllm")
    if profile == "open_webui":
        return ("runner_status_open_webui", "pipeline_next_stage_open_webui")
    raise ValueError(f"Unsupported export profile: {profile!r}")


@dataclass(frozen=True, slots=True)
class RunSnapshot:
    total_files: int
    processed: int
    failed: int
    review_required: int
    current_file: str
    current_stage: str
    state: str


@dataclass(frozen=True, slots=True)
class PreflightFilePreview:
    file_name: str
    likely_workspace: str
    next_stage: str
    review_required: bool


@dataclass(frozen=True, slots=True)
class ClassificationPreviewRow:
    file_name: str
    predicted_workspace: str
    confidence: float
    matched_by: str


@dataclass(frozen=True, slots=True)
class PreflightSummary:
    total_files: int
    pending_files: int
    processed_files: int
    failed_files: int
    pending_in_raw_folder: int
    pending_outside_raw_folder: int
    active_export_profile: str
    output_root: Path
    normalized_root: Path
    ollama_enabled: bool
    ai_mode: str
    auto_assign_workspace: bool
    estimated_review_count: int
    classification_total_files: int
    classification_by_workspace: tuple[tuple[str, int], ...]
    classification_review_required: int
    classification_ai_count: int
    classification_rules_count: int
    classification_relevance_gate_count: int
    classification_small_file_lane_count: int
    classification_wiki_count: int
    classification_wiki_share: float
    preflight_wiki_share_cap: float
    wiki_share_cap_exceeded: bool
    classification_sample: tuple[ClassificationPreviewRow, ...]
    previews: tuple[PreflightFilePreview, ...]
    human_summary: str


@dataclass(frozen=True, slots=True)
class CompletedRunSummary:
    run_id: int
    export_profile: str
    final_state: str
    files_started: int
    files_finished_ok: int
    files_marked_failed: int


@dataclass(frozen=True, slots=True)
class PendingBatchOverview:
    current_pending: int
    other_pending: int
    next_batch_folder: Path | None


class RunMonitorService:
    """Owns the worker loop so GUI can stay event-driven and thin."""

    __slots__ = (
        "_thread",
        "_pause",
        "_stop",
        "_running",
        "_db_path",
        "_raw_folder",
        "_output_folder",
        "_export_profile",
        "_log_queue",
        "_final_state",
        "_last_snapshot",
        "_logger",
        "_run_id",
        "_last_completed_run",
    )

    def __init__(self) -> None:
        self._thread: threading.Thread | None = None
        self._pause = threading.Event()
        self._stop = threading.Event()
        self._running = threading.Event()
        self._db_path: Path | None = None
        self._raw_folder: Path | None = None
        self._output_folder: Path | None = None
        self._export_profile = "anythingllm"
        self._log_queue: SimpleQueue[str] = SimpleQueue()
        self._final_state = "idle"
        self._last_snapshot = RunSnapshot(
            total_files=0,
            processed=0,
            failed=0,
            review_required=0,
            current_file="-",
            current_stage="-",
            state="idle",
        )
        self._logger = get_logger("kiw.run_monitor")
        self._run_id = 0
        self._last_completed_run: CompletedRunSummary | None = None

    def configure(
        self,
        *,
        db_path: Path,
        raw_folder: Path,
        output_folder: Path,
        export_profile: str = "anythingllm",
        log: Callable[[str], None],
    ) -> None:
        self._db_path = db_path
        self._raw_folder = raw_folder
        self._output_folder = output_folder
        self._export_profile = export_profile
        del log

    def is_running(self) -> bool:
        return self._running.is_set()

    def drain_logs(self) -> tuple[str, ...]:
        out: list[str] = []
        while True:
            try:
                out.append(self._log_queue.get_nowait())
            except Empty:
                break
        return tuple(out)

    def snapshot(self) -> RunSnapshot:
        if self._db_path is None:
            self._last_snapshot = RunSnapshot(
                total_files=0,
                processed=0,
                failed=0,
                review_required=0,
                current_file="-",
                current_stage="-",
                state="idle",
            )
            return self._last_snapshot
        status_col, next_stage_col = _profile_queue_columns(self._export_profile)
        try:
            conn = Database(self._db_path).connect()
            total_files = int(conn.execute("SELECT COUNT(*) FROM files").fetchone()[0] or 0)
            processed = int(
                conn.execute(f"SELECT COUNT(*) FROM files WHERE {status_col} = ?", (RunnerStatus.COMPLETED.value,)).fetchone()[0]
                or 0
            )
            failed = int(
                conn.execute(f"SELECT COUNT(*) FROM files WHERE {status_col} = ?", (RunnerStatus.FAILED.value,)).fetchone()[0]
                or 0
            )
            review_required = int(conn.execute("SELECT COUNT(*) FROM files WHERE review_required = 1").fetchone()[0] or 0)
            row = conn.execute(
                f"""
                SELECT COALESCE(filename, path) AS file_name, {next_stage_col} AS pipeline_next_stage
                FROM files
                WHERE {status_col} = ?
                ORDER BY updated_at DESC, id DESC
                LIMIT 1
                """,
                (RunnerStatus.PROCESSING.value,),
            ).fetchone()
            if row is None:
                current_file = "-"
                current_stage = "-"
            else:
                current_file = str(row["file_name"])
                current_stage = str(row["pipeline_next_stage"] or "-")
            if self._running.is_set():
                state = "paused" if self._pause.is_set() else "running"
            else:
                state = self._final_state
            self._last_snapshot = RunSnapshot(
                total_files=total_files,
                processed=processed,
                failed=failed,
                review_required=review_required,
                current_file=current_file,
                current_stage=current_stage,
                state=state,
            )
            return self._last_snapshot
        except sqlite3.OperationalError as exc:
            # Most commonly "database is locked" while the worker is committing.
            self._logger.warning("snapshot query skipped due to DB lock", extra={"error": str(exc)})
            if self._running.is_set():
                state = "paused" if self._pause.is_set() else "running"
            else:
                state = self._final_state
            self._last_snapshot = RunSnapshot(
                total_files=self._last_snapshot.total_files,
                processed=self._last_snapshot.processed,
                failed=self._last_snapshot.failed,
                review_required=self._last_snapshot.review_required,
                current_file=self._last_snapshot.current_file,
                current_stage=self._last_snapshot.current_stage,
                state=state,
            )
            return self._last_snapshot

    def start_with_options(self, *, scan_first: bool) -> None:
        if self._running.is_set():
            return
        missing: list[str] = []
        if self._db_path is None:
            missing.append("db_path")
        if self._raw_folder is None:
            missing.append("raw_folder")
        if self._output_folder is None:
            missing.append("output_folder")
        if missing:
            raise RuntimeError(
                "Run monitor is not configured. Missing: " + ", ".join(missing) + ". "
                "Create or load a project first."
            )
        self._pause.clear()
        self._stop.clear()
        self._run_id += 1
        self._last_completed_run = None
        self._final_state = "starting"
        self._drain_stale_logs()
        self._enqueue_log("Run started.")
        self._logger.info("run started", extra={"scan_first": scan_first})
        self._thread = threading.Thread(
            target=self._worker,
            kwargs={"scan_first": scan_first},
            name="kiw-runner",
            daemon=True,
        )
        self._thread.start()

    def start(self, *, scan_first: bool = True) -> None:
        self.start_with_options(scan_first=scan_first)

    def pause(self) -> None:
        self._pause.set()
        self._enqueue_log("Run paused.")

    def resume(self) -> None:
        self._pause.clear()
        self._enqueue_log("Run resumed.")

    def stop(self) -> None:
        self._stop.set()
        self._pause.clear()
        self._final_state = "stopping"
        self._enqueue_log("Stopping...")

    def scan_once(self) -> None:
        if self._running.is_set():
            raise RuntimeError("Cannot scan while run monitor is active.")
        if self._db_path is None or self._raw_folder is None:
            raise RuntimeError("Run monitor is not configured. Create or load a project first.")
        db = Database(self._db_path)
        db.connect()
        try:
            scan = ScanService(db)
            self._enqueue_log(f"Scanning: {self._raw_folder}")
            scan_result = scan.scan(self._raw_folder)
            self._enqueue_log(
                f"Scan matched={scan_result.files_matched}, upserted={scan_result.files_upserted}, "
                f"errors={len(scan_result.errors)}"
            )
        finally:
            db.close()

    def requeue_all(self) -> int:
        """Reset all tracked files to eligible NEW/classified state."""
        if self._running.is_set():
            raise RuntimeError("Cannot requeue while run monitor is active.")
        if self._db_path is None:
            raise RuntimeError("Run monitor is not configured. Create or load a project first.")
        status_col, next_stage_col = _profile_queue_columns(self._export_profile)
        conn = Database(self._db_path).connect()
        cur = conn.execute(
            f"""
            UPDATE files
            SET {status_col} = ?,
                {next_stage_col} = ?,
                runner_status = ?,
                pipeline_next_stage = ?,
                last_error = NULL,
                updated_at = datetime('now')
            """,
            (RunnerStatus.NEW.value, "classified", RunnerStatus.NEW.value, "classified"),
        )
        conn.commit()
        updated = int(cur.rowcount or 0)
        self._enqueue_log(f"Requeued {updated} file(s) for processing.")
        self._logger.info("requeue all completed", extra={"updated": updated})
        return updated

    def clear_pending_queue(self) -> int:
        """Mark NEW/PROCESSING/FAILED queue items as COMPLETED for active profile."""
        if self._running.is_set():
            raise RuntimeError("Cannot clear queue while run monitor is active.")
        if self._db_path is None:
            raise RuntimeError("Run monitor is not configured. Create or load a project first.")
        status_col, next_stage_col = _profile_queue_columns(self._export_profile)
        conn = Database(self._db_path).connect()
        cur = conn.execute(
            f"""
            UPDATE files
            SET {status_col} = ?,
                {next_stage_col} = NULL,
                runner_status = ?,
                pipeline_next_stage = NULL,
                last_error = NULL,
                updated_at = datetime('now')
            WHERE {status_col} IN (?, ?, ?)
              AND {next_stage_col} IS NOT NULL
            """,
            (
                RunnerStatus.COMPLETED.value,
                RunnerStatus.COMPLETED.value,
                RunnerStatus.NEW.value,
                RunnerStatus.PROCESSING.value,
                RunnerStatus.FAILED.value,
            ),
        )
        conn.commit()
        cleared = int(cur.rowcount or 0)
        self._enqueue_log(f"Cleared {cleared} pending file(s) from active queue.")
        self._logger.info("clear pending queue completed", extra={"cleared": cleared})
        return cleared

    def clear_pending_outside_current_raw(self) -> int:
        """Clear pending queue entries outside the current raw folder for active profile."""
        if self._running.is_set():
            raise RuntimeError("Cannot clear queue while run monitor is active.")
        if self._db_path is None or self._raw_folder is None:
            raise RuntimeError("Run monitor is not configured. Create or load a project first.")
        status_col, next_stage_col = _profile_queue_columns(self._export_profile)
        raw_prefix = self._raw_path_prefix()
        conn = Database(self._db_path).connect()
        cur = conn.execute(
            f"""
            UPDATE files
            SET {status_col} = ?,
                {next_stage_col} = NULL,
                runner_status = ?,
                pipeline_next_stage = NULL,
                last_error = NULL,
                updated_at = datetime('now')
            WHERE {status_col} IN (?, ?, ?)
              AND {next_stage_col} IS NOT NULL
              AND path NOT LIKE ?
            """,
            (
                RunnerStatus.COMPLETED.value,
                RunnerStatus.COMPLETED.value,
                RunnerStatus.NEW.value,
                RunnerStatus.PROCESSING.value,
                RunnerStatus.FAILED.value,
                f"{raw_prefix}%",
            ),
        )
        conn.commit()
        cleared = int(cur.rowcount or 0)
        self._enqueue_log(f"Cleared {cleared} pending file(s) outside the current raw folder.")
        self._logger.info("clear pending outside raw completed", extra={"cleared": cleared})
        return cleared

    def requeue_current_raw(self) -> int:
        """Requeue all tracked files in the current raw folder for active profile."""
        if self._running.is_set():
            raise RuntimeError("Cannot requeue while run monitor is active.")
        if self._db_path is None or self._raw_folder is None:
            raise RuntimeError("Run monitor is not configured. Create or load a project first.")
        status_col, next_stage_col = _profile_queue_columns(self._export_profile)
        raw_prefix = self._raw_path_prefix()
        conn = Database(self._db_path).connect()
        cur = conn.execute(
            f"""
            UPDATE files
            SET {status_col} = ?,
                {next_stage_col} = ?,
                runner_status = ?,
                pipeline_next_stage = ?,
                last_error = NULL,
                updated_at = datetime('now')
            WHERE path LIKE ?
            """,
            (
                RunnerStatus.NEW.value,
                "classified",
                RunnerStatus.NEW.value,
                "classified",
                f"{raw_prefix}%",
            ),
        )
        conn.commit()
        updated = int(cur.rowcount or 0)
        self._enqueue_log(f"Requeued {updated} file(s) in the current raw folder.")
        self._logger.info("requeue current raw completed", extra={"updated": updated})
        return updated

    def build_preflight_summary(self, *, preview_limit: int = 5) -> PreflightSummary:
        if self._db_path is None or self._output_folder is None or self._raw_folder is None:
            raise RuntimeError("Run monitor is not configured. Create or load a project first.")
        status_col, next_stage_col = _profile_queue_columns(self._export_profile)
        conn = Database(self._db_path).connect()
        raw_root = str(self._raw_folder.resolve())
        if raw_root.endswith(("\\", "/")):
            raw_prefix = raw_root
        else:
            raw_prefix = f"{raw_root}{os.sep}"
        total_files = int(conn.execute("SELECT COUNT(*) FROM files").fetchone()[0] or 0)
        pending_files = int(
            conn.execute(
                f"""
                SELECT COUNT(*) FROM files
                WHERE {status_col} IN (?, ?, ?)
                  AND {next_stage_col} IS NOT NULL
                """,
                (RunnerStatus.NEW.value, RunnerStatus.PROCESSING.value, RunnerStatus.FAILED.value),
            ).fetchone()[0]
            or 0
        )
        processed_files = int(
            conn.execute(f"SELECT COUNT(*) FROM files WHERE {status_col} = ?", (RunnerStatus.COMPLETED.value,)).fetchone()[0]
            or 0
        )
        failed_files = int(
            conn.execute(f"SELECT COUNT(*) FROM files WHERE {status_col} = ?", (RunnerStatus.FAILED.value,)).fetchone()[0]
            or 0
        )
        pending_in_raw_folder = int(
            conn.execute(
                f"""
                SELECT COUNT(*) FROM files
                WHERE {status_col} IN (?, ?, ?)
                  AND {next_stage_col} IS NOT NULL
                  AND path LIKE ?
                """,
                (
                    RunnerStatus.NEW.value,
                    RunnerStatus.PROCESSING.value,
                    RunnerStatus.FAILED.value,
                    f"{raw_prefix}%",
                ),
            ).fetchone()[0]
            or 0
        )
        pending_outside_raw_folder = max(0, pending_files - pending_in_raw_folder)
        pending_review_required = int(
            conn.execute(
                f"""
                SELECT COUNT(*) FROM files
                WHERE {status_col} IN (?, ?, ?)
                  AND {next_stage_col} IS NOT NULL
                  AND review_required = 1
                """,
                (RunnerStatus.NEW.value, RunnerStatus.PROCESSING.value, RunnerStatus.FAILED.value),
            ).fetchone()[0]
            or 0
        )
        completed_review_required = int(
            conn.execute(
                f"SELECT COUNT(*) FROM files WHERE {status_col} = ? AND review_required = 1",
                (RunnerStatus.COMPLETED.value,),
            ).fetchone()[0]
            or 0
        )
        historical_rate = (completed_review_required / processed_files) if processed_files > 0 else 0.0
        estimated_review_count = max(pending_review_required, int(round(pending_files * historical_rate)))

        cfg = load_classification_config(self._output_folder / ".kiw" / DEFAULT_CONFIG_FILENAME)
        classification_preview = self._build_classification_preview(
            db_path=self._db_path,
            export_profile=self._export_profile,
            config=cfg,
            sample_limit=max(10, min(20, preview_limit)),
        )
        preview_rows = conn.execute(
            f"""
            SELECT COALESCE(filename, path) AS file_name,
                   workspace,
                   stage_checkpoint,
                   review_required,
                   {next_stage_col} AS next_stage
            FROM files
            WHERE {status_col} IN (?, ?, ?)
              AND {next_stage_col} IS NOT NULL
            ORDER BY id ASC
            LIMIT ?
            """,
            (RunnerStatus.NEW.value, RunnerStatus.PROCESSING.value, RunnerStatus.FAILED.value, max(1, preview_limit)),
        ).fetchall()
        previews: list[PreflightFilePreview] = []
        for row in preview_rows:
            likely_workspace = str(row["workspace"] or "").strip()
            stage_checkpoint = row["stage_checkpoint"]
            if not likely_workspace and isinstance(stage_checkpoint, str) and stage_checkpoint.strip():
                try:
                    payload = json.loads(stage_checkpoint)
                except json.JSONDecodeError:
                    payload = {}
                if isinstance(payload, dict):
                    likely_workspace = str(payload.get("workspace") or "").strip()
            previews.append(
                PreflightFilePreview(
                    file_name=str(row["file_name"]),
                    likely_workspace=likely_workspace or "unassigned",
                    next_stage=str(row["next_stage"] or "classified"),
                    review_required=bool(row["review_required"]),
                )
            )

        profile_label = "AnythingLLM" if self._export_profile == "anythingllm" else "Open WebUI"
        workspace_counts_human = ", ".join(
            f"{count} to {workspace}" for workspace, count in classification_preview["by_workspace"][:2]
        ) or "0 assigned"
        wiki_count = int(classification_preview["wiki_count"])
        wiki_share = float(classification_preview["wiki_share"])
        cap = float(cfg.preflight_wiki_share_cap)
        wiki_share_cap_exceeded = wiki_share > cap
        human_summary = (
            f"Out of {classification_preview['total']} files, {workspace_counts_human}, and "
            f"{classification_preview['review_required']} require review. "
            f"If you click Run, pending items will be processed for {profile_label}."
        )
        if wiki_share_cap_exceeded:
            human_summary = (
                f"{human_summary} WARNING: predicted wiki share is {wiki_share:.0%}, "
                f"above cap {cap:.0%}. Run should be reviewed before starting."
            )
        return PreflightSummary(
            total_files=total_files,
            pending_files=pending_files,
            processed_files=processed_files,
            failed_files=failed_files,
            pending_in_raw_folder=pending_in_raw_folder,
            pending_outside_raw_folder=pending_outside_raw_folder,
            active_export_profile=self._export_profile,
            output_root=self._output_folder / "exports" / self._export_profile,
            normalized_root=self._output_folder / "normalized",
            ollama_enabled=cfg.enable_ollama,
            ai_mode=cfg.ai_mode,
            auto_assign_workspace=cfg.auto_assign_workspace,
            estimated_review_count=estimated_review_count,
            classification_total_files=classification_preview["total"],
            classification_by_workspace=tuple(classification_preview["by_workspace"]),
            classification_review_required=classification_preview["review_required"],
            classification_ai_count=classification_preview["ai_count"],
            classification_rules_count=classification_preview["rules_count"],
            classification_relevance_gate_count=classification_preview["relevance_gate_count"],
            classification_small_file_lane_count=classification_preview["small_file_lane_count"],
            classification_wiki_count=wiki_count,
            classification_wiki_share=wiki_share,
            preflight_wiki_share_cap=cap,
            wiki_share_cap_exceeded=wiki_share_cap_exceeded,
            classification_sample=tuple(classification_preview["sample"]),
            previews=tuple(previews),
            human_summary=human_summary,
        )

    def pending_batch_overview(self) -> PendingBatchOverview:
        """Return pending counts split by current raw folder and the next pending batch root."""
        if self._db_path is None or self._raw_folder is None:
            return PendingBatchOverview(current_pending=0, other_pending=0, next_batch_folder=None)
        status_col, next_stage_col = _profile_queue_columns(self._export_profile)
        raw_prefix = self._raw_path_prefix()
        conn = Database(self._db_path).connect()
        pending_values = (
            RunnerStatus.NEW.value,
            RunnerStatus.PROCESSING.value,
            RunnerStatus.FAILED.value,
        )
        current_pending = int(
            conn.execute(
                f"""
                SELECT COUNT(*)
                FROM files
                WHERE {status_col} IN (?, ?, ?)
                  AND {next_stage_col} IS NOT NULL
                  AND path LIKE ?
                """,
                (*pending_values, f"{raw_prefix}%"),
            ).fetchone()[0]
            or 0
        )
        outside_rows = conn.execute(
            f"""
            SELECT path
            FROM files
            WHERE {status_col} IN (?, ?, ?)
              AND {next_stage_col} IS NOT NULL
              AND path NOT LIKE ?
            """,
            (*pending_values, f"{raw_prefix}%"),
        ).fetchall()
        other_pending = len(outside_rows)
        batch_roots: set[Path] = set()
        for row in outside_rows:
            raw_path = str(row["path"])
            if not raw_path.strip():
                continue
            batch_roots.add(self._batch_root_for_path(Path(raw_path)))
        next_batch_folder = self._select_next_batch_folder(batch_roots)
        return PendingBatchOverview(
            current_pending=current_pending,
            other_pending=other_pending,
            next_batch_folder=next_batch_folder,
        )

    def _build_classification_preview(
        self,
        *,
        db_path: Path,
        export_profile: str,
        config,
        sample_limit: int,
    ) -> dict[str, object]:
        """Classify pending files in-memory only (no DB writes, no exports)."""
        db = Database(db_path)
        repo = FileRepository(db)
        pending = repo.list_for_runner(limit=100000, export_profile=export_profile)
        svc = ClassificationService(config)
        by_workspace: dict[str, int] = {}
        review_required = 0
        ai_count = 0
        rules_count = 0
        relevance_gate_count = 0
        small_file_lane_count = 0
        sample: list[ClassificationPreviewRow] = []

        for rec in pending:
            decision = svc.classify(rec)
            uses_ai = self._would_use_ai(config=config, matched_by=decision.matched_by)
            if uses_ai:
                ai_count += 1
            else:
                rules_count += 1
            ws = (decision.workspace or "").strip() or "unassigned"
            by_workspace[ws] = by_workspace.get(ws, 0) + 1
            if decision.review_required:
                review_required += 1
            reason_l = decision.classification_reason.lower()
            if reason_l.startswith("relevance gate:"):
                relevance_gate_count += 1
            if reason_l.startswith("small-file lane:"):
                small_file_lane_count += 1
            if len(sample) < sample_limit:
                sample.append(
                    ClassificationPreviewRow(
                        file_name=rec.filename or Path(rec.path).name,
                        predicted_workspace=ws,
                        confidence=float(decision.confidence),
                        matched_by=decision.matched_by,
                    )
                )

        ordered = sorted(by_workspace.items(), key=lambda item: (-item[1], item[0]))
        wiki_count = int(by_workspace.get("wiki", 0))
        total = len(pending)
        wiki_share = (float(wiki_count) / float(total)) if total else 0.0
        return {
            "total": total,
            "by_workspace": ordered,
            "review_required": review_required,
            "ai_count": ai_count,
            "rules_count": rules_count,
            "relevance_gate_count": relevance_gate_count,
            "small_file_lane_count": small_file_lane_count,
            "wiki_count": wiki_count,
            "wiki_share": round(wiki_share, 4),
            "sample": tuple(sample),
        }

    @staticmethod
    def _would_use_ai(*, config, matched_by: str) -> bool:
        if not config.enable_ollama:
            return False
        if config.ai_mode == "rules_only":
            return False
        if matched_by in (MATCH_FORCE_RULE, MATCH_NEGATIVE_RULE):
            return False
        if config.ai_mode == "ai_only_unclassified":
            return matched_by == MATCH_FALLBACK
        return True

    def _worker(self, *, scan_first: bool) -> None:
        assert self._db_path is not None
        assert self._raw_folder is not None
        assert self._output_folder is not None
        self._running.set()
        self._final_state = "running"
        run_id = self._run_id
        files_started = 0
        files_finished_ok = 0
        files_marked_failed = 0
        db: Database | None = None
        try:
            db = Database(self._db_path)
            db.connect()
            if scan_first:
                scan = ScanService(db)
                self._enqueue_log(f"Scanning: {self._raw_folder}")
                scan_result = scan.scan(self._raw_folder)
                self._enqueue_log(
                    f"Scan matched={scan_result.files_matched}, upserted={scan_result.files_upserted}, "
                    f"errors={len(scan_result.errors)}"
                )

            while not self._stop.is_set():
                if self._pause.is_set():
                    self._stop.wait(0.1)
                    continue
                config = load_classification_config(self._output_folder / ".kiw" / DEFAULT_CONFIG_FILENAME)
                runner = PipelineRunner(
                    db,
                    normalized_work_dir=self._output_folder / "normalized",
                    export_root=self._output_folder / "exports",
                    export_profile=self._export_profile,
                    chunk_target_words=config.chunk_target_size,
                    min_chunk_words=config.minimum_chunk_size,
                )
                result = runner.run(max_files=1)
                files_started += int(result.files_started)
                files_finished_ok += int(result.files_finished_ok)
                files_marked_failed += int(result.files_marked_failed)
                self._enqueue_log(
                    f"Job #{result.job_id}: started={result.files_started}, "
                    f"ok={result.files_finished_ok}, failed={result.files_marked_failed}"
                )
                if result.files_started == 0:
                    self._final_state = "completed"
                    self._enqueue_log("Run completed.")
                    break
        except Exception as exc:  # noqa: BLE001
            self._final_state = "failed"
            self._logger.exception("run monitor worker failed")
            self._enqueue_log(f"Run failed: {type(exc).__name__}: {exc}")
        finally:
            self._last_completed_run = CompletedRunSummary(
                run_id=run_id,
                export_profile=self._export_profile,
                final_state=self._final_state,
                files_started=files_started,
                files_finished_ok=files_finished_ok,
                files_marked_failed=files_marked_failed,
            )
            if db is not None:
                db.close()
            self._running.clear()
            self._stop.clear()
            self._pause.clear()
            self._thread = None
            self._logger.info("worker cleanup complete", extra={"final_state": self._final_state})
            self._enqueue_log("Thread/worker cleanup complete.")

    def _enqueue_log(self, message: str) -> None:
        self._log_queue.put(message)
        self._logger.info(message)

    def _raw_path_prefix(self) -> str:
        if self._raw_folder is None:
            raise RuntimeError("Run monitor is not configured. Create or load a project first.")
        raw_root = str(self._raw_folder.resolve())
        if raw_root.endswith(("\\", "/")):
            return raw_root
        return f"{raw_root}{os.sep}"

    @staticmethod
    def _batch_root_for_path(path: Path) -> Path:
        parts = list(path.parts)
        lower = [p.lower() for p in parts]
        if "source_batches" in lower:
            idx = lower.index("source_batches")
            if idx + 1 < len(parts):
                return Path(*parts[: idx + 2]).resolve()
        return path.parent.resolve()

    @staticmethod
    def _select_next_batch_folder(candidates: set[Path]) -> Path | None:
        if not candidates:
            return None
        ordered = sorted(candidates, key=RunMonitorService._batch_sort_key)
        return ordered[0]

    @staticmethod
    def _batch_sort_key(path: Path) -> tuple[int, str, str]:
        name = path.name.lower()
        match = re.fullmatch(r"batch_(\d+)", name)
        if match:
            return (0, f"{int(match.group(1)):09d}", str(path).lower())
        return (1, name, str(path).lower())

    def _drain_stale_logs(self) -> None:
        while True:
            try:
                self._log_queue.get_nowait()
            except Empty:
                return

    def get_last_completed_run(self) -> CompletedRunSummary | None:
        return self._last_completed_run
