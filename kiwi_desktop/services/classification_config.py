"""Config model and loader for deterministic file classification."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

DEFAULT_CONFIG_FILENAME = "classification_rules.json"
DEFAULT_CONFIG_SEED_PATH = Path(__file__).resolve().parent / "data" / "classification_rules_seed.json"
VALID_AI_MODES = {"rules_only", "ai_only_unclassified", "ai_all"}
VALID_AI_PROVIDERS = {"ollama", "claude", "openai"}
VALID_DUPLICATE_FILENAME_POLICIES = {"rename", "overwrite", "skip"}
RULE_CONFIDENCE_KEYS: tuple[str, ...] = (
    "force_rule",
    "negative_rule",
    "company_map",
    "project_map",
    "pattern",
    "ollama",
    "fallback",
)
# Baseline scores by classification source (tunable via RULE_CONFIDENCE in JSON).
DEFAULT_RULE_CONFIDENCE: dict[str, float] = {
    "force_rule": 0.96,
    "negative_rule": 0.95,
    "company_map": 0.90,
    "project_map": 0.85,
    "pattern": 0.75,
    "ollama": 0.72,
    "fallback": 0.40,
}
DEFAULT_RISKY_MATCH_TERMS: tuple[str, ...] = (
    "doc",
    "docs",
    "file",
    "files",
    "note",
    "notes",
    "project",
    "projects",
    "data",
    "misc",
)

# Single-token map/pattern keys that match only these terms do not auto-assign a workspace (category may
# still be suggested). Multi-word keys are never treated as broad-only.
DEFAULT_BROAD_KEYWORDS: tuple[str, ...] = (
    "project",
    "projects",
    "brief",
    "customer",
    "doc",
    "docs",
    "data",
    "note",
    "notes",
    "file",
    "files",
)

# Default category -> export workspace folder name (aligned with exporter / GUI WORKSPACE_OPTIONS).
# "wiki" is only used for explicit markdown/note material (e.g. CODE_EXT .md); unknown categories do not
# implicitly map to wiki — those stay unassigned until rules or review assign a workspace.
DEFAULT_WORKSPACES: dict[str, str] = {
    "portfolio": "career_portfolio",
    "ai_project": "ai_projects",
    "archive": "archive",
    "case_studies": "case_studies",
    "markdown": "wiki",
}

# Starter maps: lowercase keys; values are category labels resolved via WORKSPACES.
DEFAULT_COMPANY_MAP: dict[str, str] = {
    "acme": "archive",
    "contoso": "archive",
    "example_client": "archive",
}

DEFAULT_PROJECT_MAP: dict[str, str] = {
    "agentic": "ai_project",
    "mlops": "ai_project",
    "llm": "ai_project",
}

# Extension (no dot) -> category
DEFAULT_CODE_EXT: dict[str, str] = {
    "py": "ai_project",
    "ipynb": "ai_project",
    "md": "markdown",
    "markdown": "markdown",
    "pptx": "archive",
    "ppt": "archive",
    "docx": "archive",
    "doc": "archive",
    "pdf": "archive",
}

@dataclass(frozen=True, slots=True)
class ForceRule:
    contains: str
    category: str
    workspace: str | None = None
    subfolder: str | None = None
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class DocTypePattern:
    contains: str
    doc_type: str
    category: str | None = None
    workspace: str | None = None
    subfolder: str | None = None
    reason: str | None = None


# Example high-priority path/filename keyword (users can override or clear via FORCE_RULES in JSON).
DEFAULT_FORCE_RULES: tuple[ForceRule, ...] = (
    ForceRule(contains="resume", category="portfolio", subfolder="resumes"),
)


@dataclass(frozen=True, slots=True)
class ClassificationConfig:
    workspaces: dict[str, str]
    force_rules: tuple[ForceRule, ...]
    negative_rules: tuple[ForceRule, ...]
    company_map: dict[str, str]
    project_map: dict[str, str]
    doc_type_patterns: tuple[DocTypePattern, ...]
    code_ext: dict[str, str]
    rule_confidence: dict[str, float]
    risky_keywords: tuple[str, ...]
    broad_keywords: tuple[str, ...]
    broad_match_force_review: bool
    enable_ollama: bool
    ollama_model: str
    ai_provider: str
    api_key: str
    cloud_model: str
    ai_mode: str
    auto_assign_workspace: bool
    duplicate_filename_policy: str
    chunk_target_size: int
    minimum_chunk_size: int
    review_confidence_threshold: float
    relevance_min_score: int
    small_file_char_threshold: int
    preflight_wiki_share_cap: float

    @classmethod
    def defaults(cls) -> "ClassificationConfig":
        return cls(
            workspaces=dict(DEFAULT_WORKSPACES),
            force_rules=DEFAULT_FORCE_RULES,
            negative_rules=(),
            company_map=dict(DEFAULT_COMPANY_MAP),
            project_map=dict(DEFAULT_PROJECT_MAP),
            doc_type_patterns=(),
            code_ext=dict(DEFAULT_CODE_EXT),
            rule_confidence=dict(DEFAULT_RULE_CONFIDENCE),
            risky_keywords=DEFAULT_RISKY_MATCH_TERMS,
            broad_keywords=DEFAULT_BROAD_KEYWORDS,
            broad_match_force_review=True,
            enable_ollama=False,
            ollama_model="llama3.2:3b",
            ai_provider="ollama",
            api_key="",
            cloud_model="gpt-4o-mini",
            ai_mode="rules_only",
            auto_assign_workspace=True,
            duplicate_filename_policy="rename",
            chunk_target_size=220,
            minimum_chunk_size=120,
            review_confidence_threshold=0.70,
            relevance_min_score=2,
            small_file_char_threshold=260,
            preflight_wiki_share_cap=0.30,
        )

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> "ClassificationConfig":
        base = cls.defaults()
        workspaces = _merge_string_maps(DEFAULT_WORKSPACES, payload.get("WORKSPACES"))

        negative_rules = _force_rules(payload.get("NEGATIVE_RULES", payload.get("OVERRIDE_RULES")))
        rules = _force_rules(payload.get("FORCE_RULES"))
        if "NEGATIVE_RULES" in payload or "OVERRIDE_RULES" in payload:
            negative_rules_out: tuple[ForceRule, ...] = tuple(negative_rules)
        else:
            negative_rules_out = base.negative_rules
        if "FORCE_RULES" in payload:
            force_rules_out: tuple[ForceRule, ...] = tuple(rules)
        else:
            force_rules_out = base.force_rules
        doc_type_patterns = _doc_type_patterns(payload.get("DOC_TYPE_PATTERNS"))
        if "DOC_TYPE_PATTERNS" in payload:
            doc_type_patterns_out: tuple[DocTypePattern, ...] = tuple(doc_type_patterns)
        else:
            doc_type_patterns_out = base.doc_type_patterns
        company_map = _merge_string_maps(base.company_map, payload.get("COMPANY_MAP"))
        project_map = _merge_string_maps(base.project_map, payload.get("PROJECT_MAP"))
        code_ext = {k.lower().lstrip("."): v for k, v in _merge_string_maps(base.code_ext, payload.get("CODE_EXT")).items()}
        risky_raw = payload.get("RISKY_KEYWORDS", payload.get("RISKY_MATCH_TERMS"))
        risky_terms = _string_tuple(risky_raw, base.risky_keywords)
        broad_raw = payload.get("BROAD_KEYWORDS", payload.get("broad_keywords"))
        broad_terms = _string_tuple(broad_raw, base.broad_keywords)
        rule_confidence = _rule_confidence_map(payload.get("RULE_CONFIDENCE"), base.rule_confidence)
        _merge_legacy_rule_confidence_keys(rule_confidence, payload.get("RULE_CONFIDENCE"))
        ai_provider_raw = str(payload.get("ai_provider", base.ai_provider)).strip().lower()
        ai_provider = ai_provider_raw if ai_provider_raw in VALID_AI_PROVIDERS else base.ai_provider
        api_key = str(payload.get("api_key", base.api_key)).strip()
        cloud_model = str(payload.get("cloud_model", base.cloud_model)).strip() or base.cloud_model
        ai_mode_raw = str(payload.get("ai_mode", base.ai_mode)).strip() or base.ai_mode
        ai_mode = ai_mode_raw if ai_mode_raw in VALID_AI_MODES else base.ai_mode
        dup_raw = str(payload.get("duplicate_filename_policy", base.duplicate_filename_policy)).strip().lower()
        duplicate_filename_policy = (
            dup_raw if dup_raw in VALID_DUPLICATE_FILENAME_POLICIES else base.duplicate_filename_policy
        )
        chunk_target = _int_or_default(payload.get("chunk_target_size"), base.chunk_target_size, minimum=20)
        min_chunk = _int_or_default(payload.get("minimum_chunk_size"), base.minimum_chunk_size, minimum=1)
        relevance_min_score = _int_or_default(payload.get("relevance_min_score"), base.relevance_min_score, minimum=0)
        small_file_char_threshold = _int_or_default(
            payload.get("small_file_char_threshold"), base.small_file_char_threshold, minimum=50
        )
        preflight_wiki_share_cap = _float_or_default(
            payload.get("preflight_wiki_share_cap"),
            base.preflight_wiki_share_cap,
        )
        preflight_wiki_share_cap = max(0.05, min(1.0, preflight_wiki_share_cap))
        low_conf_raw = payload.get(
            "confidence_threshold",
            payload.get("low_confidence_threshold", payload.get("review_confidence_threshold")),
        )
        threshold = _float_or_default(
            low_conf_raw, base.review_confidence_threshold
        )
        return cls(
            workspaces=workspaces,
            force_rules=force_rules_out,
            negative_rules=negative_rules_out,
            company_map=company_map,
            project_map=project_map,
            doc_type_patterns=doc_type_patterns_out,
            code_ext=code_ext,
            rule_confidence=rule_confidence,
            risky_keywords=risky_terms,
            broad_keywords=broad_terms,
            broad_match_force_review=bool(
                payload.get("broad_match_force_review", base.broad_match_force_review)
            ),
            enable_ollama=bool(payload.get("enable_ollama", base.enable_ollama)),
            ollama_model=str(payload.get("ollama_model", base.ollama_model)),
            ai_provider=ai_provider,
            api_key=api_key,
            cloud_model=cloud_model,
            ai_mode=ai_mode,
            auto_assign_workspace=bool(payload.get("auto_assign_workspace", base.auto_assign_workspace)),
            duplicate_filename_policy=duplicate_filename_policy,
            chunk_target_size=chunk_target,
            minimum_chunk_size=min_chunk,
            review_confidence_threshold=threshold,
            relevance_min_score=relevance_min_score,
            small_file_char_threshold=small_file_char_threshold,
            preflight_wiki_share_cap=preflight_wiki_share_cap,
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "WORKSPACES": dict(self.workspaces),
            "NEGATIVE_RULES": [
                {
                    "contains": r.contains,
                    "category": r.category,
                    "workspace": r.workspace,
                    "subfolder": r.subfolder,
                    "reason": r.reason,
                }
                for r in self.negative_rules
            ],
            "OVERRIDE_RULES": [
                {
                    "contains": r.contains,
                    "category": r.category,
                    "workspace": r.workspace,
                    "subfolder": r.subfolder,
                    "reason": r.reason,
                }
                for r in self.negative_rules
            ],
            "FORCE_RULES": [
                {
                    "contains": r.contains,
                    "category": r.category,
                    "workspace": r.workspace,
                    "subfolder": r.subfolder,
                    "reason": r.reason,
                }
                for r in self.force_rules
            ],
            "COMPANY_MAP": dict(self.company_map),
            "PROJECT_MAP": dict(self.project_map),
            "DOC_TYPE_PATTERNS": [
                {
                    "contains": p.contains,
                    "doc_type": p.doc_type,
                    "category": p.category,
                    "workspace": p.workspace,
                    "subfolder": p.subfolder,
                    "reason": p.reason,
                }
                for p in self.doc_type_patterns
            ],
            "CODE_EXT": dict(self.code_ext),
            "RULE_CONFIDENCE": dict(self.rule_confidence),
            "RISKY_KEYWORDS": list(self.risky_keywords),
            "RISKY_MATCH_TERMS": list(self.risky_keywords),
            "BROAD_KEYWORDS": list(self.broad_keywords),
            "broad_match_force_review": self.broad_match_force_review,
            "enable_ollama": self.enable_ollama,
            "ollama_model": self.ollama_model,
            "ai_provider": self.ai_provider,
            "api_key": self.api_key,
            "cloud_model": self.cloud_model,
            "ai_mode": self.ai_mode,
            "auto_assign_workspace": self.auto_assign_workspace,
            "duplicate_filename_policy": self.duplicate_filename_policy,
            "chunk_target_size": self.chunk_target_size,
            "minimum_chunk_size": self.minimum_chunk_size,
            "relevance_min_score": self.relevance_min_score,
            "small_file_char_threshold": self.small_file_char_threshold,
            "preflight_wiki_share_cap": self.preflight_wiki_share_cap,
            "confidence_threshold": self.review_confidence_threshold,
            "low_confidence_threshold": self.review_confidence_threshold,
            "review_confidence_threshold": self.review_confidence_threshold,
        }


def load_classification_config(path: Path | None) -> ClassificationConfig:
    if path is None or not path.is_file():
        return ClassificationConfig.defaults()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ClassificationConfig.defaults()
    if not isinstance(payload, dict):
        return ClassificationConfig.defaults()
    return ClassificationConfig.from_dict(payload)


def ensure_default_classification_config(path: Path) -> None:
    if path.exists():
        return
    write_classification_config_from_seed(path)


def write_classification_config_from_seed(path: Path) -> bool:
    """Write classification config from bundled seed when available.

    Returns True when seed file was used, False when defaults fallback was used.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    if DEFAULT_CONFIG_SEED_PATH.is_file():
        try:
            seed_text = DEFAULT_CONFIG_SEED_PATH.read_text(encoding="utf-8")
            payload = json.loads(seed_text)
            if isinstance(payload, dict):
                path.write_text(seed_text, encoding="utf-8")
                return True
        except (OSError, json.JSONDecodeError):
            pass
    config = ClassificationConfig.defaults()
    path.write_text(json.dumps(config.to_dict(), indent=2), encoding="utf-8")
    return False


