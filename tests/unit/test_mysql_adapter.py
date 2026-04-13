import pytest

from query_analyzer.adapters.exceptions import QueryAnalysisError
from query_analyzer.adapters.models import ConnectionConfig, QueryAnalysisReport
from query_analyzer.adapters.sql.mysql import MySQLAdapter


@pytest.fixture
def mysql_config():
    return ConnectionConfig(
        engine="mysql",
        host="localhost",
        port=3306,
        database="test_db",
        username="test_user",
        password="test_password",
    )


@pytest.fixture
def in_memory_connection(mocker):
    mock_conn = mocker.MagicMock()
    mock_cursor = mocker.MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    return mock_conn, mock_cursor


class TestMySQLAdapterInit:
    def test_adapter_initialization(self, mysql_config):
        adapter = MySQLAdapter(mysql_config)

        assert adapter is not None
        assert adapter._config == mysql_config
        assert adapter.connection is None

    def test_adapter_has_parser(self, mysql_config):
        adapter = MySQLAdapter(mysql_config)

        assert adapter.parser is not None
        assert adapter.parser.__class__.__name__ == "MySQLExplainParser"


class TestMySQLAdapterConnection:
    def test_is_ddl_create_table(self, mysql_config):
        adapter = MySQLAdapter(mysql_config)

        assert adapter._is_ddl_statement("CREATE TABLE t (id INT)")
        assert adapter._is_ddl_statement("create table t (id INT)")
        assert adapter._is_ddl_statement("  CREATE TABLE t (id INT)")

    def test_is_ddl_alter_table(self, mysql_config):
        adapter = MySQLAdapter(mysql_config)

        assert adapter._is_ddl_statement("ALTER TABLE t ADD COLUMN c INT")
        assert adapter._is_ddl_statement("  ALTER TABLE t DROP COLUMN c")

    def test_is_ddl_drop_table(self, mysql_config):
        adapter = MySQLAdapter(mysql_config)

        assert adapter._is_ddl_statement("DROP TABLE t")
        assert adapter._is_ddl_statement("DROP TABLE IF EXISTS t")

    def test_is_ddl_truncate_table(self, mysql_config):
        adapter = MySQLAdapter(mysql_config)

        assert adapter._is_ddl_statement("TRUNCATE TABLE t")

    def test_is_not_ddl_select(self, mysql_config):
        adapter = MySQLAdapter(mysql_config)

        assert not adapter._is_ddl_statement("SELECT * FROM t")

    def test_is_not_ddl_insert(self, mysql_config):
        adapter = MySQLAdapter(mysql_config)

        assert not adapter._is_ddl_statement("INSERT INTO t VALUES (1)")

    def test_is_not_ddl_update(self, mysql_config):
        adapter = MySQLAdapter(mysql_config)

        assert not adapter._is_ddl_statement("UPDATE t SET c = 1")

    def test_is_not_ddl_delete(self, mysql_config):
        adapter = MySQLAdapter(mysql_config)

        assert not adapter._is_ddl_statement("DELETE FROM t WHERE id = 1")

    def test_is_ddl_with_leading_comment(self, mysql_config):
        adapter = MySQLAdapter(mysql_config)

        assert adapter._is_ddl_statement("-- This is a comment\nCREATE TABLE t (id INT)")

    def test_is_not_connected_initially(self, mysql_config):
        adapter = MySQLAdapter(mysql_config)

        assert not adapter.is_connected()


