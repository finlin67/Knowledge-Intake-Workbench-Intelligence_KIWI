"""Deterministic classification from config-driven rules (library-style pipeline)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from models.file_record import FileRecord
from services.classification_config import ClassificationConfig, DocTypePattern, ForceRule, load_classification_config
from utils.file_readers import extract_text_sample
from utils.logging_utils import get_logger

# Persisted / displayed identifiers (must match DB and downstream tooling).
MATCH_FORCE_RULE = "force_rule"
MATCH_NEGATIVE_RULE = "negative_rule"
MATCH_COMPANY_MAP = "company_map"
MATCH_PROJECT_MAP = "project_map"
MATCH_PATTERN = "pattern"
MATCH_FALLBACK = "fallback"

# Ollama scores are clamped to this band before persistence (model output may be outside).
OLLAMA_CONFIDENCE_MIN = 0.6
OLLAMA_CONFIDENCE_MAX = 0.85


def clamp_ollama_confidence(value: float) -> float:
    """Clamp AI-reported confidence to the configured Ollama band (0.6–0.85 by default)."""
    x = float(value)
    return min(OLLAMA_CONFIDENCE_MAX, max(OLLAMA_CONFIDENCE_MIN, round(x, 3)))


@dataclass(frozen=True, slots=True)
class ClassificationDecision:
    category: str
    workspace: str | None
    subfolder: str
    doc_type: str
    confidence: float
    matched_by: str
    classification_reason: str
    review_required: bool
    case_study_candidate: bool
    portfolio_candidate: bool
    ai_used: bool


class ClassificationService:
    __slots__ = ("_config", "_risky_terms", "_broad_terms", "_log")

    def __init__(self, config: ClassificationConfig) -> None:
        self._config = config
        self._risky_terms = {t.strip().lower() for t in config.risky_keywords if t.strip()}
        self._broad_terms = {t.strip().lower() for t in config.broad_keywords if t.strip()}
        self._log = get_logger("kiw.classification")

    @classmethod
    def from_path(cls, config_path: Path | None) -> "ClassificationService":
        return cls(load_classification_config(config_path))

    def classify(self, rec: FileRecord) -> ClassificationDecision:
        haystack = f"{rec.path} {rec.filename or ''}".lower()
        normalized_haystack = _normalize_text(haystack)
        extension = (rec.extension or "").lower().lstrip(".")
        text_sample = extract_text_sample(Path(rec.path))
        signals = _detect_content_signals(text_sample)
        relevance_score = _relevance_score(haystack=haystack, text_sample=text_sample, config=self._config)
        small_file = len(text_sample.strip()) < self._config.small_file_char_threshold

        # Order: 1) FORCE_RULES → 2) NEGATIVE_RULES → 3) COMPANY_MAP → 4) PROJECT_MAP →
        # 5) DOC_TYPE_PATTERNS → 6) CODE_EXT → (pipeline may apply AI) → 7) FALLBACK.
        # 1. FORCE_RULES (phrase matches before single-token rules within this list)
        for rule in _sort_rules_phrase_first(self._config.force_rules):
            needle = rule.contains.lower()
            if needle and _contains_match(haystack=haystack, normalized_haystack=normalized_haystack, token=needle):
                category = rule.category
                workspace = self._resolve_workspace(
                    category=category,
                    suggested_workspace=rule.workspace,
                    current_workspace=rec.workspace,
                )
                subfolder = (rule.subfolder or "").strip()
                risky = self._is_risky_match(needle)
                broad_only = self._map_key_is_broad_only(rule.contains)
                base_conf = self._rule_confidence(MATCH_FORCE_RULE, 0.96)
                confidence = self._risky_confidence(base_conf) if risky else base_conf
                confidence = _boost_confidence_for_portfolio_workspace(confidence, workspace, signals)
                reason = rule.reason or f'Matched FORCE_RULES keyword: {rule.contains}'
                if risky:
                    reason = f"{reason} (review required: risky/broad keyword '{rule.contains}')"
                decision = self._decision(
                    category=category,
                    workspace=workspace,
                    subfolder=subfolder,
                    doc_type=_doc_type_from_category(category),
                    confidence=confidence,
                    matched_by=MATCH_FORCE_RULE,
                    reason=reason,
                    ai_used=False,
                    force_review=risky,
                    broad_keyword_only_match=broad_only,
                    case_study_candidate_hint=signals.case_study_candidate,
                    portfolio_candidate_hint=signals.portfolio_candidate,
                )
                self._log.debug(
                    "classified by force rule",
                    extra={"file_id": rec.id, "matched_by": decision.matched_by, "review_required": decision.review_required},
                )
                return decision

        # 2. NEGATIVE_RULES (override routing; phrase-first within list)
        for rule in _sort_rules_phrase_first(self._config.negative_rules):
            needle = rule.contains.lower()
            if needle and _contains_match(haystack=haystack, normalized_haystack=normalized_haystack, token=needle):
                category = rule.category
                workspace = self._resolve_workspace(
                    category=category,
                    suggested_workspace=rule.workspace,
                    current_workspace=rec.workspace,
                )
                subfolder = (rule.subfolder or "").strip()
                risky = self._is_risky_match(needle)
                broad_only = self._map_key_is_broad_only(rule.contains)
                base_conf = self._rule_confidence("negative_rule", 0.95)
                confidence = self._risky_confidence(base_conf) if risky else base_conf
                confidence = _boost_confidence_for_portfolio_workspace(confidence, workspace, signals)
                reason = rule.reason or f"Matched NEGATIVE_RULES keyword: {rule.contains}"
                if risky:
                    reason = f"{reason} (review required: risky/broad keyword '{rule.contains}')"
                decision = self._decision(
                    category=category,
                    workspace=workspace,
                    subfolder=subfolder,
                    doc_type=_doc_type_from_category(category),
                    confidence=confidence,
                    matched_by=MATCH_NEGATIVE_RULE,
                    reason=reason,
                    ai_used=False,
                    force_review=risky,
                    broad_keyword_only_match=broad_only,
                    case_study_candidate_hint=signals.case_study_candidate,
                    portfolio_candidate_hint=signals.portfolio_candidate,
                )
                self._log.debug(
                    "classified by negative rule",
                    extra={"file_id": rec.id, "matched_by": decision.matched_by, "review_required": decision.review_required},
                )
                return decision

        # 3. COMPANY_MAP
        company_hit = _first_category_match(haystack, normalized_haystack, self._config.company_map)
        if company_hit is not None:
            category, token = company_hit
            risky = self._is_risky_match(token)
            broad_only = self._map_key_is_broad_only(token)
            ws = self._resolve_workspace(category=category, current_workspace=rec.workspace)
            base_conf = self._rule_confidence(MATCH_COMPANY_MAP, 0.90)
            confidence = self._risky_confidence(base_conf) if risky else base_conf
            confidence = _boost_confidence_for_portfolio_workspace(confidence, ws, signals)
            reason = f"Matched COMPANY_MAP keyword: {token}"
            if risky:
                reason = f"{reason} (review required: risky/broad keyword)"
            decision = self._decision(
                category=category,
                workspace=ws,
                subfolder="",
                doc_type=_doc_type_from_category(category),
                confidence=confidence,
                matched_by=MATCH_COMPANY_MAP,
                reason=reason,
                ai_used=False,
                force_review=risky,
                broad_keyword_only_match=broad_only,
                case_study_candidate_hint=signals.case_study_candidate,
                portfolio_candidate_hint=signals.portfolio_candidate,
            )
            self._log.debug(
                "classified by company map",
                extra={"file_id": rec.id, "matched_by": decision.matched_by, "review_required": decision.review_required},
            )
            return decision

        # 4. PROJECT_MAP
        project_hit = _first_category_match(haystack, normalized_haystack, self._config.project_map)
        if project_hit is not None:
            category, token = project_hit
            risky = self._is_risky_match(token)
            broad_only = self._map_key_is_broad_only(token)
            ws = self._resolve_workspace(category=category, current_workspace=rec.workspace)
            base_conf = self._rule_confidence(MATCH_PROJECT_MAP, 0.85)
            confidence = self._risky_confidence(base_conf) if risky else base_conf
            confidence = _boost_confidence_for_portfolio_workspace(confidence, ws, signals)
            reason = f"Matched PROJECT_MAP keyword: {token}"
            if risky:
                reason = f"{reason} (review required: risky/broad keyword)"
            decision = self._decision(
                category=category,
                workspace=ws,
                subfolder="",
                doc_type=_doc_type_from_category(category),
                confidence=confidence,
                matched_by=MATCH_PROJECT_MAP,
                reason=reason,
                ai_used=False,
                force_review=risky,
                broad_keyword_only_match=broad_only,
                case_study_candidate_hint=signals.case_study_candidate,
                portfolio_candidate_hint=signals.portfolio_candidate,
            )
            self._log.debug(
                "classified by project map",
                extra={"file_id": rec.id, "matched_by": decision.matched_by, "review_required": decision.review_required},
            )
            return decision

        # 5. DOC_TYPE_PATTERNS
        doc_type_hit = _first_doc_type_pattern(haystack, normalized_haystack, self._config.doc_type_patterns)
        if doc_type_hit is not None:
            pattern, token = doc_type_hit
            category = pattern.category or _category_from_doc_type(pattern.doc_type)
            workspace = self._resolve_workspace(
                category=category,
                suggested_workspace=pattern.workspace,
                current_workspace=rec.workspace,
            )
            subfolder = (pattern.subfolder or "").strip()
            risky = self._is_risky_match(token)
            broad_only = self._map_key_is_broad_only(token)
            base_conf = self._rule_confidence(MATCH_PATTERN, self._rule_confidence(MATCH_PROJECT_MAP, 0.85))
            confidence = self._risky_confidence(base_conf) if risky else base_conf
            confidence = _boost_confidence_for_portfolio_workspace(confidence, workspace, signals)
            reason = pattern.reason or f"Matched DOC_TYPE_PATTERNS keyword: {token}"
            if risky:
                reason = f"{reason} (review required: risky/broad keyword)"
            decision = self._decision(
                category=category,
                workspace=workspace,
                subfolder=subfolder,
                doc_type=pattern.doc_type,
                confidence=confidence,
                matched_by=MATCH_PATTERN,
                reason=reason,
                ai_used=False,
                force_review=risky,
                broad_keyword_only_match=broad_only,
                case_study_candidate_hint=signals.case_study_candidate,
                portfolio_candidate_hint=signals.portfolio_candidate,
            )
            self._log.debug(
                "classified by doc type pattern",
                extra={"file_id": rec.id, "matched_by": decision.matched_by, "review_required": decision.review_required},
            )
            return decision

        # 6. CODE_EXT (file-type pattern)
        # Guardrail: generic markdown extensions should not auto-route to wiki here.
        # They should flow through small-file lane / relevance gate / fallback unless
        # explicit FORCE/MAP/PATTERN rules matched earlier.
        if extension and extension in self._config.code_ext:
            category = self._config.code_ext[extension]
            if category == "markdown":
                category = ""
            if not category:
                pass
            else:
                ws = self._resolve_workspace(category=category, current_workspace=rec.workspace)
                decision = self._decision(
                    category=category,
                    workspace=ws,
                    subfolder="code",
                    doc_type=_doc_type_from_category(category),
                    confidence=_boost_confidence_for_portfolio_workspace(self._rule_confidence(MATCH_PATTERN, 0.75), ws, signals),
                    matched_by=MATCH_PATTERN,
                    reason=f"Matched CODE_EXT extension: {extension}",
                    ai_used=False,
                    case_study_candidate_hint=signals.case_study_candidate,
                    portfolio_candidate_hint=signals.portfolio_candidate,
                )
                self._log.debug(
                    "classified by extension",
                    extra={"file_id": rec.id, "matched_by": decision.matched_by, "review_required": decision.review_required},
                )
                return decision

        # Small-file lane: low-context fragments are routed to wiki for lightweight reference.
        if text_sample.strip() and small_file and relevance_score < self._config.relevance_min_score:
            return self._decision(
                category="markdown",
                workspace="wiki",
                subfolder="fragments",
                doc_type="note",
                confidence=self._rule_confidence(MATCH_PATTERN, 0.75),
                matched_by=MATCH_PATTERN,
                reason=(
                    f"Small-file lane: low-context fragment "
                    f"(chars<{self._config.small_file_char_threshold}, relevance={relevance_score}) routed to wiki."
                ),
                ai_used=False,
                case_study_candidate_hint=False,
                portfolio_candidate_hint=False,
            )

        # Relevance gate: full-size low-signal docs are held for review instead of auto-routing.
        if text_sample.strip() and relevance_score < self._config.relevance_min_score:
            return self._decision(
                category="other",
                workspace=None,
                subfolder="review",
                doc_type="misc",
                confidence=self._rule_confidence(MATCH_FALLBACK, 0.40),
                matched_by=MATCH_FALLBACK,
                reason=(
                    f"Relevance gate: score {relevance_score} below minimum "
                    f"{self._config.relevance_min_score}; held for review."
                ),
                ai_used=False,
                case_study_candidate_hint=signals.case_study_candidate,
                portfolio_candidate_hint=signals.portfolio_candidate,
            )

        # 7. Fallback — no automatic wiki; unassigned until rules or review
        decision = self._decision(
            category="other",
            workspace=None,
            subfolder="review",
            doc_type="misc",
            confidence=self._rule_confidence(MATCH_FALLBACK, 0.40),
            matched_by=MATCH_FALLBACK,
            reason=(
                "No FORCE_RULES, COMPANY_MAP, PROJECT_MAP, CODE_EXT, or DOC_TYPE_PATTERNS match; "
                "no workspace assigned (fallback)."
            ),
            ai_used=False,
            case_study_candidate_hint=signals.case_study_candidate,
            portfolio_candidate_hint=signals.portfolio_candidate,
        )
        self._log.debug(
            "classified by fallback",
            extra={"file_id": rec.id, "matched_by": decision.matched_by, "review_required": decision.review_required},
        )
        return decision

    def make_decision(
        self,
        *,
        category: str,
        workspace: str | None,
        subfolder: str,
        doc_type: str = "",
        confidence: float,
        matched_by: str,
        reason: str,
        ai_used: bool,
        force_review: bool = False,
        broad_keyword_only_match: bool = False,
        case_study_candidate_hint: bool = False,
        portfolio_candidate_hint: bool = False,
    ) -> ClassificationDecision:
        return self._decision(
            category=category,
            workspace=workspace,
            subfolder=subfolder,
            doc_type=doc_type,
            confidence=confidence,
            matched_by=matched_by,
            reason=reason,
            ai_used=ai_used,
            force_review=force_review,
            broad_keyword_only_match=broad_keyword_only_match,
            case_study_candidate_hint=case_study_candidate_hint,
            portfolio_candidate_hint=portfolio_candidate_hint,
        )

    def _workspace_for_category(self, category: str) -> str | None:
        c = category.strip()
        ws = self._config.workspaces.get(c)
        if ws:
            return ws
        return None

    def _resolve_workspace(
        self,
        *,
        category: str,
        suggested_workspace: str | None = None,
        current_workspace: str | None = None,
    ) -> str | None:
        if self._config.auto_assign_workspace:
            if suggested_workspace and suggested_workspace.strip():
                return suggested_workspace.strip()
            return self._workspace_for_category(category)
        if current_workspace and str(current_workspace).strip():
            return str(current_workspace).strip()
        return None

    def _decision(
        self,
        *,
        category: str,
        workspace: str | None,
        subfolder: str,
        doc_type: str,
        confidence: float,
        matched_by: str,
        reason: str,
        ai_used: bool,
        force_review: bool = False,
        broad_keyword_only_match: bool = False,
        case_study_candidate_hint: bool = False,
        portfolio_candidate_hint: bool = False,
    ) -> ClassificationDecision:
        c = category.strip() or "other"
        threshold = self._config.review_confidence_threshold
        raw_ws = (workspace or "").strip() or None
        if raw_ws is None and matched_by != MATCH_FALLBACK and self._config.auto_assign_workspace:
            raw_ws = self._workspace_for_category(c)

        low_confidence = confidence < threshold
        clear_workspace = (
            matched_by == MATCH_FALLBACK or low_confidence or broad_keyword_only_match
        )

        if clear_workspace:
            final_ws: str | None = None
        else:
            final_ws = raw_ws

        reason_out = reason
        if low_confidence and matched_by != MATCH_FALLBACK:
            reason_out = (
                f"{reason} (confidence {confidence:.3f} below threshold {threshold:.3f}; "
                "workspace not auto-assigned until review)"
            )
        if broad_keyword_only_match and matched_by != MATCH_FALLBACK:
            reason_out = (
                f"{reason_out} (broad keyword alone; workspace not auto-assigned until review)"
            )

        if matched_by == MATCH_FALLBACK:
            review_required = True
        else:
            review_required = low_confidence or broad_keyword_only_match
        if force_review and self._config.broad_match_force_review:
            review_required = True

        return ClassificationDecision(
            category=c,
            workspace=final_ws,
            subfolder=subfolder.strip(),
            doc_type=doc_type.strip() or _doc_type_from_category(c),
            confidence=round(confidence, 3),
            matched_by=matched_by,
            classification_reason=reason_out,
            review_required=review_required,
            case_study_candidate=_is_case_study_candidate(c, doc_type, reason_out) or bool(case_study_candidate_hint),
            portfolio_candidate=_is_portfolio_candidate(c, doc_type, reason_out) or bool(portfolio_candidate_hint),
            ai_used=ai_used,
        )

    def _is_risky_match(self, token: str) -> bool:
        t = token.strip().lower()
        if not t:
            return False
        if len(t) <= 3:
            return True
        return t in self._risky_terms

    def _map_key_is_broad_only(self, key: str) -> bool:
        """True when the rule/map key is a single broad token (multi-word keys are never broad-only)."""
        parts = _normalize_text(key.strip().lower()).split()
        if len(parts) != 1:
            return False
        return parts[0] in self._broad_terms

    @staticmethod
    def _risky_confidence(base: float) -> float:
        return max(0.40, round(base - 0.35, 3))

    def _rule_confidence(self, key: str, default: float) -> float:
        rc = self._config.rule_confidence
        if key == MATCH_PATTERN:
            if "pattern" in rc:
                return float(rc["pattern"])
            return float(rc.get("code_ext", rc.get("doc_type_pattern", default)))
        return float(rc.get(key, default))

    def ollama_default_confidence(self) -> float:
        return clamp_ollama_confidence(self._rule_confidence("ollama", 0.72))


def _phrase_first_sort_key(label: str) -> tuple[int, int, str]:
    """Sort key: multi-word phrases before single tokens; then longer labels first."""
    t = label.strip().lower()
    parts = _normalize_text(t).split()
    tier = 1 if len(parts) < 2 else 0
    return (tier, -len(t), t)


def _sort_rules_phrase_first(rules: tuple[ForceRule, ...]) -> tuple[ForceRule, ...]:
    return tuple(sorted(rules, key=lambda r: _phrase_first_sort_key(r.contains)))


def _ordered_map_pairs(mapping: dict[str, str]) -> list[tuple[str, str]]:
    items = [(k, v) for k, v in mapping.items() if str(k).strip()]
    items.sort(key=lambda kv: _phrase_first_sort_key(kv[0]))
    return items


def _first_category_match(
    haystack: str,
    normalized_haystack: str,
    mapping: dict[str, str],
) -> tuple[str, str] | None:
    """Deterministic match: phrase keys before single-token keys; then longer keys first within each tier."""
    for token, category in _ordered_map_pairs(mapping):
        if _contains_match(haystack=haystack, normalized_haystack=normalized_haystack, token=token):
            return (category, token)
    return None


def _first_doc_type_pattern(
    haystack: str,
    normalized_haystack: str,
    patterns: tuple[DocTypePattern, ...],
) -> tuple[DocTypePattern, str] | None:
    ordered = sorted(patterns, key=lambda p: _phrase_first_sort_key(p.contains))
    for pattern in ordered:
        token = pattern.contains.strip().lower()
        if token and _contains_match(haystack=haystack, normalized_haystack=normalized_haystack, token=token):
            return (pattern, token)
    return None


def _normalize_text(text: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", text.lower()).split())


def _contains_match(*, haystack: str, normalized_haystack: str, token: str) -> bool:
    t = token.strip().lower()
    if not t:
        return False
    if t in haystack:
        return True
    normalized_token = _normalize_text(t)
    return bool(normalized_token) and normalized_token in normalized_haystack


def _doc_type_from_category(category: str) -> str:
    c = category.strip().lower()
    if c == "portfolio":
        return "portfolio"
    if c == "case_studies":
        return "case_study"
    if c == "archive":
        return "reference"
    if c == "ai_project":
        return "project_doc"
    if c == "markdown":
        return "note"
    return "misc"


def _category_from_doc_type(doc_type: str) -> str:
    d = doc_type.strip().lower()
    if d in {"case_study", "case-study"}:
        return "case_studies"
    if d in {"portfolio", "resume", "cv"}:
        return "portfolio"
    if d in {"reference", "manual", "policy"}:
        return "archive"
    if d in {"project_doc", "spec", "design_doc"}:
        return "ai_project"
    return "other"


def _is_case_study_candidate(category: str, doc_type: str, reason: str) -> bool:
    text = f"{category} {doc_type} {reason}".lower()
    return "case_stud" in text or "migration" in text


def _is_portfolio_candidate(category: str, doc_type: str, reason: str) -> bool:
    text = f"{category} {doc_type} {reason}".lower()
    return "portfolio" in text or "resume" in text or "cv" in text


@dataclass(frozen=True, slots=True)
class _ContentSignals:
    has_metrics: bool
    has_action_verbs: bool
    has_business_context: bool
    case_study_candidate: bool
    portfolio_candidate: bool


_METRICS_RE = re.compile(
    r"(\b\d{1,3}\s*%|\$\s?\d[\d,]*(?:\.\d+)?|\broi\b|\bpipeline\b|\bgrowth\b)",
    re.IGNORECASE,
)
_ACTION_VERBS_RE = re.compile(
    r"\b(built|launched|led|designed|implemented|shipped|delivered|optimized|improved|automated)\b",
    re.IGNORECASE,
)
_BUSINESS_CTX_RE = re.compile(
    r"\b(campaign|abm|pipeline|revenue|customer|stakeholder|go[\s-]?to[\s-]?market|gtm|conversion|retention)\b",
    re.IGNORECASE,
)


def _detect_content_signals(sample: str) -> _ContentSignals:
    has_metrics = bool(_METRICS_RE.search(sample))
    has_action_verbs = bool(_ACTION_VERBS_RE.search(sample))
    has_business = bool(_BUSINESS_CTX_RE.search(sample))

    # Case studies usually have business context + impact/metrics; portfolio snippets need verbs + some context.
    case_study_candidate = has_business and (has_metrics or has_action_verbs)
    portfolio_candidate = has_action_verbs and (has_metrics or has_business)
    return _ContentSignals(
        has_metrics=has_metrics,
        has_action_verbs=has_action_verbs,
        has_business_context=has_business,
        case_study_candidate=case_study_candidate,
        portfolio_candidate=portfolio_candidate,
    )


_RELEVANCE_PATTERNS: tuple[str, ...] = (
    r"\b(case study|customer story|success story|campaign|abm)\b",
    r"\b(revenue|pipeline|roi|growth|conversion|retention)\b",
    r"\b(project|implementation|launch|roadmap|strategy|playbook)\b",
    r"\b(crm platform|cloud platform|enterprise platform|customer platform)\b",
    r"\b(react|typescript|next\.?js|python|llm|rag|agentic)\b",
)


def _relevance_score(*, haystack: str, text_sample: str, config: ClassificationConfig) -> int:
    combined = f"{haystack} {text_sample[:4000]}"
    normalized_combined = _normalize_text(combined)
    score = 0
    for pat in _RELEVANCE_PATTERNS:
        if re.search(pat, combined, re.IGNORECASE):
            score += 1
    dynamic_tokens: set[str] = set()
    dynamic_tokens.update(str(k).strip().lower() for k in config.company_map.keys())
    dynamic_tokens.update(str(k).strip().lower() for k in config.project_map.keys())
    dynamic_tokens.update(rule.contains.strip().lower() for rule in config.force_rules)
    for token in dynamic_tokens:
        if token and _contains_match(haystack=combined.lower(), normalized_haystack=normalized_combined, token=token):
            score += 1
    if _METRICS_RE.search(combined):
        score += 1
    if _ACTION_VERBS_RE.search(combined):
        score += 1
    return score


def _boost_confidence_for_portfolio_workspace(conf: float, workspace: str | None, signals: _ContentSignals) -> float:
    """Light boost for likely portfolio-ready content when routing to portfolio workspace."""
    ws = (workspace or "").strip()
    if ws != "career_portfolio":
        return conf
    if not (signals.has_action_verbs and (signals.has_metrics or signals.has_business_context)):
        return conf
    return min(0.99, round(conf + 0.03, 3))
