"""Derive triage-only fields from ``FileRecord`` rows (no DB columns)."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

from models.file_record import FileRecord

_RULE_GAP_MATCHED_BY = frozenset({"company_map", "project_map", "pattern"})
_AI_FILENAME_MARKERS = ("grok", "claude", "chatgpt", "perplexity")
_PDF_CHUNK_RE = re.compile(r"\.pdf.*\d+\.md$", re.IGNORECASE)
_CATEGORY_TO_WORKSPACE = {
    "portfolio": "career_portfolio",
    "ai_project": "ai_projects",
    "archive": "archive",
    "case_studies": "case_studies",
    "markdown": "wiki",
}


def is_unassigned_workspace(workspace: str | None) -> bool:
    if workspace is None:
        return True
    s = str(workspace).strip()
    return s == "" or s.lower() == "unassigned"


def derive_priority(rec: FileRecord) -> str:
    sz = rec.size_bytes if rec.size_bytes is not None else 0
    conf = rec.confidence
    mb = (rec.matched_by or "").strip()
    if rec.review_required and sz > 3000:
        return "High"
    if sz < 500 or (mb == "fallback" and conf is not None and conf < 0.45):
        return "Low"
    return "Medium"


def derive_reason(rec: FileRecord) -> str:
    """Return rule_gap | ai_session | pdf_chunk | noise | needs_review | other."""
    name = (rec.filename or rec.display_name or rec.path or "").lower()
    sz = rec.size_bytes if rec.size_bytes is not None else 0
    mb = (rec.matched_by or "").strip()

    if sz < 500:
        return "noise"
    if mb == "ollama" or any(m in name for m in _AI_FILENAME_MARKERS):
        return "ai_session"
    if _PDF_CHUNK_RE.search(rec.filename or "") or _PDF_CHUNK_RE.search(rec.path or ""):
        return "pdf_chunk"
    if mb in _RULE_GAP_MATCHED_BY:
        return "rule_gap"
    if mb == "fallback":
        return "needs_review"
    return "other"


def _subfolder_signal(sub: str | None) -> str | None:
    if sub is None:
        return None
    s = str(sub).strip()
    if not s:
        return None
    low = s.lower()
    if low in {"review", "none"}:
        return None
    return s


def _top_keyword_from_reason(reason: str | None) -> str:
    if not reason:
        return ""
    raw = str(reason).strip()
    if not raw:
        return ""
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            for key in ("keyword", "token", "match", "reason"):
                v = parsed.get(key)
                if isinstance(v, str) and v.strip():
                    return v.strip()[:40]
    except json.JSONDecodeError:
        pass
    parts = re.split(r"[^\w\-]+", raw, maxsplit=1)
    token = parts[0] if parts else raw
    token = token.strip()
    if not token:
        return raw[:40]
    return token[:40]


def derive_signals(rec: FileRecord) -> str:
    sf = _subfolder_signal(rec.subfolder)
    if sf:
        return sf
    return _top_keyword_from_reason(rec.classification_reason)


def derive_suggested_workspace(rec: FileRecord) -> str:
    """Checkpoint / classification hint when the row is still unassigned."""
    if rec.stage_checkpoint:
        try:
            payload = json.loads(rec.stage_checkpoint)
        except json.JSONDecodeError:
            payload = None
        if isinstance(payload, dict):
            for key in ("suggested_workspace", "workspace", "predicted_workspace"):
                v = payload.get(key)
                if isinstance(v, str):
                    t = v.strip()
                    if t and t.lower() != "unassigned":
                        return t
            cat = payload.get("category")
            if isinstance(cat, str) and cat.strip():
                mapped = _CATEGORY_TO_WORKSPACE.get(cat.strip())
                if mapped:
                    return mapped
    reason = rec.classification_reason or ""
    if reason.strip().startswith("{"):
        try:
            payload = json.loads(reason)
            if isinstance(payload, dict):
                for key in ("suggested_workspace", "workspace"):
                    v = payload.get(key)
                    if isinstance(v, str) and v.strip():
                        return v.strip()
        except json.JSONDecodeError:
            pass
    mb = (rec.matched_by or "").strip()
    if mb in _RULE_GAP_MATCHED_BY:
        return "-"
    return "-"


@dataclass(frozen=True, slots=True)
class UnassignedTriageRow:
    """One unassigned / review-adjacent file with derived triage fields."""

    file_id: int
    path: str
    filename: str
    matched_by: str | None
    suggested_workspace: str
    priority: str
    reason: str
    signals: str
    size_bytes: int | None
    record: FileRecord


def build_unassigned_triage_row(rec: FileRecord) -> UnassignedTriageRow:
    name = rec.filename or rec.display_name or ""
    return UnassignedTriageRow(
        file_id=rec.id,
        path=rec.path,
        filename=name or rec.path,
        matched_by=rec.matched_by,
        suggested_workspace=derive_suggested_workspace(rec),
        priority=derive_priority(rec),
        reason=derive_reason(rec),
        signals=derive_signals(rec),
        size_bytes=rec.size_bytes,
        record=rec,
    )


def is_ai_session_row(r: UnassignedTriageRow) -> bool:
    """Filename markers or Ollama classification (card metric / filter)."""
    name = (r.filename or "").lower()
    if (r.record.matched_by or "").strip() == "ollama":
        return True
    return any(m in name for m in _AI_FILENAME_MARKERS)


def summary_counts(rows: tuple[UnassignedTriageRow, ...]) -> tuple[int, int, int, int, int]:
    """Totals, rule gaps, high priority, AI sessions, safe to skip."""
    total = len(rows)
    rule_gaps = sum(1 for r in rows if r.reason == "rule_gap")
    high_pri = sum(
        1
        for r in rows
        if r.record.review_required and (r.record.size_bytes or 0) > 3000
    )
    ai_sessions = sum(1 for r in rows if is_ai_session_row(r))
    safe = 0
    for r in rows:
        sz = r.record.size_bytes if r.record.size_bytes is not None else 0
        conf = r.record.confidence
        mb = (r.record.matched_by or "").strip()
        if sz < 500 or (mb == "fallback" and conf is not None and conf < 0.45):
            safe += 1
    return total, rule_gaps, high_pri, ai_sessions, safe
