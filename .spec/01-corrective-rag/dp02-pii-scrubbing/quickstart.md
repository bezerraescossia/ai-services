# Quickstart: Corpus PII Scrubbing & Flagging

**Feature**: `dp02-pii-scrubbing` — run after DP1 has ingested a corpus_version.

---

## Prerequisites

1. DP1 has already run for the target `corpus_version` — chunks are in Qdrant with `retrievable=false, pii_flagged=false`.
2. Qdrant is running (default: `http://localhost:6333`).
3. `OPENAI_API_KEY` is **not** required for DP2 — no embeddings are generated.

```bash
# Start Qdrant if not already running
docker compose up -d qdrant

# Verify DP1's chunks are present (replace version with your actual value)
CORPUS_VERSION=20260822-98c9d49d0bad
```

---

## Run the PII scan

```bash
export QDRANT_URL=http://localhost:6333

python -m corrective_rag.scrubbing --corpus-version $CORPUS_VERSION
```

Expected output (corpus is expected clean):

```
pii_scan_complete corpus_version=20260822-98c9d49d0bad scanned=312 clean=312 flagged=0
```

If the corpus contains planted PII (e.g. in a test):

```
pii_scan_complete corpus_version=... scanned=312 clean=311 flagged=1
```

---

## Verify the audit trail

```bash
cat data/corrective-rag/$CORPUS_VERSION/pii_scan/audit.jsonl | head -5
```

Each line is a JSON object per scanned chunk. Example:

```json
{"chunk_id": "abc123", "categories_detected": [], "action_taken": "clean", "scan_timestamp": "2026-08-24T12:00:00+00:00"}
```

---

## Verify chunks are published in Qdrant

Use the Qdrant REST API or dashboard to confirm `retrievable=true` on all chunks for the corpus_version:

```bash
curl -s "$QDRANT_URL/collections/document_chunks/points/scroll" \
  -H "Content-Type: application/json" \
  -d '{
    "filter": {
      "must": [
        {"key": "corpus_version", "match": {"value": "'"$CORPUS_VERSION"'"}},
        {"key": "retrievable", "match": {"value": false}}
      ]
    },
    "limit": 1,
    "with_payload": false
  }' | python3 -c "import json,sys; r=json.load(sys.stdin); print('Unscanned chunks remaining:', len(r['result']['points']))"
```

Expected: `Unscanned chunks remaining: 0`

---

## Re-run idempotency

Running the command again against the same `corpus_version` is safe:

```bash
python -m corrective_rag.scrubbing --corpus-version $CORPUS_VERSION
# pii_scan_complete corpus_version=... scanned=0 clean=0 flagged=0
```

`scanned=0` confirms idempotency — all chunks were already `retrievable=true` and no writes occurred.

---

## What's next

Once `pii_scan_complete` is confirmed with `scanned=N` (first run) and all chunks are `retrievable=true`, MOD1 (Baseline Retriever) can build against the live index. See `.spec/01-corrective-rag/epic.md` for the full sequencing.

---

## Failure: scan aborted

If the detector errors on a chunk:

```
pii_scan_aborted corpus_version=... failed_chunk='<id>' cause=<exception>
```

This is FR-009 behaviour — no partial writes were made. Inspect the chunk text for encoding issues or malformed content, then re-run. All chunks remain in their pre-scan state.
