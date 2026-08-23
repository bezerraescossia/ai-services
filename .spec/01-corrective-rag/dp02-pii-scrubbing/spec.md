# Feature Specification: Corpus PII Scrubbing & Flagging

**Feature Branch**: `dp02-pii-scrubbing`
**Created**: 2026-08-22
**Status**: Clarified
**Epic**: .spec/01-corrective-rag/epic.md — Feature DP2
**Input**: User description: "corrective rag"

## Clarifications

### Session 2026-08-22

- Q: Which categories of entity should DP2 treat as flaggable personal data in this corpus, given that most of the corpus is legitimately about named people (astronauts, scientists)? → A: Contact/identifier data only — emails, phone numbers, physical addresses, government ID numbers. Never flag a person's name by itself, including the article's own subject.
- Q: When DP2 detects flaggable personal data in a chunk, how should it resolve that chunk before DP1's index can consider it settled? → A: Auto-redact and publish — replace the detected span with a redaction placeholder, set `pii_flagged=true`, and still flip `retrievable=true`. No manual step blocks the pipeline.
- Q: If the PII detector itself errors out while scanning a specific chunk, should the whole scan run abort, or should that chunk be skipped and left for later retry? → A: Abort whole run — mirrors DP1's own failure policy and preserves FR-008's guarantee that a completed run never leaves a chunk unresolved.
- Q: Should the eval also check for false positives on ordinary non-biography content (e.g. numeric mission/spacecraft designations resembling an ID number), beyond SC-004's subject-biography check? → A: Yes — add a false-positive check on a sample of ordinary corpus content containing identifier-like tokens that are not personal data.
- Q: Should DP2's scan run automatically as soon as DP1's ingestion completes, or as a separately, manually triggered step? → A: Manually triggered, separate step — matches DP1's own "manually-triggered batch job" framing for this demo; someone runs DP1 then explicitly runs DP2.

## Business & Data Understanding

**Business Objective**: No chunk containing personal data may become retrievable, be surfaced in a generated answer, or be sent to MOD3's third-party web-search fallback, per Principle VII and the constitution's LGPD data-governance requirement. DP1 writes every chunk in an unpublished state (`retrievable=false`, `pii_flagged=false` by default); this feature is the mandatory gate that decides, chunk by chunk, whether that default holds or must change before MOD1's retriever can ever query it.

**ML Objective**: A PII-detection pass over each unpublished Document Chunk's text — entity recognition for personal-data categories — that classifies each chunk as clean or flagged and gates/redacts accordingly. Framing: per-chunk multi-label entity detection over a fixed, small corpus (not a streaming or online task), run once per corpus_version as a batch pass immediately after DP1.

**Data Availability & Quality**: Per BDU1's resolution, the corpus is ~20-30 public Wikipedia articles about space exploration — not expected to contain personal data in the LGPD sense, but almost entirely *about* named individuals (astronauts, scientists, engineers) who are the encyclopedic subject of the very articles being indexed. A naive "flag any person's name" policy would quarantine most of the corpus and defeat the point of building it. Per Clarifications, the flaggable scope is fixed to contact/identifier-type data only (emails, phone numbers, physical addresses, government ID numbers) — a person's name is never flaggable on its own, including the article's own subject.

