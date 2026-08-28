from __future__ import annotations

import argparse
import logging
import os
import sys

from openai import OpenAI
from qdrant_client import QdrantClient

from corrective_rag.retrieval.retriever import (
    DEFAULT_K,
    EmbeddingModelMismatchError,
    EmptyQueryError,
    ManifestNotFoundError,
    retrieve,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Retrieve top-k chunks for a query against a corpus_version."
    )
    parser.add_argument("--query", required=True, type=str)
    parser.add_argument("--corpus-version", required=True, type=str)
    parser.add_argument("--k", type=int, default=DEFAULT_K)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv if argv is not None else sys.argv[1:])

    if not os.environ.get("OPENAI_API_KEY"):
        print("OPENAI_API_KEY environment variable is required.", file=sys.stderr)
        return 1

    qdrant_url = os.environ.get("QDRANT_URL", "http://localhost:6333")

    try:
        result = retrieve(
            query=args.query,
            corpus_version=args.corpus_version,
            openai_client=OpenAI(),
            qdrant_client=QdrantClient(url=qdrant_url),
            k=args.k,
        )
    except (EmptyQueryError, EmbeddingModelMismatchError, ManifestNotFoundError) as exc:
        print(f"Retrieval failed: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # FR-009: Qdrant/other unexpected errors surface here, no retry.
        print(f"Retrieval failed: {exc}", file=sys.stderr)
        return 1

    print(f"decision_id={result.decision_id}")
    for chunk in result.chunks:
        print(
            f"chunk_id={chunk.chunk_id} "
            f"source_document_id={chunk.source_document_id!r} "
            f"score={chunk.score:.4f}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
