-- Knowledge Intake Workbench — SQLite schema
-- files: resumable per-file pipeline stage + opaque checkpoint for resume tokens.

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    path TEXT NOT NULL UNIQUE,
    filename TEXT,
    extension TEXT,
    file_created_at TEXT,
    file_modified_at TEXT,
    display_name TEXT,
    size_bytes INTEGER,
    sha256 TEXT,
    mime_type TEXT,
    current_stage TEXT NOT NULL DEFAULT 'pending'
        CHECK (length(trim(current_stage)) > 0),
    stage_checkpoint TEXT,
    pipeline_version INTEGER NOT NULL DEFAULT 1 CHECK (pipeline_version >= 1),
    stage_attempt INTEGER NOT NULL DEFAULT 0 CHECK (stage_attempt >= 0),
    last_error TEXT,
    runner_status TEXT NOT NULL DEFAULT 'new'
        CHECK (runner_status IN ('new', 'processing', 'completed', 'failed')),
    pipeline_next_stage TEXT DEFAULT 'classified',
    runner_status_anythingllm TEXT NOT NULL DEFAULT 'new'
        CHECK (runner_status_anythingllm IN ('new', 'processing', 'completed', 'failed')),
    pipeline_next_stage_anythingllm TEXT DEFAULT 'classified',
    runner_status_open_webui TEXT NOT NULL DEFAULT 'new'
        CHECK (runner_status_open_webui IN ('new', 'processing', 'completed', 'failed')),
    pipeline_next_stage_open_webui TEXT DEFAULT 'classified',
    workspace TEXT NOT NULL DEFAULT '',
    subfolder TEXT,
    matched_by TEXT,
    classification_reason TEXT,
    review_required INTEGER NOT NULL DEFAULT 0,
    ai_used INTEGER NOT NULL DEFAULT 0,
    content_hash TEXT,
    confidence REAL,
    case_study_candidate INTEGER NOT NULL DEFAULT 0,
    portfolio_candidate INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_files_current_stage ON files (current_stage);
CREATE INDEX IF NOT EXISTS idx_files_updated_at ON files (updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_files_extension ON files (extension);
CREATE INDEX IF NOT EXISTS idx_files_runner ON files (runner_status, id);
CREATE INDEX IF NOT EXISTS idx_files_workspace ON files (workspace);

CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT NOT NULL CHECK (length(trim(kind)) > 0),
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'running', 'completed', 'failed', 'cancelled')),
    priority INTEGER NOT NULL DEFAULT 0,
    payload_json TEXT,
    result_json TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    started_at TEXT,
    completed_at TEXT,
    error_message TEXT
);

CREATE INDEX IF NOT EXISTS idx_jobs_status_priority ON jobs (status, priority DESC, id);
CREATE INDEX IF NOT EXISTS idx_jobs_kind ON jobs (kind);

CREATE TABLE IF NOT EXISTS outputs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id INTEGER NOT NULL,
    job_id INTEGER,
    kind TEXT NOT NULL CHECK (length(trim(kind)) > 0),
    storage_path TEXT,
    content_hash TEXT,
    meta_json TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (file_id) REFERENCES files (id) ON DELETE CASCADE,
    FOREIGN KEY (job_id) REFERENCES jobs (id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_outputs_file_id ON outputs (file_id);
CREATE INDEX IF NOT EXISTS idx_outputs_job_id ON outputs (job_id);
CREATE INDEX IF NOT EXISTS idx_outputs_kind ON outputs (kind);
