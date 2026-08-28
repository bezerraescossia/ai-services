from __future__ import annotations

import json
import logging
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

from corrective_rag.ingestion.vector_store import ChunkRecord, upsert_chunks
from corrective_rag.retrieval.retriever import (
    DEFAULT_K,
    EmbeddingModelMismatchError,
    EmptyQueryError,
    ManifestNotFoundError,
    read_pinned_embedding_model,
    retrieve,
)
from corrective_rag.shared.openai_client import EMBEDDING_MODEL

CORPUS_VERSION = "20260822-deadbeef"


class _FakeEmbeddings:
    def __init__(self, vector: list[float] | None = None) -> None:
        self._vector = _pad(vector or [1.0, 0.0, 0.0])
        self.call_count = 0

    def create(self, *, model: str, input: str):
        self.call_count += 1
        return SimpleNamespace(
            data=[SimpleNamespace(embedding=self._vector)],
            usage=SimpleNamespace(total_tokens=5),
        )


class _FakeOpenAI:
    def __init__(self, vector: list[float] | None = None) -> None:
        self.embeddings = _FakeEmbeddings(vector)


def _write_manifest(base_dir: Path, corpus_version: str, embedding_model: str) -> None:
    manifest_dir = base_dir / corpus_version / "chunks"
    manifest_dir.mkdir(parents=True, exist_ok=True)
    manifest = [
        {
            "chunk_id": "chunk-0",
            "source_document_id": "Apollo 11",
            "text": "text",
            "embedding_model": embedding_model,
            "embedding_model_version": embedding_model,
        }
    ]
    (manifest_dir / "manifest.json").write_text(json.dumps(manifest))


def _qdrant_client() -> QdrantClient:
    return QdrantClient(":memory:")


def _pad(vector: list[float]) -> list[float]:
    """Pad a short test vector to the collection's fixed 1536 dims (zeros preserve direction)."""
    return vector + [0.0] * (1536 - len(vector))


def _seed_chunk(
    client: QdrantClient,
    *,
    chunk_id: str,
    corpus_version: str,
    retrievable: bool,
    embedding: list[float],
    source_document_id: str = "Apollo 11",
    text: str = "some chunk text",
) -> None:
    upsert_chunks(
        client,
        [
            ChunkRecord(
                chunk_id=chunk_id,
                corpus_version=corpus_version,
                source_document_id=source_document_id,
                text=text,
                embedding=_pad(embedding),
            )
        ],
    )
    # upsert_chunks always writes retrievable=false by default (DP1 behavior);
    # flip it here to simulate DP2 having cleared the chunk, when needed.
    if retrievable:
        chunk_id_filter = qmodels.Filter(
            must=[qmodels.FieldCondition(key="chunk_id", match=qmodels.MatchValue(value=chunk_id))]
        )
        client.set_payload(
            collection_name="document_chunks",
            payload={"retrievable": True},
            points=[
                p.id
                for p in client.scroll(
                    collection_name="document_chunks",
                    scroll_filter=chunk_id_filter,
                    limit=1,
                )[0]
            ],
        )


# --- read_pinned_embedding_model -------------------------------------------------


def test_read_pinned_embedding_model_returns_model_from_manifest(tmp_path: Path):
    _write_manifest(tmp_path, CORPUS_VERSION, "text-embedding-3-small")

    model = read_pinned_embedding_model(CORPUS_VERSION, base_dir=tmp_path)

    assert model == "text-embedding-3-small"


def test_read_pinned_embedding_model_raises_when_manifest_missing(tmp_path: Path):
    with pytest.raises(ManifestNotFoundError):
        read_pinned_embedding_model(CORPUS_VERSION, base_dir=tmp_path)


def test_read_pinned_embedding_model_raises_when_manifest_empty(tmp_path: Path):
    manifest_dir = tmp_path / CORPUS_VERSION / "chunks"
    manifest_dir.mkdir(parents=True)
    (manifest_dir / "manifest.json").write_text("[]")

    with pytest.raises(ManifestNotFoundError):
        read_pinned_embedding_model(CORPUS_VERSION, base_dir=tmp_path)


# --- validation / guard paths ------------------------------------------------------


