"""Pytest configuration and shared fixtures."""

import pytest

from query_analyzer.adapters import AdapterRegistry


@pytest.fixture(autouse=True)
def ensure_postgresql_registered() -> None:
    """Ensure PostgreSQL adapter is registered before each test.

    This is needed because some tests (like adapter_registry tests) may clear
    the registry, and we need to re-register PostgreSQL for subsequent tests.
    """
    # Import to trigger registration
    from query_analyzer.adapters.sql import PostgreSQLAdapter  # noqa: F401

    # If not registered, register it
    if not AdapterRegistry.is_registered("postgresql"):
        from query_analyzer.adapters.sql import PostgreSQLAdapter as PGAdapter

        AdapterRegistry.register("postgresql")(PGAdapter)


# ============================================================================
# PARAMETRIZED QUERY FIXTURES FOR ANTI-PATTERN DETECTION
# ============================================================================


@pytest.fixture(
    params=[
        pytest.param(
            {
                "name": "index_scan_by_id",
                "table": "orders",
                "query": "SELECT * FROM orders WHERE id = 1",
                "expected_score_min": 80,
                "expected_warnings": [],
                "expected_recommendation_keywords": [],
                "should_be_fast": True,
            },
            id="index_scan_by_id",
        ),
        pytest.param(
            {
                "name": "seq_scan_large_table",
                "table": "large_table",
                "query": "SELECT * FROM large_table WHERE created_at > now() - interval '1 day'",
                "expected_score_max": 75,
                "expected_warnings": ["secuencial", "Búsqueda secuencial"],
                "expected_recommendation_keywords": ["índice", "index"],
                "should_be_fast": False,
            },
            id="seq_scan_large_table",
        ),
        pytest.param(
            {
                "name": "join_with_index",
                "table": "orders, customers",
                "query": """
                    SELECT o.id, c.name
                    FROM orders o
                    JOIN customers c ON o.customer_id = c.id
                    WHERE o.id = 1
                    LIMIT 10
                """,
                "expected_score_min": 70,
                "expected_warnings": [],
                "expected_recommendation_keywords": [],
                "should_be_fast": True,
            },
            id="join_with_index",
        ),
        pytest.param(
            {
                "name": "select_star_unnecessary",
                "table": "large_table",
                "query": "SELECT * FROM large_table LIMIT 100",
                "expected_score_max": 95,
                "expected_warnings": [],
                "expected_recommendation_keywords": ["SELECT"],
                "should_be_fast": True,
            },
            id="select_star",
        ),
        pytest.param(
            {
                "name": "like_with_leading_wildcard",
                "table": "customers",
                "query": "SELECT * FROM customers WHERE name LIKE '%test%'",
                "expected_score_max": 80,
                "expected_warnings": ["secuencial", "LIKE"],
                "expected_recommendation_keywords": ["índice", "index"],
                "should_be_fast": False,
            },
            id="like_leading_wildcard",
        ),
        pytest.param(
            {
                "name": "missing_where_clause",
                "table": "large_table",
                "query": "SELECT COUNT(*) FROM large_table",
                "expected_score_max": 85,
                "expected_warnings": [],
                "expected_recommendation_keywords": [],
                "should_be_fast": False,
            },
            id="missing_where",
        ),
        pytest.param(
            {
                "name": "nested_subquery",
                "table": "orders",
                "query": """
                    SELECT * FROM orders
                    WHERE customer_id IN (SELECT id FROM customers WHERE country = 'USA')
                    LIMIT 10
                """,
                "expected_score_min": 60,
                "expected_warnings": [],
                "expected_recommendation_keywords": [],
                "should_be_fast": True,
            },
            id="nested_subquery",
        ),
        pytest.param(
            {
                "name": "index_on_date_field",
                "table": "orders",
                "query": "SELECT * FROM orders WHERE order_date = CURRENT_DATE",
                "expected_score_min": 70,
                "expected_warnings": [],
                "expected_recommendation_keywords": [],
                "should_be_fast": True,
            },
            id="index_on_date",
        ),
        pytest.param(
            {
                "name": "cartesian_product_implicit",
                "table": "orders, order_items",
                "query": "SELECT * FROM orders, order_items WHERE orders.id = order_items.order_id LIMIT 10",
                "expected_score_min": 60,
                "expected_warnings": [],
                "expected_recommendation_keywords": [],
                "should_be_fast": True,
            },
            id="cartesian_product",
        ),
        pytest.param(
            {
                "name": "limit_without_order",
                "table": "large_table",
                "query": "SELECT * FROM large_table LIMIT 1000",
                "expected_score_min": 50,
                "expected_warnings": [],
                "expected_recommendation_keywords": [],
                "should_be_fast": False,
            },
            id="limit_no_order",
        ),
    ]
)
def anti_pattern_query(request: pytest.FixtureRequest) -> dict:
    """Parametrized fixture: yields anti-pattern query definitions.

    Each parameter is a dict with:
        - name: Query pattern name
        - table: Table(s) involved
        - query: SQL query string
        - expected_score_min/max: Score thresholds
        - expected_warnings: List of warning keywords (case-insensitive)
        - expected_recommendation_keywords: Recommendation keywords to find
        - should_be_fast: Whether execution should be fast
    """
    return request.param
