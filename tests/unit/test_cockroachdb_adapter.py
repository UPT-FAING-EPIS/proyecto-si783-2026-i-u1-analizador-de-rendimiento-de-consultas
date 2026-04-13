"""Unit tests for CockroachDB adapter (mock-based, no real DB)."""

from unittest.mock import MagicMock, Mock, patch

import pytest

from query_analyzer.adapters import CockroachDBAdapter, ConnectionConfig
from query_analyzer.adapters.exceptions import QueryAnalysisError
from query_analyzer.adapters.models import QueryAnalysisReport
from query_analyzer.adapters.sql.cockroachdb_parser import CockroachDBParser


class TestCockroachDBAdapterInit:
    """Test adapter initialization."""

    def test_adapter_initializes_with_config(self):
        """CockroachDBAdapter initializes with ConnectionConfig."""
        config = ConnectionConfig(
            engine="cockroachdb",
            host="localhost",
            port=26257,
            database="defaultdb",
            username="root",
            password=None,
        )
        adapter = CockroachDBAdapter(config)

        assert adapter._config == config
        assert adapter._is_connected is False
        assert adapter.parser is not None
        assert isinstance(adapter.parser, CockroachDBParser)
        assert adapter.metrics_helper is not None

    def test_adapter_is_base_adapter_subclass(self):
        """CockroachDBAdapter inherits from BaseAdapter."""
        from query_analyzer.adapters.base import BaseAdapter

        config = ConnectionConfig(
            engine="cockroachdb",
            host="localhost",
            port=26257,
            database="defaultdb",
            username="root",
            password=None,
        )
        adapter = CockroachDBAdapter(config)
        assert isinstance(adapter, BaseAdapter)


class TestCockroachDBAdapterConnection:
    """Test connection management."""

    @patch("query_analyzer.adapters.sql.cockroachdb.psycopg2.connect")
    def test_connect_success(self, mock_psycopg2_connect):
        """connect() succeeds and sets _is_connected."""
        mock_conn = Mock()
        mock_psycopg2_connect.return_value = mock_conn

        config = ConnectionConfig(
            engine="cockroachdb",
            host="localhost",
            port=26257,
            database="defaultdb",
            username="root",
            password=None,
        )
        adapter = CockroachDBAdapter(config)
        adapter.connect()

        assert adapter._is_connected is True
        assert adapter._connection == mock_conn
        mock_psycopg2_connect.assert_called_once()

    @patch("query_analyzer.adapters.sql.cockroachdb.psycopg2.connect")
    def test_connect_failure(self, mock_psycopg2_connect):
        """connect() raises ConnectionError on psycopg2 failure."""
        from psycopg2 import OperationalError

        mock_psycopg2_connect.side_effect = OperationalError("Connection failed")

        config = ConnectionConfig(
            engine="cockroachdb",
            host="localhost",
            port=26257,
            database="defaultdb",
            username="root",
            password=None,
        )
        adapter = CockroachDBAdapter(config)

        with pytest.raises(Exception):  # ConnectionError
            adapter.connect()

        assert adapter._is_connected is False

    def test_disconnect(self):
        """disconnect() closes connection and resets state."""
        config = ConnectionConfig(
            engine="cockroachdb",
            host="localhost",
            port=26257,
            database="defaultdb",
            username="root",
            password=None,
        )
        adapter = CockroachDBAdapter(config)

        # Mock connected state
        mock_conn = Mock()
        adapter._connection = mock_conn
        adapter._is_connected = True

        adapter.disconnect()

        assert adapter._is_connected is False
        assert adapter._connection is None
        mock_conn.close.assert_called_once()

    def test_test_connection_true(self):
        """test_connection() returns True when SELECT 1 succeeds."""
        config = ConnectionConfig(
            engine="cockroachdb",
            host="localhost",
            port=26257,
            database="defaultdb",
            username="root",
            password=None,
        )
        adapter = CockroachDBAdapter(config)

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

    def test_test_connection_false_not_connected(self):
        """test_connection() returns False if not connected."""
        config = ConnectionConfig(
            engine="cockroachdb",
            host="localhost",
            port=26257,
            database="defaultdb",
            username="root",
            password=None,
        )
        adapter = CockroachDBAdapter(config)
        adapter._is_connected = False

        result = adapter.test_connection()

        assert result is False


