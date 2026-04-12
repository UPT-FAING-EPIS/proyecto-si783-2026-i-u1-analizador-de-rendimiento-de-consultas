"""Unit tests for Neo4j adapter."""

from unittest.mock import MagicMock, patch

import pytest

from query_analyzer.adapters import (
    AdapterRegistry,
    ConnectionConfig,
    Neo4jAdapter,
)

# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def neo4j_config() -> ConnectionConfig:
    """Valid Neo4j connection config."""
    return ConnectionConfig(
        engine="neo4j",
        host="localhost",
        port=7687,
        database="neo4j",
        username="neo4j",
        password="neo4j123",
        extra={"expand_threshold": 1000},
    )


# ============================================================================
# TESTS - Instantiation & Registry
# ============================================================================


class TestNeo4jAdapterInstantiation:
    """Neo4j adapter creation and initialization."""

    def test_instantiate_with_valid_config(self, neo4j_config: ConnectionConfig) -> None:
        """Create Neo4j adapter with valid config."""
        adapter = Neo4jAdapter(neo4j_config)

        assert adapter._config == neo4j_config
        assert adapter._is_connected is False
        assert adapter._connection is None
        # Check that parser and metrics_helper are initialized
        assert hasattr(adapter, "parser")
        assert hasattr(adapter, "metrics_helper")

    def test_registry_can_create_neo4j_adapter(self, neo4j_config: ConnectionConfig) -> None:
        """Registry factory creates Neo4j adapter."""
        adapter = AdapterRegistry.create("neo4j", neo4j_config)

        assert isinstance(adapter, Neo4jAdapter)
        assert adapter._config == neo4j_config

    def test_registry_case_insensitive(self, neo4j_config: ConnectionConfig) -> None:
        """Registry lookup is case-insensitive."""
        adapter1 = AdapterRegistry.create("neo4j", neo4j_config)
        adapter2 = AdapterRegistry.create("Neo4j", neo4j_config)
        adapter3 = AdapterRegistry.create("NEO4J", neo4j_config)

        assert isinstance(adapter1, Neo4jAdapter)
        assert isinstance(adapter2, Neo4jAdapter)
        assert isinstance(adapter3, Neo4jAdapter)

    def test_adapter_inherits_expand_threshold(self, neo4j_config: ConnectionConfig) -> None:
        """Adapter uses configurable expand_threshold."""
        config_custom = ConnectionConfig(
            engine="neo4j",
            host="localhost",
            port=7687,
            database="neo4j",
            username="neo4j",
            password="neo4j123",
            extra={"expand_threshold": 500},
        )

        adapter = Neo4jAdapter(config_custom)
        assert hasattr(adapter, "parser")
        assert adapter.parser.expand_threshold == 500


# ============================================================================
# TESTS - Connection Management
# ============================================================================


class TestNeo4jAdapterConnection:
    """Connection lifecycle tests."""

    @patch("query_analyzer.adapters.graph.neo4j.GraphDatabase.driver")
    def test_connect_success(
        self, mock_driver_factory: MagicMock, neo4j_config: ConnectionConfig
    ) -> None:
        """Successful connection sets _is_connected=True."""
        # Mock driver and session
        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_driver.session.return_value = mock_session
        mock_driver_factory.return_value = mock_driver

        adapter = Neo4jAdapter(neo4j_config)
        adapter.connect()

        assert adapter._is_connected is True
        assert adapter._connection is not None
        mock_driver_factory.assert_called_once()

    @patch("query_analyzer.adapters.graph.neo4j.GraphDatabase.driver")
    def test_connect_failure(
        self, mock_driver_factory: MagicMock, neo4j_config: ConnectionConfig
    ) -> None:
        """Connection failure raises ConnectionError."""
        from neo4j.exceptions import ServiceUnavailable

        mock_driver_factory.side_effect = ServiceUnavailable("Connection refused")

        adapter = Neo4jAdapter(neo4j_config)

        from query_analyzer.adapters.exceptions import ConnectionError as AdapterConnectionError

        with pytest.raises(AdapterConnectionError):
            adapter.connect()

        assert adapter._is_connected is False

    @patch("query_analyzer.adapters.graph.neo4j.GraphDatabase.driver")
    def test_disconnect(
        self, mock_driver_factory: MagicMock, neo4j_config: ConnectionConfig
    ) -> None:
        """Disconnect closes driver and sets state."""
        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_driver.session.return_value = mock_session
        mock_driver_factory.return_value = mock_driver

        adapter = Neo4jAdapter(neo4j_config)
        adapter.connect()
        adapter.disconnect()

        assert adapter._is_connected is False
        assert adapter._connection is None
        mock_driver.close.assert_called_once()

    @patch("query_analyzer.adapters.graph.neo4j.GraphDatabase.driver")
    def test_test_connection_success(
        self, mock_driver_factory: MagicMock, neo4j_config: ConnectionConfig
    ) -> None:
        """test_connection() returns True when connected."""
        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_driver.session.return_value = mock_session
        mock_driver_factory.return_value = mock_driver

        adapter = Neo4jAdapter(neo4j_config)
        adapter.connect()

        assert adapter.test_connection() is True

    def test_test_connection_not_connected(self, neo4j_config: ConnectionConfig) -> None:
        """test_connection() returns False when not connected."""
        adapter = Neo4jAdapter(neo4j_config)
        assert adapter.test_connection() is False


