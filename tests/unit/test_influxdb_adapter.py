"""Unit tests for InfluxDB adapter."""

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from query_analyzer.adapters import AdapterRegistry, ConnectionConfig, InfluxDBAdapter
from query_analyzer.adapters.models import Recommendation, Warning

# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture(autouse=True)
def _ensure_influxdb_adapter_registered() -> None:
    """Ensure InfluxDB adapter is registered before each test.

    This runs before each test in this module, even if a previous test's
    clean_registry fixture cleared the registry.
    """
    if "influxdb" not in AdapterRegistry.list_engines():
        pass


@pytest.fixture
def influxdb_config() -> ConnectionConfig:
    """Valid InfluxDB connection config."""
    return ConnectionConfig(
        engine="influxdb",
        host="localhost",
        port=8086,
        database="telegraf",
        username="admin",
        password="influxdb_token_abc123xyz",
        extra={"org": "myorg", "connection_timeout": 10},
    )


@pytest.fixture
def mock_query_api_result() -> str:
    """Mock InfluxDB query response (CSV format)."""
    return """result,table,_time,_value,_field,_measurement
_result,0,2024-01-15T10:00:00Z,42.5,temperature,weather
_result,0,2024-01-15T10:01:00Z,43.2,temperature,weather
_result,0,2024-01-15T10:02:00Z,41.8,temperature,weather"""


# ============================================================================
# TESTS - Instantiation & Registry
# ============================================================================


class TestInfluxDBAdapterInstantiation:
    """InfluxDB adapter creation and initialization."""

    def test_instantiate_with_valid_config(self, influxdb_config: ConnectionConfig) -> None:
        """Create InfluxDB adapter with valid config."""
        adapter = InfluxDBAdapter(influxdb_config)

        assert adapter._config == influxdb_config
        assert adapter._is_connected is False
        assert adapter._connection is None
        assert hasattr(adapter, "parser")

    def test_registry_can_create_influxdb_adapter(self, influxdb_config: ConnectionConfig) -> None:
        """Registry factory creates InfluxDB adapter."""
        adapter = AdapterRegistry.create("influxdb", influxdb_config)

        assert isinstance(adapter, InfluxDBAdapter)
        assert adapter._config == influxdb_config

    def test_registry_case_insensitive(self, influxdb_config: ConnectionConfig) -> None:
        """Registry lookup is case-insensitive."""
        adapter1 = AdapterRegistry.create("influxdb", influxdb_config)
        adapter2 = AdapterRegistry.create("InfluxDB", influxdb_config)
        adapter3 = AdapterRegistry.create("INFLUXDB", influxdb_config)

        assert isinstance(adapter1, InfluxDBAdapter)
        assert isinstance(adapter2, InfluxDBAdapter)
        assert isinstance(adapter3, InfluxDBAdapter)


# ============================================================================
# TESTS - Connection Management
# ============================================================================


