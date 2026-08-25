# Epic: Corrective RAG

**Epic ID**: `01-corrective-rag`
**Created**: 2026-08-22
**Status**: Draft
**Input**: User description: "corrective rag"

## Objective & Business Context

Vanilla RAG trusts whatever its top-k retrieval returns, even when it's irrelevant — which produces confidently wrong answers grounded on garbage context. This epic builds a Corrective RAG (CRAG) system: retrieval is followed by a lightweight relevance evaluator, and when confidence falls below threshold, the system falls back to a wider source (web search) instead of feeding the generator irrelevant context. Success at the epic level means a production service that measurably reduces the rate of answers grounded on irrelevant retrieval, with the evaluator/fallback decision auditable and its accuracy tracked over time.

## Scope & Non-Goals

**In Scope**: document ingestion and indexing, a baseline retriever, a relevance evaluator scoring retrieved chunks, a fallback web-search retrieval path triggered below a confidence threshold, generation grounded on validated context, a held-out evaluation harness, deployment as an independently deployable service (with shadow rollout and rollback per the constitution), and production monitoring of evaluator/fallback behavior.

**Non-Goals**: Graph RAG-style global corpus synthesis, Self-RAG (training retrieval/critique into the base model itself), Agentic RAG's open-ended multi-step tool planning, HyDE query rewriting, and fine-tuning the base LLM — all deferred to a later epic if a distinct need for them emerges.

## Constitution Check

*Gate: must pass before the feature backlog below is considered final.*

| Principle (.spec/constitution.md) | Assessment | Note |
|---|---|---|
| I. Reproducibility First | Pass | DP1 pins the environment, versions the corpus with DVC, and fixes seeds for any stochastic step. |
| II. Experiment Tracking Is Mandatory | Pass | MOD and EVAL features log every run (hyperparameters, metrics, artifacts, data lineage) to MLflow. |
| III. Evaluation Before Shipping | Pass | EVAL1/EVAL2 build the held-out eval set and gate DEPLOY1. |
| IV. Test-First Development | Pass | Enforced per-feature by `sdd-implement`'s Plan/Tasks stages, not at epic level. |
| V. Service Independence with a Shared Core | Pass | DEPLOY1 ships CRAG as one independently deployable service. This is the first service in this repo, so there's no existing shared library to draw from yet — see Assumptions. |
| VI. Observability by Default | Pass | DEPLOY1 requires structured logs/metrics including LLM token usage and cost; MON1 extends this into dashboards. |
| VII. No Secrets or PII in Code, Logs, or Prompts | Pass | Fallback web-search queries risk leaking PII to a third party; mitigated by QA row MOD5 (query sanitization). |
| Model Risk & Responsible AI | Pass | DEPLOY3 adds the human-in-the-loop fallback; EVAL3 (QA) adds the mandatory fairness/bias review before first ship. |
| Data Governance & Privacy (LGPD) | Pass | DP2 (QA) scrubs/flags personal data at ingestion time; exact legal-basis/retention documentation is deferred to DP1/DP2's own specs. |
| Model & Prompt Versioning | Pass | DEPLOY2 implements the mandatory shadow deployment and documented rollback path before full rollout. |

## Feature Backlog

*Organized by CRISP-ML(Q) phase.*

### Business & Data Understanding

**Requirements & Constraints**: The epic description ("corrective rag") names no concrete corpus, query population, or fallback provider — these must be scoped before any downstream feature can be built concretely.

| ID | Feature Name | Type | Goal | Priority | Depends On | Status |
|---|---|---|---|---|---|---|
| BDU1 | Corpus & Use-Case Scoping | Feature | Define the target document corpus, primary user query types, and what distinguishes a "relevant" from an "irrelevant" retrieval for this use case | P1 | — | Implemented — [spec](bdu01-corpus-scoping/spec.md) |

**Risks & QA**

| Risk | Feasible As-Is? | QA Method / Mitigation | Resulting Backlog ID |
|---|---|---|---|
| Scoping happens without input from actual end users, producing a corpus/use-case definition nobody needs | Yes | Reviewed directly during BDU1's own spec/clarify pass; no separate QA feature needed | — |

### Data Preparation

**Requirements & Constraints**: Corpus must be versioned (Principle I) and screened for personal data (LGPD, Principle VII) before indexing.

