"""Row mapped to ``outputs``."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True, slots=True)
class OutputRecord:
    id: int
    file_id: int
    job_id: int | None
    kind: str
    storage_path: str | None
    content_hash: str | None
    meta_json: str | None
    created_at: datetime | None

    @classmethod
    def from_row(cls, row: Any) -> OutputRecord:
        return cls(
            id=int(row["id"]),
            file_id=int(row["file_id"]),
            job_id=row["job_id"],
            kind=str(row["kind"]),
            storage_path=row["storage_path"],
            content_hash=row["content_hash"],
            meta_json=row["meta_json"],
            created_at=_parse_dt(row["created_at"]),
        )


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
