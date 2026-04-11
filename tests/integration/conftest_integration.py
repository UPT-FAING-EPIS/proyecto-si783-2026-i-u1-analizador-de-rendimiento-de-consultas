"""Integration test fixtures for database adapters."""

import os
import time
from collections.abc import Generator

import pytest

from query_analyzer.adapters import (
    ConnectionConfig,
    MySQLAdapter,
    PostgreSQLAdapter,
)

# Try to import optional adapters
try:
    from query_analyzer.adapters.sql import SQLiteAdapter
except ImportError:
    SQLiteAdapter = None  # type: ignore

try:
    from query_analyzer.adapters.sql import CockroachDBAdapter
except ImportError:
    CockroachDBAdapter = None  # type: ignore

try:
    from query_analyzer.adapters.sql import YugabyteDBAdapter
except ImportError:
    YugabyteDBAdapter = None  # type: ignore


# ============================================================================
# CONNECTION CONFIGS - Database credentials from environment or defaults
# ============================================================================


@pytest.fixture(scope="session")
def docker_postgres_config() -> ConnectionConfig:
    """PostgreSQL connection config for Docker container."""
    return ConnectionConfig(
        engine="postgresql",
        host=os.getenv("DB_POSTGRES_HOST", "localhost"),
        port=int(os.getenv("DB_POSTGRES_PORT", "5432")),
        database=os.getenv("DB_POSTGRES_NAME", "query_analyzer"),
        username=os.getenv("DB_POSTGRES_USER", "postgres"),
        password=os.getenv("DB_POSTGRES_PASSWORD", "postgres123"),
        extra={"seq_scan_threshold": 10000, "connection_timeout": 10},
    )


@pytest.fixture(scope="session")
def docker_mysql_config() -> ConnectionConfig:
    """MySQL connection config for Docker container."""
    return ConnectionConfig(
        engine="mysql",
        host=os.getenv("DB_MYSQL_HOST", "localhost"),
        port=int(os.getenv("DB_MYSQL_PORT", "3306")),
        database=os.getenv("DB_MYSQL_NAME", "query_analyzer"),
        username=os.getenv("DB_MYSQL_USER", "analyst"),
        password=os.getenv("DB_MYSQL_PASSWORD", "mysql123"),
        extra={"seq_scan_threshold": 5000, "connection_timeout": 10},
    )


@pytest.fixture(scope="session")
def docker_sqlite_config() -> ConnectionConfig:
    """SQLite connection config."""
    # Use temp file or in-memory
    db_path = os.getenv("DB_SQLITE_PATH", ":memory:")
    return ConnectionConfig(
        engine="sqlite",
        database=db_path,
        extra={"timeout": 10},
    )


@pytest.fixture(scope="session")
def docker_cockroachdb_config() -> ConnectionConfig:
    """CockroachDB connection config."""
    return ConnectionConfig(
        engine="cockroachdb",
        host=os.getenv("DB_COCKROACH_HOST", "localhost"),
        port=int(os.getenv("DB_COCKROACH_PORT", "26257")),
        database=os.getenv("DB_COCKROACH_NAME", "defaultdb"),
        username=os.getenv("DB_COCKROACH_USER", "root"),
        password=os.getenv("DB_COCKROACH_PASSWORD", ""),
        extra={"seq_scan_threshold": 10000, "sslmode": "disable"},
    )


@pytest.fixture(scope="session")
def docker_yugabytedb_config() -> ConnectionConfig:
    """YugabyteDB connection config."""
    return ConnectionConfig(
        engine="yugabytedb",
        host=os.getenv("DB_YUGABYTE_HOST", "localhost"),
        port=int(os.getenv("DB_YUGABYTE_PORT", "5433")),
        database=os.getenv("DB_YUGABYTE_NAME", "yugabyte"),
        username=os.getenv("DB_YUGABYTE_USER", "yugabyte"),
        password=os.getenv("DB_YUGABYTE_PASSWORD", "yugabyte"),
        extra={"seq_scan_threshold": 10000, "connection_timeout": 10},
    )


# ============================================================================
# ADAPTER FIXTURES - Per-database adapter instances
# ============================================================================


