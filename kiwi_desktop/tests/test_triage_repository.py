"""Tests for triage list_unassigned repository query and derivation."""

from __future__ import annotations

from pathlib import Path

from db.repositories import FileRepository
from db.session import Database
from models.enums import RunnerStatus
from models.triage_derivation import UnassignedTriageRow, build_unassigned_triage_row, derive_reason


def test_list_unassigned_filters_workspace(tmp_path: Path) -> None:
    db_path = tmp_path / "p" / ".kiw" / "project.sqlite3"
    db_path.parent.mkdir(parents=True)
    db = Database(db_path)
    db.connect()
    files = FileRepository(db)

    a = files.insert(path=str((tmp_path / "a.md").resolve()), display_name="a.md")
    files.set_workspace(a.id, "career_portfolio")

    b = files.insert(path=str((tmp_path / "b.md").resolve()), display_name="b.md")
    files.set_workspace(b.id, "")

    c = files.insert(path=str((tmp_path / "c.md").resolve()), display_name="c.md")
    files.set_workspace(c.id, "unassigned")

    rows = files.list_unassigned()
    ids = {r.file_id for r in rows}
    assert a.id not in ids
    assert b.id in ids
    assert c.id in ids


def test_requeue_for_classification_updates(tmp_path: Path) -> None:
    db_path = tmp_path / "p" / ".kiw" / "project.sqlite3"
    db_path.parent.mkdir(parents=True)
    db = Database(db_path)
    db.connect()
    files = FileRepository(db)
    rec = files.insert(path=str((tmp_path / "x.md").resolve()), display_name="x.md")
    conn = db.connect()
    conn.execute(
        """
        UPDATE files SET runner_status = ?, runner_status_anythingllm = ?, pipeline_next_stage_anythingllm = ?
        WHERE id = ?
        """,
        (RunnerStatus.COMPLETED.value, RunnerStatus.COMPLETED.value, None, rec.id),
    )
    conn.commit()

    n = files.requeue_for_classification((rec.id,))
    assert n == 1
    again = files.get_by_id(rec.id)
    assert again is not None
    assert again.runner_status == RunnerStatus.NEW.value


def test_derive_reason_noise_before_ai() -> None:
    """Small files classify as noise even if filename hints AI."""
    from models.file_record import FileRecord

    rec = FileRecord(
        id=1,
        path="/x",
        filename="claude_notes.md",
        extension=".md",
        file_created_at=None,
        file_modified_at=None,
        display_name="claude_notes.md",
        size_bytes=100,
        sha256=None,
        mime_type=None,
        current_stage="pending",
        stage_checkpoint=None,
        pipeline_version=1,
        stage_attempt=0,
        last_error=None,
        runner_status="new",
        pipeline_next_stage="classified",
        workspace=None,
        subfolder=None,
        matched_by="pattern",
        classification_reason=None,
        review_required=False,
        ai_used=False,
        content_hash=None,
        confidence=0.9,
        case_study_candidate=False,
        portfolio_candidate=False,
        created_at=None,
        updated_at=None,
    )
    assert derive_reason(rec) == "noise"


def test_unassigned_triage_row_builds() -> None:
    from models.file_record import FileRecord

    rec = FileRecord(
        id=2,
        path="/y",
        filename="z.pdf.3.md",
        extension=".md",
        file_created_at=None,
        file_modified_at=None,
        display_name="z.pdf.3.md",
        size_bytes=2000,
        sha256=None,
        mime_type=None,
        current_stage="pending",
        stage_checkpoint=None,
        pipeline_version=1,
        stage_attempt=0,
        last_error=None,
        runner_status="new",
        pipeline_next_stage="classified",
        workspace=None,
        subfolder="notes",
        matched_by="fallback",
        classification_reason="keyword:acme",
        review_required=True,
        ai_used=False,
        content_hash=None,
        confidence=0.3,
        case_study_candidate=False,
        portfolio_candidate=False,
        created_at=None,
        updated_at=None,
    )
    row = build_unassigned_triage_row(rec)
    assert isinstance(row, UnassignedTriageRow)
    assert row.reason == "pdf_chunk"
    assert "notes" in row.signals
