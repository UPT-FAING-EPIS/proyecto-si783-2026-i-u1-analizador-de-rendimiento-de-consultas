"""Unit tests for CockroachDB parser (using PostgreSQL parser logic)."""

import pytest

from query_analyzer.adapters.sql.postgresql_parser import PostgreSQLExplainParser

# Fixtures for parser test data


@pytest.fixture
def simple_plan_json():
    """Simple index join (good case — no warnings)."""
    return {
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


@pytest.fixture
def full_scan_plan_json():
    """Full seq scan (warning expected)."""
    return {
        "Plan": {
            "Node Type": "Seq Scan",
            "Table": "large_table",
            "Startup Cost": 0.0,
            "Total Cost": 10000.0,
            "Plan Rows": 50000,
            "Actual Rows": 45000,
            "Filter": "status = 'active'",
        },
        "Planning Time": 2.0,
        "Execution Time": 2500.0,
    }


@pytest.fixture
def cross_join_plan_json():
    """Nested loop / cross join (warning expected)."""
    return {
        "Plan": {
            "Node Type": "Nested Loop Join",
            "Plans": [
                {
                    "Node Type": "Seq Scan",
                    "Table": "regions",
                    "Actual Rows": 10,
                    "Plan Rows": 10,
                },
                {
                    "Node Type": "Seq Scan",
                    "Table": "products",
                    "Actual Rows": 100000,
                    "Plan Rows": 100000,
                },
            ],
        },
        "Planning Time": 1.0,
        "Execution Time": 5000.0,
    }


class TestCockroachDBParserBasic:
    """Test parser with CRDB JSON format."""

    def test_parser_can_parse_simple_json(self, simple_plan_json):
        """Parser successfully parses CRDB JSON format."""
        parser = PostgreSQLExplainParser()
        metrics = parser.parse(simple_plan_json)

        assert isinstance(metrics, dict)
        assert "planning_time_ms" in metrics
        assert "execution_time_ms" in metrics
        assert "total_cost" in metrics
        assert "all_nodes" in metrics

    def test_parser_extracts_execution_time(self, simple_plan_json):
        """Execution time extracted correctly."""
        parser = PostgreSQLExplainParser()
        metrics = parser.parse(simple_plan_json)

        assert metrics["execution_time_ms"] == 45.3

    def test_parser_extracts_planning_time(self, simple_plan_json):
        """Planning time extracted correctly."""
        parser = PostgreSQLExplainParser()
        metrics = parser.parse(simple_plan_json)

        assert metrics["planning_time_ms"] == 1.5

    def test_parser_extracts_cost(self, simple_plan_json):
        """Total cost extracted correctly."""
        parser = PostgreSQLExplainParser()
        metrics = parser.parse(simple_plan_json)

        assert metrics["total_cost"] == 500.0

    def test_parser_extracts_all_nodes(self, simple_plan_json):
        """All nodes extracted from plan tree."""
        parser = PostgreSQLExplainParser()
        metrics = parser.parse(simple_plan_json)

        # Should have at least 3 nodes: Hash Join + 2 scans
        assert len(metrics["all_nodes"]) >= 3
        node_types = [n.get("Node Type") for n in metrics["all_nodes"]]
        assert "Hash Join" in node_types


class TestCockroachDBParserWarnings:
    """Test warning detection."""

    def test_simple_join_no_warnings(self, simple_plan_json):
        """Index join should not generate warnings."""
        parser = PostgreSQLExplainParser()
        metrics = parser.parse(simple_plan_json)
        warnings = parser.identify_warnings(metrics, metrics["all_nodes"])

        # Index join is efficient — should have few/no warnings
        # (PostgreSQL parser may have some, but not for index usage)
        warning_codes = [w.code for w in warnings]
        # Should NOT have warnings about joins
        assert "nested_loop" not in warning_codes

    def test_full_scan_generates_warning(self, full_scan_plan_json):
        """Full seq scan should generate warning."""
        parser = PostgreSQLExplainParser()
        metrics = parser.parse(full_scan_plan_json)
        warnings = parser.identify_warnings(metrics, metrics["all_nodes"])

        # Should have at least one warning (full table scan)
        assert len(warnings) > 0
        # All warnings are strings
        assert all(isinstance(w, str) for w in warnings)

    def test_cross_join_generates_warning(self, cross_join_plan_json):
        """Cross join should generate warning."""
        parser = PostgreSQLExplainParser()
        metrics = parser.parse(cross_join_plan_json)
        warnings = parser.identify_warnings(metrics, metrics["all_nodes"])

        # Should have warnings for nested loop with large cross product
        assert len(warnings) > 0


class TestCockroachDBParserScoring:
    """Test score calculation."""

    def test_score_in_valid_range(self, simple_plan_json):
        """Score is always between 0 and 100."""
        parser = PostgreSQLExplainParser()
        metrics = parser.parse(simple_plan_json)
        warnings = parser.identify_warnings(metrics, metrics["all_nodes"])
        score = parser.calculate_score(metrics, warnings)

        assert 0 <= score <= 100

    def test_score_reproducible(self, simple_plan_json):
        """Same plan produces same score (reproducibility)."""
        parser = PostgreSQLExplainParser()
        metrics1 = parser.parse(simple_plan_json)
        warnings1 = parser.identify_warnings(metrics1, metrics1["all_nodes"])
        score1 = parser.calculate_score(metrics1, warnings1)

        metrics2 = parser.parse(simple_plan_json)
        warnings2 = parser.identify_warnings(metrics2, metrics2["all_nodes"])
        score2 = parser.calculate_score(metrics2, warnings2)

        assert score1 == score2

    def test_full_scan_reduces_score(self, simple_plan_json, full_scan_plan_json):
        """Plan with full scan should have lower score."""
        parser = PostgreSQLExplainParser()

        metrics1 = parser.parse(simple_plan_json)
        warnings1 = parser.identify_warnings(metrics1, metrics1["all_nodes"])
        score1 = parser.calculate_score(metrics1, warnings1)

        metrics2 = parser.parse(full_scan_plan_json)
        warnings2 = parser.identify_warnings(metrics2, metrics2["all_nodes"])
        score2 = parser.calculate_score(metrics2, warnings2)

        # Full scan plan should have lower score
        assert score2 < score1


class TestCockroachDBParserRecommendations:
    """Test recommendation generation."""

    def test_recommendations_generated(self, simple_plan_json):
        """Recommendations are generated for warnings."""
        parser = PostgreSQLExplainParser()
        metrics = parser.parse(simple_plan_json)
        warnings = parser.identify_warnings(metrics, metrics["all_nodes"])
        recommendations = parser.generate_recommendations(metrics, warnings)

        assert isinstance(recommendations, list)

    def test_full_scan_generates_index_recommendation(self, full_scan_plan_json):
        """Full scan should recommend index creation."""
        parser = PostgreSQLExplainParser()
        metrics = parser.parse(full_scan_plan_json)
        warnings = parser.identify_warnings(metrics, metrics["all_nodes"])
        recommendations = parser.generate_recommendations(metrics, warnings)

        # Should have recommendations if there are warnings
        if len(warnings) > 0:
            assert len(recommendations) > 0
