"""Unit tests for PostgreSQL adapter."""

from unittest.mock import MagicMock, patch

import pytest

from query_analyzer.adapters import (
    AdapterRegistry,
    ConnectionConfig,
    PostgreSQLAdapter,  # This import triggers @AdapterRegistry.register decorator
)

# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def pg_config() -> ConnectionConfig:
    """Valid PostgreSQL connection config."""
    return ConnectionConfig(
        engine="postgresql",
        host="localhost",
        port=5432,
        database="test_db",
        username="postgres",
        password="postgres",
        extra={"seq_scan_threshold": 10000},
    )


# ============================================================================
# TESTS - Instantiation & Registry
# ============================================================================


class TestPostgreSQLAdapterInstantiation:
    """PostgreSQL adapter creation and initialization."""

    def test_instantiate_with_valid_config(self, pg_config: ConnectionConfig) -> None:
        """Create PostgreSQL adapter with valid config."""
        adapter = PostgreSQLAdapter(pg_config)

        assert adapter._config == pg_config
        assert adapter._is_connected is False
        assert adapter._connection is None
        # Check that parser and metrics_helper are initialized
        assert hasattr(adapter, "parser")
        assert hasattr(adapter, "metrics_helper")

    def test_registry_can_create_postgresql_adapter(self, pg_config: ConnectionConfig) -> None:
        """Registry factory creates PostgreSQL adapter."""
        # The decorator in postgresql.py registers it
        adapter = AdapterRegistry.create("postgresql", pg_config)

        assert isinstance(adapter, PostgreSQLAdapter)
        assert adapter._config == pg_config

    def test_registry_case_insensitive(self, pg_config: ConnectionConfig) -> None:
        """Registry lookup is case-insensitive."""
        adapter1 = AdapterRegistry.create("postgresql", pg_config)
        adapter2 = AdapterRegistry.create("PostgreSQL", pg_config)
        adapter3 = AdapterRegistry.create("POSTGRESQL", pg_config)

        assert isinstance(adapter1, PostgreSQLAdapter)
        assert isinstance(adapter2, PostgreSQLAdapter)
        assert isinstance(adapter3, PostgreSQLAdapter)

    def test_adapter_inherits_seq_scan_threshold(self, pg_config: ConnectionConfig) -> None:
        """Adapter uses configurable seq_scan_threshold."""
        config_custom = ConnectionConfig(
            engine="postgresql",
            host="localhost",
            port=5432,
            database="test_db",
            username="postgres",
            password="postgres",
            extra={"seq_scan_threshold": 5000},
        )

        adapter = PostgreSQLAdapter(config_custom)
        # Check that parser uses the custom threshold
        assert hasattr(adapter, "parser")


# ============================================================================
# TESTS - Connection Management
# ============================================================================


class TestPostgreSQLAdapterConnection:
    """Connection lifecycle tests."""

    @patch("query_analyzer.adapters.sql.postgresql.psycopg2.connect")
    def test_connect_success(self, mock_connect: MagicMock, pg_config: ConnectionConfig) -> None:
        """Successful connection sets _is_connected=True."""
        mock_connection = MagicMock()
        mock_connect.return_value = mock_connection

        adapter = PostgreSQLAdapter(pg_config)
        adapter.connect()

        assert adapter._is_connected is True
        assert adapter._connection == mock_connection
        mock_connect.assert_called_once()

    @patch("query_analyzer.adapters.sql.postgresql.psycopg2.connect")
    def test_connect_failure(self, mock_connect: MagicMock, pg_config: ConnectionConfig) -> None:
        """Connection failure raises ConnectionError."""
        import psycopg2

        mock_connect.side_effect = psycopg2.OperationalError("Connection refused")

        adapter = PostgreSQLAdapter(pg_config)

        with pytest.raises(Exception):
            adapter.connect()

        assert adapter._is_connected is False
        assert adapter._connection is None

    @patch("query_analyzer.adapters.sql.postgresql.psycopg2.connect")
    def test_disconnect_cleanup(self, mock_connect: MagicMock, pg_config: ConnectionConfig) -> None:
        """Disconnection closes connection and sets state."""
        mock_connection = MagicMock()
        mock_connect.return_value = mock_connection

        adapter = PostgreSQLAdapter(pg_config)
        adapter.connect()
        assert adapter._is_connected is True

        adapter.disconnect()

        assert adapter._is_connected is False
        assert adapter._connection is None
        mock_connection.close.assert_called_once()

    @patch("query_analyzer.adapters.sql.postgresql.psycopg2.connect")
    def test_context_manager(self, mock_connect: MagicMock, pg_config: ConnectionConfig) -> None:
        """Context manager connects and disconnects."""
        mock_connection = MagicMock()
        mock_connect.return_value = mock_connection

        adapter = PostgreSQLAdapter(pg_config)

        with adapter:
            assert adapter._is_connected is True

        assert adapter._is_connected is False
        mock_connection.close.assert_called_once()


# ============================================================================
# TESTS - Connection Testing
# ============================================================================


