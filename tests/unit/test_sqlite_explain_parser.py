"""Tests for SQLiteExplainParser."""

import pytest

from query_analyzer.adapters.sql.sqlite_parser import SQLiteExplainParser


class TestSQLiteExplainParser:
    """Test suite for SQLiteExplainParser."""

    @pytest.fixture
    def parser(self):
        """Create parser instance."""
        return SQLiteExplainParser(table_row_threshold=1000)

    @pytest.fixture
    def explain_full_scan(self):
        """EXPLAIN output for full table scan."""
        return "id\tparent\tnotused\tdetail\n0\t0\t0\tSCAN TABLE orders"

    @pytest.fixture
    def explain_indexed_search(self):
        """EXPLAIN output for indexed search."""
        return "id\tparent\tnotused\tdetail\n0\t0\t0\tSEARCH TABLE users USING INDEX idx_users_email (email=?)"

    @pytest.fixture
    def explain_join_with_scan_and_search(self):
        """EXPLAIN output for JOIN with one scan and one search."""
        return "id\tparent\tnotused\tdetail\n0\t0\t0\tSCAN TABLE orders\n1\t0\t0\tSEARCH TABLE customers USING INDEX idx_customers_id"

    @pytest.fixture
    def explain_multiple_scans(self):
        """EXPLAIN output for query with multiple scans."""
        return "id\tparent\tnotused\tdetail\n0\t0\t0\tSCAN TABLE orders\n1\t0\t0\tSCAN TABLE items"

    @pytest.fixture
    def explain_scan_with_where(self):
        """EXPLAIN output for scan with WHERE clause."""
        return "id\tparent\tnotused\tdetail\n0\t0\t0\tSCAN TABLE orders WHERE status=?"

    @pytest.fixture
    def explain_empty(self):
        """Empty EXPLAIN output."""
        return ""

    def test_parse_full_scan(self, parser, explain_full_scan):
        """Test parsing full table scan."""
        result = parser.parse(explain_full_scan)

        assert result["total_nodes"] == 1
        assert result["scan_count"] == 1
        assert result["search_count"] == 0
        assert "orders" in result["full_scan_tables"]
        assert len(result["indexed_searches"]) == 0

    def test_parse_indexed_search(self, parser, explain_indexed_search):
        """Test parsing indexed search."""
        result = parser.parse(explain_indexed_search)

        assert result["total_nodes"] == 1
        assert result["search_count"] == 1
        assert result["scan_count"] == 0
        assert "users" in result["indexed_searches"]
        assert len(result["full_scan_tables"]) == 0

    def test_parse_join_mixed(self, parser, explain_join_with_scan_and_search):
        """Test parsing JOIN with mixed scan and search."""
        result = parser.parse(explain_join_with_scan_and_search)

        assert result["total_nodes"] == 2
        assert result["scan_count"] == 1
        assert result["search_count"] == 1
        assert "orders" in result["full_scan_tables"]
        assert "customers" in result["indexed_searches"]

    def test_parse_multiple_scans(self, parser, explain_multiple_scans):
        """Test parsing multiple scans."""
        result = parser.parse(explain_multiple_scans)

        assert result["total_nodes"] == 2
        assert result["scan_count"] == 2
        assert result["search_count"] == 0
        assert "orders" in result["full_scan_tables"]
        assert "items" in result["full_scan_tables"]

    def test_parse_empty_output(self, parser, explain_empty):
        """Test parsing empty EXPLAIN output."""
        result = parser.parse(explain_empty)

        assert result["total_nodes"] == 0
        assert result["scan_count"] == 0
        assert result["search_count"] == 0
        assert result["full_scan_tables"] == []
        assert result["indexed_searches"] == []

    def test_parse_preserves_raw_plan(self, parser, explain_full_scan):
        """Test that raw EXPLAIN output is preserved."""
        result = parser.parse(explain_full_scan)

        assert result["raw_plan"] == explain_full_scan

    def test_parse_node_details(self, parser, explain_indexed_search):
        """Test that node details are correctly extracted."""
        result = parser.parse(explain_indexed_search)

        node = result["nodes"][0]
        assert node["id"] == 0
        assert node["parent"] == 0
        assert node["operation"] == "SEARCH_TABLE_WITH_INDEX"
        assert node["table"] == "users"
        assert node["index"] == "idx_users_email"
        assert node["uses_index"] is True
        assert node["is_full_scan"] is False

    def test_warnings_full_scan(self, parser, explain_full_scan):
        """Test that full scan generates warning."""
        parsed = parser.parse(explain_full_scan)
        warnings = parser.identify_warnings(parsed)

        assert len(warnings) > 0
        assert any("Full table scan" in w for w in warnings)
        assert any("orders" in w for w in warnings)

    def test_warnings_indexed_search(self, parser, explain_indexed_search):
        """Test that indexed search generates no warnings."""
        parsed = parser.parse(explain_indexed_search)
        warnings = parser.identify_warnings(parsed)

        assert len(warnings) == 0

    def test_warnings_mixed_scans_searches(
        self, parser, explain_join_with_scan_and_search
    ):
        """Test that mixed scans/searches generates warning."""
        parsed = parser.parse(explain_join_with_scan_and_search)
        warnings = parser.identify_warnings(parsed)

        assert len(warnings) > 0
        assert any("mixed" in w.lower() for w in warnings)

    def test_warnings_multiple_scans(self, parser, explain_multiple_scans):
        """Test that multiple scans generate multiple warnings."""
        parsed = parser.parse(explain_multiple_scans)
        warnings = parser.identify_warnings(parsed)

        assert len(warnings) >= 2

    def test_recommendations_no_warnings(self, parser):
        """Test that no warnings = positive recommendation."""
        recommendations = parser.generate_recommendations([])

        assert len(recommendations) == 1
        assert "well-optimized" in recommendations[0].lower()

    def test_recommendations_from_full_scan_warning(self, parser, explain_full_scan):
        """Test recommendations for full scan."""
        parsed = parser.parse(explain_full_scan)
        warnings = parser.identify_warnings(parsed)
        recommendations = parser.generate_recommendations(warnings)

        assert len(recommendations) > 0
        assert any("index" in r.lower() for r in recommendations)

    def test_recommendations_mixed_optimization(
        self, parser, explain_join_with_scan_and_search
    ):
        """Test recommendations for mixed optimization."""
        parsed = parser.parse(explain_join_with_scan_and_search)
        warnings = parser.identify_warnings(parsed)
        recommendations = parser.generate_recommendations(warnings)

        assert len(recommendations) > 0

    def test_score_perfect_indexed(self, parser, explain_indexed_search):
        """Test that all-indexed query gets high score."""
        parsed = parser.parse(explain_indexed_search)
        warnings = parser.identify_warnings(parsed)
        score = parser.calculate_score(parsed, warnings)

        assert score >= 85
        assert score <= 100

    def test_score_full_scan(self, parser, explain_full_scan):
        """Test that full scan gets lower score."""
        parsed = parser.parse(explain_full_scan)
        warnings = parser.identify_warnings(parsed)
        score = parser.calculate_score(parsed, warnings)

        assert score <= 70
        assert score >= 0

    def test_score_multiple_scans_lower(self, parser, explain_multiple_scans):
        """Test that multiple scans result in lower score."""
        parsed = parser.parse(explain_multiple_scans)
        warnings = parser.identify_warnings(parsed)
        score = parser.calculate_score(parsed, warnings)

        assert score < 60

    def test_score_mixed_scans_searches(
        self, parser, explain_join_with_scan_and_search
    ):
        """Test that mixed scans/searches gets medium score."""
        parsed = parser.parse(explain_join_with_scan_and_search)
        warnings = parser.identify_warnings(parsed)
        score = parser.calculate_score(parsed, warnings)

        assert 30 <= score <= 85

    def test_score_range_valid(self, parser):
        """Test that score is always 0-100."""
        test_cases = [
            "id\tparent\tnotused\tdetail\n0\t0\t0\tSCAN TABLE t1\n1\t0\t0\tSCAN TABLE t2\n2\t0\t0\tSCAN TABLE t3",
            "id\tparent\tnotused\tdetail\n0\t0\t0\tSEARCH TABLE t1 USING INDEX idx1",
        ]

        for explain_output in test_cases:
            parsed = parser.parse(explain_output)
            warnings = parser.identify_warnings(parsed)
            score = parser.calculate_score(parsed, warnings)

            assert 0 <= score <= 100

    def test_extract_scan_table(self, parser):
        """Test extracting SCAN TABLE operation."""
        info = parser._extract_operation_info("SCAN TABLE orders")

        assert info["operation"] == "SCAN_TABLE"
        assert info["table"] == "orders"
        assert info["uses_index"] is False
        assert info["is_full_scan"] is True

    def test_extract_search_table(self, parser):
        """Test extracting SEARCH TABLE operation."""
        info = parser._extract_operation_info(
            "SEARCH TABLE customers USING INDEX idx_customers_id (id=?)"
        )

        assert info["operation"] == "SEARCH_TABLE_WITH_INDEX"
        assert info["table"] == "customers"
        assert info["index"] == "idx_customers_id"
        assert info["uses_index"] is True
        assert info["is_full_scan"] is False

    def test_extract_scan_with_where(self, parser):
        """Test extracting SCAN TABLE with WHERE."""
        info = parser._extract_operation_info("SCAN TABLE orders WHERE status = ?")

        assert info["operation"] == "SCAN_TABLE"
        assert info["table"] == "orders"

    def test_extract_correlated_subquery(self, parser):
        """Test extracting correlated subquery."""
        info = parser._extract_operation_info("EXECUTE CORRELATED SCALAR SUBQUERY")

        assert info["operation"] == "CORRELATED_SUBQUERY"

    def test_extract_temp_btree(self, parser):
        """Test extracting temp B-tree."""
        info = parser._extract_operation_info("USE TEMP B-TREE FOR ORDER BY")

        assert info["operation"] == "TEMP_BTREE"

    def test_extract_unknown(self, parser):
        """Test extracting unknown operation."""
        info = parser._extract_operation_info("UNKNOWN OPERATION")

        assert info["operation"] == "UNKNOWN"

    def test_parse_with_extra_whitespace(self, parser):
        """Test parsing with extra whitespace."""
        explain = "id\tparent\tnotused\tdetail\n  \n0\t0\t0\tSCAN TABLE orders\n  "
        result = parser.parse(explain)

        assert result["total_nodes"] == 1

    def test_parse_mixed_case_table_names(self, parser):
        """Test parsing preserves table name case."""
        explain = "id\tparent\tnotused\tdetail\n0\t0\t0\tSCAN TABLE Orders"
        result = parser.parse(explain)

        assert "Orders" in result["full_scan_tables"]

    def test_score_consistency(self, parser, explain_full_scan):
        """Test that score calculation is consistent."""
        parsed = parser.parse(explain_full_scan)
        warnings = parser.identify_warnings(parsed)

        score1 = parser.calculate_score(parsed, warnings)
        score2 = parser.calculate_score(parsed, warnings)

        assert score1 == score2
