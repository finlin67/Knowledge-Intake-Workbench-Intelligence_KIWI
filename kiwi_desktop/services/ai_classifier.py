"""Optional AI-based classification adapters."""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True, slots=True)
class AIClassificationResult:
    workspace: str | None
    subfolder: str
    doc_type: str
    confidence: float
    reasoning: str


class AIClassifier(Protocol):
    def classify(
        self,
        *,
        file_path: Path,
        file_name: str,
        preview_text: str,
        use_content_preview: bool = True,
    ) -> AIClassificationResult | None:
        """Return AI classification, or None when no usable result is available."""


class NullAIClassifier:
    __slots__ = ()

    def classify(self, *, file_path: Path, file_name: str, preview_text: str) -> AIClassificationResult | None:
        del file_path, file_name, preview_text
        return None


class OllamaAIClassifier:
    __slots__ = ("_model", "_base_url", "_timeout_s")

    def __init__(self, *, model: str, base_url: str = "http://127.0.0.1:11434", timeout_s: float = 15.0) -> None:
        self._model = model.strip() or "llama3.2:3b"
        self._base_url = base_url.rstrip("/")
        self._timeout_s = timeout_s

    def classify(
        self,
        *,
        file_path: Path,
        file_name: str,
        preview_text: str,
        use_content_preview: bool = True,
    ) -> AIClassificationResult | None:
        del use_content_preview
        fast = _filename_signals(file_name)
        if fast is not None:
            return AIClassificationResult(
                workspace=fast["workspace"],
                subfolder=fast.get("subfolder", ""),
                doc_type=fast.get("doc_type", "misc"),
                confidence=fast["confidence"],
                reasoning=fast["reasoning"],
            )
        # Schema enforcement: strict JSON only, validated, with a single retry on schema failure.
        last_error: str | None = None
        for attempt in range(2):
            if use_content_preview:
                prompt = _build_prompt(
                    file_path=file_path,
                    file_name=file_name,
                    preview_text=preview_text,
                    last_error=last_error,
                )
            else:
                prompt = _build_prompt_no_content(
                    file_path=file_path,
                    file_name=file_name,
                    last_error=last_error,
                )
            payload = {
                "model": self._model,
                "prompt": prompt,
                "stream": False,
                "format": "json",
                "options": {"temperature": 0},
            }
            body = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                f"{self._base_url}/api/generate",
                data=body,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=self._timeout_s) as resp:
                    raw = resp.read().decode("utf-8")
            except (TimeoutError, urllib.error.URLError, urllib.error.HTTPError):
                return None
            try:
                outer = json.loads(raw)
            except json.JSONDecodeError:
                return None
            llm_response = outer.get("response")
            if not isinstance(llm_response, str) or not llm_response.strip():
                return None
            try:
                parsed = json.loads(llm_response)
            except json.JSONDecodeError:
                last_error = "Response was not valid JSON."
                continue
            result = _parse_result(parsed)
            if result is not None:
                return result
            last_error = "Response did not match required schema."
        return None

    def test_connection(self) -> tuple[bool, str]:
        payload = {"model": self._model}
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{self._base_url}/api/show",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self._timeout_s) as resp:
                raw = resp.read().decode("utf-8")
        except TimeoutError:
            return (False, "Ollama request timed out.")
        except urllib.error.HTTPError as exc:
            return (False, f"Ollama HTTP error: {exc.code}")
        except urllib.error.URLError as exc:
            return (False, f"Ollama connection failed: {exc.reason}")

        try:
            _parsed = json.loads(raw) if raw.strip() else {}
        except json.JSONDecodeError:
            return (False, "Ollama returned invalid JSON.")
        return (True, f"Ollama reachable ({self._model}).")

    def list_models(self) -> tuple[bool, tuple[str, ...], str]:
        req = urllib.request.Request(
            f"{self._base_url}/api/tags",
            headers={"Content-Type": "application/json"},
            method="GET",
        )
        try:
            with urllib.request.urlopen(req, timeout=self._timeout_s) as resp:
                raw = resp.read().decode("utf-8")
        except TimeoutError:
            return (False, tuple(), "Ollama model list request timed out.")
        except urllib.error.HTTPError as exc:
            return (False, tuple(), f"Ollama HTTP error while listing models: {exc.code}")
        except urllib.error.URLError as exc:
            return (False, tuple(), f"Ollama connection failed while listing models: {exc.reason}")

        try:
            payload = json.loads(raw) if raw.strip() else {}
        except json.JSONDecodeError:
            return (False, tuple(), "Ollama returned invalid JSON for model list.")
        models_raw = payload.get("models")
        if not isinstance(models_raw, list):
            return (False, tuple(), "Ollama response did not include a valid model list.")
        names: list[str] = []
        for item in models_raw:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name", "")).strip()
            if name:
                names.append(name)
        unique = tuple(sorted(set(names)))
        if not unique:
            return (True, tuple(), "Connected to Ollama, but no local models were found.")
        return (True, unique, f"Loaded {len(unique)} Ollama model(s).")


