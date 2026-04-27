"""Recursive filesystem scanner for supported intake file types."""

from __future__ import annotations

import hashlib
import mimetypes
import os
import sqlite3
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from db.repositories import FileRepository
from db.session import Database
from utils.logging_utils import get_logger

SUPPORTED_SUFFIXES: frozenset[str] = frozenset(
    {
        ".csv",
        ".css",
        ".doc",
        ".docx",
        ".html",
        ".js",
        ".json",
        ".md",
        ".markdown",
        ".pdf",
        ".ppt",
        ".pptx",
        ".py",
        ".rst",
        ".sh",
        ".sql",
        ".ts",
        ".tsx",
        ".txt",
        ".yaml",
        ".yml",
        ".jsx",
    }
)


@dataclass(frozen=True, slots=True)
class ScanResult:
    root: Path
    files_matched: int
    files_upserted: int
    errors: tuple[str, ...]


def _file_times(st: os.stat_result) -> tuple[datetime, datetime]:
    """Return (created, modified) in UTC; creation may fall back to mtime on some platforms."""
    modified = datetime.fromtimestamp(st.st_mtime, tz=timezone.utc)
    birth = getattr(st, "st_birthtime", None)
    if birth is not None:
        created = datetime.fromtimestamp(birth, tz=timezone.utc)
    elif sys.platform == "win32":
        created = datetime.fromtimestamp(st.st_ctime, tz=timezone.utc)
    else:
        created = datetime.fromtimestamp(st.st_mtime, tz=timezone.utc)
    return created, modified


def sha256_file(path: Path, *, chunk_size: int = 1 << 20) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def is_supported_path(path: Path) -> bool:
    suf = path.suffix.lower()
    return suf in SUPPORTED_SUFFIXES


class ScanService:
    """Walk a directory tree, hash files, and upsert rows into ``files``."""

    __slots__ = ("_files", "_log")

    def __init__(self, database: Database) -> None:
        self._files = FileRepository(database)
        self._log = get_logger("kiw.scan")

    def scan(self, root: Path) -> ScanResult:
        root = root.expanduser().resolve()
        if not root.is_dir():
            self._log.warning("scan rejected: not a directory", extra={"root": str(root)})
            return ScanResult(
                root=root,
                files_matched=0,
                files_upserted=0,
                errors=(f"Not a directory: {root}",),
            )

        self._log.info("scan started", extra={"root": str(root)})
        matched = 0
        upserted = 0
        err_list: list[str] = []

        for dirpath, _dirnames, filenames in os.walk(root, topdown=True, followlinks=False):
            for name in sorted(filenames):
                fp = Path(dirpath) / name
                if not is_supported_path(fp):
                    continue
                if not fp.is_file():
                    continue
                matched += 1
                try:
                    st = fp.stat()
                    created, modified = _file_times(st)
                    ext = fp.suffix.lower()
                    digest = sha256_file(fp)
                    mime, _enc = mimetypes.guess_type(name)
                    resolved = str(fp.resolve())
                    self._files.upsert_scanned_file(
                        path=resolved,
                        filename=name,
                        extension=ext,
                        size_bytes=st.st_size,
                        sha256_hex=digest,
                        file_created_at=created,
                        file_modified_at=modified,
                        mime_type=mime,
                        display_name=name,
                    )
                    upserted += 1
                except (OSError, PermissionError, sqlite3.Error) as e:
                    self._log.exception("scan file failure", extra={"path": str(fp)})
                    err_list.append(f"{fp}: {e}")

        self._log.info(
            "scan completed",
            extra={"root": str(root), "matched": matched, "upserted": upserted, "errors": len(err_list)},
        )
        return ScanResult(
            root=root,
            files_matched=matched,
            files_upserted=upserted,
            errors=tuple(err_list),
        )
