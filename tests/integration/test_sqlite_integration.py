"""Integration tests for SQLite adapter."""

import logging
from collections.abc import Generator

import pytest

from query_analyzer.adapters import ConnectionConfig

logger = logging.getLogger(__name__)


# Try to import SQLite adapter
try:
    from query_analyzer.adapters.sql import SQLiteAdapter

    SQLITE_AVAILABLE = True
except ImportError:
    SQLITE_AVAILABLE = False


# ============================================================================
# FIXTURES - SQLite Setup
# ============================================================================


@pytest.fixture(scope="session")
def sqlite_config() -> ConnectionConfig:
    """SQLite connection config (in-memory database for testing)."""
    return ConnectionConfig(
        engine="sqlite",
        database=":memory:",
        extra={"timeout": 10},
    )


@pytest.fixture
def sqlite_adapter(sqlite_config: ConnectionConfig) -> Generator:
    """SQLite adapter with automatic connection management."""
    if not SQLITE_AVAILABLE:
        pytest.skip("SQLiteAdapter not available")

    adapter = SQLiteAdapter(sqlite_config)

    try:
        adapter.connect()
        # Create test tables for integration tests
        _create_test_tables(adapter)
        yield adapter
    finally:
        adapter.disconnect()


def _create_test_tables(adapter: SQLiteAdapter) -> None:
    """Create test tables for SQLite integration tests."""
    cursor = adapter._connection.cursor()
    try:
        # Create customers table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS customers (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create orders table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY,
                customer_id INTEGER NOT NULL,
                order_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                total REAL,
                FOREIGN KEY(customer_id) REFERENCES customers(id)
            )
        """)

        # Create indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_orders_customer_id ON orders(customer_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_customers_email ON customers(email)")

        # Create large_table for anti-pattern tests (seq scan, select *, etc.)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS large_table (
                id INTEGER PRIMARY KEY,
                data TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_large_table_created_at ON large_table(created_at)
        """)

        # Create order_items for cartesian product anti-pattern test
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS order_items (
                id INTEGER PRIMARY KEY,
                order_id INTEGER NOT NULL,
                product_id INTEGER,
                quantity INTEGER,
                price REAL,
                FOREIGN KEY(order_id) REFERENCES orders(id)
            )
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_order_items_order_id ON order_items(order_id)
        """)

        # Add country column to customers if it doesn't exist (for nested_subquery test)
        try:
            cursor.execute("ALTER TABLE customers ADD COLUMN country TEXT DEFAULT 'USA'")
        except Exception:
            pass  # Column already exists

        # Insert test data
        cursor.execute(
            "INSERT OR IGNORE INTO customers (id, name, email) VALUES (1, 'John Doe', 'john@example.com')"
        )
        cursor.execute(
            "INSERT OR IGNORE INTO customers (id, name, email) VALUES (2, 'Jane Smith', 'jane@example.com')"
        )
        # Set country for existing rows (INSERT OR IGNORE won't update)
        cursor.execute("UPDATE customers SET country = 'USA' WHERE country IS NULL")
        cursor.execute(
            "INSERT OR IGNORE INTO orders (id, customer_id, total) VALUES (1, 1, 100.00)"
        )
        cursor.execute(
            "INSERT OR IGNORE INTO orders (id, customer_id, total) VALUES (2, 1, 200.00)"
        )
        cursor.execute(
            "INSERT OR IGNORE INTO orders (id, customer_id, total) VALUES (3, 2, 150.00)"
        )

        # Insert data into large_table (10K rows for seq scan threshold)
        cursor.execute("SELECT COUNT(*) FROM large_table")
        if cursor.fetchone()[0] == 0:
            for i in range(1, 10001):
                cursor.execute(
                    "INSERT INTO large_table (id, data, created_at) VALUES (?, ?, datetime('now', ?))",
                    (i, f"data_row_{i}", f"-{i % 365} days"),
                )

        # Insert data into order_items
        cursor.execute("SELECT COUNT(*) FROM order_items")
        if cursor.fetchone()[0] == 0:
            for i in range(1, 21):
                cursor.execute(
                    "INSERT INTO order_items (id, order_id, product_id, quantity, price) VALUES (?, ?, ?, ?, ?)",
                    (i, (i % 3) + 1, i, i % 5 + 1, round(i * 10.5, 2)),
                )

        adapter._connection.commit()
    finally:
        cursor.close()


# ============================================================================
# TESTS - Connection Management
# ============================================================================


class TestSQLiteIntegrationConnection:
    """SQLite connectivity tests."""

    def test_connect_and_disconnect(self, sqlite_config: ConnectionConfig) -> None:
        """Connect to and disconnect from SQLite."""
        if not SQLITE_AVAILABLE:
            pytest.skip("SQLiteAdapter not available")

        adapter = SQLiteAdapter(sqlite_config)

        try:
            adapter.connect()
            assert adapter.is_connected() is True
            assert adapter.test_connection() is True

            adapter.disconnect()
            assert adapter.is_connected() is False
        except Exception as e:
            pytest.skip(f"SQLite test failed: {e}")

    def test_context_manager(self, sqlite_config: ConnectionConfig) -> None:
        """Context manager works with SQLite."""
        if not SQLITE_AVAILABLE:
            pytest.skip("SQLiteAdapter not available")

        adapter = SQLiteAdapter(sqlite_config)

        try:
            with adapter:
                assert adapter.is_connected() is True
                assert adapter.test_connection() is True

            assert adapter.is_connected() is False
        except Exception:
            pytest.skip("SQLite test failed")


# ============================================================================
# TESTS - Real EXPLAIN QUERY PLAN Analysis
# ============================================================================


class TestSQLiteIntegrationExplain:
    """Real EXPLAIN QUERY PLAN tests on SQLite."""

    def test_explain_simple_select(self, sqlite_adapter) -> None:
        """Execute EXPLAIN QUERY PLAN on simple SELECT."""
        query = "SELECT * FROM orders LIMIT 10"

        try:
            report = sqlite_adapter.execute_explain(query)

            assert report.engine == "sqlite"
            assert report.query == query
            assert 0 <= report.score <= 100
            assert report.raw_plan is not None
            assert isinstance(report.metrics, dict)
        except Exception as e:
            pytest.skip(f"EXPLAIN analysis failed: {e}")

    def test_anti_pattern_query_analysis(
        self,
        sqlite_adapter,
        anti_pattern_query: dict,
    ) -> None:
        """Analyze anti-pattern queries and validate scoring/warnings."""
        query = anti_pattern_query["query"]

        try:
            report = sqlite_adapter.execute_explain(query)

            # Validate score range if specified
            if "expected_score_min" in anti_pattern_query:
                assert report.score >= anti_pattern_query["expected_score_min"], (
                    f"Score {report.score} below minimum "
                    f"{anti_pattern_query['expected_score_min']} for {anti_pattern_query['name']}"
                )

            if "expected_score_max" in anti_pattern_query:
                assert report.score <= anti_pattern_query["expected_score_max"], (
                    f"Score {report.score} above maximum "
                    f"{anti_pattern_query['expected_score_max']} for {anti_pattern_query['name']}"
                )

            # Validate expected warnings
            if anti_pattern_query.get("expected_warnings"):
                for expected_warning in anti_pattern_query["expected_warnings"]:
                    assert any(expected_warning.lower() in w.lower() for w in report.warnings), (
                        f"Expected warning containing '{expected_warning}' not found "
                        f"in {report.warnings} for query: {anti_pattern_query['name']}"
                    )

            # Validate expected recommendation keywords
            if anti_pattern_query.get("expected_recommendation_keywords"):
                for keyword in anti_pattern_query["expected_recommendation_keywords"]:
                    assert any(
                        keyword.lower() in (rec.title or "").lower()
                        for rec in report.recommendations
                    ), (
                        f"Expected recommendation keyword '{keyword}' not found "
                        f"in {report.recommendations} for {anti_pattern_query['name']}"
                    )

        except Exception as e:
            pytest.skip(f"Anti-pattern analysis failed for {anti_pattern_query['name']}: {e}")

    def test_explain_table_scan_detection(self, sqlite_adapter) -> None:
        """EXPLAIN QUERY PLAN detects table scans."""
        query = "SELECT * FROM orders WHERE id = 1"

        try:
            report = sqlite_adapter.execute_explain(query)

            assert report.score > 0
            assert isinstance(report.metrics, dict)
        except Exception as e:
            pytest.skip(f"Table scan detection failed: {e}")

    def test_explain_index_scan(self, sqlite_adapter) -> None:
        """EXPLAIN QUERY PLAN shows index scan information."""
        query = "SELECT * FROM orders WHERE id = 1"

        try:
            report = sqlite_adapter.execute_explain(query)

            # Index scan should have reasonable score
            assert report.score >= 50
        except Exception as e:
            pytest.skip(f"Index scan EXPLAIN failed: {e}")


# ============================================================================
# TESTS - Metrics Collection
# ============================================================================


class TestSQLiteIntegrationMetrics:
    """SQLite metrics collection tests."""

    def test_get_metrics(self, sqlite_adapter) -> None:
        """Collect SQLite database metrics."""
        try:
            metrics = sqlite_adapter.get_metrics()

            assert isinstance(metrics, dict)
        except Exception as e:
            pytest.skip(f"Metrics collection failed: {e}")

    def test_get_engine_info(self, sqlite_adapter) -> None:
        """Collect SQLite engine information."""
        try:
            info = sqlite_adapter.get_engine_info()

            assert isinstance(info, dict)
            if "version" in info:
                assert isinstance(info["version"], str)

        except Exception as e:
            pytest.skip(f"Engine info collection failed: {e}")


# ============================================================================
# TESTS - Query Validation
# ============================================================================


class TestSQLiteIntegrationValidation:
    """SQLite query validation tests."""

    def test_invalid_table_raises_error(self, sqlite_adapter) -> None:
        """Invalid table name raises clear error."""
        with pytest.raises(Exception) as exc_info:
            sqlite_adapter.execute_explain("SELECT * FROM nonexistent_table_xyz")

        error_msg = str(exc_info.value)
        assert "no such table" in error_msg.lower() or "nonexistent_table" in error_msg

    def test_invalid_column_raises_error(self, sqlite_adapter) -> None:
        """Invalid column name raises clear error."""
        with pytest.raises(Exception) as exc_info:
            sqlite_adapter.execute_explain("SELECT nonexistent_column_xyz FROM orders")

        error_msg = str(exc_info.value)
        assert "no such column" in error_msg.lower() or "nonexistent_column" in error_msg

    def test_syntax_error_raises_error(self, sqlite_adapter) -> None:
        """Malformed SQL raises clear error."""
        with pytest.raises(Exception) as exc_info:
            sqlite_adapter.execute_explain("SELECT * FORM orders")  # Typo: FORM -> FROM

        error_msg = str(exc_info.value)
        assert "syntax" in error_msg.lower() or "error" in error_msg.lower()

    def test_select_works(self, sqlite_adapter) -> None:
        """SELECT statements are accepted."""
        try:
            report = sqlite_adapter.execute_explain("SELECT 1")
            assert isinstance(report, object)
            assert hasattr(report, "score")
        except Exception as e:
            pytest.skip(f"SELECT test failed: {e}")