class ClaudeAIClassifier:
    __slots__ = ("_model", "_api_key", "_timeout_s")

    def __init__(self, *, model: str, api_key: str, timeout_s: float = 15.0) -> None:
        self._model = model.strip() or "claude-sonnet-4-5"
        self._api_key = api_key.strip()
        self._timeout_s = timeout_s

    def classify(
        self,
        *,
        file_path: Path,
        file_name: str,
        preview_text: str,
        use_content_preview: bool = True,
    ) -> AIClassificationResult | None:
        del file_path
        if not self._api_key:
            return None
        try:
            import anthropic
        except ImportError:
            return None

        client = anthropic.Anthropic(api_key=self._api_key, timeout=self._timeout_s)
        prompt = _build_cloud_prompt(file_name=file_name, preview_text=preview_text, use_content_preview=use_content_preview)
        message = client.messages.create(
            model=self._model,
            max_tokens=250,
            messages=[{"role": "user", "content": prompt}],
        )
        content = message.content
        if not isinstance(content, list) or not content:
            return None
        text = getattr(content[0], "text", "")
        parsed = _extract_json_dict(str(text or ""))
        if parsed is None:
            return None
        return _parse_cloud_result(parsed)


class OpenAIClassifier:
    __slots__ = ("_model", "_api_key", "_timeout_s")

    def __init__(self, *, model: str, api_key: str, timeout_s: float = 15.0) -> None:
        self._model = model.strip() or "gpt-4o"
        self._api_key = api_key.strip()
        self._timeout_s = timeout_s

    def classify(
        self,
        *,
        file_path: Path,
        file_name: str,
        preview_text: str,
        use_content_preview: bool = True,
    ) -> AIClassificationResult | None:
        del file_path
        if not self._api_key:
            return None
        try:
            import openai
        except ImportError:
            return None

        client = openai.OpenAI(api_key=self._api_key, timeout=self._timeout_s)
        prompt = _build_cloud_prompt(file_name=file_name, preview_text=preview_text, use_content_preview=use_content_preview)
        response = client.chat.completions.create(
            model=self._model,
            max_tokens=250,
            messages=[{"role": "user", "content": prompt}],
        )
        if not response.choices:
            return None
        text = response.choices[0].message.content
        parsed = _extract_json_dict(str(text or ""))
        if parsed is None:
            return None
        return _parse_cloud_result(parsed)


_ALLOWED_OLLAMA_WORKSPACES: tuple[str, ...] = (
    "Career_Portfolio",
    "Case_Studies",
    "AI_Projects",
    "Archive",
    "Reference",
    "Wiki",
)
_AI_CONFIDENCE_THRESHOLD = 0.70
_REQUIRED_KEYS: tuple[str, ...] = ("workspace", "subfolder", "doc_type", "confidence", "reasoning")
_FILENAME_SIGNAL_CONFIDENCE = 0.82
_DISCARD_SIGNAL_CONFIDENCE = 0.30

_PORTFOLIO_SIGNALS: tuple[str, ...] = (
    "resume",
    "cover_letter",
    "linkedin",
    "achievement",
    "accomplishment",
    "executive_bio",
    "professional_bio",
    "curriculum_vitae",
)
_AI_PROJECT_SIGNALS: tuple[str, ...] = (
    "main_project",
    "side_project",
    "internal_tooling",
    "automation_suite",
    "project_planner",
    "project-planner",
    "anythingllm",
    "open_webui",
    "ollama_",
)
_ARCHIVE_SIGNALS: tuple[str, ...] = (
    "acme_corp",
    "enterprise_client",
    "previous_employer",
    "vendor_docs",
    "partner_material",
    "client_archive",
)
_CASE_STUDY_SIGNALS: tuple[str, ...] = (
    "case_study",
    "case-study",
    "success_story",
    "pipeline_report",
    "metrics_report",
)
_DISCARD_LITERAL_SIGNALS: tuple[str, ...] = (
    "untitled",
    "new_document",
    "lorem_ipsum",
    "screenshot",
    "temp_",
    "_copy_final",
    "test_doc",
)
_DISCARD_REGEX_SIGNALS: tuple[re.Pattern[str], ...] = (re.compile(r"draft_\d"),)


