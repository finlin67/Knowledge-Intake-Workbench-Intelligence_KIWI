"""Tests for paragraph-group chunking."""

from __future__ import annotations

from services.chunking_service import ParagraphChunker, estimate_word_count


def _words(n: int, prefix: str) -> str:
    return " ".join(f"{prefix}{i}" for i in range(n))


def test_estimate_word_count() -> None:
    assert estimate_word_count("hello world") == 2
    assert estimate_word_count("A-b test's case") == 3


def test_chunk_by_paragraph_groups_near_target() -> None:
    text = (
        "---\n"
        "title: t\n"
        "---\n\n"
        f"{_words(60, 'a')}\n\n"
        f"{_words(60, 'b')}\n\n"
        f"{_words(50, 'c')}\n\n"
        f"{_words(30, 'd')}\n"
    )
    chunker = ParagraphChunker(target_words=130, min_words=80)
    result = chunker.chunk_text(text)
    assert len(result.chunks) == 2
    assert len(result.metadata) == 2
    assert result.metadata[0].chunk_index == 0
    assert result.metadata[1].chunk_index == 1
    assert result.metadata[0].estimated_word_count >= 100
    assert result.metadata[1].estimated_word_count >= 70
    assert all(c.strip() for c in result.chunks)


def test_avoids_empty_chunks() -> None:
    text = "\n\n   \n\n# Heading\n\n   \n\nSome text here.\n"
    result = ParagraphChunker(target_words=50, min_words=10).chunk_text(text)
    assert len(result.chunks) == 1
    assert result.chunks[0]
    assert result.metadata[0].estimated_word_count > 0
