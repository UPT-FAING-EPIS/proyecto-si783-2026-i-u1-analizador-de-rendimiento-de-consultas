# AGENTS.md — Query Performance Analyzer

Fast-track guidance for OpenCode and agentic coding operations.

---

## Quick Start

**Use `uv` exclusively** (not pip). All development through `uv run`:
```bash
uv sync              # Install dependencies + dev tools
uv run query_analyzer  # Run CLI app
python -m query_analyzer  # Alternative entry point
```

---

## Build, Lint & Test Commands

### Linting & Formatting (pre-commit order: ruff → mypy)
```bash
uv run ruff check --fix    # Auto-fix linting issues
uv run ruff format         # Format code (line-length=100)
uv run mypy query_analyzer # Type check (disallow_untyped_defs=false OK)
```

### Unit Tests (no Docker needed)
```bash
uv run pytest tests/unit/                    # All unit tests
uv run pytest tests/unit/test_registry.py   # Single file
uv run pytest tests/unit/test_registry.py::test_register_adapter  # Single test
uv run pytest -k "test_register" -v         # Tests matching pattern
```

### Integration Tests (requires Docker)
```bash
make up              # Start services (PostgreSQL, MySQL, MongoDB, Redis, etc.)
make health          # Verify services ready (wait ~30s)
uv run pytest tests/integration/                          # All integration tests
uv run pytest tests/integration/test_postgresql_integration.py  # Engine-specific
uv run pytest tests/integration/ -k "test_explain" -v    # Pattern-based filtering
make down            # Stop services (keep volumes)
make reset           # Destroy containers + volumes (clean slate)
```

### Test Coverage
```bash
uv run pytest --cov=query_analyzer --cov-report=term-missing
uv run pytest --cov=query_analyzer --cov-report=html  # Open htmlcov/index.html
```

---

## Code Style Guidelines

### Imports
- Sort: standard library → third-party → local (ruff enforces via `-I` flag)
- Avoid circular imports; use TYPE_CHECKING for type hints
```python
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .models import ConnectionConfig
```

### Formatting
- **Line length:** 100 characters (ruff format enforces)
- **Docstring style:** Google format (pydocstyle convention)
- Indentation: 4 spaces (no tabs)

### Type Hints
- Use type hints on all function signatures (disallow_incomplete_defs=true)
- `disallow_untyped_defs=false` is intentional (type coverage ~70%, strictened post-v1)
- Return types always required; use `None` explicitly
- Tests excluded from mypy checks (no type hints needed in tests/)

```python
def execute_explain(self, query: str) -> QueryAnalysisReport:
    """Analyze query and return report."""
```

### Naming Conventions
- **Classes:** PascalCase (e.g., `PostgreSQLAdapter`, `ConnectionConfig`)
- **Functions/methods:** snake_case (e.g., `execute_explain`, `validate_config`)
- **Constants:** UPPER_SNAKE_CASE (e.g., `DEFAULT_PORT`, `MAX_RETRIES`)
- **Private:** leading underscore (e.g., `_config`, `_connection`)
- **Boolean methods:** prefix with `is_` or `has_` (e.g., `is_connected`, `has_errors`)

### Error Handling
All custom exceptions inherit from module-level base class:
```python
# config/exceptions.py
class ConfigError(Exception):
    """Base for all config errors."""

class ConfigValidationError(ConfigError):
    """Configuration content is invalid."""

# adapters/exceptions.py
class AdapterError(Exception):
    """Base for all adapter errors."""

class ConnectionError(AdapterError):
    """Failed to connect to database."""
```

Raise with context for debugging:
```python
try:
    adapter.connect()
except ConnectionError as e:
    raise QueryAnalysisError(f"Connection failed: {e}") from e
```

### Docstrings (Google Style)
```python
def analyze_query(query: str, config: ConnectionConfig) -> QueryAnalysisReport:
    """Analyze SQL query performance.

    Args:
        query: SQL query string
        config: Database connection config

    Returns:
        Report with metrics and recommendations

    Raises:
        QueryAnalysisError: If query execution fails
    """
```

---

## Architecture Essentials

**Adapter Pattern:** Pluggable drivers via `AdapterRegistry`:
```python
@AdapterRegistry.register("postgresql")
class PostgreSQLAdapter(BaseAdapter):
    def execute_explain(self, query: str) -> QueryAnalysisReport: ...
```

Create instances: `adapter = AdapterRegistry.create("postgresql", config)`

**Core modules:**
- `adapters/base.py` — abstract interface (connect, disconnect, execute_explain)
- `adapters/registry.py` — factory pattern
- `adapters/sql/*` — PostgreSQL, MySQL, SQLite, CockroachDB, YugabyteDB
- `config/*` — connection profiles, encryption
- `core/*` — anti-pattern detection, recommendations (engine-agnostic)
- `cli/*` — CLI entry point (typer-based)

---

## Pre-Commit Hooks (Auto-Run on Commit)

Install once: `uv run pre-commit install`

Hooks run in order:
1. **ruff** (`--fix`) — Auto-fixes; re-add modified files
2. **ruff-format** — Formatting
3. **mypy** — Type checking (fails if errors remain; fix and retry)
4. **pre-commit-hooks** — Trailing whitespace, merge conflicts, large files

If commit fails: ruff auto-modifies files (re-add), mypy rejects on type errors (fix manually), retry commit.

---

## Key Quirks

| Item | Detail |
|------|--------|
| **MyPy strictness** | `disallow_untyped_defs=false` intentional (post-v1 tightening) |
| **E501 ignored** | ruff formatter handles line-length, not linter |
| **Adapter registry** | Tests auto-register PostgreSQL via `ensure_postgresql_registered()` fixture |
| **No pytest.ini** | Config in `[tool.pytest]` section of pyproject.toml |

---

## Git Policy (CRITICAL)

❌ **NEVER** `git add` or `git commit` without explicit user request
✅ **OK** to explore: `git status`, `git log`, `git diff`, `git branch`
❌ **NEVER** force push, rebase -i, or destructive operations

Commit message format (when authorized): [Conventional Commits](https://www.conventionalcommits.org/)
- `feat:` New feature
- `fix:` Bug fix
- `docs:` Documentation
- `test:` Test changes
- `chore:` Administrative tasks

---

## Useful Commands

```bash
# Full workflow
uv sync && uv run ruff check --fix && uv run ruff format && uv run mypy query_analyzer
uv run pytest tests/unit/ -v
# Then: make up && make health && uv run pytest tests/integration/ && make down

# Cleanup
make reset                    # Remove containers & volumes
uv run pre-commit clean      # Clear hook cache
rm -rf htmlcov .coverage .pytest_cache
```

**No Cursor rules** (.cursor/rules/) or **GitHub Copilot instructions** found in this repo.
