# Implementation Plan: Corpus PII Scrubbing & Flagging

**Branch**: `dp02-pii-scrubbing` | **Date**: 2026-08-24 | **Spec**: .spec/01-corrective-rag/dp02-pii-scrubbing/spec.md

## Summary

DP2 implements a local, rule-based PII detection pass over every chunk DP1 left in its default unpublished state (`retrievable=false`, `pii_flagged=false`). For each chunk, regex patterns covering the four resolved flaggable categories (email, phone, physical address, government ID) are applied; detected spans are replaced with `[REDACTED:<CATEGORY>]` placeholders and the chunk is published as `pii_flagged=true, retrievable=true`; clean chunks are published as `pii_flagged=false, retrievable=true`. The pass is transactional — all Qdrant updates are deferred until the full scan succeeds (FR-009), making a partial corpus_version impossible.

## Technical Context

**Language/Version**: Python 3.13 (project baseline)
**Primary Dependencies**: `qdrant-client` (already in pyproject.toml — only existing dependency needed; pure-regex detector adds no new runtime dependency)
**Data Sources & Pipeline**: Qdrant `document_chunks` collection written by DP1; scan reads chunks via scroll API filtered by `corpus_version` and unscanned payload state (`retrievable=false`, `pii_flagged=false`).
**Feature Engineering**: N/A — rule-based pattern matching over raw chunk text.
**Model Architecture Candidates**: Regex patterns per category (selected). Justified below in the Constitution Check note for Principle II; no trained model is needed for the fixed 4-category scope against a corpus that is expected to be clean (synthetic planted examples are the only positive set per SC-003's accepted deviation).
**Training Infra/Compute**: N/A — no training.
**Experiment Tracking Tool**: MLflow not applicable (see Complexity Tracking — documented exception). Evaluation results (SC-003/SC-004/SC-005 pass/fail + counts) are written to `data/corrective-rag/<corpus_version>/pii_scan/eval_results.json` for auditability.
**Evaluation Protocol**: Three binary pass/fail gates on manually curated or planted chunk sets: SC-003 (100% recall on ≥1 planted chunk per category), SC-004 (0 false positives on ≥10 subject-biography chunks), SC-005 (0 false positives on ≥10 identifier-like-token chunks). All evaluated before any Deployment task.
**Storage**: Qdrant (chunk payload mutations) + local JSONL audit trail at `data/corrective-rag/<corpus_version>/pii_scan/audit.jsonl`.
**Testing**: Unit (detector patterns, redactor, audit), integration (scanner against live Qdrant via docker-compose).
**Deployment Target**: Manually triggered batch CLI — same framing as DP1's own batch job (per Clarifications).
**Monitoring & Retraining Triggers**: N/A for this feature; scan is a once-per-corpus_version batch step.
**Target Platform**: Local / CI (same as DP1).
**Performance Goals**: No latency SLO — single-pass batch job over a small corpus (~20-30 articles, O(hundreds) of chunks). Full scan expected in seconds.
**Constraints**: FR-006: detector MUST run without sending chunk text to any external API. FR-009: abort whole run on any detector exception. FR-007: idempotent re-runs.
**Scale/Scope**: Single corpus_version at a time; ~20-30 Wikipedia articles; O(hundreds) of chunks.

## Constitution Check

| Principle | Assessment | Note |
|---|---|---|
| I. Reproducibility First | Pass | Regex patterns are deterministic; no stochastic process. Audit trail and eval results written to DVC-tracked `data/` paths. No new lockfile changes needed — no new runtime deps. |
| II. Experiment Tracking (MLflow) | Documented Exception | This is a rule-based detector with no training runs, hyperparameters, or model artifacts. MLflow would log nothing meaningful. Evaluation results (SC-003/SC-004/SC-005) are written to `eval_results.json` in the DVC-tracked scan dir. Recorded in Complexity Tracking below. |
| III. Evaluation Before Shipping | Pass | SC-003/SC-004/SC-005 form the explicit Evaluation Gate (see below). All three must pass before any Deployment-phase task. |
| IV. Test-First Development (TDD) | Pass | Tests written before implementation per plan's Phase ordering. |
| V. Service Independence | Pass | `corrective_rag.scrubbing` is a new sub-package within the existing monolith module; no shared runtime state with `ingestion`. Communicates with Qdrant over its defined HTTP client, same pattern as DP1. |
| VI. Observability by Default | Pass | Structured logging (same `logging.basicConfig` pattern as DP1). Scan progress logged per chunk; final summary (scanned/clean/flagged/redacted counts) logged at INFO level. No LLM calls → no token-usage tracking needed. |
| VII. No Secrets or PII in Logs | Pass | Chunk text and detected spans are NEVER logged. Log lines contain only `chunk_id`, `corpus_version`, category labels, and action taken — no raw text or redacted content. |
| LGPD Data Governance | Pass | Audit trail (FR-005) documents what was found (categories, action), satisfying LGPD documentation requirement. Legal basis, retention, and deletion path documented in spec.md Assumptions — referenced here, not re-litigated. |

## Evaluation Gate

| Metric | Threshold | Eval Set | Source |
|---|---|---|---|
| Recall on planted flaggable examples | 100% (all planted spans detected) | ≥1 synthetic chunk per resolved category (email, phone, physical address, government ID); seeded because corpus is expected clean | spec.md SC-003 |
| False-positive rate on subject-biography chunks | 0 flagged | Manually reviewed sample of ≥10 subject-biography chunks from the corpus (chunks whose only person-related content is the article's own encyclopedic subject) | spec.md SC-004 |
| False-positive rate on identifier-like-token chunks | 0 flagged | Manually reviewed sample of ≥10 chunks containing mission/spacecraft catalog numbers or similar identifier-like tokens that are not personal data | spec.md SC-005 |

All three gates must pass before any Phase 6 (Deployment) task in `tasks.md` may execute.

## Project Structure

### Documentation (this feature)

```
.spec/01-corrective-rag/dp02-pii-scrubbing/
├── spec.md                    # (exists)
├── requirements.md            # (exists)
├── plan.md                    # (this file)
├── data-model.md              # PII Scan Record entity; references shared-data-model.md
├── scrubbing-contract.md      # CLI contract + Qdrant payload mutation contract
├── quickstart.md              # runnable validation guide
└── tasks.md                   # generated by Tasks sub-stage after plan review
```

### Source Code

```
src/corrective_rag/scrubbing/
├── __init__.py
├── detector.py      # regex patterns per PII category; returns list[DetectedSpan]
├── redactor.py      # replaces DetectedSpan list in text with [REDACTED:<CATEGORY>] tokens
├── scanner.py       # full scan pass: scroll Qdrant → detect → collect → bulk update
├── audit.py         # PiiScanRecord dataclass + JSONL append + eval_results.json writer
└── cli.py           # CLI entry point: python -m corrective_rag.scrubbing --corpus-version

tests/corrective_rag/scrubbing/
├── __init__.py
├── test_detector.py    # unit: pattern coverage per category, subject-exclusion edge cases
├── test_redactor.py    # unit: span replacement, multi-span, no-span fast path
├── test_scanner.py     # integration: full scan against Qdrant (docker-compose fixture)
└── test_audit.py       # unit: JSONL append, eval_results write, idempotency
```

**Structure Decision**: Mirrors DP1's `ingestion/` sub-package pattern exactly — a flat module under `corrective_rag/` with one file per concern. No sub-folders. CLI matches DP1's `python -m corrective_rag.ingestion` entry-point style.

### Data Layout

```
data/corrective-rag/
└── <corpus_version>/
    └── pii_scan/
        ├── audit.jsonl          # one JSON line per scanned chunk (FR-005)
        └── eval_results.json    # SC-003/SC-004/SC-005 pass/fail record (Principle II exception)
```

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| Principle II (MLflow) exception | Rule-based regex detector has no training run, hyperparameters, or model artifact to track. There is no meaningful MLflow run to log. | Logging a shell-script-style eval result to MLflow would be cargo-culting the tool — it would produce a run with zero parameters and three hard-coded metrics, adding a mandatory MLflow service dependency to a feature that has no model. Eval results go to `eval_results.json` in the DVC-tracked scan dir for reproducibility without the overhead. |
