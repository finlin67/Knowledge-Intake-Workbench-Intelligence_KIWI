"""Persistence for ``jobs``."""

from __future__ import annotations

import sqlite3
from collections.abc import Sequence

from db.session import Database
from models.enums import JobStatus
from models.job_record import JobRecord


class JobRepository:
    """Create and update batch / worker jobs."""

    __slots__ = ("_db",)

    def __init__(self, database: Database) -> None:
        self._db = database

    def get_by_id(self, job_id: int) -> JobRecord | None:
        conn = self._db.connect()
        row = conn.execute(
            """
            SELECT id, kind, status, priority, payload_json, result_json,
                   created_at, started_at, completed_at, error_message
            FROM jobs WHERE id = ?
            """,
            (job_id,),
        ).fetchone()
        return JobRecord.from_row(row) if row is not None else None

    def create(
        self,
        *,
        kind: str,
        status: str = JobStatus.PENDING.value,
        priority: int = 0,
        payload_json: str | None = None,
    ) -> JobRecord:
        conn = self._db.connect()
        cur = conn.execute(
            """
            INSERT INTO jobs (kind, status, priority, payload_json)
            VALUES (?, ?, ?, ?)
            """,
            (kind, status, priority, payload_json),
        )
        new_id = cur.lastrowid
        conn.commit()
        row = conn.execute(
            """
            SELECT id, kind, status, priority, payload_json, result_json,
                   created_at, started_at, completed_at, error_message
            FROM jobs WHERE id = ?
            """,
            (new_id,),
        ).fetchone()
        if row is None:
            raise sqlite3.DatabaseError("Insert did not persist a row")
        return JobRecord.from_row(row)

    def list_by_status(self, status: str, *, limit: int = 100) -> Sequence[JobRecord]:
        conn = self._db.connect()
        rows = conn.execute(
            """
            SELECT id, kind, status, priority, payload_json, result_json,
                   created_at, started_at, completed_at, error_message
            FROM jobs
            WHERE status = ?
            ORDER BY priority DESC, id ASC
            LIMIT ?
            """,
            (status, limit),
        ).fetchall()
        return tuple(JobRecord.from_row(r) for r in rows)

    def update_status(
        self,
        job_id: int,
        *,
        status: str,
        error_message: str | None = None,
        result_json: str | None = None,
        mark_started: bool = False,
        mark_completed: bool = False,
    ) -> None:
        """Update job lifecycle fields; timestamps set when flags are True."""
        conn = self._db.connect()
        fragments = ["status = ?", "error_message = ?"]
        params: list[object] = [status, error_message]
        if result_json is not None:
            fragments.append("result_json = ?")
            params.append(result_json)
        if mark_started:
            fragments.append("started_at = datetime('now')")
        if mark_completed:
            fragments.append("completed_at = datetime('now')")
        params.append(job_id)
        sql = f"UPDATE jobs SET {', '.join(fragments)} WHERE id = ?"
        conn.execute(sql, params)
        conn.commit()
