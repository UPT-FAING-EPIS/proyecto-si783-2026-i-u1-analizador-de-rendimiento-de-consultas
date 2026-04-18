"""Unit tests for Neo4j EXPLAIN parser."""

import pytest

from query_analyzer.adapters.graph.neo4j_parser import Neo4jExplainParser

# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def parser() -> Neo4jExplainParser:
    """Neo4j parser instance."""
    return Neo4jExplainParser(expand_threshold=1000)


# ============================================================================
# SAMPLE DATA
# ============================================================================


@pytest.fixture
def simple_profile_result() -> dict:
    """Simple Neo4j 5.26 PROFILE result with one scan node (flat structure)."""
    # In Neo4j 5.26, summary.profile IS the root operator
    root_operator = {
        "operatorType": "ProduceResults",
        "dbHits": 0,
        "rows": 5,
        "args": {"EstimatedRows": 5},
        "children": [
            {
                "operatorType": "NodeByLabelScan",
                "dbHits": 100,
                "rows": 5,
                "args": {"label": "User", "EstimatedRows": 1000},
                "children": [],
            }
        ],
    }
    # _extract_profile_info wraps this in the standard structure for the parser
    return {
        "profile": {
            "plan": root_operator,
            "stats": {"rows": 5, "time": 10, "dbHits": 100},
        }
    }


@pytest.fixture
def expand_profile_result() -> dict:
    """Neo4j 5.26 PROFILE result with Expand node (flat structure)."""
    root_operator = {
        "operatorType": "ProduceResults",
        "dbHits": 0,
        "rows": 10,
        "args": {"EstimatedRows": 10},
        "children": [
            {
                "operatorType": "Expand(All)",
                "dbHits": 50,
                "rows": 10,
                "args": {"EstimatedRows": 10},
                "children": [
                    {
                        "operatorType": "NodeByLabelScan",
                        "dbHits": 5,
                        "rows": 1,
                        "args": {"label": "User", "EstimatedRows": 100},
                        "children": [],
                    }
                ],
            }
        ],
    }
    return {
        "profile": {
            "plan": root_operator,
            "stats": {"rows": 10, "time": 15, "dbHits": 55},
        }
    }


@pytest.fixture
def cartesian_product_result() -> dict:
    """Neo4j 5.26 PROFILE result with CartesianProduct (flat structure)."""
    root_operator = {
        "operatorType": "ProduceResults",
        "dbHits": 0,
        "rows": 100,
        "args": {"EstimatedRows": 100},
        "children": [
            {
                "operatorType": "CartesianProduct",
                "dbHits": 200,
                "rows": 100,
                "args": {"EstimatedRows": 100},
                "children": [
                    {
                        "operatorType": "NodeByLabelScan",
                        "dbHits": 100,
                        "rows": 10,
                        "args": {"label": "User", "EstimatedRows": 100},
                        "children": [],
                    },
                    {
                        "operatorType": "NodeByLabelScan",
                        "dbHits": 100,
                        "rows": 10,
                        "args": {"label": "Product", "EstimatedRows": 100},
                        "children": [],
                    },
                ],
            }
        ],
    }
    return {
        "profile": {
            "plan": root_operator,
            "stats": {"rows": 100, "time": 20, "dbHits": 200},
        }
    }


# ============================================================================
# TESTS - Parse Basic Structure
# ============================================================================


