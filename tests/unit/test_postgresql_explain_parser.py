"""Unit tests for PostgreSQL EXPLAIN plan parser."""

import pytest

from query_analyzer.adapters.sql import PostgreSQLExplainParser

# ============================================================================
# FIXTURES - Sample EXPLAIN plans
# ============================================================================


@pytest.fixture
def simple_select_plan() -> dict:
    """Simple SELECT query EXPLAIN output."""
    return {
        "Plan": {
            "Node Type": "Seq Scan",
            "Relation Name": "customers",
            "Startup Cost": 0.0,
            "Total Cost": 100.0,
            "Plan Rows": 100,
            "Actual Rows": 100,
            "Actual Total Time": 5.0,
            "Buffers": {"Shared Hit": 50, "Shared Read": 2},
        },
        "Planning Time": 0.123,
        "Execution Time": 5.0,
    }


@pytest.fixture
def join_plan_with_multiple_nodes() -> dict:
    """JOIN query with multiple nodes."""
    return {
        "Plan": {
            "Node Type": "Hash Join",
            "Startup Cost": 0.0,
            "Total Cost": 500.0,
            "Plan Rows": 500,
            "Actual Rows": 487,
            "Actual Total Time": 25.0,
            "Buffers": {"Shared Hit": 300, "Shared Read": 20},
            "Plans": [
                {
                    "Node Type": "Seq Scan",
                    "Relation Name": "orders",
                    "Startup Cost": 0.0,
                    "Total Cost": 100.0,
                    "Plan Rows": 100,
                    "Actual Rows": 100,
                    "Actual Total Time": 5.0,
                    "Buffers": {"Shared Hit": 50, "Shared Read": 2},
                },
                {
                    "Node Type": "Hash",
                    "Startup Cost": 100.0,
                    "Total Cost": 200.0,
                    "Plan Rows": 1000,
                    "Actual Rows": 1000,
                    "Actual Total Time": 10.0,
                    "Buffers": {"Shared Hit": 250, "Shared Read": 18},
                    "Plans": [
                        {
                            "Node Type": "Seq Scan",
                            "Relation Name": "customers",
                            "Startup Cost": 0.0,
                            "Total Cost": 100.0,
                            "Plan Rows": 1000,
                            "Actual Rows": 1000,
                            "Actual Total Time": 8.0,
                            "Buffers": {"Shared Hit": 250, "Shared Read": 18},
                        }
                    ],
                },
            ],
        },
        "Planning Time": 0.456,
        "Execution Time": 25.0,
    }


@pytest.fixture
def large_table_seq_scan() -> dict:
    """Sequential scan on large table (10K+ rows)."""
    return {
        "Plan": {
            "Node Type": "Seq Scan",
            "Relation Name": "large_table",
            "Startup Cost": 0.0,
            "Total Cost": 5000.0,
            "Plan Rows": 10000,
            "Actual Rows": 10000,
            "Actual Total Time": 150.0,
            "Buffers": {"Shared Hit": 2000, "Shared Read": 500},
        },
        "Planning Time": 0.1,
        "Execution Time": 150.0,
    }


@pytest.fixture
def row_divergence_plan() -> dict:
    """Plan with >20% row divergence."""
    return {
        "Plan": {
            "Node Type": "Hash Join",
            "Startup Cost": 0.0,
            "Total Cost": 300.0,
            "Plan Rows": 100,
            "Actual Rows": 30,  # 70% divergence from estimate
            "Actual Total Time": 20.0,
            "Buffers": {"Shared Hit": 200, "Shared Read": 5},
            "Plans": [
                {
                    "Node Type": "Index Scan",
                    "Relation Name": "orders",
                    "Index Name": "idx_orders_id",
                    "Startup Cost": 0.0,
                    "Total Cost": 50.0,
                    "Plan Rows": 50,
                    "Actual Rows": 50,
                    "Actual Total Time": 3.0,
                    "Buffers": {"Shared Hit": 100, "Shared Read": 1},
                },
                {
                    "Node Type": "Hash",
                    "Startup Cost": 50.0,
                    "Total Cost": 150.0,
                    "Plan Rows": 100,
                    "Actual Rows": 20,  # >20% divergence
                    "Actual Total Time": 5.0,
                    "Buffers": {"Shared Hit": 100, "Shared Read": 4},
                    "Plans": [
                        {
                            "Node Type": "Index Scan",
                            "Relation Name": "customers",
                            "Index Name": "idx_customers_id",
                            "Startup Cost": 0.0,
                            "Total Cost": 50.0,
                            "Plan Rows": 100,
                            "Actual Rows": 20,
                            "Actual Total Time": 3.0,
                            "Buffers": {"Shared Hit": 100, "Shared Read": 4},
                        }
                    ],
                },
            ],
        },
        "Planning Time": 0.2,
        "Execution Time": 20.0,
    }


