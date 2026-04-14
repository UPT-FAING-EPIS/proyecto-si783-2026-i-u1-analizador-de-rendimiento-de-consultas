"""Unit tests for Cassandra adapter."""

from unittest.mock import MagicMock, Mock, patch

import pytest

from query_analyzer.adapters import (
    AdapterRegistry,
    CassandraAdapter,  # This import triggers @AdapterRegistry.register decorator
    ConnectionConfig,
)

# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def cassandra_config() -> ConnectionConfig:
    """Valid Cassandra connection config."""
    return ConnectionConfig(
        engine="cassandra",
        host="127.0.0.1",
        port=9042,
        database="test_keyspace",
        username="cassandra",
        password="cassandra",
        extra={"protocol_version": 3},
    )


@pytest.fixture
def mock_trace_event() -> Mock:
    """Mock a single trace event."""
    event = Mock()
    event.event_id = "123e4567-e89b-12d3-a456-426614174000"
    event.timestamp = 1000
    event.source = "127.0.0.1"
    event.thread_id = 1
    event.activity = "Parsing SELECT statement"
    event.source_elapsed = 100
    return event


@pytest.fixture
def mock_cluster_and_session():
    """Mock Cassandra cluster and session."""
    cluster = MagicMock()
    session = MagicMock()
    cluster.connect.return_value = session
    return cluster, session


@pytest.fixture
def mock_trace() -> Mock:
    """Mock query trace object."""
    trace = Mock()
    trace.duration = 5000  # microseconds
    trace.client = "127.0.0.1"
    trace.coordinator = "127.0.0.1"

    # Create mock events
    event1 = Mock()
    event1.event_id = "event1"
    event1.timestamp = 1000
    event1.source = "127.0.0.1"
    event1.thread_id = 1
    event1.activity = "Parsing SELECT"
    event1.source_elapsed = 100

    event2 = Mock()
    event2.event_id = "event2"
    event2.timestamp = 1100
    event2.source = "127.0.0.2"
    event2.thread_id = 1
    event2.activity = "Executing read"
    event2.source_elapsed = 200

    trace.events = [event1, event2]
    return trace


@pytest.fixture
def mock_result_set(mock_trace) -> Mock:
    """Mock Cassandra result set with trace."""
    result_set = MagicMock()
    result_set.get_query_trace.return_value = mock_trace
    result_set.__iter__ = MagicMock(return_value=iter([{"user_id": 1}]))
    return result_set


# ============================================================================
# ADAPTER REGISTRATION TESTS
# ============================================================================


class TestCassandraAdapterRegistration:
    """Test that CassandraAdapter is properly registered."""

    def test_cassandra_adapter_registered(self) -> None:
        """Test that 'cassandra' is registered in AdapterRegistry."""
        assert AdapterRegistry.is_registered("cassandra")

    def test_cassandra_adapter_creation(self, cassandra_config: ConnectionConfig) -> None:
        """Test that CassandraAdapter can be created via registry."""
        adapter = AdapterRegistry.create("cassandra", cassandra_config)
        assert isinstance(adapter, CassandraAdapter)
        assert adapter._config == cassandra_config


# ============================================================================
# CONNECTION TESTS
# ============================================================================


