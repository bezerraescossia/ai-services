# Quickstart: Baseline Retriever

## Prerequisites

- DP1 (ingestion) and DP2 (PII scrubbing) already run for the target `corpus_version`, so the Qdrant `document_chunks` collection has `retrievable=true` chunks under it. The active corpus for this epic is `corpus_version=20260822-eac47701064f` (2328 chunks, all cleared).
- Qdrant running: `docker compose up -d`.
- `OPENAI_API_KEY` set (via `.env`, sourced into the shell, or exported directly).

## Run a query

```bash
export QDRANT_URL=http://localhost:6333  # optional, this is the default
PYTHONPATH=src uv run python -m corrective_rag.retrieval.cli \
  --query "What were the goals of the Apollo 11 mission?" \
  --corpus-version 20260822-eac47701064f \
  --k 5
```

**Expected output** (scores will match exactly, since OpenAI embeddings are deterministic for a fixed input and corpus):

```text
decision_id=<a fresh uuid each run>
chunk_id=68b93f0143c996c7 source_document_id='Apollo 13' score=0.5894
chunk_id=6a2678acaa123450 source_document_id='Apollo 13' score=0.5870
chunk_id=9620630ca05fdb82 source_document_id='Apollo 13' score=0.5743
chunk_id=89e289fc5f4bcf53 source_document_id='Apollo 11' score=0.5703
chunk_id=5e77caf3e4400883 source_document_id='Apollo 11' score=0.5678
```

Structured log lines (to stderr/stdout depending on your terminal, via Python logging) confirm token usage per FR-005:

```text
... corrective_rag.retrieval.retriever INFO mod1_retrieval_embedding feature=mod1 tokens_used=11 estimated_cost_usd=0.000000 corpus_version=20260822-eac47701064f
... corrective_rag.retrieval.retriever INFO mod1_retrieval_complete feature=mod1 corpus_version=20260822-eac47701064f k=5 returned=5
```

## Inspect the Evaluation Gate result

```bash
cat data/corrective-rag/eval/baseline_retriever/eval_results.json
```

Shows `top1_similarity`, `sc003_pass`, `p95_latency_seconds`, `sc004_pass`, and the MLflow run id from the last gate run.

To browse the full MLflow run (params, metrics, timestamps):

```bash
uv run mlflow ui --backend-store-uri sqlite:///mlflow.db
```

Open the printed URL, select the `mod01-baseline-retriever` experiment, and find the run by the id recorded in `eval_results.json`.

## Re-run the Evaluation Gate

```python
from openai import OpenAI
from qdrant_client import QdrantClient
from corrective_rag.retrieval.evaluation import run_evaluation_gate

run_evaluation_gate(
    corpus_version="20260822-eac47701064f",
    openai_client=OpenAI(),
    qdrant_client=QdrantClient(url="http://localhost:6333"),
)
```

This overwrites `eval_results.json` and creates a new MLflow run.

## Error paths to try

```bash
# Empty query — rejected before any API call
PYTHONPATH=src uv run python -m corrective_rag.retrieval.cli --query "   " --corpus-version 20260822-eac47701064f

# Unknown corpus_version — no manifest on disk
PYTHONPATH=src uv run python -m corrective_rag.retrieval.cli --query "test" --corpus-version does-not-exist
```

Both exit non-zero with a one-line `Retrieval failed: ...` message on stderr.
