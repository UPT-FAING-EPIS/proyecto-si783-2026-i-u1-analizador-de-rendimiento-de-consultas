"""Unit tests for YugabyteDB adapter (mock-based, no real DB)."""

from unittest.mock import MagicMock, Mock, patch

import pytest

from query_analyzer.adapters import AdapterRegistry, ConnectionConfig
from query_analyzer.adapters.exceptions import QueryAnalysisError
from query_analyzer.adapters.models import QueryAnalysisReport
from query_analyzer.adapters.sql.yugabytedb import YugabyteDBAdapter
from query_analyzer.adapters.sql.yugabytedb_parser import YugabyteDBParser


class TestYugabyteDBAdapterInit:
    """Test adapter initialization."""

    def test_adapter_initializes_with_config(self) -> None:
        """YugabyteDBAdapter initializes with ConnectionConfig."""
        config = ConnectionConfig(
            engine="yugabytedb",
            host="localhost",
            port=5433,
            database="yugabyte",
            username="yugabyte",
            password="yugabyte",
        )
        adapter = YugabyteDBAdapter(config)

        assert adapter._config == config
        assert adapter._is_connected is False
        assert adapter.parser is not None
        assert isinstance(adapter.parser, YugabyteDBParser)
        assert adapter.metrics_helper is not None

    def test_adapter_is_base_adapter_subclass(self) -> None:
        """YugabyteDBAdapter inherits from BaseAdapter."""
        from query_analyzer.adapters.base import BaseAdapter

        config = ConnectionConfig(
            engine="yugabytedb",
            host="localhost",
            port=5433,
            database="yugabyte",
            username="yugabyte",
            password="yugabyte",
        )
        adapter = YugabyteDBAdapter(config)
        assert isinstance(adapter, BaseAdapter)

    def test_adapter_uses_yugabytedb_parser(self) -> None:
        """Adapter uses YugabyteDB parser, not PostgreSQL parser."""
        config = ConnectionConfig(
            engine="yugabytedb",
            host="localhost",
            port=5433,
            database="yugabyte",
            username="yugabyte",
            password="yugabyte",
        )
        adapter = YugabyteDBAdapter(config)

        assert isinstance(adapter.parser, YugabyteDBParser)

    def test_registry_can_create_yugabytedb_adapter(self) -> None:
        """Registry factory creates YugabyteDB adapter."""
        config = ConnectionConfig(
            engine="yugabytedb",
            host="localhost",
            port=5433,
            database="yugabyte",
            username="yugabyte",
            password="yugabyte",
        )
        adapter = AdapterRegistry.create("yugabytedb", config)

        assert isinstance(adapter, YugabyteDBAdapter)
        assert adapter._config == config


# ============================================================================
# TESTS - Connection Management
# ============================================================================