class TestCassandraConnection:
    """Test connection/disconnection logic."""

    @patch("query_analyzer.adapters.nosql.cassandra.Cluster")
    def test_connect_success(
        self, mock_cluster_class: MagicMock, cassandra_config: ConnectionConfig
    ) -> None:
        """Test successful connection."""
        mock_cluster = MagicMock()
        mock_session = MagicMock()
        mock_cluster.connect.return_value = mock_session
        mock_cluster_class.return_value = mock_cluster

        adapter = CassandraAdapter(cassandra_config)
        adapter.connect()

        assert adapter.is_connected()
        assert adapter._session is not None
        assert adapter._cluster is not None

    @patch("query_analyzer.adapters.nosql.cassandra.Cluster")
    def test_connect_with_auth(
        self, mock_cluster_class: MagicMock, cassandra_config: ConnectionConfig
    ) -> None:
        """Test connection with authentication."""
        mock_cluster = MagicMock()
        mock_session = MagicMock()
        mock_cluster.connect.return_value = mock_session
        mock_cluster_class.return_value = mock_cluster

        adapter = CassandraAdapter(cassandra_config)
        adapter.connect()

        # Verify Cluster was called with auth provider
        call_kwargs = mock_cluster_class.call_args[1]
        assert "auth_provider" in call_kwargs

    @patch("query_analyzer.adapters.nosql.cassandra.Cluster")
    def test_disconnect_success(
        self, mock_cluster_class: MagicMock, cassandra_config: ConnectionConfig
    ) -> None:
        """Test successful disconnection."""
        mock_cluster = MagicMock()
        mock_session = MagicMock()
        mock_cluster.connect.return_value = mock_session
        mock_cluster_class.return_value = mock_cluster

        adapter = CassandraAdapter(cassandra_config)
        adapter.connect()
        adapter.disconnect()

        assert not adapter.is_connected()
        mock_session.shutdown.assert_called_once()
        mock_cluster.shutdown.assert_called_once()

    @patch("query_analyzer.adapters.nosql.cassandra.Cluster")
    def test_test_connection_valid(
        self, mock_cluster_class: MagicMock, cassandra_config: ConnectionConfig
    ) -> None:
        """Test connection testing."""
        mock_cluster = MagicMock()
        mock_session = MagicMock()
        mock_session.execute.return_value = MagicMock()
        mock_cluster.connect.return_value = mock_session
        mock_cluster_class.return_value = mock_cluster

        adapter = CassandraAdapter(cassandra_config)
        adapter.connect()
        result = adapter.test_connection()

        assert result is True
        mock_session.execute.assert_called()

    @patch("query_analyzer.adapters.nosql.cassandra.Cluster")
    def test_test_connection_not_connected(
        self, mock_cluster_class: MagicMock, cassandra_config: ConnectionConfig
    ) -> None:
        """Test connection test when not connected."""
        adapter = CassandraAdapter(cassandra_config)
        result = adapter.test_connection()

        assert result is False


# ============================================================================
# TABLE NAME EXTRACTION TESTS
# ============================================================================


class TestTableNameExtraction:
    """Test table name extraction from queries."""

    def test_extract_table_name_simple(self, cassandra_config: ConnectionConfig) -> None:
        """Test simple table name extraction."""
        adapter = CassandraAdapter(cassandra_config)
        table_name = adapter._extract_table_name("SELECT * FROM users WHERE id = 1")
        assert table_name == "users"

    def test_extract_table_name_with_keyspace(self, cassandra_config: ConnectionConfig) -> None:
        """Test table name extraction with keyspace prefix."""
        adapter = CassandraAdapter(cassandra_config)
        table_name = adapter._extract_table_name("SELECT * FROM test_keyspace.users WHERE id = 1")
        assert table_name == "users"

    def test_extract_table_name_not_found(self, cassandra_config: ConnectionConfig) -> None:
        """Test table name extraction when not found."""
        adapter = CassandraAdapter(cassandra_config)
        table_name = adapter._extract_table_name("INVALID QUERY")
        assert table_name is None


# ============================================================================
# EXECUTE EXPLAIN TESTS
# ============================================================================