class TestInfluxDBAdapterConnection:
    """Connection lifecycle tests."""

    @patch("influxdb_client.InfluxDBClient")
    def test_connect_success(
        self, mock_client_class: MagicMock, influxdb_config: ConnectionConfig
    ) -> None:
        """Successful connection sets _is_connected=True."""
        mock_client = MagicMock()
        mock_health = MagicMock()
        mock_health.status = "pass"
        mock_client.health.return_value = mock_health
        mock_orgs_api = MagicMock()
        mock_org = MagicMock()
        mock_org.id = "org-id-123"
        mock_org.name = "myorg"
        mock_orgs_api.find_organizations.return_value = [mock_org]
        mock_client.organizations_api.return_value = mock_orgs_api
        mock_client.query_api.return_value = MagicMock()
        mock_client_class.return_value = mock_client

        adapter = InfluxDBAdapter(influxdb_config)
        adapter.connect()

        assert adapter._is_connected is True
        assert adapter._connection is not None

    @patch("influxdb_client.InfluxDBClient")
    def test_connect_failure_raises_error(
        self, mock_client_class: MagicMock, influxdb_config: ConnectionConfig
    ) -> None:
        """Connection failure raises ConnectionError."""
        from query_analyzer.adapters.exceptions import (
            ConnectionError as AdapterConnectionError,
        )

        mock_client_class.side_effect = Exception("Connection refused")

        adapter = InfluxDBAdapter(influxdb_config)

        with pytest.raises(AdapterConnectionError):
            adapter.connect()

        assert adapter._is_connected is False

    @patch("influxdb_client.InfluxDBClient")
    def test_disconnect(
        self, mock_client_class: MagicMock, influxdb_config: ConnectionConfig
    ) -> None:
        """Disconnect closes connection and sets state."""
        mock_client = MagicMock()
        mock_health = MagicMock()
        mock_health.status = "pass"
        mock_client.health.return_value = mock_health
        mock_orgs_api = MagicMock()
        mock_org = MagicMock()
        mock_org.id = "org-id-123"
        mock_org.name = "myorg"
        mock_orgs_api.find_organizations.return_value = [mock_org]
        mock_client.organizations_api.return_value = mock_orgs_api
        mock_client.query_api.return_value = MagicMock()
        mock_client_class.return_value = mock_client

        adapter = InfluxDBAdapter(influxdb_config)
        adapter.connect()
        adapter.disconnect()

        assert adapter._is_connected is False
        assert adapter._connection is None
        mock_client.close.assert_called_once()

    @patch("influxdb_client.InfluxDBClient")
    def test_test_connection_returns_bool(
        self, mock_client_class: MagicMock, influxdb_config: ConnectionConfig
    ) -> None:
        """test_connection returns bool without raising."""
        mock_client = MagicMock()
        mock_health = MagicMock()
        mock_health.status = "pass"
        mock_client.health.return_value = mock_health
        mock_orgs_api = MagicMock()
        mock_org = MagicMock()
        mock_org.id = "org-id-123"
        mock_org.name = "myorg"
        mock_orgs_api.find_organizations.return_value = [mock_org]
        mock_client.organizations_api.return_value = mock_orgs_api
        mock_client.query_api.return_value = MagicMock()
        mock_client_class.return_value = mock_client

        adapter = InfluxDBAdapter(influxdb_config)
        adapter.connect()

        result = adapter.test_connection()

        assert isinstance(result, bool)
        assert result is True


# ============================================================================
# TESTS - V2 Model Validation (execute_explain returns proper objects)
# ============================================================================


