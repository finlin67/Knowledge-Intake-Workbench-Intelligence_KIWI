"""Exporter profiles for downstream tools (Open WebUI, AnythingLLM)."""

from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import yaml

from utils.paths import get_kiw_data_dir
from utils.logging_utils import get_logger

ProfileName = str
PROFILE_OPEN_WEBUI = "open_webui"
PROFILE_ANYTHINGLLM = "anythingllm"
DUPLICATE_FILENAME_POLICY_RENAME = "rename"
DUPLICATE_FILENAME_POLICY_OVERWRITE = "overwrite"
DUPLICATE_FILENAME_POLICY_SKIP = "skip"
_ANYTHINGLLM_WORKSPACE_MAP: dict[str, str] = {
    "career_portfolio": "Career_Portfolio",
    "archive": "Career_Archive",
    "ai_projects": "AI_Web_Projects",
    "wiki": "Reference",
    "case_studies": "Case_Studies",
    "unassigned": "Unassigned",
}


@dataclass(frozen=True, slots=True)
class ExportResult:
    profile: ProfileName
    profile_root: Path
    source_export_path: Path
    chunk_export_paths: tuple[Path, ...]


def _safe_segment(text: str) -> str:
    clean = "".join(c if c.isalnum() or c in "-_." else "_" for c in text.strip())
    return clean or "item"


def _safe_subfolder_path(text: str) -> tuple[str, ...]:
    parts = re.split(r"[\\/]+", text.strip())
    out: list[str] = []
    for part in parts:
        p = _safe_segment(part)
        if p and p != "item":
            out.append(p)
    return tuple(out)


def _sanitize_filename(text: str) -> str:
    clean = re.sub(r"[^A-Za-z0-9_.-]+", "_", text.strip().replace(" ", "_"))
    clean = re.sub(r"_+", "_", clean).strip("._")
    return clean or "document"


def _split_frontmatter(md: str) -> tuple[dict[str, object], str]:
    if not md.startswith("---\n"):
        return {}, md
    end = md.find("\n---\n", 4)
    if end < 0:
        return {}, md
    yaml_block = md[4:end]
    body = md[end + len("\n---\n") :]
    try:
        front = yaml.safe_load(yaml_block) or {}
    except yaml.YAMLError:
        front = {}
    if not isinstance(front, dict):
        front = {}
    return front, body


def _render_frontmatter(front: dict[str, object], body: str) -> str:
    dumped = yaml.safe_dump(front, sort_keys=False, allow_unicode=True, default_flow_style=False).rstrip()
    return f"---\n{dumped}\n---\n\n{body.lstrip()}"


def _read_markdown_with_meta(path: Path) -> tuple[dict[str, object], str]:
    raw = path.read_text(encoding="utf-8", errors="replace")
    return _split_frontmatter(raw)


def _load_json(path: Path, fallback: object) -> object:
    if not path.exists():
        return fallback
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return fallback


