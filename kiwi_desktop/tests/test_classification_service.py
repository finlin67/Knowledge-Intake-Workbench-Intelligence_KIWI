"""Tests for config-driven deterministic classification."""

from __future__ import annotations

import json
from pathlib import Path

from db.repositories import FileRepository
from db.session import Database
from services.classification_service import ClassificationService


def test_classification_prefers_force_rules(tmp_path: Path) -> None:
    cfg_path = tmp_path / "classification_rules.json"
    cfg_path.write_text(
        json.dumps(
            {
                "FORCE_RULES": [
                    {
                        "contains": "resume",
                        "category": "portfolio",
                        "workspace": "career_portfolio",
                        "subfolder": "resumes",
                    }
                ],
                "COMPANY_MAP": {"acme": "archive"},
                "PROJECT_MAP": {"agentic": "ai_project"},
                "CODE_EXT": {"py": "ai_project"},
            }
        ),
        encoding="utf-8",
    )
    db = Database(Path(":memory:"))
    db.connect()
    rec = FileRepository(db).insert(path=str((tmp_path / "resume_acme.py").resolve()), display_name="resume_acme.py")
    decision = ClassificationService.from_path(cfg_path).classify(rec)
    assert decision.category == "portfolio"
    assert decision.workspace == "career_portfolio"
    assert decision.subfolder == "resumes"
    assert decision.matched_by == "force_rule"
    assert decision.doc_type == "portfolio"
    assert "FORCE_RULES" in decision.classification_reason or "resume" in decision.classification_reason
    assert decision.review_required is False


def test_classification_falls_back_to_other_with_review(tmp_path: Path) -> None:
    db = Database(Path(":memory:"))
    db.connect()
    rec = FileRepository(db).insert(path=str((tmp_path / "notes.unknown").resolve()), display_name="notes.unknown")
    decision = ClassificationService.from_path(None).classify(rec)
    assert decision.category == "other"
    assert decision.workspace is None
    assert decision.matched_by == "fallback"
    assert decision.doc_type == "misc"
    assert decision.confidence == 0.40
    assert decision.review_required is True


def test_risky_keyword_match_forces_review_required(tmp_path: Path) -> None:
    cfg_path = tmp_path / "classification_rules.json"
    cfg_path.write_text(
        json.dumps(
            {
                "COMPANY_MAP": {"doc": "archive"},
                "RISKY_MATCH_TERMS": ["doc"],
            }
        ),
        encoding="utf-8",
    )
    db = Database(Path(":memory:"))
    db.connect()
    rec = FileRepository(db).insert(path=str((tmp_path / "doc_index.md").resolve()), display_name="doc_index.md")
    decision = ClassificationService.from_path(cfg_path).classify(rec)
    assert decision.category == "archive"
    assert decision.matched_by == "company_map"
    assert decision.review_required is True
    assert "risky" in decision.classification_reason.lower()


def test_classification_order_company_before_project(tmp_path: Path) -> None:
    cfg_path = tmp_path / "classification_rules.json"
    cfg_path.write_text(
        json.dumps(
            {
                "COMPANY_MAP": {"acme": "archive"},
                "PROJECT_MAP": {"acme": "ai_project"},
            }
        ),
        encoding="utf-8",
    )
    db = Database(Path(":memory:"))
    db.connect()
    rec = FileRepository(db).insert(path=str((tmp_path / "acme_notes.md").resolve()), display_name="acme_notes.md")
    decision = ClassificationService.from_path(cfg_path).classify(rec)
    assert decision.category == "archive"
    assert decision.matched_by == "company_map"


def test_phrase_match_preferred_over_single_token(tmp_path: Path) -> None:
    cfg_path = tmp_path / "classification_rules.json"
    cfg_path.write_text(
        json.dumps(
            {
                "COMPANY_MAP": {"example_client": "archive", "example_client platform": "case_studies"},
            }
        ),
        encoding="utf-8",
    )
    db = Database(Path(":memory:"))
    db.connect()
    rec = FileRepository(db).insert(
        path=str((tmp_path / "example_client_platform_migration.md").resolve()),
        display_name="example_client_platform_migration.md",
    )
    decision = ClassificationService.from_path(cfg_path).classify(rec)
    assert decision.category == "case_studies"
    assert decision.matched_by == "company_map"
    assert "example_client platform" in decision.classification_reason.lower()