def test_retrieve_raises_on_empty_query_before_any_api_call(tmp_path: Path):
    _write_manifest(tmp_path, CORPUS_VERSION, EMBEDDING_MODEL)
    openai_client = _FakeOpenAI()

    with pytest.raises(EmptyQueryError):
        retrieve(
            query="   ",
            corpus_version=CORPUS_VERSION,
            openai_client=openai_client,
            qdrant_client=_qdrant_client(),
            base_dir=tmp_path,
        )

    assert openai_client.embeddings.call_count == 0


def test_retrieve_raises_on_embedding_model_mismatch_before_any_api_call(tmp_path: Path):
    _write_manifest(tmp_path, CORPUS_VERSION, "some-other-embedding-model")
    openai_client = _FakeOpenAI()

    with pytest.raises(EmbeddingModelMismatchError):
        retrieve(
            query="What were the goals of the Apollo 11 mission?",
            corpus_version=CORPUS_VERSION,
            openai_client=openai_client,
            qdrant_client=_qdrant_client(),
            base_dir=tmp_path,
        )

    assert openai_client.embeddings.call_count == 0


# --- Qdrant interaction: filtering, ordering, k -------------------------------------


def test_retrieve_returns_default_k_ordered_descending_by_score(tmp_path: Path):
    _write_manifest(tmp_path, CORPUS_VERSION, EMBEDDING_MODEL)
    client = _qdrant_client()
    for i in range(6):
        # Chunks progressively less aligned with the query vector [1, 0, 0].
        vector = [1.0 - i * 0.1, i * 0.1, 0.0]
        _seed_chunk(
            client,
            chunk_id=f"chunk-{i}",
            corpus_version=CORPUS_VERSION,
            retrievable=True,
            embedding=vector,
        )

    result = retrieve(
        query="What were the goals of the Apollo 11 mission?",
        corpus_version=CORPUS_VERSION,
        openai_client=_FakeOpenAI([1.0, 0.0, 0.0]),
        qdrant_client=client,
        base_dir=tmp_path,
    )

    assert len(result.chunks) == DEFAULT_K == 5
    assert result.relevance_scores == sorted(result.relevance_scores, reverse=True)
    for chunk in result.chunks:
        assert chunk.chunk_id
        assert chunk.text
        assert chunk.source_document_id
        assert chunk.corpus_version == CORPUS_VERSION


def test_retrieve_respects_a_custom_k(tmp_path: Path):
    _write_manifest(tmp_path, CORPUS_VERSION, EMBEDDING_MODEL)
    client = _qdrant_client()
    for i in range(6):
        _seed_chunk(
            client,
            chunk_id=f"chunk-{i}",
            corpus_version=CORPUS_VERSION,
            retrievable=True,
            embedding=[1.0 - i * 0.1, i * 0.1, 0.0],
        )

    result = retrieve(
        query="What were the goals of the Apollo 11 mission?",
        corpus_version=CORPUS_VERSION,
        openai_client=_FakeOpenAI([1.0, 0.0, 0.0]),
        qdrant_client=client,
        k=3,
        base_dir=tmp_path,
    )

    assert len(result.chunks) == 3


def test_retrieve_never_returns_a_non_retrievable_chunk_even_if_higher_scoring(tmp_path: Path):
    _write_manifest(tmp_path, CORPUS_VERSION, EMBEDDING_MODEL)
    client = _qdrant_client()
    # This chunk is a perfect match for the query vector but is not yet cleared.
    _seed_chunk(
        client,
        chunk_id="unpublished-best-match",
        corpus_version=CORPUS_VERSION,
        retrievable=False,
        embedding=[1.0, 0.0, 0.0],
    )
    for i in range(5):
        _seed_chunk(
            client,
            chunk_id=f"chunk-{i}",
            corpus_version=CORPUS_VERSION,
            retrievable=True,
            embedding=[0.5 - i * 0.05, 0.5, 0.0],
        )

    result = retrieve(
        query="What were the goals of the Apollo 11 mission?",
        corpus_version=CORPUS_VERSION,
        openai_client=_FakeOpenAI([1.0, 0.0, 0.0]),
        qdrant_client=client,
        base_dir=tmp_path,
    )

    assert "unpublished-best-match" not in result.retrieved_chunk_ids


