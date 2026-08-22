import os

import httpx
import pytest
from openai import OpenAI
from qdrant_client import QdrantClient

from corrective_rag.ingestion.pipeline import run_ingestion
from corrective_rag.ingestion.vector_store import COLLECTION_NAME

requires_openai_key = pytest.mark.skipif(
    not os.environ.get("OPENAI_API_KEY"),
    reason="OPENAI_API_KEY not set — integration test requires a real embedding call",
)

FIXTURE_ARTICLES = ["Apollo 11", "Voyager 1"]


def _qdrant_client() -> QdrantClient:
    return QdrantClient(url=os.environ.get("QDRANT_URL", "http://localhost:6333"))


@requires_openai_key
def test_ingest_and_query_returns_relevant_chunks():
    qdrant = _qdrant_client()
    openai_client = OpenAI()
    wiki_client = httpx.Client()

    result = run_ingestion(
        titles=FIXTURE_ARTICLES,
        wiki_client=wiki_client,
        openai_client=openai_client,
        qdrant_client=qdrant,
    )

    assert result.chunk_count > 0
    assert result.corpus_version

    version_filter = {
        "must": [{"key": "corpus_version", "match": {"value": result.corpus_version}}]
    }
    points, _ = qdrant.scroll(
        collection_name=COLLECTION_NAME,
        scroll_filter=version_filter,
        limit=1000,
        with_payload=True,
    )
    assert points
    assert all(p.payload["corpus_version"] == result.corpus_version for p in points)
    assert all(p.payload["retrievable"] is False for p in points)

    query_vector = (
        openai_client.embeddings.create(
            model="text-embedding-3-small", input="Apollo 11 mission goals"
        )
        .data[0]
        .embedding
    )
    hits = qdrant.query_points(collection_name=COLLECTION_NAME, query=query_vector, limit=3).points
    assert hits
    assert any(h.payload["source_document_id"] == "Apollo 11" for h in hits)


@requires_openai_key
def test_rerun_is_idempotent():
    qdrant = _qdrant_client()
    openai_client = OpenAI()
    wiki_client = httpx.Client()

    first = run_ingestion(
        titles=FIXTURE_ARTICLES,
        wiki_client=wiki_client,
        openai_client=openai_client,
        qdrant_client=qdrant,
    )
    second = run_ingestion(
        titles=FIXTURE_ARTICLES,
        wiki_client=wiki_client,
        openai_client=openai_client,
        qdrant_client=qdrant,
    )

    assert first.corpus_version == second.corpus_version
    assert first.chunk_ids == second.chunk_ids
    assert second.skipped_existing is True

    version_filter = {"must": [{"key": "corpus_version", "match": {"value": first.corpus_version}}]}
    points, _ = qdrant.scroll(
        collection_name=COLLECTION_NAME,
        scroll_filter=version_filter,
        limit=1000,
        with_payload=False,
    )
    assert len({p.id for p in points}) == len(first.chunk_ids)
