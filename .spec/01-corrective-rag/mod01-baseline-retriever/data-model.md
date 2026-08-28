# Data Model: Baseline Retriever

**Feature**: `mod01-baseline-retriever`
**Shared entities**: see `.spec/01-corrective-rag/shared-data-model.md` — the entities below are MOD1's Python representation of those shared entities, not new entities of their own.

## Document Chunk (read-only)

MOD1 never writes a Document Chunk field. It reads chunks from Qdrant's `document_chunks` collection (written by DP1, cleared by DP2) via a query filtered to `corpus_version=<active>` and `retrievable=true`. Each hit's payload is mapped into a `RetrievedChunk`:

| `RetrievedChunk` field | Source (Qdrant payload / computed) |
|---|---|
| `chunk_id` | `payload["chunk_id"]` |
| `text` | `payload["text"]` |
| `source_document_id` | `payload["source_document_id"]` |
| `corpus_version` | `payload["corpus_version"]` |
| `score` | the search hit's raw cosine similarity score |

`payload["retrievable"]` and `payload["pii_flagged"]` are read implicitly (via the query filter) but not surfaced on `RetrievedChunk` — a chunk that reaches this dataclass is, by construction, always `retrievable=true`.

## Retrieval Decision Record (partially initialized)

MOD1 initializes the subset of `shared-data-model.md`'s Retrieval Decision Record fields it owns, returned as a `RetrievalResult`:

| Retrieval Decision Record field | `RetrievalResult` field | Set by MOD1? |
|---|---|---|
| `decision_id` | `decision_id` | Yes — a fresh `uuid4()` per call |
| `query` | `query` | Yes — the raw input query string |
| `retrieved_chunk_ids` | `retrieved_chunk_ids` | Yes — chunk IDs in score-descending order |
| `relevance_scores` | `relevance_scores` | Yes — raw cosine similarity, same order as `retrieved_chunk_ids` (per the Clarify-resolved decision to persist raw scores here rather than leave them ephemeral) |
| `confidence_verdict` | — | No — MOD2 |
| `fallback_triggered` | — | No — MOD3 |
| `fallback_source_ref` | — | No — MOD3 |
| `final_context_refs` | — | No — MOD4 |
| `answer` | — | No — MOD4 |
| `routed_to_human` | — | No — DEPLOY3 |
| `mlflow_run_id` | — | No — this is the per-query decision's own MLflow lineage (MOD2 onward), distinct from MOD1's own Evaluation Gate MLflow run (`experiment=mod01-baseline-retriever`), which evaluates the retriever itself, not a single query |

`RetrievalResult.chunks` (`list[RetrievedChunk]`) is not part of the shared Retrieval Decision Record — it's MOD1's own return-value convenience so a caller doesn't have to re-fetch chunk text/source separately from `retrieved_chunk_ids`.

`RetrievalResult` is returned to the caller (DEPLOY1's future orchestrating pipeline) and is not persisted by MOD1 itself — persistence of the full Retrieval Decision Record, once all fields are populated by MOD2 through DEPLOY3, is DEPLOY1's responsibility (per `spec.md`'s Assumptions).
