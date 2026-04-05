import pytest

from query_analyzer.adapters.sql.mysql_parser import MySQLExplainParser


@pytest.fixture
def parser():
    return MySQLExplainParser()


@pytest.fixture
def full_scan_json():
    return """{
        "query_block": {
            "select_id": 1,
            "cost_info": {
                "query_cost": "101.00"
            },
            "table": {
                "table_name": "customers",
                "access_type": "ALL",
                "rows_examined": 1000,
                "rows_produced": 1000,
                "cost_info": {
                    "read_cost": "100.00",
                    "eval_cost": "1.00",
                    "prefix_cost": "101.00"
                }
            }
        }
    }"""


@pytest.fixture
def indexed_search_json():
    return """{
        "query_block": {
            "select_id": 1,
            "table": {
                "table_name": "orders",
                "access_type": "ref",
                "possible_keys": ["idx_customer_id"],
                "key": "idx_customer_id",
                "key_length": "4",
                "used_key_parts": ["customer_id"],
                "ref": ["query_analyzer.customers.id"],
                "rows_examined": 5,
                "rows_produced": 5,
                "cost_info": {
                    "read_cost": "2.50",
                    "eval_cost": "0.50",
                    "prefix_cost": "3.00"
                }
            }
        }
    }"""


@pytest.fixture
def filesort_json():
    return """{
        "query_block": {
            "select_id": 1,
            "table": {
                "table_name": "customers",
                "access_type": "ALL",
                "rows_examined": 100,
                "rows_produced": 100
            },
            "order_by": [
                {
                    "item": "customers.name",
                    "filesort": true,
                    "cost": 100.0
                }
            ]
        }
    }"""


@pytest.fixture
def temporary_json():
    return """{
        "query_block": {
            "select_id": 1,
            "table": {
                "table_name": "orders",
                "access_type": "ref",
                "rows_examined": 500,
                "rows_produced": 500,
                "extra": [
                    {
                        "using_temporary_table": true
                    }
                ]
            }
        }
    }"""


@pytest.fixture
def complex_json():
    return """{
        "query_block": {
            "select_id": 1,
            "nested_loop": [
                {
                    "table": {
                        "table_name": "customers",
                        "access_type": "ALL",
                        "rows_examined": 1000,
                        "extra": [
                            {
                                "using_temporary_table": true
                            }
                        ]
                    }
                }
            ],
            "order_by": [
                {
                    "item": "id",
                    "filesort": true,
                    "cost": 200.0
                }
            ]
        }
    }"""


