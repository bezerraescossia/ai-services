from __future__ import annotations

import json
import uuid
from pathlib import Path
from unittest.mock import patch

import pytest
from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

from corrective_rag.ingestion.vector_store import COLLECTION_NAME
from corrective_rag.scrubbing.scanner import ScanAbortedError, ScanResult, run_scan

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _point_id(chunk_id: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, chunk_id))


def _make_point(
    chunk_id: str,
    corpus_version: str,
    text: str,
    *,
    retrievable: bool = False,
    pii_flagged: bool = False,
) -> qmodels.PointStruct:
    return qmodels.PointStruct(
        id=_point_id(chunk_id),
        vector=[0.0] * 1536,
        payload={
            "chunk_id": chunk_id,
            "corpus_version": corpus_version,
            "source_document_id": "doc-1",
            "text": text,
            "pii_flagged": pii_flagged,
            "retrievable": retrievable,
            "embedding_ref": _point_id(chunk_id),
        },
    )


# ---------------------------------------------------------------------------
# Fixture: in-memory Qdrant with 3 chunks
#   chunk-clean  — no PII, unpublished  → should become retrievable=True, pii_flagged=False
#   chunk-email  — planted email        → retrievable=True, pii_flagged=True, text redacted
#   chunk-done   — already retrievable  → must be unchanged (idempotency)
# ---------------------------------------------------------------------------

CORPUS_VERSION = "20260824-test0001"

CHUNK_CLEAN_ID = "chunk-clean"
CHUNK_EMAIL_ID = "chunk-email"
CHUNK_DONE_ID = "chunk-done"

CLEAN_TEXT = "Neil Armstrong walked on the Moon in July 1969."
EMAIL_TEXT = "Contact mission_control@example.invalid for updates."
DONE_TEXT = "Already published, no action needed."


@pytest.fixture()
def qdrant_client() -> QdrantClient:
    client = QdrantClient(":memory:")
    client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=qmodels.VectorParams(size=1536, distance=qmodels.Distance.COSINE),
    )
    client.upsert(
        collection_name=COLLECTION_NAME,
        points=[
            _make_point(CHUNK_CLEAN_ID, CORPUS_VERSION, CLEAN_TEXT),
            _make_point(CHUNK_EMAIL_ID, CORPUS_VERSION, EMAIL_TEXT),
            _make_point(
                CHUNK_DONE_ID, CORPUS_VERSION, DONE_TEXT, retrievable=True, pii_flagged=False
            ),
        ],
    )
    return client


def _get_payload(client: QdrantClient, chunk_id: str) -> dict:
    results, _ = client.scroll(
        collection_name=COLLECTION_NAME,
        scroll_filter=qmodels.Filter(
            must=[qmodels.FieldCondition(key="chunk_id", match=qmodels.MatchValue(value=chunk_id))]
        ),
        with_payload=True,
        limit=1,
    )
    assert results, f"chunk {chunk_id!r} not found in Qdrant"
    return results[0].payload or {}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestRunScanHappyPath:
    def test_clean_chunk_becomes_retrievable(
        self, qdrant_client: QdrantClient, tmp_path: Path
    ) -> None:
        run_scan(CORPUS_VERSION, qdrant_client, tmp_path)
        payload = _get_payload(qdrant_client, CHUNK_CLEAN_ID)
        assert payload["retrievable"] is True
        assert payload["pii_flagged"] is False

    def test_email_chunk_is_flagged_and_retrievable(
        self, qdrant_client: QdrantClient, tmp_path: Path
    ) -> None:
        run_scan(CORPUS_VERSION, qdrant_client, tmp_path)
        payload = _get_payload(qdrant_client, CHUNK_EMAIL_ID)
        assert payload["retrievable"] is True
        assert payload["pii_flagged"] is True
        assert "mission_control@example.invalid" not in payload["text"]
        assert "[REDACTED:EMAIL]" in payload["text"]

    def test_already_resolved_chunk_is_unchanged(
        self, qdrant_client: QdrantClient, tmp_path: Path
    ) -> None:
        run_scan(CORPUS_VERSION, qdrant_client, tmp_path)
        payload = _get_payload(qdrant_client, CHUNK_DONE_ID)
        # Still clean and still retrievable — no change
        assert payload["retrievable"] is True
        assert payload["pii_flagged"] is False
        assert payload["text"] == DONE_TEXT

    def test_returns_scan_result(self, qdrant_client: QdrantClient, tmp_path: Path) -> None:
        result = run_scan(CORPUS_VERSION, qdrant_client, tmp_path)
        assert isinstance(result, ScanResult)
        assert result.corpus_version == CORPUS_VERSION
        assert result.scanned == 2  # chunk-done is skipped (already retrievable)
        assert result.clean == 1
        assert result.flagged == 1

    def test_audit_jsonl_has_two_records(self, qdrant_client: QdrantClient, tmp_path: Path) -> None:
        run_scan(CORPUS_VERSION, qdrant_client, tmp_path)
        audit_file = tmp_path / "audit.jsonl"
        assert audit_file.exists()
        lines = audit_file.read_text().strip().splitlines()
        assert len(lines) == 2  # chunk-done skipped, clean + email scanned
        chunk_ids = {json.loads(line)["chunk_id"] for line in lines}
        assert CHUNK_CLEAN_ID in chunk_ids
        assert CHUNK_EMAIL_ID in chunk_ids
        assert CHUNK_DONE_ID not in chunk_ids


