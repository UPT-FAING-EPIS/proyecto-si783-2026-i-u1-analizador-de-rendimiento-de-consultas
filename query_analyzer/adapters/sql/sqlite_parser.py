"""SQLite EXPLAIN QUERY PLAN Parser.

Parses the output of EXPLAIN QUERY PLAN and extracts operation details,
identifies full table scans, indexed searches, and generates warnings.
"""

import re
from typing import Any


class SQLiteExplainParser:
    """Parser for SQLite EXPLAIN QUERY PLAN output.

    SQLite produces tab-separated output with columns: id, parent, notused, detail
    Example:
        id  parent  notused  detail
        0   0       0        SCAN TABLE orders
        1   0       0        SEARCH TABLE users USING INDEX idx_users_id
    """

    def __init__(self, table_row_threshold: int = 1000):
        """Initialize parser with configuration.

        Args:
            table_row_threshold: Estimated row count to trigger warnings on full scans.
                                Default 1000 (conservative for small SQLite databases).
        """
        self.table_row_threshold = table_row_threshold

    def parse(self, explain_output: str) -> dict[str, Any]:
        """Parse EXPLAIN QUERY PLAN output.

        Args:
            explain_output: Raw output from EXPLAIN QUERY PLAN (tab-separated text)

        Returns:
            Dict with structure:
            {
                "raw_plan": str,
                "nodes": list[dict],
                "full_scan_tables": list[str],
                "indexed_searches": list[str],
                "scan_count": int,
                "search_count": int,
                "total_nodes": int
            }
        """
        nodes = []
        full_scan_tables = []
        indexed_searches = []

        lines = explain_output.strip().split("\n")
        if not lines:
            return self._empty_plan()

        start_idx = 0
        if "id" in lines[0].lower() or "parent" in lines[0].lower():
            start_idx = 1

        for line in lines[start_idx:]:
            if not line.strip():
                continue

            parts = line.split("\t")
            if len(parts) < 4:
                continue

            node_id, parent, notused, detail = parts[0], parts[1], parts[2], parts[3]

            op_info = self._extract_operation_info(detail)

            node = {
                "id": int(node_id),
                "parent": int(parent),
                "detail": detail,
                "operation": op_info["operation"],
                "table": op_info.get("table"),
                "index": op_info.get("index"),
                "uses_index": op_info["uses_index"],
                "is_full_scan": op_info["is_full_scan"],
            }
            nodes.append(node)

            if op_info["is_full_scan"] and op_info.get("table"):
                if op_info["table"] not in full_scan_tables:
                    full_scan_tables.append(op_info["table"])

            if op_info["uses_index"] and op_info.get("table"):
                if op_info["table"] not in indexed_searches:
                    indexed_searches.append(op_info["table"])

        return {
            "raw_plan": explain_output,
            "nodes": nodes,
            "full_scan_tables": full_scan_tables,
            "indexed_searches": indexed_searches,
            "scan_count": sum(1 for n in nodes if not n["uses_index"]),
            "search_count": sum(1 for n in nodes if n["uses_index"]),
            "total_nodes": len(nodes),
        }

    def _extract_operation_info(self, detail: str) -> dict[str, Any]:
        """Extract operation type and details from detail string.

        Args:
            detail: Detail string from EXPLAIN output

        Returns:
            Dict with: operation, table, index, uses_index, is_full_scan
        """
        detail = detail.strip()

        scan_match = re.match(
            r"SCAN\s+(?:TABLE\s+)?(\w+)(?:\s+(.*))?", detail, re.IGNORECASE
        )
        if scan_match:
            table = scan_match.group(1)
            where_clause = scan_match.group(2) or ""
            is_full_scan = True
            return {
                "operation": "SCAN_TABLE",
                "table": table,
                "uses_index": False,
                "is_full_scan": is_full_scan,
            }

        search_match = re.match(
            r"SEARCH\s+(?:TABLE\s+)?(\w+)\s+USING\s+(?:INDEX|PRIMARY KEY)\s+(\w+)(?:\s+(.*))?",
            detail,
            re.IGNORECASE,
        )
        if search_match:
            table = search_match.group(1)
            index = search_match.group(2)
            return {
                "operation": "SEARCH_TABLE_WITH_INDEX",
                "table": table,
                "index": index,
                "uses_index": True,
                "is_full_scan": False,
            }

        if "EXECUTE CORRELATED SCALAR SUBQUERY" in detail:
            return {
                "operation": "CORRELATED_SUBQUERY",
                "uses_index": False,
                "is_full_scan": False,
            }

        if "USE TEMP B-TREE" in detail:
            return {
                "operation": "TEMP_BTREE",
                "uses_index": False,
                "is_full_scan": False,
            }

        return {
            "operation": "UNKNOWN",
            "uses_index": False,
            "is_full_scan": False,
        }

    def identify_warnings(self, parsed_plan: dict[str, Any]) -> list[str]:
        """Identify query optimization issues.

        Args:
            parsed_plan: Output from parse()

        Returns:
            List of warning messages
        """
        warnings = []

        if parsed_plan["full_scan_tables"]:
            for table in parsed_plan["full_scan_tables"]:
                warnings.append(
                    f"Full table scan on '{table}' - Consider adding an index"
                )

        if (
            parsed_plan["scan_count"] > 0
            and parsed_plan["search_count"] == 0
            and parsed_plan["total_nodes"] > 1
        ):
            warnings.append(
                "Query uses only full table scans without index optimization"
            )

        if parsed_plan["scan_count"] > 0 and parsed_plan["search_count"] > 0:
            warnings.append(
                "Mixed scan and search operations - Some tables are not properly indexed"
            )

        return warnings

    def generate_recommendations(self, warnings: list[str]) -> list[str]:
        """Generate actionable recommendations based on warnings.

        Args:
            warnings: List from identify_warnings()

        Returns:
            List of recommendation strings
        """
        recommendations = []

        if not warnings:
            recommendations.append("Query is well-optimized with proper indexing")
            return recommendations

        for warning in warnings:
            if "Full table scan" in warning:
                match = re.search(r"on '(\w+)'", warning)
                if match:
                    table = match.group(1)
                    recommendations.append(
                        f"Add an index on the WHERE clause column(s) of table '{table}'"
                    )

            if "Mixed scan and search" in warning:
                recommendations.append(
                    "Review index strategy - ensure all joined tables use indexes"
                )

            if "only full table scans" in warning:
                recommendations.append(
                    "Add indexes on columns used in WHERE clauses and JOIN conditions"
                )

        return recommendations

    def calculate_score(self, parsed_plan: dict[str, Any], warnings: list[str]) -> int:
        """Calculate optimization score (0-100).

        Scoring logic:
        - Base: 100
        - Full scan without index: -35 per scan
        - Multiple scans: -20
        - Mix of scans/searches: -20
        - Perfect (all indexed): +0

        Args:
            parsed_plan: Output from parse()
            warnings: Output from identify_warnings()

        Returns:
            Integer score 0-100
        """
        score = 100

        if parsed_plan["full_scan_tables"]:
            score -= min(35, 35 * len(parsed_plan["full_scan_tables"]))

        if parsed_plan["scan_count"] > 1:
            score -= 20

        if parsed_plan["scan_count"] > 0 and parsed_plan["search_count"] > 0:
            score -= 20

        return max(0, min(100, score))

    def _empty_plan(self) -> dict[str, Any]:
        """Return empty plan structure."""
        return {
            "raw_plan": "",
            "nodes": [],
            "full_scan_tables": [],
            "indexed_searches": [],
            "scan_count": 0,
            "search_count": 0,
            "total_nodes": 0,
        }
