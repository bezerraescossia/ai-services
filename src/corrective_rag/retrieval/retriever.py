from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

from corrective_rag.ingestion.vector_store import COLLECTION_NAME
from corrective_rag.ingestion.versioning import DEFAULT_BASE_DIR
from corrective_rag.shared.openai_client import (
    EMBEDDING_MODEL,
    EmbeddingClient,
    embed_text_with_usage,
)

logger = logging.getLogger(__name__)

DEFAULT_K = 5


class EmptyQueryError(ValueError):
    """Raised when the query is empty or whitespace-only (FR-006)."""


class EmbeddingModelMismatchError(RuntimeError):
    """Raised when the manifest's pinned embedding model doesn't match the model in use (FR-007)."""


class ManifestNotFoundError(RuntimeError):
    """Raised when a corpus_version's manifest is missing or empty."""


@dataclass(frozen=True)
class RetrievedChunk:
    chunk_id: str
    text: str
    source_document_id: str
    corpus_version: str
    score: float


@dataclass(frozen=True)
class RetrievalResult:
    decision_id: str
    query: str
    retrieved_chunk_ids: list[str] = field(default_factory=list)
    relevance_scores: list[float] = field(default_factory=list)
    chunks: list[RetrievedChunk] = field(default_factory=list)


def read_pinned_embedding_model(corpus_version: str, *, base_dir: Path = DEFAULT_BASE_DIR) -> str:
    manifest_path = base_dir / corpus_version / "chunks" / "manifest.json"
    if not manifest_path.exists():
        raise ManifestNotFoundError(
            f"No corpus manifest found for corpus_version={corpus_version!r} at {manifest_path}"
        )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not manifest:
        raise ManifestNotFoundError(
            f"Corpus manifest for corpus_version={corpus_version!r} is empty"
        )
    return manifest[0]["embedding_model"]


def retrieve(
    *,
    query: str,
    corpus_version: str,
    openai_client: EmbeddingClient,
    qdrant_client: QdrantClient,
    k: int = DEFAULT_K,
    base_dir: Path = DEFAULT_BASE_DIR,
) -> RetrievalResult:
    if not query.strip():
        raise EmptyQueryError("query must not be empty or whitespace-only")

    pinned_model = read_pinned_embedding_model(corpus_version, base_dir=base_dir)
    if pinned_model != EMBEDDING_MODEL:
        raise EmbeddingModelMismatchError(
            f"corpus_version={corpus_version!r} is pinned to embedding_model={pinned_model!r}, "
            f"but the retriever uses {EMBEDDING_MODEL!r}"
        )

    embedding = embed_text_with_usage(openai_client, query)
    logger.info(
        "mod1_retrieval_embedding feature=mod1 tokens_used=%d "
        "estimated_cost_usd=%.6f corpus_version=%s",
        embedding.tokens_used,
        embedding.estimated_cost_usd,
        corpus_version,
    )

    query_filter = qmodels.Filter(
        must=[
            qmodels.FieldCondition(
                key="corpus_version", match=qmodels.MatchValue(value=corpus_version)
            ),
            qmodels.FieldCondition(key="retrievable", match=qmodels.MatchValue(value=True)),
        ]
    )
    hits = qdrant_client.query_points(
        collection_name=COLLECTION_NAME,
        query=embedding.vector,
        query_filter=query_filter,
        limit=k,
    ).points

    chunks = [
        RetrievedChunk(
            chunk_id=hit.payload["chunk_id"],
            text=hit.payload["text"],
            source_document_id=hit.payload["source_document_id"],
            corpus_version=hit.payload["corpus_version"],
            score=hit.score,
        )
        for hit in hits
        if hit.payload is not None
    ]

    logger.info(
        "mod1_retrieval_complete feature=mod1 corpus_version=%s k=%d returned=%d",
        corpus_version,
        k,
        len(chunks),
    )

    return RetrievalResult(
        decision_id=str(uuid.uuid4()),
        query=query,
        retrieved_chunk_ids=[chunk.chunk_id for chunk in chunks],
        relevance_scores=[chunk.score for chunk in chunks],
        chunks=chunks,
    )
