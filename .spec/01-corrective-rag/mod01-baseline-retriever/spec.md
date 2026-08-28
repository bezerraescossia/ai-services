# Feature Specification: Baseline Retriever

**Feature Branch**: `mod01-baseline-retriever`
**Created**: 2026-08-24
**Status**: Clarified
**Epic**: .spec/01-corrective-rag/epic.md — Feature MOD1
**Input**: User description: "corrective rag"

## Clarifications

### Session 2026-08-24

- Q: What should the default value of k be for the top-k retrieval? → A: k=5. Small, demo-appropriate candidate set; lower cost and latency. MOD2 evaluates 5 chunks per query. k remains runtime-configurable so it can be adjusted without a code change.
- Q: Should raw cosine similarity scores be persisted to the Retrieval Decision Record or remain ephemeral pipeline state? → A: Persisted. The shared data model already has `relevance_scores` as a field on the Retrieval Decision Record (attributed to MOD2 in `shared-data-model.md`). MOD1 populates this field as part of initializing the record — making every query's retrieval quality auditable in EVAL2, MON1, and MON2 at no extra cost.

## Business & Data Understanding

**Business Objective**: Before any answer can be generated or evaluated, the system must find the corpus chunks that are most likely to be relevant to the user's query. MOD1 is the entry point for every live query into the CRAG pipeline — it produces the candidate set that MOD2's relevance evaluator will score, that MOD3's fallback logic will act on, and that MOD4's generator will condition on. Without a working retriever, the corrective mechanism has nothing to evaluate or correct.

**ML Objective**: Dense retrieval — embed the user query using the same model and version pinned by DP1 (`text-embedding-3-small`), then run a nearest-neighbor search against the Qdrant `document_chunks` collection to return the top-k most similar chunks by cosine similarity. The query and corpus embeddings are produced by the same model, so cosine similarity is a meaningful proxy for semantic relatedness. This is deliberately baseline — no hybrid search, re-ranking, or query rewriting — giving MOD2 a clean, unaugmented candidate set to evaluate.

**Data Availability & Quality**: The indexed corpus produced by DP1 and cleared by DP2 — 2328 chunks on corpus_version `20260822-eac47701064f`, all `retrievable=true`. Every chunk carries an embedding vector under the `text-embedding-3-small` model (recorded in the DVC-tracked manifest). The embedding model identifier is pinned there and must be read at retrieval time to guarantee query/corpus vector compatibility. The corpus is a static, manually-triggered snapshot (no live Wikipedia updates at query time), consistent with BDU1's framing.

**Non-Goals**: This feature does not score retrieved chunks for relevance (MOD2); does not trigger or implement the web-search fallback (MOD3); does not generate answers (MOD4); does not sanitize queries before an external call (MOD5 — that is a different data path, for fallback queries only); does not build or curate the held-out evaluation set (EVAL1); does not implement query rewriting, HyDE, or hybrid (sparse+dense) retrieval — explicitly deferred to a later epic per the Non-Goals in `epic.md`.

## User Scenarios & Testing

### User Story 1 — Query retrieves relevant chunks from the corpus (Priority: P1)

A user issues a natural-language query about space exploration. The retriever must return the top-k Document Chunks whose content is semantically closest to the query, so MOD2's evaluator has something to score.

**Why this priority**: This is the walking skeleton's next step after DP1/DP2. Every subsequent Modeling and Evaluation feature (MOD2 onward) is blocked until retrieval works end-to-end.

**Independent Test**: Issue an in-corpus query (e.g. "What were the goals of the Apollo 11 mission?") against the live Qdrant index and confirm the response contains k non-empty Document Chunks — at least one of which originates from a relevant source article (e.g. `source_document_id` contains "Apollo 11").

**Acceptance Scenarios**:

