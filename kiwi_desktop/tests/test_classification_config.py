"""Tests for project-local classification config persistence."""

from __future__ import annotations

import json

from services.classification_config import (
    ClassificationConfig,
    load_classification_config,
    save_classification_config,
)


def test_config_defaults_include_settings_fields() -> None:
    cfg = ClassificationConfig.defaults()
    assert cfg.enable_ollama is False
    assert cfg.ollama_model
    assert cfg.ai_provider == "ollama"
    assert cfg.api_key == ""
    assert cfg.cloud_model
    assert cfg.ai_mode == "rules_only"
    assert cfg.auto_assign_workspace is True
    assert cfg.duplicate_filename_policy == "rename"
    assert cfg.chunk_target_size >= 20
    assert cfg.minimum_chunk_size >= 1
    assert 0.0 < cfg.review_confidence_threshold <= 1.0
    assert cfg.broad_keywords


def test_save_and_load_settings_fields(tmp_path) -> None:
    path = tmp_path / "classification_rules.json"
    cfg = ClassificationConfig.defaults()
    cfg2 = ClassificationConfig(
        workspaces=cfg.workspaces,
        force_rules=cfg.force_rules,
        negative_rules=cfg.negative_rules,
        company_map=cfg.company_map,
        project_map=cfg.project_map,
        doc_type_patterns=cfg.doc_type_patterns,
        code_ext=cfg.code_ext,
        rule_confidence=cfg.rule_confidence,
        risky_keywords=cfg.risky_keywords,
        broad_keywords=cfg.broad_keywords,
        broad_match_force_review=cfg.broad_match_force_review,
        enable_ollama=True,
        ollama_model="llama3.2:1b",
        ai_provider="openai",
        api_key="sk-test",
        cloud_model="gpt-4o",
        ai_mode="ai_all",
        auto_assign_workspace=False,
        duplicate_filename_policy="skip",
        chunk_target_size=350,
        minimum_chunk_size=150,
        review_confidence_threshold=0.61,
        relevance_min_score=3,
        small_file_char_threshold=320,
        preflight_wiki_share_cap=0.40,
    )
    save_classification_config(path, cfg2)
    loaded = load_classification_config(path)
    assert loaded.enable_ollama is True
    assert loaded.ollama_model == "llama3.2:1b"
    assert loaded.ai_provider == "openai"
    assert loaded.api_key == "sk-test"
    assert loaded.cloud_model == "gpt-4o"
    assert loaded.ai_mode == "ai_all"
    assert loaded.auto_assign_workspace is False
    assert loaded.duplicate_filename_policy == "skip"
    assert loaded.chunk_target_size == 350
    assert loaded.minimum_chunk_size == 150
    assert loaded.review_confidence_threshold == 0.61
    assert loaded.relevance_min_score == 3
    assert loaded.small_file_char_threshold == 320
    assert loaded.preflight_wiki_share_cap == 0.40
    assert loaded.rule_confidence["force_rule"] > 0.0
    assert loaded.rule_confidence["pattern"] > 0.0
    assert loaded.rule_confidence["negative_rule"] > 0.0
    assert "confidence_threshold" in loaded.to_dict()


def test_confidence_threshold_json_alias(tmp_path) -> None:
    path = tmp_path / "classification_rules.json"
    path.write_text(json.dumps({"confidence_threshold": 0.55}), encoding="utf-8")
    loaded = load_classification_config(path)
    assert loaded.review_confidence_threshold == 0.55
