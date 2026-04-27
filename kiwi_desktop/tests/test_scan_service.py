"""Tests for recursive file scanning."""

from __future__ import annotations

from pathlib import Path

from db.repositories import FileRepository
from db.session import Database
from models.enums import FileStage, RunnerStatus
from services.scan_service import ScanService, is_supported_path, sha256_file


def test_is_supported_path() -> None:
    assert is_supported_path(Path("x.MD")) is True
    assert is_supported_path(Path("a.markdown")) is True
    assert is_supported_path(Path("b.exe")) is False


def test_sha256_file_is_stable(tmp_path: Path) -> None:
    p = tmp_path / "hash-me.txt"
    p.write_text("alpha\nbeta\ngamma\n", encoding="utf-8")
    h1 = sha256_file(p)
    h2 = sha256_file(p)
    assert h1 == h2
    assert len(h1) == 64


def test_scan_indexes_supported_files(tmp_path: Path) -> None:
    (tmp_path / "a.md").write_text("# hi", encoding="utf-8")
    (tmp_path / "skip.bin").write_bytes(b"\x00")
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "b.json").write_text("{}", encoding="utf-8")

    db = Database(Path(":memory:"))
    db.connect()
    result = ScanService(db).scan(tmp_path)

    assert result.files_matched == 2
    assert result.files_upserted == 2
    assert result.errors == ()

    files = FileRepository(db)
    md_path = str((tmp_path / "a.md").resolve())
    row = files.get_by_path(md_path)
    assert row is not None
    assert row.filename == "a.md"
    assert row.extension == ".md"
    assert row.size_bytes == len("# hi".encode("utf-8"))
    assert row.sha256 is not None and len(row.sha256) == 64
    assert row.file_modified_at is not None
    assert row.runner_status == RunnerStatus.NEW.value
    assert row.pipeline_next_stage == "classified"


def test_scan_upsert_preserves_pipeline_stage(tmp_path: Path) -> None:
    md = tmp_path / "note.md"
    md.write_text("v1", encoding="utf-8")

    db = Database(Path(":memory:"))
    db.connect()
    files = FileRepository(db)
    ScanService(db).scan(tmp_path)

    rec = files.get_by_path(str(md.resolve()))
    assert rec is not None
    assert rec.current_stage == FileStage.PENDING.value

    ok = files.try_transition_stage(
        rec.id,
        expect_stage=FileStage.PENDING.value,
        new_stage=FileStage.HASHING.value,
    )
    assert ok is True

    md.write_text("v2-changed", encoding="utf-8")
    ScanService(db).scan(tmp_path)

    again = files.get_by_path(str(md.resolve()))
    assert again is not None
    assert again.current_stage == FileStage.HASHING.value
    assert again.sha256 != rec.sha256
    assert again.runner_status == RunnerStatus.NEW.value
    assert again.pipeline_next_stage == "classified"


def test_scan_returns_clear_error_for_missing_root(tmp_path: Path) -> None:
    db = Database(Path(":memory:"))
    db.connect()
    missing = tmp_path / "does-not-exist"
    result = ScanService(db).scan(missing)
    assert result.files_matched == 0
    assert result.files_upserted == 0
    assert result.errors
    assert "Not a directory" in result.errors[0]
