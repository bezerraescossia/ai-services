# Tasks: Corpus PII Scrubbing & Flagging

**Feature**: `dp02-pii-scrubbing`
**Spec**: .spec/01-corrective-rag/dp02-pii-scrubbing/spec.md
**Plan**: .spec/01-corrective-rag/dp02-pii-scrubbing/plan.md

User Stories in scope:
- US1 — No chunk with personal data becomes retrievable (P1)
- US2 — Legitimate encyclopedic content is not gutted by over-flagging (P1)

---

## Phase 1 — Setup

- [X] T001 Create scrubbing source package skeleton: `src/corrective_rag/scrubbing/__init__.py`, `detector.py` (empty), `redactor.py` (empty), `audit.py` (empty), `scanner.py` (empty), `cli.py` (empty)
- [X] T002 Create test package skeleton: `tests/corrective_rag/scrubbing/__init__.py`, `test_detector.py` (empty), `test_redactor.py` (empty), `test_audit.py` (empty), `test_scanner.py` (empty)

---

## Phase 2 — Foundational (Failing Tests — TDD)

- [X] T003 [P] Write failing unit tests for `src/corrective_rag/scrubbing/detector.py` in `tests/corrective_rag/scrubbing/test_detector.py`: one test per flaggable category (email, phone, physical address, government ID); a chunk with only a person's name is clean; ambiguous numeric token (could be ID or catalog number) is flagged; multi-span text produces multiple DetectedSpan entries; empty text returns empty list
- [X] T004 [P] Write failing unit tests for `src/corrective_rag/scrubbing/redactor.py` in `tests/corrective_rag/scrubbing/test_redactor.py`: single span replaced with `[REDACTED:<CATEGORY>]`; multiple non-overlapping spans all replaced; no-span input returns original text unchanged; replacement preserves surrounding characters
- [X] T005 [P] Write failing unit tests for `src/corrective_rag/scrubbing/audit.py` in `tests/corrective_rag/scrubbing/test_audit.py`: `PiiScanRecord` serializes to expected JSON shape; `append_audit` writes a valid JSONL line; calling `append_audit` twice for different chunk_ids produces two lines; `write_eval_results` writes a JSON file with SC-003/SC-004/SC-005 pass/fail fields
- [X] T006 Write failing integration test for `src/corrective_rag/scrubbing/scanner.py` in `tests/corrective_rag/scrubbing/test_scanner.py`: fixture populates an in-memory Qdrant client with three chunks for a corpus_version (1 clean, 1 with a planted email, 1 already `retrievable=true`); after `run_scan()`, assert the planted chunk has `pii_flagged=true` and `retrievable=true` with redacted text; assert the clean chunk has `pii_flagged=false` and `retrievable=true`; assert the already-resolved chunk is unchanged (idempotency); assert audit JSONL has exactly 2 records (the already-resolved chunk is skipped); assert `ScanAbortedError` is raised and no Qdrant writes occur when a DetectorError is injected mid-scan — depends on T003–T005 contracts

---

## Phase 3 — Data Preparation

- [ ] T007 Create `data/corrective-rag/eval/pii_scrubbing/planted_examples.json`: synthetic eval set with ≥1 chunk per resolved flaggable category (email, phone, physical address, government ID); each entry includes `chunk_id`, `text` (Wikipedia-prose-style sentence with a planted span), and `expected_categories`; spans must be realistic but non-real (e.g. `user@example.invalid`, `+55 11 91234-5678`, `Rua Teste 123 São Paulo`, `123.456.789-09`)
- [ ] T008 [P] Create `data/corrective-rag/eval/pii_scrubbing/biography_chunks.json`: manually curated sample of ≥10 real chunks from the ingested corpus where the only person-related content is the article's own encyclopedic subject named in context; extract from the Qdrant scroll or the DVC manifest; each entry includes `chunk_id`, `text`, `source_document_id`; expected result for SC-004: zero flagged — used to guard against over-flagging
- [ ] T009 [P] Create `data/corrective-rag/eval/pii_scrubbing/identifier_chunks.json`: manually curated sample of ≥10 real chunks from the corpus containing mission or spacecraft catalog numbers, numeric designations, or similar identifier-like tokens that are not personal data (e.g. "Apollo 11", "STS-135", "Vostok 1"); each entry includes `chunk_id`, `text`, `source_document_id`; expected result for SC-005: zero flagged — used to guard against token-shaped false positives

---

## Phase 4 — Modeling / Experimentation

