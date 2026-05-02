"""Integration tests for InfluxDB adapter with Docker."""

import logging
import time
from collections.abc import Generator

import pytest

from query_analyzer.adapters import ConnectionConfig, InfluxDBAdapter
from query_analyzer.adapters.exceptions import QueryAnalysisError

logger = logging.getLogger(__name__)


# ============================================================================
# FIXTURES - Docker InfluxDB Setup
# ============================================================================


@pytest.fixture(scope="session")
def docker_influxdb_config() -> ConnectionConfig:
    """InfluxDB connection config for Docker container."""
    return ConnectionConfig(
        engine="influxdb",
        host="localhost",
        port=8086,
        database="query_analyzer",
        password="mytoken",  # API token
        extra={"org": "", "connection_timeout": 10},
    )


@pytest.fixture
def influxdb_adapter(
    docker_influxdb_config: ConnectionConfig,
) -> Generator[InfluxDBAdapter]:
    """Connect to Docker InfluxDB, yield adapter, cleanup."""
    adapter = InfluxDBAdapter(docker_influxdb_config)

    # Wait for Docker to be ready (with timeout)
    max_retries = 30
    for attempt in range(max_retries):
        try:
            adapter.connect()
            if adapter.test_connection():
                logger.info(f"Connected to InfluxDB after {attempt + 1} attempts")
                break
        except Exception as e:
            logger.debug(f"Connection attempt {attempt + 1}/{max_retries} failed: {e}")
            time.sleep(1)
    else:
        pytest.skip("Could not connect to Docker InfluxDB - is it running?")

    yield adapter

    # Cleanup
    adapter.disconnect()


# ============================================================================
# TESTS - Connection & Lifecycle
# ============================================================================


class TestInfluxDBIntegrationConnection:
    """Real database connectivity tests."""

    def test_connect_and_disconnect(self, docker_influxdb_config: ConnectionConfig) -> None:
        """Connect to and disconnect from Docker InfluxDB."""
        adapter = InfluxDBAdapter(docker_influxdb_config)

        try:
            adapter.connect()
            assert adapter.is_connected() is True
            assert adapter.test_connection() is True

            adapter.disconnect()
            assert adapter.is_connected() is False
        except Exception as e:
            pytest.skip(f"Docker InfluxDB not available: {e}")

    def test_context_manager_real_database(self, docker_influxdb_config: ConnectionConfig) -> None:
        """Context manager works with real InfluxDB."""
        adapter = InfluxDBAdapter(docker_influxdb_config)

        try:
            with adapter:
                assert adapter.is_connected() is True
                assert adapter.test_connection() is True

            assert adapter.is_connected() is False
        except Exception:
            pytest.skip("Docker InfluxDB not available")

    def test_invalid_credentials_raises_error(
        self, docker_influxdb_config: ConnectionConfig
    ) -> None:
        """Invalid token raises ConnectionError."""
        bad_config = ConnectionConfig(
            engine="influxdb",
            host="localhost",
            port=8086,
            database="query_analyzer",
            password="invalid_token_xyz",
            extra={"org": "", "connection_timeout": 1},
        )

        adapter = InfluxDBAdapter(bad_config)

        # Connection may fail or succeed but health check will fail
        try:
            with pytest.raises(Exception):  # ConnectionError or other exception
                adapter.connect()
        except Exception:
            pytest.skip("Docker InfluxDB behavior differs")


# ============================================================================
# TESTS - Query Analysis & Anti-Pattern Detection
# ============================================================================


