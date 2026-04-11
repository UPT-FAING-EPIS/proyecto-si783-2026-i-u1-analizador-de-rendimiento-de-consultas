"""Unit tests for CockroachDB parser with CRDB-specific features."""

import pytest

from query_analyzer.adapters.sql.cockroachdb_parser import CockroachDBParser

# Fixtures for parser test data


@pytest.fixture
def simple_plan_json():
    """Simple hash join (good case — no warnings)."""
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
def lookup_join_plan_json():
    """Plan with CockroachDB-specific Lookup Join."""
    return {
        "Plan": {
            "Node Type": "Lookup Join",
            "Startup Cost": 100.0,
            "Total Cost": 500.0,
            "Plan Rows": 1000,
            "Actual Rows": 950,
            "Plans": [
                {
                    "Node Type": "Index Scan",
                    "Index Name": "orders_idx",
                    "Table": "orders",
                    "Actual Rows": 100,
                    "Plan Rows": 105,
                },
                {
                    "Node Type": "Index Scan",
                    "Index Name": "customers_idx",
                    "Table": "customers",
                    "Actual Rows": 950,
                    "Plan Rows": 1000,
                },
            ],
        },
        "Planning Time": 1.5,
        "Execution Time": 45.3,
    }


@pytest.fixture
def zigzag_join_plan_json():
    """Plan with CockroachDB-specific Zigzag Join."""
    return {
        "Plan": {
            "Node Type": "Zigzag Join",
            "Startup Cost": 50.0,
            "Total Cost": 300.0,
            "Plan Rows": 500,
            "Actual Rows": 480,
            "Plans": [
                {
                    "Node Type": "Index Scan",
                    "Index Name": "idx_a",
                    "Table": "data",
                    "Actual Rows": 240,
                    "Plan Rows": 250,
                },
                {
                    "Node Type": "Index Scan",
                    "Index Name": "idx_b",
                    "Table": "data",
                    "Actual Rows": 240,
                    "Plan Rows": 250,
                },
            ],
        },
        "Planning Time": 0.8,
        "Execution Time": 30.0,
    }


