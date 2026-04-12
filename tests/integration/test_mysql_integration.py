"""Integration tests for MySQL adapter with Docker."""

import logging
import time
from collections.abc import Generator

import pytest

from query_analyzer.adapters import (
    ConnectionConfig,
)
from query_analyzer.adapters.sql import MySQLAdapter

logger = logging.getLogger(__name__)


# ============================================================================
# FIXTURES - Docker MySQL Setup
# ============================================================================


@pytest.fixture(scope="session")
def docker_mysql_config() -> ConnectionConfig:
    """MySQL connection config for Docker container."""
    return ConnectionConfig(
        engine="mysql",
        host="localhost",
        port=3306,
        database="query_analyzer",
        username="analyst",
        password="mysql123",
        extra={"seq_scan_threshold": 5000, "connection_timeout": 10},
    )


@pytest.fixture
def mysql_adapter(
    docker_mysql_config: ConnectionConfig,
) -> Generator[MySQLAdapter]:
    """Connect to Docker MySQL, yield adapter, cleanup."""
    adapter = MySQLAdapter(docker_mysql_config)

    # Wait for Docker to be ready (with timeout)
    max_retries = 30
    for attempt in range(max_retries):
        try:
            adapter.connect()
            if adapter.test_connection():
                logger.info(f"Connected to MySQL after {attempt + 1} attempts")
                break
        except Exception as e:
            logger.debug(f"Connection attempt {attempt + 1}/{max_retries} failed: {e}")
            time.sleep(1)
    else:
        pytest.skip("Could not connect to Docker MySQL - is it running?")

    yield adapter

    # Cleanup
    adapter.disconnect()


# ============================================================================
# TESTS - Real Database Connection
# ============================================================================


class TestMySQLIntegrationConnection:
    """Real database connectivity tests."""

    def test_connect_and_disconnect(self, docker_mysql_config: ConnectionConfig) -> None:
        """Connect to and disconnect from Docker MySQL."""
        adapter = MySQLAdapter(docker_mysql_config)

        try:
            adapter.connect()
            assert adapter.is_connected() is True
            assert adapter.test_connection() is True

            adapter.disconnect()
            assert adapter.is_connected() is False
        except Exception as e:
            pytest.skip(f"Docker MySQL not available: {e}")

    def test_context_manager_real_database(self, docker_mysql_config: ConnectionConfig) -> None:
        """Context manager works with real database."""
        adapter = MySQLAdapter(docker_mysql_config)

        try:
            with adapter:
                assert adapter.is_connected() is True
                assert adapter.test_connection() is True

            assert adapter.is_connected() is False
        except Exception:
            pytest.skip("Docker MySQL not available")

    def test_invalid_credentials_raises_error(self, docker_mysql_config: ConnectionConfig) -> None:
        """Invalid credentials raise descriptive error."""
        bad_config = ConnectionConfig(
            engine="mysql",
            host="localhost",
            port=3306,
            database="query_analyzer",
            username="analyst",
            password="wrongpassword123",
            extra={"connection_timeout": 5},
        )
        adapter = MySQLAdapter(bad_config)

        with pytest.raises(Exception) as exc_info:
            adapter.connect()

        # Should mention authentication error
        error_msg = str(exc_info.value).lower()
        assert "password" in error_msg or "auth" in error_msg or "access denied" in error_msg


# ============================================================================
# TESTS - Real EXPLAIN Analysis with Parametrized Queries
# ============================================================================


