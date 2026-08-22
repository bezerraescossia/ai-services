# Contract: Ingestion CLI & Qdrant Collection Schema

**Spec**: .spec/01-corrective-rag/dp01-document-ingestion/spec.md | **Plan**: plan.md

## CLI Interface

```text
PYTHONPATH=src uv run python -m corrective_rag.ingestion.cli --articles articles.txt
```

| Argument/Env Var | Required | Meaning |
|---|---|---|
| `--articles PATH` | Yes | Path to a newline-separated file of Wikipedia article titles (the finalized ~20-30 space-exploration titles). |
| `OPENAI_API_KEY` (env) | Yes | OpenAI API key for embedding calls. Read from the environment only — never logged, never accepted as a CLI flag. |
| `QDRANT_URL` (env) | No, default `http://localhost:6333` | Qdrant server address. |

**Exit behavior**: exit code `0` only if every article was fetched, chunked, embedded, and upserted successfully, and the resulting `corpus_version` was `dvc add`-ed. Any persistent failure (article fetch, embedding call, Qdrant upsert) after retries MUST cause a non-zero exit with the failing article/chunk identified on stderr — no partial `corpus_version` is left committed (FR-009).

## Qdrant Collection Schema

**Collection name**: `document_chunks`
**Vector size**: 1536 (`text-embedding-3-small`'s output dimension), distance metric: cosine.

| Payload Field | Type | Notes |
|---|---|---|
| `chunk_id` | string | Deterministic: `sha256(source_document_id + chunk_index + text)[:16]` |
| `corpus_version` | string | Per `data-preparation.md`'s versioning scheme |
| `source_document_id` | string | The originating Wikipedia article title |
| `text` | string | Chunk content (pre-redaction; DP2 may rewrite this field in place) |
| `pii_flagged` | bool | Always `false` on write by this feature — "not yet scanned" default (FR-006) |
| `embedding_ref` | string | The Qdrant point ID itself acts as this pointer; stored redundantly in the payload for cross-referencing from the chunk manifest |
| `retrievable` | bool | Always `false` on write by this feature (FR-004) — DP2 is the only feature authorized to flip this to `true` |

MOD1's retriever MUST query with a payload filter `retrievable = true` — this is a hard contract, not an optional filter, since an unfiltered query would return DP2-unscanned content.

## DVC Output Layout

```text
data/corrective-rag/<corpus_version>/
├── raw/
│   └── <article_title>.json       # {title, fetched_at, extract_text}
└── chunks/
    └── manifest.json              # [{chunk_id, source_document_id, text, embedding_model, embedding_model_version}, ...]
```

`manifest.json` is the pre-embedding record of every chunk in this `corpus_version` — it mirrors what was written to Qdrant, minus the actual vector, and is what a later reproduction run diffs against to confirm identical chunking (SC-004).
