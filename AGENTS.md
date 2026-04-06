# AGENTS.md — Query Performance Analyzer

Fast-track guidance for OpenCode and future agent sessions. Only includes facts that differ from Python/Linux defaults or would otherwise cause mistakes.

---

## Entry Points & Package Manager

**Use `uv` exclusively** — not pip. All workflows go through `uv run`.

```bash
# Sync environment (install deps + dev tools)
uv sync

# Run the app (TUI/CLI)
uv run query_analyzer

# Or equivalently
python -m query_analyzer
```

No direct Python execution; the project relies on uv's venv handling.

---

## Code Quality: Pre-commit Hooks & Linting

**Critical execution order:** ruff (auto-fixes files) runs *before* mypy (must pass after fixes).

- **Ruff** (lines 38–52 in pyproject.toml): line-length=100, select E/F/W/I/N/UP/B/D, ignores E501 (handled by formatter)
- **MyPy** (lines 61–76): `disallow_incomplete_defs = true`, **but `disallow_untyped_defs = false` intentionally** (type coverage incomplete in early phase)
  - Excludes: tests/ (no type hints required)

Manually run before commit:
```bash
uv run ruff check --fix
uv run ruff format
uv run mypy query_analyzer
```

Or rely on installed hooks:
```bash
uv run pre-commit install  # One-time setup
git add . && git commit -m "..."  # Hooks run automatically
```

**If commit fails:** ruff auto-fixes files (re-add them) then mypy rejects on remaining type errors (fix them). Retry commit.

---

## Testing

### Unit Tests
```bash
uv run pytest tests/unit/
```

No Docker required. MyPy skips test files (no type coverage expected).

### Integration Tests
Require database services running:
```bash
make up              # Start Docker Compose services
make health          # Verify services are ready
uv run pytest tests/integration/
make down            # Optional cleanup
```

**Adapter registry quirk:** `conftest.py` auto-registers PostgreSQL adapter before each test via `ensure_postgresql_registered()` fixture. Some tests (like adapter_registry tests) may clear the registry; re-registration is automatic.

### Coverage
```bash
uv run pytest --cov=query_analyzer
```

---

## Architecture: Adapter Pattern & Registry

The core design is a **pluggable adapter system** for multi-engine support.

**Structure:**
- `query_analyzer/adapters/base.py` — `BaseAdapter` abstract class (interface for all drivers)
- `query_analyzer/adapters/registry.py` — `AdapterRegistry` (factory & registration)
- `query_analyzer/adapters/sql/` — PostgreSQL, MySQL, SQLite, CockroachDB, etc.
- `query_analyzer/adapters/nosql/` — MongoDB, Redis, Neo4j, etc.
- `query_analyzer/core/` — `AntiPatternDetector`, `RecommendationEngine`, parsers (engine-agnostic)
- `query_analyzer/cli/` — CLI entry point (typer-based)
- `query_analyzer/tui/` — Textual UI (TUI framework)

**Adapter registration pattern:**
```python
@AdapterRegistry.register("postgresql")
class PostgreSQLAdapter(BaseAdapter):
    def connect(self) -> None: ...
    def execute_explain(self, query: str) -> QueryAnalysisReport: ...
    # ... (other abstract methods)
```

**Creating an adapter instance:**
```python
config = ConnectionConfig(engine="postgresql", host="localhost", ...)
adapter = AdapterRegistry.create("postgresql", config)
adapter.connect()
report = adapter.execute_explain("SELECT ...")
```

No direct imports of specific adapters needed in client code.

---

## CockroachDB Adapter

**CockroachDBAdapter** (`query_analyzer/adapters/sql/cockroachdb.py`) extends **PostgreSQLAdapter** to handle CRDB-specific optimizations.

### Key Features

