"""MySQL EXPLAIN plan parser and analyzer."""

import json
import re
from typing import Any


class MySQLExplainParser:
    """Parser for MySQL EXPLAIN FORMAT=JSON output.

    Analyzes EXPLAIN output, extracts table access patterns, identifies performance
    issues (full scans, filesort, temporary tables), and computes an optimization
    score (0-100) based on plan structure.
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
