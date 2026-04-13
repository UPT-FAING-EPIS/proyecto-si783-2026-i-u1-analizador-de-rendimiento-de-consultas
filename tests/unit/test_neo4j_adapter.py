"""Unit tests for Neo4j adapter."""

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from query_analyzer.adapters import (
    AdapterRegistry,
    ConnectionConfig,
    Neo4jAdapter,
)
from query_analyzer.adapters.models import Recommendation, Warning

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
            "rows": 0,
        }

        mock_result.consume.return_value = mock_summary
        mock_session.run.return_value = mock_result
        mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_driver.session.return_value.__exit__ = MagicMock(return_value=None)
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


# ============================================================================
# TESTS - V2 Model Validation (execute_explain returns proper objects)
# ============================================================================


class TestNeo4jAdapterV2Models:
    """Tests for v2 QueryAnalysisReport structure with proper Warning/Recommendation objects."""

    @pytest.fixture
    def mock_profile_result(self) -> dict:
        """Mock Neo4j PROFILE result with plan tree structure."""
        return {
            "profile": {
                "plan": {
                    "operatorType": "ProduceResults",
                    "dbHits": 0,
                    "rows": 100,
                    "children": [
                        {
                            "operatorType": "NodeIndexSeek",
                            "dbHits": 50,
                            "rows": 100,
                            "indexName": "idx_user_email",
                            "children": [],
                        }
                    ],
                },
                "stats": {"rows": 100, "time": 5, "dbHits": 50},
            }
        }

    @patch("query_analyzer.adapters.graph.neo4j.GraphDatabase.driver")
    def test_execute_explain_returns_v2_report_structure(
        self,
        mock_driver_factory: MagicMock,
        neo4j_config: ConnectionConfig,
        mock_profile_result: dict,
    ) -> None:
        """execute_explain returns QueryAnalysisReport with v2 structure."""
        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_summary = MagicMock()

        mock_summary.profile = mock_profile_result["profile"]
        mock_result.consume.return_value = mock_summary
        mock_session.run.return_value = mock_result
        mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_driver.session.return_value.__exit__ = MagicMock(return_value=None)
        mock_driver_factory.return_value = mock_driver

        adapter = Neo4jAdapter(neo4j_config)
        adapter.connect()

        report = adapter.execute_explain("MATCH (n:User {email: 'test@example.com'}) RETURN n")

        # Verify v2 report structure
        assert report.engine == "neo4j"
        assert isinstance(report.query, str)
        assert 0 <= report.score <= 100
        assert isinstance(report.execution_time_ms, (int, float))
        assert report.execution_time_ms > 0
        assert isinstance(report.warnings, list)
        assert isinstance(report.recommendations, list)
        assert hasattr(report, "plan_tree")
        assert hasattr(report, "analyzed_at")

    @patch("query_analyzer.adapters.graph.neo4j.GraphDatabase.driver")
    def test_execute_explain_warnings_are_warning_objects(
        self,
        mock_driver_factory: MagicMock,
        neo4j_config: ConnectionConfig,
        mock_profile_result: dict,
    ) -> None:
        """execute_explain returns warnings as Warning objects (not strings)."""
        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_summary = MagicMock()

        # COLLSCAN plan (no index) to trigger warning
        collscan_plan = {
            "operatorType": "ProduceResults",
            "dbHits": 0,
            "rows": 100,
            "children": [
                {
                    "operatorType": "AllNodesScan",
                    "dbHits": 100,
                    "rows": 100,
                    "children": [],
                }
            ],
        }

        mock_summary.profile = {
            "plan": collscan_plan,
            "stats": {"rows": 100, "time": 5, "dbHits": 100},
        }
        mock_result.consume.return_value = mock_summary
        mock_session.run.return_value = mock_result
        mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_driver.session.return_value.__exit__ = MagicMock(return_value=None)
        mock_driver_factory.return_value = mock_driver

        adapter = Neo4jAdapter(neo4j_config)
        adapter.connect()

        report = adapter.execute_explain("MATCH (n:User) RETURN n")

        # Verify warnings are Warning objects
        for warning in report.warnings:
            assert isinstance(warning, Warning), f"Expected Warning object, got {type(warning)}"
            assert hasattr(warning, "message"), "Warning missing 'message' field"
            assert hasattr(warning, "severity"), "Warning missing 'severity' field"
            assert warning.severity in ("critical", "high", "medium", "low")
            assert isinstance(warning.message, str)

    @patch("query_analyzer.adapters.graph.neo4j.GraphDatabase.driver")
    def test_execute_explain_recommendations_are_recommendation_objects(
        self,
        mock_driver_factory: MagicMock,
        neo4j_config: ConnectionConfig,
        mock_profile_result: dict,
    ) -> None:
        """execute_explain returns recommendations as Recommendation objects (not strings)."""
        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_summary = MagicMock()

        mock_summary.profile = mock_profile_result["profile"]
        mock_result.consume.return_value = mock_summary
        mock_session.run.return_value = mock_result
        mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_driver.session.return_value.__exit__ = MagicMock(return_value=None)
        mock_driver_factory.return_value = mock_driver

        adapter = Neo4jAdapter(neo4j_config)
        adapter.connect()

        report = adapter.execute_explain("MATCH (n:User) RETURN n")

        # Verify recommendations are Recommendation objects
        for rec in report.recommendations:
            assert isinstance(rec, Recommendation), (
                f"Expected Recommendation object, got {type(rec)}"
            )
            assert hasattr(rec, "title"), "Recommendation missing 'title' field"
            assert hasattr(rec, "description"), "Recommendation missing 'description' field"
            assert hasattr(rec, "priority"), "Recommendation missing 'priority' field"
            assert isinstance(rec.title, str)
            assert isinstance(rec.description, str)
            assert 1 <= rec.priority <= 10

    @patch("query_analyzer.adapters.graph.neo4j.GraphDatabase.driver")
    def test_execute_explain_plan_tree_structure(
        self,
        mock_driver_factory: MagicMock,
        neo4j_config: ConnectionConfig,
        mock_profile_result: dict,
    ) -> None:
        """execute_explain builds PlanNode tree from Neo4j plan."""
        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_summary = MagicMock()

        # Properly set up the mock to return our profile result dict
        mock_summary.profile = mock_profile_result["profile"]
        mock_result.consume.return_value = mock_summary
        mock_session.run.return_value = mock_result
        mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_driver.session.return_value.__exit__ = MagicMock(return_value=None)
        mock_driver_factory.return_value = mock_driver

        adapter = Neo4jAdapter(neo4j_config)
        adapter.connect()

        report = adapter.execute_explain("MATCH (n:User) RETURN n")

        # Verify plan_tree exists and has PlanNode structure
        assert report.plan_tree is not None
        assert hasattr(report.plan_tree, "node_type")
        assert hasattr(report.plan_tree, "children")
        assert hasattr(report.plan_tree, "properties")
        assert report.plan_tree.node_type in (
            "ProduceResults",
            "NodeIndexSeek",
            "AllNodesScan",
            "Filter",
        )
        # Root should have children
        assert isinstance(report.plan_tree.children, list)

    @patch("query_analyzer.adapters.graph.neo4j.GraphDatabase.driver")
    def test_execute_explain_analyzed_at_is_utc(
        self,
        mock_driver_factory: MagicMock,
        neo4j_config: ConnectionConfig,
        mock_profile_result: dict,
    ) -> None:
        """execute_explain sets analyzed_at with UTC timezone."""
        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_summary = MagicMock()

        mock_summary.profile = mock_profile_result["profile"]
        mock_result.consume.return_value = mock_summary
        mock_session.run.return_value = mock_result
        mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_driver.session.return_value.__exit__ = MagicMock(return_value=None)
        mock_driver_factory.return_value = mock_driver

        adapter = Neo4jAdapter(neo4j_config)
        adapter.connect()

        report = adapter.execute_explain("MATCH (n:User) RETURN n")

        # Verify analyzed_at is set and is UTC
        assert report.analyzed_at is not None
        assert isinstance(report.analyzed_at, datetime)
        assert report.analyzed_at.tzinfo == UTC