class TestNeo4jParserBasic:
    """Basic parser functionality."""

    def test_parse_simple_result(
        self, parser: Neo4jExplainParser, simple_profile_result: dict
    ) -> None:
        """Parse simple profile result."""
        metrics = parser.parse(simple_profile_result)

        assert metrics["execution_time_ms"] >= 0
        assert metrics["total_db_hits"] == 100
        assert metrics["total_rows"] == 5
        assert metrics["node_count"] == 2  # ProduceResults + NodeByLabelScan

    def test_parse_with_expand(
        self, parser: Neo4jExplainParser, expand_profile_result: dict
    ) -> None:
        """Parse profile with Expand node."""
        metrics = parser.parse(expand_profile_result)

        assert metrics["node_count"] == 3  # ProduceResults + Expand + NodeByLabelScan
        assert metrics["total_db_hits"] == 55  # 0 + 50 + 5
        assert len(metrics["expand_nodes"]) == 1
        assert len(metrics["scan_nodes"]) == 1

    def test_parse_cartesian_product(
        self, parser: Neo4jExplainParser, cartesian_product_result: dict
    ) -> None:
        """Parse profile with CartesianProduct."""
        metrics = parser.parse(cartesian_product_result)

        assert metrics["node_count"] == 4  # ProduceResults + CartesianProduct + 2 scans
        assert len(metrics["join_nodes"]) == 1
        assert metrics["join_nodes"][0]["operatorType"] == "CartesianProduct"


# ============================================================================
# TESTS - Metrics Aggregation
# ============================================================================


class TestNeo4jParserMetrics:
    """Metrics aggregation tests."""

    def test_aggregate_db_hits(
        self, parser: Neo4jExplainParser, expand_profile_result: dict
    ) -> None:
        """Correctly aggregate db_hits across nodes."""
        metrics = parser.parse(expand_profile_result)

        # Sum should be: 0 (ProduceResults) + 50 (Expand) + 5 (Scan) = 55
        assert metrics["total_db_hits"] == 55

    def test_find_most_expensive_node(
        self, parser: Neo4jExplainParser, expand_profile_result: dict
    ) -> None:
        """Identify node with highest db_hits."""
        metrics = parser.parse(expand_profile_result)

        most_expensive = metrics["most_expensive_node"]
        assert most_expensive["dbHits"] == 50  # The Expand node
        assert most_expensive["operatorType"] == "Expand(All)"


# ============================================================================
# TESTS - Plan Normalization
# ============================================================================


class TestNeo4jParserNormalization:
    """Plan normalization to engine-agnostic format."""

    def test_normalize_label_scan(self, parser: Neo4jExplainParser) -> None:
        """Normalize NodeByLabelScan node."""
        node = {
            "operatorType": "NodeByLabelScan",
            "dbHits": 100,
            "rows": 5,
            "args": {"label": "User", "EstimatedRows": 1000},
            "children": [],
        }

        normalized = parser.normalize_plan(node)

        assert normalized["node_type"] == "NodeByLabelScan"
        assert normalized["actual_rows"] == 5
        assert normalized["estimated_rows"] == 1000
        assert normalized["db_hits"] == 100
        assert normalized["index_used"] is False

    def test_normalize_expand(self, parser: Neo4jExplainParser) -> None:
        """Normalize Expand node."""
        node = {
            "operatorType": "Expand(All)",
            "dbHits": 50,
            "rows": 10,
            "args": {"EstimatedRows": 10},
            "children": [],
        }

        normalized = parser.normalize_plan(node)

        assert normalized["node_type"] == "Expand"
        assert normalized["actual_rows"] == 10
        assert normalized["db_hits"] == 50

    def test_normalize_index_scan(self, parser: Neo4jExplainParser) -> None:
        """Normalize NodeIndexScan node."""
        node = {
            "operatorType": "NodeIndexSeek",
            "dbHits": 10,
            "rows": 1,
            "args": {"index": "idx_email", "EstimatedRows": 1},
            "children": [],
        }

        normalized = parser.normalize_plan(node)

        assert normalized["node_type"] == "NodeIndexScan"
        assert normalized["index_used"] is True


# ============================================================================
# TESTS - Anti-pattern Detection
# ============================================================================


