"""Sliding-window text chunker with configurable size and overlap."""

from __future__ import annotations

from app.documents.models import DocumentChunk


def chunk_text(
    document_id: str,
    text: str,
    chunk_size: int = 500,
    overlap: int = 80,
) -> list[DocumentChunk]:
    """Split *text* into overlapping windows.

    Each window is at most *chunk_size* characters, with *overlap* characters
    shared with the adjacent chunks so context is preserved across boundaries.
    """
    if not text.strip():
        return []

    words = text.split()
    chunks: list[DocumentChunk] = []
    start = 0
    index = 0

    # Build chunks as word lists, keeping character budget
    window: list[str] = []
    window_chars = 0

    for word in words:
        window.append(word)
        window_chars += len(word) + 1

        if window_chars >= chunk_size:
            text_chunk = " ".join(window)
            chunks.append(
                DocumentChunk(
                    document_id=document_id,
                    index=index,
                    text=text_chunk,
                )
            )
            index += 1
            # Keep the trailing *overlap* words
            overlap_words: list[str] = []
            overlap_chars = 0
            for w in reversed(window):
                if overlap_chars + len(w) + 1 > overlap:
                    break
                overlap_words.insert(0, w)
                overlap_chars += len(w) + 1
            window = overlap_words
            window_chars = overlap_chars
            start += 1

    if window:
        chunks.append(
            DocumentChunk(
                document_id=document_id,
                index=index,
                text=" ".join(window),
            )
        )

    return chunks
