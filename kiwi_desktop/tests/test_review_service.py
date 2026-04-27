"""Tests for review workflows (failed, duplicates, retry, category override)."""

from __future__ import annotations

from pathlib import Path

from db.repositories import FileRepository
from db.session import Database
from models.enums import RunnerStatus
from services.review_service import ReviewService


def test_failed_retry_and_override(tmp_path: Path) -> None:
    db_path = tmp_path / "state.sqlite3"
    db = Database(db_path)
    db.connect()
    repo = FileRepository(db)
    f = repo.insert(path=str((tmp_path / "a.md").resolve()), display_name="a.md")
    repo.mark_runner_failed(f.id, "boom")

    svc = ReviewService()
    failed = svc.list_failed_files(db_path=db_path)
    assert failed and failed[0].file_id == f.id

    updated = svc.retry_failed_files(db_path=db_path, file_ids=(f.id,))
    assert updated == 1
    after = repo.get_by_id(f.id)
    assert after is not None
    assert after.runner_status == RunnerStatus.NEW.value
    assert after.last_error is None

    svc.override_category(db_path=db_path, file_id=f.id, category="manual-note")
    final = repo.get_by_id(f.id)
    assert final is not None
    assert final.stage_checkpoint is not None
    assert "manual-note" in final.stage_checkpoint


def test_exact_sha_duplicates(tmp_path: Path) -> None:
    db_path = tmp_path / "state.sqlite3"
    db = Database(db_path)
    db.connect()
    repo = FileRepository(db)
    repo.insert(path=str((tmp_path / "a.txt").resolve()), display_name="a.txt", sha256="abc")
    repo.insert(path=str((tmp_path / "b.txt").resolve()), display_name="b.txt", sha256="abc")
    repo.insert(path=str((tmp_path / "c.txt").resolve()), display_name="c.txt", sha256="xyz")

    groups = ReviewService().list_exact_sha_duplicates(db_path=db_path)
    assert len(groups) == 1
    assert groups[0].sha256 == "abc"
    assert len(groups[0].file_ids) == 2


def test_workspace_override_and_auto_assign(tmp_path: Path) -> None:
    db_path = tmp_path / "state.sqlite3"
    db = Database(db_path)
    db.connect()
    repo = FileRepository(db)
    f1 = repo.insert(path=str((tmp_path / "p.md").resolve()), display_name="p.md")
    f2 = repo.insert(path=str((tmp_path / "a.md").resolve()), display_name="a.md")
    svc = ReviewService()
    svc.override_category(db_path=db_path, file_id=f1.id, category="portfolio")
    svc.override_category(db_path=db_path, file_id=f2.id, category="ai_project")
    count = svc.auto_assign_workspaces(db_path=db_path, file_ids=(f1.id, f2.id))
    assert count == 2
    r1 = repo.get_by_id(f1.id)
    r2 = repo.get_by_id(f2.id)
    assert r1 is not None and r1.workspace == "career_portfolio"
    assert r2 is not None and r2.workspace == "ai_projects"

    svc.override_workspace(db_path=db_path, file_id=f2.id, workspace="archive")
    r2b = repo.get_by_id(f2.id)
    assert r2b is not None and r2b.workspace == "archive"


def test_review_required_listing(tmp_path: Path) -> None:
    db_path = tmp_path / "state.sqlite3"
    db = Database(db_path)
    db.connect()
    repo = FileRepository(db)
    r1 = repo.insert(path=str((tmp_path / "review.md").resolve()), display_name="review.md")
    r2 = repo.insert(path=str((tmp_path / "ok.md").resolve()), display_name="ok.md")
    repo.update_stage_checkpoint(
        r1.id,
        '{"category":"other","confidence":0.31,"matched_by":"fallback","classification_reason":"no match","review_required":true}',
    )
    repo.update_stage_checkpoint(
        r2.id,
        '{"category":"portfolio","confidence":0.92,"matched_by":"force_rule","classification_reason":"forced","review_required":false}',
    )
    rows = ReviewService().list_review_required_files(db_path=db_path)
    assert len(rows) == 1
    assert rows[0].file_id == r1.id
    assert rows[0].matched_by == "fallback"
    marked = ReviewService().mark_reviewed(db_path=db_path, file_ids=(r1.id,))
    assert marked == 1
    rows_after = ReviewService().list_review_required_files(db_path=db_path)
    assert len(rows_after) == 0


def test_audit_queue_groups_summary_and_tokens(tmp_path: Path) -> None:
    db_path = tmp_path / "state.sqlite3"
    db = Database(db_path)
    db.connect()
    repo = FileRepository(db)
    f1 = repo.insert(path=str((tmp_path / "acme-ml-notes.md").resolve()), display_name="acme-ml-notes.md")
    f2 = repo.insert(path=str((tmp_path / "acme-q4-summary.md").resolve()), display_name="acme-q4-summary.md")
    f3 = repo.insert(path=str((tmp_path / "normal-doc.md").resolve()), display_name="normal-doc.md")
    repo.update_stage_checkpoint(
        f1.id,
        '{"confidence":0.20,"matched_by":"fallback","classification_reason":"no match","review_required":true}',
    )
    repo.update_stage_checkpoint(
        f2.id,
        '{"confidence":0.61,"matched_by":"project_map","classification_reason":"mapped","review_required":false}',
    )
    repo.update_classification_fields(f1.id, {"matched_by": "fallback", "workspace": "wiki"})
    repo.update_classification_fields(f2.id, {"matched_by": "project_map", "workspace": "archive"})
    repo.mark_runner_failed(f2.id, "failed classify")
    repo.set_review_required(f1.id, True)
    repo.update_stage_checkpoint(
        f3.id,
        '{"confidence":0.95,"matched_by":"force_rule","classification_reason":"forced","review_required":false}',
    )
    repo.update_classification_fields(f3.id, {"matched_by": "force_rule", "workspace": "wiki"})

    data = ReviewService().get_audit_queue(db_path=db_path, low_confidence_threshold=0.65)
    assert len(data.review_required) == 1
    assert data.review_required[0].file_id == f1.id
    assert len(data.fallback) == 1
    assert data.fallback[0].file_id == f1.id
    assert len(data.failed) == 1
    assert data.failed[0].file_id == f2.id
    assert len(data.low_confidence) == 2
    assert data.summary.unresolved_count == 2
    assert ("fallback", 1) in data.summary.by_matched_by
    assert ("project_map", 1) in data.summary.by_matched_by
    token_keys = {token for token, _count in data.summary.common_tokens}
    assert "acme" in token_keys
