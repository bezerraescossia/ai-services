from __future__ import annotations

import datetime as dt
import hashlib
import json
import subprocess
from pathlib import Path

from corrective_rag.ingestion.chunking import Chunk
from corrective_rag.ingestion.wikipedia_client import FetchedArticle

DEFAULT_BASE_DIR = Path("data/corrective-rag")


def compute_corpus_version(articles: list[FetchedArticle], *, today: dt.date | None = None) -> str:
    """Pure function: same article content always yields the same corpus_version.

    No disk or DVC I/O here — persistence is a separate step (see the Phase 4
    persistence functions added alongside this one).
    """
    resolved_date = today or dt.date.today()
    content = "\x00".join(
        f"{article.title}\x01{article.extract_text}"
        for article in sorted(articles, key=lambda a: a.title)
    )
    content_hash = hashlib.sha256(content.encode()).hexdigest()[:12]
    return f"{resolved_date:%Y%m%d}-{content_hash}"


def version_exists(corpus_version: str, *, base_dir: Path = DEFAULT_BASE_DIR) -> bool:
    """Whether this corpus_version was already persisted (drives the idempotency short-circuit)."""
    return (base_dir / corpus_version / "chunks" / "manifest.json").exists()


def persist_corpus_version(
    corpus_version: str,
    *,
    articles: list[FetchedArticle],
    chunks: list[Chunk],
    embedding_model: str,
    embedding_model_version: str,
    base_dir: Path = DEFAULT_BASE_DIR,
) -> Path:
    """Write raw articles + chunk manifest under base_dir/<corpus_version>/ and `dvc add` them.

    Per data-preparation.md's Versioning Scheme: raw/ and chunks/manifest.json are
    each DVC-tracked so a prior corpus_version can be reproduced via `dvc checkout`.
    """
    version_dir = base_dir / corpus_version
    raw_dir = version_dir / "raw"
    chunks_dir = version_dir / "chunks"
    raw_dir.mkdir(parents=True, exist_ok=True)
    chunks_dir.mkdir(parents=True, exist_ok=True)

    for article in articles:
        raw_path = raw_dir / f"{article.title}.json"
        raw_path.write_text(
            json.dumps(
                {
                    "title": article.title,
                    "fetched_at": article.fetched_at,
                    "extract_text": article.extract_text,
                },
                indent=2,
            )
        )

    manifest = [
        {
            "chunk_id": chunk.chunk_id,
            "source_document_id": chunk.source_document_id,
            "text": chunk.text,
            "embedding_model": embedding_model,
            "embedding_model_version": embedding_model_version,
        }
        for chunk in chunks
    ]
    (chunks_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))

    subprocess.run(["dvc", "add", str(version_dir)], check=True, capture_output=True)

    return version_dir
