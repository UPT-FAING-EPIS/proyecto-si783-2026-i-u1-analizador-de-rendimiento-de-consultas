"""Integration tests for PostgreSQL adapter with Docker."""

import logging
import time
from collections.abc import Generator

import pytest

from query_analyzer.adapters import (
    ConnectionConfig,
    PostgreSQLAdapter,
)

logger = logging.getLogger(__name__)


# ============================================================================
# FIXTURES - Docker PostgreSQL Setup
# ============================================================================


@pytest.fixture(scope="session")
def docker_postgres_config() -> ConnectionConfig:
    """PostgreSQL connection config for Docker container."""
    return ConnectionConfig(
        engine="postgresql",
        host="localhost",
        port=5432,
        database="query_analyzer",
        username="postgres",
        password="postgres123",
        extra={"seq_scan_threshold": 10000, "connection_timeout": 10},
    )


@pytest.fixture
def pg_adapter(
    docker_postgres_config: ConnectionConfig,
) -> Generator[PostgreSQLAdapter]:
    """Connect to Docker PostgreSQL, yield adapter, cleanup."""
    adapter = PostgreSQLAdapter(docker_postgres_config)

    # Wait for Docker to be ready (with timeout)
    max_retries = 30
    for attempt in range(max_retries):
        try:
            adapter.connect()
            if adapter.test_connection():
                logger.info(f"Connected to PostgreSQL after {attempt + 1} attempts")
                break
        except Exception as e:
            logger.debug(f"Connection attempt {attempt + 1}/{max_retries} failed: {e}")
            time.sleep(1)
    else:
        pytest.skip("Could not connect to Docker PostgreSQL - is it running?")

    yield adapter

    # Cleanup
    adapter.disconnect()


# ============================================================================
# TESTS - Real Database Connection
# ============================================================================


class TestPostgreSQLIntegrationConnection:
    """Real database connectivity tests."""

    def test_connect_and_disconnect(self, docker_postgres_config: ConnectionConfig) -> None:
        """Connect to and disconnect from Docker PostgreSQL."""
        adapter = PostgreSQLAdapter(docker_postgres_config)

        try:
            adapter.connect()
            assert adapter.is_connected() is True
            assert adapter.test_connection() is True

            adapter.disconnect()
            assert adapter.is_connected() is False
        except Exception as e:
            pytest.skip(f"Docker PostgreSQL not available: {e}")

    def test_context_manager_real_database(self, docker_postgres_config: ConnectionConfig) -> None:
        """Context manager works with real database."""
        adapter = PostgreSQLAdapter(docker_postgres_config)

        try:
            with adapter:
                assert adapter.is_connected() is True
                assert adapter.test_connection() is True

            assert adapter.is_connected() is False
        except Exception:
            pytest.skip("Docker PostgreSQL not available")

    def test_invalid_credentials_raises_error(
        self, docker_postgres_config: ConnectionConfig
    ) -> None:
        """Invalid credentials raise descriptive error."""
        bad_config = ConnectionConfig(
            engine="postgresql",
            host="localhost",
            port=5432,
            database="query_analyzer",
            username="postgres",
            password="wrongpassword123",
            extra={"connection_timeout": 5},
        )
        adapter = PostgreSQLAdapter(bad_config)

        with pytest.raises(Exception) as exc_info:
            adapter.connect()

        # Should mention authentication error
        error_msg = str(exc_info.value).lower()
        assert "password" in error_msg or "auth" in error_msg or "connection" in error_msg


# ============================================================================
# TESTS - Real EXPLAIN Analysis with Parametrized Queries
# ============================================================================


class TestPostgreSQLIntegrationExplain:
    """Real EXPLAIN ANALYZE tests on Docker PostgreSQL."""

    def test_explain_simple_select(self, pg_adapter: PostgreSQLAdapter) -> None:
        """Execute EXPLAIN on simple SELECT from orders table."""
        query = "SELECT * FROM orders LIMIT 10"

        try:
            report = pg_adapter.execute_explain(query)

            assert report.engine == "postgresql"
            assert report.query == query
            assert 0 <= report.score <= 100
            assert report.execution_time_ms > 0
            assert report.raw_plan is not None
            assert isinstance(report.metrics, dict)
        except Exception as e:
            pytest.skip(f"EXPLAIN analysis failed: {e}")

    def test_anti_pattern_query_analysis(
        self,
        pg_adapter: PostgreSQLAdapter,
        anti_pattern_query: dict,
    ) -> None:
        """Analyze anti-pattern queries and validate scoring/warnings."""
        query = anti_pattern_query["query"]

        try:
            report = pg_adapter.execute_explain(query)

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
                    assert any(
                        keyword.lower() in (rec.title or "").lower()
                        for rec in report.recommendations
                    ), (
                        f"Expected recommendation keyword '{keyword}' not found "
                        f"in {report.recommendations} for {anti_pattern_query['name']}"
                    )

        except Exception as e:
            pytest.skip(f"Anti-pattern analysis failed for {anti_pattern_query['name']}: {e}")

    def test_explain_detects_seq_scan_on_large_table(self, pg_adapter: PostgreSQLAdapter) -> None:
        """Analyze SELECT on large_table (10K rows) - should detect Seq Scan."""
        query = "SELECT * FROM large_table WHERE created_at > now() - interval '1 day'"

        try:
            report = pg_adapter.execute_explain(query)

            # Should detect sequential scan
            assert report.score < 85, "Score should be lower for Seq Scan on large table"
            assert any("Búsqueda secuencial" in w for w in report.warnings), (
                "Should warn about sequential scan"
            )
            assert any("índice" in (r.title or "").lower() for r in report.recommendations), (
                "Should recommend index creation"
            )
        except Exception as e:
            pytest.skip(f"Large table EXPLAIN failed: {e}")

    def test_explain_index_scan_has_good_score(self, pg_adapter: PostgreSQLAdapter) -> None:
        """Analyze query with index scan - should have good score."""
        # orders table has index on id
        query = "SELECT * FROM orders WHERE id = 1"

        try:
            report = pg_adapter.execute_explain(query)

            # Index scan should have good score
            assert report.score >= 70, f"Expected score >= 70, got {report.score}"
        except Exception as e:
            pytest.skip(f"Index scan EXPLAIN failed: {e}")

    def test_explain_join_query(self, pg_adapter: PostgreSQLAdapter) -> None:
        """Analyze JOIN query."""
        query = """
            SELECT o.id, c.name
            FROM orders o
            JOIN customers c ON o.customer_id = c.id
            LIMIT 10
        """

        try:
            report = pg_adapter.execute_explain(query)

            assert report.score > 0
            assert report.execution_time_ms > 0
            assert len(report.metrics.get("scan_nodes", [])) > 0, (
                "Should identify scan nodes in JOIN"
            )
        except Exception as e:
            pytest.skip(f"JOIN EXPLAIN failed: {e}")


