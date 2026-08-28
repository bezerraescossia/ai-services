import os

import pytest
from openai import OpenAI
from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

from corrective_rag.ingestion.vector_store import COLLECTION_NAME
from corrective_rag.retrieval.retriever import retrieve

requires_openai_key = pytest.mark.skipif(
    not os.environ.get("OPENAI_API_KEY"),
    reason="OPENAI_API_KEY not set — integration test requires a real embedding call",
)

CORPUS_VERSION = "20260822-eac47701064f"


def _qdrant_client() -> QdrantClient:
    return QdrantClient(url=os.environ.get("QDRANT_URL", "http://localhost:6333"))


@requires_openai_key
def test_retrieve_returns_relevant_chunks_from_live_corpus():
    result = retrieve(
        query="What were the goals of the Apollo 11 mission?",
        corpus_version=CORPUS_VERSION,
        openai_client=OpenAI(),
        qdrant_client=_qdrant_client(),
        k=5,
    )

    assert len(result.chunks) == 5
    assert any("Apollo 11" in chunk.source_document_id for chunk in result.chunks)  # SC-001


@requires_openai_key
def test_retrieve_never_returns_a_non_retrievable_chunk_from_live_corpus():
    qdrant = _qdrant_client()

    result = retrieve(
        query="What were the goals of the Apollo 11 mission?",
        corpus_version=CORPUS_VERSION,
        openai_client=OpenAI(),
        qdrant_client=qdrant,
        k=5,
    )

    chunk_id_filter = qmodels.Filter(
        must=[
            qmodels.FieldCondition(
                key="corpus_version", match=qmodels.MatchValue(value=CORPUS_VERSION)
            ),
            qmodels.FieldCondition(
                key="chunk_id", match=qmodels.MatchAny(any=result.retrieved_chunk_ids)
            ),
        ]
    )
    points, _ = qdrant.scroll(
        collection_name=COLLECTION_NAME,
        scroll_filter=chunk_id_filter,
        limit=len(result.retrieved_chunk_ids),
        with_payload=True,
    )
    assert len(points) == len(result.retrieved_chunk_ids)
    assert all(point.payload["retrievable"] is True for point in points)  # SC-002
