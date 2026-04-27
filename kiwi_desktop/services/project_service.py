"""Project context setup/load for desktop workflows."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from db.session import Database, has_required_tables, reset_database_initialization
from services.classification_config import (
    DEFAULT_CONFIG_FILENAME,
    ensure_default_classification_config,
)
from utils.logging_utils import get_logger

PROJECT_DIR_NAME = ".kiw"
PROJECT_META_NAME = "project.json"
PROJECT_DB_NAME = "state.sqlite3"
APP_STATE_DIR_NAME = ".kiw"
LAST_PROJECT_NAME = "last_project.json"


@dataclass(frozen=True, slots=True)
class ProjectContext:
    name: str
    raw_folder: Path
    output_folder: Path
    db_path: Path
    project_file: Path


class ProjectService:
    """Create/load project metadata without coupling to UI concerns."""

    __slots__ = ("_log",)

    def __init__(self) -> None:
        self._log = get_logger("kiw.project")

    def create_project(self, *, raw_folder: Path, output_folder: Path, name: str) -> ProjectContext:
        raw = self._resolve_user_path(raw_folder, must_exist=True)
        out = self._resolve_user_path(output_folder, must_exist=False)
        if not raw.is_dir():
            raise ValueError(f"Raw folder does not exist or is not a directory: {raw}")
        out.mkdir(parents=True, exist_ok=True)
        meta_dir = out / PROJECT_DIR_NAME
        meta_dir.mkdir(parents=True, exist_ok=True)
        db_path = meta_dir / PROJECT_DB_NAME
        project_file = meta_dir / PROJECT_META_NAME
        if db_path.exists():
            # "Create project" should start fresh, not silently reuse old queue state.
            db_path.unlink()
        reset_database_initialization(db_path)
        payload = {
            "name": name.strip() or "Knowledge Intake Project",
            "raw_folder": str(raw),
            "output_folder": str(out),
            "db_path": str(db_path),
        }
        project_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        ensure_default_classification_config(meta_dir / DEFAULT_CONFIG_FILENAME)
        db = Database(db_path)
        conn = db.connect()
        if not has_required_tables(conn):
            db.close()
            raise RuntimeError(f"Project database failed schema initialization: {db_path}")
        db.close()
        self._log.info("project created", extra={"project_name": payload["name"], "output": str(out)})
        ctx = ProjectContext(
            name=str(payload["name"]),
            raw_folder=raw,
            output_folder=out,
            db_path=db_path,
            project_file=project_file,
        )
        self.save_last_output_folder(output_folder=ctx.output_folder)
        return ctx

    def load_project(self, *, output_folder: Path) -> ProjectContext:
        out = self._resolve_user_path(output_folder, must_exist=False)
        project_file = out / PROJECT_DIR_NAME / PROJECT_META_NAME
        if not project_file.is_file():
            raise FileNotFoundError(
                f"Project file not found: {project_file}. "
                f"Use Create Project first or select the correct output folder."
            )
        try:
            data = json.loads(project_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Project metadata is invalid JSON: {project_file}") from exc
        if "raw_folder" not in data:
            raise ValueError(f"Project metadata missing 'raw_folder': {project_file}")
        raw_folder = Path(str(data["raw_folder"])).expanduser().resolve()
        if not raw_folder.exists():
            raise FileNotFoundError(
                f"Raw folder from project metadata no longer exists: {raw_folder}"
            )
        db_path = Path(str(data.get("db_path") or (out / PROJECT_DIR_NAME / PROJECT_DB_NAME))).resolve()
        db = Database(db_path)
        conn = db.connect()
        if not has_required_tables(conn):
            db.close()
            raise RuntimeError(f"Project database is missing required tables: {db_path}")
        db.close()
        self._log.info("project loaded", extra={"project_name": data.get("name", ""), "output": str(out)})
        ctx = ProjectContext(
            name=str(data.get("name") or "Knowledge Intake Project"),
            raw_folder=raw_folder,
            output_folder=out,
            db_path=db_path,
            project_file=project_file,
        )
        self.save_last_output_folder(output_folder=ctx.output_folder)
        return ctx

    def load_last_output_folder(self) -> Path | None:
        state_file = self._state_file()
        if not state_file.is_file():
            return None
        try:
            data = json.loads(state_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None
        val = data.get("output_folder")
        if not isinstance(val, str) or not val.strip():
            return None
        return Path(val).expanduser().resolve()

    def save_last_output_folder(self, *, output_folder: Path) -> None:
        state_file = self._state_file()
        state_file.parent.mkdir(parents=True, exist_ok=True)
        payload = {"output_folder": str(output_folder.expanduser().resolve())}
        state_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def try_load_last_project(self) -> ProjectContext | None:
        out = self.load_last_output_folder()
        if out is None:
            return None
        try:
            return self.load_project(output_folder=out)
        except (FileNotFoundError, ValueError):
            return None

    @staticmethod
    def _state_file() -> Path:
        return Path.home() / APP_STATE_DIR_NAME / LAST_PROJECT_NAME

    @staticmethod
    def _resolve_user_path(path_value: Path, *, must_exist: bool) -> Path:
        candidate = path_value.expanduser()
        if candidate.is_absolute():
            return candidate.resolve()

        cwd = Path.cwd()
        probes = [
            cwd / candidate,
            cwd.parent / candidate,
        ]

        if must_exist:
            for probe in probes:
                if probe.exists():
                    return probe.resolve()
            discovered = ProjectService._discover_named_directory(candidate.name)
            if discovered is not None:
                return discovered
            return probes[-1].resolve()

        # For creatable paths (like output folders), prefer the shared KIWI parent.
        return probes[-1].resolve()

    @staticmethod
    def _discover_named_directory(folder_name: str) -> Path | None:
        cleaned = folder_name.strip()
        if not cleaned:
            return None

        search_roots = [
            Path.home(),
            Path.home() / "Documents",
            Path.home() / "Desktop",
        ]
        matches: list[Path] = []
        for root in search_roots:
            if not root.exists():
                continue
            try:
                for path in root.rglob(cleaned):
                    if not path.is_dir():
                        continue
                    if path.name.lower() != cleaned.lower():
                        continue
                    matches.append(path.resolve())
                    if len(matches) > 50:
                        break
            except OSError:
                continue
            if len(matches) > 50:
                break

        if not matches:
            return None
        if len(matches) == 1:
            return matches[0]

        # Prefer known source-batch locations when the folder name is ambiguous.
        preferred = [p for p in matches if "source_batches" in str(p).lower()]
        candidates = preferred or matches
        candidates.sort(key=lambda p: (len(p.parts), len(str(p))))
        return candidates[0]