@pytest.fixture
def optimal_index_scan() -> dict:
    """Optimal query with index scan and exact row estimates."""
    return {
        "Plan": {
            "Node Type": "Index Scan",
            "Relation Name": "orders",
            "Index Name": "idx_orders_id",
            "Startup Cost": 0.0,
            "Total Cost": 50.0,
            "Plan Rows": 100,
            "Actual Rows": 100,  # Exact estimate
            "Actual Total Time": 8.0,
            "Buffers": {"Shared Hit": 100, "Shared Read": 0},  # Perfect cache hit
        },
        "Planning Time": 0.05,
        "Execution Time": 8.0,
    }


# ============================================================================
# TESTS - Parser Basic
# ============================================================================


class TestPostgreSQLExplainParserBasic:
    """Basic parser functionality tests."""

    def test_parse_simple_select(self, simple_select_plan: dict) -> None:
        """Parse simple SELECT with sequential scan."""
        parser = PostgreSQLExplainParser()
        metrics = parser.parse(simple_select_plan)

        assert metrics["planning_time_ms"] == 0.123
        assert metrics["execution_time_ms"] == 5.0
        assert metrics["total_cost"] == 100.0
        assert metrics["node_count"] == 1
        assert metrics["most_expensive_node"]["type"] == "Seq Scan"

    def test_parse_join_multiple_nodes(self, join_plan_with_multiple_nodes: dict) -> None:
        """Parse JOIN query with multiple nested nodes."""
        parser = PostgreSQLExplainParser()
        metrics = parser.parse(join_plan_with_multiple_nodes)

        # Should have Hash Join + Seq Scan + Hash + Seq Scan = 4 nodes
        assert metrics["node_count"] == 4
        assert metrics["most_expensive_node"]["type"] == "Hash Join"
        assert metrics["most_expensive_node"]["cost"] == 500.0

    def test_extract_buffer_statistics(self, join_plan_with_multiple_nodes: dict) -> None:
        """Extract and aggregate buffer statistics."""
        parser = PostgreSQLExplainParser()
        metrics = parser.parse(join_plan_with_multiple_nodes)

        buffer_stats = metrics["buffer_stats"]
        # All nodes' buffers: Hash Join(300+20) + Seq Scan(50+2) + Hash(250+18) + Seq Scan(250+18)
        # Hit total: 300 + 50 + 250 + 250 = 850
        # Read total: 20 + 2 + 18 + 18 = 58
        assert buffer_stats["shared_hit_total"] == 850
        assert buffer_stats["shared_read_total"] == 58
        assert buffer_stats["cache_miss_rate"] > 0.0
        assert buffer_stats["cache_miss_rate"] < 0.1  # Good cache ratio

    def test_identify_scan_nodes(self, join_plan_with_multiple_nodes: dict) -> None:
        """Identify all sequential/index scan nodes."""
        parser = PostgreSQLExplainParser()
        metrics = parser.parse(join_plan_with_multiple_nodes)

        scan_nodes = metrics["scan_nodes"]
        # Should find 2 Seq Scans
        assert len(scan_nodes) == 2
        assert all("Scan" in node.get("Node Type", "") for node in scan_nodes)

    def test_identify_join_nodes(self, join_plan_with_multiple_nodes: dict) -> None:
        """Identify all join operation nodes."""
        parser = PostgreSQLExplainParser()
        metrics = parser.parse(join_plan_with_multiple_nodes)

        join_nodes = metrics["join_nodes"]
        # Should find Hash Join + Hash
        assert len(join_nodes) == 2


# ============================================================================
# TESTS - Row Divergence & Warnings
# ============================================================================


class TestRowDivergence:
    """Row estimate divergence tests."""

    def test_row_divergence_calculation(self) -> None:
        """Calculate row divergence correctly."""
        parser = PostgreSQLExplainParser()

        # Exact estimate
        assert parser._calculate_row_divergence(100, 100) == 0.0

        # 50% divergence
        assert parser._calculate_row_divergence(100, 50) == 0.5

        # 100% divergence (double)
        assert parser._calculate_row_divergence(100, 200) == 1.0

        # No plan rows (edge case)
        assert parser._calculate_row_divergence(0, 100) == float("inf")

    def test_warning_row_divergence_greater_than_20_percent(
        self, row_divergence_plan: dict
    ) -> None:
        """Generate warning when row divergence > 20%."""
        parser = PostgreSQLExplainParser()
        metrics = parser.parse(row_divergence_plan)
        warnings = parser.identify_warnings(metrics, metrics["all_nodes"])

        # Should have warning about row divergence
        assert any("Estimación de filas" in w for w in warnings)
        assert any("inexacta" in w for w in warnings)


# ============================================================================
# TESTS - Sequential Scan Warnings
# ============================================================================