class TestYugabyteDBAdapterConnection:
    """Test connection management."""

    @patch("query_analyzer.adapters.sql.yugabytedb.psycopg2.connect")
    def test_connect_success_with_custom_port(self, mock_psycopg2_connect: Mock) -> None:
        """connect() succeeds with custom port (5433)."""
        mock_conn = Mock()
        mock_psycopg2_connect.return_value = mock_conn

        config = ConnectionConfig(
            engine="yugabytedb",
            host="localhost",
            port=5433,
            database="yugabyte",
            username="yugabyte",
            password="yugabyte",
        )
        adapter = YugabyteDBAdapter(config)
        adapter.connect()

        assert adapter._is_connected is True
        assert adapter._connection == mock_conn
        # Verify psycopg2.connect was called with port 5433
        mock_psycopg2_connect.assert_called_once()
        call_kwargs = mock_psycopg2_connect.call_args[1]
        assert call_kwargs["port"] == 5433

    @patch("query_analyzer.adapters.sql.yugabytedb.psycopg2.connect")
    def test_connect_converts_default_pg_port_to_yb_port(self, mock_psycopg2_connect: Mock) -> None:
        """connect() converts PostgreSQL port 5432 to YugabyteDB port 5433."""
        mock_conn = Mock()
        mock_psycopg2_connect.return_value = mock_conn

        config = ConnectionConfig(
            engine="yugabytedb",
            host="localhost",
            port=5432,  # PostgreSQL default
            database="yugabyte",
            username="yugabyte",
            password="yugabyte",
        )
        adapter = YugabyteDBAdapter(config)
        adapter.connect()

        assert adapter._is_connected is True
        # Verify psycopg2.connect was called with port 5433 (converted)
        call_kwargs = mock_psycopg2_connect.call_args[1]
        assert call_kwargs["port"] == 5433

    @patch("query_analyzer.adapters.sql.yugabytedb.psycopg2.connect")
    def test_connect_failure(self, mock_psycopg2_connect: Mock) -> None:
        """connect() raises ConnectionError on psycopg2 failure."""
        from psycopg2 import OperationalError

        mock_psycopg2_connect.side_effect = OperationalError("Connection failed")

        config = ConnectionConfig(
            engine="yugabytedb",
            host="localhost",
            port=5433,
            database="yugabyte",
            username="yugabyte",
            password="yugabyte",
        )
        adapter = YugabyteDBAdapter(config)

        with pytest.raises(Exception):  # ConnectionError
            adapter.connect()

        assert adapter._is_connected is False

    def test_disconnect(self) -> None:
        """disconnect() closes connection and resets state."""
        config = ConnectionConfig(
            engine="yugabytedb",
            host="localhost",
            port=5433,
            database="yugabyte",
            username="yugabyte",
            password="yugabyte",
        )
        adapter = YugabyteDBAdapter(config)

        # Mock connected state
        mock_conn = Mock()
        adapter._connection = mock_conn
        adapter._is_connected = True

        adapter.disconnect()

        assert adapter._is_connected is False
        assert adapter._connection is None
        mock_conn.close.assert_called_once()

    def test_test_connection_true(self) -> None:
        """test_connection() returns True when SELECT 1 succeeds."""
        config = ConnectionConfig(
            engine="yugabytedb",
            host="localhost",
            port=5433,
            database="yugabyte",
            username="yugabyte",
            password="yugabyte",
        )
        adapter = YugabyteDBAdapter(config)

        # Mock connected state
        mock_cursor = MagicMock()
        mock_conn = MagicMock()
        mock_conn.cursor = MagicMock(return_value=mock_cursor)
        mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
        mock_cursor.__exit__ = MagicMock(return_value=None)

        adapter._connection = mock_conn
        adapter._is_connected = True

        result = adapter.test_connection()

        assert result is True
        mock_cursor.execute.assert_called_once_with("SELECT 1")

    def test_test_connection_false_not_connected(self) -> None:
        """test_connection() returns False if not connected."""
        config = ConnectionConfig(
            engine="yugabytedb",
            host="localhost",
            port=5433,
            database="yugabyte",
            username="yugabyte",
            password="yugabyte",
        )
        adapter = YugabyteDBAdapter(config)

        result = adapter.test_connection()

        assert result is False

    def test_test_connection_false_on_error(self) -> None:
        """test_connection() returns False on query error."""
        config = ConnectionConfig(
            engine="yugabytedb",
            host="localhost",
            port=5433,
            database="yugabyte",
            username="yugabyte",
            password="yugabyte",
        )
        adapter = YugabyteDBAdapter(config)

        # Mock connected state with error
        mock_cursor = MagicMock()
        mock_cursor.execute.side_effect = Exception("Query failed")
        mock_conn = MagicMock()
        mock_conn.cursor = MagicMock(return_value=mock_cursor)
        mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
        mock_cursor.__exit__ = MagicMock(return_value=None)

        adapter._connection = mock_conn
        adapter._is_connected = True

        result = adapter.test_connection()

        assert result is False


# ============================================================================
# TESTS - Query Analysis
# ============================================================================


