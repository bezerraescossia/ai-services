# Implementation Plan: Document Ingestion & Indexing Pipeline

**Branch**: `dp01-document-ingestion` | **Date**: 2026-08-22 | **Spec**: .spec/01-corrective-rag/dp01-document-ingestion/spec.md

## Summary

A manually-triggered batch pipeline that fetches BDU1's scoped ~20-30 space-exploration Wikipedia articles, splits them into paragraph/sentence-respecting chunks, embeds each chunk via OpenAI's `text-embedding-3-small`, and upserts them into a Qdrant collection in an unpublished state (`retrievable=false`) — leaving DP2 to clear them before MOD1 can ever query the index. Every corpus snapshot (raw articles + chunk manifest) is versioned with DVC using a local-only cache, giving each run a citable `corpus_version` without requiring cloud storage for this demo.

## Technical Context

**Language/Version**: Python 3.13 (per `.python-version` / `pyproject.toml`'s `requires-python`).
**Primary Dependencies**: `openai` (embeddings client), `qdrant-client` (vector store, server mode), `langchain-text-splitters` (paragraph/sentence-aware chunking), `tenacity` (retry/backoff on fetch and embedding calls), `httpx` (Wikipedia REST API client), `dvc` (corpus versioning). All added to `[project.dependencies]`, pinned via `uv.lock` per Principle I.
**Data Sources & Pipeline**: Wikipedia's public REST API (page-extract endpoint, no auth) → paragraph/sentence chunking → OpenAI embedding per chunk → upsert into Qdrant with `corpus_version`, `pii_flagged=false`, `retrievable=false` payload fields → DVC-track the raw article JSON and the chunk manifest under a single `corpus_version` directory. Single batch run, not streaming.
**Feature Engineering**: N/A — raw chunk text is embedded directly, no additional transforms.
**Model Architecture Candidates**: N/A — uses OpenAI's hosted `text-embedding-3-small` via API, not a trained/selected model. The exact model identifier is pinned as DVC-tracked metadata alongside each `corpus_version` (mitigates the spec's own Risk Assessment item: silent embedding-model drift breaking reproducibility).
**Training Infra/Compute**: N/A — no training; ingestion runs locally or in CI as a single API-bound batch job.
**Experiment Tracking Tool**: Not used by this feature. `epic.md`'s own Constitution Check already scoped MLflow logging (Principle II) to the Modeling/Evaluation features (MOD*/EVAL*) — DP1 is a data pipeline, not a training/fine-tune/prompt-evaluation run, so no MLflow run is logged here. Structured logging (Principle VI, see below) covers this feature's observability needs instead.
**Evaluation Protocol**: N/A — no candidate model is being selected or gated; `spec.md`'s SC-003/SC-004 are pipeline-completeness and determinism checks (100% chunks embedded; identical `chunk_id` set on re-run), verified directly in Tasks, not via a held-out evaluation run. See Evaluation Gate section below (omitted).
**Storage**: Qdrant (Docker server, collection `document_chunks`) for vectors + metadata payload; local filesystem under `data/corrective-rag/` for raw article JSON and the chunk manifest, versioned with DVC using a local-only cache (no remote configured yet — can be added later without invalidating existing versions).
**Testing**: pytest unit tests for chunking (boundary-respecting, deterministic `chunk_id`), the Wikipedia client's retry/backoff and fail-loud behavior (mocked HTTP), and the embedding wrapper's cost/token logging (mocked OpenAI client); one integration test running the full pipeline against a real local Qdrant service (started as a CI service container / local Docker Compose) and asserting a raw similarity query returns non-empty results — this is Principle IV application code, so tests are written and made to fail before implementation.
**Deployment Target**: Manually-triggered batch CLI (`uv run python -m corrective_rag.ingestion.cli`), run locally or as a CI/ops step — not a long-running service. DEPLOY1 is the feature that turns the overall CRAG pipeline into an always-on service.
**Monitoring & Retraining Triggers**: N/A for this feature — MON1/MON2 own production monitoring once DEPLOY1 exists.
**Target Platform**: Linux (GitHub Actions `ubuntu-latest` and local dev), Qdrant reachable at `localhost:6333` via Docker.
**Project Type**: Single project — one initiative directory under `src/`, per this repo's existing `README.md` convention.
**Performance Goals**: N/A — demo-scale (~20-30 articles), single batch run, no latency SLA.
**Constraints**: `OPENAI_API_KEY` MUST be supplied via environment variable (CI secret / local `.env`, never committed — Principle VII); a Qdrant server MUST be reachable at ingestion time (Docker Compose locally, a `services:` container in CI).
**Scale/Scope**: ~20-30 Wikipedia articles per BDU1's scoping; single corpus_version per run.

## Constitution Check

*Gate: must pass before detailing the project structure below.*