class TestSequentialScanWarnings:
    """Sequential scan detection and warnings."""

    def test_warning_seq_scan_large_table(self, large_table_seq_scan: dict) -> None:
        """Generate warning for sequential scan on large table (>10K rows)."""
        # Change to use > 10000 since threshold is 10000
        parser = PostgreSQLExplainParser(seq_scan_threshold=10000)
        # Modify the test plan to have 11000 rows instead of 10000
        modified_plan = large_table_seq_scan.copy()
        modified_plan["Plan"]["Plan Rows"] = 11000
        metrics = parser.parse(modified_plan)
        warnings = parser.identify_warnings(metrics, metrics["all_nodes"])

        # Should have warning about sequential scan
        assert any("Búsqueda secuencial" in w for w in warnings)
        assert any("large_table" in w for w in warnings)
        assert any("índice" in w for w in warnings)

    def test_recommendation_for_seq_scan(self, large_table_seq_scan: dict) -> None:
        """Generate recommendation for sequential scan issue."""
        parser = PostgreSQLExplainParser()
        metrics = parser.parse(large_table_seq_scan)
        warnings = parser.identify_warnings(metrics, metrics["all_nodes"])
        recommendations = parser.generate_recommendations(metrics, warnings)

        assert any("índice" in r.lower() for r in recommendations)


# ============================================================================
# TESTS - Score Calculation
# ============================================================================


class TestScoreCalculation:
    """Optimization score calculation tests."""

    def test_score_optimal_query_is_high(self, optimal_index_scan: dict) -> None:
        """Optimal query (index scan, exact rows, good cache) has high score."""
        parser = PostgreSQLExplainParser()
        metrics = parser.parse(optimal_index_scan)
        warnings = parser.identify_warnings(metrics, metrics["all_nodes"])
        score = parser.calculate_score(metrics, warnings)

        # Should be >= 85 for optimal query
        assert score >= 85, f"Expected score >= 85, got {score}"

    def test_score_with_execution_time_penalty(self, large_table_seq_scan: dict) -> None:
        """Score decreases with high execution time."""
        parser = PostgreSQLExplainParser()
        metrics = parser.parse(large_table_seq_scan)
        warnings = parser.identify_warnings(metrics, metrics["all_nodes"])
        score_slow = parser.calculate_score(metrics, warnings)

        # Score should be lower due to 150ms execution time
        assert score_slow < 85

    def test_score_with_row_divergence(self, row_divergence_plan: dict) -> None:
        """Score reflects row estimate divergence."""
        parser = PostgreSQLExplainParser()
        metrics = parser.parse(row_divergence_plan)
        warnings = parser.identify_warnings(metrics, metrics["all_nodes"])
        score = parser.calculate_score(metrics, warnings)

        # Row divergence should reduce score below 85
        assert score <= 85

    def test_score_range_boundaries(self) -> None:
        """Score is always within 0-100 range."""
        parser = PostgreSQLExplainParser()

        # Create extreme metrics
        metrics_poor = {
            "execution_time_ms": 5000.0,
            "planning_time_ms": 10.0,
            "all_nodes": [
                {
                    "Node Type": "Nested Loop",
                    "Actual Rows": 5000,
                    "Plan Rows": 100,
                    "Total Cost": 10000.0,
                    "Buffers": {"Shared Hit": 100, "Shared Read": 900},
                }
            ],
            "buffer_stats": {"cache_miss_rate": 0.9},
        }
        warnings = ["Multiple serious issues"]
        score = parser.calculate_score(metrics_poor, warnings)

        assert 0 <= score <= 100


# ============================================================================
# TESTS - Nested Loop Detection
# ============================================================================


class TestNestedLoopDetection:
    """Nested loop analysis and warnings."""

    def test_warning_nested_loop_high_iterations(self) -> None:
        """Generate warning for nested loop with many iterations."""
        nested_loop_plan = {
            "Plan": {
                "Node Type": "Nested Loop",
                "Startup Cost": 0.0,
                "Total Cost": 2000.0,
                "Plan Rows": 1000,
                "Actual Rows": 1500,  # >1000 iterations
                "Actual Total Time": 200.0,
                "Buffers": {"Shared Hit": 1000, "Shared Read": 100},
            },
            "Planning Time": 0.1,
            "Execution Time": 200.0,
        }

        parser = PostgreSQLExplainParser()
        metrics = parser.parse(nested_loop_plan)
        warnings = parser.identify_warnings(metrics, metrics["all_nodes"])

        assert any("Nested Loop" in w for w in warnings)
        assert any("iteraciones" in w for w in warnings)


# ============================================================================
# TESTS - Cache Hit Rate Analysis
# ============================================================================


class TestCacheAnalysis:
    """Cache hit rate analysis."""

    def test_warning_poor_cache_hit_rate(self) -> None:
        """Generate warning when cache miss rate > 10%."""
        plan_with_poor_cache = {
            "Plan": {
                "Node Type": "Seq Scan",
                "Relation Name": "orders",
                "Startup Cost": 0.0,
                "Total Cost": 1000.0,
                "Plan Rows": 1000,
                "Actual Rows": 1000,
                "Actual Total Time": 100.0,
                "Buffers": {"Shared Hit": 100, "Shared Read": 900},  # 90% miss rate
            },
            "Planning Time": 0.1,
            "Execution Time": 100.0,
        }

        parser = PostgreSQLExplainParser()
        metrics = parser.parse(plan_with_poor_cache)
        warnings = parser.identify_warnings(metrics, metrics["all_nodes"])

        assert any("caché" in w for w in warnings)
        assert any("fallos" in w for w in warnings)
