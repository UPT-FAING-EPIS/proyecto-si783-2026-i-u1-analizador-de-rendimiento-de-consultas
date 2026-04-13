"""Unit tests for MongoDB adapter."""

import json
from unittest.mock import MagicMock, patch

import pytest

from query_analyzer.adapters import (
    AdapterRegistry,
    ConnectionConfig,
    MongoDBAdapter,  # This import triggers @AdapterRegistry.register decorator
    Recommendation,
    Warning,
)

# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def mongo_config() -> ConnectionConfig:
    """Valid MongoDB connection config."""
    return ConnectionConfig(
        engine="mongodb",
        host="localhost",
        port=27017,
        database="test_db",
        username="admin",
        password="password",
        extra={"authSource": "admin"},
    )


@pytest.fixture
def mock_explain_result() -> dict:
    """Mock MongoDB explain output with execution stats."""
    return {
        "executionStats": {
            "executionStages": {
                "stage": "COLLSCAN",
                "nReturned": 100,
                "totalDocsExamined": 10000,
                "totalKeysExamined": 0,
                "executionTimeMillis": 50,
            },
            "nReturned": 100,
            "totalDocsExamined": 10000,
            "totalKeysExamined": 0,
            "executionTimeMillis": 50,
        },
        "queryPlanner": {
            "winningPlan": {
                "stage": "COLLSCAN",
                "filter": {"age": {"$gt": 18}},
            }
        },
    }


@pytest.fixture
def mock_explain_with_index() -> dict:
    """Mock MongoDB explain output with index scan."""
    return {
        "executionStats": {
            "executionStages": {
                "stage": "FETCH",
                "inputStage": {"stage": "IXSCAN", "indexName": "age_1"},
                "nReturned": 50,
                "totalDocsExamined": 50,
                "totalKeysExamined": 50,
                "executionTimeMillis": 10,
            },
            "nReturned": 50,
            "totalDocsExamined": 50,
            "totalKeysExamined": 50,
            "executionTimeMillis": 10,
        },
        "queryPlanner": {
            "winningPlan": {
                "stage": "FETCH",
                "inputStage": {
                    "stage": "IXSCAN",
                    "indexName": "age_1",
                    "keyPattern": {"age": 1},
                },
            }
        },
    }


# ============================================================================
# TESTS - Instantiation & Registry
# ============================================================================


class TestMongoDBAdapterInstantiation:
    """MongoDB adapter creation and initialization."""

    def test_instantiate_with_valid_config(self, mongo_config: ConnectionConfig) -> None:
        """Create MongoDB adapter with valid config."""
        adapter = MongoDBAdapter(mongo_config)

        assert adapter._config == mongo_config
        assert adapter._is_connected is False
        assert adapter._client is None
        assert adapter._db is None

    def test_registry_can_create_mongodb_adapter(self, mongo_config: ConnectionConfig) -> None:
        """Registry factory creates MongoDB adapter."""
        adapter = AdapterRegistry.create("mongodb", mongo_config)

        assert isinstance(adapter, MongoDBAdapter)
        assert adapter._config == mongo_config

    def test_registry_case_insensitive(self, mongo_config: ConnectionConfig) -> None:
        """Registry lookup is case-insensitive."""
        adapter1 = AdapterRegistry.create("mongodb", mongo_config)
        adapter2 = AdapterRegistry.create("MongoDB", mongo_config)
        adapter3 = AdapterRegistry.create("MONGODB", mongo_config)

        assert isinstance(adapter1, MongoDBAdapter)
        assert isinstance(adapter2, MongoDBAdapter)
        assert isinstance(adapter3, MongoDBAdapter)


# ============================================================================
# TESTS - Connection Management
# ============================================================================


