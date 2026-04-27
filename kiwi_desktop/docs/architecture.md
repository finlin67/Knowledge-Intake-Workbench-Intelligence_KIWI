# Architecture (stub)

Knowledge Intake Workbench uses a thin layered layout:

- **CLI (`cli/`)** — Typer commands and Rich presentation; no business rules beyond argument parsing.
- **Services (`services/`)** — Use cases (create/list items) orchestrating the database.
- **Models (`models/`)** — Dataclasses mapping SQLite rows.
- **DB (`db/`)** — `sqlite3` connections, schema DDL, and bootstrap.

State is stored in a single SQLite file; override with `--db` on commands.