class TestMySQLAdapterExplain:
    def test_execute_explain_rejects_ddl(self, mysql_config, mocker):
        adapter = MySQLAdapter(mysql_config)

        mocker.patch.object(adapter, "is_connected", return_value=True)

        with pytest.raises(QueryAnalysisError) as exc_info:
            adapter.execute_explain("CREATE TABLE t (id INT)")

        assert "DDL statements" in str(exc_info.value)

    def test_execute_explain_requires_connection(self, mysql_config):
        adapter = MySQLAdapter(mysql_config)

        with pytest.raises(QueryAnalysisError) as exc_info:
            adapter.execute_explain("SELECT * FROM t")

        assert "Not connected" in str(exc_info.value)

    def test_execute_explain_returns_report(self, mysql_config, mocker):
        adapter = MySQLAdapter(mysql_config)

        mock_conn = mocker.MagicMock()
        mock_cursor = mocker.MagicMock()
        mock_cursor.fetchone.return_value = (
            '{"query_block": {"table": {"table_name": "t", "access_type": "ALL"}}}',
        )
        mock_conn.cursor.return_value = mock_cursor
        adapter.connection = mock_conn

        report = adapter.execute_explain("SELECT * FROM t")

        assert isinstance(report, QueryAnalysisReport)
        assert report.engine == "mysql"
        assert report.query == "SELECT * FROM t"
        assert 0 <= report.score <= 100

    def test_execute_explain_detects_full_scan(self, mysql_config, mocker):
        adapter = MySQLAdapter(mysql_config)

        mock_conn = mocker.MagicMock()
        mock_cursor = mocker.MagicMock()
        mock_cursor.fetchone.return_value = (
            '{"query_block": {"table": {"table_name": "customers", "access_type": "ALL", "rows_examined": 1000}}}',
        )
        mock_conn.cursor.return_value = mock_cursor
        adapter.connection = mock_conn

        report = adapter.execute_explain("SELECT * FROM customers")

        assert len(report.warnings) > 0
        # MySQL full scan with ALL access type and SELECT * - should warn about both
        assert any("scan" in w.message.lower() or "SELECT *" in w.message for w in report.warnings)
        assert report.score < 100  # Should be penalized

    def test_execute_explain_detects_indexed(self, mysql_config, mocker):
        adapter = MySQLAdapter(mysql_config)

        mock_conn = mocker.MagicMock()
        mock_cursor = mocker.MagicMock()
        mock_cursor.fetchone.return_value = (
            '{"query_block": {"table": {"table_name": "orders", "access_type": "ref", "key": "idx_cust_id"}}}',
        )
        mock_conn.cursor.return_value = mock_cursor
        adapter.connection = mock_conn

        report = adapter.execute_explain("SELECT * FROM orders WHERE customer_id = 1")

        # Should have SELECT * warning but not a scan warning (because indexed)
        assert any("SELECT *" in w.message for w in report.warnings)
        # Should not have full scan warning
        assert not any(
            "scan" in w.message.lower() and "full" in w.message.lower() for w in report.warnings
        )
        assert report.score >= 90  # Good score with index

    def test_execute_explain_with_filesort(self, mysql_config, mocker):
        adapter = MySQLAdapter(mysql_config)

        mock_conn = mocker.MagicMock()
        mock_cursor = mocker.MagicMock()
        mock_cursor.fetchone.return_value = (
            '{"query_block": {"table": {"table_name": "t", "access_type": "ALL"}, "order_by": [{"filesort": true}]}}',
        )
        mock_conn.cursor.return_value = mock_cursor
        adapter.connection = mock_conn

        report = adapter.execute_explain("SELECT * FROM t ORDER BY col")

        # Expect warnings (either filesort or SELECT * or both)
        assert len(report.warnings) > 0
        assert report.score < 100

    def test_get_metrics_structure(self, mysql_config, mocker):
        adapter = MySQLAdapter(mysql_config)

        mock_conn = mocker.MagicMock()
        mock_cursor = mocker.MagicMock()

        def cursor_side_effect():
            cursor = mocker.MagicMock()
            return cursor

        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.side_effect = [(5,), (3,), (1024000,), (0,)]
        adapter.connection = mock_conn

        metrics = adapter.get_metrics()

        assert "tables" in metrics
        assert "indexes" in metrics
        assert "database_size_bytes" in metrics
        assert "slow_queries_count" in metrics

    def test_get_engine_info_structure(self, mysql_config, mocker):
        adapter = MySQLAdapter(mysql_config)

        mock_conn = mocker.MagicMock()
        adapter.connection = mock_conn

        engine_info = adapter.get_engine_info()

        assert engine_info["engine"] == "mysql"
        assert "version" in engine_info

    def test_get_slow_queries_returns_list(self, mysql_config, mocker):
        adapter = MySQLAdapter(mysql_config)

        mock_conn = mocker.MagicMock()
        mock_cursor = mocker.MagicMock()
        mock_cursor.fetchall.return_value = [
            ("SELECT * FROM t", 2000),
        ]
        mock_conn.cursor.return_value = mock_cursor
        adapter.connection = mock_conn

        slow_queries = adapter.get_slow_queries(1000)

        assert isinstance(slow_queries, list)

    def test_test_connection_success(self, mysql_config, mocker):
        adapter = MySQLAdapter(mysql_config)

        mock_conn = mocker.MagicMock()
        mock_cursor = mocker.MagicMock()
        mock_cursor.fetchone.return_value = (1,)
        mock_conn.cursor.return_value = mock_cursor
        adapter.connection = mock_conn

        assert adapter.test_connection() is True

    def test_test_connection_failure(self, mysql_config):
        adapter = MySQLAdapter(mysql_config)

        assert adapter.test_connection() is False

    def test_is_connected_false(self, mysql_config):
        adapter = MySQLAdapter(mysql_config)

        assert adapter.is_connected() is False

    def test_disconnect(self, mysql_config, mocker):
        adapter = MySQLAdapter(mysql_config)

        mock_conn = mocker.MagicMock()
        adapter.connection = mock_conn

        adapter.disconnect()

        mock_conn.close.assert_called_once()
        assert adapter.connection is None