- [X] T010 [US1] Implement `src/corrective_rag/scrubbing/detector.py`: define `DetectedSpan(start, end, category, text)`; implement `detect(text: str) -> list[DetectedSpan]` using compiled regex patterns for email (RFC-5322-lite: `[\w.+-]+@[\w-]+\.[a-zA-Z]{2,}`), phone (E.164 or common BR/US format with optional country code and separators), physical address (street number + keyword heuristic: rua/avenida/av./street + number), government ID (CPF `\d{3}\.\d{3}\.\d{3}-\d{2}`, RG `\d{1,2}\.\d{3}\.\d{3}-[\dX]`, SSN-like `\d{3}-\d{2}-\d{4}`); sort results by start offset ascending; case-insensitive flags where applicable. Accept: all T003 tests pass AND T014 (SC-003 gate) passes | Reject → T010-R: tighten false-positive-prone patterns (especially address heuristic and gov-ID patterns) with stricter anchors or negative lookaheads, then re-run T003 and T014
- [X] T011 [P] [US1] Implement `src/corrective_rag/scrubbing/redactor.py`: implement `redact(text: str, spans: list[DetectedSpan]) -> str` — sort spans by `start` descending to preserve earlier offsets during replacement, replace each span with `[REDACTED:<CATEGORY>]` (category uppercased), return original text unchanged when `spans` is empty. Accept: all T004 tests pass | Reject → T011-R: fix offset drift in multi-span replacement (process right-to-left, or accumulate offset delta) and re-run T004
- [X] T012 [P] [US1] Implement `src/corrective_rag/scrubbing/audit.py`: define `PiiScanRecord(chunk_id: str, categories_detected: list[str], action_taken: Literal["clean", "redacted"], scan_timestamp: str)`; implement `append_audit(record: PiiScanRecord, path: Path) -> None` (JSONL append, creates file+parent dirs if absent); implement `write_eval_results(results: dict, path: Path) -> None` (JSON write with keys `sc003_pass`, `sc004_pass`, `sc005_pass`, `run_timestamp`). Accept: all T005 tests pass | Reject → T012-R: fix serialization (ensure `categories_detected` serializes as list, timestamp is ISO-8601) and re-run T005
- [X] T013 [US1] [US2] Implement `src/corrective_rag/scrubbing/scanner.py`: define `ScanAbortedError(chunk_id, cause)`; implement `run_scan(corpus_version: str, qdrant_client: QdrantClient, audit_dir: Path) -> ScanResult` — scroll all points in `document_chunks` where `corpus_version == corpus_version AND retrievable == false AND pii_flagged == false` (FR-007 idempotency: already-resolved chunks are skipped by the filter); for each chunk call `detect(text)` inside a try/except — on any exception raise `ScanAbortedError` immediately (FR-009: no Qdrant writes if any chunk errors); collect `(point_id, new_payload_delta)` pairs in memory; after the full scroll completes successfully, bulk-`set_payload` all deltas in one call (clean: `{pii_flagged: false, retrievable: true}`; flagged: `{pii_flagged: true, retrievable: true, text: redacted_text}`); then call `append_audit` per chunk; return `ScanResult(corpus_version, scanned, clean, flagged)`. Accept: T006 integration test passes | Reject → T013-R: isolate the abort path — verify no Qdrant `set_payload` call is made before the full scan loop completes without exception, and re-run T006

---

## Phase 5 — Evaluation Gate

*All three gates must be [X] with PASS before any Phase 6 task may begin.*

- [ ] T014 Run SC-003 recall gate: call `detect(chunk["text"])` for every entry in `data/corrective-rag/eval/pii_scrubbing/planted_examples.json`; assert 100% of entries have at least one `DetectedSpan` matching the entry's `expected_categories`; write `sc003_pass: true/false` and per-category miss list to `data/corrective-rag/eval/pii_scrubbing/eval_results.json` via `write_eval_results` — PASS required before Phase 6
- [ ] T015 [P] Run SC-004 false-positive gate: call `detect(chunk["text"])` for every entry in `data/corrective-rag/eval/pii_scrubbing/biography_chunks.json`; assert zero entries return a non-empty span list; write `sc004_pass: true/false` and any false-positive `chunk_id` list to `data/corrective-rag/eval/pii_scrubbing/eval_results.json` — PASS required before Phase 6
- [ ] T016 [P] Run SC-005 false-positive gate: call `detect(chunk["text"])` for every entry in `data/corrective-rag/eval/pii_scrubbing/identifier_chunks.json`; assert zero entries return a non-empty span list; write `sc005_pass: true/false` and any false-positive `chunk_id` list to `data/corrective-rag/eval/pii_scrubbing/eval_results.json` — PASS required before Phase 6