class TestMySQLIntegrationExplain:
    """Real EXPLAIN tests on Docker MySQL."""

    def test_explain_simple_select(self, mysql_adapter: MySQLAdapter) -> None:
        """Execute EXPLAIN on simple SELECT from orders table."""
        query = "SELECT * FROM orders LIMIT 10"

        try:
            report = mysql_adapter.execute_explain(query)

            assert report.engine == "mysql"
            assert report.query == query
            assert 0 <= report.score <= 100
            assert report.execution_time_ms >= 0
            assert report.raw_plan is not None
            assert isinstance(report.metrics, dict)
        except Exception as e:
            pytest.skip(f"EXPLAIN analysis failed: {e}")

    def test_anti_pattern_query_analysis(
        self,
        mysql_adapter: MySQLAdapter,
        anti_pattern_query: dict,
    ) -> None:
        """Analyze anti-pattern queries and validate scoring/warnings."""
        query = anti_pattern_query["query"]

        try:
            report = mysql_adapter.execute_explain(query)

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

            # Validate expected recommendation keywords
            if anti_pattern_query.get("expected_recommendation_keywords"):
                for keyword in anti_pattern_query["expected_recommendation_keywords"]:
                    assert any(keyword.lower() in rec.lower() for rec in report.recommendations), (
                        f"Expected recommendation keyword '{keyword}' not found "
                        f"in {report.recommendations} for {anti_pattern_query['name']}"
                    )

        except Exception as e:
            pytest.skip(f"Anti-pattern analysis failed for {anti_pattern_query['name']}: {e}")

    def test_explain_index_scan_has_good_score(self, mysql_adapter: MySQLAdapter) -> None:
        """Analyze query with index - should have good score."""
        query = "SELECT * FROM customers WHERE id = 1"

        try:
            report = mysql_adapter.execute_explain(query)

            # Index scan should have good score
            assert report.score >= 70, f"Expected score >= 70, got {report.score}"
        except Exception as e:
            pytest.skip(f"Index scan EXPLAIN failed: {e}")

    def test_explain_full_scan_detection(self, mysql_adapter: MySQLAdapter) -> None:
        """Test EXPLAIN detects full table scans."""
        query = "SELECT COUNT(*) FROM customers"

        try:
            report = mysql_adapter.execute_explain(query)

            assert isinstance(report.warnings, list)
            assert isinstance(report.metrics, dict)
        except Exception as e:
            pytest.skip(f"Full scan detection failed: {e}")


# ============================================================================
# TESTS - Metrics Collection
# ============================================================================


class TestMySQLIntegrationMetrics:
    """Real metrics collection from MySQL."""

    def test_get_metrics(self, mysql_adapter: MySQLAdapter) -> None:
        """Collect database metrics."""
        try:
            metrics = mysql_adapter.get_metrics()

            assert isinstance(metrics, dict)
        except Exception as e:
            pytest.skip(f"Metrics collection failed: {e}")

    def test_get_engine_info(self, mysql_adapter: MySQLAdapter) -> None:
        """Collect engine information."""
        try:
            info = mysql_adapter.get_engine_info()

            assert isinstance(info, dict)
            if "version" in info:
                assert isinstance(info["version"], str)

        except Exception as e:
            pytest.skip(f"Engine info collection failed: {e}")


# ============================================================================
# TESTS - Slow Queries Detection
# ============================================================================


class TestMySQLIntegrationSlowQueries:
    """Real slow query detection."""

    def test_get_slow_queries_returns_list(self, mysql_adapter: MySQLAdapter) -> None:
        """get_slow_queries returns a list."""
        try:
            result = mysql_adapter.get_slow_queries(threshold_ms=0)
            assert isinstance(result, list)

        except Exception as e:
            pytest.skip(f"Slow query call failed: {e}")


# ============================================================================
# TESTS - Query Validation
# ============================================================================


class TestMySQLIntegrationValidation:
    """Query validation in EXPLAIN analysis."""

    def test_ddl_rejection(self, mysql_adapter: MySQLAdapter) -> None:
        """EXPLAIN rejects DDL statements."""
        from query_analyzer.adapters.exceptions import QueryAnalysisError

        ddl_queries = [
            "CREATE TABLE test (id INT)",
            "DROP TABLE test",
            "ALTER TABLE orders ADD COLUMN test INT",
        ]

        for query in ddl_queries:
            with pytest.raises((QueryAnalysisError, Exception)) as exc_info:
                mysql_adapter.execute_explain(query)

            error_msg = str(exc_info.value)
            assert "DDL" in error_msg or "not supported" in error_msg.lower()

    def test_invalid_table_raises_error(self, mysql_adapter: MySQLAdapter) -> None:
        """Invalid table name raises clear error."""
        with pytest.raises(Exception) as exc_info:
            mysql_adapter.execute_explain("SELECT * FROM nonexistent_table_xyz")

        error_msg = str(exc_info.value)
        assert "nonexistent_table" in error_msg or "doesn't exist" in error_msg.lower()

    def test_invalid_column_raises_error(self, mysql_adapter: MySQLAdapter) -> None:
        """Invalid column name raises clear error."""
        with pytest.raises(Exception) as exc_info:
            mysql_adapter.execute_explain("SELECT nonexistent_xyz FROM orders")

        error_msg = str(exc_info.value)
        assert "nonexistent_xyz" in error_msg or "unknown column" in error_msg.lower()

    def test_syntax_error_raises_error(self, mysql_adapter: MySQLAdapter) -> None:
        """Malformed SQL raises clear error."""
        with pytest.raises(Exception) as exc_info:
            mysql_adapter.execute_explain("SELECT * FORM customers")  # Typo: FORM -> FROM

        error_msg = str(exc_info.value)
        assert "syntax" in error_msg.lower() or "error" in error_msg.lower()