class TestYugabyteDBAdapterExecuteExplain:
    """Test EXPLAIN query analysis."""

    def _create_explain_result(self) -> tuple:
        """Helper to create mock EXPLAIN result."""
        explain_json = {
            "Plan": {
                "Node Type": "Hash Join",
                "Startup Cost": 100.0,
                "Total Cost": 500.0,
                "Plan Rows": 1000,
                "Actual Rows": 950,
                "Plans": [
                    {
                        "Node Type": "Index Scan",
                        "Index Name": "users_idx",
                        "Table": "users",
                        "Actual Rows": 100,
                        "Plan Rows": 105,
                    },
                    {
                        "Node Type": "Seq Scan",
                        "Table": "orders",
                        "Actual Rows": 950,
                        "Plan Rows": 1000,
                    },
                ],
            },
            "Planning Time": 1.5,
            "Execution Time": 45.3,
        }
        return ([explain_json],)  # psycopg2 returns list in tuple

    @patch("query_analyzer.adapters.sql.yugabytedb.psycopg2.connect")
    def test_execute_explain_success(self, mock_psycopg2_connect: Mock) -> None:
        """execute_explain() analyzes query and returns report."""
        # Mock connection and cursor
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = self._create_explain_result()
        mock_conn = MagicMock()
        mock_conn.cursor = MagicMock(return_value=mock_cursor)
        mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
        mock_cursor.__exit__ = MagicMock(return_value=None)
        mock_psycopg2_connect.return_value = mock_conn

        config = ConnectionConfig(
            engine="yugabytedb",
            host="localhost",
            port=5433,
            database="yugabyte",
            username="yugabyte",
            password="yugabyte",
        )
        adapter = YugabyteDBAdapter(config)
        adapter.connect()

        # Execute EXPLAIN
        report = adapter.execute_explain("SELECT * FROM users")

        assert isinstance(report, QueryAnalysisReport)
        assert report.query == "SELECT * FROM users"
        assert report.engine == "yugabytedb"
        assert 0 <= report.score <= 100
        assert report.execution_time_ms > 0
        assert len(report.warnings) >= 0
        assert len(report.recommendations) >= 0

    @patch("query_analyzer.adapters.sql.yugabytedb.psycopg2.connect")
    def test_execute_explain_not_connected(self, mock_psycopg2_connect: Mock) -> None:
        """execute_explain() raises error if not connected."""
        config = ConnectionConfig(
            engine="yugabytedb",
            host="localhost",
            port=5433,
            database="yugabyte",
            username="yugabyte",
            password="yugabyte",
        )
        adapter = YugabyteDBAdapter(config)

        with pytest.raises(QueryAnalysisError):
            adapter.execute_explain("SELECT * FROM users")

    @patch("query_analyzer.adapters.sql.yugabytedb.psycopg2.connect")
    def test_execute_explain_rejects_ddl(self, mock_psycopg2_connect: Mock) -> None:
        """execute_explain() rejects DDL statements."""
        mock_conn = Mock()
        mock_psycopg2_connect.return_value = mock_conn

        config = ConnectionConfig(
            engine="yugabytedb",
            host="localhost",
            port=5433,
            database="yugabyte",
            username="yugabyte",
            password="yugabyte",
        )
        adapter = YugabyteDBAdapter(config)
        adapter._is_connected = True
        adapter._connection = mock_conn

        # Test various DDL statements
        for ddl in ["CREATE TABLE", "ALTER TABLE", "DROP TABLE", "TRUNCATE TABLE"]:
            with pytest.raises(QueryAnalysisError):
                adapter.execute_explain(ddl)

    @patch("query_analyzer.adapters.sql.yugabytedb.psycopg2.connect")
    def test_execute_explain_with_empty_result(self, mock_psycopg2_connect: Mock) -> None:
        """execute_explain() raises error on empty result."""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None  # Empty result
        mock_conn = MagicMock()
        mock_conn.cursor = MagicMock(return_value=mock_cursor)
        mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
        mock_cursor.__exit__ = MagicMock(return_value=None)
        mock_psycopg2_connect.return_value = mock_conn

        config = ConnectionConfig(
            engine="yugabytedb",
            host="localhost",
            port=5433,
            database="yugabyte",
            username="yugabyte",
            password="yugabyte",
        )
        adapter = YugabyteDBAdapter(config)
        adapter.connect()

        with pytest.raises(QueryAnalysisError):
            adapter.execute_explain("SELECT * FROM users")

    @patch("query_analyzer.adapters.sql.yugabytedb.psycopg2.connect")
    def test_execute_explain_with_json_string_result(self, mock_psycopg2_connect: Mock) -> None:
        """execute_explain() handles JSON string results from psycopg2."""
        import json

        explain_json = {
            "Plan": {
                "Node Type": "Seq Scan",
                "Table": "users",
                "Plan Rows": 1000,
                "Actual Rows": 950,
            },
            "Planning Time": 0.5,
            "Execution Time": 20.0,
        }

        # Return JSON string (old psycopg2 behavior)
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (json.dumps([explain_json]),)
        mock_conn = MagicMock()
        mock_conn.cursor = MagicMock(return_value=mock_cursor)
        mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
        mock_cursor.__exit__ = MagicMock(return_value=None)
        mock_psycopg2_connect.return_value = mock_conn

        config = ConnectionConfig(
            engine="yugabytedb",
            host="localhost",
            port=5433,
            database="yugabyte",
            username="yugabyte",
            password="yugabyte",
        )
        adapter = YugabyteDBAdapter(config)
        adapter.connect()

        report = adapter.execute_explain("SELECT * FROM users")

        assert isinstance(report, QueryAnalysisReport)
        assert report.engine == "yugabytedb"


# ============================================================================
# TESTS - Registry Integration
# ============================================================================


class TestYugabyteDBAdapterRegistry:
    """Test adapter registry integration."""

    def test_registry_registers_yugabytedb_on_import(self) -> None:
        """Importing yugabytedb module registers adapter in registry."""
        # The @AdapterRegistry.register decorator should have registered it
        config = ConnectionConfig(
            engine="yugabytedb",
            host="localhost",
            port=5433,
            database="yugabyte",
            username="yugabyte",
            password="yugabyte",
        )
        adapter = AdapterRegistry.create("yugabytedb", config)

        assert isinstance(adapter, YugabyteDBAdapter)

    def test_registry_case_insensitive(self) -> None:
        """Registry lookup is case-insensitive."""
        config = ConnectionConfig(
            engine="yugabytedb",
            host="localhost",
            port=5433,
            database="yugabyte",
            username="yugabyte",
            password="yugabyte",
        )
        adapter1 = AdapterRegistry.create("yugabytedb", config)
        adapter2 = AdapterRegistry.create("YugabyteDB", config)
        adapter3 = AdapterRegistry.create("YUGABYTEDB", config)

        assert isinstance(adapter1, YugabyteDBAdapter)
        assert isinstance(adapter2, YugabyteDBAdapter)
        assert isinstance(adapter3, YugabyteDBAdapter)

    def test_adapter_inherits_seq_scan_threshold(self) -> None:
        """Adapter uses configurable seq_scan_threshold."""
        config_custom = ConnectionConfig(
            engine="yugabytedb",
            host="localhost",
            port=5433,
            database="yugabyte",
            username="yugabyte",
            password="yugabyte",
            extra={"seq_scan_threshold": 5000},
        )
        adapter = YugabyteDBAdapter(config_custom)

        assert adapter.parser.seq_scan_threshold == 5000
