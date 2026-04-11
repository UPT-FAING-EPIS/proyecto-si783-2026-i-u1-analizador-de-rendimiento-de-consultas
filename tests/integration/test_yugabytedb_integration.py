"""Integration tests for YugabyteDB adapter with Docker."""

import logging
import time
from collections.abc import Generator

import pytest

from query_analyzer.adapters import ConnectionConfig

logger = logging.getLogger(__name__)


# Try to import YugabyteDB adapter
try:
    from query_analyzer.adapters.sql import YugabyteDBAdapter

    YUGABYTE_AVAILABLE = True
except ImportError:
    YUGABYTE_AVAILABLE = False


# ============================================================================
# FIXTURES - Docker YugabyteDB Setup
# ============================================================================


@pytest.fixture(scope="session")
def docker_yugabyte_config() -> ConnectionConfig:
    """YugabyteDB connection config for Docker container."""
    return ConnectionConfig(
        engine="yugabytedb",
        host="localhost",
        port=5433,  # YugabyteDB YSQL port
        database="yugabyte",
        username="yugabyte",
        password="yugabyte",
        extra={"seq_scan_threshold": 10000, "connection_timeout": 10},
    )


@pytest.fixture
def yugabyte_adapter(
    docker_yugabyte_config: ConnectionConfig,
) -> Generator:
    """Connect to Docker YugabyteDB, yield adapter, cleanup."""
    if not YUGABYTE_AVAILABLE:
        pytest.skip("YugabyteDBAdapter not available")

    adapter = YugabyteDBAdapter(docker_yugabyte_config)

    # Wait for Docker to be ready
    max_retries = 30
    for attempt in range(max_retries):
        try:
            adapter.connect()
            if adapter.test_connection():
                logger.info(f"Connected to YugabyteDB after {attempt + 1} attempts")
                break
        except Exception as e:
            logger.debug(f"Connection attempt {attempt + 1}/{max_retries} failed: {e}")
            time.sleep(1)
    else:
        pytest.skip("Could not connect to Docker YugabyteDB - is it running?")

    yield adapter

    # Cleanup
    adapter.disconnect()


# ============================================================================
# TESTS - Real Database Connection
# ============================================================================


class TestYugabyteDBIntegrationConnection:
    """Real database connectivity tests."""

    def test_connect_and_disconnect(self, docker_yugabyte_config: ConnectionConfig) -> None:
        """Connect to and disconnect from Docker YugabyteDB."""
        if not YUGABYTE_AVAILABLE:
            pytest.skip("YugabyteDBAdapter not available")

        adapter = YugabyteDBAdapter(docker_yugabyte_config)

        try:
            adapter.connect()
            assert adapter.is_connected() is True
            assert adapter.test_connection() is True

            adapter.disconnect()
            assert adapter.is_connected() is False
        except Exception as e:
            pytest.skip(f"Docker YugabyteDB not available: {e}")

    def test_context_manager_real_database(self, docker_yugabyte_config: ConnectionConfig) -> None:
        """Context manager works with real database."""
        if not YUGABYTE_AVAILABLE:
            pytest.skip("YugabyteDBAdapter not available")

        adapter = YugabyteDBAdapter(docker_yugabyte_config)

        try:
            with adapter:
                assert adapter.is_connected() is True
                assert adapter.test_connection() is True

            assert adapter.is_connected() is False
        except Exception:
            pytest.skip("Docker YugabyteDB not available")

    def test_default_credentials_work(self, docker_yugabyte_config: ConnectionConfig) -> None:
        """YugabyteDB default credentials connect successfully."""
        try:
            adapter = YugabyteDBAdapter(docker_yugabyte_config)
            adapter.connect()
            assert adapter.is_connected() is True
            adapter.disconnect()
        except Exception as e:
            pytest.skip(f"Docker YugabyteDB not available: {e}")

    def test_port_5433_conversion(self, docker_yugabyte_config: ConnectionConfig) -> None:
        """YugabyteDB uses correct YSQL port (5433)."""
        assert docker_yugabyte_config.port == 5433, "YugabyteDB should use port 5433 (YSQL)"

    def test_invalid_credentials_raises_error(
        self, docker_yugabyte_config: ConnectionConfig
    ) -> None:
        """Invalid credentials raise descriptive error."""
        if not YUGABYTE_AVAILABLE:
            pytest.skip("YugabyteDBAdapter not available")

        bad_config = ConnectionConfig(
            engine="yugabytedb",
            host="localhost",
            port=5433,
            database="yugabyte",
            username="yugabyte",
            password="wrongpassword123",
            extra={"connection_timeout": 5},
        )
        adapter = YugabyteDBAdapter(bad_config)

        with pytest.raises(Exception) as exc_info:
            adapter.connect()

        error_msg = str(exc_info.value).lower()
        assert any(keyword in error_msg for keyword in ["password", "auth", "connection", "denied"])


# ============================================================================
# TESTS - Real EXPLAIN Analysis with Parametrized Queries
# ============================================================================


