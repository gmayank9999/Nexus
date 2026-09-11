"""Memory extractor: identifies candidate memories from agent run context."""

from __future__ import annotations

import json
import logging

from pydantic import ValidationError

from app.memory.models import Memory, MemoryCandidate
from app.memory.repository import MemoryRepository
from app.providers.base import LLMProvider, Message

logger = logging.getLogger(__name__)

_EXTRACTOR_SYSTEM = """\
You are a memory extraction assistant for NEXUS AI.
Analyze the conversation/run summary and extract important facts worth remembering.

Output a JSON array (no markdown) of objects:
[
  {
    "category": "user_preference|user_goal|user_fact|"
                "project_context|learning_state|task_context",
    "content": "concise statement of the memory",
    "confidence": 0.0..1.0
  }
]

Rules:
- Only extract facts that are genuinely useful for future interactions.
- Do NOT extract tool call details or internal agent steps.
- Keep each memory concise (< 200 characters).
- confidence: 1.0 = explicitly stated, 0.7 = strongly implied, 0.5 = uncertain.
- Return [] if nothing is worth remembering.
"""


class MemoryExtractor:
    """Extracts candidate memories from text using an LLM provider."""

    def __init__(self, provider: LLMProvider, repository: MemoryRepository) -> None:
        self._provider = provider
        self._repo = repository

    async def extract_and_save(
        self,
        user_id: str,
        run_id: str,
        summary: str,
        min_confidence: float = 0.6,
    ) -> list[Memory]:
        """Extract memories from *summary* and persist them above the threshold."""
        candidates = await self._extract(summary)
        saved: list[Memory] = []
        for candidate in candidates:
            if candidate.confidence < min_confidence:
                continue
            memory = Memory(
                user_id=user_id,
                run_id=run_id,
                category=candidate.category,
                content=candidate.content,
                confidence=candidate.confidence,
                source="agent",
            )
            await self._repo.create(memory)
            saved.append(memory)
        logger.info(
            "Extracted %d memories from run %s (threshold %.1f)",
            len(saved),
            run_id,
            min_confidence,
        )
        return saved

    async def _extract(self, summary: str) -> list[MemoryCandidate]:
        try:
            response = await self._provider.generate(
                messages=[
                    Message(role="system", content=_EXTRACTOR_SYSTEM),
                    Message(
                        role="user",
                        content=f"Extract memories from:\n\n{summary}",
                    ),
                ]
            )
            raw = response.content.strip()
            # Strip markdown code fences if present
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[1].rsplit("```", 1)[0]
            data = json.loads(raw)
            candidates: list[MemoryCandidate] = []
            for item in data:
                try:
                    candidates.append(MemoryCandidate.model_validate(item))
                except ValidationError as exc:
                    logger.debug("Skipping invalid memory candidate: %s", exc)
            return candidates
        except Exception as exc:
            logger.warning("Memory extraction failed: %s", exc)
            return []