- **Wire Protocol Compatibility:** CockroachDB implements PostgreSQL wire protocol, so uses `psycopg2` driver
- **CockroachDB Parser:** `CockroachDBParser` extends `PostgreSQLExplainParser` to detect CRDB-specific join types
- **EXPLAIN Fallback Strategy:**
  1. `EXPLAIN (DISTSQL, ANALYZE, FORMAT JSON)` — full distributed metrics (v22.1+)
  2. `EXPLAIN (ANALYZE, FORMAT JSON)` — standard format
  3. `EXPLAIN ANALYZE` — text fallback if JSON unavailable

### CRDB-Specific Features

| Feature | Detection | Warning Threshold |
|---------|-----------|-------------------|
| **Lookup Join** | Node type contains "Lookup Join" | Count > 5 |
| **Zigzag Join** | Node type contains "Zigzag Join" | Informational |
| **Distributed Execution** | Presence of "Distributed" or "Remote" nodes | Informational |

### Metrics Added

```python
{
    # PostgreSQL inherited
    "planning_time_ms": float,
    "execution_time_ms": float,
    ...
    # CockroachDB-specific
    "is_distributed": bool,           # Uses distributed execution
    "lookup_join_count": int,         # Number of Lookup Joins
    "zigzag_join_count": int,         # Number of Zigzag Joins
    "has_remote_execution": bool,     # Contains Remote nodes
}
```

### Example Usage

```python
from query_analyzer.adapters import AdapterRegistry, ConnectionConfig

config = ConnectionConfig(
    engine="cockroachdb",
    host="localhost",
    port=26257,
    database="defaultdb",
    username="root",
    password="",
    extra={"seq_scan_threshold": 10000}
)

adapter = AdapterRegistry.create("cockroachdb", config)
adapter.connect()
report = adapter.execute_explain("SELECT * FROM orders JOIN customers ...")
print(f"Score: {report.score}/100")
print(f"Is Distributed: {report.metrics['is_distributed']}")
print(f"Lookup Joins: {report.metrics['lookup_join_count']}")
adapter.disconnect()
```

---

## YugabyteDB Adapter

**YugabyteDBAdapter** (`query_analyzer/adapters/sql/yugabytedb.py`) extends **PostgreSQLAdapter** with YugabyteDB-specific defaults.

### Key Features

- **Wire Protocol Compatibility:** YugabyteDB implements PostgreSQL wire protocol, uses `psycopg2` driver
- **YugabyteDB Parser:** `YugabyteDBParser` extends `PostgreSQLExplainParser` (minimal override for MVP)
- **Default Port:** Automatically converts PostgreSQL default port 5432 → YugabyteDB port 5433
- **Standard EXPLAIN Format:** Uses standard PostgreSQL EXPLAIN (no DISTSQL equivalent in v1)
- **Implicit Distribution:** Distribution is transparent to query optimizer (DocDB storage layer handles it)

### Architecture Note

Unlike CockroachDB, YugabyteDB distribution is **implicit** and not visible in EXPLAIN output. For MVP (v1):
- Parser reuses PostgreSQL behavior (no special node type detection)
- Future enhancements (v1.1) will add:
  - Tablet-level metrics via `yb_local_tablets()` and `yb_tablet_servers()`
  - Colocation detection and warnings
  - Cross-region query patterns

### Example Usage

```python
from query_analyzer.adapters import AdapterRegistry, ConnectionConfig

config = ConnectionConfig(
    engine="yugabytedb",
    host="localhost",
    port=5433,  # YugabyteDB YSQL port (or omit - adapter auto-converts 5432→5433)
    database="yugabyte",
    username="yugabyte",
    password="yugabyte",
    extra={"seq_scan_threshold": 10000}
)

adapter = AdapterRegistry.create("yugabytedb", config)
adapter.connect()
report = adapter.execute_explain("SELECT * FROM users JOIN orders ...")
print(f"Score: {report.score}/100")
print(f"Execution Time: {report.execution_time_ms}ms")
adapter.disconnect()
```

### Default Credentials

- Username: `yugabyte`
- Password: `yugabyte`
- Database: `yugabyte`
- YSQL Port: `5433` (PostgreSQL-compatible query layer)

---

## Docker & Services