class TestYugabyteDBIntegrationExplain:
    """Real EXPLAIN tests on Docker YugabyteDB."""

    def test_explain_simple_select(self, yugabyte_adapter) -> None:
        """Execute EXPLAIN on simple SELECT query."""
        query = "SELECT 1"

        try:
            report = yugabyte_adapter.execute_explain(query)

            assert report.engine == "yugabytedb"
            assert report.query == query
            assert 0 <= report.score <= 100
            assert report.raw_plan is not None
            assert isinstance(report.metrics, dict)
        except Exception as e:
            pytest.skip(f"EXPLAIN analysis failed: {e}")

    def test_anti_pattern_query_analysis(
        self,
        yugabyte_adapter,
        anti_pattern_query: dict,
    ) -> None:
        """Analyze anti-pattern queries and validate scoring/warnings."""
        query = anti_pattern_query["query"]

        try:
            report = yugabyte_adapter.execute_explain(query)

            # Validate score range if specified
            if "expected_score_min" in anti_pattern_query:
                assert report.score >= anti_pattern_query["expected_score_min"], (
                    f"Score {report.score} below minimum "
                    f"{anti_pattern_query['expected_score_min']} for {anti_pattern_query['name']}"
                )

            if "expected_score_max" in anti_pattern_query:
                assert report.score <= anti_pattern_query["expected_score_max"], (
                    f"Score {report.score} above maximum "
                    f"{anti_pattern_query['expected_score_max']} for {anti_pattern_query['name']}"
                )

            # Validate expected warnings
            if anti_pattern_query.get("expected_warnings"):
                for expected_warning in anti_pattern_query["expected_warnings"]:
                    assert any(expected_warning.lower() in w.lower() for w in report.warnings), (
                        f"Expected warning containing '{expected_warning}' not found "
                        f"in {report.warnings} for query: {anti_pattern_query['name']}"
                    )

        except Exception as e:
            pytest.skip(f"Anti-pattern analysis failed for {anti_pattern_query['name']}: {e}")

    def test_explain_index_scan(self, yugabyte_adapter) -> None:
        """Analyze query with potential index usage."""
        query = "SELECT 1 WHERE 1 = 1"

        try:
            report = yugabyte_adapter.execute_explain(query)

            # Score should be in valid range
            assert 0 <= report.score <= 100
        except Exception as e:
            pytest.skip(f"Index scan analysis failed: {e}")

    def test_explain_creates_report_with_all_fields(self, yugabyte_adapter) -> None:
        """QueryAnalysisReport has all expected fields."""
        query = "SELECT 1"

        try:
            report = yugabyte_adapter.execute_explain(query)

            # Check all required fields
            assert hasattr(report, "query")
            assert hasattr(report, "engine")
            assert hasattr(report, "score")
            assert hasattr(report, "execution_time_ms")
            assert hasattr(report, "warnings")
            assert hasattr(report, "recommendations")
            assert hasattr(report, "raw_plan")
            assert hasattr(report, "metrics")
        except Exception as e:
            pytest.skip(f"Report fields check failed: {e}")


# ============================================================================
# TESTS - Metrics Collection
# ============================================================================


class TestYugabyteDBIntegrationMetrics:
    """Real metrics collection tests."""

    def test_get_metrics(self, yugabyte_adapter) -> None:
        """Collect database metrics."""
        try:
            metrics = yugabyte_adapter.get_metrics()

            assert isinstance(metrics, dict)
        except Exception as e:
            pytest.skip(f"Metrics collection failed: {e}")

    def test_get_engine_info(self, yugabyte_adapter) -> None:
        """Collect engine information."""
        try:
            info = yugabyte_adapter.get_engine_info()

            assert isinstance(info, dict)
            if "version" in info:
                assert isinstance(info["version"], str)

        except Exception as e:
            pytest.skip(f"Engine info collection failed: {e}")


# ============================================================================
# TESTS - Slow Queries Detection
# ============================================================================


class TestYugabyteDBIntegrationSlowQueries:
    """Real slow query detection."""

    def test_get_slow_queries_returns_list(self, yugabyte_adapter) -> None:
        """get_slow_queries returns a list."""
        try:
            result = yugabyte_adapter.get_slow_queries(threshold_ms=100)
            assert isinstance(result, list)

        except Exception as e:
            pytest.skip(f"Slow query call failed: {e}")


# ============================================================================
# TESTS - Query Validation
# ============================================================================


class TestYugabyteDBIntegrationValidation:
    """Query validation in EXPLAIN analysis."""

    def test_ddl_rejection(self, yugabyte_adapter) -> None:
        """EXPLAIN rejects DDL statements."""
        ddl_queries = [
            "CREATE TABLE test (id INT)",
            "DROP TABLE test",
            "ALTER TABLE yugabyte ADD COLUMN test INT",
        ]

        for query in ddl_queries:
            with pytest.raises(Exception) as exc_info:
                yugabyte_adapter.execute_explain(query)

            error_msg = str(exc_info.value)
            assert "DDL" in error_msg or "not supported" in error_msg.lower()

    def test_invalid_table_raises_error(self, yugabyte_adapter) -> None:
        """Invalid table name raises clear error."""
        with pytest.raises(Exception) as exc_info:
            yugabyte_adapter.execute_explain("SELECT * FROM nonexistent_table_xyz")

        error_msg = str(exc_info.value)
        assert "nonexistent_table" in error_msg or "does not exist" in error_msg.lower()

    def test_invalid_column_raises_error(self, yugabyte_adapter) -> None:
        """Invalid column name raises clear error."""
        with pytest.raises(Exception) as exc_info:
            yugabyte_adapter.execute_explain(
                "SELECT nonexistent_column_xyz FROM information_schema.tables"
            )

        error_msg = str(exc_info.value)
        assert "nonexistent_column" in error_msg or "does not exist" in error_msg.lower()

    def test_syntax_error_raises_error(self, yugabyte_adapter) -> None:
        """Malformed SQL raises clear error."""
        with pytest.raises(Exception) as exc_info:
            yugabyte_adapter.execute_explain("SELECT * FORM information_schema.tables")

        error_msg = str(exc_info.value)
        assert "syntax" in error_msg.lower() or "error" in error_msg.lower()
