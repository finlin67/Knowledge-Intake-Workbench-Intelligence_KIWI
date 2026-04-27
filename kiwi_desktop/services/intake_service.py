"""Application use cases for registering and listing tracked files."""

from __future__ import annotations

from collections.abc import Sequence

from db.repositories import FileRepository
from db.session import Database
from models import FileRecord
from models.enums import FileStage


class IntakeService:
    """Thin façade over ``FileRepository`` for CLI / UI layers."""

    def __init__(self, db: Database) -> None:
        self._files = FileRepository(db)

    def list_recent(self, limit: int = 20) -> Sequence[FileRecord]:
        return self._files.list_recent(limit=limit)

    def register_file(
        self,
        *,
        path: str,
        display_name: str | None = None,
        size_bytes: int | None = None,
        mime_type: str | None = None,
    ) -> FileRecord:
        """Insert a new row at ``pending`` (or raise if ``path`` is already tracked)."""
        return self._files.insert(
            path=path,
            display_name=display_name,
            size_bytes=size_bytes,
            mime_type=mime_type,
            current_stage=FileStage.PENDING.value,
        )
