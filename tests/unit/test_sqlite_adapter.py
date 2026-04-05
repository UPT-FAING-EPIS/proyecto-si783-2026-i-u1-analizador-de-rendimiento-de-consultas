"""Tests for SQLiteAdapter."""

import pytest

from query_analyzer.adapters.exceptions import (
    QueryAnalysisError,
)
from query_analyzer.adapters.models import ConnectionConfig, QueryAnalysisReport
from query_analyzer.adapters.sql.sqlite import SQLiteAdapter


class TestSQLiteAdapterConnection:
    """Test suite for SQLiteAdapter connection management."""

    @pytest.fixture
    def in_memory_config(self):
        """Create config for in-memory database."""
        return ConnectionConfig(
            engine="sqlite",
            host="localhost",
            port=0,
            database=":memory:",
            username="",
            password="",
        )

    @pytest.fixture
    def file_db_config(self, tmp_path):
        """Create config for file-based database."""
        db_file = tmp_path / "test.db"
        return ConnectionConfig(
            engine="sqlite",
            host="localhost",
            port=0,
            database=str(db_file),
            username="",
            password="",
        )

    @pytest.fixture
    def in_memory_adapter(self, in_memory_config):
        """Create adapter for in-memory database."""
        return SQLiteAdapter(in_memory_config)

    @pytest.fixture
    def file_adapter(self, file_db_config):
        """Create adapter for file-based database."""
        return SQLiteAdapter(file_db_config)

    def test_adapter_initialization(self, in_memory_adapter):
        """Test adapter can be initialized."""
        assert in_memory_adapter is not None
        assert not in_memory_adapter.is_connected()

    def test_connect_in_memory(self, in_memory_adapter):
        """Test connecting to in-memory database."""
        in_memory_adapter.connect()

        assert in_memory_adapter.is_connected()
        in_memory_adapter.disconnect()

    def test_connect_file_database(self, file_adapter):
        """Test connecting to file-based database."""
        file_adapter.connect()

        assert file_adapter.is_connected()
        file_adapter.disconnect()

    def test_connect_creates_parent_directories(self, tmp_path):
        """Test that connect() creates parent directories."""
        nested_path = tmp_path / "deeply" / "nested" / "path" / "test.db"
        config = ConnectionConfig(
            engine="sqlite",
            host="localhost",
            port=0,
            database=str(nested_path),
            username="",
            password="",
        )
        adapter = SQLiteAdapter(config)

        adapter.connect()

        assert nested_path.parent.exists()
        adapter.disconnect()

    def test_disconnect(self, in_memory_adapter):
        """Test disconnection."""
        in_memory_adapter.connect()
        assert in_memory_adapter.is_connected()

        in_memory_adapter.disconnect()
        assert not in_memory_adapter.is_connected()

    def test_test_connection(self, in_memory_adapter):
        """Test connection validity check."""
        assert not in_memory_adapter.test_connection()

        in_memory_adapter.connect()
        assert in_memory_adapter.test_connection()

        in_memory_adapter.disconnect()
        assert not in_memory_adapter.test_connection()

    def test_context_manager(self, in_memory_adapter):
        """Test using adapter as context manager."""
        assert not in_memory_adapter.is_connected()

        with in_memory_adapter:
            assert in_memory_adapter.is_connected()

        assert not in_memory_adapter.is_connected()

    @pytest.fixture
    def connected_adapter(self, in_memory_adapter):
        """Connected adapter with test tables."""
        in_memory_adapter.connect()

        conn = in_memory_adapter.get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            CREATE TABLE customers (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                email TEXT UNIQUE,
                country TEXT
            )
        """
        )

        cursor.execute(
            """
            CREATE TABLE orders (
                id INTEGER PRIMARY KEY,
                customer_id INTEGER NOT NULL,
                status TEXT,
                total REAL,
                FOREIGN KEY (customer_id) REFERENCES customers(id)
            )
        """
        )

        cursor.execute("CREATE INDEX idx_orders_customer ON orders(customer_id)")

        conn.commit()

        yield in_memory_adapter

        in_memory_adapter.disconnect()

    def test_execute_explain_full_scan(self, connected_adapter):
        """Test EXPLAIN for full table scan."""
        query = "SELECT * FROM customers"
        report = connected_adapter.execute_explain(query)

        assert isinstance(report, QueryAnalysisReport)
        assert report.engine == "sqlite"
        assert report.query == query
        assert 0 <= report.score <= 100
        assert "customers" in report.raw_plan["full_scan_tables"]

    def test_execute_explain_indexed_search(self, connected_adapter):
        """Test EXPLAIN for indexed search."""
        query = "SELECT * FROM orders WHERE customer_id = 1"
        report = connected_adapter.execute_explain(query)

        assert isinstance(report, QueryAnalysisReport)
        assert report.score >= 70

    def test_execute_explain_generates_warnings(self, connected_adapter):
        """Test that full scans generate warnings."""
        query = "SELECT * FROM customers"
        report = connected_adapter.execute_explain(query)

        assert len(report.warnings) > 0
        assert any("scan" in w.lower() for w in report.warnings)

    def test_execute_explain_generates_recommendations(self, connected_adapter):
        """Test that recommendations are generated."""
        query = "SELECT * FROM customers"
        report = connected_adapter.execute_explain(query)

        assert len(report.recommendations) > 0

    def test_execute_explain_select_statement(self, connected_adapter):
        """Test EXPLAIN works with SELECT."""
        query = "SELECT id, name FROM customers"
        report = connected_adapter.execute_explain(query)

        assert report is not None

    def test_execute_explain_insert_statement(self, connected_adapter):
        """Test EXPLAIN works with INSERT."""
        query = "INSERT INTO customers (name, email) VALUES ('John', 'john@example.com')"
        report = connected_adapter.execute_explain(query)

        assert report is not None

    def test_execute_explain_update_statement(self, connected_adapter):
        """Test EXPLAIN works with UPDATE."""
        query = "UPDATE customers SET name = 'Jane' WHERE id = 1"
        report = connected_adapter.execute_explain(query)

        assert report is not None

    def test_execute_explain_delete_statement(self, connected_adapter):
        """Test EXPLAIN works with DELETE."""
        query = "DELETE FROM customers WHERE id = 1"
        report = connected_adapter.execute_explain(query)

        assert report is not None

    def test_reject_create_table(self, connected_adapter):
        """Test that CREATE TABLE is rejected."""
        query = "CREATE TABLE test (id INTEGER)"

        with pytest.raises(QueryAnalysisError):
            connected_adapter.execute_explain(query)

    def test_reject_alter_table(self, connected_adapter):
        """Test that ALTER TABLE is rejected."""
        query = "ALTER TABLE customers ADD COLUMN age INTEGER"

        with pytest.raises(QueryAnalysisError):
            connected_adapter.execute_explain(query)

    def test_reject_drop_table(self, connected_adapter):
        """Test that DROP TABLE is rejected."""
        query = "DROP TABLE customers"

        with pytest.raises(QueryAnalysisError):
            connected_adapter.execute_explain(query)

    def test_reject_truncate_table(self, connected_adapter):
        """Test that TRUNCATE is rejected (if supported)."""
        query = "DELETE FROM customers"
        report = connected_adapter.execute_explain(query)
        assert report is not None

    def test_reject_with_leading_comments(self, connected_adapter):
        """Test DDL rejection works with leading comments."""
        query = "-- This creates a table\nCREATE TABLE test (id INTEGER)"

        with pytest.raises(QueryAnalysisError):
            connected_adapter.execute_explain(query)

    def test_get_metrics_structure(self, connected_adapter):
        """Test get_metrics returns proper structure."""
        metrics = connected_adapter.get_metrics()

        assert isinstance(metrics, dict)
        assert "tables" in metrics
        assert "indexes" in metrics
        assert "page_size_bytes" in metrics
        assert "cache_size_pages" in metrics

    def test_get_metrics_correct_counts(self, connected_adapter):
        """Test metrics show correct table and index counts."""
        metrics = connected_adapter.get_metrics()

        assert metrics["tables"] == 2

        assert metrics["indexes"] == 1

    def test_get_engine_info_structure(self, connected_adapter):
        """Test get_engine_info returns proper structure."""
        info = connected_adapter.get_engine_info()

        assert isinstance(info, dict)
        assert "version" in info
        assert "engine" in info
        assert info["engine"] == "sqlite"
        assert "database_path" in info
        assert "max_connections" in info
        assert info["max_connections"] == 1

    def test_get_engine_info_version(self, connected_adapter):
        """Test engine info contains valid SQLite version."""
        info = connected_adapter.get_engine_info()

        assert info["version"]
        assert "." in info["version"]

    def test_get_slow_queries_returns_empty(self, connected_adapter):
        """Test that get_slow_queries returns empty list (not supported)."""
        result = connected_adapter.get_slow_queries(threshold_ms=1000)

        assert isinstance(result, list)
        assert len(result) == 0

    def test_execute_explain_without_connection(self, in_memory_adapter):
        """Test execute_explain fails without connection."""
        query = "SELECT 1"

        with pytest.raises(QueryAnalysisError):
            in_memory_adapter.execute_explain(query)

    def test_invalid_database_path(self):
        """Test connection fails with invalid path."""
        config = ConnectionConfig(
            engine="sqlite",
            host="localhost",
            port=0,
            database="/invalid/path/that/does/not/exist/test.db",
            username="",
            password="",
        )
        SQLiteAdapter(config)

    def test_full_workflow(self, in_memory_adapter):
        """Test complete workflow: connect -> analyze -> metrics -> disconnect."""
        in_memory_adapter.connect()
        assert in_memory_adapter.is_connected()

        conn = in_memory_adapter.get_connection()
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE test (id INTEGER, name TEXT)")
        cursor.execute("CREATE INDEX idx_test_name ON test(name)")
        conn.commit()

        report = in_memory_adapter.execute_explain("SELECT * FROM test")
        assert report is not None
        assert report.score >= 0

        metrics = in_memory_adapter.get_metrics()
        assert metrics["tables"] == 1
        assert metrics["indexes"] == 1

        info = in_memory_adapter.get_engine_info()
        assert info["engine"] == "sqlite"

        in_memory_adapter.disconnect()
        assert not in_memory_adapter.is_connected()

    def test_multiple_sequential_queries(self, connected_adapter):
        """Test analyzing multiple queries sequentially."""
        queries = [
            "SELECT * FROM customers",
            "SELECT * FROM orders WHERE customer_id = 1",
            "SELECT c.name, o.total FROM customers c JOIN orders o ON c.id = o.customer_id",
        ]

        reports = []
        for query in queries:
            report = connected_adapter.execute_explain(query)
            reports.append(report)
            assert report is not None
            assert 0 <= report.score <= 100

        assert len(reports) == 3