def test_retrieve_excludes_chunks_from_a_different_corpus_version(tmp_path: Path):
    _write_manifest(tmp_path, CORPUS_VERSION, EMBEDDING_MODEL)
    client = _qdrant_client()
    _seed_chunk(
        client,
        chunk_id="other-version-chunk",
        corpus_version="20260822-otherversion",
        retrievable=True,
        embedding=[1.0, 0.0, 0.0],
    )
    _seed_chunk(
        client,
        chunk_id="this-version-chunk",
        corpus_version=CORPUS_VERSION,
        retrievable=True,
        embedding=[0.9, 0.1, 0.0],
    )

    result = retrieve(
        query="What were the goals of the Apollo 11 mission?",
        corpus_version=CORPUS_VERSION,
        openai_client=_FakeOpenAI([1.0, 0.0, 0.0]),
        qdrant_client=client,
        base_dir=tmp_path,
    )

    assert result.retrieved_chunk_ids == ["this-version-chunk"]


def test_retrieve_returns_fewer_than_k_without_raising_when_corpus_is_smaller(tmp_path: Path):
    _write_manifest(tmp_path, CORPUS_VERSION, EMBEDDING_MODEL)
    client = _qdrant_client()
    _seed_chunk(
        client,
        chunk_id="only-chunk",
        corpus_version=CORPUS_VERSION,
        retrievable=True,
        embedding=[1.0, 0.0, 0.0],
    )

    result = retrieve(
        query="What were the goals of the Apollo 11 mission?",
        corpus_version=CORPUS_VERSION,
        openai_client=_FakeOpenAI([1.0, 0.0, 0.0]),
        qdrant_client=client,
        base_dir=tmp_path,
    )

    assert len(result.chunks) == 1


# --- logging -------------------------------------------------------------------------


def test_retrieve_logs_tokens_cost_and_corpus_version(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
):
    _write_manifest(tmp_path, CORPUS_VERSION, EMBEDDING_MODEL)
    client = _qdrant_client()
    _seed_chunk(
        client,
        chunk_id="only-chunk",
        corpus_version=CORPUS_VERSION,
        retrievable=True,
        embedding=[1.0, 0.0, 0.0],
    )

    with caplog.at_level(logging.INFO):
        retrieve(
            query="What were the goals of the Apollo 11 mission?",
            corpus_version=CORPUS_VERSION,
            openai_client=_FakeOpenAI([1.0, 0.0, 0.0]),
            qdrant_client=client,
            base_dir=tmp_path,
        )

    messages = [record.getMessage() for record in caplog.records]
    embedding_lines = [m for m in messages if "feature=mod1" in m and "tokens_used" in m]
    assert embedding_lines
    assert f"corpus_version={CORPUS_VERSION}" in embedding_lines[0]


def test_retrieve_logs_the_actual_returned_count_when_fewer_than_k(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
):
    _write_manifest(tmp_path, CORPUS_VERSION, EMBEDDING_MODEL)
    client = _qdrant_client()
    _seed_chunk(
        client,
        chunk_id="only-chunk",
        corpus_version=CORPUS_VERSION,
        retrievable=True,
        embedding=[1.0, 0.0, 0.0],
    )

    with caplog.at_level(logging.INFO):
        retrieve(
            query="What were the goals of the Apollo 11 mission?",
            corpus_version=CORPUS_VERSION,
            openai_client=_FakeOpenAI([1.0, 0.0, 0.0]),
            qdrant_client=client,
            base_dir=tmp_path,
        )

    messages = [record.getMessage() for record in caplog.records]
    assert any("returned=1" in m and "k=5" in m for m in messages)


# --- FR-009: Qdrant connectivity errors propagate without retry ----------------------


def test_retrieve_propagates_qdrant_errors_without_retrying(tmp_path: Path):
    _write_manifest(tmp_path, CORPUS_VERSION, EMBEDDING_MODEL)

    class _ConnectionError(Exception):
        pass

    spy_client = MagicMock()
    spy_client.query_points.side_effect = _ConnectionError("Qdrant unreachable")

    with pytest.raises(_ConnectionError):
        retrieve(
            query="What were the goals of the Apollo 11 mission?",
            corpus_version=CORPUS_VERSION,
            openai_client=_FakeOpenAI([1.0, 0.0, 0.0]),
            qdrant_client=spy_client,
            base_dir=tmp_path,
        )

    assert spy_client.query_points.call_count == 1