def _filename_signals(file_name: str) -> dict | None:
    """
    Check if filename alone contains enough signal to classify without reading content.
    Returns a dict with workspace/subfolder/doc_type/confidence/reasoning if confident, else None.
    """
    name = str(file_name or "").strip().lower()
    if not name:
        return None

    matched_groups: list[tuple[str, str]] = []

    def _first_match(keywords: tuple[str, ...]) -> str | None:
        for kw in keywords:
            if kw in name:
                return kw
        return None

    portfolio = _first_match(_PORTFOLIO_SIGNALS)
    if portfolio is not None:
        matched_groups.append(("portfolio", portfolio))
    ai_project = _first_match(_AI_PROJECT_SIGNALS)
    if ai_project is not None:
        matched_groups.append(("ai_project", ai_project))
    archive = _first_match(_ARCHIVE_SIGNALS)
    if archive is not None:
        matched_groups.append(("archive", archive))
    case_study = _first_match(_CASE_STUDY_SIGNALS)
    if case_study is not None:
        matched_groups.append(("case_study", case_study))

    discard_kw = _first_match(_DISCARD_LITERAL_SIGNALS)
    if discard_kw is None:
        for rx in _DISCARD_REGEX_SIGNALS:
            if rx.search(name):
                discard_kw = rx.pattern
                break
    if discard_kw is not None:
        matched_groups.append(("discard", discard_kw))

    if len(matched_groups) != 1:
        return None
    group, keyword = matched_groups[0]
    if group == "portfolio":
        return {
            "workspace": "Career_Portfolio",
            "subfolder": "",
            "doc_type": "portfolio",
            "confidence": _FILENAME_SIGNAL_CONFIDENCE,
            "reasoning": f"filename_signal: {keyword}",
        }
    if group == "ai_project":
        return {
            "workspace": "AI_Projects",
            "subfolder": "",
            "doc_type": "project_doc",
            "confidence": _FILENAME_SIGNAL_CONFIDENCE,
            "reasoning": f"filename_signal: {keyword}",
        }
    if group == "archive":
        return {
            "workspace": "Archive",
            "subfolder": "",
            "doc_type": "reference",
            "confidence": _FILENAME_SIGNAL_CONFIDENCE,
            "reasoning": f"filename_signal: {keyword}",
        }
    if group == "case_study":
        return {
            "workspace": "Case_Studies",
            "subfolder": "",
            "doc_type": "case_study",
            "confidence": _FILENAME_SIGNAL_CONFIDENCE,
            "reasoning": f"filename_signal: {keyword}",
        }
    return {
        "workspace": None,
        "subfolder": "",
        "doc_type": "misc",
        "confidence": _DISCARD_SIGNAL_CONFIDENCE,
        "reasoning": f"filename_signal: {keyword}",
    }


def _build_prompt(*, file_path: Path, file_name: str, preview_text: str, last_error: str | None) -> str:
    error_hint = f"Previous output was invalid: {last_error}\n" if last_error else ""
    return (
        "Classify this local file for a knowledge intake pipeline.\n"
        f"{error_hint}"
        "Return ONLY a strict JSON object (no markdown, no explanation text).\n"
        f"Required keys (exactly these): {', '.join(_REQUIRED_KEYS)}.\n"
        f"workspace must be one of: {', '.join(_ALLOWED_OLLAMA_WORKSPACES)}, or null.\n"
        "subfolder must be a string (\"\" allowed).\n"
        "doc_type must be a short string (e.g. portfolio, case_study, project_doc, reference, note, misc).\n"
        "confidence must be a number between 0 and 1.\n"
        f"If uncertain, set workspace=null AND set confidence < {_AI_CONFIDENCE_THRESHOLD:.2f}.\n"
        f"file_name: {file_name}\n"
        f"file_path: {file_path}\n"
        f"preview_text: {preview_text[:1200]}\n"
    )


