"""Tests for files table classification columns and repository updates."""

from __future__ import annotations

from pathlib import Path

from db.repositories import FileRepository
from db.session import Database


def test_files_table_has_classification_columns(tmp_path: Path) -> None:
    db_path = tmp_path / "state.sqlite3"
    db = Database(db_path)
    conn = db.connect()
    cols = {str(r[1]) for r in conn.execute("PRAGMA table_info(files)").fetchall()}
    assert "workspace" in cols
    assert "subfolder" in cols
    assert "matched_by" in cols
    assert "classification_reason" in cols
    assert "review_required" in cols
    assert "ai_used" in cols
    assert "content_hash" in cols
    assert "confidence" in cols
    assert "case_study_candidate" in cols
    assert "portfolio_candidate" in cols


def test_classification_updates_round_trip(tmp_path: Path) -> None:
    db_path = tmp_path / "state.sqlite3"
    db = Database(db_path)
    db.connect()
    repo = FileRepository(db)
    p = (tmp_path / "doc.md").resolve()
    p.write_text("x", encoding="utf-8")
    rec = repo.insert(path=str(p), display_name="doc.md")
    assert rec.subfolder is None
    assert rec.matched_by is None
    assert rec.classification_reason is None
    assert rec.review_required is False
    assert rec.ai_used is False
    assert rec.content_hash is None

    repo.update_classification_fields(
        rec.id,
        {
            "workspace": "wiki",
            "subfolder": "notes",
            "matched_by": "force_rule",
            "classification_reason": "path match",
            "content_hash": "abc123",
            "confidence": 0.96,
            "case_study_candidate": True,
            "portfolio_candidate": True,
        },
    )
    repo.set_review_required(rec.id, True)
    repo.set_ai_used(rec.id, True)

    again = repo.get_by_id(rec.id)
    assert again is not None
    assert again.workspace == "wiki"
    assert again.subfolder == "notes"
    assert again.matched_by == "force_rule"
    assert again.classification_reason == "path match"
    assert again.content_hash == "abc123"
    assert again.confidence == 0.96
    assert again.case_study_candidate is True
    assert again.portfolio_candidate is True
    assert again.review_required is True
    assert again.ai_used is True

    repo.set_review_required(rec.id, False)
    repo.set_ai_used(rec.id, False)
    cleared = repo.get_by_id(rec.id)
    assert cleared is not None
    assert cleared.review_required is False
    assert cleared.ai_used is False


def test_migrate_files_table_idempotent(tmp_path: Path) -> None:
    """Second migration pass should not fail on already-migrated DB."""
    from db import migrations

    db_path = tmp_path / "state.sqlite3"
    db = Database(db_path)
    conn = db.connect()
    migrations.migrate_files_table(conn)
    migrations.migrate_files_table(conn)
    conn.commit()
