"""Resumable per-file pipeline runner (classified → normalized → chunked → exported)."""

from __future__ import annotations

import json
import hashlib
import traceback
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from db.repositories import FileRepository, JobRepository
from db.session import Database
from models.classification_patch import ClassificationFieldsPatch
from models.enums import JobKind, JobStatus, PipelineStage, RunnerStatus
from models.file_record import FileRecord
from services.chunking_service import ParagraphChunker
from services.classification_config import DEFAULT_CONFIG_FILENAME
from services.classification_config import load_classification_config
from services.classification_service import (
    MATCH_FALLBACK,
    MATCH_FORCE_RULE,
    MATCH_NEGATIVE_RULE,
    ClassificationDecision,
    ClassificationService,
    clamp_ollama_confidence,
)
from services.ai_classifier import AIClassifier, ClaudeAIClassifier, NullAIClassifier, OllamaAIClassifier, OpenAIClassifier
from services.exporter_service import (
    PROFILE_ANYTHINGLLM,
    PROFILE_OPEN_WEBUI,
    ExporterService,
)
from services.normalizer_service import FirstPassNormalizer
from utils.logging_utils import get_logger

PIPELINE_ORDER: tuple[PipelineStage, ...] = (
    PipelineStage.CLASSIFIED,
    PipelineStage.NORMALIZED,
    PipelineStage.CHUNKED,
    PipelineStage.EXPORTED,
)


def _optional_workspace_str(value: object) -> str | None:
    if value is None:
        return None
    s = str(value).strip()
    return s or None


def _export_workspace_value(rec_workspace: str | None, checkpoint_workspace: object) -> str:
    for candidate in (rec_workspace, checkpoint_workspace):
        ws = _optional_workspace_str(candidate)
        if ws:
            return ws
    return "unassigned"

_OLLAMA_WORKSPACE_TO_INTERNAL: dict[str, tuple[str, str]] = {
    # ollama enum -> (internal workspace, internal category)
    "Career_Portfolio": ("career_portfolio", "portfolio"),
    "Case_Studies": ("case_studies", "case_studies"),
    "AI_Projects": ("ai_projects", "ai_project"),
    "Archive": ("archive", "archive"),
    # "Reference" and "Wiki" both map to the same internal workspace folder name.
    "Reference": ("wiki", "other"),
    "Wiki": ("wiki", "other"),
}


def _category_from_doc_type(doc_type: str) -> str:
    d = (doc_type or "").strip().lower()
    if d in {"case_study", "case-study"}:
        return "case_studies"
    if d in {"portfolio", "resume", "cv"}:
        return "portfolio"
    if d in {"reference", "manual", "policy"}:
        return "archive"
    if d in {"project_doc", "spec", "design_doc"}:
        return "ai_project"
    if d in {"note"}:
        return "markdown"
    return "other"

def _next_pipeline_stage(after_completed: str) -> str | None:
    cur = PipelineStage(after_completed)
    idx = PIPELINE_ORDER.index(cur)
    if idx + 1 >= len(PIPELINE_ORDER):
        return None
    return PIPELINE_ORDER[idx + 1].value


def _run_stage_placeholder(_record: FileRecord, stage: PipelineStage) -> None:
    """Replace with real work; kept side-effect free for tests."""
    del _record, stage


STAGE_HANDLERS: dict[str, Callable[[FileRecord, PipelineStage], None]] = {
    PipelineStage.CLASSIFIED.value: _run_stage_placeholder,
    PipelineStage.NORMALIZED.value: _run_stage_placeholder,
    PipelineStage.CHUNKED.value: _run_stage_placeholder,
    PipelineStage.EXPORTED.value: _run_stage_placeholder,
}


@dataclass(frozen=True, slots=True)
class PipelineRunResult:
    job_id: int
    files_started: int
    files_finished_ok: int
    files_marked_failed: int


