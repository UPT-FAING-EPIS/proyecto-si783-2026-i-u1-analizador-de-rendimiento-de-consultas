"""Integration tests for MSSQL adapter with Docker-based SQL Server."""

import time
from collections.abc import Generator

import pytest

from query_analyzer.adapters import ConnectionConfig

try:
    from query_analyzer.adapters.sql import MSSQLAdapter
except ImportError:
    MSSQLAdapter = None  # type: ignore


@pytest.fixture(scope="session")
def docker_mssql_config() -> ConnectionConfig:
    """SQL Server connection config for Docker container."""
    return ConnectionConfig(
        engine="mssql",
        host="localhost",
        port=1433,
        database="tempdb",
        username="sa",
        password="YourPassword123!",
        extra={"seq_scan_threshold": 10000, "connection_timeout": 30},
    )


@pytest.fixture
def mssql_adapter(docker_mssql_config: ConnectionConfig) -> Generator:
    """Connect to Docker SQL Server, yield adapter, cleanup."""
    if MSSQLAdapter is None:
        pytest.skip("MSSQLAdapter not available (pymssql missing)")

    adapter = MSSQLAdapter(docker_mssql_config)

    max_retries = 30
    for attempt in range(max_retries):
        try:
            adapter.connect()
            if adapter.test_connection():
                break
        except Exception:
            if attempt < max_retries - 1:
                time.sleep(2)
            else:
                pytest.skip("Could not connect to SQL Server - is Docker running?")

    yield adapter
    adapter.disconnect()


class TestMSSQLAdapterConnection:
    """Test connection lifecycle with real SQL Server."""

    def test_connect_and_disconnect(self, mssql_adapter) -> None:
        assert mssql_adapter.is_connected()

    def test_test_connection(self, mssql_adapter) -> None:
        assert mssql_adapter.test_connection()


class TestMSSQLAdapterExplain:
    """Test SHOWPLAN_XML analysis."""

    def test_simple_select(self, mssql_adapter) -> None:
        report = mssql_adapter.execute_explain(
            "SELECT * FROM sys.objects WHERE type = 'U'"
        )
        assert report.engine == "mssql"
        assert 0 <= report.score <= 100
        assert report.plan_tree is not None

    def test_rejects_ddl(self, mssql_adapter) -> None:
        with pytest.raises(Exception, match="DDL"):
            mssql_adapter.execute_explain("CREATE TABLE #test (id INT)")

    def test_select_with_where(self, mssql_adapter) -> None:
        report = mssql_adapter.execute_explain(
            "SELECT * FROM sys.objects WHERE type = 'U'"
        )
        assert report.raw_plan is not None
        assert "xml" in report.raw_plan


class TestMSSQLAdapterMetrics:
    """Test metrics retrieval."""

    def test_get_metrics(self, mssql_adapter) -> None:
        metrics = mssql_adapter.get_metrics()
        assert isinstance(metrics, dict)

    def test_get_engine_info(self, mssql_adapter) -> None:
        info = mssql_adapter.get_engine_info()
        assert info.get("engine") == "mssql"
        assert "version" in info
        assert "edition" in info


class TestMSSQLAdapterSlowQueries:
    """Test slow query detection."""

    def test_get_slow_queries(self, mssql_adapter) -> None:
        queries = mssql_adapter.get_slow_queries(threshold_ms=1000)
        assert isinstance(queries, list)
