"""Well-known pipeline and job enumerations (stored as TEXT in SQLite)."""

from __future__ import annotations

from enum import StrEnum


class FileStage(StrEnum):
    """Per-file pipeline stage; resume via ``stage_checkpoint`` JSON on ``files``."""

    PENDING = "pending"
    DISCOVERED = "discovered"
    HASHING = "hashing"
    EXTRACTING = "extracting"
    INDEXING = "indexing"
    COMPLETED = "completed"
    FAILED = "failed"


class JobStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobKind(StrEnum):
    """Example job kinds; extend as the workbench grows."""

    SCAN = "scan"
    INGEST_BATCH = "ingest_batch"
    REINDEX = "reindex"
    PIPELINE_RUN = "pipeline_run"


class RunnerStatus(StrEnum):
    """Per-file runner queue state (resume selection)."""

    NEW = "new"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class PipelineStage(StrEnum):
    """Ordered intake pipeline; ``pipeline_next_stage`` is the stage to execute next."""

    CLASSIFIED = "classified"
    NORMALIZED = "normalized"
    CHUNKED = "chunked"
    EXPORTED = "exported"
