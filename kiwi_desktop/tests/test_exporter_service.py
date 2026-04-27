"""Tests for exporter profiles and manifest traceability."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import yaml

from services.exporter_service import (
    PROFILE_ANYTHINGLLM,
    PROFILE_OPEN_WEBUI,
    ExporterService,
)


def test_export_open_webui_layout_and_manifests(tmp_path: Path) -> None:
    normalized = tmp_path / "norm.md"
    normalized.write_text("---\ntitle: T\n---\n\nBody\n", encoding="utf-8")
    svc = ExporterService(export_root=tmp_path / "exports")

    out = svc.export(
        profile=PROFILE_OPEN_WEBUI,
        source_id=7,
        source_file="alpha.md",
        source_path="/src/alpha.md",
        category="markdown",
        workspace="wiki",
        subfolder="Example_Client/Playbooks",
        matched_by="fallback",
        confidence=0.42,
        normalized_path=str(normalized),
        chunks=["chunk a", "chunk b"],
        chunk_metadata=[
            {"chunk_index": 0, "estimated_word_count": 2},
            {"chunk_index": 1, "estimated_word_count": 2},
        ],
    )

    assert out.source_export_path.is_file()
    assert "/open_webui/wiki/Example_Client/Playbooks/" in str(out.source_export_path).replace("\\", "/")
    assert len(out.chunk_export_paths) == 0

    files_manifest = out.profile_root / "files_manifest.csv"
    chunks_manifest = out.profile_root / "chunks_manifest.json"
    assert files_manifest.is_file()
    assert chunks_manifest.is_file()
    with files_manifest.open("r", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    assert rows and rows[0]["source_path"] == "/src/alpha.md"
    assert rows[0]["category"] == "markdown"
    assert rows[0]["workspace"] == "wiki"
    assert rows[0]["export_path"]
    chunks = json.loads(chunks_manifest.read_text(encoding="utf-8"))
    assert chunks == []
    content = out.source_export_path.read_text(encoding="utf-8")
    fm = yaml.safe_load(content.split("---", 2)[1])
    assert fm["workspace"] == "wiki"
    assert fm["subfolder"] == "Example_Client/Playbooks"
    assert fm["matched_by"] == "fallback"
    assert fm["confidence"] == 0.42
    assert fm["source_file"] == "alpha.md"
    assert fm["processed_date"]


def test_export_anythingllm_writes_chunk_files_and_chunk_manifest(tmp_path: Path) -> None:
    normalized = tmp_path / "norm.md"
    normalized.write_text("---\ntitle: T\n---\n\nBody\n", encoding="utf-8")
    svc = ExporterService(export_root=tmp_path / "exports")

    out = svc.export(
        profile=PROFILE_ANYTHINGLLM,
        source_id=9,
        source_file="beta doc.txt",
        source_path="/src/beta.txt",
        category="text",
        workspace="ai_projects",
        subfolder="Nested/ShouldNotAppear",
        matched_by="project_map",
        confidence=0.73,
        normalized_path=str(normalized),
        chunks=["first chunk", "second chunk"],
        chunk_metadata=[
            {"chunk_index": 0, "estimated_word_count": 2},
            {"chunk_index": 1, "estimated_word_count": 2},
        ],
    )

    assert out.source_export_path.is_file()
    p = str(out.source_export_path).replace("\\", "/")
    assert "/anythingllm/AI_Web_Projects/" in p
    assert "/Nested/" not in p
    assert " " not in out.source_export_path.name
    assert len(out.chunk_export_paths) == 0

    chunks_manifest = out.profile_root / "chunks_manifest.json"
    rows = json.loads(chunks_manifest.read_text(encoding="utf-8"))
    assert rows == []


def test_duplicate_filenames_get_suffixes(tmp_path: Path) -> None:
    normalized = tmp_path / "norm.md"
    normalized.write_text("---\ntitle: T\n---\n\nBody\n", encoding="utf-8")
    svc = ExporterService(export_root=tmp_path / "exports")
    out1 = svc.export(
        profile=PROFILE_ANYTHINGLLM,
        source_id=1,
        source_file="same name.txt",
        source_path="/src/a.txt",
        category="text",
        workspace="wiki",
        subfolder="A/B",
        matched_by="force_rule",
        confidence=0.99,
        normalized_path=str(normalized),
        chunks=[],
        chunk_metadata=[],
    )
    out2 = svc.export(
        profile=PROFILE_ANYTHINGLLM,
        source_id=2,
        source_file="same name.txt",
        source_path="/src/b.txt",
        category="text",
        workspace="wiki",
        subfolder="A/B",
        matched_by="force_rule",
        confidence=0.99,
        normalized_path=str(normalized),
        chunks=[],
        chunk_metadata=[],
    )
    assert out1.source_export_path.name == "same_name.md"
    assert out2.source_export_path.name == "same_name_1.md"


def test_duplicate_filenames_can_overwrite_when_configured(tmp_path: Path) -> None:
    normalized = tmp_path / "norm.md"
    normalized.write_text("---\ntitle: T\n---\n\nBody\n", encoding="utf-8")
    svc = ExporterService(export_root=tmp_path / "exports", duplicate_filename_policy="overwrite")
    out1 = svc.export(
        profile=PROFILE_ANYTHINGLLM,
        source_id=11,
        source_file="same name.txt",
        source_path="/src/a.txt",
        category="text",
        workspace="wiki",
        subfolder="",
        matched_by="force_rule",
        confidence=0.99,
        normalized_path=str(normalized),
        chunks=[],
        chunk_metadata=[],
    )
    out2 = svc.export(
        profile=PROFILE_ANYTHINGLLM,
        source_id=12,
        source_file="same name.txt",
        source_path="/src/b.txt",
        category="text",
        workspace="wiki",
        subfolder="",
        matched_by="force_rule",
        confidence=0.99,
        normalized_path=str(normalized),
        chunks=[],
        chunk_metadata=[],
    )
    assert out1.source_export_path.name == "same_name.md"
    assert out2.source_export_path.name == "same_name.md"


def test_duplicate_filenames_can_skip_when_configured(tmp_path: Path) -> None:
    normalized1 = tmp_path / "norm1.md"
    normalized2 = tmp_path / "norm2.md"
    normalized1.write_text("---\ntitle: First\n---\n\nFirst body\n", encoding="utf-8")
    normalized2.write_text("---\ntitle: Second\n---\n\nSecond body\n", encoding="utf-8")
    svc = ExporterService(export_root=tmp_path / "exports", duplicate_filename_policy="skip")
    out1 = svc.export(
        profile=PROFILE_ANYTHINGLLM,
        source_id=21,
        source_file="same name.txt",
        source_path="/src/a.txt",
        category="text",
        workspace="wiki",
        subfolder="",
        matched_by="force_rule",
        confidence=0.99,
        normalized_path=str(normalized1),
        chunks=[],
        chunk_metadata=[],
    )
    out2 = svc.export(
        profile=PROFILE_ANYTHINGLLM,
        source_id=22,
        source_file="same name.txt",
        source_path="/src/b.txt",
        category="text",
        workspace="wiki",
        subfolder="",
        matched_by="force_rule",
        confidence=0.99,
        normalized_path=str(normalized2),
        chunks=[],
        chunk_metadata=[],
    )
    assert out1.source_export_path.name == "same_name.md"
    assert out2.source_export_path.name == "same_name.md"
    content = out1.source_export_path.read_text(encoding="utf-8")
    assert "First body" in content
    assert "Second body" not in content


def test_export_path_generation_profiles(tmp_path: Path) -> None:
    normalized = tmp_path / "norm.md"
    normalized.write_text("---\ntitle: T\n---\n\nBody\n", encoding="utf-8")
    svc = ExporterService(export_root=tmp_path / "exports")
    out_any = svc.export(
        profile=PROFILE_ANYTHINGLLM,
        source_id=31,
        source_file="client-notes.md",
        source_path="/src/client-notes.md",
        category="archive",
        workspace="archive",
        subfolder="Example_Client",
        matched_by="company_map",
        confidence=0.88,
        normalized_path=str(normalized),
        chunks=[],
        chunk_metadata=[],
    )
    out_web = svc.export(
        profile=PROFILE_OPEN_WEBUI,
        source_id=32,
        source_file="client-notes.md",
        source_path="/src/client-notes.md",
        category="archive",
        workspace="archive",
        subfolder="Example_Client/Q4",
        matched_by="company_map",
        confidence=0.88,
        normalized_path=str(normalized),
        chunks=[],
        chunk_metadata=[],
    )
    p_any = str(out_any.source_export_path).replace("\\", "/")
    p_web = str(out_web.source_export_path).replace("\\", "/")
    assert "/anythingllm/Career_Archive/" in p_any
    assert "/Example_Client/" not in p_any
    assert "/open_webui/archive/Example_Client/Q4/" in p_web
