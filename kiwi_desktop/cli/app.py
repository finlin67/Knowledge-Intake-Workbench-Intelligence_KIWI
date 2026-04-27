"""Typer application wired to services and Rich output."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from db.session import Database, get_default_db_path
from services.intake_service import IntakeService
from services.exporter_service import PROFILE_ANYTHINGLLM, PROFILE_OPEN_WEBUI
from services.pipeline_runner import PipelineRunner
from services.scan_service import ScanService
from utils.console import get_console

app = typer.Typer(
    name="kiw",
    help="Knowledge Intake Workbench — capture and list local knowledge entries.",
    add_completion=False,
)
_console: Console | None = None


def console() -> Console:
    global _console
    if _console is None:
        _console = get_console()
    return _console


def _service(db_path: Optional[Path]) -> IntakeService:
    path = db_path if db_path is not None else get_default_db_path()
    return IntakeService(Database(path))


def _database(db_path: Optional[Path]) -> Database:
    path = db_path if db_path is not None else get_default_db_path()
    return Database(path)


@app.command("init")
def cmd_init(
    db_path: Optional[Path] = typer.Option(
        None,
        "--db",
        help="Path to SQLite database file.",
        exists=False,
    ),
) -> None:
    """Create the database file and apply schema."""
    db = Database(db_path)
    db.connect()
    db.close()
    p = db.path
    console().print(f"[green]OK[/green] Database ready at [bold]{p}[/bold]")


@app.command("add")
def cmd_add(
    path: Path = typer.Argument(..., help="Filesystem path to register for intake."),
    name: Optional[str] = typer.Option(
        None, "--name", "-n", help="Optional display name (defaults to path stem)."
    ),
    db_path: Optional[Path] = typer.Option(None, "--db", help="SQLite database path."),
) -> None:
    """Register a file path and start it at the pending stage."""
    svc = _service(db_path)
    resolved = path.expanduser().resolve()
    size_bytes: int | None = None
    if resolved.is_file():
        try:
            size_bytes = resolved.stat().st_size
        except OSError:
            size_bytes = None
    display = name if name is not None else resolved.name
    item = svc.register_file(path=str(resolved), display_name=display, size_bytes=size_bytes)
    console().print(
        f"[green]Registered[/green] file [bold]#{item.id}[/bold]: [cyan]{item.path}[/cyan] "
        f"([dim]{item.current_stage}[/dim])"
    )


@app.command("list")
def cmd_list(
    limit: int = typer.Option(20, "--limit", "-n", min=1, max=500),
    db_path: Optional[Path] = typer.Option(None, "--db", help="SQLite database path."),
) -> None:
    """List recently updated tracked files."""
    svc = _service(db_path)
    items = svc.list_recent(limit=limit)
    if not items:
        console().print("[dim]No files yet. Use [bold]kiw add PATH[/bold].[/dim]")
        raise typer.Exit(0)

    table = Table(title="Knowledge Intake — files", show_lines=False)
    table.add_column("ID", justify="right", style="dim")
    table.add_column("Stage", style="magenta")
    table.add_column("Path", style="bold")
    table.add_column("Updated", style="dim")

    for it in items:
        updated = it.updated_at.isoformat(sep=" ", timespec="seconds") if it.updated_at else "—"
        table.add_row(str(it.id), it.current_stage, it.path, updated)

    console().print(table)


@app.command("scan")
def cmd_scan(
    root: Path = typer.Argument(..., exists=True, file_okay=False, help="Root folder to scan."),
    db_path: Optional[Path] = typer.Option(None, "--db", help="SQLite database path."),
) -> None:
    """Recursively index supported files under ROOT (SHA256 + metadata upsert)."""
    db = _database(db_path)
    db.connect()
    svc = ScanService(db)
    result = svc.scan(root)

    if result.errors and result.files_matched == 0 and result.files_upserted == 0:
        for line in result.errors:
            console().print(f"[red]{line}[/red]")
        raise typer.Exit(1)

    console().print(
        f"[green]Scan complete[/green] under [bold]{result.root}[/bold]: "
        f"[cyan]{result.files_matched}[/cyan] matched, "
        f"[cyan]{result.files_upserted}[/cyan] upserted."
    )
    for line in result.errors:
        console().print(f"[yellow]Warning:[/yellow] {line}")


@app.command("run")
def cmd_run(
    max_files: Optional[int] = typer.Option(
        None,
        "--max-files",
        min=1,
        help="Maximum number of files to process in this invocation (default: all eligible).",
    ),
    export_profile: str = typer.Option(
        PROFILE_ANYTHINGLLM,
        "--export-profile",
        help="Exporter profile: anythingllm or open_webui.",
    ),
    db_path: Optional[Path] = typer.Option(None, "--db", help="SQLite database path."),
) -> None:
    """Run the resumable intake pipeline on files in new, processing, or failed state."""
    if export_profile not in {PROFILE_ANYTHINGLLM, PROFILE_OPEN_WEBUI}:
        raise typer.BadParameter(
            f"Unsupported export profile: {export_profile!r}. "
            f"Choose {PROFILE_ANYTHINGLLM!r} or {PROFILE_OPEN_WEBUI!r}.",
            param_hint="--export-profile",
        )
    db = _database(db_path)
    db.connect()
    runner = PipelineRunner(db, export_profile=export_profile)
    out = runner.run(max_files=max_files)
    console().print(
        f"[green]Job #{out.job_id}[/green] — started [cyan]{out.files_started}[/cyan] file(s), "
        f"finished OK [cyan]{out.files_finished_ok}[/cyan], "
        f"failed [cyan]{out.files_marked_failed}[/cyan]."
    )


@app.command("gui")
def cmd_gui() -> None:
    """Launch the PySide6 desktop shell."""
    from gui.app import run_gui

    raise typer.Exit(run_gui())