@pytest.fixture
def pg_adapter(docker_postgres_config: ConnectionConfig) -> Generator:
    """PostgreSQL adapter with automatic connection management."""
    adapter = PostgreSQLAdapter(docker_postgres_config)

    max_retries = 30
    for attempt in range(max_retries):
        try:
            adapter.connect()
            if adapter.test_connection():
                break
        except Exception:
            if attempt < max_retries - 1:
                time.sleep(1)
            else:
                pytest.skip("Could not connect to Docker PostgreSQL - is it running?")

    yield adapter
    adapter.disconnect()


@pytest.fixture
def mysql_adapter(docker_mysql_config: ConnectionConfig) -> Generator:
    """MySQL adapter with automatic connection management."""
    adapter = MySQLAdapter(docker_mysql_config)

    max_retries = 30
    for attempt in range(max_retries):
        try:
            adapter.connect()
            if adapter.test_connection():
                break
        except Exception:
            if attempt < max_retries - 1:
                time.sleep(1)
            else:
                pytest.skip("Could not connect to Docker MySQL - is it running?")

    yield adapter
    adapter.disconnect()


@pytest.fixture
def sqlite_adapter(docker_sqlite_config: ConnectionConfig) -> Generator:
    """SQLite adapter with automatic connection management."""
    if SQLiteAdapter is None:
        pytest.skip("SQLiteAdapter not available")

    adapter = SQLiteAdapter(docker_sqlite_config)
    adapter.connect()

    yield adapter
    adapter.disconnect()


@pytest.fixture
def cockroachdb_adapter(docker_cockroachdb_config: ConnectionConfig) -> Generator:
    """CockroachDB adapter with automatic connection management."""
    if CockroachDBAdapter is None:
        pytest.skip("CockroachDBAdapter not available")

    adapter = CockroachDBAdapter(docker_cockroachdb_config)

    max_retries = 30
    for attempt in range(max_retries):
        try:
            adapter.connect()
            if adapter.test_connection():
                break
        except Exception:
            if attempt < max_retries - 1:
                time.sleep(1)
            else:
                pytest.skip("Could not connect to CockroachDB - is it running?")

    yield adapter
    adapter.disconnect()


@pytest.fixture
def yugabytedb_adapter(docker_yugabytedb_config: ConnectionConfig) -> Generator:
    """YugabyteDB adapter with automatic connection management."""
    if YugabyteDBAdapter is None:
        pytest.skip("YugabyteDBAdapter not available")

    adapter = YugabyteDBAdapter(docker_yugabytedb_config)

    max_retries = 30
    for attempt in range(max_retries):
        try:
            adapter.connect()
            if adapter.test_connection():
                break
        except Exception:
            if attempt < max_retries - 1:
                time.sleep(1)
            else:
                pytest.skip("Could not connect to YugabyteDB - is it running?")

    yield adapter
    adapter.disconnect()


# ============================================================================
# PARAMETRIZED ADAPTERS - For testing all drivers
# ============================================================================


@pytest.fixture(
    params=["postgresql", "mysql"],
    ids=["postgresql", "mysql"],
)
def sql_adapter_pg_mysql(request: pytest.FixtureRequest) -> Generator:
    """Parametrized fixture for PostgreSQL and MySQL adapters."""
    engine = request.param

    if engine == "postgresql":
        config = ConnectionConfig(
            engine="postgresql",
            host="localhost",
            port=5432,
            database="query_analyzer",
            username="postgres",
            password="postgres123",
            extra={"seq_scan_threshold": 10000},
        )
        adapter = PostgreSQLAdapter(config)
    elif engine == "mysql":
        config = ConnectionConfig(
            engine="mysql",
            host="localhost",
            port=3306,
            database="query_analyzer",
            username="analyst",
            password="mysql123",
            extra={"seq_scan_threshold": 5000},
        )
        adapter = MySQLAdapter(config)
    else:
        pytest.skip(f"Unsupported engine: {engine}")

    # Connect with retries
    max_retries = 10
    for attempt in range(max_retries):
        try:
            adapter.connect()
            if adapter.test_connection():
                break
        except Exception:
            if attempt < max_retries - 1:
                time.sleep(1)
            else:
                pytest.skip(f"Could not connect to {engine} - is it running?")

    yield adapter
    adapter.disconnect()