**Non-Goals**: This feature does not ingest, fetch, or chunk documents (DP1's job); does not build the retriever (MOD1) or relevance evaluator (MOD2); does not sanitize live user or fallback queries (MOD5 — a different data path: in-flight queries, not indexed corpus content); does not flag or redact a person's name on its own, including the article's own subject (per Clarifications); does not implement the human-in-the-loop *answer* routing used at serving time (DEPLOY3) — flagged chunks are auto-redacted and published, not routed to a review queue.

## User Scenarios & Testing

### User Story 1 - No chunk with personal data becomes retrievable (Priority: P1)

Before any chunk DP1 wrote can be queried by MOD1's retriever, it must pass a personal-data scan. Today, DP1 leaves every chunk unpublished (`retrievable=false`) specifically so this feature can be the deciding step.

**Why this priority**: This is the constitution's hard LGPD/Principle VII gate for the corpus — MOD1 cannot be built against a live index until this decision path exists for every chunk DP1 produces.

**Independent Test**: Can be tested by running the scan against a corpus_version containing at least one chunk with a deliberately embedded personal-data example (e.g. a planted email address) and confirming that chunk is not `retrievable=true` while unrelated clean chunks are.

**Acceptance Scenarios**:

1. **Given** a corpus_version with all chunks in DP1's default unpublished state, **When** the scan runs, **Then** every chunk is classified clean or flagged and its `pii_flagged`/`retrievable` fields are updated accordingly — no chunk is left in DP1's "not yet scanned" default state afterward.
2. **Given** a chunk containing a planted personal-data example, **When** the scan runs, **Then** that chunk is flagged, the detected span is redacted in the chunk text, and `retrievable=true` is set only on the redacted version.

---

### User Story 2 - Legitimate encyclopedic content is not gutted by over-flagging (Priority: P1)

A chunk that discusses the article's own subject by name (e.g. "Buzz Aldrin was the second person to walk on the Moon") must not be quarantined as if it exposed personal data — this corpus is a set of biographical/technical Wikipedia articles, and flagging every named person would make the demo corpus useless.

**Why this priority**: Equally load-bearing as User Story 1 — a scan that only errs toward over-flagging silently fails the epic by leaving MOD1 with a near-empty retrievable index.

**Independent Test**: Can be tested by running the scan against a chunk that only names the article's own subject (no other personal-data category present) and confirming it is classified clean and reaches `retrievable=true`.

**Acceptance Scenarios**:

1. **Given** a chunk whose only person-related content is the article's own subject named in an encyclopedic, already-public context, **When** the scan runs, **Then** the chunk is classified clean and becomes `retrievable=true`.

---

### Edge Cases

- What happens when a chunk contains a numeric or string token that could be a flaggable identifier (e.g. a government ID number) or could be an innocuous in-domain designation (e.g. a mission or spacecraft catalog number)? Must not silently default to clean when genuinely ambiguous — treated as flagged and redacted per Assumptions, erring toward the safer default.
- How does the system behave when the PII-detection step itself would need to send raw, unscreened chunk text to a third-party API to do the scan? Must not do so — see Risk Assessment; the detector must run without exporting unscreened chunk text externally.
- How does the system handle a chunk with zero detected entities of any kind (most of the corpus, expected)? Fast path — classified clean, `retrievable=true`, no further action.
- How does the system behave if the scan is re-run against a corpus_version that has already been fully cleared? Must be idempotent — must not change already-resolved `pii_flagged`/`retrievable` values or create duplicate scan records.
- How does the system behave if the detector errors while scanning a specific chunk (malformed text, unexpected exception)? Must abort the entire run rather than partially resolving the corpus_version — matches DP1's own fail-loud policy.

## Requirements

### Functional Requirements

- **FR-001**: The system MUST scan the text of every chunk in DP1's default unpublished state (`retrievable=false`, `pii_flagged=false`, not yet scanned) for personal-data entities in the categories resolved in Clarifications.
- **FR-002**: The system MUST classify each scanned chunk as clean or flagged based on those resolved categories, excluding a person named as the article's own encyclopedic subject from counting as flaggable on that basis alone.
- **FR-003**: For a chunk classified clean, the system MUST set `pii_flagged=false` (confirmed) and `retrievable=true`.
- **FR-004**: For a chunk classified flagged, the system MUST replace each detected span with a redaction placeholder in the chunk text, set `pii_flagged=true`, and set `retrievable=true` on the redacted chunk — per Clarifications, no chunk is permanently quarantined by this feature.
- **FR-005**: The system MUST record, per scanned chunk, which categories (if any) were detected and what action was taken — this record is the audit trail the constitution's LGPD documentation requirement (what personal data was found, how it was handled) points to.
- **FR-006**: The system MUST run its detection step without sending raw, unscreened chunk text to any third-party API — the detector MUST be a local/self-hosted mechanism, not an external LLM call made before the text has been screened.
- **FR-007**: The system MUST be idempotent — re-running the scan against a corpus_version whose chunks are already fully resolved MUST NOT change their `pii_flagged`/`retrievable` values or create duplicate scan records.
- **FR-008**: The system MUST leave no chunk from a completed scan run in DP1's "not yet scanned" default state — every chunk must exit the run either clean or flagged.
- **FR-009**: The system MUST abort the entire scan run, resolving no chunk in that run, if the detector errors while scanning any single chunk — matching DP1's fail-loud policy rather than partially resolving a corpus_version.

### Key Entities

- **Document Chunk**: see `.spec/01-corrective-rag/shared-data-model.md` — this feature is the sole writer that flips `pii_flagged` to `true` and the second writer (after DP1's default `false`) of `retrievable`.
- **PII Scan Record**: local to this feature (not in the shared data model — no other feature in the epic currently consumes it). Represents the audit trail for one chunk's scan: `chunk_id`, `categories_detected` (list, possibly empty), `action_taken` (clean / redacted), `scan_timestamp`. Backs FR-005's LGPD audit requirement.

## Risk Assessment

| Failure Mode | Likelihood | Severity | Mitigation |
|---|---|---|---|
| The PII-detection step itself sends raw, unscreened chunk text to a third-party LLM API to do the scan — leaking exactly the data this feature exists to protect | Medium | High | FR-006: detection must run via a local/self-hosted NER or rule-based mechanism, never an external API call on unscreened text |
| Over-flagging (treating the article's own named subject as personal data) quarantines most of the corpus, leaving MOD1 with a near-empty retrievable index | Medium | High | FR-002 explicitly excludes the article's own encyclopedic subject from counting as flaggable on that basis alone; User Story 2's acceptance test guards this directly |
| Under-flagging misses a genuine contact/identifier-type mention (e.g. an email or phone number embedded in cited source text), which is later surfaced in a generated answer or sent to MOD3's fallback unredacted | Low | High | Detector evaluated against a small set of chunks with deliberately planted personal-data examples per resolved category before this feature ships (see Success Criteria SC-003); ambiguous detections do not default to clean (Edge Cases) |
| Auto-redaction leaves a chunk garbled or loses meaning-critical context (e.g. a redacted span mid-sentence), degrading retrieval/generation quality on an otherwise-relevant chunk | Low | Medium | Redaction replaces only the detected span with a placeholder token rather than dropping the whole chunk; spot-checked during this feature's own implementation before MOD1 builds against the index |
| No natural positive examples exist in this corpus to evaluate detector recall against (the corpus is expected to be clean) | High | Low | Evaluate using synthetic/planted examples rather than a naturally-occurring held-out set — documented as an accepted deviation from a fully natural eval set, appropriate given the corpus's expected composition |

## Success Criteria

### Business KPIs

- **SC-001**: 100% of chunks in a completed scan run exit DP1's "not yet scanned" default state — verified by checking no chunk in the corpus_version has `pii_flagged=false` while still being in an unscanned/undetermined status.
- **SC-002**: Zero chunks classified clean contain a detectable instance of a resolved flaggable category — verified by re-running the detector against the published (`retrievable=true`) subset as a spot audit and confirming no positive hits.

### Model/ML Metrics

- **SC-003**: The detector achieves 100% recall on a planted-example set (at least one synthetic chunk per resolved flaggable category, seeded specifically for this evaluation since the corpus is expected to contain no natural positive examples) before this feature is considered ready to gate DP1's output for MOD1.
- **SC-004**: Zero chunks whose only person-related content is the article's own encyclopedic subject are classified flagged, measured against a manually reviewed sample of at least 10 subject-biography chunks from the corpus.
- **SC-005**: Zero false positives on a manually reviewed sample of at least 10 chunks containing identifier-like tokens that are not personal data (e.g. mission/spacecraft catalog numbers), guarding against token-shaped over-flagging distinct from SC-004's name-based case.

## Assumptions

- **Legal basis / retention / deletion (LGPD documentation)**: the corpus is public Wikipedia content, so the legal basis for any incidentally-detected personal data is treated as legitimate interest in already publicly-manifested data (LGPD Art. 7, IX); retention follows the corpus_version's own DVC lifecycle (no separate retention clock); a data-subject deletion/access request is fulfilled by excluding or redacting the source content at the next ingestion re-run, since there is no live per-user data store to purge. These are stated here as the feature's documentation deliverable per the constitution's Data Governance & Privacy section, not re-litigated as a separate clarification.
- The specific PII-detection mechanism (a named NER library/model vs. rule-based pattern matching) is an implementation choice deferred to this feature's own `plan.md`; the spec only fixes the observable behavior (local execution, category coverage, subject-exclusion rule) that choice must satisfy.
- This feature runs once per corpus_version, immediately after DP1 and before MOD1 exists — matching the epic's Sequencing note (BDU1 → DP1 → DP2 → MOD1) already reflected in DP1's own spec and in `epic.md`'s MOD1 dependency row. Per Clarifications, it is a separately, manually triggered batch step (not auto-chained after DP1), consistent with DP1's own manually-triggered framing for this demo.
- Ambiguous detections (Edge Cases: a token that could be a flaggable identifier or an innocuous in-domain designation) are treated as flagged and redacted, not clean — erring toward the safer default when genuinely uncertain, consistent with auto-redaction carrying no manual-review cost.
