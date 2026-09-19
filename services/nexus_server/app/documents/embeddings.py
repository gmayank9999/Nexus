"""Embedding provider abstraction with local sentence-transformer and fallback."""

from __future__ import annotations

import hashlib
import logging
import math
from typing import Protocol, runtime_checkable

logger = logging.getLogger(__name__)


@runtime_checkable
class EmbeddingProvider(Protocol):
    """Produce dense vector embeddings for text."""

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Return one embedding vector per input text."""
        ...

    def cosine_similarity(self, a: list[float], b: list[float]) -> float:
        """Return cosine similarity in [-1, 1]."""
        ...


def _dot(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b, strict=True))


def _norm(v: list[float]) -> float:
    return math.sqrt(sum(x * x for x in v))


class LocalEmbeddingProvider:
    """sentence-transformers based embedding, falls back to TF-IDF hash."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2") -> None:
        self._model_name = model_name
        self._model: object | None = None
        self._loaded = False

    def _load(self) -> None:
        if self._loaded:
            return
        try:
            from sentence_transformers import (
                SentenceTransformer,  # type: ignore[import-untyped]
            )

            self._model = SentenceTransformer(self._model_name, local_files_only=True)
            logger.info("Loaded embedding model %s", self._model_name)
        except Exception as exc:
            logger.warning(
                "sentence-transformers unavailable (%s); using hash fallback",
                exc,
            )
            self._model = None
        self._loaded = True

    async def embed(self, texts: list[str]) -> list[list[float]]:
        self._load()
        if self._model is not None:
            from sentence_transformers import (
                SentenceTransformer,  # type: ignore[import-untyped]
            )

            model: SentenceTransformer = self._model  # type: ignore[assignment]
            vectors = model.encode(texts, show_progress_bar=False)
            return [v.tolist() for v in vectors]
        return [_hash_embed(t) for t in texts]

    def cosine_similarity(self, a: list[float], b: list[float]) -> float:
        na, nb = _norm(a), _norm(b)
        if na == 0 or nb == 0:
            return 0.0
        return _dot(a, b) / (na * nb)


def _hash_embed(text: str, dim: int = 64) -> list[float]:
    """Simple deterministic hash-based embedding used when ST is unavailable."""
    vec = [0.0] * dim
    words = text.lower().split()
    for word in words:
        h = int.from_bytes(hashlib.sha256(word.encode("utf-8")).digest()[:8], "big")
        for i in range(dim):
            sign = 1 if (h >> i) & 1 else -1
            vec[i] += sign
    norm = _norm(vec) or 1.0
    return [x / norm for x in vec]