class TestMongoDBAdapterConnection:
    """Connection lifecycle tests."""

    @patch("query_analyzer.adapters.nosql.mongodb.MongoClient")
    def test_connect_success(
        self, mock_mongo_client_class: MagicMock, mongo_config: ConnectionConfig
    ) -> None:
        """Successful connection sets _is_connected=True."""
        mock_client = MagicMock()
        mock_mongo_client_class.return_value = mock_client
        mock_client.admin.command.return_value = {"ok": 1}
        mock_client.__getitem__ = MagicMock(return_value=MagicMock())

        adapter = MongoDBAdapter(mongo_config)
        adapter.connect()

        assert adapter._is_connected is True
        assert adapter._client == mock_client

    @patch("query_analyzer.adapters.nosql.mongodb.MongoClient")
    def test_connect_failure(
        self, mock_mongo_client_class: MagicMock, mongo_config: ConnectionConfig
    ) -> None:
        """Connection failure raises ConnectionError."""
        from pymongo.errors import ServerSelectionTimeoutError

        mock_mongo_client_class.side_effect = ServerSelectionTimeoutError("Connection refused")

        adapter = MongoDBAdapter(mongo_config)

        with pytest.raises(Exception):
            adapter.connect()

        assert adapter._is_connected is False
        assert adapter._client is None

    @patch("query_analyzer.adapters.nosql.mongodb.MongoClient")
    def test_disconnect_cleanup(
        self, mock_mongo_client_class: MagicMock, mongo_config: ConnectionConfig
    ) -> None:
        """Disconnection closes connection and sets state."""
        mock_client = MagicMock()
        mock_mongo_client_class.return_value = mock_client
        mock_client.admin.command.return_value = {"ok": 1}
        mock_client.__getitem__ = MagicMock(return_value=MagicMock())

        adapter = MongoDBAdapter(mongo_config)
        adapter.connect()
        assert adapter._is_connected is True

        adapter.disconnect()

        assert adapter._is_connected is False
        assert adapter._client is not None  # Object still exists but connection closed
        mock_client.close.assert_called_once()

    @patch("query_analyzer.adapters.nosql.mongodb.MongoClient")
    def test_context_manager(
        self, mock_mongo_client_class: MagicMock, mongo_config: ConnectionConfig
    ) -> None:
        """Context manager connects and disconnects."""
        mock_client = MagicMock()
        mock_mongo_client_class.return_value = mock_client
        mock_client.admin.command.return_value = {"ok": 1}
        mock_client.__getitem__ = MagicMock(return_value=MagicMock())

        adapter = MongoDBAdapter(mongo_config)

        with adapter:
            assert adapter._is_connected is True

        assert adapter._is_connected is False
        mock_client.close.assert_called_once()


# ============================================================================
# TESTS - Connection Testing
# ============================================================================


class TestMongoDBAdapterConnectionTest:
    """Connection test method tests."""

    @patch("query_analyzer.adapters.nosql.mongodb.MongoClient")
    def test_test_connection_success(
        self, mock_mongo_client_class: MagicMock, mongo_config: ConnectionConfig
    ) -> None:
        """test_connection returns True when connected."""
        mock_client = MagicMock()
        mock_mongo_client_class.return_value = mock_client
        mock_client.admin.command.return_value = {"ok": 1}
        mock_client.__getitem__ = MagicMock(return_value=MagicMock())

        adapter = MongoDBAdapter(mongo_config)
        adapter.connect()
        result = adapter.test_connection()

        assert result is True

    def test_test_connection_not_connected(self, mongo_config: ConnectionConfig) -> None:
        """test_connection returns False when not connected."""
        adapter = MongoDBAdapter(mongo_config)
        result = adapter.test_connection()

        assert result is False

    @patch("query_analyzer.adapters.nosql.mongodb.MongoClient")
    def test_test_connection_failure(
        self, mock_mongo_client_class: MagicMock, mongo_config: ConnectionConfig
    ) -> None:
        """test_connection returns False on exception."""
        from query_analyzer.adapters.exceptions import ConnectionError as AdapterConnectionError

        mock_client = MagicMock()
        mock_mongo_client_class.return_value = mock_client
        mock_client.admin.command.side_effect = Exception("Command error")
        mock_client.__getitem__ = MagicMock(return_value=MagicMock())

        adapter = MongoDBAdapter(mongo_config)

        # Connection itself will raise due to ping command failure
        with pytest.raises(AdapterConnectionError):
            adapter.connect()

        assert adapter._is_connected is False


# ============================================================================
# TESTS - EXPLAIN Analysis & Report Structure (v2 Models)
# ============================================================================


