"""Parse MongoDB executionStats output."""

from typing import Any


class MongoExplainParser:
    """Parse MongoDB EXPLAIN output (executionStats format)."""

    @staticmethod
    def parse(explain_json: dict) -> dict:
        """Parse MongoDB executionStats.

        Args:
            explain_json: Full explain output from collection.find().explain()

        Returns:
            Normalized structure with metrics and stages
            {
                "stages": [...],
                "metrics": {
                    "execution_time_ms": float,
                    "documents_returned": int,
                    "documents_examined": int,
                    "keys_examined": int,
                    "execution_stages": list,
                    "primary_stage": str,
                },
                "has_collection_scan": bool,
                "has_sort": bool,
                "has_index": bool,
            }
        """
        exec_stats = explain_json.get("executionStats", {})
        query_planner = explain_json.get("queryPlanner", {})

        # Traverse winning plan tree
        stages = MongoExplainParser._traverse_stages(query_planner.get("winningPlan", {}), depth=0)

        # Extract metrics
        nreturned = exec_stats.get("nReturned", 0)
        docs_examined = exec_stats.get("totalDocsExamined", 0)
        keys_examined = exec_stats.get("totalKeysExamined", 0)
        exec_time_ms = exec_stats.get("executionTimeMillis", 0)

        # Detect stage types
        stage_types = [s.get("stage") for s in stages if s.get("stage")]
        has_collscan = "COLLSCAN" in stage_types
        has_ixscan = "IXSCAN" in stage_types
        has_sort = "SORT" in stage_types

        return {
            "stages": stages,
            "metrics": {
                "execution_time_ms": exec_time_ms,
                "documents_returned": nreturned,
                "documents_examined": docs_examined,
                "keys_examined": keys_examined,
                "execution_stages": stage_types,
                "primary_stage": stage_types[0] if stage_types else "UNKNOWN",
            },
            "has_collection_scan": has_collscan,
            "has_sort": has_sort,
            "has_index": has_ixscan,
            "raw": explain_json,
        }

    @staticmethod
    def _traverse_stages(plan_node: dict, depth: int = 0) -> list[dict]:
        """Recursively traverse MongoDB plan tree.

        MongoDB plan nodes can have:
        - inputStage: single child (FETCH → IXSCAN, SORT → inputStage, etc)
        - stages: array of stages ($group/$sort/$match in aggregation - Phase 2)

        Args:
            plan_node: Current stage node
            depth: Recursion depth (for debugging)

        Returns:
            Flat list of normalized stages
        """
        normalized: dict[str, Any] = {
            "stage": plan_node.get("stage"),
            "index_name": plan_node.get("indexName"),
            "key_pattern": plan_node.get("keyPattern"),
            "filter": plan_node.get("filter"),
            "direction": plan_node.get("direction"),
            "depth": depth,
        }

        stages = [normalized]

        # Handle inputStage (most common)
        if "inputStage" in plan_node:
            input_stage = plan_node["inputStage"]
            stages.extend(MongoExplainParser._traverse_stages(input_stage, depth + 1))

        # Handle stages array (aggregation pipelines - Phase 2)
        if "stages" in plan_node:
            for stage in plan_node["stages"]:
                stages.extend(MongoExplainParser._traverse_stages(stage, depth + 1))

        return stages