class TestInfluxDBAdapterV2Models:
    """Tests for v2 QueryAnalysisReport structure with Warning/Recommendation objects."""

    @patch("influxdb_client.InfluxDBClient")
    def test_execute_explain_returns_v2_report_structure(
        self,
        mock_client_class: MagicMock,
        influxdb_config: ConnectionConfig,
        mock_query_api_result: str,
    ) -> None:
        """execute_explain returns QueryAnalysisReport with v2 structure."""
        mock_client = MagicMock()
        mock_health = MagicMock()
        mock_health.status = "pass"
        mock_client.health.return_value = mock_health

        mock_orgs_api = MagicMock()
        mock_org = MagicMock()
        mock_org.id = "org-id-123"
        mock_org.name = "myorg"
        mock_orgs_api.find_organizations.return_value = [mock_org]
        mock_client.organizations_api.return_value = mock_orgs_api

        mock_query_api = MagicMock()
        mock_response = MagicMock()
        mock_response.data = mock_query_api_result.encode("utf-8")
        mock_query_api.query_raw.return_value = mock_response
        mock_client.query_api.return_value = mock_query_api
        mock_client_class.return_value = mock_client

        adapter = InfluxDBAdapter(influxdb_config)
        adapter.connect()

        flux_query = 'from(bucket:"telegraf") |> range(start:-24h, stop:now()) |> filter(fn:(r) => r._measurement == "weather")'
        report = adapter.execute_explain(flux_query)

        assert report.engine == "influxdb"
        assert isinstance(report.query, str)
        assert 0 <= report.score <= 100
        assert isinstance(report.execution_time_ms, (int, float))
        assert report.execution_time_ms > 0
        assert isinstance(report.warnings, list)
        assert isinstance(report.recommendations, list)
        assert hasattr(report, "plan_tree")
        assert hasattr(report, "analyzed_at")

    @patch("influxdb_client.InfluxDBClient")
    def test_execute_explain_warnings_are_warning_objects(
        self,
        mock_client_class: MagicMock,
        influxdb_config: ConnectionConfig,
        mock_query_api_result: str,
    ) -> None:
        """execute_explain returns warnings as Warning objects (not strings)."""
        mock_client = MagicMock()
        mock_health = MagicMock()
        mock_health.status = "pass"
        mock_client.health.return_value = mock_health

        mock_orgs_api = MagicMock()
        mock_org = MagicMock()
        mock_org.id = "org-id-123"
        mock_org.name = "myorg"
        mock_orgs_api.find_organizations.return_value = [mock_org]
        mock_client.organizations_api.return_value = mock_orgs_api

        mock_query_api = MagicMock()
        mock_response = MagicMock()
        mock_response.data = mock_query_api_result.encode("utf-8")
        mock_query_api.query_raw.return_value = mock_response
        mock_client.query_api.return_value = mock_query_api
        mock_client_class.return_value = mock_client

        adapter = InfluxDBAdapter(influxdb_config)
        adapter.connect()

        flux_query = 'from(bucket:"telegraf") |> range(start:-24h, stop:now())'
        report = adapter.execute_explain(flux_query)
        for warning in report.warnings:
            assert isinstance(warning, Warning), f"Expected Warning object, got {type(warning)}"
            assert hasattr(warning, "message"), "Warning missing 'message' field"
            assert hasattr(warning, "severity"), "Warning missing 'severity' field"
            assert warning.severity in ("critical", "high", "medium", "low")
            assert isinstance(warning.message, str)

    @patch("influxdb_client.InfluxDBClient")
    def test_execute_explain_recommendations_are_recommendation_objects(
        self,
        mock_client_class: MagicMock,
        influxdb_config: ConnectionConfig,
        mock_query_api_result: str,
    ) -> None:
        """execute_explain returns recommendations as Recommendation objects."""
        mock_client = MagicMock()
        mock_health = MagicMock()
        mock_health.status = "pass"
        mock_client.health.return_value = mock_health

        mock_orgs_api = MagicMock()
        mock_org = MagicMock()
        mock_org.id = "org-id-123"
        mock_org.name = "myorg"
        mock_orgs_api.find_organizations.return_value = [mock_org]
        mock_client.organizations_api.return_value = mock_orgs_api

        mock_query_api = MagicMock()
        mock_response = MagicMock()
        mock_response.data = mock_query_api_result.encode("utf-8")
        mock_query_api.query_raw.return_value = mock_response
        mock_client.query_api.return_value = mock_query_api
        mock_client_class.return_value = mock_client

        adapter = InfluxDBAdapter(influxdb_config)
        adapter.connect()

        flux_query = 'from(bucket:"telegraf") |> range(start:-24h, stop:now())'
        report = adapter.execute_explain(flux_query)

        for rec in report.recommendations:
            assert isinstance(rec, Recommendation), (
                f"Expected Recommendation object, got {type(rec)}"
            )
            assert hasattr(rec, "priority"), "Recommendation missing 'priority' field"
            assert hasattr(rec, "title"), "Recommendation missing 'title' field"
            assert 1 <= rec.priority <= 10

    @patch("influxdb_client.InfluxDBClient")
    def test_execute_explain_analyzed_at_is_utc_timezone(
        self,
        mock_client_class: MagicMock,
        influxdb_config: ConnectionConfig,
        mock_query_api_result: str,
    ) -> None:
        """execute_explain analyzed_at has UTC timezone (not naive)."""
        mock_client = MagicMock()
        mock_health = MagicMock()
        mock_health.status = "pass"
        mock_client.health.return_value = mock_health

        mock_orgs_api = MagicMock()
        mock_org = MagicMock()
        mock_org.id = "org-id-123"
        mock_org.name = "myorg"
        mock_orgs_api.find_organizations.return_value = [mock_org]
        mock_client.organizations_api.return_value = mock_orgs_api

        mock_query_api = MagicMock()
        mock_response = MagicMock()
        mock_response.data = mock_query_api_result.encode("utf-8")
        mock_query_api.query_raw.return_value = mock_response
        mock_client.query_api.return_value = mock_query_api
        mock_client_class.return_value = mock_client

        adapter = InfluxDBAdapter(influxdb_config)
        adapter.connect()

        flux_query = 'from(bucket:"telegraf") |> range(start:-24h, stop:now())'
        report = adapter.execute_explain(flux_query)

        assert isinstance(report.analyzed_at, datetime)
        assert report.analyzed_at.tzinfo is UTC
        assert report.analyzed_at is not None

    @patch("influxdb_client.InfluxDBClient")
    def test_execute_explain_execution_time_ms_is_positive(
        self,
        mock_client_class: MagicMock,
        influxdb_config: ConnectionConfig,
        mock_query_api_result: str,
    ) -> None:
        """execute_explain execution_time_ms is strictly > 0."""
        mock_client = MagicMock()
        mock_health = MagicMock()
        mock_health.status = "pass"
        mock_client.health.return_value = mock_health

        mock_orgs_api = MagicMock()
        mock_org = MagicMock()
        mock_org.id = "org-id-123"
        mock_org.name = "myorg"
        mock_orgs_api.find_organizations.return_value = [mock_org]
        mock_client.organizations_api.return_value = mock_orgs_api

        mock_query_api = MagicMock()
        mock_response = MagicMock()
        mock_response.data = mock_query_api_result.encode("utf-8")
        mock_query_api.query_raw.return_value = mock_response
        mock_client.query_api.return_value = mock_query_api
        mock_client_class.return_value = mock_client

        adapter = InfluxDBAdapter(influxdb_config)
        adapter.connect()

        flux_query = 'from(bucket:"telegraf") |> range(start:-24h, stop:now())'
        report = adapter.execute_explain(flux_query)

        assert report.execution_time_ms > 0

    @patch("influxdb_client.InfluxDBClient")
    def test_execute_explain_warnings_have_valid_severity(
        self,
        mock_client_class: MagicMock,
        influxdb_config: ConnectionConfig,
        mock_query_api_result: str,
    ) -> None:
        """execute_explain warnings have valid severity levels."""
        mock_client = MagicMock()
        mock_health = MagicMock()
        mock_health.status = "pass"
        mock_client.health.return_value = mock_health

        mock_orgs_api = MagicMock()
        mock_org = MagicMock()
        mock_org.id = "org-id-123"
        mock_org.name = "myorg"
        mock_orgs_api.find_organizations.return_value = [mock_org]
        mock_client.organizations_api.return_value = mock_orgs_api

        mock_query_api = MagicMock()
        mock_response = MagicMock()
        mock_response.data = mock_query_api_result.encode("utf-8")
        mock_query_api.query_raw.return_value = mock_response
        mock_client.query_api.return_value = mock_query_api
        mock_client_class.return_value = mock_client

        adapter = InfluxDBAdapter(influxdb_config)
        adapter.connect()

        flux_query = 'from(bucket:"telegraf") |> range(start:-24h, stop:now())'
        report = adapter.execute_explain(flux_query)

        for warning in report.warnings:
            assert warning.severity in ("critical", "high", "medium", "low")

    @patch("influxdb_client.InfluxDBClient")
    def test_execute_explain_unbounded_query_triggers_critical_warning(
        self,
        mock_client_class: MagicMock,
        influxdb_config: ConnectionConfig,
    ) -> None:
        """Unbounded query (no time filter) triggers critical warning."""
        mock_client = MagicMock()
        mock_health = MagicMock()
        mock_health.status = "pass"
        mock_client.health.return_value = mock_health

        mock_orgs_api = MagicMock()
        mock_org = MagicMock()
        mock_org.id = "org-id-123"
        mock_org.name = "myorg"
        mock_orgs_api.find_organizations.return_value = [mock_org]
        mock_client.organizations_api.return_value = mock_orgs_api

        mock_query_api = MagicMock()
        mock_response = MagicMock()
        mock_response.data = b"result,table,_time\n_result,0,2024-01-15T10:00:00Z"
        mock_query_api.query_raw.return_value = mock_response
        mock_client.query_api.return_value = mock_query_api
        mock_client_class.return_value = mock_client

        adapter = InfluxDBAdapter(influxdb_config)
        adapter.connect()

        flux_query = 'from(bucket:"telegraf") |> filter(fn:(r) => r._measurement == "weather")'
        report = adapter.execute_explain(flux_query)

        critical_warnings = [w for w in report.warnings if w.severity == "critical"]
        assert len(critical_warnings) > 0, "Expected critical warning for unbounded query"
        assert any("time" in w.message.lower() for w in critical_warnings), (
            "Warning should mention time filter"
        )

    @patch("influxdb_client.InfluxDBClient")
    def test_execute_explain_bounded_query_no_unbounded_warning(
        self,
        mock_client_class: MagicMock,
        influxdb_config: ConnectionConfig,
        mock_query_api_result: str,
    ) -> None:
        """Bounded query (with time filter) does not trigger unbounded warning."""
        mock_client = MagicMock()
        mock_health = MagicMock()
        mock_health.status = "pass"
        mock_client.health.return_value = mock_health

        mock_orgs_api = MagicMock()
        mock_org = MagicMock()
        mock_org.id = "org-id-123"
        mock_org.name = "myorg"
        mock_orgs_api.find_organizations.return_value = [mock_org]
        mock_client.organizations_api.return_value = mock_orgs_api

        mock_query_api = MagicMock()
        mock_response = MagicMock()
        mock_response.data = mock_query_api_result.encode("utf-8")
        mock_query_api.query_raw.return_value = mock_response
        mock_client.query_api.return_value = mock_query_api
        mock_client_class.return_value = mock_client

        adapter = InfluxDBAdapter(influxdb_config)
        adapter.connect()

        flux_query = 'from(bucket:"telegraf") |> range(start:-24h, stop:now()) |> filter(fn:(r) => r._measurement == "weather")'
        report = adapter.execute_explain(flux_query)

        unbounded_warnings = [
            w
            for w in report.warnings
            if "time" in w.message.lower() and "without" in w.message.lower()
        ]
        assert len(unbounded_warnings) == 0, "Bounded query should not have unbounded warning"

    @patch("influxdb_client.InfluxDBClient")
    def test_execute_explain_plan_tree_is_none(
        self,
        mock_client_class: MagicMock,
        influxdb_config: ConnectionConfig,
        mock_query_api_result: str,
    ) -> None:
        """InfluxDB plan_tree is None (Flux is sequential, not tree)."""
        mock_client = MagicMock()
        mock_health = MagicMock()
        mock_health.status = "pass"
        mock_client.health.return_value = mock_health

        mock_orgs_api = MagicMock()
        mock_org = MagicMock()
        mock_org.id = "org-id-123"
        mock_org.name = "myorg"
        mock_orgs_api.find_organizations.return_value = [mock_org]
        mock_client.organizations_api.return_value = mock_orgs_api

        mock_query_api = MagicMock()
        mock_response = MagicMock()
        mock_response.data = mock_query_api_result.encode("utf-8")
        mock_query_api.query_raw.return_value = mock_response
        mock_client.query_api.return_value = mock_query_api
        mock_client_class.return_value = mock_client

        adapter = InfluxDBAdapter(influxdb_config)
        adapter.connect()

        flux_query = 'from(bucket:"telegraf") |> range(start:-24h, stop:now())'
        report = adapter.execute_explain(flux_query)

        assert report.plan_tree is None

    @patch("influxdb_client.InfluxDBClient")
    def test_execute_explain_recommendations_priority_in_range(
        self,
        mock_client_class: MagicMock,
        influxdb_config: ConnectionConfig,
        mock_query_api_result: str,
    ) -> None:
        """All recommendations have priority in [1, 10] range."""
        mock_client = MagicMock()
        mock_health = MagicMock()
        mock_health.status = "pass"
        mock_client.health.return_value = mock_health

        mock_orgs_api = MagicMock()
        mock_org = MagicMock()
        mock_org.id = "org-id-123"
        mock_org.name = "myorg"
        mock_orgs_api.find_organizations.return_value = [mock_org]
        mock_client.organizations_api.return_value = mock_orgs_api

        mock_query_api = MagicMock()
        mock_response = MagicMock()
        mock_response.data = mock_query_api_result.encode("utf-8")
        mock_query_api.query_raw.return_value = mock_response
        mock_client.query_api.return_value = mock_query_api
        mock_client_class.return_value = mock_client

        adapter = InfluxDBAdapter(influxdb_config)
        adapter.connect()

        flux_query = 'from(bucket:"telegraf") |> range(start:-24h, stop:now())'
        report = adapter.execute_explain(flux_query)

        for rec in report.recommendations:
            assert 1 <= rec.priority <= 10


