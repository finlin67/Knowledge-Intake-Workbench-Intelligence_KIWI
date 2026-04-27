"""Tests for SQLite repositories."""

from __future__ import annotations

from pathlib import Path

import pytest

from db.repositories import FileRepository, JobRepository
from db.session import Database
from models.enums import FileStage, JobKind, JobStatus


@pytest.fixture
def db() -> Database:
    d = Database(Path(":memory:"))
    d.connect()
    return d


def test_file_stage_transition(db: Database) -> None:
    files = FileRepository(db)
    f = files.insert(path="/data/a.txt", current_stage=FileStage.PENDING.value)
    assert f.current_stage == FileStage.PENDING.value

    ok = files.try_transition_stage(
        f.id,
        expect_stage=FileStage.PENDING.value,
        new_stage=FileStage.HASHING.value,
        checkpoint='{"cursor": 0}',
    )
    assert ok is True
    loaded = files.get_by_id(f.id)
    assert loaded is not None
    assert loaded.current_stage == FileStage.HASHING.value
    assert loaded.stage_checkpoint == '{"cursor": 0}'

    ok2 = files.try_transition_stage(
        f.id,
        expect_stage=FileStage.PENDING.value,
        new_stage=FileStage.COMPLETED.value,
    )
    assert ok2 is False


def test_job_lifecycle(db: Database) -> None:
    jobs = JobRepository(db)
    j = jobs.create(kind=JobKind.SCAN.value, payload_json='{"root": "/"}')
    assert j.status == JobStatus.PENDING.value

    jobs.update_status(
        j.id,
        status=JobStatus.RUNNING.value,
        mark_started=True,
    )
    loaded = jobs.get_by_id(j.id)
    assert loaded is not None
    assert loaded.status == JobStatus.RUNNING.value
    assert loaded.started_at is not None

    jobs.update_status(
        j.id,
        status=JobStatus.COMPLETED.value,
        result_json='{"count": 3}',
        mark_completed=True,
    )
    done = jobs.get_by_id(j.id)
    assert done is not None
    assert done.status == JobStatus.COMPLETED.value
    assert done.completed_at is not None
