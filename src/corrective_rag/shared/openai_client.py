from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Protocol

logger = logging.getLogger(__name__)

EMBEDDING_MODEL = "text-embedding-3-small"
# USD per 1K tokens, per https://openai.com/api/pricing/ at the time this model was pinned.
EMBEDDING_COST_PER_1K_TOKENS = 0.00002


class EmbeddingClient(Protocol):
    @property
    def embeddings(self) -> Any: ...


@dataclass(frozen=True)
class EmbeddingResult:
    vector: list[float]
    tokens_used: int
    estimated_cost_usd: float


def _call_embeddings(client: EmbeddingClient, text: str) -> EmbeddingResult:
    response = client.embeddings.create(model=EMBEDDING_MODEL, input=text)  # type: ignore[attr-defined]
    usage = response.usage
    cost_usd = (usage.total_tokens / 1000) * EMBEDDING_COST_PER_1K_TOKENS
    logger.info(
        "openai_embedding_call model=%s tokens=%d cost_usd=%.6f",
        EMBEDDING_MODEL,
        usage.total_tokens,
        cost_usd,
    )
    return EmbeddingResult(
        vector=list(response.data[0].embedding),
        tokens_used=usage.total_tokens,
        estimated_cost_usd=cost_usd,
    )


def embed_text(client: EmbeddingClient, text: str) -> list[float]:
    return _call_embeddings(client, text).vector


def embed_text_with_usage(client: EmbeddingClient, text: str) -> EmbeddingResult:
    return _call_embeddings(client, text)
