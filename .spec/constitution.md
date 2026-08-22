# AI Services Constitution

## Core Principles

### I. Reproducibility First
Every service MUST pin its runtime environment via a dependency lockfile (e.g. `uv.lock`, `poetry.lock`, or a hash-pinned `requirements.txt`) — no unpinned installs in a committed environment. Any stochastic process (training, sampling, evaluation) MUST fix and log its random seed. Datasets used for training or evaluation MUST be versioned with DVC; no model or eval result may reference an unversioned dataset.

**Rationale**: Without pinned environments, fixed seeds, and versioned data, a reported result cannot be reproduced or audited later — this is the baseline for everything else in this document being enforceable.

### II. Experiment Tracking Is Mandatory
Every training run, fine-tune, or prompt-evaluation run MUST be logged to MLflow, capturing hyperparameters, metrics, produced artifacts, and the data version/lineage used. Runs not logged to MLflow MUST NOT be cited as the basis for a shipping decision.

### III. Evaluation Before Shipping
No model or prompt change may ship to production without being scored against a fixed, held-out evaluation set. The eval set MUST NOT overlap with data used for training or prompt iteration. Eval results MUST be logged (Principle II) and referenced in the change that ships them.

### IV. Test-First Development (TDD)
For all application code (service logic, APIs, data pipelines — distinct from model evaluation, governed by Principle III), tests MUST be written before implementation and MUST fail first. No implementation code is merged without a preceding failing test that it makes pass.

### V. Service Independence with a Shared Core
Each service in this repository MUST be independently deployable: services MUST NOT share a runtime process, a live database, or in-memory state with one another, and MUST communicate only through defined APIs or queues. Logic common to multiple services (e.g. LLM client wrappers, the eval harness, MLflow logging helpers) MUST be extracted into a shared internal library and imported at build time, not duplicated per service or coupled at runtime.

### VI. Observability by Default
Every service MUST emit structured logs and basic metrics (latency, error rate) from its first deployment. Services that call an LLM MUST additionally track token usage and cost per call. Observability is not deferred to a later milestone.

### VII. No Secrets or PII in Code, Logs, or Prompts
API keys and credentials MUST NOT appear in source control or logs. Personally identifiable information MUST NOT appear in logs or be sent to third-party LLM providers without an explicit, documented exception. Any exception must be justified in the feature spec that requires it.

## Model Risk & Responsible AI

Low-confidence model predictions MUST route to a human-in-the-loop fallback path rather than auto-acting on an uncertain result; each service that serves predictions MUST define its confidence threshold and fallback behavior explicitly. A fairness/bias review MUST be completed and recorded before any model ships to production for the first time, and repeated on any material retraining.

## Data Governance & Privacy

Personal data handled by any service is subject to LGPD (Lei Geral de Proteção de Dados, Brazil). Pipelines that touch personal data MUST document: what is collected, the legal basis, retention period, and how a data-subject deletion/access request is fulfilled. This governance requirement composes with Principle VII (no PII in logs/prompts) rather than replacing it.

## Model & Prompt Versioning

Every model and prompt MUST be versioned (e.g. via the MLflow model registry or an equivalent tagged registry for prompts). A new model or prompt version MUST run in shadow mode (receiving production traffic in parallel, without serving its output to users) before full rollout, and MUST have a documented, tested rollback path to the prior version before shadow mode begins.

## Development Workflow

- No PR merges without passing tests (Principle IV) and, where applicable, a passing evaluation gate (Principle III).
- A spec/plan review MUST check the proposed feature against every principle in this document; any conflict is either resolved before implementation or explicitly justified in the feature's plan as a documented exception.
- Shadow deployment and rollback verification (see Model & Prompt Versioning) are required workflow steps before a model/prompt reaches full production traffic, not optional hardening done after the fact.

## Governance

This constitution supersedes ad hoc practice for every service in this repository. Amendments require the author to state the change, its rationale, and the resulting semantic version bump (MAJOR for removal/redefinition of a principle, MINOR for a new principle or material expansion, PATCH for clarification) in a Sync Impact Report prepended to this file. `sdd-backlog` and `sdd-implement` MUST check new epics, features, plans, and tasks against these principles and flag conflicts before proceeding.

**Version**: 1.0.0 | **Ratified**: 2026-08-22 | **Last Amended**: 2026-08-22
