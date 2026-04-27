"""Chunk normalized markdown into paragraph groups near a target word count."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

_WORD_RE = re.compile(r"\b[\w'-]+\b")
_HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s+")


@dataclass(frozen=True, slots=True)
class ChunkMetadata:
    chunk_index: int
    estimated_word_count: int


@dataclass(frozen=True, slots=True)
class ChunkingResult:
    chunks: tuple[str, ...]
    metadata: tuple[ChunkMetadata, ...]


def estimate_word_count(text: str) -> int:
    return len(_WORD_RE.findall(text))


def _split_frontmatter(text: str) -> tuple[str, str]:
    """Return (frontmatter, body) where frontmatter includes delimiters if present."""
    if not text.startswith("---\n"):
        return "", text
    end = text.find("\n---\n", 4)
    if end < 0:
        return "", text
    end += len("\n---\n")
    return text[:end], text[end:]


def _split_blocks_for_future_heading_aware_chunking(body: str) -> list[str]:
    """
    Paragraph-ish blocks split on blank lines.

    The function keeps heading lines as independent blocks where possible so we can
    later implement heading-aware grouping with minimal changes.
    """
    blocks: list[str] = []
    for part in re.split(r"\n\s*\n+", body.strip()):
        block = part.strip()
        if not block:
            continue
        if _HEADING_RE.match(block):
            blocks.append(block)
            continue
        blocks.append(block)
    return blocks


class ParagraphChunker:
    """Current strategy: paragraph groups near target size (heading-aware ready)."""

    __slots__ = ("_target_words", "_min_words")

    def __init__(self, *, target_words: int = 220, min_words: int = 120) -> None:
        if target_words < 20:
            raise ValueError("target_words must be >= 20")
        if min_words < 1:
            raise ValueError("min_words must be >= 1")
        self._target_words = target_words
        self._min_words = min_words

    def chunk_text(self, markdown_text: str) -> ChunkingResult:
        _frontmatter, body = _split_frontmatter(markdown_text)
        blocks = _split_blocks_for_future_heading_aware_chunking(body)
        if not blocks:
            return ChunkingResult(chunks=(), metadata=())

        out_chunks: list[str] = []
        out_meta: list[ChunkMetadata] = []

        current_blocks: list[str] = []
        current_words = 0
        idx = 0

        for block in blocks:
            wc = estimate_word_count(block)
            if wc == 0:
                continue
            # Flush once we are near target and adding this block would overshoot.
            if (
                current_blocks
                and current_words >= self._min_words
                and (current_words + wc) > self._target_words
            ):
                text = "\n\n".join(current_blocks).strip()
                if text:
                    out_chunks.append(text)
                    out_meta.append(ChunkMetadata(chunk_index=idx, estimated_word_count=current_words))
                    idx += 1
                current_blocks = []
                current_words = 0

            current_blocks.append(block)
            current_words += wc

        if current_blocks and current_words > 0:
            text = "\n\n".join(current_blocks).strip()
            if text:
                out_chunks.append(text)
                out_meta.append(ChunkMetadata(chunk_index=idx, estimated_word_count=current_words))

        return ChunkingResult(chunks=tuple(out_chunks), metadata=tuple(out_meta))

    def chunk_markdown_file(self, path: Path) -> ChunkingResult:
        content = path.read_text(encoding="utf-8", errors="replace")
        return self.chunk_text(content)