| Principle (.spec/constitution.md) | Assessment | Note |
|---|---|---|
| I. Reproducibility First | Pass | `uv.lock` pins the environment; DVC (local cache) versions every corpus_version (raw articles + chunk manifest); the embedding model identifier/version is pinned and recorded as DVC-tracked metadata; chunk IDs are deterministic hashes (source_document_id + chunk index + text hash), not random, so no seed is needed. |
| II. Experiment Tracking Is Mandatory | Pass (N/A) | Scoped to MOD/EVAL features per `epic.md`'s own Constitution Check — DP1 is a data pipeline, not a training/fine-tune/prompt-evaluation run. |
| III. Evaluation Before Shipping | Pass (N/A) | No model or prompt ships from DP1; nothing here is gated by a held-out evaluation set. |
| IV. Test-First Development | Pass | This is real application code (fetch/chunk/embed/index orchestration) — unit and integration tests are written first and must fail before implementation, per Tasks below. |
| V. Service Independence with a Shared Core | Pass (deferred) | DP1 is a batch pipeline/CLI, not itself a deployed service — Principle V's "independently deployable service" requirement applies to DEPLOY1, which wraps the full CRAG pipeline. DP1 still isolates reusable logic (Wikipedia client, embedding wrapper) under `src/corrective_rag/shared/` so DEPLOY1 and later services can reuse it without a retrofit, per the epic's own Assumptions. |
| VI. Observability by Default | Pass | Structured logs emitted per ingestion run (articles fetched, chunks produced, retries) including per-call OpenAI token usage and cost, since embedding calls are LLM calls under this principle. |
| VII. No Secrets or PII in Code, Logs, or Prompts | Pass | `OPENAI_API_KEY` read only from environment, never logged; chunks are written `retrievable=false` and `pii_flagged=false` (unscanned default) — DP2 remains the sole feature that flips either field toward publishable. |
| Model Risk & Responsible AI | Pass (N/A) | DP1 serves no prediction. |
| Data Governance & Privacy (LGPD) | Pass | DP1 sets `pii_flagged=false` as an explicit "not yet scanned" default (FR-006) rather than implying clean; DP2 owns the actual scan. |
| Model & Prompt Versioning | Pass (N/A) | No model/prompt version is shipped by DP1; the embedding model identifier is pinned for reproducibility (Principle I) rather than registered/versioned in the Model & Prompt Versioning sense, since DP1 doesn't serve it as a product-facing model. |

No violations — Complexity Tracking is not needed.

## Evaluation Gate

*Omitted — DP1 selects no candidate model and ships no prompt/model version. `spec.md`'s Model/ML Metrics (SC-003: 100% chunks have non-null `embedding_ref`; SC-004: deterministic `chunk_id` set on re-run) are pipeline-completeness/determinism checks verified directly against the run's own output in Tasks, not thresholds requiring a held-out evaluation set or an accept/reject modeling decision.*

## Project Structure

### Documentation (this feature)

```text
.spec/01-corrective-rag/dp01-document-ingestion/
├── plan.md                  # this file
├── spec.md
├── requirements.md          # quality checklist, all items pass
├── data-preparation.md      # sourcing, versioning scheme, no train/val/test split (not a training pipeline)
├── ingestion-contract.md    # CLI interface + Qdrant collection schema + DVC output layout
├── quickstart.md            # docker compose up, set OPENAI_API_KEY, run ingestion, verify a similarity query
└── tasks.md                 # generated next
```

No `research.md` (all Technical Context decisions were resolved directly with the user this session, zero remaining `NEEDS CLARIFICATION`). No `data-model.md` — the only entity this feature touches (Document Chunk) is already fully defined in `.spec/01-corrective-rag/shared-data-model.md`; there is nothing local left to define.

### Source Code (repository root)

```text
src/
└── corrective_rag/
    ├── __init__.py
    ├── shared/                      # reusable across this epic's later features (Principle V)
    │   ├── __init__.py
    │   └── openai_client.py         # thin wrapper: embedding calls + per-call token/cost logging
    └── ingestion/
        ├── __init__.py
        ├── wikipedia_client.py      # fetch article extracts, retry+backoff, fail-loud on persistent failure
        ├── chunking.py              # langchain-text-splitters wrapper, deterministic chunk_id
        ├── vector_store.py          # Qdrant collection setup + idempotent upsert (retrievable=false, pii_flagged=false)
        ├── versioning.py            # writes raw/chunk artifacts under data/corrective-rag/<corpus_version>/ and drives `dvc add`
        ├── pipeline.py              # orchestrates fetch → chunk → embed → index → version; idempotent end to end
        └── cli.py                   # `python -m corrective_rag.ingestion.cli --articles ...`

data/
└── corrective-rag/
    └── <corpus_version>/
        ├── raw/                     # fetched article JSON, DVC-tracked
        └── chunks/manifest.json     # pre-embedding chunk records, DVC-tracked

tests/
└── corrective_rag/
    └── ingestion/
        ├── test_chunking.py
        ├── test_wikipedia_client.py
        ├── test_vector_store.py
        └── test_pipeline_integration.py   # requires a local Qdrant (see quickstart.md)

docker-compose.yml            # Qdrant service for local dev, mirrored by a CI service container
```

**Structure Decision**: `src/corrective_rag/` uses an underscore, not the hyphen shown as an illustrative example in the root `README.md` (`src/corrective-rag/`) — a hyphenated directory cannot be imported as a Python package (`import corrective-rag` is not valid syntax), and this feature is the first to actually need cross-module imports (`pipeline.py` importing `chunking.py`, `vector_store.py`, etc.) and importable test modules. `pyproject.toml` needs `pythonpath = ["src"]` added under `[tool.pytest.ini_options]` so `tests/` can import `corrective_rag` without installing it as a package (consistent with the existing `package = false` setting). The root `README.md`'s example will be corrected to match in this feature's Setup tasks.

## Complexity Tracking

*Not applicable — no Constitution Check violation was recorded.*
