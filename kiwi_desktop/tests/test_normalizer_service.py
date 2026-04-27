"""Tests for first-pass normalizer."""

from __future__ import annotations

import re
from pathlib import Path

import yaml

from models.file_record import FileRecord
from services.normalizer_service import FirstPassNormalizer, NormalizeResult


def _record(**kwargs: object) -> FileRecord:
    base = dict(
        id=1,
        path="/x/y.md",
        filename="y.md",
        extension=".md",
        file_created_at=None,
        file_modified_at=None,
        display_name="y.md",
        size_bytes=10,
        sha256=None,
        mime_type=None,
        current_stage="pending",
        stage_checkpoint=None,
        pipeline_version=1,
        stage_attempt=0,
        last_error=None,
        runner_status="new",
        pipeline_next_stage="classified",
        workspace="wiki",
        subfolder=None,
        matched_by=None,
        classification_reason=None,
        review_required=False,
        ai_used=False,
        content_hash=None,
        confidence=None,
        case_study_candidate=False,
        portfolio_candidate=False,
        created_at=None,
        updated_at=None,
    )
    base.update(kwargs)
    return FileRecord(**base)  # type: ignore[arg-type]


def test_normalize_markdown_strips_frontmatter_and_sets_title(tmp_path: Path) -> None:
    src = tmp_path / "note.md"
    src.write_text("---\nold: true\n---\n\n# Real Title\n\nBody.\n", encoding="utf-8")
    work = tmp_path / "out"
    n = FirstPassNormalizer(work_dir=work)
    rec = _record(id=7, path=str(src.resolve()), filename="note.md", extension=".md")
    out = n.normalize(rec)
    assert isinstance(out, NormalizeResult)
    assert out.title == "Real Title"
    assert out.category == "markdown"
    text = out.output_path.read_text(encoding="utf-8")
    assert text.startswith("---\n")
    assert "source_path:" in text
    assert "Real Title" in text
    assert "Body." in text
    assert "old: true" not in text


def test_normalize_txt(tmp_path: Path) -> None:
    src = tmp_path / "t.txt"
    src.write_text("plain\n", encoding="utf-8")
    n = FirstPassNormalizer(work_dir=tmp_path / "w")
    rec = _record(id=2, path=str(src.resolve()), filename="t.txt", extension=".txt")
    out = n.normalize(rec)
    assert out.category == "text"
    assert "plain" in out.output_path.read_text(encoding="utf-8")


def test_normalize_json_fenced(tmp_path: Path) -> None:
    src = tmp_path / "d.json"
    src.write_text('{"a": 1}', encoding="utf-8")
    n = FirstPassNormalizer(work_dir=tmp_path / "w")
    rec = _record(id=3, path=str(src.resolve()), filename="d.json", extension=".json")
    out = n.normalize(rec)
    assert out.category == "json"
    body = out.output_path.read_text(encoding="utf-8")
    assert "```json" in body
    assert '"a": 1' in body


def test_stub_pdf_contains_todo(tmp_path: Path) -> None:
    src = tmp_path / "x.pdf"
    src.write_bytes(b"%PDF-1.4 stub")
    n = FirstPassNormalizer(work_dir=tmp_path / "w")
    rec = _record(id=4, path=str(src.resolve()), filename="x.pdf", extension=".pdf")
    out = n.normalize(rec)
    assert out.category == "pdf"
    t = out.output_path.read_text(encoding="utf-8")
    assert "TODO" in t or "todo" in t.lower()
    assert "pypdf" in t.lower() or "pdfplumber" in t.lower() or "pymupdf" in t.lower()


def test_frontmatter_fields(tmp_path: Path) -> None:
    src = tmp_path / "a.md"
    src.write_text("hi", encoding="utf-8")
    n = FirstPassNormalizer(work_dir=tmp_path / "w")
    rec = _record(id=9, path=str(src.resolve()), filename="a.md", extension=".md")
    out = n.normalize(rec)
    raw = out.output_path.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n", raw, re.DOTALL)
    assert m is not None
    fm = yaml.safe_load(m.group(1))
    assert fm["title"]
    assert fm["source_file"] == "a.md"
    assert Path(fm["source_path"]) == src.resolve()
    assert fm["category"] == "markdown"
