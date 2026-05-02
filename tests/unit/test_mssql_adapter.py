"""Unit tests for MSSQL adapter."""

from unittest.mock import MagicMock, patch

import pytest

from query_analyzer.adapters import (
    AdapterRegistry,
    ConnectionConfig,
    QueryAnalysisReport,
)
from query_analyzer.adapters.exceptions import ConnectionError, QueryAnalysisError

mssql_import_path = "query_analyzer.adapters.sql.sqlserver.pymssql"


@pytest.fixture
def mssql_config() -> ConnectionConfig:
    """Valid SQL Server connection config."""
    return ConnectionConfig(
        engine="mssql",
        host="localhost",
        port=1433,
        database="test_db",
        username="sa",
        password="TestPass123!",
        extra={"seq_scan_threshold": 10000},
    )


SAMPLE_SHOWPLAN_XML = """<?xml version="1.0" encoding="utf-16"?>
<ShowPlanXML xmlns="http://schemas.microsoft.com/sqlserver/2004/07/showplan">
  <BatchSequence>
    <Batch>
      <Statements>
        <StmtSimple StatementText="SELECT * FROM users WHERE id = 1">
          <QueryPlan CachedPlanSize="16">
            <RelOp NodeId="0" PhysicalOp="Clustered Index Seek"
                   LogicalOp="Clustered Index Seek"
                   EstimateRows="1" EstimatedTotalSubtreeCost="0.0032831">
              <Object Database="[test]" Schema="[dbo]" Table="[users]"
                      Index="[pk_users]" />
            </RelOp>
          </QueryPlan>
        </StmtSimple>
      </Statements>
    </Batch>
  </BatchSequence>
</ShowPlanXML>"""


class TestMSSQLAdapterInstantiation:
    """MSSQL adapter creation and initialization."""

    def test_instantiate_with_valid_config(self, mssql_config: ConnectionConfig) -> None:
        adapter = None
        try:
            from query_analyzer.adapters.sql.sqlserver import MSSQLAdapter

            adapter = MSSQLAdapter(mssql_config)
        except ImportError:
            pytest.skip("MSSQLAdapter not available (pymssql missing)")

        assert adapter._config == mssql_config
        assert adapter._is_connected is False
        assert adapter._connection is None
        assert hasattr(adapter, "parser")
        assert hasattr(adapter, "metrics_helper")

    def test_registry_can_create_mssql_adapter(self, mssql_config: ConnectionConfig) -> None:
        if not AdapterRegistry.is_registered("mssql"):
            pytest.skip("MSSQL adapter not registered (pymssql may be missing)")
        adapter = AdapterRegistry.create("mssql", mssql_config)
        assert adapter._config == mssql_config

    def test_registry_case_insensitive(self, mssql_config: ConnectionConfig) -> None:
        if not AdapterRegistry.is_registered("mssql"):
            pytest.skip("MSSQL adapter not registered")
        adapter1 = AdapterRegistry.create("mssql", mssql_config)
        adapter2 = AdapterRegistry.create("MSSQL", mssql_config)
        assert adapter1 is not None
        assert adapter2 is not None


