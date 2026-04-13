"""Unit tests for MongoDB EXPLAIN parser."""

from query_analyzer.adapters.nosql.mongodb_parser import MongoExplainParser


class TestMongoExplainParser:
    """MongoDB EXPLAIN output parsing tests."""

    def test_parse_empty_result(self) -> None:
        """Parser handles empty explain output."""
        result = MongoExplainParser.parse({})

        assert len(result["stages"]) >= 1  # At least one empty stage
        assert result["stages"][0]["stage"] is None  # Empty stage has None stage type
        assert result["metrics"]["execution_time_ms"] == 0
        assert result["metrics"]["documents_returned"] == 0
        assert result["metrics"]["documents_examined"] == 0
        assert result["has_collection_scan"] is False

    def test_parse_collscan_query(self) -> None:
        """Parser detects COLLSCAN stage."""
        explain_output = {
            "executionStats": {
                "nReturned": 100,
                "totalDocsExamined": 10000,
                "totalKeysExamined": 0,
                "executionTimeMillis": 50,
            },
            "queryPlanner": {
                "winningPlan": {
                    "stage": "COLLSCAN",
                    "filter": {"age": {"$gt": 18}},
                }
            },
        }

        result = MongoExplainParser.parse(explain_output)

        assert len(result["stages"]) > 0
        assert result["stages"][0]["stage"] == "COLLSCAN"
        assert result["metrics"]["execution_time_ms"] == 50
        assert result["metrics"]["documents_returned"] == 100
        assert result["metrics"]["documents_examined"] == 10000
        assert result["has_collection_scan"] is True
        assert result["has_index"] is False

    def test_parse_index_scan_query(self) -> None:
        """Parser detects IXSCAN stage."""
        explain_output = {
            "executionStats": {
                "nReturned": 50,
                "totalDocsExamined": 50,
                "totalKeysExamined": 50,
                "executionTimeMillis": 10,
            },
            "queryPlanner": {
                "winningPlan": {
                    "stage": "FETCH",
                    "inputStage": {
                        "stage": "IXSCAN",
                        "indexName": "age_1",
                        "keyPattern": {"age": 1},
                    },
                }
            },
        }

        result = MongoExplainParser.parse(explain_output)

        assert len(result["stages"]) > 0
        assert result["has_index"] is True
        assert result["has_collection_scan"] is False
        assert result["metrics"]["documents_examined"] == 50
        assert result["metrics"]["keys_examined"] == 50

    def test_parse_sort_stage(self) -> None:
        """Parser detects SORT stage."""
        explain_output = {
            "executionStats": {
                "nReturned": 100,
                "totalDocsExamined": 100,
                "totalKeysExamined": 0,
                "executionTimeMillis": 30,
            },
            "queryPlanner": {
                "winningPlan": {
                    "stage": "SORT",
                    "inputStage": {
                        "stage": "COLLSCAN",
                    },
                }
            },
        }

        result = MongoExplainParser.parse(explain_output)

        assert result["has_sort"] is True

    def test_parse_extraction_of_metrics(self) -> None:
        """Parser correctly extracts and calculates metrics."""
        explain_output = {
            "executionStats": {
                "nReturned": 200,
                "totalDocsExamined": 50000,
                "totalKeysExamined": 1000,
                "executionTimeMillis": 150,
            },
            "queryPlanner": {
                "winningPlan": {
                    "stage": "IXSCAN",
                }
            },
        }

        result = MongoExplainParser.parse(explain_output)

        metrics = result["metrics"]
        assert metrics["documents_returned"] == 200
        assert metrics["documents_examined"] == 50000
        assert metrics["keys_examined"] == 1000
        assert metrics["execution_time_ms"] == 150
        assert metrics["primary_stage"] == "IXSCAN"

    def test_parse_stage_depth_tracking(self) -> None:
        """Parser tracks stage depth for hierarchical structure."""
        explain_output = {
            "executionStats": {
                "nReturned": 50,
                "totalDocsExamined": 50,
                "totalKeysExamined": 50,
                "executionTimeMillis": 10,
            },
            "queryPlanner": {
                "winningPlan": {
                    "stage": "FETCH",
                    "inputStage": {
                        "stage": "IXSCAN",
                        "indexName": "age_1",
                        "keyPattern": {"age": 1},
                    },
                }
            },
        }

        result = MongoExplainParser.parse(explain_output)

        stages = result["stages"]
        assert stages[0]["depth"] == 0  # FETCH is at depth 0
        assert stages[1]["depth"] == 1  # IXSCAN is at depth 1

    def test_parse_index_properties(self) -> None:
        """Parser extracts index name and key pattern."""
        explain_output = {
            "executionStats": {
                "nReturned": 50,
                "totalDocsExamined": 50,
                "totalKeysExamined": 50,
                "executionTimeMillis": 10,
            },
            "queryPlanner": {
                "winningPlan": {
                    "stage": "IXSCAN",
                    "indexName": "age_index",
                    "keyPattern": {"age": 1},
                }
            },
        }

        result = MongoExplainParser.parse(explain_output)

        assert result["stages"][0]["index_name"] == "age_index"
        assert result["stages"][0]["key_pattern"] == {"age": 1}

    def test_parse_filter_extraction(self) -> None:
        """Parser extracts filter conditions."""
        explain_output = {
            "executionStats": {
                "nReturned": 100,
                "totalDocsExamined": 10000,
                "totalKeysExamined": 0,
                "executionTimeMillis": 50,
            },
            "queryPlanner": {
                "winningPlan": {
                    "stage": "COLLSCAN",
                    "filter": {"age": {"$gt": 18}, "city": "NYC"},
                }
            },
        }

        result = MongoExplainParser.parse(explain_output)

        assert result["stages"][0]["filter"] == {"age": {"$gt": 18}, "city": "NYC"}

    def test_parse_multiple_stages(self) -> None:
        """Parser handles multiple chained stages."""
        explain_output = {
            "executionStats": {
                "nReturned": 50,
                "totalDocsExamined": 50,
                "totalKeysExamined": 50,
                "executionTimeMillis": 20,
            },
            "queryPlanner": {
                "winningPlan": {
                    "stage": "SORT",
                    "inputStage": {
                        "stage": "FETCH",
                        "inputStage": {
                            "stage": "IXSCAN",
                            "indexName": "name_1",
                        },
                    },
                }
            },
        }

        result = MongoExplainParser.parse(explain_output)

        stages = result["stages"]
        assert len(stages) == 3
        assert stages[0]["stage"] == "SORT"
        assert stages[1]["stage"] == "FETCH"
        assert stages[2]["stage"] == "IXSCAN"
        assert stages[0]["depth"] == 0
        assert stages[1]["depth"] == 1
        assert stages[2]["depth"] == 2

    def test_parse_raw_plan_preserved(self) -> None:
        """Parser preserves raw explain output."""
        explain_output = {
            "executionStats": {
                "nReturned": 100,
                "totalDocsExamined": 10000,
            },
            "queryPlanner": {
                "winningPlan": {
                    "stage": "COLLSCAN",
                }
            },
            "custom_field": "preserved",
        }

        result = MongoExplainParser.parse(explain_output)

        assert result["raw"] == explain_output
        assert result["raw"]["custom_field"] == "preserved"
