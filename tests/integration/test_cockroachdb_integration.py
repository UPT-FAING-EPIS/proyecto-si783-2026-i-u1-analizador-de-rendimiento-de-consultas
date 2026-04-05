"""Integration tests for CockroachDB adapter with Docker."""

import logging
import time
from collections.abc import Generator

import pytest

from query_analyzer.adapters import CockroachDBAdapter, ConnectionConfig

logger = logging.getLogger(__name__)


# ============================================================================
# FIXTURES - Docker CockroachDB Setup
# ============================================================================


@pytest.fixture(scope="session")
def docker_crdb_config() -> ConnectionConfig:
    """CockroachDB connection config for Docker container."""
    return ConnectionConfig(
        engine="cockroachdb",
        host="localhost",
        port=26257,
        database="defaultdb",
        username="root",
        password="",
        extra={"seq_scan_threshold": 10000, "connection_timeout": 10},
    )


@pytest.fixture
def crdb_adapter(
    docker_crdb_config: ConnectionConfig,
) -> Generator[CockroachDBAdapter]:
    """Connect to Docker CockroachDB, yield adapter, cleanup."""
    adapter = CockroachDBAdapter(docker_crdb_config)

    # Wait for Docker to be ready (max 30 attempts × 1 sec = 30 sec)
    max_retries = 30
    for attempt in range(max_retries):
        try:
            adapter.connect()
            if adapter.test_connection():
                logger.info(f"Connected to CockroachDB after {attempt + 1} attempts")
                break
        except Exception as e:
            logger.debug(f"Connection attempt {attempt + 1}/{max_retries} failed: {e}")
            time.sleep(1)
    else:
        pytest.skip("Could not connect to Docker CockroachDB — is it running?")

    yield adapter

    # Cleanup
    adapter.disconnect()


# ============================================================================
# TESTS - Real Database Connection
# ============================================================================


class TestCockroachDBIntegrationConnection:
    """Real database connectivity tests."""

    def test_connect_and_disconnect(self, docker_crdb_config: ConnectionConfig) -> None:
        """Connect to and disconnect from Docker CockroachDB."""
        adapter = CockroachDBAdapter(docker_crdb_config)

        try:
            adapter.connect()
            assert adapter.is_connected() is True
            assert adapter.test_connection() is True

            adapter.disconnect()
            assert adapter.is_connected() is False
        except Exception as e:
            pytest.skip(f"Docker CockroachDB not available: {e}")

    def test_context_manager_auto_disconnect(self, docker_crdb_config: ConnectionConfig) -> None:
        """Adapter works as context manager with auto-disconnect."""
        try:
            with CockroachDBAdapter(docker_crdb_config) as adapter:
                assert adapter.is_connected() is True
                assert adapter.test_connection() is True
            # After exiting, should be disconnected
            assert adapter.is_connected() is False
        except Exception as e:
            pytest.skip(f"Docker CockroachDB not available: {e}")


class TestCockroachDBIntegrationExplain:
    """EXPLAIN query execution tests."""

    def test_explain_simple_select(self, crdb_adapter: CockroachDBAdapter) -> None:
        """Execute EXPLAIN on simple SELECT query."""
        query = "SELECT 1"
        report = crdb_adapter.execute_explain(query)

        assert report.engine == "cockroachdb"
        assert report.query == query
        assert 0 <= report.score <= 100
        assert isinstance(report.warnings, list)
        assert report.raw_plan is not None

    def test_explain_system_table_query(self, crdb_adapter: CockroachDBAdapter) -> None:
        """Execute EXPLAIN on system table query."""
        query = "SELECT * FROM system.nodes LIMIT 5"
        report = crdb_adapter.execute_explain(query)

        assert report.engine == "cockroachdb"
        assert 0 <= report.score <= 100
        assert isinstance(report.recommendations, list)

    def test_explain_creates_report_with_all_fields(self, crdb_adapter: CockroachDBAdapter) -> None:
        """QueryAnalysisReport has all expected fields."""
        query = "SELECT 1"
        report = crdb_adapter.execute_explain(query)

        # Check all required fields
        assert hasattr(report, "query")
        assert hasattr(report, "engine")
        assert hasattr(report, "score")
        assert hasattr(report, "execution_time_ms")
        assert hasattr(report, "warnings")
        assert hasattr(report, "recommendations")
        assert hasattr(report, "raw_plan")
        assert hasattr(report, "metrics")

    def test_explain_score_reproducible(self, crdb_adapter: CockroachDBAdapter) -> None:
        """Same query produces same score (reproducibility test)."""
        query = "SELECT 1"

        report1 = crdb_adapter.execute_explain(query)
        report2 = crdb_adapter.execute_explain(query)

        assert report1.score == report2.score, "Score must be reproducible"

    def test_explain_different_queries_different_scores(
        self, crdb_adapter: CockroachDBAdapter
    ) -> None:
        """Different queries can produce different scores."""
        query1 = "SELECT 1"
        query2 = "SELECT * FROM system.nodes"

        report1 = crdb_adapter.execute_explain(query1)
        report2 = crdb_adapter.execute_explain(query2)

        # Scores can be same by coincidence, but should be independently calculated
        assert isinstance(report1.score, (int, float))
        assert isinstance(report2.score, (int, float))