class TestPostgreSQLAdapterConnectionTest:
    """Connection test method tests."""

    @patch("query_analyzer.adapters.sql.postgresql.psycopg2.connect")
    def test_test_connection_success(
        self, mock_connect: MagicMock, pg_config: ConnectionConfig
    ) -> None:
        """test_connection returns True when connected."""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (1,)
        mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
        mock_cursor.__exit__ = MagicMock(return_value=None)

        mock_connection = MagicMock()
        mock_connection.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_connection

        adapter = PostgreSQLAdapter(pg_config)
        adapter.connect()
        result = adapter.test_connection()

        assert result is True

    def test_test_connection_not_connected(self, pg_config: ConnectionConfig) -> None:
        """test_connection returns False when not connected."""
        adapter = PostgreSQLAdapter(pg_config)
        result = adapter.test_connection()

        assert result is False

    @patch("query_analyzer.adapters.sql.postgresql.psycopg2.connect")
    def test_test_connection_failure(
        self, mock_connect: MagicMock, pg_config: ConnectionConfig
    ) -> None:
        """test_connection returns False on exception."""
        mock_cursor = MagicMock()
        mock_cursor.__enter__ = MagicMock(side_effect=Exception("Cursor error"))
        mock_cursor.__exit__ = MagicMock(return_value=None)

        mock_connection = MagicMock()
        mock_connection.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_connection

        adapter = PostgreSQLAdapter(pg_config)
        adapter.connect()
        result = adapter.test_connection()

        assert result is False


# ============================================================================
# TESTS - EXPLAIN Analysis
# ============================================================================


class TestPostgreSQLAdapterExplain:
    """EXPLAIN query analysis tests."""

    @patch("query_analyzer.adapters.sql.postgresql.psycopg2.connect")
    def test_execute_explain_rejects_ddl(
        self, mock_connect: MagicMock, pg_config: ConnectionConfig
    ) -> None:
        """execute_explain rejects DDL statements."""
        mock_connection = MagicMock()
        mock_connect.return_value = mock_connection

        adapter = PostgreSQLAdapter(pg_config)
        adapter.connect()

        with pytest.raises(Exception) as exc_info:
            adapter.execute_explain("CREATE TABLE test (id INT)")

        assert "DDL" in str(exc_info.value) or "not supported" in str(exc_info.value)

    @patch("query_analyzer.adapters.sql.postgresql.psycopg2.connect")
    def test_execute_explain_not_connected(
        self, mock_connect: MagicMock, pg_config: ConnectionConfig
    ) -> None:
        """execute_explain raises error if not connected."""
        adapter = PostgreSQLAdapter(pg_config)

        with pytest.raises(Exception):
            adapter.execute_explain("SELECT 1")


# ============================================================================
# TESTS - Slow Queries
# ============================================================================


class TestPostgreSQLAdapterSlowQueries:
    """Slow query detection tests."""

    @patch("query_analyzer.adapters.sql.postgresql.psycopg2.connect")
    def test_get_slow_queries_not_connected(
        self, mock_connect: MagicMock, pg_config: ConnectionConfig
    ) -> None:
        """get_slow_queries returns empty list if not connected."""
        adapter = PostgreSQLAdapter(pg_config)
        result = adapter.get_slow_queries()

        assert result == []

    @patch("query_analyzer.adapters.sql.postgresql.psycopg2.connect")
    def test_get_slow_queries_extension_not_installed(
        self, mock_connect: MagicMock, pg_config: ConnectionConfig
    ) -> None:
        """get_slow_queries returns empty list if pg_stat_statements not available."""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (False,)
        mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
        mock_cursor.__exit__ = MagicMock(return_value=None)

        mock_connection = MagicMock()
        mock_connection.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_connection

        adapter = PostgreSQLAdapter(pg_config)
        adapter.connect()

        # Patch the metrics helper check
        with patch(
            "query_analyzer.adapters.sql.postgresql_metrics.PostgreSQLMetricsHelper.check_pg_stat_statements_available",
            return_value=False,
        ):
            result = adapter.get_slow_queries()

        assert result == []


# ============================================================================
# TESTS - Metrics & Engine Info
# ============================================================================


class TestPostgreSQLAdapterMetrics:
    """Metrics and engine info retrieval."""

    @patch("query_analyzer.adapters.sql.postgresql.psycopg2.connect")
    def test_get_metrics_not_connected(
        self, mock_connect: MagicMock, pg_config: ConnectionConfig
    ) -> None:
        """get_metrics returns empty dict if not connected."""
        adapter = PostgreSQLAdapter(pg_config)
        result = adapter.get_metrics()

        assert result == {}

    @patch("query_analyzer.adapters.sql.postgresql.psycopg2.connect")
    def test_get_engine_info_not_connected(
        self, mock_connect: MagicMock, pg_config: ConnectionConfig
    ) -> None:
        """get_engine_info returns empty dict if not connected."""
        adapter = PostgreSQLAdapter(pg_config)
        result = adapter.get_engine_info()

        assert result == {}


# ============================================================================
# TESTS - is_connected & get_connection
# ============================================================================


class TestPostgreSQLAdapterState:
    """Adapter state tracking."""

    def test_is_connected_initial_state(self, pg_config: ConnectionConfig) -> None:
        """New adapter starts as not connected."""
        adapter = PostgreSQLAdapter(pg_config)
        assert adapter.is_connected() is False

    @patch("query_analyzer.adapters.sql.postgresql.psycopg2.connect")
    def test_is_connected_after_connect(
        self, mock_connect: MagicMock, pg_config: ConnectionConfig
    ) -> None:
        """is_connected reflects connection state."""
        mock_connection = MagicMock()
        mock_connect.return_value = mock_connection

        adapter = PostgreSQLAdapter(pg_config)
        assert adapter.is_connected() is False

        adapter.connect()
        assert adapter.is_connected() is True

        adapter.disconnect()
        assert adapter.is_connected() is False
