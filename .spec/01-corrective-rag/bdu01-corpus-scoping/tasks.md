# Tasks: Corpus & Use-Case Scoping

**Input**: `.spec/01-corrective-rag/bdu01-corpus-scoping/spec.md`, `plan.md`
**Prerequisites**: `plan.md` (no Evaluation Gate — confirmed non-ML)

This feature produces no source code — every Functional Requirement is already resolved as text in `spec.md`. Tasks here verify those resolutions are complete and correctly consumed by the features that depend on them; there is no Setup, Foundational, Data Preparation, Modeling, Evaluation, or Deployment phase because none of that infrastructure exists for a scoping deliverable.

## Phase 1: Setup

*None — no environment, dependency, or project scaffolding is needed to verify text already committed in `spec.md`.*

## Phase 2: Foundational

*None — there is no shared infrastructure this feature must stand up before its user stories can be checked.*

## Phase 3: User Story 1 - Team scopes a concrete, buildable target (Priority: P1)

**Goal**: Confirm the scoping deliverable (corpus, relevance definition, fallback-provider status, PII expectation) is complete and that DP1 already builds against it without needing further clarification.

**Independent Test**: Inspect `.spec/01-corrective-rag/dp01-document-ingestion/spec.md` and confirm it references a concrete corpus source with zero `[NEEDS CLARIFICATION]` markers about corpus identity.

- [X] T001 Verify `spec.md` FR-001 names a concrete corpus — source system (Wikipedia public REST API), format, and approximate volume (~20-30 articles) — with no open question left for DP1. **Confirmed**: FR-001 states this exactly.
- [X] T002 Verify `spec.md` FR-003 states a concrete, checkable relevance definition (what makes a retrieved chunk "relevant" vs. "irrelevant" for this corpus) usable unmodified as a future EVAL1 labeling guideline. **Confirmed**: FR-003 gives a full relevant/irrelevant definition (topic match, question match, staleness) with no open wording left.
- [X] T003 Verify `spec.md` FR-004 (fallback-provider decision explicitly deferred to MOD3) and FR-005 (PII expectation: none expected in this public corpus, but DP2 still runs as a mandatory safety net) are both stated without ambiguity. **Confirmed**: both FRs record an explicit "Resolved:" outcome, no open question.
- [X] T004 Verify `.spec/01-corrective-rag/dp01-document-ingestion/spec.md` contains zero `[NEEDS CLARIFICATION]` markers related to corpus identity, format, or volume, and explicitly cites this feature's resolution as its source. **Confirmed**: `grep -c "NEEDS CLARIFICATION"` on DP1's spec.md returns 0; DP1 cites BDU1 by path in its Data Availability & Quality section and 6 other places.

**Checkpoint**: US1 independently verified — the scoping deliverable is complete and DP1 already consumes it cleanly.

## Phase 4: User Story 2 - Demo user's query needs are represented (Priority: P2)

**Goal**: Confirm a representative query set is documented and ready for a future EVAL1 to consume unmodified.

**Independent Test**: Inspect `spec.md` and confirm at least 3 representative example queries are documented, covering both an in-topic case and a fallback-triggering case.

- [X] T005 Verify `spec.md`'s User Story 2 documents at least 3 representative example queries spanning in-topic (Apollo 11 mission goals), time-sensitive/fallback-triggering (current SpaceX CEO), and off-topic (capital of France) cases. **Confirmed**: all 3 present verbatim in User Story 2's Acceptance Scenarios and cross-referenced in FR-002.

**Checkpoint**: US2 independently verified — the query set is ready for EVAL1 to consume once it is specified.

## Final Phase: Polish

- [X] T006 Cross-check `spec.md`'s Success Criteria SC-001 against the epic's current state: confirm DP1 (Specified, zero corpus-related `[NEEDS CLARIFICATION]`) satisfies its half of SC-001 now; record that the MOD1-MOD4/EVAL1 half remains open until those features are specified in a future `sdd-backlog` run — not a blocker for this feature's own completion, since BDU1's own deliverable is already resolved. **Recorded**: DP1's share of SC-001 is met today (T004); MOD1-MOD4/EVAL1's share is Deferred, tracked against `epic.md`'s existing backlog rows rather than re-opened here.

## Dependencies & Execution Order

- Phase 3 (US1) and Phase 4 (US2) both read only `spec.md` and, for T004, `dp01-document-ingestion/spec.md` — no phase depends on another completing first; both could run in any order.
- T006 (Polish) depends on T001-T005 having been checked, since it cross-references their results into a single Success Criteria status note.

## Parallel Example

```text
# T001-T003 and T005 all read different sections of the same static spec.md and have no
# write side effects — they can be verified together in a single pass rather than sequentially:
T001, T002, T003, T005
```

## Implementation Strategy

**MVP = the whole feature**: since every requirement is already resolved as committed text and DP1 already builds against it, there is no incremental subset to ship — completing Phase 3 and Phase 4's verification (T001-T005) and recording the Polish cross-check (T006) closes this feature out entirely.
