from __future__ import annotations

import uuid
from dataclasses import dataclass

from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

COLLECTION_NAME = "document_chunks"
VECTOR_SIZE = 1536


@dataclass(frozen=True)
class ChunkRecord:
    chunk_id: str
    corpus_version: str
    source_document_id: str
    text: str
    embedding: list[float]


def ensure_collection(client: QdrantClient) -> None:
    if client.collection_exists(COLLECTION_NAME):
        return
    client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=qmodels.VectorParams(size=VECTOR_SIZE, distance=qmodels.Distance.COSINE),
    )


def _point_id(chunk_id: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, chunk_id))


def _point_struct(record: ChunkRecord) -> qmodels.PointStruct:
    point_id = _point_id(record.chunk_id)
    return qmodels.PointStruct(
        id=point_id,
        vector=record.embedding,
        payload={
            "chunk_id": record.chunk_id,
            "corpus_version": record.corpus_version,
            "source_document_id": record.source_document_id,
            "text": record.text,
            "pii_flagged": False,
            "embedding_ref": point_id,
            "retrievable": False,
        },
    )


def upsert_chunks(client: QdrantClient, records: list[ChunkRecord]) -> list[str]:
    """Upsert every record in a single request.

    One `client.upsert` call per chunk fragments Qdrant's RocksDB storage into
    thousands of small segment files over a full ingestion run, eventually
    exhausting the container's open-file limit — batch to keep segment count low.
    """
    ensure_collection(client)
    points = [_point_struct(record) for record in records]
    client.upsert(collection_name=COLLECTION_NAME, points=points)
    return [str(point.id) for point in points]


def upsert_chunk(
    client: QdrantClient,
    *,
    chunk_id: str,
    corpus_version: str,
    source_document_id: str,
    text: str,
    embedding: list[float],
) -> str:
    record = ChunkRecord(
        chunk_id=chunk_id,
        corpus_version=corpus_version,
        source_document_id=source_document_id,
        text=text,
        embedding=embedding,
    )
    return upsert_chunks(client, [record])[0]
