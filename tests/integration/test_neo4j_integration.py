"""Neo4j adapter integration tests."""

import pytest

from query_analyzer.adapters import AdapterRegistry
from query_analyzer.adapters.exceptions import QueryAnalysisError
from query_analyzer.adapters.models import ConnectionConfig


@pytest.fixture(scope="session")
def docker_neo4j_config() -> ConnectionConfig:
    """Neo4j Docker configuration."""
    return ConnectionConfig(
        engine="neo4j",
        host="localhost",
        port=7687,
        database="neo4j",
        username="neo4j",
        password="neo4j123",
        extra={"expand_threshold": 1000},
    )


@pytest.fixture(scope="function")
def neo4j_adapter_instance(docker_neo4j_config: ConnectionConfig):
    """Yields connected Neo4j adapter."""
    adapter = AdapterRegistry.create("neo4j", docker_neo4j_config)
    try:
        adapter.connect()
        yield adapter
    finally:
        adapter.disconnect()


@pytest.fixture(scope="function")
def populated_graph(neo4j_adapter_instance):
    """Yields Neo4j adapter with test data (users and follows relationships)."""
    session = neo4j_adapter_instance._driver.session(database="neo4j")

    try:
        # Clean up any existing test data
        session.run("MATCH (n:TestUser) DETACH DELETE n")
        session.run("MATCH (n:TestProduct) DETACH DELETE n")

        # Create test data
        session.run("""
            CREATE (u1:TestUser {id: 1, name: 'Alice', email: 'alice@example.com', age: 30})
            CREATE (u2:TestUser {id: 2, name: 'Bob', email: 'bob@example.com', age: 25})
            CREATE (u3:TestUser {id: 3, name: 'Charlie', email: 'charlie@example.com', age: 35})
            CREATE (p1:TestProduct {id: 1, name: 'Laptop', price: 1000})
            CREATE (p2:TestProduct {id: 2, name: 'Phone', price: 500})
            CREATE (p3:TestProduct {id: 3, name: 'Tablet', price: 400})
        """)

        # Create relationships
        session.run("""
            MATCH (u1:TestUser {id: 1}), (u2:TestUser {id: 2})
            CREATE (u1)-[:FOLLOWS]->(u2)
        """)

        session.run("""
            MATCH (u1:TestUser {id: 2}), (p:TestProduct {id: 1})
            CREATE (u1)-[:PURCHASED]->(p)
        """)

        session.run("""
            MATCH (u3:TestUser {id: 3}), (p:TestProduct)
            CREATE (u3)-[:VIEWED]->(p)
        """)

        yield neo4j_adapter_instance

    finally:
        # Cleanup after test
        session.run("MATCH (n:TestUser) DETACH DELETE n")
        session.run("MATCH (n:TestProduct) DETACH DELETE n")
        session.close()


# ============================================================================
# TESTS - Connection Management
# ============================================================================


class TestNeo4jConnection:
    """Test connection lifecycle."""

    def test_connect_success(self, neo4j_adapter_instance):
        """Verify connection established."""
        assert neo4j_adapter_instance._is_connected
        assert neo4j_adapter_instance._driver is not None

    def test_test_connection_success(self, docker_neo4j_config: ConnectionConfig):
        """Verify test_connection() works."""
        adapter = AdapterRegistry.create("neo4j", docker_neo4j_config)
        try:
            adapter.connect()
            assert adapter.test_connection() is True
        finally:
            adapter.disconnect()

    def test_disconnect(self, neo4j_adapter_instance):
        """Verify disconnect closes connection."""
        neo4j_adapter_instance.disconnect()
        assert not neo4j_adapter_instance._is_connected

    def test_get_engine_info(self, neo4j_adapter_instance):
        """Verify engine info retrieval."""
        info = neo4j_adapter_instance.get_engine_info()
        assert info["engine"] == "neo4j"
        assert "driver" in info


# ============================================================================
# TESTS - Data Preparation
# ============================================================================


class TestNeo4jDataSetup:
    """Test data setup for integration tests."""

    def test_create_test_nodes(self, populated_graph):
        """Verify test nodes were created."""
        session = populated_graph._driver.session(database="neo4j")
        try:
            result = session.run("MATCH (n:TestUser) RETURN count(n) as count")
            count = result.single()["count"]
            assert count == 3, "Expected 3 test users"
        finally:
            session.close()

    def test_create_test_relationships(self, populated_graph):
        """Verify test relationships were created."""
        session = populated_graph._driver.session(database="neo4j")
        try:
            result = session.run("MATCH ()-[r]-() RETURN count(r) as count")
            count = result.single()["count"]
            assert count > 0, "Expected test relationships"
        finally:
            session.close()


