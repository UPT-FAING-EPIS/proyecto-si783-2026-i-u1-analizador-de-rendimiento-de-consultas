# Contributing

Thanks for contributing to Query Analyzer.

This document is focused on contributors and maintainers. The end-user guide is in `README.md`.

## Development setup

Use `uv` for all local development tasks.

### Requirements

- Python 3.14+
- `uv`
- Docker + Docker Compose (only for integration tests)

### Install dependencies

```bash
uv sync
```

### Run the app locally

```bash
uv run query_analyzer
```

Alternative entry point:

```bash
python -m query_analyzer
```

## Code quality checks

Run checks in this order (same as pre-commit):

```bash
uv run ruff check --fix
uv run ruff format
uv run mypy query_analyzer
```

## Tests

### Unit tests

```bash
uv run pytest tests/unit/
```

Examples:

```bash
uv run pytest tests/unit/test_registry.py
uv run pytest tests/unit/test_registry.py::test_register_adapter
uv run pytest -k "test_register" -v
```

### Integration tests (Docker required)

```bash
make up
make health
uv run pytest tests/integration/
make down
```

Useful cleanup command:

```bash
make reset
```

## Pre-commit hooks

Install once:

```bash
uv run pre-commit install
```

Run manually on all files:

```bash
uv run pre-commit run --all-files
```

## Coding conventions

- Keep line length at 100 characters (`ruff format` enforces this).
- Add type hints on function signatures and explicit return types.
- Follow import ordering: stdlib, third-party, local.
- Use Google-style docstrings.
- Naming:
  - Classes: `PascalCase`
  - Functions/methods: `snake_case`
  - Constants: `UPPER_SNAKE_CASE`

## Project architecture

The project uses an adapter pattern through `AdapterRegistry`.

- Core adapter interface: `query_analyzer/adapters/base.py`
- Adapter factory/registry: `query_analyzer/adapters/registry.py`
- SQL adapters: `query_analyzer/adapters/sql/`
- NoSQL adapters: `query_analyzer/adapters/nosql/`
- Config models and handling: `query_analyzer/config/`
- Engine-agnostic analysis/recommendations: `query_analyzer/core/`

## Contribution workflow

1. Create a branch from `main`.
2. Make focused changes.
3. Run lint, format, type checks, and relevant tests.
4. Open a Pull Request with:
   - problem statement
   - implementation summary
   - test evidence

## Commit messages

Use Conventional Commits when possible:

- `feat:` new feature
- `fix:` bug fix
- `docs:` documentation
- `test:` test changes
- `chore:` maintenance

## Release notes for maintainers

Releases are automated by pushing tags that start with `v` and are handled by:

- `.github/workflows/release.yml`

Example:

```bash
git tag v0.1.0
git push origin v0.1.0
```

The workflow builds platform binaries and publishes package managers via JReleaser.