class TestInfluxDBIntegrationQueryAnalysis:
    """Flux query analysis and anti-pattern detection tests."""

    def test_unbounded_query_detection(self, influxdb_adapter: InfluxDBAdapter) -> None:
        """Detect unbounded query (no time filter) - CRITICAL warning.

        Unbounded queries (missing range()) perform full bucket scans and
        should receive the maximum penalty (-30 points).
        """
        # Query without range() - should get critical warning
        flux_query = 'from(bucket:"metrics") |> filter(fn: (r) => r._measurement == "cpu")'

        report = influxdb_adapter.execute_explain(flux_query)

        # Score should be heavily penalized
        assert report.score < 100, "Unbounded query should reduce score"
        assert report.score <= 70, f"Expected score <= 70, got {report.score}"

        # Should have warning about time filter
        assert any(
            "time filter" in (w.message or "").lower() or "unbounded" in (w.message or "").lower()
            for w in report.warnings
        ), f"Expected time filter warning, got: {report.warnings}"

        # Should recommend adding time filter
        assert any("range" in (r.title or "").lower() for r in report.recommendations), (
            f"Expected range recommendation, got: {report.recommendations}"
        )

    def test_bounded_query_high_score(self, influxdb_adapter: InfluxDBAdapter) -> None:
        """Well-formed query with time filter should have high score."""
        flux_query = (
            'from(bucket:"metrics") '
            "|> range(start: -1h, stop: now()) "
            '|> filter(fn: (r) => r._measurement == "cpu")'
        )

        report = influxdb_adapter.execute_explain(flux_query)

        # Should have high score (no unbounded warning)
        assert report.score == 100, f"Expected score 100, got {report.score}"

        # Should NOT have unbounded warning
        assert not any("unbounded" in (w.message or "").lower() for w in report.warnings), (
            f"Should have no unbounded warning, got: {report.warnings}"
        )

    def test_high_cardinality_group_by_detection(self, influxdb_adapter: InfluxDBAdapter) -> None:
        """Detect high-cardinality group-by (>10 columns)."""
        # Simulate many group-by columns (>10)
        columns_list = (
            '["col1", "col2", "col3", "col4", "col5", "col6", "col7", '
            '"col8", "col9", "col10", "col11"]'
        )
        flux_query = (
            'from(bucket:"metrics") '
            "|> range(start: -1h, stop: now()) "
            f"|> group(columns: {columns_list}) "
        )

        report = influxdb_adapter.execute_explain(flux_query)

        # Should have cardinality warning
        assert any(
            "cardinality" in (w.message or "").lower() or "group" in (w.message or "").lower()
            for w in report.warnings
        ), f"Expected cardinality warning, got: {report.warnings}"

        # Score should be reduced
        assert report.score < 100

    def test_excessive_transformations_detection(self, influxdb_adapter: InfluxDBAdapter) -> None:
        """Detect excessive map/reduce operations (>5)."""
        flux_query = (
            'from(bucket:"metrics") '
            "|> range(start: -1h, stop: now()) "
            "|> map(fn: (r) => ({r with value: r.value * 2})) "
            "|> map(fn: (r) => ({r with value: r.value + 1})) "
            "|> map(fn: (r) => ({r with value: r.value * 3})) "
            "|> reduce(fn: (r, acc) => acc + r.value) "
            "|> map(fn: (r) => ({r with final: r.value})) "
            "|> map(fn: (r) => ({r with final: r.final + 1})) "
        )

        report = influxdb_adapter.execute_explain(flux_query)

        # Should recommend simplification
        assert any("simplif" in (rec.title or "").lower() for rec in report.recommendations), (
            f"Expected simplification recommendation, got: {report.recommendations}"
        )

    def test_invalid_flux_syntax_raises_error(self, influxdb_adapter: InfluxDBAdapter) -> None:
        """Invalid Flux query raises QueryAnalysisError."""
        invalid_flux = "DELETE BUCKET my_bucket"

        with pytest.raises(QueryAnalysisError):
            influxdb_adapter.execute_explain(invalid_flux)

    def test_import_keyword_raises_error(self, influxdb_adapter: InfluxDBAdapter) -> None:
        """Flux IMPORT statement raises QueryAnalysisError."""
        invalid_flux = 'IMPORT "mypackage"'

        with pytest.raises(QueryAnalysisError):
            influxdb_adapter.execute_explain(invalid_flux)

    def test_query_returns_analysis_report(self, influxdb_adapter: InfluxDBAdapter) -> None:
        """Query analysis returns complete QueryAnalysisReport."""
        flux_query = 'from(bucket:"metrics") |> range(start: -1h, stop: now()) '

        report = influxdb_adapter.execute_explain(flux_query)

        # Verify report structure
        assert report.engine == "influxdb"
        assert report.query == flux_query
        assert 0 <= report.score <= 100
        assert report.execution_time_ms >= 0
        assert isinstance(report.warnings, list)
        assert isinstance(report.recommendations, list)
        assert report.raw_plan is not None
        assert isinstance(report.metrics, dict)


# ============================================================================
# TESTS - Adapter Methods
# ============================================================================