| ID | Feature Name | Type | Goal | Priority | Depends On | Status |
|---|---|---|---|---|---|---|
| DP1 | Document Ingestion & Indexing Pipeline | Feature | Chunk, embed, and index the scoped corpus into a vector store, versioning every corpus snapshot with DVC | P1 | BDU1 | Implemented — [spec](dp01-document-ingestion/spec.md) |
| DP2 | Corpus PII Scrubbing & Flagging | QA | Scan ingested documents for personal data before indexing and flag/redact per LGPD before the corpus is used downstream | P1 | DP1 | Implemented — [spec](dp02-pii-scrubbing/spec.md) |

**Risks & QA**

| Risk | Feasible As-Is? | QA Method / Mitigation | Resulting Backlog ID |
|---|---|---|---|
| Corpus may contain personal data indexed and later surfaced in answers or sent to a third-party fallback, unnoticed | No | Dedicated PII scan/redaction pass before indexing | DP2 |

### Modeling

**Requirements & Constraints**: The relevance evaluator is CRAG's defining mechanism — retrieval must never reach the generator unfiltered. Every modeling run must log to MLflow (Principle II).

| ID | Feature Name | Type | Goal | Priority | Depends On | Status |
|---|---|---|---|---|---|---|
| MOD1 | Baseline Retriever | Feature | Embed queries and retrieve top-k candidate chunks from the indexed corpus | P1 | DP1, DP2 | Specified — [spec](mod01-baseline-retriever/spec.md) |
| MOD2 | Retrieval Relevance Evaluator | Feature | Score each retrieved chunk's relevance to the query and classify overall retrieval confidence | P1 | MOD1 | Not Started |
| MOD3 | Fallback Web-Search Retrieval | Feature | When evaluator confidence falls below threshold, retrieve supplementary context from a web-search source instead | P1 | MOD2 | Not Started |
| MOD4 | Grounded Answer Generation | Feature | Generate an answer conditioned only on evaluator-approved and/or fallback context; hedge or decline when neither source is sufficient | P1 | MOD2, MOD3 | Not Started |
| MOD5 | Fallback Query Sanitization | QA | Strip/redact personal data from a query before it is sent to the external web-search fallback | P1 | MOD3 | Not Started |

**Risks & QA**

| Risk | Feasible As-Is? | QA Method / Mitigation | Resulting Backlog ID |
|---|---|---|---|
| Fallback queries sent to a third-party web-search API may contain personal data, violating Principle VII / LGPD | No | Sanitize/redact the query before the external call | MOD5 |
| Evaluator threshold is uncalibrated, causing excess fallback cost or too many irrelevant chunks passing through | Yes | Calibrated directly against the held-out set in EVAL1/EVAL2, not a separate feature | — |

### Evaluation

**Requirements & Constraints**: No model/prompt change ships without scoring against a fixed held-out set (Principle III); a fairness/bias review is mandatory before first production ship (Model Risk & Responsible AI).

| ID | Feature Name | Type | Goal | Priority | Depends On | Status |
|---|---|---|---|---|---|---|
| EVAL1 | Held-Out Relevance & Answer-Quality Eval Set | Feature | Curate a held-out set of (query, retrieved-chunk relevance labels, gold answer) examples, disjoint from any training/tuning data | P1 | MOD1 | Not Started |
| EVAL2 | End-to-End CRAG Evaluation Harness | Feature | Score the full pipeline against EVAL1 — evaluator accuracy, fallback trigger rate, answer groundedness/correctness — logged to MLflow | P1 | EVAL1, MOD4 | Not Started |
| EVAL3 | Fairness & Bias Review | QA | Review evaluator and generation outputs for disparate behavior across query/demographic slices before first production ship | P1 | EVAL2 | Not Started |

**Risks & QA**

| Risk | Feasible As-Is? | QA Method / Mitigation | Resulting Backlog ID |
|---|---|---|---|
| Evaluator or generator performs unevenly across user groups, shipping unnoticed | No | Dedicated fairness/bias review before first production ship, repeated on material retraining | EVAL3 |

### Deployment

**Requirements & Constraints**: Must ship as an independently deployable service (Principle V) with structured logs/metrics from day one (Principle VI); a new model/prompt version requires shadow deployment and a tested rollback path before full rollout (Model & Prompt Versioning); low-confidence predictions must route to a human fallback (Model Risk & Responsible AI).

