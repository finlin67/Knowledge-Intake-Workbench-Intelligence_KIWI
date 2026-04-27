"""Review workflows: failed files, duplicates, retry, and category overrides."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from db.repositories import FileRepository
from db.session import Database
from models.enums import RunnerStatus

WORKSPACE_OPTIONS: tuple[str, ...] = (
    "career_portfolio",
    "ai_projects",
    "archive",
    "case_studies",
    "wiki",
    "unassigned",
)

CATEGORY_OPTIONS: tuple[str, ...] = (
    "portfolio",
    "ai_project",
    "archive",
    "case_studies",
    "other",
    "default",
)

_WORKSPACE_BY_CATEGORY: dict[str, str] = {
    "portfolio": "career_portfolio",
    "ai_project": "ai_projects",
    "archive": "archive",
    "case_studies": "case_studies",
    "markdown": "wiki",
}


@dataclass(frozen=True, slots=True)
class FailedFileRow:
    file_id: int
    file_name: str
    status: str
    error: str


@dataclass(frozen=True, slots=True)
class DuplicateGroup:
    sha256: str
    file_ids: tuple[int, ...]
    file_names: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ReviewRequiredRow:
    file_id: int
    file_name: str
    category: str
    confidence: float
    matched_by: str
    reason: str


@dataclass(frozen=True, slots=True)
class AuditQueueRow:
    file_id: int
    file_name: str
    status: str
    workspace: str
    subfolder: str
    confidence: float
    matched_by: str
    review_required: bool
    reason: str


@dataclass(frozen=True, slots=True)
class AuditQueueSummary:
    by_matched_by: tuple[tuple[str, int], ...]
    by_workspace: tuple[tuple[str, int], ...]
    unresolved_count: int
    common_tokens: tuple[tuple[str, int], ...]


@dataclass(frozen=True, slots=True)
class AuditQueueData:
    review_required: tuple[AuditQueueRow, ...]
    fallback: tuple[AuditQueueRow, ...]
    failed: tuple[AuditQueueRow, ...]
    low_confidence: tuple[AuditQueueRow, ...]
    summary: AuditQueueSummary


class ReviewService:
    __slots__ = ()

    def list_failed_files(self, *, db_path: Path, limit: int = 500) -> tuple[FailedFileRow, ...]:
        db = Database(db_path)
        files = FileRepository(db).list_recent(limit=limit)
        out: list[FailedFileRow] = []
        for f in files:
            if f.runner_status != RunnerStatus.FAILED.value:
                continue
            out.append(
                FailedFileRow(
                    file_id=f.id,
                    file_name=f.filename or Path(f.path).name,
                    status=f.runner_status,
                    error=f.last_error or "",
                )
            )
        return tuple(out)

    def list_exact_sha_duplicates(self, *, db_path: Path) -> tuple[DuplicateGroup, ...]:
        db = Database(db_path)
        conn = db.connect()
        groups = conn.execute(
            """
            SELECT sha256
            FROM files
            WHERE sha256 IS NOT NULL AND TRIM(sha256) != ''
            GROUP BY sha256
            HAVING COUNT(*) > 1
            ORDER BY COUNT(*) DESC, sha256 ASC
            """
        ).fetchall()
        out: list[DuplicateGroup] = []
        for g in groups:
            sha = str(g["sha256"])
            rows = conn.execute(
                """
                SELECT id, COALESCE(filename, path) AS file_name
                FROM files
                WHERE sha256 = ?
                ORDER BY id ASC
                """,
                (sha,),
            ).fetchall()
            out.append(
                DuplicateGroup(
                    sha256=sha,
                    file_ids=tuple(int(r["id"]) for r in rows),
                    file_names=tuple(str(r["file_name"]) for r in rows),
                )
            )
        return tuple(out)

    def list_review_required_files(self, *, db_path: Path, limit: int = 500) -> tuple[ReviewRequiredRow, ...]:
        db = Database(db_path)
        files = FileRepository(db).list_recent(limit=limit)
        out: list[ReviewRequiredRow] = []
        for f in files:
            payload = _checkpoint_payload(f.stage_checkpoint)
            needs_review = f.review_required or bool(payload.get("review_required", False))
            if not needs_review:
                continue
            confidence_num = _confidence_from_file_record(f, payload)
            out.append(
                ReviewRequiredRow(
                    file_id=f.id,
                    file_name=f.filename or Path(f.path).name,
                    category=str(payload.get("category") or "unknown"),
                    confidence=confidence_num,
                    matched_by=str(f.matched_by or payload.get("matched_by") or ""),
                    reason=str(f.classification_reason or payload.get("classification_reason") or ""),
                )
            )
        return tuple(out)

    def get_audit_queue(
        self,
        *,
        db_path: Path,
        limit: int = 1500,
        low_confidence_threshold: float = 0.65,
    ) -> AuditQueueData:
        db = Database(db_path)
        files = FileRepository(db).list_recent(limit=limit)
        review_required_rows: list[AuditQueueRow] = []
        fallback_rows: list[AuditQueueRow] = []
        failed_rows: list[AuditQueueRow] = []
        low_conf_rows: list[AuditQueueRow] = []
        unresolved_count = 0
        matched_counts: dict[str, int] = {}
        workspace_counts: dict[str, int] = {}
        token_counts: dict[str, int] = {}

        for f in files:
            payload = _checkpoint_payload(f.stage_checkpoint)
            confidence_num = _confidence_from_file_record(f, payload)
            matched_by = str(f.matched_by or payload.get("matched_by") or "").strip()
            reason = str(f.classification_reason or payload.get("classification_reason") or "").strip()
            review_required = bool(f.review_required or payload.get("review_required", False))
            row = AuditQueueRow(
                file_id=f.id,
                file_name=f.filename or Path(f.path).name,
                status=f.runner_status,
                workspace=(f.workspace or "").strip() or "unassigned",
                subfolder=str(f.subfolder or payload.get("subfolder") or "").strip(),
                confidence=confidence_num,
                matched_by=matched_by,
                review_required=review_required,
                reason=reason,
            )
            is_failed = f.runner_status == RunnerStatus.FAILED.value
            is_fallback = matched_by == "fallback"
            is_low_conf = confidence_num < low_confidence_threshold
            if review_required:
                review_required_rows.append(row)
            if is_fallback:
                fallback_rows.append(row)
            if is_failed:
                failed_rows.append(row)
            if is_low_conf:
                low_conf_rows.append(row)

            if review_required or is_fallback or is_failed or is_low_conf:
                unresolved_count += 1
                matched_key = matched_by or "(unknown)"
                matched_counts[matched_key] = matched_counts.get(matched_key, 0) + 1
                workspace_counts[row.workspace] = workspace_counts.get(row.workspace, 0) + 1

            if is_fallback:
                for token in _filename_tokens(row.file_name):
                    token_counts[token] = token_counts.get(token, 0) + 1

        return AuditQueueData(
            review_required=tuple(review_required_rows),
            fallback=tuple(fallback_rows),
            failed=tuple(failed_rows),
            low_confidence=tuple(low_conf_rows),
            summary=AuditQueueSummary(
                by_matched_by=_sorted_counts(matched_counts),
                by_workspace=_sorted_counts(workspace_counts),
                unresolved_count=unresolved_count,
                common_tokens=_sorted_counts(token_counts, limit=25),
            ),
        )

    def retry_failed_files(self, *, db_path: Path, file_ids: tuple[int, ...]) -> int:
        if not file_ids:
            return 0
        db = Database(db_path)
        conn = db.connect()
        q = ",".join("?" for _ in file_ids)
        cur = conn.execute(
            f"""
            UPDATE files
            SET runner_status = ?, last_error = NULL, updated_at = datetime('now')
            WHERE id IN ({q}) AND runner_status = ?
            """,
            (RunnerStatus.NEW.value, *file_ids, RunnerStatus.FAILED.value),
        )
        conn.commit()
        return int(cur.rowcount or 0)

    def mark_reviewed(self, *, db_path: Path, file_ids: tuple[int, ...]) -> int:
        if not file_ids:
            return 0
        db = Database(db_path)
        repo = FileRepository(db)
        updated = 0
        for file_id in file_ids:
            rec = repo.get_by_id(file_id)
            if rec is None:
                continue
            payload = _checkpoint_payload(rec.stage_checkpoint)
            payload["review_required"] = False
            repo.update_stage_checkpoint(file_id, json.dumps(payload, ensure_ascii=False))
            repo.set_review_required(file_id, False)
            updated += 1
        return updated

    def override_category(self, *, db_path: Path, file_id: int, category: str) -> None:
        c = category.strip()
        if not c:
            raise ValueError("Category cannot be empty.")
        db = Database(db_path)
        repo = FileRepository(db)
        rec = repo.get_by_id(file_id)
        if rec is None:
            raise ValueError(f"File id not found: {file_id}")
        payload: dict[str, object] = {}
        if rec.stage_checkpoint:
            try:
                raw = json.loads(rec.stage_checkpoint)
                if isinstance(raw, dict):
                    payload = dict(raw)
            except json.JSONDecodeError:
                payload = {}
        payload["category"] = c
        repo.update_stage_checkpoint(file_id, json.dumps(payload, ensure_ascii=False))

    def override_workspace(self, *, db_path: Path, file_id: int, workspace: str) -> None:
        ws = workspace.strip()
        if ws not in WORKSPACE_OPTIONS:
            raise ValueError(f"Invalid workspace: {workspace!r}")
        db = Database(db_path)
        repo = FileRepository(db)
        rec = repo.get_by_id(file_id)
        if rec is None:
            raise ValueError(f"File id not found: {file_id}")
        payload: dict[str, object] = {}
        if rec.stage_checkpoint:
            try:
                raw = json.loads(rec.stage_checkpoint)
                if isinstance(raw, dict):
                    payload = dict(raw)
            except json.JSONDecodeError:
                payload = {}
        payload["workspace"] = ws
        repo.update_stage_checkpoint(file_id, json.dumps(payload, ensure_ascii=False))
        repo.set_workspace(file_id, ws)

    def override_subfolder(self, *, db_path: Path, file_id: int, subfolder: str) -> None:
        normalized = subfolder.strip()
        db = Database(db_path)
        repo = FileRepository(db)
        rec = repo.get_by_id(file_id)
        if rec is None:
            raise ValueError(f"File id not found: {file_id}")
        payload: dict[str, object] = {}
        if rec.stage_checkpoint:
            try:
                raw = json.loads(rec.stage_checkpoint)
                if isinstance(raw, dict):
                    payload = dict(raw)
            except json.JSONDecodeError:
                payload = {}
        if normalized:
            payload["subfolder"] = normalized
        else:
            payload.pop("subfolder", None)
        repo.update_classification_fields(file_id, {"subfolder": normalized or None})
        repo.update_stage_checkpoint(file_id, json.dumps(payload, ensure_ascii=False))

    def apply_category_workspace(
        self,
        *,
        db_path: Path,
        file_ids: tuple[int, ...],
        category: str,
        workspace: str,
    ) -> int:
        if not file_ids:
            return 0
        cat = category.strip()
        if cat not in CATEGORY_OPTIONS:
            raise ValueError(f"Invalid category: {category!r}")
        if workspace not in WORKSPACE_OPTIONS:
            raise ValueError(f"Invalid workspace: {workspace!r}")
        for file_id in file_ids:
            self.override_category(db_path=db_path, file_id=file_id, category=cat)
            self.override_workspace(db_path=db_path, file_id=file_id, workspace=workspace)
        return len(file_ids)

    def auto_assign_workspaces(self, *, db_path: Path, file_ids: tuple[int, ...]) -> int:
        if not file_ids:
            return 0
        db = Database(db_path)
        repo = FileRepository(db)
        updated = 0
        for file_id in file_ids:
            rec = repo.get_by_id(file_id)
            if rec is None:
                continue
            category = "default"
            if rec.stage_checkpoint:
                try:
                    payload = json.loads(rec.stage_checkpoint)
                    if isinstance(payload, dict):
                        c = payload.get("category")
                        if isinstance(c, str) and c.strip():
                            category = c.strip()
                except json.JSONDecodeError:
                    pass
            ws = _WORKSPACE_BY_CATEGORY.get(category, "unassigned")
            self.override_workspace(db_path=db_path, file_id=file_id, workspace=ws)
            updated += 1
        return updated


def _confidence_from_file_record(rec: object, payload: dict[str, object]) -> float:
    cf = getattr(rec, "confidence", None)
    if cf is not None:
        try:
            return float(cf)
        except (TypeError, ValueError):
            pass
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


def _sorted_counts(counter: dict[str, int], *, limit: int | None = None) -> tuple[tuple[str, int], ...]:
    ordered = sorted(counter.items(), key=lambda item: (-item[1], item[0]))
    if limit is not None:
        ordered = ordered[:limit]
    return tuple(ordered)


def _filename_tokens(name: str) -> tuple[str, ...]:
    base = Path(name).stem.lower()
    raw_tokens = re.split(r"[^a-z0-9]+", base)
    stop_words = {"and", "for", "from", "that", "this", "with", "file", "final", "draft", "copy"}
    tokens: list[str] = []
    for tok in raw_tokens:
        if len(tok) < 3 or tok.isdigit() or tok in stop_words:
            continue
        tokens.append(tok)
    return tuple(tokens)
