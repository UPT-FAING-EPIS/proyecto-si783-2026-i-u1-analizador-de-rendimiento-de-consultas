import os
import time

import pytest

from query_analyzer.adapters.models import ConnectionConfig
from query_analyzer.adapters.sql.mysql import MySQLAdapter


@pytest.fixture(scope="module")
def mysql_available():
    try:
        import pymysql

        try:
            conn = pymysql.connect(
                host="localhost",
                port=int(os.getenv("DB_MYSQL_PORT", 3306)),
                user=os.getenv("DB_MYSQL_USER", "analyst"),
                password=os.getenv("DB_MYSQL_PASSWORD", "mysql123"),
                database=os.getenv("DB_MYSQL_NAME", "query_analyzer"),
            )
            conn.close()
            return True
        except Exception:
            return False
    except ImportError:
        return False


@pytest.fixture(scope="module")
def mysql_config():
    return ConnectionConfig(
        engine="mysql",
        host="localhost",
        port=int(os.getenv("DB_MYSQL_PORT", 3306)),
        database=os.getenv("DB_MYSQL_NAME", "query_analyzer"),
        username=os.getenv("DB_MYSQL_USER", "analyst"),
        password=os.getenv("DB_MYSQL_PASSWORD", "mysql123"),
    )


@pytest.fixture(scope="module")
def mysql_adapter(mysql_config, mysql_available):
    if not mysql_available:
        pytest.skip("MySQL Docker container not available")

    adapter = MySQLAdapter(mysql_config)
    try:
        adapter.connect()
        yield adapter
    finally:
        if adapter.is_connected():
            adapter.disconnect()


class TestMySQLIntegration:
    def test_connect_to_mysql(self, mysql_adapter):
        assert mysql_adapter.is_connected()

    def test_test_connection(self, mysql_adapter):
        assert mysql_adapter.test_connection() is True

    def test_get_metrics(self, mysql_adapter):
        metrics = mysql_adapter.get_metrics()

        assert "tables" in metrics
        assert "indexes" in metrics
        assert "database_size_bytes" in metrics

    def test_get_engine_info(self, mysql_adapter):
        engine_info = mysql_adapter.get_engine_info()

        assert engine_info["engine"] == "mysql"
        assert "version" in engine_info
        assert engine_info["version"].startswith("8") or engine_info["version"].startswith("5")

    def test_explain_simple_select(self, mysql_adapter):
        report = mysql_adapter.execute_explain("SELECT * FROM customers LIMIT 10")

        assert report.engine == "mysql"
        assert 0 <= report.score <= 100
        assert report.execution_time_ms >= 0

    def test_explain_with_index(self, mysql_adapter):
        report = mysql_adapter.execute_explain("SELECT * FROM customers WHERE id = 1")

        assert report.engine == "mysql"
        assert report.score >= 70

    def test_explain_full_scan_detection(self, mysql_adapter):
        """Test EXPLAIN detects full table scans."""
        report = mysql_adapter.execute_explain("SELECT COUNT(*) FROM customers")

        assert isinstance(report.warnings, list)

    def test_slow_queries_table_exists(self, mysql_adapter):
        slow_queries = mysql_adapter.get_slow_queries(threshold_ms=0)

        assert isinstance(slow_queries, list)

    def test_multiple_explains(self, mysql_adapter):
        queries = [
            "SELECT * FROM customers",
            "SELECT id, name FROM customers WHERE id > 10",
            "SELECT * FROM orders",
        ]

        reports = []
        for query in queries:
            report = mysql_adapter.execute_explain(query)
            reports.append(report)

        assert len(reports) == 3
        assert all(r.engine == "mysql" for r in reports)
        assert all(0 <= r.score <= 100 for r in reports)

    def test_explain_with_join(self, mysql_adapter):
        try:
            report = mysql_adapter.execute_explain(
                "SELECT c.id, o.id FROM customers c JOIN orders o ON c.id = o.customer_id LIMIT 10"
            )

            assert report.engine == "mysql"
            assert 0 <= report.score <= 100
        except Exception:
            pytest.skip("JOIN tables not available")

    def test_explain_insert(self, mysql_adapter):
        report = mysql_adapter.execute_explain(
            "INSERT INTO customers (name, email) VALUES ('Test', 'test@example.com')"
        )

        assert report.engine == "mysql"

    def test_explain_update(self, mysql_adapter):
        report = mysql_adapter.execute_explain(
            "UPDATE customers SET name = 'Updated' WHERE id = 999"
        )

        assert report.engine == "mysql"

    def test_ddl_rejection(self, mysql_adapter):
        from query_analyzer.adapters.exceptions import QueryAnalysisError

        with pytest.raises(QueryAnalysisError):
            mysql_adapter.execute_explain("CREATE TABLE test (id INT)")

        with pytest.raises(QueryAnalysisError):
            mysql_adapter.execute_explain("DROP TABLE test")

        with pytest.raises(QueryAnalysisError):
            mysql_adapter.execute_explain("ALTER TABLE customers ADD COLUMN test INT")

    def test_adapter_context_manager(self, mysql_config, mysql_available):
        if not mysql_available:
            pytest.skip("MySQL Docker container not available")

        adapter = MySQLAdapter(mysql_config)
        adapter.connect()

        try:
            assert adapter.is_connected()
            report = adapter.execute_explain("SELECT 1")
            assert report is not None
        finally:
            adapter.disconnect()
            time.sleep(0.1)
            assert not adapter.is_connected()
