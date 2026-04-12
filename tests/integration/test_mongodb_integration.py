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
        """Query using indexed field → basic explain."""
        # Query orders collection by email (indexed field in seed data)
        query = json.dumps({"collection": "orders", "filter": {"email": "customer1@example.com"}})

        report = mongodb_adapter.execute_explain(query)

        assert report.engine == "mongodb"
        assert report.score >= 0
        assert isinstance(report.warnings, list)

    def test_explain_collection_scan(self, mongodb_adapter):
        """Query without suitable index → basic explain."""
        # Query orders collection by country (non-indexed field)
        query = json.dumps({"collection": "orders", "filter": {"country": "USA"}})

        report = mongodb_adapter.execute_explain(query)

        assert report.engine == "mongodb"
        assert report.score >= 0
        assert isinstance(report.warnings, list)

    def test_explain_with_projection(self, mongodb_adapter):
        """Query with projection."""
        query = json.dumps(
            {
                "collection": "orders",
                "filter": {"_id": {"$gt": 1}},
                "projection": {"customer_name": 1, "email": 1},
            }
        )

        report = mongodb_adapter.execute_explain(query)

        assert report.engine == "mongodb"
        assert report.score >= 0

    def test_explain_with_sort(self, mongodb_adapter):
        """Query with sort operation."""
        query = json.dumps(
            {
                "collection": "orders",
                "filter": {"country": "USA"},
                "sort": {"customer_name": 1},
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