def test_override_rules_force_reference_or_misc(tmp_path: Path) -> None:
    cfg_path = tmp_path / "classification_rules.json"
    cfg_path.write_text(
        json.dumps(
            {
                "NEGATIVE_RULES": [
                    {"contains": "readme template", "category": "markdown", "workspace": "wiki", "subfolder": "reference"},
                    {"contains": "tmp export", "category": "other", "workspace": "wiki", "subfolder": "misc"},
                ],
                "COMPANY_MAP": {"readme": "archive"},
            }
        ),
        encoding="utf-8",
    )
    db = Database(Path(":memory:"))
    db.connect()
    rec = FileRepository(db).insert(
        path=str((tmp_path / "readme_template.md").resolve()),
        display_name="readme_template.md",
    )
    decision = ClassificationService.from_path(cfg_path).classify(rec)
    assert decision.matched_by == "negative_rule"
    assert decision.workspace == "wiki"
    assert decision.subfolder == "reference"
    assert decision.category == "markdown"


def test_risky_keyword_lowers_confidence(tmp_path: Path) -> None:
    cfg_path = tmp_path / "classification_rules.json"
    cfg_path.write_text(
        json.dumps(
            {
                "COMPANY_MAP": {"doc": "archive"},
                "RISKY_MATCH_TERMS": ["doc"],
            }
        ),
        encoding="utf-8",
    )
    db = Database(Path(":memory:"))
    db.connect()
    rec = FileRepository(db).insert(path=str((tmp_path / "doc_pack.md").resolve()), display_name="doc_pack.md")
    decision = ClassificationService.from_path(cfg_path).classify(rec)
    assert decision.confidence < 0.90


def test_doc_type_pattern_classification(tmp_path: Path) -> None:
    cfg_path = tmp_path / "classification_rules.json"
    cfg_path.write_text(
        json.dumps(
            {
                "DOC_TYPE_PATTERNS": [
                    {"contains": "case study", "doc_type": "case_study", "subfolder": "case-studies"}
                ],
            }
        ),
        encoding="utf-8",
    )
    db = Database(Path(":memory:"))
    db.connect()
    rec = FileRepository(db).insert(
        path=str((tmp_path / "migration_case_study.md").resolve()),
        display_name="migration_case_study.md",
    )
    decision = ClassificationService.from_path(cfg_path).classify(rec)
    assert decision.matched_by == "pattern"
    assert decision.doc_type == "case_study"
    assert decision.category == "case_studies"
    assert decision.case_study_candidate is True


def test_rule_confidence_defaults_from_config(tmp_path: Path) -> None:
    cfg_path = tmp_path / "classification_rules.json"
    cfg_path.write_text(
        json.dumps(
            {
                "RULE_CONFIDENCE": {
                    "company_map": 0.66,
                    "fallback": 0.19,
                },
                "COMPANY_MAP": {"acme": "archive"},
            }
        ),
        encoding="utf-8",
    )
    db = Database(Path(":memory:"))
    db.connect()
    rec_company = FileRepository(db).insert(path=str((tmp_path / "acme.md").resolve()), display_name="acme.md")
    rec_fallback = FileRepository(db).insert(path=str((tmp_path / "zzz.unknown").resolve()), display_name="zzz.unknown")
    svc = ClassificationService.from_path(cfg_path)
    dec_company = svc.classify(rec_company)
    dec_fallback = svc.classify(rec_fallback)
    assert dec_company.confidence == 0.66
    assert dec_fallback.confidence == 0.19
    assert dec_company.workspace is None
    assert dec_company.review_required is True
    assert dec_fallback.workspace is None


def test_broad_map_keyword_does_not_assign_workspace(tmp_path: Path) -> None:
    cfg_path = tmp_path / "classification_rules.json"
    cfg_path.write_text(
        json.dumps(
            {
                "PROJECT_MAP": {"project": "ai_project"},
                "BROAD_KEYWORDS": ["project", "brief", "customer"],
            }
        ),
        encoding="utf-8",
    )
    db = Database(Path(":memory:"))
    db.connect()
    rec = FileRepository(db).insert(
        path=str((tmp_path / "customer_project_notes.md").resolve()),
        display_name="customer_project_notes.md",
    )
    decision = ClassificationService.from_path(cfg_path).classify(rec)
    assert decision.category == "ai_project"
    assert decision.matched_by == "project_map"
    assert decision.workspace is None
    assert decision.review_required is True
    assert "broad keyword alone" in decision.classification_reason.lower()


