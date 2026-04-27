"""Row mapped to ``jobs``."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True, slots=True)
class JobRecord:
    id: int
    kind: str
    status: str
    priority: int
    payload_json: str | None
    result_json: str | None
    created_at: datetime | None
    started_at: datetime | None
    completed_at: datetime | None
    error_message: str | None

    @classmethod
    def from_row(cls, row: Any) -> JobRecord:
        return cls(
            id=int(row["id"]),
            kind=str(row["kind"]),
            status=str(row["status"]),
            priority=int(row["priority"]),
            payload_json=row["payload_json"],
            result_json=row["result_json"],
            created_at=_parse_dt(row["created_at"]),
            started_at=_parse_dt(row["started_at"]),
            completed_at=_parse_dt(row["completed_at"]),
            error_message=row["error_message"],
        )


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
