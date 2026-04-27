"""SQLite connection lifecycle: load schema from ``schema.sql`` and bootstrap."""

from __future__ import annotations

import sqlite3
import threading
from importlib import resources
from pathlib import Path
from typing import Generator

from db import migrations
from utils.paths import get_kiw_data_dir

_SCHEMA_CACHE: str | None = None
_INIT_LOCK = threading.Lock()
_INITIALIZED_DATABASES: set[str] = set()
_REQUIRED_TABLES: frozenset[str] = frozenset({"files", "jobs", "outputs"})


def _load_schema_sql() -> str:
    global _SCHEMA_CACHE
    if _SCHEMA_CACHE is None:
        _SCHEMA_CACHE = resources.files("db").joinpath("schema.sql").read_text(encoding="utf-8")
    return _SCHEMA_CACHE


def get_default_db_path() -> Path:
    """Return the default SQLite file path (user data dir / app name)."""
    return get_kiw_data_dir() / "state.sqlite3"


def reset_database_initialization(path: Path) -> None:
    """Forget cached initialization state for a database path."""
    if str(path) == ":memory:":
        return
    db_key = str(path.expanduser().resolve())
    with _INIT_LOCK:
        _INITIALIZED_DATABASES.discard(db_key)


def has_required_tables(conn: sqlite3.Connection) -> bool:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table'"
    ).fetchall()
    tables = {str(row[0]) for row in rows}
    return _REQUIRED_TABLES.issubset(tables)


class Database:
    """Owns the database path, applies DDL from ``schema.sql``, exposes connections."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or get_default_db_path()
        self._conn: sqlite3.Connection | None = None

    def connect(self) -> sqlite3.Connection:
        """Return a live connection with ``row_factory=sqlite3.Row`` and schema applied."""
        if self._conn is None:
            if str(self.path) != ":memory:":
                self.path.parent.mkdir(parents=True, exist_ok=True)
            # Keep lock waits short so UI polling never appears frozen under write contention.
            self._conn = sqlite3.connect(self.path, check_same_thread=False, timeout=2.0)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA foreign_keys = ON;")
            # WAL allows concurrent readers while the worker thread is writing.
            self._conn.execute("PRAGMA journal_mode = WAL;")
            self._conn.execute("PRAGMA busy_timeout = 2000;")
            if str(self.path) == ":memory:":
                self.apply_schema()
            else:
                db_key = str(self.path.expanduser().resolve())
                schema_ready = has_required_tables(self._conn)
                with _INIT_LOCK:
                    if db_key not in _INITIALIZED_DATABASES or not schema_ready:
                        self.apply_schema()
                        _INITIALIZED_DATABASES.add(db_key)
        return self._conn

    def apply_schema(self) -> None:
        """Execute ``schema.sql`` and additive migrations (idempotent)."""
        conn = self._conn
        if conn is None:
            raise RuntimeError("Database not connected")
        conn.executescript(_load_schema_sql())
        migrations.migrate_files_table(conn)
        conn.commit()

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Context-style lifecycle: connect, yield, close."""
        try:
            yield self.connect()
        finally:
            self.close()


def connect_memory() -> sqlite3.Connection:
    """In-memory SQLite with schema applied (tests / ephemeral tooling)."""
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.executescript(_load_schema_sql())
    migrations.migrate_files_table(conn)
    conn.commit()
    return conn