def test_phrase_project_map_wins_over_broad_token(tmp_path: Path) -> None:
    cfg_path = tmp_path / "classification_rules.json"
    cfg_path.write_text(
        json.dumps(
            {
                "PROJECT_MAP": {
                    "customer success": "case_studies",
                    "customer": "ai_project",
                },
            }
        ),
        encoding="utf-8",
    )
    db = Database(Path(":memory:"))
    db.connect()
    rec = FileRepository(db).insert(
        path=str((tmp_path / "customer_success_story.md").resolve()),
        display_name="customer_success_story.md",
    )
    decision = ClassificationService.from_path(cfg_path).classify(rec)
    assert decision.category == "case_studies"
    assert "customer success" in decision.classification_reason.lower()


def test_force_rules_phrase_before_single_token(tmp_path: Path) -> None:
    cfg_path = tmp_path / "classification_rules.json"
    cfg_path.write_text(
        json.dumps(
            {
                "FORCE_RULES": [
                    {"contains": "internal", "category": "archive", "workspace": "archive"},
                    {"contains": "internal only brief", "category": "portfolio", "workspace": "career_portfolio"},
                ],
            }
        ),
        encoding="utf-8",
    )
    db = Database(Path(":memory:"))
    db.connect()
    rec = FileRepository(db).insert(
        path=str((tmp_path / "internal_only_brief_v1.md").resolve()),
        display_name="internal_only_brief_v1.md",
    )
    decision = ClassificationService.from_path(cfg_path).classify(rec)
    assert decision.category == "portfolio"
    assert decision.matched_by == "force_rule"
    assert "internal only brief" in decision.classification_reason.lower()


def test_auto_assign_workspace_can_be_disabled(tmp_path: Path) -> None:
    cfg_path = tmp_path / "classification_rules.json"
    cfg_path.write_text(
        json.dumps(
            {
                "auto_assign_workspace": False,
                "COMPANY_MAP": {"acme": "archive"},
            }
        ),
        encoding="utf-8",
    )
    db = Database(Path(":memory:"))
    db.connect()
    rec = FileRepository(db).insert(path=str((tmp_path / "acme.md").resolve()), display_name="acme.md")
    decision = ClassificationService.from_path(cfg_path).classify(rec)
    assert decision.category == "archive"
    assert decision.workspace is None


def test_small_file_lane_routes_low_context_fragments_to_wiki(tmp_path: Path) -> None:
    cfg_path = tmp_path / "classification_rules.json"
    cfg_path.write_text(
        json.dumps(
            {
                "relevance_min_score": 3,
                "small_file_char_threshold": 300,
            }
        ),
        encoding="utf-8",
    )
    file_path = tmp_path / "snippet.md"
    file_path.write_text("todo ideas\ncheck link later\n", encoding="utf-8")
    db = Database(Path(":memory:"))
    db.connect()
    rec = FileRepository(db).insert(path=str(file_path.resolve()), display_name=file_path.name)
    decision = ClassificationService.from_path(cfg_path).classify(rec)
    assert decision.workspace == "wiki"
    assert decision.subfolder == "fragments"
    assert decision.matched_by == "pattern"
    assert "small-file lane" in decision.classification_reason.lower()


def test_relevance_gate_holds_low_signal_full_size_documents_for_review(tmp_path: Path) -> None:
    cfg_path = tmp_path / "classification_rules.json"
    cfg_path.write_text(
        json.dumps(
            {
                "relevance_min_score": 4,
                "small_file_char_threshold": 100,
            }
        ),
        encoding="utf-8",
    )
    file_path = tmp_path / "long_notes.md"
    file_path.write_text(("misc notes only\n" * 60), encoding="utf-8")
    db = Database(Path(":memory:"))
    db.connect()
    rec = FileRepository(db).insert(path=str(file_path.resolve()), display_name=file_path.name)
    decision = ClassificationService.from_path(cfg_path).classify(rec)
    assert decision.matched_by == "fallback"
    assert decision.workspace is None
    assert decision.review_required is True
    assert "relevance gate" in decision.classification_reason.lower()


def test_markdown_extension_is_not_auto_routed_to_wiki_without_other_signals(tmp_path: Path) -> None:
    cfg_path = tmp_path / "classification_rules.json"
    cfg_path.write_text(
        json.dumps(
            {
                "relevance_min_score": 4,
                "small_file_char_threshold": 120,
                "CODE_EXT": {"md": "markdown"},
            }
        ),
        encoding="utf-8",
    )
    file_path = tmp_path / "weekly_notes.md"
    file_path.write_text(("random note text\n" * 40), encoding="utf-8")
    db = Database(Path(":memory:"))
    db.connect()
    rec = FileRepository(db).insert(path=str(file_path.resolve()), display_name=file_path.name)
    decision = ClassificationService.from_path(cfg_path).classify(rec)
    assert decision.workspace is None
    assert decision.review_required is True
    assert decision.matched_by == "fallback"
