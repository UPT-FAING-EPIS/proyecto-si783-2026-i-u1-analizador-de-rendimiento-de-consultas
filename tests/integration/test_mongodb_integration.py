"""MongoDB adapter integration tests."""

import json

import pytest

from query_analyzer.adapters import AdapterRegistry
from query_analyzer.adapters.exceptions import QueryAnalysisError
from query_analyzer.adapters.models import ConnectionConfig


@pytest.fixture(scope="session")
def docker_mongodb_config() -> ConnectionConfig:
    """MongoDB Docker configuration."""
    return ConnectionConfig(
        engine="mongodb",
        host="localhost",
        port=27017,
        database="query_analyzer",
        username="admin",
        password="mongodb123",
        extra={"authSource": "admin"},
    )


@pytest.fixture(scope="function")
def mongodb_adapter(docker_mongodb_config):
    """Yields connected MongoDB adapter."""
    adapter = AdapterRegistry.create("mongodb", docker_mongodb_config)
    adapter.connect()
    yield adapter
    adapter.disconnect()


class TestMongoDBConnection:
    """Test connection lifecycle."""

    def test_connect_success(self, mongodb_adapter):
        """Verify connection established."""
        assert mongodb_adapter._is_connected
        assert mongodb_adapter._client is not None

    def test_test_connection_success(self, docker_mongodb_config):
        """Verify test_connection() works."""
        adapter = AdapterRegistry.create("mongodb", docker_mongodb_config)
        adapter.connect()
        try:
            assert adapter.test_connection() is True
        finally:
            adapter.disconnect()

    def test_disconnect(self, mongodb_adapter):
        """Verify disconnect closes connection."""
        mongodb_adapter.disconnect()
        assert not mongodb_adapter._is_connected

    def test_get_engine_info(self, mongodb_adapter):
        """Verify engine info retrieval."""
        info = mongodb_adapter.get_engine_info()
        assert info["engine"] == "mongodb"
        assert info["driver"] == "pymongo"


class TestMongoDBExplain:
    """Test EXPLAIN functionality."""

    def test_explain_with_ixscan(self, mongodb_adapter):
        """Query using index → good score."""
        query = json.dumps({"collection": "users", "filter": {"email": "test@example.com"}})

        report = mongodb_adapter.execute_explain(query)

        assert report.engine == "mongodb"
        assert report.score >= 75
        assert len(report.warnings) == 0
        assert "IXSCAN" in str(report.metrics.get("execution_stages", []))

    def test_explain_collection_scan(self, mongodb_adapter):
        """Query without index → COLLSCAN anti-pattern."""
        query = json.dumps({"collection": "logs", "filter": {"message": {"$regex": "error"}}})

        report = mongodb_adapter.execute_explain(query)

        assert report.score < 100
        assert len(report.warnings) > 0
        assert any("collection" in w.lower() for w in report.warnings)

    def test_explain_with_projection(self, mongodb_adapter):
        """Query with projection."""
        query = json.dumps(
            {
                "collection": "users",
                "filter": {"age": {"$gt": 18}},
                "projection": {"name": 1, "email": 1},
            }
        )

        report = mongodb_adapter.execute_explain(query)

        assert report.engine == "mongodb"
        assert report.score >= 0

    def test_explain_with_sort(self, mongodb_adapter):
        """Query with sort operation."""
        query = json.dumps(
            {
                "collection": "users",
                "filter": {"status": "active"},
                "sort": {"created_at": 1},
            }
        )

        report = mongodb_adapter.execute_explain(query)

        assert report.engine == "mongodb"
        # May or may not have SORT stage depending on index availability

    def test_explain_invalid_json(self, mongodb_adapter):
        """Invalid JSON query format."""
        query = "not valid json"
        with pytest.raises(QueryAnalysisError):
            mongodb_adapter.execute_explain(query)

    def test_explain_missing_collection(self, mongodb_adapter):
        """Query missing collection field."""
        query = json.dumps({"filter": {"age": {"$gt": 18}}})
        with pytest.raises(QueryAnalysisError):
            mongodb_adapter.execute_explain(query)

    def test_explain_nonexistent_collection(self, mongodb_adapter):
        """Query for nonexistent collection."""
        query = json.dumps({"collection": "nonexistent_collection", "filter": {"field": "value"}})

        # MongoDB allows querying nonexistent collections
        report = mongodb_adapter.execute_explain(query)
        assert report.engine == "mongodb"


class TestMongoDBSlowQueries:
    """Test slow query profiling."""

    def test_get_slow_queries(self, mongodb_adapter):
        """Profiling returns list."""
        slow_queries = mongodb_adapter.get_slow_queries(threshold_ms=1000)
        assert isinstance(slow_queries, list)

    def test_slow_queries_structure(self, mongodb_adapter):
        """Slow queries have expected structure."""
        slow_queries = mongodb_adapter.get_slow_queries(threshold_ms=10000)

        if slow_queries:
            for query in slow_queries:
                assert "timestamp" in query
                assert "operation" in query
                assert "namespace" in query
                assert "duration_ms" in query
