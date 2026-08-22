# Feature Specification: Document Ingestion & Indexing Pipeline

**Feature Branch**: `dp01-document-ingestion`
**Created**: 2026-08-22
**Status**: Draft
**Epic**: .spec/01-corrective-rag/epic.md — Feature DP1
**Input**: User description: "corrective rag"

## Clarifications

### Session 2026-08-22

- Q: Should DP1's indexed corpus become queryable by MOD1's retriever immediately after ingestion, or stay staged until DP2's PII scan clears it? → A: Staged until DP2 clears it. DP1 writes chunks to the index in an unpublished/unretrievable state; DP2's scan flips cleared chunks to retrievable (or drops/quarantines flagged ones). Matches the epic's Sequencing note (BDU1 → DP1 → DP2 → MOD1) and gives Principle VII a hard gate before anything is ever queryable.

## Business & Data Understanding

**Business Objective**: Every downstream CRAG component (the retriever, the relevance evaluator, the eval harness) needs a queryable, versioned index of the scoped corpus to operate against. Without a reliable, reproducible ingestion pipeline, retrieval quality and eval results can never be pinned to a specific, auditable corpus state.

**ML Objective**: Not a model itself — this feature is the data pipeline that turns BDU1's resolved corpus (Wikipedia articles on space exploration) into embedded, indexed Document Chunks that MOD1's retriever can query by similarity. Framing: batch ingestion producing a versioned artifact (the index), not an online/streaming pipeline.

**Data Availability & Quality**: Per BDU1 (`.spec/01-corrective-rag/bdu01-corpus-scoping/spec.md`), the corpus is ~20-30 English Wikipedia articles about space exploration (e.g. Apollo program, Mars rovers, the ISS, Voyager program), fetched via Wikipedia's public REST API — no authentication required, well-documented HTML/plain-text extract format. This feature selects the final concrete article list within that scope (BDU1 explicitly deferred the exact list to DP1). Volume is demo-scale (tens of articles, not a large corpus), so ingestion is expected to complete as a single batch run rather than requiring incremental/streaming processing.