def save_classification_config(path: Path, config: ClassificationConfig) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(config.to_dict(), indent=2), encoding="utf-8")


def _string_map(value: object) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    out: dict[str, str] = {}
    for k, v in value.items():
        ks = str(k).strip().lower()
        vs = str(v).strip()
        if ks and vs:
            out[ks] = vs
    return out


def _merge_string_maps(defaults: dict[str, str], override: object) -> dict[str, str]:
    merged = dict(defaults)
    merged.update(_string_map(override))
    return merged


def _float_or_default(value: object, default: float) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    if out <= 0.0:
        return default
    if out > 1.0:
        return 1.0
    return out


def _int_or_default(value: object, default: int, *, minimum: int) -> int:
    try:
        out = int(value)
    except (TypeError, ValueError):
        return default
    if out < minimum:
        return minimum
    return out


def _string_tuple(value: object, default: tuple[str, ...]) -> tuple[str, ...]:
    if not isinstance(value, list):
        return default
    out: list[str] = []
    for item in value:
        s = str(item).strip().lower()
        if s:
            out.append(s)
    return tuple(out) if out else default


def _force_rules(value: object) -> list[ForceRule]:
    rules: list[ForceRule] = []
    if not isinstance(value, list):
        return rules
    for item in value:
        if not isinstance(item, dict):
            continue
        contains = str(item.get("contains", "")).strip()
        category = str(item.get("category", "")).strip()
        if not contains or not category:
            continue
        workspace = str(item.get("workspace", "")).strip() or None
        subfolder = str(item.get("subfolder", "")).strip() or None
        reason = str(item.get("reason", "")).strip() or None
        rules.append(
            ForceRule(
                contains=contains,
                category=category,
                workspace=workspace,
                subfolder=subfolder,
                reason=reason,
            )
        )
    return rules


