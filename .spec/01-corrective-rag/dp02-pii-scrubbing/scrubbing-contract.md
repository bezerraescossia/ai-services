# Scrubbing Contract: Corpus PII Scrubbing & Flagging

**Feature**: `dp02-pii-scrubbing`
**Plan**: `.spec/01-corrective-rag/dp02-pii-scrubbing/plan.md`

---

## CLI Contract

**Entry point**: `python -m corrective_rag.scrubbing [args]`

### Arguments

| Argument | Required | Default | Description |
|---|---|---|---|
| `--corpus-version <v>` | Yes | — | The `corpus_version` string produced by DP1 (e.g. `20260822-98c9d49d0bad`). |
| `--base-dir <path>` | No | `data/corrective-rag` | Base data directory for audit output. |

### Environment Variables

| Variable | Default | Description |
|---|---|---|
| `QDRANT_URL` | `http://localhost:6333` | URL of the Qdrant instance holding the `document_chunks` collection. |

### Exit Codes

| Code | Meaning |
|---|---|
| `0` | Scan completed successfully. All unscanned chunks are now published. |
| `1` | Scan aborted due to a detector error on a specific chunk. No Qdrant writes were made for this run. |

### Stdout (success)

```
pii_scan_complete corpus_version=<v> scanned=N clean=N flagged=N
```

### Stderr (failure)

```
pii_scan_aborted corpus_version=<v> failed_chunk='<chunk_id>' cause=<exception>
```

### Example

```bash
export QDRANT_URL=http://localhost:6333
python -m corrective_rag.scrubbing --corpus-version 20260822-98c9d49d0bad
# pii_scan_complete corpus_version=20260822-98c9d49d0bad scanned=312 clean=311 flagged=1
```

---

## Qdrant Payload Mutation Contract

**Collection**: `document_chunks` (defined by DP1 in `src/corrective_rag/ingestion/vector_store.py`)

### Scan filter (read)

`run_scan()` scrolls all points matching:

```
corpus_version == <requested_version>
AND retrievable == false
AND pii_flagged == false
```

Points that are already `retrievable=true` are excluded — this is the idempotency guarantee (FR-007). Re-running the scan against a fully-resolved corpus_version returns zero points and performs no writes.

### Payload mutations (write)

All mutations are deferred until the full scan loop completes without error. If any detector call raises an exception, no `set_payload` calls are made for that run (FR-009 abort semantics).

**Clean chunk** (no PII detected):

```json
{
  "pii_flagged": false,
  "retrievable": true
}
```

**Flagged chunk** (PII detected and redacted):

```json
{
  "pii_flagged": true,
  "retrievable": true,
  "text": "<redacted text with [REDACTED:<CATEGORY>] placeholders>"
}
```

### Idempotency guarantee

A completed scan run leaves every chunk in the corpus_version with `retrievable=true`. A subsequent run finds zero unscanned chunks and writes nothing. Audit records are not duplicated.

### Abort semantics

If the detector raises any exception while scanning a chunk:
- `ScanAbortedError(chunk_id, cause)` is raised immediately.
- No `set_payload` calls have been made.
- No audit records have been written.
- The corpus_version remains in its pre-scan state — all scanned-so-far chunks are still `retrievable=false`.

---

## Audit File Layout

```
data/corrective-rag/
└── <corpus_version>/
    └── pii_scan/
        ├── audit.jsonl          # one JSON line per scanned chunk
        └── eval_results.json    # SC-003/SC-004/SC-005 pass/fail record (written by eval phase)
```

### audit.jsonl — one line per scanned chunk

```json
{"chunk_id": "abc123", "categories_detected": [], "action_taken": "clean", "scan_timestamp": "2026-08-24T12:00:00+00:00"}
{"chunk_id": "def456", "categories_detected": ["EMAIL"], "action_taken": "redacted", "scan_timestamp": "2026-08-24T12:00:00+00:00"}
```

Fields: see `data-model.md` — PII Scan Record.

Already-resolved chunks (skipped by the scroll filter) do NOT produce an audit record on re-run — idempotency is preserved at the audit-file level too.

---

## Detection Categories

The following PII categories are in scope (per spec Clarifications):

| Category label | Description | Example pattern |
|---|---|---|
| `EMAIL` | Email addresses | `user@example.com` |
| `PHONE` | Phone numbers (E.164, BR, NANP) | `+55 11 91234-5678`, `212-555-0199` |
| `ADDRESS` | Physical addresses (street keyword + number) | `Rua das Flores 123`, `42 Elm Street` |
| `GOV_ID` | Government ID numbers (CPF, RG, SSN) | `123.456.789-09`, `123-45-6789` |

A person's name alone is **never** a flaggable category (per spec Clarifications Q1 — the subject-exclusion rule). No NLP or external API is used; detection is regex-only (FR-006).
