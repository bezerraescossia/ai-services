# AI Services

Monolith of independently deployable ML/LLM services (starting with Corrective RAG)

## Structure

`src/` holds one directory per initiative/epic (e.g. `src/corrective-rag/`,
`src/recommendation-system/`) — see [`src/README.md`](src/README.md).

## Development

```bash
uv sync
uv run pre-commit install
```

## Common tasks

| Command | What it does |
| --- | --- |
| `uv run task test` | Run the test suite |
| `uv run task test-cov` | Run tests with coverage |
| `uv run task lint` | Lint with ruff |
| `uv run task format` | Format with ruff |
| `uv run task typecheck` | Type-check with mypy |
| `uv run task check` | Lint + typecheck + test |
| `uv run task precommit` | Run all pre-commit hooks on all files |