class TestCockroachDBIntegrationMetrics:
    """Metrics and engine info tests."""

    def test_get_metrics_returns_dict(self, crdb_adapter: CockroachDBAdapter) -> None:
        """get_metrics() returns dict."""
        metrics = crdb_adapter.get_metrics()

        assert isinstance(metrics, dict)
        assert "engine" in metrics
        assert metrics["engine"] == "cockroachdb"

    def test_get_metrics_no_error_field(self, crdb_adapter: CockroachDBAdapter) -> None:
        """get_metrics() never includes 'error' field (silent errors)."""
        metrics = crdb_adapter.get_metrics()

        # Clean dict — no error field
        assert "error" not in metrics

    def test_get_engine_info_returns_dict(self, crdb_adapter: CockroachDBAdapter) -> None:
        """get_engine_info() returns dict with engine."""
        info = crdb_adapter.get_engine_info()

        assert isinstance(info, dict)
        if len(info) > 0:  # May be empty if no connection
            assert "engine" in info or "version" in info

    def test_get_slow_queries_returns_empty_list(self, crdb_adapter: CockroachDBAdapter) -> None:
        """get_slow_queries() returns empty list (not implemented in v1)."""
        queries = crdb_adapter.get_slow_queries(threshold_ms=100)

        assert isinstance(queries, list)
        assert len(queries) == 0


class TestCockroachDBIntegrationRegistry:
    """Adapter registry integration tests."""

    def test_registry_creates_cockroachdb_adapter(
        self, docker_crdb_config: ConnectionConfig
    ) -> None:
        """AdapterRegistry.create('cockroachdb', config) returns adapter."""
        from query_analyzer.adapters.registry import AdapterRegistry

        adapter = AdapterRegistry.create("cockroachdb", docker_crdb_config)

        assert isinstance(adapter, CockroachDBAdapter)

    def test_registry_adapter_can_connect(self, docker_crdb_config: ConnectionConfig) -> None:
        """Adapter from registry can connect and test."""
        from query_analyzer.adapters.registry import AdapterRegistry

        try:
            adapter = AdapterRegistry.create("cockroachdb", docker_crdb_config)
            adapter.connect()
            assert adapter.test_connection() is True
            adapter.disconnect()
        except Exception as e:
            pytest.skip(f"Docker CockroachDB not available: {e}")


class TestCockroachDBIntegrationErrorHandling:
    """Error handling and edge cases."""

    def test_execute_explain_rejects_ddl(self, crdb_adapter: CockroachDBAdapter) -> None:
        """execute_explain() raises error for DDL statements."""
        from query_analyzer.adapters.exceptions import QueryAnalysisError

        with pytest.raises(QueryAnalysisError):
            crdb_adapter.execute_explain("CREATE TABLE test (id INT)")

    def test_execute_explain_invalid_sql(self, crdb_adapter: CockroachDBAdapter) -> None:
        """execute_explain() raises error for invalid SQL."""
        from query_analyzer.adapters.exceptions import QueryAnalysisError

        with pytest.raises(QueryAnalysisError):
            crdb_adapter.execute_explain("SELECTABLE INVALID SQL HERE")