`docker/compose.yml` defines 7 database services for dev & testing:
- PostgreSQL, MySQL, MongoDB, Redis, InfluxDB, Neo4j, CockroachDB, YugabyteDB

**Makefile shortcuts:**
- `make up` — start services (non-blocking)
- `make down` — stop services
- `make reset` — destroy containers & volumes (clean slate)
- `make seed` — populate SQL databases with test data
- `make health` — check service health status
- `make logs` or `make logs-<service>` — tail logs

**Credentials:** Defined in `.env` (copy from `.env.example`). Defaults:
```
DB_POSTGRES_USER=postgres, DB_POSTGRES_PASSWORD=postgres123, DB_POSTGRES_PORT=5432
DB_MYSQL_USER=analyst, DB_MYSQL_PASSWORD=mysql123, DB_MYSQL_PORT=3306
DB_MONGODB_USER=admin, DB_MONGODB_PASSWORD=mongodb123, DB_MONGODB_PORT=27017
```

---

## Known Quirks & Intentional Decisions

| Item | Detail | Why |
|---|---|---|
| MyPy permissiveness | `disallow_untyped_defs = false` | Type coverage ~70%; strictness deferred to post-v1 |
| Type skipping | Tests excluded from MyPy checks | Tests don't need type hints; focus on core code |
| E501 ignored | Ruff ignores line-length in lint rules | Formatter (`ruff format`) handles it instead |
| Test fixtures | Adapter registry auto-registers PostgreSQL | Prevents test pollution from adapter state changes |
| No pytest.ini | Config lives in `[tool.pytest]` section of pyproject.toml | Single source of truth for all tool config |

---

## 📋 Git Policies (CRÍTICO)

### Política de Commits
❌ NUNCA hagas `git add` sin autorización explícita del usuario
❌ NUNCA hagas `git commit` sin autorización explícita del usuario
✅ Puedes preparar cambios y mostrar diffs, pero espera instrucción explícita
✅ Si el usuario dice "crea un commit" o "haz commit", entonces procede

### Política de Git Push
❌ NUNCA hagas `git push` sin autorización explícita del usuario
✅ Solo haz push cuando el usuario lo pida explícitamente
✅ Avisa al usuario si hay commits listos para ser pusheados

### Operaciones Git Permitidas
✅ **Exploración sin restricciones:**
- `git status` — Ver estado del repositorio
- `git log` — Ver histórico de commits
- `git diff` — Ver cambios
- `git branch` — Ver ramas

✅ **Cambios de rama:** Solo si el usuario lo solicita explícitamente

❌ **Operaciones destructivas:** `git reset --hard`, `git rebase -i`, `git add .`
   - Solo con autorización explícita del usuario

### Commit Message Format (cuando esté autorizado)
Usar [Conventional Commits](https://www.conventionalcommits.org/):
- `feat:` Nueva funcionalidad
- `fix:` Corrección de bugs
- `docs:` Documentación
- `test:` Tests
- `chore:` Tareas administrativas

---

## Common Workflows

```bash
# Develop a new feature
git checkout -b feature/my-feature
uv sync
# ... make changes ...
uv run ruff check --fix && uv run ruff format
uv run mypy query_analyzer
uv run pytest tests/unit/
git add . && git commit -m "feat: description"

# Run integration tests
make up
make health   # Wait for services
uv run pytest tests/integration/
make down

# Clean up
make reset    # Remove containers & volumes
uv run pre-commit clean  # Clear cache
```

---

## Useful References

- **Backlog & roadmap:** See root backlog document (4 phases: v0-setup → v1-sql → v2-nosql → v3-tui → v4-release)
- **Dependencies:** `pyproject.toml` [project] section (production) and [dependency-groups.dev] (dev tools)
- **Docker config:** `docker/compose.yml` (services), `docker/seed/` (test data scripts)
- **Pre-commit hooks:** `.pre-commit-config.yaml` (ruff, mypy, standard checks)
- **Type stubs for drivers:** `[additional_dependencies]` in `.pre-commit-config.yaml` (mypy mirrors-mypy hook)