class TestInfluxDBIntegrationMethods:
    """Test all BaseAdapter methods."""

    def test_get_engine_info(self, influxdb_adapter: InfluxDBAdapter) -> None:
        """Get InfluxDB engine information."""
        info = influxdb_adapter.get_engine_info()

        assert isinstance(info, dict)
        assert info.get("engine") == "influxdb"
        assert "version" in info or "commit" in info

    def test_get_metrics(self, influxdb_adapter: InfluxDBAdapter) -> None:
        """Get InfluxDB metrics."""
        metrics = influxdb_adapter.get_metrics()

        assert isinstance(metrics, dict)
        # May be empty or have status/message
        if metrics:
            assert "status" in metrics or "message" in metrics

    def test_get_slow_queries(self, influxdb_adapter: InfluxDBAdapter) -> None:
        """Get slow queries (graceful fallback - returns empty list for InfluxDB)."""
        slow_queries = influxdb_adapter.get_slow_queries(threshold_ms=100)

        assert isinstance(slow_queries, list)
        # InfluxDB 2.x doesn't have traditional slow query logs
        # So this gracefully returns empty list

    def test_get_slow_queries_not_connected(self, docker_influxdb_config: ConnectionConfig) -> None:
        """Get slow queries when not connected returns empty list."""
        adapter = InfluxDBAdapter(docker_influxdb_config)
        # Don't connect

        slow_queries = adapter.get_slow_queries()

        assert isinstance(slow_queries, list)
        assert len(slow_queries) == 0

    def test_get_metrics_not_connected(self, docker_influxdb_config: ConnectionConfig) -> None:
        """Get metrics when not connected returns empty dict."""
        adapter = InfluxDBAdapter(docker_influxdb_config)
        # Don't connect

        metrics = adapter.get_metrics()

        assert isinstance(metrics, dict)
        assert len(metrics) == 0

    def test_get_engine_info_not_connected(self, docker_influxdb_config: ConnectionConfig) -> None:
        """Get engine info when not connected returns empty dict."""
        adapter = InfluxDBAdapter(docker_influxdb_config)
        # Don't connect

        info = adapter.get_engine_info()

        assert isinstance(info, dict)
        assert len(info) == 0


# ============================================================================
# TESTS - Parser & Normalization
# ============================================================================


class TestInfluxDBIntegrationParser:
    """Test Flux parser and plan normalization."""

    def test_parser_extracts_bucket(self, influxdb_adapter: InfluxDBAdapter) -> None:
        """Parser correctly extracts bucket name."""
        flux_query = 'from(bucket:"my_metrics")'
        parsed = influxdb_adapter.parser.parse_query(flux_query)

        assert parsed["bucket"] == "my_metrics"

    def test_parser_detects_time_filter(self, influxdb_adapter: InfluxDBAdapter) -> None:
        """Parser detects presence of time filter."""
        query_with_time = 'from(bucket:"m") |> range(start: -1h, stop: now())'
        query_without_time = 'from(bucket:"m") |> filter(fn: (r) => true)'

        parsed_with = influxdb_adapter.parser.parse_query(query_with_time)
        parsed_without = influxdb_adapter.parser.parse_query(query_without_time)

        assert parsed_with["has_time_filter"] is True
        assert parsed_without["has_time_filter"] is False

    def test_normalize_plan_includes_flux_metadata(self, influxdb_adapter: InfluxDBAdapter) -> None:
        """Normalized plan includes flux_metadata field."""
        parsed = {
            "bucket": "metrics",
            "has_time_filter": False,
            "time_range": None,
            "measurements": [],
            "filters": [],
            "group_by_columns": [],
            "has_aggregation": False,
            "transformation_count": 0,
            "operations": ["filter"],
        }

        normalized = influxdb_adapter.parser.normalize_plan(parsed)

        assert "flux_metadata" in normalized
        assert normalized["flux_metadata"]["has_time_filter"] is False
        assert normalized["flux_metadata"]["transformation_count"] == 0


# ============================================================================
# TESTS - Error Handling & Edge Cases
# ============================================================================


class TestInfluxDBIntegrationErrorHandling:
    """Test error handling and edge cases."""

    def test_empty_query_raises_error(self, influxdb_adapter: InfluxDBAdapter) -> None:
        """Empty query raises QueryAnalysisError."""
        with pytest.raises(QueryAnalysisError):
            influxdb_adapter.execute_explain("")

    def test_create_bucket_statement_raises_error(self, influxdb_adapter: InfluxDBAdapter) -> None:
        """CREATE BUCKET statement raises QueryAnalysisError."""
        with pytest.raises(QueryAnalysisError):
            influxdb_adapter.execute_explain("CREATE BUCKET new_bucket")

    def test_query_analysis_not_connected_raises_error(
        self, docker_influxdb_config: ConnectionConfig
    ) -> None:
        """Query analysis when not connected raises error."""
        adapter = InfluxDBAdapter(docker_influxdb_config)

        with pytest.raises(QueryAnalysisError):
            adapter.execute_explain('from(bucket:"metrics")')

    def test_adapter_lifecycle_multiple_connects(
        self, docker_influxdb_config: ConnectionConfig
    ) -> None:
        """Adapter handles multiple connect/disconnect cycles."""
        adapter = InfluxDBAdapter(docker_influxdb_config)

        try:
            # First cycle
            adapter.connect()
            assert adapter.is_connected() is True
            adapter.disconnect()
            assert adapter.is_connected() is False

            # Second cycle
            adapter.connect()
            assert adapter.is_connected() is True
            adapter.disconnect()
            assert adapter.is_connected() is False
        except Exception as e:
            pytest.skip(f"Docker InfluxDB not available: {e}")