class TestCockroachDBAdapterExplain:
    """Test EXPLAIN execution."""

    def test_execute_explain_not_connected(self):
        """execute_explain() raises error if not connected."""
        config = ConnectionConfig(
            engine="cockroachdb",
            host="localhost",
            port=26257,
            database="defaultdb",
            username="root",
            password=None,
        )
        adapter = CockroachDBAdapter(config)
        adapter._is_connected = False

        with pytest.raises(QueryAnalysisError, match="Not connected"):
            adapter.execute_explain("SELECT 1")

    def test_execute_explain_rejects_ddl_create(self):
        """execute_explain() rejects CREATE statements."""
        config = ConnectionConfig(
            engine="cockroachdb",
            host="localhost",
            port=26257,
            database="defaultdb",
            username="root",
            password=None,
        )
        adapter = CockroachDBAdapter(config)
        adapter._is_connected = True

        with pytest.raises(QueryAnalysisError, match="Cannot analyze DDL"):
            adapter.execute_explain("CREATE TABLE test (id INT)")

    def test_execute_explain_rejects_ddl_alter(self):
        """execute_explain() rejects ALTER statements."""
        config = ConnectionConfig(
            engine="cockroachdb",
            host="localhost",
            port=26257,
            database="defaultdb",
            username="root",
            password=None,
        )
        adapter = CockroachDBAdapter(config)
        adapter._is_connected = True

        with pytest.raises(QueryAnalysisError, match="Cannot analyze DDL"):
            adapter.execute_explain("ALTER TABLE test ADD COLUMN x INT")

    def test_execute_explain_json_success(self):
        """execute_explain() succeeds with JSON format."""
        config = ConnectionConfig(
            engine="cockroachdb",
            host="localhost",
            port=26257,
            database="defaultdb",
            username="root",
            password=None,
        )
        adapter = CockroachDBAdapter(config)
        adapter._is_connected = True

        # Mock cursor returning JSON
        mock_cursor = MagicMock()
        mock_explain_json = {
            "Plan": {
                "Node Type": "Scan",
                "Table": "test",
                "Total Cost": 100.0,
                "Plan Rows": 1000,
                "Actual Rows": 950,
            },
            "Planning Time": 1.0,
            "Execution Time": 5.0,
        }
        # psycopg2 returns list as result[0]
        mock_cursor.fetchone.return_value = ([mock_explain_json],)

        mock_conn = MagicMock()
        mock_conn.cursor = MagicMock(return_value=mock_cursor)
        mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
        mock_cursor.__exit__ = MagicMock(return_value=None)

        adapter._connection = mock_conn

        report = adapter.execute_explain("SELECT * FROM test")

        assert isinstance(report, QueryAnalysisReport)
        assert report.engine == "cockroachdb"
        assert report.query == "SELECT * FROM test"
        assert 0 <= report.score <= 100

    def test_execute_explain_json_fallback_to_text(self):
        """execute_explain() falls back to text when JSON fails."""
        config = ConnectionConfig(
            engine="cockroachdb",
            host="localhost",
            port=26257,
            database="defaultdb",
            username="root",
            password=None,
        )
        adapter = CockroachDBAdapter(config)
        adapter._is_connected = True

        # Mock cursor: first call (DISTSQL) fails, second call (JSON) fails, third call (text) succeeds
        mock_cursor = MagicMock()
        mock_cursor.execute.side_effect = [
            Exception("DISTSQL not supported"),  # DISTSQL fails
            Exception("JSON format not supported"),  # JSON fails
            None,  # Text succeeds
        ]
        mock_cursor.fetchone.return_value = None  # No JSON result
        mock_cursor.fetchall.return_value = [("Seq Scan",), ("Full scan",)]

        mock_conn = MagicMock()
        mock_conn.cursor = MagicMock(return_value=mock_cursor)
        mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
        mock_cursor.__exit__ = MagicMock(return_value=None)

        adapter._connection = mock_conn

        report = adapter.execute_explain("SELECT * FROM test")

        assert isinstance(report, QueryAnalysisReport)
        # Verify fallback happened by checking execute called three times (DISTSQL, JSON, ANALYZE)
        assert mock_cursor.execute.call_count == 3

    def test_execute_explain_detects_full_scan_warning(self):
        """execute_explain() detects full scan in text output."""
        config = ConnectionConfig(
            engine="cockroachdb",
            host="localhost",
            port=26257,
            database="defaultdb",
            username="root",
            password=None,
        )
        adapter = CockroachDBAdapter(config)
        adapter._is_connected = True

        # Mock cursor: DISTSQL fails, JSON fails, text succeeds
        mock_cursor = MagicMock()

        # Track which execute() call we're on
        def execute_side_effect(query):
            if "DISTSQL" in query:
                raise Exception("DISTSQL not supported")
            elif "FORMAT JSON" in query:
                raise Exception("JSON parsing failed")
            # Text format succeeds

        mock_cursor.execute.side_effect = execute_side_effect
        mock_cursor.fetchall.return_value = [("Seq Scan on large_table",), ("Full scan",)]
        mock_cursor.fetchone.return_value = None

        mock_conn = MagicMock()
        mock_conn.cursor = MagicMock(return_value=mock_cursor)
        mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
        mock_cursor.__exit__ = MagicMock(return_value=None)

        adapter._connection = mock_conn

        report = adapter.execute_explain("SELECT * FROM large_table")

        # Should have at least one warning
        assert len(report.warnings) > 0
        # At least one should mention "full" or "scan"
        assert any(
            "full" in w.message.lower() or "scan" in w.message.lower() for w in report.warnings
        )

    def test_execute_explain_detects_cross_region_warning(self):
        """execute_explain() detects cross-region full scan (CRITICAL)."""
        config = ConnectionConfig(
            engine="cockroachdb",
            host="localhost",
            port=26257,
            database="defaultdb",
            username="root",
            password=None,
        )
        adapter = CockroachDBAdapter(config)
        adapter._is_connected = True

        # Mock cursor: DISTSQL fails, JSON fails, text succeeds
        mock_cursor = MagicMock()

        def execute_side_effect(query):
            if "DISTSQL" in query:
                raise Exception("DISTSQL not supported")
            elif "FORMAT JSON" in query:
                raise Exception("JSON parsing failed")
            # Text format succeeds

        mock_cursor.execute.side_effect = execute_side_effect
        mock_cursor.fetchall.return_value = [
            ("Distributed execution across regions",),
            ("Full scan on us-east-1 region",),
        ]
        mock_cursor.fetchone.return_value = None

        mock_conn = MagicMock()
        mock_conn.cursor = MagicMock(return_value=mock_cursor)
        mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
        mock_cursor.__exit__ = MagicMock(return_value=None)

        adapter._connection = mock_conn

        report = adapter.execute_explain("SELECT * FROM global_table")

        # Should have cross-region warning
        assert len(report.warnings) > 0
        # Check for CRITICAL warning
        assert any("critical" in w.message.lower() for w in report.warnings)


