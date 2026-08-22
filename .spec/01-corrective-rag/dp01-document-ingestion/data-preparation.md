# Data Preparation: Document Ingestion & Indexing Pipeline

**Spec**: .spec/01-corrective-rag/dp01-document-ingestion/spec.md | **Plan**: plan.md

## Sourcing

- **Source**: Wikipedia's MediaWiki Action API (`/w/api.php?action=query&prop=extracts&explaintext=1`), no authentication required — implemented in `wikipedia_client.py` in place of the REST v1 endpoints originally sketched here, since `action=query` returns the same plain-text extract in one call. Wikipedia's API etiquette policy rejects requests with no descriptive `User-Agent` header (discovered as a real `403 Forbidden` during Implement); every request sends one identifying this pipeline.
- **Selection**: The concrete list of ~20-30 article titles (space-exploration topic, per BDU1) is finalized as part of this feature's own implementation — see `ingestion-contract.md` for the article-list input format.
- **Volume**: Demo-scale — tens of articles, fetched and processed as a single batch run, not incrementally.

## Versioning Scheme

- **Unit of versioning**: one `corpus_version` per ingestion run, identifying both the raw fetched article set and the chunk set derived from it.
- **`corpus_version` format**: `{YYYYMMDD}-{content_hash}`, where `content_hash` is a short SHA-256 prefix over the sorted, concatenated raw article content — this makes the identifier both human-orderable and content-addressed, so two runs against unchanged source content are recognizable as the same version without re-embedding (idempotency, FR-008).
- **DVC tracking**: `data/corrective-rag/<corpus_version>/raw/` and `data/corrective-rag/<corpus_version>/chunks/manifest.json` are each `dvc add`-ed after a successful run, producing `.dvc` pointer files committed to git. Per the Clarify-resolved DVC-remote decision, no cloud remote is configured — the local DVC cache (`.dvc/cache`) is sufficient to check out any prior `corpus_version` on the same machine or in a CI job that restores the cache; a remote can be added later without invalidating any existing version's hash.
- **Embedding model pin**: the exact model identifier (`text-embedding-3-small`) is written into every chunk manifest entry as both `embedding_model` and `embedding_model_version`. OpenAI's embeddings API does not expose a separate dated-snapshot version string the way its chat models do (no `-2024-01-25`-style suffix) — `embedding_model_version` currently duplicates `embedding_model` and exists as a forward-compatible field for if/when OpenAI starts versioning embedding model snapshots, so a later reproduction attempt can still detect if the hosted model's behavior changed underneath the same name.

## Split Strategy

Not applicable — this is not a training pipeline. DP1 produces one indexed corpus, not train/validation/test partitions; EVAL1 (a separate, later feature) is responsible for carving out its own held-out evaluation examples from queries against this index, disjoint from any data used to tune the retriever or evaluator.

## Leakage Checks

Not applicable for the same reason — there is no model being trained against this data that could leak between splits. The one adjacent concern (a chunk becoming queryable before it's been screened for personal data) is handled structurally, not via a split: every chunk is written `retrievable=false` and only DP2 can flip it, per the shared Document Chunk entity's `retrievable` field.