class TestMongoDBAdapterExplain:
    """EXPLAIN query analysis tests - v2 model validation."""

    @patch("query_analyzer.adapters.nosql.mongodb.MongoClient")
    def test_execute_explain_not_connected(
        self, mock_mongo_client_class: MagicMock, mongo_config: ConnectionConfig
    ) -> None:
        """execute_explain raises error if not connected."""
        adapter = MongoDBAdapter(mongo_config)

        query_json = json.dumps({"collection": "users", "filter": {"age": {"$gt": 18}}})

        with pytest.raises(Exception):
            adapter.execute_explain(query_json)

    @patch("query_analyzer.adapters.nosql.mongodb.MongoClient")
    def test_execute_explain_invalid_json(
        self, mock_mongo_client_class: MagicMock, mongo_config: ConnectionConfig
    ) -> None:
        """execute_explain rejects invalid JSON."""
        mock_client = MagicMock()
        mock_mongo_client_class.return_value = mock_client
        mock_client.admin.command.return_value = {"ok": 1}
        mock_client.__getitem__ = MagicMock(return_value=MagicMock())

        adapter = MongoDBAdapter(mongo_config)
        adapter.connect()

        with pytest.raises(Exception) as exc_info:
            adapter.execute_explain("not valid json")

        assert "JSON" in str(exc_info.value) or "json" in str(exc_info.value)

    @patch("query_analyzer.adapters.nosql.mongodb.MongoClient")
    def test_execute_explain_missing_collection(
        self, mock_mongo_client_class: MagicMock, mongo_config: ConnectionConfig
    ) -> None:
        """execute_explain requires 'collection' field."""
        mock_client = MagicMock()
        mock_mongo_client_class.return_value = mock_client
        mock_client.admin.command.return_value = {"ok": 1}
        mock_client.__getitem__ = MagicMock(return_value=MagicMock())

        adapter = MongoDBAdapter(mongo_config)
        adapter.connect()

        query_json = json.dumps({"filter": {"age": {"$gt": 18}}})

        with pytest.raises(Exception) as exc_info:
            adapter.execute_explain(query_json)

        assert "collection" in str(exc_info.value)

    @patch("query_analyzer.adapters.nosql.mongodb.MongoClient")
    def test_execute_explain_returns_v2_report_structure(
        self,
        mock_mongo_client_class: MagicMock,
        mongo_config: ConnectionConfig,
        mock_explain_result: dict,
    ) -> None:
        """execute_explain returns QueryAnalysisReport v2 with proper structure."""
        mock_client = MagicMock()
        mock_mongo_client_class.return_value = mock_client
        mock_client.admin.command.return_value = {"ok": 1}

        mock_db = MagicMock()
        mock_client.__getitem__ = MagicMock(return_value=mock_db)

        mock_collection = MagicMock()
        mock_db.__getitem__ = MagicMock(return_value=mock_collection)

        mock_cursor = MagicMock()
        mock_cursor.explain.return_value = mock_explain_result
        mock_cursor.sort.return_value = mock_cursor
        mock_cursor.limit.return_value = mock_cursor
        mock_collection.find.return_value = mock_cursor

        adapter = MongoDBAdapter(mongo_config)
        adapter.connect()

        query_json = json.dumps({"collection": "users", "filter": {"age": {"$gt": 18}}})
        report = adapter.execute_explain(query_json)

        # Validate v2 structure
        assert report.engine == "mongodb"
        assert report.query == query_json
        assert isinstance(report.score, (int, float))
        assert 0 <= report.score <= 100
        assert report.execution_time_ms > 0
        assert isinstance(report.warnings, list)
        assert isinstance(report.recommendations, list)
        assert report.analyzed_at is not None

    @patch("query_analyzer.adapters.nosql.mongodb.MongoClient")
    def test_execute_explain_warnings_are_warning_objects(
        self,
        mock_mongo_client_class: MagicMock,
        mongo_config: ConnectionConfig,
        mock_explain_result: dict,
    ) -> None:
        """execute_explain returns warnings as Warning objects (not strings)."""
        mock_client = MagicMock()
        mock_mongo_client_class.return_value = mock_client
        mock_client.admin.command.return_value = {"ok": 1}

        mock_db = MagicMock()
        mock_client.__getitem__ = MagicMock(return_value=mock_db)

        mock_collection = MagicMock()
        mock_db.__getitem__ = MagicMock(return_value=mock_collection)

        mock_cursor = MagicMock()
        mock_cursor.explain.return_value = mock_explain_result
        mock_cursor.sort.return_value = mock_cursor
        mock_cursor.limit.return_value = mock_cursor
        mock_collection.find.return_value = mock_cursor

        adapter = MongoDBAdapter(mongo_config)
        adapter.connect()

        query_json = json.dumps({"collection": "users", "filter": {"age": {"$gt": 18}}})
        report = adapter.execute_explain(query_json)

        # Verify warnings are Warning objects
        for warning in report.warnings:
            assert isinstance(warning, Warning)
            assert hasattr(warning, "severity")
            assert hasattr(warning, "message")
            assert warning.severity in ("critical", "high", "medium", "low")
            assert isinstance(warning.message, str)

    @patch("query_analyzer.adapters.nosql.mongodb.MongoClient")
    def test_execute_explain_recommendations_are_recommendation_objects(
        self,
        mock_mongo_client_class: MagicMock,
        mongo_config: ConnectionConfig,
        mock_explain_result: dict,
    ) -> None:
        """execute_explain returns recommendations as Recommendation objects (not strings)."""
        mock_client = MagicMock()
        mock_mongo_client_class.return_value = mock_client
        mock_client.admin.command.return_value = {"ok": 1}

        mock_db = MagicMock()
        mock_client.__getitem__ = MagicMock(return_value=mock_db)

        mock_collection = MagicMock()
        mock_db.__getitem__ = MagicMock(return_value=mock_collection)

        mock_cursor = MagicMock()
        mock_cursor.explain.return_value = mock_explain_result
        mock_cursor.sort.return_value = mock_cursor
        mock_cursor.limit.return_value = mock_cursor
        mock_collection.find.return_value = mock_cursor

        adapter = MongoDBAdapter(mongo_config)
        adapter.connect()

        query_json = json.dumps({"collection": "users", "filter": {"age": {"$gt": 18}}})
        report = adapter.execute_explain(query_json)

        # Verify recommendations are Recommendation objects
        for rec in report.recommendations:
            assert isinstance(rec, Recommendation)
            assert hasattr(rec, "priority")
            assert hasattr(rec, "title")
            assert hasattr(rec, "description")
            assert 1 <= rec.priority <= 10
            assert isinstance(rec.title, str)
            assert isinstance(rec.description, str)

    @patch("query_analyzer.adapters.nosql.mongodb.MongoClient")
    def test_execute_explain_plan_tree_structure(
        self,
        mock_mongo_client_class: MagicMock,
        mongo_config: ConnectionConfig,
        mock_explain_with_index: dict,
    ) -> None:
        """execute_explain builds PlanNode tree from MongoDB stages."""
        mock_client = MagicMock()
        mock_mongo_client_class.return_value = mock_client
        mock_client.admin.command.return_value = {"ok": 1}

        mock_db = MagicMock()
        mock_client.__getitem__ = MagicMock(return_value=mock_db)

        mock_collection = MagicMock()
        mock_db.__getitem__ = MagicMock(return_value=mock_collection)

        mock_cursor = MagicMock()
        mock_cursor.explain.return_value = mock_explain_with_index
        mock_cursor.sort.return_value = mock_cursor
        mock_cursor.limit.return_value = mock_cursor
        mock_collection.find.return_value = mock_cursor

        adapter = MongoDBAdapter(mongo_config)
        adapter.connect()

        query_json = json.dumps(
            {"collection": "users", "filter": {"age": {"$gt": 18}}, "sort": {"age": 1}}
        )
        report = adapter.execute_explain(query_json)

        # Verify plan_tree exists and has PlanNode structure
        assert report.plan_tree is not None
        assert hasattr(report.plan_tree, "node_type")
        assert hasattr(report.plan_tree, "children")
        assert report.plan_tree.node_type in ("Fetch", "Index Scan", "Collection Scan", "Sort")

    @patch("query_analyzer.adapters.nosql.mongodb.MongoClient")
    def test_execute_explain_collscan_detection(
        self,
        mock_mongo_client_class: MagicMock,
        mongo_config: ConnectionConfig,
        mock_explain_result: dict,
    ) -> None:
        """execute_explain detects COLLSCAN anti-pattern as warning."""
        mock_client = MagicMock()
        mock_mongo_client_class.return_value = mock_client
        mock_client.admin.command.return_value = {"ok": 1}

        mock_db = MagicMock()
        mock_client.__getitem__ = MagicMock(return_value=mock_db)

        mock_collection = MagicMock()
        mock_db.__getitem__ = MagicMock(return_value=mock_collection)

        mock_cursor = MagicMock()
        mock_cursor.explain.return_value = mock_explain_result
        mock_cursor.sort.return_value = mock_cursor
        mock_cursor.limit.return_value = mock_cursor
        mock_collection.find.return_value = mock_cursor

        adapter = MongoDBAdapter(mongo_config)
        adapter.connect()

        query_json = json.dumps({"collection": "users", "filter": {"age": {"$gt": 18}}})
        report = adapter.execute_explain(query_json)

        # Should have warnings due to COLLSCAN + high examination ratio
        assert len(report.warnings) > 0
        # Check that at least one warning mentions collection scan or index
        assert any(
            "collection" in w.message.lower() or "index" in w.message.lower()
            for w in report.warnings
        )

    @patch("query_analyzer.adapters.nosql.mongodb.MongoClient")
    def test_execute_explain_index_scan_better_score(
        self,
        mock_mongo_client_class: MagicMock,
        mongo_config: ConnectionConfig,
        mock_explain_with_index: dict,
        mock_explain_result: dict,
    ) -> None:
        """execute_explain gives better score for indexed queries."""
        mock_client = MagicMock()
        mock_mongo_client_class.return_value = mock_client
        mock_client.admin.command.return_value = {"ok": 1}

        mock_db = MagicMock()
        mock_client.__getitem__ = MagicMock(return_value=mock_db)

        mock_collection = MagicMock()
        mock_db.__getitem__ = MagicMock(return_value=mock_collection)

        # Test with index
        mock_cursor_indexed = MagicMock()
        mock_cursor_indexed.explain.return_value = mock_explain_with_index
        mock_cursor_indexed.sort.return_value = mock_cursor_indexed
        mock_cursor_indexed.limit.return_value = mock_cursor_indexed

        # Test with collection scan
        mock_cursor_collscan = MagicMock()
        mock_cursor_collscan.explain.return_value = mock_explain_result
        mock_cursor_collscan.sort.return_value = mock_cursor_collscan
        mock_cursor_collscan.limit.return_value = mock_cursor_collscan

        def side_effect(*args, **kwargs):
            # Return different cursors based on call
            return (
                mock_cursor_indexed
                if hasattr(mock_cursor_indexed, "_test")
                else mock_cursor_collscan
            )

        mock_db.__getitem__.side_effect = lambda name: mock_collection

        adapter = MongoDBAdapter(mongo_config)
        adapter.connect()

        # First query with index
        mock_collection.find.return_value = mock_cursor_indexed
        query_indexed = json.dumps(
            {"collection": "users", "filter": {"age": {"$gt": 18}}, "sort": {"age": 1}}
        )
        report_indexed = adapter.execute_explain(query_indexed)
        score_indexed = report_indexed.score

        # Second query with collection scan
        mock_collection.find.return_value = mock_cursor_collscan
        query_collscan = json.dumps({"collection": "users", "filter": {"age": {"$gt": 18}}})
        report_collscan = adapter.execute_explain(query_collscan)
        score_collscan = report_collscan.score

        # Indexed should score better or equal
        assert score_indexed >= score_collscan


