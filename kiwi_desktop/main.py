"""Entry point for Knowledge Intake Workbench."""

from __future__ import annotations

from cli.app import app
from utils.logging_utils import configure_logging


def main() -> None:
    """Console script entry (`kiw` / `python main.py`)."""
    configure_logging()
    app()


if __name__ == "__main__":
    main()
