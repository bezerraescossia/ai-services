# Data Model: Corpus PII Scrubbing & Flagging

**Feature**: `dp02-pii-scrubbing`
**Epic entity reference**: `.spec/01-corrective-rag/shared-data-model.md`

This feature is the **sole writer** of `pii_flagged=true` on a Document Chunk, and the **second writer** of `retrievable` (after DP1's default `false`).

---

## PII Scan Record

**Represents**: The per-chunk audit trail of one PII scan pass — what personal-data categories were detected and what action was taken. Backs FR-005's LGPD audit requirement.

**Scope**: Local to this feature. No other feature in the epic currently consumes it directly. Stored as JSONL at `data/corrective-rag/<corpus_version>/pii_scan/audit.jsonl`.

| Field | Type | Notes |
|---|---|---|
| chunk_id | string | Identifies the Document Chunk this record covers (FK to `Document Chunk.chunk_id`). |
| categories_detected | list[string] | Sorted list of detected PII category labels (e.g. `["EMAIL", "PHONE"]`). Empty list for a clean chunk. |
| action_taken | enum: `"clean"` / `"redacted"` | `"clean"` if no PII was detected; `"redacted"` if at least one span was replaced. |
| scan_timestamp | string (ISO-8601) | UTC timestamp of when this chunk was scanned. |

**State transitions**: A chunk is scanned once per corpus_version scan run. If `run_scan()` is called again against an already-fully-resolved corpus_version, the scroll filter returns zero unscanned chunks and no new records are written (FR-007 idempotency).

---

## Document Chunk (reference — from `shared-data-model.md`)

This feature reads and mutates two fields:

| Field | DP2 Action | Effect |
|---|---|---|
| `pii_flagged` | Write | Set to `false` (confirmed clean) or `true` (PII detected and redacted). DP1 initialises this field to `false`; DP2 either confirms that default or flips it. |
| `retrievable` | Write | Set to `true` after scan completes (clean or redacted), regardless of whether PII was found. Per spec Clarification Q2: no chunk is permanently quarantined — flagged chunks are auto-redacted and published. |
| `text` | Conditional write | Updated (redacted) in-place only when `pii_flagged=true`. Detected spans are replaced with `[REDACTED:<CATEGORY>]` tokens. |

All other Document Chunk fields are read-only for DP2.

---

## Eval Results Record

**Represents**: The per-run record of evaluation gate outcomes. Written by the Evaluation phase (T014–T016) to `data/corrective-rag/eval/pii_scrubbing/eval_results.json`. Not consumed at runtime — serves as the audit artifact for the Principle II documented exception (no MLflow, rule-based detector).

| Field | Type | Notes |
|---|---|---|
| sc003_pass | boolean | 100% recall on planted examples gate. |
| sc003_detail | string | Human-readable summary of results. |
| sc004_pass | boolean | 0 false positives on subject-biography chunks gate. |
| sc004_detail | string | Human-readable summary. |
| sc005_pass | boolean | 0 false positives on identifier-token chunks gate. |
| sc005_detail | string | Human-readable summary. |
| run_timestamp | string (ISO-8601) | UTC timestamp of the evaluation run. |
| corpus_version | string | Corpus version evaluated against. |