class PipelineRunner:
    """Processes eligible files one at a time; persists after each stage."""

    __slots__ = (
        "_db",
        "_files",
        "_jobs",
        "_normalizer",
        "_chunker",
        "_exporter",
        "_export_profile",
        "_classifier",
        "_ai_classifier",
        "_enable_ollama",
        "_ai_provider",
        "_ai_provider_enabled",
        "_ai_mode",
        "_log",
    )

    def __init__(
        self,
        database: Database,
        *,
        normalized_work_dir: Path | None = None,
        chunk_target_words: int = 220,
        min_chunk_words: int = 120,
        export_profile: str = PROFILE_ANYTHINGLLM,
        export_root: Path | None = None,
        classification_config_path: Path | None = None,
        ai_classifier: AIClassifier | None = None,
    ) -> None:
        self._db = database
        self._files = FileRepository(database)
        self._jobs = JobRepository(database)
        self._normalizer = FirstPassNormalizer(
            work_dir=normalized_work_dir,
        )
        self._chunker = ParagraphChunker(target_words=chunk_target_words, min_words=min_chunk_words)
        if export_profile not in {PROFILE_OPEN_WEBUI, PROFILE_ANYTHINGLLM}:
            raise ValueError(f"Unsupported export profile: {export_profile!r}")
        self._export_profile = export_profile
        config_path = classification_config_path
        if config_path is None and export_root is not None:
            config_path = export_root.parent / ".kiw" / DEFAULT_CONFIG_FILENAME
        config = load_classification_config(config_path)
        self._exporter = ExporterService(
            export_root=export_root,
            duplicate_filename_policy=config.duplicate_filename_policy,
        )
        self._classifier = ClassificationService(config)
        self._enable_ollama = config.enable_ollama
        self._ai_provider = (config.ai_provider or "ollama").strip().lower() or "ollama"
        self._ai_mode = config.ai_mode
        self._ai_provider_enabled = False
        if ai_classifier is not None:
            self._ai_classifier = ai_classifier
            self._ai_provider_enabled = True
        elif self._ai_provider == "claude" and config.api_key.strip():
            self._ai_classifier = ClaudeAIClassifier(model=config.cloud_model, api_key=config.api_key)
            self._ai_provider_enabled = True
        elif self._ai_provider == "openai" and config.api_key.strip():
            self._ai_classifier = OpenAIClassifier(model=config.cloud_model, api_key=config.api_key)
            self._ai_provider_enabled = True
        elif self._enable_ollama:
            self._ai_classifier = OllamaAIClassifier(model=config.ollama_model)
            self._ai_provider_enabled = True
        else:
            self._ai_classifier = NullAIClassifier()
        self._log = get_logger("kiw.pipeline")

    def run(self, *, max_files: int | None = None) -> PipelineRunResult:
        payload = json.dumps({"max_files": max_files})
        job = self._jobs.create(kind=JobKind.PIPELINE_RUN.value, payload_json=payload)
        self._jobs.update_status(job.id, status=JobStatus.RUNNING.value, mark_started=True)
        self._log.info("pipeline run started", extra={"job_id": job.id, "max_files": max_files})

        started = 0
        ok = 0
        failed = 0
        attempted: set[int] = set()

        try:
            while True:
                if max_files is not None and len(attempted) >= max_files:
                    break
                rec = self._files.next_for_runner(exclude_ids=attempted, export_profile=self._export_profile)
                if rec is None:
                    break
                attempted.add(rec.id)
                started += 1
                self._files.mark_runner_processing(rec.id, export_profile=self._export_profile)
                self._log.info(
                    "file started",
                    extra={
                        "job_id": job.id,
                        "file_id": rec.id,
                        "file_name": rec.filename or Path(rec.path).name,
                    },
                )
                if self._process_one_file(rec.id):
                    ok += 1
                    self._log.info(
                        "file completed",
                        extra={
                            "job_id": job.id,
                            "file_id": rec.id,
                            "status": RunnerStatus.COMPLETED.value,
                        },
                    )
                else:
                    failed += 1
                    self._log.warning(
                        "file completed with failure",
                        extra={
                            "job_id": job.id,
                            "file_id": rec.id,
                            "status": RunnerStatus.FAILED.value,
                        },
                    )
        finally:
            result = json.dumps(
                {
                    "files_started": started,
                    "files_finished_ok": ok,
                    "files_marked_failed": failed,
                }
            )
            self._jobs.update_status(
                job.id,
                status=JobStatus.COMPLETED.value,
                result_json=result,
                mark_completed=True,
            )
            self._log.info(
                "pipeline run completed",
                extra={"job_id": job.id, "files_started": started, "files_ok": ok, "files_failed": failed},
            )

        return PipelineRunResult(
            job_id=job.id,
            files_started=started,
            files_finished_ok=ok,
            files_marked_failed=failed,
        )

    def _process_one_file(self, file_id: int) -> bool:
        """Return True if the file ended in a completed (or empty) success path."""
        while True:
            rec = self._files.get_by_id(file_id)
            if rec is None:
                return True
            queue_status, stage_name = self._files.get_profile_queue_state(file_id, export_profile=self._export_profile)
            if queue_status == RunnerStatus.COMPLETED.value:
                return True
            if stage_name is None:
                self._files.commit_pipeline_stage_success(
                    file_id,
                    next_stage=None,
                    export_profile=self._export_profile,
                )
                return True

            try:
                stage = PipelineStage(stage_name)
            except ValueError:
                self._files.mark_runner_failed(
                    file_id,
                    f"Unknown pipeline stage: {stage_name!r}",
                    export_profile=self._export_profile,
                )
                self._log.error("unknown pipeline stage", extra={"file_id": file_id, "stage": stage_name})
                return False

            try:
                if stage == PipelineStage.NORMALIZED:
                    self._handle_normalized(rec, stage)
                elif stage == PipelineStage.CHUNKED:
                    self._handle_chunked(rec, stage)
                elif stage == PipelineStage.EXPORTED:
                    self._handle_exported(rec, stage)
                elif stage == PipelineStage.CLASSIFIED:
                    self._handle_classified(rec, stage)
                else:
                    handler = STAGE_HANDLERS.get(stage.value)
                    if handler is None:
                        self._files.mark_runner_failed(
                            file_id,
                            f"No handler for stage {stage.value!r}",
                            export_profile=self._export_profile,
                        )
                        self._log.error("missing stage handler", extra={"file_id": file_id, "stage": stage.value})
                        return False
                    handler(rec, stage)
            except Exception as e:  # noqa: BLE001 — per-file isolation
                tb = traceback.format_exc()
                self._files.mark_runner_failed(
                    file_id,
                    f"{type(e).__name__}: {e}\n{tb}",
                    export_profile=self._export_profile,
                )
                self._log.exception("file processing failed", extra={"file_id": file_id, "stage": stage.value})
                return False

            nxt = _next_pipeline_stage(stage.value)
            self._files.commit_pipeline_stage_success(
                file_id,
                next_stage=nxt,
                export_profile=self._export_profile,
            )
            if nxt is None:
                return True

    def _handle_normalized(self, rec: FileRecord, _stage: PipelineStage) -> None:
        checkpoint = self._checkpoint_payload(rec)
        out = self._normalizer.normalize(rec)
        category = checkpoint.get("category")
        if not isinstance(category, str) or not category.strip():
            category = out.category
        checkpoint.update(
            {
                "normalized_path": str(out.output_path),
                "title": out.title,
                "normalized_detected_category": out.category,
                "category": category,
            }
        )
        self._files.update_stage_checkpoint(
            rec.id,
            json.dumps(checkpoint, ensure_ascii=False),
        )

    def _handle_classified(self, rec: FileRecord, _stage: PipelineStage) -> None:
        checkpoint = self._checkpoint_payload(rec)
        decision = self._classifier.classify(rec)
        decision = self._maybe_apply_ai_classification(rec, decision)
        content_hash = self._content_hash_for_record(rec)
        self._log.info(
            "classification decided",
            extra={
                "file_id": rec.id,
                "matched_by": decision.matched_by,
                "confidence": decision.confidence,
                "review_required": decision.review_required,
                "ai_used": decision.ai_used,
            },
        )
        checkpoint["category"] = decision.category
        checkpoint["workspace"] = decision.workspace
        checkpoint["subfolder"] = decision.subfolder
        checkpoint["doc_type"] = decision.doc_type
        checkpoint["confidence"] = decision.confidence
        checkpoint["matched_by"] = decision.matched_by
        checkpoint["classification_reason"] = decision.classification_reason
        checkpoint["review_required"] = decision.review_required
        checkpoint["case_study_candidate"] = decision.case_study_candidate
        checkpoint["portfolio_candidate"] = decision.portfolio_candidate
        checkpoint["ai_used"] = decision.ai_used
        patch: ClassificationFieldsPatch = {
            "workspace": decision.workspace,
            "subfolder": decision.subfolder or None,
            "matched_by": decision.matched_by,
            "classification_reason": decision.classification_reason,
            "content_hash": content_hash,
            "confidence": decision.confidence,
            "case_study_candidate": decision.case_study_candidate,
            "portfolio_candidate": decision.portfolio_candidate,
        }
        self._files.update_classification_fields(rec.id, patch)
        self._files.set_review_required(rec.id, decision.review_required)
        self._files.set_ai_used(rec.id, decision.ai_used)
        handler = STAGE_HANDLERS.get(PipelineStage.CLASSIFIED.value)
        if handler is not None:
            handler(rec, PipelineStage.CLASSIFIED)
        self._files.update_stage_checkpoint(rec.id, json.dumps(checkpoint, ensure_ascii=False))

    def _maybe_apply_ai_classification(
        self,
        rec: FileRecord,
        rules_decision: ClassificationDecision,
    ) -> ClassificationDecision:
        if not self._ai_provider_enabled:
            return rules_decision
        if self._ai_mode == "rules_only":
            return rules_decision
        if rules_decision.matched_by in (MATCH_FORCE_RULE, MATCH_NEGATIVE_RULE):
            return rules_decision
        if self._ai_mode == "ai_only_unclassified" and rules_decision.matched_by != MATCH_FALLBACK:
            return rules_decision

        content_hash = self._content_hash_for_record(rec)
        if content_hash:
            cached = self._files.get_cached_ollama_classification(content_hash=content_hash)
            if cached is not None:
                cached_conf = float(cached["confidence"])
                if cached_conf <= 0.0:
                    cached_conf = self._classifier.ollama_default_confidence()
                else:
                    cached_conf = clamp_ollama_confidence(cached_conf)
                return self._classifier.make_decision(
                    category=str(cached["category"]),
                    workspace=_optional_workspace_str(cached.get("workspace")),
                    subfolder=str(cached.get("subfolder") or ""),
                    confidence=cached_conf,
                    matched_by="ollama",
                    reason=f"Ollama cached: {cached['reason']}",
                    ai_used=True,
                )

        try:
            preview = self._preview_text(Path(rec.path))
            ai_result = self._ai_classifier.classify(
                file_path=Path(rec.path),
                file_name=rec.filename or Path(rec.path).name,
                preview_text=preview,
            )
        except Exception:  # noqa: BLE001
            self._log.exception("ai classification failed", extra={"file_id": rec.id, "provider": self._ai_provider})
            return rules_decision
        if ai_result is None:
            self._log.warning(
                "ai provider returned no usable classification; using rules result",
                extra={"file_id": rec.id, "rules_matched_by": rules_decision.matched_by, "provider": self._ai_provider},
            )
            return rules_decision
        ai_conf = float(ai_result.confidence)
        if ai_conf <= 0.0:
            ai_conf = self._classifier.ollama_default_confidence()
        else:
            ai_conf = clamp_ollama_confidence(ai_conf)
        if ai_result.workspace is None:
            internal_ws: str | None = None
            category = rules_decision.category
        else:
            mapped = _OLLAMA_WORKSPACE_TO_INTERNAL.get(str(ai_result.workspace).strip())
            if mapped is None:
                return rules_decision
            internal_ws, category = mapped
            category = _category_from_doc_type(ai_result.doc_type) or category
        return self._classifier.make_decision(
            category=category,
            workspace=internal_ws,
            subfolder=ai_result.subfolder,
            doc_type=ai_result.doc_type,
            confidence=ai_conf,
            matched_by="ollama",
            reason=f"{self._ai_provider_label()}: {ai_result.reasoning}",
            ai_used=True,
        )

    def _ai_provider_label(self) -> str:
        if self._ai_provider == "claude":
            return "Claude"
        if self._ai_provider == "openai":
            return "OpenAI"
        return "Ollama"

    def _handle_chunked(self, rec: FileRecord, _stage: PipelineStage) -> None:
        checkpoint = self._checkpoint_payload(rec)
        normalized_path = checkpoint.get("normalized_path")
        if not isinstance(normalized_path, str) or not normalized_path:
            raise ValueError("stage_checkpoint missing normalized_path for chunked stage")
        result = self._chunker.chunk_markdown_file(Path(normalized_path))
        checkpoint["chunks"] = list(result.chunks)
        checkpoint["chunk_metadata"] = [
            {
                "chunk_index": m.chunk_index,
                "estimated_word_count": m.estimated_word_count,
            }
            for m in result.metadata
        ]
        checkpoint["chunk_count"] = len(result.chunks)
        self._files.update_stage_checkpoint(
            rec.id,
            json.dumps(checkpoint, ensure_ascii=False),
        )

    def _handle_exported(self, rec: FileRecord, _stage: PipelineStage) -> None:
        checkpoint = self._checkpoint_payload(rec)
        normalized_path = checkpoint.get("normalized_path")
        category = checkpoint.get("category")
        chunks = checkpoint.get("chunks")
        chunk_meta = checkpoint.get("chunk_metadata")
        if not isinstance(normalized_path, str) or not normalized_path:
            raise ValueError("stage_checkpoint missing normalized_path for exported stage")
        if not isinstance(category, str) or not category:
            category = "unknown"
        if not isinstance(chunks, list):
            chunks = []
        if not isinstance(chunk_meta, list):
            chunk_meta = []

        source_file = rec.filename or Path(rec.path).name
        result = self._exporter.export(
            profile=self._export_profile,
            source_id=rec.id,
            source_file=source_file,
            source_path=rec.path,
            category=category,
            workspace=_export_workspace_value(rec.workspace, checkpoint.get("workspace")),
            subfolder=str(rec.subfolder or checkpoint.get("subfolder") or ""),
            matched_by=str(rec.matched_by or checkpoint.get("matched_by") or ""),
            confidence=float(checkpoint.get("confidence", 0.0) or 0.0),
            normalized_path=normalized_path,
            chunks=[str(c) for c in chunks],
            chunk_metadata=[m for m in chunk_meta if isinstance(m, dict)],
        )

        checkpoint["export_profile"] = result.profile
        checkpoint["export_root"] = str(result.profile_root)
        checkpoint["export_source_path"] = str(result.source_export_path)
        checkpoint["export_chunk_paths"] = [str(p) for p in result.chunk_export_paths]
        self._files.update_stage_checkpoint(
            rec.id,
            json.dumps(checkpoint, ensure_ascii=False),
        )

    @staticmethod
    def _checkpoint_payload(rec: FileRecord) -> dict[str, object]:
        if not rec.stage_checkpoint:
            return {}
        try:
            raw = json.loads(rec.stage_checkpoint)
        except json.JSONDecodeError:
            return {}
        return raw if isinstance(raw, dict) else {}

    @staticmethod
    def _preview_text(path: Path) -> str:
        try:
            return path.read_text(encoding="utf-8", errors="ignore")[:4000]
        except OSError:
            return ""

    @staticmethod
    def _content_hash_for_record(rec: FileRecord) -> str | None:
        if rec.content_hash:
            return rec.content_hash
        if rec.sha256:
            return rec.sha256
        path = Path(rec.path)
        if not path.is_file():
            return None
        try:
            data = path.read_bytes()
        except OSError:
            return None
        return hashlib.sha256(data).hexdigest()


def set_stage_handler(stage: PipelineStage, fn: Callable[[FileRecord, PipelineStage], None]) -> None:
    """Override stage behavior (e.g. in tests)."""
    STAGE_HANDLERS[stage.value] = fn


def reset_pipeline_handlers() -> None:
    """Restore default no-op handlers (use after tests that patch ``STAGE_HANDLERS``)."""
    for s in PIPELINE_ORDER:
        STAGE_HANDLERS[s.value] = _run_stage_placeholder