class TestMySQLExplainParser:
    def test_parse_full_scan(self, parser, full_scan_json):
        result = parser.parse(full_scan_json)

        assert result["has_full_scan"] is True
        assert len(result["tables_accessed"]) == 1
        assert result["tables_accessed"][0]["table_name"] == "customers"
        assert result["tables_accessed"][0]["access_type"] == "ALL"
        assert result["tables_accessed"][0]["is_full_scan"] is True

    def test_parse_indexed_search(self, parser, indexed_search_json):
        result = parser.parse(indexed_search_json)

        assert result["has_full_scan"] is False
        assert len(result["tables_accessed"]) == 1
        assert result["tables_accessed"][0]["table_name"] == "orders"
        assert result["tables_accessed"][0]["access_type"] == "REF"
        assert result["tables_accessed"][0]["key_used"] == "idx_customer_id"
        assert result["tables_accessed"][0]["is_full_scan"] is False

    def test_parse_filesort(self, parser, filesort_json):
        result = parser.parse(filesort_json)

        assert result["has_using_filesort"] is True
        assert result["has_full_scan"] is True

    def test_parse_temporary(self, parser, temporary_json):
        result = parser.parse(temporary_json)

        assert result["has_using_temporary"] is True

    def test_parse_complex(self, parser, complex_json):
        result = parser.parse(complex_json)

        assert result["has_full_scan"] is True
        assert result["has_using_filesort"] is True
        assert result["has_using_temporary"] is True

    def test_parse_empty(self, parser):
        result = parser.parse("{}")

        assert result["has_full_scan"] is False
        assert result["has_using_filesort"] is False
        assert result["has_using_temporary"] is False
        assert len(result["tables_accessed"]) == 0

    def test_parse_invalid_json(self, parser):
        result = parser.parse("invalid json")

        assert result["has_full_scan"] is False
        assert len(result["tables_accessed"]) == 0

    def test_warnings_full_scan(self, parser, full_scan_json):
        parsed = parser.parse(full_scan_json)
        warnings = parser.identify_warnings(parsed)

        assert len(warnings) > 0
        assert any("Full table scan" in w for w in warnings)
        assert any("customers" in w for w in warnings)

    def test_warnings_filesort(self, parser, filesort_json):
        parsed = parser.parse(filesort_json)
        warnings = parser.identify_warnings(parsed)

        assert any("filesort" in w.lower() for w in warnings)

    def test_warnings_temporary(self, parser, temporary_json):
        parsed = parser.parse(temporary_json)
        warnings = parser.identify_warnings(parsed)

        assert any("temporary" in w.lower() for w in warnings)

    def test_warnings_multiple(self, parser, complex_json):
        parsed = parser.parse(complex_json)
        warnings = parser.identify_warnings(parsed)

        assert len(warnings) >= 3
        assert any("scan" in w.lower() for w in warnings)
        assert any("filesort" in w.lower() for w in warnings)
        assert any("temporary" in w.lower() for w in warnings)

    def test_recommendations_full_scan(self, parser, full_scan_json):
        parsed = parser.parse(full_scan_json)
        warnings = parser.identify_warnings(parsed)
        recommendations = parser.generate_recommendations(warnings)

        assert len(recommendations) > 0
        assert any("index" in r.lower() for r in recommendations)

    def test_recommendations_filesort(self, parser, filesort_json):
        parsed = parser.parse(filesort_json)
        warnings = parser.identify_warnings(parsed)
        recommendations = parser.generate_recommendations(warnings)

        assert any("ORDER BY" in r for r in recommendations)

    def test_recommendations_temporary(self, parser, temporary_json):
        parsed = parser.parse(temporary_json)
        warnings = parser.identify_warnings(parsed)
        recommendations = parser.generate_recommendations(warnings)

        assert len(recommendations) > 0

    def test_score_perfect_indexed(self, parser, indexed_search_json):
        parsed = parser.parse(indexed_search_json)
        warnings = parser.identify_warnings(parsed)
        score = parser.calculate_score(parsed, warnings)

        assert score == 100

    def test_score_full_scan(self, parser, full_scan_json):
        parsed = parser.parse(full_scan_json)
        warnings = parser.identify_warnings(parsed)
        score = parser.calculate_score(parsed, warnings)

        assert score == 70

    def test_score_filesort(self, parser, filesort_json):
        parsed = parser.parse(filesort_json)
        warnings = parser.identify_warnings(parsed)
        score = parser.calculate_score(parsed, warnings)

        assert score == 55

    def test_score_temporary(self, parser, temporary_json):
        parsed = parser.parse(temporary_json)
        warnings = parser.identify_warnings(parsed)
        score = parser.calculate_score(parsed, warnings)

        assert score == 80

    def test_score_combined(self, parser, complex_json):
        parsed = parser.parse(complex_json)
        warnings = parser.identify_warnings(parsed)
        score = parser.calculate_score(parsed, warnings)

        assert score == 35

    def test_score_range_valid(self, parser):
        test_cases = [
            "",
            "{}",
            '{"query_block": {}}',
        ]

        for test_json in test_cases:
            parsed = parser.parse(test_json)
            warnings = parser.identify_warnings(parsed)
            score = parser.calculate_score(parsed, warnings)

            assert 0 <= score <= 100

    def test_parse_preserves_raw_json(self, parser, full_scan_json):
        result = parser.parse(full_scan_json)

        assert "raw_json" in result
        assert result["raw_json"] == full_scan_json

    def test_rows_examined_accumulated(self, parser):
        json_str = """{
            "query_block": {
                "nested_loop": [
                    {
                        "table": {
                            "table_name": "t1",
                            "access_type": "ALL",
                            "rows_examined": 100
                        }
                    },
                    {
                        "table": {
                            "table_name": "t2",
                            "access_type": "ALL",
                            "rows_examined": 200
                        }
                    }
                ]
            }
        }"""

        result = parser.parse(json_str)

        assert result["total_rows_examined"] == 300
