"""Project-specific filesystem locations (data dir, working dirs)."""

from __future__ import annotations

import os
from pathlib import Path


def get_kiw_data_dir() -> Path:
    """
    Application data root for Knowledge Intake Workbench.

    Windows: ``%LOCALAPPDATA%\\KnowledgeIntakeWorkbench``
    Unix: ``$XDG_DATA_HOME/KnowledgeIntakeWorkbench`` or ``~/.local/share/...``
    """
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("XDG_DATA_HOME")
    if base:
        root = Path(base) / "KnowledgeIntakeWorkbench"
    else:
        root = Path.home() / ".local" / "share" / "KnowledgeIntakeWorkbench"
    root.mkdir(parents=True, exist_ok=True)
    return root


def get_normalized_work_dir() -> Path:
    """Directory for first-pass normalized markdown outputs (created if missing)."""
    d = get_kiw_data_dir() / "normalized"
    d.mkdir(parents=True, exist_ok=True)
    return d
