"""Tests for GUI-supporting services (project + inventory)."""

from __future__ import annotations

from pathlib import Path

from db.repositories import FileRepository
from db.session import Database
from services.inventory_filter import FILTER_REVIEW_REQUIRED, FILTER_WORKSPACE
from services.inventory_service import InventoryService
from services.project_service import ProjectService


def test_project_create_and_load(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    out = tmp_path / "out"
    raw.mkdir()
    svc = ProjectService()
    created = svc.create_project(raw_folder=raw, output_folder=out, name="Demo")
    assert created.db_path.exists()
    assert (out / ".kiw" / "classification_rules.json").is_file()
    loaded = svc.load_project(output_folder=out)
    assert loaded.name == "Demo"
    assert loaded.raw_folder == raw.resolve()
    assert loaded.output_folder == out.resolve()


def test_project_try_load_last_project(tmp_path: Path, monkeypatch) -> None:
    raw = tmp_path / "raw"
    out = tmp_path / "out"
    raw.mkdir()
    state_file = tmp_path / ".kiw" / "last_project.json"
    monkeypatch.setattr(ProjectService, "_state_file", staticmethod(lambda: state_file))
    svc = ProjectService()
    svc.create_project(raw_folder=raw, output_folder=out, name="Demo")
    loaded = svc.try_load_last_project()
    assert loaded is not None
    assert loaded.output_folder == out.resolve()
    assert loaded.raw_folder == raw.resolve()


def test_project_try_load_last_project_returns_none_for_missing_project(tmp_path: Path, monkeypatch) -> None:
    missing = tmp_path / "missing-output"
    state_file = tmp_path / ".kiw" / "last_project.json"
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text(f'{{"output_folder":"{missing}"}}', encoding="utf-8")
    monkeypatch.setattr(ProjectService, "_state_file", staticmethod(lambda: state_file))
    assert ProjectService().try_load_last_project() is None


def test_inventory_rows(tmp_path: Path) -> None:
    db_path = tmp_path / "state.sqlite3"
    db = Database(db_path)
    db.connect()
    files = FileRepository(db)
    files.insert(path=str((tmp_path / "a.md").resolve()), display_name="a.md", size_bytes=11)
    row = files.get_by_path(str((tmp_path / "a.md").resolve()))
    assert row is not None
    files.update_stage_checkpoint(row.id, '{"category":"markdown"}')
    rows = InventoryService().load_rows(db_path=db_path)
    assert rows
    assert rows[0].file_name == "a.md"
    assert rows[0].category == "markdown"
    assert rows[0].workspace == "unassigned"
    assert rows[0].matched_by == ""
    assert rows[0].review_required is False


def test_inventory_rows_include_classification_details(tmp_path: Path) -> None:
    db_path = tmp_path / "state.sqlite3"
    db = Database(db_path)
    db.connect()
    files = FileRepository(db)
    files.insert(path=str((tmp_path / "b.md").resolve()), display_name="b.md", size_bytes=12)
    row = files.get_by_path(str((tmp_path / "b.md").resolve()))
    assert row is not None
    files.update_stage_checkpoint(
        row.id,
        '{"category":"other","confidence":0.42,"matched_by":"fallback","classification_reason":"no match","review_required":true}',
    )
    rows = InventoryService().load_rows(db_path=db_path)
    assert rows
    assert rows[0].confidence == 0.42
    assert rows[0].matched_by == "fallback"
    assert rows[0].classification_reason == "no match"
    assert rows[0].review_required is True


def test_inventory_load_rows_filter_review_required(tmp_path: Path) -> None:
    db_path = tmp_path / "state.sqlite3"
    db = Database(db_path)
    db.connect()
    repo = FileRepository(db)
    r = repo.insert(path=str((tmp_path / "x.md").resolve()), display_name="x.md")
    repo.set_review_required(r.id, True)
    rows = InventoryService().load_rows(db_path=db_path, filter_mode=FILTER_REVIEW_REQUIRED)
    assert len(rows) == 1
    assert rows[0].file_id == r.id


def test_inventory_load_rows_filter_workspace(tmp_path: Path) -> None:
    db_path = tmp_path / "state.sqlite3"
    db = Database(db_path)
    db.connect()
    repo = FileRepository(db)
    r = repo.insert(path=str((tmp_path / "y.md").resolve()), display_name="y.md")
    repo.update_classification_fields(r.id, {"workspace": "archive"})
    rows = InventoryService().load_rows(
        db_path=db_path,
        filter_mode=FILTER_WORKSPACE,
        workspace_filter="archive",
    )
    assert len(rows) == 1
    assert rows[0].workspace == "archive"


def test_review_service_override_subfolder_persists(tmp_path: Path) -> None:
    db_path = tmp_path / "state.sqlite3"
    db = Database(db_path)
    db.connect()
    repo = FileRepository(db)
    r = repo.insert(path=str((tmp_path / "z.md").resolve()), display_name="z.md")
    from services.review_service import ReviewService

    ReviewService().override_subfolder(db_path=db_path, file_id=r.id, subfolder="notes/a")
    again = repo.get_by_id(r.id)
    assert again is not None
    assert again.subfolder == "notes/a"