class TestMySQLAdapterDML:
    def test_select_statement(self, mysql_config, mocker):
        adapter = MySQLAdapter(mysql_config)

        mock_conn = mocker.MagicMock()
        mock_cursor = mocker.MagicMock()
        mock_cursor.fetchone.return_value = (
            '{"query_block": {"table": {"table_name": "t", "access_type": "ref"}}}',
        )
        mock_conn.cursor.return_value = mock_cursor
        adapter.connection = mock_conn

        report = adapter.execute_explain("SELECT id, name FROM customers")

        assert report is not None
        assert isinstance(report, QueryAnalysisReport)

    def test_insert_statement(self, mysql_config, mocker):
        adapter = MySQLAdapter(mysql_config)

        mock_conn = mocker.MagicMock()
        mock_cursor = mocker.MagicMock()
        mock_cursor.fetchone.return_value = (
            '{"query_block": {"table": {"table_name": "t", "access_type": "ALL"}}}',
        )
        mock_conn.cursor.return_value = mock_cursor
        adapter.connection = mock_conn

        report = adapter.execute_explain("INSERT INTO customers VALUES (1, 'John')")

        assert report is not None

    def test_update_statement(self, mysql_config, mocker):
        adapter = MySQLAdapter(mysql_config)

        mock_conn = mocker.MagicMock()
        mock_cursor = mocker.MagicMock()
        mock_cursor.fetchone.return_value = (
            '{"query_block": {"table": {"table_name": "t", "access_type": "ref"}}}',
        )
        mock_conn.cursor.return_value = mock_cursor
        adapter.connection = mock_conn

        report = adapter.execute_explain("UPDATE customers SET name = 'Jane' WHERE id = 1")

        assert report is not None

    def test_delete_statement(self, mysql_config, mocker):
        adapter = MySQLAdapter(mysql_config)

        mock_conn = mocker.MagicMock()
        mock_cursor = mocker.MagicMock()
        mock_cursor.fetchone.return_value = (
            '{"query_block": {"table": {"table_name": "t", "access_type": "ref"}}}',
        )
        mock_conn.cursor.return_value = mock_cursor
        adapter.connection = mock_conn

        report = adapter.execute_explain("DELETE FROM customers WHERE id = 1")

        assert report is not None