def _read_files_manifest_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    out: list[dict[str, str]] = []
    with path.open("r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            if row:
                out.append({k: v for k, v in row.items() if k is not None and v is not None})
    return out


class ExporterService:
    """
    Export normalized/chunked content with profile-specific layouts.

    - `open_webui`: one normalized markdown per source in workspace-style folders.
    - `anythingllm`: normalized markdown plus chunk files in dedicated chunk folders.
    """

    __slots__ = ("_root", "_duplicate_filename_policy", "_log")

    def __init__(
        self,
        *,
        export_root: Path | None = None,
        duplicate_filename_policy: str = DUPLICATE_FILENAME_POLICY_RENAME,
    ) -> None:
        base = export_root if export_root is not None else (get_kiw_data_dir() / "exports")
        self._root = base
        self._root.mkdir(parents=True, exist_ok=True)
        policy = duplicate_filename_policy.strip().lower()
        if policy not in {
            DUPLICATE_FILENAME_POLICY_RENAME,
            DUPLICATE_FILENAME_POLICY_OVERWRITE,
            DUPLICATE_FILENAME_POLICY_SKIP,
        }:
            policy = DUPLICATE_FILENAME_POLICY_RENAME
        self._duplicate_filename_policy = policy
        self._log = get_logger("kiw.exporter")

    def export(
        self,
        *,
        profile: ProfileName,
        source_id: int,
        source_file: str,
        source_path: str,
        category: str,
        workspace: str,
        subfolder: str = "",
        matched_by: str = "",
        confidence: float = 0.0,
        normalized_path: str,
        chunks: list[str],
        chunk_metadata: list[dict[str, object]],
    ) -> ExportResult:
        if profile not in {PROFILE_OPEN_WEBUI, PROFILE_ANYTHINGLLM}:
            raise ValueError(f"Unsupported export profile: {profile!r}")

        workspace = (workspace or "").strip() or "unassigned"

        profile_root = self._root / profile
        profile_root.mkdir(parents=True, exist_ok=True)
        export_dir = self._export_directory(
            profile=profile,
            profile_root=profile_root,
            workspace=workspace,
            subfolder=subfolder,
        )
        export_dir.mkdir(parents=True, exist_ok=True)
        files_manifest = profile_root / "files_manifest.csv"

        norm_src = Path(normalized_path)
        if not norm_src.is_file():
            raise FileNotFoundError(f"Normalized source not found: {norm_src}")

        source_export_path = self._export_flat_markdown(
            export_dir=export_dir,
            source_id=source_id,
            source_file=source_file,
            source_path=source_path,
            category=category,
            workspace=workspace,
            subfolder=subfolder,
            matched_by=matched_by,
            confidence=confidence,
            normalized_path=norm_src,
            preferred_export_path=self._existing_export_path(files_manifest, source_id),
        )
        chunk_paths: list[Path] = []

        self._update_manifests(
            profile_root=profile_root,
            source_id=source_id,
            source_file=source_file,
            source_path=source_path,
            category=category,
            workspace=workspace,
            subfolder=subfolder,
            profile=profile,
            normalized_export_path=source_export_path,
            chunk_export_paths=chunk_paths,
            chunk_metadata=chunk_metadata,
        )
        self._log.info(
            "export completed",
            extra={
                "profile": profile,
                "source_id": source_id,
                "workspace": workspace,
                "subfolder": subfolder,
                "destination": str(source_export_path),
            },
        )

        return ExportResult(
            profile=profile,
            profile_root=profile_root,
            source_export_path=source_export_path,
            chunk_export_paths=tuple(chunk_paths),
        )

    def _export_flat_markdown(
        self,
        *,
        export_dir: Path,
        source_id: int,
        source_file: str,
        source_path: str,
        category: str,
        workspace: str,
        subfolder: str,
        matched_by: str,
        confidence: float,
        normalized_path: Path,
        preferred_export_path: Path | None,
    ) -> Path:
        base_name = _sanitize_filename(Path(source_file).stem)
        if preferred_export_path is not None and preferred_export_path.parent == export_dir:
            dst = preferred_export_path
        else:
            dst = export_dir / f"{base_name}.md"
            if dst.exists():
                if self._duplicate_filename_policy == DUPLICATE_FILENAME_POLICY_RENAME:
                    i = 1
                    while dst.exists():
                        dst = export_dir / f"{base_name}_{i}.md"
                        i += 1
                elif self._duplicate_filename_policy == DUPLICATE_FILENAME_POLICY_SKIP:
                    return dst

        front, body = _read_markdown_with_meta(normalized_path)
        # Ensure traceability metadata is always present.
        front["source_id"] = source_id
        front["processed_date"] = datetime.now(UTC).isoformat()
        front["source_file"] = source_file
        front["source_path"] = source_path
        front["workspace"] = workspace
        front["subfolder"] = subfolder
        front["matched_by"] = matched_by
        front["confidence"] = round(float(confidence), 3)
        front["category"] = category
        dst.write_text(_render_frontmatter(front, body), encoding="utf-8")
        return dst

    def _existing_export_path(self, files_manifest: Path, source_id: int) -> Path | None:
        for row in _read_files_manifest_rows(files_manifest):
            try:
                sid = int(row.get("source_id", "0"))
            except ValueError:
                continue
            if sid != source_id:
                continue
            exp = row.get("export_path") or row.get("normalized_export_path")
            if exp:
                return Path(exp)
        return None

    def _update_manifests(
        self,
        *,
        profile_root: Path,
        source_id: int,
        source_file: str,
        source_path: str,
        category: str,
        workspace: str,
        subfolder: str,
        profile: str,
        normalized_export_path: Path,
        chunk_export_paths: list[Path],
        chunk_metadata: list[dict[str, object]],
    ) -> None:
        files_manifest = profile_root / "files_manifest.csv"
        rows: list[dict[str, object]] = []
        for row in _read_files_manifest_rows(files_manifest):
            try:
                sid = int(row.get("source_id", "0"))
            except ValueError:
                sid = 0
            rows.append(
                {
                    "source_id": sid,
                    "profile": row.get("profile", ""),
                    "category": row.get("category", ""),
                    "workspace": row.get("workspace", ""),
                    "subfolder": row.get("subfolder", ""),
                    "source_file": row.get("source_file", ""),
                    "source_path": row.get("source_path", ""),
                    "normalized_export_path": row.get("normalized_export_path", ""),
                    "export_path": row.get("export_path", ""),
                }
            )
        # Upsert by source_id for stable traceability across reruns.
        rows = [r for r in rows if isinstance(r, dict) and r.get("source_id") != source_id]
        rows.append(
            {
                "source_id": source_id,
                "profile": profile,
                "category": category,
                "workspace": workspace,
                "subfolder": subfolder,
                "source_file": source_file,
                "source_path": source_path,
                "normalized_export_path": str(normalized_export_path),
                "export_path": str(normalized_export_path),
            }
        )
        rows.sort(key=lambda x: (str(x.get("category", "")), int(x.get("source_id", 0))))

        with files_manifest.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "source_id",
                    "profile",
                    "category",
                    "workspace",
                    "subfolder",
                    "source_file",
                    "source_path",
                    "normalized_export_path",
                    "export_path",
                ],
            )
            writer.writeheader()
            for row in rows:
                writer.writerow(row)
        chunks_manifest = profile_root / "chunks_manifest.json"
        existing_obj = _load_json(chunks_manifest, [])
        existing = existing_obj if isinstance(existing_obj, list) else []
        existing = [e for e in existing if isinstance(e, dict) and e.get("source_id") != source_id]

        per_chunk: list[dict[str, object]] = []
        for i, cp in enumerate(chunk_export_paths):
            meta = chunk_metadata[i] if i < len(chunk_metadata) and isinstance(chunk_metadata[i], dict) else {}
            per_chunk.append(
                {
                    "source_id": source_id,
                    "profile": profile,
                    "category": category,
                    "workspace": workspace,
                    "subfolder": subfolder,
                    "source_file": source_file,
                    "source_path": source_path,
                    "chunk_index": int(meta.get("chunk_index", i)),
                    "estimated_word_count": int(meta.get("estimated_word_count", 0)),
                    "chunk_path": str(cp),
                    "export_path": str(cp),
                }
            )

        existing.extend(per_chunk)
        existing.sort(key=lambda x: (int(x.get("source_id", 0)), int(x.get("chunk_index", 0))))
        chunks_manifest.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")

    def _export_directory(
        self,
        *,
        profile: str,
        profile_root: Path,
        workspace: str,
        subfolder: str,
    ) -> Path:
        if profile == PROFILE_ANYTHINGLLM:
            ws = _ANYTHINGLLM_WORKSPACE_MAP.get(workspace, _safe_segment(workspace).title().replace("_", "_"))
            return profile_root / ws
        # open_webui supports workspace/subfolder hierarchy for manual organization.
        ws_dir = profile_root / _safe_segment(workspace)
        parts = _safe_subfolder_path(subfolder)
        if not parts:
            return ws_dir
        return ws_dir.joinpath(*parts)