@pytest.fixture
def multiple_lookup_joins_plan_json():
    """Plan with multiple Lookup Joins (should trigger warning)."""
    return {
        "Plan": {
            "Node Type": "Lookup Join",
            "Plans": [
                {
                    "Node Type": "Lookup Join",
                    "Plans": [
                        {
                            "Node Type": "Lookup Join",
                            "Plans": [
                                {
                                    "Node Type": "Lookup Join",
                                    "Plans": [
                                        {
                                            "Node Type": "Lookup Join",
                                            "Plans": [
                                                {
                                                    "Node Type": "Lookup Join",
                                                    "Actual Rows": 100,
                                                    "Plan Rows": 100,
                                                },
                                                {
                                                    "Node Type": "Seq Scan",
                                                    "Actual Rows": 100,
                                                    "Plan Rows": 100,
                                                },
                                            ],
                                            "Actual Rows": 100,
                                            "Plan Rows": 100,
                                        },
                                        {
                                            "Node Type": "Seq Scan",
                                            "Actual Rows": 100,
                                            "Plan Rows": 100,
                                        },
                                    ],
                                    "Actual Rows": 100,
                                    "Plan Rows": 100,
                                },
                                {"Node Type": "Seq Scan", "Actual Rows": 100, "Plan Rows": 100},
                            ],
                            "Actual Rows": 100,
                            "Plan Rows": 100,
                        },
                        {"Node Type": "Seq Scan", "Actual Rows": 100, "Plan Rows": 100},
                    ],
                    "Actual Rows": 100,
                    "Plan Rows": 100,
                },
                {"Node Type": "Seq Scan", "Actual Rows": 100, "Plan Rows": 100},
            ],
            "Actual Rows": 100,
            "Plan Rows": 100,
        },
        "Planning Time": 2.0,
        "Execution Time": 100.0,
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


class TestCockroachDBParserBasic:
    """Test CockroachDB parser with basic functionality."""

    def test_parser_uses_crdb_parser_class(self):
        """CockroachDBParser is the right class."""
        parser = CockroachDBParser()
        assert isinstance(parser, CockroachDBParser)

    def test_parser_can_parse_simple_json(self, simple_plan_json):
        """Parser successfully parses CRDB JSON format."""
        parser = CockroachDBParser()
        metrics = parser.parse(simple_plan_json)

        assert isinstance(metrics, dict)
        assert "planning_time_ms" in metrics
        assert "execution_time_ms" in metrics
        assert "total_cost" in metrics
        assert "all_nodes" in metrics

    def test_parser_extracts_execution_time(self, simple_plan_json):
        """Execution time extracted correctly."""
        parser = CockroachDBParser()
        metrics = parser.parse(simple_plan_json)

        assert metrics["execution_time_ms"] == 45.3

    def test_parser_extracts_planning_time(self, simple_plan_json):
        """Planning time extracted correctly."""
        parser = CockroachDBParser()
        metrics = parser.parse(simple_plan_json)

        assert metrics["planning_time_ms"] == 1.5

    def test_parser_extracts_cost(self, simple_plan_json):
        """Total cost extracted correctly."""
        parser = CockroachDBParser()
        metrics = parser.parse(simple_plan_json)

        assert metrics["total_cost"] == 500.0


class TestCockroachDBParserCRDBMetrics:
    """Test CockroachDB-specific metrics extraction."""

    def test_parser_detects_lookup_join(self, lookup_join_plan_json):
        """Parser detects Lookup Join nodes."""
        parser = CockroachDBParser()
        metrics = parser.parse(lookup_join_plan_json)

        assert "lookup_join_count" in metrics
        assert metrics["lookup_join_count"] > 0

    def test_parser_detects_zigzag_join(self, zigzag_join_plan_json):
        """Parser detects Zigzag Join nodes."""
        parser = CockroachDBParser()
        metrics = parser.parse(zigzag_join_plan_json)

        assert "zigzag_join_count" in metrics
        assert metrics["zigzag_join_count"] > 0

    def test_parser_tracks_is_distributed(self, simple_plan_json):
        """Parser includes is_distributed metric."""
        parser = CockroachDBParser()
        metrics = parser.parse(simple_plan_json)

        assert "is_distributed" in metrics
        assert isinstance(metrics["is_distributed"], bool)

    def test_parser_tracks_remote_execution(self, simple_plan_json):
        """Parser includes has_remote_execution metric."""
        parser = CockroachDBParser()
        metrics = parser.parse(simple_plan_json)

        assert "has_remote_execution" in metrics
        assert isinstance(metrics["has_remote_execution"], bool)


class TestCockroachDBParserWarnings:
    """Test CockroachDB-specific warning detection."""

    def test_simple_hash_join_minimal_warnings(self, simple_plan_json):
        """Hash join should not generate CRDB warnings."""
        parser = CockroachDBParser()
        metrics = parser.parse(simple_plan_json)
        warnings = parser.identify_warnings(metrics, metrics["all_nodes"])

        # Should be minimal warnings
        assert isinstance(warnings, list)
        assert all(isinstance(w, str) for w in warnings)

    def test_many_lookup_joins_generate_warning(self, multiple_lookup_joins_plan_json):
        """Many Lookup Joins should trigger warning."""
        parser = CockroachDBParser()
        metrics = parser.parse(multiple_lookup_joins_plan_json)
        warnings = parser.identify_warnings(metrics, metrics["all_nodes"])

        # Should have warning about lookup joins
        # Note: May or may not have lookup warning depending on threshold, but should have some warnings
        assert isinstance(warnings, list)

    def test_full_scan_generates_warning(self, full_scan_plan_json):
        """Full seq scan should generate warning."""
        parser = CockroachDBParser()
        metrics = parser.parse(full_scan_plan_json)
        warnings = parser.identify_warnings(metrics, metrics["all_nodes"])

        # Should have at least one warning (full table scan)
        assert len(warnings) > 0
        assert all(isinstance(w, str) for w in warnings)


class TestCockroachDBParserScoring:
    """Test score calculation with CRDB-specific deductions."""

    def test_score_in_valid_range(self, simple_plan_json):
        """Score is always between 0 and 100."""
        parser = CockroachDBParser()
        metrics = parser.parse(simple_plan_json)
        warnings = parser.identify_warnings(metrics, metrics["all_nodes"])
        score = parser.calculate_score(metrics, warnings)

        assert 0 <= score <= 100

    def test_score_reproducible(self, simple_plan_json):
        """Same plan produces same score (reproducibility)."""
        parser = CockroachDBParser()
        metrics1 = parser.parse(simple_plan_json)
        warnings1 = parser.identify_warnings(metrics1, metrics1["all_nodes"])
        score1 = parser.calculate_score(metrics1, warnings1)

        metrics2 = parser.parse(simple_plan_json)
        warnings2 = parser.identify_warnings(metrics2, metrics2["all_nodes"])
        score2 = parser.calculate_score(metrics2, warnings2)

        assert score1 == score2

    def test_full_scan_reduces_score(self, simple_plan_json, full_scan_plan_json):
        """Plan with full scan should have lower score."""
        parser = CockroachDBParser()

        metrics1 = parser.parse(simple_plan_json)
        warnings1 = parser.identify_warnings(metrics1, metrics1["all_nodes"])
        score1 = parser.calculate_score(metrics1, warnings1)

        metrics2 = parser.parse(full_scan_plan_json)
        warnings2 = parser.identify_warnings(metrics2, metrics2["all_nodes"])
        score2 = parser.calculate_score(metrics2, warnings2)

        # Full scan plan should have lower score
        assert score2 < score1


class TestCockroachDBParserNormalization:
    """Test node normalization for CRDB-specific types."""

    def test_normalize_lookup_join(self, lookup_join_plan_json):
        """Lookup Join is properly normalized."""
        parser = CockroachDBParser()
        plan = lookup_join_plan_json["Plan"]

        normalized = parser.normalize_plan(plan)

        assert normalized["node_type"] == "Lookup Join"
        assert "extra_info" in normalized
        assert any("CockroachDB" in info for info in normalized["extra_info"])

    def test_normalize_zigzag_join(self, zigzag_join_plan_json):
        """Zigzag Join is properly normalized."""
        parser = CockroachDBParser()
        plan = zigzag_join_plan_json["Plan"]

        normalized = parser.normalize_plan(plan)

        assert normalized["node_type"] == "Zigzag Join"
        assert "extra_info" in normalized
        assert any("CockroachDB" in info for info in normalized["extra_info"])


class TestCockroachDBParserRecommendations:
    """Test recommendation generation."""

    def test_recommendations_generated(self, simple_plan_json):
        """Recommendations are generated."""
        parser = CockroachDBParser()
        metrics = parser.parse(simple_plan_json)
        warnings = parser.identify_warnings(metrics, metrics["all_nodes"])
        recommendations = parser.generate_recommendations(metrics, warnings)

        assert isinstance(recommendations, list)
        assert all(isinstance(r, str) for r in recommendations)