---

## Phase 6 — Deployment

- [ ] T017 [US1] [US2] Implement `src/corrective_rag/scrubbing/cli.py`: `python -m corrective_rag.scrubbing --corpus-version <v>` — mirrors DP1's `cli.py` pattern; reads `QDRANT_URL` env var (default `http://localhost:6333`); resolves audit dir to `data/corrective-rag/<corpus_version>/pii_scan/`; calls `run_scan()`; on success prints `pii_scan_complete corpus_version=<v> scanned=N clean=N flagged=N` to stdout; on `ScanAbortedError` prints error to stderr and exits non-zero; DVC-add is a separate task (T022)
- [ ] T018 Write `.spec/01-corrective-rag/dp02-pii-scrubbing/data-model.md`: document `PII Scan Record` entity (`chunk_id`, `categories_detected`, `action_taken`, `scan_timestamp`) per FR-005's LGPD audit requirement; cross-reference `Document Chunk` from `shared-data-model.md`; note that DP2 is the sole writer of `pii_flagged=true` and the second writer of `retrievable` (after DP1's default `false`)
- [ ] T019 [P] Write `.spec/01-corrective-rag/dp02-pii-scrubbing/scrubbing-contract.md`: CLI contract (args, env vars, exit codes, stdout format, error messages); Qdrant payload mutation contract (fields written per chunk, idempotency guarantee, abort semantics — no partial-corpus_version mutations possible); audit file layout
- [ ] T020 [P] Write `.spec/01-corrective-rag/dp02-pii-scrubbing/quickstart.md`: prerequisites (DP1 already run for the target `corpus_version`, Qdrant running); setup (env vars); scan command; expected stdout; how to inspect `audit.jsonl` to confirm the audit trail; how to verify `retrievable=true` for clean chunks in Qdrant; how to re-run idempotently

---

## Final Phase — Polish

- [ ] T021 Run full check: `uv run task check` (`lint + typecheck + test`); fix any ruff or mypy errors introduced by this feature; confirm all tests in `tests/corrective_rag/scrubbing/` are green
- [ ] T022 DVC-track the eval dataset: `dvc add data/corrective-rag/eval/pii_scrubbing/` (Principle I — eval dataset is a versioned artifact, not a free-floating file)
- [ ] T023 Update `.spec/01-corrective-rag/epic.md`: flip DP2's `Status` from `Specified` to `Implemented` in the Data Preparation feature table row

---

## Dependencies & Execution Order

```
T001 → T002
T002 → T003, T004, T005          [parallel]
T003, T004, T005 → T006
T006 → T007
T007 → T008, T009                [parallel]
T008, T009 → T010
T010 → T011, T012                [parallel]
T011, T012 → T013
T013 → T014
T014 → T015, T016                [parallel — Phase 5 gate]
T015, T016 → T017
T017 → T018
T018 → T019, T020                [parallel]
T019, T020 → T021
T021 → T022 → T023
```

**Hard gate**: T015 and T016 must both be [X] with PASS before T017 (CLI) begins. If T014 fails, follow T010-R before attempting T015–T016.

## Parallel Example

Within Phase 4, after T010 is [X]:

```
# T011 (redactor.py) and T012 (audit.py) touch different files with no shared state
# Run concurrently; both must be [X] before T013 (scanner.py) begins

# T011 — tests/corrective_rag/scrubbing/test_redactor.py → src/corrective_rag/scrubbing/redactor.py
# T012 — tests/corrective_rag/scrubbing/test_audit.py    → src/corrective_rag/scrubbing/audit.py
# T013 — waits for both
```

## Implementation Strategy — MVP Scope

MVP = T001–T013 (all source files passing their unit and integration tests) + T014–T016 (evaluation gates) + T017 (CLI entry point). This is the minimum that satisfies FR-001 through FR-009 and clears the Evaluation Gate so MOD1 can build against a fully-published corpus.

T018–T020 (contracts, quickstart) and T021–T023 (polish, DVC, epic update) are finalization tasks that run after the gate clears and before the PR merges.

If T014 (SC-003 recall) fails: follow T010-R immediately — do not attempt T015/T016 with a broken detector.
If T015 or T016 (false-positive gates) fail: follow T010-R (tighten the offending pattern) and re-run only the failing gate before proceeding.