def _build_prompt_no_content(*, file_path: Path, file_name: str, last_error: str | None) -> str:
    error_hint = f"Previous output was invalid: {last_error}\n" if last_error else ""
    return (
        "Classify this local file for a knowledge intake pipeline.\n"
        f"{error_hint}"
        "Return ONLY a strict JSON object (no markdown, no explanation text).\n"
        f"Required keys (exactly these): {', '.join(_REQUIRED_KEYS)}.\n"
        f"workspace must be one of: {', '.join(_ALLOWED_OLLAMA_WORKSPACES)}, or null.\n"
        "subfolder must be a string (\"\" allowed).\n"
        "doc_type must be a short string (e.g. portfolio, case_study, project_doc, reference, note, misc).\n"
        "confidence must be a number between 0 and 1.\n"
        f"If uncertain, set workspace=null AND set confidence < {_AI_CONFIDENCE_THRESHOLD:.2f}.\n"
        f"file_name: {file_name}\n"
        f"file_path: {file_path}\n"
        "preview_text: [not provided]\n"
    )


def _parse_result(value: object) -> AIClassificationResult | None:
    if not isinstance(value, dict):
        return None
    if set(value.keys()) != set(_REQUIRED_KEYS):
        return None

    raw_workspace = value.get("workspace")
    if raw_workspace is None:
        workspace: str | None = None
    elif isinstance(raw_workspace, str):
        ws = raw_workspace.strip()
        if ws not in _ALLOWED_OLLAMA_WORKSPACES:
            return None
        workspace = ws
    else:
        return None

    subfolder = str(value.get("subfolder", "")).strip()
    doc_type = str(value.get("doc_type", "")).strip()
    reasoning = str(value.get("reasoning", "")).strip()
    if not doc_type or not reasoning:
        return None
    try:
        confidence = float(value.get("confidence", 0.0))
    except (TypeError, ValueError):
        return None
    if confidence < 0.0:
        confidence = 0.0
    if confidence > 1.0:
        confidence = 1.0
    # If model claims "uncertain", enforce confidence below threshold.
    if workspace is None and confidence >= _AI_CONFIDENCE_THRESHOLD:
        return None
    return AIClassificationResult(
        workspace=workspace,
        subfolder=subfolder,
        doc_type=doc_type,
        confidence=confidence,
        reasoning=reasoning,
    )


def _build_cloud_prompt(*, file_name: str, preview_text: str, use_content_preview: bool) -> str:
    preview = preview_text[:1200] if use_content_preview else "[not provided]"
    return (
        "Classify this document into a workspace category.\n"
        "Return ONLY JSON and no extra text.\n"
        "Preferred JSON schema: "
        '{"workspace": "Career_Portfolio|Case_Studies|AI_Projects|Archive|Reference|Wiki|null", '
        '"subfolder": "", "doc_type": "misc", "confidence": 0.0, "reasoning": "brief reason"}.\n'
        "Backward-compatible schema also accepted: "
        '{"workspace": "...", "confidence": 0.0, "reasoning": "brief reason"}.\n'
        f"Filename: {file_name}\n"
        f"Content preview: {preview}\n"
    )


def _extract_json_dict(text: str) -> dict[str, object] | None:
    raw = text.strip()
    if not raw:
        return None
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", raw, flags=re.DOTALL)
    if match is None:
        return None
    try:
        parsed = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _parse_cloud_result(value: dict[str, object]) -> AIClassificationResult | None:
    if set(value.keys()) == set(_REQUIRED_KEYS):
        return _parse_result(value)

    raw_workspace = value.get("workspace")
    if raw_workspace is None:
        workspace: str | None = None
    else:
        ws = str(raw_workspace).strip()
        workspace = ws if ws in _ALLOWED_OLLAMA_WORKSPACES else None

    subfolder = str(value.get("subfolder", "")).strip()
    doc_type = str(value.get("doc_type", "misc")).strip() or "misc"
    reasoning = str(value.get("reasoning", "")).strip()
    if not reasoning:
        return None
    try:
        confidence = float(value.get("confidence", 0.0))
    except (TypeError, ValueError):
        return None
    confidence = max(0.0, min(1.0, confidence))
    if workspace is None and confidence >= _AI_CONFIDENCE_THRESHOLD:
        confidence = min(confidence, _AI_CONFIDENCE_THRESHOLD - 0.01)

    return AIClassificationResult(
        workspace=workspace,
        subfolder=subfolder,
        doc_type=doc_type,
        confidence=confidence,
        reasoning=reasoning,
    )