class TestRunScanIdempotency:
    def test_re_run_does_not_change_already_resolved_chunks(
        self, qdrant_client: QdrantClient, tmp_path: Path
    ) -> None:
        run_scan(CORPUS_VERSION, qdrant_client, tmp_path)
        # Second run — all chunks are now retrievable, nothing to scan
        result = run_scan(CORPUS_VERSION, qdrant_client, tmp_path)
        assert result.scanned == 0
        assert result.clean == 0
        assert result.flagged == 0

    def test_re_run_does_not_duplicate_audit_records(
        self, qdrant_client: QdrantClient, tmp_path: Path
    ) -> None:
        audit_file = tmp_path / "audit.jsonl"
        run_scan(CORPUS_VERSION, qdrant_client, tmp_path)
        first_count = len(audit_file.read_text().strip().splitlines())
        run_scan(CORPUS_VERSION, qdrant_client, tmp_path)
        second_count = len(audit_file.read_text().strip().splitlines())
        assert first_count == second_count  # second run writes nothing


class TestRunScanAbortOnError:
    def test_detector_error_raises_scan_aborted(
        self, qdrant_client: QdrantClient, tmp_path: Path
    ) -> None:
        from corrective_rag.scrubbing import detector as detector_module

        original_detect = detector_module.detect

        call_count = 0

        def flaky_detect(text: str):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("simulated detector failure")
            return original_detect(text)

        with (
            patch.object(detector_module, "detect", side_effect=flaky_detect),
            pytest.raises(ScanAbortedError),
        ):
            run_scan(CORPUS_VERSION, qdrant_client, tmp_path)

    def test_no_qdrant_writes_on_abort(self, qdrant_client: QdrantClient, tmp_path: Path) -> None:
        from corrective_rag.scrubbing import detector as detector_module

        def always_fail(text: str):
            raise RuntimeError("simulated detector failure")

        with (
            patch.object(detector_module, "detect", side_effect=always_fail),
            pytest.raises(ScanAbortedError),
        ):
            run_scan(CORPUS_VERSION, qdrant_client, tmp_path)

        # Neither chunk-clean nor chunk-email should have been mutated
        clean_payload = _get_payload(qdrant_client, CHUNK_CLEAN_ID)
        email_payload = _get_payload(qdrant_client, CHUNK_EMAIL_ID)
        assert clean_payload["retrievable"] is False
        assert email_payload["retrievable"] is False

    def test_no_audit_records_written_on_abort(
        self, qdrant_client: QdrantClient, tmp_path: Path
    ) -> None:
        from corrective_rag.scrubbing import detector as detector_module

        def always_fail(text: str):
            raise RuntimeError("simulated detector failure")

        with (
            patch.object(detector_module, "detect", side_effect=always_fail),
            pytest.raises(ScanAbortedError),
        ):
            run_scan(CORPUS_VERSION, qdrant_client, tmp_path)

        audit_file = tmp_path / "audit.jsonl"
        assert not audit_file.exists() or audit_file.read_text().strip() == ""
