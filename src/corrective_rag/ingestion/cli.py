from __future__ import annotations

import argparse
import logging
import os
import sys

import httpx
from openai import OpenAI
from qdrant_client import QdrantClient

from corrective_rag.ingestion.pipeline import run_ingestion
from corrective_rag.ingestion.wikipedia_client import WikipediaFetchError

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ingest and index the corrective-rag corpus.")
    parser.add_argument(
        "--articles",
        required=True,
        type=str,
        help="Path to a newline-separated file of Wikipedia article titles.",
    )
    return parser.parse_args(argv)


def _read_titles(path: str) -> list[str]:
    with open(path, encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv if argv is not None else sys.argv[1:])

    if not os.environ.get("OPENAI_API_KEY"):
        print("OPENAI_API_KEY environment variable is required.", file=sys.stderr)
        return 1

    qdrant_url = os.environ.get("QDRANT_URL", "http://localhost:6333")
    titles = _read_titles(args.articles)

    try:
        result = run_ingestion(
            titles=titles,
            wiki_client=httpx.Client(timeout=30.0),
            openai_client=OpenAI(),
            qdrant_client=QdrantClient(url=qdrant_url),
        )
    except WikipediaFetchError as exc:
        print(f"Ingestion failed on article {exc.title!r}: {exc}", file=sys.stderr)
        return 1

    print(
        f"Ingestion complete: corpus_version={result.corpus_version} "
        f"chunks={result.chunk_count} skipped_existing={result.skipped_existing}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
