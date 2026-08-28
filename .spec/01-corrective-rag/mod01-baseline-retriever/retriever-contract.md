# Contract: Baseline Retriever

**Feature**: `mod01-baseline-retriever`

## Function: `corrective_rag.retrieval.retriever.retrieve`

```python
def retrieve(
    *,
    query: str,
    corpus_version: str,
    openai_client: OpenAI,
    qdrant_client: QdrantClient,
    k: int = DEFAULT_K,  # 5
    base_dir: Path = DEFAULT_BASE_DIR,  # data/corrective-rag
) -> RetrievalResult:
    ...
```

**Preconditions**: caller supplies a real `OpenAI` client (or a compatible fake with `.embeddings.create(...)`) and a real `QdrantClient` already pointed at the collection DP1/DP2 populate. `corpus_version` must have a manifest on disk at `<base_dir>/<corpus_version>/chunks/manifest.json` (written by DP1).

**Return value** — `RetrievalResult`:

| Field | Type | Notes |
|---|---|---|
| `decision_id` | `str` | Fresh UUID4 per call |
| `query` | `str` | Echoes the input query |
| `retrieved_chunk_ids` | `list[str]` | Score-descending order |
| `relevance_scores` | `list[float]` | Same order as `retrieved_chunk_ids`, raw cosine similarity |
| `chunks` | `list[RetrievedChunk]` | `chunk_id`, `text`, `source_document_id`, `corpus_version`, `score` per chunk |

**Error conditions** (all raised *before* any Qdrant search; the first two are raised before the embedding API call too):

| Exception | Fires when | Relative to embedding call |
|---|---|---|
| `EmptyQueryError` (`ValueError`) | `query.strip()` is empty (FR-006) | Before — no API call made |
| `EmbeddingModelMismatchError` (`RuntimeError`) | The manifest's pinned `embedding_model` ≠ the model `embed_text_with_usage` actually uses (FR-007) | Before — no API call made, avoids spending tokens on a call whose result would be discarded |
| `ManifestNotFoundError` (`RuntimeError`) | `corpus_version`'s manifest file is missing or empty | Before — no API call made |
| *(unwrapped Qdrant/OpenAI exception)* | Qdrant is unreachable, or the embedding call itself fails (FR-009) | Propagates as-is from the underlying client — no retry, no silent empty-result fallback |

**Guarantees**:
- Never returns a chunk with `retrievable=false` — the filter is applied at the Qdrant query level (`query_filter`), never as a post-filter (FR-004).
- Never returns a chunk from a different `corpus_version`.
- Returns fewer than `k` chunks without raising if the filtered corpus has fewer matching points; logs the actual count.
- Emits exactly two structured `INFO` log lines per successful call: `mod1_retrieval_embedding feature=mod1 tokens_used=<int> estimated_cost_usd=<float> corpus_version=<str>` and `mod1_retrieval_complete feature=mod1 corpus_version=<str> k=<int> returned=<int>`.

## CLI: `python -m corrective_rag.retrieval.cli`

```text
python -m corrective_rag.retrieval.cli --query "<text>" --corpus-version <version> [--k 5]
```

**Environment**: `OPENAI_API_KEY` (required), `QDRANT_URL` (optional, default `http://localhost:6333`).

**Exit codes**: `0` on success; `1` if `OPENAI_API_KEY` is unset, or on `EmptyQueryError` / `EmbeddingModelMismatchError` / `ManifestNotFoundError` / any Qdrant or OpenAI error — in every failure case a one-line `Retrieval failed: <message>` is printed to stderr.

**Success stdout**:

```text
decision_id=<uuid>
chunk_id=<id> source_document_id=<repr> score=<float, 4 decimals>
...one line per returned chunk, score-descending...
```