1. **Given** a query about a topic covered in the corpus (e.g. Apollo 11), **When** the retriever runs, **Then** it returns exactly k Document Chunks, each with a non-null `chunk_id`, `text`, `source_document_id`, `corpus_version`, and a raw cosine similarity score, ordered descending by score.
2. **Given** any query, **When** the retriever runs, **Then** every returned chunk has `retrievable=true` — no unpublished or PII-unscanned chunk ever appears in the result.
3. **Given** a query about a topic not covered in the corpus (e.g. deep-sea oceanography), **When** the retriever runs, **Then** it still returns k chunks, but their cosine similarity scores are noticeably lower than for an in-corpus query — the retriever does not filter by score, it returns the top-k regardless (score-based action is MOD2's job).

---

### User Story 2 — Retrieval cost and token usage are observable (Priority: P1)

Every call to an LLM API must emit token usage and cost, per Principle VI. The query embedding is such a call.

**Why this priority**: Constitutional requirement — Principle VI mandates per-call token/cost logging for any LLM API call from the first deployment.

**Independent Test**: Run a retrieval call with a mock-instrumented embedding client and confirm a structured log line is emitted containing `tokens_used` and `estimated_cost_usd` for the query embedding call.

**Acceptance Scenarios**:

1. **Given** a retrieval call is made, **When** the embedding API returns, **Then** a structured log line is emitted with at least: `feature=mod1`, `tokens_used=<int>`, `estimated_cost_usd=<float>`, `corpus_version=<str>`.

---

### Edge Cases

- What if the query embedding call fails or times out? Must raise clearly with the failed query identified; must not return a partial or empty result silently.
- What if the Qdrant search returns fewer than k results (corpus smaller than k)? Return however many exist — do not error; log the actual count.
- What if the query text is empty or whitespace-only? Must reject before embedding — raise a validation error, not a downstream API error.
- What if the embedding model identifier recorded in the corpus manifest differs from the one used at query time (e.g. a future model pin change)? Must detect and raise — embedding-model mismatch makes cosine similarity meaningless, and silent mismatch is the risk DP1's manifest pin was designed to prevent.
- What if Qdrant is unreachable at retrieval time? Must surface the connectivity error immediately; must not retry indefinitely.

## Requirements

### Functional Requirements

- **FR-001**: The system MUST embed the user query using the same embedding model and version pinned for the corpus (`text-embedding-3-small`, per DP1's DVC-tracked manifest for the active `corpus_version`) — it MUST read the pinned model identifier from the manifest rather than hardcoding it.
- **FR-002**: The system MUST query the Qdrant `document_chunks` collection filtered to `retrievable=true` and the active `corpus_version`, returning the top-k chunks by cosine similarity to the query vector.
- **FR-003**: The system MUST return each retrieved chunk's `chunk_id`, `text`, `source_document_id`, `corpus_version`, and raw cosine similarity score, ordered descending by score.
- **FR-004**: The system MUST never return a chunk with `retrievable=false` — the filter is non-negotiable and must be applied at the Qdrant query level, not as a post-filter in application code.
- **FR-005**: The system MUST log a structured line per retrieval call with at least `tokens_used` and `estimated_cost_usd` for the query embedding, per Principle VI.
- **FR-006**: The system MUST raise a validation error (before any API call) when the query is empty or whitespace-only.
- **FR-007**: The system MUST raise immediately if the embedding model identifier read from the active corpus manifest does not match the model used for the query embedding call.
- **FR-008**: k MUST be a runtime-configurable parameter with a default value of 5.
- **FR-009**: The system MUST surface a clear error if Qdrant is unreachable, with no silent fallback to an empty result set.

### Key Entities

- **Document Chunk**: see `.spec/01-corrective-rag/shared-data-model.md` — this feature is a reader only; it does not write any chunk fields. The filter `retrievable=true` and `corpus_version=<active>` are applied at query time.
- **Retrieval Decision Record**: see `.spec/01-corrective-rag/shared-data-model.md` — MOD1 initializes this record for each query, setting `decision_id`, `query`, `retrieved_chunk_ids`, and `relevance_scores` (the raw cosine similarity scores, one per retrieved chunk in the same order as `retrieved_chunk_ids`). The record is returned as part of MOD1's result struct; its persistence to a store is the orchestrating pipeline's responsibility (DEPLOY1), not MOD1's.

## Risk Assessment

| Failure Mode | Likelihood | Severity | Mitigation |
|---|---|---|---|
| Query and corpus embeddings are produced by different model versions, making cosine similarity scores arbitrary | Low | High | FR-001/FR-007: read the pinned model identifier from the corpus manifest at runtime; raise immediately on mismatch rather than returning meaningless scores to MOD2 |
| Retriever returns chunks with `retrievable=false` (PII-unscanned or quarantined), exposing them to MOD2/MOD4 | Low | High | FR-004: the `retrievable=true` filter is applied at the Qdrant query level — application-level post-filtering is insufficient and must not be used as the sole gate |
| k is set too small for MOD2's evaluator to distinguish "mostly relevant" from "fully irrelevant" retrieval | Medium | Medium | FR-008: k is runtime-configurable; resolved to a concrete default after MOD2's spec clarifies its minimum-input requirement |
| k is set too large, flooding MOD2 with low-similarity noise chunks and biasing its confidence classification | Medium | Medium | Same mitigation — k is configurable and calibrated against MOD2's evaluation during EVAL2 |
| Empty or near-empty corpus (e.g. future re-ingestion under a new corpus_version with fewer cleared chunks) causes retrieval to silently return fewer than k results | Low | Low | FR-002/FR-009: return however many exist (don't error), log the actual count; caller sees count and can handle it |

## Success Criteria

### Business KPIs

- **SC-001**: Given an in-corpus query (e.g. "What were the goals of the Apollo 11 mission?"), at least one of the top-k returned chunks has a `source_document_id` corresponding to a relevantly-titled article — verified by manual inspection of the smoke-test run.
- **SC-002**: Zero returned chunks across any retrieval call have `retrievable=false` — verified by asserting the filter is applied at the Qdrant query level in the integration test.

### Model/ML Metrics

- **SC-003**: The top-1 cosine similarity score for a representative in-corpus query meets or exceeds 0.55 — used as a sanity-check threshold, not a tuned production gate. Revised from an initial 0.70 during MOD1's Implement sub-stage after live measurement against the real corpus: `text-embedding-3-small` scores natural-language *question*-vs-*prose-passage* pairs meaningfully below verbatim-text similarity — 20 representative in-corpus queries against the live corpus scored 0.616–0.743 (median 0.694), the canonical query itself ("What were the goals of the Apollo 11 mission?") scored 0.589, and a deliberately out-of-corpus control query ("What is the deepest part of the ocean and what lives there?") scored 0.342 — a wide, clean separation that validates the retriever's discriminative power (Acceptance Scenario 3). 0.55 sits safely above that out-of-corpus floor with a large margin while still covering the measured in-corpus range. A score below this on an obviously in-topic query indicates the embedding model mismatch mitigation (FR-007) was bypassed or the corpus is severely misaligned.
- **SC-004**: P95 end-to-end retrieval latency (embed query + Qdrant search) is under 3 seconds for k=5 against the 2328-chunk corpus — measured in the integration test. This is a demo-scale baseline, not a production SLO; DEPLOY1 will establish the production target.

## Assumptions

- The active `corpus_version` is `20260822-eac47701064f` (the DP2-cleared snapshot) for all development and evaluation work through MOD4/EVAL2. MOD1 must accept `corpus_version` as a runtime parameter so future re-ingestion runs can be targeted without a code change.
- MOD1 is a pure retrieval function — it returns a result struct and does not itself persist the Retrieval Decision Record to any store. The record's lifecycle (creation, threading through MOD2/MOD3/MOD4, final persistence) is the orchestrating pipeline's responsibility, to be implemented in DEPLOY1. MOD1's job is to initialize the record's required fields (`decision_id`, `query`, `retrieved_chunk_ids`) and return them as part of its result struct.
- The shared `openai_client.py` wrapper built in DP1 (which handles per-call token/cost logging) is reused here for the query embedding call — MOD1 does not implement its own LLM client.
- The Qdrant collection schema, connection parameters, and `document_chunks` collection name are established by DP1 and are not re-specified here; MOD1 reads from the existing collection.
- k=5 is the proposed default (FR-008), pending confirmation from the MOD2 spec that 5 chunks is a sufficient input for the relevance evaluator's classification logic. This is the only open question that affects MOD1's interface contract with MOD2.