class TestExecuteExplain:
    """Test query analysis via execute_explain."""

    @patch("query_analyzer.adapters.nosql.cassandra.Cluster")
    def test_execute_explain_allow_filtering(
        self,
        mock_cluster_class: MagicMock,
        cassandra_config: ConnectionConfig,
        mock_result_set: Mock,
    ) -> None:
        """Test ALLOW FILTERING detection."""
        mock_cluster = MagicMock()
        mock_session = MagicMock()
        mock_cluster.connect.return_value = mock_session
        mock_cluster_class.return_value = mock_cluster

        # Mock query execution
        mock_statement = MagicMock()
        mock_session.prepare.return_value = mock_statement
        mock_session.execute.return_value = mock_result_set

        adapter = CassandraAdapter(cassandra_config)
        adapter.connect()

        # Mock schema cache
        adapter._schema_cache["users"] = {
            "partition_keys": ["user_id"],
            "clustering_keys": [],
            "columns": [{"name": "user_id", "kind": "partition_key"}],
        }

        query = "SELECT * FROM users WHERE email = 'test@example.com' ALLOW FILTERING"
        report = adapter.execute_explain(query)

        assert report.engine == "cassandra"
        assert report.score < 100  # Should be penalized
        assert len(report.warnings) > 0
        assert any("ALLOW FILTERING" in w.message for w in report.warnings)

    @patch("query_analyzer.adapters.nosql.cassandra.Cluster")
    def test_execute_explain_full_cluster_scan(
        self,
        mock_cluster_class: MagicMock,
        cassandra_config: ConnectionConfig,
        mock_result_set: Mock,
    ) -> None:
        """Test full cluster scan detection."""
        mock_cluster = MagicMock()
        mock_session = MagicMock()
        mock_cluster.connect.return_value = mock_session
        mock_cluster_class.return_value = mock_cluster

        mock_statement = MagicMock()
        mock_session.prepare.return_value = mock_statement
        mock_session.execute.return_value = mock_result_set

        adapter = CassandraAdapter(cassandra_config)
        adapter.connect()

        # Schema with partition key
        adapter._schema_cache["users"] = {
            "partition_keys": ["user_id"],
            "clustering_keys": [],
            "columns": [{"name": "user_id", "kind": "partition_key"}],
        }

        # Query without partition key filter = full cluster scan
        query = "SELECT * FROM users WHERE email = 'test@example.com'"
        report = adapter.execute_explain(query)

        assert report.score < 100
        assert len(report.warnings) > 0

    @patch("query_analyzer.adapters.nosql.cassandra.Cluster")
    def test_execute_explain_invalid_query_type(
        self, mock_cluster_class: MagicMock, cassandra_config: ConnectionConfig
    ) -> None:
        """Test that non-SELECT queries are rejected."""
        mock_cluster = MagicMock()
        mock_session = MagicMock()
        mock_cluster.connect.return_value = mock_session
        mock_cluster_class.return_value = mock_cluster

        adapter = CassandraAdapter(cassandra_config)
        adapter.connect()

        with pytest.raises(Exception) as exc_info:
            adapter.execute_explain("INSERT INTO users (id) VALUES (1)")

        assert "SELECT" in str(exc_info.value)

    @patch("query_analyzer.adapters.nosql.cassandra.Cluster")
    def test_execute_explain_not_connected(
        self, mock_cluster_class: MagicMock, cassandra_config: ConnectionConfig
    ) -> None:
        """Test execute_explain when not connected."""
        adapter = CassandraAdapter(cassandra_config)

        with pytest.raises(Exception) as exc_info:
            adapter.execute_explain("SELECT * FROM users")

        assert "connected" in str(exc_info.value).lower()


# ============================================================================
# METRICS TESTS
# ============================================================================


class TestGetMetrics:
    """Test metrics collection."""

    @patch("query_analyzer.adapters.nosql.cassandra.Cluster")
    def test_get_metrics_success(
        self, mock_cluster_class: MagicMock, cassandra_config: ConnectionConfig
    ) -> None:
        """Test successful metrics collection."""
        mock_cluster = MagicMock()
        mock_session = MagicMock()
        mock_cluster.connect.return_value = mock_session
        mock_cluster_class.return_value = mock_cluster

        # Mock system queries
        cluster_row = MagicMock()
        cluster_row.cluster_name = "TestCluster"
        mock_session.execute.side_effect = [
            [cluster_row],  # system.local
            [MagicMock(count=2)],  # system.peers count
            [],  # system.size_estimates (empty list)
        ]

        adapter = CassandraAdapter(cassandra_config)
        adapter.connect()
        metrics = adapter.get_metrics()

        assert "cluster_name" in metrics
        assert "node_count" in metrics
        assert metrics["cluster_name"] == "TestCluster"
        assert metrics["node_count"] == 3  # 2 peers + 1 local


# ============================================================================
# ENGINE INFO TESTS
# ============================================================================


class TestGetEngineInfo:
    """Test engine info retrieval."""

    @patch("query_analyzer.adapters.nosql.cassandra.Cluster")
    def test_get_engine_info_success(
        self, mock_cluster_class: MagicMock, cassandra_config: ConnectionConfig
    ) -> None:
        """Test engine info retrieval."""
        mock_cluster = MagicMock()
        mock_session = MagicMock()
        mock_cluster.connect.return_value = mock_session
        mock_cluster_class.return_value = mock_cluster

        info_row = MagicMock()
        info_row.cluster_name = "TestCluster"
        info_row.release_version = "3.11.0"
        info_row.schema_version = "abc123"
        info_row.cql_version = "3.4.4"
        mock_session.execute.return_value = [info_row]

        adapter = CassandraAdapter(cassandra_config)
        adapter.connect()
        info = adapter.get_engine_info()

        assert info["cluster_name"] == "TestCluster"
        assert info["release_version"] == "3.11.0"