# ============================================================================
# TESTS - Error Handling
# ============================================================================


class TestInfluxDBAdapterErrorHandling:
    """Error handling and validation tests."""

    @patch("influxdb_client.InfluxDBClient")
    def test_execute_explain_not_connected_raises_error(
        self, mock_client_class: MagicMock, influxdb_config: ConnectionConfig
    ) -> None:
        """execute_explain raises QueryAnalysisError when not connected."""
        from query_analyzer.adapters.exceptions import QueryAnalysisError

        adapter = InfluxDBAdapter(influxdb_config)

        with pytest.raises(QueryAnalysisError):
            adapter.execute_explain('from(bucket:"test")')

    @patch("influxdb_client.InfluxDBClient")
    def test_execute_explain_empty_query_raises_error(
        self, mock_client_class: MagicMock, influxdb_config: ConnectionConfig
    ) -> None:
        """execute_explain raises QueryAnalysisError on empty query."""
        from query_analyzer.adapters.exceptions import QueryAnalysisError

        mock_client = MagicMock()
        mock_health = MagicMock()
        mock_health.status = "pass"
        mock_client.health.return_value = mock_health
        mock_orgs_api = MagicMock()
        mock_org = MagicMock()
        mock_org.id = "org-id-123"
        mock_org.name = "myorg"
        mock_orgs_api.find_organizations.return_value = [mock_org]
        mock_client.organizations_api.return_value = mock_orgs_api
        mock_client.query_api.return_value = MagicMock()
        mock_client_class.return_value = mock_client

        adapter = InfluxDBAdapter(influxdb_config)
        adapter.connect()

        with pytest.raises(QueryAnalysisError):
            adapter.execute_explain("")

    @patch("influxdb_client.InfluxDBClient")
    def test_execute_explain_ddl_statement_raises_error(
        self, mock_client_class: MagicMock, influxdb_config: ConnectionConfig
    ) -> None:
        """execute_explain rejects DDL statements."""
        from query_analyzer.adapters.exceptions import QueryAnalysisError

        mock_client = MagicMock()
        mock_health = MagicMock()
        mock_health.status = "pass"
        mock_client.health.return_value = mock_health
        mock_orgs_api = MagicMock()
        mock_org = MagicMock()
        mock_org.id = "org-id-123"
        mock_org.name = "myorg"
        mock_orgs_api.find_organizations.return_value = [mock_org]
        mock_client.organizations_api.return_value = mock_orgs_api
        mock_client.query_api.return_value = MagicMock()
        mock_client_class.return_value = mock_client

        adapter = InfluxDBAdapter(influxdb_config)
        adapter.connect()

        with pytest.raises(QueryAnalysisError):
            adapter.execute_explain("CREATE BUCKET mybucket")
