# Phase Report: Data Preparation — Corrective RAG

**Epic**: .spec/01-corrective-rag/epic.md | **Date**: 2026-08-24

## Features Delivered

| ID | Feature Name | Type | spec.md | plan.md |
|---|---|---|---|---|
| DP1 | Document Ingestion & Indexing Pipeline | Feature | [spec](../dp01-document-ingestion/spec.md) | [plan](../dp01-document-ingestion/plan.md) |
| DP2 | Corpus PII Scrubbing & Flagging | QA | [spec](../dp02-pii-scrubbing/spec.md) | [plan](../dp02-pii-scrubbing/plan.md) |

## Risks Realized vs. Planned

| Risk (from epic.md Risks & QA table) | Materialized? | Outcome |
|---|---|---|
| Corpus may contain personal data indexed and later surfaced in answers or sent to a third-party fallback, unnoticed | No | DP2 scanned corpus_version `20260822-eac47701064f` (2328 chunks); zero flaggable PII found in the real Wikipedia corpus. LGPD audit trail written to `data/corrective-rag/20260822-eac47701064f/pii_scan/audit.jsonl`. All chunks are now `retrievable=true`; none are quarantined. |

## QA Outcomes

**DP2 (Corpus PII Scrubbing & Flagging)**: The regex-based local detector passed all three mandatory eval gates before the CLI was deployed to gate DP1's output for MOD1.

- SC-003 (recall): 100% — 9/9 planted synthetic examples detected across all four resolved flaggable categories (EMAIL, PHONE, ADDRESS, GOV_ID), including multi-span chunks. No false negatives.
- SC-004 (subject-biography precision): 0 false positives on 10 manually curated subject-biography chunks (e.g. chunks naming Buzz Aldrin, Neil Armstrong as the article's encyclopedic subject). Clarification-resolved subject-exclusion rule held.
- SC-005 (identifier-token precision): 0 false positives on 10 manually curated chunks containing mission/spacecraft catalog numbers and numeric designations not constituting personal data (e.g. Apollo 11, STS-135). Token-shaped over-flagging risk did not materialize.

Eval results DVC-tracked at `data/corrective-rag/eval/pii_scrubbing/` (`eval.dvc`).

## Key Metrics

| Metric | Threshold | Actual Result | Source Feature |
|---|---|---|---|
| Articles ingested without fetch failure | 27/27 (SC-001) | 27/27 — zero unresolved fetch failures | DP1 |
| Chunks with non-null embedding_ref | 100% (SC-003) | 100% — 2328/2328 chunks, corpus_version `20260822-eac47701064f` | DP1 |
| Corpus idempotency on re-run | Identical chunk_id set (SC-004) | Confirmed — third run recognized existing corpus_version, returned `skipped_existing=True`, no re-embedding | DP1 |
| PII detector recall on planted examples | 100% (SC-003) | 9/9 detected (100%) | DP2 |
| False-positive rate on subject-biography chunks | 0% (SC-004) | 0/10 flagged (0%) | DP2 |
| False-positive rate on identifier-token chunks | 0% (SC-005) | 0/10 flagged (0%) | DP2 |

## Go/No-Go for Next Phase

**Go.**

DP1 and DP2 have both delivered their required success criteria. The Qdrant `document_chunks` collection on corpus_version `20260822-eac47701064f` contains 2328 fully-published chunks (`retrievable=true`) with LGPD audit coverage. MOD1's Baseline Retriever may now build against a live, cleared index.

No blocking issues for the Modeling phase. The two notable implementation findings below are carry-forward items, not blockers.

## Carry-Forward Items

- **tasks.md sync gap (DP2)**: DP2's `tasks.md` was not updated to `[X]` for Phases 3–Final (T007–T023) at commit time. The code, eval results, and documentation files confirm all work was completed (matching the epic's `Implemented` status and commit `a09128b`), but the checklist is stale. Should be reconciled before DP2 is referenced as a template for future QA features. Low priority — no downstream blocker.

- **Multiple corpus_versions in the index**: Three DVC-tracked corpus_versions exist: `20260822-98c9d49d0bad` (2-article integration test fixture), `20260822-e1e94a7b8625` (27-article full run, pre-chunking-fix), and `20260822-eac47701064f` (27-article full run, post-chunking-fix, PII-scanned). MOD1 MUST target `20260822-eac47701064f` — this is the only version that has passed the DP2 scan gate and has all chunks in `retrievable=true` state. The others should not be used as the production corpus for retrieval; their presence is intentional (content-addressed design) and does not require cleanup.

- **Wikipedia article drift**: T028 confirmed that re-fetching the same 27 articles ~15 minutes apart produced a different `corpus_version` due to a live Wikipedia edit to "Space Shuttle Columbia disaster". The content-addressing design handled this correctly (new version rather than silent corruption). MOD1/EVAL1 must pin their work to a specific `corpus_version` identifier, not re-fetch live content at query time — consistent with BDU1's static-snapshot framing, but worth making explicit when MOD1's retriever is scoped.
