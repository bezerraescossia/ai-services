# Quickstart: Document Ingestion & Indexing Pipeline

**Spec**: .spec/01-corrective-rag/dp01-document-ingestion/spec.md | **Plan**: plan.md | **Contract**: ingestion-contract.md

## Prerequisites

- `uv sync` has been run (installs `openai`, `qdrant-client`, `langchain-text-splitters`, `tenacity`, `httpx`, `dvc`, plus dev tooling).
- `OPENAI_API_KEY` is set in your shell environment (never commit it — see `.env.example` once added).
- Docker is available locally for Qdrant.

## Setup

```bash
docker compose up -d qdrant
export OPENAI_API_KEY=sk-...
```

## Run Ingestion

```bash
PYTHONPATH=src uv run python -m corrective_rag.ingestion.cli --articles src/corrective_rag/ingestion/articles.txt
```

`PYTHONPATH=src` is required because `[tool.uv] package = false` deliberately keeps this monolith uninstalled as a package (see `plan.md`'s Structure Decision) — the same reason `pyproject.toml` sets `pythonpath = ["src"]` for pytest.

Expected output: a log line per article fetched, a summary line with the resulting `corpus_version`, chunk count, and total embedding token/cost, and exit code `0`.

## Verify

```bash
uv run python -c "
from qdrant_client import QdrantClient
client = QdrantClient(url='http://localhost:6333')
hits = client.query_points(
    collection_name='document_chunks',
    query=[0.0] * 1536,  # placeholder; real check embeds 'Apollo 11 mission goals' first
    limit=3,
).points
print(len(hits), 'points found')
"
```

Per `spec.md`'s User Story 1 Independent Test, a real similarity query for an in-topic term (e.g. "Apollo 11 mission goals") against the index should return one or more chunks whose `source_document_id` corresponds to a relevant article — even though every returned chunk still has `retrievable=false` until DP2 runs (this quickstart queries the raw index directly, bypassing the `retrievable` filter MOD1 will enforce later).

## Reproduce a Prior Version

```bash
dvc checkout data/corrective-rag/<corpus_version>/
```

Checks out the exact raw articles and chunk manifest for that `corpus_version`, per `data-preparation.md`'s versioning scheme.
