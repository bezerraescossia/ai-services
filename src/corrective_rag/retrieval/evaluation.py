from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path

import mlflow
from openai import OpenAI
from qdrant_client import QdrantClient

from corrective_rag.retrieval.retriever import DEFAULT_K, retrieve
from corrective_rag.shared.openai_client import EMBEDDING_MODEL

logger = logging.getLogger(__name__)

CANONICAL_QUERY = "What were the goals of the Apollo 11 mission?"
SC003_THRESHOLD = 0.55
SC004_THRESHOLD_SECONDS = 3.0

_EVAL_DIR = Path("data/corrective-rag/eval/baseline_retriever")
DEFAULT_LATENCY_QUERIES_PATH = _EVAL_DIR / "latency_queries.json"
DEFAULT_RESULTS_PATH = _EVAL_DIR / "eval_results.json"


@dataclass(frozen=True)
class EvaluationGateResult:
    corpus_version: str
    k: int
    embedding_model: str
    corpus_chunk_count: int
    top1_similarity: float
    sc003_pass: bool
    p95_latency_seconds: float
    sc004_pass: bool
    mlflow_run_id: str


def _p95(values: list[float]) -> float:
    ordered = sorted(values)
    index = min(int(round(0.95 * (len(ordered) - 1))), len(ordered) - 1)
    return ordered[index]


def run_evaluation_gate(
    *,
    corpus_version: str,
    openai_client: OpenAI,
    qdrant_client: QdrantClient,
    k: int = DEFAULT_K,
    latency_queries_path: Path = DEFAULT_LATENCY_QUERIES_PATH,
    results_path: Path = DEFAULT_RESULTS_PATH,
) -> EvaluationGateResult:
    canonical_result = retrieve(
        query=CANONICAL_QUERY,
        corpus_version=corpus_version,
        openai_client=openai_client,
        qdrant_client=qdrant_client,
        k=k,
    )
    scores = canonical_result.relevance_scores
    top1_similarity = scores[0] if scores else 0.0
    sc003_pass = top1_similarity >= SC003_THRESHOLD

    latency_queries = json.loads(latency_queries_path.read_text(encoding="utf-8"))
    latencies = []
    corpus_chunk_count = 0
    for query in latency_queries:
        start = time.perf_counter()
        latency_result = retrieve(
            query=query,
            corpus_version=corpus_version,
            openai_client=openai_client,
            qdrant_client=qdrant_client,
            k=k,
        )
        latencies.append(time.perf_counter() - start)
        corpus_chunk_count = max(corpus_chunk_count, len(latency_result.chunks))
    p95_latency_seconds = _p95(latencies)
    sc004_pass = p95_latency_seconds < SC004_THRESHOLD_SECONDS

    mlflow.set_tracking_uri("sqlite:///mlflow.db")
    mlflow.set_experiment("mod01-baseline-retriever")
    with mlflow.start_run(run_name=f"evaluation-gate-{corpus_version}") as run:
        mlflow.log_param("corpus_version", corpus_version)
        mlflow.log_param("k", k)
        mlflow.log_param("embedding_model", EMBEDDING_MODEL)
        mlflow.log_metric("top1_similarity", top1_similarity)
        mlflow.log_metric("p95_latency_seconds", p95_latency_seconds)
        mlflow.log_metric("corpus_chunk_count", corpus_chunk_count)
        mlflow.log_metric("sc003_pass", int(sc003_pass))
        mlflow.log_metric("sc004_pass", int(sc004_pass))
        mlflow_run_id = run.info.run_id

    result = EvaluationGateResult(
        corpus_version=corpus_version,
        k=k,
        embedding_model=EMBEDDING_MODEL,
        corpus_chunk_count=corpus_chunk_count,
        top1_similarity=top1_similarity,
        sc003_pass=sc003_pass,
        p95_latency_seconds=p95_latency_seconds,
        sc004_pass=sc004_pass,
        mlflow_run_id=mlflow_run_id,
    )

    results_path.parent.mkdir(parents=True, exist_ok=True)
    results_path.write_text(
        json.dumps(
            {
                "corpus_version": result.corpus_version,
                "k": result.k,
                "embedding_model": result.embedding_model,
                "corpus_chunk_count": result.corpus_chunk_count,
                "top1_similarity": result.top1_similarity,
                "sc003_pass": result.sc003_pass,
                "p95_latency_seconds": result.p95_latency_seconds,
                "sc004_pass": result.sc004_pass,
                "mlflow_run_id": result.mlflow_run_id,
            },
            indent=2,
        )
    )

    logger.info(
        "mod1_evaluation_gate_complete feature=mod1 corpus_version=%s top1_similarity=%.4f "
        "sc003_pass=%s p95_latency_seconds=%.4f sc004_pass=%s mlflow_run_id=%s",
        corpus_version,
        top1_similarity,
        sc003_pass,
        p95_latency_seconds,
        sc004_pass,
        mlflow_run_id,
    )

    return result
