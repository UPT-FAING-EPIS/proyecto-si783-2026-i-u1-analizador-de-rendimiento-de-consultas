"""SQLite EXPLAIN QUERY PLAN Parser.

Parses the output of EXPLAIN QUERY PLAN and extracts operation details,
identifies full table scans, indexed searches, and generates warnings.
"""

import re
from typing import Any


class SQLiteExplainParser:
    """Parseador especializado para salidas EXPLAIN QUERY PLAN de SQLite.

    Analiza planes de ejecución en formato texto (EXPLAIN QUERY PLAN) con
    columnas separadas por tabulaciones: id, parent, notused, detail.
    Identifica operaciones de acceso a datos (full scans vs. indexed searches),
    detecta anti-patrones como scans innecesarios, y calcula una puntuación
    de optimización (0-100).

    Ejemplo de entrada:
        id  parent  notused  detail
        0   0       0        SCAN TABLE orders
        1   0       0        SEARCH TABLE users USING INDEX idx_users_id

    Atributos:
        table_row_threshold: Número estimado de filas para generar warnings
            en full scans (default: 1000; conservador para SQLite pequeño).
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

            node_id, parent, _, detail = parts[0], parts[1], parts[2], parts[3]

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

        scan_match = re.match(r"SCAN\s+(?:TABLE\s+)?(\w+)(?:\s+(.*))?", detail, re.IGNORECASE)
        if scan_match:
            table = scan_match.group(1)
            is_full_scan = True
            return {
                "operation": "SCAN_TABLE",
                "table": table,
                "uses_index": False,
                "is_full_scan": is_full_scan,
            }

        search_match = re.match(
            r"SEARCH\s+(?:TABLE\s+)?(\w+)\s+USING\s+(?:INDEX|INTEGER PRIMARY KEY|PRIMARY KEY)(?:\s+(\w+))?(?:\s+(.*))?",
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

        ⚠️ DEPRECATED (v1.0): This method is superseded by AntiPatternDetector.analyze().
        For new code, use AntiPatternDetector directly. This method will be removed in v2.0.

        Args:
            parsed_plan: Output from parse()

        Returns:
            List of warning messages
        """
        warnings = []

        if parsed_plan["full_scan_tables"]:
            for table in parsed_plan["full_scan_tables"]:
                warnings.append(f"Full table scan on '{table}' - Consider adding an index")

        if (
            parsed_plan["scan_count"] > 0
            and parsed_plan["search_count"] == 0
            and parsed_plan["total_nodes"] > 1
        ):
            warnings.append("Query uses only full table scans without index optimization")

        if parsed_plan["scan_count"] > 0 and parsed_plan["search_count"] > 0:
            warnings.append(
                "Mixed scan and search operations - Some tables are not properly indexed"
            )

        return warnings

    def generate_recommendations(self, warnings: list[str]) -> list[str]:
        """Generate actionable recommendations based on warnings.

        ⚠️ DEPRECATED (v1.0): This method is superseded by AntiPatternDetector.analyze().
        For new code, use AntiPatternDetector directly. This method will be removed in v2.0.

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

        ⚠️ DEPRECATED (v1.0): This method is superseded by AntiPatternDetector.analyze().
        For new code, use AntiPatternDetector directly. This method will be removed in v2.0.

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

    def normalize_plan(self, plan_line: str) -> dict[str, Any]:
        """Convert SQLite EXPLAIN QUERY PLAN text to normalized format (engine-agnostic).

        Converts SQLite text-based EXPLAIN QUERY PLAN output to a normalized format that can be
        used by the AntiPatternDetector, which is independent of the SQL engine.

        SQLite EXPLAIN format example:
        "0|0|0 SCAN TABLE customers (~100 rows)"
        "0|1|1 SEARCH TABLE orders USING AUTOINDEX ON (customer_id=?)"

        Args:
            plan_line: A single line from EXPLAIN QUERY PLAN output

        Returns:
            Normalized plan node with keys:
                - node_type: str ("Seq Scan" for SCAN, "Index Scan" for SEARCH)
                - table_name: str | None (extracted from SCAN/SEARCH TABLE <name>)
                - actual_rows: int | None (extracted from (~rows) annotation)
                - estimated_rows: int | None (same as actual_rows in SQLite)
                - actual_time_ms: None (not available in SQLite)
                - estimated_cost: None (not available in SQLite)
                - index_used: str | None (extracted from USING clause)
                - filter_condition: None (not available in SQLite EXPLAIN)
                - extra_info: list[str] (any additional info like AUTOINDEX)
                - buffers: None (not available in SQLite)
                - children: list[dict] (empty, SQLite doesn't provide hierarchical plans in text format)
        """
        if not plan_line:
            return {}

        # Parse SQLite EXPLAIN QUERY PLAN format: "id|parent|notused OPERATION"
        # Example: "0|0|0 SCAN TABLE customers (~100 rows)"

        # Extract operation part (after the "id|parent|notused" prefix)
        match = re.match(r"^[\d\|]+\s+(.*)$", plan_line.strip())
        if not match:
            return {}

        operation = match.group(1)

        # Determine node type and extract details
        if "SCAN TABLE" in operation:
            node_type = "Seq Scan"
            table_match = re.search(r"SCAN TABLE (\w+)", operation)
            table_name = table_match.group(1) if table_match else None
            index_used = None

        elif "SEARCH TABLE" in operation:
            node_type = "Index Scan"
            table_match = re.search(r"SEARCH TABLE (\w+)", operation)
            table_name = table_match.group(1) if table_match else None

            # Extract index name from USING clause
            index_match = re.search(r"USING (\w+)", operation)
            index_used = index_match.group(1) if index_match else None

        else:
            # Other operations (COMPOUND, MATERIALIZE, etc.)
            node_type = operation.split()[0] if operation else "Unknown"
            table_name = None
            index_used = None

        # Extract row count estimate (SQLite format: ~100 rows)
        rows_match = re.search(r"\(~(\d+) rows?\)", operation)
        rows = int(rows_match.group(1)) if rows_match else None

        # Extract extra info (e.g., AUTOINDEX, condition info)
        extra_info = []
        if "AUTOINDEX" in operation:
            extra_info.append("AUTOINDEX")

        return {
            "node_type": node_type,
            "table_name": table_name,
            "actual_rows": rows,
            "estimated_rows": rows,  # SQLite provides same estimate
            "actual_time_ms": None,  # Not available in SQLite
            "estimated_cost": None,  # Not available in SQLite
            "index_used": index_used,
            "filter_condition": None,  # Not provided in text format
            "extra_info": extra_info,
            "buffers": None,  # Not available in SQLite
            "children": [],  # SQLite EXPLAIN doesn't provide hierarchical plans
        }
