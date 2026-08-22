from unittest.mock import MagicMock

from qdrant_client import QdrantClient

from corrective_rag.ingestion.vector_store import (
    COLLECTION_NAME,
    ChunkRecord,
    upsert_chunk,
    upsert_chunks,
)


def _client() -> QdrantClient:
    return QdrantClient(":memory:")


def test_upsert_writes_expected_defaults_and_given_corpus_version():
    client = _client()

    upsert_chunk(
        client,
        chunk_id="abc123",
        corpus_version="20260822-deadbeef",
        source_document_id="Apollo 11",
        text="Apollo 11 was the spaceflight...",
        embedding=[0.1] * 1536,
    )

    points, _ = client.scroll(collection_name=COLLECTION_NAME, limit=10, with_payload=True)
    assert len(points) == 1
    payload = points[0].payload
    assert payload["chunk_id"] == "abc123"
    assert payload["corpus_version"] == "20260822-deadbeef"
    assert payload["retrievable"] is False
    assert payload["pii_flagged"] is False
    assert payload["embedding_ref"]


def test_upsert_same_chunk_id_twice_is_idempotent():
    client = _client()

    for _ in range(2):
        upsert_chunk(
            client,
            chunk_id="abc123",
            corpus_version="20260822-deadbeef",
            source_document_id="Apollo 11",
            text="Apollo 11 was the spaceflight...",
            embedding=[0.1] * 1536,
        )

    points, _ = client.scroll(collection_name=COLLECTION_NAME, limit=10, with_payload=True)
    assert len(points) == 1


def test_upsert_chunks_writes_every_record_in_a_single_upsert_call():
    client = _client()
    records = [
        ChunkRecord(
            chunk_id=f"chunk-{i}",
            corpus_version="20260822-deadbeef",
            source_document_id="Apollo 11",
            text=f"chunk text {i}",
            embedding=[0.1] * 1536,
        )
        for i in range(5)
    ]

    upsert_chunks(client, records)

    points, _ = client.scroll(collection_name=COLLECTION_NAME, limit=10, with_payload=True)
    assert {p.payload["chunk_id"] for p in points} == {f"chunk-{i}" for i in range(5)}


def test_upsert_chunks_issues_one_upsert_call_regardless_of_batch_size():
    spy_client = MagicMock()
    spy_client.collection_exists.return_value = True
    records = [
        ChunkRecord(
            chunk_id=f"chunk-{i}",
            corpus_version="20260822-deadbeef",
            source_document_id="Apollo 11",
            text=f"chunk text {i}",
            embedding=[0.1] * 1536,
        )
        for i in range(50)
    ]

    upsert_chunks(spy_client, records)

    assert spy_client.upsert.call_count == 1
    assert len(spy_client.upsert.call_args.kwargs["points"]) == 50
