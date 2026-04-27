"""Smoke tests for CLI import and Typer app wiring."""

from __future__ import annotations

from typer.testing import CliRunner

from cli.app import app

runner = CliRunner()


def test_cli_help() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "Knowledge Intake" in result.stdout