# ============================================================================
# TESTS - Query Validation
# ============================================================================


class TestNeo4jQueryValidation:
    """Query validation tests."""

    @patch("query_analyzer.adapters.graph.neo4j.GraphDatabase.driver")
    def test_reject_ddl_create_index(
        self, mock_driver_factory: MagicMock, neo4j_config: ConnectionConfig
    ) -> None:
        """Reject CREATE INDEX queries."""
        from query_analyzer.adapters.exceptions import QueryAnalysisError

        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_driver.session.return_value = mock_session
        mock_driver_factory.return_value = mock_driver

        adapter = Neo4jAdapter(neo4j_config)
        adapter.connect()

        with pytest.raises(QueryAnalysisError):
            adapter.execute_explain("CREATE INDEX idx_name FOR (n:User) ON (n.email)")

    @patch("query_analyzer.adapters.graph.neo4j.GraphDatabase.driver")
    def test_reject_ddl_drop(
        self, mock_driver_factory: MagicMock, neo4j_config: ConnectionConfig
    ) -> None:
        """Reject DROP queries."""
        from query_analyzer.adapters.exceptions import QueryAnalysisError

        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_driver.session.return_value = mock_session
        mock_driver_factory.return_value = mock_driver

        adapter = Neo4jAdapter(neo4j_config)
        adapter.connect()

        with pytest.raises(QueryAnalysisError):
            adapter.execute_explain("DROP INDEX idx_name")

    @patch("query_analyzer.adapters.graph.neo4j.GraphDatabase.driver")
    def test_accept_valid_match_query(
        self, mock_driver_factory: MagicMock, neo4j_config: ConnectionConfig
    ) -> None:
        """Accept MATCH queries (basic validation passes)."""
        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_summary = MagicMock()

        # Mock the PROFILE result structure
        mock_summary.profile = {
            "operatorType": "ProduceResults",
            "dbHits": 0,
            "children": [],
        }
        mock_summary.counters = MagicMock()
        mock_summary.counters.rows_written = 0
        mock_summary.result_available_after = 0
        mock_summary.result_consumed_after = 5

        mock_result.consume.return_value = mock_summary
        mock_session.run.return_value = mock_result
        mock_driver.session.return_value = mock_session
        mock_driver_factory.return_value = mock_driver

        adapter = Neo4jAdapter(neo4j_config)
        adapter.connect()

        # This should not raise
        report = adapter.execute_explain("MATCH (n:User) RETURN n")
        assert report.engine == "neo4j"


# ============================================================================
# TESTS - Metrics & Info
# ============================================================================


class TestNeo4jMetrics:
    """Metrics and engine info tests."""

    @patch("query_analyzer.adapters.graph.neo4j.GraphDatabase.driver")
    def test_get_engine_info_returns_dict(
        self, mock_driver_factory: MagicMock, neo4j_config: ConnectionConfig
    ) -> None:
        """get_engine_info returns dict with engine key."""
        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_driver.session.return_value = mock_session
        mock_driver_factory.return_value = mock_driver

        adapter = Neo4jAdapter(neo4j_config)
        adapter.connect()

        info = adapter.get_engine_info()

        assert isinstance(info, dict)
        assert info.get("engine") == "neo4j"

    @patch("query_analyzer.adapters.graph.neo4j.GraphDatabase.driver")
    def test_get_metrics_returns_dict(
        self, mock_driver_factory: MagicMock, neo4j_config: ConnectionConfig
    ) -> None:
        """get_metrics returns dict."""
        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_driver.session.return_value = mock_session
        mock_driver_factory.return_value = mock_driver

        adapter = Neo4jAdapter(neo4j_config)
        adapter.connect()

        metrics = adapter.get_metrics()

        assert isinstance(metrics, dict)

    @patch("query_analyzer.adapters.graph.neo4j.GraphDatabase.driver")
    def test_get_slow_queries_returns_empty_list(
        self, mock_driver_factory: MagicMock, neo4j_config: ConnectionConfig
    ) -> None:
        """get_slow_queries returns empty list (Neo4j doesn't support)."""
        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_driver.session.return_value = mock_session
        mock_driver_factory.return_value = mock_driver

        adapter = Neo4jAdapter(neo4j_config)
        adapter.connect()

        slow_queries = adapter.get_slow_queries(1000)

        assert isinstance(slow_queries, list)
        assert len(slow_queries) == 0