| ID | Feature Name | Type | Goal | Priority | Depends On | Status |
|---|---|---|---|---|---|---|
| DEPLOY1 | CRAG Service API | Feature | Expose the CRAG pipeline as an independently deployable service with structured logging and metrics, including per-call token usage and cost | P1 | EVAL2 | Not Started |
| DEPLOY2 | Shadow Deployment & Rollback | Feature | Run a new model/evaluator/prompt version in shadow mode against production traffic, with a documented, tested rollback path, before full rollout | P1 | DEPLOY1 | Not Started |
| DEPLOY3 | Human-in-the-Loop Fallback Routing | Feature | Route answers where both the relevance evaluator and the web-search fallback are low-confidence to a human review queue instead of auto-serving | P1 | DEPLOY1 | Not Started |

**Risks & QA**

| Risk | Feasible As-Is? | QA Method / Mitigation | Resulting Backlog ID |
|---|---|---|---|
| A regressive model/evaluator update reaches full production traffic with no way back | No | Mandatory shadow mode + tested rollback before full rollout | DEPLOY2 |
| Low-confidence answers are auto-served with no human fallback | No | Dedicated human-in-the-loop routing path | DEPLOY3 |

### Monitoring & Maintenance

**Requirements & Constraints**: Builds on DEPLOY1's observability baseline to track the evaluator/fallback mechanism specifically over time.

| ID | Feature Name | Type | Goal | Priority | Depends On | Status |
|---|---|---|---|---|---|---|
| MON1 | Evaluator & Fallback Monitoring Dashboard | Feature | Track evaluator confidence distribution, fallback trigger rate, latency, and token cost in production over time | P2 | DEPLOY1 | Not Started |
| MON2 | Drift Alerting | QA | Alert when evaluator confidence distribution or fallback trigger rate shifts materially from its EVAL2 baseline | P2 | MON1 | Not Started |

**Risks & QA**

| Risk | Feasible As-Is? | QA Method / Mitigation | Resulting Backlog ID |
|---|---|---|---|
| Corpus or query distribution drifts silently in production, degrading evaluator/fallback accuracy with no signal | No | Automated drift alerting against the EVAL2 baseline | MON2 |

## Shared Entities

- **Document Chunk**: used by DP1, DP2, MOD1, MOD2, EVAL1
- **Retrieval Decision Record**: used by MOD2, MOD3, MOD4, EVAL1, EVAL2, MON1, MON2
- **Eval Example**: used by EVAL1, EVAL2, EVAL3

See `shared-data-model.md`.

## Sequencing / Minimum Viable Epic

BDU1 → DP1 → DP2 → MOD1 → MOD2 → MOD3 → MOD4 → EVAL1 → EVAL2 → EVAL3 constitutes the walking skeleton: it proves the core corrective mechanism (retrieve → evaluate → fall back if needed → generate → score against a held-out set) end-to-end, with the constitution's mandatory PII and fairness gates included since both are hard blockers rather than optional hardening. DEPLOY1-3 and MON1-2 turn that proven pipeline into a governed production service and are sequenced after the skeleton, not part of it.

## Assumptions

- **Resolved by BDU1** (.spec/01-corrective-rag/bdu01-corpus-scoping/spec.md): this is a demo repository. The corpus is Wikipedia articles (~20-30, topic: space exploration) fetched via Wikipedia's public REST API and DVC-snapshotted by DP1. The fallback web-search provider remains explicitly undecided, deferred to MOD3's own spec.
- This is the first service in the `ai-services` repository, so Principle V's "shared internal library" has nothing yet to extract from. DEPLOY1 should still isolate reusable logic (LLM client wrapper, MLflow logging helpers) into an internal library from the start so later services can adopt it without a retrofit.
- The corpus (public Wikipedia articles) is not expected to contain personal data in the LGPD sense, per BDU1's resolution — but DP2 still runs as a mandatory safety-net scan per the constitution, since article text may incidentally reference identifiable individuals.

## Phase Reports

- [Business & Data Understanding](reports/business-data-understanding-report.md) — Go (2026-08-22)
- [Data Preparation](reports/data-preparation-report.md) — Go (2026-08-24)
