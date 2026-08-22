from __future__ import annotations

import logging
from dataclasses import dataclass, field

import httpx
from openai import OpenAI
from qdrant_client import QdrantClient

from corrective_rag.ingestion.chunking import split_into_chunks
from corrective_rag.ingestion.vector_store import ChunkRecord, upsert_chunks
from corrective_rag.ingestion.versioning import (
    compute_corpus_version,
    persist_corpus_version,
    version_exists,
)
from corrective_rag.ingestion.wikipedia_client import fetch_articles
from corrective_rag.shared.openai_client import EMBEDDING_MODEL, embed_text

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class IngestionResult:
    corpus_version: str
    chunk_count: int
    chunk_ids: list[str] = field(default_factory=list)
    skipped_existing: bool = False


def run_ingestion(
    *,
    titles: list[str],
    wiki_client: httpx.Client,
    openai_client: OpenAI,
    qdrant_client: QdrantClient,
) -> IngestionResult:
    articles = fetch_articles(wiki_client, titles)
    logger.info("ingestion_articles_fetched count=%d", len(articles))

    corpus_version = compute_corpus_version(articles)
    chunks_by_article = [
        (article, split_into_chunks(article.title, article.extract_text)) for article in articles
    ]
    all_chunks = [chunk for _, chunks in chunks_by_article for chunk in chunks]

    if version_exists(corpus_version):
        logger.info(
            "ingestion_run_skipped_existing corpus_version=%s chunks=%d",
            corpus_version,
            len(all_chunks),
        )
        return IngestionResult(
            corpus_version=corpus_version,
            chunk_count=len(all_chunks),
            chunk_ids=[chunk.chunk_id for chunk in all_chunks],
            skipped_existing=True,
        )

    for _, article_chunks in chunks_by_article:
        records = [
            ChunkRecord(
                chunk_id=chunk.chunk_id,
                corpus_version=corpus_version,
                source_document_id=chunk.source_document_id,
                text=chunk.text,
                embedding=embed_text(openai_client, chunk.text),
            )
            for chunk in article_chunks
        ]
        if records:
            upsert_chunks(qdrant_client, records)

    persist_corpus_version(
        corpus_version,
        articles=articles,
        chunks=all_chunks,
        embedding_model=EMBEDDING_MODEL,
        embedding_model_version=EMBEDDING_MODEL,
    )

    logger.info(
        "ingestion_run_complete corpus_version=%s chunks=%d",
        corpus_version,
        len(all_chunks),
    )

    return IngestionResult(
        corpus_version=corpus_version,
        chunk_count=len(all_chunks),
        chunk_ids=[chunk.chunk_id for chunk in all_chunks],
    )