class TestNeo4jAntiPatternDetection:
    """Anti-pattern detection in Cypher plans."""

    def test_detect_all_nodes_scan(self, parser: Neo4jExplainParser) -> None:
        """Detect AllNodesScan anti-pattern."""
        plan = {
            "operatorType": "ProduceResults",
            "children": [
                {
                    "operatorType": "AllNodesScan",
                    "dbHits": 10000,
                    "rows": 10000,
                    "children": [],
                }
            ],
        }

        patterns = parser.detect_anti_patterns_cypher(plan)

        assert len(patterns) > 0
        assert any(p["type"] == "AllNodesScan" for p in patterns)
        assert any(p["severity"] == "HIGH" for p in patterns)

    def test_detect_cartesian_product(self, parser: Neo4jExplainParser) -> None:
        """Detect CartesianProduct anti-pattern."""
        plan = {
            "operatorType": "ProduceResults",
            "children": [
                {
                    "operatorType": "CartesianProduct",
                    "dbHits": 100,
                    "rows": 100,
                    "children": [],
                }
            ],
        }

        patterns = parser.detect_anti_patterns_cypher(plan)

        assert len(patterns) > 0
        assert any(p["type"] == "CartesianProduct" for p in patterns)

    def test_detect_label_scan_with_filter(self, parser: Neo4jExplainParser) -> None:
        """Detect label scan followed by filter."""
        plan = {
            "operatorType": "ProduceResults",
            "children": [
                {
                    "operatorType": "NodeByLabelScan",
                    "dbHits": 100,
                    "rows": 10,
                    "children": [
                        {
                            "operatorType": "Filter",
                            "dbHits": 100,
                            "rows": 5,
                            "children": [],
                        }
                    ],
                }
            ],
        }

        patterns = parser.detect_anti_patterns_cypher(plan)

        # Should detect LabelScanWithFilter
        assert any(p["type"] == "LabelScanWithFilter" for p in patterns)

    def test_detect_unbounded_expand(self, parser: Neo4jExplainParser) -> None:
        """Detect Expand without limit on high-degree node."""
        plan = {
            "operatorType": "ProduceResults",
            "children": [
                {
                    "operatorType": "Expand(All)",
                    "dbHits": 5000,
                    "rows": 2000,  # Over threshold
                    "children": [],
                }
            ],
        }

        patterns = parser.detect_anti_patterns_cypher(plan)

        assert any(p["type"] == "UnboundedExpand" for p in patterns)

    def test_detect_filter_after_expand(self, parser: Neo4jExplainParser) -> None:
        """Detect Filter applied after Expand."""
        plan = {
            "operatorType": "ProduceResults",
            "children": [
                {
                    "operatorType": "Expand(All)",
                    "dbHits": 100,
                    "rows": 50,
                    "children": [
                        {
                            "operatorType": "Filter",
                            "dbHits": 50,
                            "rows": 10,
                            "children": [],
                        }
                    ],
                }
            ],
        }

        patterns = parser.detect_anti_patterns_cypher(plan)

        assert any(p["type"] == "FilterAfterExpand" for p in patterns)


# ============================================================================
# TESTS - Edge Cases
# ============================================================================


class TestNeo4jParserEdgeCases:
    """Edge case handling."""

    def test_parse_empty_plan(self, parser: Neo4jExplainParser) -> None:
        """Handle empty profile result."""
        result = {"profile": {"plan": {}, "stats": {}}}

        metrics = parser.parse(result)

        assert metrics["total_db_hits"] == 0
        assert metrics["total_rows"] == 0
        assert metrics["node_count"] == 0

    def test_normalize_empty_plan(self, parser: Neo4jExplainParser) -> None:
        """Normalize empty plan node."""
        normalized = parser.normalize_plan({})

        assert normalized == {}

    def test_normalize_plan_with_children(self, parser: Neo4jExplainParser) -> None:
        """Normalize plan recursively with children."""
        plan = {
            "operatorType": "Filter",
            "dbHits": 50,
            "rows": 10,
            "args": {"Condition": "n.age > 18", "EstimatedRows": 20},
            "children": [
                {
                    "operatorType": "NodeByLabelScan",
                    "dbHits": 100,
                    "rows": 20,
                    "args": {"EstimatedRows": 100},
                    "children": [],
                }
            ],
        }

        normalized = parser.normalize_plan(plan)

        assert normalized["node_type"] == "Filter"
        assert len(normalized["children"]) == 1
        assert normalized["children"][0]["node_type"] == "NodeByLabelScan"
