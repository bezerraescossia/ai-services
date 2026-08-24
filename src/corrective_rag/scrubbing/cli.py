from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

from qdrant_client import QdrantClient

from corrective_rag.scrubbing.scanner import ScanAbortedError, run_scan

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

_DEFAULT_BASE_DIR = Path("data/corrective-rag")


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Scan a corpus_version for PII and publish all chunks."
    )
    parser.add_argument(
        "--corpus-version",
        required=True,
        help="The corpus_version string produced by DP1 (e.g. 20260822-98c9d49d0bad).",
    )
    parser.add_argument(
        "--base-dir",
        default=str(_DEFAULT_BASE_DIR),
        help="Base data directory (default: data/corrective-rag).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv if argv is not None else sys.argv[1:])

    qdrant_url = os.environ.get("QDRANT_URL", "http://localhost:6333")
    audit_dir = Path(args.base_dir) / args.corpus_version / "pii_scan"

    try:
        result = run_scan(
            corpus_version=args.corpus_version,
            qdrant_client=QdrantClient(url=qdrant_url),
            audit_dir=audit_dir,
        )
    except ScanAbortedError as exc:
        print(
            f"pii_scan_aborted corpus_version={args.corpus_version} "
            f"failed_chunk={exc.chunk_id!r} cause={exc.cause}",
            file=sys.stderr,
        )
        return 1

    print(
        f"pii_scan_complete corpus_version={result.corpus_version} "
        f"scanned={result.scanned} clean={result.clean} flagged={result.flagged}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
