# Feature Specification: Corpus & Use-Case Scoping

**Feature Branch**: `bdu01-corpus-scoping`
**Created**: 2026-08-22
**Status**: Clarified
**Epic**: .spec/01-corrective-rag/epic.md — Feature BDU1
**Input**: User description: "corrective rag"

## Clarifications

### Session 2026-08-22

- Q: What document corpus will the Corrective RAG system serve? → A: This is a demo repo — use publicly fetchable example docs over HTTP. Resolved as: Wikipedia articles, fetched via Wikipedia's public REST API (no auth required), matching the corpus used by the original RAG paper and by CRAG's own evaluation setup.
- Q: Which fallback web-search provider should MOD3 call when retrieval confidence is low? → A: Not decided yet — explicitly deferred to MOD3's own spec, which will pick a concrete provider without blocking this feature.

To make the demo concretely buildable, this feature also fixes a narrow topic rather than "all of Wikipedia": a curated set of ~20-30 articles about **space exploration** (e.g. Apollo program, Mars rovers, the ISS, Voyager program). This gives the demo a clean way to show both paths — an in-topic query the evaluator should pass, and an out-of-topic or time-sensitive query that should trigger MOD3's fallback.

## Business & Data Understanding

**Business Objective**: The epic was scoped generically ("corrective rag") with no named corpus, query population, or fallback provider. Every downstream feature (ingestion, retrieval, the relevance evaluator, the eval harness) needs a concrete target to build against instead of an assumed one — building against an assumed corpus risks a system nobody can actually use.

**ML Objective**: Not a model itself — this feature is the requirements/scoping deliverable that parameterizes every downstream ML component with a concrete document corpus, a representative query set, and a checkable definition of "relevant" vs. "irrelevant" retrieval that MOD2's evaluator and EVAL1's labels will both use unmodified.

**Data Availability & Quality**: This is a demo repository, so the corpus is Wikipedia articles fetched over HTTP via Wikipedia's public REST API — freely available, no authentication, well-documented format (article HTML/plain-text extract). Scope is fixed to ~20-30 articles about space exploration; DP1 finalizes the exact article list at ingestion time. Content is current as of fetch time; Wikipedia articles are continuously edited, so DP1's DVC snapshot is the authoritative version for reproducibility (Principle I), not "live Wikipedia" at query time.

**Non-Goals**: This feature does not build or evaluate any model; it does not ingest or index documents (DP1's job); it does not implement the fallback web-search call (MOD3's job) beyond noting that provider selection is explicitly deferred to MOD3's own spec.

## User Scenarios & Testing

### User Story 1 - Team scopes a concrete, buildable target (Priority: P1)

The team building Corrective RAG needs a documented, agreed corpus and relevance definition before any ingestion or modeling work starts, so later features aren't built on silently assumed data that turns out not to exist or not to match real usage.

**Why this priority**: Every other feature in this epic (DP1 onward) depends on this scoping being resolved — without it, ingestion and modeling would proceed on the placeholder assumptions already flagged in `epic.md`.

**Independent Test**: Can be tested by checking that DP1's own spec can be written referencing a concrete corpus source, with no `[NEEDS CLARIFICATION]` marker about "what corpus."

**Acceptance Scenarios**:

1. **Given** no corpus had been named yet, **When** this scoping feature is completed, **Then** a specific document source (Wikipedia articles via HTTP), format, and approximate volume are documented and available to DP1.
2. **Given** the relevance evaluator (MOD2) needs a checkable definition of "relevant," **When** this scoping feature is completed, **Then** a concrete relevance definition is documented that EVAL1 can use unmodified as its labeling guideline.

---

### User Story 2 - Demo user's query needs are represented (Priority: P2)

Anyone trying the deployed CRAG demo will ask both in-topic questions (answerable from the space-exploration corpus) and questions the corpus can't answer (off-topic or too recent for the DVC-pinned snapshot) — both patterns need to be captured now, so the retriever and evaluator are tuned against realistic usage rather than only the easy case.

**Why this priority**: Materially shapes MOD1/MOD2's design, but the walking skeleton can proceed with this first-pass query set and refine later — unlike User Story 1, it isn't a hard blocker.

**Independent Test**: Can be tested by checking that at least 3 representative example queries, covering both the in-topic and fallback-triggering case, are documented.

**Acceptance Scenarios**:

