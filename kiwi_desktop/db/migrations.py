"""Lightweight additive migrations for existing SQLite databases."""

from __future__ import annotations

import sqlite3


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return {str(r[1]) for r in rows}


def migrate_files_table(conn: sqlite3.Connection) -> None:
    """Add scanner-related columns to ``files`` when missing (idempotent)."""
    cols = _columns(conn, "files")
    statements: list[str] = []
    if "filename" not in cols:
        statements.append("ALTER TABLE files ADD COLUMN filename TEXT")
    if "extension" not in cols:
        statements.append("ALTER TABLE files ADD COLUMN extension TEXT")
    if "file_created_at" not in cols:
        statements.append("ALTER TABLE files ADD COLUMN file_created_at TEXT")
    if "file_modified_at" not in cols:
        statements.append("ALTER TABLE files ADD COLUMN file_modified_at TEXT")
    if "runner_status" not in cols:
        statements.append("ALTER TABLE files ADD COLUMN runner_status TEXT DEFAULT 'new'")
    if "pipeline_next_stage" not in cols:
        statements.append("ALTER TABLE files ADD COLUMN pipeline_next_stage TEXT DEFAULT 'classified'")
    if "runner_status_anythingllm" not in cols:
        statements.append("ALTER TABLE files ADD COLUMN runner_status_anythingllm TEXT DEFAULT 'new'")
    if "pipeline_next_stage_anythingllm" not in cols:
        statements.append("ALTER TABLE files ADD COLUMN pipeline_next_stage_anythingllm TEXT DEFAULT 'classified'")
    if "runner_status_open_webui" not in cols:
        statements.append("ALTER TABLE files ADD COLUMN runner_status_open_webui TEXT DEFAULT 'new'")
    if "pipeline_next_stage_open_webui" not in cols:
        statements.append("ALTER TABLE files ADD COLUMN pipeline_next_stage_open_webui TEXT DEFAULT 'classified'")
    if "workspace" not in cols:
        statements.append("ALTER TABLE files ADD COLUMN workspace TEXT DEFAULT ''")
    if "subfolder" not in cols:
        statements.append("ALTER TABLE files ADD COLUMN subfolder TEXT")
    if "matched_by" not in cols:
        statements.append("ALTER TABLE files ADD COLUMN matched_by TEXT")
    if "classification_reason" not in cols:
        statements.append("ALTER TABLE files ADD COLUMN classification_reason TEXT")
    if "review_required" not in cols:
        statements.append("ALTER TABLE files ADD COLUMN review_required INTEGER NOT NULL DEFAULT 0")
    if "ai_used" not in cols:
        statements.append("ALTER TABLE files ADD COLUMN ai_used INTEGER NOT NULL DEFAULT 0")
    if "content_hash" not in cols:
        statements.append("ALTER TABLE files ADD COLUMN content_hash TEXT")
    if "confidence" not in cols:
        statements.append("ALTER TABLE files ADD COLUMN confidence REAL")
    if "case_study_candidate" not in cols:
        statements.append("ALTER TABLE files ADD COLUMN case_study_candidate INTEGER NOT NULL DEFAULT 0")
    if "portfolio_candidate" not in cols:
        statements.append("ALTER TABLE files ADD COLUMN portfolio_candidate INTEGER NOT NULL DEFAULT 0")
    for sql in statements:
        conn.execute(sql)

    conn.execute(
        "UPDATE files SET runner_status = 'new' WHERE runner_status IS NULL OR TRIM(runner_status) = ''"
    )
    conn.execute(
        """
        UPDATE files
        SET pipeline_next_stage = 'classified'
        WHERE pipeline_next_stage IS NULL AND IFNULL(runner_status, '') != 'completed'
        """
    )
    conn.execute(
        "UPDATE files SET review_required = 0 WHERE review_required IS NULL"
    )
    conn.execute("UPDATE files SET ai_used = 0 WHERE ai_used IS NULL")
    conn.execute(
        """
        UPDATE files
        SET runner_status_anythingllm = COALESCE(NULLIF(TRIM(runner_status_anythingllm), ''), runner_status, 'new')
        """
    )
    conn.execute(
        """
        UPDATE files
        SET runner_status_open_webui = COALESCE(NULLIF(TRIM(runner_status_open_webui), ''), runner_status, 'new')
        """
    )
    conn.execute(
        """
        UPDATE files
        SET pipeline_next_stage_anythingllm = COALESCE(
            pipeline_next_stage_anythingllm,
            CASE
                WHEN runner_status_anythingllm = 'completed' THEN NULL
                ELSE COALESCE(pipeline_next_stage, 'classified')
            END
        )
        """
    )
    conn.execute(
        """
        UPDATE files
        SET pipeline_next_stage_open_webui = COALESCE(
            pipeline_next_stage_open_webui,
            CASE
                WHEN runner_status_open_webui = 'completed' THEN NULL
                ELSE COALESCE(pipeline_next_stage, 'classified')
            END
        )
        """
    )