class TestMSSQLAdapterConnection:
    """Connection lifecycle tests."""

    def test_connect_success(self, mssql_config: ConnectionConfig) -> None:
        try:
            from query_analyzer.adapters.sql.sqlserver import MSSQLAdapter
        except ImportError:
            pytest.skip("MSSQLAdapter not available")

        with patch(f"{mssql_import_path}.connect") as mock_connect:
            mock_connection = MagicMock()
            mock_connect.return_value = mock_connection

            adapter = MSSQLAdapter(mssql_config)
            adapter.connect()

            assert adapter._is_connected is True
            assert adapter._connection == mock_connection
            mock_connect.assert_called_once()

    def test_connect_failure(self, mssql_config: ConnectionConfig) -> None:
        try:
            from query_analyzer.adapters.sql.sqlserver import MSSQLAdapter, pymssql
        except ImportError:
            pytest.skip("MSSQLAdapter not available")

        with patch(f"{mssql_import_path}.connect") as mock_connect:
            mock_connect.side_effect = pymssql.OperationalError("Connection refused")

            adapter = MSSQLAdapter(mssql_config)
            with pytest.raises(ConnectionError, match="Failed to connect"):
                adapter.connect()
            assert adapter._is_connected is False

    def test_disconnect(self, mssql_config: ConnectionConfig) -> None:
        try:
            from query_analyzer.adapters.sql.sqlserver import MSSQLAdapter
        except ImportError:
            pytest.skip("MSSQLAdapter not available")

        with patch(f"{mssql_import_path}.connect") as mock_connect:
            mock_connection = MagicMock()
            mock_connect.return_value = mock_connection

            adapter = MSSQLAdapter(mssql_config)
            adapter.connect()
            adapter.disconnect()

            assert adapter._is_connected is False
            mock_connection.close.assert_called_once()

    def test_context_manager(self, mssql_config: ConnectionConfig) -> None:
        try:
            from query_analyzer.adapters.sql.sqlserver import MSSQLAdapter
        except ImportError:
            pytest.skip("MSSQLAdapter not available")

        with patch(f"{mssql_import_path}.connect") as mock_connect:
            mock_connection = MagicMock()
            mock_connect.return_value = mock_connection

            with MSSQLAdapter(mssql_config) as adapter:
                assert adapter._is_connected is True

            assert adapter._is_connected is False
            mock_connection.close.assert_called_once()


class TestMSSQLAdapterConnectionTest:
    """test_connection() method tests."""

    def test_test_connection_success(self, mssql_config: ConnectionConfig) -> None:
        try:
            from query_analyzer.adapters.sql.sqlserver import MSSQLAdapter
        except ImportError:
            pytest.skip("MSSQLAdapter not available")

        with patch(f"{mssql_import_path}.connect") as mock_connect:
            mock_connection = MagicMock()
            mock_cursor = MagicMock()
            mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
            mock_cursor.__exit__ = MagicMock(return_value=None)
            mock_connection.cursor.return_value = mock_cursor
            mock_connect.return_value = mock_connection

            adapter = MSSQLAdapter(mssql_config)
            adapter.connect()

            assert adapter.test_connection() is True
            mock_cursor.execute.assert_called_with("SELECT 1")

    def test_test_connection_when_not_connected(self, mssql_config: ConnectionConfig) -> None:
        try:
            from query_analyzer.adapters.sql.sqlserver import MSSQLAdapter
        except ImportError:
            pytest.skip("MSSQLAdapter not available")

        adapter = MSSQLAdapter(mssql_config)
        assert adapter.test_connection() is False