class TestCockroachDBAdapterMetrics:
    """Test metrics and engine info methods."""

    def test_get_metrics_success(self):
        """get_metrics() returns dict with engine + version."""
        config = ConnectionConfig(
            engine="cockroachdb",
            host="localhost",
            port=26257,
            database="defaultdb",
            username="root",
            password=None,
        )
        adapter = CockroachDBAdapter(config)
        adapter._is_connected = True

        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = ("CockroachDB v23.2.0",)
        mock_conn = MagicMock()
        mock_conn.cursor = MagicMock(return_value=mock_cursor)
        mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
        mock_cursor.__exit__ = MagicMock(return_value=None)

        adapter._connection = mock_conn

        metrics = adapter.get_metrics()

        assert isinstance(metrics, dict)
        assert metrics["engine"] == "cockroachdb"
        assert "version" in metrics

    def test_get_metrics_permission_error(self):
        """get_metrics() catches permission error, returns minimal dict."""
        config = ConnectionConfig(
            engine="cockroachdb",
            host="localhost",
            port=26257,
            database="defaultdb",
            username="root",
            password=None,
        )
        adapter = CockroachDBAdapter(config)
        adapter._is_connected = True

        mock_cursor = MagicMock()
        mock_cursor.fetchone.side_effect = Exception("Permission denied")
        mock_conn = MagicMock()
        mock_conn.cursor = MagicMock(return_value=mock_cursor)
        mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
        mock_cursor.__exit__ = MagicMock(return_value=None)

        adapter._connection = mock_conn

        metrics = adapter.get_metrics()

        # Should return minimal dict without error field
        assert isinstance(metrics, dict)
        assert metrics["engine"] == "cockroachdb"
        assert "error" not in metrics

    def test_get_metrics_not_connected(self):
        """get_metrics() returns minimal dict if not connected."""
        config = ConnectionConfig(
            engine="cockroachdb",
            host="localhost",
            port=26257,
            database="defaultdb",
            username="root",
            password=None,
        )
        adapter = CockroachDBAdapter(config)
        adapter._is_connected = False

        metrics = adapter.get_metrics()

        assert metrics == {"engine": "cockroachdb"}

    def test_get_engine_info_success(self):
        """get_engine_info() returns version + engine."""
        config = ConnectionConfig(
            engine="cockroachdb",
            host="localhost",
            port=26257,
            database="defaultdb",
            username="root",
            password=None,
        )
        adapter = CockroachDBAdapter(config)
        adapter._is_connected = True

        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = ("CockroachDB v23.2.0",)
        mock_conn = MagicMock()
        mock_conn.cursor = MagicMock(return_value=mock_cursor)
        mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
        mock_cursor.__exit__ = MagicMock(return_value=None)

        adapter._connection = mock_conn

        info = adapter.get_engine_info()

        assert isinstance(info, dict)
        assert info["engine"] == "cockroachdb"
        assert "version" in info

    def test_get_engine_info_not_connected(self):
        """get_engine_info() returns empty dict if not connected."""
        config = ConnectionConfig(
            engine="cockroachdb",
            host="localhost",
            port=26257,
            database="defaultdb",
            username="root",
            password=None,
        )
        adapter = CockroachDBAdapter(config)
        adapter._is_connected = False

        info = adapter.get_engine_info()

        assert info == {}

    def test_get_slow_queries_not_implemented(self):
        """get_slow_queries() returns empty list (not implemented in v1)."""
        config = ConnectionConfig(
            engine="cockroachdb",
            host="localhost",
            port=26257,
            database="defaultdb",
            username="root",
            password=None,
        )
        adapter = CockroachDBAdapter(config)

        queries = adapter.get_slow_queries(threshold_ms=1000)

        assert isinstance(queries, list)
        assert len(queries) == 0


class TestCockroachDBAdapterRegistry:
    """Test adapter registration."""

    def test_adapter_registered_in_registry(self):
        """CockroachDBAdapter is registered as 'cockroachdb'."""
        from query_analyzer.adapters.registry import AdapterRegistry

        assert AdapterRegistry.is_registered("cockroachdb")

    def test_adapter_can_be_created_by_registry(self):
        """AdapterRegistry.create('cockroachdb', ...) works."""
        from query_analyzer.adapters.registry import AdapterRegistry

        config = ConnectionConfig(
            engine="cockroachdb",
            host="localhost",
            port=26257,
            database="defaultdb",
            username="root",
            password=None,
        )
        adapter = AdapterRegistry.create("cockroachdb", config)

        assert isinstance(adapter, CockroachDBAdapter)