# ============================================================================
# TESTS - Metrics
# ============================================================================


class TestMongoDBAdapterMetrics:
    """Metrics extraction and validation tests."""

    @patch("query_analyzer.adapters.nosql.mongodb.MongoClient")
    def test_get_metrics_returns_dict(
        self, mock_mongo_client_class: MagicMock, mongo_config: ConnectionConfig
    ) -> None:
        """get_metrics returns engine metrics."""
        mock_client = MagicMock()
        mock_mongo_client_class.return_value = mock_client
        mock_client.server_info.return_value = {
            "version": "5.0.0",
            "os": {"type": "Linux"},
        }

        adapter = MongoDBAdapter(mongo_config)
        adapter._client = mock_client

        metrics = adapter.get_metrics()

        assert isinstance(metrics, dict)
        assert "version" in metrics
        assert metrics["version"] == "5.0.0"

    @patch("query_analyzer.adapters.nosql.mongodb.MongoClient")
    def test_get_engine_info_returns_dict(
        self, mock_mongo_client_class: MagicMock, mongo_config: ConnectionConfig
    ) -> None:
        """get_engine_info returns engine info."""
        mock_client = MagicMock()
        mock_mongo_client_class.return_value = mock_client
        mock_client.server_info.return_value = {
            "version": "5.0.0",
            "os": {"type": "Linux"},
        }

        adapter = MongoDBAdapter(mongo_config)
        adapter._client = mock_client

        info = adapter.get_engine_info()

        assert isinstance(info, dict)
        assert info["engine"] == "mongodb"
        assert info["driver"] == "pymongo"
        assert "version" in info