class TestMSSQLAdapterExplain:
    """EXPLAIN analysis tests."""

    def test_rejects_ddl(self, mssql_config: ConnectionConfig) -> None:
        try:
            from query_analyzer.adapters.sql.sqlserver import MSSQLAdapter
        except ImportError:
            pytest.skip("MSSQLAdapter not available")

        with patch(f"{mssql_import_path}.connect"):
            adapter = MSSQLAdapter(mssql_config)
            adapter.connect()
            with pytest.raises(QueryAnalysisError, match="DDL"):
                adapter.execute_explain("CREATE TABLE test (id INT)")

    def test_execute_explain_returns_report(self, mssql_config: ConnectionConfig) -> None:
        try:
            from query_analyzer.adapters.sql.sqlserver import MSSQLAdapter
        except ImportError:
            pytest.skip("MSSQLAdapter not available")

        with patch(f"{mssql_import_path}.connect") as mock_connect:
            mock_connection = MagicMock()
            mock_cursor = MagicMock()
            mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
            mock_cursor.__exit__ = MagicMock(return_value=None)
            mock_cursor.fetchone.return_value = (SAMPLE_SHOWPLAN_XML,)
            mock_connection.cursor.return_value = mock_cursor
            mock_connect.return_value = mock_connection

            adapter = MSSQLAdapter(mssql_config)
            adapter.connect()

            report = adapter.execute_explain("SELECT * FROM users WHERE id = 1")

            assert isinstance(report, QueryAnalysisReport)
            assert report.engine == "mssql"
            assert 0 <= report.score <= 100
            assert "xml" in report.raw_plan

            # Verify SHOWPLAN_XML was properly toggled
            cursor_calls = [c[0][0] for c in mock_cursor.execute.call_args_list]
            assert "SET SHOWPLAN_XML ON" in cursor_calls
            assert "SET SHOWPLAN_XML OFF" in cursor_calls

    def test_execute_explain_requires_connection(self, mssql_config: ConnectionConfig) -> None:
        try:
            from query_analyzer.adapters.sql.sqlserver import MSSQLAdapter
        except ImportError:
            pytest.skip("MSSQLAdapter not available")

        adapter = MSSQLAdapter(mssql_config)
        with pytest.raises(QueryAnalysisError, match="Not connected"):
            adapter.execute_explain("SELECT 1")

    def test_showplan_off_on_error(self, mssql_config: ConnectionConfig) -> None:
        try:
            from query_analyzer.adapters.sql.sqlserver import MSSQLAdapter
        except ImportError:
            pytest.skip("MSSQLAdapter not available")

        with patch(f"{mssql_import_path}.connect") as mock_connect:
            mock_connection = MagicMock()
            mock_cursor = MagicMock()
            mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
            mock_cursor.__exit__ = MagicMock(return_value=None)

            # Step 1 succeeds (SET SHOWPLAN_XML ON), step 2 (query) fails
            mock_cursor.execute.side_effect = [None, RuntimeError("Query failed")]
            mock_connection.cursor.return_value = mock_cursor
            mock_connect.return_value = mock_connection

            adapter = MSSQLAdapter(mssql_config)
            adapter.connect()

            with pytest.raises(QueryAnalysisError, match="Failed to analyze"):
                adapter.execute_explain("SELECT * FROM users")

            # Must have called SET SHOWPLAN_XML OFF in error handler
            off_calls = [
                c for c in mock_cursor.execute.call_args_list if "SET SHOWPLAN_XML OFF" in str(c)
            ]
            assert len(off_calls) >= 1
            mock_connection.rollback.assert_called_once()


class TestMSSQLAdapterSlowQueries:
    """Slow query detection tests."""

    def test_returns_empty_when_not_connected(self, mssql_config: ConnectionConfig) -> None:
        try:
            from query_analyzer.adapters.sql.sqlserver import MSSQLAdapter
        except ImportError:
            pytest.skip("MSSQLAdapter not available")

        adapter = MSSQLAdapter(mssql_config)
        assert adapter.get_slow_queries() == []


class TestMSSQLAdapterMetrics:
    """Metrics retrieval tests."""

    def test_returns_empty_when_not_connected(self, mssql_config: ConnectionConfig) -> None:
        try:
            from query_analyzer.adapters.sql.sqlserver import MSSQLAdapter
        except ImportError:
            pytest.skip("MSSQLAdapter not available")

        adapter = MSSQLAdapter(mssql_config)
        assert adapter.get_metrics() == {}
        assert adapter.get_engine_info() == {}


class TestMSSQLAdapterState:
    """is_connected() state tracking tests."""

    def test_is_connected_lifecycle(self, mssql_config: ConnectionConfig) -> None:
        try:
            from query_analyzer.adapters.sql.sqlserver import MSSQLAdapter
        except ImportError:
            pytest.skip("MSSQLAdapter not available")

        with patch(f"{mssql_import_path}.connect") as mock_connect:
            mock_connect.return_value = MagicMock()

            adapter = MSSQLAdapter(mssql_config)
            assert adapter.is_connected() is False

            adapter.connect()
            assert adapter.is_connected() is True

            adapter.disconnect()
            assert adapter.is_connected() is False
