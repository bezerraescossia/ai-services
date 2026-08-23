# Implementation Plan: Corpus & Use-Case Scoping

**Branch**: `bdu01-corpus-scoping` | **Date**: 2026-08-22 | **Spec**: .spec/01-corrective-rag/bdu01-corpus-scoping/spec.md

## Summary

This feature is a scoping/decision deliverable, not a piece of software: it names the corpus (Wikipedia articles on space exploration), a representative query set, a checkable relevance definition, and the fallback-provider/PII expectations that DP1 onward build against. Per `spec.md`'s own Non-Goals ("not a model itself"), every Functional Requirement is already resolved as text inside `spec.md` — DP1 already references those resolutions directly with zero `[NEEDS CLARIFICATION]` markers. There is no code, pipeline, or model for this plan to design; "implementation" here means verifying those resolutions are complete, consistent, and actually consumable by the downstream features that depend on them (DP1, confirmed; MOD2/EVAL1, pending their own future specs).

## Technical Context

**Language/Version**: N/A — no source code is produced by this feature.
**Primary Dependencies**: N/A
**Data Sources & Pipeline**: N/A — this feature *names* the data source (Wikipedia's public REST API) for DP1 to ingest; it does not itself fetch, store, or pipeline anything.
**Feature Engineering**: N/A
**Model Architecture Candidates**: N/A
**Training Infra/Compute**: N/A
**Experiment Tracking Tool**: N/A — no run to log.
**Evaluation Protocol**: N/A — see Evaluation Gate section below (omitted; confirmed non-ML).
**Storage**: N/A
**Testing**: N/A — no application code to test under Principle IV; verification here means checking the resolved text against downstream artifacts, not running a test suite.
**Deployment Target**: N/A
**Monitoring & Retraining Triggers**: N/A
**Target Platform**: N/A
**Project Type**: N/A — documentation/decision deliverable only.
**Performance Goals**: N/A
**Constraints**: N/A
**Scale/Scope**: Scope is fixed by the spec itself — a single scoping decision covering corpus, query set, relevance definition, fallback-provider status, and PII expectation. Nothing left open at this feature's level (all resolved in Clarifications).

## Constitution Check

*Gate: must pass before detailing the project structure below.*

| Principle (.spec/constitution.md) | Assessment | Note |
|---|---|---|
| I. Reproducibility First | Pass (N/A) | No stochastic process, dataset, or environment created by this feature — DP1 owns DVC versioning of the actual corpus. |
| II. Experiment Tracking Is Mandatory | Pass (N/A) | No run to log — this feature produces no model or prompt output. |
| III. Evaluation Before Shipping | Pass (N/A) | Nothing ships from this feature; EVAL1/EVAL2 own the held-out evaluation gate for the pipeline this feature scopes. |
| IV. Test-First Development | Pass (N/A) | No application code is written by this feature. |
| V. Service Independence with a Shared Core | Pass (N/A) | No service is created here. |
| VI. Observability by Default | Pass (N/A) | No running component to observe. |
| VII. No Secrets or PII in Code, Logs, or Prompts | Pass | Spec's FR-005 already states the PII expectation (none expected in this public corpus) that sizes DP2's safety-net scan; nothing here handles secrets or PII directly. |
| Model Risk & Responsible AI | Pass (N/A) | No model prediction served by this feature. |
| Data Governance & Privacy (LGPD) | Pass | FR-005 documents the PII expectation for the named corpus, which DP2 treats as binding input to its own scope. |
| Model & Prompt Versioning | Pass (N/A) | No model or prompt version introduced. |

No violations — Complexity Tracking is not needed.

## Evaluation Gate

*Omitted — confirmed non-ML feature. `spec.md` states explicitly under Non-Goals and ML Objective that this feature "does not build or evaluate any model"; its Success Criteria (SC-001, SC-002) are downstream-consumability checks, not model metrics, and are verified directly in Tasks below instead of via a held-out evaluation run.*

## Project Structure

### Documentation (this feature)

```text
.spec/01-corrective-rag/bdu01-corpus-scoping/
├── plan.md              # this file
├── spec.md              # the resolved scoping deliverable itself — doubles as the feature's output
├── requirements.md       # quality checklist, all items pass
└── tasks.md              # generated next — verification tasks only, no build tasks
```

No `research.md` (zero remaining `NEEDS CLARIFICATION`), no `data-preparation.md`/`data-model.md` (Key Entities are references to the shared model, not new entities owned here), no contract file (no interface exposed), no `quickstart.md` (nothing runnable to walk through).

### Source Code (repository root)

N/A — this feature adds no files under `src/`. The repository's `src/` layout convention (one directory per initiative, per the root `README.md`) is established by the first feature in this epic that actually produces code (DP1), not by this scoping feature.

**Structure Decision**: No source tree changes. This feature's sole artifact is the resolved decision text already committed in `spec.md`; Tasks below verify that text is complete and correctly consumed by DP1, and check the box on the two future-facing consumability claims (MOD2's relevance definition, EVAL1's query set) that can only be fully confirmed once those features are specified.

## Complexity Tracking

*Not applicable — no Constitution Check violation was recorded.*
