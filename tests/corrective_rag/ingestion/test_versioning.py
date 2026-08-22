import datetime as dt
import json
import subprocess

from corrective_rag.ingestion.chunking import split_into_chunks
from corrective_rag.ingestion.versioning import (
    compute_corpus_version,
    persist_corpus_version,
)
from corrective_rag.ingestion.wikipedia_client import FetchedArticle

FIXED_DATE = dt.date(2026, 8, 22)


def _articles() -> list[FetchedArticle]:
    fetched_at = "2026-08-22T00:00:00+00:00"
    return [
        FetchedArticle(title="Apollo 11", extract_text="text a", fetched_at=fetched_at),
        FetchedArticle(title="Voyager 1", extract_text="text b", fetched_at=fetched_at),
    ]


def test_same_content_produces_same_corpus_version():
    v1 = compute_corpus_version(_articles(), today=FIXED_DATE)
    v2 = compute_corpus_version(_articles(), today=FIXED_DATE)

    assert v1 == v2


def test_different_content_produces_different_corpus_version():
    articles = _articles()
    v1 = compute_corpus_version(articles, today=FIXED_DATE)

    articles[0] = FetchedArticle(
        title="Apollo 11", extract_text="different text", fetched_at="2026-08-22T00:00:00+00:00"
    )
    v2 = compute_corpus_version(articles, today=FIXED_DATE)

    assert v1 != v2


def test_article_order_does_not_affect_corpus_version():
    articles = _articles()
    v1 = compute_corpus_version(articles, today=FIXED_DATE)
    v2 = compute_corpus_version(list(reversed(articles)), today=FIXED_DATE)

    assert v1 == v2


def test_compute_corpus_version_has_no_side_effects(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    compute_corpus_version(_articles(), today=FIXED_DATE)

    assert list(tmp_path.iterdir()) == []


def test_persist_and_checkout_roundtrip(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    subprocess.run(["dvc", "init", "--no-scm", "-q"], check=True, cwd=tmp_path)

    articles = _articles()
    long_text = "Apollo 11 was the spaceflight that first landed humans on the Moon. " * 3
    chunks = split_into_chunks(articles[0].title, long_text)
    corpus_version = "20260822-testhash"
    base_dir = tmp_path / "data" / "corrective-rag"

    version_dir = persist_corpus_version(
        corpus_version,
        articles=articles,
        chunks=chunks,
        embedding_model="text-embedding-3-small",
        embedding_model_version="text-embedding-3-small",
        base_dir=base_dir,
    )

    manifest_path = version_dir / "chunks" / "manifest.json"
    raw_path = version_dir / "raw" / "Apollo 11.json"
    assert manifest_path.exists()
    assert raw_path.exists()
    original_manifest = manifest_path.read_text()
    original_raw = raw_path.read_text()

    manifest_path.unlink()
    raw_path.unlink()
    subprocess.run(["dvc", "checkout", str(version_dir)], check=True, cwd=tmp_path)

    assert manifest_path.read_text() == original_manifest
    assert raw_path.read_text() == original_raw

    manifest = json.loads(original_manifest)
    assert manifest[0]["chunk_id"] == chunks[0].chunk_id
    assert manifest[0]["source_document_id"] == "Apollo 11"
    assert manifest[0]["embedding_model"] == "text-embedding-3-small"
