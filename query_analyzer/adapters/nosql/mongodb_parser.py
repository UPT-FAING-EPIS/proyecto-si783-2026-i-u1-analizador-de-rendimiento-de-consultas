"""Parse MongoDB executionStats output."""

import json
from typing import Any

from ..models import PlanNode


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

        stages = MongoExplainParser._traverse_stages(query_planner.get("winningPlan", {}), depth=0)

        nreturned = exec_stats.get("nReturned", 0)
        docs_examined = exec_stats.get("totalDocsExamined", 0)
        keys_examined = exec_stats.get("totalKeysExamined", 0)
        exec_time_ms = exec_stats.get("executionTimeMillis", 0)

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
    def build_plan_tree(explain_json: dict) -> PlanNode | None:
        """Build PlanNode hierarchy from MongoDB explain output.

        Args:
            explain_json: Full explain output from collection.find().explain()

        Returns:
            PlanNode tree or None if no plan available
        """
        query_planner = explain_json.get("queryPlanner", {})
        winning_plan = query_planner.get("winningPlan", {})

        if not winning_plan:
            return None

        return MongoExplainParser._build_node_tree(winning_plan, 0)

    @staticmethod
    def _build_node_tree(plan_node: dict, depth: int = 0) -> PlanNode | None:
        """Recursively build PlanNode tree from MongoDB plan.

        Args:
            plan_node: Current stage node
            depth: Recursion depth

        Returns:
            PlanNode or None if invalid
        """
        if not plan_node:
            return None

        stage_name = plan_node.get("stage", "Unknown")

        properties: dict[str, Any] = {
            "depth": depth,
        }

        if "indexName" in plan_node:
            properties["index_name"] = plan_node["indexName"]

        if "keyPattern" in plan_node:
            properties["key_pattern"] = plan_node["keyPattern"]

        if "filter" in plan_node:
            properties["filter"] = (
                json.dumps(plan_node["filter"])
                if isinstance(plan_node["filter"], dict)
                else plan_node["filter"]
            )

        if "direction" in plan_node:
            properties["direction"] = plan_node["direction"]

        children: list[PlanNode] = []

        if "inputStage" in plan_node:
            input_stage = plan_node["inputStage"]
            child_node = MongoExplainParser._build_node_tree(input_stage, depth + 1)
            if child_node:
                children.append(child_node)

        if "stages" in plan_node:
            for stage in plan_node["stages"]:
                child_node = MongoExplainParser._build_node_tree(stage, depth + 1)
                if child_node:
                    children.append(child_node)

        node_type = MongoExplainParser._map_stage_to_node_type(stage_name)

        return PlanNode(
            node_type=node_type,
            cost=None,
            estimated_rows=None,
            actual_rows=None,
            actual_time_ms=None,
            children=children,
            properties=properties,
        )

    @staticmethod
    def _map_stage_to_node_type(stage_name: str) -> str:
        """Map MongoDB stage name to generic node type.

        Args:
            stage_name: MongoDB stage name (COLLSCAN, IXSCAN, FETCH, etc.)

        Returns:
            Generic node type for display
        """
        mapping = {
            "COLLSCAN": "Collection Scan",
            "IXSCAN": "Index Scan",
            "FETCH": "Fetch",
            "SORT": "Sort",
            "LIMIT": "Limit",
            "SKIP": "Skip",
            "PROJECTION": "Projection",
            "SHARDING_FILTER": "Sharding Filter",
            "COUNT": "Count",
            "COUNT_SCAN": "Count Scan",
            "DISTINCT": "Distinct",
            "DISTINCT_SCAN": "Distinct Scan",
            "MULTI_PLAN": "Multi Plan",
            "TEXT": "Text Search",
            "FLOW_CONTROL": "Flow Control",
            "SHARD_MERGE": "Shard Merge",
            "UNKNOWN": "Unknown",
        }
        return mapping.get(stage_name, f"Unknown ({stage_name})")

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
