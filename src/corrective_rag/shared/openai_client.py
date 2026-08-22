from __future__ import annotations

import logging
from typing import Any, Protocol

logger = logging.getLogger(__name__)

EMBEDDING_MODEL = "text-embedding-3-small"
# USD per 1K tokens, per https://openai.com/api/pricing/ at the time this model was pinned.
EMBEDDING_COST_PER_1K_TOKENS = 0.00002


class _EmbeddingClient(Protocol):
    @property
    def embeddings(self) -> Any: ...


def embed_text(client: _EmbeddingClient, text: str) -> list[float]:
    response = client.embeddings.create(model=EMBEDDING_MODEL, input=text)  # type: ignore[attr-defined]
    usage = response.usage
    cost_usd = (usage.total_tokens / 1000) * EMBEDDING_COST_PER_1K_TOKENS
    logger.info(
        "openai_embedding_call model=%s tokens=%d cost_usd=%.6f",
        EMBEDDING_MODEL,
        usage.total_tokens,
        cost_usd,
    )
    return list(response.data[0].embedding)