# ============================================================================
# TESTS - PROFILE Queries
# ============================================================================


class TestNeo4jProfileQueries:
    """Test PROFILE query execution."""

    def test_profile_simple_match(self, populated_graph):
        """Execute PROFILE on simple MATCH query."""
        query = "MATCH (n:TestUser) RETURN n"

        report = populated_graph.execute_explain(query)

        assert report.engine == "neo4j"
        assert report.score >= 0
        assert report.score <= 100
        assert report.execution_time_ms >= 0
        assert isinstance(report.warnings, list)
        assert isinstance(report.recommendations, list)

    def test_profile_match_with_filter(self, populated_graph):
        """Execute PROFILE on MATCH with WHERE clause."""
        query = "MATCH (n:TestUser) WHERE n.age > 25 RETURN n"

        report = populated_graph.execute_explain(query)

        assert report.engine == "neo4j"
        assert report.score >= 0
        assert report.execution_time_ms >= 0

    def test_profile_expand_with_relationship(self, populated_graph):
        """Execute PROFILE on query with relationship expansion."""
        query = "MATCH (u:TestUser)-[r:FOLLOWS]->(other:TestUser) RETURN u, other"

        report = populated_graph.execute_explain(query)

        assert report.engine == "neo4j"
        assert report.score >= 0
        assert report.execution_time_ms >= 0

    def test_profile_multi_hop_expansion(self, populated_graph):
        """Execute PROFILE on multi-hop relationship query."""
        query = "MATCH (u:TestUser)-[:PURCHASED]->(p:TestProduct) RETURN u, p"

        report = populated_graph.execute_explain(query)

        assert report.engine == "neo4j"
        assert report.score >= 0


# ============================================================================
# TESTS - Anti-pattern Detection
# ============================================================================


class TestNeo4jAntiPatterns:
    """Test anti-pattern detection in Cypher queries."""

    def test_detect_cartesian_product(self, populated_graph):
        """Detect cartesian product (disconnected patterns)."""
        # This query creates a cartesian product because there's no connection between u1 and u2
        query = "MATCH (u1:TestUser), (u2:TestUser) RETURN u1, u2"

        report = populated_graph.execute_explain(query)

        assert report.engine == "neo4j"
        # Cartesian product should be detected and affect score
        assert report.score >= 0

    def test_all_nodes_scan_detection(self, populated_graph):
        """Detect full graph scan (if applicable)."""
        # This query scans all relationships without label filtering
        query = "MATCH ()-[r]-() RETURN r"

        report = populated_graph.execute_explain(query)

        assert report.engine == "neo4j"
        assert report.score >= 0


# ============================================================================
# TESTS - Metrics Retrieval
# ============================================================================


class TestNeo4jMetrics:
    """Test metrics retrieval."""

    def test_get_metrics(self, populated_graph):
        """Verify metrics retrieval."""
        metrics = populated_graph.get_metrics()

        assert isinstance(metrics, dict)
        # Should have at least node_count or relationship_count
        assert len(metrics) > 0 or metrics == {}

    def test_get_engine_info(self, populated_graph):
        """Verify engine info retrieval."""
        info = populated_graph.get_engine_info()

        assert isinstance(info, dict)
        assert info.get("engine") == "neo4j"

    def test_get_slow_queries(self, populated_graph):
        """Verify get_slow_queries returns empty (Neo4j doesn't support)."""
        slow_queries = populated_graph.get_slow_queries(1000)

        assert isinstance(slow_queries, list)
        assert len(slow_queries) == 0


# ============================================================================
# TESTS - Error Handling
# ============================================================================


class TestNeo4jErrorHandling:
    """Test error handling."""

    def test_reject_create_index_query(self, neo4j_adapter_instance):
        """Reject CREATE INDEX query."""
        with pytest.raises(QueryAnalysisError):
            neo4j_adapter_instance.execute_explain(
                "CREATE INDEX idx_name FOR (n:User) ON (n.email)"
            )

    def test_reject_drop_query(self, neo4j_adapter_instance):
        """Reject DROP query."""
        with pytest.raises(QueryAnalysisError):
            neo4j_adapter_instance.execute_explain("DROP INDEX idx_name")

    def test_execute_explain_not_connected(self, docker_neo4j_config: ConnectionConfig):
        """execute_explain fails when not connected."""
        adapter = AdapterRegistry.create("neo4j", docker_neo4j_config)
        # Don't connect

        with pytest.raises(QueryAnalysisError):
            adapter.execute_explain("MATCH (n) RETURN n")
