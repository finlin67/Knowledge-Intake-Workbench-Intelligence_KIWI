# KIWI — Knowledge Intake Workbench Intelligence: Developer Guide

**Version:** 0.1.x  
**Stack:** Python 3.11+, PySide6, SQLite, Typer  
**Purpose:** Desktop/CLI tool for capturing, classifying, normalizing, and exporting local knowledge files for downstream RAG/LLM systems.

---

## Table of Contents

1. [Why KIWI Exists](#1-why-kiwi-exists)
2. [What KIWI Does](#2-what-kiwi-does)
3. [Project Structure](#3-project-structure)
4. [Technology Stack](#4-technology-stack)
5. [Architecture Overview](#5-architecture-overview)
6. [The Processing Pipeline](#6-the-processing-pipeline)
7. [Classification System](#7-classification-system)
8. [Database Schema](#8-database-schema)
9. [GUI Layer](#9-gui-layer)
10. [CLI Layer](#10-cli-layer)
11. [Configuration & Environment](#11-configuration--environment)
12. [Testing](#12-testing)
13. [Key Design Decisions](#13-key-design-decisions)
14. [Where to Start as a Developer](#14-where-to-start-as-a-developer)

---

## 1. Why KIWI Exists

Modern RAG (Retrieval-Augmented Generation) pipelines require clean, consistently structured knowledge files. In practice, the raw material — PDFs, Word documents, PowerPoint decks, markdown notes, code files — is messy, inconsistently named, and scattered across folders.

KIWI solves the **intake problem**: it sits at the front of the pipeline and transforms a raw folder of files into organized, normalized markdown documents that tools like AnythingLLM or Open WebUI can ingest directly.

The core needs it addresses:

- **Organization** — automatically classify files into workspaces and subfolders based on configurable rules
- **Normalization** — convert any supported file type (PDF, DOCX, PPTX, plain text, code) into clean markdown with YAML frontmatter
- **Auditability** — flag low-confidence or ambiguous files for human review before they enter the pipeline
- **Resumability** — long runs over large file sets can be paused, resumed, or retried without reprocessing completed files
- **Dual-target export** — export in the exact folder layout expected by different downstream tools

---

## 2. What KIWI Does

At a high level, KIWI takes a **raw folder** of files and produces an **output folder** of clean, organized markdown:

```
Raw Folder (messy)                    Output Folder (clean)
────────────────                      ─────────────────────
docs/                                 exports/
  Q3_report_final_v2.pdf    →           anythingllm/
  acme_proposal.docx        →             finance/Q3_report_final_v2.md
  random_notes.txt          →             proposals/acme_proposal.md
  script.py                 →           open_webui/
  ...                                     projects/code/script.md
                                          ...
```

The pipeline stages for each file are:

1. **Scan** — walk the filesystem, compute SHA256 hash, extract metadata, register in database
2. **Classify** — apply rule-based classification to assign workspace, subfolder, and confidence score
3. **Normalize** — convert source file to clean markdown with YAML frontmatter
4. **Chunk** — split normalized content into word-count-bounded paragraphs for chunked indexing
5. **Export** — write final markdown to the correct folder layout for the target platform

All state is persisted in a project-local SQLite database so the pipeline is fully resumable.

---

## 3. Project Structure

```
KIWI/
├── main.py                    # Entry point — dispatches to CLI or GUI
├── pyproject.toml             # Package metadata; defines `kiw` script entry point
├── requirements.txt           # Runtime dependencies
├── .env.example               # Optional environment variable reference
│
├── cli/
│   └── app.py                 # Typer CLI commands (init, add, scan, run, list, gui)
│
├── gui/
│   ├── app.py                 # Qt application lifecycle (QApplication setup)
│   ├── main_window.py         # Main tabbed window controller
│   ├── setup_wizard.py        # Project creation/loading dialog (shown on startup)
│   ├── controllers.py         # Tab-level business logic (Inventory, Review, Run, etc.)
│   ├── widgets.py             # Reusable UI components (tables, status bars, buttons)
│   ├── theme.py               # Qt stylesheet definitions
│   └── triage_tab.py          # Classification review/audit interface
│
├── db/
│   ├── session.py             # SQLite connection lifecycle (WAL, row_factory)
│   ├── schema.sql             # DDL — files, jobs, outputs tables
│   ├── migrations.py          # Schema version tracking and upgrade path
│   └── repositories/
│       ├── file_repository.py # CRUD for file records, stage transitions, runner queues
│       └── job_repository.py  # CRUD for background job records
│
├── models/
│   ├── enums.py               # FileStage, JobStatus, PipelineStage, RunnerStatus
│   ├── file_record.py         # FileRecord dataclass (frozen)
│   ├── job_record.py          # JobRecord dataclass (frozen)
│   ├── output_record.py       # OutputRecord dataclass (frozen)
│   ├── classification_patch.py # Partial update payload for classification fields
│   └── triage_derivation.py   # View-model for triage queue rows
│
├── services/
│   ├── scan_service.py             # Recursive FS walk, hashing, metadata, upsert
│   ├── classification_service.py   # Deterministic rule-based classifier
│   ├── classification_config.py    # Config model, defaults, JSON loader
│   ├── ai_classifier.py            # Ollama integration + NullAIClassifier stub
│   ├── intake_service.py           # Façade used by CLI (register, list files)
│   ├── normalizer_service.py       # Source → markdown + YAML frontmatter
│   ├── chunking_service.py         # Paragraph-based chunking
│   ├── exporter_service.py         # Profile-based export (AnythingLLM / Open WebUI)
│   ├── pipeline_runner.py          # Orchestrates all pipeline stages
│   ├── project_service.py          # Project creation/loading (.kiw/project.json)
│   ├── inventory_service.py        # File inventory queries and filtering
│   ├── inventory_filter.py         # Filter predicate helpers
│   ├── review_service.py           # Audit queue (failed, review-required, fallback)
│   ├── run_monitor_service.py      # Live pipeline progress and log capture
│   └── data/
│       └── classification_rules_seed.json  # Default classification rules
│
├── utils/
│   ├── file_readers.py        # extract_text_sample — reads PDF, PPTX, DOCX, text
│   ├── logging_utils.py       # JSON-line structured logging setup
│   ├── paths.py               # OS-appropriate data/work directory resolution
│   └── console.py             # Rich console singleton for CLI output
│
└── tests/
    └── test_*.py              # Pytest unit and integration tests
```

---

## 4. Technology Stack

| Layer | Library | Notes |
|---|---|---|
| Language | Python 3.11+ | Uses match/case, tomllib, frozen dataclasses |
| CLI | [Typer](https://typer.tiangolo.com/) | Modern Click wrapper; auto-generates `--help` |
| GUI | [PySide6](https://doc.qt.io/qtforpython-6/) | Qt6 Python bindings; tabbed MDI-style desktop app |
| Database | SQLite3 (stdlib) | WAL mode, busy timeout; no ORM |
| PDF extraction | [PyMuPDF](https://pymupdf.readthedocs.io/) (`fitz`) | Text extraction from PDF pages |
| Word/PPTX | python-docx, python-pptx | Paragraph and slide text extraction |
| YAML | PyYAML | Frontmatter generation |
| AI (optional) | [Ollama](https://ollama.ai/) HTTP API | Local LLM inference; disabled by default |
| Console output | [Rich](https://rich.readthedocs.io/) | Formatted CLI output and progress |
| Packaging | setuptools + pyproject.toml | PEP 518; `kiw` script entry point |

---

## 5. Architecture Overview

KIWI uses a **layered architecture** with strict dependency direction: GUI/CLI → Services → Repositories → Database.

```
┌──────────────────────────────────────────┐
│  Entry Points                            │
│   main.py  →  cli/app.py  |  gui/app.py  │
└──────────────────┬───────────────────────┘
                   │
┌──────────────────▼───────────────────────┐
│  Services (stateless business logic)     │
│   ScanService, ClassificationService,   │
│   PipelineRunner, ExporterService, ...  │
└──────────────────┬───────────────────────┘
                   │
┌──────────────────▼───────────────────────┐
│  Repositories (data access objects)      │
│   FileRepository, JobRepository         │
└──────────────────┬───────────────────────┘
                   │
┌──────────────────▼───────────────────────┐
│  Database (SQLite + WAL)                 │
│   .kiw/state.sqlite3                    │
└──────────────────────────────────────────┘
```

**Key design principle:** Services have no knowledge of the GUI or CLI. Controllers in the GUI layer call services directly; the CLI does the same. This makes the processing logic fully testable and headlessly operable.

### Project Isolation

Each KIWI project is self-contained in a chosen output folder:

```
<output_folder>/
  .kiw/
    project.json               # { name, raw_folder, output_folder, db_path }
    state.sqlite3              # SQLite database (WAL mode)
    classification_rules.json  # Per-project classification config
  normalized/                  # Intermediate normalized markdown files
  exports/
    anythingllm/<workspace>/   # Flat layout for AnythingLLM
    open_webui/<workspace>/<subfolder>/  # Hierarchical layout for Open WebUI
  files_manifest.csv
  chunks_manifest.json
```

Multiple projects can coexist on the same machine; each has its own database.

---

## 6. The Processing Pipeline

Each file moves through a state machine. States are persisted in the database so the pipeline is resumable after a crash or intentional pause.

### State Machine

```
pending → discovered → hashing → extracting → indexing → completed
                                                        ↘ failed
```

At the runner level, each file also has per-export-profile state:

```
runner_status: new → processing → completed
                              ↘ failed (retryable)

pipeline_next_stage: classified → normalized → chunked → exported
```

### Stage Details

**Stage 1: Scan (`ScanService`)**

- Recursively walks the raw folder
- Filters by supported extensions (whitelist in config)
- Computes SHA256 hash for deduplication
- Extracts metadata: size, MIME type, creation/modified timestamps
- Upserts into `files` table (path is the unique key — re-scanning is idempotent)

**Stage 2: Classify (`ClassificationService`)**

- Reads a text sample from the file (first ~2000 chars via `extract_text_sample`)
- Applies rules in deterministic priority order (see [Classification System](#7-classification-system))
- Writes: `workspace`, `subfolder`, `matched_by`, `classification_reason`, `confidence`, `review_required`
- Sets `pipeline_next_stage = 'normalized'`

**Stage 3: Normalize (`FirstPassNormalizer`)**

- Converts source file to clean markdown:
  - `.md` / `.txt`: read as UTF-8, strip any existing frontmatter
  - `.json`: pretty-print inside a code fence
  - `.pdf`: extract text per-page with PyMuPDF
  - `.docx`: extract paragraphs with python-docx
  - `.pptx`: extract slide text with python-pptx
- Infers a title (first H1 heading, or filename)
- Prepends YAML frontmatter: `title`, `source_file`, `source_path`, `category`
- Writes to `<output>/.kiw/normalized/<file_id>_<safe_stem>.md`
- Sets `pipeline_next_stage = 'chunked'`

**Stage 4: Chunk (`ParagraphChunker`)**

- Reads normalized markdown
- Splits on blank lines → paragraph blocks
- Groups blocks until target word count is reached (default: 220 words)
- Stores chunk metadata for traceability
- Sets `pipeline_next_stage = 'exported'`

**Stage 5: Export (`ExporterService`)**

- Writes final markdown to export folder based on profile:
  - **anythingllm**: `exports/anythingllm/<workspace>/<filename>.md` (flat)
  - **open_webui**: `exports/open_webui/<workspace>/<subfolder>/<filename>.md` (hierarchical)
- Handles filename collisions (rename / overwrite / skip policy)
- Writes `files_manifest.csv` and `chunks_manifest.json`
- Sets `runner_status = 'completed'`

### PipelineRunner

`services/pipeline_runner.py` is the orchestrator. It:

1. Queries for the next file with `runner_status = 'new'` for the active profile
2. Calls each stage service in sequence
3. Writes a checkpoint to the database after each stage
4. Sets `runner_status = 'failed'` and records `last_error` on any exception
5. Loops until no more files are pending or a stop signal is received

The GUI run monitor calls `PipelineRunner.run()` in a background thread and polls `RunMonitorService` for live progress counts.

---

## 7. Classification System

Classification is the most configurable part of KIWI. It is entirely **rule-based and deterministic** by default, with an optional Ollama AI fallback.

### Rule Evaluation Order

Rules are checked in this priority sequence and the **first match wins**:

| Priority | Rule Type | Description |
|---|---|---|
| 1 | `FORCE_RULES` | Explicit phrase matches — highest confidence (0.96) |
| 2 | `NEGATIVE_RULES` | Exclusion patterns — skip classification |
| 3 | `COMPANY_MAP` | Organization name → category lookup (0.90) |
| 4 | `PROJECT_MAP` | Project name → category lookup (0.85) |
| 5 | `DOC_TYPE_PATTERNS` | Regex on filename and/or content (0.75) |
| 6 | `CODE_EXT` | File extension → category (0.90) |
| 7 | AI (Ollama) | Optional LLM fallback if enabled (0.60–0.85) |
| 8 | FALLBACK | Unassigned + `review_required = True` (0.40) |

### Review Flags

A file is flagged `review_required = True` if:

- It hits the FALLBACK rule (nothing matched)
- It matched a **risky keyword** (e.g., "doc", "file", "project" — intentionally generic terms)
- It matched a **broad-only keyword** (single-word generic match)
- Its confidence score is below the configured threshold

Flagged files appear in the Review tab in the GUI and are held out of automatic export until approved.

### Configuration File

Classification is configured per-project at `.kiw/classification_rules.json`. It is seeded from `services/data/classification_rules_seed.json` on project creation and can be edited by hand or through the GUI's Settings tab.

Key fields:

```json
{
  "WORKSPACES": { "category_name": "folder_name" },
  "FORCE_RULES": [
    { "contains": "curriculum vitae", "category": "portfolio", "workspace": "career_portfolio", "subfolder": "resumes", "reason": "CV keyword" }
  ],
  "COMPANY_MAP": { "acme_corp": "archive" },
  "PROJECT_MAP": { "agentic": "ai_project" },
  "DOC_TYPE_PATTERNS": [
    { "pattern": "case_study", "field": "filename", "category": "case_studies" }
  ],
  "CODE_EXT": { ".py": "ai_project", ".ipynb": "ai_project" },
  "RULE_CONFIDENCE": { "force": 0.96, "company_map": 0.90 },
  "RISKY_MATCH_TERMS": ["doc", "file", "project"],
  "enable_ollama": false,
  "ollama_model": "mistral",
  "ai_mode": "ai_only_unclassified"
}
```

### Ollama AI Classifier

When `enable_ollama = true`, `OllamaAIClassifier` is used as a fallback. It sends the file's text sample and filename to a locally-running Ollama instance and parses the response. AI confidence is clamped to the `0.60–0.85` band. If Ollama is unreachable, it falls back gracefully to `NullAIClassifier` (which always returns no classification).

---

## 8. Database Schema

The database lives at `.kiw/state.sqlite3` (WAL mode, `busy_timeout = 2000ms`).

### Required-table guard (important)

Recent hardening added a required-table validation pass in `db/session.py`.

- `connect()` now verifies required tables exist even if the DB path was already cached as initialized.
- If required tables are missing (for example, after a partial DB recreation), schema creation/migrations are re-applied.
- `project_service.py` calls this validation during project create/load and raises a runtime error if the schema is still invalid.

This prevents a class of failures where the DB file exists but queue operations fail because core tables were never created.

### `files` Table

The central table. Every scanned file has exactly one row.

```sql
CREATE TABLE files (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    path                  TEXT UNIQUE NOT NULL,       -- absolute path
    filename              TEXT NOT NULL,
    extension             TEXT,
    size_bytes            INTEGER,
    sha256                TEXT,
    mime_type             TEXT,
    file_created_at       TEXT,                       -- UTC ISO-8601
    file_modified_at      TEXT,

    -- Pipeline state machine
    current_stage         TEXT DEFAULT 'pending',     -- FileStage enum
    stage_checkpoint      TEXT,                       -- opaque JSON resume token
    pipeline_version      INTEGER DEFAULT 1,
    stage_attempt         INTEGER DEFAULT 0,
    last_error            TEXT,

    -- Per-profile runner state (anythingllm + open_webui columns duplicated)
    runner_status                      TEXT DEFAULT 'new',
    pipeline_next_stage                TEXT,
    runner_status_anythingllm          TEXT DEFAULT 'new',
    pipeline_next_stage_anythingllm    TEXT,
    runner_status_open_webui           TEXT DEFAULT 'new',
    pipeline_next_stage_open_webui     TEXT,

    -- Classification results
    workspace             TEXT,
    subfolder             TEXT,
    matched_by            TEXT,                       -- rule type that matched
    classification_reason TEXT,
    review_required       INTEGER DEFAULT 0,          -- boolean
    ai_used               INTEGER DEFAULT 0,
    confidence            REAL,                       -- 0.0–1.0

    -- Triage flags
    case_study_candidate  INTEGER DEFAULT 0,
    portfolio_candidate   INTEGER DEFAULT 0,

    created_at            TEXT DEFAULT (datetime('now')),
    updated_at            TEXT DEFAULT (datetime('now'))
);
```

Indexes exist on: `runner_status`, `pipeline_next_stage`, `workspace`, `updated_at`, `extension`.

### `jobs` Table

Background job records (scan runs, pipeline runs).

```sql
CREATE TABLE jobs (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    kind          TEXT NOT NULL,           -- scan|ingest_batch|pipeline_run|...
    status        TEXT DEFAULT 'pending',  -- pending|running|completed|failed|cancelled
    priority      INTEGER DEFAULT 0,
    payload_json  TEXT,
    result_json   TEXT,
    created_at    TEXT,
    started_at    TEXT,
    completed_at  TEXT,
    error_message TEXT
);
```

### `outputs` Table

Tracks generated artifacts per file (normalized markdown, chunks, exports).

```sql
CREATE TABLE outputs (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id       INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,
    job_id        INTEGER REFERENCES jobs(id),
    kind          TEXT,                    -- normalized|chunked|exported
    storage_path  TEXT,
    content_hash  TEXT,
    meta_json     TEXT,
    created_at    TEXT
);
```

### Repository Pattern

All database access goes through repository classes in `db/repositories/`. Direct SQL is written there — no ORM. Connections are managed by `db/session.py`, which sets WAL mode and row_factory on creation.

---

## 9. GUI Layer

The GUI is a PySide6 (Qt6) desktop application with a tabbed interface.

### Startup Flow

1. `main.py` → `gui/app.py` → creates `QApplication`
2. `SetupWizard` dialog is shown: user picks an existing project or creates a new one
3. On confirmation, `MainWindow` is opened with the selected project context

### Tab Structure (`main_window.py` + `controllers.py`)

| Tab | Controller | Purpose |
|---|---|---|
| Inventory | `InventoryController` | Browse all tracked files; filter by stage, workspace, extension |
| Review | `ReviewController` | Approve or retry files flagged `review_required` or `failed` |
| Run | `RunController` | Trigger pipeline runs; select export profile |
| Monitor | `RunMonitorController` | Live progress counters; pause/stop controls |
| Triage | `TriageTab` | Detailed classification audit — see matched_by, reason, confidence |
| Settings | `SettingsController` | Edit classification rules, Ollama config, project metadata |

### Threading Model

Pipeline runs execute in a `QThread` (or `threading.Thread`). The GUI polls `RunMonitorService` on a timer (`QTimer`) for progress updates. Results are passed back to the main thread via Qt signals. No direct SQLite access occurs on the main thread during a run — WAL mode ensures the GUI's read queries don't block the writer.

### Widgets (`widgets.py`)

Reusable components:
- `KiwiTable` — sortable/filterable QTableView with column definitions
- `StatusBar` — pipeline stage progress bars
- `ActionButton` — consistent styled QPushButton

### Theming (`theme.py`)

A single Qt stylesheet is applied at application startup. Colors and fonts are defined as constants. The theme is dark-by-default.

---

## 10. CLI Layer

The CLI is built with [Typer](https://typer.tiangolo.com/) and defined in `cli/app.py`. The `kiw` command is registered in `pyproject.toml`.

### Commands

```
kiw init     --output <folder>            # Create a new project
kiw scan     --db <path> <raw_folder>     # Scan and register files
kiw list     --db <path>                  # List tracked files
kiw run      --db <path>                  # Run the pipeline
             --max-files <n>
             --export-profile <profile>
kiw gui                                   # Launch the desktop GUI
```

All commands share the same service layer as the GUI — the CLI is just a different entry point, not a different implementation.

---

## 11. Configuration & Environment

### Environment Variables

Defined in `.env.example`. Loaded via `python-dotenv` if present.

| Variable | Default | Purpose |
|---|---|---|
| `OLLAMA_BASE_URL` | `http://127.0.0.1:11434` | Ollama API endpoint |
| `KIW_LOG_LEVEL` | `INFO` | Logging verbosity |

### OS-Aware Data Directory (`utils/paths.py`)

| Platform | Path |
|---|---|
| Windows | `%LOCALAPPDATA%\KnowledgeIntakeWorkbench` |
| Linux/macOS | `$XDG_DATA_HOME/KnowledgeIntakeWorkbench` or `~/.local/share/...` |

Logs are written to `<data_dir>/logs/app.log.jsonl`.

### Logging (`utils/logging_utils.py`)

JSON-line structured logging: one JSON object per line. Fields include `timestamp`, `level`, `logger`, `message`, and optional extras (`file_id`, `job_id`, `stage`). This format is easy to ship to log aggregators (Loki, CloudWatch, etc.) if needed.

---

## 12. Testing

Tests live in `tests/` and use `pytest`.

### Running Tests

```bash
pip install -r requirements.txt
pytest tests/
```

### Test Patterns

- **Classification tests**: pass file samples directly to `ClassificationService` with fixture configs; assert `matched_by`, `workspace`, `confidence`
- **Schema tests**: create in-memory SQLite DB from `schema.sql`; verify table structure
- **Schema guard tests**: verify required-table checks recover from missing-table states and fail fast when recovery is impossible
- **Normalization tests**: pass sample file paths; assert frontmatter and content structure
- **Export tests**: mock the exporter with a temp directory; verify output paths match profile layout
- **Scan tests**: use `tmp_path` fixtures with synthetic files

Integration tests use a real (in-memory) SQLite database — no mocking of the database layer.

---

## 13. Key Design Decisions

### 1. Local-First, No External Dependencies by Default

Everything runs offline. Ollama AI classification is opt-in. No cloud APIs are called. This makes KIWI viable in air-gapped environments and keeps the privacy footprint minimal.

### 2. Deterministic Classification Before AI

Rules are always evaluated first. The AI is a fallback of last resort. This means:
- Results are reproducible and auditable
- The rules file is the single source of truth for what goes where
- AI is only involved when rules genuinely can't decide

### 3. Resumable Pipeline via Database Checkpoints

Every stage transition writes to the database before moving on. If the process crashes mid-run, the next run picks up exactly where it left off — files already completed are skipped, files mid-stage retry from their last checkpoint.

### 4. Per-Profile Runner State Columns

Rather than a separate runs or exports table, each file row has dedicated `runner_status_*` and `pipeline_next_stage_*` columns per export profile. This lets a file be independently processed for AnythingLLM and Open WebUI without complex join logic, and makes the queue query trivial: `WHERE runner_status_anythingllm = 'new'`.

### 5. Review Queue as a First-Class Feature

Low-confidence and ambiguous files don't silently get exported — they're held in a review queue. This is intentional: the cost of a misclassified file in a RAG knowledge base is high (wrong context pollutes search results). The review step is the human-in-the-loop gate.

### 6. No ORM

All SQL is written by hand in repository classes. This keeps queries transparent, avoids migration complexity introduced by ORM tooling, and makes schema changes explicit via `db/schema.sql` and `db/migrations.py`.

### 7. GUI and CLI Share the Same Service Layer

The services know nothing about PySide6 or Typer. This is enforced structurally: `services/` has no imports from `gui/` or `cli/`. Both the GUI and CLI call services directly. Testing the business logic doesn't require spinning up a Qt application.

---

## 14. Where to Start as a Developer

If you're new to the codebase, here's a recommended reading order:

1. **[models/enums.py](models/enums.py)** — understand the states each file moves through
2. **[db/schema.sql](db/schema.sql)** — see the full data model in one place
3. **[services/scan_service.py](services/scan_service.py)** — simplest service; understand the pattern
4. **[services/classification_service.py](services/classification_service.py)** — core logic; most complex service
5. **[services/pipeline_runner.py](services/pipeline_runner.py)** — understand how stages are orchestrated
6. **[gui/main_window.py](gui/main_window.py)** — top-level GUI structure
7. **[gui/controllers.py](gui/controllers.py)** — how the GUI calls services

### Common Extension Points

| Task | Where to look |
|---|---|
| Add a new file type for normalization | `services/normalizer_service.py`, `utils/file_readers.py` |
| Add a new classification rule type | `services/classification_service.py`, `services/classification_config.py` |
| Add a new export profile | `services/exporter_service.py` |
| Add a new GUI tab | `gui/main_window.py`, `gui/controllers.py` |
| Add a new CLI command | `cli/app.py` |
| Change the database schema | `db/schema.sql`, `db/migrations.py`, `db/repositories/` |

### Web/API and Release Packaging

Current operator flow is primarily through the web app (`KIWI_Web`) backed by FastAPI (`kiwi_desktop/api`).

- Web setup and run state: `KIWI_Web/app/setup/page.tsx`
- Settings UI and AI save controls: `KIWI_Web/app/settings/page.tsx`
- API surface: `kiwi_desktop/api/routers/`
- Windows portable release workflow: `.github/workflows/windows-release.yml`

For release steps and tag-based packaging, see `../Support Documents/RELEASE_WINDOWS_GUIDE.md`.

### Running Locally

```bash
# Install dependencies
pip install -r requirements.txt

# Launch the GUI
python main.py gui

# Or use the installed entry point (after pip install -e .)
kiw gui

# Run the CLI pipeline headlessly
kiw init --output ./my_project
kiw scan ./raw_docs --db ./my_project/.kiw/state.sqlite3
kiw run --db ./my_project/.kiw/state.sqlite3 --export-profile anythingllm
```
