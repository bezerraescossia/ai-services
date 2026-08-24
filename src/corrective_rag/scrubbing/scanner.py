from __future__ import annotations

import datetime as dt
import logging
from dataclasses import dataclass
from pathlib import Path

from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

from corrective_rag.ingestion.vector_store import COLLECTION_NAME
from corrective_rag.scrubbing import detector as detector_module
from corrective_rag.scrubbing.audit import PiiScanRecord, append_audit
from corrective_rag.scrubbing.redactor import redact

logger = logging.getLogger(__name__)

_BATCH_SIZE = 100


@dataclass(frozen=True)
class ScanResult:
    corpus_version: str
    scanned: int
    clean: int
    flagged: int


class ScanAbortedError(Exception):
    """Raised when the detector errors on any single chunk (FR-009).

    No Qdrant mutations are written when this is raised.
    """

    def __init__(self, chunk_id: str, cause: Exception) -> None:
        self.chunk_id = chunk_id
        self.cause = cause
        super().__init__(f"Scan aborted on chunk {chunk_id!r}: {cause}")


def _scroll_unscanned(
    client: QdrantClient, corpus_version: str
) -> list[qmodels.ScoredPoint | qmodels.Record]:
    """Return all points for *corpus_version* that are in DP1's unpublished state."""
    scan_filter = qmodels.Filter(
        must=[
            qmodels.FieldCondition(
                key="corpus_version", match=qmodels.MatchValue(value=corpus_version)
            ),
            qmodels.FieldCondition(key="retrievable", match=qmodels.MatchValue(value=False)),
            qmodels.FieldCondition(key="pii_flagged", match=qmodels.MatchValue(value=False)),
        ]
    )

    all_points: list = []
    offset = None

    while True:
        batch, next_offset = client.scroll(
            collection_name=COLLECTION_NAME,
            scroll_filter=scan_filter,
            with_payload=True,
            with_vectors=False,
            limit=_BATCH_SIZE,
            offset=offset,
        )
        all_points.extend(batch)
        if next_offset is None:
            break
        offset = next_offset

    return all_points


def run_scan(
    corpus_version: str,
    qdrant_client: QdrantClient,
    audit_dir: Path,
) -> ScanResult:
    """Scan every unresolved chunk for *corpus_version*, update Qdrant, write audit.

    Semantics (FR-007, FR-008, FR-009):
    - Idempotent: already-resolved chunks (retrievable=True) are skipped by the filter.
    - Transactional: all Qdrant payload updates are deferred until the full scan
      completes without error; any detector exception aborts with no writes.
    - Abort-on-error: ScanAbortedError is raised (and propagates) on the first
      detector failure, leaving the corpus_version in its current state.
    """
    audit_file = audit_dir / "audit.jsonl"

    points = _scroll_unscanned(qdrant_client, corpus_version)

    if not points:
        logger.info("pii_scan_skipped corpus_version=%s reason=no_unscanned_chunks", corpus_version)
        return ScanResult(corpus_version=corpus_version, scanned=0, clean=0, flagged=0)

    # Phase 1: scan all chunks in-memory — no writes yet (FR-009)
    @dataclass
    class _ChunkResult:
        point_id: str
        chunk_id: str
        original_text: str
        redacted_text: str
        pii_flagged: bool
        categories: list[str]

    results: list[_ChunkResult] = []

    for point in points:
        payload = point.payload or {}
        chunk_id: str = payload.get("chunk_id", str(point.id))
        text: str = payload.get("text", "")

        try:
            spans = detector_module.detect(text)
        except Exception as exc:
            raise ScanAbortedError(chunk_id, exc) from exc

        if spans:
            redacted = redact(text, spans)
            categories = sorted({s.category for s in spans})
            results.append(
                _ChunkResult(
                    point_id=str(point.id),
                    chunk_id=chunk_id,
                    original_text=text,
                    redacted_text=redacted,
                    pii_flagged=True,
                    categories=categories,
                )
            )
        else:
            results.append(
                _ChunkResult(
                    point_id=str(point.id),
                    chunk_id=chunk_id,
                    original_text=text,
                    redacted_text=text,
                    pii_flagged=False,
                    categories=[],
                )
            )

    # Phase 2: bulk-write all Qdrant payload deltas (all-or-nothing per run)
    now = dt.datetime.now(dt.UTC).isoformat()

    for r in results:
        payload_delta: dict = {
            "pii_flagged": r.pii_flagged,
            "retrievable": True,
        }
        if r.pii_flagged:
            payload_delta["text"] = r.redacted_text

        qdrant_client.set_payload(
            collection_name=COLLECTION_NAME,
            payload=payload_delta,
            points=[r.point_id],
        )

        append_audit(
            PiiScanRecord(
                chunk_id=r.chunk_id,
                categories_detected=r.categories,
                action_taken="redacted" if r.pii_flagged else "clean",
                scan_timestamp=now,
            ),
            audit_file,
        )

    clean = sum(1 for r in results if not r.pii_flagged)
    flagged = sum(1 for r in results if r.pii_flagged)

    logger.info(
        "pii_scan_complete corpus_version=%s scanned=%d clean=%d flagged=%d",
        corpus_version,
        len(results),
        clean,
        flagged,
    )

    return ScanResult(
        corpus_version=corpus_version,
        scanned=len(results),
        clean=clean,
        flagged=flagged,
    )
