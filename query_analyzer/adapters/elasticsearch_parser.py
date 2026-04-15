"""Parse Elasticsearch _profile API responses and query structures."""

from typing import Any, cast


class ElasticsearchParser:
    """Parser for Elasticsearch _profile output and query analysis.

    Analyzes search profiles from Elasticsearch _profile API to extract
    execution metrics, query structure, and identify performance anti-patterns.

    The _profile API provides detailed execution information broken down into:
    - query: Time spent building/executing the query
    - collector: Time spent collecting results
    - rewrite: Time spent rewriting queries (e.g., for filters)
    - aggregations: Time spent on aggregations (if present)
    """

    @staticmethod
    def parse_profile(response: dict[str, Any]) -> dict[str, Any]:
        """Parse Elasticsearch search response with _profile data.

        Extracts profile timing information from all shards and builds
        a normalized structure compatible with QueryAnalysisReport.

        Args:
            response: Full Elasticsearch search response including profile data

        Returns:
            Normalized dict with:
                - stages: List of execution stages with timing
                - metrics: Aggregated metrics (execution_time_ms, took, etc.)
                - query_type: Detected query type
                - has_filter: Whether query includes filters
                - raw: Original profile response
        """
        profile = response.get("profile", {})
        shards = profile.get("shards", [])
        took = response.get("took", 0)
        timed_out = response.get("timed_out", False)

        # Aggregate timing across shards
        total_query_time_us = 0.0
        total_collector_time_us = 0.0
        stages = []

        for _shard_idx, shard_profile in enumerate(shards):
            shard_stages = ElasticsearchParser._parse_shard_profile(shard_profile)
            stages.extend(shard_stages)

            # Sum timing from main phases
            query_list = shard_profile.get("query", [])
            collector_list = shard_profile.get("collector", [])

            if query_list:
                total_query_time_us += query_list[0].get("time_in_nanos", 0) / 1000.0

            if collector_list:
                total_collector_time_us += collector_list[0].get("time_in_nanos", 0) / 1000.0

        # Convert to milliseconds
        execution_time_ms = (total_query_time_us + total_collector_time_us) / 1000.0

        # Extract query structure from request (if available in response)
        query_structure = response.get("query", {})
        query_type = ElasticsearchParser._detect_query_type(query_structure)
        has_filter = ElasticsearchParser._has_filter(query_structure)

        return {
            "stages": stages,
            "metrics": {
                "execution_time_ms": execution_time_ms,
                "took": took,
                "timed_out": timed_out,
                "query_type": query_type,
                "total_query_time_us": total_query_time_us,
                "total_collector_time_us": total_collector_time_us,
                "documents_examined": 0,  # Estimated below
                "documents_returned": response.get("hits", {}).get("total", {}).get("value", 0),
            },
            "has_filter": has_filter,
            "raw": profile,
        }

    @staticmethod
    def _parse_shard_profile(shard_profile: dict[str, Any]) -> list[dict[str, Any]]:
        """Parse a single shard's profile into stages.

        Args:
            shard_profile: Profile dict for one shard

        Returns:
            List of stage dicts with timing and details
        """
        stages = []

        # Process query phases
        for phase_name in ["query", "collector", "rewrite"]:
            phase_list = shard_profile.get(phase_name, [])
            for item in phase_list:
                stage_dict = {
                    "name": phase_name,
                    "time_us": item.get("time_in_nanos", 0) / 1000.0,
                    "breakdown": item.get("breakdown", {}),
                    "children": item.get("children", []),
                    "description": item.get("description", ""),
                }
                stages.append(stage_dict)

        return stages

    @staticmethod
    def _detect_query_type(query_structure: dict[str, Any]) -> str:
        """Detect the primary query type from query structure.

        Args:
            query_structure: Query dict from Elasticsearch query DSL

        Returns:
            Query type string: "match_all", "bool", "wildcard", "script", etc.
        """
        if not query_structure:
            return "unknown"

        # Check for top-level query type
        if "match_all" in query_structure:
            return "match_all"
        elif "bool" in query_structure:
            return "bool"
        elif "wildcard" in query_structure:
            return "wildcard"
        elif "script_score" in query_structure:
            return "script_score"
        elif "script" in query_structure:
            return "script"
        elif "term" in query_structure:
            return "term"
        elif "match" in query_structure:
            return "match"
        elif "range" in query_structure:
            return "range"
        else:
            # Return first key if it's a recognized query type
            keys = list(query_structure.keys())
            return keys[0] if keys else "unknown"

    @staticmethod
    def _has_filter(query_structure: dict[str, Any]) -> bool:
        """Check if query includes filters.

        A query "has filter" if:
        - It's a bool query with a must/should/filter clause
        - It's not a bare match_all query

        Args:
            query_structure: Query dict

        Returns:
            True if query has filters, False otherwise
        """
        if not query_structure:
            return False

        # If it's a bool query, check for filter/must/should clauses
        if "bool" in query_structure:
            bool_clause = query_structure["bool"]
            return bool(
                bool_clause.get("filter") or bool_clause.get("must") or bool_clause.get("should")
            )

        # If it's just match_all, no filters
        if "match_all" in query_structure:
            return False

        # Any other query type implicitly has filtering
        return True

    @staticmethod
    def parse_query_string(query_str: str) -> dict[str, Any]:
        """Parse JSON query string into dict.

        Args:
            query_str: JSON string representing Elasticsearch query

        Returns:
            Parsed dict

        Raises:
            ValueError: If query string is not valid JSON
        """
        import json

        try:
            parsed = json.loads(query_str)
            return cast(dict[str, Any], parsed)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON query string: {e}") from e

    @staticmethod
    def has_wildcard_query(query_structure: dict[str, Any]) -> bool:
        """Check if query contains wildcard queries.

        Recursively searches the query structure for wildcard queries.

        Args:
            query_structure: Query dict

        Returns:
            True if any wildcard query found
        """
        if not isinstance(query_structure, dict):
            return False

        if "wildcard" in query_structure:
            return True

        # Recursively check nested structures
        for value in query_structure.values():
            if isinstance(value, dict):
                if ElasticsearchParser.has_wildcard_query(value):
                    return True
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        if ElasticsearchParser.has_wildcard_query(item):
                            return True

        return False

    @staticmethod
    def has_script_query(query_structure: dict[str, Any]) -> bool:
        """Check if query contains scripts.

        Looks for script, script_score, and other script contexts.

        Args:
            query_structure: Query dict

        Returns:
            True if any script found
        """
        if not isinstance(query_structure, dict):
            return False

        script_keys = {"script", "script_score", "script_fields"}
        if any(key in query_structure for key in script_keys):
            return True

        # Recursively check nested structures
        for value in query_structure.values():
            if isinstance(value, dict):
                if ElasticsearchParser.has_script_query(value):
                    return True
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        if ElasticsearchParser.has_script_query(item):
                            return True

        return False

    @staticmethod
    def estimate_documents_examined(response: dict[str, Any]) -> int:
        """Estimate number of documents examined from response.

        For Elasticsearch, we estimate based on shard hits and profiling data.

        Args:
            response: Search response

        Returns:
            Estimated document count examined
        """
        # Simple heuristic: use total hits as estimate (ES doesn't expose docs examined)
        hits_info = response.get("hits", {})
        total_info = hits_info.get("total", {})

        if isinstance(total_info, dict):
            value = total_info.get("value", 0)
            return cast(int, value)
        if isinstance(total_info, int):
            return total_info
        return 0