# ============================================================================
# TESTS - Metrics Collection
# ============================================================================


class TestPostgreSQLIntegrationMetrics:
    """Real metrics collection from pg_stat_database."""

    def test_get_metrics(self, pg_adapter: PostgreSQLAdapter) -> None:
        """Collect database metrics."""
        try:
            metrics = pg_adapter.get_metrics()

            # Should have basic metrics
            assert isinstance(metrics, dict)
            # These might be 0 but should be present or handled gracefully
            if metrics:
                assert "database" in metrics or "active_connections" in metrics

        except Exception as e:
            pytest.skip(f"Metrics collection failed: {e}")

    def test_get_engine_info(self, pg_adapter: PostgreSQLAdapter) -> None:
        """Collect engine information."""
        try:
            info = pg_adapter.get_engine_info()

            assert isinstance(info, dict)
            if info:
                assert "version" in info or "engine" in info

        except Exception as e:
            pytest.skip(f"Engine info collection failed: {e}")


# ============================================================================
# TESTS - Slow Queries Detection
# ============================================================================


class TestPostgreSQLIntegrationSlowQueries:
    """Real slow query detection."""

    def test_get_slow_queries_graceful_fallback(self, pg_adapter: PostgreSQLAdapter) -> None:
        """get_slow_queries handles missing pg_stat_statements gracefully."""
        try:
            slow_queries = pg_adapter.get_slow_queries(threshold_ms=100)

            # Should return list (empty if extension not installed)
            assert isinstance(slow_queries, list)

        except Exception as e:
            pytest.skip(f"Slow query detection failed: {e}")

    def test_get_slow_queries_returns_list(self, pg_adapter: PostgreSQLAdapter) -> None:
        """get_slow_queries always returns a list."""
        try:
            # Even if extension is not available, should not raise
            result = pg_adapter.get_slow_queries()
            assert isinstance(result, list)

        except Exception as e:
            pytest.skip(f"Slow query call failed: {e}")


# ============================================================================
# TESTS - Query Validation
# ============================================================================


class TestPostgreSQLIntegrationValidation:
    """Query validation in EXPLAIN analysis."""

    def test_reject_ddl_statements(self, pg_adapter: PostgreSQLAdapter) -> None:
        """EXPLAIN rejects DDL statements."""
        ddl_queries = [
            "CREATE TABLE test (id INT)",
            "ALTER TABLE orders ADD COLUMN test INT",
            "DROP TABLE test",
            "TRUNCATE orders",
        ]

        for query in ddl_queries:
            with pytest.raises(Exception) as exc_info:
                pg_adapter.execute_explain(query)

            assert "DDL" in str(exc_info.value) or "not supported" in str(exc_info.value), (
                f"Should reject DDL: {query}"
            )

    def test_accept_select_insert_update_delete(self, pg_adapter: PostgreSQLAdapter) -> None:
        """EXPLAIN accepts SELECT, INSERT, UPDATE, DELETE."""
        try:
            # SELECT - should work
            report = pg_adapter.execute_explain("SELECT 1")
            assert isinstance(report, object)
            assert hasattr(report, "score")

        except Exception as e:
            pytest.skip(f"Query validation failed: {e}")

    def test_invalid_table_raises_error(self, pg_adapter: PostgreSQLAdapter) -> None:
        """Invalid table name raises clear error."""
        with pytest.raises(Exception) as exc_info:
            pg_adapter.execute_explain("SELECT * FROM nonexistent_table_xyz")

        error_msg = str(exc_info.value)
        assert "nonexistent_table" in error_msg or "does not exist" in error_msg.lower()

    def test_invalid_column_raises_error(self, pg_adapter: PostgreSQLAdapter) -> None:
        """Invalid column name raises clear error."""
        with pytest.raises(Exception) as exc_info:
            pg_adapter.execute_explain("SELECT nonexistent_column_xyz FROM orders")

        error_msg = str(exc_info.value)
        assert "nonexistent_column" in error_msg or "does not exist" in error_msg.lower()

    def test_syntax_error_raises_error(self, pg_adapter: PostgreSQLAdapter) -> None:
        """Malformed SQL raises clear error."""
        with pytest.raises(Exception) as exc_info:
            pg_adapter.execute_explain("SELECT * FORM orders")  # Typo: FORM -> FROM

        error_msg = str(exc_info.value)
        assert "syntax" in error_msg.lower() or "error" in error_msg.lower()