**Non-Goals**: This feature does not implement retrieval or similarity search over the index (MOD1's job); does not score or filter chunks for relevance (MOD2's job); does not scrub or redact personal data from chunk content (DP2's job — DP1 only creates the field for DP2 to populate); does not select or justify a specific embedding model or vector store product — those are implementation choices for this feature's own plan, not spec-level decisions.

## User Scenarios & Testing

### User Story 1 - Corpus becomes queryable for retrieval (Priority: P1)

The team needs the scoped Wikipedia corpus turned into a set of embedded, indexed chunks so that MOD1's retriever has something concrete to query. Today, no ingestion or index exists — MOD1 cannot be built or tested without this feature completing first.

**Why this priority**: Every downstream Modeling and Evaluation feature (MOD1 onward) is blocked until an index exists. This is the walking skeleton's second step after BDU1.

**Independent Test**: Can be tested by running ingestion end-to-end and confirming a similarity query against the resulting index returns chunk results (even before MOD1's own retriever logic exists, a raw nearest-neighbor query against the index should return non-empty results for an in-topic query).

**Acceptance Scenarios**:

1. **Given** the finalized list of ~20-30 space-exploration Wikipedia article titles, **When** the ingestion pipeline runs, **Then** each article is fetched, split into Document Chunks, embedded, and written to the index with a shared `corpus_version` identifier.
2. **Given** an ingestion run has completed, **When** a raw similarity query is issued against the index for an in-topic term (e.g. "Apollo 11 mission goals"), **Then** the index returns one or more chunks whose `source_document_id` corresponds to a relevant article.

---

### User Story 2 - Corpus snapshot is versioned and reproducible (Priority: P1)

Anyone re-running an evaluation or debugging a retrieval result later needs to know exactly which corpus snapshot produced a given index — an unversioned or silently-mutating index makes eval results and production behavior impossible to audit or reproduce (Principle I).

**Why this priority**: Reproducibility is a constitutional hard requirement, not an enhancement; EVAL2 and DEPLOY2 both need a stable, citable corpus version to compare against.

**Independent Test**: Can be tested by running ingestion twice against the same source content and confirming both runs produce an identical chunk set under a new DVC-tracked version, with the ability to check out either version independently.

**Acceptance Scenarios**:

1. **Given** an ingestion run has completed, **When** the resulting corpus snapshot is inspected, **Then** it is tracked under a DVC version identifier that uniquely maps to the exact raw articles fetched and the exact chunk set produced from them.
2. **Given** two ingestion runs against unchanged source articles, **When** their outputs are compared, **Then** the chunk_id set and chunk text are identical (deterministic chunking), differing only in metadata such as timestamps.

---

### Edge Cases

- What happens when a Wikipedia article fetch fails (network error, 404, article renamed/deleted since BDU1's scoping)? The run must fail loudly with the specific failing article identified, rather than silently producing a partial corpus.
- How does chunking handle an article shorter than one chunk, or containing mostly non-prose content (e.g. infoboxes, reference lists)? Must not produce empty or near-empty chunks that dilute retrieval quality.
- How does the system behave if the embedding API is rate-limited or briefly unavailable mid-run? The run must retry with backoff and, on persistent failure, abort without partially indexing the corpus_version (avoids a half-embedded, unreliable snapshot).
- How does the system behave when re-run against a corpus_version that already exists (no source changes)? Must be idempotent — must not create duplicate chunk_ids or a redundant DVC version.

## Requirements

### Functional Requirements

- **FR-001**: The system MUST fetch the finalized list of ~20-30 space-exploration Wikipedia articles via Wikipedia's public REST API, per BDU1's scoping.
- **FR-002**: The system MUST split each fetched article into Document Chunks bounded to a size suitable for embedding and retrieval, respecting paragraph/sentence boundaries rather than splitting mid-sentence.
- **FR-003**: The system MUST generate an embedding vector for every Document Chunk and record a pointer to it in `embedding_ref` (per the shared Document Chunk entity) — never the raw vector itself in the entity record.
- **FR-004**: The system MUST write every chunk into the vector store index in an unpublished/unretrievable state, associated with the `corpus_version` it belongs to — chunks MUST NOT be queryable by MOD1's retriever until DP2 has cleared them (per Clarifications).
- **FR-005**: The system MUST version each corpus snapshot (raw fetched article content and the chunk set derived from it) with DVC before it is considered available to downstream features, per Principle I.
- **FR-006**: The system MUST set `pii_flagged` to a default "not yet scanned" (`false`) value on chunk creation — actual PII scanning, flagging, and publishing to a queryable state is DP2's responsibility, run as a subsequent pass.
- **FR-007**: The system MUST fix and log any random seed used by a stochastic step in the pipeline (if any), per Principle I.
- **FR-008**: The system MUST be idempotent — re-running ingestion against unchanged source content MUST NOT create duplicate `chunk_id`s or a redundant DVC version.
- **FR-009**: The system MUST fail the entire ingestion run (not partially index) if any article fetch or embedding call fails persistently after retries, and MUST report which article/chunk failed.

### Key Entities

- **Document Chunk**: see `.spec/01-corrective-rag/shared-data-model.md` — this feature is the sole producer of Document Chunk records (`pii_flagged` and `retrievable` are both written here as defaults — `false` — and later updated by DP2).

## Risk Assessment

| Failure Mode | Likelihood | Severity | Mitigation |
|---|---|---|---|
| A Wikipedia article fetch fails or is rate-limited mid-run, producing a partial/incomplete corpus that gets silently used downstream | Medium | Medium | FR-009: fail the whole run on any persistent fetch/embedding failure rather than partially indexing |
| Chunking splits content awkwardly (mid-sentence, mid-fact), degrading retrieval relevance and confusing MOD2's evaluator | Medium | Medium | FR-002: chunk on paragraph/sentence boundaries; spot-check chunk boundaries before MOD1/MOD2 build against the index |
| Embedding model/API version changes between the initial ingestion run and a later re-run, silently breaking reproducibility of a previously-cited corpus_version | Low | Medium | Pin the exact embedding model identifier/version as DVC-tracked metadata alongside each corpus_version |

## Success Criteria

### Business KPIs

- **SC-001**: All ~20-30 scoped space-exploration articles are successfully ingested, chunked, and indexed in a single run with zero unresolved fetch failures.
- **SC-002**: Any previously-produced corpus_version can be checked out via its DVC identifier and yields the exact same chunk set it originally produced, enabling any later eval or production result to be reproduced.

### Model/ML Metrics

- **SC-003**: 100% of chunks written to the index have a non-null `embedding_ref` — measured at the end of any given ingestion run against its corpus_version.
- **SC-004**: Re-running ingestion twice against the same source article content produces an identical `chunk_id` set (verified by hash comparison), confirming deterministic chunking.

## Assumptions

- Per the resolved Clarification above, MOD1's retriever effectively depends on DP2 having run (not just DP1) even though the epic's Feature Backlog table lists MOD1's "Depends On" as DP1 only — `epic.md` is being updated alongside this spec to reflect DP2 as an additional dependency for MOD1, matching the Sequencing section's stated build order.
- Chunk size/overlap strategy and the specific embedding model/vector store are implementation decisions deferred to this feature's own `plan.md`, not spec-level choices — the spec only fixes the observable properties (boundary-respecting, deterministic, versioned) those choices must satisfy.
- Ingestion is a manually-triggered batch job for this demo (matching BDU1's framing of a DVC-pinned static snapshot rather than "live Wikipedia" at query time), not a scheduled/streaming pipeline.
- The finalized article list (the specific ~20-30 titles within the space-exploration topic) is selected as part of this feature's own implementation, not re-litigated at spec level, per BDU1's explicit deferral.
- **Closed during Implement** — finalized article list: 27 space-exploration titles, recorded in `src/corrective_rag/ingestion/articles.txt` (Apollo program, Apollo 11, Apollo 8, Apollo 13, Project Mercury, Project Gemini, Space Shuttle program, Space Shuttle Challenger disaster, Space Shuttle Columbia disaster, International Space Station, Skylab, Voyager program, Voyager 1, Voyager 2, Mars rover, Curiosity (rover), Perseverance (rover), Opportunity (rover), Spirit (rover), Viking program, Hubble Space Telescope, New Horizons, Cassini–Huygens, Juno (spacecraft), Artemis program, Neil Armstrong, Buzz Aldrin).
- **Closed during Implement** — finalized embedding model pin: `text-embedding-3-small` (OpenAI), recorded as both `embedding_model` and `embedding_model_version` in every persisted chunk manifest entry — see `data-preparation.md`'s Versioning Scheme for why OpenAI's embeddings API doesn't yet warrant a distinct version field.
- **FR-007 is N/A**: no stochastic step exists in this pipeline. `chunk_id` is a deterministic content hash (not randomly seeded), and the embedding call is a non-sampling, deterministic API request — there is no random seed to fix or log.