def _rule_confidence_map(value: object, default: dict[str, float]) -> dict[str, float]:
    out = dict(default)
    if not isinstance(value, dict):
        return out
    for key in RULE_CONFIDENCE_KEYS:
        if key not in value:
            continue
        out[key] = _float_or_default(value.get(key), out[key])
    return out


def _merge_legacy_rule_confidence_keys(out: dict[str, float], raw: object) -> None:
    """Map deprecated keys (``code_ext``, ``doc_type_pattern``) into ``pattern`` when present in JSON."""
    if not isinstance(raw, dict):
        return
    if "pattern" in raw:
        return
    if "code_ext" in raw:
        out["pattern"] = _float_or_default(raw.get("code_ext"), out.get("pattern", DEFAULT_RULE_CONFIDENCE["pattern"]))
    elif "doc_type_pattern" in raw:
        out["pattern"] = _float_or_default(
            raw.get("doc_type_pattern"), out.get("pattern", DEFAULT_RULE_CONFIDENCE["pattern"])
        )


def _doc_type_patterns(value: object) -> list[DocTypePattern]:
    out: list[DocTypePattern] = []
    if not isinstance(value, list):
        return out
    for item in value:
        if not isinstance(item, dict):
            continue
        contains = str(item.get("contains", "")).strip()
        doc_type = str(item.get("doc_type", "")).strip()
        if not contains or not doc_type:
            continue
        out.append(
            DocTypePattern(
                contains=contains,
                doc_type=doc_type,
                category=str(item.get("category", "")).strip() or None,
                workspace=str(item.get("workspace", "")).strip() or None,
                subfolder=str(item.get("subfolder", "")).strip() or None,
                reason=str(item.get("reason", "")).strip() or None,
            )
        )
    return out