1. **Given** the resolved space-exploration corpus, **When** this scoping feature is completed, **Then** at least 3 representative example queries are documented for use by EVAL1, covering both the in-topic and fallback-triggering case:
   - "What was the goal of the Apollo 11 mission?" — in-topic, should retrieve relevant chunks with no fallback needed.
   - "Who is the current CEO of SpaceX?" — time-sensitive; likely under-covered by the static DVC-pinned snapshot, a good candidate to trigger low-confidence fallback.
   - "What is the capital of France?" — off-topic relative to the corpus; the evaluator should score retrieval as irrelevant and MOD3's fallback should fire.

---

### Edge Cases

- What happens if the named corpus turns out to be too small or too narrow to support a meaningful held-out eval set (EVAL1)? Flagged here as a feasibility risk, not resolved by this feature — EVAL1's own spec must re-check corpus size against its labeling needs.
- How is a corpus that changes shape between scoping and DP1's ingestion handled? Out of scope for this feature; DP1 versions whatever exists at ingestion time via DVC.

## Requirements

### Functional Requirements

- **FR-001**: The scoping deliverable MUST identify a concrete document corpus — source system, format, and approximate volume — that DP1 can ingest without further clarification. Resolved: Wikipedia articles fetched via Wikipedia's public REST API, demo-scale volume.
- **FR-002**: The scoping deliverable MUST define at least 3 representative example queries drawn from the resolved use case. Resolved: see User Story 2's three example queries (Apollo 11, SpaceX CEO, capital of France).
- **FR-003**: The scoping deliverable MUST state a concrete, checkable definition of "relevant" vs. "irrelevant" retrieval for this use case, usable unmodified as EVAL1's labeling guideline. Resolved: a retrieved chunk is **relevant** if it contains information that directly answers, or is necessary supporting context to answer, the query about a space-exploration topic covered by the corpus. It is **irrelevant** if it comes from an unrelated topic, answers a different question than the one asked (even while sharing surface keywords), or is a stale/superseded fact the static DVC snapshot can no longer vouch for (e.g. a "current" role or status).
- **FR-004**: The scoping deliverable MUST explicitly record the fallback-provider decision status for MOD3. Resolved: not decided at this stage — MOD3's own spec selects a concrete web-search provider (e.g. a public search API) without this decision blocking BDU1, DP1, or MOD1/MOD2.
- **FR-005**: The scoping deliverable MUST state whether the named corpus is expected to contain personal or regulated data, so DP2's PII-scrubbing scope can be sized correctly. Resolved: Wikipedia articles are public encyclopedic content about notable topics, not expected to contain personal data in the LGPD sense — but DP2 still runs as a mandatory safety-net scan per the constitution, since article text may incidentally reference identifiable individuals.

### Key Entities

- **Document Chunk**: see .spec/01-corrective-rag/shared-data-model.md — this feature determines the corpus that DP1 will chunk from, but does not itself produce chunks.
- **Query Example**: a representative anticipated user query, local to this feature; consumed by EVAL1 when building held-out examples. Not a shared entity — it's a scoping artifact, not a runtime object.

## Risk Assessment

| Failure Mode | Likelihood | Severity | Mitigation |
|---|---|---|---|
| Scoping proceeds on an assumed corpus/use case that doesn't match real demand, and downstream features are built against the wrong target | Medium | High | Resolve corpus and use case directly with the requester via this feature's Clarify pass before DP1 starts |
| Named corpus turns out to contain regulated personal data that wasn't anticipated, forcing rework of DP2's scope after ingestion has already started | Medium | Medium | FR-005 requires an explicit PII expectation to be stated now, before DP1/DP2 are specified |

## Success Criteria

### Business KPIs

- **SC-001**: DP1, MOD1-MOD4, and EVAL1 can each be specified without a `[NEEDS CLARIFICATION]` marker related to corpus identity, query population, or fallback provider.

### Model/ML Metrics

- **SC-002**: The relevance definition produced by this feature (FR-003) is adopted unmodified as EVAL1's labeling guideline — no redefinition needed once the held-out set is built.

## Assumptions

- No stakeholder beyond the requester of this epic has been identified yet; this feature's Clarify pass treats the requester's answers as authoritative for corpus, query population, and fallback provider decisions.
- The resolved corpus is assumed to be text-based documents (not audio/video/image), matching the CRAG paper's scope and this epic's Non-Goals.
- "Space exploration" was chosen as the fixed demo topic because it cleanly supports both the in-topic and fallback-triggering example queries (User Story 2) needed to demonstrate CRAG's core mechanism; DP1 may adjust the exact article list within this topic without needing to re-run this scoping feature.
