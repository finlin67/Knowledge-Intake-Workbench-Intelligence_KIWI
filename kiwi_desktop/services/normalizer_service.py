"""First-pass normalizer: source files → canonical markdown + YAML frontmatter."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

import yaml

from models.file_record import FileRecord
from utils.file_readers import extract_text_sample
from utils.paths import get_normalized_work_dir

_TEXT_READ = {".md", ".markdown", ".txt"}
_JSON = {".json"}
_EXTRACT_BINARY = {".pdf", ".pptx", ".ppt", ".docx", ".doc"}


@dataclass(frozen=True, slots=True)
class NormalizeResult:
    """Result of normalizing one source file."""

    output_path: Path
    category: str
    title: str


def _extension(path: Path, record: FileRecord) -> str:
    ext = (record.extension or path.suffix or "").lower()
    if not ext.startswith("."):
        ext = f".{ext}" if ext else ""
    return ext


def _category_for_extension(ext: str) -> str:
    ext = ext.lower()
    mapping = {
        ".md": "markdown",
        ".markdown": "markdown",
        ".txt": "text",
        ".json": "json",
        ".pdf": "pdf",
        ".pptx": "pptx",
        ".ppt": "pptx",
        ".docx": "docx",
        ".doc": "docx",
    }
    return mapping.get(ext, "unknown")


def _safe_stem(name: str, max_len: int = 100) -> str:
    stem = Path(name).stem
    safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in stem)
    return safe[:max_len] if safe else "document"


def _strip_optional_frontmatter(text: str) -> str:
    """Remove a leading YAML block delimited by ``---`` lines (common in markdown)."""
    if not text.startswith("---"):
        return text
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return text
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        return text
    return "\n".join(lines[end + 1 :]).lstrip("\n")


def _infer_title_from_markdown(body: str, fallback: str) -> str:
    m = re.search(r"^\s*#\s+(.+)$", body, re.MULTILINE)
    if m:
        return m.group(1).strip()
    return fallback


def _read_utf8(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _body_for_json(path: Path) -> str:
    raw = _read_utf8(path)
    data = json.loads(raw)
    pretty = json.dumps(data, indent=2, ensure_ascii=False)
    return f"```json\n{pretty}\n```\n"


def _build_document(
    *,
    title: str,
    source_file: str,
    source_path: str,
    category: str,
    body: str,
) -> str:
    front = {
        "title": title,
        "source_file": source_file,
        "source_path": source_path,
        "category": category,
    }
    dumped = yaml.safe_dump(
        front,
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
    ).rstrip()
    return f"---\n{dumped}\n---\n\n{body.lstrip()}\n"


class FirstPassNormalizer:
    """
    Reads supported sources and writes normalized ``.md`` under the project working directory.

    Direct reads: ``.md``, ``.markdown``, ``.txt``, ``.json``.
    Binary extraction: ``.pdf``, ``.pptx``, ``.ppt``, ``.docx``, ``.doc``.
    """

    __slots__ = ("_work_dir",)

    def __init__(self, *, work_dir: Path | None = None) -> None:
        self._work_dir = work_dir if work_dir is not None else get_normalized_work_dir()

    def normalize(self, record: FileRecord, *, category: str | None = None) -> NormalizeResult:
        src = Path(record.path)
        if not src.is_file():
            raise FileNotFoundError(f"Source not found or not a file: {src}")

        source_path = str(src.resolve())
        source_file = record.filename or src.name
        ext = _extension(src, record)
        cat = category if category is not None else _category_for_extension(ext)
        stem_title = _safe_stem(source_file)

        if ext in _EXTRACT_BINARY:
            title = stem_title
            extracted = extract_text_sample(src)
            if ext == ".pdf":
                body = f"## {title}\n\n{extracted}".strip()
            else:
                # DOCX output is already markdown-formatted; PPTX output is slide markdown.
                body = extracted.strip()
        elif ext in _TEXT_READ:
            raw = _read_utf8(src)
            if ext in (".md", ".markdown"):
                body_md = _strip_optional_frontmatter(raw)
                title = _infer_title_from_markdown(body_md, stem_title)
                body = body_md
            else:
                body = raw
                title = stem_title
        elif ext in _JSON:
            body = _body_for_json(src)
            title = stem_title
        else:
            raise ValueError(f"Unsupported extension for normalization: {ext!r}")

        doc = _build_document(
            title=title,
            source_file=source_file,
            source_path=source_path,
            category=cat,
            body=body,
        )

        out = self._output_path(record)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(doc, encoding="utf-8", newline="\n")

        return NormalizeResult(output_path=out, category=cat, title=title)

    def _output_path(self, record: FileRecord) -> Path:
        stem = _safe_stem(record.filename or Path(record.path).name)
        return self._work_dir / f"{record.id:06d}_{stem}.md"
