"""MySQL EXPLAIN plan parser and analyzer."""

import json
import re
from typing import Any


class MySQLExplainParser:
    """Parseador especializado para salidas EXPLAIN de MySQL.

    Analiza planes de ejecución en formato JSON (EXPLAIN FORMAT=JSON) para
    extraer patrones de acceso a datos y detectar anti-patrones de rendimiento.
    Identifica problemas comunes como full table scans, uso de filesort,
    creación de tablas temporales, y calcula una puntuación de optimización
    (0-100) basada en la estructura del plan.

    Métodos principales:
        - parse(): Parsea JSON de EXPLAIN y extrae métricas
        - identify_warnings(): Detecta anti-patrones
        - generate_recommendations(): Sugiere optimizaciones
        - calculate_score(): Genera puntuación 0-100
    """

    def parse(self, json_output: str) -> dict[str, Any]:
        """Parse EXPLAIN FORMAT=JSON output and extract metrics.

        Args:
            json_output: Complete EXPLAIN FORMAT=JSON output as string

        Returns:
            Dictionary with:
                - raw_json: Original JSON string
                - query_block: Parsed query block
                - tables_accessed: List of table access info
                - has_using_filesort: Whether external sort is used
                - has_using_temporary: Whether temporary table is used
                - has_full_scan: Whether full table scan exists
                - total_rows_examined: Total rows examined across all tables
        """
        try:
            data = json.loads(json_output)
        except json.JSONDecodeError:
            return self._empty_result()

        parsed = self._empty_result()
        parsed["raw_json"] = json_output

        if "query_block" not in data:
            return parsed

        query_block = data["query_block"]
        parsed["query_block"] = query_block

        self._extract_tables(query_block, parsed)

        return parsed

    def _empty_result(self) -> dict[str, Any]:
        """Create empty result dict with default values.

        Returns:
            Empty result dictionary with initialized fields
        """
        return {
            "raw_json": "",
            "query_block": {},
            "tables_accessed": [],
            "has_using_filesort": False,
            "has_using_temporary": False,
            "has_full_scan": False,
            "total_rows_examined": 0,
        }

    def _extract_tables(self, query_block: dict, result: dict) -> None:
        """Recursively extract table access information from query block.

        Args:
            query_block: Current query block dictionary
            result: Result accumulator dictionary
        """
        if "table" in query_block:
            table_info = query_block["table"]
            self._process_table(table_info, result)

        if "nested_loop" in query_block:
            for nested_item in query_block["nested_loop"]:
                self._extract_tables(nested_item, result)

        if "union_result" in query_block:
            union = query_block["union_result"]
            if "query_block" in union:
                self._extract_tables(union["query_block"], result)

        if "order_by" in query_block:
            order_items = query_block["order_by"]
            if isinstance(order_items, list):
                for item in order_items:
                    if isinstance(item, dict) and item.get("filesort") is True:
                        result["has_using_filesort"] = True

    def _process_table(self, table_info: dict, result: dict) -> None:
        """Process individual table access information.

        Args:
            table_info: Table information dictionary from EXPLAIN output
            result: Result accumulator dictionary
        """
        table_name = table_info.get("table_name", "unknown")
        access_type = table_info.get("access_type", "unknown").upper()
        key_used = table_info.get("key")
        rows_examined = table_info.get("rows_examined", 0)
        extra = table_info.get("extra", [])

        result["total_rows_examined"] += rows_examined

        is_full_scan = access_type == "ALL"
        if is_full_scan:
            result["has_full_scan"] = True

        if isinstance(extra, list):
            for extra_item in extra:
                if isinstance(extra_item, dict):
                    if extra_item.get("using_temporary_table") is True:
                        result["has_using_temporary"] = True
                    extra_desc = extra_item.get("description", "")
                    if "filesort" in extra_desc.lower():
                        result["has_using_filesort"] = True
                    if "temporary" in extra_desc.lower():
                        result["has_using_temporary"] = True
                elif isinstance(extra_item, str):
                    if "filesort" in extra_item.lower():
                        result["has_using_filesort"] = True
                    if "temporary" in extra_item.lower():
                        result["has_using_temporary"] = True

        result["tables_accessed"].append(
            {
                "table_name": table_name,
                "access_type": access_type,
                "key_used": key_used,
                "rows_examined": rows_examined,
                "is_full_scan": is_full_scan,
            }
        )

    def identify_warnings(self, parsed_plan: dict[str, Any]) -> list[str]:
        """Identify performance warnings in the execution plan.

        ⚠️ DEPRECATED (v1.0): This method is superseded by AntiPatternDetector.analyze().
        For new code, use AntiPatternDetector directly. This method will be removed in v2.0.

        Args:
            parsed_plan: Parsed EXPLAIN output from parse()

        Returns:
            List of warning messages describing performance issues
        """
        warnings = []

        full_scan_tables = [
            t["table_name"] for t in parsed_plan.get("tables_accessed", []) if t.get("is_full_scan")
        ]
        if full_scan_tables:
            for table in full_scan_tables:
                warnings.append(
                    f"Full table scan detected on '{table}': type=ALL. "
                    "This scans entire table without using an index."
                )

        if parsed_plan.get("has_using_filesort"):
            warnings.append(
                "Using filesort: MySQL cannot use an index for ORDER BY "
                "and must perform an extra sort pass."
            )

        if parsed_plan.get("has_using_temporary"):
            warnings.append(
                "Using temporary table: MySQL must create a temporary table "
                "for GROUP BY or DISTINCT, often impacting performance."
            )

        return warnings

    def generate_recommendations(self, warnings: list[str]) -> list[str]:
        """Generate optimization recommendations based on identified warnings.

        ⚠️ DEPRECATED (v1.0): This method is superseded by AntiPatternDetector.analyze().
        For new code, use AntiPatternDetector directly. This method will be removed in v2.0.

        Args:
            warnings: List of warning messages from identify_warnings()

        Returns:
            List of actionable optimization recommendations
        """
        recommendations = []

        for warning in warnings:
            if "Full table scan" in warning:
                table_match = re.search(r"'([^']+)'", warning)
                if table_match:
                    table = table_match.group(1)
                    recommendations.append(
                        f"Add or improve index on WHERE clause columns for table '{table}'"
                    )
                else:
                    recommendations.append(
                        "Add index on WHERE clause columns to avoid full table scan"
                    )

            elif "Using filesort" in warning:
                recommendations.append("Create index on ORDER BY columns to avoid external sort")

            elif "Using temporary" in warning:
                recommendations.append(
                    "Optimize GROUP BY/DISTINCT query or add appropriate indexes"
                )

        return recommendations

    def calculate_score(self, parsed_plan: dict[str, Any], warnings: list[str]) -> int:
        """Calculate optimization score for the query plan.

        ⚠️ DEPRECATED (v1.0): This method is superseded by AntiPatternDetector.analyze().
        For new code, use AntiPatternDetector directly. This method will be removed in v2.0.

        Args:
            parsed_plan: Parsed EXPLAIN output from parse()
            warnings: List of warnings from identify_warnings()

        Returns:
            Score between 0 and 100, where 100 is optimal
        """
        score = 100

        full_scan_count = sum(
            1 for t in parsed_plan.get("tables_accessed", []) if t.get("is_full_scan")
        )
        score -= full_scan_count * 30

        if parsed_plan.get("has_using_temporary"):
            score -= 20

        if parsed_plan.get("has_using_filesort"):
            score -= 15

        return max(0, min(100, score))

    def normalize_plan(self, plan: dict) -> dict:
        """Convert MySQL EXPLAIN plan to normalized format (engine-agnostic).

        Converts MySQL EXPLAIN FORMAT=JSON plan structure to a normalized format that can be
        used by the AntiPatternDetector, which is independent of the SQL engine.

        Args:
            plan: EXPLAIN output dictionary from MySQL

        Returns:
            Normalized plan node with keys:
                - node_type: str (mapped from access_type: ALL -> "Seq Scan", etc.)
                - table_name: str | None
                - actual_rows: int | None (mapped from rows_examined)
                - estimated_rows: int | None (mapped from rows)
                - actual_time_ms: float | None (not available in MySQL)
                - estimated_cost: float | None (not available in MySQL)
                - index_used: str | None (mapped from 'key' field)
                - filter_condition: str | None (extracted from 'filtered')
                - extra_info: list[str] (from 'extra' field, e.g., "Using filesort")
                - buffers: None (not available in MySQL)
                - children: list[dict] (normalized child nodes from 'nested_loop')
        """
        if not plan:
            return {}

        # Extract table info
        table_data = plan.get("table", {})
        table_name = table_data.get("table_name")

        # Map MySQL access_type to standard node_type
        access_type = table_data.get("access_type", "UNKNOWN")
        node_type_map = {
            "ALL": "Seq Scan",
            "const": "Index Scan",
            "eq_ref": "Index Scan",
            "ref": "Index Scan",
            "range": "Index Scan",
            "index": "Index Scan",
            "index_merge": "Index Scan",
            "system": "Index Scan",
        }
        node_type = node_type_map.get(access_type, f"Scan({access_type})")

        # Extract row counts (MySQL uses "rows" for estimated, "rows_examined" for actual)
        rows_examined = table_data.get("rows_examined")
        estimated_rows = table_data.get("rows")

        # Extract index information
        index_used = table_data.get("key")

        # Extract extra information
        extra_info = []
        extra_list = table_data.get("extra", [])
        if extra_list:
            for extra in extra_list:
                if "extra_info" in extra:
                    extra_info.append(extra["extra_info"])

        # Filter condition (MySQL doesn't provide this directly in the plan,
        # but we can infer from the query structure if needed)
        filter_condition = None

        # Recursively normalize nested loops (MySQL sub-queries/joins)
        children = []
        for nested_loop in plan.get("nested_loop", []):
            children.append(self.normalize_plan({"table": nested_loop}))

        return {
            "node_type": node_type,
            "table_name": table_name,
            "actual_rows": rows_examined,
            "estimated_rows": estimated_rows,
            "actual_time_ms": None,  # Not available in MySQL EXPLAIN
            "estimated_cost": None,  # Not available in MySQL EXPLAIN
            "index_used": index_used,
            "filter_condition": filter_condition,
            "extra_info": extra_info,
            "buffers": None,  # Not available in MySQL
            "children": children,
        }
