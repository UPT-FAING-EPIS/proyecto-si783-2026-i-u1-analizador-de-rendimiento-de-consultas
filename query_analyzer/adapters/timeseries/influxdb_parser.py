"""InfluxDB Flux query parser using regex-based pattern matching."""

import re
from typing import Any


class InfluxDBFluxParser:
    """Regex-based parser for Flux query analysis and validation.

    Parses Flux query syntax using compiled regex patterns to extract:
    - Pipeline operations (from, range, filter, group, aggregation, etc.)
    - Time filters (range clause with start/stop parameters)
    - Measurement/bucket names
    - Field and tag filtering
    - Transformations (map, reduce, custom functions)
    - Group-by cardinality (number of grouping columns)

    Flux is InfluxDB's functional query language using pipe-based syntax (|>).
    Unlike SQL, Flux pipelines are sequential and don't form a tree structure.

    Attributes:
        pattern_from: Regex to extract bucket name from from(bucket:"...")
        pattern_range: Regex to extract time range from range(start:..., stop:...)
        pattern_filter: Regex to extract filter conditions
        pattern_group: Regex to extract group-by columns
        pattern_aggregation: Regex to detect aggregation functions
        pattern_map: Regex to count map() transformations
        pattern_reduce: Regex to count reduce() transformations
        pattern_custom_fn: Regex to detect custom function calls
    """

    def __init__(self) -> None:
        """Initialize parser with compiled regex patterns.

        Patterns are compiled once for efficiency across multiple parse operations.
        """
        # Pattern 1: Extract bucket name from from(bucket:"bucket_name")
        self.pattern_from = re.compile(r'from\s*\(\s*bucket\s*:\s*"([^"]+)"')

        # Pattern 2: Extract time range from range(start:VALUE, stop:VALUE)
        # Handles both quoted and unquoted values, including functions like now(), -1h
        # Uses lazy matching for stop value to handle nested parentheses in function calls
        self.pattern_range = re.compile(
            r"range\s*\(\s*start\s*:\s*([^,]+)\s*,\s*stop\s*:\s*(.+?)\s*\)"
        )

        # Pattern 3: Extract filter conditions
        self.pattern_filter = re.compile(r"\|\>\s*filter\s*\(\s*fn\s*:\s*([^)]+)\s*\)")

        # Pattern 4: Extract group-by columns from group(columns:[...])
        self.pattern_group = re.compile(r"\|\>\s*group\s*\(\s*columns\s*:\s*\[([^\]]+)\]\s*\)")

        # Pattern 5: Detect aggregation operations
        self.pattern_aggregation = re.compile(
            r"\|\>\s*(aggregateWindow|mean|sum|count|max|min|median|stddev|derivative)\s*\("
        )

        # Pattern 6: Count map() transformations
        self.pattern_map = re.compile(r"\|\>\s*map\s*\(")

        # Pattern 7: Count reduce() transformations
        self.pattern_reduce = re.compile(r"\|\>\s*reduce\s*\(")

        # Pattern 8: Detect custom function calls (anything with pipe and function call)
        self.pattern_custom_fn = re.compile(r"\|\>\s*(\w+)\s*\(")

    def parse_query(self, flux_query: str) -> dict[str, Any]:
        """Parse Flux query and extract structural information.

        Main entry point for Flux parsing. Applies all regex patterns to extract
        query structure, time filtering, transformations, and group-by information.

        Args:
            flux_query: Flux query string to analyze

        Returns:
            Dictionary containing:
                - bucket: str | None - Measurement bucket name
                - has_time_filter: bool - Whether query has range() clause
                - time_range: tuple[str, str] | None - (start, stop) times
                - measurements: list[str] - Measurement names (if extractable)
                - filters: list[str] - Filter conditions
                - group_by_columns: list[str] - Columns in group() clause
                - has_aggregation: bool - Whether query uses aggregation
                - transformation_count: int - Number of map/reduce operations
                - operations: list[str] - Sequence of pipe operations
        """
        query_clean = flux_query.strip()

        return {
            "bucket": self._extract_bucket(query_clean),
            "has_time_filter": self._has_time_filter(query_clean),
            "time_range": self._extract_time_range(query_clean),
            "measurements": self._extract_measurements(query_clean),
            "filters": self._extract_filters(query_clean),
            "group_by_columns": self._extract_group_by_columns(query_clean),
            "has_aggregation": self._has_aggregation(query_clean),
            "transformation_count": self._count_transformations(query_clean),
            "operations": self._extract_operations(query_clean),
        }

    def normalize_plan(self, parsed: dict[str, Any]) -> dict[str, Any]:
        """Convert parsed Flux structure to normalized engine-agnostic format.

        Normalizes Flux-specific structure to match the format used by
        AntiPatternDetector, which is independent of the database engine.

        Adds a flux_metadata field containing Flux-specific information not
        present in SQL engines.

        Args:
            parsed: Dictionary returned from parse_query()

        Returns:
            Dictionary with engine-agnostic normalized plan structure:
                - node_type: str - Always "Flux Pipeline"
                - table_name: str | None - Bucket name
                - actual_rows: None - Flux doesn't expose row counts
                - estimated_rows: None - Flux doesn't expose row counts
                - actual_time_ms: None - Populated by adapter
                - estimated_cost: None - Flux doesn't have cost model
                - index_used: None - Flux doesn't show index usage
                - filter_condition: None - Flux filters are complex
                - extra_info: list[str] - Issues and warnings
                - buffers: None - Not applicable to Flux
                - children: list - Empty (Flux is sequential, not tree)
                - flux_metadata: dict - Flux-specific details
        """
        return {
            "node_type": "Flux Pipeline",
            "table_name": parsed.get("bucket"),
            "actual_rows": None,
            "estimated_rows": None,
            "actual_time_ms": None,
            "estimated_cost": None,
            "index_used": None,
            "filter_condition": None,
            "extra_info": self._build_extra_info(parsed),
            "buffers": None,
            "children": [],
            # InfluxDB/Flux-specific metadata for anti-pattern detection
            "flux_metadata": {
                "operations": parsed.get("operations", []),
                "has_time_filter": parsed.get("has_time_filter", False),
                "time_range": parsed.get("time_range"),
                "group_by_columns": parsed.get("group_by_columns", []),
                "transformation_count": parsed.get("transformation_count", 0),
                "has_aggregation": parsed.get("has_aggregation", False),
            },
        }

    # =========================================================================
    # PRIVATE HELPER METHODS - Regex-based extraction
    # =========================================================================

    def _extract_bucket(self, query: str) -> str | None:
        """Extract bucket name from from(bucket:"...") clause.

        Args:
            query: Flux query string

        Returns:
            Bucket name or None if not found
        """
        match = self.pattern_from.search(query)
        return match.group(1) if match else None

    def _has_time_filter(self, query: str) -> bool:
        """Check if query has time filter via range() clause.

        Presence of range(start:X, stop:Y) indicates time filtering.

        Args:
            query: Flux query string

        Returns:
            True if query contains range() clause, False otherwise
        """
        return bool(self.pattern_range.search(query))

    def _extract_time_range(self, query: str) -> tuple[str, str] | None:
        """Extract start and stop times from range(start:..., stop:...) clause.

        Handles nested parentheses in function calls like now() by manually
        parsing the range clause instead of relying on regex lookahead.

        Args:
            query: Flux query string

        Returns:
            Tuple of (start_time, stop_time) or None if range not found
        """
        # Find the start of range( clause
        range_idx = query.find("range(")
        if range_idx == -1:
            return None

        # Find matching closing parenthesis by counting paren depth
        start_idx = range_idx + 6  # Skip "range("
        paren_depth = 1
        end_idx = start_idx

        while end_idx < len(query) and paren_depth > 0:
            if query[end_idx] == "(":
                paren_depth += 1
            elif query[end_idx] == ")":
                paren_depth -= 1
            end_idx += 1

        if paren_depth != 0:  # Unmatched parentheses
            return None

        # Extract content inside range(...)
        range_content = query[start_idx : end_idx - 1]

        # Parse start: and stop: values
        start_match = re.search(r"start\s*:\s*([^,]+)", range_content)
        stop_match = re.search(r"stop\s*:\s*(.+)$", range_content)

        if start_match and stop_match:
            start = start_match.group(1).strip()
            stop = stop_match.group(1).strip()
            return (start, stop)

        return None

    def _extract_filters(self, query: str) -> list[str]:
        """Extract all filter conditions from filter(fn:...) clauses.

        Args:
            query: Flux query string

        Returns:
            List of filter function expressions
        """
        matches = self.pattern_filter.findall(query)
        return matches

    def _extract_measurements(self, query: str) -> list[str]:
        """Extract measurement names from query.

        Looks for measurement references in filter conditions like
        r._measurement == "measurement_name".

        Args:
            query: Flux query string

        Returns:
            List of measurement names found
        """
        # Pattern to extract measurements from filter conditions like r._measurement == "name"
        pattern = re.compile(r'r\._measurement\s*==\s*"([^"]+)"')
        matches = pattern.findall(query)
        return matches

    def _extract_group_by_columns(self, query: str) -> list[str]:
        """Extract columns from group(columns:[...]) clause.

        Parses the column list to identify all grouping dimensions.

        Args:
            query: Flux query string

        Returns:
            List of column names in group-by clause
        """
        match = self.pattern_group.search(query)
        if match:
            columns_str = match.group(1)
            # Split by comma and clean up quotes
            columns = [col.strip().strip('"') for col in columns_str.split(",")]
            return columns
        return []

    def _count_transformations(self, query: str) -> int:
        """Count map(), reduce(), and custom transformation operations.

        Identifies expensive operations that add computational cost.

        Args:
            query: Flux query string

        Returns:
            Total count of transformation operations
        """
        count = 0

        # Count map() operations
        map_count = len(self.pattern_map.findall(query))
        count += map_count

        # Count reduce() operations
        reduce_count = len(self.pattern_reduce.findall(query))
        count += reduce_count

        return count

    def _has_aggregation(self, query: str) -> bool:
        """Check if query uses aggregation functions.

        Aggregation operations include mean, sum, count, aggregateWindow, etc.

        Args:
            query: Flux query string

        Returns:
            True if aggregation detected, False otherwise
        """
        return bool(self.pattern_aggregation.search(query))

    def _extract_operations(self, query: str) -> list[str]:
        """Extract sequence of pipe operations from query.

        Parses the pipeline to identify operation sequence in order.

        Args:
            query: Flux query string

        Returns:
            List of operation names in pipeline order
        """
        operations = []

        # Split by pipe operator and extract operation names
        parts = query.split("|>")

        # Skip first part (from clause) and process remaining operations
        for part in parts[1:]:
            # Extract operation name (before the opening parenthesis)
            operation = part.strip().split("(")[0].strip()
            if operation:
                operations.append(operation)

        return operations

    def _build_extra_info(self, parsed: dict[str, Any]) -> list[str]:
        """Build list of extra information and warnings about query.

        Identifies common issues visible from parsing (before execution).

        Args:
            parsed: Dictionary from parse_query()

        Returns:
            List of strings describing issues or concerns
        """
        info = []

        # CRITICAL: No time filter (unbounded query)
        if not parsed.get("has_time_filter", False):
            info.append("CRITICAL: No time filter (unbounded query - full bucket scan)")

        # WARNING: High transformation count
        transform_count = parsed.get("transformation_count", 0)
        if transform_count > 5:
            info.append(f"High transformation count: {transform_count} operations")

        # WARNING: High-cardinality group-by
        group_by = parsed.get("group_by_columns", [])
        if len(group_by) > 10:
            info.append(f"High cardinality group-by: {len(group_by)} columns")

        # INFO: No aggregation (if many transformations)
        if not parsed.get("has_aggregation", False) and transform_count > 2:
            info.append("No aggregation detected with multiple transformations")

        return info
