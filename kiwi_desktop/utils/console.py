"""Rich console factory (consistent styling across CLI)."""

from __future__ import annotations

from rich.console import Console
from rich.theme import Theme

_KIW_THEME = Theme(
    {
        "info": "cyan",
        "warning": "yellow",
        "danger": "bold red",
        "success": "bold green",
    }
)


def get_console() -> Console:
    """Return a shared Rich Console with a small custom theme."""
    return Console(theme=_KIW_THEME)
